"""Unified post-session evaluator for OmniLLM HRI sessions.

────────────────────────────────────────────────────────────────────────────────
WHAT THIS SCRIPT DOES (one-paragraph summary)
────────────────────────────────────────────────────────────────────────────────
You run this AFTER a recording session is finished. It reads the JSONL log
produced by ``omnillm.utils.experiment_logger.ExperimentLogger`` (one line per
interaction), runs four post-hoc analyses on every interaction, and writes ONE
wide CSV file that is ready to load into pandas / scikit-learn for machine-
learning benchmarking later.

The four analyses, each lifted from the deleted standalone modules:

  1. **LLM-as-Judge scoring**     (was ``omnillm/evaluator.py``)
     Sends each (utterance, response) pair to a strong judge model
     (default: openai-gpt4o) and asks it to score the response from 0 to 1.
  2. **ELO rating updates**       (was ``omnillm/scorer.py``)
     When two models answered prompts of the same task_type, treats the
     higher judge score as a "win" and updates each model's ELO rating.
     Uses the same algorithm as LMSYS Chatbot Arena.
  3. **Cost roll-up**             (was ``omnillm/utils/cost_tracker.py``)
     Aggregates cost_usd per model and per session. Written into a tiny
     summary file next to the main CSV.
  4. **CSV export**               (was ``omnillm/utils/export.py``)
     One wide row per interaction with the columns documented in CSV_COLUMNS
     below. Designed so ``pd.read_csv(...)`` Just Works.

────────────────────────────────────────────────────────────────────────────────
WHY THIS LIVES IN A SEPARATE SCRIPT (instead of inside the live pipeline)
────────────────────────────────────────────────────────────────────────────────
The live HRI pipeline (``omnillm/hri/pipeline.py``) MUST be fast (<2 s/turn).
We cannot afford to run a judge LLM on every utterance in real time — that
would double latency and double cost. So we log everything cheaply during the
session and do the expensive evaluation here, OFFLINE, after the fact.

This script never imports the live pipeline. It only:
  - reads JSONL logs written by ExperimentLogger,
  - calls the gateway to run the judge LLM, and
  - writes CSV / JSON output files.

────────────────────────────────────────────────────────────────────────────────
USAGE
────────────────────────────────────────────────────────────────────────────────
    python scripts/evaluate_session.py \\
        --log experiments/sessions/2026-05-22.jsonl \\
        --out experiments/eval_2026-05-22.csv \\
        --judge openai-gpt4o

Outputs:
    <out>.csv                 — one wide row per interaction (the ML feed)
    <out>.elo.json            — final ELO leaderboard for all models seen
    <out>.cost_summary.json   — per-model and per-session cost totals
    <out>.jsonl               — raw enriched rows (for re-runs / resume)

Re-running is safe: rows already present in <out>.jsonl are skipped (the
(session_id, utterance) tuple is the resume key), so a long evaluation can
be interrupted and continued.
"""

# `from __future__ import annotations` lets us write modern type hints like
# `dict[str, Any]` and `list[Row]` on every Python version since 3.9 without
# wrapping them in quotes. It's a free correctness/readability win.
from __future__ import annotations

# ── Standard-library imports ──────────────────────────────────────────────────
# WHAT:  Standard tools that ship with Python — no pip install needed.
# WHY:   Keep the dependency footprint small; this script must run on any
#        machine that already has the OmniLLM package installed.
import argparse   # CLI flag parsing (--log, --out, --judge, ...)
import asyncio    # We need async because gateway.query() is async.
import csv        # Standard CSV writer; we use DictWriter for column safety.
import json       # JSONL parsing (one JSON object per line in input log).
import math       # ELO uses math.pow for the expected-score curve.
import re         # Fallback regex when judge returns a malformed JSON answer.
import sys        # sys.stderr for error output, sys.exit for return codes.
import time       # time.monotonic for per-judge latency measurement.
from dataclasses import dataclass, field   # Tiny typed records for ELO state.
from datetime import datetime, timezone    # ISO timestamps for the ELO history.
from pathlib import Path                   # Cross-platform path handling.
from typing import Any                     # `Any` = "I really don't know yet."

