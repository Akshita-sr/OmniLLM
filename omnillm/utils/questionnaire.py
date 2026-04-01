"""Questionnaire data models for the Embodied LLM Arena study.

Implements the post-interaction questionnaire described in the research design,
capturing:

1. **Interaction Questionnaire** (after each condition block):
   - "The robot's answers were accurate" (1–7 Likert)
   - "The robot was natural to talk to" (1–7 Likert)
   - "I trust the information the robot gave me" (1–7 Likert)
   - "The robot's gestures were appropriate" (1–7 Likert)
   - "The robot responded quickly enough" (1–7 Likert)

2. **Godspeed Subscales** (perceived intelligence, naturalness, trust):
   Standard HRI evaluation scales (Bartneck et al., 2009).

3. **Pairwise Preference** (end of session):
   "Which version of Pepper did you prefer?" — used to update ELO ratings.

Usage::

    from omnillm.utils.questionnaire import (
        InteractionQuestionnaire,
        PairwisePreference,
        QuestionnaireCollector,
    )

    q = InteractionQuestionnaire(
        session_id="s1",
        participant_id="P001",
        condition="C",
        accuracy=6,
        naturalness=5,
        trust=6,
        gesture_appropriateness=5,
        response_speed=7,
    )
    print(q.mean_score)   # 5.8

    pref = PairwisePreference(
        session_id="s1",
        participant_id="P001",
        condition_a="A",
        condition_b="C",
        preferred="C",
    )

    collector = QuestionnaireCollector()
    collector.add_interaction_response(q)
    collector.add_pairwise_preference(pref)
    collector.save("results/questionnaire_data.json")
"""

from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal


# ── Likert scale type ─────────────────────────────────────────────────────────

LikertScale = Literal[1, 2, 3, 4, 5, 6, 7]
"""1–7 Likert scale used for all questionnaire items."""


# ── Interaction Questionnaire ─────────────────────────────────────────────────

@dataclass
class InteractionQuestionnaire:
    """Post-interaction questionnaire response (after each experimental condition).

    Uses a 1–7 Likert scale (1=strongly disagree, 7=strongly agree).

    Attributes:
        session_id: Session UUID.
        participant_id: Participant label (e.g. ``"P001"``).
        condition: Experimental condition (``"A"``–``"E"``).
        accuracy: "The robot's answers were accurate" (1–7).
        naturalness: "The robot was natural to talk to" (1–7).
        trust: "I trust the information the robot gave me" (1–7).
        gesture_appropriateness: "The robot's gestures were appropriate" (1–7).
        response_speed: "The robot responded quickly enough" (1–7).
        free_text: Optional open-ended feedback.
        timestamp: ISO 8601 timestamp when questionnaire was completed.
    """

    session_id: str
    participant_id: str
    condition: str
    accuracy: int = 4
    naturalness: int = 4
    trust: int = 4
    gesture_appropriateness: int = 4
    response_speed: int = 4
    free_text: str = ""
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def __post_init__(self) -> None:
        for attr in ("accuracy", "naturalness", "trust", "gesture_appropriateness", "response_speed"):
            val = getattr(self, attr)
            if not (1 <= val <= 7):
                raise ValueError(
                    f"Likert score for '{attr}' must be between 1 and 7, got {val}"
                )

    @property
    def mean_score(self) -> float:
        """Mean of all five Likert items (1–7)."""
        scores = [
            self.accuracy,
            self.naturalness,
            self.trust,
            self.gesture_appropriateness,
            self.response_speed,
        ]
        return sum(scores) / len(scores)

    @property
    def normalised_score(self) -> float:
        """Mean score normalised to [0, 1]."""
        return (self.mean_score - 1) / 6.0


# ── Godspeed Subscales ────────────────────────────────────────────────────────

