# PART IV — PEPPER, CHOREGRAPHE, NAOqi

This part is the practical guide to the robot side of the project. We start
with the hardware, work up through NAOqi the operating system, the
Choregraphe IDE, the Python 2.7 problem and its solution, and end with five
walk-throughs you can actually run.

\newpage

## Chapter 23 — Meet Pepper — The Hardware Inside the Plastic Shell

> **⚡ AT A GLANCE.** Pepper is a 120 cm, 28 kg humanoid robot from SoftBank
> Robotics. 20 degrees of freedom. Intel Atom CPU, 4 GB RAM. Four
> microphones in the head. Two ear speakers. A 10.1″ chest tablet. Eye LEDs.
> Three omnidirectional wheels at the base. ~10 hours of battery. Knowing
> this hardware shapes how you think about the AI server's job.

### 23.1  Physical Specs

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

### 23.2  Sensors

```
                 ┌─────────────────────┐
                 │  HEAD                │
                 │  • 2× 5 MP RGB cam  │
                 │     (forehead, chin) │
                 │  • ASUS Xtion 3D    │
                 │     depth sensor    │
                 │  • 4× microphones   │
                 │  • 3× capacitive    │
                 │     touch sensors   │
                 │  • Eye LEDs (RGB)   │
                 └──────┬──────────────┘
                        │
                ┌───────┴────────┐
                │  TORSO          │
                │  • 10.1" tablet │
                │     1280×800    │
                │  • Hand touch   │
                │     sensors     │
                │  • IMU          │
                └───────┬─────────┘
                        │
              ┌─────────┴──────────┐
              │  BASE                │
              │  • 3× wheels        │
              │  • 2× sonar         │
              │  • 6× laser line    │
              │  • 2× infrared      │
              │  • 3× bumper        │
              │  • IMU              │
              └─────────────────────┘
```

The cameras and depth sensor are not used by OmniLLM in the current design,
but they are available — see "Future Work" in Chapter 39.

### 23.3  The Tablet

The chest tablet is a separate Android computer (1.3 GHz quad-core
ARM Cortex-A7, 1 GB RAM, 32 GB storage) communicating with the head
computer over an internal network at IP `198.18.0.1`. From OmniLLM's
perspective it is just a service: `ALTabletService`. You can `loadUrl()`
to display web content, `showImage()` to display an image, or
`executeJS()` to run JavaScript in the browser.

For the Embodied LLM Arena, the tablet is mostly unused (most lab tasks
do not need a screen), but it is available for showing maps during
navigation tasks.

### 23.4  The Speaker / Microphone Pair

Pepper has **four microphones** in its head, and the NAOqi audio device
exposes all four channels at 48 kHz, or **a single mixed-down channel at
16 kHz**. OmniLLM uses the 16 kHz mono channel — the same format Whisper
expects.

The "front" channel (channel 3 in the four-channel layout) is the most
useful for one-on-one conversation. ALAudioDevice's `setClientPreferences`
call in `naoqi_client.py` selects this:

```python
self._audio_device.setClientPreferences(
    "OmniLLMCapture",
    16000,    # sample rate
    3,        # channel: front
    0,        # deinterleaved: no
)
```

### 23.5  Eye LEDs as a Communication Channel

The eye LEDs are addressable RGB LEDs. NAOqi exposes them through `ALLeds`:

```python
leds.fadeRGB("FaceLeds", r, g, b, fade_duration_seconds)
```

OmniLLM uses the eye colour to communicate **mode**:

| Colour | Hex | Mode |
|--------|-----|------|
| Friendly green | `#00FF88` | Greeting, acknowledgement, social |
| Calm blue | `#00AAFF` | Navigation guidance |
| Default blue | `#44AAFF` | Idle / neutral |
| White | `#FFFFFF` | Showing tablet content |
| Yellow | `#FFFF00` | Thinking |
| Red-orange | `#FF4400` | Confused / error |
| Warm orange | `#FF8800` | Goodbye |

This is *not* arbitrary aesthetic. Eye colour is a documented HRI signal
that participants register subconsciously. Switching from blue (navigation)
to green (success) reinforces the spoken response.

### 23.6  Why ALAnimatedSpeech, Not Plain ALTextToSpeech

NAOqi has two text-to-speech services:

- **`ALTextToSpeech`** — voice only. The robot is rigid while speaking.
- **`ALAnimatedSpeech`** — voice + automatic body gestures synchronised to
  the speech.

OmniLLM uses `ALAnimatedSpeech` *always* because:

1. Embodied perception research (Bartneck, Andrist, etc.) consistently
   shows that "talking head" robots are rated lower on naturalness and
   intelligence.
2. Pepper has joints; not using them is wasteful.
3. The cost is zero — `ALAnimatedSpeech` is built-in.

The configuration that produces sensible motion is:

```python
config = {"bodyLanguageMode": "contextual"}
animated_speech.say(text, config)
```

`bodyLanguageMode` accepts: `"contextual"` (gestures match speech content,
**recommended**), `"random"` (random gestures, looks unhinged), or
`"disabled"` (back to talking-head mode).

### 23.7  Hardware End-of-Life Note

Aldebaran (the company behind Pepper and NAO) filed for bankruptcy in
February 2025. Maxvision Technology (Shenzhen) acquired the IP in July
2025. **No new units are being manufactured.** Existing units continue to
work; spare parts are increasingly hard to source. This is one reason
OmniLLM is designed to be platform-portable — the abstract `RobotBridge`
can target NAO, Buddy, or any future robot you point it at.

\newpage

## Chapter 24 — NAOqi 101 — The Operating System That Runs on Pepper

> **⚡ AT A GLANCE.** NAOqi is the middleware that makes Pepper a robot
> rather than a Linux box on wheels. It is a service broker on TCP port
> 9559 that exposes named services (`ALAnimatedSpeech`, `ALMotion`, etc.)
> to any client that connects with the right credentials. Its Python
> binding is **Python 2.7 only**.

### 24.1  What NAOqi Is

Imagine the robot as a Linux server, and NAOqi as the daemon process that
runs on top of Linux providing all the high-level robot abstractions.

```
              ┌──────────────────────────────────────────────┐
              │  Hardware                                    │
              │  motors, sensors, speakers, microphones      │
              └────────────────┬─────────────────────────────┘
                               ▲
              ┌────────────────┴─────────────────────────────┐
              │  Linux kernel (Gentoo)                       │
              │  device drivers                              │
              └────────────────┬─────────────────────────────┘
                               ▲
              ┌────────────────┴─────────────────────────────┐
              │  NAOqi daemon                                │
              │  starts ~50 services on port 9559            │
              │  ALMotion, ALMemory, ALAnimatedSpeech,       │
              │  ALAudioDevice, ALLeds, ALBehaviorManager,   │
              │  ALFaceDetection, ALTabletService, ...       │
              └────────────────┬─────────────────────────────┘
                               ▲
              ┌────────────────┴─────────────────────────────┐
              │  Clients                                     │
              │  • Choregraphe over the LAN                  │
              │  • Custom Python 2.7 clients (like ours)     │
              │  • Custom C++ clients                         │
              └──────────────────────────────────────────────┘
```

