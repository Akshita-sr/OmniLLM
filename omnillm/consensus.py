"""Multi-Model Consensus Engine — The 'LLM Council' Architecture.

Instead of picking one best model, this module dispatches prompts to multiple
models simultaneously and synthesises a superior combined answer.  This
approach is inspired by:

- arXiv:2601.07245 "Learning to Trust the Crowd: Multi-Model Consensus
  Reasoning Engine"
- Andrej Karpathy's "LLM Council" concept
- MDPI "Multiple Large AI Models' Consensus for Object Detection"

The pipeline has four phases:

1. **Broadcaster** — Send the prompt to all council models via the LiteLLM
   gateway concurrently.
2. **Independent Generation** — Each model responds without seeing the others'
   answers.
3. **Consensus Analysis** — Compute semantic similarity between responses,
   identify agreement clusters, and detect dissenting views.
4. **Final Verdict** — A judge LLM synthesises the best combined answer, or
   the majority-vote cluster is selected.

Benefits over single-model approaches:
- Dramatically reduces hallucinations (errors in minority are filtered out)
- Improves calibration (uncertainty is surfaced when models disagree)
- Provides richer reasoning by combining diverse model "perspectives"
- Critical for robotics: consensus prevents dangerous hallucinated actions
"""

from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass, field
from typing import Literal

from omnillm.gateway import LLMGateway, ModelResponse


@dataclass
class ConsensusConfig:
    """Configuration for a Consensus Engine run.

    Attributes:
        council_models: List of model IDs to query.
        judge_model: Model used to synthesise the final answer.
        strategy: How to combine responses.
        min_agreement: Minimum fraction of models that must agree (0-1).
            Used to flag low-confidence results.
    """

    council_models: list[str]
    judge_model: str = "openai-gpt4o"
    strategy: Literal["majority_vote", "weighted", "synthesis"] = "synthesis"
    min_agreement: float = 0.6


@dataclass
class ConsensusResult:
    """The output of a consensus run.

    Attributes:
        final_answer: The synthesised or majority-vote answer.
        individual_responses: Raw responses from all council members.
        agreement_score: Fraction of responses in the majority cluster (0-1).
        synthesis_reasoning: Judge's explanation of how the answer was formed.
        dissenting_models: Models whose responses were in the minority cluster.
        strategy_used: Which consensus strategy was applied.
    """

    final_answer: str
    individual_responses: list[ModelResponse]
    agreement_score: float
    synthesis_reasoning: str
    dissenting_models: list[str] = field(default_factory=list)
    strategy_used: str = "synthesis"


