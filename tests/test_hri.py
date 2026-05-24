"""Tests for omnillm.hri — task classifier and language detector."""

from __future__ import annotations

import pytest

from omnillm.hri.classifier import ClassificationResult, HRITaskClassifier, HRITaskType
from omnillm.hri.language_detector import LanguageDetectionResult, LanguageDetector


# ── HRITaskClassifier ─────────────────────────────────────────────────────────

class TestHRITaskType:
    def test_all_task_types_exist(self):
        values = [t.value for t in HRITaskType]
        assert "info_retrieval" in values
        assert "navigation" in values
        assert "social_conversation" in values
        assert "multilingual" in values


class TestHRITaskClassifier:
    def setup_method(self):
        self.clf = HRITaskClassifier()

    def test_classify_navigation_room(self):
        result = self.clf.classify("Where is Room 305?")
        assert result.task_type == HRITaskType.NAVIGATION
        assert result.confidence > 0.5

    def test_classify_navigation_cafeteria(self):
        result = self.clf.classify("Can you point me to the cafeteria?")
        assert result.task_type == HRITaskType.NAVIGATION

    def test_classify_navigation_directions(self):
        result = self.clf.classify("How do I get to the seminar room?")
        assert result.task_type == HRITaskType.NAVIGATION

    def test_classify_social_greeting(self):
        result = self.clf.classify("Hello, how are you?")
        assert result.task_type == HRITaskType.SOCIAL_CONVERSATION
        assert result.confidence > 0.5

    def test_classify_social_question(self):
        result = self.clf.classify("What do you think about artificial intelligence?")
        assert result.task_type == HRITaskType.SOCIAL_CONVERSATION

    def test_classify_info_retrieval_hours(self):
        result = self.clf.classify("What time does the lab open?")
        assert result.task_type == HRITaskType.INFO_RETRIEVAL

    def test_classify_info_retrieval_professor(self):
        result = self.clf.classify("Tell me about Professor Smith's research.")
        assert result.task_type == HRITaskType.INFO_RETRIEVAL

    def test_classify_info_retrieval_wifi(self):
        result = self.clf.classify("What is the wifi password?")
        assert result.task_type == HRITaskType.INFO_RETRIEVAL

    def test_classify_multilingual_non_english(self):
        result = self.clf.classify("Bonjour, comment allez-vous?", detected_language="fr")
        assert result.task_type == HRITaskType.MULTILINGUAL
        assert result.confidence > 0.9

    def test_classify_multilingual_preserves_language(self):
        result = self.clf.classify("Wo ist das Labor?", detected_language="de")
        assert result.task_type == HRITaskType.MULTILINGUAL
        assert result.detected_language == "de"

    def test_classify_returns_classification_result(self):
        result = self.clf.classify("Where is the exit?")
        assert isinstance(result, ClassificationResult)
        assert isinstance(result.task_type, HRITaskType)
        assert 0 <= result.confidence <= 1
        assert result.method == "rule_based"

    def test_classify_ambiguous_defaults_to_info_retrieval(self):
        result = self.clf.classify("xyz xyz xyz")
        assert result.task_type == HRITaskType.INFO_RETRIEVAL
        assert result.confidence < 0.6

    def test_classify_floor_pattern(self):
        result = self.clf.classify("How do I get to floor 3?")
        assert result.task_type == HRITaskType.NAVIGATION


# ── LanguageDetector ──────────────────────────────────────────────────────────

class TestLanguageDetector:
    def setup_method(self):
        self.detector = LanguageDetector()

    def test_detect_english(self):
        result = self.detector.detect("Hello, how are you? What is the lab schedule?")
        assert result.language == "en"
        assert result.is_english is True

    def test_detect_french(self):
        result = self.detector.detect("Bonjour, comment allez-vous? Je voudrais savoir.")
        assert result.language == "fr"
        assert result.is_english is False

    def test_detect_german(self):
        result = self.detector.detect("Guten Morgen, ich suche das Labor.")
        assert result.language == "de"
        assert result.is_english is False

    def test_detect_arabic_script(self):
        result = self.detector.detect("مرحبا كيف حالك")
        assert result.language == "ar"
        assert result.is_english is False
        assert result.script == "Arabic"

    def test_detect_japanese_hiragana(self):
        result = self.detector.detect("こんにちは、お元気ですか")
        assert result.language == "ja"
        assert result.is_english is False

    def test_detect_chinese_cjk(self):
        result = self.detector.detect("你好，请问实验室在哪里")
        assert result.language in ("zh", "ja")  # CJK ambiguity
        assert result.is_english is False

    def test_detect_returns_detection_result(self):
        result = self.detector.detect("Hello")
        assert isinstance(result, LanguageDetectionResult)
        assert 0 <= result.confidence <= 1

    def test_detect_short_english_question(self):
        result = self.detector.detect("What time does the lab open?")
        assert result.language == "en"
        assert result.is_english is True

    def test_detect_english_with_substring_traps(self):
        result = self.detector.detect("Is the lab open at ten?")
        assert result.language == "en"
        assert result.is_english is True

    def test_detect_empty_string_returns_english(self):
        result = self.detector.detect("")
        assert result.language == "en"

    def test_get_optimal_model_english(self):
        assert self.detector.get_optimal_model("en") == "openai-gpt4o-mini"

    def test_get_optimal_model_french(self):
        assert self.detector.get_optimal_model("fr") == "claude-haiku"

    def test_get_optimal_model_unknown(self):
        assert self.detector.get_optimal_model("xx") == "claude-haiku"

    def test_custom_model_map(self):
        detector = LanguageDetector(custom_model_map={"fr": "claude-haiku"})
        assert detector.get_optimal_model("fr") == "claude-haiku"


# ── process_interaction pipeline (merged from test_new_components.py) ─────────
# These are end-to-end integration tests that exercise the full unified
# pipeline (triage → router → answer → gesture → RobotAction) with mocked
# gateway responses. They live here (not in a separate file) because they
# test the HRI orchestrator more than any one classifier.

class TestProcessInteraction:
    @pytest.mark.asyncio
    async def test_returns_robot_action_shape(self):
        from unittest.mock import AsyncMock, patch

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
        from unittest.mock import AsyncMock, patch

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
        from unittest.mock import AsyncMock, patch

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

    @pytest.mark.asyncio
    async def test_mode_is_propagated_to_metadata_logger(self):
        """The new `mode` parameter must reach the experiment logger."""
        from unittest.mock import AsyncMock, patch

        from omnillm.gateway import LLMGateway, ModelResponse
        from omnillm.hri.pipeline import process_interaction
        from omnillm.utils.experiment_logger import ExperimentLogger

        gateway = LLMGateway()
        fake_resp = ModelResponse(model_id="openai-gpt4o-mini", content="ok")
        logger = ExperimentLogger()

        with patch.object(gateway, "query", new=AsyncMock(return_value=fake_resp)):
            await process_interaction(
                "Hello",
                gateway=gateway,
                rag=None,
                logger=logger,
                session_id="s1",
                participant_id="P001",
                mode="choregraphe",
            )

        records = logger.get_records()
        assert len(records) == 1
        assert records[0].mode == "choregraphe"


# ── Audio module (merged from test_new_components.py) ─────────────────────────

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


# ── Server smoke (merged from test_new_components.py) ─────────────────────────

class TestServer:
    def test_create_app_importable(self):
        from omnillm.server import app as server_module
        assert hasattr(server_module, "create_app")
