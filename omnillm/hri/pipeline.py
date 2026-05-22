"""HRI interaction pipeline — straight-line async function (no LangGraph).

Replaces the previous ``agent_graph.py`` with a single ``process_interaction``
coroutine that runs:

    detect language → classify task → (RAG | direct | multilingual | council)
      → plan gesture → return RobotAction dict (and optionally log it)

No state-merge wrapper, no conditional graph edges, no per-condition
overrides. One path. Simple to read, easy to debug.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

from omnillm.hri.classifier import HRITaskClassifier
from omnillm.hri.language_detector import LanguageDetector
from omnillm.robotics.gesture_planner import GesturePlanner

if TYPE_CHECKING:
    from omnillm.gateway import LLMGateway
    from omnillm.rag.pipeline import RAGPipeline
    from omnillm.utils.experiment_logger import ExperimentLogger


SYSTEM_PROMPT_BASE = (
    "You are Pepper, a friendly social robot in the Sgorbissa HRI lab at "
    "DIBRIS, University of Genoa. Answer warmly and concisely (1–3 sentences)."
)

COUNCIL_DEFAULT = ["openai-gpt4o-mini", "claude-haiku", "gemini-2.5-flash"]


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
    t0 = time.monotonic()

    lang = language_hint or LanguageDetector().detect(utterance).language_code
    task = HRITaskClassifier().classify(
        utterance, detected_language=lang
    ).task_type.value

    if council:
        text, model_id = await _answer_council(gateway, utterance, rag)
    elif task == "multilingual":
        text, model_id = await _answer_multilingual(gateway, utterance, lang_code=lang)
    elif task in ("info_retrieval", "navigation") and rag is not None:
        text, model_id = await _answer_with_rag(rag, utterance, default_model)
    else:
        text, model_id = await _answer_direct(gateway, utterance, default_model)

    gesture, led = GesturePlanner().plan(task, text)
    latency_ms = (time.monotonic() - t0) * 1000

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
            "rag_used": task in ("info_retrieval", "navigation") and rag is not None and not council,
        },
    }

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


# ── Internal answer strategies ────────────────────────────────────────────────

async def _answer_direct(
    gateway: "LLMGateway", utterance: str, model_id: str
) -> tuple[str, str]:
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


async def _answer_with_rag(
    rag: "RAGPipeline", utterance: str, model_id: str
) -> tuple[str, str]:
    rag_resp = await rag.query(utterance, model_id=model_id)
    if not rag_resp.answer:
        return "I don't have information about that yet.", rag_resp.model_id or model_id
    return rag_resp.answer, rag_resp.model_id or model_id


async def _answer_multilingual(
    gateway: "LLMGateway", utterance: str, lang_code: str
) -> tuple[str, str]:
    from omnillm.hri.language_detector import (
        _LANGUAGE_MODEL_MAP, _LANGUAGE_NAME_MAP,
    )
    language_name = _LANGUAGE_NAME_MAP.get(lang_code, lang_code.upper())
    target = _LANGUAGE_MODEL_MAP.get(lang_code, _LANGUAGE_MODEL_MAP["unknown"])
    system_prompt = (
        f"{SYSTEM_PROMPT_BASE} The user is speaking {language_name}. "
        f"Respond in {language_name}."
    )
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": utterance},
    ]
    # Try language-optimal model; fall back to gpt-4o-mini if it errors.
    for candidate in (target, "openai-gpt4o-mini"):
        resp = await gateway.query(candidate, messages, temperature=0.7)
        if not resp.is_error and resp.content:
            return resp.content, resp.model_id or candidate
    return "Mi dispiace, non riesco a rispondere ora.", target


async def _answer_council(
    gateway: "LLMGateway", utterance: str, rag: "RAGPipeline | None"
) -> tuple[str, str]:
    from omnillm.consensus import ConsensusConfig, ConsensusEngine

    available = [m for m in COUNCIL_DEFAULT if m in gateway.list_models()]
    if not available:
        available = gateway.list_models()[:3]

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
    return council_resp.final_answer, "council:" + "+".join(available)
