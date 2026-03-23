"""Experiment Logger for the Embodied LLM Arena study.

Records all interaction data generated during the multi-LLM HRI experiment,
including:
- Which LLM model was used for each response
- Response latency (end-of-speech → start-of-robot-response)
- Token counts (input and output)
- Cost per interaction
- RAG retrieval scores (faithfulness, chunk relevance)
- LLM-as-Judge evaluation scores (accuracy, relevance, fluency, safety)
- Language detected for each utterance
- Task classification (T1–T4)
- Task completion success (binary)
- Full transcripts for qualitative analysis

Data can be exported to JSON or CSV for statistical analysis in R/Python.

Usage::

    logger = ExperimentLogger()
    logger.log_interaction(
        session_id="abc-123",
        participant_id="P001",
        condition="C",
        task_type="info_retrieval",
        utterance="What time does the lab open?",
        response="The lab opens at 9 AM on weekdays.",
        model_id="openai-gpt4o-mini",
        latency_ms=432.1,
        rag_enabled=True,
        rag_faithfulness=0.95,
        judge_score=0.88,
        task_success=True,
        language="en",
    )
    logger.save("experiment_data.json")
"""

from __future__ import annotations

import csv
import json
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass
class InteractionRecord:
    """A single logged HRI interaction.

    Attributes:
        session_id: Unique session identifier (links to :class:`~omnillm.hri.experiment.ParticipantSession`).
        participant_id: Participant label.
        condition: Experimental condition (``"A"``–``"E"``).
        task_type: HRI task type (``"info_retrieval"``, ``"navigation"``,
            ``"social_conversation"``, or ``"multilingual"``).
        utterance: Transcribed user speech (from Whisper).
        response: Robot's spoken response (LLM output).
        model_id: Which LLM model generated the response.
        latency_ms: End-to-end latency from end-of-speech to start-of-speech in ms.
        input_tokens: LLM input token count.
        output_tokens: LLM output token count.
        cost_usd: Estimated cost of this interaction in USD.
        rag_enabled: Whether RAG retrieval was used.
        rag_faithfulness: RAG faithfulness score (0–1).  -1.0 = not scored.
        rag_chunk_count: Number of document chunks retrieved.
        judge_score: LLM-as-judge quality score (0–1).  -1.0 = not scored.
        task_success: Whether the task was completed successfully.
        language: ISO 639-1 language code of the utterance.
        gesture_used: Named gesture Pepper performed (if any).
        timestamp: ISO 8601 timestamp of the interaction.
        notes: Free-form observer notes.
    """

    session_id: str
    participant_id: str
    condition: str
    task_type: str
    utterance: str
    response: str
    model_id: str
    latency_ms: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    rag_enabled: bool = False
    rag_faithfulness: float = -1.0
    rag_chunk_count: int = 0
    judge_score: float = -1.0
    task_success: bool | None = None
    language: str = "en"
    gesture_used: str | None = None
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    notes: str = ""


