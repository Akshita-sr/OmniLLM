# -*- coding: utf-8 -*-
"""OmniLLM — multi-LLM orchestration for the Sgorbissa HRI lab.

Public API (what `from omnillm import ...` exposes):
  - LLMGateway, ModelResponse — the unified LLM call interface
  - SmartRouter, RouteDecision, RoutingStrategy, StrategyDecision — System 2 routing
  - TriageClassifier, TriageResult — System 1 fast classifier
  - ConsensusEngine, ConsensusConfig, ConsensusResult — multi-LLM council
  - RAGPipeline, RAGResponse — knowledge-base grounding
  - HRITaskClassifier, HRITaskType, LanguageDetector — HRI task + language helpers
  - ExperimentLogger, InteractionRecord — per-turn structured logging
  - GesturePlanner — text → gesture mapping for Pepper

The pre-pivot evaluation framework (Evaluator, EloScorer, CostTracker,
ResultExporter, the `omnillm` CLI) was removed in the 2026-05-22 refactor.
Its post-hoc scoring + ELO + cost rollup + CSV export is now in
[scripts/evaluate_session.py] — run that AFTER a recording session to
produce ML-ready CSV.
"""

__version__ = "0.2.0"
__author__ = "Akshita-sr"

from omnillm.gateway import LLMGateway, ModelResponse
from omnillm.router import SmartRouter, RouteDecision, RoutingStrategy, StrategyDecision
from omnillm.triage import TriageClassifier, TriageResult
from omnillm.consensus import ConsensusEngine, ConsensusConfig, ConsensusResult
from omnillm.rag import RAGPipeline, RAGResponse
from omnillm.hri import HRITaskClassifier, HRITaskType, LanguageDetector
from omnillm.utils.experiment_logger import ExperimentLogger, InteractionRecord
from omnillm.robotics.gesture_planner import GesturePlanner

__all__ = [
    "LLMGateway",
    "ModelResponse",
    "SmartRouter",
    "RouteDecision",
    "RoutingStrategy",
    "StrategyDecision",
    "TriageClassifier",
    "TriageResult",
    "ConsensusEngine",
    "ConsensusConfig",
    "ConsensusResult",
    "RAGPipeline",
    "RAGResponse",
    "HRITaskClassifier",
    "HRITaskType",
    "LanguageDetector",
    "ExperimentLogger",
    "InteractionRecord",
    "GesturePlanner",
]
