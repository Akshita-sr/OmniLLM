\newpage

# PART XI — EXTENDED BEGINNER MATERIAL

> This part is for the **beginner / intermediate** reader. It assumes
> you have read Parts I-III but want **deeper** explanations. Four
> chapters expand on areas that beginners typically struggle with:
>
> - **Chapter 56** walks one user question through every Python line.
> - **Chapter 57** is a much larger glossary of the AI stack with the
>   "why we chose this" reasoning.
> - **Chapter 58** is a Choregraphe-only walkthrough — you can do this
>   without a real Pepper.
> - **Chapter 59** is a complete pretend experimental session — what
>   commands to type, what the JSON looks like, what to enter into
>   the questionnaire.
> - **Chapter 60** is the future-work / improvement plan.

\newpage

## Chapter 56 — "Reading the Code": A Single Question's Journey, Line by Line

> **AT A GLANCE.** Take one user input — *"Where is Room 305?"* — and
> trace it through every Python function that touches it. If you can
> read this chapter top to bottom and recognise every step, you
> understand OmniLLM.

### 56.1  The Scenario

You are running:

```bash
# Terminal 1
python -m omnillm.server.app

# Terminal 2 (drives the AI server with curl)
curl -X POST http://localhost:5000/interact \
  -H "Content-Type: application/json" \
  -d '{"text": "Where is Room 305?",
       "participant_id": "DEMO",
       "session_id": "demo-1",
       "condition": "C",
       "rag_enabled": true}'
```

What happens between the curl and the JSON response?

### 56.2  Stage 1 — Flask Receives the Request

**File: `omnillm/server/app.py`, function `interact()`**

Flask matches `POST /interact` to a Python function. The body is
parsed from JSON into a dict:

```python
@app.route("/interact", methods=["POST"])
def interact():
    data = request.get_json(force=True) or {}
    utterance = data.get("text", "")          # "Where is Room 305?"
    audio_b64 = data.get("audio", "")         # "" (text-only)
    participant_id = data.get("participant_id", "unknown")
    session_id = data.get("session_id", "")
    condition = data.get("condition", "A")
    rag_enabled = bool(data.get("rag_enabled", True) and rag is not None)
```

**What you see in Python you may not recognise:**

- `@app.route(...)` is a **decorator**. It wraps the function below it
  with Flask's URL routing logic. The function is still callable
  directly, but Flask also knows "if a `POST /interact` comes in,
  call `interact`".
- `data.get("text", "")` returns `data["text"]` if it exists,
  otherwise `""`. This is **safer than `data["text"]`** because the
  latter raises `KeyError` if the field is missing.

### 56.3  Stage 2 — Hand Off to the LangGraph Pipeline

**File: `omnillm/server/app.py`, function `interact()` (continued)**

```python
audio_bytes = base64.b64decode(audio_b64) if audio_b64 else b""

graph = _get_graph()       # lazily compile LangGraph the first time
if graph is not None:
    state = {
        "utterance": utterance,
        "audio_bytes": audio_bytes,
        "participant_id": participant_id,
        "session_id": session_id,
        "condition": condition,
        "rag_enabled": rag_enabled,
        "model_id": _default_model,
    }
    result = _run_async(graph.ainvoke(state))
    return jsonify(result.get("robot_action",
                              {"speech": result.get("response_text", "")}))
```

**What's happening:**

- `_get_graph()` returns a compiled LangGraph DAG. The first call takes
  about 10 seconds (imports + compile); subsequent calls are instant.
- `graph.ainvoke(state)` runs the **entire graph asynchronously**
  starting from the `state` dict. Each node reads keys it cares about
  and writes back updates.
- `_run_async(coro)` is a tiny helper that creates a fresh event loop
  per request — needed because Flask is synchronous but LangGraph is
  asynchronous.

### 56.4  Stage 3 — Inside the Graph (Node by Node)

**File: `omnillm/hri/agent_graph.py`, function `build_hri_graph()`**

Compilation builds this graph:

```
START
  v
transcribe_audio
  v
detect_language
  v
classify_task
  v  (conditional)
  +-> rag           (T1, RAG on)
  +-> nav_rag       (T2, RAG on)
  +-> direct_llm    (T3 or condition E)
  +-> multilingual_llm  (T4)
  v
smart_router
  v
generate_action_plan
  v
log_interaction
  v
END
```

#### 56.4.1  Node 1 — `transcribe_audio`

```python
async def transcribe_audio(state: dict) -> dict:
    audio = state.get("audio_bytes", b"")
    if not audio:
        # text-only mode — utterance already set
        return {"_start_time": time.monotonic()}
    # ...else call Whisper STT (skipped here)
```

Because we passed `text="Where is Room 305?"` (no audio), `audio` is
empty, so this node just records the start time and passes through.

#### 56.4.2  Node 2 — `detect_language`

```python
async def detect_language(state: dict) -> dict:
    utterance = state.get("utterance", "")
    detector = LanguageDetector()
    result = detector.detect(utterance)
    return {"detected_language": result.language_code}
```

The detector inspects the script and word frequencies and returns
`"en"`. Almost any English text is identified in under 10 ms by Tier 1
(Unicode script check) — no LLM call required.

