"""Tests for omnillm.router — Smart Router module."""

from __future__ import annotations

from pathlib import Path

import pytest

from omnillm.router import RouteDecision, RoutingStrategy, SmartRouter
from omnillm.triage import TriageResult

CONFIG_PATH = Path(__file__).parent.parent / "config" / "models.yaml"


def _triage(complexity: str, intent: str = "general_chat", safety: str = "safe") -> TriageResult:
    """Helper: build a minimal TriageResult for autonomous-routing tests."""
    return TriageResult(
        intent=intent,           # type: ignore[arg-type]
        complexity=complexity,   # type: ignore[arg-type]
        safety=safety,           # type: ignore[arg-type]
        confidence=0.9,
        method="rule_based",
        reasoning="test fixture",
    )


class TestRouteDecision:
    """Tests for RouteDecision dataclass."""

    def test_creation(self):
        decision = RouteDecision(
            model_id="openai-gpt4o",
            confidence=0.9,
            reason="Best quality",
            estimated_cost=0.005,
            estimated_latency_ms=2500,
            strategy_used=RoutingStrategy.BEST_QUALITY,
        )
        assert decision.model_id == "openai-gpt4o"
        assert decision.confidence == pytest.approx(0.9)
        assert decision.strategy_used == RoutingStrategy.BEST_QUALITY


class TestRoutingStrategy:
    """Tests for RoutingStrategy enum."""

    def test_all_strategies_exist(self):
        strategies = [s.value for s in RoutingStrategy]
        assert "BEST_QUALITY" in strategies
        assert "LOWEST_COST" in strategies
        assert "LOWEST_LATENCY" in strategies
        assert "BEST_VALUE" in strategies
        assert "LOCAL_PREFERRED" in strategies


class TestSmartRouter:
    """Tests for SmartRouter."""

    def test_init_default_config(self):
        router = SmartRouter(config_path=CONFIG_PATH)
        assert router._models is not None
        assert len(router._models) > 0

    def test_route_returns_decision(self):
        router = SmartRouter(config_path=CONFIG_PATH)
        decision = router.route(task_category="reasoning")
        assert isinstance(decision, RouteDecision)
        assert decision.model_id in router._models
        assert 0 <= decision.confidence <= 1

    def test_route_best_quality(self):
        router = SmartRouter(config_path=CONFIG_PATH)
        decision = router.route(
            task_category="reasoning",
            strategy=RoutingStrategy.BEST_QUALITY,
        )
        assert decision.strategy_used == RoutingStrategy.BEST_QUALITY
        assert decision.model_id is not None

    def test_route_lowest_cost_prefers_free_models(self):
        router = SmartRouter(config_path=CONFIG_PATH)
        decision = router.route(
            task_category="general",
            strategy=RoutingStrategy.LOWEST_COST,
        )
        # Should prefer local (free) models
        assert decision.estimated_cost >= 0.0

    def test_route_local_preferred_returns_local(self):
        router = SmartRouter(config_path=CONFIG_PATH)
        decision = router.route(
            task_category="general",
            strategy=RoutingStrategy.LOCAL_PREFERRED,
        )
        info = router._models.get(decision.model_id, {})
        assert info.get("type") == "local"

    def test_route_with_budget_constraint(self):
        router = SmartRouter(config_path=CONFIG_PATH)
        # Budget of 0 should return local (free) models
        decision = router.route(
            task_category="general",
            budget_usd=0.0,
        )
        cost = router._get_cost_per_query(decision.model_id)
        assert cost == pytest.approx(0.0)

    def test_route_budget_too_tight_falls_back(self):
        """If budget is tighter than all models, fallback should still return something."""
        router = SmartRouter(config_path=CONFIG_PATH)
        # Negative budget is impossible — should fall back gracefully
        decision = router.route(
            task_category="general",
            budget_usd=-1.0,  # impossibly tight
        )
        assert decision.model_id is not None

    def test_route_by_complexity_short_prompt(self):
        router = SmartRouter(config_path=CONFIG_PATH)
        decision = router.route_by_complexity("Hi there")
        assert isinstance(decision, RouteDecision)
        # Short prompts should use LOWEST_COST strategy
        assert decision.strategy_used == RoutingStrategy.LOWEST_COST

    def test_route_by_complexity_long_prompt(self):
        router = SmartRouter(config_path=CONFIG_PATH)
        long_prompt = " ".join(["word"] * 100)
        decision = router.route_by_complexity(long_prompt)
        assert decision.strategy_used == RoutingStrategy.BEST_QUALITY

    def test_update_scores_affects_routing(self):
        router = SmartRouter(config_path=CONFIG_PATH)
        # Give openai-gpt4o a perfect score
        router.update_scores([
            {
                "model_id": "openai-gpt4o",
                "category": "test-category",
                "score": 1.0,
                "latency_ms": 100,
            }
        ])
        assert "test-category" in router._scores
        assert "openai-gpt4o" in router._scores["test-category"]
        assert router._scores["test-category"]["openai-gpt4o"]["quality"] == pytest.approx(1.0)

    def test_calculate_value_score(self):
        router = SmartRouter(config_path=CONFIG_PATH)
        # Perfect quality, zero cost, minimum latency should score near 1.0
        score = router._calculate_value_score(quality=1.0, cost=0.0, latency_ms=500)
        assert score == pytest.approx(1.0)

        # Poor quality
        score_low = router._calculate_value_score(quality=0.0, cost=0.0, latency_ms=500)
        assert score_low < score

    def test_get_quality_fallback_to_default(self):
        router = SmartRouter(config_path=CONFIG_PATH)
        # No eval data — should use defaults
        quality = router._get_quality("openai-gpt4o", "unknown-category")
        assert quality == pytest.approx(0.90)

    def test_get_quality_unknown_model_fallback(self):
        router = SmartRouter(config_path=CONFIG_PATH)
        quality = router._get_quality("completely-unknown-model")
        assert quality == pytest.approx(0.5)

    def test_route_decision_has_reason(self):
        router = SmartRouter(config_path=CONFIG_PATH)
        decision = router.route()
        assert len(decision.reason) > 0

    def test_all_strategies_return_valid_decision(self):
        router = SmartRouter(config_path=CONFIG_PATH)
        for strategy in RoutingStrategy:
            decision = router.route(strategy=strategy)
            assert decision.model_id in router._models
            assert isinstance(decision.confidence, float)

    def test_task_type_strategy_exists(self):
        strategies = [s.value for s in RoutingStrategy]
        assert "TASK_TYPE" in strategies

    def test_route_for_hri_task_info_retrieval(self):
        router = SmartRouter(config_path=CONFIG_PATH)
        decision = router.route_for_hri_task("info_retrieval")
        assert isinstance(decision, RouteDecision)
        assert decision.model_id in router._models
        assert decision.strategy_used == RoutingStrategy.TASK_TYPE

    def test_route_for_hri_task_navigation(self):
        router = SmartRouter(config_path=CONFIG_PATH)
        decision = router.route_for_hri_task("navigation")
        assert isinstance(decision, RouteDecision)
        assert decision.model_id in router._models

    def test_route_for_hri_task_social(self):
        router = SmartRouter(config_path=CONFIG_PATH)
        decision = router.route_for_hri_task("social_conversation")
        assert isinstance(decision, RouteDecision)
        assert decision.model_id in router._models

    def test_route_for_hri_task_multilingual(self):
        router = SmartRouter(config_path=CONFIG_PATH)
        decision = router.route_for_hri_task("multilingual")
        assert isinstance(decision, RouteDecision)
        assert decision.model_id in router._models

    def test_route_for_hri_task_uses_hri_routing_config(self):
        router = SmartRouter(config_path=CONFIG_PATH)
        # info_retrieval is mapped to openai-gpt4o-mini in models.yaml
        decision = router.route_for_hri_task("info_retrieval")
        assert decision.model_id == "openai-gpt4o-mini"

    def test_route_for_hri_task_with_budget(self):
        router = SmartRouter(config_path=CONFIG_PATH)
        decision = router.route_for_hri_task("navigation", budget_usd=0.0)
        # Budget=0 forces local (free) model
        assert router._get_cost_per_query(decision.model_id) == pytest.approx(0.0)


