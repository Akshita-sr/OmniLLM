\newpage

# Part II — Architecture, Flow, & Tech Stack

> *Part I told you what we are building and why. Part II tells you what the system looks like when it is running.*

\newpage

## Chapter 5 — The Three-Layer System Architecture

### At a Glance

OmniLLM lives across three concentric layers: a **Human Layer** (the participant talking, listening, looking), a **Robot Layer** (Pepper running NAOqi under Python 2.7), and an **AI Layer** (the modern Python 3.11+ stack on your laptop or a server). The three layers communicate exclusively over HTTP-and-JSON, which is what makes the Python-2.7/Python-3.x divide tolerable. The interaction itself flows in a single direction: human speech enters the Robot Layer, the Robot Layer marshals it to the AI Layer over HTTP, the AI Layer responds with a `RobotAction` JSON, and the Robot Layer enacts that action (speech + gesture + LED + tablet) back at the human.

### The Big Picture

The system is most usefully drawn as three nested boxes with two HTTP arrows crossing the box boundaries:

```
+---------------------------------------------------------------------+
|                        HUMAN PARTICIPANT                            |
|         Speaks to Pepper -> Sees tablet -> Hears response           |
+----------------------------+----------------------------------------+
                             | Voice (microphone) / Head touch / Typed
                             v
+---------------------------------------------------------------------+
|              PEPPER ROBOT  (Python 2.7 -- NAOqi process)            |
|                                                                     |
|  ALAudioDevice ----capture WAV----> HTTP POST to AI server          |
|  ALAnimatedSpeech <--- response text -- HTTP response               |
|  ALMotion       <--- gesture commands -- JSON action plan           |
|  ALLeds         <--- LED colour       -- JSON action plan           |
|  ALTabletService <--- web URL          -- JSON action plan          |
|  ALTracker      <--- face-track on/off -- JSON action plan          |
|                                                                     |
|       <-- HTTP (localhost:5000 / omnillm.server.app) -->            |
+---------------------------------------------------------------------+
                             |
                             v
+---------------------------------------------------------------------+
|              AI SERVER  (Python 3.11+ -- omnillm.server.app)        |
|                                                                     |
|  +--------------------------------------------------------------+   |
|  |            LangGraph Agent Graph (hri/agent_graph.py)        |   |
|  |                                                              |   |
|  |  [START] -> [Transcribe Audio (Whisper)]                     |   |
|  |          -> [Detect Language]                                |   |
|  |          -> [Classify Task Type  T1/T2/T3/T4]                |   |
|  |          -> CONDITIONAL ROUTING                              |   |
|  |               +- T1 Info Retrieval -> [RAG Pipeline]         |   |
|  |               +- T2 Navigation     -> [RAG + Gesture]        |   |
|  |               +- T3 Social Chat    -> [Direct LLM]           |   |
|  |               +- T4 Multilingual   -> [Lang-Optimal LLM]     |   |
|  |          -> [Smart Router / Council]   (Conditions C, D)     |   |
|  |          -> [Generate Robot Action Plan]                     |   |
|  |          -> [Log Everything]                                 |   |
|  |          -> RESPOND to Pepper via HTTP                       |   |
|  +--------------------------------------------------------------+   |
|                                                                     |
|  +-----------------+  +------------------+  +-----------------+     |
|  |   RAG Pipeline  |  |  OmniLLM Core    |  |  Data Logger    |     |
|  |  ChromaDB +     |  |  LiteLLM Gateway |  |  Latencies      |     |
|  |  fallback search|  |  Smart Router    |  |  Tokens / cost  |     |
|  |  PDF/CSV/TXT KB |  |  Consensus       |  |  Transcripts    |     |
|  +-----------------+  |  LLM-as-Judge    |  |  Task success   |     |
|                       |  ELO Scorer      |  +-----------------+     |
|                       +------------------+                          |
|                                                                     |
|  +--------------------------------------------------------------+   |
|  |               LLM Backends (via LiteLLM)                     |   |
|  |   GPT-4o-mini | Claude Haiku | Gemini 2.5 Flash | DeepSeek    |   |
|  |   Ollama local: Llama 3:8b | Qwen 2.5:7b | Mistral:7b ...    |   |
|  +--------------------------------------------------------------+   |
+---------------------------------------------------------------------+
```