# ── Project-internal import ───────────────────────────────────────────────────
# WHAT:  Only ONE import from the live package — the gateway, used to call the
#        judge LLM.
# WHY:   Keeping this script decoupled means we never accidentally trigger a
#        live-pipeline side-effect from an offline evaluation run.
# HOW:   LLMGateway reads config/models.yaml and gives us a uniform .query()
#        method across OpenAI / Anthropic / Google / local Ollama, etc.
from omnillm.gateway import LLMGateway


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 0: THE ML-READY CSV SCHEMA
# ══════════════════════════════════════════════════════════════════════════════
# WHAT:  This is the canonical column order for the output CSV. Every row
#        produced by this script has exactly these columns, in this order.
# WHY:   Downstream ML code can rely on a stable schema. If you add a column,
#        ADD IT AT THE END so existing scripts that load by column index don't
#        break.
# HOW IT CONNECTS:  _row_to_csv_dict() below builds each row using these keys.

CSV_COLUMNS: list[str] = [
    # ── Identity ──────────────────────────────────────────────────────────────
    "timestamp",          # ISO 8601 string from the original log line.
    "session_id",         # Recording session UUID (groups one participant run).
    "participant_id",     # Participant label, e.g. "P001" (anonymised).
    "mode",               # Operating mode at log time: laptop/choregraphe/real/real_laptop_mic.
    # ── Input / classification ────────────────────────────────────────────────
    "task_type",          # HRI task: info_retrieval / navigation / social_conversation / multilingual.
    "language",           # ISO 639-1 code: en / it / fr / de / ...
    "user_input",         # The user's utterance (transcribed if mic input).
    # ── Model + performance ───────────────────────────────────────────────────
    "model_id",           # The model that produced the response.
    "latency_ms",         # End-to-end latency (mic-end → start-of-robot-speech).
    "prompt_tokens",      # Input token count (renamed from input_tokens for clarity).
    "completion_tokens",  # Output token count (renamed from output_tokens).
    "cost_usd",           # Estimated dollar cost of this single interaction.
    # ── Quality (filled in by THIS script's judge step) ───────────────────────
    "judge_score",        # 0.0–1.0 from the judge LLM; -1.0 if not scored.
    "judge_reasoning",    # Short text explanation from the judge.
    "judge_latency_ms",   # How long the judge took (useful for cost analysis).
    # ── RAG-specific (only meaningful when rag_enabled=True) ─────────────────
    "rag_enabled",        # True/False — was the response grounded in the KB?
    "faithfulness",       # 0.0–1.0 faithfulness score; -1.0 if not scored.
    "rag_chunk_count",    # How many KB chunks the retriever returned.
    # ── Strategy + triage signals (from the live router) ──────────────────────
    "was_consensus",      # True if the council strategy ran (multi-model synthesis).
    "council_models",     # Semicolon-joined list of council member ids, or empty.
    "triage_intent",      # e.g. information_request / coding / navigation.
    "triage_complexity",  # simple / medium / complex.
    "triage_safety",      # safe / dangerous_or_medical / ambiguous.
    "strategy_used",      # direct / rag / council (which branch ran).
    "fallback_attempts",  # 0 = primary model worked; N = N failures before success.
    # ── ELO leaderboard signal (filled in by THIS script's scoring step) ─────
    "elo_rating_before",  # The model's ELO BEFORE this interaction was scored.
    "elo_rating_after",   # ...and AFTER (so you can compute delta in pandas).
    # ── Presentation + outcome ────────────────────────────────────────────────
    "gesture",            # The named gesture Pepper performed, or empty.
    "success",            # Task-success boolean from the logger, or empty.
    # ── Council diagnostic (Part 7 Embodied Veracity foundation) ─────────────
    "agreement_score",    # Synthesis judge's 0.0–1.0 agreement; empty for non-council rows.
]


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 1: LOAD LOGS (JSON array OR JSONL — both supported)
# ══════════════════════════════════════════════════════════════════════════════
# WHAT:  Read the recording-session log file from disk.
# WHY:   ExperimentLogger.save() writes a JSON array; the /export endpoint
#        also returns one; but real-time loggers append one JSON per line
#        (JSONL). We accept both so the script is tolerant of either path.
# HOW IT CONNECTS:  Called once at the top of _amain() with the --log path.

def _load_log(path: Path) -> list[dict[str, Any]]:
    """Read a log file. Auto-detects JSON array vs JSONL.

    Returns a list of dicts (one per logged interaction). Returns an empty
    list if the file is empty. Raises if the file does not exist (the caller
    should check first).
    """
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        # An empty file is not an error — just nothing to evaluate.
        return []

    # If the first non-whitespace character is "[", it's a JSON array.
    # Otherwise, treat it as JSONL (one JSON object per line).
    if text[0] == "[":
        return list(json.loads(text))

    rows: list[dict[str, Any]] = []
    for line in text.splitlines():
        line = line.strip()
        if line:                                    # skip blank lines
            rows.append(json.loads(line))
    return rows


