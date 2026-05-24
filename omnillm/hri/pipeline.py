"""HRI interaction pipeline — straight-line async function (no LangGraph).

Replaces the previous ``agent_graph.py`` with a single ``process_interaction``
coroutine that runs:

    detect language → classify task → (RAG | direct | multilingual | council)
      → plan gesture → return RobotAction dict (and optionally log it)

No state-merge wrapper, no conditional graph edges, no per-condition
overrides. One path. Simple to read, easy to debug.

──────────────────────────────────────────────────────────────────────
BEGINNER ORIENTATION
──────────────────────────────────────────────────────────────────────
This is the BRAIN of OmniLLM. Every user utterance flows through the
``process_interaction`` function below. It is ~180 lines long and reads
top-to-bottom like a recipe.

Cross-reference: OMNILLM_MASTER_BOOK.md Part 2 §2.3 ("Single-Process
Data Flow") and §2.11 ("Multilingual Walkthrough") explain this file at
a higher level. Read those sections first if anything below is unclear.
──────────────────────────────────────────────────────────────────────
"""

# `from __future__ import annotations` lets us use modern type hints
# (like ``RAGPipeline | None``) on Python 3.9+. Safe to include in every file.
from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

# Three helpers used at runtime. Each is a tiny class that does one job.
# See the docstrings of each module for details.
from omnillm.hri.classifier import HRITaskClassifier
from omnillm.hri.language_detector import LanguageDetector
from omnillm.robotics.gesture_planner import GesturePlanner
from omnillm.router import SmartRouter, StrategyDecision
from omnillm.triage import TriageClassifier, TriageResult

# ``TYPE_CHECKING`` is False at runtime, True only when a type-checker
# (mypy/pyright) is reading the file. We import the big modules only for
# type hints so they aren't loaded when this script runs — avoids
# circular imports and keeps startup fast.
if TYPE_CHECKING:
    from omnillm.gateway import LLMGateway
    from omnillm.rag.pipeline import RAGPipeline
    from omnillm.utils.experiment_logger import ExperimentLogger


# ──────────────────────────────────────────────────────────────────────
# THE BASE SYSTEM PROMPT — sent as the "system" message to every LLM call.
# ──────────────────────────────────────────────────────────────────────
# Tells the model: who it is, where it is, and HOW to answer.
# The "1–3 sentences" constraint is CRITICAL for HRI — a wall of text
# cannot be processed by a listener in real time.
SYSTEM_PROMPT_BASE = (
    "You are Pepper, a friendly social robot in the Sgorbissa HRI lab at "
    "DIBRIS, University of Genoa. Answer warmly and concisely (1–3 sentences)."
)

# Default LLM council for the council=True branch. Three models from three
# different vendors (OpenAI / Anthropic / Google) so they bring genuinely
# diverse "perspectives", all from the cheap-and-fast tier so latency stays
# under ~2 s. For a higher-quality council swap in gpt-4o / claude-sonnet /
# gemini-2.5-pro — but expect 4–6 s latency.
COUNCIL_DEFAULT = ["openai-gpt4o-mini", "claude-haiku", "gemini-2.5-flash"]


