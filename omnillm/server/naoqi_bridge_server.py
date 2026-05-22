# -*- coding: utf-8 -*-
"""Python 2.7 NAOqi Bridge Server for Pepper Robot.

A small HTTP server that runs on (or near) the Pepper robot and exposes
NAOqi services to the Python 3.x OmniLLM stack.  It is the counterpart of
:class:`omnillm.robotics.pepper.PepperBridge`.

This file is intentionally Python-2.7 compatible: NAOqi 2.5.5.5 is locked
to Python 2.7 and most Pepper installs ship with that interpreter.  No
external dependencies beyond the standard library and the NAOqi SDK.

Architecture
------------
::

    Python 3 PepperBridge (LangGraph node)
       |
       |  POST /action      { speech, gesture, emotion_led, tablet_url, ... }
       |  POST /audio/record{ duration_seconds, sample_rate, channels }
       |  POST /tracker/start { target: "Face" }
       |  POST /tracker/stop
       |  POST /disconnect
       |  GET  /sensors  -> { touch_sensors, face_detected, battery_level }
       |  GET  /ping     -> { ok, naoqi, robot_ip, port }
       v
    This server (Python 2.7, NAOqi process)
       |
       |  ALBroker / ALProxy
       v
    Pepper (real or Choregraphe virtual robot)


Usage
-----
On Pepper (or any machine with pynaoqi 2.5)::

    C:\\Python27\\python.exe -m omnillm.server.naoqi_bridge_server \\
        --robot-ip 127.0.0.1 --robot-port 62763 --bridge-port 6000

For real Pepper at the lab::

    C:\\Python27\\python.exe -m omnillm.server.naoqi_bridge_server \\
        --robot-ip 192.168.1.42 --robot-port 9559 --bridge-port 6000

Notes
-----
* ``ALBroker(..., "127.0.0.1", 0, robot_ip, robot_port)`` is used because
  ``qi.Session()`` hits a Windows 11 TCP loopback bug with NAOqi 2.5 (see
  the project memory ``pepper-windows-quirks``).
* ALAudioRecorder, ALTabletService, ALFaceDetection, ALTracker are only
  available on real Pepper -- the server returns sensible 501 responses
  when called against Choregraphe's virtual robot, never crashes.
* Audio recordings are written to a per-process temp dir and returned as
  base64-encoded WAV bytes in the JSON response.
"""

from __future__ import print_function

import argparse
import base64
import json
import os
import sys
import tempfile
import threading
import time
import traceback

try:
    # Python 2.7 stdlib
    from BaseHTTPServer import BaseHTTPRequestHandler, HTTPServer
    from SocketServer import ThreadingMixIn
    _IS_PY2 = True
except ImportError:
    # Python 3 fallback (for syntax-check on dev machines without NAOqi)
    from http.server import BaseHTTPRequestHandler, HTTPServer  # type: ignore
    from socketserver import ThreadingMixIn  # type: ignore
    _IS_PY2 = False


# ---------------------------------------------------------------------------
# NAOqi SDK -- lazy and graceful: missing SDK means simulation mode.
# ---------------------------------------------------------------------------
NAOQI_AVAILABLE = False
BROKER_AVAILABLE = False
QI_AVAILABLE = False

try:
    import qi  # type: ignore
    QI_AVAILABLE = True
    NAOQI_AVAILABLE = True
except Exception:
    # SyntaxError on Python 3 if pynaoqi 2.5's qi/__init__.py is on
    # PYTHONPATH; ImportError if the SDK is simply missing. Either way,
    # degrade to simulation mode rather than crash.
    pass

try:
    from naoqi import ALBroker, ALProxy  # type: ignore
    BROKER_AVAILABLE = True
    NAOQI_AVAILABLE = True
except Exception:
    pass