def _already_evaluated_keys(out_jsonl_path: Path) -> set[tuple[str, str]]:
    """Return (session_id, utterance) tuples already present in the JSONL output.

    WHY:  This is the "resume" mechanism. If you stop and restart the script,
          rows that were already scored are skipped so we don't pay for the
          judge LLM twice.
    """
    if not out_jsonl_path.exists():
        return set()
    keys: set[tuple[str, str]] = set()
    for row in _load_log(out_jsonl_path):
        sid = str(row.get("session_id", ""))
        utt = str(row.get("utterance", ""))
        keys.add((sid, utt))
    return keys


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 2: LLM-AS-JUDGE SCORING (was omnillm/evaluator.py)
# ══════════════════════════════════════════════════════════════════════════════
# WHAT:  Call a strong judge model and ask it, in JSON, "how good is this
#        response, from 0 to 1?".
# WHY:   We can't score quality with a string-match — natural language has
#        infinitely many valid answers. The standard solution in the LLM-as-
#        Judge literature (arXiv:2412.05579) is to use another LLM as the
#        evaluator. We use the "referenceless / G-Eval" pattern because there
#        is no gold reference answer for free-form HRI conversation.
# HOW IT CONNECTS:  Called once per interaction by _enrich_row().

# The judge prompt template. The exact wording matters — the judge MUST
# return JSON only, otherwise our parser will fall back to a regex hunt and
# the score will be a coarse 0.5 default.
_JUDGE_PROMPT_TEMPLATE = (
    "You are an expert evaluator. Evaluate the following AI response on a scale "
    "from 0.0 to 1.0 where 1.0 is perfect.\n\n"
    "**Original question:**\n{prompt}\n\n"
    "**AI Response:**\n{response}\n\n"
    "Evaluate for: accuracy, completeness, clarity, and helpfulness.\n\n"
    "Respond ONLY with a valid JSON object in this exact format:\n"
    '{{ "score": <float 0.0-1.0>, "reasoning": "<one-paragraph explanation>" }}'
)


async def _run_judge(
    gateway: LLMGateway,
    judge_model: str,
    user_prompt: str,
    ai_response: str,
) -> tuple[float, str]:
    """Send one (prompt, response) pair to the judge and parse the JSON back.

    Returns (score in [0,1], reasoning string).

    HOW IT WORKS, STEP BY STEP:
      1. Format the judge prompt with the user's question and the AI's answer.
      2. Send it to the gateway at temperature=0.0 (deterministic — same
         input → same output, important for reproducible benchmarking).
      3. Try to parse the response as strict JSON.
      4. If JSON parsing fails, fall back to a regex hunt for any float
         between 0 and 1 in the response. Last-ditch default is 0.5.
    """
    # STEP 1: build the message list. The gateway expects OpenAI-style
    # chat messages (a list of {"role": ..., "content": ...} dicts).
    messages = [
        {
            "role": "user",
            "content": _JUDGE_PROMPT_TEMPLATE.format(
                prompt=user_prompt, response=ai_response
            ),
        }
    ]

    # STEP 2: actually call the LLM. temperature=0.0 makes it deterministic.
    judge_resp = await gateway.query(judge_model, messages, temperature=0.0)

    # If the judge itself errored (rate limit, auth, etc.), return a neutral
    # 0.5 score so the row is still written and the script keeps going.
    if judge_resp.is_error:
        return 0.5, f"judge_error: {judge_resp.error}"

    raw = judge_resp.content.strip()

    # STEP 3a: some models wrap JSON in ```json ... ``` markdown fences.
    # Strip those before trying to parse.
    if "```" in raw:
        # split("```") → ["before fence", "json\n{...}", "after fence"]
        # We want index 1, then drop the optional "json" language hint.
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]

    # STEP 3b: try strict JSON parse.
    try:
        data = json.loads(raw)
        score = float(data.get("score", 0.5))
        reasoning = str(data.get("reasoning", ""))
        # Clamp to [0, 1] — the judge sometimes returns 1.5 or -0.2.
        return min(max(score, 0.0), 1.0), reasoning
    except (ValueError, KeyError):
        # ValueError covers json.JSONDecodeError too — it's a subclass.
        pass

    # STEP 4: fallback — hunt for any plausible float in the raw text.
    # \b is a word boundary; ([01](?:\.\d+)?|\d*\.\d+) matches things like
    # "0.83", "1.0", ".7", "0".
    match = re.search(r"\b([01](?:\.\d+)?|\d*\.\d+)\b", judge_resp.content)
    if match:
        score = float(match.group(1))
        return min(max(score, 0.0), 1.0), judge_resp.content[:500]

    return 0.5, f"unparseable_judge_response: {judge_resp.content[:200]}"


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 3: ELO RATING (was omnillm/scorer.py)
# ══════════════════════════════════════════════════════════════════════════════
# WHAT:  Maintain a running ELO rating per model_id. Treat the higher-judge-
#        score model as the "winner" of every pairwise comparison we can
#        construct from rows that share the same task_type.
# WHY:   Average judge scores can be misleading if some models only answered
#        easy questions. ELO weights wins against strong opponents more.
#        It's the same algorithm that LMSYS Chatbot Arena uses for LLMs.
# HOW IT CONNECTS:  evolve_elo() is called once per (sorted) row in _amain().
#        Final leaderboard is written to <out>.elo.json.


