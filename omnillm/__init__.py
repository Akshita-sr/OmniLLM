"""OmniLLM — Compare, Route, and Orchestrate Every LLM.

A living, plugin-based platform for multi-LLM comparison, smart routing,
consensus ensembles, and future robotics integration.
"""

__version__ = "0.1.0"
__author__ = "Akshita-sr"

from omnillm.gateway import LLMGateway, ModelResponse
from omnillm.evaluator import Evaluator, EvalResult, EvalTask
from omnillm.router import SmartRouter, RouteDecision, RoutingStrategy
from omnillm.scorer import EloScorer
from omnillm.consensus import ConsensusEngine, ConsensusConfig, ConsensusResult
from omnillm.rag import RAGPipeline, RAGResponse
from omnillm.hri import (
    HRITaskClassifier,
    HRITaskType,
    LanguageDetector,
    ExperimentCondition,
    ExperimentManager,
    ParticipantSession,
)
from omnillm.utils.experiment_logger import ExperimentLogger, InteractionRecord
from omnillm.robotics.gesture_planner import GesturePlanner

__all__ = [
    "LLMGateway",
    "ModelResponse",
    "Evaluator",
    "EvalResult",
    "EvalTask",
    "SmartRouter",
    "RouteDecision",
    "RoutingStrategy",
    "EloScorer",
    "ConsensusEngine",
    "ConsensusConfig",
    "ConsensusResult",
    # RAG pipeline
    "RAGPipeline",
    "RAGResponse",
    # HRI module
    "HRITaskClassifier",
    "HRITaskType",
    "LanguageDetector",
    "ExperimentCondition",
    "ExperimentManager",
    "ParticipantSession",
    # Utilities
    "ExperimentLogger",
    "InteractionRecord",
    # Robotics
    "GesturePlanner",
]
