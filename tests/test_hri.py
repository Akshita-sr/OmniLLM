"""Tests for omnillm.hri — HRI task classifier, language detector, and experiment manager."""

from __future__ import annotations

import pytest

from omnillm.hri.classifier import ClassificationResult, HRITaskClassifier, HRITaskType
from omnillm.hri.experiment import (
    CONDITION_CONFIGS,
    ConditionConfig,
    ExperimentCondition,
    ExperimentManager,
    ParticipantSession,
)
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
        # Regression: substring matches against 2-letter Spanish words
        # ("la" in "lab", "es" in "does", "en" in "open") used to mis-
        # classify this plain English question as Spanish, routing it
        # through the multilingual node → gemini-flash.
        result = self.detector.detect("What time does the lab open?")
        assert result.language == "en"
        assert result.is_english is True

    def test_detect_english_with_substring_traps(self):
        # Words like "open", "lab", "ten" each contain 2-letter foreign
        # function words. Word-boundary matching must ignore them.
        result = self.detector.detect("Is the lab open at ten?")
        assert result.language == "en"
        assert result.is_english is True

    def test_detect_empty_string_returns_english(self):
        result = self.detector.detect("")
        assert result.language == "en"

    def test_get_optimal_model_english(self):
        model = self.detector.get_optimal_model("en")
        assert model == "openai-gpt4o-mini"

    def test_get_optimal_model_french(self):
        # Temporarily openai-gpt4o-mini while Gemini quota is exhausted.
        # Revert to "gemini-flash" once Google free-tier access is restored.
        model = self.detector.get_optimal_model("fr")
        assert model == "openai-gpt4o-mini"

    def test_get_optimal_model_unknown(self):
        # Same as above — fallback also rerouted off gemini-flash.
        model = self.detector.get_optimal_model("xx")
        assert model == "openai-gpt4o-mini"

    def test_custom_model_map(self):
        detector = LanguageDetector(custom_model_map={"fr": "claude-haiku"})
        model = detector.get_optimal_model("fr")
        assert model == "claude-haiku"


# ── ExperimentCondition ───────────────────────────────────────────────────────

class TestExperimentCondition:
    def test_all_conditions_exist(self):
        values = [c.value for c in ExperimentCondition]
        assert "A" in values
        assert "B" in values
        assert "C" in values
        assert "D" in values
        assert "E" in values

    def test_condition_from_string(self):
        cond = ExperimentCondition("C")
        assert cond == ExperimentCondition.C


class TestConditionConfigs:
    def test_all_five_conditions_configured(self):
        assert len(CONDITION_CONFIGS) == 5

    def test_condition_a_uses_gpt4o_mini(self):
        cfg = CONDITION_CONFIGS[ExperimentCondition.A]
        assert cfg.model_id == "openai-gpt4o-mini"
        assert cfg.rag_enabled is True
        assert cfg.use_consensus is False

    def test_condition_b_uses_local_model(self):
        cfg = CONDITION_CONFIGS[ExperimentCondition.B]
        assert cfg.model_id == "llama3-8b-local"
        assert cfg.rag_enabled is True

    def test_condition_c_uses_smart_routing(self):
        cfg = CONDITION_CONFIGS[ExperimentCondition.C]
        assert cfg.model_id is None
        assert cfg.use_smart_routing is True
        assert cfg.rag_enabled is True

    def test_condition_d_uses_consensus(self):
        cfg = CONDITION_CONFIGS[ExperimentCondition.D]
        assert cfg.model_id is None
        assert cfg.use_consensus is True
        assert len(cfg.council_models) >= 2

    def test_condition_e_disables_rag(self):
        cfg = CONDITION_CONFIGS[ExperimentCondition.E]
        assert cfg.model_id == "openai-gpt4o-mini"
        assert cfg.rag_enabled is False


# ── ExperimentManager ─────────────────────────────────────────────────────────

