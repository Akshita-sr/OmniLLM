"""Evaluation Engine with three LLM-as-Judge patterns.

Implements the full evaluation pipeline described in the problem statement,
including three judge patterns from the LLM-as-Judge literature:

1. **Referenceless (G-Eval)** — judge evaluates the response on its own merits
   without a gold-standard reference answer.
2. **Reference-Based** — judge compares response to a provided reference answer
   to score accuracy and completeness.
3. **Pairwise** — judge compares two model responses head-to-head and declares
   a winner, with position-swapping to eliminate position bias.

References:
    - arXiv:2412.05579 "LLMs-as-Judges: A Comprehensive Survey"
    - LMSYS Chatbot Arena ELO methodology
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from typing import Any, Literal

from omnillm.gateway import LLMGateway, ModelResponse


@dataclass
class EvalTask:
    """A single evaluation task/prompt.

    Attributes:
        id: Unique task identifier.
        category: Evaluation axis (reasoning, knowledge, code, etc.).
        prompt: The question or instruction to send to the model.
        reference_answer: Optional gold-standard answer for reference-based judging.
        grading_fn: Optional callable ``(response: str) -> float`` for programmatic grading.
        judge_prompt: Optional additional instructions for the judge model.
        judge_pattern: Which LLM-as-judge pattern to use.
    """

    id: str
    category: str
    prompt: str
    reference_answer: str | None = None
    grading_fn: Any | None = None  # callable(response: str) -> float
    judge_prompt: str | None = None
    judge_pattern: Literal["referenceless", "reference_based", "pairwise"] = (
        "referenceless"
    )


@dataclass
class EvalResult:
    """Result of evaluating one model on one task.

    Attributes:
        task_id: ID of the :class:`EvalTask` that was evaluated.
        model_id: ID of the model that was evaluated.
        response: The full :class:`~omnillm.gateway.ModelResponse` from the model.
        score: Normalised score in [0, 1].
        category: Evaluation axis (copied from the task).
        judge_reasoning: Explanation from the judge LLM, if applicable.
        notes: Free-form notes about this evaluation.
    """

    task_id: str
    model_id: str
    response: ModelResponse
    score: float
    category: str
    judge_reasoning: str = ""
    notes: str = ""


@dataclass
class PairwiseResult:
    """Result of a head-to-head model comparison on a single task.

    Attributes:
        task_id: ID of the :class:`EvalTask`.
        model_a: First model ID.
        model_b: Second model ID.
        winner: ``"model_a"``, ``"model_b"``, or ``"tie"``.
        judge_reasoning: Explanation from the judge LLM.
    """

    task_id: str
    model_a: str
    model_b: str
    winner: Literal["model_a", "model_b", "tie"]
    judge_reasoning: str = ""


class Evaluator:
    """Orchestrates model evaluation using LLM-as-judge patterns.

    Example::

        gateway = LLMGateway()
        evaluator = Evaluator(gateway, judge_model="openai-gpt4o")

        task = EvalTask(
            id="bat-ball",
            category="reasoning",
            prompt="A bat and a ball cost $1.10...",
            reference_answer="$0.05",
            judge_pattern="reference_based",
        )
        result = await evaluator.evaluate_task(task, "claude-3.5-sonnet")
        print(result.score)
    """

    def __init__(
        self,
        gateway: LLMGateway,
        judge_model: str = "openai-gpt4o",
    ) -> None:
        """Initialise the evaluator.

        Args:
            gateway: Initialised :class:`~omnillm.gateway.LLMGateway` instance.
            judge_model: Model ID to use as the judge.  Should be a capable model
                (e.g. GPT-4o or Claude 3 Opus) for reliable evaluation.
        """
        self.gateway = gateway
        self.judge_model = judge_model

    # ── High-level public API ─────────────────────────────────────────────────

    async def evaluate_task(
        self, task: EvalTask, model_id: str
    ) -> EvalResult:
        """Evaluate a single model on a single task.

        Args:
            task: The evaluation task.
            model_id: Model to evaluate.

        Returns:
            :class:`EvalResult` with score, response, and judge reasoning.
        """
        messages = [{"role": "user", "content": task.prompt}]
        response = await self.gateway.query(model_id, messages)

        if response.is_error:
            return EvalResult(
                task_id=task.id,
                model_id=model_id,
                response=response,
                score=0.0,
                category=task.category,
                notes=f"Model error: {response.error}",
            )

        # Programmatic grading takes priority
        if task.grading_fn is not None:
            try:
                score = float(task.grading_fn(response.content))
                return EvalResult(
                    task_id=task.id,
                    model_id=model_id,
                    response=response,
                    score=min(max(score, 0.0), 1.0),
                    category=task.category,
                    notes="Graded by grading_fn",
                )
            except Exception as exc:  # noqa: BLE001
                return EvalResult(
                    task_id=task.id,
                    model_id=model_id,
                    response=response,
                    score=0.0,
                    category=task.category,
                    notes=f"grading_fn raised: {exc}",
                )

        # LLM-as-judge patterns
        if task.judge_pattern == "reference_based" and task.reference_answer:
            score, reasoning = await self._judge_reference_based(task, response)
        elif task.judge_pattern == "pairwise":
            # Pairwise requires two models; single-model eval falls back to referenceless
            score, reasoning = await self._judge_referenceless(task, response)
        else:
            score, reasoning = await self._judge_referenceless(task, response)

        return EvalResult(
            task_id=task.id,
            model_id=model_id,
            response=response,
            score=score,
            category=task.category,
            judge_reasoning=reasoning,
        )

    async def evaluate_pairwise(
        self, task: EvalTask, model_a: str, model_b: str
    ) -> PairwiseResult:
        """Compare two models head-to-head using position-swapped judging.

        To eliminate the well-known position bias in LLM judges (they tend to
        prefer the *first* response), we run the comparison twice with A and B
        swapped and take a consistent result.  If the two runs disagree, we
        declare a tie.

        Args:
            task: The evaluation task.
            model_a: First model ID.
            model_b: Second model ID.

        Returns:
            :class:`PairwiseResult` with winner and reasoning.
        """
        messages = [{"role": "user", "content": task.prompt}]
        resp_a, resp_b = await asyncio.gather(
            self.gateway.query(model_a, messages),
            self.gateway.query(model_b, messages),
        )

        # Run pairwise judge twice with swapped positions to cancel position bias
        winner_1, reasoning_1 = await self._judge_pairwise(
            task, resp_a, resp_b, swap=False
        )
        winner_2, reasoning_2 = await self._judge_pairwise(
            task, resp_a, resp_b, swap=True
        )

        # Combine the two runs
        if winner_1 == winner_2:
            final_winner: Literal["model_a", "model_b", "tie"] = winner_1
        else:
            final_winner = "tie"

        return PairwiseResult(
            task_id=task.id,
            model_a=model_a,
            model_b=model_b,
            winner=final_winner,
            judge_reasoning=f"Run 1: {reasoning_1}\nRun 2: {reasoning_2}",
        )

    async def run_benchmark(
        self,
        tasks: list[EvalTask],
        model_ids: list[str],
        max_concurrent: int = 5,
    ) -> list[EvalResult]:
        """Run a full benchmark: all tasks × all models.

        Uses :class:`asyncio.Semaphore` to limit concurrent API calls and avoid
        rate-limit errors.

        Args:
            tasks: List of evaluation tasks.
            model_ids: List of model IDs to benchmark.
            max_concurrent: Maximum simultaneous LLM calls.

        Returns:
            Flat list of :class:`EvalResult` objects.
        """
        semaphore = asyncio.Semaphore(max_concurrent)

        async def _limited(task: EvalTask, model_id: str) -> EvalResult:
            async with semaphore:
                return await self.evaluate_task(task, model_id)

        coros = [
            _limited(task, model_id)
            for task in tasks
            for model_id in model_ids
        ]
        results = await asyncio.gather(*coros)
        return list(results)

    # ── Judge implementations ─────────────────────────────────────────────────

    async def _judge_referenceless(
        self, task: EvalTask, response: ModelResponse
    ) -> tuple[float, str]:
        """G-Eval style: judge evaluates the response without a reference answer.

        Returns:
            Tuple of (score in [0,1], reasoning string).
        """
        extra = f"\n\nAdditional grading instructions:\n{task.judge_prompt}" if task.judge_prompt else ""

        prompt = (
            f"You are an expert evaluator. Evaluate the following AI response on a scale "
            f"from 0.0 to 1.0 where 1.0 is perfect.\n\n"
            f"**Original question:**\n{task.prompt}\n\n"
            f"**AI Response:**\n{response.content}\n\n"
            f"Evaluate for: accuracy, completeness, clarity, and helpfulness.{extra}\n\n"
            f"Respond ONLY with a valid JSON object in this exact format:\n"
            f'{{ "score": <float 0.0-1.0>, "reasoning": "<one-paragraph explanation>" }}'
        )

        return await self._call_judge(prompt)

    async def _judge_reference_based(
        self, task: EvalTask, response: ModelResponse
    ) -> tuple[float, str]:
        """Reference-based judge: compares response to the gold-standard answer.

        Returns:
            Tuple of (score in [0,1], reasoning string).
        """
        extra = f"\n\nScoring rubric:\n{task.judge_prompt}" if task.judge_prompt else ""

        prompt = (
            f"You are an expert evaluator. Score the AI's response by comparing it to "
            f"the reference answer. Score from 0.0 (wrong) to 1.0 (perfectly correct).\n\n"
            f"**Question:**\n{task.prompt}\n\n"
            f"**Reference Answer:**\n{task.reference_answer}\n\n"
            f"**AI Response:**\n{response.content}{extra}\n\n"
            f"Respond ONLY with a valid JSON object:\n"
            f'{{ "score": <float 0.0-1.0>, "reasoning": "<explanation>" }}'
        )

        return await self._call_judge(prompt)

    async def _judge_pairwise(
        self,
        task: EvalTask,
        response_a: ModelResponse,
        response_b: ModelResponse,
        swap: bool = False,
    ) -> tuple[Literal["model_a", "model_b", "tie"], str]:
        """Pairwise judge: pick the better of two responses.

        Args:
            task: The evaluation task.
            response_a: First model's response.
            response_b: Second model's response.
            swap: If True, present B before A in the prompt (position-swap).

        Returns:
            Tuple of (winner label, reasoning string).
        """
        if swap:
            first_content = response_b.content
            second_content = response_a.content
            first_label = "Response B"
            second_label = "Response A"
        else:
            first_content = response_a.content
            second_content = response_b.content
            first_label = "Response A"
            second_label = "Response B"

        prompt = (
            f"You are an expert judge. Compare two AI responses and pick the better one.\n\n"
            f"**Question:**\n{task.prompt}\n\n"
            f"**{first_label}:**\n{first_content}\n\n"
            f"**{second_label}:**\n{second_content}\n\n"
            f'Respond ONLY with JSON: {{ "winner": "A" | "B" | "tie", "reasoning": "<explanation>" }}'
        )

        messages = [{"role": "user", "content": prompt}]
        judge_response = await self.gateway.query(self.judge_model, messages, temperature=0.0)

        try:
            raw = judge_response.content.strip()
            # Extract JSON if wrapped in markdown
            if "```" in raw:
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            data = json.loads(raw)
            raw_winner = str(data.get("winner", "tie")).upper()
            reasoning = str(data.get("reasoning", ""))

            if swap:
                # Un-swap: if judge said A wins but we presented B first, actual winner is B
                if raw_winner == "A":
                    winner: Literal["model_a", "model_b", "tie"] = "model_b"
                elif raw_winner == "B":
                    winner = "model_a"
                else:
                    winner = "tie"
            else:
                if raw_winner == "A":
                    winner = "model_a"
                elif raw_winner == "B":
                    winner = "model_b"
                else:
                    winner = "tie"

            return winner, reasoning
        except (json.JSONDecodeError, KeyError):
            return "tie", f"Judge parse error: {judge_response.content[:200]}"

    async def _call_judge(self, prompt: str) -> tuple[float, str]:
        """Send a scoring prompt to the judge model and parse the JSON response.

        Returns:
            Tuple of (score in [0,1], reasoning string).
        """
        messages = [{"role": "user", "content": prompt}]
        response = await self.gateway.query(self.judge_model, messages, temperature=0.0)

        if response.is_error:
            return 0.5, f"Judge error: {response.error}"

        try:
            raw = response.content.strip()
            if "```" in raw:
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            data = json.loads(raw)
            score = float(data.get("score", 0.5))
            reasoning = str(data.get("reasoning", ""))
            return min(max(score, 0.0), 1.0), reasoning
        except (json.JSONDecodeError, ValueError, KeyError):
            # Fall back: look for a float in the response
            import re

            match = re.search(r"\b([01](?:\.\d+)?|\d*\.\d+)\b", response.content)
            if match:
                score = float(match.group(1))
                return min(max(score, 0.0), 1.0), response.content[:500]
            return 0.5, f"Could not parse judge response: {response.content[:200]}"
