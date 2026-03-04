"""Tests for omnillm.scorer — ELO Rating System module."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from omnillm.scorer import EloScorer


class TestEloScorer:
    """Tests for the EloScorer class."""

    def test_init_defaults(self):
        scorer = EloScorer()
        assert scorer.k_factor == 32
        assert scorer.default_rating == 1500
        assert scorer.ratings == {}
        assert scorer.matches_played == {}

    def test_init_custom_params(self):
        scorer = EloScorer(k_factor=16, default_rating=1200)
        assert scorer.k_factor == 16
        assert scorer.default_rating == 1200

    def test_expected_score_equal_ratings(self):
        scorer = EloScorer()
        # Equal ratings → 50% expected score
        score = scorer.expected_score(1500, 1500)
        assert score == pytest.approx(0.5)

    def test_expected_score_higher_rated(self):
        scorer = EloScorer()
        # Higher-rated player should have > 50% expected score
        score = scorer.expected_score(1600, 1400)
        assert score > 0.5

    def test_expected_score_lower_rated(self):
        scorer = EloScorer()
        score = scorer.expected_score(1400, 1600)
        assert score < 0.5

    def test_expected_scores_sum_to_one(self):
        scorer = EloScorer()
        ea = scorer.expected_score(1700, 1300)
        eb = scorer.expected_score(1300, 1700)
        assert ea + eb == pytest.approx(1.0)

    def test_record_match_initialises_models(self):
        scorer = EloScorer()
        scorer.record_match("model-a", "model-b", "model_a")
        assert "model-a" in scorer.ratings
        assert "model-b" in scorer.ratings

    def test_record_match_winner_gains_rating(self):
        scorer = EloScorer()
        scorer.record_match("model-a", "model-b", "model_a")
        assert scorer.ratings["model-a"] > 1500
        assert scorer.ratings["model-b"] < 1500

    def test_record_match_loser_loses_rating(self):
        scorer = EloScorer()
        scorer.record_match("model-a", "model-b", "model_b")
        assert scorer.ratings["model-b"] > 1500
        assert scorer.ratings["model-a"] < 1500

    def test_record_match_tie_small_changes(self):
        scorer = EloScorer()
        scorer.record_match("model-a", "model-b", "tie")
        # Equal initial ratings → tie should not change ratings much
        assert scorer.ratings["model-a"] == pytest.approx(1500, abs=1)
        assert scorer.ratings["model-b"] == pytest.approx(1500, abs=1)

    def test_record_match_increments_games_played(self):
        scorer = EloScorer()
        scorer.record_match("model-a", "model-b", "model_a")
        scorer.record_match("model-a", "model-b", "model_b")
        assert scorer.matches_played["model-a"] == 2
        assert scorer.matches_played["model-b"] == 2

    def test_get_leaderboard_sorted(self):
        scorer = EloScorer()
        scorer.record_match("strong-model", "weak-model", "model_a")
        scorer.record_match("strong-model", "weak-model", "model_a")
        scorer.record_match("strong-model", "weak-model", "model_a")
        board = scorer.get_leaderboard()
        assert board[0][0] == "strong-model"
        assert board[0][1] > board[1][1]

    def test_get_leaderboard_includes_games(self):
        scorer = EloScorer()
        scorer.record_match("model-a", "model-b", "model_a")
        board = scorer.get_leaderboard()
        for model_id, rating, games in board:
            assert isinstance(games, int)
            assert games >= 0

    def test_get_category_leaderboard(self):
        scorer = EloScorer()
        scorer.record_match("a", "b", "model_a", category="reasoning")
        scorer.record_match("c", "d", "model_a", category="code")
        reasoning_board = scorer.get_category_leaderboard("reasoning")
        code_board = scorer.get_category_leaderboard("code")
        assert len(reasoning_board) > 0
        assert len(code_board) > 0

    def test_get_rating_returns_default_for_new_model(self):
        scorer = EloScorer()
        rating = scorer.get_rating("unknown-model")
        assert rating == 1500

    def test_get_rating_returns_updated_rating(self):
        scorer = EloScorer()
        scorer.record_match("model-a", "model-b", "model_a")
        rating = scorer.get_rating("model-a")
        assert rating > 1500

    def test_get_rating_history(self):
        scorer = EloScorer()
        scorer.record_match("model-a", "model-b", "model_a")
        scorer.record_match("model-a", "model-c", "model_a")
        history = scorer.get_rating_history("model-a")
        assert len(history) == 2
        assert history[0][1] < history[1][1]  # Rating should increase with wins

    def test_get_rating_history_empty_for_unknown(self):
        scorer = EloScorer()
        history = scorer.get_rating_history("unknown-model")
        assert history == []

    def test_rating_is_symmetric(self):
        """Verify that total rating change is zero (zero-sum)."""
        scorer = EloScorer()
        scorer.record_match("model-a", "model-b", "model_a")
        total = scorer.ratings["model-a"] + scorer.ratings["model-b"]
        assert total == pytest.approx(3000)  # 1500 + 1500

    def test_save_and_load(self):
        scorer = EloScorer()
        scorer.record_match("model-a", "model-b", "model_a")
        scorer.record_match("model-b", "model-c", "model_b")

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name

        scorer.save(path)

        # Load into a new scorer
        scorer2 = EloScorer()
        scorer2.load(path)

        assert scorer2.ratings["model-a"] == pytest.approx(scorer.ratings["model-a"])
        assert scorer2.ratings["model-b"] == pytest.approx(scorer.ratings["model-b"])
        assert scorer2.k_factor == scorer.k_factor
        assert len(scorer2._history) == 2

    def test_save_creates_valid_json(self):
        scorer = EloScorer()
        scorer.record_match("a", "b", "model_a")

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
            path = f.name

        scorer.save(path)

        with open(path) as f:
            data = json.load(f)

        assert "ratings" in data
        assert "history" in data
        assert "k_factor" in data

    def test_multiple_matches_convergence(self):
        """Stronger model should climb above weaker model after many wins."""
        scorer = EloScorer()
        for _ in range(20):
            scorer.record_match("strong", "weak", "model_a")
        assert scorer.ratings["strong"] > scorer.ratings["weak"]
        assert scorer.ratings["strong"] > 1600  # Should have risen significantly
