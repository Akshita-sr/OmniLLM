"""Pepper Robot Bridge — NAOqi SDK integration.

Architecture — Python 2.7 ↔ Python 3.x Server Bridge
------------------------------------------------------
NAOqi (the Pepper/NAO SDK) is locked to Python 2.7, but modern AI stacks
require Python 3.11+.  This bridge implements the following two-process
architecture (based on: Theseus thesis, NAO/Pepper LLM integration):

    ┌────────────────────────────────────────────────────────────────┐
    │  Pepper Robot (Python 2.7 process)                            │
    │  ┌──────────────────────────────────────────────────────────┐ │
    │  │  NAOqi Client Process                                     │ │
    │  │  - ALAudioDevice captures audio from microphones         │ │
    │  │  - Sends WAV bytes via HTTP POST to AI Server            │ │
    │  │  - Receives JSON response {"speech":..,"gesture":..}     │ │
    │  │  - Triggers ALAnimatedSpeech + expressive listening      │ │
    │  └────────────────────────┬─────────────────────────────────┘ │
    └───────────────────────────│────────────────────────────────────┘
                                │  HTTP (JSON / WAV)
    ┌───────────────────────────▼────────────────────────────────────┐
    │  AI Server (Python 3.x — this code)                            │
    │  - Receives audio, transcribes with OpenAI Whisper            │
    │  - Sends transcript to LiteLLM gateway                        │
    │  - Returns RobotAction JSON                                    │
    │  - This PepperBridge.execute_action() sends back to the       │
    │    NAOqi bridge server running on/near the robot              │
    └────────────────────────────────────────────────────────────────┘

The NAOqi bridge server is a small Flask app that exposes:
- POST /action  → executes a RobotAction JSON on the robot via NAOqi
- GET  /sensors → returns current sensor data

Note: Actual NAOqi calls (ALAnimatedSpeech, ALMotion, etc.) live in the
Python 2.7 NAOqi process.  This class communicates with that process over HTTP.

References:
    - SoftBank Robotics NAOqi Documentation:
      https://developer.softbankrobotics.com/naoqi-sdk-doc
    - "LLM Enabled Social Robots – Aged Care" (IEEE)
    - "LLMs as NAO Robot 3D Motion Planners" (ICCV 2025 Workshop)
"""

from __future__ import annotations

import json
from typing import Any

from omnillm.robotics.bridge import RobotAction, RobotBridge, RobotSensorData


