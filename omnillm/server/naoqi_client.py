"""NAOqi Python 2.7 Client for Pepper Robot.

This script runs ON or NEAR the Pepper robot using Python 2.7 + NAOqi SDK.
It serves as the bridge between the Pepper hardware (ALAudioDevice,
ALAnimatedSpeech, ALMotion, ALTabletService) and the Python 3.x AI server.

IMPORTANT: This file is intentionally written to be compatible with
Python 2.7 (NAOqi SDK limitation).  Do not use Python 3-only syntax.

Architecture
------------

    This script (Python 2.7, NAOqi process)
        │  Captures audio via ALAudioDevice
        │  POST audio + session info to AI server
        │  Receives RobotAction JSON
        │  Executes: ALAnimatedSpeech, ALMotion, ALTabletService
        ▼
    AI Server (Python 3.x, localhost:5000)

Usage (on Pepper or a Python 2.7 machine with NAOqi)
-----------------------------------------------------
    python naoqi_client.py --robot-ip 192.168.1.100 --server-ip localhost

Configuration
-------------
    --robot-ip   IP address of the Pepper robot (default: localhost)
    --robot-port NAOqi port (default: 9559)
    --server-ip  IP of the Python 3.x AI server (default: localhost)
    --server-port Port of the AI server (default: 5000)
    --participant Participant ID for the experiment session
    --condition   Experimental condition A-E (default: A)

NAOqi References
----------------
    http://doc.aldebaran.com/2-5/naoqi/audio/alaudiosource.html
    http://doc.aldebaran.com/2-5/naoqi/audio/alanimatedspeech.html
    http://doc.aldebaran.com/2-5/naoqi/motion/almotion.html
"""

from __future__ import print_function

import argparse
import base64
import json
import sys
import time
import uuid

# ---------------------------------------------------------------------------
# Python 2/3 compatible HTTP request (prefer urllib2 for Python 2.7)
# ---------------------------------------------------------------------------
try:
    import urllib2 as urllib_request
    from urllib2 import Request as UrlRequest
except ImportError:
    # Python 3 fallback (for testing outside NAOqi environment)
    import urllib.request as urllib_request  # type: ignore
    from urllib.request import Request as UrlRequest  # type: ignore

# ---------------------------------------------------------------------------
# NAOqi SDK (only available on/near Pepper hardware)
# ---------------------------------------------------------------------------
NAOQI_AVAILABLE = False
try:
    import qi  # type: ignore  # NAOqi 2.x (modern)
    NAOQI_AVAILABLE = True
except ImportError:
    try:
        import naoqi  # type: ignore  # NAOqi 1.x legacy
        NAOQI_AVAILABLE = True
    except ImportError:
        print("[WARN] NAOqi SDK not available — running in simulation mode.", file=sys.stderr)


# ── Constants ──────────────────────────────────────────────────────────────────

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

#: Pepper LED IDs for eye colour changes
EYE_LED_GROUP = "FaceLeds"


# ── PepperNAOqiClient ──────────────────────────────────────────────────────────

