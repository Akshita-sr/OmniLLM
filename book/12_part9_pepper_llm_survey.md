\newpage

# PART IX — PEPPER-LLM INTEGRATION SURVEY

> This part is a **standalone technical reference** on how Pepper, NAOqi,
> Choregraphe and modern LLMs fit together. It consolidates the
> `compass_artifact_*.md` research notes that informed OmniLLM's design.
> If Parts I–VIII told you *what OmniLLM is*, Part IX tells you *what
> Pepper is* — the hardware, the middleware, and the catalogue of
> published projects that tried this before you.

\newpage

## Chapter 40 — Pepper's Hardware and Software Platform

> **AT A GLANCE.** Pepper is a 120 cm, 28 kg, 20-DoF semi-humanoid social
> robot from SoftBank Robotics (originally Aldebaran). 20 degrees of freedom,
> Intel Atom CPU, NAOqi OS on top of Gentoo Linux, Python 2.7 only. The
> hardware is interesting; the software is dated; both are what you'll
> work with.

### 40.1  Physical Specs at a Glance

| Attribute | Value |
|---|---|
| Height | 120 cm |
| Weight | 28 kg |
| Degrees of freedom | 20 (2 head, 2×6 arm/hand, 2 hip, 1 knee, 3 omnidirectional base wheels) |
| Battery | 30 Ah / 795 Wh lithium-ion (~8–10 hours active) |
| Onboard CPU | Intel Atom E3845 quad-core @ 1.91 GHz |
| Onboard RAM | 4 GB DDR3 |
| Onboard storage | 8 GB flash + microSD slot |
| Operating system | NAOqi OS (modified Gentoo Linux) |
| Onboard Python | 2.7 |

### 40.2  Sensor Suite

- **2 × 5 MP RGB cameras** (forehead and chin, Omnivision OV5640)
- **ASUS Xtion 3D depth sensor** (320×240, 0.4–8 m range) behind the eyes
- **4 directional microphones** on the head for sound localisation
- **2 speakers** in the ears
- **2 sonar sensors** in the base
- **6 laser line generators** in the base
- **2 infrared sensors** in the base
- **3 bumper contact sensors** in the base
- **3 head capacitive touch sensors** and **2 hand touch sensors**
- **Gyroscope and accelerometer IMUs** in both torso and base

### 40.3  The Chest Tablet

The chest-mounted **10.1-inch IPS capacitive touchscreen** runs at
**1280×800 resolution** with 5-point multi-touch. It is powered by a
separate **1.3 GHz quad-core ARM Cortex-A7** with **1 GB RAM** and
**32 GB storage** running Android. The tablet communicates with the
robot's head computer over an internal network at IP **198.18.0.1**. From
NAOqi's perspective it is exposed via the `ALTabletService` module.

### 40.4  Two OS Variants — and Which to Use

| Version | SDK | Choregraphe | API surface | Pepper status |
|---|---|---|---|---|
| **NAOqi 2.5** | Python/C++ | Yes | ~1,000+ APIs | Standard for most Pepper units in research labs |
| **NAOqi 2.9** | Android + QiSDK (Java/Kotlin) | No | ~20 high-level APIs | Newer "Pepper 1.8" units; Choregraphe-incompatible |

For LLM integration work using Python, **NAOqi 2.5 is the de-facto
standard**. OmniLLM targets this version.

### 40.5  The End-of-Life Situation

Aldebaran filed for bankruptcy in **February 2025**. Its IP was acquired
by **Maxvision Technology Corp. (Shenzhen)** in **July 2025**, and
**no new units are being manufactured**. Existing units continue to
work; spare parts and SDK downloads are increasingly hard to source.

The implication for OmniLLM: the abstract `RobotBridge` (Chapter 19) is
deliberately platform-portable. When (not if) you have to retarget
NAO or Buddy or any future robot, only the bridge implementation
changes — the AI server doesn't.

\newpage

## Chapter 41 — NAOqi Framework, PyNAOqi, and Programmatic Connection