class ExperimentLogger:
    """Logs all HRI interaction data for the Embodied LLM Arena study.

    Designed to produce the automatic data collection described in the research
    design:
    - Which LLM was used for each response
    - Response latency (time from end of speech to start of robot response)
    - Token count (input and output)
    - Cost per interaction
    - RAG retrieval scores (relevance of retrieved chunks)
    - LLM-as-Judge scores (accuracy, relevance, fluency, safety)
    - Language detected
    - Task classification

    Example::

        logger = ExperimentLogger()
        logger.log_interaction(
            session_id="s1",
            participant_id="P001",
            condition="A",
            task_type="info_retrieval",
            utterance="What are the lab hours?",
            response="The lab is open 9 AM to 6 PM.",
            model_id="openai-gpt4o-mini",
            latency_ms=380.0,
            rag_enabled=True,
            task_success=True,
        )
        logger.save("results.json")
    """

    def __init__(self) -> None:
        self._records: list[InteractionRecord] = []

    def log_interaction(
        self,
        session_id: str,
        participant_id: str,
        condition: str,
        task_type: str,
        utterance: str,
        response: str,
        model_id: str,
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
        notes: str = "",
    ) -> InteractionRecord:
        """Log a single HRI interaction.

        Args:
            session_id: Session UUID from :class:`~omnillm.hri.experiment.ParticipantSession`.
            participant_id: Participant label.
            condition: Experimental condition (``"A"``–``"E"``).
            task_type: HRI task type (``"info_retrieval"``, ``"navigation"``, etc.).
            utterance: Transcribed user speech.
            response: Robot's spoken response.
            model_id: LLM model ID that generated the response.
            latency_ms: End-to-end latency in milliseconds.
            input_tokens: LLM input token count.
            output_tokens: LLM output token count.
            cost_usd: Estimated cost of this interaction.
            rag_enabled: Whether RAG was active.
            rag_faithfulness: RAG faithfulness score (0–1, -1 = not scored).
            rag_chunk_count: Number of document chunks retrieved.
            judge_score: LLM-as-judge quality score (0–1, -1 = not scored).
            task_success: Whether the task was completed successfully.
            language: ISO 639-1 language code.
            gesture_used: Named gesture Pepper performed.
            notes: Free-form observer notes.

        Returns:
            The logged :class:`InteractionRecord`.
        """
        record = InteractionRecord(
            session_id=session_id,
            participant_id=participant_id,
            condition=condition,
            task_type=task_type,
            utterance=utterance,
            response=response,
            model_id=model_id,
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
            notes=notes,
        )
        self._records.append(record)
        return record

    def log_from_rag_response(
        self,
        session_id: str,
        participant_id: str,
        condition: str,
        task_type: str,
        utterance: str,
        rag_response: Any,  # RAGResponse
        task_success: bool | None = None,
        gesture_used: str | None = None,
        notes: str = "",
    ) -> InteractionRecord:
        """Convenience method: log an interaction from a :class:`~omnillm.rag.pipeline.RAGResponse`.

        Args:
            session_id: Session UUID.
            participant_id: Participant label.
            condition: Experimental condition.
            task_type: HRI task type.
            utterance: Transcribed user speech.
            rag_response: :class:`~omnillm.rag.pipeline.RAGResponse` instance.
            task_success: Whether the task was completed successfully.
            gesture_used: Named gesture Pepper performed.
            notes: Free-form observer notes.

        Returns:
            The logged :class:`InteractionRecord`.
        """
        return self.log_interaction(
            session_id=session_id,
            participant_id=participant_id,
            condition=condition,
            task_type=task_type,
            utterance=utterance,
            response=rag_response.answer,
            model_id=rag_response.model_id,
            latency_ms=rag_response.latency_ms,
            rag_enabled=rag_response.rag_enabled,
            rag_faithfulness=rag_response.faithfulness_score,
            rag_chunk_count=len(rag_response.retrieved_chunks),
            task_success=task_success,
            gesture_used=gesture_used,
            notes=notes,
        )

    # ── Analytics ─────────────────────────────────────────────────────────────

    def get_records(
        self,
        session_id: str | None = None,
        condition: str | None = None,
        task_type: str | None = None,
        model_id: str | None = None,
    ) -> list[InteractionRecord]:
        """Return records filtered by optional criteria.

        Args:
            session_id: Filter by session ID.
            condition: Filter by condition (``"A"``–``"E"``).
            task_type: Filter by task type.
            model_id: Filter by model ID.

        Returns:
            Filtered list of :class:`InteractionRecord` objects.
        """
        records = self._records
        if session_id is not None:
            records = [r for r in records if r.session_id == session_id]
        if condition is not None:
            records = [r for r in records if r.condition == condition]
        if task_type is not None:
            records = [r for r in records if r.task_type == task_type]
        if model_id is not None:
            records = [r for r in records if r.model_id == model_id]
        return records

    def get_summary(self) -> dict[str, Any]:
        """Return aggregate statistics across all logged interactions.

        Returns:
            Dict with per-condition and per-model averages for key metrics.
        """
        if not self._records:
            return {"total_interactions": 0}

        by_model: dict[str, list[InteractionRecord]] = {}
        by_condition: dict[str, list[InteractionRecord]] = {}
        by_task: dict[str, list[InteractionRecord]] = {}

        for r in self._records:
            by_model.setdefault(r.model_id, []).append(r)
            by_condition.setdefault(r.condition, []).append(r)
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

        model_stats = {
            mid: {
                "count": len(recs),
                "avg_latency_ms": round(_avg_latency(recs), 1),
                "avg_judge_score": round(_avg_judge(recs), 3),
                "success_rate": round(_success_rate(recs), 3),
                "total_cost_usd": round(_total_cost(recs), 6),
            }
            for mid, recs in by_model.items()
        }

        condition_stats = {
            cond: {
                "count": len(recs),
                "avg_latency_ms": round(_avg_latency(recs), 1),
                "avg_judge_score": round(_avg_judge(recs), 3),
                "success_rate": round(_success_rate(recs), 3),
            }
            for cond, recs in by_condition.items()
        }

        return {
            "total_interactions": len(self._records),
            "by_model": model_stats,
            "by_condition": condition_stats,
            "by_task_type": {
                t: {"count": len(recs), "avg_latency_ms": round(_avg_latency(recs), 1)}
                for t, recs in by_task.items()
            },
            "total_cost_usd": round(sum(r.cost_usd for r in self._records), 6),
        }

    # ── Persistence ───────────────────────────────────────────────────────────

    def save(self, path: str | Path) -> None:
        """Save all interaction records to a JSON file.

        Args:
            path: Destination file path.
        """
        data = [asdict(r) for r in self._records]
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, default=str)

    def load(self, path: str | Path) -> None:
        """Load records from a JSON file (appends to existing records).

        Args:
            path: Source file path.
        """
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        for item in data:
            self._records.append(InteractionRecord(**item))

    def save_csv(self, path: str | Path) -> None:
        """Export all records to a CSV file for statistical analysis (R/SPSS/Excel).

        Args:
            path: Destination file path.
        """
        if not self._records:
            return
        fieldnames = list(asdict(self._records[0]).keys())
        with open(path, "w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=fieldnames)
            writer.writeheader()
            for r in self._records:
                writer.writerow(asdict(r))
