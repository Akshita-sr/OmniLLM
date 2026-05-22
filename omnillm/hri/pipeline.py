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
    language_hint: str | None = None,
    logger: "ExperimentLogger | None" = None,
    session_id: str = "",
    participant_id: str = "anon",
) -> dict[str, Any]:
    """Run one user utterance through the HRI pipeline.

    Returns a RobotAction-shaped dict: ``{speech, gesture, emotion_led, metadata}``.
    The dict is JSON-serialisable and ready to send to ``PepperBridge.execute_action``.

    ``language_hint`` (e.g. from Whisper) is trusted over the text-based detector
    when present — Whisper hears the audio and is more reliable than n-gram
    matching on short transcripts.
    """
    # ``time.monotonic`` is a clock that never jumps backwards (unlike
    # ``time.time``, which NTP can move). Perfect for measuring elapsed time.
    t0 = time.monotonic()

    # STEP 1 — DETECT LANGUAGE.
    # If Whisper gave us a hint, trust it (Whisper hears the actual audio
    # and is more reliable on short transcripts than our n-gram detector).
    lang = language_hint or LanguageDetector().detect(utterance).language_code

    # STEP 2 — CLASSIFY THE TASK TYPE.
    # Returns one of: info_retrieval / navigation / social_conversation / multilingual.
    # If ``lang != "en"`` the classifier short-circuits to "multilingual".
    task = HRITaskClassifier().classify(
        utterance, detected_language=lang
    ).task_type.value

    # STEP 3 — ROUTE TO THE RIGHT ANSWER STRATEGY (exactly one branch runs).
    if council:
        # Council mode overrides everything: 3 LLMs answer in parallel,
        # a judge LLM synthesises the best combined answer.
        text, model_id = await _answer_council(gateway, utterance, rag)
    elif task == "multilingual":
        # Non-English → language-optimal model + "respond in <language>" prompt.
        text, model_id = await _answer_multilingual(gateway, utterance, lang_code=lang)
    elif task in ("info_retrieval", "navigation") and rag is not None:
        # Factual or spatial + RAG available → retrieve KB chunks and answer
        # ONLY from them. See rag/pipeline.py.
        text, model_id = await _answer_with_rag(rag, utterance, default_model)
    else:
        # Default fallthrough: social chat OR RAG disabled. Ask the routed
        # model directly with no grounding.
        text, model_id = await _answer_direct(gateway, utterance, default_model)

    # STEP 4 — PLAN A GESTURE + LED COLOUR.
    # The gesture planner is rule-based: it looks at the task type and the
    # response text and returns ``(gesture_name, hex_led_colour)``.
    gesture, led = GesturePlanner().plan(task, text)
    latency_ms = (time.monotonic() - t0) * 1000

    # STEP 5 — ASSEMBLE THE RobotAction DICT.
    # This shape is the contract with naoqi_bridge_server.py. Don't add
    # fields here without also updating the bridge to handle them.
    action: dict[str, Any] = {
        "speech": text,
        "gesture": gesture,
        "emotion_led": led,
        "metadata": {
            "task_type": task,
            "language": lang,
            "model_id": model_id,
            "latency_ms": round(latency_ms, 1),
            "council": council,
            # ``rag_used`` is True only when RAG actually fired. Council
            # has its own context-stuffing logic so we report it separately.
            "rag_used": task in ("info_retrieval", "navigation") and rag is not None and not council,
        },
    }

    # STEP 6 — LOG THE INTERACTION (best-effort; never breaks the response).
    # Wrapped in try/except so a logging bug never breaks the user-facing
    # response. The participant must never see an error because the logger
    # crashed — that would invalidate the HRI experiment data.
    if logger is not None:
        try:
            logger.log_interaction(
                session_id=session_id,
                participant_id=participant_id,
                condition="default",
                task_type=task,
                utterance=utterance,
                response=text,
                model_id=model_id,
                latency_ms=latency_ms,
                rag_enabled=action["metadata"]["rag_used"],
                language=lang,
                gesture_used=gesture,
            )
        except Exception:
            pass  # logging is best-effort, never breaks the response

    return action


# ──────────────────────────────────────────────────────────────────────
# THE FOUR INTERNAL ANSWER STRATEGIES.
# Each returns a tuple of (response_text, model_id_used).
# ──────────────────────────────────────────────────────────────────────
# ── Internal answer strategies ────────────────────────────────────────────────

async def _answer_direct(
    gateway: "LLMGateway", utterance: str, model_id: str
) -> tuple[str, str]:
    # DIRECT: ask one LLM, no retrieval, no consensus.
    # beginner: ``temperature=0.7`` is a creativity knob (0.0 = deterministic,
    # 1.0 = most creative). 0.7 is the conventional default for chat.
    resp = await gateway.query(
        model_id,
        [
            {"role": "system", "content": SYSTEM_PROMPT_BASE},
            {"role": "user", "content": utterance},
        ],
        temperature=0.7,
    )
    # On API failure, return a graceful apology — the robot still gets to
    # speak rather than crashing the whole pipeline.
    if resp.is_error:
        return f"Sorry, I couldn't answer ({resp.error}).", model_id
    return resp.content, resp.model_id or model_id


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
    gateway: "LLMGateway", utterance: str, rag: "RAGPipeline | None"
) -> tuple[str, str]:
    # COUNCIL: three LLMs answer concurrently, a judge LLM synthesises the
    # best combined response. See omnillm/consensus.py for the engine and
    # OMNILLM_MASTER_BOOK.md §3.4.4 for the synthesis prompt verbatim.
    from omnillm.consensus import ConsensusConfig, ConsensusEngine

    # Filter the default council down to models the gateway actually knows
    # about (some require API keys the user might not have set).
    available = [m for m in COUNCIL_DEFAULT if m in gateway.list_models()]
    if not available:
        available = gateway.list_models()[:3]

    # If RAG is available, pre-fetch chunks ONCE and pass them as context
    # to all three council members. More efficient than letting each model
    # call RAG independently, and ensures all three see the same facts.
    context = ""
    if rag is not None:
        chunks = rag.retrieve(utterance)
        if chunks:
            context = "\n\n".join(f"[{c.source}]: {c.text}" for c in chunks)

    user_msg = f"Context:\n{context}\n\nQuestion: {utterance}" if context else utterance
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT_BASE},
        {"role": "user", "content": user_msg},
    ]
    engine = ConsensusEngine(gateway, ConsensusConfig(council_models=available))
    council_resp = await engine.query_council(messages)
    # The model_id string makes it obvious in the log that this was a
    # council answer (e.g. "council:openai-gpt4o-mini+claude-haiku+gemini-2.5-flash").
    return council_resp.final_answer, "council:" + "+".join(available)
