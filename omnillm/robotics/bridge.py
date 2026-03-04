"""Abstract Robot Bridge and shared data types.

This module defines the abstract interface that all robot integrations must
implement, plus shared data types for robot actions and sensor readings.

Architecture Overview
---------------------
The bridge pattern decouples the LLM layer from robot-specific SDKs:

    ┌──────────────────────────────────────────────────────────────────┐
    │                       OmniLLM Core                               │
    │  (LLMGateway / ConsensusEngine / SmartRouter)                    │
    └───────────────────────┬──────────────────────────────────────────┘
                            │  RobotAction / str (JSON)
                            ▼
    ┌──────────────────────────────────────────────────────────────────┐
    │                   RobotBridge (ABC)                              │
    │  parse_llm_to_action()  →  execute_action(RobotAction)          │
    └─────────┬────────────────┬───────────────────┬───────────────────┘
              │                │                   │
    ┌─────────▼──────┐ ┌───────▼──────┐ ┌─────────▼──────┐
    │  PepperBridge  │ │  NAOBridge   │ │  BuddyBridge   │
    │  (NAOqi/HTTP)  │ │  (NAOqi/HTTP)│ │  (WebSocket)   │
    └────────────────┘ └──────────────┘ └────────────────┘

Safety note
-----------
In robotics applications, incorrect LLM outputs can cause physical harm.
Always validate :class:`RobotAction` objects through the consensus engine
before executing on a real robot — a single-model hallucination should not
be enough to trigger robot movement.
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class RobotAction:
    """A structured action command for a robot.

    Attributes:
        speech: Text for the robot's text-to-speech system.
        gesture: Named gesture to perform (e.g. ``"wave"``, ``"bow"``).
        movement: Movement parameters as a dict
            (e.g. ``{"direction": "forward", "speed": 0.3, "distance_m": 1.0}``).
        emotion_led: LED colour for eye/body LEDs (hex colour code, e.g. ``"#00FF00"``).
        nav2_goal: ROS2 Nav2 goal pose dict with ``position`` and ``orientation``.
        metadata: Arbitrary additional parameters.
    """

    speech: str = ""
    gesture: str | None = None
    movement: dict[str, Any] | None = None
    emotion_led: str | None = None
    nav2_goal: dict[str, Any] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class RobotSensorData:
    """Sensor readings from a robot.

    Attributes:
        touch_sensors: Dict of touch sensor name → boolean (pressed or not).
        face_detected: Whether the robot's camera sees a human face.
        speech_detected: Transcribed speech from the robot's microphone.
        battery_level: Battery charge level as a fraction (0.0–1.0).
    """

    touch_sensors: dict[str, bool] = field(default_factory=dict)
    face_detected: bool = False
    speech_detected: str | None = None
    battery_level: float = 1.0


class RobotBridge(ABC):
    """Abstract base class for robot integrations.

    Subclasses must implement all abstract methods for a specific robot platform.
    All methods are coroutines to support non-blocking I/O.
    """

    @abstractmethod
    async def connect(self) -> bool:
        """Establish a connection to the robot.

        Returns:
            True if connected successfully, False otherwise.
        """
        ...

    @abstractmethod
    async def disconnect(self) -> bool:
        """Close the connection to the robot.

        Returns:
            True if disconnected cleanly, False otherwise.
        """
        ...

    @abstractmethod
    async def execute_action(self, action: RobotAction) -> bool:
        """Execute a :class:`RobotAction` on the robot.

        Args:
            action: The action to execute.

        Returns:
            True if the action completed successfully.
        """
        ...

    @abstractmethod
    async def get_sensor_data(self) -> RobotSensorData:
        """Read current sensor data from the robot.

        Returns:
            :class:`RobotSensorData` with current readings.
        """
        ...

    @abstractmethod
    async def say(self, text: str) -> bool:
        """Make the robot speak.

        Args:
            text: Text for TTS.

        Returns:
            True if speech completed.
        """
        ...

    @abstractmethod
    async def gesture(self, name: str) -> bool:
        """Trigger a named gesture.

        Args:
            name: Gesture name (robot-specific, e.g. ``"wave"``, ``"bow"``).

        Returns:
            True if gesture completed.
        """
        ...


# ── Utility functions ──────────────────────────────────────────────────────────

def parse_llm_to_action(llm_json_output: str) -> RobotAction:
    """Parse LLM-generated JSON into a :class:`RobotAction`.

    The LLM is expected to return JSON matching the :class:`RobotAction`
    schema.  Unknown fields are stored in ``metadata``.

    Args:
        llm_json_output: Raw JSON string from the LLM.

    Returns:
        Parsed :class:`RobotAction`.

    Raises:
        ValueError: If the JSON is invalid or does not contain a dict.
    """
    try:
        raw = llm_json_output.strip()
        # Strip Markdown code fences if present
        if raw.startswith("```"):
            lines = raw.split("\n")
            raw = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON from LLM: {exc}") from exc

    if not isinstance(data, dict):
        raise ValueError(f"Expected a JSON object, got {type(data).__name__}")

    known_keys = {"speech", "gesture", "movement", "emotion_led", "nav2_goal"}
    metadata = {k: v for k, v in data.items() if k not in known_keys}

    return RobotAction(
        speech=str(data.get("speech", "")),
        gesture=data.get("gesture"),
        movement=data.get("movement"),
        emotion_led=data.get("emotion_led"),
        nav2_goal=data.get("nav2_goal"),
        metadata=metadata,
    )


def parse_nav2_goal(llm_output: str) -> dict[str, Any]:
    """Parse LLM natural-language output into a ROS2 Nav2 goal pose.

    The LLM should output JSON with ``position`` (x, y, z) and
    ``orientation`` (x, y, z, w) keys.  This function validates and
    normalises the structure.

    Args:
        llm_output: LLM response that should contain a Nav2 goal JSON.

    Returns:
        Dict with ``position`` and ``orientation`` keys suitable for a
        ROS2 ``geometry_msgs/PoseStamped`` message.

    Raises:
        ValueError: If the JSON is invalid or missing required fields.
    """
    try:
        raw = llm_output.strip()
        if raw.startswith("```"):
            lines = raw.split("\n")
            raw = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON from LLM: {exc}") from exc

    # Handle array of poses — take the first
    if isinstance(data, list):
        data = data[0]

    if not isinstance(data, dict):
        raise ValueError(f"Expected a JSON object, got {type(data).__name__}")

    position = data.get("position", {})
    orientation = data.get("orientation", {})

    # Validate required fields
    for key in ("x", "y", "z"):
        if key not in position:
            raise ValueError(f"Nav2 goal missing position.{key}")

    for key in ("x", "y", "z", "w"):
        if key not in orientation:
            raise ValueError(f"Nav2 goal missing orientation.{key}")

    return {
        "position": {
            "x": float(position["x"]),
            "y": float(position["y"]),
            "z": float(position.get("z", 0.0)),
        },
        "orientation": {
            "x": float(orientation.get("x", 0.0)),
            "y": float(orientation.get("y", 0.0)),
            "z": float(orientation["z"]),
            "w": float(orientation["w"]),
        },
    }
