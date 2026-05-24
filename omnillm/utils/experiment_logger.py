"""Experiment Logger for OmniLLM HRI sessions.

────────────────────────────────────────────────────────────────────────────────
WHAT THIS MODULE DOES
────────────────────────────────────────────────────────────────────────────────
Records one structured row per HRI interaction. Each row captures:
  - which LLM model was used and what it answered
  - latency, token counts, and dollar cost
  - RAG retrieval signals (was it used, faithfulness score, chunk count)
  - autonomous triage + strategy decisions (the System 1 / System 2 fields)
  - language, gesture, mode (laptop / choregraphe / real / real_laptop_mic)
  - free-form notes

────────────────────────────────────────────────────────────────────────────────
WHY THIS LIVES IN ONE PLACE
────────────────────────────────────────────────────────────────────────────────
The live pipeline ([omnillm/hri/pipeline.py]) calls ``log_interaction`` once
per turn. The post-session evaluator ([scripts/evaluate_session.py]) READS
the JSON / JSONL written by ``save`` / per-line append and runs the judge
LLM over each row. Keeping the schema in this one dataclass means there is
exactly one place to add a column when the schema changes.

────────────────────────────────────────────────────────────────────────────────
HISTORICAL NOTE — the dropped `condition` field
────────────────────────────────────────────────────────────────────────────────
Until 2026-05-22 every record carried a `condition: str` field (values
"A"–"E") from the original A/B/C/D/E experimental design. The 2026-05-22
refactor dropped that design — there are no conditions anymore — so the
field was removed entirely. Old JSON dumps that still contain a "condition"
key will load cleanly: ``load()`` filters out keys the new dataclass does
not know about.
"""

# Modern type-hint syntax on every Python from 3.9 onwards.
from __future__ import annotations

# Stdlib only. CSV/JSON for persistence, dataclasses for the record shape,
# datetime for ISO timestamps, pathlib for cross-platform paths.
import csv
import json
from dataclasses import asdict, dataclass, field, fields as dc_fields
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass
class InteractionRecord:
    """One logged HRI interaction.

    Every field has a safe default so callers only have to fill in the
    parts they care about. The post-session evaluator at
    [scripts/evaluate_session.py] reads these rows back and adds judge /
    ELO / cost-rollup columns.
    """

    # ── Identity ──────────────────────────────────────────────────────────────
    session_id: str
    participant_id: str
    task_type: str
    utterance: str
    response: str
    model_id: str

    # ── Operating context (NEW 2026-05-22 — replaces the dropped condition) ──
    # WHAT:  Which of the four operating modes was active when this row was
    #        logged. One of "laptop" / "choregraphe" / "real" / "real_laptop_mic".
    # WHY:   The post-session evaluator and the ML benchmarking step want to
    #        compare results across hardware configurations (e.g. "is judge
    #        score lower when the laptop mic is used vs the robot mic?").
    # HOW IT CONNECTS:  Server reads OMNILLM_MODE env var (set by run.py)
    #        and passes it through log_interaction(mode=...).
    mode: str = ""

    # ── Performance ───────────────────────────────────────────────────────────
    latency_ms: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0

    # ── RAG ───────────────────────────────────────────────────────────────────
    rag_enabled: bool = False
    rag_faithfulness: float = -1.0    # -1.0 = not scored
    rag_chunk_count: int = 0

    # ── Quality (post-hoc — filled in by scripts/evaluate_session.py) ────────
    judge_score: float = -1.0          # -1.0 = not yet judged
    task_success: bool | None = None   # None = not labelled

    # ── Presentation ──────────────────────────────────────────────────────────
    language: str = "en"
    gesture_used: str | None = None

    # ── Autonomous triage + strategy (System 1 / System 2 signals) ────────────
    triage_intent: str = ""
    triage_complexity: str = ""
    triage_safety: str = ""
    triage_method: str = ""
    strategy_used: str = ""
    strategy_reason: str = ""
    fallback_attempts: int = 0

    # ── Bookkeeping ───────────────────────────────────────────────────────────
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    notes: str = ""