#### 56.4.3  Node 3 — `classify_task`

```python
async def classify_task(state: dict) -> dict:
    utterance = state.get("utterance", "")
    classifier = HRITaskClassifier()
    result = classifier.classify(utterance, detected_language="en")
    return {"task_type": result.task_type.value,
            "task_confidence": result.confidence}
```

The classifier hits the regex `\broom\s+\d+\b` ("Room 305") and the
keyword `where`. Score for **navigation** wins → returns
`{"task_type": "navigation", "task_confidence": 0.92}`.

#### 56.4.4  Conditional Edge — Pick the Branch

```python
def _route_by_task_type(state: dict) -> str:
    task_type = state.get("task_type", "info_retrieval")
    condition = state.get("condition", "A")
    rag_enabled = state.get("rag_enabled", True)
    if condition == "E":
        return "direct_llm"
    routing = {
        "info_retrieval":      "rag" if rag_enabled else "direct_llm",
        "navigation":          "nav_rag" if rag_enabled else "direct_llm",
        "social_conversation": "direct_llm",
        "multilingual":        "multilingual_llm",
    }
    return routing.get(task_type, "direct_llm")
```

`task_type="navigation"` and `rag_enabled=True` → return `"nav_rag"`.
LangGraph dispatches to the `nav_rag` node.

#### 56.4.5  Node 4 — `nav_rag` (RAG + Gesture Planner)

```python
async def run_nav_rag(state: dict) -> dict:
    utterance = state.get("utterance", "")
    rag_resp = await rag.query(utterance, model_id=state.get("model_id"))
    planner = GesturePlanner()
    gesture, led = planner.plan("navigation", rag_resp.answer)
    return {
        "rag_context":   "\n\n".join(f"[{c.source}]: {c.text}"
                                       for c in rag_resp.retrieved_chunks),
        "rag_chunks":    rag_resp.retrieved_chunks,
        "rag_faithfulness": rag_resp.faithfulness_score,
        "response_text": rag_resp.answer,
        "model_id":      rag_resp.model_id,
        "latency_ms":    rag_resp.latency_ms,
        "gesture":       gesture,
        "led_color":     led,
    }
```

What `rag.query()` does internally:

1. Convert "Where is Room 305?" into an embedding vector.
2. Search ChromaDB for the 4 most similar chunks.
3. Build an augmented prompt: `system + "Use only this context: ..." + user`.
4. Call `gateway.query(model_id, messages)` — this returns the answer.
5. (Optional) Score the answer's faithfulness with a judge LLM.

The result is something like:

```
"Room 305 is on the third floor of Building C. Take the elevator
on your left, then turn left at the corridor."
```

Then `planner.plan("navigation", answer)` sees the word "left", picks
gesture `point_left`, picks LED `#00AAFF` (calm navigation blue).

#### 56.4.6  Node 5 — `smart_router`

For `condition="C"`, the router fires:

```python
from omnillm.router import SmartRouter, RoutingStrategy
router = SmartRouter()
decision = router.route_for_hri_task(
    task_type="navigation",
    strategy=RoutingStrategy.TASK_TYPE,
)
target = decision.model_id     # e.g. "gemini-flash" per hri_task_routing
resp = await gateway.query(target, messages)
return {"response_text": resp.content, "model_id": resp.model_id, ...}
```

The router reads `config/models.yaml`'s `hri_task_routing.navigation`
and finds `gemini-flash` is the optimal model for navigation. It
re-asks the question with that model. The answer overrides what
`nav_rag` produced.

(For condition `A` or `B`, the smart_router node is a no-op — the
previous answer wins.)

#### 56.4.7  Node 6 — `generate_action_plan`

```python
async def generate_action_plan(state: dict) -> dict:
    return {
        "robot_action": {
            "speech":       state["response_text"],
            "gesture":      state["gesture"],
            "emotion_led":  state["led_color"],
            "metadata":     {"task_type": state["task_type"],
                              "model_id":  state["model_id"],
                              "rag_enabled": state["rag_enabled"]},
        }
    }
```

This is just packaging — the heavy work is done.

#### 56.4.8  Node 7 — `log_interaction`

```python
async def log_interaction(state: dict) -> dict:
    total_latency = (time.monotonic() - state["_start_time"]) * 1000
    logger.log_interaction(
        session_id=state.get("session_id", ""),
        participant_id=state.get("participant_id", ""),
        condition=state.get("condition", "A"),
        task_type=state.get("task_type"),
        utterance=state.get("utterance", ""),
        response=state.get("response_text", ""),
        model_id=state.get("model_id", ""),
        latency_ms=total_latency,
        ...
    )
    return {"latency_ms": total_latency}
```

The logger appends an `InteractionRecord` to the in-memory list
(written to disk at end of session via `logger.save()`).

### 56.5  Stage 4 — Flask Returns the JSON

Back in `app.py`:

```python
return jsonify(result.get("robot_action", ...))
```

The dict is serialised to JSON and returned with HTTP 200:

```json
{
  "speech": "Room 305 is on the third floor of Building C. Take the elevator on your left, then turn left at the corridor.",
  "gesture": "point_left",
  "emotion_led": "#00AAFF",
  "metadata": {
    "task_type": "navigation",
    "model_id":  "gemini-flash",
    "rag_enabled": true
  }
}
```

