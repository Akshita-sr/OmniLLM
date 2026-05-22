"""HRI Task Classifier — maps utterances to the four Embodied LLM Arena task types.

Task types correspond to the four experimental conditions:

- **T1 — Information Retrieval**: Factual questions that benefit from RAG.
  Examples: "What time does the lab open?", "Tell me about Professor X".
- **T2 — Navigation/Guidance**: Spatial questions requiring robot gestures.
  Examples: "Where is Room 305?", "Point me to the cafeteria".
- **T3 — Social Conversation**: Open-ended chat testing naturalness and empathy.
  Examples: "How are you?", "What do you think about AI?".
- **T4 — Multilingual**: Any utterance in a non-English language.
  The system auto-detects language and routes to the best multilingual model.

The classifier uses a rule-based keyword approach by default (no external
dependencies) and can optionally use an LLM for more accurate classification
when a gateway is provided.

Usage::

    classifier = HRITaskClassifier()
    task_type, confidence = classifier.classify("Where is the bathroom?")
    print(task_type)   # HRITaskType.NAVIGATION
    print(confidence)  # 0.95

──────────────────────────────────────────────────────────────────────
BEGINNER ORIENTATION
──────────────────────────────────────────────────────────────────────
This file decides "what kind of question did the user ask?" so the
pipeline knows which model to route to. It is RULE-BASED on purpose
(zero latency, zero cost, deterministic) — see OMNILLM_MASTER_BOOK.md
§2.6 ("Deep Dive: Classification") for the design rationale.

Output: a ``ClassificationResult`` dataclass with ``task_type`` (one of
4 values), a confidence score 0–1, and a one-line reasoning string.
──────────────────────────────────────────────────────────────────────
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from omnillm.gateway import LLMGateway


# ──────────────────────────────────────────────────────────────────────
# THE FOUR TASK TYPES — exported as an Enum for type safety.
# beginner: an Enum is a fixed set of named constants. Using it everywhere
# prevents typos like ``"info_retrival"`` (missing 'e') that a plain string
# would silently allow.
# ──────────────────────────────────────────────────────────────────────
class HRITaskType(str, Enum):
    """The four HRI task types in the Embodied LLM Arena experiment."""

    INFO_RETRIEVAL = "info_retrieval"
    """T1: Factual questions answered from the knowledge base (RAG-dependent)."""

    NAVIGATION = "navigation"
    """T2: Spatial guidance requests requiring robot pointing/movement."""

    SOCIAL_CONVERSATION = "social_conversation"
    """T3: Open-ended conversational exchange testing naturalness/empathy."""

    MULTILINGUAL = "multilingual"
    """T4: Non-English utterances (auto-detected, routes to multilingual model)."""


@dataclass
class ClassificationResult:
    """Result of classifying a single utterance.

    Attributes:
        task_type: The predicted :class:`HRITaskType`.
        confidence: Classifier confidence in [0, 1].
        reasoning: Brief explanation of the classification decision.
        detected_language: ISO 639-1 language code (e.g. ``"en"``, ``"fr"``).
        method: Whether rule-based or llm classification was used.
    """

    task_type: HRITaskType
    confidence: float
    reasoning: str = ""
    detected_language: str = "en"
    method: str = "rule_based"


# ──────────────────────────────────────────────────────────────────────
# KEYWORD LISTS — the heart of the rule-based classifier.
# ──────────────────────────────────────────────────────────────────────
# beginner: ``frozenset`` is an immutable set. We use it because (a) set
# membership is O(1) which is fast, and (b) frozensets can't be modified
# accidentally — these are constants.
# ── Keyword lists for rule-based classification ────────────────────────────

# T2 — NAVIGATION. Words that suggest spatial guidance.
_NAVIGATION_KEYWORDS: frozenset[str] = frozenset(
    [
        "where", "room", "floor", "building", "cafeteria", "toilet", "bathroom",
        "restroom", "office", "lab", "laboratory", "exit", "entrance", "door",
        "stairs", "elevator", "lift", "corridor", "hall", "hallway", "point",
        "direction", "guide", "navigate", "take me", "show me", "how to get",
        "how do i get", "find", "locate", "map", "route",
    ]
)

# Regex patterns for navigation — matches multi-word phrases that a
# single-word keyword set can't catch. ``\b`` = word boundary.
_NAVIGATION_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\broom\s+\d+\b", re.IGNORECASE),
    re.compile(r"\b(floor|level)\s+\d+\b", re.IGNORECASE),
    re.compile(r"\bwhere\s+(is|are|can i find)\b", re.IGNORECASE),
    re.compile(r"\b(go to|take me to|show me|guide me to)\b", re.IGNORECASE),
    re.compile(r"\bhow (to get|do i get) to\b", re.IGNORECASE),
]

# T3 — SOCIAL CONVERSATION.
_SOCIAL_KEYWORDS: frozenset[str] = frozenset(
    [
        "how are you", "tell me", "what do you think", "do you like", "your opinion",
        "what is your", "nice to meet", "hello", "hi there", "good morning",
        "good afternoon", "good evening", "how's it going", "how have you been",
        "what's new", "chat", "talk", "joke", "story", "interesting", "favourite",
        "favorite", "feel", "think", "believe", "enjoy", "love", "hate",
        "what are you", "can you", "do you", "are you",
    ]
)

_SOCIAL_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\bhow are you\b", re.IGNORECASE),
    re.compile(r"\btell me (something|a joke|a story|about yourself)\b", re.IGNORECASE),
    re.compile(r"\bwhat do you (think|feel|believe)\b", re.IGNORECASE),
    re.compile(r"\b(nice to meet|good to meet)\b", re.IGNORECASE),
    re.compile(r"\b(are you|do you) (a robot|an AI|intelligent|happy|sad)\b", re.IGNORECASE),
]

# T1 — INFO RETRIEVAL (factual questions about the lab / people / facilities).
_INFO_RETRIEVAL_KEYWORDS: frozenset[str] = frozenset(
    [
        "hours", "open", "close", "schedule", "time", "when", "professor",
        "researcher", "research", "project", "publication", "wifi", "password",
        "wifi password", "internet", "network", "phone", "email", "contact",
        "who is", "what is the", "tell me about", "information about",
        "what are the", "describe", "explain",
    ]
)

_INFO_RETRIEVAL_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\b(what time|when does|when do|what are the hours)\b", re.IGNORECASE),
    re.compile(r"\b(tell me about|information about|who is|what is)\b", re.IGNORECASE),
    re.compile(r"\b(professor|dr\.?|doctor|researcher)\s+\w+\b", re.IGNORECASE),
    re.compile(r"\b(wifi|password|internet)\b", re.IGNORECASE),
    re.compile(r"\b(research|project|publication|paper)\b", re.IGNORECASE),
]


# ──────────────────────────────────────────────────────────────────────
# THE CLASSIFIER CLASS.
# ──────────────────────────────────────────────────────────────────────
class HRITaskClassifier:
    """Classifies user utterances into HRI task types (T1–T4).

    Uses a rule-based approach by default (no external dependencies).
    When a :class:`~omnillm.gateway.LLMGateway` is provided, can optionally
    use LLM-based classification for higher accuracy on ambiguous inputs.

    Example::

        classifier = HRITaskClassifier()
        result = classifier.classify("Where is Room 305?")
        print(result.task_type)    # HRITaskType.NAVIGATION
        print(result.confidence)   # 0.95
    """

    def __init__(
        self,
        gateway: LLMGateway | None = None,
        classifier_model: str = "openai-gpt4o-mini",
        language_threshold: float = 0.85,
    ) -> None:
        """Initialise the task classifier.

        Args:
            gateway: Optional :class:`~omnillm.gateway.LLMGateway` for
                LLM-based classification on ambiguous inputs.
            classifier_model: Model ID to use for LLM-based classification.
            language_threshold: Confidence threshold below which the classifier
                defers to multilingual routing.
        """
        self.gateway = gateway
        self.classifier_model = classifier_model
        self.language_threshold = language_threshold

    # ──────────────────────────────────────────────────────────────────
    # THE MAIN ENTRY POINT — call this once per utterance.
    # ──────────────────────────────────────────────────────────────────
    def classify(
        self,
        utterance: str,
        detected_language: str = "en",
    ) -> ClassificationResult:
        """Classify an utterance into a task type (rule-based).

        Non-English utterances (``detected_language != "en"``) are immediately
        classified as :attr:`HRITaskType.MULTILINGUAL`.

        Args:
            utterance: The user's spoken input (transcribed text).
            detected_language: ISO 639-1 language code (default ``"en"``).

        Returns:
            :class:`ClassificationResult` with task type and confidence.
        """
        # T4: Multilingual ALWAYS takes precedence over content classification.
        # If the user is speaking French, they're asking a "multilingual"
        # question regardless of whether the content is factual or social.
        # The multilingual model itself will figure out the rest.
        if detected_language != "en":
            return ClassificationResult(
                task_type=HRITaskType.MULTILINGUAL,
                confidence=0.99,
                reasoning=f"Non-English input detected (language={detected_language})",
                detected_language=detected_language,
                method="rule_based",
            )

        text_lower = utterance.lower()
        # beginner: ``re.findall(r"\b\w+\b", text)`` splits the text into
        # words by word boundaries. We use a set so membership checks are O(1).
        words = set(re.findall(r"\b\w+\b", text_lower))

        # Score each category against the same text.
        nav_score = self._score_category(
            text_lower, words, _NAVIGATION_KEYWORDS, _NAVIGATION_PATTERNS
        )
        social_score = self._score_category(
            text_lower, words, _SOCIAL_KEYWORDS, _SOCIAL_PATTERNS
        )
        info_score = self._score_category(
            text_lower, words, _INFO_RETRIEVAL_KEYWORDS, _INFO_RETRIEVAL_PATTERNS
        )

        scores: dict[HRITaskType, float] = {
            HRITaskType.NAVIGATION: nav_score,
            HRITaskType.SOCIAL_CONVERSATION: social_score,
            HRITaskType.INFO_RETRIEVAL: info_score,
        }

        # Pick the highest-scoring task type.
        best_type = max(scores, key=lambda t: scores[t])
        best_score = scores[best_type]

        # Default to INFO_RETRIEVAL if no signal is strong enough. This is
        # the safest fallback because RAG will gracefully say "I don't know"
        # for vague inputs, whereas defaulting to SOCIAL might give a wrong
        # tone for a factual question.
        if best_score < 0.1:
            return ClassificationResult(
                task_type=HRITaskType.INFO_RETRIEVAL,
                confidence=0.4,
                reasoning="No strong task signal — defaulting to info_retrieval",
                detected_language=detected_language,
                method="rule_based",
            )

        # Map raw score [0.1, 1.0] → confidence [0.59, 0.95]. The +0.5 floor
        # reflects that "we matched something" gives at least 50% confidence.
        # Normalise confidence: 0.1 → 0.5, 0.5+ → 0.95
        confidence = min(0.95, 0.5 + best_score * 0.9)

        return ClassificationResult(
            task_type=best_type,
            confidence=round(confidence, 2),
            reasoning=f"Rule-based scores: nav={nav_score:.2f}, social={social_score:.2f}, info={info_score:.2f}",
            detected_language=detected_language,
            method="rule_based",
        )

    # ──────────────────────────────────────────────────────────────────
    # OPTIONAL: LLM-based classification for ambiguous inputs.
    # Slower (~300 ms) and costs ~$0.0002 per call. Not used by default.
    # ──────────────────────────────────────────────────────────────────
    async def classify_with_llm(
        self, utterance: str, detected_language: str = "en"
    ) -> ClassificationResult:
        """Classify an utterance using LLM-based zero-shot classification.

        Provides higher accuracy than rule-based on ambiguous or complex inputs.
        Requires ``self.gateway`` to be set.

        Args:
            utterance: The user's spoken input.
            detected_language: ISO 639-1 language code.

        Returns:
            :class:`ClassificationResult`.

        Raises:
            RuntimeError: If no gateway was provided at initialisation.
        """
        if self.gateway is None:
            raise RuntimeError(
                "LLM classification requires a gateway. Pass gateway=LLMGateway() to __init__."
            )

        import json

        # T4: Multilingual takes precedence (same rule as rule-based path).
        if detected_language != "en":
            return ClassificationResult(
                task_type=HRITaskType.MULTILINGUAL,
                confidence=0.99,
                reasoning=f"Non-English input (language={detected_language})",
                detected_language=detected_language,
                method="llm",
            )

        # The actual classification prompt. Note the "Respond ONLY with valid
        # JSON" line — we then parse the response with json.loads().
        prompt = (
            "Classify the following user utterance from a human-robot interaction "
            "into one of four categories:\n\n"
            "1. info_retrieval — factual question about the lab, people, schedule, facilities\n"
            "2. navigation — asking for directions, location of a room, spatial guidance\n"
            "3. social_conversation — casual chat, greeting, personal questions, opinions\n"
            "4. multilingual — utterance in a non-English language\n\n"
            f'Utterance: "{utterance}"\n\n'
            'Respond ONLY with valid JSON: {"task_type": "info_retrieval"|"navigation"|'
            '"social_conversation"|"multilingual", "confidence": <float 0.0-1.0>, '
            '"reasoning": "<one sentence>"}'
        )

        messages = [{"role": "user", "content": prompt}]
        # temperature=0.0 makes the LLM deterministic — same input always
        # produces the same output. Critical for a classifier.
        resp = await self.gateway.query(self.classifier_model, messages, temperature=0.0)

        if resp.is_error:
            # Network/rate-limit failure → fall back to rule-based. Better
            # to classify with reduced accuracy than to crash.
            return self.classify(utterance, detected_language)

        try:
            raw = resp.content.strip()
            # Strip Markdown code fences if the LLM added them despite our
            # "Respond ONLY with JSON" instruction. Models sometimes do this.
            if "```" in raw:
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            data = json.loads(raw)
            task_str = str(data.get("task_type", "info_retrieval"))
            task_type = HRITaskType(task_str)
            # Clamp confidence to [0, 1] just in case the LLM returned 1.2 or -0.3.
            confidence = float(min(max(data.get("confidence", 0.7), 0.0), 1.0))
            reasoning = str(data.get("reasoning", ""))
            return ClassificationResult(
                task_type=task_type,
                confidence=confidence,
                reasoning=reasoning,
                detected_language=detected_language,
                method="llm",
            )
        except (json.JSONDecodeError, ValueError, KeyError):
            # Malformed JSON or unknown task_type → fall back to rule-based.
            return self.classify(utterance, detected_language)

    # ── Private helpers ───────────────────────────────────────────────────────

    @staticmethod
    def _score_category(
        text: str,
        words: set[str],
        keywords: frozenset[str],
        patterns: list[re.Pattern[str]],
    ) -> float:
        """Compute a weighted score for a task category.

        Scoring formula:
          - Single-word keyword overlap: up to +0.3 (0.1 per hit, capped)
          - Multi-word keyword phrase hit: +0.15 each
          - Regex pattern match: +0.25 each
        Max score is clamped to 1.0.
        """
        score = 0.0
        # Keyword overlap score
        keyword_hits = len(words & keywords)
        if keyword_hits:
            score += min(0.3, keyword_hits * 0.1)
        # Phrase keyword hits (multi-word)
        for kw in keywords:
            if " " in kw and kw in text:
                score += 0.15
        # Pattern match bonus
        for pattern in patterns:
            if pattern.search(text):
                score += 0.25
        return min(1.0, score)