### 24.2  The Service Broker Model

NAOqi is built around a **service broker**. Every NAOqi service registers
itself with the broker on startup; clients look up services by name and
get a proxy object that can call methods on them. Services can run
**locally** (in the same process — fast, zero-copy) or **remotely** (over
TCP — slower, fully serialised).

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

OmniLLM's `naoqi_client.py` tries `qi` first, falls back to `naoqi`, so
it works against both NAOqi 1.x and 2.x.

### 24.3  The Twelve Services You Need to Know

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

### 24.4  The Python 2.7 Constraint Explained

The NAOqi Python binding (`pynaoqi`) is shipped as a platform-specific
archive on SoftBank's developer portal. It is a CPython extension that
depends on the binary layout of Python 2.7 specifically. There is no port
to Python 3 that exposes the full service surface.

A community-built `qi 3.1.5` package (`pip install qi==3.1.5`) exists for
Python 3 on Linux x86_64 but several services are broken (touch detection,
audio callbacks, certain event subscriptions). It is unsuitable for
production.

The conclusion: **NAOqi requires Python 2.7**. Modern AI libraries
require Python 3.11+. They cannot live in the same process. **Hence the
two-process bridge** of Chapter 26.

### 24.5  Lifecycle Quirks

Two NAOqi quirks that will trip you up:

1. **Stiffness must be enabled before any movement.** A fresh-booted Pepper
   has zero stiffness — its motors are dead weight. You must call
   `motion.wakeUp()` (or `motion.setStiffnesses("Body", 1.0)`) first.
   `ALAnimatedSpeech` will speak without stiffness, but the body language
   will not animate.

2. **`ALAudioRecorder` and `ALSpeechRecognition` cannot share the
   microphone.** They both subscribe to the audio device exclusively. You
   must `unsubscribe` one before using the other. OmniLLM uses neither
   directly — it captures via `ALAudioDevice` and sends to Whisper.

### 24.6  Connection from your PC

To connect from your PC, you need:

1. **Network access**. Same Wi-Fi as Pepper, or wired to the same LAN.
2. **Pepper's IP address**. Press the chest button once and Pepper says
   it ("My IP address is 192.168.1.100").
3. **The pynaoqi SDK**. Downloaded from SoftBank's developer portal,
   installed at `C:\pynaoqi\pynaoqi-python2.7-2.5.5.5-win32-vs2013\`.
4. **Python 2.7** at `C:\Python27\python.exe`.
5. **The right `PYTHONPATH`**:

```bat
set PYTHONPATH=C:\pynaoqi\pynaoqi-python2.7-2.5.5.5-win32-vs2013\lib;%PYTHONPATH%
set PATH=C:\pynaoqi\pynaoqi-python2.7-2.5.5.5-win32-vs2013\lib;%PATH%
```

Then `import naoqi` or `import qi` will work.

\newpage

## Chapter 25 — Choregraphe — The Visual Programming Studio

> **⚡ AT A GLANCE.** Choregraphe is SoftBank's desktop IDE for Pepper / NAO.
> Box-and-wire visual programming + Python script editor + 3D virtual
> robot simulator. Critical for OmniLLM in three ways: (1) testing
> behaviours without a physical robot, (2) installing custom animations
> the gesture planner will trigger, and (3) live-monitoring during
> experiments.

### 25.1  What Choregraphe Is

Choregraphe is a four-panel desktop application:

```
┌──────────────┬────────────────────────────┬─────────────────┐
│              │                            │                 │
│   BOX        │       FLOW DIAGRAM         │   3D ROBOT      │
│   LIBRARIES  │                            │   VIEW          │
│   (left)     │       (center)             │                 │
│              │                            │   (right)       │
│   Drag boxes │   Where you wire boxes     │                 │
│   from here  │   together to make a       │   Virtual or    │
│              │   behaviour                │   real Pepper   │
├──────────────┴────────────────────────────┴─────────────────┤
│                                                              │
│   LOG VIEWER  /  SCRIPT EDITOR  (bottom)                     │
│   • NAOqi log messages  /  Python script execution            │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

It is locked to NAOqi 2.5 — version 2.5.5.5 or 2.5.10/11 for Pepper.
Newer NAOqi 2.9 (Android-based) does **not** support Choregraphe.

### 25.2  When to Use Choregraphe Versus OmniLLM

Choregraphe and OmniLLM serve different purposes — they are friends, not
substitutes:

| You want to… | Use Choregraphe | Use OmniLLM |
|--------------|-----------------|-------------|
| Test if Pepper's speech works | ✓ | — |
| Test a single gesture animation | ✓ | — |
| Build / tune a custom animation | ✓ | — |
| Build a *scripted* interaction | ✓ | — |
| Build an **AI-driven** conversation | — | ✓ |
| Use multiple LLMs as backends | — | ✓ |
| Run a controlled HRI experiment | — | ✓ |
| Live-monitor during an experiment | ✓ (alongside) | ✓ |

The typical workflow combines them:

1. **Plan the gesture vocabulary** in Choregraphe. Drag and edit
   animations until they look natural.
2. **Install the custom behaviours** on Pepper (Choregraphe → File →
   Build Application Package, then upload).
3. **Add the new gesture names** to OmniLLM's `GESTURE_TO_BEHAVIOR` dict
   in `naoqi_client.py` and `gesture_planner.py`.
4. **Run the OmniLLM experiment**, leaving Choregraphe open as a monitor.

### 25.3  Connecting Choregraphe to a Robot

**Virtual robot** (no hardware needed):

1. Open Choregraphe.
2. **Connection** → **Connect to virtual robot**.
3. Pepper appears in the 3D view; the bottom-left status shows
   `Connected to localhost:9559 (virtual)`.

**Physical robot:**

1. Make sure your PC and Pepper are on the same Wi-Fi.
2. Press Pepper's chest button → it says its IP.
3. **Connection** → **Connect to…**, enter the IP, port 9559.
4. The 3D view now mirrors the real robot's joint positions.

### 25.4  Box-and-Wire Programming

Each Choregraphe **box** is a small piece of behaviour. Boxes have input
and output **bangs** (signal triggers). You drag boxes onto the flow
diagram and connect their bangs to define the order:

```
  ┌─────────────┐     ┌──────────────┐     ┌────────────────┐
  │  onStart    ├────▶│  Say "Hello" ├────▶│ Wave Animation │
  └─────────────┘     └──────────────┘     └────────────────┘
                                                   │
                                                   ▼
                                          ┌────────────────┐
                                          │  Set LEDs blue │
                                          └────────────────┘
```

Inside each box is a Python 2.7 script with `onLoad()`, `onUnload()`,
`onInput_onStart()`, and `onInput_onStop()` lifecycle methods. You can
inspect and edit any box's script.