# ---------------------------------------------------------------------------
# Gesture -> NAOqi behavior map.  Mirrors the one in naoqi_client.py so the
# RobotAction JSON contract is identical from either entry point.
# ---------------------------------------------------------------------------
GESTURE_TO_BEHAVIOR = {
    "wave": "animations/Stand/Gestures/Hey_1",
    "bow": "animations/Stand/Gestures/BowShort_1",
    "wave_goodbye": "animations/Stand/Gestures/Farewells_1",
    "point_left": "animations/Stand/Gestures/Explain_8",
    "point_right": "animations/Stand/Gestures/Explain_7",
    "point_forward": "animations/Stand/Gestures/Explain_1",
    "point_up": "animations/Stand/Gestures/Explain_6",
    "show_tablet": "animations/Stand/Gestures/ShowTablet_1",
    "nod": "animations/Stand/Emotions/Positive/Enthusiastic_1",
    "think": "animations/Stand/Emotions/Neutral/Thinking_1",
    "happy": "animations/Stand/Emotions/Positive/Happy_4",
    "confused": "animations/Stand/Emotions/Negative/Confused_1",
}

EYE_LED_GROUP = "FaceLeds"

#: Tactile event names we expose via GET /sensors (Pepper 2.5)
_TOUCH_EVENTS = {
    "head_front": "FrontTactilTouched",
    "head_middle": "MiddleTactilTouched",
    "head_rear": "RearTactilTouched",
    "left_hand": "HandLeftBackTouched",
    "right_hand": "HandRightBackTouched",
    "bumper_front_left": "Device/SubDeviceList/Platform/FrontLeft/Bumper/Sensor/Value",
    "bumper_front_right": "Device/SubDeviceList/Platform/FrontRight/Bumper/Sensor/Value",
}


# ---------------------------------------------------------------------------
# NAOqi facade -- one shared object held by the HTTP handlers.
# ---------------------------------------------------------------------------

class _NoOp(object):
    """Stand-in for an ALProxy that swallows method calls."""

    def __getattr__(self, name):
        def _stub(*args, **kwargs):
            print("[SIM] {0}(*{1!r}, **{2!r})".format(name, args, kwargs))
            return None
        # Bare attribute access for nested objects like proxy.post.runBehavior
        if name == "post":
            return self
        return _stub


def _try_proxy(service_name):
    """Best-effort ALProxy lookup; returns a no-op stub if not available.

    NAOqi 2.5's ALProxy constructor sometimes returns ``None`` rather than
    raising when the remote service isn't reachable (e.g. a broker is up but
    the robot is offline).  We collapse that case to a :class:`_NoOp` so
    callers don't trip on ``AttributeError`` later.
    """
    if not BROKER_AVAILABLE:
        return _NoOp()
    try:
        proxy = ALProxy(service_name)
    except Exception as exc:
        print("[WARN] {0} not available: {1}".format(service_name, exc),
              file=sys.stderr)
        return _NoOp()
    if proxy is None:
        print("[WARN] {0} returned None proxy".format(service_name),
              file=sys.stderr)
        return _NoOp()
    return proxy


