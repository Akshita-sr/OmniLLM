"""LangGraph Agent Pipeline for the Embodied LLM Arena.

Implements the full multi-node agent graph described in the system architecture:

    [START]
      → Transcribe Audio (Whisper)
      → Detect Language
      → Classify Task Type (T1–T4)
      → Conditional Routing
            ├─ T1 Info Retrieval  → RAG Pipeline → OmniLLM Router
            ├─ T2 Navigation      → RAG + Gesture Planner → OmniLLM Router
            ├─ T3 Social Chat     → Direct LLM
            └─ T4 Multilingual    → Language-Optimal LLM
      → Generate Robot Action Plan
      → Log Everything (for evaluation)
      → [END] HTTP Response to Pepper

The graph is built with **LangGraph** (``langgraph`` package).  If LangGraph is
not installed, the module raises :class:`ImportError` with a clear message
pointing to the ``[hri]`` install extra.

Architecture reference:
    Problem statement — System Architecture Diagram (AI Server section)

Usage::

    from omnillm.hri.agent_graph import build_hri_graph, HRIGraphState
    from omnillm.gateway import LLMGateway
    from omnillm.rag import RAGPipeline

    gateway = LLMGateway()
    rag = RAGPipeline(gateway=gateway)
    graph = build_hri_graph(gateway=gateway, rag=rag)

    result = await graph.ainvoke({
        "audio_bytes": b"...",           # WAV bytes from Pepper
        "participant_id": "P001",
        "session_id": "s-abc-123",
        "condition": "C",
        "rag_enabled": True,
    })
    print(result["robot_action"])   # RobotAction JSON dict
    print(result["response_text"])  # Text Pepper will speak
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    from omnillm.gateway import LLMGateway
    from omnillm.rag.pipeline import RAGPipeline
    from omnillm.utils.experiment_logger import ExperimentLogger


# ── State definition ──────────────────────────────────────────────────────────

@dataclass
class HRIGraphState:
    """Shared state that flows through every node in the HRI agent graph.

    Fields are progressively populated as the graph executes.

    Attributes:
        audio_bytes: Raw WAV bytes captured from Pepper's microphone.
        participant_id: Experiment participant label (e.g. ``"P001"``).
        session_id: UUID of the :class:`~omnillm.hri.experiment.ParticipantSession`.
        condition: Experimental condition (``"A"``–``"E"``).
        rag_enabled: Whether RAG retrieval is active for this interaction.
        utterance: Transcribed text from Whisper STT.
        detected_language: ISO 639-1 language code (e.g. ``"en"``, ``"fr"``).
        task_type: Classified task type (``"info_retrieval"``, ``"navigation"``, etc.).
        task_confidence: Classifier confidence (0–1).
        rag_context: Retrieved document chunks as a formatted string.
        rag_chunks: Raw list of retrieved :class:`~omnillm.rag.pipeline.DocumentChunk`.
        rag_faithfulness: RAG faithfulness score (-1.0 = not scored).
        model_id: LLM model ID used for the final response.
        response_text: LLM-generated response text.
        gesture: Pepper gesture name (e.g. ``"point_left"``).
        led_color: Pepper LED colour (hex).
        robot_action: Final :class:`~omnillm.robotics.bridge.RobotAction` as a dict.
        judge_score: LLM-as-judge quality score (-1.0 = not scored).
        latency_ms: End-to-end latency in milliseconds.
        input_tokens: LLM input token count.
        output_tokens: LLM output token count.
        cost_usd: Estimated cost for this interaction.
        error: Error message if any node failed.
        _start_time: Internal wall-clock start time (set by the transcription node).
    """

    audio_bytes: bytes = b""
    participant_id: str = ""
    session_id: str = ""
    condition: str = "A"
    rag_enabled: bool = True

    utterance: str = ""
    detected_language: str = "en"
    task_type: str = "info_retrieval"
    task_confidence: float = 0.0

    rag_context: str = ""
    rag_chunks: list[Any] = field(default_factory=list)
    rag_faithfulness: float = -1.0

    model_id: str = ""
    response_text: str = ""
    gesture: str | None = None
    led_color: str | None = None
    robot_action: dict[str, Any] = field(default_factory=dict)

    judge_score: float = -1.0
    latency_ms: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0

    error: str | None = None
    _start_time: float = field(default_factory=time.monotonic)


# ── Node functions ────────────────────────────────────────────────────────────

def _make_transcribe_node(gateway: "LLMGateway"):
    """Create the Transcribe Audio node.

    Uses :class:`~omnillm.robotics.whisper_stt.WhisperSTT` when the
    ``audio_bytes`` field is populated.  If audio is empty (text-only mode),
    the utterance field is passed through unchanged.
    """
    async def transcribe_audio(state: dict[str, Any]) -> dict[str, Any]:
        audio = state.get("audio_bytes", b"")
        if not audio:
            # Text-only mode — utterance already set by caller
            return {"_start_time": time.monotonic()}

        try:
            from omnillm.robotics.whisper_stt import WhisperSTT
            stt = WhisperSTT()
            utterance = await stt.transcribe(audio)
            return {"utterance": utterance, "_start_time": time.monotonic()}
        except Exception as exc:
            return {"error": f"Transcription failed: {exc}", "_start_time": time.monotonic()}

    return transcribe_audio


def _make_detect_language_node():
    """Create the Detect Language node."""
    async def detect_language(state: dict[str, Any]) -> dict[str, Any]:
        utterance = state.get("utterance", "")
        if not utterance:
            return {}

        try:
            from omnillm.hri.language_detector import LanguageDetector
            detector = LanguageDetector()
            result = detector.detect(utterance)
            return {"detected_language": result.language_code}
        except Exception:
            return {"detected_language": "en"}

    return detect_language


def _make_classify_task_node():
    """Create the Classify Task Type node (T1–T4)."""
    async def classify_task(state: dict[str, Any]) -> dict[str, Any]:
        utterance = state.get("utterance", "")
        language = state.get("detected_language", "en")

        from omnillm.hri.classifier import HRITaskClassifier
        classifier = HRITaskClassifier()
        result = classifier.classify(utterance, detected_language=language)

        return {
            "task_type": result.task_type.value,
            "task_confidence": result.confidence,
        }

    return classify_task


def _make_rag_node(rag: "RAGPipeline"):
    """Create the RAG Pipeline node (T1 — Info Retrieval).

    Honours ``state["model_id"]`` when set so per-condition routing (e.g.
    Condition B → ``llama3-8b-local``) actually drives the LLM used for the
    grounded answer, not just the gateway-default cloud model.
    """
    async def run_rag(state: dict[str, Any]) -> dict[str, Any]:
        utterance = state.get("utterance", "")
        target_model = state.get("model_id") or None

        try:
            rag_resp = await rag.query(utterance, model_id=target_model)
            chunks_text = "\n\n".join(
                f"[{c.source}]: {c.text}" for c in rag_resp.retrieved_chunks
            )
            return {
                "rag_context": chunks_text,
                "rag_chunks": rag_resp.retrieved_chunks,
                "rag_faithfulness": rag_resp.faithfulness_score,
                "response_text": rag_resp.answer,
                "model_id": rag_resp.model_id,
                "latency_ms": rag_resp.latency_ms,
            }
        except Exception as exc:
            return {"error": f"RAG failed: {exc}"}

    return run_rag


def _make_nav_rag_node(rag: "RAGPipeline"):
    """Create the Navigation + Gesture Planner node (T2 — Navigation).

    Same per-condition model override as :func:`_make_rag_node`.
    """
    async def run_nav_rag(state: dict[str, Any]) -> dict[str, Any]:
        utterance = state.get("utterance", "")
        target_model = state.get("model_id") or None

        try:
            rag_resp = await rag.query(utterance, model_id=target_model)
            chunks_text = "\n\n".join(
                f"[{c.source}]: {c.text}" for c in rag_resp.retrieved_chunks
            )

            from omnillm.robotics.gesture_planner import GesturePlanner
            planner = GesturePlanner()
            gesture, led = planner.plan("navigation", rag_resp.answer)

            return {
                "rag_context": chunks_text,
                "rag_chunks": rag_resp.retrieved_chunks,
                "rag_faithfulness": rag_resp.faithfulness_score,
                "response_text": rag_resp.answer,
                "model_id": rag_resp.model_id,
                "latency_ms": rag_resp.latency_ms,
                "gesture": gesture,
                "led_color": led,
            }
        except Exception as exc:
            return {"error": f"Navigation RAG failed: {exc}"}

    return run_nav_rag


def _make_direct_llm_node(gateway: "LLMGateway", model_id: str):
    """Create the Direct LLM node (T3 — Social Conversation)."""
    async def direct_llm(state: dict[str, Any]) -> dict[str, Any]:
        utterance = state.get("utterance", "")
        target_model = state.get("model_id") or model_id

        system_prompt = (
            "You are Pepper, a friendly social robot in the Sgorbissa HRI lab "
            "at DIBRIS, University of Genoa. "
            "Respond warmly, naturally, and concisely (1–3 sentences). "
            "You are helpful, curious, and slightly playful."
        )
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": utterance},
        ]

        try:
            resp = await gateway.query(target_model, messages, temperature=0.8)
            if resp.is_error:
                return {"error": resp.error}

            from omnillm.robotics.gesture_planner import GesturePlanner
            planner = GesturePlanner()
            gesture, led = planner.plan("social_conversation", resp.content)

            return {
                "response_text": resp.content,
                "model_id": resp.model_id,
                "input_tokens": resp.input_tokens,
                "output_tokens": resp.output_tokens,
                "cost_usd": resp.cost_usd,
                "latency_ms": resp.latency_ms,
                "gesture": gesture,
                "led_color": led,
            }
        except Exception as exc:
            return {"error": f"Direct LLM failed: {exc}"}

    return direct_llm


def _make_multilingual_llm_node(gateway: "LLMGateway"):
    """Create the Language-Optimal LLM node (T4 — Multilingual).

    Tries the language-optimal model first (claude-haiku for non-English).
    If that model returns an error (e.g. transient overload from the
    provider), retries once with ``openai-gpt4o-mini`` while keeping the
    multilingual system prompt, so the T4 treatment is preserved instead of
    silently degrading to the no-language fallback handler in app.py.
    """
    async def multilingual_llm(state: dict[str, Any]) -> dict[str, Any]:
        utterance = state.get("utterance", "")

        from omnillm.hri.language_detector import LanguageDetector
        detector = LanguageDetector()
        lang_result = detector.detect(utterance)
        target_model = lang_result.recommended_model or "openai-gpt4o-mini"

        system_prompt = (
            f"You are Pepper, a friendly social robot in the Sgorbissa HRI lab "
            f"at DIBRIS, University of Genoa. The user is speaking "
            f"{lang_result.language_name}. Respond in {lang_result.language_name}. "
            f"Keep your response brief and friendly (1–3 sentences)."
        )
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": utterance},
        ]

        backup_model = "openai-gpt4o-mini"
        models_tried: list[str] = []
        last_error: str | None = None
        resp = None
        for model in (target_model, backup_model):
            if model in models_tried:
                continue
            models_tried.append(model)
            try:
                resp = await gateway.query(model, messages, temperature=0.7)
            except Exception as exc:
                last_error = f"{model}: {exc}"
                resp = None
                continue
            if not resp.is_error:
                break
            last_error = f"{model}: {resp.error}"
            resp = None

        if resp is None:
            return {"error": f"Multilingual LLM failed: {last_error}"}

        from omnillm.robotics.gesture_planner import GesturePlanner
        planner = GesturePlanner()
        gesture, led = planner.plan("multilingual", resp.content)

        return {
            "response_text": resp.content,
            "model_id": resp.model_id,
            "input_tokens": resp.input_tokens,
            "output_tokens": resp.output_tokens,
            "cost_usd": resp.cost_usd,
            "latency_ms": resp.latency_ms,
            "gesture": gesture,
            "led_color": led,
        }

    return multilingual_llm


def _make_smart_router_node(gateway: "LLMGateway"):
    """Create the OmniLLM Smart Router / Council node.

    Used for conditions C (smart-routed) and D (consensus/council).
    Selects or synthesises the best model response based on task type.
    """
    async def smart_router(state: dict[str, Any]) -> dict[str, Any]:
        condition = state.get("condition", "A")
        task_type = state.get("task_type", "info_retrieval")
        utterance = state.get("utterance", "")
        rag_context = state.get("rag_context", "")
        response_text = state.get("response_text", "")

        # If already have a response from RAG/direct LLM, only route if needed
        if response_text and condition not in ("C", "D"):
            return {}

        try:
            if condition == "D":
                # Consensus mode: 3 models answer, best synthesised
                from omnillm.consensus import ConsensusEngine, ConsensusConfig
                council_models = ["openai-gpt4o-mini", "gemini-2.5-flash", "claude-haiku"]
                available = [m for m in council_models if m in gateway.list_models()]
                if not available:
                    available = gateway.list_models()[:3]
                engine = ConsensusEngine(
                    gateway=gateway,
                    config=ConsensusConfig(council_models=available),
                )

                system_prompt = (
                    "You are Pepper, a helpful social robot in the IRAI Lab. "
                    "Answer concisely (2–4 sentences). Use the context if relevant."
                )
                if rag_context:
                    user_msg = f"Context:\n{rag_context}\n\nQuestion: {utterance}"
                else:
                    user_msg = utterance

                messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_msg},
                ]
                council_resp = await engine.query_council(messages)
                return {
                    "response_text": council_resp.final_answer,
                    "model_id": "council:" + "+".join(available),
                }

            elif condition == "C":
                # Smart-routed: OmniLLM selects best model for task type
                from omnillm.router import SmartRouter
                router = SmartRouter()
                decision = router.route_for_hri_task(
                    hri_task_type=task_type,
                )
                target = decision.model_id
                system_prompt = (
                    "You are Pepper, a helpful social robot in the IRAI Lab. "
                    "Answer concisely (2–4 sentences). Use the context if relevant."
                )
                if rag_context:
                    user_msg = f"Context:\n{rag_context}\n\nQuestion: {utterance}"
                else:
                    user_msg = utterance

                messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_msg},
                ]
                resp = await gateway.query(target, messages, temperature=0.5)
                if resp.is_error:
                    return {"error": resp.error}
                return {
                    "response_text": resp.content,
                    "model_id": resp.model_id,
                    "input_tokens": resp.input_tokens,
                    "output_tokens": resp.output_tokens,
                    "cost_usd": resp.cost_usd,
                    "latency_ms": resp.latency_ms,
                }

        except Exception as exc:
            return {"error": f"Smart router failed: {exc}"}

        return {}

    return smart_router


def _make_action_plan_node():
    """Create the Generate Robot Action Plan node."""
    async def generate_action_plan(state: dict[str, Any]) -> dict[str, Any]:
        response_text = state.get("response_text", "")
        gesture = state.get("gesture")
        led_color = state.get("led_color")
        task_type = state.get("task_type", "info_retrieval")

        # If gesture not yet assigned, plan based on task type
        if gesture is None:
            from omnillm.robotics.gesture_planner import GesturePlanner
            planner = GesturePlanner()
            gesture, led_color = planner.plan(task_type, response_text)

        action = {
            "speech": response_text,
            "gesture": gesture,
            "emotion_led": led_color,
            "metadata": {
                "task_type": task_type,
                "model_id": state.get("model_id", ""),
                "rag_enabled": state.get("rag_enabled", True),
            },
        }
        return {"robot_action": action, "gesture": gesture, "led_color": led_color}

    return generate_action_plan


def _make_log_node(logger: "ExperimentLogger | None"):
    """Create the Log Everything node."""
    async def log_interaction(state: dict[str, Any]) -> dict[str, Any]:
        if logger is None:
            return {}

        start = state.get("_start_time", time.monotonic())
        total_latency = (time.monotonic() - start) * 1000

        try:
            logger.log_interaction(
                session_id=state.get("session_id", ""),
                participant_id=state.get("participant_id", ""),
                condition=state.get("condition", "A"),
                task_type=state.get("task_type", "info_retrieval"),
                utterance=state.get("utterance", ""),
                response=state.get("response_text", ""),
                model_id=state.get("model_id", ""),
                latency_ms=total_latency,
                input_tokens=state.get("input_tokens", 0),
                output_tokens=state.get("output_tokens", 0),
                cost_usd=state.get("cost_usd", 0.0),
                rag_enabled=state.get("rag_enabled", True),
                rag_faithfulness=state.get("rag_faithfulness", -1.0),
                rag_chunk_count=len(state.get("rag_chunks", [])),
                judge_score=state.get("judge_score", -1.0),
                language=state.get("detected_language", "en"),
                gesture_used=state.get("gesture"),
            )
        except Exception:
            pass  # Logging failure should never crash the interaction

        return {"latency_ms": total_latency}

    return log_interaction


# ── Routing edge ───────────────────────────────────────────────────────────────

def _route_by_task_type(state: dict[str, Any]) -> str:
    """Determine the next node based on task type and experimental condition."""
    task_type = state.get("task_type", "info_retrieval")
    condition = state.get("condition", "A")
    rag_enabled = state.get("rag_enabled", True)

    # Condition E (RAG-Off Control) always goes to direct LLM
    if condition == "E":
        return "direct_llm"

    routing = {
        "info_retrieval": "rag" if rag_enabled else "direct_llm",
        "navigation": "nav_rag" if rag_enabled else "direct_llm",
        "social_conversation": "direct_llm",
        "multilingual": "multilingual_llm",
    }
    return routing.get(task_type, "direct_llm")


# ── Graph builder ─────────────────────────────────────────────────────────────

def build_hri_graph(
    gateway: "LLMGateway",
    rag: "RAGPipeline | None" = None,
    logger: "ExperimentLogger | None" = None,
    default_model: str = "openai-gpt4o-mini",
):
    """Build and compile the HRI LangGraph agent graph.

    Args:
        gateway: Initialised :class:`~omnillm.gateway.LLMGateway`.
        rag: Initialised :class:`~omnillm.rag.pipeline.RAGPipeline`.
            Required for T1 (info retrieval) and T2 (navigation) tasks.
            If not provided, those task types fall back to direct LLM.
        logger: Optional :class:`~omnillm.utils.experiment_logger.ExperimentLogger`
            to record all interactions.
        default_model: Fallback model ID for direct LLM and multilingual nodes.

    Returns:
        A compiled LangGraph ``CompiledGraph`` that accepts a dict matching
        :class:`HRIGraphState` fields and returns an updated state dict.

    Raises:
        ImportError: If the ``langgraph`` package is not installed.
            Install with ``pip install "omnillm[hri]"`` or
            ``pip install langgraph``.

    Example::

        graph = build_hri_graph(gateway=gateway, rag=rag, logger=logger)
        result = await graph.ainvoke({
            "utterance": "Where is Room 305?",
            "participant_id": "P001",
            "session_id": "s1",
            "condition": "C",
            "rag_enabled": True,
        })
        print(result["response_text"])
        print(result["robot_action"])
    """
    try:
        from langgraph.graph import StateGraph, END  # type: ignore[import-untyped]
    except ImportError as exc:
        raise ImportError(
            "LangGraph is required for the HRI agent graph.\n"
            'Install with: pip install "omnillm[hri]" or pip install langgraph'
        ) from exc

    # Use a plain dict as state to be compatible with LangGraph's StateGraph
    builder = StateGraph(dict)

    # In LangGraph 1.x with StateGraph(dict), each node's return REPLACES state
    # instead of merging. Wrap every node so it returns the merged state
    # ({**state, **delta}) and the original keys survive through the pipeline.
    def _merge_state(fn):
        async def wrapped(state):
            delta = await fn(state)
            if not isinstance(delta, dict):
                return state
            return {**state, **delta}
        return wrapped

    # Create a minimal RAG pipeline for fallback if none provided
    _rag = rag

    # ── Add nodes ──────────────────────────────────────────────────────────────
    builder.add_node("transcribe_audio", _merge_state(_make_transcribe_node(gateway)))
    builder.add_node("detect_language", _merge_state(_make_detect_language_node()))
    builder.add_node("classify_task", _merge_state(_make_classify_task_node()))

    if _rag is not None:
        builder.add_node("rag", _merge_state(_make_rag_node(_rag)))
        builder.add_node("nav_rag", _merge_state(_make_nav_rag_node(_rag)))
    else:
        # If no RAG provided, both rag/nav_rag fall back to direct LLM
        builder.add_node("rag", _merge_state(_make_direct_llm_node(gateway, default_model)))
        builder.add_node("nav_rag", _merge_state(_make_direct_llm_node(gateway, default_model)))

    builder.add_node("direct_llm", _merge_state(_make_direct_llm_node(gateway, default_model)))
    builder.add_node("multilingual_llm", _merge_state(_make_multilingual_llm_node(gateway)))
    builder.add_node("smart_router", _merge_state(_make_smart_router_node(gateway)))
    builder.add_node("generate_action_plan", _merge_state(_make_action_plan_node()))
    builder.add_node("log_interaction", _merge_state(_make_log_node(logger)))

    # ── Add edges ──────────────────────────────────────────────────────────────
    builder.set_entry_point("transcribe_audio")
    builder.add_edge("transcribe_audio", "detect_language")
    builder.add_edge("detect_language", "classify_task")

    # Conditional routing based on task type
    builder.add_conditional_edges(
        "classify_task",
        _route_by_task_type,
        {
            "rag": "rag",
            "nav_rag": "nav_rag",
            "direct_llm": "direct_llm",
            "multilingual_llm": "multilingual_llm",
        },
    )

    # All task branches converge at the smart router
    builder.add_edge("rag", "smart_router")
    builder.add_edge("nav_rag", "smart_router")
    builder.add_edge("direct_llm", "smart_router")
    builder.add_edge("multilingual_llm", "smart_router")

    builder.add_edge("smart_router", "generate_action_plan")
    builder.add_edge("generate_action_plan", "log_interaction")
    builder.add_edge("log_interaction", END)

    return builder.compile()