@dataclass
class GodspeedResponse:
    """Godspeed questionnaire subscale ratings (Bartneck et al., 2009).

    Five subscales, each rated 1–5 (bipolar adjective pairs):

    - **Anthropomorphism**: Fake–Natural, Machine-like–Human-like,
      Unconscious–Conscious, Artificial–Lifelike, Moving rigidly–Moving elegantly
    - **Animacy**: Dead–Alive, Stagnant–Lively, Mechanical–Organic,
      Artificial–Lifelike, Inert–Interactive, Apathetic–Responsive
    - **Likeability**: Dislike–Like, Unfriendly–Friendly, Unkind–Kind,
      Unpleasant–Pleasant, Awful–Nice
    - **Perceived Intelligence**: Incompetent–Competent, Ignorant–Knowledgeable,
      Irresponsible–Responsible, Unintelligent–Intelligent, Foolish–Sensible
    - **Perceived Safety**: Anxious–Relaxed, Agitated–Calm,
      Quiescent–Surprised, Surprised–Quiescent

    Reference:
        Bartneck, C., Kulić, D., Croft, E., & Zoghbi, S. (2009).
        Measurement instruments for the anthropomorphism, animacy, likeability,
        perceived intelligence, and perceived safety of robots.
        *International Journal of Social Robotics*, 1(1), 71–81.
    """

    session_id: str
    participant_id: str
    condition: str
    anthropomorphism: float = 3.0
    """Mean of anthropomorphism items (1–5)."""
    animacy: float = 3.0
    """Mean of animacy items (1–5)."""
    likeability: float = 3.0
    """Mean of likeability items (1–5)."""
    perceived_intelligence: float = 3.0
    """Mean of perceived intelligence items (1–5)."""
    perceived_safety: float = 3.0
    """Mean of perceived safety items (1–5)."""
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    @property
    def overall_mean(self) -> float:
        """Mean across all five subscale scores."""
        return (
            self.anthropomorphism
            + self.animacy
            + self.likeability
            + self.perceived_intelligence
            + self.perceived_safety
        ) / 5.0


# ── Pairwise Preference ───────────────────────────────────────────────────────

@dataclass
class PairwisePreference:
    """Records a participant's pairwise preference between two conditions.

    Used to update ELO ratings via :class:`~omnillm.scorer.EloScorer`.

    Attributes:
        session_id: Session UUID.
        participant_id: Participant label.
        condition_a: First condition presented (``"A"``–``"E"``).
        condition_b: Second condition presented.
        preferred: Which condition the participant preferred
            (``"A"``–``"E"``, or ``"tie"`` if no preference).
        reasoning: Optional participant explanation of their choice.
        timestamp: ISO 8601 timestamp.
    """

    session_id: str
    participant_id: str
    condition_a: str
    condition_b: str
    preferred: str
    reasoning: str = ""
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


# ── Observer Rating ───────────────────────────────────────────────────────────

@dataclass
class ObserverRating:
    """Observer-rated metrics during a live HRI interaction.

    Filled in by the experimenter or a colleague watching the interaction.

    Attributes:
        session_id: Session UUID.
        participant_id: Participant label.
        condition: Experimental condition.
        task_type: HRI task type (``"info_retrieval"``, ``"navigation"``, etc.).
        gesture_sync_quality: Gesture–speech synchronisation quality (1–5).
        task_completed: Whether the participant obtained the correct information.
        breakdown_count: Number of interaction breakdown moments observed.
        notes: Free-form observer notes.
    """

    session_id: str
    participant_id: str
    condition: str
    task_type: str
    gesture_sync_quality: int = 3
    task_completed: bool = True
    breakdown_count: int = 0
    notes: str = ""
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


# ── Collector ─────────────────────────────────────────────────────────────────