class ExperimentLogger:
    """In-memory collector of InteractionRecord objects with JSON/CSV export.

    Typical usage from the live pipeline ([omnillm/hri/pipeline.py]):

        logger = ExperimentLogger()
        logger.log_interaction(
            session_id="s1", participant_id="P001",
            task_type="info_retrieval",
            utterance="What are the lab hours?",
            response="The lab is open 9 AM to 6 PM.",
            model_id="openai-gpt4o-mini",
            mode="choregraphe",
            latency_ms=380.0,
            rag_enabled=True,
        )
        logger.save("results.json")
    """

    def __init__(self) -> None:
        self._records: list[InteractionRecord] = []

    @property
    def records(self) -> list[InteractionRecord]:
        """Read-only view of all logged records (a defensive copy)."""
        return list(self._records)

    def log_interaction(
        self,
        session_id: str,
        participant_id: str,
        task_type: str,
        utterance: str,
        response: str,
        model_id: str,
        *,
        mode: str = "",
        latency_ms: float = 0.0,
        input_tokens: int = 0,
        output_tokens: int = 0,
        cost_usd: float = 0.0,
        rag_enabled: bool = False,
        rag_faithfulness: float = -1.0,
        rag_chunk_count: int = 0,
        judge_score: float = -1.0,
        task_success: bool | None = None,
        language: str = "en",
        gesture_used: str | None = None,
        triage_intent: str = "",
        triage_complexity: str = "",
        triage_safety: str = "",
        triage_method: str = "",
        strategy_used: str = "",
        strategy_reason: str = "",
        fallback_attempts: int = 0,
        notes: str = "",
    ) -> InteractionRecord:
        """Append one InteractionRecord. Returns the record so callers can inspect it.

        All optional fields are KEYWORD-ONLY (note the ``*`` in the signature)
        so callers can't accidentally swap positional args after a future
        refactor changes ordering.
        """
        record = InteractionRecord(
            session_id=session_id,
            participant_id=participant_id,
            task_type=task_type,
            utterance=utterance,
            response=response,
            model_id=model_id,
            mode=mode,
            latency_ms=latency_ms,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost_usd,
            rag_enabled=rag_enabled,
            rag_faithfulness=rag_faithfulness,
            rag_chunk_count=rag_chunk_count,
            judge_score=judge_score,
            task_success=task_success,
            language=language,
            gesture_used=gesture_used,
            triage_intent=triage_intent,
            triage_complexity=triage_complexity,
            triage_safety=triage_safety,
            triage_method=triage_method,
            strategy_used=strategy_used,
            strategy_reason=strategy_reason,
            fallback_attempts=fallback_attempts,
            notes=notes,
        )
        self._records.append(record)
        return record

    def log_from_rag_response(
        self,
        session_id: str,
        participant_id: str,
        task_type: str,
        utterance: str,
        rag_response: Any,  # omnillm.rag.pipeline.RAGResponse (avoid import cycle)
        *,
        mode: str = "",
        task_success: bool | None = None,
        gesture_used: str | None = None,
        notes: str = "",
    ) -> InteractionRecord:
        """Convenience wrapper: log an interaction from a RAGResponse object."""
        return self.log_interaction(
            session_id=session_id,
            participant_id=participant_id,
            task_type=task_type,
            utterance=utterance,
            response=rag_response.answer,
            model_id=rag_response.model_id,
            mode=mode,
            latency_ms=rag_response.latency_ms,
            rag_enabled=rag_response.rag_enabled,
            rag_faithfulness=rag_response.faithfulness_score,
            rag_chunk_count=len(rag_response.retrieved_chunks),
            task_success=task_success,
            gesture_used=gesture_used,
            notes=notes,
        )

    # ── Filtering ─────────────────────────────────────────────────────────────

    def get_records(
        self,
        session_id: str | None = None,
        task_type: str | None = None,
        model_id: str | None = None,
        mode: str | None = None,
    ) -> list[InteractionRecord]:
        """Return records matching every supplied filter (AND semantics)."""
        records = self._records
        if session_id is not None:
            records = [r for r in records if r.session_id == session_id]
        if task_type is not None:
            records = [r for r in records if r.task_type == task_type]
        if model_id is not None:
            records = [r for r in records if r.model_id == model_id]
        if mode is not None:
            records = [r for r in records if r.mode == mode]
        return records

    # ── Aggregates ────────────────────────────────────────────────────────────

    def get_summary(self) -> dict[str, Any]:
        """Return aggregate stats grouped by model, mode, and task_type.

        Each group reports: count, avg_latency_ms, avg_judge_score (when
        scored), success_rate (when labelled), and total_cost_usd.
        """
        if not self._records:
            return {"total_interactions": 0}

        by_model: dict[str, list[InteractionRecord]] = {}
        by_mode: dict[str, list[InteractionRecord]] = {}
        by_task: dict[str, list[InteractionRecord]] = {}
        for r in self._records:
            by_model.setdefault(r.model_id, []).append(r)
            by_mode.setdefault(r.mode or "unspecified", []).append(r)
            by_task.setdefault(r.task_type, []).append(r)

        def _avg_latency(recs: list[InteractionRecord]) -> float:
            vals = [r.latency_ms for r in recs if r.latency_ms > 0]
            return sum(vals) / len(vals) if vals else 0.0

        def _avg_judge(recs: list[InteractionRecord]) -> float:
            vals = [r.judge_score for r in recs if r.judge_score >= 0]
            return sum(vals) / len(vals) if vals else -1.0

        def _success_rate(recs: list[InteractionRecord]) -> float:
            scored = [r for r in recs if r.task_success is not None]
            if not scored:
                return -1.0
            return sum(1 for r in scored if r.task_success) / len(scored)

        def _total_cost(recs: list[InteractionRecord]) -> float:
            return sum(r.cost_usd for r in recs)

        return {
            "total_interactions": len(self._records),
            "by_model": {
                mid: {
                    "count": len(recs),
                    "avg_latency_ms": round(_avg_latency(recs), 1),
                    "avg_judge_score": round(_avg_judge(recs), 3),
                    "success_rate": round(_success_rate(recs), 3),
                    "total_cost_usd": round(_total_cost(recs), 6),
                }
                for mid, recs in by_model.items()
            },
            "by_mode": {
                m: {
                    "count": len(recs),
                    "avg_latency_ms": round(_avg_latency(recs), 1),
                    "avg_judge_score": round(_avg_judge(recs), 3),
                    "success_rate": round(_success_rate(recs), 3),
                }
                for m, recs in by_mode.items()
            },
            "by_task_type": {
                t: {"count": len(recs), "avg_latency_ms": round(_avg_latency(recs), 1)}
                for t, recs in by_task.items()
            },
            "total_cost_usd": round(sum(r.cost_usd for r in self._records), 6),
        }

    # ── Persistence ───────────────────────────────────────────────────────────

    def save(self, path: str | Path) -> None:
        """Write all records to a JSON array file."""
        data = [asdict(r) for r in self._records]
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, default=str)

    def load(self, path: str | Path) -> None:
        """Append records read from a JSON array file.

        Unknown keys in the file (e.g. the dropped ``condition`` field from
        pre-2026-05-22 dumps) are silently ignored, so loading legacy logs
        does NOT raise.
        """
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        # Build the set of field names the current dataclass accepts so we
        # can drop any extras from old dumps.
        known = {f.name for f in dc_fields(InteractionRecord)}
        for item in data:
            filtered = {k: v for k, v in item.items() if k in known}
            self._records.append(InteractionRecord(**filtered))

    def save_csv(self, path: str | Path) -> None:
        """Export all records to a CSV file for spreadsheet inspection."""
        if not self._records:
            return
        fieldnames = list(asdict(self._records[0]).keys())
        with open(path, "w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=fieldnames)
            writer.writeheader()
            for r in self._records:
                writer.writerow(asdict(r))