### 56.6  Stage 5 — What Pepper Does With It

If a real Pepper was at the other end, `naoqi_client.py` would:

```python
def _execute_action(self, action):
    speech    = action.get("speech", "")
    gesture   = action.get("gesture")
    led_color = action.get("emotion_led")
    if led_color: self._set_leds(led_color)
    if gesture and gesture in GESTURE_TO_BEHAVIOR:
        self._run_behavior_async(GESTURE_TO_BEHAVIOR[gesture])
    if speech: self._speak(speech)
```

- Eyes fade to `#00AAFF` over 300 ms.
- `ALBehaviorManager.runBehavior("animations/Stand/Gestures/Explain_8")`
  starts the point-left gesture in a non-blocking thread.
- `ALAnimatedSpeech.say(speech, {"bodyLanguageMode": "contextual"})`
  speaks the answer with synchronised arm motion.

### 56.7  The Whole Picture

That is one question, end-to-end. Sub-second latency (≈ 1.4 s typical),
all of it logged, every model swap configurable, every step
testable in isolation.

If you can find the code for each step in the repo without re-reading
this chapter, you understand OmniLLM.

\newpage

## Chapter 57 — AI-Stack and Frameworks — Expanded Glossary with Rationale

> **AT A GLANCE.** Every important tool OmniLLM depends on, with a
> "what it is", "why we picked it", "what we'd use otherwise", and
> "where to read more".

### 57.1  LiteLLM

**What it is.** A Python library that exposes 100+ LLM providers
behind one identical function call. You pass `model="openai/gpt-4o"`
or `model="anthropic/claude-haiku"` or `model="ollama/llama3:8b"` —
the call is the same.

**Why we picked it.** Without it, OmniLLM would need separate
adapter code for each provider, each with its own pagination,
error-handling, and token-counting quirks. LiteLLM normalises this
in one library that's actively maintained.

**Alternatives.** Direct provider SDKs (`openai`, `anthropic`,
`google-generativeai`) — more control, more code. `aisuite`,
`openrouter` — similar idea, smaller communities.

**Where used.** Imported by `omnillm/gateway.py`.

### 57.2  LangGraph

**What it is.** A library on top of LangChain for building **stateful
agent graphs** — directed graphs whose nodes are async functions
sharing a single state dict, with conditional edges between them.

**Why we picked it.** OmniLLM's HRI pipeline is genuinely a graph
(transcribe → detect → classify → branch → answer → plan → log)
with conditional routing. Writing this as one 200-line `async`
function with `if/elif` branches would work but be untestable,
unreadable, and impossible to visualise. LangGraph gives us named
nodes, typed state, and `add_conditional_edges`.

**Alternatives.** Plain async functions (more verbose, no diagram).
LangChain's deprecated `AgentExecutor` (limited routing). Custom DAG
libraries — most don't handle async well.

**Where used.** `omnillm/hri/agent_graph.py`.

### 57.3  ChromaDB

**What it is.** A pure-Python embedded vector database. Stores
embeddings + their source text + metadata. Supports cosine similarity
search.

**Why we picked it.** Embedded (no separate process), persistent
across restarts, zero configuration, pip-installable. For a single
researcher with a < 10 k-document knowledge base, this is plenty.

**Alternatives.** **Qdrant**, **Weaviate**, **Pinecone** — heavier,
require running a server. **FAISS** — fast but lower-level, no
metadata. For OmniLLM's scale, ChromaDB is the sweet spot.

**Where used.** `omnillm/rag/pipeline.py`.

### 57.4  LangChain

**What it is.** A broader framework for LLM apps. OmniLLM uses
*only* its document loaders (`PyPDFLoader`, `CSVLoader`,
`TextLoader`) — not the larger Chain abstractions, which are
opinionated and easy to outgrow.

**Why we picked it.** The document loaders save dozens of lines per
file format. Tested by a large community.

**Alternatives.** Write your own loaders. For PDFs, `pypdf` directly.
For CSVs, `pandas`. We could do this — but LangChain's loaders
normalise the output (each chunk has `.page_content`, `.metadata`)
which makes the rest of the pipeline cleaner.

**Where used.** `omnillm/rag/pipeline.py`.

### 57.5  Sentence-Transformers

**What it is.** A Python library that turns text into embedding
vectors using small (~100 MB), fast, locally-runnable models.

**Why we picked it.** ChromaDB's default embedding is
`all-MiniLM-L6-v2` from sentence-transformers — fast (~5 ms per
short text on CPU), small, and free. No need to pay OpenAI for
embeddings during indexing.

**Alternatives.** OpenAI's `text-embedding-3-small` API —
higher-quality embeddings, $0.02 per million tokens, requires
internet. For a small lab KB, the quality difference doesn't justify
the cost.

**Where used.** Indirectly via ChromaDB.

### 57.6  OpenAI Whisper

**What it is.** A speech-to-text model trained by OpenAI on 680 k
hours of multilingual audio. Available as a downloadable model
(`pip install openai-whisper`) or via the OpenAI API.

