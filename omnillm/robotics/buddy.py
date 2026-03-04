"""Buddy Robot Bridge — Android-based robot with WebSocket streaming.

Buddy is a companion robot by Blue Frog Robotics running Android.  Unlike
Pepper/NAO which use NAOqi, Buddy's AI interface is built around a WebSocket
connection for real-time, token-by-token streaming of LLM responses.

Architecture — FastAPI ↔ Android WebSocket
------------------------------------------

    ┌──────────────────────────────────────────────────────────────────┐
    │  Buddy Robot (Android)                                          │
    │  ┌──────────────────────────────────────────────────────────┐   │
    │  │  Android App                                              │   │
    │  │  - Captures voice via microphone                         │   │
    │  │  - Transcribes with Google Speech-to-Text API            │   │
    │  │  - Sends transcript text via WebSocket                   │   │
    │  │  - Receives streaming LLM tokens via WebSocket           │   │
    │  │  - Pipes tokens to Android TTS in real time              │   │
    │  └──────────────────────────────┬────────────────────────────┘   │
    └──────────────────────────────────│────────────────────────────────┘
                                       │  WebSocket (text)
    ┌──────────────────────────────────▼────────────────────────────────┐
    │  AI Server (this code — FastAPI + LiteLLM)                        │
    │  - Accepts WebSocket connections from Buddy                       │
    │  - Receives transcript text messages                              │
    │  - Calls LiteLLM with streaming=True                             │
    │  - Streams tokens back over WebSocket in real time               │
    │  - Sends final RobotAction JSON at end of stream                 │
    └────────────────────────────────────────────────────────────────────┘

Benefits of WebSocket streaming for Buddy:
- Sub-100ms perceived latency (TTS starts before LLM finishes)
- Natural conversational rhythm
- Enables real-time interruption ("Hey Buddy, stop!")

References:
    - Blue Frog Robotics Buddy documentation:
      https://www.bluefrogrobotics.com/buddy/
    - "LLM-Powered Multi-Session HRI" (Frontiers in Robotics and AI)
    - FastAPI WebSocket: https://fastapi.tiangolo.com/advanced/websockets/
"""

from __future__ import annotations

import json
from typing import Any

from omnillm.robotics.bridge import RobotAction, RobotBridge, RobotSensorData


