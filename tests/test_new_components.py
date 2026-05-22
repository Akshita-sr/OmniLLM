"""Tests for the streamlined refactor: hri.pipeline, robotics.audio, server.app."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest


# ── process_interaction pipeline ──────────────────────────────────────────────

class TestProcessInteraction:
    @pytest.mark.asyncio
    async def test_returns_robot_action_shape(self):
        from omnillm.gateway import LLMGateway, ModelResponse
        from omnillm.hri.pipeline import process_interaction

        gateway = LLMGateway()
        fake_resp = ModelResponse(
            model_id="openai-gpt4o-mini",
            content="The lab opens at 9 AM.",
            input_tokens=20,
            output_tokens=10,
        )
        with patch.object(gateway, "query", new=AsyncMock(return_value=fake_resp)):
            action = await process_interaction(
                "What time does the lab open?",
                gateway=gateway,
                rag=None,
            )

        assert "speech" in action
        assert "gesture" in action
        assert "emotion_led" in action
        assert "metadata" in action
        assert action["speech"] == "The lab opens at 9 AM."
        meta = action["metadata"]
        assert meta["task_type"] in {"info_retrieval", "navigation", "social_conversation"}
        assert meta["language"] == "en"
        assert meta["model_id"]

    @pytest.mark.asyncio
    async def test_multilingual_routes_to_haiku(self):
        from omnillm.gateway import LLMGateway, ModelResponse
        from omnillm.hri.pipeline import process_interaction

        gateway = LLMGateway()

        async def mock_query(model_id, *args, **kwargs):
            assert "haiku" in model_id or "gpt4o" in model_id
            return ModelResponse(model_id=model_id, content="Ciao, come stai?")

        with patch.object(gateway, "query", new_callable=AsyncMock, side_effect=mock_query):
            action = await process_interaction(
                "Ciao, dove si trova il laboratorio?",
                gateway=gateway,
                rag=None,
            )

        assert action["metadata"]["task_type"] == "multilingual"
        assert action["metadata"]["language"] == "it"

    @pytest.mark.asyncio
    async def test_gesture_planned_for_navigation(self):
        from omnillm.gateway import LLMGateway, ModelResponse
        from omnillm.hri.pipeline import process_interaction

        gateway = LLMGateway()
        fake_resp = ModelResponse(
            model_id="openai-gpt4o-mini",
            content="The lab is on your left.",
        )
        with patch.object(gateway, "query", new=AsyncMock(return_value=fake_resp)):
            action = await process_interaction(
                "Where is the lab?",
                gateway=gateway,
                rag=None,
            )

        assert action["metadata"]["task_type"] == "navigation"
        assert action["gesture"] in {"point_left", "point_forward", "point_right", "point_up", "nod"}


# ── Audio module imports ──────────────────────────────────────────────────────

class TestAudioModule:
    def test_module_imports(self):
        from omnillm.robotics import audio
        assert hasattr(audio, "record_from_mic")
        assert hasattr(audio, "transcribe")

    @pytest.mark.asyncio
    async def test_transcribe_empty_returns_empty(self):
        from omnillm.robotics.audio import transcribe
        text, lang = await transcribe(b"", backend="api")
        assert text == ""
        assert lang == ""

    def test_normalise_lang_iso_codes(self):
        from omnillm.robotics.audio import _normalise_lang
        assert _normalise_lang("english") == "en"
        assert _normalise_lang("italian") == "it"
        assert _normalise_lang("fr") == "fr"
        assert _normalise_lang("") == ""


# ── Server smoke ──────────────────────────────────────────────────────────────

class TestServer:
    def test_create_app_importable(self):
        from omnillm.server import app as server_module
        assert hasattr(server_module, "create_app")


# ── Knowledge base (post-rebuild) ─────────────────────────────────────────────

class TestKnowledgeBase:
    KB_DIR = Path(__file__).parent.parent / "knowledge_base"

    def test_knowledge_base_directory_exists(self):
        assert self.KB_DIR.exists(), f"knowledge_base/ dir not found at {self.KB_DIR}"

    def test_kb_has_some_content(self):
        files = [p for p in self.KB_DIR.iterdir() if p.is_file()]
        assert len(files) > 0, "KB is empty — run: python -m omnillm.rag.builder --rebuild"
