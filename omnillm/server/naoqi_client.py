# -*- coding: utf-8 -*-
"""NAOqi Python 2.7 Client for Pepper Robot -- production interaction loop.

Runs ON or NEAR Pepper using Python 2.7 + NAOqi 2.5.5.5.  Bridges the robot
hardware (microphone, speakers, tablet, LEDs, behaviors, face tracker) with
the Python 3.x OmniLLM AI server over HTTP.

This file is intentionally written Python-2.7 compatible -- do NOT use
Python 3-only syntax.

Three interaction triggers (selectable via ``--trigger``):

* ``touch``  -- front-head tactile sensor starts a fixed-duration recording
                (default 5 s) and ships it to the AI server.  Best for
                demos; no false triggers; no Whisper waste.
* ``vad``    -- continuous capture from front mic; ALAudioDevice level
                callback triggers an utterance when energy exceeds a
                threshold and falls back below it.  Burns more Whisper
                quota but feels natural.
* ``text``   -- ignore the microphone; read questions from stdin.  Useful
                for fast demos, CI, and the virtual robot (which has no
                mic).  Pairs with the ``--check-only`` bridge sanity test.

Topology
--------
::

    [ Pepper (real or virtual) ]
        ALBroker ALProxy
        ^
        |
    [ this Python 2.7 process ]                 <-- you are here
        |  POST /interact { audio | text, condition, ... }
        v
    [ Python 3.x OmniLLM AI server (Flask) ]
        Whisper -> LangGraph -> RobotAction JSON
        |
        '--> response comes back, this process executes it on Pepper.

NAOqi References
----------------
* http://doc.aldebaran.com/2-5/naoqi/audio/alaudiorecorder.html
* http://doc.aldebaran.com/2-5/naoqi/audio/alanimatedspeech.html
* http://doc.aldebaran.com/2-5/naoqi/motion/almotion.html
* http://doc.aldebaran.com/2-5/naoqi/interaction/tabletservice/altabletservice.html
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
import uuid

# ---------------------------------------------------------------------------
# Python 2/3 compatible HTTP request (prefer urllib2 for Python 2.7)
# ---------------------------------------------------------------------------
try:
    import urllib2 as urllib_request
    from urllib2 import Request as UrlRequest
except ImportError:
    import urllib.request as urllib_request  # type: ignore
    from urllib.request import Request as UrlRequest  # type: ignore

# raw_input exists in Python 2; map it to input() on Python 3 so the text
# loop still works if someone runs this file with Python 3 (e.g. for
# syntax-only smoke checks).
try:
    _read_line = raw_input  # type: ignore[name-defined]  # noqa: F821
except NameError:  # Python 3
    _read_line = input


# ---------------------------------------------------------------------------
# NAOqi SDK detection.  See pepper-windows-quirks memory for why ALBroker is
# preferred for Choregraphe virtual Pepper on Windows 11.
# ---------------------------------------------------------------------------
NAOQI_AVAILABLE = False
QI_AVAILABLE = False
BROKER_AVAILABLE = False

try:
    import qi  # type: ignore
    QI_AVAILABLE = True
    NAOQI_AVAILABLE = True
except Exception:
    # ImportError when SDK is missing.  SyntaxError when pynaoqi 2.5's
    # qi/__init__.py (Python-2 source) is on PYTHONPATH but we're running
    # under Python 3 -- the file uses `async` as an identifier and Python 3
    # rejects it at parse time.  Either way we just degrade gracefully.
    pass

try:
    from naoqi import ALBroker, ALProxy  # type: ignore
    BROKER_AVAILABLE = True
    NAOQI_AVAILABLE = True
except Exception:
    pass

if not NAOQI_AVAILABLE:
    print("[WARN] NAOqi SDK not available -- running in simulation mode.",
          file=sys.stderr)


# ── Gesture / LED maps (mirror naoqi_bridge_server.py to keep behaviors in sync)

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


def _try_proxy(service_name):
    """Best-effort ALProxy lookup; returns None if the service isn't available.

    NAOqi 2.5's ALProxy constructor occasionally returns ``None`` instead of
    raising when the named service is unreachable -- we normalise both into
    ``None`` so the caller's truthiness check works the same way.
    """
    if not BROKER_AVAILABLE:
        return None
    try:
        proxy = ALProxy(service_name)
    except Exception as exc:
        print("[WARN] {0} not available: {1}".format(service_name, exc),
              file=sys.stderr)
        return None
    return proxy if proxy is not None else None


# ── Client ────────────────────────────────────────────────────────────────────

class PepperNAOqiClient(object):
    """Python 2.7 NAOqi client.  See module docstring for architecture."""

    def __init__(self, robot_ip, robot_port, server_ip, server_port,
                 participant_id, condition, trigger="text", use_broker=True,
                 track_face=False, record_seconds=5):
        # type: (str, int, str, int, str, str, str, bool, bool, int) -> None
        self.robot_ip = robot_ip
        self.robot_port = robot_port
        self.server_url = "http://{0}:{1}".format(server_ip, server_port)
        self.participant_id = participant_id
        self.condition = condition
        self.session_id = str(uuid.uuid4())
        self.trigger = trigger
        self.use_broker = use_broker
        self.track_face = track_face
        self.record_seconds = record_seconds

        self._broker = None
        self._app = None

        self._tts = None         # ALAnimatedSpeech (or ALTextToSpeech fallback)
        self._motion = None      # ALMotion
        self._leds = None        # ALLeds
        self._memory = None      # ALMemory
        self._behavior = None    # ALBehaviorManager
        self._audio_rec = None   # ALAudioRecorder (real Pepper only)
        self._audio_dev = None   # ALAudioDevice (VAD energy callback)
        self._tablet = None      # ALTabletService
        self._tracker = None     # ALTracker

        self._connected = False
        self._touch_event = threading.Event()  # set by tactile callback
        self._stop_flag = threading.Event()

        self._recordings_dir = "/home/nao/recordings/microphones"
        if not os.path.isdir(self._recordings_dir):
            self._recordings_dir = tempfile.gettempdir()

    # ── Connection ───────────────────────────────────────────────────────────

    def connect(self):
        # type: () -> bool
        if not NAOQI_AVAILABLE:
            print("[SIM] NAOqi not available -- simulation mode")
            self._connected = True
            return True

        use_broker = self.use_broker or not QI_AVAILABLE
        if use_broker and not BROKER_AVAILABLE:
            print("[ERR] ALBroker requested but naoqi module not importable.",
                  file=sys.stderr)
            return False

        try:
            if use_broker:
                listen_ip = ("127.0.0.1"
                             if self.robot_ip in ("127.0.0.1", "localhost")
                             else "0.0.0.0")
                self._broker = ALBroker("OmniLLMBroker", listen_ip, 0,
                                        self.robot_ip, self.robot_port)
                self._tts = _try_proxy("ALAnimatedSpeech") or _try_proxy("ALTextToSpeech")
                self._motion = _try_proxy("ALMotion")
                self._leds = _try_proxy("ALLeds")
                self._memory = _try_proxy("ALMemory")
                self._behavior = _try_proxy("ALBehaviorManager")
                self._audio_rec = _try_proxy("ALAudioRecorder")
                self._audio_dev = _try_proxy("ALAudioDevice")
                self._tablet = _try_proxy("ALTabletService")
                self._tracker = _try_proxy("ALTracker")
            else:
                self._app = qi.Application([
                    "PepperClient",
                    "--qi-url=tcp://{0}:{1}".format(self.robot_ip, self.robot_port),
                ])
                self._app.start()
                s = self._app.session
                self._tts = s.service("ALAnimatedSpeech")
                self._motion = s.service("ALMotion")
                self._leds = s.service("ALLeds")
                self._memory = s.service("ALMemory")
                self._behavior = s.service("ALBehaviorManager")
                self._audio_rec = s.service("ALAudioRecorder")
                self._audio_dev = s.service("ALAudioDevice")
                self._tablet = s.service("ALTabletService")
                self._tracker = s.service("ALTracker")

            try:
                self._motion.wakeUp()
            except Exception:
                pass

            self._connected = True
            print("[OK] Connected to Pepper at {0}:{1} via {2} mode".format(
                self.robot_ip, self.robot_port,
                "broker" if use_broker else "qi"))
            return True
        except Exception as exc:
            print("[ERR] Failed to connect to Pepper: {0}".format(exc),
                  file=sys.stderr)
            return False

    # ── Main loop ────────────────────────────────────────────────────────────

    def run(self):
        # type: () -> None
        if not self._connected:
            if not self.connect():
                return

        print("[OK] OmniLLM Pepper client running. Session: {0}".format(self.session_id))
        print("[OK] Trigger mode: {0}".format(self.trigger))
        print("[OK] Press Ctrl+C to stop.")

        self._speak("Hello! I am Pepper, powered by OmniLLM. How can I help you today?")

        if self.track_face:
            self._start_face_tracker()

        try:
            if self.trigger == "text":
                self._text_loop()
            elif self.trigger == "touch":
                self._touch_loop()
            elif self.trigger == "vad":
                self._vad_loop()
            else:
                print("[ERR] Unknown trigger mode: {0}".format(self.trigger),
                      file=sys.stderr)
        except KeyboardInterrupt:
            print("\n[OK] Shutting down.")
        finally:
            self._stop_flag.set()
            if self.track_face:
                self._stop_face_tracker()
            self._cleanup()

    # ── Trigger: TEXT ────────────────────────────────────────────────────────

    def _text_loop(self):
        # type: () -> None
        print("[text] Type a question and hit Enter.  Empty line + Enter quits.")
        while not self._stop_flag.is_set():
            try:
                line = _read_line("> ").strip()
            except (EOFError, KeyboardInterrupt):
                break
            if not line:
                break
            response = self._send_text(line)
            if response is None:
                self._speak("I'm sorry, I could not connect to my AI brain.")
                continue
            self._execute_action(response)

    # ── Trigger: TOUCH ───────────────────────────────────────────────────────

    def _touch_loop(self):
        # type: () -> None
        if self._memory is None:
            print("[ERR] No ALMemory proxy -- cannot subscribe to touch events.",
                  file=sys.stderr)
            return

        # Subscribe to the front-head tactile sensor.  Pepper exposes it via
        # ALMemory event "FrontTactilTouched".  Callback runs in NAOqi's
        # thread; we just set a threading.Event so the main loop wakes up.
        subscriber = None
        try:
            subscriber = self._memory.subscriber("FrontTactilTouched")
            subscriber.signal.connect(self._on_touch)
            print("[touch] Subscribed to FrontTactilTouched. "
                  "Touch the front of Pepper's head to talk.")
        except Exception as exc:
            print("[WARN] could not subscribe to FrontTactilTouched: {0} "
                  "-- falling back to polling.".format(exc), file=sys.stderr)
            subscriber = None

        try:
            while not self._stop_flag.is_set():
                if subscriber is None:
                    # Polling fallback (used by virtual Pepper which doesn't
                    # always fire subscriber callbacks reliably).
                    self._poll_touch()

                if not self._touch_event.wait(timeout=0.5):
                    continue
                self._touch_event.clear()

                print("[touch] Touch detected -- recording {0}s...".format(
                    self.record_seconds))
                self._set_leds("#FFFF00")  # yellow: listening
                audio = self._record_audio(self.record_seconds)
                self._set_leds("#44AAFF")  # blue: thinking

                response = self._send_audio(audio) if audio else self._send_text(
                    "(no audio captured)")
                if response is None:
                    self._speak("I'm sorry, I could not connect to my AI brain.")
                    continue
                self._execute_action(response)
        finally:
            if subscriber is not None:
                try:
                    subscriber.signal.disconnect()
                except Exception:
                    pass

    def _on_touch(self, value):
        """Callback fired by ALMemory subscriber when the front head is touched.

        ``value`` is the new state (1.0 = pressed, 0.0 = released).  We
        only react to PRESS events to avoid double-triggering on release.
        """
        try:
            pressed = bool(value)
        except Exception:
            pressed = False
        if pressed:
            self._touch_event.set()

    def _poll_touch(self):
        # type: () -> None
        try:
            val = self._memory.getData("FrontTactilTouched")
            if bool(val):
                self._touch_event.set()
        except Exception:
            pass

    # ── Trigger: VAD ─────────────────────────────────────────────────────────

    def _vad_loop(self):
        # type: () -> None
        """Continuous capture with naive energy-threshold VAD.

        Implementation note: a proper VAD on Pepper subscribes ALAudioDevice
        to its raw stream, but that requires writing a C++ module bound via
        ``addModule``.  Here we approximate by recording fixed 1s chunks
        and computing PCM RMS in Python -- crude but works for demo use.
        """
        if self._audio_rec is None:
            print("[ERR] ALAudioRecorder not available; VAD mode requires real Pepper. "
                  "Switch to --trigger text or touch.", file=sys.stderr)
            return

        SILENCE_RMS = 250        # below this = silence (16-bit PCM)
        TRIGGER_RMS = 800        # above this = treat as speech
        MAX_UTTERANCE_S = 8.0
        MIN_UTTERANCE_S = 0.6

        print("[vad] Continuous listening (energy gate). Talk to Pepper any time.")
        speaking = False
        utterance_chunks = []
        utterance_start = 0.0

        while not self._stop_flag.is_set():
            chunk = self._record_audio(1)  # 1 second chunk
            rms = _wav_rms(chunk)
            if not speaking and rms > TRIGGER_RMS:
                speaking = True
                utterance_chunks = [chunk]
                utterance_start = time.time()
                self._set_leds("#FFFF00")
            elif speaking:
                utterance_chunks.append(chunk)
                if rms < SILENCE_RMS or (time.time() - utterance_start) > MAX_UTTERANCE_S:
                    speaking = False
                    if (time.time() - utterance_start) < MIN_UTTERANCE_S:
                        print("[vad] utterance too short, skipping.")
                        self._set_leds("#44AAFF")
                        continue
                    audio = _concat_wavs(utterance_chunks)
                    self._set_leds("#44AAFF")
                    response = self._send_audio(audio)
                    if response is None:
                        self._speak("I'm sorry, I could not connect to my AI brain.")
                        continue
                    self._execute_action(response)

    # ── Audio capture (ALAudioRecorder) ──────────────────────────────────────

    def _record_audio(self, duration_seconds):
        # type: (int) -> bytes
        """Record ``duration_seconds`` of audio from the front microphone.

        Returns the raw WAV bytes, or ``b""`` if recording isn't supported
        (e.g. virtual Pepper or simulation mode).
        """
        if not NAOQI_AVAILABLE or self._audio_rec is None:
            time.sleep(duration_seconds)
            return b""

        filename = "omnillm_capture_{0}.wav".format(int(time.time() * 1000))
        path = os.path.join(self._recordings_dir, filename).replace("\\", "/")

        try:
            try:
                self._audio_rec.stopMicrophonesRecording()
            except Exception:
                pass
            # channels: [left, right, front, rear] -- front mic only.
            self._audio_rec.startMicrophonesRecording(path, "wav", 16000, [0, 0, 1, 0])
            time.sleep(duration_seconds)
            self._audio_rec.stopMicrophonesRecording()
        except Exception as exc:
            print("[ERR] Audio capture error: {0}".format(exc), file=sys.stderr)
            return b""

        try:
            with open(path, "rb") as fh:
                data = fh.read()
            try:
                os.remove(path)
            except Exception:
                pass
            return data
        except Exception as exc:
            print("[ERR] Could not read recorded WAV: {0}".format(exc), file=sys.stderr)
            return b""

    # ── HTTP to AI server ────────────────────────────────────────────────────

    def _send_audio(self, audio_bytes):
        # type: (bytes) -> dict
        payload = json.dumps({
            "audio": base64.b64encode(audio_bytes).decode("utf-8") if audio_bytes else "",
            "participant_id": self.participant_id,
            "session_id": self.session_id,
            "condition": self.condition,
            "rag_enabled": True,
        }).encode("utf-8")
        return self._post_json("/interact", payload)

    def _send_text(self, text):
        # type: (str) -> dict
        payload = json.dumps({
            "text": text,
            "participant_id": self.participant_id,
            "session_id": self.session_id,
            "condition": self.condition,
            "rag_enabled": True,
        }).encode("utf-8")
        return self._post_json("/interact", payload)

    def _post_json(self, path, payload):
        try:
            req = UrlRequest(
                url=self.server_url + path,
                data=payload,
                headers={"Content-Type": "application/json"},
            )
            response = urllib_request.urlopen(req, timeout=60)
            return json.loads(response.read().decode("utf-8"))
        except Exception as exc:
            print("[ERR] Server request failed: {0}".format(exc), file=sys.stderr)
            return None

    # ── Action execution on Pepper ───────────────────────────────────────────

    def _execute_action(self, action):
        # type: (dict) -> None
        if not action:
            return
        speech = action.get("speech", "") or action.get("response_text", "")
        gesture = action.get("gesture")
        led_color = action.get("emotion_led")
        metadata = action.get("metadata", {}) or {}
        tablet_url = action.get("tablet_url") or metadata.get("tablet_url")

        if led_color:
            self._set_leds(led_color)
        if gesture and gesture in GESTURE_TO_BEHAVIOR:
            self._run_behavior_async(GESTURE_TO_BEHAVIOR[gesture])
        if tablet_url:
            self._show_on_tablet(tablet_url)
        if speech:
            self._speak(speech)
        print("[Pepper] Spoke: {0}".format(speech[:80] if speech else "(nothing)"))

    def _speak(self, text):
        if not NAOQI_AVAILABLE or self._tts is None:
            print("[SIM] SPEECH: {0}".format(text))
            return
        try:
            text = text.encode("utf-8") if isinstance(text, unicode) else text  # noqa: F821
        except NameError:
            # Python 3 fallback
            pass
        try:
            try:
                self._tts.say(text, {"bodyLanguageMode": "contextual"})
            except TypeError:
                self._tts.say(text)
        except Exception as exc:
            print("[ERR] Speech error: {0}".format(exc), file=sys.stderr)

    def _set_leds(self, hex_color):
        if not NAOQI_AVAILABLE or self._leds is None:
            print("[SIM] LED: {0}".format(hex_color))
            return
        try:
            hex_color = hex_color.lstrip("#")
            r = int(hex_color[0:2], 16) / 255.0
            g = int(hex_color[2:4], 16) / 255.0
            b = int(hex_color[4:6], 16) / 255.0
            self._leds.fadeRGB(EYE_LED_GROUP, r, g, b, 0.3)
        except Exception as exc:
            print("[ERR] LED error: {0}".format(exc), file=sys.stderr)

    def _run_behavior_async(self, behavior_name):
        if not NAOQI_AVAILABLE or self._behavior is None:
            print("[SIM] GESTURE: {0}".format(behavior_name))
            return
        try:
            try:
                if not self._behavior.isBehaviorInstalled(behavior_name):
                    return
            except Exception:
                pass
            self._behavior.post.runBehavior(behavior_name)
        except Exception as exc:
            print("[ERR] Behavior error: {0}".format(exc), file=sys.stderr)

    def _show_on_tablet(self, url):
        if self._tablet is None:
            print("[SIM] TABLET: {0}".format(url))
            return
        try:
            self._tablet.showImage(url)
        except Exception as exc:
            print("[WARN] Tablet error: {0}".format(exc), file=sys.stderr)

    # ── Face tracking ────────────────────────────────────────────────────────

    def _start_face_tracker(self):
        if self._tracker is None:
            print("[SIM] face tracking unavailable")
            return
        try:
            self._tracker.setMode("Head")
            self._tracker.registerTarget("Face", 0.1)
            self._tracker.track("Face")
            print("[OK] Face tracker started.")
        except Exception as exc:
            print("[WARN] Face tracker start failed: {0}".format(exc),
                  file=sys.stderr)

    def _stop_face_tracker(self):
        if self._tracker is None:
            return
        try:
            self._tracker.stopTracker()
            self._tracker.unregisterAllTargets()
            print("[OK] Face tracker stopped.")
        except Exception:
            pass

    # ── Cleanup ──────────────────────────────────────────────────────────────

    def _cleanup(self):
        try:
            if NAOQI_AVAILABLE and self._motion:
                self._motion.rest()
        except Exception:
            pass
        if self._broker is not None:
            try:
                self._broker.shutdown()
            except Exception:
                pass


# ── Helpers (PCM math, WAV concat) ────────────────────────────────────────────

def _wav_rms(wav_bytes):
    """Compute RMS of 16-bit PCM samples inside a WAV blob (header-tolerant).

    Returns 0 when the buffer is empty or unparseable so VAD fails closed.
    """
    if not wav_bytes:
        return 0
    try:
        import wave
        import audioop
        import io
        bio = io.BytesIO(wav_bytes)
        with wave.open(bio, "rb") as wf:
            frames = wf.readframes(wf.getnframes())
            sampwidth = wf.getsampwidth()
        if not frames:
            return 0
        return audioop.rms(frames, sampwidth)
    except Exception:
        return 0


def _concat_wavs(wav_chunks):
    """Concatenate a list of WAV blobs into one WAV (assumes same format).

    Naive implementation -- keeps the header of the first chunk and appends
    only the PCM payload of the rest.  Good enough to ship to Whisper.
    """
    if not wav_chunks:
        return b""
    if len(wav_chunks) == 1:
        return wav_chunks[0]
    try:
        import wave
        import io
        first = wav_chunks[0]
        bio_in = io.BytesIO(first)
        with wave.open(bio_in, "rb") as wf:
            params = wf.getparams()
            payload = wf.readframes(wf.getnframes())
        for chunk in wav_chunks[1:]:
            try:
                with wave.open(io.BytesIO(chunk), "rb") as wf:
                    payload += wf.readframes(wf.getnframes())
            except Exception:
                continue
        bio_out = io.BytesIO()
        with wave.open(bio_out, "wb") as wf:
            wf.setparams(params)
            wf.writeframes(payload)
        return bio_out.getvalue()
    except Exception:
        return wav_chunks[0]


# ── Entry point ──────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="OmniLLM NAOqi Client for Pepper")
    parser.add_argument("--robot-ip", default="127.0.0.1", help="Pepper IP")
    parser.add_argument("--robot-port", type=int, default=9559, help="NAOqi port")
    parser.add_argument("--server-ip", default="127.0.0.1", help="AI server IP")
    parser.add_argument("--server-port", type=int, default=5000, help="AI server port")
    parser.add_argument("--participant", default="P000", help="Participant ID")
    parser.add_argument("--condition", default="A", choices=["A", "B", "C", "D", "E"],
                        help="Experimental condition (A-E)")
    parser.add_argument("--trigger", default="text", choices=["touch", "vad", "text"],
                        help="How to start a turn (default: text)")
    parser.add_argument("--use-broker", action="store_true", default=True,
                        help="Use legacy ALBroker pattern (default; needed for "
                             "Choregraphe virtual robot on Windows 11)")
    parser.add_argument("--no-broker", dest="use_broker", action="store_false",
                        help="Use modern qi.Application instead of ALBroker.")
    parser.add_argument("--track-face", action="store_true",
                        help="Enable ALTracker face-follow during the session.")
    parser.add_argument("--record-seconds", type=int, default=5,
                        help="Touch-mode recording duration (default 5s).")
    args = parser.parse_args()

    client = PepperNAOqiClient(
        robot_ip=args.robot_ip,
        robot_port=args.robot_port,
        server_ip=args.server_ip,
        server_port=args.server_port,
        participant_id=args.participant,
        condition=args.condition,
        trigger=args.trigger,
        use_broker=args.use_broker,
        track_face=args.track_face,
        record_seconds=args.record_seconds,
    )
    client.run()


if __name__ == "__main__":
    main()
