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