**Why we picked it.** Best-in-class accuracy at the
**multilingual** level, robust to noise, free if you run it locally.
Pepper's onboard `ALSpeechRecognition` is widely regarded as
unusable for open-domain speech.

**Alternatives.** **Vosk** (lighter, offline), **Google Speech**
(cloud), **Faster-Whisper** (a faster C++ port — recommended for
production but adds setup complexity). For a research prototype,
plain Whisper is fine.

**Where used.** `omnillm/robotics/whisper_stt.py`.

### 57.7  Asyncio

**What it is.** Python's standard library for **non-blocking I/O**.
`async def` declares a coroutine; `await` pauses it until an I/O
operation completes; `asyncio.gather(...)` runs many coroutines
concurrently.

**Why we picked it.** LLM calls are I/O-bound — most of the time is
spent waiting for the network. Asyncio lets us query 5 models in the
wall-clock time of the slowest one, not the sum.

**Alternatives.** Threading (more complex, GIL contention),
multiprocessing (overkill, slow startup). For pure-I/O work, asyncio
wins.

**Where used.** Throughout — `gateway.py`, `consensus.py`,
`evaluator.py`, `agent_graph.py`, `server/app.py`.

### 57.8  Flask

**What it is.** A minimalist Python web framework. Serves HTTP
endpoints with decorators (`@app.route`).

**Why we picked it.** Tiny, well-documented, easy to test, single
worker is the right concurrency model for one robot.

**Alternatives.** **FastAPI** (async-native, faster, more modern) —
genuinely better for high-throughput services. We didn't pick it
because Flask's simplicity matched the single-robot single-worker
use case, and the synchronous-to-async bridge (`_run_async`) is
easy to write. If you ever serve many robots simultaneously, switch
to FastAPI + uvicorn.

**Where used.** `omnillm/server/app.py`.

### 57.9  Click

**What it is.** A Python library for building command-line
interfaces with decorators (`@click.command`, `@click.option`).

**Why we picked it.** Better than `argparse` (less boilerplate),
supports nested command groups (`omnillm ask`, `omnillm evaluate`),
auto-generates `--help` text.

**Alternatives.** **Typer** (built on Click, uses type hints —
slightly nicer for greenfield projects), **argparse** (stdlib, more
verbose).

**Where used.** `omnillm/cli.py`.

### 57.10  Rich

**What it is.** A Python library for beautiful coloured terminal
output — tables, panels, progress bars, syntax-highlighted code.

**Why we picked it.** OmniLLM's CLI is a research dashboard. A
coloured table of model latencies is dramatically more readable
than `print(dict)`.

**Alternatives.** **tabulate** (tables only), plain `print()`
(grey, unreadable for long output).

**Where used.** `omnillm/cli.py`.

### 57.11  Ollama

**What it is.** A free local LLM runtime. `ollama serve` starts a
daemon on `localhost:11434`; `ollama pull llama3:8b` downloads a
model. Exposes an OpenAI-compatible HTTP API.

**Why we picked it.** Free, private, fast on a laptop with a GPU.
The "Condition B" baseline of the experiment depends on it.

**Alternatives.** **vLLM** (faster but heavier), **LM Studio**
(GUI), **GGUF + llama.cpp** (more control, more setup). Ollama is
the easiest for a research lab.

**Where used.** Via LiteLLM in `omnillm/gateway.py`. Models
registered in `config/models.yaml` with `provider: ollama`.

### 57.12  ReportLab + xhtml2pdf

**What it is.** Two pure-Python libraries that together produce PDFs
from HTML. xhtml2pdf orchestrates; ReportLab does the actual
rendering. We register DejaVu Sans + DejaVu Sans Mono with
ReportLab so Unicode glyphs render.

**Why we picked it.** No native dependencies (libgobject, Pango,
Cairo) — installable on Windows with pip alone. WeasyPrint produces
better output but requires GTK on Windows which the user couldn't
install.

**Alternatives.** **WeasyPrint** (best quality, needs GTK), **mPDF**
(PHP), **wkhtmltopdf** (Webkit, large binary), **LaTeX** (best
quality, huge install). xhtml2pdf is the lowest-friction choice.

**Where used.** `book/build_pdf.py`.

### 57.13  pytest + pytest-asyncio + pytest-mock

**What it is.** The Python testing trinity. pytest is the framework;
pytest-asyncio runs `async` test functions; pytest-mock provides the
`mocker` fixture.

**Why we picked it.** Standard in the Python ecosystem. The 278
tests in `tests/` run in ~5 s without a single real API call —
because pytest-mock fakes out the LLM calls.

**Where used.** `tests/`.

\newpage

## Chapter 58 — Choregraphe-Only Walkthrough (No Robot Needed)

> **AT A GLANCE.** You can develop and demo 90 % of OmniLLM without a
> physical robot. Choregraphe's virtual robot is enough. This chapter
> is the complete recipe.

### 58.1  Why This Path Exists

A real Pepper costs $20–30 k second-hand (and rising, since
production stopped). For development you only need to verify:

- The AI server returns sensible JSON.
- The JSON, when replayed against NAOqi, produces the expected speech
  + gesture + LED.

Choregraphe's virtual robot is sufficient for both.