class NaoqiFacade(object):
    """Wraps NAOqi proxies so the HTTP layer can call them by intent.

    Holds an ALBroker (legacy) for Windows-11 virtual-Pepper compatibility.
    On real Pepper the same code path works -- ALBroker just opens a
    different transport.
    """

    def __init__(self, robot_ip, robot_port):
        self.robot_ip = robot_ip
        self.robot_port = robot_port
        self.simulation = not NAOQI_AVAILABLE

        # Lock so concurrent /action and /audio requests don't trip over each
        # other in NAOqi (which is not fully thread-safe for ALMotion calls).
        self._lock = threading.Lock()

        self._broker = None
        self._tts = None              # ALAnimatedSpeech (preferred) or ALTextToSpeech
        self._behavior = None         # ALBehaviorManager
        self._motion = None           # ALMotion
        self._leds = None             # ALLeds
        self._audio_rec = None        # ALAudioRecorder
        self._memory = None           # ALMemory
        self._tablet = None           # ALTabletService
        self._tracker = None          # ALTracker
        self._face_det = None         # ALFaceDetection

        # Where to write WAV captures.  /home/nao/recordings/microphones/
        # is the NAOqi-recommended path on real Pepper; falls back to
        # tempdir on Windows so virtual-Pepper mode at least syntactically
        # works (it returns silence -- no real mic).
        self._recordings_dir = "/home/nao/recordings/microphones"
        if not os.path.isdir(self._recordings_dir):
            self._recordings_dir = tempfile.gettempdir()

    # ── Connection lifecycle ─────────────────────────────────────────────────

    def connect(self):
        if self.simulation:
            print("[SIM] NAOqi SDK not available -- simulation mode.")
            self._tts = _NoOp()
            self._behavior = _NoOp()
            self._motion = _NoOp()
            self._leds = _NoOp()
            self._audio_rec = _NoOp()
            self._memory = _NoOp()
            self._tablet = _NoOp()
            self._tracker = _NoOp()
            self._face_det = _NoOp()
            return True

        if not BROKER_AVAILABLE:
            print("[ERR] naoqi.ALBroker not importable -- cannot connect.",
                  file=sys.stderr)
            return False

        # Windows 11 loopback workaround: listen on 127.0.0.1 for virtual
        # Pepper, on 0.0.0.0 for real Pepper (so the robot can call back).
        listen_ip = "127.0.0.1" if self.robot_ip in ("127.0.0.1", "localhost") else "0.0.0.0"

        try:
            self._broker = ALBroker(
                "OmniLLMBridgeBroker", listen_ip, 0,
                self.robot_ip, self.robot_port,
            )
        except Exception as exc:
            # Most common cause: no robot listening at robot_ip:robot_port
            # (Choregraphe not running, or wrong port).  Degrade to NoOp
            # proxies so the HTTP layer keeps responding and the caller can
            # see ``simulation=True`` in /ping, instead of producing a half-
            # alive server with all proxies left as None.
            print("[ERR] ALBroker construction failed: {0}\n"
                  "      Falling back to simulation mode.".format(exc),
                  file=sys.stderr)
            self.simulation = True
            self._broker = None
            self._tts = _NoOp()
            self._behavior = _NoOp()
            self._motion = _NoOp()
            self._leds = _NoOp()
            self._audio_rec = _NoOp()
            self._memory = _NoOp()
            self._tablet = _NoOp()
            self._tracker = _NoOp()
            self._face_det = _NoOp()
            return True

        # ALAnimatedSpeech is the natural-speech-with-body-motion service.
        # Fall back to ALTextToSpeech if the animated variant isn't available.
        self._tts = _try_proxy("ALAnimatedSpeech")
        if isinstance(self._tts, _NoOp):
            self._tts = _try_proxy("ALTextToSpeech")

        self._behavior = _try_proxy("ALBehaviorManager")
        self._motion = _try_proxy("ALMotion")
        self._leds = _try_proxy("ALLeds")
        self._audio_rec = _try_proxy("ALAudioRecorder")
        self._memory = _try_proxy("ALMemory")
        self._tablet = _try_proxy("ALTabletService")
        self._tracker = _try_proxy("ALTracker")
        self._face_det = _try_proxy("ALFaceDetection")

        # Wake up the robot once on connect.  No-op on virtual Pepper.
        try:
            self._motion.wakeUp()
        except Exception:
            pass

        print("[OK] NaoqiFacade connected to {0}:{1} (listen={2})".format(
            self.robot_ip, self.robot_port, listen_ip))
        return True

    def disconnect(self):
        try:
            if self._motion:
                self._motion.rest()
        except Exception:
            pass
        try:
            if self._broker is not None:
                self._broker.shutdown()
        except Exception:
            pass

    # ── Action execution ─────────────────────────────────────────────────────

    def execute_action(self, action):
        """Execute a RobotAction dict on Pepper.

        :param action: dict with optional keys ``speech``, ``gesture``,
            ``movement``, ``emotion_led``, ``tablet_url``.
        :returns: dict with per-key boolean outcomes and any error strings.
        """
        result = {"ok": True, "executed": {}}

        with self._lock:
            # 1. LED colour first -- gives instant visual feedback while
            #    speech queues up.
            led = action.get("emotion_led")
            if led:
                ok, err = self._set_leds(led)
                result["executed"]["emotion_led"] = ok
                if err:
                    result.setdefault("errors", {})["emotion_led"] = err

            # 2. Gesture/behavior in parallel with speech so they overlap.
            gesture = action.get("gesture")
            if gesture and gesture in GESTURE_TO_BEHAVIOR:
                ok, err = self._run_behavior_async(GESTURE_TO_BEHAVIOR[gesture])
                result["executed"]["gesture"] = ok
                if err:
                    result.setdefault("errors", {})["gesture"] = err

            # 3. Tablet -- best effort, no-op on virtual robot.
            tablet_url = action.get("tablet_url") or (
                action.get("metadata", {}) or {}).get("tablet_url")
            if tablet_url:
                ok, err = self._show_on_tablet(tablet_url)
                result["executed"]["tablet"] = ok
                if err:
                    result.setdefault("errors", {})["tablet"] = err

            # 4. Movement (optional) -- guarded by a sanity speed cap.
            movement = action.get("movement")
            if movement:
                ok, err = self._move(movement)
                result["executed"]["movement"] = ok
                if err:
                    result.setdefault("errors", {})["movement"] = err

            # 5. Speech last so the LED+gesture have already kicked in.
            speech = action.get("speech")
            if speech:
                ok, err = self._speak(speech)
                result["executed"]["speech"] = ok
                if err:
                    result.setdefault("errors", {})["speech"] = err

        result["ok"] = "errors" not in result
        return result

    def _speak(self, text):
        try:
            text = text.encode("utf-8") if isinstance(text, type(u"")) else text
            try:
                # ALAnimatedSpeech.say(text, config_dict)
                self._tts.say(text, {"bodyLanguageMode": "contextual"})
            except TypeError:
                # ALTextToSpeech.say(text)
                self._tts.say(text)
            return True, None
        except Exception as exc:
            return False, str(exc)

    def _set_leds(self, hex_color):
        try:
            hex_color = hex_color.lstrip("#")
            r = int(hex_color[0:2], 16) / 255.0
            g = int(hex_color[2:4], 16) / 255.0
            b = int(hex_color[4:6], 16) / 255.0
            self._leds.fadeRGB(EYE_LED_GROUP, r, g, b, 0.3)
            return True, None
        except Exception as exc:
            return False, str(exc)

    def _run_behavior_async(self, behavior_name):
        try:
            # isBehaviorInstalled is unreliable across Pepper firmware versions
            # and returns None from our _NoOp stubs.  Treat None and True as
            # "go ahead"; only skip when explicitly False.
            try:
                installed = self._behavior.isBehaviorInstalled(behavior_name)
                if installed is False:
                    return False, "behavior not installed: {0}".format(behavior_name)
            except Exception:
                pass
            self._behavior.post.runBehavior(behavior_name)
            return True, None
        except Exception as exc:
            return False, str(exc)

    def _show_on_tablet(self, url):
        try:
            # ALTabletService is Pepper-only and absent on virtual robot.
            self._tablet.showImage(url)
            return True, None
        except Exception as exc:
            return False, str(exc)

    def _move(self, movement):
        """Drive the base with x/y/theta velocities.

        ``movement`` is a dict with ``x``, ``y``, ``theta`` (m/s, m/s, rad/s),
        and optional ``duration_s``.  All values are clamped to safe limits
        (|x|, |y| <= 0.3 m/s, |theta| <= 0.5 rad/s) regardless of what the
        LLM asks for.  Robots should not be moved by hallucination.
        """
        try:
            x = float(movement.get("x", 0.0))
            y = float(movement.get("y", 0.0))
            theta = float(movement.get("theta", 0.0))
            duration_s = float(movement.get("duration_s", 1.0))

            x = max(-0.3, min(0.3, x))
            y = max(-0.3, min(0.3, y))
            theta = max(-0.5, min(0.5, theta))
            duration_s = max(0.0, min(3.0, duration_s))

            self._motion.moveToward(x, y, theta)
            time.sleep(duration_s)
            self._motion.stopMove()
            return True, None
        except Exception as exc:
            return False, str(exc)

    # ── Sensors ──────────────────────────────────────────────────────────────

    def read_sensors(self):
        sensors = {
            "touch_sensors": {},
            "face_detected": False,
            "battery_level": 1.0,
        }

        for label, key in _TOUCH_EVENTS.items():
            try:
                val = self._memory.getData(key)
                sensors["touch_sensors"][label] = bool(val)
            except Exception:
                sensors["touch_sensors"][label] = False

        try:
            faces = self._memory.getData("FaceDetected")
            sensors["face_detected"] = bool(faces) and faces != []
        except Exception:
            sensors["face_detected"] = False

        try:
            sensors["battery_level"] = float(
                self._memory.getData("Device/SubDeviceList/Battery/Charge/Sensor/Value")
            )
        except Exception:
            sensors["battery_level"] = 1.0

        return sensors

    # ── Audio capture ────────────────────────────────────────────────────────

    def record_audio(self, duration_seconds=5, sample_rate=16000, channels=None):
        """Record audio from Pepper's front microphone and return base64 WAV.

        :param duration_seconds: how long to record.  Capped at 30s.
        :param sample_rate: 16000 / 22050 / 44100 / 48000.
        :param channels: 4-tuple of 0/1 (left, right, front, rear).
            Default ``[0, 0, 1, 0]`` = front mic only.
        :returns: dict ``{ok, audio_b64, error?, simulated?}``.
        """
        if channels is None:
            channels = [0, 0, 1, 0]
        duration_seconds = max(0.5, min(30.0, float(duration_seconds)))

        # Choregraphe virtual robot has no microphone -- short-circuit so the
        # caller can fall back to whatever (e.g. text mode).
        if isinstance(self._audio_rec, _NoOp) or self.simulation:
            return {"ok": False, "simulated": True,
                    "error": "no microphone on virtual Pepper", "audio_b64": ""}

        filename = "omnillm_capture_{0}.wav".format(int(time.time() * 1000))
        if not os.path.isdir(self._recordings_dir):
            try:
                os.makedirs(self._recordings_dir)
            except Exception:
                pass
        path = os.path.join(self._recordings_dir, filename)
        # NAOqi expects a forward-slash absolute path even on Windows-deployed
        # bridges; tempfile may give us backslashes, normalise.
        path_for_naoqi = path.replace("\\", "/")

        try:
            self._audio_rec.stopMicrophonesRecording()  # best-effort reset
        except Exception:
            pass

        try:
            with self._lock:
                self._audio_rec.startMicrophonesRecording(
                    path_for_naoqi, "wav", int(sample_rate), list(channels)
                )
            time.sleep(duration_seconds)
            with self._lock:
                self._audio_rec.stopMicrophonesRecording()
        except Exception as exc:
            return {"ok": False, "error": "recording failed: {0}".format(exc),
                    "audio_b64": ""}

        try:
            # The file is on the robot's filesystem.  When the bridge runs on
            # the robot itself this open() succeeds directly.  When the
            # bridge runs on a separate machine, you'd need to scp it back --
            # outside our scope; document that in the README.
            with open(path, "rb") as fh:
                data = fh.read()
            return {"ok": True, "audio_b64": base64.b64encode(data).decode("ascii"),
                    "samples": len(data), "path": path}
        except Exception as exc:
            return {"ok": False,
                    "error": "could not read WAV at {0}: {1}".format(path, exc),
                    "audio_b64": ""}

    # ── Face tracking ────────────────────────────────────────────────────────

    def start_tracker(self, target="Face"):
        try:
            self._tracker.setMode("Head")  # head-only, no base movement
            self._tracker.registerTarget(target, 0.1)
            self._tracker.track(target)
            return {"ok": True, "target": target}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def stop_tracker(self):
        try:
            self._tracker.stopTracker()
            self._tracker.unregisterAllTargets()
            return {"ok": True}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}


