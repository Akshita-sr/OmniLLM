\newpage

## Chapter 13 — Robotics Modules

> *Four files between them are everything that talks to (or pretends to talk to) Pepper. They are the cleanest layer in the codebase — abstract base class + concrete Pepper implementation + two small utilities — because the hard work has been delegated to the bridge server in Chapter 14.*

\newpage

### 13.1 `omnillm/robotics/bridge.py` — The Abstract Robot Bridge

#### At a Glance

`bridge.py` declares the **contract** that any robot integration must obey. It defines two data types (`RobotAction`, `RobotSensorData`) and one abstract base class (`RobotBridge` with six abstract async methods). The point is to keep the rest of the codebase **robot-agnostic** — any future humanoid (Nao, Tiago, iCub, a Unity-rendered avatar) can drop in by subclassing `RobotBridge`.

| Symbol | Lines | Purpose |
|---|---|---|
| `RobotAction` dataclass | 20 | What the AI Layer wants the robot to do: `speech`, `gesture`, `movement`, `emotion_led`, `nav2_goal`, `metadata` |
| `RobotSensorData` dataclass | 8 | What the robot tells us back: `touch_sensors`, `face_detected`, `speech_detected`, `battery_level` |
| `RobotBridge` (ABC) | 50 | Six abstract methods: `connect`, `disconnect`, `execute_action`, `get_sensor_data`, `say`, `gesture` |
| `parse_llm_to_action` | 40 | Helper: parse an LLM's JSON output into a `RobotAction`. Strips markdown code fences. |
| `parse_nav2_goal` | 50 | Helper: validate a Nav2-style `{position, orientation}` JSON. Forward-looking for future ROS2 integration. |

#### The Contract

Every method on `RobotBridge` is `async`. This matters because LangGraph's nodes are async — so the bridge can be `await`-ed mid-pipeline without blocking. If we'd written sync methods, every gesture would freeze the entire async event loop for the duration of the NAOqi RPC.

The six abstract methods:

```python
@abstractmethod
async def connect(self) -> bool: ...

@abstractmethod
async def disconnect(self) -> bool: ...

@abstractmethod
async def execute_action(self, action: RobotAction) -> bool: ...

@abstractmethod
async def get_sensor_data(self) -> RobotSensorData: ...

@abstractmethod
async def say(self, text: str) -> bool: ...

@abstractmethod
async def gesture(self, name: str) -> bool: ...
```

The first four are mandatory for any robot. `say()` and `gesture()` are convenience wrappers (every implementation will do something like `return await self.execute_action(RobotAction(speech=text))`) but having them in the ABC enforces the convention.

#### The Safety Note in the Source File

The module docstring contains this warning:

> *"In robotics applications, incorrect LLM outputs can cause physical harm. Always validate `RobotAction` objects through the consensus engine before executing on a real robot — a single-model hallucination should not be enough to trigger robot movement."*

For Pepper specifically, the safety surface is small (Pepper has no grippers, cannot lift objects, cannot manipulate humans), but the principle generalises. Future deployments that wire OmniLLM to a manipulator or a mobile platform should consider running the LLM output through `consensus.synthesise()` before sending it to `execute_action()`.

\newpage

### 13.2 `omnillm/robotics/pepper.py` — The Python 3 Side of Pepper

#### At a Glance

`PepperBridge` is a concrete `RobotBridge` for Pepper. It speaks `aiohttp` HTTP to the Python 2.7 `naoqi_bridge_server` (which we will discuss in Chapter 14). All NAOqi-specific work happens on the Python-2.7 side; this file is pure Python-3 and pure HTTP.

The class supports three modes (`server`, `direct`, `stub`) with automatic detection. The `make_pepper_bridge()` factory function does the right thing for both real Pepper and Choregraphe's virtual robot.

#### The Three Modes

| Mode | Trigger | What `execute_action()` does |
|---|---|---|
| `server` | `GET /ping` to the bridge port returns `{"ok": true, "naoqi": true}` | POST `/action` to the bridge server, which translates to NAOqi calls |
| `direct` | Set manually via `bridge.use_direct_mode()`. Used only by unit tests. | Prints the action to stdout, returns True |
| `stub` | Fallback when nothing else works | Logs to stdout via `logger.info()`, returns True |

The auto-detection logic is in `PepperBridge.connect()`:

```python
async def connect(self) -> bool:
    ping = await self._ping_bridge_server()
    if ping is not None:
        self._mode = "server"
        self._connected = True
        return True
    if self._fallback_policy == "raise":
        raise ConnectionError(...)
    self._mode = "stub"
    self._connected = True
    return True
```

