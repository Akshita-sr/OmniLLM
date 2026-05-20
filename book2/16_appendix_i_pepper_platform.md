\newpage

# Appendix I — The Pepper Platform Reference

> *Everything you need to know about the **hardware**, **NAOqi middleware**, **Choregraphe IDE**, and **community-validated bridge patterns** — collected in one place. Parts I–VI use Pepper as a black box; this appendix opens the black box.*
>
> *Ported and updated from the first-edition book's Part IV (Chapters 23–27A). Knowledge-base references have been updated from the legacy IRAI Lab to the current **DIBRIS / Sgorbissa HRI Lab** context.*

\newpage

## I.1 — Meet Pepper: The Hardware Inside the Plastic Shell

### At a Glance

Pepper is a **120 cm**, **28 kg** humanoid robot from SoftBank Robotics. **20 degrees of freedom**. Intel Atom CPU, 4 GB RAM. Four microphones in the head. Two ear speakers. A 10.1″ chest tablet. Eye LEDs. Three omnidirectional wheels at the base. ~8–10 hours of battery. Knowing this hardware shapes how you think about the AI server's job.

### I.1.1 — Physical Specs

| Attribute | Value |
|-----------|-------|
| Height | 120 cm |
| Weight | 28 kg |
| Degrees of freedom | 20 (head 2, each arm/hand 6, hip 2, knee 1, base wheels 3) |
| Battery | 30 Ah / 795 Wh lithium-ion (~8–10 hours active) |
| Onboard CPU | Intel Atom E3845 quad-core @ 1.91 GHz |
| Onboard RAM | 4 GB DDR3 |
| Onboard storage | 8 GB flash + microSD slot |
| Operating system | NAOqi OS (modified Gentoo Linux) |
| Onboard Python | Python 2.7 |
| Tablet OS | Android 4.4 (1.3 GHz quad-core ARM Cortex-A7, 1 GB RAM, 32 GB storage) |

### I.1.2 — Sensors at a Glance

```
                 +---------------------+
                 |  HEAD                |
                 |  * 2x 5 MP RGB cam  |
                 |     (forehead, chin) |
                 |  * ASUS Xtion 3D    |
                 |     depth sensor    |
                 |  * 4x microphones   |
                 |  * 3x capacitive    |
                 |     touch sensors   |
                 |  * Eye LEDs (RGB)   |
                 +------+--------------+
                        |
                +-------+--------+
                |  TORSO          |
                |  * 10.1" tablet |
                |     1280x800    |
                |  * Hand touch   |
                |     sensors     |
                |  * IMU          |
                +-------+---------+
                        |
              +---------+----------+
              |  BASE                |
              |  * 3x wheels        |
              |  * 2x sonar         |
              |  * 6x laser line    |
              |  * 2x infrared      |
              |  * 3x bumper        |
              |  * IMU              |
              +---------------------+
```

The cameras and depth sensor are not currently consumed by OmniLLM; they are available for the vision-language extensions discussed in Chapter 33.

### I.1.3 — The Tablet

The chest tablet is a **separate Android computer** communicating with the head computer over an internal network at IP `198.18.0.1`. From OmniLLM's perspective it is just a NAOqi service: `ALTabletService`. You can `loadUrl()` to display web content, `showImage()` to display an image, or `executeJS()` to run JavaScript in the browser.

For the Embodied LLM Arena experimental study, the tablet is mostly unused (the four task types do not need a screen), but it is available for showing maps during navigation tasks. A tablet-based questionnaire UI is one of the short-term improvements in Chapter 32.

### I.1.4 — The Speaker / Microphone Pair

Pepper has **four microphones** in its head, and the NAOqi audio device exposes all four channels at 48 kHz, **or** a single mixed-down channel at **16 kHz**. OmniLLM uses the 16 kHz mono channel — the same format Whisper expects.

The "front" channel (channel 3 in the four-channel layout) is the most useful for one-on-one conversation. `ALAudioDevice.setClientPreferences` configures it:

```python
self._audio_device.setClientPreferences(
    "OmniLLMCapture",
    16000,    # sample rate
    3,        # channel: front
    0,        # deinterleaved: no
)
```