# ──────────────────────────────────────────────────────────────────────
# MAIN ENTRY POINT — call this once per user utterance.
# ──────────────────────────────────────────────────────────────────────
# beginner: ``async def`` defines a COROUTINE — a function that can pause
# itself while waiting on slow I/O (like LLM API calls). The caller uses
# ``await process_interaction(...)`` to run it.
async def process_interaction(
    utterance: str,
    gateway: "LLMGateway",
    rag: "RAGPipeline | None" = None,
    *,
    default_model: str = "openai-gpt4o-mini",
    council: bool = False,
    strategy_override: str = "auto",
    language_hint: str | None = None,
    logger: "ExperimentLogger | None" = None,
    session_id: str = "",
    participant_id: str = "anon",
    mode: str = "",
) -> dict[str, Any]:
    """Run one user utterance through the autonomous HRI pipeline.

    The pipeline is the "LLM-OS kernel":

      detect language → triage (intent / complexity / safety) →
      autonomous strategy decision (direct | rag | council) →
      answer (with model fallback) → HRI gesture sub-classification →
      assemble RobotAction → log interaction

    Returns a RobotAction-shaped dict: ``{speech, gesture, emotion_led, metadata}``.
    The dict is JSON-serialisable and ready to send to ``PepperBridge.execute_action``.

    Args:
        utterance: User text (transcribed if mic input).
        gateway: Shared :class:`~omnillm.gateway.LLMGateway`.
        rag: Optional :class:`~omnillm.rag.pipeline.RAGPipeline` for KB grounding.
        default_model: Fallback model if YAML defaults are missing.
        council: Deprecated alias for ``strategy_override="council"``.
        strategy_override: ``"auto"`` (default — autonomous triage decides),
            or one of ``"direct"`` / ``"rag"`` / ``"council"`` to force a
            specific strategy regardless of triage output.
        language_hint: ISO 639-1 language code, e.g. from Whisper. When set,
            trusted over the text-based detector.
        logger: Optional :class:`~omnillm.utils.experiment_logger.ExperimentLogger`.
        session_id: Experiment session UUID (for logging).
        participant_id: Participant label (for logging).
    """
    # ``time.monotonic`` is a clock that never jumps backwards (unlike
    # ``time.time``, which NTP can move). Perfect for measuring elapsed time.
    t0 = time.monotonic()

    # Backwards compat: the legacy ``council=True`` flag wins over override
    # only if override is "auto". Explicit override always wins.
    if strategy_override == "auto" and council:
        strategy_override = "council"

    # STEP 1 — DETECT LANGUAGE (Whisper hint trusted on short transcripts).
    lang = language_hint or LanguageDetector().detect(utterance).language_code

    # STEP 2 — TRIAGE (autonomous Layer 1: intent / complexity / safety).
    # Always runs. Rule pass is ~0 ms; LLM escalation only on ambiguous
    # English prompts and only when safety is "safe".
    triage = await TriageClassifier(gateway).triage(utterance, language=lang)

    # STEP 2b — STRATEGY DECISION (autonomous Layer 1.5).
    # Either honour the explicit override or ask the router.
    if strategy_override != "auto":
        decision = _override_decision(strategy_override, gateway, default_model)
    elif lang != "en":
        # Multilingual gets its own dedicated path — it's a presentation
        # concern (language) more than a strategy concern. Keep the
        # battle-tested multilingual branch.
        decision = StrategyDecision(
            strategy="direct",
            primary_model="",  # handled inside _answer_multilingual
            fallback_chain=[],
            reason=f"language={lang} → multilingual path",
        )
    else:
        decision = SmartRouter().route_autonomous(
            triage, rag_available=rag is not None
        )

    # STEP 3 — ANSWER (exactly one branch runs).
    # `agreement_score` is only meaningful for the council branch; for direct/
    # rag/multilingual it stays None and is logged as null in the JSONL.
    agreement_score: float | None = None
    if lang != "en" and strategy_override == "auto":
        # Multilingual branch (kept for parity with the previous pipeline).
        text, model_id = await _answer_multilingual(gateway, utterance, lang_code=lang)
        fallback_count = 0
    elif decision.strategy == "council":
        text, model_id, agreement_score = await _answer_council(
            gateway, utterance, rag,
            safety_aware=(triage.safety != "safe"),
        )
        fallback_count = 0
    elif decision.strategy == "rag" and rag is not None:
        text, model_id = await _answer_with_rag(rag, utterance, decision.primary_model)
        fallback_count = 0
    else:
        text, model_id, fallback_count = await _answer_direct_with_fallback(
            gateway, utterance, decision.fallback_chain or [decision.primary_model or default_model],
        )

    # STEP 3.5 — HRI SUB-CLASSIFY for gesture + LED (presentation layer).
    # This is the ONLY remaining job of the legacy HRITaskClassifier — it
    # tells the GesturePlanner which gesture/LED to use. The strategy
    # decision was already made above.
    hri_task = HRITaskClassifier().classify(
        utterance, detected_language=lang
    ).task_type.value
    gesture, led = GesturePlanner().plan(hri_task, text)
    latency_ms = (time.monotonic() - t0) * 1000

    # STEP 4 — ASSEMBLE THE RobotAction DICT.
    rag_used = decision.strategy == "rag" and rag is not None
    action: dict[str, Any] = {
        "speech": text,
        "gesture": gesture,
        "emotion_led": led,
        "metadata": {
            "task_type": hri_task,
            "language": lang,
            "model_id": model_id,
            "latency_ms": round(latency_ms, 1),
            "council": decision.strategy == "council",
            "rag_used": rag_used,
            # Autonomous triage + strategy fields (LLM-OS kernel additions).
            "triage": {
                "intent": triage.intent,
                "complexity": triage.complexity,
                "safety": triage.safety,
                "confidence": triage.confidence,
                "method": triage.method,
            },
            "strategy": decision.strategy,
            "strategy_reason": decision.reason,
            "fallback_attempts": fallback_count,
            # Council diagnostic — None for non-council strategies.
            "agreement_score": agreement_score,
        },
    }

    # STEP 5 — LOG THE INTERACTION (best-effort; never breaks the response).
    if logger is not None:
        try:
            logger.log_interaction(
                session_id=session_id,
                participant_id=participant_id,
                task_type=hri_task,
                utterance=utterance,
                response=text,
                model_id=model_id,
                mode=mode,
                latency_ms=latency_ms,
                rag_enabled=rag_used,
                language=lang,
                gesture_used=gesture,
                triage_intent=triage.intent,
                triage_complexity=triage.complexity,
                triage_safety=triage.safety,
                triage_method=triage.method,
                strategy_used=decision.strategy,
                strategy_reason=decision.reason,
                fallback_attempts=fallback_count,
                agreement_score=agreement_score,
            )
        except Exception:
            pass  # logging is best-effort, never breaks the response

    return action