### 58.2  Install Choregraphe 2.5

Choregraphe is shipped by SoftBank / Aldebaran. The download is on
the SoftBank developer portal (free account required); the version
that matches Pepper is **2.5.5.5** or **2.5.10/11**.

- Install at the default location:
  `C:\Program Files (x86)\Aldebaran\Choregraphe Suite 2.5\`.
- Launch — you should see the four-panel layout (Box Library,
  Flow Diagram, 3D Robot, Log Viewer).

### 58.3  Spin Up the Virtual Robot

1. Menu → **Connection → Connect to virtual robot**.
2. The 3D view fills with a virtual Pepper.
3. Right-click the robot in the 3D view → **Wake Up**. Stiffness
   turns on; Pepper holds upright.
4. The status bar shows `Connected to localhost:9559 (virtual)`.

### 58.4  Start OmniLLM

In a separate terminal:

```bash
cd C:\Users\akshi\OneDrive\Desktop\OmniLLM
.venv\Scripts\activate
python -m omnillm.server.app --model llama3-8b-local
# (or --model openai-gpt4o-mini if you have an API key)
```

In another terminal, query the server:

```bash
curl -X POST http://localhost:5000/interact ^
  -H "Content-Type: application/json" ^
  -d "{\"text\":\"Where is Room 305?\",\"participant_id\":\"DEMO\",\"condition\":\"B\"}"
```

Response:

```json
{
  "speech":     "Room 305 is on your left on the third floor.",
  "gesture":    "point_left",
  "emotion_led":"#00AAFF",
  "metadata":   {"task_type":"navigation","model_id":"llama3-8b-local"}
}
```

### 58.5  Replay the Action on the Virtual Robot

In Choregraphe, press `Alt+5` to open the Script Editor. Paste:

```python
# (replace with the values from your curl response)
speech    = "Room 305 is on your left on the third floor."
gesture   = "animations/Stand/Gestures/Explain_8"   # point_left
led_hex   = (0.0, 0.67, 1.0)   # #00AAFF

tts  = ALProxy("ALAnimatedSpeech", "localhost", 9559)
bm   = ALProxy("ALBehaviorManager", "localhost", 9559)
leds = ALProxy("ALLeds", "localhost", 9559)

leds.fadeRGB("FaceLeds", led_hex[0], led_hex[1], led_hex[2], 0.3)
bm.post.runBehavior(gesture)            # non-blocking
tts.say(speech, {"bodyLanguageMode": "contextual"})
```

You should see:

- The virtual Pepper's eyes turn blue (`#00AAFF`).
- Its left arm raises (the Explain_8 gesture).
- Your PC speakers play the speech.

This proves OmniLLM ↔ NAOqi end-to-end **without a real robot**.

### 58.6  Fully Automating Replay

A helper script that closes the loop — Choregraphe-side Python 2.7
client that polls the AI server like the real `naoqi_client.py`:

```python
# choregraphe_replay.py  -- run in Choregraphe Script Editor
import json, urllib2, time
from naoqi import ALProxy

SERVER = "http://localhost:5000/interact"
GESTURE_MAP = {
    "point_left":  "animations/Stand/Gestures/Explain_8",
    "point_right": "animations/Stand/Gestures/Explain_7",
    "wave":        "animations/Stand/Gestures/Hey_1",
    "nod":         "animations/Stand/Emotions/Positive/Enthusiastic_1",
    "think":      "animations/Stand/Emotions/Neutral/Thinking_1",
}

tts  = ALProxy("ALAnimatedSpeech", "localhost", 9559)
bm   = ALProxy("ALBehaviorManager", "localhost", 9559)
leds = ALProxy("ALLeds", "localhost", 9559)

def ask(text):
    payload = json.dumps({"text": text, "participant_id": "DEMO",
                          "session_id": "demo", "condition": "C",
                          "rag_enabled": True})
    req = urllib2.Request(SERVER, payload,
                          {"Content-Type": "application/json"})
    return json.loads(urllib2.urlopen(req).read())

def execute(action):
    led = action.get("emotion_led", "#44AAFF").lstrip("#")
    r, g, b = (int(led[i:i+2], 16) / 255.0 for i in (0,2,4))
    leds.fadeRGB("FaceLeds", r, g, b, 0.3)
    gname = action.get("gesture")
    if gname and gname in GESTURE_MAP:
        bm.post.runBehavior(GESTURE_MAP[gname])
    if action.get("speech"):
        tts.say(action["speech"], {"bodyLanguageMode": "contextual"})

# Demo loop -- four task types
for q in [
    "What time does the lab open?",
    "Where is Room 305?",
    "How are you today, Pepper?",
    "Bonjour Pepper, comment allez-vous?",
]:
    print(q)
    execute(ask(q))
    time.sleep(2)
```

Save this in Choregraphe's Script Editor and run it. The virtual
Pepper will speak, gesture and change LED colour for each of the
four questions, end-to-end through OmniLLM. **This is the
zero-hardware demo loop.**

### 58.7  What You Cannot Test Without a Real Robot