class PepperBridge(RobotBridge):
    """Pepper robot integration via HTTP bridge to NAOqi process.

    Communicates with a NAOqi Python 2.7 bridge server running on or near
    the robot.  All NAOqi-specific calls are handled by that bridge server;
    this class is pure Python 3.x.

    Example::

        bridge = PepperBridge(robot_ip="192.168.1.100")
        await bridge.connect()
        action = RobotAction(speech="Hello!", gesture="wave", emotion_led="#00FF00")
        await bridge.execute_action(action)
        await bridge.disconnect()
    """

    def __init__(
        self,
        robot_ip: str,
        robot_port: int = 9559,
        bridge_port: int = 5000,
    ) -> None:
        """Initialise the Pepper bridge.

        Args:
            robot_ip: IP address of the Pepper robot on the local network.
            robot_port: NAOqi SDK port (default 9559).
            bridge_port: Port of the Flask/HTTP bridge server running on or
                near the robot (default 5000).
        """
        self.robot_ip = robot_ip
        self.robot_port = robot_port
        self.bridge_port = bridge_port
        self._bridge_url = f"http://{robot_ip}:{bridge_port}"
        self._connected = False

    # ── Connection management ─────────────────────────────────────────────────

    async def connect(self) -> bool:
        """Connect to the NAOqi bridge server.

        In production, this sends a GET /ping to the bridge server and
        verifies that the NAOqi session is active.

        Returns:
            True if bridge server is reachable and NAOqi session is active.
        """
        # PLACEHOLDER: In production use aiohttp to GET {bridge_url}/ping
        # import aiohttp
        # async with aiohttp.ClientSession() as session:
        #     async with session.get(f"{self._bridge_url}/ping") as resp:
        #         self._connected = resp.status == 200
        self._connected = True
        return self._connected

    async def disconnect(self) -> bool:
        """Disconnect from the NAOqi bridge server.

        Returns:
            True if disconnected cleanly.
        """
        # PLACEHOLDER: In production: POST {bridge_url}/disconnect
        self._connected = False
        return True

    # ── Action execution ──────────────────────────────────────────────────────

    async def execute_action(self, action: RobotAction) -> bool:
        """Send a :class:`RobotAction` to the NAOqi bridge server.

        The bridge server translates the RobotAction JSON into NAOqi API calls:
        - ``action.speech`` → ``ALAnimatedSpeech.say(text)``
        - ``action.gesture`` → ``ALBehaviorManager.runBehavior(gesture)``
        - ``action.movement`` → ``ALMotion.moveTo(x, y, theta)``
        - ``action.emotion_led`` → ``ALLeds.fadeRGB("FaceLeds", r, g, b, 0.5)``

        Args:
            action: The action to execute on Pepper.

        Returns:
            True if the action was dispatched successfully.
        """
        if not self._connected:
            raise RuntimeError("Not connected. Call connect() first.")

        payload = {
            "speech": action.speech,
            "gesture": action.gesture,
            "movement": action.movement,
            "emotion_led": action.emotion_led,
        }

        # PLACEHOLDER: In production:
        # import aiohttp
        # async with aiohttp.ClientSession() as session:
        #     async with session.post(
        #         f"{self._bridge_url}/action",
        #         json=payload,
        #         timeout=aiohttp.ClientTimeout(total=30),
        #     ) as resp:
        #         return resp.status == 200

        # Log what would be sent in placeholder mode
        print(f"[PepperBridge] Would POST to {self._bridge_url}/action:")
        print(json.dumps(payload, indent=2))
        return True

    async def get_sensor_data(self) -> RobotSensorData:
        """Retrieve current sensor data from Pepper.

        The bridge server exposes GET /sensors which returns a JSON dict
        of ALMemory values including touch sensors, face detection, and
        battery level.

        Returns:
            :class:`RobotSensorData` with current readings.
        """
        # PLACEHOLDER: In production:
        # import aiohttp
        # async with aiohttp.ClientSession() as session:
        #     async with session.get(f"{self._bridge_url}/sensors") as resp:
        #         data = await resp.json()
        #         return RobotSensorData(
        #             touch_sensors=data.get("touch_sensors", {}),
        #             face_detected=data.get("face_detected", False),
        #             speech_detected=data.get("speech_detected"),
        #             battery_level=data.get("battery_level", 1.0),
        #         )
        return RobotSensorData(
            touch_sensors={"head": False, "left_hand": False, "right_hand": False},
            face_detected=False,
            battery_level=0.85,
        )

    async def say(self, text: str) -> bool:
        """Make Pepper speak.

        Uses ALAnimatedSpeech via the NAOqi bridge for natural, expressive
        speech with automatic body animations (Expressive Listening mode).

        Args:
            text: Text to speak (supports NAOqi markup for emphasis/pauses).

        Returns:
            True if speech completed.
        """
        action = RobotAction(speech=text)
        return await self.execute_action(action)

    async def gesture(self, name: str) -> bool:
        """Trigger a named gesture or behaviour on Pepper.

        Named behaviours are defined in the robot's behaviour library and
        triggered via ``ALBehaviorManager.runBehavior(name)``.

        Args:
            name: Behaviour name (e.g. ``"wave"``, ``"bow"``, ``"dance"``).

        Returns:
            True if the gesture completed.
        """
        action = RobotAction(gesture=name)
        return await self.execute_action(action)

    # ── Pepper-specific helpers ───────────────────────────────────────────────

    async def _send_to_bridge(self, endpoint: str, payload: dict[str, Any]) -> bool:
        """Send a command to the Python 2.7 NAOqi bridge server.

        Args:
            endpoint: API endpoint (e.g. ``"/action"``).
            payload: JSON-serialisable dict to POST.

        Returns:
            True if the server returned HTTP 200.
        """
        # PLACEHOLDER: real implementation uses aiohttp
        # import aiohttp
        # url = f"{self._bridge_url}{endpoint}"
        # async with aiohttp.ClientSession() as session:
        #     async with session.post(url, json=payload) as resp:
        #         return resp.status == 200
        print(f"[PepperBridge] _send_to_bridge({endpoint}): {payload}")
        return True
