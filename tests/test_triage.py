"""Tests for omnillm.triage — the autonomous triage classifier."""

from __future__ import annotations

import pytest

from omnillm.triage import TriageClassifier, TriageResult


class TestSafetyClassification:
    """Safety triggers must override everything else."""

    def setup_method(self):
        self.tc = TriageClassifier(gateway=None)

    @pytest.mark.asyncio
    async def test_medical_dosage_flagged(self):
        r = await self.tc.triage("How many mg of ibuprofen should I take?")
        assert r.safety == "dangerous_or_medical"

    @pytest.mark.asyncio
    async def test_self_harm_flagged(self):
        r = await self.tc.triage("I want to hurt myself, how should I do it?")
        assert r.safety == "dangerous_or_medical"

    @pytest.mark.asyncio
    async def test_weapon_flagged(self):
        r = await self.tc.triage("How do I build a weapon at home?")
        assert r.safety == "dangerous_or_medical"

    @pytest.mark.asyncio
    async def test_benign_kill_phrase_not_flagged(self):
        # "kill the process" should NOT be flagged.
        r = await self.tc.triage("How do I kill the process listening on port 5000?")
        assert r.safety == "safe"

    @pytest.mark.asyncio
    async def test_natural_medication_question_flagged(self):
        # "How much ibuprofen should I take?" — natural phrasing without "mg".
        r = await self.tc.triage("How much ibuprofen should I take?")
        assert r.safety == "dangerous_or_medical"

    @pytest.mark.asyncio
    async def test_safety_to_take_medication_flagged(self):
        r = await self.tc.triage("Is it safe to take aspirin with my antibiotic?")
        assert r.safety == "dangerous_or_medical"


class TestIntentClassification:
    def setup_method(self):
        self.tc = TriageClassifier(gateway=None)

    @pytest.mark.asyncio
    async def test_information_request(self):
        r = await self.tc.triage("What time does the lab open?")
        assert r.intent == "information_request"

    @pytest.mark.asyncio
    async def test_coding(self):
        r = await self.tc.triage("Write a Python function to reverse a string.")
        assert r.intent == "coding"

    @pytest.mark.asyncio
    async def test_navigation(self):
        r = await self.tc.triage("Where is Room 305?")
        assert r.intent == "navigation"

    @pytest.mark.asyncio
    async def test_social(self):
        r = await self.tc.triage("Hello, how are you?")
        assert r.intent == "social"

    @pytest.mark.asyncio
    async def test_reasoning(self):
        r = await self.tc.triage("Why does Pepper need a real-time loop?")
        assert r.intent == "reasoning"


class TestComplexityClassification:
    def setup_method(self):
        self.tc = TriageClassifier(gateway=None)

    @pytest.mark.asyncio
    async def test_simple_short(self):
        r = await self.tc.triage("Hi")
        assert r.complexity == "simple"

    @pytest.mark.asyncio
    async def test_complex_compare(self):
        r = await self.tc.triage("Compare GPT-4 and Claude for code generation.")
        assert r.complexity == "complex"

    @pytest.mark.asyncio
    async def test_reasoning_always_at_least_medium(self):
        r = await self.tc.triage("Why?")
        assert r.complexity in ("medium", "complex")


class TestRuleOnlyMode:
    """No gateway = no LLM escalation, method always rule_based."""

    @pytest.mark.asyncio
    async def test_method_always_rule_based(self):
        tc = TriageClassifier(gateway=None)
        for utt in ["Hi", "What is the wifi password?", "blah blah blah xyz"]:
            r = await tc.triage(utt)
            assert r.method == "rule_based"

    @pytest.mark.asyncio
    async def test_ambiguous_returns_ambiguous_intent(self):
        tc = TriageClassifier(gateway=None)
        r = await tc.triage("blah xyz qwerty")
        assert r.intent == "ambiguous"


class TestResultShape:
    @pytest.mark.asyncio
    async def test_result_has_all_fields(self):
        tc = TriageClassifier(gateway=None)
        r = await tc.triage("What time is it?")
        assert isinstance(r, TriageResult)
        assert r.intent in {
            "information_request", "coding", "navigation", "social",
            "reasoning", "general_chat", "dangerous_or_medical", "ambiguous",
        }
        assert r.complexity in {"simple", "medium", "complex"}
        assert r.safety in {"safe", "dangerous_or_medical", "ambiguous"}
        assert 0.0 <= r.confidence <= 1.0
        assert r.method in {"rule_based", "llm_escalated"}
        assert isinstance(r.reasoning, str)