In *auto* mode, `connect()` *always* succeeds — falling to stub if no real bridge is reachable. This is why every pytest can do `bridge = await make_pepper_bridge()` without owning a robot.

#### Choregraphe Port Auto-Discovery

Choregraphe's virtual robot picks a random port between 49152 and 65535 every launch. The `discover_choregraphe_port` function does a two-pass scan:

1. **Hint pass.** Try a small list of ports known from past launches: `(49959, 49960, 49961, 60930, 62494, 9559)`. These are the values the author's laptop has seen across all Choregraphe sessions; the most recent value is first.
2. **Slice scan.** If no hint matches, sample `max_scan=256` ports uniformly across the ephemeral range. The total time bound is `256 * timeout = 256 * 0.05s ≈ 13s` in the worst case, typically <1s when the port is found in the first dozen tries.

The scan is **TCP-reachability only** — it does not validate that the peer actually speaks NAOqi. The follow-up `connect()` call to the bridge server is what catches false positives.

#### The `_tcp_reachable` Helper

```python
def _tcp_reachable(host: str, port: int, timeout: float = 0.5) -> bool:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(timeout)
            sock.connect((host, port))
            return True
    except (OSError, socket.timeout):
        return False
```

A pre-check to avoid paying aiohttp setup cost when the port isn't even open. Tiny optimisation, but with a 256-port scan it cuts the total scan time from 30+ seconds (full aiohttp setup per port) to <1 second.

#### `make_pepper_bridge()` — The Public Entry Point

This is what almost everyone calls. Its contract:

```python
async def make_pepper_bridge(
    robot_ip: str = "127.0.0.1",
    robot_port: int | None = None,
    bridge_port: int = 6000,
    fallback: Literal["auto", "stub", "raise"] = "auto",
) -> PepperBridge:
```

The behaviour:

- `robot_ip="127.0.0.1"`, `robot_port=None` → Choregraphe virtual robot; run port discovery; fall back to 9559 if discovery fails.
- `robot_ip=<other>`, `robot_port=None` → assume real Pepper on default NAOqi port 9559.
- `bridge_port=6000` → standard bridge port; configurable if you run multiple Pepper instances or have a port collision.
- Always calls `.connect()` before returning, so the caller can immediately use the bridge.

#### Why aiohttp and Not requests?

(Beginner) **`requests`** is the famous synchronous Python HTTP library. **`aiohttp`** is the async equivalent. We use aiohttp because every method in `PepperBridge` is `async`. If we used `requests` inside an async method, the call would block the event loop — every other async task (other LLM calls, sensor polling) would pause until the HTTP call returns. That defeats the entire point of asyncio.

\newpage

### 13.3 `omnillm/robotics/gesture_planner.py` — Speech-to-Gesture Mapping

#### At a Glance

`GesturePlanner.plan(task_type, response_text)` returns `(gesture_name, led_color)` based on:

1. The HRI task type (gives a default).
2. Keyword/regex matches in the response text (overrides the default).

It is a small, deterministic, rule-based mapping that runs in milliseconds. The thesis study uses it for every interaction; no LLM is involved in gesture selection.

#### Why Not Have the LLM Pick the Gesture?

The author tested this. Two findings:

1. **LLM-generated gesture names hallucinate.** Asked for a gesture name from a fixed list, GPT-4o-mini frequently returns something off-list (`"smile_warmly"` instead of `"wave"`).
2. **Latency.** Asking the LLM to return JSON with `{response: "...", gesture: "...", led: "..."}` adds ~30% to response time and ~60% to output tokens (cost).

A rule-based planner is faster, cheaper, and 100% reliable. The "smartness" of the brain lives in the LLM's text; the gesture is paired with that text using fixed rules.

#### The Default Gesture Per Task Type

```python
_TASK_DEFAULT_GESTURES = {
    "info_retrieval":      "nod",
    "navigation":          "point_forward",
    "social_conversation": "wave",
    "multilingual":        "nod",
}
```

A T1 (info-retrieval) interaction defaults to a `nod` (acknowledging the question). A T2 (navigation) interaction defaults to `point_forward`. A T3 (social) interaction defaults to a `wave` (friendly greeting). T4 (multilingual) gets a `nod` — neutral but engaged.

#### Direction Patterns Override the Default

For T2 specifically, the planner scans the response text for direction-words:

```python
_DIRECTION_PATTERNS = [
    (re.compile(r"\bon (your |the )?(left|east)\b", re.I), "point_left"),
    (re.compile(r"\bon (your |the )?(right|west)\b", re.I), "point_right"),
    (re.compile(r"\b(straight ahead|in front|forward|north)\b", re.I), "point_forward"),
    (re.compile(r"\b(upstairs|above|floor \d+|level \d+)\b", re.I), "point_up"),
    (re.compile(r"\b(turn left)\b", re.I), "point_left"),
    (re.compile(r"\b(turn right)\b", re.I), "point_right"),
]
```

If the response text is *"The Pepper room is at the end of the ground-floor corridor, on the right"*, the `(right|west)` pattern matches and the gesture becomes `point_right` — overriding the T2 default of `point_forward`.

#### Content-Triggered Gestures

```python
_CONTENT_GESTURE_MAP = [
    (re.compile(r"\b(hello|hi|hey|welcome|greet)\b", re.I), "wave"),
    (re.compile(r"\b(goodbye|bye|see you|farewell)\b", re.I), "wave_goodbye"),
    (re.compile(r"\b(show|look at|see (the |this )?(map|screen|tablet|display))\b", re.I), "show_tablet"),
    (re.compile(r"\b(thinking|let me check|processing)\b", re.I), "think"),
    (re.compile(r"\b(sorry|apologise|don't know|not sure|unclear)\b", re.I), "confused"),
    (re.compile(r"\b(absolutely|certainly|exactly|correct|yes)\b", re.I), "nod"),
]
```

These work across task types. If the LLM's response says *"Hello!"*, the planner picks `wave`. If it says *"I'm not sure"*, the planner picks `confused` (and the LED turns red-orange).

#### LED Colours

`GESTURE_LED_COLORS` is a fixed mapping from gesture to hex colour. The colour choice is informed by:

- Green = positive / friendly (wave, bow, nod)
- Blue = informational / calm (pointing, neutral)
- White = directs attention to the tablet
- Yellow = thinking
- Red-orange = confusion / error

The LED is a *redundant* channel — the speech alone carries the answer — but it makes the interaction feel more responsive and helps participants distinguish *"the robot is processing"* from *"the robot is talking"*.

\newpage

### 13.4 `omnillm/robotics/whisper_stt.py` — Speech-to-Text

#### At a Glance

`WhisperSTT` is a thin wrapper around two STT backends:

| Backend | Library | When to use |
|---|---|---|
| `local` | `openai-whisper` (the original Whisper pip package) | Default. Privacy-preserving, no cost, runs offline. |
| `api` | `openai` SDK | Only if you set `WHISPER_BACKEND=api` and provide an OpenAI key. Faster on weak laptops; ships your audio to the cloud. |

The class accepts WAV bytes (or a path-like object) and returns the transcribed string plus an estimated confidence. Used by:

- The agent graph's `transcribe_audio` node (when called via `/interact` with `audio` in the body).
- The Flask `/transcribe` endpoint (Whisper-only, no LLM call).

#### Why Whisper-base by Default?

`WhisperSTT(backend="local", model_size="base")` is the default. `base` is the smallest non-trivial Whisper model — about 74M parameters, ~140 MB download, runs in ~700ms per 5-second utterance on CPU. We picked it over `tiny` (39M, 200ms, noticeably worse on accents) and over `small`/`medium`/`large` (slower, marginally better).

The pilot showed that `base` correctly transcribes the canonical 4 prompts (English + Italian) with 100% accuracy. For deployment with more participant accents the model size can be bumped via `model_size="small"`.

#### Why Local, Not API?

Discussed in Chapter 8. Briefly:

1. **GDPR.** Participant audio never leaves the lab laptop.
2. **Latency.** Local Whisper-base = ~700ms; cloud API = ~1.5s + network jitter.
3. **Cost.** Free.

The tradeoff: Whisper-base is weaker on heavy accents than Whisper-large or the cloud API. For the experimental study, the experimenter's role is to ask the participant to re-state if Whisper misfires — and the misfire rate is constant across conditions (it has no effect on the condition-level outcome).

\newpage

## Chapter 14 — Server & NAOqi Bridge

> *Three files between them are the entire HTTP surface area of OmniLLM. Two of them run in Python 2.7 (`naoqi_client.py` and `naoqi_bridge_server.py`); one runs in Python 3.11+ (`app.py`). They never share a process. They only share JSON.*

\newpage

### 14.1 `omnillm/server/app.py` — The Flask AI Server

#### At a Glance

`app.py` is the Python 3.11+ Flask server. It exposes six HTTP endpoints; it loads the gateway, RAG pipeline, and LangGraph at startup; and it serves as the single integration point that the Python 2.7 NAOqi processes talk to.

