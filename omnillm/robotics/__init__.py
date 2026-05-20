"""Robotics integration package for OmniLLM.

Provides abstract bridge interface and concrete implementations for:
- Pepper robot (NAOqi, Python 2.7 -> 3.x bridge)
- Gesture Planner for task-to-action mapping (Embodied LLM Arena)
"""

from omnillm.robotics.bridge import (
    RobotAction,
    RobotBridge,
    RobotSensorData,
    parse_llm_to_action,
    parse_nav2_goal,
)
from omnillm.robotics.pepper import (
    PepperBridge,
    discover_choregraphe_port,
    make_pepper_bridge,
)
from omnillm.robotics.gesture_planner import GesturePlanner

__all__ = [
    "RobotAction",
    "RobotBridge",
    "RobotSensorData",
    "parse_llm_to_action",
    "parse_nav2_goal",
    "PepperBridge",
    "discover_choregraphe_port",
    "make_pepper_bridge",
    "GesturePlanner",
]