def _override_decision(
    strategy_override: str, gateway: "LLMGateway", default_model: str
) -> StrategyDecision:
    """Build a StrategyDecision from a forced override string.

    Reads the same autonomous_defaults from models.yaml as the router so
    forced direct/rag still pick a sensible primary model.
    """
    defaults = gateway._config.get("routing", {}).get("autonomous_defaults", {})
    primary = defaults.get("simple_model", default_model)
    chain = [primary, *[m for m in defaults.get("simple_fallback", []) if m != primary]]
    return StrategyDecision(
        strategy=strategy_override,  # type: ignore[arg-type]
        primary_model=primary if strategy_override != "council" else "",
        fallback_chain=chain if strategy_override != "council" else [],
        reason=f"strategy_override='{strategy_override}' (manual)",
    )


# ──────────────────────────────────────────────────────────────────────
# THE FOUR INTERNAL ANSWER STRATEGIES.
# Each returns a tuple of (response_text, model_id_used).
# ──────────────────────────────────────────────────────────────────────
# ── Internal answer strategies ────────────────────────────────────────────────

async def _answer_direct(
    gateway: "LLMGateway", utterance: str, model_id: str
) -> tuple[str, str]:
    # DIRECT (single model, no fallback) — kept for callers that want the
    # original behaviour. New code should use _answer_direct_with_fallback.
    resp = await gateway.query(
        model_id,
        [
            {"role": "system", "content": SYSTEM_PROMPT_BASE},
            {"role": "user", "content": utterance},
        ],
        temperature=0.7,
    )
    if resp.is_error:
        return f"Sorry, I couldn't answer ({resp.error}).", model_id
    return resp.content, resp.model_id or model_id


async def _answer_direct_with_fallback(
    gateway: "LLMGateway", utterance: str, model_chain: list[str]
) -> tuple[str, str, int]:
    """DIRECT with provider fallback — Karpathy/Sutskever robustness leg.

    Tries each model in the chain in order; first non-error wins. Returns
    ``(text, model_id, fallback_attempts)`` so the pipeline can record
    whether fallback fired.
    """
    if not model_chain:
        return "Sorry, no model is available right now.", "(empty)", 0

    resp = await gateway.query_with_fallback(
        model_chain,
        [
            {"role": "system", "content": SYSTEM_PROMPT_BASE},
            {"role": "user", "content": utterance},
        ],
        temperature=0.7,
    )
    fallback_count = len(resp.metadata.get("fallback_attempts", []))
    if resp.is_error:
        return f"Sorry, I couldn't answer ({resp.error}).", resp.model_id, fallback_count
    return resp.content, resp.model_id, fallback_count


