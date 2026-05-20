"""Tests for the upgraded PepperBridge and Choregraphe port discovery.

These tests run on any machine -- no NAOqi SDK or robot required.
"""

from __future__ import annotations

import asyncio
import socket
from contextlib import closing

import pytest


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _free_port() -> int:
    """Grab a random free local TCP port (race-prone but fine for tests)."""
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


# ── PepperBridge: stub fallback ───────────────────────────────────────────────

class TestPepperBridgeStubFallback:
    def test_connect_auto_fallback_to_stub_when_no_server(self):
        """When the bridge server is unreachable and fallback='auto', the
        bridge should silently switch to stub mode and report connected."""
        from omnillm.robotics.pepper import PepperBridge

        bridge = PepperBridge(
            robot_ip="127.0.0.1", bridge_port=_free_port(), fallback="auto",
        )

        async def go():
            ok = await bridge.connect()
            return ok, bridge.mode

        ok, mode = asyncio.run(go())
        assert ok is True
        assert mode == "stub"

    def test_connect_raise_when_unreachable(self):
        from omnillm.robotics.pepper import PepperBridge

        bridge = PepperBridge(
            robot_ip="127.0.0.1", bridge_port=_free_port(), fallback="raise",
        )

        async def go():
            await bridge.connect()

        with pytest.raises(ConnectionError):
            asyncio.run(go())

    def test_stub_execute_action_returns_true(self):
        from omnillm.robotics.bridge import RobotAction
        from omnillm.robotics.pepper import PepperBridge

        bridge = PepperBridge(
            robot_ip="127.0.0.1", bridge_port=_free_port(), fallback="auto",
        )

        async def go():
            await bridge.connect()
            return await bridge.execute_action(
                RobotAction(speech="hi", gesture="wave", emotion_led="#00FF00"))

        ok = asyncio.run(go())
        assert ok is True

    def test_stub_get_sensor_data_safe_defaults(self):
        from omnillm.robotics.pepper import PepperBridge

        bridge = PepperBridge(
            robot_ip="127.0.0.1", bridge_port=_free_port(), fallback="auto",
        )

        async def go():
            await bridge.connect()
            return await bridge.get_sensor_data()

        data = asyncio.run(go())
        assert data.battery_level == pytest.approx(0.85, abs=0.01)
        assert data.face_detected is False
        # touch_sensors keys should exist even in stub mode
        assert set(data.touch_sensors.keys()) >= {"head_front", "head_middle", "head_rear"}

    def test_stub_record_audio_reports_simulated(self):
        from omnillm.robotics.pepper import PepperBridge

        bridge = PepperBridge(
            robot_ip="127.0.0.1", bridge_port=_free_port(), fallback="auto",
        )

        async def go():
            await bridge.connect()
            return await bridge.record_audio(duration_seconds=1)

        resp = asyncio.run(go())
        assert resp["ok"] is False
        assert resp.get("simulated") is True
        assert resp["audio_b64"] == ""

    def test_direct_mode_via_use_direct_mode(self):
        from omnillm.robotics.bridge import RobotAction
        from omnillm.robotics.pepper import PepperBridge

        bridge = PepperBridge(robot_ip="127.0.0.1", bridge_port=_free_port())
        bridge.use_direct_mode()
        assert bridge.mode == "direct"

        async def go():
            return await bridge.execute_action(RobotAction(speech="x"))

        assert asyncio.run(go()) is True


# ── Choregraphe port discovery ────────────────────────────────────────────────

class TestChoregrapheDiscovery:
    def test_discover_returns_none_when_nothing_listening(self):
        from omnillm.robotics.pepper import discover_choregraphe_port

        # Pick a host port that is definitely closed and pass it as a hint,
        # plus a narrow scan range that's unlikely to find anything.
        async def go():
            return await discover_choregraphe_port(
                host="127.0.0.1",
                hints=(_free_port(),),         # always closed
                scan_range=(0, 1),             # impossible range
                max_scan=1,
                timeout=0.05,
            )

        assert asyncio.run(go()) is None

    def test_discover_finds_an_open_port(self):
        from omnillm.robotics.pepper import discover_choregraphe_port

        # Open a real listener so discovery has something to find.
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind(("127.0.0.1", 0))
        sock.listen(1)
        port = sock.getsockname()[1]

        try:
            async def go():
                return await discover_choregraphe_port(
                    host="127.0.0.1",
                    hints=(port,),
                    scan_range=None,
                    timeout=0.2,
                )

            assert asyncio.run(go()) == port
        finally:
            sock.close()


# ── make_pepper_bridge factory ────────────────────────────────────────────────

class TestMakePepperBridgeFactory:
    def test_factory_falls_back_when_nothing_running(self):
        from omnillm.robotics.pepper import make_pepper_bridge

        async def go():
            return await make_pepper_bridge(
                robot_ip="127.0.0.1",
                robot_port=9559,            # explicit -- skip discovery
                bridge_port=_free_port(),   # closed
                fallback="auto",
            )

        bridge = asyncio.run(go())
        assert bridge.mode == "stub"
