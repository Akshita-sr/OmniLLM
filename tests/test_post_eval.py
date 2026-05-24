"""Tests for scripts/evaluate_session.py — the unified post-session evaluator.

This file replaces the deleted tests/test_evaluator.py and tests/test_scorer.py
which used to cover the old standalone omnillm/evaluator.py + omnillm/scorer.py
modules. Their logic now lives inside scripts/evaluate_session.py, so the
tests target the helpers in that script.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest


# ── Module loader ─────────────────────────────────────────────────────────────
# WHAT:  scripts/evaluate_session.py is not a normal package (no __init__.py
#        in scripts/), so we load it by file path with importlib. That gives
#        us access to all its helpers (EloBoard, _run_judge, etc.) for tests.
# WHY:   Keeping the script outside the package boundary stops accidental
#        live-pipeline imports of the evaluation helpers. The tests pay the
#        small cost of importing it manually.

_SCRIPT_PATH = Path(__file__).parent.parent / "scripts" / "evaluate_session.py"


def _load_eval_module():
    """Import scripts/evaluate_session.py as a module named 'evaluate_session'."""
    spec = importlib.util.spec_from_file_location("evaluate_session", _SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["evaluate_session"] = module
    spec.loader.exec_module(module)
    return module


eval_mod = _load_eval_module()


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 1: EloBoard (was omnillm/scorer.py:EloScorer)
# ══════════════════════════════════════════════════════════════════════════════

class TestEloBoard:
    def test_init_defaults(self):
        board = eval_mod.EloBoard()
        assert board.k_factor == 32
        assert board.default_rating == 1500
        assert board.ratings == {}
        assert board.matches_played == {}

    def test_init_custom_params(self):
        board = eval_mod.EloBoard(k_factor=16, default_rating=1200)
        assert board.k_factor == 16
        assert board.default_rating == 1200

    def test_expected_equal_ratings(self):
        board = eval_mod.EloBoard()
        assert board._expected(1500, 1500) == pytest.approx(0.5)

    def test_expected_higher_rating_wins_more_often(self):
        board = eval_mod.EloBoard()
        assert board._expected(1600, 1400) > 0.5
        assert board._expected(1400, 1600) < 0.5

    def test_expected_scores_sum_to_one(self):
        board = eval_mod.EloBoard()
        ea = board._expected(1700, 1300)
        eb = board._expected(1300, 1700)
        assert ea + eb == pytest.approx(1.0)

    def test_record_match_initialises_models(self):
        board = eval_mod.EloBoard()
        board.record_match("a", "b", "model_a")
        assert "a" in board.ratings
        assert "b" in board.ratings

    def test_winner_gains_rating(self):
        board = eval_mod.EloBoard()
        board.record_match("a", "b", "model_a")
        assert board.ratings["a"] > 1500
        assert board.ratings["b"] < 1500

    def test_loser_loses_rating(self):
        board = eval_mod.EloBoard()
        board.record_match("a", "b", "model_b")
        assert board.ratings["b"] > 1500
        assert board.ratings["a"] < 1500

    def test_tie_keeps_ratings_close(self):
        board = eval_mod.EloBoard()
        board.record_match("a", "b", "tie")
        assert board.ratings["a"] == pytest.approx(1500, abs=1)
        assert board.ratings["b"] == pytest.approx(1500, abs=1)

    def test_increments_matches_played(self):
        board = eval_mod.EloBoard()
        board.record_match("a", "b", "model_a")
        board.record_match("a", "b", "model_b")
        assert board.matches_played["a"] == 2
        assert board.matches_played["b"] == 2

    def test_record_match_returns_before_after(self):
        board = eval_mod.EloBoard()
        ra_b, rb_b, ra_a, rb_a = board.record_match("a", "b", "model_a")
        assert ra_b == 1500.0 and rb_b == 1500.0
        assert ra_a > 1500.0 and rb_a < 1500.0

    def test_leaderboard_sorted_descending(self):
        board = eval_mod.EloBoard()
        for _ in range(3):
            board.record_match("strong", "weak", "model_a")
        lb = board.leaderboard()
        assert lb[0][0] == "strong"
        assert lb[0][1] > lb[1][1]

    def test_get_rating_default(self):
        board = eval_mod.EloBoard()
        assert board.get_rating("never-seen") == 1500

    def test_get_rating_updated(self):
        board = eval_mod.EloBoard()
        board.record_match("a", "b", "model_a")
        assert board.get_rating("a") > 1500

    def test_zero_sum_property(self):
        """Total rating across two players must be conserved (zero-sum)."""
        board = eval_mod.EloBoard()
        board.record_match("a", "b", "model_a")
        assert board.ratings["a"] + board.ratings["b"] == pytest.approx(3000)

    def test_history_recorded(self):
        board = eval_mod.EloBoard()
        board.record_match("a", "b", "model_a", category="reasoning")
        assert len(board.history) == 1
        m = board.history[0]
        assert m.category == "reasoning"
        assert m.winner == "model_a"


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 2: _judge_score_to_elo_winner
# ══════════════════════════════════════════════════════════════════════════════

class TestJudgeScoreToEloWinner:
    def test_a_wins_clearly(self):
        assert eval_mod._judge_score_to_elo_winner(0.9, 0.5) == "model_a"

    def test_b_wins_clearly(self):
        assert eval_mod._judge_score_to_elo_winner(0.4, 0.85) == "model_b"

    def test_close_scores_are_tie(self):
        # Anything within 0.05 of each other is a tie (judge noise floor).
        assert eval_mod._judge_score_to_elo_winner(0.80, 0.83) == "tie"

    def test_exact_equality_is_tie(self):
        assert eval_mod._judge_score_to_elo_winner(0.7, 0.7) == "tie"


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 3: _run_judge (was omnillm/evaluator.py LLM-as-Judge logic)
# ══════════════════════════════════════════════════════════════════════════════

def _mock_gateway_with_judge_text(judge_text: str) -> MagicMock:
    """Build a MagicMock LLMGateway whose .query returns the given text."""
    from omnillm.gateway import ModelResponse

    gw = MagicMock()
    gw.query = AsyncMock(
        return_value=ModelResponse(model_id="openai-gpt4o", content=judge_text)
    )
    return gw


class TestRunJudge:
    @pytest.mark.asyncio
    async def test_parses_clean_json(self):
        gw = _mock_gateway_with_judge_text(
            '{"score": 0.8, "reasoning": "good answer"}'
        )
        score, reasoning = await eval_mod._run_judge(gw, "openai-gpt4o", "q?", "a")
        assert score == pytest.approx(0.8)
        assert "good answer" in reasoning

    @pytest.mark.asyncio
    async def test_strips_markdown_fences(self):
        gw = _mock_gateway_with_judge_text(
            '```json\n{"score": 0.5, "reasoning": "ok"}\n```'
        )
        score, _ = await eval_mod._run_judge(gw, "openai-gpt4o", "q", "a")
        assert score == pytest.approx(0.5)

    @pytest.mark.asyncio
    async def test_clamps_above_one(self):
        gw = _mock_gateway_with_judge_text(
            '{"score": 1.5, "reasoning": "over max"}'
        )
        score, _ = await eval_mod._run_judge(gw, "openai-gpt4o", "q", "a")
        assert score <= 1.0

    @pytest.mark.asyncio
    async def test_clamps_below_zero(self):
        gw = _mock_gateway_with_judge_text(
            '{"score": -0.5, "reasoning": "under min"}'
        )
        score, _ = await eval_mod._run_judge(gw, "openai-gpt4o", "q", "a")
        assert score >= 0.0

    @pytest.mark.asyncio
    async def test_regex_fallback_for_malformed_json(self):
        gw = _mock_gateway_with_judge_text("score is 0.73 because reasons")
        score, _ = await eval_mod._run_judge(gw, "openai-gpt4o", "q", "a")
        assert score == pytest.approx(0.73)

    @pytest.mark.asyncio
    async def test_default_when_unparseable(self):
        gw = _mock_gateway_with_judge_text("complete garbage no numbers")
        score, reasoning = await eval_mod._run_judge(gw, "openai-gpt4o", "q", "a")
        assert score == pytest.approx(0.5)
        assert "unparseable" in reasoning


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 4: _row_to_csv_dict — the CSV projection
# ══════════════════════════════════════════════════════════════════════════════

class TestRowToCsvDict:
    def test_basic_row_has_all_columns(self):
        row = {
            "session_id": "s1", "participant_id": "P001",
            "task_type": "info_retrieval", "utterance": "q", "response": "a",
            "model_id": "openai-gpt4o-mini",
        }
        out = eval_mod._row_to_csv_dict(row)
        for col in eval_mod.CSV_COLUMNS:
            assert col in out, f"missing column: {col}"

    def test_utterance_becomes_user_input(self):
        out = eval_mod._row_to_csv_dict({"utterance": "hello"})
        assert out["user_input"] == "hello"

    def test_input_tokens_becomes_prompt_tokens(self):
        out = eval_mod._row_to_csv_dict({"input_tokens": 42})
        assert out["prompt_tokens"] == 42

    def test_council_model_id_is_flagged(self):
        out = eval_mod._row_to_csv_dict({
            "model_id": "council:gpt4o-mini+claude-haiku+gemini-flash",
        })
        assert out["was_consensus"] is True
        assert out["council_models"] == "gpt4o-mini;claude-haiku;gemini-flash"

    def test_council_safe_prefix_also_flagged(self):
        out = eval_mod._row_to_csv_dict({
            "model_id": "council-safe:a+b",
        })
        assert out["was_consensus"] is True
        assert out["council_models"] == "a;b"

    def test_non_council_not_flagged(self):
        out = eval_mod._row_to_csv_dict({"model_id": "openai-gpt4o-mini"})
        assert out["was_consensus"] is False
        assert out["council_models"] == ""

    def test_success_none_becomes_empty(self):
        out = eval_mod._row_to_csv_dict({"task_success": None})
        assert out["success"] == ""

    def test_success_true_preserved(self):
        out = eval_mod._row_to_csv_dict({"task_success": True})
        assert out["success"] is True


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 5: _build_cost_summary
# ══════════════════════════════════════════════════════════════════════════════

class TestBuildCostSummary:
    def test_total_cost_summed(self):
        rows = [
            {"model_id": "a", "cost_usd": 0.001, "session_id": "s1"},
            {"model_id": "b", "cost_usd": 0.002, "session_id": "s1"},
        ]
        summary = eval_mod._build_cost_summary(rows)
        assert summary["total_cost_usd"] == pytest.approx(0.003)
        assert summary["total_calls"] == 2

    def test_grouped_by_model_sorted_by_cost_desc(self):
        rows = [
            {"model_id": "cheap", "cost_usd": 0.001},
            {"model_id": "expensive", "cost_usd": 0.010},
            {"model_id": "cheap", "cost_usd": 0.001},
        ]
        summary = eval_mod._build_cost_summary(rows)
        ordered = list(summary["by_model"].keys())
        assert ordered[0] == "expensive"
        assert summary["by_model"]["cheap"]["calls"] == 2

    def test_grouped_by_session(self):
        rows = [
            {"model_id": "a", "cost_usd": 0.5, "session_id": "s1"},
            {"model_id": "a", "cost_usd": 0.3, "session_id": "s2"},
        ]
        summary = eval_mod._build_cost_summary(rows)
        assert summary["by_session"]["s1"] == pytest.approx(0.5)
        assert summary["by_session"]["s2"] == pytest.approx(0.3)

    def test_missing_fields_default_to_zero(self):
        # A row with no cost / tokens at all should not raise.
        rows = [{"model_id": "x"}]
        summary = eval_mod._build_cost_summary(rows)
        assert summary["total_cost_usd"] == 0.0
        assert summary["by_model"]["x"]["cost_usd"] == 0.0


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 6: _load_log — supports JSON array AND JSONL
# ══════════════════════════════════════════════════════════════════════════════

class TestLoadLog:
    def test_loads_json_array(self, tmp_path: Path):
        p = tmp_path / "log.json"
        p.write_text(json.dumps([{"a": 1}, {"a": 2}]))
        rows = eval_mod._load_log(p)
        assert rows == [{"a": 1}, {"a": 2}]

    def test_loads_jsonl(self, tmp_path: Path):
        p = tmp_path / "log.jsonl"
        p.write_text('{"a": 1}\n{"a": 2}\n')
        rows = eval_mod._load_log(p)
        assert rows == [{"a": 1}, {"a": 2}]

    def test_blank_file_returns_empty(self, tmp_path: Path):
        p = tmp_path / "empty.json"
        p.write_text("")
        assert eval_mod._load_log(p) == []

    def test_jsonl_skips_blank_lines(self, tmp_path: Path):
        p = tmp_path / "log.jsonl"
        p.write_text('{"a": 1}\n\n{"a": 2}\n')
        assert len(eval_mod._load_log(p)) == 2


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 7: _run_elo_pass — synthetic pairwise from same-task-type rows
# ══════════════════════════════════════════════════════════════════════════════

class TestRunEloPass:
    def test_no_matches_when_only_one_model_per_task(self):
        rows = [
            {"task_type": "info_retrieval", "model_id": "a", "judge_score": 0.9},
        ]
        out, board = eval_mod._run_elo_pass(rows)
        assert board.history == []
        assert out[0]["elo_rating_before"] == 1500
        assert out[0]["elo_rating_after"] == 1500

    def test_pair_in_same_task_creates_match(self):
        rows = [
            {"task_type": "info_retrieval", "model_id": "a", "judge_score": 0.9},
            {"task_type": "info_retrieval", "model_id": "b", "judge_score": 0.5},
        ]
        _, board = eval_mod._run_elo_pass(rows)
        assert len(board.history) == 1
        assert board.history[0].winner == "model_a"
        assert board.get_rating("a") > 1500

    def test_skips_rows_without_judge_score(self):
        rows = [
            {"task_type": "info_retrieval", "model_id": "a", "judge_score": -1.0},
            {"task_type": "info_retrieval", "model_id": "b", "judge_score": 0.7},
        ]
        _, board = eval_mod._run_elo_pass(rows)
        assert board.history == []

    def test_self_match_skipped(self):
        # Same model_id twice on the same task — meaningless pair.
        rows = [
            {"task_type": "navigation", "model_id": "a", "judge_score": 0.9},
            {"task_type": "navigation", "model_id": "a", "judge_score": 0.5},
        ]
        _, board = eval_mod._run_elo_pass(rows)
        assert board.history == []