async def _answer_with_rag(
    rag: "RAGPipeline", utterance: str, model_id: str
) -> tuple[str, str]:
    # RAG: retrieve KB chunks, then ask the LLM with those chunks as context.
    # The "answer ONLY from context" instruction lives inside ``rag.query`` —
    # see rag/pipeline.py for the prompt.
    rag_resp = await rag.query(utterance, model_id=model_id)
    # Empty answer = retrieval found nothing useful. Polite refusal beats silence.
    if not rag_resp.answer:
        return "I don't have information about that yet.", rag_resp.model_id or model_id
    return rag_resp.answer, rag_resp.model_id or model_id


async def _answer_multilingual(
    gateway: "LLMGateway", utterance: str, lang_code: str
) -> tuple[str, str]:
    # MULTILINGUAL: route to the language-optimal model and add a "respond
    # in <language>" instruction to the system prompt.
    # Local imports keep the language-detector internals out of the global
    # namespace and avoid circular imports.
    from omnillm.hri.language_detector import (
        _LANGUAGE_MODEL_MAP, _LANGUAGE_NAME_MAP,
    )
    language_name = _LANGUAGE_NAME_MAP.get(lang_code, lang_code.upper())
    target = _LANGUAGE_MODEL_MAP.get(lang_code, _LANGUAGE_MODEL_MAP["unknown"])
    # The system prompt itself stays in English — LLMs follow English
    # instructions more reliably than translated ones, even when the
    # response must be in another language.
    system_prompt = (
        f"{SYSTEM_PROMPT_BASE} The user is speaking {language_name}. "
        f"Respond in {language_name}."
    )
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": utterance},
    ]
    # Try language-optimal model; fall back to gpt-4o-mini if it errors.
    # This loop prevents the old "silent collapse to English" bug where a
    # Haiku error returned an English error message that got labelled as
    # a multilingual response.
    for candidate in (target, "openai-gpt4o-mini"):
        resp = await gateway.query(candidate, messages, temperature=0.7)
        if not resp.is_error and resp.content:
            return resp.content, resp.model_id or candidate
    # Both attempts failed. Italian refusal because Italian is the most
    # likely non-English language at DIBRIS — better than an English error.
    return "Mi dispiace, non riesco a rispondere ora.", target


async def _answer_council(
    gateway: "LLMGateway",
    utterance: str,
    rag: "RAGPipeline | None",
    safety_aware: bool = False,
) -> tuple[str, str, float]:
    # COUNCIL: three LLMs answer concurrently, a judge LLM synthesises the
    # best combined response. See omnillm/consensus.py for the engine and
    # OMNILLM_MASTER_BOOK.md §3.4.4 for the synthesis prompt verbatim.
    #
    # ``safety_aware=True`` passes a refusal-allowing instruction to the
    # judge — used when the triage classifier flagged the prompt as
    # dangerous/medical.
    from omnillm.consensus import ConsensusConfig, ConsensusEngine

    # Filter the default council down to models the gateway actually knows
    # about (some require API keys the user might not have set).
    available = [m for m in COUNCIL_DEFAULT if m in gateway.list_models()]
    if not available:
        available = gateway.list_models()[:3]

    # If RAG is available AND this isn't a safety-flagged prompt, pre-fetch
    # chunks ONCE and pass them as context to all three council members.
    # Skip RAG for dangerous prompts — KB facts about lab hours don't help
    # the judge decide whether to refuse a medical question.
    context = ""
    if rag is not None and not safety_aware:
        chunks = rag.retrieve(utterance)
        if chunks:
            context = "\n\n".join(f"[{c.source}]: {c.text}" for c in chunks)

    user_msg = f"Context:\n{context}\n\nQuestion: {utterance}" if context else utterance
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT_BASE},
        {"role": "user", "content": user_msg},
    ]
    engine = ConsensusEngine(gateway, ConsensusConfig(council_models=available))
    council_resp = await engine.query_council(messages, safety_aware=safety_aware)
    # The model_id string makes it obvious in the log that this was a
    # council answer (e.g. "council:openai-gpt4o-mini+claude-haiku+gemini-2.5-flash").
    prefix = "council-safe:" if safety_aware else "council:"
    # Returning agreement_score as the 3rd tuple element threads the council's
    # diagnostic signal up to the metadata + JSONL log — the Part 7 Embodied
    # Veracity follow-up consumes it. None branches default agreement_score=None.
    return council_resp.final_answer, prefix + "+".join(available), council_resp.agreement_score