@dataclass
class EloMatch:
    """One pairwise match we synthesised from two interactions of the same task_type."""

    timestamp: str        # ISO timestamp of when the match was "played" (== row).
    model_a: str
    model_b: str
    winner: str           # "model_a" / "model_b" / "tie"
    category: str = "general"  # The task_type bucket the match belongs to.
    rating_a_before: float = 1500.0
    rating_b_before: float = 1500.0
    rating_a_after: float = 1500.0
    rating_b_after: float = 1500.0


class EloBoard:
    """A tiny self-contained ELO scorer.

    Replaces the deleted omnillm/scorer.py:EloScorer with the same algorithm
    and just the methods we actually need in this script.

    Standard chess-style ELO formula:
      expected = 1 / (1 + 10**((rating_opponent - rating_self) / 400))
      new_rating = old_rating + k_factor * (actual_score - expected)

    where actual_score is 1.0 for win, 0.0 for loss, 0.5 for tie.
    K-factor 32 is the standard "rapid update" setting used by LMSYS.
    """

    def __init__(self, k_factor: float = 32.0, default_rating: float = 1500.0) -> None:
        self.k_factor = k_factor
        self.default_rating = default_rating
        # Mutable state. Keys are model_id strings.
        self.ratings: dict[str, float] = {}
        self.matches_played: dict[str, int] = {}
        # Optional history if anyone wants to plot rating-over-time later.
        self.history: list[EloMatch] = []

    def _expected(self, rating_a: float, rating_b: float) -> float:
        """Probability that A beats B given their current ratings. In (0, 1)."""
        return 1.0 / (1.0 + math.pow(10.0, (rating_b - rating_a) / 400.0))

    def get_rating(self, model_id: str) -> float:
        """Return current rating, or default for first-time models."""
        return self.ratings.get(model_id, self.default_rating)

    def record_match(
        self,
        model_a: str,
        model_b: str,
        winner: str,
        category: str = "general",
    ) -> tuple[float, float, float, float]:
        """Update ratings after a match. Returns (a_before, b_before, a_after, b_after).

        The "before" values are useful for the per-row CSV columns
        (elo_rating_before / elo_rating_after).
        """
        # Initialise first-time models. Both start at default_rating (1500).
        if model_a not in self.ratings:
            self.ratings[model_a] = self.default_rating
            self.matches_played[model_a] = 0
        if model_b not in self.ratings:
            self.ratings[model_b] = self.default_rating
            self.matches_played[model_b] = 0

        ra_before = self.ratings[model_a]
        rb_before = self.ratings[model_b]

        # The probability each model "should" win, given current ratings.
        ea = self._expected(ra_before, rb_before)
        eb = 1.0 - ea

        # The actual outcome: 1.0 / 0.0 / 0.5 for win / loss / tie.
        if winner == "model_a":
            sa, sb = 1.0, 0.0
        elif winner == "model_b":
            sa, sb = 0.0, 1.0
        else:  # tie
            sa, sb = 0.5, 0.5

        # The ELO update step itself.
        ra_after = ra_before + self.k_factor * (sa - ea)
        rb_after = rb_before + self.k_factor * (sb - eb)

        self.ratings[model_a] = ra_after
        self.ratings[model_b] = rb_after
        self.matches_played[model_a] += 1
        self.matches_played[model_b] += 1

        self.history.append(
            EloMatch(
                timestamp=datetime.now(timezone.utc).isoformat(),
                model_a=model_a, model_b=model_b, winner=winner, category=category,
                rating_a_before=ra_before, rating_b_before=rb_before,
                rating_a_after=ra_after, rating_b_after=rb_after,
            )
        )
        return ra_before, rb_before, ra_after, rb_after

    def leaderboard(self) -> list[tuple[str, float, int]]:
        """Sorted list of (model_id, rating, games_played), highest rating first."""
        return sorted(
            [(m, self.ratings[m], self.matches_played.get(m, 0)) for m in self.ratings],
            key=lambda x: x[1],
            reverse=True,
        )


