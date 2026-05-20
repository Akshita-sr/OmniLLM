"""Pepper Robot Bridge -- Python 3 client of the NAOqi 2.7 bridge server.

This is the Python 3.x half of the two-process Pepper integration.  It is a
thin async HTTP client of :mod:`omnillm.server.naoqi_bridge_server`, which
runs in Python 2.7 because NAOqi 2.5 is locked to that interpreter.

Topology
--------
::

    [ Python 3 OmniLLM stack (LangGraph, gateway, ...) ]
            |
            |  PepperBridge -- aiohttp POST /action, /audio/record, ...
            v
    [ Python 2.7 naoqi_bridge_server :6000 ]
            |
            |  ALBroker / ALProxy
            v
    [ Pepper 2.5.5.5  (real robot or Choregraphe virtual) ]

Modes
-----
The bridge supports three runtime modes, chosen by :meth:`PepperBridge.connect`:

1. **server** -- a Python 2.7 ``naoqi_bridge_server`` is reachable at
   ``bridge_port`` and is connected to a robot (real or virtual). Real HTTP
   calls drive Pepper.

2. **direct** -- the same Python 3 process embeds a minimal in-process
   action handler that prints actions to stdout.  Used when no bridge
   server is reachable but the caller still wants the same async API.

3. **stub** -- no robot anywhere; actions are logged.  This is the default
   fallback when nothing else works, so that :class:`PepperBridge` never
   raises during construction and tests can run on any developer machine.

The mode is auto-detected on :meth:`connect` based on what is reachable.

Example
-------
::

    bridge = PepperBridge(robot_ip="192.168.1.42")  # real Pepper at lab
    await bridge.connect()
    await bridge.execute_action(RobotAction(
        speech="Hello!", gesture="wave", emotion_led="#00FF00",
    ))
    await bridge.disconnect()
"""

from __future__ import annotations

import asyncio
import logging
import socket
from typing import Any, Literal

from omnillm.robotics.bridge import RobotAction, RobotBridge, RobotSensorData

logger = logging.getLogger(__name__)

Mode = Literal["server", "direct", "stub"]


