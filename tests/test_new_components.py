"""Tests for the new components: agent_graph, whisper_stt, questionnaire, server."""

from __future__ import annotations

import asyncio
import base64
import json
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch


# ── HRIGraphState ─────────────────────────────────────────────────────────────

class TestHRIGraphState:
    def test_default_state(self):
        from omnillm.hri.agent_graph import HRIGraphState
        state = HRIGraphState()
        assert state.utterance == ""
        assert state.detected_language == "en"
        assert state.task_type == "info_retrieval"
        assert state.rag_enabled is True
        assert state.robot_action == {}
        assert state.error is None

    def test_state_with_values(self):
        from omnillm.hri.agent_graph import HRIGraphState
        state = HRIGraphState(
            utterance="Where is Room 305?",
            participant_id="P001",
            condition="C",
            rag_enabled=True,
        )
        assert state.utterance == "Where is Room 305?"
        assert state.participant_id == "P001"
        assert state.condition == "C"

    def test_state_start_time_set(self):
        import time
        from omnillm.hri.agent_graph import HRIGraphState
        before = time.monotonic()
        state = HRIGraphState()
        after = time.monotonic()
        assert before <= state._start_time <= after


# ── Routing logic ─────────────────────────────────────────────────────────────

class TestRouteByTaskType:
    def test_info_retrieval_rag_on(self):
        from omnillm.hri.agent_graph import _route_by_task_type
        state = {"task_type": "info_retrieval", "condition": "A", "rag_enabled": True}
        assert _route_by_task_type(state) == "rag"

    def test_info_retrieval_rag_off(self):
        from omnillm.hri.agent_graph import _route_by_task_type
        state = {"task_type": "info_retrieval", "condition": "A", "rag_enabled": False}
        assert _route_by_task_type(state) == "direct_llm"

    def test_navigation_rag_on(self):
        from omnillm.hri.agent_graph import _route_by_task_type
        state = {"task_type": "navigation", "condition": "A", "rag_enabled": True}
        assert _route_by_task_type(state) == "nav_rag"

    def test_navigation_rag_off(self):
        from omnillm.hri.agent_graph import _route_by_task_type
        state = {"task_type": "navigation", "condition": "A", "rag_enabled": False}
        assert _route_by_task_type(state) == "direct_llm"

    def test_social_always_direct(self):
        from omnillm.hri.agent_graph import _route_by_task_type
        state = {"task_type": "social_conversation", "condition": "A", "rag_enabled": True}
        assert _route_by_task_type(state) == "direct_llm"

    def test_multilingual_always_multilingual(self):
        from omnillm.hri.agent_graph import _route_by_task_type
        state = {"task_type": "multilingual", "condition": "A", "rag_enabled": True}
        assert _route_by_task_type(state) == "multilingual_llm"

    def test_condition_e_always_direct(self):
        from omnillm.hri.agent_graph import _route_by_task_type
        # Condition E = RAG-Off Control
        for task in ("info_retrieval", "navigation", "social_conversation"):
            state = {"task_type": task, "condition": "E", "rag_enabled": True}
            assert _route_by_task_type(state) == "direct_llm"

    def test_unknown_task_type_defaults_to_direct_llm(self):
        from omnillm.hri.agent_graph import _route_by_task_type
        state = {"task_type": "unknown_type", "condition": "A", "rag_enabled": True}
        assert _route_by_task_type(state) == "direct_llm"


# ── Node functions (unit) ─────────────────────────────────────────────────────

class TestDetectLanguageNode:
    async def test_detect_english(self):
        from omnillm.hri.agent_graph import _make_detect_language_node
        node = _make_detect_language_node()
        result = await node({"utterance": "Where is the lab?"})
        assert result.get("detected_language") == "en"

    async def test_empty_utterance(self):
        from omnillm.hri.agent_graph import _make_detect_language_node
        node = _make_detect_language_node()
        result = await node({"utterance": ""})
        assert result == {}


