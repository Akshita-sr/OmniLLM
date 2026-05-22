"""Offline session evaluator — score logged HRI interactions after the fact.

Runs AFTER a session is finished. Reads the JSON/JSONL produced by
``ExperimentLogger`` (or the ``/export`` server endpoint), then for each
interaction asks a judge LLM to score the response quality. Writes a
JSONL output with one record per evaluation, ready for pandas / ML
feature extraction.

This script is INTENTIONALLY decoupled from the live pipeline:

- It never imports or modifies anything inside ``omnillm.hri.pipeline``.
- It does not touch the server, the bridge, or the running gateway.
- It only reads logs and emits new files.

Usage::

    python scripts/evaluate_session.py \\
        --log experiments/sessions/2026-05-22.jsonl \\
        --judge openai-gpt4o \\
        --out experiments/eval_2026-05-22.jsonl

The output JSONL has these fields per row (for later ML work):

    session_id, participant_id, task_type, utterance, response, model_id,
    latency_ms, cost_usd, rag_enabled,
    triage_intent, triage_complexity, triage_safety, strategy_used,
    fallback_attempts,
    quality_score, judge_reasoning, judge_latency_ms

Resume support: if --out already exists, rows with already-evaluated
``(session_id, utterance)`` keys are skipped, so re-running picks up where
a previous run left off.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path
from typing import Any

from omnillm.evaluator import EvalTask, Evaluator
from omnillm.gateway import LLMGateway


def _load_log(path: Path) -> list[dict[str, Any]]:
    """Read a log file — supports JSON array OR JSONL (one row per line)."""
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return []
    if text[0] == "[":
        # JSON array (the /export endpoint shape).
        return list(json.loads(text))
    # JSONL.
    rows: list[dict[str, Any]] = []
    for line in text.splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def _already_evaluated_keys(out_path: Path) -> set[tuple[str, str]]:
    """Return the set of (session_id, utterance) tuples already in --out."""
    if not out_path.exists():
        return set()
    keys: set[tuple[str, str]] = set()
    for row in _load_log(out_path):
        sid = str(row.get("session_id", ""))
        utt = str(row.get("utterance", ""))
        keys.add((sid, utt))
    return keys


async def _evaluate_one(
    evaluator: Evaluator, row: dict[str, Any]
) -> dict[str, Any]:
    """Score one logged interaction, returning the enriched row."""
    utterance = str(row.get("utterance", ""))
    response = str(row.get("response", ""))
    if not utterance or not response:
        return {**row, "quality_score": -1.0, "judge_reasoning": "empty utterance or response"}

    # Build a referenceless EvalTask. We hand the response in via a
    # synthetic grading_fn that returns the LLM judge score — actually
    # simpler: just call the judge directly with the referenceless prompt.
    task = EvalTask(
        id=f"{row.get('session_id', '?')}:{utterance[:40]}",
        category=str(row.get("triage_intent") or row.get("task_type") or "general"),
        prompt=utterance,
        judge_pattern="referenceless",
    )

    t0 = time.monotonic()
    # The evaluator's _judge_referenceless internally calls the judge —
    # but evaluate_task() also re-queries the response model, which we
    # don't want (we already have the response). Use the private judge
    # method directly to avoid the extra LLM call.
    from omnillm.gateway import ModelResponse
    synthetic_resp = ModelResponse(
        model_id=str(row.get("model_id", "")),
        content=response,
    )
    score, reasoning = await evaluator._judge_referenceless(task, synthetic_resp)
    judge_latency_ms = (time.monotonic() - t0) * 1000

    return {
        **row,
        "quality_score": round(score, 4),
        "judge_reasoning": reasoning,
        "judge_latency_ms": round(judge_latency_ms, 1),
    }


async def _amain(args: argparse.Namespace) -> int:
    log_path = Path(args.log)
    if not log_path.exists():
        print(f"error: log file not found: {log_path}", file=sys.stderr)
        return 2

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    rows = _load_log(log_path)
    if args.limit:
        rows = rows[: args.limit]
    print(f"Loaded {len(rows)} interactions from {log_path}")

    seen = _already_evaluated_keys(out_path)
    if seen:
        print(f"Resume: skipping {len(seen)} already-evaluated rows.")

    gateway = LLMGateway()
    evaluator = Evaluator(gateway, judge_model=args.judge)

    # Append-mode write so resume works naturally.
    written = 0
    with out_path.open("a", encoding="utf-8") as out_fh:
        for i, row in enumerate(rows, start=1):
            key = (str(row.get("session_id", "")), str(row.get("utterance", "")))
            if key in seen:
                continue
            try:
                enriched = await _evaluate_one(evaluator, row)
            except Exception as exc:  # noqa: BLE001 — keep going on per-row failures
                enriched = {
                    **row,
                    "quality_score": -1.0,
                    "judge_reasoning": f"evaluation failed: {exc}",
                }
            out_fh.write(json.dumps(enriched) + "\n")
            out_fh.flush()
            written += 1
            if i % 5 == 0 or i == len(rows):
                print(f"  evaluated {i}/{len(rows)}  (score={enriched.get('quality_score', '?')})")

    print(f"Done. Wrote {written} new evaluations to {out_path}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Offline session evaluator (post-hoc).")
    parser.add_argument("--log", required=True,
                        help="Path to session log (JSON array OR JSONL).")
    parser.add_argument("--out", required=True,
                        help="Output JSONL path (appended; resume-friendly).")
    parser.add_argument("--judge", default="openai-gpt4o",
                        help="Judge model ID (default: openai-gpt4o).")
    parser.add_argument("--limit", type=int, default=0,
                        help="Limit to first N rows (debugging).")
    args = parser.parse_args()
    try:
        return asyncio.run(_amain(args))
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    sys.exit(main())
