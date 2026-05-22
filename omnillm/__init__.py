"""OmniLLM — multi-LLM orchestration for the Sgorbissa HRI lab."""

__version__ = "0.2.0"
__author__ = "Akshita-sr"

from omnillm.gateway import LLMGateway, ModelResponse
from omnillm.evaluator import Evaluator, EvalResult, EvalTask
from omnillm.router import SmartRouter, RouteDecision, RoutingStrategy
from omnillm.scorer import EloScorer
from omnillm.consensus import ConsensusEngine, ConsensusConfig, ConsensusResult
from omnillm.rag import RAGPipeline, RAGResponse
from omnillm.hri import HRITaskClassifier, HRITaskType, LanguageDetector
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
    "RAGPipeline",
    "RAGResponse",
    "HRITaskClassifier",
    "HRITaskType",
    "LanguageDetector",
    "ExperimentLogger",
    "InteractionRecord",
    "GesturePlanner",
]