class ConsensusEngine:
    """Multi-Model Consensus Engine — query a council, synthesise a verdict.

    Example::

        gateway = LLMGateway()
        config = ConsensusConfig(
            council_models=["openai-gpt4o", "claude-3.5-sonnet", "gemini-2-pro"],
            judge_model="openai-gpt4o",
            strategy="synthesis",
        )
        engine = ConsensusEngine(gateway, config)
        result = await engine.query_council(
            [{"role": "user", "content": "What is 2+2?"}]
        )
        print(result.final_answer)
        print(f"Agreement: {result.agreement_score:.0%}")
    """

    def __init__(self, gateway: LLMGateway, config: ConsensusConfig) -> None:
        """Initialise the consensus engine.

        Args:
            gateway: Initialised :class:`~omnillm.gateway.LLMGateway`.
            config: :class:`ConsensusConfig` specifying council and strategy.
        """
        self.gateway = gateway
        self.config = config

    # ── Public API ────────────────────────────────────────────────────────────

    async def query_council(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
    ) -> ConsensusResult:
        """Run the full consensus pipeline.

        Phase 1: Query all council models concurrently.
        Phase 2: Analyse responses (similarity, agreement score).
        Phase 3: Apply the configured consensus strategy.

        Args:
            messages: OpenAI-style message list to send to all models.
            temperature: Sampling temperature for council members.

        Returns:
            :class:`ConsensusResult` with final answer and metadata.
        """
        # Phase 1: Broadcast to all council models
        responses = await self.gateway.query_multiple(
            self.config.council_models, messages, temperature=temperature
        )

        # Filter out errors (but keep track for transparency)
        valid = [r for r in responses if not r.is_error]
        if not valid:
            return ConsensusResult(
                final_answer="All council models returned errors.",
                individual_responses=responses,
                agreement_score=0.0,
                synthesis_reasoning="No valid responses from council.",
            )

        # Phase 3: Apply strategy
        if self.config.strategy == "majority_vote":
            return await self._majority_vote(valid, responses)
        if self.config.strategy == "weighted":
            return await self._weighted_consensus(valid, responses)
        # Default: synthesis
        return await self._synthesis(valid, messages, responses)

    # ── Consensus strategies ──────────────────────────────────────────────────

    async def _majority_vote(
        self,
        valid_responses: list[ModelResponse],
        all_responses: list[ModelResponse],
    ) -> ConsensusResult:
        """Semantic majority vote: cluster responses, pick the largest cluster.

        Uses word-level Jaccard similarity as a lightweight proxy for
        semantic similarity — no external embedding model required.

        Args:
            valid_responses: Non-error council responses.
            all_responses: All responses (including errors).

        Returns:
            :class:`ConsensusResult` with the majority-cluster representative.
        """
        if len(valid_responses) == 1:
            return ConsensusResult(
                final_answer=valid_responses[0].content,
                individual_responses=all_responses,
                agreement_score=1.0,
                synthesis_reasoning="Only one valid council member responded.",
                strategy_used="majority_vote",
            )

        # Build similarity matrix and find majority cluster
        clusters: list[list[ModelResponse]] = []
        threshold = 0.15  # Jaccard similarity threshold

        for resp in valid_responses:
            placed = False
            for cluster in clusters:
                if self._jaccard_similarity(resp.content, cluster[0].content) >= threshold:
                    cluster.append(resp)
                    placed = True
                    break
            if not placed:
                clusters.append([resp])

        majority_cluster = max(clusters, key=len)
        agreement = len(majority_cluster) / len(valid_responses)

        # Pick the longest response in the majority cluster as representative
        best = max(majority_cluster, key=lambda r: len(r.content))

        dissenting = [
            r.model_id
            for cluster in clusters
            if cluster is not majority_cluster
            for r in cluster
        ]

        return ConsensusResult(
            final_answer=best.content,
            individual_responses=all_responses,
            agreement_score=agreement,
            synthesis_reasoning=(
                f"Majority vote: {len(majority_cluster)}/{len(valid_responses)} models agreed. "
                f"Largest cluster representative selected."
            ),
            dissenting_models=dissenting,
            strategy_used="majority_vote",
        )

    async def _weighted_consensus(
        self,
        valid_responses: list[ModelResponse],
        all_responses: list[ModelResponse],
    ) -> ConsensusResult:
        """Weight council responses by model quality (static weights).

        In a full production system, weights would come from the ELO scorer.
        Here we use a simple static quality mapping.

        Args:
            valid_responses: Non-error council responses.
            all_responses: All responses.

        Returns:
            :class:`ConsensusResult`.
        """
        # Static quality weights — in production, use EloScorer ratings
        _WEIGHTS: dict[str, float] = {
            "openai-gpt4o": 0.90,
            "openai-o1": 0.95,
            "claude-3.5-sonnet": 0.89,
            "claude-3-opus": 0.88,
            "gemini-2-pro": 0.85,
            "gemini-1.5-flash": 0.75,
            "deepseek-v3-cloud": 0.82,
            "deepseek-r1-cloud": 0.87,
        }

        best_resp = max(
            valid_responses,
            key=lambda r: _WEIGHTS.get(r.model_id, 0.70),
        )
        best_weight = _WEIGHTS.get(best_resp.model_id, 0.70)
        total_weight = sum(_WEIGHTS.get(r.model_id, 0.70) for r in valid_responses)
        agreement = best_weight / total_weight if total_weight > 0 else 1.0

        return ConsensusResult(
            final_answer=best_resp.content,
            individual_responses=all_responses,
            agreement_score=min(agreement, 1.0),
            synthesis_reasoning=(
                f"Weighted consensus: {best_resp.model_id} had highest weight "
                f"({best_weight:.2f}). Used its response."
            ),
            dissenting_models=[
                r.model_id for r in valid_responses if r.model_id != best_resp.model_id
            ],
            strategy_used="weighted",
        )

    async def _synthesis(
        self,
        valid_responses: list[ModelResponse],
        original_messages: list[dict[str, str]],
        all_responses: list[ModelResponse],
    ) -> ConsensusResult:
        """Use a judge LLM to synthesise the best answer from all council responses.

        This is the most powerful strategy.  The judge sees all council answers
        and produces a final response that combines their best elements.

        Args:
            valid_responses: Non-error council responses.
            original_messages: The original prompt sent to the council.
            all_responses: All responses (for result metadata).

        Returns:
            :class:`ConsensusResult` with synthesised answer.
        """
        original_prompt = original_messages[-1].get("content", "") if original_messages else ""

        council_section = "\n\n".join(
            f"### {r.model_id}\n{r.content}" for r in valid_responses
        )

        synthesis_prompt = (
            f"You are a synthesis judge reviewing multiple AI responses to a question. "
            f"Your job is to produce the BEST possible answer by combining insights from all responses.\n\n"
            f"**Original Question:**\n{original_prompt}\n\n"
            f"**Council Responses:**\n{council_section}\n\n"
            f"Instructions:\n"
            f"1. Identify areas of agreement across responses (these are likely correct)\n"
            f"2. Note any disagreements or unique insights\n"
            f"3. Synthesise a final answer that is more accurate and complete than any individual response\n\n"
            f"Respond with valid JSON:\n"
            f'{{"final_answer": "<synthesised answer>", "agreement_score": <0.0-1.0>, '
            f'"reasoning": "<how you combined the responses>", '
            f'"dissenting_models": ["<model_id if it disagreed>", ...]}}'
        )

        judge_messages = [{"role": "user", "content": synthesis_prompt}]
        judge_response = await self.gateway.query(
            self.config.judge_model, judge_messages, temperature=0.0
        )

        if judge_response.is_error:
            # Fallback to best valid response
            fallback = valid_responses[0]
            return ConsensusResult(
                final_answer=fallback.content,
                individual_responses=all_responses,
                agreement_score=self._compute_agreement_score(valid_responses),
                synthesis_reasoning=f"Judge failed ({judge_response.error}). Using first valid response.",
                strategy_used="synthesis",
            )

        try:
            raw = judge_response.content.strip()
            if "```" in raw:
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            data = json.loads(raw)
            return ConsensusResult(
                final_answer=str(data.get("final_answer", valid_responses[0].content)),
                individual_responses=all_responses,
                agreement_score=float(data.get("agreement_score", 0.5)),
                synthesis_reasoning=str(data.get("reasoning", "")),
                dissenting_models=list(data.get("dissenting_models", [])),
                strategy_used="synthesis",
            )
        except (json.JSONDecodeError, KeyError, ValueError):
            # Fallback: use judge's raw response as-is
            return ConsensusResult(
                final_answer=judge_response.content,
                individual_responses=all_responses,
                agreement_score=self._compute_agreement_score(valid_responses),
                synthesis_reasoning="(Raw synthesis — JSON parse failed)",
                strategy_used="synthesis",
            )

    # ── Utility methods ───────────────────────────────────────────────────────

    def _compute_agreement_score(self, responses: list[ModelResponse]) -> float:
        """Estimate agreement as the fraction of responses in the largest cluster.

        Uses Jaccard similarity to cluster responses without requiring an
        embedding model.

        Args:
            responses: List of model responses to compare.

        Returns:
            Float in [0, 1] — fraction of models in the majority cluster.
        """
        if not responses:
            return 0.0
        if len(responses) == 1:
            return 1.0

        clusters: list[list[ModelResponse]] = []
        threshold = 0.15

        for resp in responses:
            placed = False
            for cluster in clusters:
                if self._jaccard_similarity(resp.content, cluster[0].content) >= threshold:
                    cluster.append(resp)
                    placed = True
                    break
            if not placed:
                clusters.append([resp])

        majority_size = max(len(c) for c in clusters)
        return majority_size / len(responses)

    @staticmethod
    def _jaccard_similarity(text_a: str, text_b: str) -> float:
        """Compute word-level Jaccard similarity between two texts.

        Args:
            text_a: First text.
            text_b: Second text.

        Returns:
            Float in [0, 1] — proportion of shared unique words.
        """
        def tokenise(text: str) -> set[str]:
            return set(re.findall(r"\b\w+\b", text.lower()))

        tokens_a = tokenise(text_a)
        tokens_b = tokenise(text_b)
        if not tokens_a and not tokens_b:
            return 1.0
        if not tokens_a or not tokens_b:
            return 0.0
        intersection = tokens_a & tokens_b
        union = tokens_a | tokens_b
        return len(intersection) / len(union)