| Feature | Virtual works? | Why / Why not |
|---|---|---|
| `ALAnimatedSpeech` (speech + body language) | yes (PC speakers) | rendered |
| `ALMotion` (joints) | yes | rendered in 3D |
| `ALLeds` | yes | LED colour shows in 3D |
| `ALBehaviorManager` (pre-installed gestures) | yes | runs the animation |
| `ALAudioDevice` (microphone) | **no** | no virtual mic |
| `ALAudioRecorder` | **no** | no audio stream |
| `ALFaceDetection` | **no** | no camera |
| `ALTabletService` | partial | tablet view exists but limited |

The bottom line: anything *output* works on the virtual robot;
anything *input from the world* (audio, vision, touch) does not. So
you cannot run a full STT-driven session on the virtual robot. Use
the `--text` curl path instead.

\newpage

## Chapter 59 — A Complete First Experimental Session — Worked Example

> **AT A GLANCE.** A pretend participant P001 walks into your lab. We
> run them through all three conditions of one slot of the Latin
> square. Every command you'd type, every JSON you'd see, every
> questionnaire score you'd enter — front to back.

### 59.1  Before the Participant Arrives

```bash
# 0. Pre-flight check
cd C:\Users\akshi\OneDrive\Desktop\OmniLLM
.venv\Scripts\activate

omnillm models                      # all 19 models load
pytest tests/ -v 2>&1 | tail -3     # 278 tests pass

# 1. Make sure Pepper is awake (or virtual Choregraphe is connected)
C:\Python27\python.exe -c "from naoqi import ALProxy; ^
  ALProxy('ALMotion','192.168.1.100',9559).wakeUp()"

# 2. Start the AI server, this terminal
python -m omnillm.server.app --host 0.0.0.0 --port 5000

# expected log lines:
# INFO:omnillm.rag.pipeline:Indexed 12 chunks from lab_info.txt
# INFO:omnillm.rag.pipeline:Indexed 8  chunks from faq.txt
# INFO:omnillm.rag.pipeline:Knowledge base loaded -- 42 total chunks
#  * Running on all addresses (0.0.0.0)
#  * Running on http://127.0.0.1:5000
```

You also have a paper copy of:

- Consent form (two copies)
- The 5-item questionnaire (printed)
- A Latin-square sheet that says "P001: blocks A, C, E in that order"

### 59.2  Participant Arrives — Briefing (5 minutes)

> *"Thank you for joining. Today you'll talk with Pepper in three
> different modes. After each mode you'll fill in a short
> questionnaire. The whole session is about 30 minutes. You can stop
> at any time without giving a reason. There are no right or wrong
> answers — we're studying Pepper, not you. Please sign here..."*

Hand over the consent form. Note that P001 speaks English and French.

### 59.3  Block 1 — Condition A (GPT-4o-mini, RAG ON)

In a second terminal, launch the NAOqi client (or, in our virtual
demo, the `choregraphe_replay.py` from §58.6 — but pass the
participant ID and condition):

```bash
# (real Pepper)
C:\Python27\python.exe omnillm\server\naoqi_client.py ^
  --robot-ip 192.168.1.100 ^
  --server-ip 192.168.1.50 ^
  --participant P001 ^
  --condition A
```

Pepper says: *"Hello! I am Pepper, powered by OmniLLM. How can I help
you today?"*

You prompt the participant for each task in turn:

| Task | Your verbal cue to participant |
|---|---|
| T1 | *"Ask Pepper a factual question about the lab — like the WiFi password, or what time it opens."* |
| T2 | *"Ask Pepper to direct you somewhere — like Room 305 or the cafeteria."* |
| T3 | *"Have a casual chat with Pepper — say hello, ask how it is."* |
| T4 | *"You said you speak French — please ask any of those questions again in French."* |

P001 says: "What's the lab WiFi password?"

Server logs (truncated):

```
INFO:omnillm.server.app:[interact] participant=P001 condition=A task=info_retrieval
INFO:omnillm.rag.pipeline:Retrieved 4 chunks, top score 0.78
INFO:litellm:openai-gpt4o-mini  in=320  out=42  latency=987ms  cost=$0.0001
INFO:omnillm.utils.experiment_logger:Logged interaction len(records)=1
```

Pepper responds: *"The visitor WiFi is 'UniGuest' with password
'Welcome2026!'."*

After all four tasks for block A, hand over the **questionnaire**:

```
Condition (you write): A
Participant ID:        P001
Q1 The robot's answers were accurate           [ ] 1  [ ] 2  [ ] 3  [ ] 4  [ ] 5  [ ] 6  [ ] 7
Q2 The robot was natural to talk to            [ ] 1  [ ] 2  [ ] 3  [ ] 4  [ ] 5  [ ] 6  [ ] 7
Q3 I trust the information the robot gave me   [ ] 1  [ ] 2  [ ] 3  [ ] 4  [ ] 5  [ ] 6  [ ] 7
Q4 The robot's gestures were appropriate       [ ] 1  [ ] 2  [ ] 3  [ ] 4  [ ] 5  [ ] 6  [ ] 7
Q5 The robot responded quickly enough          [ ] 1  [ ] 2  [ ] 3  [ ] 4  [ ] 5  [ ] 6  [ ] 7
```

P001 ticks 6 / 5 / 6 / 5 / 7.