class PepperBridge(RobotBridge):
    """Pepper robot integration via HTTP bridge to a NAOqi Python 2.7 server.

    All NAOqi-specific work happens in :mod:`omnillm.server.naoqi_bridge_server`.
    This class is pure Python 3.x and uses :mod:`aiohttp` for non-blocking I/O.

    Args:
        robot_ip: IP address of the Pepper robot (or ``127.0.0.1`` for the
            Choregraphe virtual robot).
        robot_port: NAOqi port.  ``9559`` for real Pepper.  For Choregraphe's
            virtual robot it is randomised per launch -- pass it explicitly
            or let :func:`discover_choregraphe_port` find it.
        bridge_host: Host on which the Python 2.7 bridge server listens.
            Defaults to ``robot_ip``.
        bridge_port: Port of the Python 2.7 bridge server (default ``6000``).
        connect_timeout: Seconds to wait for /ping during :meth:`connect`.
        action_timeout: Seconds to wait for any /action POST.
        fallback: ``"auto"`` (default), ``"stub"``, or ``"raise"``.  Controls
            what happens when the bridge server is unreachable: ``"auto"``
            falls back to stub mode silently, ``"raise"`` raises
            :class:`ConnectionError`.

    Example::

        bridge = PepperBridge(robot_ip="192.168.1.100")
        await bridge.connect()
        await bridge.say("Hello!")
        await bridge.disconnect()
    """

    def __init__(
        self,
        robot_ip: str,
        robot_port: int = 9559,
        bridge_host: str | None = None,
        bridge_port: int = 6000,
        connect_timeout: float = 2.0,
        action_timeout: float = 30.0,
        fallback: Literal["auto", "stub", "raise"] = "auto",
    ) -> None:
        self.robot_ip = robot_ip
        self.robot_port = robot_port
        self.bridge_host = bridge_host or robot_ip
        self.bridge_port = bridge_port
        self._bridge_url = f"http://{self.bridge_host}:{self.bridge_port}"
        self._connect_timeout = connect_timeout
        self._action_timeout = action_timeout
        self._fallback_policy = fallback

        self._mode: Mode = "stub"
        self._connected = False
        self._ping_info: dict[str, Any] = {}

    # ── Connection management ────────────────────────────────────────────────

    async def connect(self) -> bool:
        """Detect what's reachable and pick a mode.

        Order of preference: ``server`` -> ``stub`` (no real robot anywhere).
        ``direct`` is selected only when the caller explicitly switches via
        :meth:`use_direct_mode` -- this method never picks it automatically
        because ``direct`` doesn't actually move a robot.

        Returns:
            True when the chosen mode is usable.  Always True in ``auto``
            fallback; raises only when ``fallback="raise"`` and the bridge
            server is unreachable.
        """
        # Try the Python 2.7 bridge server first.
        ping = await self._ping_bridge_server()
        if ping is not None:
            self._mode = "server"
            self._ping_info = ping
            self._connected = True
            logger.info(
                "PepperBridge connected via bridge server at %s "
                "(NAOqi=%s, simulation=%s)",
                self._bridge_url, ping.get("naoqi"), ping.get("simulation"),
            )
            return True

        # No bridge server.
        if self._fallback_policy == "raise":
            raise ConnectionError(
                f"NAOqi bridge server unreachable at {self._bridge_url}. "
                "Start it on the Pepper side with: "
                "C:\\Python27\\python.exe -m omnillm.server.naoqi_bridge_server"
            )

        self._mode = "stub"
        self._connected = True
        logger.warning(
            "PepperBridge falling back to STUB mode (no bridge at %s). "
            "Actions will be logged to stdout, not sent to a robot.",
            self._bridge_url,
        )
        return True

    async def disconnect(self) -> bool:
        if self._mode == "server" and self._connected:
            try:
                await self._post("/disconnect", {})
            except Exception:  # noqa: BLE001
                pass
        self._connected = False
        return True

    def use_direct_mode(self) -> None:
        """Switch to in-process direct mode (no bridge server, no robot).

        This is mainly for unit tests that exercise the LangGraph node code
        path without standing up a NAOqi server.  Actions are printed.
        """
        self._mode = "direct"
        self._connected = True

    @property
    def mode(self) -> Mode:
        return self._mode

    @property
    def ping_info(self) -> dict[str, Any]:
        return dict(self._ping_info)

    # ── Public API ───────────────────────────────────────────────────────────

    async def execute_action(self, action: RobotAction) -> bool:
        if not self._connected:
            raise RuntimeError("PepperBridge not connected -- call connect() first.")

        payload = {
            "speech": action.speech,
            "gesture": action.gesture,
            "movement": action.movement,
            "emotion_led": action.emotion_led,
            "tablet_url": (action.metadata or {}).get("tablet_url"),
            "metadata": action.metadata,
        }

        if self._mode == "server":
            resp = await self._post("/action", payload, timeout=self._action_timeout)
            return bool(resp and resp.get("ok"))

        # direct / stub
        logger.info("[%s] action: %s", self._mode, payload)
        return True

    async def get_sensor_data(self) -> RobotSensorData:
        if self._mode == "server":
            data = await self._get("/sensors") or {}
            return RobotSensorData(
                touch_sensors=dict(data.get("touch_sensors", {})),
                face_detected=bool(data.get("face_detected", False)),
                battery_level=float(data.get("battery_level", 1.0)),
            )
        # Stub: pretend nothing is happening.
        return RobotSensorData(
            touch_sensors={"head_front": False, "head_middle": False, "head_rear": False},
            face_detected=False,
            battery_level=0.85,
        )

    async def say(self, text: str) -> bool:
        return await self.execute_action(RobotAction(speech=text))

    async def gesture(self, name: str) -> bool:
        return await self.execute_action(RobotAction(gesture=name))

    async def record_audio(
        self,
        duration_seconds: float = 5.0,
        sample_rate: int = 16000,
        channels: list[int] | None = None,
    ) -> dict[str, Any]:
        """Record audio from Pepper's microphone and return base64 WAV.

        Returns a dict with ``ok``, ``audio_b64``, and optional ``error`` /
        ``simulated`` keys.  In stub / direct mode returns an empty payload
        with ``simulated=True`` so callers can fall back to text input.
        """
        if channels is None:
            channels = [0, 0, 1, 0]
        if self._mode != "server":
            return {"ok": False, "simulated": True,
                    "error": f"PepperBridge mode={self._mode} -- no microphone",
                    "audio_b64": ""}
        resp = await self._post(
            "/audio/record",
            {"duration_seconds": duration_seconds, "sample_rate": sample_rate,
             "channels": channels},
            timeout=max(self._action_timeout, duration_seconds + 5),
        )
        return resp or {"ok": False, "audio_b64": "", "error": "no response"}

    async def start_face_tracking(self) -> bool:
        if self._mode != "server":
            logger.info("[%s] would start face tracking", self._mode)
            return True
        resp = await self._post("/tracker/start", {"target": "Face"})
        return bool(resp and resp.get("ok"))

    async def stop_face_tracking(self) -> bool:
        if self._mode != "server":
            logger.info("[%s] would stop face tracking", self._mode)
            return True
        resp = await self._post("/tracker/stop", {})
        return bool(resp and resp.get("ok"))

    # ── HTTP helpers ─────────────────────────────────────────────────────────

    async def _ping_bridge_server(self) -> dict[str, Any] | None:
        """GET /ping with a short timeout; returns the JSON body or None."""
        # Cheap TCP pre-check so we don't pay aiohttp setup cost when the
        # port isn't even open.
        if not _tcp_reachable(self.bridge_host, self.bridge_port,
                              timeout=self._connect_timeout):
            return None
        try:
            return await self._get("/ping", timeout=self._connect_timeout)
        except Exception:  # noqa: BLE001
            return None

    async def _get(self, path: str, timeout: float | None = None) -> dict[str, Any] | None:
        import aiohttp

        url = self._bridge_url + path
        t = aiohttp.ClientTimeout(total=timeout or self._action_timeout)
        async with aiohttp.ClientSession(timeout=t) as session:
            async with session.get(url) as resp:
                if resp.status != 200:
                    logger.warning("GET %s -> %s", url, resp.status)
                    return None
                return await resp.json(content_type=None)

    async def _post(
        self, path: str, payload: dict[str, Any], timeout: float | None = None,
    ) -> dict[str, Any] | None:
        import aiohttp

        url = self._bridge_url + path
        t = aiohttp.ClientTimeout(total=timeout or self._action_timeout)
        async with aiohttp.ClientSession(timeout=t) as session:
            async with session.post(url, json=payload) as resp:
                if resp.status != 200:
                    logger.warning("POST %s -> %s", url, resp.status)
                    return None
                return await resp.json(content_type=None)


