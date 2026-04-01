"""Human-Robot Interaction (HRI) module for the Embodied LLM Arena experiment.

Provides the core components for running the multi-LLM HRI experiment with
Pepper robot:

- :class:`~omnillm.hri.classifier.HRITaskClassifier` — classifies utterances
  into one of four task types (T1–T4).
- :class:`~omnillm.hri.language_detector.LanguageDetector` — detects the
  language of a text input and maps it to the optimal LLM.
- :class:`~omnillm.hri.experiment.ExperimentManager` — manages experimental
  conditions (A–E), participant sessions, and data collection.

Experimental conditions:

+-----+-------------------+------------------------------------------+
| ID  | Name              | Description                              |
+=====+===================+==========================================+
| A   | Fixed Cloud LLM   | GPT-4o-mini for all tasks                |
+-----+-------------------+------------------------------------------+
| B   | Fixed Local LLM   | Llama3:8b (Ollama) for all tasks         |
+-----+-------------------+------------------------------------------+
| C   | Smart-Routed      | OmniLLM selects model per task type      |
+-----+-------------------+------------------------------------------+
| D   | Consensus         | 3-model council, best answer synthesised |
+-----+-------------------+------------------------------------------+
| E   | RAG-Off Control   | GPT-4o-mini without RAG grounding        |
+-----+-------------------+------------------------------------------+

HRI Task Types:

+----+----------------------+------------------------------------------+
| ID | Name                 | Example utterances                       |
+====+======================+==========================================+
| T1 | info_retrieval       | "What time does the lab open?"           |
+----+----------------------+------------------------------------------+
| T2 | navigation           | "Where is Room 305?"                     |
+----+----------------------+------------------------------------------+
| T3 | social_conversation  | "How are you?" / "Tell me something"     |
+----+----------------------+------------------------------------------+
| T4 | multilingual         | Any non-English utterance                |
+----+----------------------+------------------------------------------+
"""

from omnillm.hri.classifier import HRITaskClassifier, HRITaskType
from omnillm.hri.experiment import ExperimentCondition, ExperimentManager, ParticipantSession
from omnillm.hri.language_detector import LanguageDetector

# agent_graph is imported lazily (requires langgraph optional dependency)
# Use: from omnillm.hri.agent_graph import build_hri_graph, HRIGraphState

__all__ = [
    "HRITaskClassifier",
    "HRITaskType",
    "LanguageDetector",
    "ExperimentCondition",
    "ExperimentManager",
    "ParticipantSession",
    "build_hri_graph",
    "HRIGraphState",
]


def build_hri_graph(*args, **kwargs):  # type: ignore[misc]
    """Lazy import shim for :func:`~omnillm.hri.agent_graph.build_hri_graph`."""
    from omnillm.hri.agent_graph import build_hri_graph as _build
    return _build(*args, **kwargs)


def HRIGraphState(*args, **kwargs):  # type: ignore[misc]  # noqa: N802
    """Lazy import shim for :class:`~omnillm.hri.agent_graph.HRIGraphState`."""
    from omnillm.hri.agent_graph import HRIGraphState as _State
    return _State(*args, **kwargs)
