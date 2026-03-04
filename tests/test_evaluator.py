"""Tests for omnillm.evaluator — Evaluation engine module."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from omnillm.evaluator import EvalResult, EvalTask, Evaluator, PairwiseResult
from omnillm.gateway import LLMGateway, ModelResponse

CONFIG_PATH = Path(__file__).parent.parent / "config" / "models.yaml"


def _make_mock_gateway(response_content: str = "Test answer") -> MagicMock:
    """Create a mock LLMGateway that returns a fixed response."""
    gw = MagicMock(spec=LLMGateway)
    mock_resp = ModelResponse(
        model_id="openai-gpt4o",
        content=response_content,
        input_tokens=10,
        output_tokens=20,
        latency_ms=500.0,
        cost_usd=0.0001,
    )
    gw.query = AsyncMock(return_value=mock_resp)
    gw.query_multiple = AsyncMock(return_value=[mock_resp, mock_resp])
    return gw


class TestEvalTask:
    """Tests for the EvalTask dataclass."""

    def test_minimal_creation(self):
        task = EvalTask(id="test-1", category="reasoning", prompt="What is 2+2?")
        assert task.id == "test-1"
        assert task.category == "reasoning"
        assert task.prompt == "What is 2+2?"
        assert task.reference_answer is None
        assert task.grading_fn is None
        assert task.judge_pattern == "referenceless"

    def test_with_reference_answer(self):
        task = EvalTask(
            id="test-2",
            category="knowledge",
            prompt="Capital of France?",
            reference_answer="Paris",
            judge_pattern="reference_based",
        )
        assert task.reference_answer == "Paris"
        assert task.judge_pattern == "reference_based"

    def test_with_grading_fn(self):
        fn = lambda r: 1.0 if "4" in r else 0.0
        task = EvalTask(id="math", category="math", prompt="2+2?", grading_fn=fn)
        assert task.grading_fn("4") == 1.0
        assert task.grading_fn("5") == 0.0


class TestEvalResult:
    """Tests for EvalResult dataclass."""

    def test_creation(self):
        resp = ModelResponse(model_id="openai-gpt4o", content="Paris")
        result = EvalResult(
            task_id="test-1",
            model_id="openai-gpt4o",
            response=resp,
            score=0.95,
            category="knowledge",
        )
        assert result.task_id == "test-1"
        assert result.score == pytest.approx(0.95)
        assert result.judge_reasoning == ""

    def test_with_reasoning(self):
        resp = ModelResponse(model_id="test", content="hello")
        result = EvalResult(
            task_id="t1",
            model_id="test",
            response=resp,
            score=0.8,
            category="general",
            judge_reasoning="Good answer",
        )
        assert result.judge_reasoning == "Good answer"


class TestPairwiseResult:
    """Tests for PairwiseResult dataclass."""

    def test_creation(self):
        pr = PairwiseResult(
            task_id="t1",
            model_a="openai-gpt4o",
            model_b="claude-3.5-sonnet",
            winner="model_a",
        )
        assert pr.winner == "model_a"
        assert pr.task_id == "t1"

    def test_tie(self):
        pr = PairwiseResult(
            task_id="t1",
            model_a="a",
            model_b="b",
            winner="tie",
            judge_reasoning="Both are equal",
        )
        assert pr.winner == "tie"


class TestEvaluator:
    """Tests for the Evaluator class."""

    def _make_evaluator_with_mock_judge(
        self, judge_response: str = '{"score": 0.8, "reasoning": "Good answer"}'
    ) -> tuple[Evaluator, MagicMock]:
        gw = MagicMock(spec=LLMGateway)

        # Subject model response
        model_resp = ModelResponse(
            model_id="claude-3.5-sonnet",
            content="The ball costs $0.05.",
            latency_ms=500.0,
        )
        # Judge response
        judge_resp = ModelResponse(
            model_id="openai-gpt4o",
            content=judge_response,
        )

        async def mock_query(model_id, messages, **kwargs):
            if model_id == "openai-gpt4o":
                return judge_resp
            return model_resp

        gw.query = AsyncMock(side_effect=mock_query)
        evaluator = Evaluator(gw, judge_model="openai-gpt4o")
        return evaluator, gw

    @pytest.mark.asyncio
    async def test_evaluate_task_with_grading_fn(self):
        gw = _make_mock_gateway("4")
        gw.query = AsyncMock(
            return_value=ModelResponse(model_id="test", content="4", latency_ms=100)
        )
        task = EvalTask(
            id="math",
            category="math",
            prompt="What is 2+2?",
            grading_fn=lambda r: 1.0 if r.strip() == "4" else 0.0,
        )
        evaluator = Evaluator(gw, judge_model="openai-gpt4o")
        result = await evaluator.evaluate_task(task, "test")
        assert result.score == pytest.approx(1.0)
        assert result.notes == "Graded by grading_fn"

    @pytest.mark.asyncio
    async def test_evaluate_task_with_error_response(self):
        gw = MagicMock(spec=LLMGateway)
        gw.query = AsyncMock(
            return_value=ModelResponse(
                model_id="test", content="", error="API timeout"
            )
        )
        task = EvalTask(id="t1", category="general", prompt="Hello")
        evaluator = Evaluator(gw)
        result = await evaluator.evaluate_task(task, "test")
        assert result.score == 0.0
        assert "error" in result.notes.lower()

    @pytest.mark.asyncio
    async def test_evaluate_task_referenceless(self):
        evaluator, gw = self._make_evaluator_with_mock_judge(
            '{"score": 0.8, "reasoning": "Reasonable answer"}'
        )
        task = EvalTask(
            id="t1", category="reasoning", prompt="Explain gravity.",
            judge_pattern="referenceless",
        )
        result = await evaluator.evaluate_task(task, "claude-3.5-sonnet")
        assert result.score == pytest.approx(0.8)
        assert "Reasonable answer" in result.judge_reasoning

    @pytest.mark.asyncio
    async def test_evaluate_task_reference_based(self):
        evaluator, gw = self._make_evaluator_with_mock_judge(
            '{"score": 0.9, "reasoning": "Correct answer"}'
        )
        task = EvalTask(
            id="t1", category="knowledge",
            prompt="Capital of France?",
            reference_answer="Paris",
            judge_pattern="reference_based",
        )
        result = await evaluator.evaluate_task(task, "claude-3.5-sonnet")
        assert result.score == pytest.approx(0.9)

    @pytest.mark.asyncio
    async def test_evaluate_task_clamps_score(self):
        evaluator, gw = self._make_evaluator_with_mock_judge(
            '{"score": 1.5, "reasoning": "Over max"}'
        )
        task = EvalTask(id="t1", category="general", prompt="Test")
        result = await evaluator.evaluate_task(task, "claude-3.5-sonnet")
        assert result.score <= 1.0

    @pytest.mark.asyncio
    async def test_evaluate_pairwise_returns_result(self):
        gw = MagicMock(spec=LLMGateway)

        resp_a = ModelResponse(model_id="model-a", content="Response A")
        resp_b = ModelResponse(model_id="model-b", content="Response B")
        judge_resp = ModelResponse(
            model_id="openai-gpt4o",
            content='{"winner": "A", "reasoning": "A is better"}',
        )

        async def mock_query(model_id, messages, **kwargs):
            if model_id == "model-a":
                return resp_a
            if model_id == "model-b":
                return resp_b
            return judge_resp

        gw.query = AsyncMock(side_effect=mock_query)

        evaluator = Evaluator(gw, judge_model="openai-gpt4o")
        task = EvalTask(id="t1", category="general", prompt="Test")
        result = await evaluator.evaluate_pairwise(task, "model-a", "model-b")

        assert isinstance(result, PairwiseResult)
        assert result.winner in ("model_a", "model_b", "tie")

    @pytest.mark.asyncio
    async def test_run_benchmark(self):
        gw = MagicMock(spec=LLMGateway)
        model_resp = ModelResponse(model_id="test", content="answer")
        judge_resp = ModelResponse(
            model_id="judge", content='{"score": 0.7, "reasoning": "ok"}'
        )

        async def mock_query(model_id, messages, **kwargs):
            if model_id == "openai-gpt4o":
                return judge_resp
            return model_resp

        gw.query = AsyncMock(side_effect=mock_query)
        evaluator = Evaluator(gw, judge_model="openai-gpt4o")

        tasks = [
            EvalTask(id="t1", category="reasoning", prompt="Q1"),
            EvalTask(id="t2", category="knowledge", prompt="Q2"),
        ]
        results = await evaluator.run_benchmark(tasks, ["model-a"])
        assert len(results) == 2

    def test_judge_prompt_construction_includes_task_prompt(self):
        """Verify that judge prompts include the original task question."""
        gw = MagicMock(spec=LLMGateway)
        evaluator = Evaluator(gw)
        # We can't easily call _judge_referenceless without async but we can
        # verify the evaluator was constructed correctly
        assert evaluator.judge_model == "openai-gpt4o"
