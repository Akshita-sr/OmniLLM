"""Tasks package for OmniLLM.

Provides built-in sample evaluation tasks and YAML/JSON task loaders.
"""

from omnillm.tasks.sample_tasks import (
    ALL_TASKS,
    TASKS_BY_CATEGORY,
    REASONING_TASKS,
    KNOWLEDGE_TASKS,
    CODE_TASKS,
    INSTRUCTION_TASKS,
    SAFETY_TASKS,
    ROBOT_TASKS,
    LATENCY_TASKS,
    COST_TASKS,
)
from omnillm.tasks.loader import TaskLoader

__all__ = [
    "ALL_TASKS",
    "TASKS_BY_CATEGORY",
    "REASONING_TASKS",
    "KNOWLEDGE_TASKS",
    "CODE_TASKS",
    "INSTRUCTION_TASKS",
    "SAFETY_TASKS",
    "ROBOT_TASKS",
    "LATENCY_TASKS",
    "COST_TASKS",
    "TaskLoader",
]