def _judge_score_to_elo_winner(score_a: float, score_b: float) -> str:
    """Turn two judge scores into an ELO "winner" label.

    WHY:  ELO needs a discrete win/loss/tie outcome, but judge scores are
          continuous floats. We bucket anything within 0.05 of each other as
          a tie — small differences are inside the judge's noise floor.
    """
    if abs(score_a - score_b) < 0.05:
        return "tie"
    return "model_a" if score_a > score_b else "model_b"


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 4: COST ROLL-UP (was omnillm/utils/cost_tracker.py)
# ══════════════════════════════════════════════════════════════════════════════
# WHAT:  Aggregate cost_usd across all rows, grouped by model and by session.
# WHY:   The per-row CSV already has cost_usd, but the cost summary is what
#        you look at when you decide "this council strategy is too expensive
#        for a 30-minute session". Quick at-a-glance numbers.
# HOW IT CONNECTS:  _build_cost_summary() is called once at the end of _amain
#        and written to <out>.cost_summary.json.

def _build_cost_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Roll up cost_usd by model_id and by session_id.

    Returns a small dict suitable for json.dump. Each model entry includes
    total calls, input/output tokens, and total cost — so you can compute
    cost-per-token or cost-per-call downstream if needed.
    """
    by_model: dict[str, dict[str, float]] = {}
    by_session: dict[str, float] = {}
    total_cost = 0.0
    total_calls = 0

    for row in rows:
        mid = str(row.get("model_id", "unknown"))
        sid = str(row.get("session_id", "default"))
        cost = float(row.get("cost_usd", 0.0) or 0.0)
        in_t = int(row.get("input_tokens", 0) or 0)
        out_t = int(row.get("output_tokens", 0) or 0)

        if mid not in by_model:
            by_model[mid] = {"calls": 0, "input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0}
        by_model[mid]["calls"] += 1
        by_model[mid]["input_tokens"] += in_t
        by_model[mid]["output_tokens"] += out_t
        by_model[mid]["cost_usd"] += cost

        by_session[sid] = by_session.get(sid, 0.0) + cost
        total_cost += cost
        total_calls += 1

    return {
        "total_cost_usd": round(total_cost, 6),
        "total_calls": total_calls,
        # Sort by_model by cost descending so the most-expensive model is on top.
        "by_model": dict(sorted(by_model.items(), key=lambda kv: kv[1]["cost_usd"], reverse=True)),
        "by_session": by_session,
    }


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 5: BUILD ONE WIDE CSV ROW (was omnillm/utils/export.py)
# ══════════════════════════════════════════════════════════════════════════════
# WHAT:  Take an enriched log row (original + judge fields + ELO before/after)
#        and produce a flat dict with EXACTLY the keys in CSV_COLUMNS.
# WHY:   csv.DictWriter is strict: any extra key raises, any missing key
#        writes blank. Pre-flattening into the canonical shape makes the
#        write step trivial.

def _row_to_csv_dict(row: dict[str, Any]) -> dict[str, Any]:
    """Project one enriched row onto the CSV_COLUMNS schema.

    Handles the renames (input_tokens → prompt_tokens, gesture_used → gesture,
    rag_faithfulness → faithfulness, task_success → success, utterance →
    user_input) and synthesises the council_models / was_consensus fields
    from the model_id prefix written by hri/pipeline.py.
    """
    # model_id for a council answer looks like "council:openai-gpt4o-mini+claude-haiku+gemini-2.5-flash"
    # — see omnillm/hri/pipeline.py:_answer_council for where this is written.
    model_id_raw = str(row.get("model_id", ""))
    is_council = model_id_raw.startswith(("council:", "council-safe:"))
    council_models = ""
    if is_council:
        # Split off the "council:" / "council-safe:" prefix and re-join members with ";".
        members_str = model_id_raw.split(":", 1)[1]
        council_models = ";".join(members_str.split("+"))

    return {
        # ── Identity ──
        "timestamp":        row.get("timestamp", ""),
        "session_id":       row.get("session_id", ""),
        "participant_id":   row.get("participant_id", ""),
        "mode":             row.get("mode", ""),  # may be empty for old logs
        # ── Input / classification ──
        "task_type":        row.get("task_type", ""),
        "language":         row.get("language", ""),
        "user_input":       row.get("utterance", ""),
        # ── Model + performance ──
        "model_id":         model_id_raw,
        "latency_ms":       row.get("latency_ms", 0.0),
        "prompt_tokens":    row.get("input_tokens", 0),
        "completion_tokens": row.get("output_tokens", 0),
        "cost_usd":         row.get("cost_usd", 0.0),
        # ── Quality ──
        "judge_score":      row.get("judge_score", -1.0),
        "judge_reasoning":  row.get("judge_reasoning", ""),
        "judge_latency_ms": row.get("judge_latency_ms", 0.0),
        # ── RAG ──
        "rag_enabled":      row.get("rag_enabled", False),
        "faithfulness":     row.get("rag_faithfulness", -1.0),
        "rag_chunk_count":  row.get("rag_chunk_count", 0),
        # ── Strategy + triage ──
        "was_consensus":    is_council,
        "council_models":   council_models,
        "triage_intent":    row.get("triage_intent", ""),
        "triage_complexity": row.get("triage_complexity", ""),
        "triage_safety":    row.get("triage_safety", ""),
        "strategy_used":    row.get("strategy_used", ""),
        "fallback_attempts": row.get("fallback_attempts", 0),
        # ── ELO ──
        "elo_rating_before": row.get("elo_rating_before", 1500.0),
        "elo_rating_after":  row.get("elo_rating_after", 1500.0),
        # ── Presentation + outcome ──
        "gesture":          row.get("gesture_used", "") or "",
        # task_success can be None — write as "" rather than the string "None".
        "success":          "" if row.get("task_success") is None else row.get("task_success"),
        # ── Council diagnostic ──
        # agreement_score is None for direct/rag/multilingual rows; write as ""
        # so the CSV column stays numerically typed for council rows only.
        "agreement_score":  "" if row.get("agreement_score") is None else row.get("agreement_score"),
    }


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 6: PER-ROW ENRICHMENT (run the judge, return the augmented dict)
# ══════════════════════════════════════════════════════════════════════════════
# WHAT:  Take one raw log row, run the judge on it, return the row with
#        judge_score / judge_reasoning / judge_latency_ms added.
# WHY:   Splitting this from the main loop makes the loop simple and the
#        per-row error handling cleaner (one try/except wraps this call).

async def _enrich_row(
    gateway: LLMGateway,
    judge_model: str,
    row: dict[str, Any],
) -> dict[str, Any]:
    """Run the judge on one log row and return the row with judge fields added.

    Returns a NEW dict — does not mutate the input.
    """
    utterance = str(row.get("utterance", ""))
    response = str(row.get("response", ""))

    # Defensive: empty inputs would waste a judge call and confuse the model.
    # Mark them with -1.0 and a clear reason so they sort to the bottom.
    if not utterance or not response:
        return {
            **row,
            "judge_score": -1.0,
            "judge_reasoning": "empty utterance or response (skipped judge)",
            "judge_latency_ms": 0.0,
        }

    t0 = time.monotonic()
    score, reasoning = await _run_judge(gateway, judge_model, utterance, response)
    judge_latency_ms = (time.monotonic() - t0) * 1000.0

    return {
        **row,
        "judge_score": round(score, 4),
        "judge_reasoning": reasoning,
        "judge_latency_ms": round(judge_latency_ms, 1),
    }


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 7: ELO PASS (consume enriched rows, return rows with ELO before/after)
# ══════════════════════════════════════════════════════════════════════════════
# WHAT:  Walk through enriched rows GROUPED by task_type, and for each pair of
#        consecutive rows in the same group, record an ELO match.
# WHY:   ELO needs pairwise outcomes. We synthesise them by saying "within
#        each task_type bucket, neighbouring rows are a pair; the higher
#        judge score wins". This is the same intuition LMSYS uses when
#        humans on Chatbot Arena pick which of two side-by-side responses
#        they prefer for the SAME prompt — except here the "human" is the
#        judge LLM and the "same prompt" relaxation is "same task_type".
# HOW IT CONNECTS:  Returns a new list of rows, each augmented with
#                   elo_rating_before / elo_rating_after for ITS model. The
#                   returned EloBoard holds the final leaderboard.

def _run_elo_pass(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], EloBoard]:
    """Build an ELO leaderboard from judge-scored rows. Returns (rows_with_elo, board)."""
    board = EloBoard()
    out_rows: list[dict[str, Any]] = []

    # Group row INDICES by task_type so we preserve the original order
    # when we re-emit them at the end. Using indices (not row copies)
    # avoids paying for a deep copy.
    by_task: dict[str, list[int]] = {}
    for i, row in enumerate(rows):
        # Skip rows that weren't scorable — they don't contribute to ELO.
        if float(row.get("judge_score", -1.0)) < 0:
            continue
        task = str(row.get("task_type", "general"))
        by_task.setdefault(task, []).append(i)

    # Pre-compute the elo deltas per row index so we can stamp them back in
    # original order at the end.
    elo_per_index: dict[int, tuple[float, float]] = {}

    # For each task_type bucket, walk neighbouring pairs.
    for task, idxs in by_task.items():
        for k in range(len(idxs) - 1):
            i, j = idxs[k], idxs[k + 1]
            model_a = str(rows[i].get("model_id", "unknown"))
            model_b = str(rows[j].get("model_id", "unknown"))
            # Don't record a match between a model and itself — meaningless.
            if model_a == model_b:
                continue
            score_a = float(rows[i].get("judge_score", 0.0))
            score_b = float(rows[j].get("judge_score", 0.0))
            winner = _judge_score_to_elo_winner(score_a, score_b)

            ra_before, rb_before, ra_after, rb_after = board.record_match(
                model_a, model_b, winner, category=task
            )

            # Stamp the BEFORE/AFTER values onto rows i and j.
            # If a row appears in multiple matches we only record the FIRST
            # before-rating (so "before" really means "before any of this
            # row's matches") and the LATEST after-rating.
            if i not in elo_per_index:
                elo_per_index[i] = (ra_before, ra_after)
            else:
                elo_per_index[i] = (elo_per_index[i][0], ra_after)
            if j not in elo_per_index:
                elo_per_index[j] = (rb_before, rb_after)
            else:
                elo_per_index[j] = (elo_per_index[j][0], rb_after)

    # Re-emit rows in original order, stamping ELO when we have it.
    for i, row in enumerate(rows):
        before, after = elo_per_index.get(i, (board.default_rating, board.default_rating))
        out_rows.append({**row, "elo_rating_before": round(before, 2), "elo_rating_after": round(after, 2)})

    return out_rows, board


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 8: CLI / ASYNC MAIN
# ══════════════════════════════════════════════════════════════════════════════
# WHAT:  The orchestrator. Reads args, loads logs, runs the judge over each
#        row (with resume support), runs the ELO pass, writes the four output
#        files (CSV + JSONL + ELO + cost summary).
# WHY:   Splitting orchestration from logic keeps each helper above unit-
#        testable in isolation (see tests/test_post_eval.py).

async def _amain(args: argparse.Namespace) -> int:
    """Async main. Returns the process exit code (0 = success)."""
    log_path = Path(args.log)
    if not log_path.exists():
        print(f"error: log file not found: {log_path}", file=sys.stderr)
        return 2

    # The user gives a single --out, e.g. "results/2026-05-22.csv".
    # We derive sibling paths for the other three output files.
    out_csv = Path(args.out)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    # ``with_suffix`` swaps the file extension. ``out_csv.with_suffix(".jsonl")``
    # turns "results/2026-05-22.csv" into "results/2026-05-22.jsonl".
    out_jsonl = out_csv.with_suffix(".jsonl")
    out_elo = out_csv.with_suffix(".elo.json")
    out_cost = out_csv.with_suffix(".cost_summary.json")

    # STEP 1 — Load the log.
    rows = _load_log(log_path)
    if args.limit:
        rows = rows[: args.limit]
    print(f"Loaded {len(rows)} interactions from {log_path}")

    # STEP 2 — Figure out which rows we've already evaluated (for resume).
    seen = _already_evaluated_keys(out_jsonl)
    if seen:
        print(f"Resume: {len(seen)} rows already in {out_jsonl} will be skipped.")

    # STEP 3 — Build the gateway. This reads config/models.yaml.
    gateway = LLMGateway()
    if args.judge not in gateway.list_models():
        print(
            f"warning: judge model '{args.judge}' not in models.yaml; "
            f"the call will likely fail.",
            file=sys.stderr,
        )

    # STEP 4 — Run the judge over every (new) row. Append to JSONL as we go
    # so that an interrupted run can resume mid-session without data loss.
    enriched: list[dict[str, Any]] = []
    # Load already-evaluated rows back in so they participate in the ELO pass.
    if out_jsonl.exists():
        enriched.extend(_load_log(out_jsonl))

    written = 0
    with out_jsonl.open("a", encoding="utf-8") as jsonl_fh:
        for i, row in enumerate(rows, start=1):
            key = (str(row.get("session_id", "")), str(row.get("utterance", "")))
            if key in seen:
                continue
            try:
                enriched_row = await _enrich_row(gateway, args.judge, row)
            except Exception as exc:  # per-row failure: log, continue.
                enriched_row = {
                    **row,
                    "judge_score": -1.0,
                    "judge_reasoning": f"judge_call_failed: {exc}",
                    "judge_latency_ms": 0.0,
                }

            # Write to JSONL immediately (resume safety).
            jsonl_fh.write(json.dumps(enriched_row) + "\n")
            jsonl_fh.flush()
            enriched.append(enriched_row)
            written += 1

            # Progress every 5 rows or on the last row.
            if i % 5 == 0 or i == len(rows):
                print(
                    f"  judged {i}/{len(rows)}  "
                    f"(latest score={enriched_row.get('judge_score', '?')})"
                )

    print(f"Judge pass: wrote {written} new rows to {out_jsonl}")

    # STEP 5 — ELO pass across ALL enriched rows (old + new).
    rows_with_elo, board = _run_elo_pass(enriched)
    print(f"ELO: ran {len(board.history)} pairwise matches across "
          f"{len(board.ratings)} unique models.")

    # STEP 6 — Write the wide CSV.
    with out_csv.open("w", newline="", encoding="utf-8") as csv_fh:
        writer = csv.DictWriter(csv_fh, fieldnames=CSV_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        for r in rows_with_elo:
            writer.writerow(_row_to_csv_dict(r))
    print(f"CSV: wrote {len(rows_with_elo)} rows to {out_csv}")

    # STEP 7 — Write the ELO leaderboard.
    with out_elo.open("w", encoding="utf-8") as fh:
        json.dump(
            {
                "leaderboard": [
                    {"model_id": m, "rating": round(r, 2), "matches": g}
                    for (m, r, g) in board.leaderboard()
                ],
                "k_factor": board.k_factor,
                "default_rating": board.default_rating,
            },
            fh,
            indent=2,
        )
    print(f"ELO leaderboard: {out_elo}")

    # STEP 8 — Write the cost summary.
    cost_summary = _build_cost_summary(rows_with_elo)
    with out_cost.open("w", encoding="utf-8") as fh:
        json.dump(cost_summary, fh, indent=2)
    print(f"Cost summary: ${cost_summary['total_cost_usd']:.4f} across "
          f"{cost_summary['total_calls']} calls → {out_cost}")

    return 0


def main() -> int:
    """Synchronous entry point — parses args, runs the async main."""
    parser = argparse.ArgumentParser(
        description="Unified post-session evaluator: judge + ELO + cost + CSV."
    )
    parser.add_argument(
        "--log",
        required=True,
        help="Path to session log file (JSON array or JSONL).",
    )
    parser.add_argument(
        "--out",
        required=True,
        help="Output CSV path. Sibling files <out>.jsonl/.elo.json/.cost_summary.json "
        "are written next to it.",
    )
    parser.add_argument(
        "--judge",
        default="openai-gpt4o",
        help="Judge model ID (must exist in config/models.yaml). Default: openai-gpt4o.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Limit to first N rows (debugging). 0 = no limit.",
    )
    args = parser.parse_args()

    # asyncio.run() builds an event loop, runs the coroutine, and tears the
    # loop down cleanly. KeyboardInterrupt → exit code 0 so Ctrl-C looks tidy.
    try:
        return asyncio.run(_amain(args))
    except KeyboardInterrupt:
        return 0


# This idiom — `if __name__ == "__main__":` — runs main() only when the file
# is executed directly (`python scripts/evaluate_session.py`), not when it
# is imported as a module (which the tests do).
if __name__ == "__main__":
    sys.exit(main())