class TestClassifyTaskNode:
    async def test_classify_navigation(self):
        from omnillm.hri.agent_graph import _make_classify_task_node
        node = _make_classify_task_node()
        result = await node({"utterance": "Where is Room 305?", "detected_language": "en"})
        assert result["task_type"] == "navigation"
        assert 0 < result["task_confidence"] <= 1.0

    async def test_classify_social(self):
        from omnillm.hri.agent_graph import _make_classify_task_node
        node = _make_classify_task_node()
        result = await node({"utterance": "Hello, how are you?", "detected_language": "en"})
        assert result["task_type"] == "social_conversation"

    async def test_classify_multilingual(self):
        from omnillm.hri.agent_graph import _make_classify_task_node
        node = _make_classify_task_node()
        result = await node({"utterance": "Bonjour", "detected_language": "fr"})
        assert result["task_type"] == "multilingual"


class TestActionPlanNode:
    async def test_generates_action(self):
        from omnillm.hri.agent_graph import _make_action_plan_node
        node = _make_action_plan_node()
        state = {
            "response_text": "The lab is on the left.",
            "gesture": None,
            "led_color": None,
            "task_type": "navigation",
        }
        result = await node(state)
        assert "robot_action" in result
        assert result["robot_action"]["speech"] == "The lab is on the left."
        assert result["robot_action"]["gesture"] is not None

    async def test_preserves_existing_gesture(self):
        from omnillm.hri.agent_graph import _make_action_plan_node
        node = _make_action_plan_node()
        state = {
            "response_text": "Hello!",
            "gesture": "wave",
            "led_color": "#00FF88",
            "task_type": "social_conversation",
        }
        result = await node(state)
        assert result["robot_action"]["gesture"] == "wave"
        assert result["robot_action"]["emotion_led"] == "#00FF88"


class TestLogNode:
    async def test_logs_with_logger(self):
        from omnillm.hri.agent_graph import _make_log_node
        from omnillm.utils.experiment_logger import ExperimentLogger
        logger = ExperimentLogger()
        node = _make_log_node(logger)

        import time
        state = {
            "session_id": "s1",
            "participant_id": "P001",
            "condition": "A",
            "task_type": "info_retrieval",
            "utterance": "What time does the lab open?",
            "response_text": "The lab opens at 9 AM.",
            "model_id": "openai-gpt4o-mini",
            "rag_enabled": True,
            "detected_language": "en",
            "_start_time": time.monotonic(),
        }
        await node(state)
        assert len(logger.records) == 1
        assert logger.records[0].session_id == "s1"

    async def test_no_logger_is_noop(self):
        from omnillm.hri.agent_graph import _make_log_node
        node = _make_log_node(None)
        result = await node({"session_id": "s1"})
        assert result == {}


# ── WhisperSTT ────────────────────────────────────────────────────────────────

class TestWhisperSTT:
    def test_init_defaults(self):
        from omnillm.robotics.whisper_stt import WhisperSTT
        stt = WhisperSTT()
        assert stt.backend == "local"
        assert stt.model_size == "base"
        assert stt.device == "cpu"

    def test_backend_info_local(self):
        from omnillm.robotics.whisper_stt import WhisperSTT
        stt = WhisperSTT(backend="local", model_size="small")
        assert "local" in stt.backend_info
        assert "small" in stt.backend_info

    def test_backend_info_api(self):
        from omnillm.robotics.whisper_stt import WhisperSTT
        stt = WhisperSTT(backend="api")
        assert "API" in stt.backend_info

    async def test_empty_audio_returns_empty_string(self):
        from omnillm.robotics.whisper_stt import WhisperSTT
        stt = WhisperSTT()
        result = await stt.transcribe(b"")
        assert result == ""

    async def test_local_raises_import_error_without_whisper(self):
        from omnillm.robotics.whisper_stt import WhisperSTT
        stt = WhisperSTT(backend="local")

        # Patch whisper import to fail
        with patch.dict("sys.modules", {"whisper": None}):
            with pytest.raises(ImportError, match="openai-whisper"):
                stt._load_local_model()

    async def test_api_raises_import_error_without_openai(self):
        from omnillm.robotics.whisper_stt import WhisperSTT
        stt = WhisperSTT(backend="api")

        with patch.dict("sys.modules", {"openai": None}):
            with pytest.raises(ImportError, match="openai"):
                await stt._transcribe_api(b"audio", None, None)