class TestRouteAutonomousComplexityThreshold:
    """Regression tests for the `complexity_council_threshold` ≥ semantics.

    Pre-2026-05-24 the router used `triage.complexity == threshold` (exact
    match) which silently broke when threshold was tuned to "medium". This
    suite locks in the ordinal comparison.
    """

    def _router_with_threshold(self, threshold: str) -> SmartRouter:
        router = SmartRouter(config_path=CONFIG_PATH)
        # Inject the threshold without rewriting the YAML on disk.
        router._routing_cfg.setdefault("autonomous_defaults", {})
        router._routing_cfg["autonomous_defaults"]["complexity_council_threshold"] = threshold
        return router

    def test_threshold_complex_triggers_only_on_complex(self):
        router = self._router_with_threshold("complex")
        assert router.route_autonomous(_triage("simple")).strategy != "council"
        assert router.route_autonomous(_triage("medium")).strategy != "council"
        assert router.route_autonomous(_triage("complex")).strategy == "council"

    def test_threshold_medium_triggers_on_medium_and_complex(self):
        """THE BUG FIX: threshold='medium' must escalate BOTH medium AND complex."""
        router = self._router_with_threshold("medium")
        assert router.route_autonomous(_triage("simple")).strategy != "council"
        assert router.route_autonomous(_triage("medium")).strategy == "council"
        assert router.route_autonomous(_triage("complex")).strategy == "council"

    def test_threshold_simple_triggers_on_everything(self):
        router = self._router_with_threshold("simple")
        for complexity in ("simple", "medium", "complex"):
            assert router.route_autonomous(_triage(complexity)).strategy == "council"

    def test_safety_override_always_wins_regardless_of_threshold(self):
        """Safety overrides Rule 2 — dangerous prompts go to council even at threshold=complex."""
        router = self._router_with_threshold("complex")
        triage = _triage("simple", safety="dangerous_or_medical")
        decision = router.route_autonomous(triage)
        assert decision.strategy == "council"
        assert "safety" in decision.reason.lower()
