"""Autonomous Triage Classifier — the LLM-OS kernel for OmniLLM.

Decides three things about every incoming utterance, before any expensive
model is called:

- **intent**: what kind of question this is (info, coding, navigation, social,
  reasoning, general chat, dangerous/medical, or genuinely ambiguous)
- **complexity**: simple, medium, or complex — gates the System-1 (single
  fast model) vs. System-2 (multi-model council) decision
- **safety**: safe, dangerous_or_medical, or ambiguous — gates the
  safety-aware council judge

Hybrid two-stage classifier:

1. **Rule pass** (always runs, ~0 ms, free) — keyword + regex match scores
   for each intent. If one intent dominates AND confidence >= threshold,
   return immediately.
2. **LLM escalation** (only on ambiguous, ~300 ms, ~$0.0001) — calls a
   small fast model (default ``claude-haiku``) with a strict JSON prompt
   to disambiguate. Failures fall back to the rule-pass result.

Safety override: if EITHER stage flags ``dangerous_or_medical``, that wins
unconditionally — the result is locked regardless of what the other stage
said. Better one false positive (uses council) than one false negative
(robot gives unsafe medical advice).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from omnillm.gateway import LLMGateway


Intent = Literal[
    "information_request",
    "coding",
    "navigation",
    "social",
    "reasoning",
    "general_chat",
    "dangerous_or_medical",
    "ambiguous",
]

Complexity = Literal["simple", "medium", "complex"]

Safety = Literal["safe", "dangerous_or_medical", "ambiguous"]


@dataclass
class TriageResult:
    """Output of the triage classifier."""

    intent: Intent
    complexity: Complexity
    safety: Safety
    confidence: float
    method: Literal["rule_based", "llm_escalated"]
    reasoning: str


# ──────────────────────────────────────────────────────────────────────
# RULE TABLES
# ──────────────────────────────────────────────────────────────────────
# Keyword sets are case-insensitive. Multi-word phrases are matched against
# the lowercased text; single words are matched against the tokenised word
# set so partial words don't trigger.

_DANGEROUS_KEYWORDS: frozenset[str] = frozenset(
    [
        "medical advice", "diagnose", "diagnosis", "dosage", "dose of",
        "overdose", "prescription", "self-harm", "suicide", "kill myself",
        "hurt myself", "weapon", "bomb", "poison", "explosive",
        "how to make a", "illegal drug",
    ]
)

# Common medication / drug names — combined with "take" / "dose" / "much"
# patterns below to catch "How much ibuprofen should I take?" style asks.
_MEDICATIONS: frozenset[str] = frozenset(
    [
        "ibuprofen", "acetaminophen", "paracetamol", "tylenol", "advil",
        "aspirin", "naproxen", "morphine", "oxycodone", "codeine",
        "xanax", "valium", "ambien", "lorazepam", "diazepam",
        "insulin", "warfarin", "metformin", "antibiotic", "antibiotics",
        "antidepressant", "antidepressants", "ssri", "benzodiazepine",
    ]
)

# Patterns catch phrasings keyword lists miss.
_DANGEROUS_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\bhow (much|many) (mg|milligrams?|grams?|pills?) of\b", re.IGNORECASE),
    re.compile(r"\bshould i (take|stop taking)\b.*\b(medication|medicine|drug)\b", re.IGNORECASE),
    re.compile(r"\b(am i|do i) (having|have) a\b.*(stroke|heart attack|allergic reaction)\b", re.IGNORECASE),
    # "How much/many X" where X is any medication.
    re.compile(
        r"\bhow (much|many)\b.*\b(" + "|".join(_MEDICATIONS) + r")\b",
        re.IGNORECASE,
    ),
    # "Should I / can I / is it safe to take X" where X is any medication.
    re.compile(
        r"\b(should i|can i|is it safe to|how do i) (take|use|combine|mix)\b.*\b("
        + "|".join(_MEDICATIONS) + r")\b",
        re.IGNORECASE,
    ),
]

_CODING_KEYWORDS: frozenset[str] = frozenset(
    [
        "function", "method", "class", "variable", "loop", "array", "dict",
        "list", "string", "regex", "algorithm", "stack trace", "traceback",
        "syntax error", "bug", "debug", "compile", "runtime error",
        "import", "module", "package", "repo", "git", "commit", "merge",
        "branch", "api", "endpoint", "http", "json", "yaml",
    ]
)

_CODING_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\b(python|javascript|typescript|java|c\+\+|rust|go|ruby|php|swift|kotlin)\b", re.IGNORECASE),
    re.compile(r"\b(write|fix|debug|refactor)\s+(a|the|my)?\s*(code|function|class|script|program)\b", re.IGNORECASE),
    re.compile(r"\bdef\s+\w+\s*\(", re.IGNORECASE),
    re.compile(r"```", re.IGNORECASE),
]

_NAVIGATION_KEYWORDS: frozenset[str] = frozenset(
    [
        "where", "room", "floor", "building", "cafeteria", "bathroom",
        "toilet", "lab", "office", "exit", "entrance", "stairs", "elevator",
        "point", "direction", "guide", "navigate", "take me", "show me",
        "how to get", "how do i get", "find", "locate",
    ]
)

_NAVIGATION_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\broom\s+\d+\b", re.IGNORECASE),
    re.compile(r"\bwhere\s+(is|are|can i find)\b", re.IGNORECASE),
    re.compile(r"\bhow (to get|do i get) to\b", re.IGNORECASE),
]

_SOCIAL_KEYWORDS: frozenset[str] = frozenset(
    [
        "how are you", "tell me about yourself", "what's your name",
        "your name", "hello", "hi there", "good morning", "good afternoon",
        "good evening", "nice to meet", "joke", "story", "favourite",
        "favorite", "feel", "do you like",
    ]
)

_SOCIAL_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\bhow are you\b", re.IGNORECASE),
    re.compile(r"\b(nice to meet|good to meet)\b", re.IGNORECASE),
    re.compile(r"\b(are you|do you) (a robot|an ai|happy|sad)\b", re.IGNORECASE),
]

_INFO_KEYWORDS: frozenset[str] = frozenset(
    [
        "hours", "open", "close", "schedule", "when", "professor",
        "researcher", "publication", "wifi", "password", "email", "contact",
        "who is", "what is the", "tell me about", "information about",
    ]
)

_INFO_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\b(what time|when does|when do|what are the hours)\b", re.IGNORECASE),
    re.compile(r"\b(tell me about|information about|who is|what is)\b", re.IGNORECASE),
    re.compile(r"\b(professor|dr\.?|doctor)\s+\w+\b", re.IGNORECASE),
]

_REASONING_KEYWORDS: frozenset[str] = frozenset(
    [
        "why", "how does", "step by step", "calculate", "compute", "solve",
        "prove", "compare", "trade-off", "tradeoff", "analyse", "analyze",
        "deduce", "implication", "consequence", "suppose", "assuming",
    ]
)

_REASONING_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\bwhy\s+(does|is|are|do|did|would|should)\b", re.IGNORECASE),
    re.compile(r"\bhow does\s+\w+\s+work\b", re.IGNORECASE),
    re.compile(r"\bstep[\s-]by[\s-]step\b", re.IGNORECASE),
]

# Complexity heuristics: words/phrases that signal the answer needs multi-step
# reasoning or comparison, NOT a simple fact lookup.
_COMPLEX_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\b(compare|contrast|trade-?off|pros and cons)\b", re.IGNORECASE),
    re.compile(r"\b(analyse|analyze|evaluate|critique|assess)\b", re.IGNORECASE),
    re.compile(r"\b(explain (in detail|thoroughly|how|why))\b", re.IGNORECASE),
    re.compile(r"\?.*\?", re.IGNORECASE),  # multiple questions in one utterance
]


# ──────────────────────────────────────────────────────────────────────
# THE CLASSIFIER
# ──────────────────────────────────────────────────────────────────────
class TriageClassifier:
    """Hybrid rule + LLM triage classifier.

    Always runs the rule pass first (cheap, deterministic). Escalates to an
    LLM only when rules can't decide confidently — keeping average latency
    near zero while preserving accuracy on tricky inputs.

    Example::

        triage = TriageClassifier(gateway)
        result = await triage.triage("Why does my Python loop hang?")
        # → intent="coding", complexity="medium", safety="safe"
    """

    def __init__(
        self,
        gateway: "LLMGateway | None" = None,
        triage_model: str = "claude-haiku",
        confidence_threshold: float = 0.7,
    ) -> None:
        """Initialise the triage classifier.

        Args:
            gateway: Optional :class:`~omnillm.gateway.LLMGateway` for LLM
                escalation. If ``None``, the classifier is rule-only.
            triage_model: Cheap fast model used for escalation
                (default: ``claude-haiku``).
            confidence_threshold: Rule confidence below this triggers
                escalation (when a gateway is available).
        """
        self.gateway = gateway
        self.triage_model = triage_model
        self.confidence_threshold = confidence_threshold

    async def triage(
        self, utterance: str, language: str = "en"
    ) -> TriageResult:
        """Triage one utterance.

        Args:
            utterance: User's text (already transcribed if mic input).
            language: ISO 639-1 language code (currently informational only —
                multilingual still goes through the regular pipeline).

        Returns:
            :class:`TriageResult` with intent, complexity, safety.
        """
        text_lower = utterance.lower()
        words = set(re.findall(r"\b\w+\b", text_lower))

        # ── Stage 1: safety check (highest priority) ─────────────────────
        safety, safety_reason = self._score_safety(text_lower, words)

        # ── Stage 2: intent scoring ──────────────────────────────────────
        intent_scores = self._score_intents(text_lower, words)
        best_intent, best_score = max(intent_scores.items(), key=lambda kv: kv[1])

        # ── Stage 3: complexity scoring ──────────────────────────────────
        complexity = self._score_complexity(text_lower, utterance, best_intent)

        # ── Stage 4: confidence + escalation decision ────────────────────
        confidence = min(0.95, 0.5 + best_score * 0.9) if best_score > 0 else 0.4
        needs_escalation = (
            self.gateway is not None
            and confidence < self.confidence_threshold
            and safety == "safe"  # never delay safety decisions
        )

        if needs_escalation:
            llm_result = await self._llm_escalate(utterance)
            if llm_result is not None:
                # LLM safety can only ESCALATE, never downgrade.
                if llm_result.safety != "safe":
                    final_safety = llm_result.safety
                else:
                    final_safety = safety
                return TriageResult(
                    intent=llm_result.intent,
                    complexity=llm_result.complexity,
                    safety=final_safety,
                    confidence=llm_result.confidence,
                    method="llm_escalated",
                    reasoning=llm_result.reasoning,
                )

        # Rule-based result
        return TriageResult(
            intent=best_intent if best_score > 0 else "ambiguous",
            complexity=complexity,
            safety=safety,
            confidence=round(confidence, 2),
            method="rule_based",
            reasoning=(
                f"Rules: intent_scores={ {k: round(v, 2) for k, v in intent_scores.items()} }, "
                f"safety={safety_reason}"
            ),
        )

    # ── Private helpers ────────────────────────────────────────────────────

    def _score_safety(
        self, text_lower: str, words: set[str]
    ) -> tuple[Safety, str]:
        """Return (safety_label, short_reason)."""
        for kw in _DANGEROUS_KEYWORDS:
            if " " in kw and kw in text_lower:
                return "dangerous_or_medical", f"keyword '{kw}'"
            if " " not in kw and kw in words:
                return "dangerous_or_medical", f"keyword '{kw}'"
        for pat in _DANGEROUS_PATTERNS:
            if pat.search(text_lower):
                return "dangerous_or_medical", f"pattern '{pat.pattern[:40]}'"
        return "safe", "no safety triggers"

    def _score_intents(
        self, text_lower: str, words: set[str]
    ) -> dict[Intent, float]:
        """Score each intent category 0.0-1.0 (rule-based)."""
        return {
            "information_request": _category_score(
                text_lower, words, _INFO_KEYWORDS, _INFO_PATTERNS
            ),
            "coding": _category_score(
                text_lower, words, _CODING_KEYWORDS, _CODING_PATTERNS
            ),
            "navigation": _category_score(
                text_lower, words, _NAVIGATION_KEYWORDS, _NAVIGATION_PATTERNS
            ),
            "social": _category_score(
                text_lower, words, _SOCIAL_KEYWORDS, _SOCIAL_PATTERNS
            ),
            "reasoning": _category_score(
                text_lower, words, _REASONING_KEYWORDS, _REASONING_PATTERNS
            ),
            # general_chat is the implicit fallback — never wins on its own;
            # the pipeline maps "ambiguous" + low score to it.
            "general_chat": 0.0,
        }

    def _score_complexity(
        self, text_lower: str, utterance: str, intent: Intent
    ) -> Complexity:
        """Estimate complexity from length, structure, and intent."""
        word_count = len(utterance.split())
        complex_hits = sum(1 for p in _COMPLEX_PATTERNS if p.search(text_lower))

        # Reasoning intent is always at least medium.
        if intent == "reasoning":
            return "complex" if (complex_hits or word_count > 20) else "medium"
        # Coding: long utterances usually contain context + a request.
        if intent == "coding":
            return "complex" if word_count > 30 else "medium"
        if complex_hits >= 1 or word_count > 40:
            return "complex"
        if word_count > 12:
            return "medium"
        return "simple"

    async def _llm_escalate(
        self, utterance: str
    ) -> TriageResult | None:
        """Call ``triage_model`` to disambiguate. Returns None on any error.

        Failures fall back to the rule-based result rather than raising —
        the pipeline must not crash because triage hiccupped.
        """
        if self.gateway is None:
            return None

        prompt = (
            "Classify the following user utterance for a robot AI system.\n"
            "Return ONLY valid JSON with three fields:\n"
            '- "intent": one of [information_request, coding, navigation, '
            "social, reasoning, general_chat, dangerous_or_medical]\n"
            '- "complexity": one of [simple, medium, complex]\n'
            '- "safety": one of [safe, dangerous_or_medical, ambiguous]\n'
            f'\nUtterance: "{utterance}"\n\n'
            'Format: {"intent": "...", "complexity": "...", "safety": "...", '
            '"reasoning": "<one short sentence>"}'
        )
        messages = [{"role": "user", "content": prompt}]
        resp = await self.gateway.query(
            self.triage_model, messages, temperature=0.0, max_tokens=200
        )
        if resp.is_error:
            return None

        try:
            raw = resp.content.strip()
            if "```" in raw:
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            data = json.loads(raw)
            return TriageResult(
                intent=_coerce_intent(data.get("intent", "ambiguous")),
                complexity=_coerce_complexity(data.get("complexity", "simple")),
                safety=_coerce_safety(data.get("safety", "safe")),
                confidence=0.85,
                method="llm_escalated",
                reasoning=str(data.get("reasoning", ""))[:200],
            )
        except (json.JSONDecodeError, ValueError, KeyError, TypeError):
            return None


# ──────────────────────────────────────────────────────────────────────
# MODULE-LEVEL HELPERS
# ──────────────────────────────────────────────────────────────────────
def _category_score(
    text: str,
    words: set[str],
    keywords: frozenset[str],
    patterns: list[re.Pattern[str]],
) -> float:
    """Score one category 0.0-1.0 using the same recipe as HRITaskClassifier.

    Single-word overlap: up to +0.3. Multi-word phrase hit: +0.15 each.
    Regex pattern match: +0.25 each. Clamped to 1.0.
    """
    score = 0.0
    single_word_hits = len(words & {k for k in keywords if " " not in k})
    if single_word_hits:
        score += min(0.3, single_word_hits * 0.1)
    for kw in keywords:
        if " " in kw and kw in text:
            score += 0.15
    for pat in patterns:
        if pat.search(text):
            score += 0.25
    return min(1.0, score)


_VALID_INTENTS: frozenset[str] = frozenset(
    [
        "information_request", "coding", "navigation", "social",
        "reasoning", "general_chat", "dangerous_or_medical", "ambiguous",
    ]
)


def _coerce_intent(value: object) -> Intent:
    v = str(value).strip().lower()
    return v if v in _VALID_INTENTS else "ambiguous"  # type: ignore[return-value]


def _coerce_complexity(value: object) -> Complexity:
    v = str(value).strip().lower()
    return v if v in ("simple", "medium", "complex") else "simple"  # type: ignore[return-value]


def _coerce_safety(value: object) -> Safety:
    v = str(value).strip().lower()
    return v if v in ("safe", "dangerous_or_medical", "ambiguous") else "safe"  # type: ignore[return-value]