Save those into OmniLLM via the `/evaluate` endpoint:

```bash
curl -X POST http://localhost:5000/evaluate ^
  -H "Content-Type: application/json" ^
  -d "{\"session_id\":\"P001-A\",\"participant_id\":\"P001\",\"condition\":\"A\",\"scores\":{\"accuracy\":6,\"naturalness\":5,\"trust\":6,\"gesture_appropriateness\":5,\"response_speed\":7}}"
```

Or do it programmatically at the end (Section 59.7).

### 59.4  Block 2 — Condition C (Smart-Routed)

Kill the NAOqi client (`Ctrl+C`). Restart with `--condition C`:

```bash
C:\Python27\python.exe omnillm\server\naoqi_client.py ^
  --robot-ip 192.168.1.100 ^
  --server-ip 192.168.1.50 ^
  --participant P001 ^
  --condition C
```

Same four tasks. This time the smart router picks:

| Task | Picked model | Why (from `hri_task_routing` in `models.yaml`) |
|---|---|---|
| T1 Info Retrieval | openai-gpt4o-mini | accurate, cheap, RAG-friendly |
| T2 Navigation | gemini-flash | fast, strong spatial language |
| T3 Social Chat | claude-haiku | natural conversational tone |
| T4 Multilingual | gemini-flash | strong multilingual coverage |

P001 ticks the questionnaire: 6 / 6 / 6 / 6 / 6.

### 59.5  Block 3 — Condition E (RAG-OFF Control)

```bash
C:\Python27\python.exe omnillm\server\naoqi_client.py ^
  --robot-ip 192.168.1.100 ^
  --server-ip 192.168.1.50 ^
  --participant P001 ^
  --condition E
```

Same four tasks again. **The interesting moment** — P001 asks
"What's the WiFi password?" Without RAG, the LLM has never seen your
lab's WiFi password. It says something like *"I'm sorry, I don't have
that information."* That's the data point.

P001 ticks: 4 / 5 / 3 / 5 / 7. Notice the drop in **accuracy** and
**trust** vs. block A — exactly H3's prediction.

### 59.6  Pairwise Preference

> *"Which version of Pepper did you prefer overall? Why?"*

P001: "The second one was the most natural."

That maps to **Condition C wins over A and E**. Record it:

```bash
curl -X POST http://localhost:5000/evaluate ^
  -H "Content-Type: application/json" ^
  -d "{\"type\":\"pairwise\",\"session_id\":\"P001\",\"participant_id\":\"P001\",\"condition_a\":\"A\",\"condition_b\":\"C\",\"preferred\":\"C\"}"
```

(And similarly C > E.) These feed the ELO scorer's `embodied_hri`
category.

### 59.7  End of Session — Save Everything

```bash
# Dump all the logged interactions for the day
curl http://localhost:5000/export > results/P001_full.json

# (Inside the AI server REPL, or as a separate script)
python -c "
from omnillm.scorer import EloScorer
elo = EloScorer()
elo.record_match('condition-C', 'condition-A', 'model_a', category='embodied_hri')
elo.record_match('condition-C', 'condition-E', 'model_a', category='embodied_hri')
elo.save('results/elo.json')
print(elo.get_category_leaderboard('embodied_hri'))
"
```

### 59.8  What the JSON Logs Look Like

A typical `InteractionRecord` row in `results/P001_full.json`:

```json
{
  "timestamp": "2026-05-14T10:32:17.512Z",
  "session_id": "P001-A",
  "participant_id": "P001",
  "condition": "A",
  "task_type": "info_retrieval",
  "utterance": "What's the lab WiFi password?",
  "response":  "The visitor WiFi is 'UniGuest' with password 'Welcome2026!'.",
  "model_id":  "openai-gpt4o-mini",
  "latency_ms": 987.3,
  "input_tokens": 320,
  "output_tokens": 42,
  "cost_usd": 0.0001,
  "rag_enabled": true,
  "rag_faithfulness": 0.94,
  "rag_chunk_count": 4,
  "judge_score": 0.91,
  "task_success": true,
  "language": "en",
  "gesture_used": "nod"
}
```

After 20 participants × 3 conditions × 4 tasks, you have **240 such
rows** plus 100 questionnaire rows plus ~60 pairwise preferences.
That is the dataset.

### 59.9  Final Backup Step

```bash
# Copy results/ to a separate location at the end of every day
xcopy /E /Y results\ D:\thesis-backup\results-2026-05-14\
```

Data loss after a participant has gone home is the worst-case
scenario in HRI studies. Don't be the person it happens to.

\newpage

## Chapter 60 — Future Scope and Improvement Opportunities

> **AT A GLANCE.** Where OmniLLM goes next, in priority order. Some
> are weekend tasks; some are PhD theses in themselves.

### 60.1  Near-Term (Weekend Tasks)

**Real audio capture in `naoqi_client.py`.** The current
`_record_audio()` is a 5-second placeholder. Replace with
`ALAudioRecorder` (simpler, +file transfer) or `processRemote`
callback (real-time, more code). Critical before actual user studies.

**Counterbalancing generator.** Add a `LatinSquareGenerator` to
`omnillm/hri/experiment.py` so the experimenter doesn't manage a
CSV by hand.