### 25.5  Useful Boxes for OmniLLM Work

When testing Pepper for OmniLLM, the boxes you'll reach for are:

- **Speech / Animated Say** — sanity check that ALAnimatedSpeech works.
- **Movement / Animations / Gestures / Hey_1** — wave hello.
- **Movement / Animations / Gestures / Explain_8** — point left
  (OmniLLM's `point_left`).
- **Movement / Animations / Gestures / Explain_7** — point right.
- **LEDs / Set LEDs** — change eye colour.
- **Movement / Postures / Stand** — wake up posture.

### 25.6  The Script Editor as a Quick Test Bench

You don't need to drag boxes for everything. Press `Alt+5` to open the
Script Editor at the bottom and just type Python:

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

### 25.7  Installing a Custom Behaviour

If you build a new animation in Choregraphe and want OmniLLM to trigger
it:

1. **In Choregraphe**: design the animation in the Timeline Editor,
   save the project as `MyBehaviors/WelcomeDance`.
2. **Upload** to Pepper: `File → Upload to robot…`. The behaviour now
   lives at `mybehaviors/WelcomeDance` on the robot.
3. **In OmniLLM**: edit `omnillm/server/naoqi_client.py`:

```python
GESTURE_TO_BEHAVIOR = {
    # ... existing entries ...
    "welcome_dance": "mybehaviors/WelcomeDance",   # ← add this
}
```

4. **Trigger it**: edit `omnillm/robotics/gesture_planner.py` to map
   appropriate response text or task type → `"welcome_dance"`.

\newpage

## Chapter 26 — The Python 2.7 / Python 3.x Bridge Problem (and the Solution)

> **⚡ AT A GLANCE.** This chapter is the canonical explanation of the
> single hardest engineering problem in the project. NAOqi requires
> Python 2.7. Modern AI libs require Python 3.11+. They cannot share a
> process. The solution: two processes, one HTTP boundary.

### 26.1  The Constraint

```
  ┌──────────────────────────────────────┐
  │  NAOqi SDK (pynaoqi)                 │
  │  works ONLY with Python 2.7          │
  └──────────────────────────────────────┘

  ┌──────────────────────────────────────┐
  │  langgraph, litellm, chromadb,       │
  │  langchain, sentence-transformers,   │
  │  openai-whisper                       │
  │  require Python 3.11+                 │
  └──────────────────────────────────────┘
```

You cannot install both into the same Python interpreter. There is no
"compat layer". The solution is **process separation**.

### 26.2  The Bridge Pattern

```
        ┌─────────────────────────────────────────────────┐
        │  Process 1: NAOqi client (Python 2.7)           │
        │                                                  │
        │  • imports qi / naoqi                            │
        │  • talks to Pepper hardware                      │
        │  • does HTTP to Process 2                        │
        │  • zero AI dependencies                          │
        └────────────────────────┬─────────────────────────┘
                                 │
                                 │ HTTP / JSON
                                 │
        ┌────────────────────────┴─────────────────────────┐
        │  Process 2: AI server (Python 3.11+)             │
        │                                                   │
        │  • imports langgraph, litellm, chromadb,         │
        │    langchain, openai-whisper                      │
        │  • talks to LLM providers                         │
        │  • cannot import NAOqi                            │
        └──────────────────────────────────────────────────┘
```

Each process imports only what it can. The HTTP boundary is the *only*
contact between them.

### 26.3  Five Bridge Patterns From the Literature

The compass research (`compass_artifact_*.md`) summarises five patterns
used across 15+ published Pepper-LLM projects. OmniLLM uses Pattern 1:

| Pattern | Used in | Trade-offs |
|---------|---------|------------|
| **1. HTTP / REST bridge** *(OmniLLM)* | ilabsweden/pepperchat (2023), Frontiers ASD therapy, 6+ others | Easiest to debug, well-understood, ~50–200 ms overhead |
| **2. Socket-based** | Pepper-GPT (Auckland), Ghent University elder care | Lower latency (~10–50 ms), more code |
| **3. ROS2 bridge** (`naoqi_driver2`) | Multi-robot research projects | High setup complexity, powerful for fleets |
| **4. MQTT broker** | LAIR-GPT (Ancona) | Good when many components publish/subscribe |
| **5. Python 3 `qi 3.1.5`** | Prototypes | Single process but several services broken |

OmniLLM picked Pattern 1 because it is the most-tested in the literature,
the easiest to debug (every message is just `curl`-able), and the
overhead is comfortably within the latency budget.

### 26.4  The Failure Modes You Must Anticipate

The bridge introduces three new failure surfaces. Each has a defensive
fallback:

| Failure | Mitigation |
|---------|------------|
| AI server crashed | NAOqi client times out, says "I could not connect to my AI brain" — does not crash |
| Network partition | Same as above; the `urlopen` timeout is 30 s |
| AI server returns malformed JSON | NAOqi client logs and falls back to silent failure |
| Audio capture returns empty bytes | Server can fall back to text-only mode (text field also accepted) |
| LangGraph not installed on AI server | `_fallback_interact` direct gateway call still works |
| Whisper not installed | Server returns 500 on `/transcribe`; text-only mode still works |

### 26.5  Latency Implications

The HTTP bridge adds a small but measurable overhead per interaction:

| Step | Time on LAN |
|------|-------------|
| TCP/HTTP round trip (LAN) | 5–30 ms |
| JSON serialise / deserialise | 1–5 ms |
| Base64 encode / decode (5 s of audio at 16 kHz mono) | 10–20 ms |
| Total bridge overhead per interaction | **~20–50 ms** |

This is comfortably inside the 1–3 s budget. For comparison, the LLM call
itself takes 500–2000 ms.

### 26.6  When You'd Want a Different Pattern

You'd switch off the HTTP bridge if:

- You need **sub-100 ms** end-to-end (token streaming for real-time
  conversation). Use the WebSocket pattern (BuddyBridge already does this).
- You're on **NAOqi 2.9 + Android**. Use QiSDK (Java/Kotlin), bypass the
  bridge entirely. (See "Future Work" in Chapter 39.)
- You're integrating with **ROS2 Nav2**. Use `naoqi_driver2` so the robot
  participates in the ROS2 message graph.

For a typical Pepper + LLM HRI study, the HTTP bridge is the sweet spot.

### 26.7  Anatomy of One HTTP Round Trip

When Pepper asks the AI server a question, here is what flows over the
wire:

**Request from `naoqi_client.py:233`:**

```
POST /interact HTTP/1.1
Host: 192.168.1.50:5000
Content-Type: application/json
Content-Length: ~140000        ← about 100 KB of base64 audio

{
  "audio":          "UklGRiQ...",   ← 5 s of 16 kHz WAV ~ 100 KB raw → ~135 KB b64
  "participant_id": "P001",
  "session_id":     "9c2e-abc123",
  "condition":      "C",
  "rag_enabled":    true
}
```

**Response from `app.py:275`:**

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

## Chapter 27 — Five Practical Walk-throughs (with and without a real robot)

> **⚡ AT A GLANCE.** This chapter is action-only. Five scenarios, each
> covering setup, run command, what to expect, and how to verify it
> worked. Use these as recipes.

### 27.1  Walk-through 1 — Server Smoke Test (no robot, no Choregraphe)

**Goal:** Confirm the AI server runs and answers a text question.

```bash
# Terminal 1
cd C:\Users\akshi\OneDrive\Desktop\OmniLLM
.venv\Scripts\activate
python -m omnillm.server.app --no-rag

# Terminal 2 (or browser)
curl http://localhost:5000/health
# expected: {"status": "ok", "version": "0.1.0"}

curl -X POST http://localhost:5000/interact \
  -H "Content-Type: application/json" \
  -d '{"text": "Hello, what can you do?", "participant_id": "TEST", "condition": "B"}'
# expected: JSON with speech / gesture / emotion_led
```

**Success criteria:** valid JSON response, no Python tracebacks.

**If this fails**: check `.env` API keys; verify Ollama is running for
condition B; try `condition: "A"` if you have an OpenAI key.

### 27.2  Walk-through 2 — RAG Smoke Test

**Goal:** Confirm the RAG pipeline is indexing and retrieving from the
knowledge base.

```bash
python -m omnillm.server.app    # RAG enabled by default
```

You should see in the server logs:

```
INFO:omnillm.rag.pipeline:Indexed 12 chunks from lab_info.txt
INFO:omnillm.rag.pipeline:Indexed 8 chunks from faq.txt
INFO:omnillm.rag.pipeline:Knowledge base loaded — 42 total chunks
```

Then in another terminal:

```bash
curl -X POST http://localhost:5000/interact \
  -H "Content-Type: application/json" \
  -d '{"text": "What is the WiFi password?", "participant_id": "T", "condition": "A"}'
```

**Success criteria:** the response contains "UniGuest" and "Welcome2026!"
— literally the values from `knowledge_base/lab_info.txt`. If those exact
words appear, RAG retrieved correctly.

### 27.3  Walk-through 3 — Choregraphe Virtual Robot, Text Mode

**Goal:** See OmniLLM responses *animate* on a virtual Pepper without any
physical hardware.

```
Setup:
  Terminal 1: ollama serve
  Terminal 2: python -m omnillm.server.app --model llama3-8b-local
  Choregraphe: open, Connection → Connect to virtual robot
```

The virtual Pepper has no microphone, so we'll use text mode + manually
play the gestures.

```bash
# Terminal 3: send a text question, capture the JSON
curl -X POST http://localhost:5000/interact \
  -H "Content-Type: application/json" \
  -d '{"text": "Where is Room 305?", "participant_id": "T", "condition": "B"}'
# returns: {"speech":"Room 305 ... your left.", "gesture":"point_left", "emotion_led":"#00AAFF", ...}
```

Then in Choregraphe's Script Editor:

```python
# Re-play what OmniLLM decided, on the virtual robot
tts = ALProxy("ALAnimatedSpeech", "localhost", 9559)
behavior = ALProxy("ALBehaviorManager", "localhost", 9559)
leds = ALProxy("ALLeds", "localhost", 9559)

leds.fadeRGB("FaceLeds", 0.0, 0.67, 1.0, 0.3)             # #00AAFF
behavior.post.runBehavior("animations/Stand/Gestures/Explain_8")  # point_left
tts.say("Room 305 is on your left on the third floor.",
        {"bodyLanguageMode": "contextual"})
```

**Success criteria:** PC speakers play the speech; the virtual Pepper in
the 3D view points left and its eyes turn blue.

### 27.4  Walk-through 4 — Full Pipeline With Virtual Robot, NAOqi Client

**Goal:** Run the actual `naoqi_client.py` against Choregraphe's virtual
robot, using text-mode requests.

```
Setup:
  Terminal 1: ollama serve
  Terminal 2: python -m omnillm.server.app --model llama3-8b-local
  Choregraphe: Connection → Connect to virtual robot
```

```bash
# Terminal 3: NAOqi client (Python 2.7)
set PYTHONPATH=C:\pynaoqi\pynaoqi-python2.7-2.5.5.5-win32-vs2013\lib;%PYTHONPATH%
set PATH=C:\pynaoqi\pynaoqi-python2.7-2.5.5.5-win32-vs2013\lib;%PATH%

C:\Python27\python.exe omnillm\server\naoqi_client.py ^
    --robot-ip localhost ^
    --robot-port 9559 ^
    --server-ip localhost ^
    --participant TEST ^
    --condition B
```

The client will say its greeting through Pepper's speech, then loop
trying to record audio. Since the virtual robot has no real microphone,
audio will be empty. You'll need to modify the client to use
`_send_text("Where is Room 305?")` for testing — or hook in a synthetic
audio source.

**Success criteria:** Pepper greets you in the 3D view; client log shows
HTTP requests being sent to the AI server.

### 27.5  Walk-through 5 — Physical Pepper, End-to-End

**Goal:** A complete experimental session with a real Pepper.

```
Pre-flight:
  • Pepper is plugged in and woken (chest LED solid green)
  • Note Pepper's IP (chest button → "My IP is 192.168.1.100")
  • Your PC and Pepper on the same Wi-Fi
  • API keys in .env (or Ollama running for cond. B)
```

```bash
# Terminal 1: AI server, all features
cd C:\Users\akshi\OneDrive\Desktop\OmniLLM
.venv\Scripts\activate
python -m omnillm.server.app --host 0.0.0.0 --port 5000

# Terminal 2: NAOqi client
set PYTHONPATH=C:\pynaoqi\pynaoqi-python2.7-2.5.5.5-win32-vs2013\lib;%PYTHONPATH%
C:\Python27\python.exe omnillm\server\naoqi_client.py ^
    --robot-ip 192.168.1.100 ^
    --robot-port 9559 ^
    --server-ip 192.168.1.50 ^
    --server-port 5000 ^
    --participant P001 ^
    --condition C
```

Pepper says: *"Hello! I am Pepper, powered by OmniLLM. How can I help you
today?"* The participant speaks; Pepper responds with grounded answer +
gesture + LED change.

After the session:

```bash
# Terminal 3: download all logged interactions
curl http://localhost:5000/export > results/session_P001.json
```

**Success criteria:** at least one full interaction logged; the
`metadata.model_id` field in the response matches the routing decision
expected for the chosen condition.

\newpage

## Chapter 27A — External Resources, Community Insights, and Future Directions

> **⚡ AT A GLANCE.** This chapter does not introduce new OmniLLM code. It
> reads the broader Pepper + LLM community — SoftBank's own labs,
> independent research teams (Auckland, Sweden, Italy, Czech Republic),
> open-source navigation/perception samples, deprecated-but-essential
> SDK mirrors, Japanese-voice synthesis options, and HRI evaluation
> curricula — and maps each resource to a *specific problem you will
> hit, or have already hit, with the real robot*. Treat it as the
> "what to read next" appendix for Part IV.

### 27A.1  How to use this chapter

The links collected here fall into seven recurring problem buckets that
every Pepper + LLM project meets sooner or later. Each section below is
organised the same way:

1. **The problem** — what concrete pain point this group of resources
   addresses (drawn from OmniLLM's own history, the project setup
   notes, and the "Pepper + Windows 11 quirks" memory).
2. **What the community has already published** — the repository or
   paper, what it actually contains (not just the title), and the
   licence/maintenance status.
3. **How to fold it into OmniLLM** — concrete file paths, integration
   sketches, or experiment ideas you can act on without re-architecting
   the project.

Where a resource is *only* useful as a reference (no code reuse), it
appears in the final annotated list in §27A.10 rather than as a section
of its own.

### 27A.2  Sibling HTTP-Bridge Projects — Cross-Validation of OmniLLM's Pattern 1

Chapter 26 chose Pattern 1 (HTTP/REST bridge between Python 2.7 NAOqi
and Python 3.11+ AI) by surveying the literature. Five independent
public projects use the same pattern. Reading their READMEs is the
fastest way to *cross-check* OmniLLM's architecture and spot ideas it
has not yet adopted.

| Project | Stack | What OmniLLM can borrow |
|---------|-------|--------------------------|
| **ilabsweden/pepperchat** | Py2 `module_commandable.py` on robot, Py3 `dispatcher.py` external, OpenAI ChatGPT | Uses NAOqi `Autonomous Life Proxy` to switch focus to a dedicated `nao_focus` — *prevents Pepper's built-in dialogue from talking over your LLM*. OmniLLM does not currently set Autonomous Life mode; the participant may hear Pepper's stock greeting drowning the LLM response. |
| **UoA-CARES/Pepper-GPT** | Py3 "Black Box" (Whisper + GPT-3.5), Py2 "Pepper Controller" over VPN, NAOqi 2.1.4.13 | Documents the `libboost_regex` install error explicitly — the same family of errors hits the Windows 11 pynaoqi install. Their pinning of NAOqi 2.1.4.13 confirms our 2.5.5.5 choice is *not* the only valid path. |
| **UoA-CARES/pepper-demo** | Choregraphe 2.5.10.7 + PyNAOqi, Pepper 1.8 | Documents a hard-to-find ZLIB symlink fix (`libz.so.1` ↔ system) for Choregraphe on Linux. Save this for the day you move the AI server to a Linux box. |
| **igor-lirussi/Dialogue-Pepper-Robot** | Java AIML engine + Py2 NAOqi + separate speech-recognition service | The clean split between *dialogue engine* and *speech-recognition service* (parallel processes, robot IP as a CLI flag) is what OmniLLM already does, but they expose it as a hard architectural rule. Worth citing in Part X when you defend the pipeline. |
| **softbankroboticstraining/pepper-chatbot-api** ("Pepper Chat") | NAOqi 2.5 + Google Dialogflow v2 (JSON keypath) | Documents *QiChat voice-shaping commands* (pause, speed, pitch, emotional intonation) that OmniLLM does not yet exercise. These could be added to `naoqi_client.py`'s `say()` wrapper for affective speech without leaving Pepper's TTS. |

**Direct cross-validation finding.** Every one of the five projects
ends up with the exact same two-process topology OmniLLM uses. The
*variation* is in (a) which Python 3-side LLM provider they use, and
(b) whether they let Pepper's Autonomous Life keep its default
behaviour or suppress it. OmniLLM is competitive on (a) — its
multi-provider router covers ground none of the others touch — and
*behind* on (b). The fix is one NAOqi call (`ALAutonomousLife.setState("disabled")`)
inside `naoqi_client.py` after connection and before the greeting.

### 27A.3  NAOqi 2.5 / Python 2.7 Install Hardening — Community Recipes

The single biggest source of lost hours on Windows 11 has been the
pynaoqi install path. Three community resources fill the gaps the
official Aldebaran docs leave open:

**(a) `AnonKour/pynaoqi`** — A community mirror of "the Python 2.7
NAOqi SDK", explicitly published because the official Aldebaran
distribution is hard to reach since the bankruptcy. The README
documents the exact `.bashrc` lines to add:

```
export PYTHONPATH=${PYTHONPATH}:/installation/path/pynaoqi/
```

The repo is Linux-only (compiled `.so` files), so it is **not a
substitute** for the Windows install we have at
`C:\pynaoqi\pynaoqi-python2.7-2.5.5.5-win32-vs2013\`. But if a future
collaborator runs the NAOqi client from a Linux box (recommended for
ROS interop — see 27A.4), this is the easiest source.

**(b) `nlp.fi.muni.cz/trac/pepper/wiki/InstallationInstructions`** —
The Masaryk University NLP lab's installation guide. Two pieces of
information are not in the official docs:

- A `pyenv_install.sh` script that builds Python 2 locally and drops
  pynaoqi into its `site-packages`. This is the cleanest way to keep
  a Python 2 install isolated from system Python without
  `conda`/`anaconda` (which is explicitly broken with NAOqi — confirmed
  also by the Dialogflow Medium article).
- The Choregraphe-on-Linux dependency list: `libgl-dev libxt6 libxaw7`.

**(c) `incognite-lab/Pepper-Controller`** — Wraps ~60 NAOqi methods
into a single `Pepper` class organised by domain (Language, Vision,
Motorics, System). OmniLLM's `naoqi_client.py` is more focused (it is
a *client*, not a *controller*) but the domain partitioning is a
better organisation than our current flat module. **Concrete
refactor idea**: split `naoqi_client.py` into
`naoqi_client/language.py`, `naoqi_client/motion.py`,
`naoqi_client/vision.py`, `naoqi_client/system.py`, keeping the public
HTTP surface unchanged. The Pepper-Controller code is BSD-licensed and
can be vendored.

**Windows 11 specifics.** None of the three resources above are
Windows-first. The closest community-validated Windows install path is
still through Maxtronics (the new IP owner) — see §27A.10 — but their
KB does not yet duplicate the Aldebaran developer guide. *Conclusion:*
the project setup memory's notes (loopback bug workaround, virtual
robot port, Connect-to gotcha) are still the canonical Windows 11
record. Worth publishing them as a gist before they are lost.

### 27A.4  Navigation, Proactive Mobility, and Guided-Tour Ideas

OmniLLM's current scope (Embodied LLM Arena) treats navigation as a
*spoken* directive — "Room 305 is on your left" — without Pepper
actually moving. Three SoftBank-Labs repositories show what could be
added without rewriting the agent:

**(a) `softbankrobotics-labs/pepper-proactive-mobility`** — Pepper
autonomously approaches people in range and returns "home" when no one
is present. Supports **three localisation modes**: the charging-station
homing built into NAOqi, ARUCO printed-marker localisation
(linoleum/vinyl ≤ 2 mm thick — *important* if you want a low-friction
floor in a lab), and on-board SLAM. The codebase is 94.9 % Python,
which means it is readable from the OmniLLM side rather than a black
box.

**(b) `softbankrobotics-labs/pepper-aruco` and `pepper-aruco-automapping`**
— ARUCO marker library exposed through QiSDK. Markers act as named
frames the robot can localise against. For an Embodied LLM Arena task,
print one marker per "room" and the agent can speak *and walk* to
"Room 305".

**(c) `aldebaran/naoqi_navigation_samples`** — Choregraphe `.pml`
projects for `explore`, `patrol`, and `places`. `places` is the most
directly useful — it stores named locations and walks between them.
Open in Choregraphe 2.5.2+, upload to Pepper, and trigger from
OmniLLM via `ALBehaviorManager.runBehavior("places/goto_room_305")`,
mirroring the `GESTURE_TO_BEHAVIOR` dictionary pattern in
`naoqi_client.py`.

**Concrete extension proposal — "OmniLLM Wayfinder" condition.** Add
a fourth experimental condition D to the Arena where the LLM's
response includes a `target_location` field (e.g. `"room_305"`), the
gesture planner maps that to a `places/*` Choregraphe behaviour, and
Pepper *escorts* the participant instead of merely pointing. Latency
budget is unchanged (the walk is async); the existing eye-LED
"navigation blue" already signals the mode. The ROBO-GAP findings on
robot age/gender perception (§27A.8) become an additional dependent
variable: does an escorting robot read as older/more authoritative
than a pointing one?

**On the ROS side.** `ros-naoqi/naoqi_bridge` (and `naoqi_driver2`
for ROS 2) republishes NAOqi services as ROS topics. The bridge is
worth the setup cost the moment you want to integrate with **Nav2**
or any standard ROS perception stack. The compass research already
catalogued this as bridge Pattern 3; the live repository confirms
ROS 1 Noetic and ROS 2 Foxy/Humble are the realistic targets.

### 27A.5  Multilingual Voice — The Japanese-Voice Question

OmniLLM has a language detector that recommends a model per detected
language (the recent `language_code` / `recommended_model` compat
properties). For research participants who code-switch into Japanese,
the robot is currently bottlenecked at NAOqi's stock `nao_jpf` voice
— a 2014-era diphone voice that sounds noticeably worse than modern
Japanese TTS. Two resources clarify the realistic options:

**(a) Voisona Pepper voice library (`voisona.com/song/artist/pepper_ja_JP`)**
— A *singing-voice* library trained on the same Pepper character,
sold commercially through DLsite/Amazon/Sonicwire. The vocal range
(A3–C#5) and tempo (80–120 BPM) make this a poor fit for
conversational TTS. **Verdict: not usable for the Arena.** It is
useful only if you build a "Pepper sings" demo for outreach.

**(b) CeVIO (Wikipedia article)** — The underlying engine behind
Voisona, HTS-HMM based (same family as Sinsy / Open J-Talk). CeVIO
itself is Japanese-only and Windows-only. **A better path** for
conversational Japanese on Pepper is the open-source toolchain that
shares CeVIO's lineage: **Open JTalk + HTS voices** (server-side,
generate `.wav`, send to Pepper through `ALAudioPlayer`) or **VOICEVOX**
(MIT-licensed, modern neural TTS for Japanese, runs locally on the
same GPU you use for Whisper). VOICEVOX is the most practical 2026
choice and slots into the existing TTS abstraction in
`omnillm/server/`.

**Concrete refactor proposal.** Introduce a `tts/` provider directory
mirroring `omnillm/server/providers/`. The current default
(NAOqi `ALAnimatedSpeech`) becomes `tts/naoqi.py`; add `tts/voicevox.py`
that synthesises Japanese to a 16 kHz WAV and ships it back in the
`/interact` JSON as `speech_audio_b64`. The NAOqi client plays it via
`ALAudioPlayer.playFile()`. Body language is lost in this path —
`ALAnimatedSpeech` requires synthesised speech to come from its own
engine — so use it only when the language detector chooses Japanese.

### 27A.6  Vision-Side Upgrades — Face, Emotion, Mask

OmniLLM does not currently consume Pepper's two 5 MP cameras or the
Xtion depth sensor (Chapter 23.2 notes this explicitly). Three
mature open-source pieces would change that without leaving the
existing HTTP-bridge architecture:

**(a) `ageitgey/face_recognition`** — dlib-based, 99.38 % on LFW.
Python 3 only, runs comfortably on the AI-server side. Add a
`/recognise_face` endpoint that accepts a JPEG from the NAOqi
client (captured via `ALVideoDevice.getImageRemote()`) and returns a
participant ID. Two research uses:

- **Personalised greetings** — the agent remembers a returning
  participant and adapts its register.
- **Automatic session-ID assignment** — `participant_id` is currently
  passed as a CLI flag, error-prone in a live study. Face recognition
  removes the source of that error.

**(b) `LucaCorvitto/Emotional_Pepper`** — Mixes Python (44.8 %), web
UI (42.6 %), and **PDDL planning (12.6 %)**. The PDDL piece is the
interesting one for OmniLLM: it shows a planner driving Pepper's
"mood" through a structured world model rather than freeform LLM
output. **Hybrid idea:** keep the LLM as the *content* generator, but
gate gesture/LED selection through a small PDDL plan when the agent
needs to maintain a persistent emotional arc across an interaction
(a known weakness of pure LLM-driven gesture mapping). Their report
PDF is worth pulling for Part X / thesis design.

**(c) `softbankrobotics-labs/pepper-mask-detection` and
`pepper-deep-learning`** — QiSDK libraries (Kotlin/C++), targeting
NAOqi 2.9 + Android tablet. They confirm what Chapter 23.7 warned:
*new* perception work in the SoftBank-Labs org is **NAOqi 2.9 only**.
If OmniLLM ever migrates to NAOqi 2.9, the SDK split (Kotlin on the
robot, Python on the server) becomes mandatory; bridge Pattern 5
(WebSocket) is the natural choice there, not the current REST.

**Additional finding from `arxiv.org/abs/2401.17663`** ("Social
Robot Navigation with Adaptive Proxemics Based on Emotions", Bilen
et al., 2024) — not a Pepper-LLM paper, but it provides experimental
evidence that *proxemic distance* should change with detected
emotion (angry participants want more space; happy ones don't want
less). If §27A.4's "OmniLLM Wayfinder" extension is built, the same
emotion signal could feed the approach-distance parameter.

### 27A.7  Dialogue Platforms That Came Before LLMs

Several listed resources predate the LLM era. They are *not*
substitutes for OmniLLM's stack but they teach important lessons:

**(a) Pepper + Dialogflow integration (Medium article by
blogemtech)** — Architecture: Pepper's microphone streams into a
custom `SoundProcessingModule` (ALModule subclass) with silence
detection, then to Dialogflow's `detectIntent` API. Three concrete
takeaways:

1. **Silence detection is essential** — without it Pepper streams
   constantly and you exhaust API quota. OmniLLM's current
   `ALAudioDevice.subscribe()` loop in `naoqi_client.py` does **not**
   do silence detection; it relies on a fixed 5-second window.
   For longer interactions, port the article's amplitude-threshold
   peak detector (test threshold = 14 000 on 16 kHz mono).
2. **Pepper's onboard ASR is unreliable for proper nouns** — "Bob"
   reliably mis-recognised as "Paul" despite training. This is why
   OmniLLM uses Whisper. Worth citing in defence of the design
   choice.
3. **Anaconda is incompatible with NAOqi SDK.** Use system Python 2.7
   or `pyenv`. (Matches the memory note.)

**(b) `TheRARELab/langex`** — *Not* an LLM project. A Choregraphe
template for reproducible language-HRI experiments: configurable
"Factor 1/2/3" conditions, dialogue in `.txt` files per condition,
auto-logged filenames with the experimental parameters baked in.
Three direct ideas for OmniLLM's experiment runner:

- **Filename convention** — embed condition, participant, model in
  the log filename so a folder listing is self-describing.
- **`type 'next'` advancement** — for pilot studies where you want
  to control utterance pacing manually before opening to real-time
  audio.
- **Reproducibility headers** — every log file starts with a header
  block recording all experimental parameters. OmniLLM already
  exports JSON; consider adding a `metadata` block matching langex's
  format.

**(c) `softbankrobotics-labs` org generally** — `pepper-app-launcher`,
`pepper-gamepad`, `pepper-solitaries-loop`. The "solitaries loop"
(idle animations) is the resource most relevant to OmniLLM: between
participant turns, Pepper currently goes still — uncanny in a
long study. A small subscribed loop that triggers `pepper-solitaries`
animations during idle would improve perceived liveliness without
touching the agent.

### 27A.8  Validation Suites, Curricula, and HRI Reference Datasets

For thesis-grade validity arguments (see Part X), the following
external resources let you defend the experimental design without
re-justifying every choice:

**(a) `robocupathomeedu.org/learn/online-classroom/online-challenge-2022`**
— Page would not load during research, but the broader RoboCup@Home
Education curriculum is the standard set of tasks (person following,
object handover, spoken instruction following, navigation between
rooms) that a service robot is expected to handle. Use this list as
the *external rubric* against which to claim OmniLLM coverage in
Part X. Of the standard tasks, OmniLLM currently covers spoken
instruction following and grounded answering; navigation and
person-following are unlocked by §27A.4.

**(b) `sunzhida/COMP4461_2017Fall_Lab4`** — HKUST HCI course lab on
Pepper. The exercise (`expression_teller.py`) is a one-file demo of
face detection + gender + expression classification through NAOqi's
on-board modules. Two uses for the thesis:

- **Baseline implementation** to compare LLM-driven emotional
  response against an ALMemory-event-driven baseline.
- **Pedagogical citation** when arguing OmniLLM is approachable for a
  graduate course (Part XI is already pitched this way).

**(c) `robo-gap.unisi.it`** (Perugia et al., 2022, HRI ACM/IEEE) —
A peer-reviewed dataset of perceived age, femininity, masculinity,
and gender-neutrality across 251 robots, including Pepper. The
dataset is downloadable as CSV with ICC reliability between .896 and
.954. **Concrete use in OmniLLM's thesis:** as a control variable.
When reporting results, cite ROBO-GAP's published Pepper ratings so
the reader knows *what perception baseline* the participants are
walking in with. This is the kind of small move that hardens an HRI
paper against reviewer pushback.

**(d) CARESSES (`caressesrobot.org`)** — Pepper used for *culturally
competent* elder care across UK / Japan / India. The web server was
unreachable during research; the publications stack (search "Bruno",
"Sgorbissa", "CARESSES" on Google Scholar) is the relevant entry
point. Important for Part X if you want to position OmniLLM as a
cultural-HRI platform rather than a generic chatbot.

### 27A.9  Future Directions Unlocked by These Resources

Ranked by ease and research payoff, drawing only on what the
resources above actually demonstrate:

| Idea | Effort | Research payoff | Hooks into |
|------|--------|-----------------|------------|
| Disable Autonomous Life on connect (kill stock dialogue) | 1 line in `naoqi_client.py` | Removes a confound that all five sibling projects have already fixed | §27A.2 |
| Add solitaries / idle animations loop | ~30 LoC | Perceived liveliness during long sessions | §27A.7 |
| Silence-detected audio capture (replace fixed 5 s window) | ~80 LoC | Lets the participant pause/think without truncation | §27A.7 |
| VOICEVOX Japanese TTS provider | new `tts/voicevox.py` provider | Unlocks Japanese-language Arena condition with modern voice | §27A.5 |
| ALAutonomous-style face memory via `ageitgey/face_recognition` | new `/recognise_face` endpoint | Eliminates manual participant-ID entry; enables personalised greeting | §27A.6 |
| ARUCO + `places/` navigation as new condition D | new condition + 4 Choregraphe behaviours | Tests escorting vs. pointing — novel HRI finding | §27A.4 |
| ROS 2 bridge via `naoqi_driver2` | new `naoqi_client_ros2/` package | Opens fleet / multi-robot experiments | §27A.4 |
| Migration to NAOqi 2.9 + QiSDK (Kotlin) | full rewrite of robot side | Future-proofs the project against pynaoqi rot | §27A.6 |

The first three rows are quick wins worth doing before the next
participant cohort. Rows 4–6 are dissertation-chapter scale. Rows 7–8
are post-thesis directions.

### 27A.10  Annotated Resource List

Resources that did not get a dedicated subsection above, plus pointers
back to the ones that did, with one-line "why it matters" notes:

| Resource | Why it matters for OmniLLM |
|----------|----------------------------|
| `caressesrobot.org/en/category/research/` | Pepper for culturally competent elder care — cite for cultural-HRI framing of the thesis |
| `voisona.com/song/artist/pepper_ja_JP` | Singing-voice library; *not* viable for conversational TTS, only for outreach demos |
| `en.wikipedia.org/wiki/CeVIO` | Background on the HTS-HMM family; points you toward VOICEVOX as the practical successor |
| `blogemtech.medium.com/pepper-integration-with-dialogflow-...` | Silence-detection + amplitude-threshold recipes for `naoqi_client.py` |
| `robots.ros.org/pepper/` | High-level pointer into the `naoqi_bridge` ROS packages |
| `doc.aldebaran.com/1-14/...` and `doc.aldebaran.com/2-5/...` | The canonical NAOqi reference; bookmark Service Pages (`ALMotion`, `ALAnimatedSpeech`, `ALMemory`, `ALAudioDevice`) |
| `maxtronics.com/en/support/kb/` and `.../category/pepper/...` | Post-bankruptcy mirror of Pepper 2.5 and 2.9 downloads (firmware, Choregraphe, SDK) |
| `stackoverflow.com/questions/tagged/pepper` | First-stop for one-off NAOqi/Choregraphe errors; *not* an answer source for architectural questions |
| `github.com/TheRARELab/langex` | Reproducible language-HRI experiment template — borrow its log-filename and header conventions |
| `softbankroboticstraining.github.io/pepper-chatbot-api/` | Dialogflow-based "Pepper Chat" — source of QiChat voice-shaping commands for affective TTS |
| `github.com/softbankrobotics-labs/pepper-proactive-mobility` | Proactive approach + ARUCO/SLAM localisation — basis for the Wayfinder condition |
| `github.com/aldebaran/naoqi_navigation_samples` | `explore`/`patrol`/`places` Choregraphe samples — fastest way to add named-location navigation |
| `github.com/ros-naoqi/naoqi_bridge` | ROS-side wrapper of NAOqi services — entry into Nav2 |
| `groups.google.com/g/ros-sig-aldebaran` | Slow but active community list — best place to ask `naoqi_driver2` questions |
| `doc.aldebaran.com/2-5/index_dev_guide.html` and `.../getting_started/index.html` | Official guides; sections on `ALMemory` events and `ALAnimatedSpeech` configuration are the most frequently re-read |
| `robocupathomeedu.org/.../online-challenge-2022` | External rubric of service-robot tasks — use to scope thesis claims |
| `maxtronics.com/en/support/kb/` (NAO content) | NAO-specific KB; relevant if you ever port OmniLLM to NAO as a portability proof |
| `github.com/orgs/aldebaran/repositories` | `libqi`, `libqi-python`, `qibuild` are still maintained (Apr 2026 updates); `robot-jumpstarter` is the best Python starter |
| `softbankroboticstraining.github.io/pepper-chatbot-api/#pepper-chat` | Same as above — anchored deep link into the QiChat command reference |
| `github.com/softbankrobotics-labs` (org root) | Browse for `pepper-aruco`, `pepper-mask-detection`, `pepper-deep-learning`, `pepper-solitaries-loop`, `navigation-toolkit-demo` |
| `github.com/aldebaran/naoqi_navigation_samples` | (See §27A.4 — duplicate intentional, called out twice as the highest-value link in this list) |
| `softbankroboticstraining.github.io/pepper-chatbot-api/` | Tablet UI customisation patterns — relevant if the Arena ever uses the chest tablet |
| `softbankrobotics-labs/pepper-proactive-mobility` | (See §27A.4) |
| `aldebaran/naoqi_navigation_samples` | (See §27A.4) |
| `ros-naoqi/naoqi_bridge/tree/master/naoqi_apps` | Sample ROS apps that use the bridge — read these before writing your own ROS node |
| `groups.google.com/g/ros-sig-aldebaran?pli=1` | (See above) |
| `doc.aldebaran.com/2-5/index_dev_guide.html` | Canonical dev guide |
| `robocupathomeedu.org/learn/online-classroom/online-challenge-2022` | Service-robot task rubric |
| `maxtronics.com/en/support/kb/` | Pepper KB (post-Aldebaran) |
| `maxtronics.com/en/support/kb/category/pepper/downloads-softwares/` | Pepper 2.5 & 2.9 downloads — the most reliable place to re-fetch Choregraphe and the SDK |
| `doc.aldebaran.com/2-5/getting_started/index.html` | The "first 10 minutes with Pepper" reference |
| `github.com/softbankrobotics-labs` | (org root, see above) |
| `github.com/incognite-lab/Pepper-Controller` | Python-class abstraction over NAOqi 2.5 — model for refactoring `naoqi_client.py` |
| `github.com/lillypiri/pepper` | Beginner Choregraphe exercises — useful for onboarding collaborators new to box-and-wire |
| `nlp.fi.muni.cz/trac/pepper/wiki/InstallationInstructions` | Linux install path with a custom `pyenv_install.sh` — best alternative to Anaconda |
| `robohack.org.uk/viewforum.php?f=6` | Small UK robotics-hobbyist forum — occasional Pepper troubleshooting threads, low signal |
| `github.com/sunzhida/COMP4461_2017Fall_Lab4` | HKUST course lab — `expression_teller.py` is a 50-line baseline for emotion-aware response |
| `zijianhu.com/post/nao-tutorial/installation/` | Tutorial-style NAO install — Linux focus, complements §27A.3 |
| `wiki.ros.org/nao/Tutorials/Installation` | Official ROS NAO install — pre-Pepper but the bring-up patterns transfer |
| `arxiv.org/abs/2401.17663` | Emotion-adaptive proxemics paper (Bilen et al. 2024) — empirical basis for tying detected emotion to approach distance in the Wayfinder extension |
| `github.com/ageitgey/face_recognition` | dlib-based face recognition; the practical choice for a `/recognise_face` endpoint |
| `github.com/LucaCorvitto/Emotional_Pepper` | PDDL-planned emotional behaviour over a tablet UI — hybrid LLM+planner inspiration |
| `github.com/AnonKour/pynaoqi` | Linux mirror of the Python 2.7 NAOqi SDK — keep the URL in case Aldebaran's mirror disappears |
| `robotlab.com/support/factory-reset-on-pepper-robot` | Authoritative factory-reset SOP (PuTTY/FileZilla/`nao-autoflash`) — *do not* run this without a current backup of `/home/nao` |
| `github.com/UoA-CARES/pepper-demo` | ZLIB symlink fix for Choregraphe on Linux — save for later |
| `github.com/UoA-CARES/Pepper-GPT` | Closest sibling to OmniLLM in spirit — different LLM strategy (single GPT-3.5), worth full code-walk |
| `github.com/igor-lirussi/Dialogue-Pepper-Robot` | Java AIML + Py2 NAOqi split — the architectural ancestor of OmniLLM |
| `github.com/ilabsweden/pepperchat` | The original (2023) public HTTP-bridge OpenAI Pepper project — cite as prior art |

### 27A.11  What Is Deliberately Not Here

Three categories of resource the user originally listed but that
proved either inaccessible or off-topic on closer reading:

- **`caressesrobot.org`** — server unreachable during research; the
  *published papers* (Sgorbissa, Bruno, et al.) are the productive
  citation target rather than the website.
- **`arxiv.org/abs/2401.17663`** — not an LLM-on-Pepper paper. It is a
  navigation/proxemics paper that nonetheless informs §27A.6.
- **`voisona.com` and CeVIO** — commercial, singing-voice, Japanese-
  only; the practical Japanese-TTS path for OmniLLM is VOICEVOX, not
  these. Listed because the user provided them; reasoning recorded so
  the choice does not have to be re-litigated later.

\newpage