# ---------------------------------------------------------------------------
# HTTP layer
# ---------------------------------------------------------------------------

# Shared facade instance, populated by main() before serving.
_FACADE = None  # type: ignore


def _json_bytes(payload):
    return json.dumps(payload).encode("utf-8")


class _Handler(BaseHTTPRequestHandler):
    """Routes the small REST surface above onto NaoqiFacade methods."""

    server_version = "OmniLLMNaoqiBridge/1.0"

    def log_message(self, fmt, *args):
        # Quieter default log format -- the BaseHTTPServer one is noisy.
        sys.stderr.write("[bridge] {0} - {1}\n".format(
            self.address_string(), fmt % args))

    # ── helpers ──────────────────────────────────────────────────────────────

    def _send_json(self, status, payload):
        body = _json_bytes(payload)
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except Exception:
            length = 0
        if length <= 0:
            return {}
        raw = self.rfile.read(length)
        try:
            return json.loads(raw.decode("utf-8"))
        except Exception:
            return {}

    # ── GET routes ───────────────────────────────────────────────────────────

    def do_GET(self):  # noqa: N802 (BaseHTTPRequestHandler convention)
        try:
            if self.path == "/ping":
                self._send_json(200, {
                    "ok": True,
                    "naoqi": NAOQI_AVAILABLE,
                    "broker": BROKER_AVAILABLE,
                    "qi": QI_AVAILABLE,
                    "robot_ip": _FACADE.robot_ip if _FACADE else None,
                    "robot_port": _FACADE.robot_port if _FACADE else None,
                    "simulation": _FACADE.simulation if _FACADE else True,
                })
                return

            if self.path == "/sensors":
                self._send_json(200, _FACADE.read_sensors())
                return

            self._send_json(404, {"error": "unknown path: " + self.path})
        except Exception as exc:
            self._send_json(500, {"error": str(exc),
                                  "trace": traceback.format_exc()})

    # ── POST routes ──────────────────────────────────────────────────────────

    def do_POST(self):  # noqa: N802
        try:
            body = self._read_json()
            if self.path == "/action":
                self._send_json(200, _FACADE.execute_action(body))
                return

            if self.path == "/audio/record":
                self._send_json(200, _FACADE.record_audio(
                    duration_seconds=body.get("duration_seconds", 5),
                    sample_rate=body.get("sample_rate", 16000),
                    channels=body.get("channels"),
                ))
                return

            if self.path == "/tracker/start":
                self._send_json(200, _FACADE.start_tracker(
                    body.get("target", "Face")))
                return

            if self.path == "/tracker/stop":
                self._send_json(200, _FACADE.stop_tracker())
                return

            if self.path == "/disconnect":
                _FACADE.disconnect()
                self._send_json(200, {"ok": True})
                return

            self._send_json(404, {"error": "unknown path: " + self.path})
        except Exception as exc:
            self._send_json(500, {"error": str(exc),
                                  "trace": traceback.format_exc()})