### I.1.5 — Eye LEDs as a Communication Channel

The eye LEDs are addressable RGB LEDs exposed through `ALLeds`:

```python
leds.fadeRGB("FaceLeds", r, g, b, fade_duration_seconds)
```

OmniLLM's gesture planner (Chapter 13.3) uses eye colour to communicate **interaction mode**:

| Colour | Hex | Mode |
|--------|-----|------|
| Friendly green | `#00FF88` | Greeting, acknowledgement, social |
| Calm blue | `#00AAFF` | Navigation guidance |
| Default blue | `#44AAFF` | Idle / neutral |
| White | `#FFFFFF` | Attention to tablet |
| Yellow | `#FFFF00` | Thinking |
| Red-orange | `#FF4400` | Confused / error |
| Warm orange | `#FF8800` | Goodbye |

This is **not arbitrary aesthetic.** Eye colour is a documented HRI signal that participants register subconsciously. Switching from blue (navigation) to green (success) reinforces the spoken response.

### I.1.6 — Why `ALAnimatedSpeech`, Not Plain `ALTextToSpeech`

NAOqi has two text-to-speech services:

- **`ALTextToSpeech`** — voice only. The robot is rigid while speaking.
- **`ALAnimatedSpeech`** — voice + automatic body gestures synchronised to the speech content.

OmniLLM uses `ALAnimatedSpeech` **always**, for three reasons:

1. Embodied perception research (Bartneck 2009; Andrist et al. 2014) consistently shows that "talking head" robots are rated lower on naturalness and intelligence.
2. Pepper has joints — not using them is wasteful.
3. The cost is zero — `ALAnimatedSpeech` is built-in.

The configuration that produces sensible motion:

```python
config = {"bodyLanguageMode": "contextual"}
animated_speech.say(text, config)
```

`bodyLanguageMode` accepts `"contextual"` (gestures match speech content — **recommended**), `"random"` (random gestures — looks unhinged), or `"disabled"` (back to talking-head mode).

### I.1.7 — Hardware End-of-Life Note

Aldebaran (the original company behind Pepper and NAO) filed for bankruptcy in **February 2025**. Maxvision Technology (Shenzhen) acquired the IP in **July 2025**. **No new units are being manufactured.** Existing units continue to work; spare parts are increasingly hard to source.

This is one reason OmniLLM is designed to be platform-portable: the abstract `RobotBridge` interface (Chapter 13.1) can target NAO, Buddy, or any future robot you point it at. The brain is platform-agnostic; only the bridge implementation is Pepper-specific.

\newpage

## I.2 — NAOqi 101: The Operating System That Runs on Pepper

### At a Glance

**NAOqi** is the middleware that makes Pepper a robot rather than a Linux box on wheels. It is a **service broker on TCP port 9559** that exposes named services (`ALAnimatedSpeech`, `ALMotion`, etc.) to any client that connects with the right credentials. Its Python binding is **Python 2.7 only**.

### I.2.1 — What NAOqi Is

Imagine the robot as a Linux server, and NAOqi as the daemon process that runs on top of Linux providing all the high-level robot abstractions:

```
              +----------------------------------------------+
              |  Hardware                                    |
              |  motors, sensors, speakers, microphones      |
              +----------------+-----------------------------+
                               ^
              +----------------+-----------------------------+
              |  Linux kernel (Gentoo)                       |
              |  device drivers                              |
              +----------------+-----------------------------+
                               ^
              +----------------+-----------------------------+
              |  NAOqi daemon                                |
              |  starts ~50 services on port 9559            |
              |  ALMotion, ALMemory, ALAnimatedSpeech,       |
              |  ALAudioDevice, ALLeds, ALBehaviorManager,   |
              |  ALFaceDetection, ALTabletService, ...       |
              +----------------+-----------------------------+
                               ^
              +----------------+-----------------------------+
              |  Clients                                     |
              |  * Choregraphe over the LAN                  |
              |  * Custom Python 2.7 clients (like ours)     |
              |  * Custom C++ clients                        |
              +----------------------------------------------+
```

### I.2.2 — The Service Broker Model

