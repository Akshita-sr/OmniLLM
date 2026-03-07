"""Tests for omnillm.consensus — Multi-Model Consensus Engine module."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from omnillm.consensus import ConsensusConfig, ConsensusEngine, ConsensusResult
from omnillm.gateway import LLMGateway, ModelResponse


def _make_gateway_with_responses(responses: dict[str, str]) -> MagicMock:
    """Create a mock gateway returning pre-defined responses per model."""
    gw = MagicMock(spec=LLMGateway)

    async def mock_query(model_id, messages, **kwargs):
        content = responses.get(model_id, f"Default response from {model_id}")
        return ModelResponse(model_id=model_id, content=content, latency_ms=100)

    async def mock_query_multiple(model_ids, messages, **kwargs):
        return [
            ModelResponse(
                model_id=mid,
                content=responses.get(mid, f"Response from {mid}"),
                latency_ms=100,
            )
            for mid in model_ids
        ]

    gw.query = AsyncMock(side_effect=mock_query)
    gw.query_multiple = AsyncMock(side_effect=mock_query_multiple)
    return gw


class TestConsensusConfig:
    """Tests for ConsensusConfig dataclass."""

    def test_default_values(self):
        config = ConsensusConfig(council_models=["model-a", "model-b"])
        assert config.judge_model == "openai-gpt4o"
        assert config.strategy == "synthesis"
        assert config.min_agreement == pytest.approx(0.6)

    def test_custom_values(self):
        config = ConsensusConfig(
            council_models=["model-a"],
            judge_model="claude-sonnet",
            strategy="majority_vote",
            min_agreement=0.8,
        )
        assert config.strategy == "majority_vote"
        assert config.min_agreement == pytest.approx(0.8)


class TestConsensusResult:
    """Tests for ConsensusResult dataclass."""

    def test_creation(self):
        result = ConsensusResult(
            final_answer="The answer is 42.",
            individual_responses=[],
            agreement_score=0.9,
            synthesis_reasoning="All models agreed.",
        )
        assert result.final_answer == "The answer is 42."
        assert result.agreement_score == pytest.approx(0.9)
        assert result.dissenting_models == []

    def test_with_dissenters(self):
        result = ConsensusResult(
            final_answer="42",
            individual_responses=[],
            agreement_score=0.66,
            synthesis_reasoning="2/3 models agreed.",
            dissenting_models=["model-c"],
        )
        assert "model-c" in result.dissenting_models


class TestConsensusEngine:
    """Tests for ConsensusEngine."""

    def test_init(self):
        gw = MagicMock(spec=LLMGateway)
        config = ConsensusConfig(council_models=["a", "b"])
        engine = ConsensusEngine(gw, config)
        assert engine.gateway is gw
        assert engine.config is config

    @pytest.mark.asyncio
    async def test_query_council_all_errors(self):
        """When all council models fail, should return error result."""
        gw = MagicMock(spec=LLMGateway)
        gw.query_multiple = AsyncMock(
            return_value=[
                ModelResponse(model_id="a", content="", error="Timeout"),
                ModelResponse(model_id="b", content="", error="Timeout"),
            ]
        )
        config = ConsensusConfig(
            council_models=["a", "b"],
            strategy="majority_vote",
        )
        engine = ConsensusEngine(gw, config)
        result = await engine.query_council([{"role": "user", "content": "hi"}])
        assert "error" in result.final_answer.lower()
        assert result.agreement_score == pytest.approx(0.0)

    @pytest.mark.asyncio
    async def test_majority_vote_single_response(self):
        gw = _make_gateway_with_responses({"model-a": "The answer is 4."})
        config = ConsensusConfig(
            council_models=["model-a"],
            strategy="majority_vote",
        )
        engine = ConsensusEngine(gw, config)
        result = await engine.query_council([{"role": "user", "content": "2+2?"}])
        assert result.agreement_score == pytest.approx(1.0)
        assert "4" in result.final_answer

    @pytest.mark.asyncio
    async def test_majority_vote_agreement(self):
        """Two models agree, one dissents — majority should win."""
        gw = _make_gateway_with_responses({
            "model-a": "The capital of France is Paris. It is a beautiful city.",
            "model-b": "Paris is the capital city of France, known for the Eiffel Tower.",
            "model-c": "I believe the capital is Lyon, not Paris.",
        })
        config = ConsensusConfig(
            council_models=["model-a", "model-b", "model-c"],
            strategy="majority_vote",
        )
        engine = ConsensusEngine(gw, config)
        result = await engine.query_council([{"role": "user", "content": "Capital of France?"}])
        assert isinstance(result, ConsensusResult)
        assert result.agreement_score > 0

    @pytest.mark.asyncio
    async def test_weighted_consensus(self):
        gw = _make_gateway_with_responses({
            "openai-gpt4o": "The answer is 42.",
            "claude-sonnet": "42 is the answer.",
        })
        config = ConsensusConfig(
            council_models=["openai-gpt4o", "claude-sonnet"],
            strategy="weighted",
        )
        engine = ConsensusEngine(gw, config)
        result = await engine.query_council([{"role": "user", "content": "What is 6x7?"}])
        assert isinstance(result, ConsensusResult)
        assert result.strategy_used == "weighted"
        assert "42" in result.final_answer

    @pytest.mark.asyncio
    async def test_synthesis_strategy_calls_judge(self):
        judge_content = json_synthesis_response()
        gw = _make_gateway_with_responses({
            "model-a": "The ball costs 5 cents.",
            "model-b": "The ball is $0.05.",
            "judge-model": judge_content,
        })

        # Override judge query to return synthesis
        async def mock_query(model_id, messages, **kwargs):
            if model_id == "judge-model":
                return ModelResponse(model_id="judge-model", content=judge_content)
            return ModelResponse(
                model_id=model_id,
                content=f"Answer from {model_id}",
            )

        gw.query = AsyncMock(side_effect=mock_query)

        config = ConsensusConfig(
            council_models=["model-a", "model-b"],
            judge_model="judge-model",
            strategy="synthesis",
        )
        engine = ConsensusEngine(gw, config)
        result = await engine.query_council([{"role": "user", "content": "bat and ball?"}])
        assert isinstance(result, ConsensusResult)
        assert result.strategy_used == "synthesis"

    @pytest.mark.asyncio
    async def test_synthesis_fallback_on_judge_error(self):
        """If judge fails, should fall back to first valid response."""
        gw = _make_gateway_with_responses({"model-a": "The answer is 42."})

        async def mock_query(model_id, messages, **kwargs):
            if model_id == "judge-model":
                return ModelResponse(model_id="judge-model", content="", error="Timeout")
            return ModelResponse(model_id=model_id, content="The answer is 42.")

        gw.query = AsyncMock(side_effect=mock_query)

        config = ConsensusConfig(
            council_models=["model-a"],
            judge_model="judge-model",
            strategy="synthesis",
        )
        engine = ConsensusEngine(gw, config)
        result = await engine.query_council([{"role": "user", "content": "6x7?"}])
        assert result.final_answer == "The answer is 42."

    def test_compute_agreement_score_identical(self):
        gw = MagicMock()
        engine = ConsensusEngine(gw, ConsensusConfig(council_models=["a"]))
        responses = [
            ModelResponse(model_id="a", content="Paris is the capital of France."),
            ModelResponse(model_id="b", content="Paris is the capital of France."),
        ]
        score = engine._compute_agreement_score(responses)
        assert score == pytest.approx(1.0)

    def test_compute_agreement_score_all_different(self):
        gw = MagicMock()
        engine = ConsensusEngine(gw, ConsensusConfig(council_models=["a"]))
        responses = [
            ModelResponse(model_id="a", content="aaaaaa bbbbbb cccccc"),
            ModelResponse(model_id="b", content="xxxxxx yyyyyy zzzzzz"),
            ModelResponse(model_id="c", content="pppppp qqqqqq rrrrrr"),
        ]
        score = engine._compute_agreement_score(responses)
        # Each response in its own cluster → largest is 1/3
        assert score == pytest.approx(1 / 3)

    def test_compute_agreement_score_empty(self):
        gw = MagicMock()
        engine = ConsensusEngine(gw, ConsensusConfig(council_models=[]))
        assert engine._compute_agreement_score([]) == pytest.approx(0.0)

    def test_compute_agreement_score_single(self):
        gw = MagicMock()
        engine = ConsensusEngine(gw, ConsensusConfig(council_models=["a"]))
        responses = [ModelResponse(model_id="a", content="hello")]
        assert engine._compute_agreement_score(responses) == pytest.approx(1.0)

    def test_jaccard_similarity_identical(self):
        assert ConsensusEngine._jaccard_similarity("hello world", "hello world") == pytest.approx(1.0)

    def test_jaccard_similarity_disjoint(self):
        score = ConsensusEngine._jaccard_similarity("aaa bbb", "ccc ddd")
        assert score == pytest.approx(0.0)

    def test_jaccard_similarity_partial(self):
        score = ConsensusEngine._jaccard_similarity("hello world foo", "hello bar baz")
        assert 0 < score < 1

    def test_jaccard_empty_strings(self):
        assert ConsensusEngine._jaccard_similarity("", "") == pytest.approx(1.0)

    def test_jaccard_one_empty(self):
        assert ConsensusEngine._jaccard_similarity("hello", "") == pytest.approx(0.0)


# ── Helper ────────────────────────────────────────────────────────────────────

def json_synthesis_response() -> str:
    import json
    return json.dumps({
        "final_answer": "The ball costs $0.05 (5 cents).",
        "agreement_score": 0.95,
        "reasoning": "Both models agree the ball costs 5 cents.",
        "dissenting_models": [],
    })