# ── InteractionQuestionnaire ──────────────────────────────────────────────────

class TestInteractionQuestionnaire:
    def test_valid_questionnaire(self):
        from omnillm.utils.questionnaire import InteractionQuestionnaire
        q = InteractionQuestionnaire(
            session_id="s1",
            participant_id="P001",
            condition="C",
            accuracy=6,
            naturalness=5,
            trust=6,
            gesture_appropriateness=5,
            response_speed=7,
        )
        assert q.mean_score == pytest.approx(5.8)
        assert 0 <= q.normalised_score <= 1

    def test_mean_score_all_sevens(self):
        from omnillm.utils.questionnaire import InteractionQuestionnaire
        q = InteractionQuestionnaire(
            session_id="s1", participant_id="P001", condition="A",
            accuracy=7, naturalness=7, trust=7, gesture_appropriateness=7, response_speed=7,
        )
        assert q.mean_score == 7.0
        assert q.normalised_score == pytest.approx(1.0)

    def test_mean_score_all_ones(self):
        from omnillm.utils.questionnaire import InteractionQuestionnaire
        q = InteractionQuestionnaire(
            session_id="s1", participant_id="P001", condition="A",
            accuracy=1, naturalness=1, trust=1, gesture_appropriateness=1, response_speed=1,
        )
        assert q.mean_score == 1.0
        assert q.normalised_score == pytest.approx(0.0)

    def test_invalid_score_raises(self):
        from omnillm.utils.questionnaire import InteractionQuestionnaire
        with pytest.raises(ValueError, match="accuracy"):
            InteractionQuestionnaire(
                session_id="s1", participant_id="P001", condition="A",
                accuracy=8,  # out of range
            )

    def test_invalid_score_zero_raises(self):
        from omnillm.utils.questionnaire import InteractionQuestionnaire
        with pytest.raises(ValueError):
            InteractionQuestionnaire(
                session_id="s1", participant_id="P001", condition="A",
                naturalness=0,  # out of range
            )


class TestGodspeedResponse:
    def test_overall_mean(self):
        from omnillm.utils.questionnaire import GodspeedResponse
        gs = GodspeedResponse(
            session_id="s1", participant_id="P001", condition="A",
            anthropomorphism=4.0, animacy=3.5, likeability=4.5,
            perceived_intelligence=4.0, perceived_safety=3.0,
        )
        assert gs.overall_mean == pytest.approx(3.8)


class TestPairwisePreference:
    def test_basic_preference(self):
        from omnillm.utils.questionnaire import PairwisePreference
        pref = PairwisePreference(
            session_id="s1", participant_id="P001",
            condition_a="A", condition_b="C", preferred="C",
        )
        assert pref.preferred == "C"
        assert pref.condition_a == "A"

    def test_tie_preference(self):
        from omnillm.utils.questionnaire import PairwisePreference
        pref = PairwisePreference(
            session_id="s1", participant_id="P001",
            condition_a="A", condition_b="B", preferred="tie",
        )
        assert pref.preferred == "tie"