class TestExperimentManager:
    def setup_method(self):
        self.manager = ExperimentManager()

    def test_create_session_returns_session(self):
        session = self.manager.create_session("P001", ExperimentCondition.A)
        assert isinstance(session, ParticipantSession)
        assert session.participant_id == "P001"
        assert session.condition == ExperimentCondition.A

    def test_create_session_from_string(self):
        session = self.manager.create_session("P002", "C")
        assert session.condition == ExperimentCondition.C

    def test_create_session_generates_unique_ids(self):
        s1 = self.manager.create_session("P001", "A")
        s2 = self.manager.create_session("P001", "B")
        assert s1.session_id != s2.session_id

    def test_create_session_custom_id(self):
        session = self.manager.create_session("P001", "A", session_id="my-session-id")
        assert session.session_id == "my-session-id"

    def test_get_session_by_id(self):
        session = self.manager.create_session("P001", "A")
        retrieved = self.manager.get_session(session.session_id)
        assert retrieved is session

    def test_get_session_unknown_returns_none(self):
        result = self.manager.get_session("nonexistent-id")
        assert result is None

    def test_get_condition_config(self):
        cfg = self.manager.get_condition_config("C")
        assert cfg.use_smart_routing is True

    def test_get_sessions_by_participant(self):
        self.manager.create_session("P001", "A")
        self.manager.create_session("P001", "B")
        self.manager.create_session("P002", "A")
        sessions = self.manager.get_sessions_by_participant("P001")
        assert len(sessions) == 2

    def test_get_sessions_by_condition(self):
        self.manager.create_session("P001", "A")
        self.manager.create_session("P002", "A")
        self.manager.create_session("P003", "C")
        sessions = self.manager.get_sessions_by_condition("A")
        assert len(sessions) == 2

    def test_summarise_tracks_totals(self):
        s = self.manager.create_session("P001", "A")
        s.log_task({"task_type": "info_retrieval", "utterance": "hi"})
        s.complete()
        summary = self.manager.summarise()
        assert summary["total_sessions"] == 1
        assert summary["completed_sessions"] == 1
        assert summary["total_tasks_logged"] == 1

    def test_export_data(self):
        s = self.manager.create_session("P001", "B")
        s.log_task({"task_type": "navigation"})
        data = self.manager.export_data()
        assert len(data) == 1
        assert data[0]["participant_id"] == "P001"
        assert data[0]["condition"] == "B"


# ── ParticipantSession ────────────────────────────────────────────────────────

class TestParticipantSession:
    def test_session_starts_with_empty_log(self):
        manager = ExperimentManager()
        session = manager.create_session("P001", "A")
        assert session.task_log == []
        assert session.end_time is None

    def test_log_task_appends_record(self):
        manager = ExperimentManager()
        session = manager.create_session("P001", "A")
        session.log_task({"task_type": "navigation", "utterance": "Where is Room 101?"})
        assert len(session.task_log) == 1
        assert session.task_log[0]["task_type"] == "navigation"

    def test_log_task_adds_timestamp(self):
        manager = ExperimentManager()
        session = manager.create_session("P001", "A")
        session.log_task({"task_type": "info_retrieval"})
        assert "timestamp" in session.task_log[0]

    def test_complete_sets_end_time(self):
        manager = ExperimentManager()
        session = manager.create_session("P001", "A")
        session.complete()
        assert session.end_time is not None

    def test_set_questionnaire(self):
        manager = ExperimentManager()
        session = manager.create_session("P001", "A")
        session.set_questionnaire({
            "accuracy": 6.0,
            "naturalness": 5.0,
            "trust": 7.0,
        })
        assert session.questionnaire_scores["accuracy"] == 6.0

    def test_to_dict_includes_all_fields(self):
        manager = ExperimentManager()
        session = manager.create_session("P001", "C")
        d = session.to_dict()
        assert d["participant_id"] == "P001"
        assert d["condition"] == "C"
        assert "task_log" in d
        assert "questionnaire_scores" in d