class PepperNAOqiClient(object):
    """Python 2.7 NAOqi client that bridges Pepper to the OmniLLM AI server.

    Listens for voice input, sends audio to the AI server for processing,
    and executes the returned RobotAction on the Pepper hardware.
    """

    def __init__(self, robot_ip, robot_port, server_ip, server_port, participant_id, condition):
        # type: (str, int, str, int, str, str) -> None
        self.robot_ip = robot_ip
        self.robot_port = robot_port
        self.server_url = "http://{}:{}".format(server_ip, server_port)
        self.participant_id = participant_id
        self.condition = condition
        self.session_id = str(uuid.uuid4())

        self._app = None
        self._audio_device = None
        self._animated_speech = None
        self._motion = None
        self._leds = None
        self._tablet = None
        self._behavior = None
        self._face_detection = None

        self._connected = False

    def connect(self):
        # type: () -> bool
        """Connect to Pepper via NAOqi and start required services."""
        if not NAOQI_AVAILABLE:
            print("[SIM] NAOqi not available — simulation mode")
            self._connected = True
            return True

        try:
            self._app = qi.Application(["PepperClient", "--qi-url={}:{}".format(
                self.robot_ip, self.robot_port
            )])
            self._app.start()
            session = self._app.session

            self._audio_device = session.service("ALAudioDevice")
            self._animated_speech = session.service("ALAnimatedSpeech")
            self._motion = session.service("ALMotion")
            self._leds = session.service("ALLeds")
            self._tablet = session.service("ALTabletService")
            self._behavior = session.service("ALBehaviorManager")
            self._face_detection = session.service("ALFaceDetection")

            # Wake up the robot
            self._motion.wakeUp()
            self._connected = True
            print("[OK] Connected to Pepper at {}:{}".format(self.robot_ip, self.robot_port))
            return True
        except Exception as exc:
            print("[ERR] Failed to connect to Pepper: {}".format(exc), file=sys.stderr)
            return False

    def run(self):
        # type: () -> None
        """Main interaction loop — runs until interrupted."""
        if not self._connected:
            if not self.connect():
                return

        print("[OK] OmniLLM Pepper client running. Session: {}".format(self.session_id))
        print("[OK] Press Ctrl+C to stop.")

        self._speak("Hello! I am Pepper, powered by OmniLLM. How can I help you today?")

        try:
            while True:
                self._interaction_loop()
        except KeyboardInterrupt:
            print("\n[OK] Shutting down.")
        finally:
            self._cleanup()

    def _interaction_loop(self):
        # type: () -> None
        """Wait for speech, send to server, execute response on robot."""
        print("[...] Waiting for speech input...")
        audio_bytes = self._record_audio(duration_seconds=5)

        if not audio_bytes:
            return

        print("[...] Sending audio to AI server...")
        response = self._send_audio(audio_bytes)

        if response is None:
            self._speak("I'm sorry, I could not connect to my AI brain. Please try again.")
            return

        self._execute_action(response)

    def _record_audio(self, duration_seconds=5):
        # type: (int) -> bytes
        """Record audio from Pepper's microphone.

        Returns raw WAV bytes.  In simulation mode, returns empty bytes.
        """
        if not NAOQI_AVAILABLE or self._audio_device is None:
            # Simulation: return a small silent WAV header
            return b""

        try:
            # Configure microphone
            self._audio_device.setClientPreferences(
                "OmniLLMCapture",
                16000,  # sample rate
                3,      # channel: front mic
                0,      # deinterleaved: no
            )
            # Record for duration_seconds (simplified — production uses ALSpeechRecognition)
            time.sleep(duration_seconds)
            # In real implementation: use ALAudioRecorder or callback-based capture
            # Returning placeholder; replace with actual WAV capture
            return b""
        except Exception as exc:
            print("[ERR] Audio capture error: {}".format(exc), file=sys.stderr)
            return b""

    def _send_audio(self, audio_bytes):
        # type: (bytes) -> dict
        """Send audio bytes to the AI server and return the RobotAction dict."""
        payload = json.dumps({
            "audio": base64.b64encode(audio_bytes).decode("utf-8") if audio_bytes else "",
            "participant_id": self.participant_id,
            "session_id": self.session_id,
            "condition": self.condition,
            "rag_enabled": True,
        }).encode("utf-8")

        try:
            req = UrlRequest(
                url="{}/interact".format(self.server_url),
                data=payload,
                headers={"Content-Type": "application/json"},
            )
            response = urllib_request.urlopen(req, timeout=30)
            return json.loads(response.read().decode("utf-8"))
        except Exception as exc:
            print("[ERR] Server request failed: {}".format(exc), file=sys.stderr)
            return None

    def _send_text(self, text):
        # type: (str) -> dict
        """Send a text utterance to the AI server (for testing without audio)."""
        payload = json.dumps({
            "text": text,
            "participant_id": self.participant_id,
            "session_id": self.session_id,
            "condition": self.condition,
            "rag_enabled": True,
        }).encode("utf-8")

        try:
            req = UrlRequest(
                url="{}/interact".format(self.server_url),
                data=payload,
                headers={"Content-Type": "application/json"},
            )
            response = urllib_request.urlopen(req, timeout=30)
            return json.loads(response.read().decode("utf-8"))
        except Exception as exc:
            print("[ERR] Server request failed: {}".format(exc), file=sys.stderr)
            return None

    def _execute_action(self, action):
        # type: (dict) -> None
        """Execute a RobotAction dict on the Pepper hardware."""
        speech = action.get("speech", "")
        gesture = action.get("gesture")
        led_color = action.get("emotion_led")

        # Set LED colour
        if led_color:
            self._set_leds(led_color)

        # Perform gesture (run behavior in parallel with speech)
        if gesture and gesture in GESTURE_TO_BEHAVIOR:
            self._run_behavior_async(GESTURE_TO_BEHAVIOR[gesture])

        # Speak the response
        if speech:
            self._speak(speech)

        print("[Pepper] Spoke: {}".format(speech[:80]))

    def _speak(self, text):
        # type: (str) -> None
        """Use ALAnimatedSpeech to speak text with gestures."""
        if not NAOQI_AVAILABLE or self._animated_speech is None:
            print("[SIM] SPEECH: {}".format(text))
            return
        try:
            config = {"bodyLanguageMode": "contextual"}
            self._animated_speech.say(str(text), config)
        except Exception as exc:
            print("[ERR] Speech error: {}".format(exc), file=sys.stderr)

    def _set_leds(self, hex_color):
        # type: (str) -> None
        """Set Pepper's eye LEDs to a hex colour."""
        if not NAOQI_AVAILABLE or self._leds is None:
            print("[SIM] LED: {}".format(hex_color))
            return
        try:
            # Convert hex to RGB (0.0–1.0)
            hex_color = hex_color.lstrip("#")
            r, g, b = (int(hex_color[i:i+2], 16) / 255.0 for i in (0, 2, 4))
            self._leds.fadeRGB(EYE_LED_GROUP, r, g, b, 0.3)
        except Exception as exc:
            print("[ERR] LED error: {}".format(exc), file=sys.stderr)

    def _run_behavior_async(self, behavior_name):
        # type: (str) -> None
        """Run a NAOqi behavior asynchronously."""
        if not NAOQI_AVAILABLE or self._behavior is None:
            print("[SIM] GESTURE: {}".format(behavior_name))
            return
        try:
            if self._behavior.isBehaviorInstalled(behavior_name):
                self._behavior.post.runBehavior(behavior_name)
        except Exception as exc:
            print("[ERR] Behavior error: {}".format(exc), file=sys.stderr)

    def _cleanup(self):
        # type: () -> None
        """Clean up NAOqi resources on shutdown."""
        try:
            if NAOQI_AVAILABLE and self._motion:
                self._motion.rest()
        except Exception:
            pass


# ── Entry point ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="OmniLLM NAOqi Client for Pepper")
    parser.add_argument("--robot-ip", default="localhost", help="Pepper robot IP")
    parser.add_argument("--robot-port", type=int, default=9559, help="NAOqi port")
    parser.add_argument("--server-ip", default="localhost", help="AI server IP")
    parser.add_argument("--server-port", type=int, default=5000, help="AI server port")
    parser.add_argument("--participant", default="P000", help="Participant ID")
    parser.add_argument("--condition", default="A", choices=["A", "B", "C", "D", "E"],
                        help="Experimental condition (A-E)")
    args = parser.parse_args()

    client = PepperNAOqiClient(
        robot_ip=args.robot_ip,
        robot_port=args.robot_port,
        server_ip=args.server_ip,
        server_port=args.server_port,
        participant_id=args.participant,
        condition=args.condition,
    )
    client.run()