class BuddyBridge(RobotBridge):
    """Buddy robot integration via WebSocket.

    Streams LLM responses token-by-token to Buddy's Android app, enabling
    the robot to start speaking before the full LLM response is complete.

    Example::

        bridge = BuddyBridge(websocket_url="ws://192.168.1.102:8765")
        await bridge.connect()
        await bridge.say("Hello! I am Buddy, your AI companion.")
        await bridge.disconnect()
    """

    def __init__(self, websocket_url: str) -> None:
        """Initialise the Buddy WebSocket bridge.

        Args:
            websocket_url: WebSocket URL of Buddy's Android app server
                (e.g. ``"ws://192.168.1.102:8765"``).
        """
        self.websocket_url = websocket_url
        self._websocket: Any | None = None
        self._connected = False

    # ── Connection management ─────────────────────────────────────────────────

    async def connect(self) -> bool:
        """Open the WebSocket connection to Buddy.

        In production, this uses the ``websockets`` library:

        .. code-block:: python

            import websockets
            self._websocket = await websockets.connect(self.websocket_url)

        Returns:
            True if connected successfully.
        """
        # PLACEHOLDER: real implementation:
        # import websockets
        # try:
        #     self._websocket = await websockets.connect(self.websocket_url)
        #     self._connected = True
        # except Exception as e:
        #     print(f"[BuddyBridge] Connection failed: {e}")
        #     self._connected = False
        self._connected = True
        print(f"[BuddyBridge] Connected to {self.websocket_url} (mock)")
        return self._connected

    async def disconnect(self) -> bool:
        """Close the WebSocket connection.

        Returns:
            True if disconnected cleanly.
        """
        # PLACEHOLDER: real implementation:
        # if self._websocket:
        #     await self._websocket.close()
        self._connected = False
        self._websocket = None
        return True

    # ── Action execution ──────────────────────────────────────────────────────

    async def execute_action(self, action: RobotAction) -> bool:
        """Send a :class:`RobotAction` to Buddy via WebSocket.

        The Android app receives the JSON action and handles:
        - ``action.speech`` → Android TextToSpeech.speak()
        - ``action.gesture`` → Buddy animation player
        - ``action.emotion_led`` → LED colour change
        - ``action.movement`` → Buddy navigation controller

        Args:
            action: The action to execute on Buddy.

        Returns:
            True if the message was sent successfully.
        """
        if not self._connected:
            raise RuntimeError("Not connected. Call connect() first.")

        payload: dict[str, Any] = {
            "type": "action",
            "speech": action.speech,
            "gesture": action.gesture,
            "movement": action.movement,
            "emotion_led": action.emotion_led,
        }

        # PLACEHOLDER: real implementation:
        # if self._websocket:
        #     await self._websocket.send(json.dumps(payload))
        #     ack = await self._websocket.recv()
        #     return json.loads(ack).get("status") == "ok"

        print(f"[BuddyBridge] Would send WebSocket message:")
        print(json.dumps(payload, indent=2))
        return True

    async def stream_response(
        self, prompt: str, gateway: Any, model_id: str
    ) -> str:
        """Stream an LLM response token-by-token to Buddy via WebSocket.

        This is the key feature of the Buddy bridge: instead of waiting for
        the full LLM response, tokens are streamed back as they are generated,
        allowing Buddy's TTS to start speaking immediately.

        Architecture:
        1. Send prompt to LiteLLM with ``stream=True``
        2. For each token chunk, send it over WebSocket
        3. Buddy's Android app queues tokens for TTS in real time
        4. Send final ``{"type": "end"}`` message when complete

        Args:
            prompt: User's input text.
            gateway: :class:`~omnillm.gateway.LLMGateway` instance.
            model_id: Model to use for generation.

        Returns:
            The complete response text.
        """
        # PLACEHOLDER: streaming implementation would use:
        # import litellm
        # full_response = ""
        # async for chunk in await litellm.acompletion(
        #     model=..., messages=[{"role":"user","content":prompt}], stream=True
        # ):
        #     token = chunk.choices[0].delta.content or ""
        #     full_response += token
        #     if self._websocket and token:
        #         await self._websocket.send(json.dumps({"type": "token", "content": token}))
        # if self._websocket:
        #     await self._websocket.send(json.dumps({"type": "end"}))
        # return full_response

        # Non-streaming fallback for placeholder
        messages = [{"role": "user", "content": prompt}]
        response = await gateway.query(model_id, messages)
        await self.say(response.content)
        return response.content

    async def get_sensor_data(self) -> RobotSensorData:
        """Retrieve current sensor data from Buddy.

        Buddy exposes sensor data via WebSocket messages:
        - ``{"type": "sensors"}`` request → ``{"battery": 0.9, "face_detected": true, ...}``

        Returns:
            :class:`RobotSensorData` with current readings.
        """
        # PLACEHOLDER: real implementation:
        # if self._websocket:
        #     await self._websocket.send(json.dumps({"type": "get_sensors"}))
        #     data = json.loads(await self._websocket.recv())
        #     return RobotSensorData(
        #         touch_sensors=data.get("touch", {}),
        #         face_detected=data.get("face_detected", False),
        #         speech_detected=data.get("speech", None),
        #         battery_level=data.get("battery", 1.0),
        #     )
        return RobotSensorData(
            touch_sensors={"head": False, "chest": False},
            face_detected=False,
            battery_level=0.75,
        )

    async def say(self, text: str) -> bool:
        """Make Buddy speak.

        Args:
            text: Text to speak (Android TTS processes this).

        Returns:
            True if the message was sent.
        """
        return await self.execute_action(RobotAction(speech=text))

    async def gesture(self, name: str) -> bool:
        """Trigger a named animation on Buddy.

        Buddy's Android app maps gesture names to pre-recorded animations.
        Common gestures: ``"wave"``, ``"dance"``, ``"nod"``, ``"shake_head"``.

        Args:
            name: Animation name.

        Returns:
            True if the message was sent.
        """
        return await self.execute_action(RobotAction(gesture=name))