**A `/admin` dashboard.** A small Flask page showing live: model
costs, recent interactions, current ELO, participant progress.

**Realtime API support.** Both OpenAI's Realtime API and Google
Gemini Live can do speech-to-speech without an explicit STT step.
For Pepper, this would collapse the audio path to a single
low-latency loop, dropping ~400 ms of latency.

### 60.2  Mid-Term (Sprint Tasks)

**Streaming TTS responses.** Pepper's TTS could start speaking as
soon as the first sentence is generated, rather than waiting for the
full response. The Buddy bridge already does this; Pepper would need
a parallel `stream_response` path. Cuts perceived latency by
30–60 %.

**Multi-modal LLMs with vision.** Pepper has two cameras + a depth
sensor. The agent graph could consume "what does Pepper see" as an
additional input. GPT-4o, Gemini and Claude all accept image inputs.
This unlocks "describe the person in front of me" tasks.

**Adversarial robustness eval.** A separate evaluation pass that
probes how each condition handles noisy speech, ambiguous questions,
off-topic chatter, and minor adversarial inputs. Useful for a
deployment readiness report.

**Auto-counterbalancing + auto-randomisation.** Combine with the
admin dashboard for a one-click experimental session.

### 60.3  Long-Term (Research Programmes)

**QiSDK migration.** For NAOqi 2.9 (Android) Pepper units, rewrite
the NAOqi client in Kotlin/Java using QiSDK. This eliminates the
Python 2.7 problem entirely. Substantial rewrite (~3 weeks).

**Larger-scale multi-site study.** Replicate the methodology in
multiple labs (hospitals, universities, retail) and pool the data.
The cross-context generalisation is publishable in its own right.

**Adaptive routing learning.** Replace the static `hri_task_routing`
YAML with a learned router: after every interaction, update the
router's preference based on observed satisfaction. A multi-armed
bandit (Thompson sampling on a per-task basis) could do this in
~100 lines.

**Personalisation.** A `participant_profile` in `ExperimentManager`
that the smart router consults. If P012 historically preferred fast
short answers, route their interactions to gemini-flash even on
tasks where another model wins on average.

**Multi-robot orchestration.** OmniLLM as the brain for a small
*team* of robots (Pepper + NAO + Buddy in one room). The agent graph
becomes a multi-agent system; each robot has its own
`RobotBridge` and `RobotAction`.

**Active learning of the knowledge base.** When the RAG faithfulness
score drops below a threshold, the system logs the question as "not
covered" and prompts the human curator (you) to add a document.
Knowledge base improves over time.

**A general "embodied benchmark" leaderboard.** Beyond a single lab's
data, a public submission portal (like Chatbot Arena) where any HRI
lab can upload their results and the global Embodied LLM Leaderboard
updates.

### 60.4  What Could Make This A Bigger Story

If a single result emerges from your N = 20 study, three follow-up
papers are obvious:

1. **"Why Smart Routing Wins."** Decompose the C-condition gains:
   when does smart routing help? On which task types? Under which
   noise conditions?
2. **"The Embodiment Gap."** Quantify the per-model gap between
   Chatbot Arena ELO and Embodied ELO. Identify which model
   capabilities translate to embodiment and which don't.
3. **"Faithfulness Under Pressure."** RAG faithfulness scores
   per-model under heavy retrieval (top-10 chunks) vs. light
   retrieval (top-3). Which models stay faithful as context grows?

### 60.5  When To Stop

You will be tempted to add features forever. The thesis writes itself
when you can answer **three** questions with data:

- Does smart routing beat fixed (H2)?
- Does RAG help (H3)?
- Does embodiment change the ranking (H1)?

Everything else is decoration. Add it after submission.

\newpage

---

## Closing Note (Second Edition)

You have reached the end of the expanded book. By now you should be
able to:

- **Explain** in plain English what OmniLLM is, why it exists, and
  what the robot adds — including to a sceptic asking "why bother
  with a robot?"
- **Read** any source file and know what each function does without
  guessing (Part III + Chapter 56).
- **Trace** a single user question through every Python function it
  touches (Chapter 56).
- **Connect** to a Pepper robot (or simulate one in Choregraphe) and
  drive it through the AI server (Parts IV, V, Chapter 58).
- **Re-build** the project from scratch in a sensible order
  (Part VI).
- **Run** a complete experimental session, collect the data, and
  analyse it (Chapter 59 + Chapter 53).
- **Survey** the related work, place OmniLLM in the literature, and
  defend the research contribution (Part X).
- **Choose** the right Python / NAOqi / Choregraphe / LangGraph /
  ChromaDB pattern for any new sub-problem (Part IX + Chapter 57).
- **Plan** the next year of improvements (Chapter 60).
- **Look up** any term, command, or file in seconds (Appendices).

The codebase will continue to evolve; this book will not. When the
book and the source disagree, **trust the source**. The book's job
was to get you fluent enough that you can read the source for
yourself.

Good luck with the thesis. And remember — the most interesting
result might be the one you didn't predict. Embodied LLM rankings
might agree with text rankings, or they might not. **Both findings
advance the field.**

— *End of book, second edition.*

\newpage
