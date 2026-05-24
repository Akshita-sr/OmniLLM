"""OmniLLM AI Server — Flask HTTP API.

Single path through the new ``omnillm.hri.pipeline.process_interaction``
function. No LangGraph, no fallback fork, no per-condition routing.

Endpoints
---------
``GET  /health``         — liveness probe
``GET  /status``         — server config and component status
``POST /interact``       — main entry: ``{"text": "...", "council": false}`` → RobotAction JSON
``POST /transcribe``     — ``{"audio": "<base64 WAV>"}`` → ``{"text": "...", "language": "en"}``
``POST /evaluate``       — log a post-interaction Likert questionnaire
``GET  /export``         — export all logged interactions as JSON

Default port: 5000. Run with::

    python -m omnillm.server.app --port 5000
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def create_app(
    knowledge_base_dir: str | Path | None = None,
    default_model: str | None = None,
    enable_rag: bool = True,
    persist_directory: str | Path | None = None,
):
    """Build the Flask application."""
    try:
        from flask import Flask, jsonify, request  # type: ignore[import-untyped]
    except ImportError as exc:
        raise ImportError(
            "Flask is required. Install with: pip install \"omnillm[robotics]\""
        ) from exc

    from omnillm.gateway import LLMGateway
    from omnillm.hri.pipeline import process_interaction
    from omnillm.utils.experiment_logger import ExperimentLogger

    app = Flask(__name__)
    app.config["JSON_SORT_KEYS"] = False

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
    _persist_dir = Path(
        persist_directory
        or os.getenv(
            "OMNILLM_CHROMA_DIR",
            str(Path(__file__).parent.parent.parent / ".chroma_store"),
        )
    )

    gateway = LLMGateway()
    exp_logger = ExperimentLogger()
    rag = None

    if enable_rag:
        try:
            from omnillm.rag.pipeline import RAGPipeline
            rag = RAGPipeline(
                gateway=gateway,
                model_id=_default_model,
                persist_directory=_persist_dir,
            )
            if _kb_dir.exists():
                n = rag.index_directory(_kb_dir)
                logger.info("Indexed %d chunks from %s", n, _kb_dir)
            else:
                logger.warning("KB dir %s not found — RAG enabled with empty index.", _kb_dir)
        except ImportError as exc:
            logger.warning("RAG disabled — %s", exc)
            rag = None

    def _run_async(coro):
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()

    # ── Endpoints ──────────────────────────────────────────────────────────────

    @app.route("/health", methods=["GET"])
    def health():
        return jsonify({"status": "ok", "version": "0.2.0"})

    @app.route("/status", methods=["GET"])
    def status():
        return jsonify({
            "status": "ok",
            "default_model": _default_model,
            "rag_enabled": rag is not None,
            "knowledge_base": str(_kb_dir),
            "knowledge_base_exists": _kb_dir.exists(),
            "chroma_store": str(_persist_dir),
            "available_models": gateway.list_models(),
        })

    @app.route("/transcribe", methods=["POST"])
    def transcribe():
        data: dict = request.get_json(force=True) or {}
        audio_b64: str = data.get("audio", "")
        backend = data.get("backend", "api")
        if not audio_b64:
            return jsonify({"error": "No audio provided"}), 400
        try:
            audio_bytes = base64.b64decode(audio_b64)
        except Exception:
            return jsonify({"error": "Invalid base64 audio"}), 400
        try:
            from omnillm.robotics.audio import transcribe as stt
            text, lang = _run_async(stt(audio_bytes, backend=backend))
        except ImportError as exc:
            return jsonify({"error": str(exc)}), 500
        except Exception:
            logger.exception("Transcription failed")
            return jsonify({"error": "Transcription failed. Check server logs."}), 500
        return jsonify({"text": text, "language": lang or "en"})

    @app.route("/interact", methods=["POST"])
    def interact():
        data: dict = request.get_json(force=True) or {}
        utterance: str = (data.get("text") or "").strip()
        audio_b64: str = data.get("audio", "")
        # ``strategy_override`` is the new autonomous-pipeline knob:
        #   "auto"    — let the triage classifier decide (default)
        #   "direct"  — force single-model with fallback
        #   "rag"     — force RAG-grounded answer (requires KB)
        #   "council" — force multi-LLM consensus + judge
        # The legacy ``council`` bool is kept as an alias for backwards
        # compat with old run.py builds.
        strategy_override: str = (data.get("strategy_override") or "auto").lower()
        if strategy_override not in {"auto", "direct", "rag", "council"}:
            return jsonify({
                "error": f"strategy_override must be one of auto/direct/rag/council, got '{strategy_override}'"
            }), 400
        council_alias: bool = bool(data.get("council", False))
        if council_alias and strategy_override == "auto":
            strategy_override = "council"
        session_id: str = data.get("session_id", "")
        participant_id: str = data.get("participant_id", "anon")
        stt_backend: str = data.get("stt_backend", "api")

        language_hint: str | None = data.get("language") or None
        if not utterance and audio_b64:
            try:
                from omnillm.robotics.audio import transcribe as stt
                audio_bytes = base64.b64decode(audio_b64)
                utterance, whisper_lang = _run_async(stt(audio_bytes, backend=stt_backend))
                if whisper_lang and not language_hint:
                    language_hint = whisper_lang
            except Exception:
                logger.exception("Inline transcription failed")
                return jsonify({"error": "Could not transcribe audio"}), 500

        if not utterance:
            return jsonify({"error": "Provide 'text' or 'audio'"}), 400

        # Operating-mode tag set by run.py before the launcher fires. The
        # client may also override it per-call (useful when a single server
        # instance handles multiple modes).
        mode = (data.get("mode") or os.getenv("OMNILLM_MODE") or "").strip()

        action = _run_async(process_interaction(
            utterance=utterance,
            gateway=gateway,
            rag=rag,
            default_model=_default_model,
            strategy_override=strategy_override,
            language_hint=language_hint,
            logger=exp_logger,
            session_id=session_id,
            participant_id=participant_id,
            mode=mode,
        ))
        return jsonify(action)

    @app.route("/evaluate", methods=["POST"])
    def evaluate():
        data: dict = request.get_json(force=True) or {}
        required = ["session_id", "participant_id"]
        missing = [f for f in required if f not in data]
        if missing:
            return jsonify({"error": f"Missing fields: {missing}"}), 400
        try:
            exp_logger.log_interaction(
                session_id=data["session_id"],
                participant_id=data["participant_id"],
                task_type="questionnaire",
                utterance="",
                response="",
                model_id="",
                mode=(os.getenv("OMNILLM_MODE") or ""),
                notes=json.dumps(data.get("scores", {})),
            )
        except Exception:
            logger.exception("Failed to log questionnaire")
            return jsonify({"error": "Logging failed. Check server logs."}), 500
        return jsonify({"status": "ok", "session_id": data["session_id"]})

    @app.route("/export", methods=["GET"])
    def export_data():
        records = [
            {
                "session_id": r.session_id,
                "participant_id": r.participant_id,
                "task_type": r.task_type,
                "mode": r.mode,
                "utterance": r.utterance,
                "response": r.response,
                "model_id": r.model_id,
                "latency_ms": r.latency_ms,
                "rag_enabled": r.rag_enabled,
                "language": r.language,
                "gesture_used": r.gesture_used,
                "timestamp": r.timestamp,
                "notes": r.notes,
            }
            for r in exp_logger.records
        ]
        return jsonify({"count": len(records), "records": records})

    return app


# ── Entry point ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="OmniLLM AI Server")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=5000)
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("--no-rag", action="store_true")
    parser.add_argument("--model", default=None)
    parser.add_argument("--kb", default=None)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)
    app = create_app(
        knowledge_base_dir=args.kb,
        default_model=args.model,
        enable_rag=not args.no_rag,
    )
    app.run(host=args.host, port=args.port, debug=args.debug)