NAOqi is built around a **service broker**. Every NAOqi service registers itself with the broker on startup; clients look up services by name and get a proxy object that can call methods on them. Services can run **locally** (in the same process — fast, zero-copy) or **remotely** (over TCP — slower, fully serialised).

Two ways to call a service from Python:

```python
# Modern (NAOqi 2.x)
import qi
session = qi.Session()
session.connect("tcp://192.168.1.100:9559")
tts = session.service("ALAnimatedSpeech")
tts.say("Hello!")

# Legacy (NAOqi 1.x)
from naoqi import ALProxy
tts = ALProxy("ALAnimatedSpeech", "192.168.1.100", 9559)
tts.say("Hello!")
```

OmniLLM's `naoqi_client.py` tries `qi` first, falls back to `naoqi`, so it works against both NAOqi 1.x and 2.x.

### I.2.3 — The Twelve Services You Need to Know

| Service | What it does |
|---------|--------------|
| `ALMotion` | Joint control. `wakeUp()` enables motors; `rest()` disables. `setAngles()` moves a joint. `moveTo()` walks. |
| `ALAnimatedSpeech` | TTS with body gestures. `say(text, config)`. |
| `ALTextToSpeech` | TTS without gestures. Use when you need a stationary robot. |
| `ALAudioDevice` | Microphone capture. `setClientPreferences()` + `subscribe()`. |
| `ALAudioRecorder` | Record audio to a file. Simpler than callback-based capture. |
| `ALLeds` | LED control. `fadeRGB("FaceLeds", r, g, b, duration)`. |
| `ALBehaviorManager` | Run installed animations. `runBehavior("path/to/behavior")`. `isBehaviorInstalled()`. |
| `ALMemory` | Key-value store / event bus. `getData(key)`, `subscriber(event)`. |
| `ALFaceDetection` | Vision: detect faces. Subscribe to the `"FaceDetected"` event. |
| `ALSpeechRecognition` | On-board speech recognition (limited vocabulary). Mostly inadequate; OmniLLM uses Whisper instead. |
| `ALTabletService` | Chest tablet display. `loadUrl()`, `showImage()`. |
| `ALRobotPosture` | Whole-body posture. `goToPosture("Stand", 0.8)`. |

Plus two more OmniLLM specifically uses:

- **`ALTracker`** — follows a target (face, sound, marker). Critical for the face-tracking protocol in Chapter 21.
- **`ALAutonomousLife`** — controls Pepper's autonomous "stay alive" behaviours. Calling `setState("disabled")` on connect is recommended to prevent Pepper's stock dialogue from talking over your LLM (see §I.5).

### I.2.4 — The Python 2.7 Constraint Explained

The NAOqi Python binding (`pynaoqi`) is a platform-specific archive shipped on SoftBank's developer portal. It is a CPython extension that **depends on the binary layout of Python 2.7 specifically.** There is no port to Python 3 that exposes the full service surface.

A community-built `qi 3.1.5` package (`pip install qi==3.1.5`) exists for Python 3 on Linux x86_64, but several services are broken: touch detection, audio callbacks, certain event subscriptions. It is unsuitable for production use.

The conclusion: **NAOqi requires Python 2.7. Modern AI libraries require Python 3.11+. They cannot live in the same process.** Hence the two-process HTTP bridge of Chapter 16 and §I.4 below.

### I.2.5 — Lifecycle Quirks

Two NAOqi quirks that will trip you up:

1. **Stiffness must be enabled before any movement.** A fresh-booted Pepper has zero stiffness — its motors are dead weight. You must call `motion.wakeUp()` (or `motion.setStiffnesses("Body", 1.0)`) first. `ALAnimatedSpeech` will speak without stiffness, but the body language will not animate.

2. **`ALAudioRecorder` and `ALSpeechRecognition` cannot share the microphone.** They both subscribe to the audio device exclusively. You must `unsubscribe` one before using the other. OmniLLM uses neither directly — it captures via `ALAudioDevice` and sends the bytes to Whisper.

### I.2.6 — Connection From Your PC

To connect from your PC, you need:

