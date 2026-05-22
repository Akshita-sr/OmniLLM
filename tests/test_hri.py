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
