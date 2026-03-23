"""Experiment Manager for the Embodied LLM Arena study.

Manages experimental conditions, participant sessions, and counterbalancing
for the multi-LLM HRI study with Pepper robot.

Experimental conditions (A–E):
- **A** — Fixed Cloud LLM: GPT-4o-mini for all tasks (baseline)
- **B** — Fixed Local LLM: Llama3:8b via Ollama (free/offline baseline)
- **C** — Smart-Routed: OmniLLM selects the best model per task type
- **D** — Consensus: 3-model council, best response synthesised
- **E** — RAG-Off Control: same as A but RAG retrieval disabled

The study uses a within-subjects Latin square counterbalanced design.
Each participant experiences 3 of the 5 conditions (randomly assigned
from the balanced design).

Usage::

    manager = ExperimentManager()
    session = manager.create_session(participant_id="P001", condition="C")
    config = manager.get_condition_config("C")
    print(config.model_id)       # None (smart-routed)
    print(config.rag_enabled)    # True
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class ExperimentCondition(str, Enum):
    """The five experimental conditions of the Embodied LLM Arena study."""

    A = "A"
    """Fixed Cloud LLM — GPT-4o-mini for all tasks."""

    B = "B"
    """Fixed Local LLM — Llama3:8b (Ollama) for all tasks."""

    C = "C"
    """Smart-Routed — OmniLLM dynamically selects the best model per task."""

    D = "D"
    """Consensus (Council) — 3 models answer, best response synthesised."""

    E = "E"
    """RAG-Off Control — GPT-4o-mini without RAG (isolates RAG contribution)."""


@dataclass
class ConditionConfig:
    """Configuration parameters for a single experimental condition.

    Attributes:
        condition: The :class:`ExperimentCondition` identifier.
        model_id: Fixed model to use.  ``None`` means dynamic routing (C/D).
        rag_enabled: Whether RAG retrieval is active.
        use_consensus: Whether to use the ConsensusEngine (condition D).
        use_smart_routing: Whether to use the SmartRouter (condition C).
        council_models: List of model IDs for the consensus council (condition D).
        description: Human-readable description for logging.
    """

    condition: ExperimentCondition
    model_id: str | None
    rag_enabled: bool
    use_consensus: bool = False
    use_smart_routing: bool = False
    council_models: list[str] = field(default_factory=list)
    description: str = ""


# ── Default condition configurations ─────────────────────────────────────────

CONDITION_CONFIGS: dict[ExperimentCondition, ConditionConfig] = {
    ExperimentCondition.A: ConditionConfig(
        condition=ExperimentCondition.A,
        model_id="openai-gpt4o-mini",
        rag_enabled=True,
        description="Fixed cloud LLM (GPT-4o-mini) with RAG — baseline",
    ),
    ExperimentCondition.B: ConditionConfig(
        condition=ExperimentCondition.B,
        model_id="llama3-8b-local",
        rag_enabled=True,
        description="Fixed local LLM (Llama3:8b via Ollama) with RAG",
    ),
    ExperimentCondition.C: ConditionConfig(
        condition=ExperimentCondition.C,
        model_id=None,
        rag_enabled=True,
        use_smart_routing=True,
        description="Smart-routed — OmniLLM selects best model per task type",
    ),
    ExperimentCondition.D: ConditionConfig(
        condition=ExperimentCondition.D,
        model_id=None,
        rag_enabled=True,
        use_consensus=True,
        council_models=["openai-gpt4o-mini", "claude-haiku", "gemini-flash"],
        description="Consensus council — 3 models, best answer synthesised",
    ),
    ExperimentCondition.E: ConditionConfig(
        condition=ExperimentCondition.E,
        model_id="openai-gpt4o-mini",
        rag_enabled=False,
        description="RAG-off control — GPT-4o-mini without knowledge retrieval",
    ),
}


@dataclass
class ParticipantSession:
    """A single participant's experimental session.

    Attributes:
        session_id: Unique session identifier (UUID4).
        participant_id: Participant label (e.g. ``"P001"``).
        condition: Experimental condition for this session.
        condition_config: Full configuration for the condition.
        start_time: ISO 8601 timestamp when the session started.
        end_time: ISO 8601 timestamp when the session ended (``None`` if active).
        task_log: List of task interaction records.
        questionnaire_scores: Post-session Likert scores (key → 1–7).
        notes: Free-form observer notes.
    """

    session_id: str
    participant_id: str
    condition: ExperimentCondition
    condition_config: ConditionConfig
    start_time: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    end_time: str | None = None
    task_log: list[dict[str, Any]] = field(default_factory=list)
    questionnaire_scores: dict[str, float] = field(default_factory=dict)
    notes: str = ""

    def complete(self) -> None:
        """Mark the session as complete."""
        self.end_time = datetime.now(timezone.utc).isoformat()

    def log_task(self, task_record: dict[str, Any]) -> None:
        """Append a task interaction record to the session log.

        Args:
            task_record: Dict with keys such as ``task_type``, ``utterance``,
                ``response``, ``model_id``, ``latency_ms``, ``rag_enabled``,
                ``judge_score``, ``task_success``.
        """
        task_record.setdefault("timestamp", datetime.now(timezone.utc).isoformat())
        self.task_log.append(task_record)

    def set_questionnaire(self, scores: dict[str, float]) -> None:
        """Record post-session questionnaire Likert scores.

        Args:
            scores: Dict mapping question label → Likert score (1–7).
        """
        self.questionnaire_scores.update(scores)

    def to_dict(self) -> dict[str, Any]:
        """Serialise the session to a JSON-compatible dict."""
        return {
            "session_id": self.session_id,
            "participant_id": self.participant_id,
            "condition": self.condition.value,
            "condition_description": self.condition_config.description,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "task_log": self.task_log,
            "questionnaire_scores": self.questionnaire_scores,
            "notes": self.notes,
        }


class ExperimentManager:
    """Manages experimental sessions, conditions, and participant assignments.

    Implements the Embodied LLM Arena within-subjects Latin square design.
    Each participant is assigned a set of conditions and tasks.

    Example::

        manager = ExperimentManager()
        session = manager.create_session("P001", ExperimentCondition.C)
        config = manager.get_condition_config(ExperimentCondition.C)
        print(config.use_smart_routing)   # True
        session.log_task({
            "task_type": "info_retrieval",
            "utterance": "What time does the lab open?",
            "response": "The lab opens at 9 AM.",
            "model_id": "openai-gpt4o-mini",
            "latency_ms": 432.1,
        })
        session.complete()
    """

    def __init__(
        self,
        custom_condition_configs: dict[ExperimentCondition, ConditionConfig] | None = None,
    ) -> None:
        """Initialise the experiment manager.

        Args:
            custom_condition_configs: Override default condition configurations.
                Merged with :data:`CONDITION_CONFIGS`.
        """
        self._configs: dict[ExperimentCondition, ConditionConfig] = {
            **CONDITION_CONFIGS,
            **(custom_condition_configs or {}),
        }
        self._sessions: dict[str, ParticipantSession] = {}

    def get_condition_config(
        self, condition: ExperimentCondition | str
    ) -> ConditionConfig:
        """Return the configuration for an experimental condition.

        Args:
            condition: :class:`ExperimentCondition` or string identifier
                (``"A"``, ``"B"``, ``"C"``, ``"D"``, or ``"E"``).

        Returns:
            :class:`ConditionConfig` for the requested condition.

        Raises:
            KeyError: If the condition is not registered.
        """
        if isinstance(condition, str):
            condition = ExperimentCondition(condition)
        return self._configs[condition]

    def create_session(
        self,
        participant_id: str,
        condition: ExperimentCondition | str,
        session_id: str | None = None,
    ) -> ParticipantSession:
        """Create and register a new participant session.

        Args:
            participant_id: Participant label (e.g. ``"P001"``).
            condition: Experimental condition for this session.
            session_id: Optional session ID override.  Defaults to UUID4.

        Returns:
            New :class:`ParticipantSession`.
        """
        if isinstance(condition, str):
            condition = ExperimentCondition(condition)

        sid = session_id or str(uuid.uuid4())
        config = self.get_condition_config(condition)
        session = ParticipantSession(
            session_id=sid,
            participant_id=participant_id,
            condition=condition,
            condition_config=config,
        )
        self._sessions[sid] = session
        return session

    def get_session(self, session_id: str) -> ParticipantSession | None:
        """Retrieve a session by ID.

        Args:
            session_id: Session UUID.

        Returns:
            :class:`ParticipantSession` or ``None`` if not found.
        """
        return self._sessions.get(session_id)

    def get_all_sessions(self) -> list[ParticipantSession]:
        """Return all registered sessions."""
        return list(self._sessions.values())

    def get_sessions_by_participant(
        self, participant_id: str
    ) -> list[ParticipantSession]:
        """Return all sessions for a specific participant.

        Args:
            participant_id: Participant label.

        Returns:
            List of :class:`ParticipantSession` objects.
        """
        return [s for s in self._sessions.values() if s.participant_id == participant_id]

    def get_sessions_by_condition(
        self, condition: ExperimentCondition | str
    ) -> list[ParticipantSession]:
        """Return all sessions for a specific experimental condition.

        Args:
            condition: :class:`ExperimentCondition` or string identifier.

        Returns:
            List of :class:`ParticipantSession` objects.
        """
        if isinstance(condition, str):
            condition = ExperimentCondition(condition)
        return [s for s in self._sessions.values() if s.condition == condition]

    def export_data(self) -> list[dict[str, Any]]:
        """Export all session data as a list of dicts for analysis.

        Returns:
            List of session dicts, each including all task logs and
            questionnaire scores.
        """
        return [s.to_dict() for s in self._sessions.values()]

    def summarise(self) -> dict[str, Any]:
        """Return a high-level summary of the experiment data.

        Returns:
            Dict with totals and per-condition breakdowns.
        """
        total_sessions = len(self._sessions)
        completed = sum(1 for s in self._sessions.values() if s.end_time is not None)
        by_condition: dict[str, int] = {}
        total_tasks = 0
        for session in self._sessions.values():
            cond = session.condition.value
            by_condition[cond] = by_condition.get(cond, 0) + 1
            total_tasks += len(session.task_log)
        return {
            "total_sessions": total_sessions,
            "completed_sessions": completed,
            "total_tasks_logged": total_tasks,
            "sessions_by_condition": by_condition,
        }