> **AT A GLANCE.** NAOqi is the **middleware broker** running on TCP
> port **9559**. Every module — `ALTextToSpeech`, `ALMotion`,
> `ALMemory`, and dozens more — registers its methods with the broker,
> enabling both local procedure calls (in-process, zero-copy) and
> remote procedure calls (over TCP, serialised). PyNAOqi is the
> Python 2.7 binding that exposes this entire API.

### 41.1  Installing PyNAOqi

PyNAOqi is **not pip-installable**. It must be downloaded manually from
the SoftBank Robotics developer portal as a platform-specific archive
such as `pynaoqi-python2.7-2.5.5.5-linux64.tar.gz` (Linux) or
`pynaoqi-python2.7-2.5.5.5-win32-vs2013.zip` (Windows).

Installation steps:

1. Extract the archive (e.g., to `C:\pynaoqi\` on Windows).
2. Set `PYTHONPATH` to include the SDK's `lib/python2.7/site-packages` directory.
3. On Windows, **32-bit Python 2.7 is required** to match the 32-bit
   native bindings, plus the **MSVC++ 2010 x86 redistributable**.

```bash
# Linux
export PYTHONPATH="$HOME/pynaoqi/lib/python2.7/site-packages:$PYTHONPATH"

# Windows CMD
set PYTHONPATH=C:\pynaoqi\pynaoqi-python2.7-2.5.5.5-win32-vs2013\lib;%PYTHONPATH%
set PATH=C:\pynaoqi\pynaoqi-python2.7-2.5.5.5-win32-vs2013\lib;%PATH%
```

### 41.2  Two Connection Paradigms

The **legacy `ALProxy` approach** creates direct proxies — one proxy per
service. Simple and explicit:

```python
from naoqi import ALProxy
tts = ALProxy("ALTextToSpeech", "192.168.1.100", 9559)
tts.say("Hello from ALProxy!")
```

The **modern `qi.Session` approach** uses a shared session object —
recommended for any non-trivial application because it shares one TCP
connection across all services:

```python
import qi
session = qi.Session()
session.connect("tcp://192.168.1.100:9559")
tts = session.service("ALTextToSpeech")
tts.say("Hello from qi.Session!")
```

OmniLLM's `naoqi_client.py` (Chapter 21) tries `qi` first and falls back
to `ALProxy` so it works against both old and new SDK versions.

\newpage

## Chapter 42 — The Eleven NAOqi Modules That Matter for LLM Integration

These are the modules you'll touch. Master these eleven and you can build
nearly any Pepper-LLM application.

### 42.1  Speech

**`ALTextToSpeech`** — converts text to speech on the robot's speakers;
supports speed and pitch parameters and embedded markup tags like
`\\RSPD=80\\` (speed 80 %) and `\\VCT=110\\` (voice pitch 110 %).

**`ALAnimatedSpeech`** — speech synchronised with gestures. Annotation
tags such as `^start(animations/Stand/Gestures/Hey_1)` trigger
concurrent animations. The configuration option
`bodyLanguageMode` accepts `"contextual"` (gestures match the speech
content automatically, recommended), `"random"`, or `"disabled"`.

```python
tts = session.service("ALAnimatedSpeech")
tts.say("Welcome to the lab!", {"bodyLanguageMode": "contextual"})
```

### 42.2  Motion and Posture

**`ALMotion`** — joint-level motor control. `wakeUp()` / `rest()` toggle
stiffness; `setAngles()` for non-blocking moves; `angleInterpolation()`
for timed trajectories. **You must call `wakeUp()` before any movement**
or the joints have zero stiffness and the robot ignores commands.

**`ALRobotPosture`** — whole-body posture management.
`goToPosture("Stand", 0.8)` returns Pepper to a standard stance with
80 % speed.

### 42.3  Audio

**`ALAudioRecorder`** — records microphone audio to WAV/OGG files on
the robot filesystem. Simpler API but adds a file-transfer step.

**`ALAudioDevice`** — real-time audio streaming via the `processRemote`
callback. Supports 16 kHz or 48 kHz, 1 or 4 channels. Subclass
`ALModule`, implement `processRemote(nbChannels, nbSamples, timeStamp,
inputBuffer)`, then `subscribe()` to receive raw int16 samples in real
time.

OmniLLM's audio path uses **`ALAudioDevice`** because the latency budget
demands streaming, not file-transfer.

### 42.4  Speech Recognition (Spoiler: Use Whisper Instead)

**`ALSpeechRecognition`** — on-board keyword recognition with a
predefined vocabulary; results stored in `ALMemory` under
`"WordRecognized"`. **Universally considered inadequate for open-domain
speech.** All modern Pepper-LLM projects bypass it and use OpenAI
Whisper (locally via `openai-whisper` or via the API) instead. OmniLLM
follows this pattern.

### 42.5  Events and Memory

**`ALMemory`** — the central key-value store and event bus.
`subscriber("EventName").signal.connect(callback)` enables reactive
programming. Almost every NAOqi module publishes events to `ALMemory`,
so this is where you wire perception to reaction.

```python
memory = session.service("ALMemory")
def on_touch(value):
    print("Head touched:", value)
sub = memory.subscriber("FrontTactilTouched")
sub.signal.connect(on_touch)
```

### 42.6  Vision

**`ALFaceDetection`** — OMRON-based face detection. Subscribes to the
`"FaceDetected"` event with face position, size, and optional
recognition data. Used by OmniLLM to trigger interaction start when
someone walks into Pepper's field of view.

### 42.7  Output Devices

**`ALLeds`** — RGB control of eye, ear, chest and foot LEDs.

```python
leds = session.service("ALLeds")
leds.fadeRGB("FaceLeds", 0.0, 0.67, 1.0, 0.5)   # navigation blue, 500ms fade
```

**`ALTabletService`** — controls the chest tablet display (Pepper only;
NAO has no tablet). `loadUrl()`, `showImage()`, `executeJS()`.

```python
tablet = session.service("ALTabletService")
tablet.loadUrl("http://192.168.1.50:5000/map?room=305")
tablet.showWebview()
```

### 42.8  Behaviours

**`ALBehaviorManager`** — lists, runs and stops Choregraphe behaviours
installed on the robot.

```python
bm = session.service("ALBehaviorManager")
bm.runBehavior("animations/Stand/Gestures/Hey_1")   # wave
```

OmniLLM maps each gesture name in `GESTURE_TO_BEHAVIOR`
(Chapter 21) to the behaviour path that NAOqi expects.

\newpage

## Chapter 43 — Choregraphe as a Visual Programming IDE

> **AT A GLANCE.** Choregraphe is SoftBank's drag-and-drop desktop IDE
> for programming Pepper and NAO. It is locked to **NAOqi 2.5**. It
> includes a virtual robot simulator that runs without any hardware,
> plus a Python 2.7 script editor for inline testing. For OmniLLM you
> use it for three things: testing behaviours without a real robot,
> installing custom animations, and live monitoring during experiments.

### 43.1  The Four-Panel Layout

```
+----------------------------------------------------------+
| BOX LIBRARY |  FLOW DIAGRAM  | 3D ROBOT VIEW            |
| (left)      |  (center)      | (right)                   |
|             |                |                           |
| Drag boxes  | Wire boxes     | Virtual or real Pepper   |
| from here   | together to    | reflected in real time   |
|             | build behaviour|                           |
+----------------------------------------------------------+
| LOG VIEWER / SCRIPT EDITOR (bottom)                      |
| NAOqi log messages, Python 2.7 inline scripting          |
+----------------------------------------------------------+
```

### 43.2  When to Use Choregraphe vs OmniLLM

| You want to ... | Choregraphe | OmniLLM |
|---|---|---|
| Test Pepper's speech | yes | — |
| Test a single gesture | yes | — |
| Build / tune a custom animation | yes | — |
| Build an AI-driven conversation | — | yes |
| Use multiple LLMs as backends | — | yes |
| Run a controlled HRI experiment | — | yes |
| Live monitor an experiment | yes (alongside) | yes |

They are complementary. The typical workflow:

1. **Plan gestures in Choregraphe** — drag and edit until they look natural.
2. **Upload to Pepper** — File → Build Application Package → upload.
3. **Add the gesture names to OmniLLM's `GESTURE_TO_BEHAVIOR`** map.
4. **Run the OmniLLM experiment** — leave Choregraphe open as a monitor.

### 43.3  Connecting Choregraphe

**Virtual robot (no hardware needed):**

1. Open Choregraphe.
2. Connection → Connect to virtual robot.
3. Pepper appears in the 3D view; status bar shows
   `Connected to localhost:9559 (virtual)`.

**Physical robot:**

1. Same Wi-Fi as Pepper.
2. Press Pepper's chest button — it says its IP.
3. Connection → Connect to ..., enter the IP, port 9559.
4. The 3D view mirrors the real robot's joint positions.

### 43.4  The Script Editor Shortcut

Press `Alt+5` to open the Script Editor at the bottom and type Python
2.7 directly:

```python
# Test ALAnimatedSpeech
tts = ALProxy("ALAnimatedSpeech", "localhost", 9559)
tts.say("OmniLLM is ready.", {"bodyLanguageMode": "contextual"})

# Test a gesture
b = ALProxy("ALBehaviorManager", "localhost", 9559)
b.runBehavior("animations/Stand/Gestures/Explain_8")  # point left

# Set LEDs blue
leds = ALProxy("ALLeds", "localhost", 9559)
leds.fadeRGB("FaceLeds", 0.0, 0.67, 1.0, 0.3)
```

This is the fastest way to verify NAOqi services are healthy before
debugging OmniLLM.

\newpage

## Chapter 44 — Programming Patterns: Audio, Tablet, Face Detection

### 44.1  Audio Capture for STT

There are three ways to get audio off Pepper for transcription:

| Pattern | Latency | Complexity | When to use |
|---|---|---|---|
| `ALAudioRecorder` + SCP | 2–5 s | Low | Quick demos; OK for batch |
| `ALAudioDevice.subscribe` + callback | <1 s | High | Real-time HRI (OmniLLM uses this) |
| External USB microphone + Whisper API | <0.5 s | Medium | Highest quality, bypasses Pepper mics |

Many published projects (Chapter 46) chose pattern 3 because Pepper's
on-board microphones, while four-channel, are noise-prone in busy
public settings.

### 44.2  Tablet Patterns

The chest tablet is an Android web view. Three usage patterns:

1. **Static image** — `showImage(url)` to display a map or photo.
2. **HTML page** — `loadUrl(url)` to load a Flask-served page; useful
   for showing retrieved RAG results.
3. **JavaScript bridge** — `executeJS()` lets the LLM-server push live
   updates without reloading the page.

For OmniLLM, the natural pattern is: AI server stores rendered HTML at
`/map/<room>`; the RobotAction's `metadata.tablet_url` is read by the
NAOqi client and passed to `loadUrl()`.

### 44.3  Face Detection as Interaction Trigger

```python
faces = session.service("ALFaceDetection")
faces.subscribe("OmniLLMTrigger", 500, 0.0)  # 500ms refresh

mem = session.service("ALMemory")
def on_face_seen(value):
    if value:   # value is [TimestampedFloatArray, FaceInfoArray]
        omnillm_client.greet()
sub = mem.subscriber("FaceDetected")
sub.signal.connect(on_face_seen)
```

This snippet makes Pepper wait passively and only greet visitors when
their face appears.

\newpage

## Chapter 45 — The Python 2.7 ↔ 3.x Bridge: Five Patterns Reviewed

> **AT A GLANCE.** Modern AI libraries (LiteLLM, LangGraph, ChromaDB,
> openai-whisper) require Python 3.11+. NAOqi requires Python 2.7. They
> cannot share a process. The published literature converges on five
> patterns to bridge them.

### 45.1  Pattern 1 — HTTP / REST Bridge (OmniLLM's Choice)

Two processes: Python 2.7 NAOqi client and Python 3.x Flask server.
Communicate over JSON-over-HTTP.

**Used in:** `ilabsweden/pepperchat` (2023), Frontiers ASD therapy
project (Billing et al., 2024), 6+ others.

**Trade-offs:** Easiest to debug (every message is `curl`-able), most
documented, ~50–200 ms HTTP overhead per turn. **This is the OmniLLM
default.**

### 45.2  Pattern 2 — Socket-Based Bridge

Raw TCP socket between Python 2.7 and Python 3.x, often with a custom
binary protocol or newline-delimited JSON.

**Used in:** Pepper-GPT (University of Auckland), Ghent University
elder care project.

**Trade-offs:** Lower latency (~10–50 ms), but more code to write
(framing, reconnection, error handling). Worth it for token-streaming
applications.

### 45.3  Pattern 3 — ROS2 Bridge via `naoqi_driver2`

The robot publishes audio and sensor topics over ROS2; a Python 3.x
node subscribes and dispatches to LLMs. Action plans are published
back to a ROS2 topic the robot subscribes to.

**Used in:** Multi-robot research projects, EU H2020 projects.

**Trade-offs:** Powerful when many components publish/subscribe (e.g.,
SLAM, Nav2 navigation, multi-robot coordination), but high setup
complexity for a single-robot study.

### 45.4  Pattern 4 — MQTT Broker

Both Python 2.7 and Python 3.x publish/subscribe to topics on an MQTT
broker (e.g., Eclipse Mosquitto).

**Used in:** LAIR-GPT (University of Ancona).

**Trade-offs:** Good when many components need to publish/subscribe
independently; adds a broker as a third process.

### 45.5  Pattern 5 — Python 3 qi 3.1.5 (Single Process, Risky)

A community-built `qi 3.1.5` package exists on PyPI for Linux x86_64
Python 3. It exposes the NAOqi API directly in Python 3 — no bridge
needed.

**Used in:** Prototypes, hobbyist projects.

**Trade-offs:** Several services are **broken** in this port (touch
detection, audio callbacks, certain event subscriptions). Unsuitable
for production. OmniLLM does not use this.

### 45.6  Why OmniLLM Picked Pattern 1

| Criterion | HTTP/REST | Socket | ROS2 | MQTT | qi 3.1.5 |
|---|---|---|---|---|---|
| Debuggability | best | good | poor | medium | medium |
| Latency | OK | best | OK | OK | best |
| Lines of code | low | medium | high | medium | low |
| Cross-platform | best | best | poor | best | poor |
| Survives provider quirks | best | best | OK | best | poor |
| Documented in literature | best | good | good | medium | poor |

For a typical Pepper + LLM HRI study, the HTTP bridge is the sweet
spot. If you ever need sub-100 ms end-to-end (token-streaming TTS),
switch to socket. If you ever need ROS2 navigation, add `naoqi_driver2`
alongside.

\newpage

## Chapter 46 — Catalogue of Published Pepper-LLM Projects (2023–2026)

A survey of 15+ projects that connect Pepper (or similar SoftBank robots)
to LLMs. Each entry shows what they did, the architecture pattern, and
the lesson OmniLLM learnt from it.

### 46.1  Academic Publications

| Project | Year | LLM Used | Bridge Pattern | Key Lesson |
|---|---|---|---|---|
| Irfan et al., HRI 2024 — *Between Reality and Delusion* | 2024 | ChatGPT | HTTP REST | Single LLM is fragile; multi-model would be more robust |
| Nichols et al., arXiv 2024 — *Can ChatGPT Control a Pepper Robot Adequately?* | 2024 | GPT-4 | Socket | Latency is the dominant UX variable |
| Grassi et al., HAI 2024 — *ChatGPT-based Pepper Robot for Restaurant Service* | 2024 | ChatGPT | HTTP REST | Domain-specific RAG dramatically improves perceived accuracy |
| Spitale et al., arXiv 2024 — *Vita: An LLM-Powered Social Robot for Wellbeing* | 2024 | Custom | HTTP REST | Empathy and warmth need a different system prompt than factual tasks |
| Billing et al., Frontiers 2024 — *Language Models for HRI* | 2024 | Multiple (single-model tests) | HTTP REST | First survey paper acknowledging multi-LLM as a research gap |
| Pepper-GPT (Auckland) | 2023 | GPT-3.5 | Socket | Socket latency advantage matters in face-to-face conversation |
| ilabsweden/pepperchat | 2023 | GPT-3.5 | HTTP REST | Public reference implementation of the HTTP bridge pattern |
| LAIR-GPT (Ancona) | 2023 | GPT-4 | MQTT | MQTT useful when many components subscribe |
| Frontiers ASD therapy | 2024 | GPT-4 | HTTP REST | RAG over therapy protocol PDFs increased clinician trust |

### 46.2  GitHub Repositories

| Repository | What It Contains |
|---|---|
| `Awesome-LLM-Robotics` | Curated collection of 200+ papers on LLMs + robotics |
| `microsoft/PromptCraft-Robotics` | Microsoft's framework for ChatGPT + robot control |
| `BerriAI/litellm` | Unified API gateway for 100+ LLM providers (used by OmniLLM) |
| `langchain-ai/langchain` | RAG pipelines, document loaders, chains |
| `langchain-ai/langgraph` | Stateful agent graphs with conditional routing (used by OmniLLM) |
| `softbankrobotics-labs/*` | Official Pepper/NAO community examples |
| `pepper-chatgpt-integration` | Various community projects connecting Pepper to ChatGPT |
| `Awesome-LLM-Ensemble` | Multi-model consensus and ensemble methods |
| `chroma-core/chroma` | Vector store for RAG (used by OmniLLM) |
| `lm-sys/FastChat` | LMSYS Chatbot Arena — human preference ELO for LLMs |

### 46.3  What Every Project Got Wrong (and How OmniLLM Avoids It)

| Common mistake | OmniLLM's fix |
|---|---|
| Lock the robot to one cloud provider | YAML model registry — swap providers in 7 lines |
| Hard-code prompts in NAOqi Python 2.7 | All prompting lives on the Python 3 side; Python 2.7 is a thin client |
| Skip evaluation, just demo | Built-in LLM-as-Judge, ELO scorer, automatic logging |
| Ignore latency | `latency_ms` recorded in every `ModelResponse` |
| Ignore cost | `cost_usd` tracked per-model, per-session |
| No multilingual | Three-tier language detector + per-language model mapping |
| RAG bolted on as an afterthought | RAG is a first-class LangGraph node with faithfulness scoring |
| No reproducibility | All conditions encoded as `ConditionConfig`; one YAML controls everything |

\newpage

## Chapter 47 — Lessons Learned and Best Practices

### 47.1  Hardware-Level Lessons

1. **Always `wakeUp()` before motion**, or the robot ignores you.
2. **Use `ALAnimatedSpeech`, not `ALTextToSpeech`** — embodiment effect
   research consistently shows talking-head robots rate lower on
   naturalness and intelligence.
3. **Plug in for long sessions.** Pepper can charge while operating;
   sessions exceeding 2 hours run the battery flat.
4. **Bypass on-board speech recognition.** Use external Whisper.
5. **The tablet's IP is `198.18.0.1`** — internal, not your LAN.

### 47.2  Software-Level Lessons

1. **Make the AI server bulletproof in text mode first.** Then add
   audio. Then add the robot. Most debugging time is spent on
   non-AI failures (Wi-Fi, IP addresses, NAOqi stiffness).
2. **Log everything from day 1.** You cannot reconstruct latencies or
   tokens after the fact.
3. **Mock LLM calls in tests.** Real API calls in tests are slow,
   expensive, non-deterministic and brittle.
4. **Cache the LangGraph compile.** First call takes ~10 s; subsequent
   calls are instant.
5. **Use `asyncio.gather`**, not `for ... await ...`, when querying many
   models. 1 second instead of N seconds.

### 47.3  Experimental-Design Lessons

1. **Within-subjects design** is statistically more powerful than
   between-subjects for the same N. Every participant should
   experience multiple conditions.
2. **Counterbalance with a Latin square** to cancel order effects.
3. **Pilot with at least 3 colleagues** before recruiting real
   participants — you will find bugs you couldn't anticipate.
4. **Back up data daily.** Losing a participant's session after they
   left is the worst-case scenario.
5. **Ask a single pairwise preference question** at the end. It
   produces clean ELO matches and respects the participant's time.

### 47.4  Communication-Level Lessons

1. **Show participants the robot before the experiment.** Curiosity-
   driven exploration ruins the first interaction otherwise.
2. **Frame the consent form around "studying Pepper, not you"** to
   reduce performance anxiety.
3. **Have a fallback question** ready when STT fails — "I didn't catch
   that, could you repeat?" — so a misrecognition doesn't kill the
   flow.

\newpage