class QuestionnaireCollector:
    """Aggregates and exports all questionnaire data for the study.

    Example::

        collector = QuestionnaireCollector()
        collector.add_interaction_response(q)
        collector.add_pairwise_preference(pref)
        collector.add_godspeed(gs)
        collector.save("results/questionnaires.json")
        collector.to_csv("results/questionnaires.csv")
        summary = collector.summary_by_condition()
    """

    def __init__(self) -> None:
        self._interaction: list[InteractionQuestionnaire] = []
        self._godspeed: list[GodspeedResponse] = []
        self._preferences: list[PairwisePreference] = []
        self._observer: list[ObserverRating] = []

    # ── Add records ───────────────────────────────────────────────────────────

    def add_interaction_response(self, q: InteractionQuestionnaire) -> None:
        """Add an interaction questionnaire response."""
        self._interaction.append(q)

    def add_godspeed(self, gs: GodspeedResponse) -> None:
        """Add a Godspeed subscale rating."""
        self._godspeed.append(gs)

    def add_pairwise_preference(self, pref: PairwisePreference) -> None:
        """Add a pairwise preference record."""
        self._preferences.append(pref)

    def add_observer_rating(self, obs: ObserverRating) -> None:
        """Add an observer rating."""
        self._observer.append(obs)

    # ── Summary ───────────────────────────────────────────────────────────────

    def summary_by_condition(self) -> dict[str, dict[str, float]]:
        """Compute mean Likert scores per experimental condition.

        Returns:
            Dict mapping condition ID (``"A"``–``"E"``) to a dict of
            mean scores for each questionnaire item.
        """
        from collections import defaultdict

        buckets: dict[str, list[InteractionQuestionnaire]] = defaultdict(list)
        for q in self._interaction:
            buckets[q.condition].append(q)

        summary: dict[str, dict[str, float]] = {}
        for condition, responses in sorted(buckets.items()):
            if not responses:
                continue
            n = len(responses)
            summary[condition] = {
                "n": float(n),
                "mean_accuracy": sum(r.accuracy for r in responses) / n,
                "mean_naturalness": sum(r.naturalness for r in responses) / n,
                "mean_trust": sum(r.trust for r in responses) / n,
                "mean_gesture": sum(r.gesture_appropriateness for r in responses) / n,
                "mean_speed": sum(r.response_speed for r in responses) / n,
                "mean_overall": sum(r.mean_score for r in responses) / n,
            }
        return summary

    def pairwise_win_rates(self) -> dict[str, dict[str, float]]:
        """Compute pairwise win rates between conditions.

        Returns:
            Dict ``{condition_a: {condition_b: win_rate}}`` where win_rate
            is the fraction of comparisons in which condition_a was preferred
            over condition_b.
        """
        from collections import defaultdict

        wins: dict[tuple[str, str], int] = defaultdict(int)
        total: dict[tuple[str, str], int] = defaultdict(int)

        for pref in self._preferences:
            a, b = pref.condition_a, pref.condition_b
            key = (a, b)
            total[key] += 1
            if pref.preferred == a:
                wins[(a, b)] += 1
            elif pref.preferred == b:
                wins[(b, a)] += 1
            else:
                wins[(a, b)] += 0  # tie

        result: dict[str, dict[str, float]] = {}
        for (a, b), n in total.items():
            result.setdefault(a, {})[b] = wins[(a, b)] / n if n > 0 else 0.0
        return result

    # ── Persistence ───────────────────────────────────────────────────────────

    def save(self, path: str | Path) -> None:
        """Save all questionnaire data to a JSON file.

        Args:
            path: Output file path.
        """
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "interaction_responses": [asdict(q) for q in self._interaction],
            "godspeed_responses": [asdict(gs) for gs in self._godspeed],
            "pairwise_preferences": [asdict(p) for p in self._preferences],
            "observer_ratings": [asdict(o) for o in self._observer],
            "summary_by_condition": self.summary_by_condition(),
            "pairwise_win_rates": self.pairwise_win_rates(),
        }
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2)

    def to_csv(self, path: str | Path) -> None:
        """Export interaction questionnaire responses to CSV.

        Args:
            path: Output CSV file path.
        """
        if not self._interaction:
            return

        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        fieldnames = list(asdict(self._interaction[0]).keys()) + ["mean_score", "normalised_score"]

        with open(path, "w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=fieldnames)
            writer.writeheader()
            for q in self._interaction:
                row = asdict(q)
                row["mean_score"] = round(q.mean_score, 3)
                row["normalised_score"] = round(q.normalised_score, 3)
                writer.writerow(row)