# ─────────────────────────────────────────────────────────────────────────────
# Choregraphe virtual-Pepper port discovery
# ─────────────────────────────────────────────────────────────────────────────

CHOREGRAPHE_DEFAULT_PORT_HINTS: tuple[int, ...] = (
    # Common ports the Choregraphe virtual robot has ended up on across
    # launches.  Used as fast-path hints before scanning.  The first one is
    # what Akshita's machine landed on most recently.
    49959, 49960, 49961, 60930, 62494, 9559,
)


async def discover_choregraphe_port(
    host: str = "127.0.0.1",
    hints: tuple[int, ...] = CHOREGRAPHE_DEFAULT_PORT_HINTS,
    scan_range: tuple[int, int] | None = (49152, 65535),
    max_scan: int = 256,
    timeout: float = 0.05,
) -> int | None:
    """Best-effort discovery of Choregraphe's randomised virtual-robot port.

    Strategy:

    1. Try a small list of *hint* ports (recent observed values + 9559).
    2. If none work, scan a slice of the ephemeral range looking for a
       socket that accepts a connection.  We bound the scan to
       ``max_scan`` ports so we don't pay 16k connect-syscalls.

    This is a TCP-reachability check only -- it does NOT validate that the
    peer speaks NAOqi.  Callers should follow up with an actual connection.

    Args:
        host: Always ``127.0.0.1`` for Choregraphe.
        hints: Ports to probe first (fast path).
        scan_range: Optional ``(lo, hi)`` range to scan if hints miss.
            Pass ``None`` to disable scanning.
        max_scan: Cap on how many ports we scan inside ``scan_range``.
        timeout: Per-port TCP timeout (seconds).

    Returns:
        The first port that accepts a TCP connection, or ``None`` if none
        of the candidates respond.
    """
    for port in hints:
        if _tcp_reachable(host, port, timeout=timeout):
            return port

    if scan_range is None:
        return None

    lo, hi = scan_range
    step = max(1, (hi - lo) // max_scan)
    for port in range(lo, hi, step):
        if _tcp_reachable(host, port, timeout=timeout):
            return port

    return None


def _tcp_reachable(host: str, port: int, timeout: float = 0.5) -> bool:
    """Return True if a TCP connect to ``host:port`` succeeds within timeout."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(timeout)
            sock.connect((host, port))
            return True
    except (OSError, socket.timeout):
        return False


# ─────────────────────────────────────────────────────────────────────────────
# Convenience factory
# ─────────────────────────────────────────────────────────────────────────────

async def make_pepper_bridge(
    robot_ip: str = "127.0.0.1",
    robot_port: int | None = None,
    bridge_port: int = 6000,
    fallback: Literal["auto", "stub", "raise"] = "auto",
) -> PepperBridge:
    """Build and connect a :class:`PepperBridge` with sensible auto-discovery.

    - On ``127.0.0.1`` and ``robot_port=None``, scans for the Choregraphe
      virtual-robot port.
    - On any other ``robot_ip``, assumes the real-Pepper default ``9559``.
    - Always calls :meth:`PepperBridge.connect` before returning.

    Args:
        robot_ip: ``127.0.0.1`` for virtual Pepper, lab IP for real Pepper.
        robot_port: NAOqi port. ``None`` triggers Choregraphe discovery on
            localhost.
        bridge_port: Port of the Python 2.7 bridge server.
        fallback: Passed through to :class:`PepperBridge`.

    Returns:
        A connected :class:`PepperBridge` ready to ``execute_action``.
    """
    if robot_port is None:
        if robot_ip in ("127.0.0.1", "localhost"):
            discovered = await discover_choregraphe_port(robot_ip)
            robot_port = discovered or 9559
            if discovered is None:
                logger.warning(
                    "Could not auto-discover Choregraphe port; using 9559.")
        else:
            robot_port = 9559

    bridge = PepperBridge(
        robot_ip=robot_ip,
        robot_port=robot_port,
        bridge_port=bridge_port,
        fallback=fallback,
    )
    await bridge.connect()
    return bridge


# Re-export `asyncio` for the rare caller that wants to run this synchronously.
__all__ = [
    "PepperBridge",
    "discover_choregraphe_port",
    "make_pepper_bridge",
    "CHOREGRAPHE_DEFAULT_PORT_HINTS",
]