1. **Network access.** Same Wi-Fi as Pepper, or wired to the same LAN.
2. **Pepper's IP address.** Press the chest button once and Pepper says it ("My IP address is 192.168.1.100").
3. **The pynaoqi SDK.** Downloaded from SoftBank's developer portal (or the Maxvision mirror — see §I.5), installed at `C:\pynaoqi\pynaoqi-python2.7-2.5.5.5-win32-vs2013\`.
4. **Python 2.7** at `C:\Python27\python.exe`.
5. **The right `PYTHONPATH`**:

```cmd
set PYTHONPATH=C:\pynaoqi\pynaoqi-python2.7-2.5.5.5-win32-vs2013\lib;%PYTHONPATH%
set PATH=C:\pynaoqi\pynaoqi-python2.7-2.5.5.5-win32-vs2013\lib;%PATH%
```

Then `import naoqi` or `import qi` will work.

\newpage

## I.3 — Choregraphe: The Visual Programming Studio

### At a Glance

**Choregraphe** is SoftBank's desktop IDE for Pepper / NAO. Box-and-wire visual programming + Python script editor + 3D virtual robot simulator. Critical for OmniLLM in three ways: (1) testing behaviours without a physical robot, (2) installing custom animations the gesture planner will trigger, and (3) live-monitoring during experimental sessions.

### I.3.1 — The Four-Panel Layout

```
+--------------+----------------------------+-----------------+
|              |                            |                 |
|   BOX        |       FLOW DIAGRAM         |   3D ROBOT      |
|   LIBRARIES  |                            |   VIEW          |
|   (left)     |       (center)             |                 |
|              |                            |   (right)       |
|   Drag boxes |   Where you wire boxes     |                 |
|   from here  |   together to make a       |   Virtual or    |
|              |   behaviour                |   real Pepper   |
+--------------+----------------------------+-----------------+
|                                                              |
|   LOG VIEWER  /  SCRIPT EDITOR  (bottom)                     |
|   * NAOqi log messages  /  Python script execution           |
|                                                              |
+--------------------------------------------------------------+
```

It is locked to NAOqi 2.5 — version 2.5.5.5 or 2.5.10/11 for Pepper. Newer NAOqi 2.9 (Android-based) does **not** support Choregraphe; for 2.9 use QiSDK (Java/Kotlin) instead.

### I.3.2 — When to Use Choregraphe Versus OmniLLM

Choregraphe and OmniLLM serve different purposes — they are friends, not substitutes:

| You want to… | Use Choregraphe | Use OmniLLM |
|--------------|-----------------|-------------|
| Test if Pepper's speech works | yes | — |
| Test a single gesture animation | yes | — |
| Build / tune a custom animation | yes | — |
| Build a *scripted* interaction | yes | — |
| Build an **AI-driven** conversation | — | yes |
| Use multiple LLMs as backends | — | yes |
| Run a controlled HRI experiment | — | yes |
| Live-monitor during an experiment | yes (alongside) | yes |

The typical combined workflow:

1. **Plan the gesture vocabulary** in Choregraphe. Drag and edit animations until they look natural.
2. **Install the custom behaviours** on Pepper (File → Build Application Package, then upload).
3. **Add the new gesture names** to OmniLLM's `GESTURE_TO_BEHAVIOR` mapping in `naoqi_client.py` and to the planner in `gesture_planner.py`.
4. **Run the OmniLLM experiment**, leaving Choregraphe open as a monitor.

### I.3.3 — Connecting Choregraphe to a Robot

**Virtual robot** (no hardware needed):

1. Open Choregraphe.
2. **Connection → Connect to virtual robot**.
3. Pepper appears in the 3D view; the bottom-left status shows `Connected to localhost:<port>` (port is randomised per launch — note it for `--robot-port`).

**Physical robot:**

1. PC and Pepper on the same Wi-Fi.
2. Press Pepper's chest button → it says its IP.
3. **Connection → Connect to…** enter the IP, port `9559`.
4. The 3D view now mirrors the real robot's joint positions.

### I.3.4 — Box-and-Wire Programming

Each Choregraphe **box** is a small piece of behaviour. Boxes have input and output **bangs** (signal triggers). You drag boxes onto the flow diagram and connect their bangs to define the order:

