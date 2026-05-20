"""OmniLLM AI Server — Flask HTTP bridge for Pepper robot.

This Flask application is the Python 3.x AI server that bridges the NAOqi
Python 2.7 process running on (or near) the Pepper robot with the modern AI
stack (LangGraph, LiteLLM, ChromaDB).

Architecture
------------

    Pepper (Python 2.7 NAOqi)
        │  POST /interact  { "audio": <base64 WAV> | "text": "..." }
        │  POST /transcribe { "audio": <base64 WAV> }
        │  GET  /health
        │  GET  /status
        ▼
    This Flask server (Python 3.x)
        │  Whisper STT → LangGraph pipeline → RobotAction JSON
        ▼
    Pepper receives: { "speech": "...", "gesture": "wave", "led": "#00FF88" }

Endpoints
---------
``POST /interact``
    Main endpoint.  Accepts either:

    - ``{"text": "Where is Room 305?", ...session fields...}`` for text-only
    - ``{"audio": "<base64-encoded WAV>", ...}`` for voice input

    Returns a ``RobotAction`` JSON dict.

``POST /transcribe``
    Transcribe-only endpoint.  Accepts ``{"audio": "<base64 WAV>"}`` and
    returns ``{"text": "transcribed text", "language": "en"}``.

``POST /evaluate``
    Submit a questionnaire response for logging.
    Accepts participant questionnaire Likert scores.

``GET /health``
    Liveness probe — returns ``{"status": "ok"}``.

``GET /status``
    Returns server version, model list, RAG status.

Usage (development)::

    python -m omnillm.server.app

Or via gunicorn for production::

    gunicorn omnillm.server.app:create_app() --bind 0.0.0.0:5000 --workers 1

Environment variables
---------------------
``OMNILLM_DEFAULT_MODEL``
    Default LLM model ID (default: ``"openai-gpt4o-mini"``).
``OMNILLM_KNOWLEDGE_BASE``
    Path to the directory containing knowledge base files
    (default: ``knowledge_base/`` relative to repo root).
``OPENAI_API_KEY``, ``ANTHROPIC_API_KEY``, ``GOOGLE_API_KEY``, etc.
    Cloud provider API keys (as in ``.env.example``).
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Lazy imports — these are only required when the server actually runs,
# keeping the module importable even without flask installed.
# ---------------------------------------------------------------------------

logger = logging.getLogger(__name__)


def create_app(
    knowledge_base_dir: str | Path | None = None,
    default_model: str | None = None,
    enable_rag: bool = True,
    log_to_file: str | None = None,
) -> "Any":
    """Create and configure the Flask application.

    Args:
        knowledge_base_dir: Path to the knowledge base directory.
            Defaults to the ``OMNILLM_KNOWLEDGE_BASE`` env var, or
            ``<repo_root>/knowledge_base/``.
        default_model: Default LLM model ID.  Defaults to
            ``OMNILLM_DEFAULT_MODEL`` env var or ``"openai-gpt4o-mini"``.
        enable_rag: Whether to load and enable the RAG pipeline.
        log_to_file: If set, interaction logs are saved to this path.

    Returns:
        Configured Flask :class:`~flask.Flask` application instance.
    """
    try:
        from flask import Flask, jsonify, request  # type: ignore[import-untyped]
    except ImportError as exc:
        raise ImportError(
            "Flask is required for the AI server.\n"
            'Install with: pip install "omnillm[robotics]"'
        ) from exc

    from omnillm.gateway import LLMGateway
    from omnillm.rag.pipeline import RAGPipeline
    from omnillm.utils.experiment_logger import ExperimentLogger

    app = Flask(__name__)
    app.config["JSON_SORT_KEYS"] = False

    # ── Configuration ─────────────────────────────────────────────────────────
    _default_model = (
        default_model
        or os.getenv("OMNILLM_DEFAULT_MODEL", "openai-gpt4o-mini")
    )
    _kb_dir = Path(
        knowledge_base_dir
        or os.getenv(
            "OMNILLM_KNOWLEDGE_BASE",
            str(Path(__file__).parent.parent.parent / "knowledge_base"),
        )
    )

    # ── Initialise components ─────────────────────────────────────────────────
    gateway = LLMGateway()
    exp_logger = ExperimentLogger()
    rag: RAGPipeline | None = None

    if enable_rag:
        rag = RAGPipeline(gateway=gateway, model_id=_default_model)
        _load_knowledge_base(rag, _kb_dir)

    # Build the LangGraph pipeline (imported lazily so tests don't need langgraph)
    _graph: Any = None

    def _get_graph() -> Any:
        nonlocal _graph
        if _graph is None:
            try:
                from omnillm.hri.agent_graph import build_hri_graph
                _graph = build_hri_graph(
                    gateway=gateway,
                    rag=rag,
                    logger=exp_logger,
                    default_model=_default_model,
                )
            except ImportError:
                logger.warning("LangGraph not installed — falling back to direct gateway.")
        return _graph

    # ── Helper: run async function from sync Flask context ────────────────────
    def _run_async(coro: Any) -> Any:
        """Run a coroutine in a new event loop (Flask is sync by default)."""
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()

    # ── Endpoints ─────────────────────────────────────────────────────────────

    @app.route("/health", methods=["GET"])
    def health() -> Any:
        """Liveness probe."""
        return jsonify({"status": "ok", "version": "0.1.0"})

    @app.route("/status", methods=["GET"])
    def status() -> Any:
        """Returns server configuration and component status."""
        return jsonify({
            "status": "ok",
            "default_model": _default_model,
            "rag_enabled": rag is not None,
            "knowledge_base": str(_kb_dir),
            "knowledge_base_exists": _kb_dir.exists(),
            "rag_uses_chromadb": rag.uses_chromadb if rag else False,
            "available_models": gateway.list_models(),
            "langgraph_available": _get_graph() is not None,
        })

    @app.route("/transcribe", methods=["POST"])
    def transcribe() -> Any:
        """Transcribe audio bytes to text using Whisper STT."""
        data: dict = request.get_json(force=True) or {}
        audio_b64: str = data.get("audio", "")

        if not audio_b64:
            return jsonify({"error": "No audio provided"}), 400

        try:
            audio_bytes = base64.b64decode(audio_b64)
        except Exception:
            return jsonify({"error": "Invalid base64 audio data"}), 400

        try:
            from omnillm.robotics.whisper_stt import WhisperSTT
            stt = WhisperSTT(backend="local", model_size="base")
            text = _run_async(stt.transcribe(audio_bytes))
        except ImportError:
            return jsonify({"error": "Whisper not installed — pip install openai-whisper"}), 500
        except Exception:
            logger.exception("Transcription failed")
            return jsonify({"error": "Transcription failed. Check server logs."}), 500

        # Detect language
        language = "en"
        if text:
            try:
                from omnillm.hri.language_detector import LanguageDetector
                lang_result = LanguageDetector().detect(text)
                language = lang_result.language_code
            except Exception:
                pass

        return jsonify({"text": text, "language": language})

    @app.route("/interact", methods=["POST"])
    def interact() -> Any:
        """Main interaction endpoint — processes voice or text and returns a RobotAction."""
        data: dict = request.get_json(force=True) or {}

        utterance: str = data.get("text", "")
        audio_b64: str = data.get("audio", "")
        participant_id: str = data.get("participant_id", "unknown")
        session_id: str = data.get("session_id", "")
        condition: str = data.get("condition", "A")
        rag_enabled: bool = bool(data.get("rag_enabled", True) and rag is not None)

        if not utterance and not audio_b64:
            return jsonify({"error": "Provide 'text' or 'audio' field"}), 400

        # Decode audio if provided
        audio_bytes = b""
        if audio_b64:
            try:
                audio_bytes = base64.b64decode(audio_b64)
            except Exception:
                return jsonify({"error": "Invalid base64 audio data"}), 400

        graph = _get_graph()

        if graph is not None and rag is not None:
            # Resolve the per-condition model BEFORE invoking the graph so
            # that Condition B (fixed local Llama) actually exercises the
            # local Ollama backend rather than silently falling through to
            # the server's default cloud model.  Smart-routed conditions
            # (C / D) keep the default here; their downstream nodes pick
            # the real model later.
            from omnillm.hri.experiment import (
                CONDITION_CONFIGS,
                ExperimentCondition,
            )
            try:
                cond_enum = ExperimentCondition(condition)
                cond_cfg = CONDITION_CONFIGS.get(cond_enum)
                effective_model = (
                    cond_cfg.model_id if cond_cfg and cond_cfg.model_id
                    else _default_model
                )
            except ValueError:
                effective_model = _default_model

            # Full LangGraph pipeline
            state: dict[str, Any] = {
                "utterance": utterance,
                "audio_bytes": audio_bytes,
                "participant_id": participant_id,
                "session_id": session_id,
                "condition": condition,
                "rag_enabled": rag_enabled,
                "model_id": effective_model,
            }
            try:
                result = _run_async(graph.ainvoke(state))
                if result.get("error"):
                    logger.error("Graph error: %s", result["error"])

                action = result.get("robot_action") or {"speech": result.get("response_text", "")}

                # If the graph produced no usable speech, fall back to direct gateway.
                if not action.get("speech"):
                    logger.warning("LangGraph returned empty speech — falling back to direct gateway.")
                else:
                    meta = dict(action.get("metadata") or {})
                    meta.setdefault("model_id", result.get("model_id") or _default_model)
                    meta.setdefault("rag_enabled", rag_enabled)
                    meta.setdefault("condition", condition)
                    action["metadata"] = meta
                    return jsonify(action)
            except Exception:
                logger.exception("Graph invocation failed — falling back to direct gateway.")

        # Fallback: direct gateway call (no LangGraph)
        return _fallback_interact(
            utterance=utterance,
            audio_bytes=audio_bytes,
            condition=condition,
            rag_enabled=rag_enabled,
            gateway=gateway,
            rag=rag,
            exp_logger=exp_logger,
            participant_id=participant_id,
            session_id=session_id,
            default_model=_default_model,
            run_async=_run_async,
        )

    @app.route("/evaluate", methods=["POST"])
    def evaluate() -> Any:
        """Submit post-interaction questionnaire data."""
        data: dict = request.get_json(force=True) or {}

        required = ["session_id", "participant_id", "condition"]
        missing = [f for f in required if f not in data]
        if missing:
            return jsonify({"error": f"Missing fields: {missing}"}), 400

        # Log questionnaire scores as a special interaction record
        try:
            exp_logger.log_interaction(
                session_id=data["session_id"],
                participant_id=data["participant_id"],
                condition=data["condition"],
                task_type="questionnaire",
                utterance="",
                response="",
                model_id="",
                notes=json.dumps(data.get("scores", {})),
            )
        except Exception:
            logger.exception("Failed to log questionnaire data")
            return jsonify({"error": "Failed to record questionnaire data. Check server logs."}), 500

    @app.route("/export", methods=["GET"])
    def export_data() -> Any:
        """Export all logged interaction data as JSON."""
        records = [
            {
                "session_id": r.session_id,
                "participant_id": r.participant_id,
                "condition": r.condition,
                "task_type": r.task_type,
                "utterance": r.utterance,
                "response": r.response,
                "model_id": r.model_id,
                "latency_ms": r.latency_ms,
                "rag_enabled": r.rag_enabled,
                "rag_faithfulness": r.rag_faithfulness,
                "judge_score": r.judge_score,
                "task_success": r.task_success,
                "language": r.language,
                "gesture_used": r.gesture_used,
                "timestamp": r.timestamp,
                "notes": r.notes,
            }
            for r in exp_logger.records
        ]
        return jsonify({"count": len(records), "records": records})

    return app


# ── Knowledge base loader ─────────────────────────────────────────────────────

def _load_knowledge_base(rag: "RAGPipeline", kb_dir: Path) -> None:
    """Index all files in the knowledge base directory into the RAG pipeline."""
    if not kb_dir.exists():
        logger.warning("Knowledge base directory not found: %s", kb_dir)
        return

    total = 0
    for path in sorted(kb_dir.iterdir()):
        if path.suffix.lower() in (".txt", ".csv", ".json"):
            try:
                text = path.read_text(encoding="utf-8")
                n = rag.index_text(text, source=path.name)
                total += n
                logger.info("Indexed %d chunks from %s", n, path.name)
            except Exception as exc:
                logger.warning("Failed to index %s: %s", path.name, exc)

    # Try indexing PDFs if LangChain/pypdf available
    for path in sorted(kb_dir.glob("*.pdf")):
        try:
            n = rag.index_file(path)
            total += n
            logger.info("Indexed %d chunks from %s", n, path.name)
        except Exception as exc:
            logger.warning("Failed to index PDF %s: %s", path.name, exc)

    logger.info("Knowledge base loaded — %d total chunks", total)


# ── Fallback interaction handler ──────────────────────────────────────────────

def _fallback_interact(
    utterance: str,
    audio_bytes: bytes,
    condition: str,
    rag_enabled: bool,
    gateway: Any,
    rag: Any,
    exp_logger: Any,
    participant_id: str,
    session_id: str,
    default_model: str,
    run_async: Any,
) -> Any:
    """Minimal fallback interaction handler when LangGraph is not available."""
    from flask import jsonify

    if audio_bytes and not utterance:
        try:
            from omnillm.robotics.whisper_stt import WhisperSTT
            stt = WhisperSTT()
            utterance = run_async(stt.transcribe(audio_bytes))
        except Exception:
            pass

    if not utterance:
        return jsonify({"error": "Could not transcribe audio"}), 500

    system_prompt = (
        "You are Pepper, a helpful social robot in the Sgorbissa HRI lab at "
        "DIBRIS, University of Genoa. "
        "Answer concisely (2–4 sentences)."
    )
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": utterance},
    ]

    try:
        resp = run_async(gateway.query(default_model, messages))
        speech = resp.content if not resp.is_error else "I'm sorry, I could not generate a response."
        action = {
            "speech": speech,
            "gesture": "nod",
            "emotion_led": "#44AAFF",
            "metadata": {
                "model_id": getattr(resp, "model_id", default_model) or default_model,
                "rag_enabled": rag_enabled,
                "condition": condition,
                "path": "fallback",
            },
        }
        return jsonify(action)
    except Exception:
        logger.exception("Fallback LLM call failed")
        return jsonify({"error": "Response generation failed. Check server logs."}), 500


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="OmniLLM AI Server for Pepper HRI")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=5000, help="Port to listen on (default: 5000)")
    parser.add_argument("--debug", action="store_true", help="Enable Flask debug mode")
    parser.add_argument("--no-rag", action="store_true", help="Disable RAG pipeline")
    parser.add_argument("--model", default=None, help="Default LLM model ID")
    parser.add_argument("--kb", default=None, help="Path to knowledge base directory")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)
    app = create_app(
        knowledge_base_dir=args.kb,
        default_model=args.model,
        enable_rag=not args.no_rag,
    )
    app.run(host=args.host, port=args.port, debug=args.debug)
