"""NAO Robot Bridge — NAOqi SDK integration.

NAO is a 58-cm humanoid robot from SoftBank Robotics.  It shares the NAOqi
operating system with Pepper and uses the same Python 2.7 bridge architecture
described in :mod:`omnillm.robotics.pepper`.

Key differences from Pepper:
- No tablet or front-facing screen
- No laser sensors
- Smaller form factor, more articulated joints (25 DoF vs Pepper's 20)
- ALMotion.walkTo() instead of ALMotion.moveTo() for navigation
- Primarily used in education and research (CodeLab, RoboCup)

References:
    - "LLMs as NAO Robot 3D Motion Planners" (ICCV 2025 Workshop)
      https://iccv2025.thecvf.com/
    - SoftBank Robotics NAO documentation:
      https://developer.softbankrobotics.com/nao6
    - RoboCup Standard Platform League:
      https://spl.robocup.org/
"""

from __future__ import annotations

import json
from typing import Any

from omnillm.robotics.bridge import RobotAction, RobotBridge, RobotSensorData


class NAOBridge(RobotBridge):
    """NAO robot integration via HTTP bridge to NAOqi process.

    Uses the same Python 2.7 bridge architecture as :class:`~omnillm.robotics.pepper.PepperBridge`.
    A small Flask server running in a Python 2.7 process on/near the robot
    accepts RobotAction JSON and translates it into NAOqi API calls.

    Example::

        bridge = NAOBridge(robot_ip="192.168.1.101")
        await bridge.connect()
        await bridge.say("Hello, I am NAO!")
        await bridge.gesture("wave_right")
        await bridge.disconnect()
    """

    def __init__(
        self,
        robot_ip: str,
        robot_port: int = 9559,
        bridge_port: int = 5001,
    ) -> None:
        """Initialise the NAO bridge.

        Args:
            robot_ip: IP address of the NAO robot.
            robot_port: NAOqi SDK port (default 9559).
            bridge_port: Port of the Flask bridge server (default 5001 to
                avoid conflict with Pepper's 5000).
        """
        self.robot_ip = robot_ip
        self.robot_port = robot_port
        self.bridge_port = bridge_port
        self._bridge_url = f"http://{robot_ip}:{bridge_port}"
        self._connected = False

    # ── Connection management ─────────────────────────────────────────────────

    async def connect(self) -> bool:
        """Connect to the NAO NAOqi bridge server.

        Returns:
            True if connected successfully.
        """
        # PLACEHOLDER: In production: GET {bridge_url}/ping
        self._connected = True
        return self._connected

    async def disconnect(self) -> bool:
        """Disconnect from the NAO bridge server.

        Returns:
            True if disconnected cleanly.
        """
        # PLACEHOLDER: In production: POST {bridge_url}/disconnect
        self._connected = False
        return True

    # ── Action execution ──────────────────────────────────────────────────────

    async def execute_action(self, action: RobotAction) -> bool:
        """Send a :class:`RobotAction` to the NAOqi bridge server.

        NAOqi translations:
        - ``action.speech`` → ``ALAnimatedSpeech.say(text)``
        - ``action.gesture`` → ``ALBehaviorManager.runBehavior(gesture)``
        - ``action.movement`` → ``ALMotion.walkTo(x, y, theta)``
        - ``action.emotion_led`` → ``ALLeds.fadeRGB("FaceLeds", r, g, b, 0.5)``

        Args:
            action: The action to execute on NAO.

        Returns:
            True if dispatched successfully.
        """
        if not self._connected:
            raise RuntimeError("Not connected. Call connect() first.")

        payload: dict[str, Any] = {
            "speech": action.speech,
            "gesture": action.gesture,
            "movement": action.movement,
            "emotion_led": action.emotion_led,
        }

        # PLACEHOLDER: real implementation uses aiohttp
        # import aiohttp
        # async with aiohttp.ClientSession() as session:
        #     async with session.post(f"{self._bridge_url}/action", json=payload) as resp:
        #         return resp.status == 200

        print(f"[NAOBridge] Would POST to {self._bridge_url}/action:")
        print(json.dumps(payload, indent=2))
        return True

    async def get_sensor_data(self) -> RobotSensorData:
        """Retrieve current sensor data from NAO.

        NAO's sensors via ALMemory:
        - ``Device/SubDeviceList/*/Touch/Sensor/Value`` — touch sensors
        - ``FaceDetected`` — face detection from ALFaceDetection
        - ``SpeechDetected`` — from ALSpeechRecognition
        - ``Device/SubDeviceList/Battery/Charge/Sensor/Value`` — battery

        Returns:
            :class:`RobotSensorData` with current readings.
        """
        # PLACEHOLDER: real implementation queries GET {bridge_url}/sensors
        return RobotSensorData(
            touch_sensors={
                "head_front": False,
                "head_middle": False,
                "head_rear": False,
                "left_hand": False,
                "right_hand": False,
            },
            face_detected=False,
            battery_level=0.90,
        )

    async def say(self, text: str) -> bool:
        """Make NAO speak using ALAnimatedSpeech.

        Args:
            text: Text to speak.

        Returns:
            True if speech completed.
        """
        return await self.execute_action(RobotAction(speech=text))

    async def gesture(self, name: str) -> bool:
        """Trigger a named gesture via ALBehaviorManager.

        Common NAO gestures: ``"wave_right"``, ``"bow"``, ``"yes"``, ``"no"``,
        ``"crouch"``, ``"stand_up"``, ``"sit_down"``.

        Args:
            name: Behaviour name.

        Returns:
            True if the gesture completed.
        """
        return await self.execute_action(RobotAction(gesture=name))

    # ── NAO-specific helpers ──────────────────────────────────────────────────

    async def walk_to(self, x: float, y: float, theta: float) -> bool:
        """Command NAO to walk to a relative position.

        Uses ``ALMotion.walkTo(x, y, theta)`` — walk forward x metres,
        sideways y metres, rotating theta radians.

        Args:
            x: Forward distance in metres.
            y: Lateral distance in metres (positive = left).
            theta: Rotation in radians.

        Returns:
            True if movement completed.
        """
        movement = {"x": x, "y": y, "theta": theta, "type": "walkTo"}
        return await self.execute_action(RobotAction(movement=movement))

    async def stand_up(self) -> bool:
        """Make NAO stand up from any posture.

        Uses ``ALRobotPosture.goToPosture("Stand", 0.8)``.
        """
        return await self.gesture("stand_up")

    async def sit_down(self) -> bool:
        """Make NAO sit down safely.

        Uses ``ALRobotPosture.goToPosture("Sit", 0.8)``.
        """
        return await self.gesture("sit_down")
