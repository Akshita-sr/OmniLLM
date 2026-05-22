"""Gesture Planner for HRI task-to-action mapping on Pepper.

Maps HRI task types and response content to appropriate robot gestures,
creating the multimodal interaction required by the Embodied LLM Arena
study (Task T2 — Navigation/Guidance is particularly gesture-dependent).

Pepper's gesture vocabulary (NAOqi ALBehaviorManager):
- Greeting gestures: ``"wave"``, ``"bow"``
- Pointing gestures: ``"point_left"``, ``"point_right"``, ``"point_forward"``
- Explanatory gestures: ``"show_tablet"``, ``"nod"``, ``"think"``
- Farewell gestures: ``"wave_goodbye"``
- Neutral/default: ``"neutral"``

Usage::

    planner = GesturePlanner()
    gesture, led = planner.plan("navigation", "The lab is on your left.")
    print(gesture)   # "point_left"
    print(led)       # "#00AAFF"

    action = planner.plan_action(
        task_type="social_conversation",
        response_text="Hello! Nice to meet you.",
    )
    print(action.gesture)   # "wave"
    print(action.speech)    # "Hello! Nice to meet you."
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from omnillm.robotics.bridge import RobotAction


# ── Gesture library ───────────────────────────────────────────────────────────

#: Mapping from gesture name → LED colour (hex, Pepper eye LEDs)
GESTURE_LED_COLORS: dict[str, str] = {
    "wave": "#00FF88",          # Friendly green
    "bow": "#00FF88",
    "wave_goodbye": "#FF8800",  # Warm orange
    "point_left": "#00AAFF",    # Calm blue
    "point_right": "#00AAFF",
    "point_forward": "#00AAFF",
    "point_up": "#00AAFF",
    "show_tablet": "#FFFFFF",   # White (attention to tablet)
    "nod": "#00FF88",
    "think": "#FFFF00",         # Yellow (thinking)
    "neutral": "#44AAFF",       # Default blue
    "confused": "#FF4400",      # Red-orange
    "happy": "#00FF88",
}

#: Keyword patterns in responses that indicate a specific direction/gesture
_DIRECTION_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\bon (your |the )?(left|east)\b", re.IGNORECASE), "point_left"),
    (re.compile(r"\bon (your |the )?(right|west)\b", re.IGNORECASE), "point_right"),
    (re.compile(r"\b(straight ahead|in front|forward|north)\b", re.IGNORECASE), "point_forward"),
    (re.compile(r"\b(upstairs|above|floor \d+|level \d+)\b", re.IGNORECASE), "point_up"),
    (re.compile(r"\b(turn left)\b", re.IGNORECASE), "point_left"),
    (re.compile(r"\b(turn right)\b", re.IGNORECASE), "point_right"),
]

#: Task-type default gestures
_TASK_DEFAULT_GESTURES: dict[str, str] = {
    "info_retrieval": "nod",
    "navigation": "point_forward",
    "social_conversation": "wave",
    "multilingual": "nod",
    "reasoning": "think",
}

#: Response-content keyword triggers for gesture override
_CONTENT_GESTURE_MAP: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\b(hello|hi|hey|welcome|greet)\b", re.IGNORECASE), "wave"),
    (re.compile(r"\b(goodbye|bye|see you|farewell)\b", re.IGNORECASE), "wave_goodbye"),
    (re.compile(r"\b(show|look at|see (the |this )?(map|screen|tablet|display))\b", re.IGNORECASE), "show_tablet"),
    (re.compile(r"\b(thinking|let me check|processing)\b", re.IGNORECASE), "think"),
    (re.compile(r"\b(sorry|apologise|don't know|not sure|unclear)\b", re.IGNORECASE), "confused"),
    (re.compile(r"\b(absolutely|certainly|exactly|correct|yes)\b", re.IGNORECASE), "nod"),
]


class GesturePlanner:
    """Plans robot gestures for HRI interactions based on task type and response content.

    Implements the gesture-speech coordination required by the Embodied LLM Arena
    experiment, particularly for T2 (Navigation) tasks where Pepper must physically
    point in the direction of the requested destination.

    Example::

        planner = GesturePlanner()
        gesture, led = planner.plan("navigation", "Turn left at the end of the corridor.")
        print(gesture)  # "point_left"
    """

    def plan(
        self,
        task_type: str,
        response_text: str,
    ) -> tuple[str, str]:
        """Determine the appropriate gesture and LED colour for a response.

        Priority:
        1. Direction keywords in the response (navigation tasks)
        2. Response content keywords (greetings, farewells, uncertainty)
        3. Task-type default gesture

        Args:
            task_type: HRI task type (``"info_retrieval"``, ``"navigation"``,
                ``"social_conversation"``, or ``"multilingual"``).
            response_text: The LLM-generated response text.

        Returns:
            Tuple of ``(gesture_name, led_hex_colour)``.
        """
        # 1. Directional patterns override everything (most specific)
        if task_type == "navigation":
            for pattern, gesture in _DIRECTION_PATTERNS:
                if pattern.search(response_text):
                    led = GESTURE_LED_COLORS.get(gesture, "#00AAFF")
                    return gesture, led

        # 2. Content-based gesture keywords
        for pattern, gesture in _CONTENT_GESTURE_MAP:
            if pattern.search(response_text):
                led = GESTURE_LED_COLORS.get(gesture, "#44AAFF")
                return gesture, led

        # 3. Task-type default
        gesture = _TASK_DEFAULT_GESTURES.get(task_type, "neutral")
        led = GESTURE_LED_COLORS.get(gesture, "#44AAFF")
        return gesture, led

    def plan_action(
        self,
        task_type: str,
        response_text: str,
        tablet_url: str | None = None,
    ) -> "RobotAction":
        """Create a :class:`~omnillm.robotics.bridge.RobotAction` for a response.

        Combines gesture planning with speech and optional tablet display
        into a single action object for Pepper.

        Args:
            task_type: HRI task type.
            response_text: The LLM-generated response text (will be spoken aloud).
            tablet_url: Optional URL to display on Pepper's chest tablet
                (e.g. a map image for navigation tasks).

        Returns:
            :class:`~omnillm.robotics.bridge.RobotAction` ready to execute.
        """
        from omnillm.robotics.bridge import RobotAction

        gesture, led = self.plan(task_type, response_text)

        metadata: dict[str, object] = {"task_type": task_type}
        if tablet_url:
            metadata["tablet_url"] = tablet_url

        return RobotAction(
            speech=response_text,
            gesture=gesture,
            emotion_led=led,
            metadata=metadata,
        )

    def get_navigation_gesture(self, direction_hint: str) -> str:
        """Return the most appropriate pointing gesture for a direction hint.

        Args:
            direction_hint: Natural language direction (e.g. ``"left"``,
                ``"right"``, ``"straight ahead"``, ``"upstairs"``).

        Returns:
            Gesture name string.
        """
        direction_lower = direction_hint.lower()
        if any(w in direction_lower for w in ("left", "east")):
            return "point_left"
        if any(w in direction_lower for w in ("right", "west")):
            return "point_right"
        if any(w in direction_lower for w in ("up", "upstairs", "above")):
            return "point_up"
        return "point_forward"

    @staticmethod
    def list_gestures() -> list[str]:
        """Return all known gesture names.

        Returns:
            Sorted list of gesture name strings.
        """
        return sorted(GESTURE_LED_COLORS.keys())