### Why HTTP, and Why JSON?

Two pragmatic reasons.

**Reason 1 — Python-version isolation.** NAOqi's official Python bindings are compiled against Python 2.7. CPython 2.7 reached end-of-life on 2020-01-01. The modern AI stack (LangGraph 1.x, LangChain 0.3+, `litellm`, `openai-python` ≥ 1.0, `chromadb` ≥ 0.4, `anthropic` ≥ 0.30, etc.) requires Python 3.10+ and emits syntax errors on Python 2.7. The two runtimes cannot coexist in a single process. HTTP between two separate processes is the simplest portable boundary.

**Reason 2 — Locational decoupling.** The Python 2.7 process *can* live on the robot itself (Pepper's on-board CPU runs Linux and ships with Python 2.7 pre-installed), or it can live on a nearby laptop on the same LAN. The HTTP boundary is identical either way. This matters because: (a) running large LLM agents on Pepper's on-board CPU is infeasible — so the AI Layer always lives off-board; (b) running NAOqi *itself* off-board (i.e., talking from a laptop to Pepper's broker over the LAN) gives us the same effect as if NAOqi ran on the robot, *and* gives us the easy fallback to Choregraphe's virtual robot, which only listens on `127.0.0.1`. So all our Python 2.7 entry points actually live on the laptop in our default setup.

JSON, meanwhile, is the only data format that travels lossless through every layer of the stack (Whisper output, LLM output, LiteLLM cost accounting, ChromaDB metadata, NAOqi's `ALAnimatedSpeech` annotated-text format, Pepper's tablet HTML). The choice was not exotic — but it was deliberate.

### The Layer Responsibilities Table

| Layer | Process | Language | Job | Cannot do |
|---|---|---|---|---|
| **Human** | (the participant) | n/a | Speak, listen, touch the tablet, watch | (the experimenter) writes their answers on the questionnaire |
| **Robot Layer** | `naoqi_client.py` *or* `naoqi_bridge_server.py` | Python 2.7 | Drive Pepper's actuators and sensors via NAOqi services | Run a modern LLM; install a `pip` package newer than ~2019 |
| **AI Layer** | `omnillm.server.app` (Flask) | Python 3.11+ | Speech-to-text, language detection, task classification, RAG, LLM querying, gesture planning, logging | Talk to NAOqi directly |

### Academic Context

The HTTP-bridge pattern adopted here is well-precedented in robotics: ROS itself uses a publish-subscribe message bus (`roscore`) that is process-external for similar reasons (different nodes can be in different languages and on different machines). Pepper-specific bridges — for example *PePUT* (Ganal et al. 2023) and the QiSDK-based bridge in *InjectMeAI* (Ampadu et al. 2022) — adopt the same pattern.

The split has a side benefit for replicability: a reader can run the *entire* AI Layer on their own machine without the robot present, drop in their own Robot Layer (a different humanoid platform, ROS, or even a Unity simulator like PePUT), and reproduce most of the AI-side results. The HTTP contract acts as a published, language-independent API for "Pepper's brain."

\newpage

## Chapter 6 — The Lifecycle of a Single Question, End to End

### At a Glance

Trace a single question from microphone to robot action. Two paths exist for the *capture* phase (head-touch capture vs. continuous VAD vs. typed text), but they all converge on the same `POST /interact` HTTP call. From there on, the path is identical for every interaction: Whisper STT → language detection → task classification → conditional routing → response generation → action-plan generation → logging → HTTP response → NAOqi enactment.

### Step-by-Step Trace

The participant says: *"Where is the Pepper room at DIBRIS?"*

```
TIME  LAYER           EVENT
0.00  HUMAN           Says "Where is the Pepper room at DIBRIS?" out loud.
0.20  PEPPER          ALAudioDevice captures 1.8s WAV at 16 kHz mono.
                      ALAudioRecorder saves /tmp/utterance.wav.
0.21  PEPPER (P2.7)   naoqi_client reads the WAV, base64-encodes it.
0.22  PEPPER (P2.7)   POST http://<server-ip>:5000/interact
                      Body: {"audio": "...base64...",
                             "participant_id": "P003",
                             "session_id": "uuid",
                             "condition": "C",
                             "rag_enabled": true}
0.22  AI SERVER       Flask receives the request.
0.23  AI SERVER       Resolves Condition C -> effective model = (smart-routed).
                      State dict built and passed to graph.ainvoke().
0.23  GRAPH NODE 1    transcribe_audio: WhisperSTT.transcribe(audio_bytes)
0.65  GRAPH NODE 1    -> "Where is the Pepper room at DIBRIS?"
0.65  GRAPH NODE 2    detect_language: returns "en", confidence 0.92
0.66  GRAPH NODE 3    classify_task: hits "where" and "room" -> NAVIGATION (0.95)
0.66  GRAPH ROUTE     conditional edge picks "nav_rag" branch
0.66  GRAPH NODE 4    nav_rag: rag.query(utterance, model_id=None)
                      ChromaDB top-3 chunks from university_map.txt + lab_info.txt
0.85  GRAPH NODE 4    LLM call (smart-routed -> gpt-4o-mini for navigation)
1.40  GRAPH NODE 4    -> "The Pepper room is at the end of the ground-floor
                          corridor, on the right..."
                      GesturePlanner picks gesture="point_right", led="#00AAFF"
1.40  GRAPH NODE 5    smart_router: condition is "C" but response_text is set,
                                    so no further routing - pass through.
1.41  GRAPH NODE 6    generate_action_plan: assembles the RobotAction dict.
1.41  GRAPH NODE 7    log_interaction: writes one InteractionRecord to disk.
1.42  AI SERVER       Returns JSON to Pepper.
1.42  PEPPER (P2.7)   Receives JSON, parses speech/gesture/emotion_led.
1.43  PEPPER          ALAnimatedSpeech.say("The Pepper room is...")
                      ALMotion runBehavior("animations/Stand/Gestures/Right_1")
                      ALLeds.fadeRGB("FaceLeds", 0x00AAFF, 0.3)
1.50  HUMAN           Hears the answer, sees the arm raise to the right,
                      sees the eye-LEDs turn blue.
4.30  HUMAN           Response finished. Floor returns to participant.
```

(Beginner) **Why the `_start_time` field in `HRIGraphState`.** The state has a `_start_time` set in the transcription node (the first node that always runs). The `log_interaction` node at the very end computes `total_latency = (time.monotonic() - start) * 1000`. So the "end-to-end latency" we log includes Whisper STT, language detection, task classification, RAG retrieval, LLM generation, gesture planning, and JSON marshalling — but **not** the time the WAV took to travel from Pepper to the server, and **not** the time NAOqi takes to actually utter the speech. We measure compute, not the network or the actuator. This is a deliberate choice: the network and the actuators are dependent on the lab's Wi-Fi and Pepper's hardware, neither of which is the LLM's fault.

### The State Dictionary

The graph passes one dictionary through every node. Each node *adds* fields; nothing is overwritten without intent. The schema is the `HRIGraphState` dataclass — but at runtime, LangGraph 1.x stores it as a `dict`, and we use a `_merge_state` wrapper to make every node behave as "the new state is `{**old, **node_output}`" rather than "the node return value replaces the state." This is the *single line of code* that fixed the empty-speech bug in the 2026-05 upgrade. See Chapter 12 for the deep-dive.

The most important fields after a full traversal:

| Field | Type | Set by node | Example value |
|---|---|---|---|
| `utterance` | str | transcribe_audio | `"Where is the Pepper room at DIBRIS?"` |
| `detected_language` | str | detect_language | `"en"` |
| `task_type` | str | classify_task | `"navigation"` |
| `task_confidence` | float | classify_task | `0.95` |
| `rag_context` | str | nav_rag (or rag) | (joined retrieved chunks) |
| `rag_chunks` | list | nav_rag (or rag) | (list of `DocumentChunk`) |
| `rag_faithfulness` | float | nav_rag (or rag) | `0.87` |
| `response_text` | str | LLM node | `"The Pepper room is..."` |
| `model_id` | str | LLM node | `"openai-gpt4o-mini"` |
| `gesture` | str | GesturePlanner | `"point_right"` |
| `led_color` | str | GesturePlanner | `"#00AAFF"` |
| `robot_action` | dict | generate_action_plan | full JSON for Pepper |
| `latency_ms` | float | log_interaction | `1190` |
| `input_tokens` | int | LLM node | `412` |
| `output_tokens` | int | LLM node | `34` |
| `cost_usd` | float | LLM node | `0.0000687` |

\newpage

## Chapter 7 — The LangGraph Agent Pipeline, Node by Node

### At a Glance

The brain of Pepper is a directed acyclic graph of nine asynchronous Python functions wired together by LangGraph. Every interaction creates one `HRIGraphState` dict, runs it through the graph, and gets back an updated dict. The graph is built by `build_hri_graph(gateway, rag, logger, default_model)` in [omnillm/hri/agent_graph.py](../omnillm/hri/agent_graph.py).

### The Graph, in Pictures

```
                            +-----------------------+
            (audio_bytes)   |                       |
            (or utterance)  |   transcribe_audio    |
                  +-------->|   (Whisper STT)       |
                  |         |                       |
                  |         +-----------+-----------+
                  |                     |
                  |                     v
                  |         +-----------------------+
                  |         |                       |
                  |         |   detect_language     |
                  |         |   (script + n-gram)   |
                  |         |                       |
                  |         +-----------+-----------+
                  |                     |
                  |                     v
                  |         +-----------------------+
                  |         |                       |
                  |         |   classify_task       |
                  |         |   (T1/T2/T3/T4)       |
                  |         |                       |
                  |         +-----------+-----------+
                  |                     |
                  |                     v
                  |              [CONDITIONAL EDGE]
                  |                     |
                  |     +---------------+-----------+----------+
                  |     |               |           |          |
                  |     v               v           v          v
                  | +-------+      +---------+ +---------+ +--------+
                  | |  rag  |      | nav_rag | | direct  | | multi  |
                  | |  T1   |      |   T2    | |  llm    | | lingual|
                  | +---+---+      +----+----+ +----+----+ +----+---+
                  |     |               |           |           |
                  |     +-------+-------+-----------+-----------+
                  |             |
                  |             v
                  |     +-----------------+
                  |     |  smart_router   |
                  |     |  (C: route;     |
                  |     |   D: council;   |
                  |     |   else: skip)   |
                  |     +--------+--------+
                  |              |
                  |              v
                  |     +-----------------+
                  |     |  generate_      |
                  |     |  action_plan    |
                  |     |  (speech +      |
                  |     |   gesture +     |
                  |     |   led + meta)   |
                  |     +--------+--------+
                  |              |
                  |              v
                  |     +-----------------+
                  |     |  log_           |
                  |     |  interaction    |
                  |     |  (one row)      |
                  |     +--------+--------+
                  |              |
                  |              v
                  |            [END]
                  |              |
                  +<-------------+
                                 returns RobotAction JSON to Flask
```

### Per-Node Specification

| # | Node name | Async function | Input fields | Output fields | When skipped |
|---|---|---|---|---|---|
| 1 | `transcribe_audio` | `WhisperSTT.transcribe()` if `audio_bytes`; otherwise pass-through | `audio_bytes`, `utterance` | `utterance`, `_start_time` | Text-only inputs skip Whisper entirely |
| 2 | `detect_language` | `LanguageDetector.detect()` | `utterance` | `detected_language` | If `utterance` is empty |
| 3 | `classify_task` | `HRITaskClassifier.classify()` | `utterance`, `detected_language` | `task_type`, `task_confidence` | never |
| 4a | `rag` (T1) | `RAGPipeline.query(utterance, model_id=…)` | `utterance`, `model_id` | `rag_context`, `rag_chunks`, `rag_faithfulness`, `response_text`, `model_id`, `latency_ms` | Routed only if task=info_retrieval |
| 4b | `nav_rag` (T2) | `RAGPipeline.query()` + `GesturePlanner.plan("navigation", …)` | `utterance`, `model_id` | All RAG fields + `gesture`, `led_color` | Routed only if task=navigation |
| 4c | `direct_llm` (T3) | `gateway.query(model, messages)` with social system prompt | `utterance`, `model_id` | `response_text`, `model_id`, `input_tokens`, `output_tokens`, `cost_usd`, `latency_ms`, `gesture`, `led_color` | Routed only if task=social_conversation OR Condition E |
| 4d | `multilingual_llm` (T4) | Tries lang-optimal model (Claude Haiku) first, falls back to GPT-4o-mini if first returns an error | `utterance` | Same as `direct_llm` | Routed only if task=multilingual |
| 5 | `smart_router` | For Condition C: re-routes the LLM call to the task-optimal model. For Condition D: fires a 3-model consensus. Otherwise pass-through. | All accumulated state | Possibly overwrites `response_text`, `model_id` | Conditions A, B, E pass through |
| 6 | `generate_action_plan` | Assembles `RobotAction` dict and assigns final gesture+LED if not set | All accumulated state | `robot_action` | never |
| 7 | `log_interaction` | `ExperimentLogger.log_interaction(...)` writes one CSV row to disk | All accumulated state | `latency_ms` (end-to-end) | If `logger` not provided |

### Why a Graph, Not a Function Call Chain?

(Beginner) **Why bother with LangGraph at all?** The same logic could be a single `async def process_interaction(utterance: str) -> dict` with `if`/`elif` branches. Three reasons we use a graph:

1. **Inspectability.** LangGraph can render the graph as a Mermaid or Graphviz diagram at runtime. The Chapter 7 figure above was generated this way.
2. **Hot-swappable nodes.** Want to A/B-test a different task classifier? Swap one node in `build_hri_graph()` without touching any other code.
3. **State threading.** With a function chain you must thread variables through manually (`utterance`, then `(utterance, lang)`, then `(utterance, lang, task)`, …). With LangGraph's `StateGraph(dict)` plus our `_merge_state` wrapper, the state grows naturally and any node can read any prior node's output.

The cost is a slightly heavier framework dependency. In return we get a brain shape that is easy to extend (e.g. adding a "safety filter" node before `generate_action_plan` would take ten lines of code).

\newpage

## Chapter 8 — The Tech Stack — Every Library, and Why That One

### At a Glance

OmniLLM is intentionally a thin glue layer over very capable open-source libraries. The full direct-dependency list fits on one page; every choice has a one-sentence justification. Replacing a single library with an equivalent (e.g. `chromadb` → `qdrant-client`) is a one-day refactor, not a rewrite.

### The Direct-Dependency Table

| Library | Used for | Why this one, not another |
|---|---|---|
| **litellm** | Unified LLM provider gateway | Covers 100+ providers with one API; cost-per-token table built in; well-maintained by BerriAI |
| **openai** | OpenAI SDK (used by LiteLLM under the hood for OpenAI/Azure) | Officially supported, fastest moving |
| **anthropic** | Claude SDK | Required for Claude streaming; LiteLLM uses it transparently |
| **google-generativeai** | Gemini SDK | Required for Gemini 2.5 features |
| **ollama** Python client | Local model runtime | Free, no API key, runs Llama / Qwen / Mistral on your laptop. Critical for Condition B (offline baseline). |
| **langgraph** | Stateful agent pipeline | Best-of-class for "graph of LLM nodes with conditional edges." Replaces hand-rolled `if/elif`. |
| **langchain** + **langchain-community** | RAG plumbing primitives (text splitters, document loaders) | Reuse the splitter most familiar to ML practitioners; we use only the small, stable parts. |
| **chromadb** | Embedded vector DB for RAG | Pure-Python install; no Docker; small footprint. Falls back to in-memory if disk write fails. |
| **sentence-transformers** | Local embeddings (all-MiniLM-L6-v2) | Avoids OpenAI embedding cost during dev; free; runs offline |
| **openai-whisper** | Speech-to-text (local) | The original Whisper, runs on CPU. Local STT means we never send participant audio to the cloud. |
| **langdetect** | Backup language detection | Used after our Unicode-script + n-gram heuristic fails. |
| **flask** | HTTP AI server | Smallest production-acceptable Python web framework. We use no fancy features. |
| **aiohttp** | Async HTTP client (Pepper bridge calls) | Required because the bridge driver must be async-compatible with LangGraph |
| **pyyaml** | `config/models.yaml` parsing | Standard. |
| **rich** + **click** | CLI rendering and arg-parsing | Pretty tables, command-discoverable help, easy testing. |
| **python-dotenv** | `.env` file loading | Keeps API keys out of git history |
| **pytest** + **pytest-asyncio** + **pytest-mock** | Test framework | 289 tests; all mocked; no API keys needed |

### Why No Big Frameworks?

We deliberately avoid ROS, ROS 2, and Microsoft Bot Framework. Three reasons:

1. **Setup friction.** ROS adds 4–8 GB of installation and significant cognitive overhead. For our scope (one robot, two HTTP endpoints, one knowledge base), we do not need it.
2. **Python version trap.** ROS 1 is Python 2; ROS 2 is Python 3.8+. Either way, mixing in our 3.11+ AI dependencies is risky.
3. **Portability.** A Flask AI server runs on Windows, macOS, Linux, and a Raspberry Pi without modification. ROS does not.

If a future deployment needs ROS (e.g. integrating with a mobile robot like Tiago), the AI server can run *behind* a ROS node without itself becoming ROS-dependent.

### Why Local Whisper?

We use OpenAI's **Whisper** Python package (the original, locally-run version), not the OpenAI cloud audio API. Three reasons:

1. **Privacy.** Participants speak in the lab. Sending raw audio to a third-party cloud is a non-trivial GDPR concern. Local Whisper means audio never leaves the laptop.
2. **Latency.** A local Whisper-base model on CPU transcribes a 5-second utterance in ~700ms. The cloud round-trip averages ~1.5s and varies with network.
3. **Cost.** Free.

The trade-off is accuracy: Whisper-base is noticeably weaker on accented English and on speakers under stress than Whisper-large or the cloud API. For experimental use this is acceptable because the *condition* effect is what we measure, and Whisper accuracy is constant across conditions.

### Why ChromaDB and Not FAISS?

ChromaDB ships with:

- a Python-native, pure-pip install (FAISS requires a C++ build chain);
- automatic persistence to a local SQLite file;
- a stable metadata-filtering API.

For our scale (~50 document chunks from the DIBRIS knowledge base), the speed difference between ChromaDB's HNSW and FAISS's IVF is irrelevant. ChromaDB also fails gracefully — if the SQLite file is locked or the embedding model fails to load, we fall back to a **keyword search** over the same documents (see `RAGPipeline._keyword_search()` in Chapter 12). The pipeline never crashes on a vector-DB outage.

### Why xhtml2pdf for the Book?

This is the most surprising choice. We use `xhtml2pdf` (pure Python) rather than the much higher-quality `wkhtmltopdf` or LaTeX. Three reasons:

1. **No external binary dependency.** `pip install xhtml2pdf` is the *entire* install. `wkhtmltopdf` needs a separate binary that has been variably available on Windows for the last five years.
2. **Cross-platform reproducibility.** The thesis examiner must be able to rebuild the PDF on their machine in five minutes. A pure-Python pipeline guarantees that.
3. **Font control via DejaVu.** `xhtml2pdf` lets us register the DejaVu Sans + DejaVu Sans Mono fonts (shipped with matplotlib) so that arrows, box-drawing characters, and accented Latin all render correctly. The replacement table in `build_pdf.py` (see Chapter 16's discussion) handles the few Unicode points DejaVu does not cover inside `<pre>` blocks.

The trade-off is rendering quality — xhtml2pdf is not as visually polished as LaTeX. For a thesis-supporting reference book, we judged readability over polish.

\newpage

## Chapter 9 — Two Topologies for Driving Pepper (Polling vs. Bridge Server)

### At a Glance

OmniLLM ships two ways to wire the Robot Layer to the AI Layer. **Topology 1** ("Pepper polls AI server") was the original design: Pepper itself initiates every interaction, captures audio, and POSTs to the AI server. **Topology 2** ("AI server drives Pepper") was added in May 2026: a small HTTP bridge server runs in Python 2.7 near (or on) Pepper, listens for action commands from the AI Layer, and translates them to NAOqi calls. The two topologies coexist; use whichever fits your scenario.

### Topology 1 — Pepper Polls the AI Server

This is the topology described in the original architecture diagram. The active script is `omnillm/server/naoqi_client.py` (Python 2.7). It runs in a loop:

```
1. Wait for the trigger (text input / head touch / VAD).
2. Capture audio (or read text from stdin).
3. POST audio to AI server /interact.
4. Receive RobotAction JSON.
5. Enact speech / gesture / LED / tablet via NAOqi.
6. Go to step 1.
```

**Pros:**

- Pepper "owns" its own conversation loop. The participant interacts directly with the robot; the AI server is a passive responder.
- Robust to brief AI-server restarts: Pepper keeps trying.
- Easiest to demo: `python naoqi_client.py --trigger text` and you can start typing immediately.

**Cons:**

- Action choice is entirely determined by the AI server's response. The LangGraph nodes cannot, mid-thought, decide to *also* trigger a gesture or play a sound while computing — they can only return one final action at the end.
- Streaming responses are awkward: the LLM finishes computing the full sentence before Pepper starts speaking.

### Topology 2 — AI Server Drives Pepper via the Bridge Server

This is the topology added in May 2026. The new script is `omnillm/server/naoqi_bridge_server.py` (Python 2.7). It exposes its own HTTP API near the robot:

```
GET  /ping            -> {"ok": true, "naoqi": true, "simulation": false}
POST /action          -> body = RobotAction JSON, executes speech+gesture+LED
POST /audio/record    -> body = {"seconds": 5}, returns base64 WAV
GET  /sensors         -> returns head-touch state, face detected, battery, etc.
POST /tracker/start   -> begin face tracking
POST /tracker/stop    -> stop face tracking
POST /disconnect      -> motion.rest() and disconnect from broker
```

Now the **Python 3 code** is the one that initiates conversation. Inside a LangGraph node you can write:

```python
from omnillm.robotics import make_pepper_bridge
from omnillm.robotics.bridge import RobotAction

bridge = await make_pepper_bridge(robot_ip="127.0.0.1", bridge_port=6000)
await bridge.execute_action(RobotAction(
    speech="Hello! Let me think about that.",
    gesture="nod",
    emotion_led="#FFFF00",
))
# ... think ...
await bridge.execute_action(RobotAction(
    speech="The Pepper room is at the end of the corridor.",
    gesture="point_right",
    emotion_led="#00AAFF",
))
```

**Pros:**

- The AI Layer can trigger arbitrary robot behaviours *during* its reasoning, not just at the end.
- Streaming responses become natural: speak the first sentence while the LLM is still generating the second.
- Test infrastructure: `make_pepper_bridge()` falls back to a **stub mode** that prints actions instead of executing them, so the entire pipeline runs in CI without any robot — virtual or real.

**Cons:**

- Two Python 2.7 processes to manage (the bridge plus, optionally, a separate client). The PowerShell terminal count goes from 2 to 3.
- The bridge does not own a conversation loop — you must drive it from the Python 3 side.

### Which Topology for Which Scenario?

| Scenario | Use Topology 1 | Use Topology 2 |
|---|---|---|
| Quick demo / "talk to the robot now" | ✓ |   |
| Live experimental study with the `run_subject_experiment.py` driver |   | ✓ |
| Headless CI tests on a laptop (no robot) |   | ✓ (stub mode) |
| Debugging a single NAOqi service in isolation |   | ✓ (`curl /action`) |
| Continuous voice-activity-detected conversation | ✓ |   |

The **experimental study at DIBRIS uses Topology 2** because the `run_subject_experiment.py` driver is Python-3-based and benefits from the bridge's stub-mode fallback (we can dry-run the whole 20-interaction matrix in CI before plugging in the real robot).

### Auto-Discovery: How `make_pepper_bridge()` Decides Which Bridge It Found

The Python 3 client (`omnillm/robotics/pepper.py`) has a single entry point: `make_pepper_bridge(robot_ip="127.0.0.1", robot_port=None, bridge_port=6000)`. Internally:

1. It first tries `GET http://<robot_ip>:<bridge_port>/ping`. If that returns `{"ok": true, "naoqi": true}`, mode = `"server"`.
2. If `/ping` returns `simulation: true`, the bridge is up but is talking to a *virtual* robot — mode is still `"server"` but the action-execution path tolerates "behavior not installed."
3. If `/ping` times out, the client attempts a direct NAOqi connection (using the `qi` Python bindings if installed) — mode = `"naoqi"`. This is useful for headless ROS-like integrations.
4. If neither works, mode = `"stub"`. Every `execute_action()` call prints the action to stdout and returns success. This is what makes the pytest suite work without any robot.

This three-level fallback is what we mean when we say "the absence of a robot is a first-class operating mode."

\newpage