#### Endpoints

| Method | Path | Purpose | Used by |
|---|---|---|---|
| `GET` | `/health` | Liveness probe. Returns `{"status": "ok", "version": "0.1.0"}`. | Anything wanting to know if the server is up |
| `GET` | `/status` | Server configuration dump: default model, RAG state, KB path, available models, LangGraph availability | Diagnostic tools, the README setup test |
| `POST` | `/transcribe` | Whisper STT only. Body: `{"audio": "<base64 WAV>"}`. Returns text + detected language. | Test scripts; sanity-checking Whisper without the full pipeline |
| `POST` | `/interact` | **The main endpoint.** Body: `{"audio" or "text", "participant_id", "session_id", "condition", "rag_enabled"}`. Returns the `RobotAction` JSON. | `naoqi_client.py`, `run_subject_experiment.py`, curl, anything |
| `POST` | `/evaluate` | Submit a questionnaire score. Body: `{"session_id", "participant_id", "condition", "scores": {...}}`. Writes to ExperimentLogger. | Future digital questionnaire UI (currently paper-based) |
| `GET` | `/export` | Returns all logged interaction records as JSON for off-line analysis | The analysis Jupyter notebook (Chapter 30) |

#### The `/interact` Handler — Where Everything Connects

Look at lines 223–312 of [omnillm/server/app.py](../omnillm/server/app.py). The flow is:

1. Parse JSON body. Extract `utterance`, `audio_b64`, `participant_id`, `session_id`, `condition`, `rag_enabled`.
2. Decode the base64 audio if present.
3. Resolve the per-condition model from `CONDITION_CONFIGS[condition].model_id` and *inject it into the graph state*. (This is the May 2026 fix discussed in Chapter 12.)
4. Try to invoke the LangGraph (`graph.ainvoke(state)`). If it succeeds AND `action.speech` is non-empty, return the action.
5. If the graph returns empty speech OR raises an exception, **fall back to `_fallback_interact()`** — a tiny synchronous handler that calls `gateway.query()` directly and assembles a minimal `RobotAction`.

The fallback path is important: it means the server *always* responds with something, even if LangGraph or RAG temporarily breaks. The fallback's metadata field carries `"path": "fallback"` so downstream analysis can flag which interactions used it.

#### The Lazy LangGraph Import

```python
def _get_graph():
    nonlocal _graph
    if _graph is None:
        try:
            from omnillm.hri.agent_graph import build_hri_graph
            _graph = build_hri_graph(gateway=gateway, rag=rag, logger=exp_logger, default_model=_default_model)
        except ImportError:
            logger.warning("LangGraph not installed — falling back to direct gateway.")
    return _graph
```

LangGraph is an optional install (`pip install omnillm[hri]`). If it's not installed, the server still boots; it just falls back to the direct-gateway path for every interaction. This is useful for very minimal deployments where only the `/transcribe` and `/health` endpoints are needed.

#### The CORS-and-Host Decision

The server's `--host` defaults to `0.0.0.0` so Pepper (on the LAN) can reach it. CORS is not enabled — the API is meant to be called from same-LAN processes, not browsers. If a future tablet-based participant UI needs to call `/interact` from a browser, add `flask-cors` and a strict allowlist.

#### Why Flask and Not FastAPI?

FastAPI would arguably be the modern choice (built-in async, automatic OpenAPI docs). We chose Flask because:

1. **Smaller dependency tree.** Flask + Jinja vs FastAPI + Pydantic + Starlette + uvicorn — three vs ten transitive packages.
2. **Sync handlers compose easily with async work.** Our `_run_async` helper creates a one-shot event loop per request, which is a clean pattern in Flask. FastAPI's async handlers would mostly be calling `asyncio.gather()` over LiteLLM calls — fine, but no win for us at this scale.
3. **Long-standing ecosystem.** Flask + Gunicorn for production has been a stable combination since 2014; we will not be surprised by a behaviour change.

\newpage

### 14.2 `omnillm/server/naoqi_bridge_server.py` — Python 2.7's Side of Topology 2

#### At a Glance

`naoqi_bridge_server.py` is a **stdlib-only HTTP server** that runs in Python 2.7 near Pepper. It accepts JSON action commands from the Python 3 `PepperBridge` and translates them to NAOqi RPCs. Stdlib-only because installing modern pip packages on Python 2.7 is now flaky and often fails on Windows; the file uses `BaseHTTPServer.HTTPServer` and `urllib2` and nothing else.

#### Endpoints It Exposes

