"""Smart Model Router with multiple routing strategies.

The router learns from past evaluation results to automatically select the
best model for a given task type within user-defined budget and latency
constraints.

Routing strategies:

* **BEST_QUALITY** — pick the highest-scoring model regardless of cost.
* **LOWEST_COST** — pick the cheapest model that has acceptable quality.
* **LOWEST_LATENCY** — pick the fastest model (lowest measured latency).
* **BEST_VALUE** — balance quality, cost and latency with a composite score.
* **LOCAL_PREFERRED** — prefer locally-hosted models (zero cost) first.

Based on LiteLLM routing concepts:
  Simple-Shuffle, Least-Busy, Latency-Based, Usage-Based.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

import yaml

if TYPE_CHECKING:
    from omnillm.triage import TriageResult


# Ordinal ranking of triage complexity labels. Used by the autonomous router
# to honour the `complexity_council_threshold` YAML key with TRUE ≥ semantics
# (so threshold="medium" correctly escalates BOTH medium AND complex prompts
# to council, not just exact matches). Was a silent bug with `==` comparison.
_COMPLEXITY_ORDER: dict[str, int] = {"simple": 0, "medium": 1, "complex": 2}


class RoutingStrategy(str, Enum):
    """Available routing strategies for the :class:`SmartRouter`."""

    BEST_QUALITY = "BEST_QUALITY"
    LOWEST_COST = "LOWEST_COST"
    LOWEST_LATENCY = "LOWEST_LATENCY"
    BEST_VALUE = "BEST_VALUE"
    LOCAL_PREFERRED = "LOCAL_PREFERRED"
    TASK_TYPE = "TASK_TYPE"  # HRI: route by task category (T1–T4)


@dataclass
class StrategyDecision:
    """Output of :meth:`SmartRouter.route_autonomous` — the "LLM-OS kernel"
    decision for an incoming utterance.

    Attributes:
        strategy: Which answer pipeline to invoke
            (``"direct"``, ``"rag"``, or ``"council"``).
        primary_model: The first model to try for the ``direct`` / ``rag``
            paths. Ignored for ``council`` (the council reads its own
            ``council_models`` from ``models.yaml``).
        fallback_chain: Ordered list of models for
            :meth:`omnillm.gateway.LLMGateway.query_with_fallback`. Includes
            ``primary_model`` as the first entry.
        reason: Human-readable explanation of why this strategy was picked
            — for logs, metadata, and debugging.
    """

    strategy: Literal["direct", "rag", "council"]
    primary_model: str
    fallback_chain: list[str] = field(default_factory=list)
    reason: str = ""


@dataclass
class RouteDecision:
    """The output of a routing decision.

    Attributes:
        model_id: Selected model identifier.
        confidence: Router's confidence in this choice (0-1).
        reason: Human-readable explanation of why this model was selected.
        estimated_cost: Estimated cost in USD for a typical query.
        estimated_latency_ms: Estimated response latency in milliseconds.
        strategy_used: Which :class:`RoutingStrategy` produced this decision.
    """

    model_id: str
    confidence: float
    reason: str
    estimated_cost: float
    estimated_latency_ms: float
    strategy_used: RoutingStrategy


class SmartRouter:
    """Routes prompts to the optimal model based on strategy and constraints.

    The router maintains an internal score table that is updated from
    evaluation results.  On first use (or when no data is available) it falls
    back to static heuristics derived from the model registry.

    Example::

        router = SmartRouter()
        decision = router.route(
            task_category="reasoning",
            budget_usd=0.01,
            strategy=RoutingStrategy.BEST_VALUE,
        )
        print(decision.model_id, decision.reason)
    """

    # Default model scores (quality, latency_ms) when no eval data exists
    _DEFAULT_SCORES: dict[str, dict[str, float]] = {
        "openai-gpt4o": {"quality": 0.90, "latency_ms": 2500},
        "openai-o1": {"quality": 0.95, "latency_ms": 8000},
        "claude-3.5-sonnet": {"quality": 0.89, "latency_ms": 2200},
        "claude-3-opus": {"quality": 0.88, "latency_ms": 3500},
        "gemini-2-pro": {"quality": 0.85, "latency_ms": 2000},
        "gemini-1.5-flash": {"quality": 0.75, "latency_ms": 800},
        "google-studio-pro": {"quality": 0.84, "latency_ms": 2200},
        "deepseek-v3-cloud": {"quality": 0.82, "latency_ms": 2000},
        "deepseek-r1-cloud": {"quality": 0.87, "latency_ms": 4000},
        "qwen-2.5-72b": {"quality": 0.80, "latency_ms": 2500},
        "deepseek-r1-local": {"quality": 0.78, "latency_ms": 5000},
        "qwen-2.5-local": {"quality": 0.70, "latency_ms": 3000},
        "llama3-local": {"quality": 0.68, "latency_ms": 2500},
        "mistral-local": {"quality": 0.65, "latency_ms": 2000},
    }

    def __init__(
        self,
        results_path: str | Path | None = None,
        config_path: str | Path | None = None,
    ) -> None:
        """Initialise the router.

        Args:
            results_path: Optional path to a JSON file with past evaluation
                results.  Used to build the quality/latency score table.
            config_path: Path to ``models.yaml``.  Defaults to the standard
                location relative to this file.
        """
        if config_path is None:
            config_path = Path(__file__).parent.parent / "config" / "models.yaml"
        self._config_path = Path(config_path)
        self._models: dict[str, Any] = {}
        self._scores: dict[str, dict[str, dict[str, float]]] = {}
        # category -> model_id -> {quality, latency_ms, count}

        self._load_config()
        if results_path and Path(results_path).exists():
            self._load_results(Path(results_path))

    # ── Private helpers ──────────────────────────────────────────────────────

    def _load_config(self) -> None:
        with open(self._config_path, "r", encoding="utf-8") as fh:
            cfg = yaml.safe_load(fh)
        self._models = cfg.get("models", {})
        self._routing_cfg = cfg.get("routing", {})

    def _load_results(self, path: Path) -> None:
        """Parse evaluation results JSON to build quality/latency scores."""
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        for item in data:
            cat = item.get("category", "general")
            mid = item.get("model_id", "")
            score = float(item.get("score", 0.5))
            latency = float(item.get("latency_ms", 2000))
            if cat not in self._scores:
                self._scores[cat] = {}
            if mid not in self._scores[cat]:
                self._scores[cat][mid] = {"quality": 0.0, "latency_ms": 0.0, "count": 0}
            n = self._scores[cat][mid]["count"]
            self._scores[cat][mid]["quality"] = (
                self._scores[cat][mid]["quality"] * n + score
            ) / (n + 1)
            self._scores[cat][mid]["latency_ms"] = (
                self._scores[cat][mid]["latency_ms"] * n + latency
            ) / (n + 1)
            self._scores[cat][mid]["count"] = n + 1

    def _get_quality(self, model_id: str, category: str = "general") -> float:
        """Return the quality score for a model, falling back to defaults."""
        if category in self._scores and model_id in self._scores[category]:
            return self._scores[category][model_id]["quality"]
        return self._DEFAULT_SCORES.get(model_id, {}).get("quality", 0.5)

    def _get_latency(self, model_id: str, category: str = "general") -> float:
        """Return the estimated latency for a model (ms)."""
        if category in self._scores and model_id in self._scores[category]:
            return self._scores[category][model_id]["latency_ms"]
        return self._DEFAULT_SCORES.get(model_id, {}).get("latency_ms", 3000)

    def _get_cost_per_query(self, model_id: str, avg_tokens: int = 500) -> float:
        """Estimate cost for an average-length query."""
        cfg = self._models.get(model_id, {})
        cost_in = cfg.get("cost_per_1m_input", 0.0)
        cost_out = cfg.get("cost_per_1m_output", 0.0)
        # Assume 50% input, 50% output split
        return (avg_tokens / 2 * cost_in + avg_tokens / 2 * cost_out) / 1_000_000

    def _calculate_value_score(
        self, quality: float, cost: float, latency_ms: float
    ) -> float:
        """Composite value score balancing quality, cost, and latency.

        Higher is better.  Normalisation assumes typical ranges:
        quality ∈ [0,1], cost ∈ [0, 0.05], latency ∈ [500, 10000] ms.
        """
        # Normalise cost: 0 cost -> 1.0, 0.05 USD -> 0.0
        cost_score = max(0.0, 1.0 - cost / 0.05)
        # Normalise latency: 500ms -> 1.0, 10000ms -> 0.0
        latency_score = max(0.0, 1.0 - (latency_ms - 500) / 9500)
        # Weighted combination: quality 50%, cost 30%, latency 20%
        return 0.50 * quality + 0.30 * cost_score + 0.20 * latency_score

    # ── Public routing API ───────────────────────────────────────────────────

    def route(
        self,
        task_category: str = "general",
        budget_usd: float | None = None,
        max_latency_ms: float | None = None,
        strategy: RoutingStrategy = RoutingStrategy.BEST_VALUE,
    ) -> RouteDecision:
        """Select the best model for a task given constraints.

        Args:
            task_category: Evaluation axis / task type.
            budget_usd: Maximum cost per query in USD.  ``None`` = no limit.
            max_latency_ms: Maximum acceptable latency.  ``None`` = no limit.
            strategy: Which routing strategy to apply.

        Returns:
            :class:`RouteDecision` with the selected model and rationale.
        """
        candidates = list(self._models.keys())

        # Apply hard constraints
        if budget_usd is not None:
            candidates = [
                m for m in candidates
                if self._get_cost_per_query(m) <= budget_usd
            ]
        if max_latency_ms is not None:
            candidates = [
                m for m in candidates
                if self._get_latency(m, task_category) <= max_latency_ms
            ]

        # Fallback if constraints are too strict
        fallbacks = self._routing_cfg.get("fallback_models", ["openai-gpt4o"])
        if not candidates:
            candidates = [m for m in fallbacks if m in self._models]
        if not candidates:
            candidates = list(self._models.keys())[:1]

        # Apply strategy
        if strategy == RoutingStrategy.LOCAL_PREFERRED:
            local = [m for m in candidates if self._models[m].get("type") == "local"]
            if local:
                candidates = local
        elif strategy == RoutingStrategy.TASK_TYPE:
            # Prefer models with explicit hri_strengths for the task category
            hri_map = self._routing_cfg.get("hri_task_routing", {})
            preferred = hri_map.get(task_category)
            if preferred and preferred in self._models and preferred in candidates:
                candidates = [preferred]
            else:
                # Fall back to models that list this task as a strength
                strength_matches = [
                    m for m in candidates
                    if task_category in self._models[m].get("hri_strengths", [])
                ]
                if strength_matches:
                    candidates = strength_matches

        def _score(mid: str) -> float:
            q = self._get_quality(mid, task_category)
            c = self._get_cost_per_query(mid)
            lat = self._get_latency(mid, task_category)
            if strategy == RoutingStrategy.BEST_QUALITY:
                return q
            if strategy == RoutingStrategy.LOWEST_COST:
                return -c  # lower cost -> higher score
            if strategy == RoutingStrategy.LOWEST_LATENCY:
                return -lat
            if strategy in (
                RoutingStrategy.BEST_VALUE,
                RoutingStrategy.LOCAL_PREFERRED,
                RoutingStrategy.TASK_TYPE,
            ):
                return self._calculate_value_score(q, c, lat)
            return q

        best = max(candidates, key=_score)
        quality = self._get_quality(best, task_category)
        cost = self._get_cost_per_query(best)
        latency = self._get_latency(best, task_category)

        return RouteDecision(
            model_id=best,
            confidence=quality,
            reason=(
                f"Selected by {strategy.value} strategy "
                f"(quality={quality:.2f}, cost=${cost:.5f}, latency={latency:.0f}ms)"
            ),
            estimated_cost=cost,
            estimated_latency_ms=latency,
            strategy_used=strategy,
        )

    def route_by_complexity(
        self, prompt: str, budget_usd: float | None = None
    ) -> RouteDecision:
        """Route based on prompt complexity heuristic.

        Simple heuristic:
        - Short prompts (< 50 words) -> fast, cheap model
        - Long/complex prompts (≥ 50 words) -> powerful model

        Args:
            prompt: The user's prompt text.
            budget_usd: Optional budget constraint.

        Returns:
            :class:`RouteDecision`.
        """
        word_count = len(prompt.split())
        if word_count < 50:
            strategy = RoutingStrategy.LOWEST_COST
            task_category = "latency"
        else:
            strategy = RoutingStrategy.BEST_QUALITY
            task_category = "reasoning"

        return self.route(
            task_category=task_category,
            budget_usd=budget_usd,
            strategy=strategy,
        )

    def route_for_hri_task(
        self,
        hri_task_type: str,
        budget_usd: float | None = None,
        max_latency_ms: float | None = None,
    ) -> RouteDecision:
        """Route to the optimal model for an HRI task type (T1–T4).

        Maps task types from the Embodied LLM Arena experiment to the best model
        using the ``TASK_TYPE`` strategy and ``hri_task_routing`` config.

        HRI task types:
        - ``info_retrieval`` — T1: factual/RAG queries (lab info, personnel, schedule)
        - ``navigation`` — T2: spatial guidance (room directions, pointing)
        - ``social_conversation`` — T3: open-ended chat (empathy, naturalness)
        - ``multilingual`` — T4: non-English interaction (auto-detected language)

        Args:
            hri_task_type: One of ``"info_retrieval"``, ``"navigation"``,
                ``"social_conversation"``, or ``"multilingual"``.
            budget_usd: Optional per-query budget in USD.
            max_latency_ms: Optional maximum latency constraint.

        Returns:
            :class:`RouteDecision` targeting the HRI-optimal model.
        """
        return self.route(
            task_category=hri_task_type,
            budget_usd=budget_usd,
            max_latency_ms=max_latency_ms,
            strategy=RoutingStrategy.TASK_TYPE,
        )

    def route_autonomous(
        self,
        triage: "TriageResult",
        rag_available: bool = True,
    ) -> StrategyDecision:
        """Pick a strategy + model chain autonomously from a triage result.

        This is the "LLM-OS kernel" entry point — the pipeline calls this
        instead of the manual ``--council`` flag. Reads
        ``routing.autonomous_defaults`` from ``models.yaml`` so behaviour can
        be tuned without code changes.

        Decision rules (first match wins):

        1. Safety not safe -> ``council`` (judge gets a safety-aware prompt).
        2. Complexity ``complex`` -> ``council``.
        3. Intent ``coding`` -> ``direct`` with the BEST_QUALITY model.
        4. Intent ``reasoning`` -> ``direct`` with the reasoning model.
        5. Intent ``information_request`` / ``navigation`` -> ``rag`` if
           available, else ``direct``.
        6. Default (simple social / general chat) -> ``direct`` with the
           low-cost low-latency model.

        Args:
            triage: :class:`~omnillm.triage.TriageResult` from the classifier.
            rag_available: Whether the RAG pipeline is loaded for this server.

        Returns:
            :class:`StrategyDecision` consumed by the HRI pipeline.
        """
        defaults = self._routing_cfg.get("autonomous_defaults", {})

        simple_model = defaults.get("simple_model", "openai-gpt4o-mini")
        simple_fallback: list[str] = list(defaults.get("simple_fallback", []))
        coding_model = defaults.get("coding_model", "openai-gpt4o")
        reasoning_model = defaults.get("reasoning_model", "openai-gpt4o-mini")

        # Build a chain that always starts with the primary model.
        def _chain(primary: str) -> list[str]:
            tail = [m for m in simple_fallback if m != primary]
            return [primary, *tail]

        # Rule 1: safety wins.
        if triage.safety != "safe":
            return StrategyDecision(
                strategy="council",
                primary_model="",  # council uses its own list
                fallback_chain=[],
                reason=f"safety={triage.safety} -> mandatory council with safety-aware judge",
            )

        # Rule 2: complex -> council.
        # TRUE ≥ semantics via ordinal compare — threshold="medium" must
        # trigger on BOTH medium AND complex; threshold="complex" only on complex.
        threshold = defaults.get("complexity_council_threshold", "complex")
        triage_rank = _COMPLEXITY_ORDER.get(triage.complexity, 0)
        threshold_rank = _COMPLEXITY_ORDER.get(threshold, 2)
        if triage_rank >= threshold_rank:
            return StrategyDecision(
                strategy="council",
                primary_model="",
                fallback_chain=[],
                reason=f"complexity={triage.complexity} ≥ threshold ({threshold}) -> council",
            )

        # Rule 3: coding -> BEST_QUALITY direct.
        if triage.intent == "coding":
            return StrategyDecision(
                strategy="direct",
                primary_model=coding_model,
                fallback_chain=_chain(coding_model),
                reason=f"intent=coding -> BEST_QUALITY model ({coding_model})",
            )

        # Rule 4: reasoning -> reasoning model direct.
        if triage.intent == "reasoning":
            return StrategyDecision(
                strategy="direct",
                primary_model=reasoning_model,
                fallback_chain=_chain(reasoning_model),
                reason=f"intent=reasoning -> reasoning model ({reasoning_model})",
            )

        # Rule 5: info / navigation -> RAG if available.
        if triage.intent in ("information_request", "navigation"):
            if rag_available:
                return StrategyDecision(
                    strategy="rag",
                    primary_model=simple_model,
                    fallback_chain=_chain(simple_model),
                    reason=f"intent={triage.intent} + rag_available -> RAG with {simple_model}",
                )
            return StrategyDecision(
                strategy="direct",
                primary_model=simple_model,
                fallback_chain=_chain(simple_model),
                reason=f"intent={triage.intent}, no RAG -> direct with {simple_model}",
            )

        # Rule 6: default — simple social / general chat.
        return StrategyDecision(
            strategy="direct",
            primary_model=simple_model,
            fallback_chain=_chain(simple_model),
            reason=f"intent={triage.intent}, complexity={triage.complexity} -> low-cost {simple_model}",
        )

    def update_scores(self, eval_results: list[dict[str, Any]]) -> None:
        """Update internal quality/latency scores from new evaluation data.

        Args:
            eval_results: List of dicts with keys: ``model_id``, ``category``,
                ``score``, ``latency_ms``.
        """
        for item in eval_results:
            cat = item.get("category", "general")
            mid = item.get("model_id", "")
            if not mid:
                continue
            score = float(item.get("score", 0.5))
            latency = float(item.get("latency_ms", 2000))
            if cat not in self._scores:
                self._scores[cat] = {}
            if mid not in self._scores[cat]:
                self._scores[cat][mid] = {"quality": 0.0, "latency_ms": 0.0, "count": 0}
            n = self._scores[cat][mid]["count"]
            self._scores[cat][mid]["quality"] = (
                self._scores[cat][mid]["quality"] * n + score
            ) / (n + 1)
            self._scores[cat][mid]["latency_ms"] = (
                self._scores[cat][mid]["latency_ms"] * n + latency
            ) / (n + 1)
            self._scores[cat][mid]["count"] = n + 1