class TestQuestionnaireCollector:
    def _make_questionnaire(self, session_id="s1", participant_id="P001", condition="A", scores=5):
        from omnillm.utils.questionnaire import InteractionQuestionnaire
        return InteractionQuestionnaire(
            session_id=session_id, participant_id=participant_id, condition=condition,
            accuracy=scores, naturalness=scores, trust=scores,
            gesture_appropriateness=scores, response_speed=scores,
        )

    def test_add_and_summary(self):
        from omnillm.utils.questionnaire import QuestionnaireCollector
        collector = QuestionnaireCollector()
        collector.add_interaction_response(self._make_questionnaire(condition="A", scores=6))
        collector.add_interaction_response(self._make_questionnaire(condition="C", scores=7))

        summary = collector.summary_by_condition()
        assert "A" in summary
        assert "C" in summary
        assert summary["A"]["mean_overall"] == pytest.approx(6.0)
        assert summary["C"]["mean_overall"] == pytest.approx(7.0)

    def test_pairwise_win_rates(self):
        from omnillm.utils.questionnaire import PairwisePreference, QuestionnaireCollector
        collector = QuestionnaireCollector()
        collector.add_pairwise_preference(
            PairwisePreference(session_id="s1", participant_id="P001",
                               condition_a="A", condition_b="C", preferred="C")
        )
        collector.add_pairwise_preference(
            PairwisePreference(session_id="s2", participant_id="P002",
                               condition_a="A", condition_b="C", preferred="C")
        )
        rates = collector.pairwise_win_rates()
        # C wins both times vs A
        assert rates.get("C", {}).get("A", 0.0) == pytest.approx(1.0) or \
               rates.get("A", {}).get("C", 1.0) == pytest.approx(0.0)

    def test_save_json(self, tmp_path):
        from omnillm.utils.questionnaire import QuestionnaireCollector
        collector = QuestionnaireCollector()
        collector.add_interaction_response(self._make_questionnaire())
        out = tmp_path / "test.json"
        collector.save(out)
        assert out.exists()
        data = json.loads(out.read_text())
        assert "interaction_responses" in data
        assert len(data["interaction_responses"]) == 1

    def test_to_csv(self, tmp_path):
        from omnillm.utils.questionnaire import QuestionnaireCollector
        collector = QuestionnaireCollector()
        collector.add_interaction_response(self._make_questionnaire())
        out = tmp_path / "test.csv"
        collector.to_csv(out)
        assert out.exists()
        content = out.read_text()
        assert "accuracy" in content
        assert "mean_score" in content

    def test_empty_collector_summary(self):
        from omnillm.utils.questionnaire import QuestionnaireCollector
        collector = QuestionnaireCollector()
        assert collector.summary_by_condition() == {}
        assert collector.pairwise_win_rates() == {}


# ── Flask AI server (import-only, no real calls) ──────────────────────────────

class TestServerImport:
    def test_create_app_importable(self):
        """The server module should be importable without starting the app."""
        from omnillm.server import app as server_module
        assert hasattr(server_module, "create_app")

    def test_naoqi_client_importable(self):
        from omnillm.server import naoqi_client
        assert hasattr(naoqi_client, "PepperNAOqiClient")

    def test_naoqi_client_init(self):
        from omnillm.server.naoqi_client import PepperNAOqiClient
        client = PepperNAOqiClient(
            robot_ip="192.168.1.100",
            robot_port=9559,
            server_ip="localhost",
            server_port=5000,
            participant_id="P001",
            condition="C",
        )
        assert client.robot_ip == "192.168.1.100"
        assert client.participant_id == "P001"
        assert client.condition == "C"


# ── Knowledge base files ──────────────────────────────────────────────────────

class TestKnowledgeBase:
    KB_DIR = Path(__file__).parent.parent / "knowledge_base"

    def test_knowledge_base_directory_exists(self):
        assert self.KB_DIR.exists(), f"knowledge_base/ dir not found at {self.KB_DIR}"

    def test_visitor_profiles_csv_exists(self):
        assert (self.KB_DIR / "visitor_profiles.csv").exists()

    def test_lab_info_txt_exists(self):
        assert (self.KB_DIR / "lab_info.txt").exists()

    def test_research_projects_txt_exists(self):
        assert (self.KB_DIR / "research_projects.txt").exists()

    def test_event_schedule_csv_exists(self):
        assert (self.KB_DIR / "event_schedule.csv").exists()

    def test_university_map_txt_exists(self):
        assert (self.KB_DIR / "university_map.txt").exists()

    def test_faq_txt_exists(self):
        assert (self.KB_DIR / "faq.txt").exists()

    def test_lab_info_contains_opening_hours(self):
        content = (self.KB_DIR / "lab_info.txt").read_text(encoding="utf-8")
        assert "08:00" in content

    def test_faq_contains_wifi_password(self):
        content = (self.KB_DIR / "faq.txt").read_text(encoding="utf-8")
        assert "WiFi" in content or "wifi" in content.lower()

    def test_visitor_profiles_has_header(self):
        import csv
        with open(self.KB_DIR / "visitor_profiles.csv", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            headers = reader.fieldnames or []
        assert "name" in headers
        assert "role" in headers
        assert "department" in headers

    def test_event_schedule_has_events(self):
        import csv
        with open(self.KB_DIR / "event_schedule.csv", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        assert len(rows) >= 5
