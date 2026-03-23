"""Robotics integration package for OmniLLM.

Provides abstract bridge interface and concrete implementations for:
- Pepper robot (NAOqi, Python 2.7→3.x bridge)
- NAO robot (NAOqi, Python 2.7→3.x bridge)
- Buddy robot (Android WebSocket)
- Gesture Planner for task-to-action mapping (Embodied LLM Arena)
"""

from omnillm.robotics.bridge import (
    RobotAction,
    RobotBridge,
    RobotSensorData,
    parse_llm_to_action,
    parse_nav2_goal,
)
from omnillm.robotics.pepper import PepperBridge
from omnillm.robotics.nao import NAOBridge
from omnillm.robotics.buddy import BuddyBridge
from omnillm.robotics.gesture_planner import GesturePlanner

__all__ = [
    "RobotAction",
    "RobotBridge",
    "RobotSensorData",
    "parse_llm_to_action",
    "parse_nav2_goal",
    "PepperBridge",
    "NAOBridge",
    "BuddyBridge",
    "GesturePlanner",
]