| Method | Path | Body | Returns |
|---|---|---|---|
| `GET` | `/ping` | — | `{"ok": true, "naoqi": true, "simulation": false, "robot_ip": "...", "robot_port": ...}` |
| `POST` | `/action` | `RobotAction`-like dict | `{"ok": true, "executed": {...}, "errors": {...}}` |
| `POST` | `/audio/record` | `{"duration_seconds": 5, "sample_rate": 16000, "channels": [0,0,1,0]}` | `{"ok": true, "audio_b64": "..."}` |
| `GET` | `/sensors` | — | Touch sensors + face detection state + battery |
| `POST` | `/tracker/start` | `{"target": "Face"}` | Starts ALTracker face-follow |
| `POST` | `/tracker/stop` | — | Stops face tracking |
| `POST` | `/disconnect` | — | Calls `motion.rest()` and shuts down cleanly |

#### The NaoqiFacade Class

Inside the bridge server is a single `NaoqiFacade` object that wraps the NAOqi proxies (`ALAnimatedSpeech`, `ALMotion`, `ALBehaviorManager`, `ALLeds`, `ALAudioRecorder`, `ALTracker`, `ALMemory`). The facade pattern means the HTTP handler functions don't import NAOqi directly — they call `facade.say(text)`, `facade.gesture(name)`, `facade.record_audio(...)`, etc.

This indirection is what lets the bridge server fall back to **simulation mode** when NAOqi can't be reached. In simulation mode, every `facade.*` call is a no-op that logs to stdout. The `/ping` endpoint returns `simulation: true` so the Python 3 client knows.

#### The Windows-11 Loopback Bug Workaround

When connecting to Choregraphe's virtual robot on Windows 11, NAOqi 2.5's `ALBroker` constructor must be told to listen on `127.0.0.1` *explicitly*, otherwise it tries to bind to `0.0.0.0` and fails silently. The fix:

```python
broker = ALBroker("OmniLLMBroker",
                  "127.0.0.1",        # NB: explicit, not "0.0.0.0"
                  0,                  # let OS pick an ephemeral port
                  robot_ip, robot_port)
```

Real Pepper (running NAOqi natively on Linux) does not have this bug. The bridge server detects whether it's connecting to a virtual or real robot via the `--robot-ip` flag and applies the workaround only when `robot_ip == "127.0.0.1"`.

#### How the AI Server Drives It

```python
# Python 3 LangGraph node
from omnillm.robotics import make_pepper_bridge
bridge = await make_pepper_bridge(robot_ip="127.0.0.1", bridge_port=6000)
await bridge.execute_action(RobotAction(
    speech="Hello! I am Pepper.",
    gesture="wave",
    emotion_led="#00FF88",
))
```

Internally this becomes:

```
POST http://127.0.0.1:6000/action
{
  "speech": "Hello! I am Pepper.",
  "gesture": "wave",
  "emotion_led": "#00FF88",
  "movement": null,
  "tablet_url": null,
  "metadata": {}
}
```

The bridge server's handler:

```python
def do_POST(self):
    if self.path == "/action":
        payload = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
        result = self.facade.execute_action(payload)
        self._send_json(200, result)
```

`facade.execute_action()` runs (in parallel where safe) all four sub-actions: `ALAnimatedSpeech.say(speech)`, `ALMotion.runBehavior(gesture)`, `ALLeds.fadeRGB(...)`, `ALTabletService.showWebview(tablet_url)`. Each is wrapped in a try/except; the result dict reports per-sub-action success/failure so the Python 3 caller can decide what to do.

#### Why Stdlib HTTP, Not Flask?

Two reasons:

1. **Python 2.7 + Flask + Windows = unhappy.** Modern Flask (>= 2.0) drops Python 2.7 entirely. The last Flask version that supports 2.7 (Flask 1.1) requires Werkzeug 1.0 which requires `click<8` which is unmaintained. Stdlib `BaseHTTPServer` works forever.
2. **Tiny surface area.** The bridge has six endpoints. Hand-coding the dispatcher is 30 lines.

\newpage

### 14.3 `omnillm/server/naoqi_client.py` — Python 2.7's Conversation Loop (Topology 1)

#### At a Glance

`naoqi_client.py` is the alternative Python 2.7 driver — the one used in Topology 1 ("Pepper polls AI server"). It runs in a loop, captures input, sends to the AI server, and enacts the response. It supports **three trigger modes** (`text`, `touch`, `vad`) selected via `--trigger`.

#### The Three Trigger Modes