class _ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    """Threaded server -- /sensors should not block /action."""
    daemon_threads = True
    allow_reuse_address = True


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="OmniLLM NAOqi Bridge Server (Python 2.7 + NAOqi 2.5)")
    parser.add_argument("--robot-ip", default="127.0.0.1",
                        help="Pepper IP (default: 127.0.0.1 for virtual)")
    parser.add_argument("--robot-port", type=int, default=62763,
                        help="NAOqi port (default: 62763 = Choregraphe locked port; "
                             "use 9559 for real Pepper)")
    parser.add_argument("--bridge-port", type=int, default=6000,
                        help="Port for THIS HTTP bridge (default: 6000)")
    parser.add_argument("--bind", default="127.0.0.1",
                        help="Address to bind the HTTP listener on (default: 127.0.0.1)")
    args = parser.parse_args()

    global _FACADE  # noqa: PLW0603
    _FACADE = NaoqiFacade(args.robot_ip, args.robot_port)
    if not _FACADE.connect():
        print("[ERR] NaoqiFacade connect failed -- continuing in simulation mode.",
              file=sys.stderr)

    httpd = _ThreadedHTTPServer((args.bind, args.bridge_port), _Handler)
    print("[OK] NAOqi bridge listening on http://{0}:{1}/ "
          "(robot at {2}:{3}, NAOqi={4})".format(
              args.bind, args.bridge_port, args.robot_ip, args.robot_port,
              NAOQI_AVAILABLE))
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[OK] Shutting down.")
    finally:
        _FACADE.disconnect()
        httpd.server_close()


if __name__ == "__main__":
    main()