```
  +-------------+     +--------------+     +----------------+
  |  onStart    |---->|  Say "Hello" |---->| Wave Animation |
  +-------------+     +--------------+     +----------------+
                                                   |
                                                   v
                                          +----------------+
                                          |  Set LEDs blue |
                                          +----------------+
```

Inside each box is a Python 2.7 script with `onLoad()`, `onUnload()`, `onInput_onStart()`, and `onInput_onStop()` lifecycle methods. You can inspect and edit any box's script.

### I.3.5 — Useful Boxes for OmniLLM Work

When testing Pepper for OmniLLM, the boxes you'll reach for are:

- **Speech / Animated Say** — sanity check that ALAnimatedSpeech works.
- **Movement / Animations / Gestures / Hey_1** — wave hello.
- **Movement / Animations / Gestures / Explain_8** — point left (OmniLLM's `point_left`).
- **Movement / Animations / Gestures / Explain_7** — point right.
- **LEDs / Set LEDs** — change eye colour.
- **Movement / Postures / Stand** — wake up posture.

### I.3.6 — The Script Editor as a Quick Test Bench

You don't need to drag boxes for everything. Press `Alt+5` to open the Script Editor and just type Python:

```python
# Test ALAnimatedSpeech directly
tts = ALProxy("ALAnimatedSpeech", "localhost", 9559)
config = {"bodyLanguageMode": "contextual"}
tts.say("This is what an OmniLLM response sounds like.", config)

# Test a gesture
behavior = ALProxy("ALBehaviorManager", "localhost", 9559)
behavior.runBehavior("animations/Stand/Gestures/Explain_8")  # point_left

# Test eye LEDs
leds = ALProxy("ALLeds", "localhost", 9559)
leds.fadeRGB("FaceLeds", 0.0, 0.67, 1.0, 0.5)   # navigation blue
```

This is the fastest way to verify everything OmniLLM will need.

### I.3.7 — Installing a Custom Behaviour

If you build a new animation in Choregraphe and want OmniLLM to trigger it:

1. **In Choregraphe**: design the animation in the Timeline Editor, save the project as `MyBehaviors/WelcomeDance`.
2. **Upload to Pepper**: `File → Upload to robot…`. The behaviour now lives at `mybehaviors/WelcomeDance` on the robot.
3. **In OmniLLM**: edit `omnillm/server/naoqi_client.py`:

```python
GESTURE_TO_BEHAVIOR = {
    # ... existing entries ...
    "welcome_dance": "mybehaviors/WelcomeDance",   # <-- add this
}
```

4. **Trigger it**: edit `omnillm/robotics/gesture_planner.py` to map appropriate response text or task type to `"welcome_dance"`.

\newpage

## I.4 — Five Bridge Patterns From the Literature

> *Chapter 16 introduced OmniLLM's three bridge solutions (HTTP server, HTTP client, stub). This section surveys the **five published patterns** used across 15+ Pepper-LLM projects and explains why OmniLLM chose Pattern 1.*

### I.4.1 — The Five Patterns

| Pattern | Used in | Trade-offs |
|---------|---------|------------|
| **1. HTTP / REST bridge** *(OmniLLM)* | ilabsweden/pepperchat (2023), Frontiers ASD therapy, 6+ others | Easiest to debug, well-understood, ~50–200 ms overhead |
| **2. Socket-based** | Pepper-GPT (Auckland), Ghent University elder care | Lower latency (~10–50 ms), more code |
| **3. ROS2 bridge** (`naoqi_driver2`) | Multi-robot research projects | High setup complexity, powerful for fleets |
| **4. MQTT broker** | LAIR-GPT (Ancona) | Good when many components publish/subscribe |
| **5. Python 3 `qi 3.1.5`** | Prototypes | Single process but several services broken |

OmniLLM picked **Pattern 1** because it is the most-tested in the literature, the easiest to debug (every message is just `curl`-able), and the overhead is comfortably within the latency budget.

### I.4.2 — Failure Modes the Bridge Must Handle

The HTTP bridge introduces three new failure surfaces. Each has a defensive fallback:

| Failure | Mitigation |
|---------|------------|
| AI server crashed | NAOqi client times out, says "I could not connect to my AI brain" — does not crash |
| Network partition | Same as above; the `urlopen` timeout is 30 s |
| AI server returns malformed JSON | NAOqi client logs and falls back to silent failure |
| Audio capture returns empty bytes | Server can fall back to text-only mode (text field also accepted) |
| LangGraph not installed on AI server | `_fallback_interact` direct gateway call still works |
| Whisper not installed | Server returns 500 on `/transcribe`; text-only mode still works |

### I.4.3 — Latency Implications

The HTTP bridge adds a small but measurable overhead per interaction:

| Step | Time on LAN |
|------|-------------|
| TCP/HTTP round trip (LAN) | 5–30 ms |
| JSON serialise / deserialise | 1–5 ms |
| Base64 encode / decode (5 s of audio at 16 kHz mono) | 10–20 ms |
| **Total bridge overhead per interaction** | **~20–50 ms** |

This is comfortably inside the 1–3 s budget. For comparison, the LLM call itself takes 500–2000 ms.

### I.4.4 — When You'd Want a Different Pattern

Switch off the HTTP bridge if:

- You need **sub-100 ms** end-to-end (token streaming for real-time conversation). Use a WebSocket pattern.
- You're on **NAOqi 2.9 + Android**. Use QiSDK (Java/Kotlin), bypass the bridge entirely.
- You're integrating with **ROS2 Nav2**. Use `naoqi_driver2` so the robot participates in the ROS2 message graph.

For a typical Pepper + LLM HRI study, the HTTP bridge is the sweet spot.

### I.4.5 — Anatomy of One HTTP Round-Trip

**Request from `naoqi_client.py`:**

```
POST /interact HTTP/1.1
Host: 192.168.1.50:5000
Content-Type: application/json
Content-Length: ~140000        # about 100 KB of base64 audio

{
  "audio":          "UklGRiQ...",   # 5 s of 16 kHz WAV ~ 100 KB raw -> ~135 KB b64
  "participant_id": "P001",
  "session_id":     "9c2e-abc123",
  "condition":      "C",
  "rag_enabled":    true
}
```

**Response from `app.py`:**

```
HTTP/1.1 200 OK
Content-Type: application/json

{
  "speech":      "Room 305 is on the third floor on your left.",
  "gesture":     "point_left",
  "emotion_led": "#00AAFF",
  "metadata": {
    "task_type":   "navigation",
    "model_id":    "openai-gpt4o-mini",
    "rag_enabled": true
  }
}
```

\newpage

## I.5 — Sibling HTTP-Bridge Projects: Cross-Validation

> *§I.4 chose Pattern 1 (HTTP/REST bridge) by surveying the literature. Five independent public projects use the same pattern. Reading their READMEs is the fastest way to cross-check OmniLLM's architecture and spot ideas it has not yet adopted.*

| Project | Stack | What OmniLLM can borrow |
|---------|-------|--------------------------|
| **ilabsweden/pepperchat** | Py2 `module_commandable.py` on robot, Py3 `dispatcher.py` external, OpenAI ChatGPT | Uses NAOqi `ALAutonomousLife` to switch focus to a dedicated `nao_focus` — **prevents Pepper's built-in dialogue from talking over your LLM**. OmniLLM does not currently set Autonomous Life mode; the participant may hear Pepper's stock greeting drowning the LLM response. **Fix is one line in `naoqi_client.py`: `ALAutonomousLife.setState("disabled")` after connect, before the greeting.** |
| **UoA-CARES/Pepper-GPT** | Py3 "Black Box" (Whisper + GPT-3.5), Py2 "Pepper Controller" over VPN, NAOqi 2.1.4.13 | Documents the `libboost_regex` install error explicitly — the same family of errors hits the Windows 11 pynaoqi install. Their pinning of NAOqi 2.1.4.13 confirms our 2.5.5.5 choice is *not* the only valid path. |
| **UoA-CARES/pepper-demo** | Choregraphe 2.5.10.7 + PyNAOqi, Pepper 1.8 | Documents a hard-to-find ZLIB symlink fix (`libz.so.1` ↔ system) for Choregraphe on Linux. Save this for the day you move the AI server to a Linux box. |
| **igor-lirussi/Dialogue-Pepper-Robot** | Java AIML engine + Py2 NAOqi + separate speech-recognition service | The clean split between *dialogue engine* and *speech-recognition service* (parallel processes, robot IP as a CLI flag) is what OmniLLM already does; their architectural rule is worth citing in the thesis. |
| **softbankroboticstraining/pepper-chatbot-api** (Pepper Chat) | NAOqi 2.5 + Google Dialogflow v2 (JSON keypath) | Documents **QiChat voice-shaping commands** (pause, speed, pitch, emotional intonation) that OmniLLM does not yet exercise. These could be added to `naoqi_client.py`'s `say()` wrapper for affective speech without leaving Pepper's TTS. |

**Direct cross-validation finding.** Every one of the five projects ends up with the same two-process topology OmniLLM uses. The *variation* is in (a) which LLM provider they use, and (b) whether they suppress Pepper's Autonomous Life default behaviour. OmniLLM is **ahead** on (a) — its multi-provider router covers ground none of the others touch — and **behind** on (b). One-line fix: disable Autonomous Life on connect.

\newpage

## I.6 — Curated External Resources (Pepper-Specific)

> *Resources organised by the recurring problem buckets every Pepper + LLM project meets. Each entry: link + one-line "why it matters."*

### NAOqi 2.5 / Python 2.7 install hardening

| Resource | Why it matters |
|----------|----------------|
| `AnonKour/pynaoqi` (GitHub) | Linux mirror of the Python 2.7 NAOqi SDK; keep the URL in case the official mirror disappears post-Aldebaran bankruptcy |
| `nlp.fi.muni.cz/trac/pepper/wiki/InstallationInstructions` | Masaryk University NLP lab guide — `pyenv_install.sh` for isolated Python 2 (Anaconda is incompatible with NAOqi) |
| `incognite-lab/Pepper-Controller` | Wraps ~60 NAOqi methods into a single domain-partitioned Python class — a model for refactoring `naoqi_client.py` |
| `maxtronics.com/en/support/kb/category/pepper/downloads-softwares/` | Post-bankruptcy mirror of Pepper 2.5 & 2.9 downloads; most reliable place to re-fetch Choregraphe and the SDK |

### Navigation, mobility, guided-tour extensions

| Resource | Why it matters |
|----------|----------------|
| `softbankrobotics-labs/pepper-proactive-mobility` | Pepper autonomously approaches people and returns home; supports three localisation modes (homing, ARUCO, on-board SLAM) |
| `softbankrobotics-labs/pepper-aruco` and `pepper-aruco-automapping` | ARUCO marker library through QiSDK; print one marker per "room" and Pepper can both speak *and* walk to "Room 305" |
| `aldebaran/naoqi_navigation_samples` | Choregraphe `.pml` projects for `explore`, `patrol`, and `places`. `places` is the most directly useful — named locations + walk-between |
| `ros-naoqi/naoqi_bridge` and `naoqi_driver2` | Republishes NAOqi services as ROS topics; entry into Nav2 |

### Multilingual voice (Japanese-voice question)

| Resource | Why it matters |
|----------|----------------|
| **VOICEVOX** (open-source) | MIT-licensed modern neural TTS for Japanese; runs locally on the same GPU you use for Whisper. **Practical 2026 choice for Japanese.** |
| Open JTalk + HTS voices | Alternative open Japanese TTS; older HTS-HMM family |
| Voisona Pepper voice library | Pepper-character *singing-voice* library; **NOT suitable** for conversational TTS — only for outreach demos |

### Vision-side extensions

| Resource | Why it matters |
|----------|----------------|
| `ageitgey/face_recognition` | dlib-based, 99.38% on LFW. Python 3 only. Practical choice for a `/recognise_face` endpoint that returns a participant ID |
| `LucaCorvitto/Emotional_Pepper` | PDDL-planned emotional behaviour — hybrid LLM-content + planner-mood inspiration |
| `softbankrobotics-labs/pepper-mask-detection` and `pepper-deep-learning` | NAOqi 2.9 / QiSDK only — relevant if migrating to NAOqi 2.9 |

### Dialogue platforms and ASR (pre-LLM, still instructive)

| Resource | Why it matters |
|----------|----------------|
| `softbankroboticstraining/pepper-chatbot-api` | Documents QiChat voice-shaping (pause, speed, pitch, emotional intonation) — affective TTS extension |
| `TheRARELab/langex` | Choregraphe template for reproducible language-HRI experiments — borrow filename and header conventions |
| `softbankrobotics-labs/pepper-solitaries-loop` | Idle animations for between-turn liveliness — fixes the uncanny-when-still-between-turns problem |
| Pepper + Dialogflow integration (blogemtech Medium) | Documents silence detection (essential for variable-length turns) + amplitude threshold values (14000 at 16 kHz mono) |

### Validation suites, curricula, HRI reference datasets

| Resource | Why it matters |
|----------|----------------|
| `robocupathomeedu.org` RoboCup@Home Education | External rubric of service-robot tasks (person following, object handover, instruction following, room-to-room navigation) — use to scope thesis claims |
| **ROBO-GAP** (Perugia et al. 2022, HRI ACM/IEEE) — `robo-gap.unisi.it` | Peer-reviewed dataset of perceived age, femininity, masculinity, gender-neutrality across 251 robots **including Pepper**. **Use as a control variable in the thesis.** ICC reliability 0.896–0.954. |
| **CARESSES** (`caressesrobot.org`) | Pepper used for *culturally competent* elder care (UK / Japan / India) — entry point for cultural-HRI framing. Cite the Bruno/Sgorbissa publications via Google Scholar. |

### Aldebaran / NAOqi reference docs

| Resource | Why it matters |
|----------|----------------|
| `doc.aldebaran.com/2-5/` | Canonical NAOqi 2.5 reference — bookmark the Service Pages (ALMotion, ALAnimatedSpeech, ALMemory, ALAudioDevice) |
| `doc.aldebaran.com/2-5/getting_started/index.html` | The "first 10 minutes with Pepper" reference |
| `github.com/orgs/aldebaran/repositories` | `libqi`, `libqi-python`, `qibuild` (still maintained April 2026); `robot-jumpstarter` is the best Python starter |
| `groups.google.com/g/ros-sig-aldebaran` | Slow but active community list — best place to ask `naoqi_driver2` questions |

### Emotion-adaptive proxemics (research-grade extension)

| Resource | Why it matters |
|----------|----------------|
| `arxiv.org/abs/2401.17663` (Bilen et al. 2024) | "Social Robot Navigation with Adaptive Proxemics Based on Emotions" — empirical basis for tying detected emotion to approach distance (relevant if you build the Wayfinder extension in §I.4 / Chapter 33) |

\newpage

## I.7 — A One-Liner for Each Quick-Win Improvement

Ranked by ease and research payoff:

| Improvement | Effort | Research payoff | Source |
|-------------|--------|-----------------|--------|
| Disable Autonomous Life on connect (kill stock dialogue) | 1 line in `naoqi_client.py` | Removes a confound that all five sibling projects have already fixed | §I.5, ilabsweden |
| Add solitaries / idle animations loop | ~30 LoC | Perceived liveliness during long sessions | §I.6, SoftBank Labs |
| Silence-detected audio capture (replace fixed 5 s window) | ~80 LoC | Lets the participant pause/think without truncation | §I.6, Dialogflow article |
| VOICEVOX Japanese TTS provider | new `tts/voicevox.py` | Unlocks Japanese-language Arena condition with modern voice | §I.6 |
| Face-recognition endpoint (`/recognise_face`) via `ageitgey/face_recognition` | new endpoint + Py3 dependency | Eliminates manual participant-ID entry; enables personalised greeting | §I.6 |
| ARUCO + `places/` navigation as a new task type | new task + 4 Choregraphe behaviours | Tests escorting vs. pointing — novel HRI finding | §I.6 |
| ROS 2 bridge via `naoqi_driver2` | new `naoqi_client_ros2/` package | Opens fleet / multi-robot experiments | §I.6 |
| Migration to NAOqi 2.9 + QiSDK (Kotlin) | full robot-side rewrite | Future-proofs against pynaoqi rot | §I.6 |

The first three rows are quick wins worth doing before the next participant cohort. Rows 4–6 are dissertation-chapter-scale extensions. Rows 7–8 are post-thesis directions.

\newpage