| Trigger | How a turn starts | Audio source | Works on virtual Pepper? |
|---|---|---|---|
| `text` | Type a line + Enter at the terminal. Empty line quits. | None (text→TTS) | ✅ Yes |
| `touch` | Touch Pepper's front-head sensor. Records `--record-seconds` (default 5) seconds. | `ALAudioRecorder` | ❌ No (virtual has no mic) |
| `vad` | Continuous capture. When energy threshold is exceeded, recording begins; when energy drops, recording ends. | `ALAudioDevice` | ❌ No |

The three modes share the same downstream flow:

```
[trigger fires]
   ↓
[capture input: audio bytes OR typed text]
   ↓
POST /interact with audio (base64) or text + (participant, session, condition, rag_enabled)
   ↓
[receive RobotAction JSON]
   ↓
ALAnimatedSpeech.say(action["speech"])
ALMotion.runBehavior(action["gesture"])
ALLeds.fadeRGB("FaceLeds", action["emotion_led"], 0.3)
   ↓
[loop]
```

#### Face Tracking via `--track-face`

When `--track-face` is passed, the client starts `ALTracker` with the `Face` target at startup. Pepper's head will now turn to follow detected human faces during the entire session, regardless of which trigger fires conversational turns. This is the **first-class** face-tracking integration — Section 13.2 of the experimental protocol requires it.

```cmd
C:\Python27\python.exe omnillm\server\naoqi_client.py ^
    --robot-ip 192.168.1.42 ^
    --trigger touch ^
    --record-seconds 5 ^
    --condition C ^
    --track-face
```

#### Choice Matrix for the Study

For the N=15 study at DIBRIS, the recommended trigger is **`touch`**:

- Pure-text trigger feels artificial — the participant types instead of speaking to the robot.
- VAD trigger is sensitive to ambient lab noise (HVAC, students passing, other conversations) and prone to triggering on noise. The pilot found false-positive triggers averaging ~1.2 per minute in the DIBRIS open-plan area.
- Touch trigger has a clear, intentional start (the participant touches Pepper's head), a fixed-duration capture (5 seconds), and a clear end. It is the most reproducible mode across participants.

For **demos** and **dry runs** before the study, `text` mode is the right choice — it works on virtual Pepper and lets the experimenter test the dialogue without speaking aloud in a public space.

#### How `naoqi_client.py` Handles Errors

If `/interact` returns an error or the response has empty `speech`, the client uses a fixed apology line:

```python
SAFE_SPEECH_FALLBACK = (
    "I'm sorry, I didn't quite catch that. Could you say it again?"
)
```

This is what the participant hears if Whisper failed to transcribe, or if all LLM backends were offline, or if the network broke. **Silence is the worst outcome**; a polite "try again" is the second-worst-but-acceptable outcome. The experimenter logs every fallback for off-line analysis.

\newpage

## Chapter 15 — Utilities

> *Four small files in `omnillm/utils/` between them implement the entire data-collection pipeline for the experimental study. They are also the easiest files to read in the project.*

\newpage

### 15.1 `omnillm/utils/experiment_logger.py` — The Central Dataset

#### At a Glance

`ExperimentLogger` is the **single point of truth** for what happened during a study. It exposes one method, `log_interaction(...)`, that appends one `InteractionRecord` to:

- An in-memory `self.records` list (queryable via `/export`)
- A JSON-Lines file on disk (`results/interactions_<date>.jsonl`)

Plus a `to_csv()` method that produces the canonical flat CSV for analysis.

#### The `InteractionRecord` Dataclass

Every field that gets logged for every interaction:

| Field | Type | Source |
|---|---|---|
| `session_id` | str | Passed in `/interact` body |
| `participant_id` | str | Passed in `/interact` body |
| `condition` | str | `"A"`–`"E"` |
| `task_type` | str | Output of HRITaskClassifier |
| `utterance` | str | Whisper output (or typed text) |
| `response` | str | LLM output (the `speech` field in `RobotAction`) |
| `model_id` | str | Which LLM actually produced the response |
| `latency_ms` | float | End-to-end (excluding Pepper's TTS playback) |
| `input_tokens` | int | Prompt tokens |
| `output_tokens` | int | Completion tokens |
| `cost_usd` | float | Computed from the registry |
| `rag_enabled` | bool | Was RAG active for this interaction? |
| `rag_faithfulness` | float | LLM-as-judge score (-1.0 = not scored) |
| `rag_chunk_count` | int | How many chunks were retrieved |
| `judge_score` | float | Future: post-hoc LLM-as-judge quality |
| `language` | str | Detected language |
| `gesture_used` | str | What Pepper actually did |
| `task_success` | bool | Set by the experimenter post-hoc (default None) |
| `timestamp` | str | ISO 8601, UTC |
| `notes` | str | Free-form (e.g. JSON-encoded questionnaire scores) |

#### Why JSON-Lines, Not One Big JSON?

JSON-Lines (one JSON object per line, no outer array) is append-only safe. If the server crashes mid-session, you don't lose the partial data. With a single big JSON, you would have to either rewrite the whole file on every append (slow + corruption-prone) or accept that a crash loses everything since the last save.

#### CSV Export Schema

```
session_id, participant_id, condition, task_type, utterance, response,
model_id, latency_ms, input_tokens, output_tokens, cost_usd,
rag_enabled, rag_faithfulness, judge_score, task_success, language,
gesture_used, timestamp, notes
```

This is the shape the pandas analysis in Chapter 30 consumes. Examples are in `results/subject_run_P000_*.csv`.

\newpage

### 15.2 `omnillm/utils/questionnaire.py` — Likert, Godspeed, Pairwise, Observer

#### At a Glance

Four dataclasses cover the full post-session questionnaire instrument:

| Dataclass | Items | Used for |
|---|---|---|
| `InteractionQuestionnaire` | 5 Likert items (accuracy, naturalness, trust, gesture, speed) on 1–7 | Per-condition rating, the primary outcome |
| `GodspeedResponse` | 5 subscale mean scores (anthropomorphism, animacy, likeability, perceived_intelligence, perceived_safety) on 1–5 | Optional secondary outcome; comparability with HRI literature (Bartneck et al. 2009) |
| `PairwisePreference` | Two conditions + which preferred + reasoning | Feeds the ELO scorer to build the *embodied_hri* leaderboard |
| `ObserverRating` | Gesture-sync quality, task_completed, breakdown_count, notes | Filled by the experimenter live during the session |

#### `QuestionnaireCollector` — Aggregation + Export

The collector holds lists of all four record types and offers:

- `add_interaction_response(q)`, `add_godspeed(gs)`, `add_pairwise_preference(p)`, `add_observer_rating(obs)`
- `summary_by_condition()` — mean Likert per condition, ready for the thesis tables
- `pairwise_win_rates()` — pairwise win rates for the ELO update
- `save(path)` — full JSON dump
- `to_csv(path)` — interaction-questionnaire-only CSV

#### Recommended Delivery for the Study

(I promised in the preface to answer this in the book.) **The author's recommendation is a hybrid:**

1. **Paper questionnaires** for the 5 Likert items + Godspeed + pairwise preference + open-ended comments. Familiar; doesn't introduce a second screen; participant cannot accidentally edit prior answers; ethics-cleared trivially.
2. **Digital observer logging.** The experimenter sits at the laptop and POSTs `ObserverRating` records to `/evaluate` live during the session. Faster than handwriting; captures timestamps automatically.
3. **Post-session digitisation.** After each session, the experimenter types the paper Likert scores into a short Python script that calls `collector.add_interaction_response(...)` and `collector.save(...)`. ~3 minutes per participant. The paper original is kept in a binder as ground truth.

This balances: minimal participant-facing tech (paper), maximum experimenter efficiency (digital), and zero data loss (paper backup).

#### Validation Note

`InteractionQuestionnaire.__post_init__` enforces 1 ≤ score ≤ 7 for every Likert item and raises `ValueError` otherwise. This catches the most common digitisation typo (entering 0 or 8) at insertion time rather than during analysis.

\newpage

### 15.3 `omnillm/utils/cost_tracker.py` — Per-Model USD Spend

#### At a Glance

`CostTracker` reads all logged `InteractionRecord`s, groups by `model_id`, and computes:

- Total spend per model
- Number of interactions per model
- Average cost per interaction per model
- Cumulative spend across all models
- Spend per condition

Output is the `omnillm costs` CLI command, which prints a sorted table. Useful to flag a runaway model mid-experiment.

#### Why Compute From the Log, Not Real-Time?

Because every interaction already writes its `cost_usd` to the log via the gateway's per-call cost calculation. There's no need for a separate real-time counter; we just `pandas.read_json()` the log on demand and group.

\newpage

### 15.4 `omnillm/utils/export.py` — JSON ↔ CSV ↔ Markdown

#### At a Glance

`export.py` is a small format converter that the `omnillm export` CLI calls. Three output formats:

- `--format csv` → flat CSV, ready for pandas / Excel
- `--format markdown` → rendered table, ready to paste into the thesis
- `--format json` → identity copy (mostly for testing)

Used during analysis to produce the leaderboard tables in `book2/13_part5_experiments.md` and in the thesis itself.

\newpage

## Chapter 16 — The Python 2.7 ↔ Python 3.x Bridge Problem (and Three Different Solutions to It)

> *This chapter is the most architecture-defining single problem in OmniLLM. It is also the most reusable lesson — every project that integrates a modern AI stack into legacy hardware faces some version of this.*

### At a Glance

NAOqi's official Python SDK is locked to Python 2.7. The modern AI stack we want to use (LangGraph, LiteLLM, ChromaDB, transformers, etc.) requires Python 3.10+ and is syntactically invalid on Python 2.7. The two cannot coexist in a single process. OmniLLM solves this with three different cross-version bridges, each appropriate to a different scenario.

### Solution 1 — HTTP Server in Python 3, Polling Client in Python 2.7 (Topology 1)

The original solution. `omnillm/server/app.py` (Python 3) listens on `:5000`. `omnillm/server/naoqi_client.py` (Python 2.7) drives Pepper's I/O and POSTs to the server. The two processes never share memory; the JSON over HTTP is the entire contract.

```
+--------------------+       HTTP        +-----------------+
| naoqi_client.py    |   POST /interact  | app.py          |
| (Python 2.7)       | ----------------> | (Python 3.11+)  |
|                    | <---------------- |                 |
| ALAudioDevice      |   RobotAction     | LangGraph       |
| ALAnimatedSpeech   |                   | RAG, LiteLLM    |
| ALMotion           |                   |                 |
+--------------------+                   +-----------------+
```

**When to use:** quick demos, single-question scripts, anything where Pepper is the conversational initiator.

### Solution 2 — HTTP Server in Python 2.7, Async Client in Python 3 (Topology 2)

The May 2026 addition. `omnillm/server/naoqi_bridge_server.py` (Python 2.7) listens on `:6000`. The Python 3 `PepperBridge` is an aiohttp client of that bridge. The AI stack now initiates conversation; Pepper is a passive actuator.

```
+--------------------+       HTTP        +--------------------+
| AI Layer           |    POST /action   | naoqi_bridge_      |
| (Python 3.11+,     | ----------------> | server.py          |
|  LangGraph etc.)   | <---------------- | (Python 2.7)       |
|                    |     ok / error    |                    |
| PepperBridge       |                   | NaoqiFacade        |
| (aiohttp)          |                   | ALAnimatedSpeech   |
+--------------------+                   +--------------------+
```

**When to use:** the live experimental study (`run_subject_experiment.py` initiates and drives), and any future scenario where the agent graph wants to issue *multiple* commands to the robot during one cognitive step (e.g. "speak the first sentence while computing the second").

### Solution 3 — In-Process Stub (No Robot Anywhere)

The simplest solution. `PepperBridge` falls back to *stub mode* if neither bridge nor real NAOqi is reachable. `execute_action()` prints to stdout and returns success. The entire pipeline runs in CI, in unit tests, on a beach without internet.

**When to use:** all 289 pytest tests; CI; developing the AI Layer offline.

### Why Three Solutions and Not One Universal One?

Each solution optimises a different axis:

| Solution | Optimises | Cost |
|---|---|---|
| Topology 1 | Simple demos, robot-initiated dialogue | AI Layer cannot drive robot mid-reasoning |
| Topology 2 | AI-initiated dialogue, streaming behaviours, study reproducibility | Two PowerShell terminals required |
| Stub | Zero-robot development & CI | No real robot behaviour, obviously |

A single "universal" bridge would have to optimise everything — which means optimising nothing. Three small solutions composed cleanly is better than one big one fighting itself.

### A General Pattern for Legacy-Hardware AI Integration

The pattern that emerges from OmniLLM generalises:

1. **The legacy boundary is HTTP-and-JSON.** Anything that can speak HTTP can speak it. Python 2.7 can. ROS can. C++ can. An old Java service can.
2. **The legacy side runs only its SDK and a tiny HTTP server.** Don't add a single pip-installable dependency that wasn't in the 2010s ecosystem.
3. **The modern side runs everything else.** Modern Python, modern PyTorch, modern Anthropic SDK.
4. **Every interaction crosses the boundary exactly once.** Multi-hop crossings (modern→legacy→modern→legacy) make every error 4× harder to debug.
5. **The boundary is the canonical schema.** The `RobotAction` JSON is documented in `omnillm/robotics/bridge.py`. Any version of either side that obeys it is interoperable.

This is the deployment pattern that the author expects to recommend for the next decade of "modern AI in legacy robot" integrations — because robot middleware moves *much* slower than AI library churn.

\newpage
