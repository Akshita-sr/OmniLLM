## Chapter 15 — `rag/pipeline.py` — Retrieval-Augmented Generation

> **⚡ AT A GLANCE.** Indexes documents (TXT, CSV, PDF) into ChromaDB. On
> query, retrieves top-k chunks via cosine similarity, prepends them to the
> LLM prompt as context, and asks the LLM to answer using *only* the
> context. Optional faithfulness scoring (LLM-as-Judge) and hallucination
> detection (word-overlap heuristic). Falls back gracefully to keyword search
> when ChromaDB is not installed.

### 15.1  Why RAG?

A general-purpose LLM does not know your specific lab — your room numbers,
your staff, your seminar schedule, your wifi password. Two options:

- **Fine-tune a model on your data.** Expensive, slow, must redo for every
  update.
- **Show the model your documents at query time.** Cheap, fast, instantly
  reflects updates. This is RAG.

For OmniLLM, RAG enables Tasks T1 (Information Retrieval) and T2
(Navigation) — both depend on facts in `knowledge_base/`.

### 15.2  The Three Phases

```
                ┌─────────────────────────┐
                │   1. INDEXING (once)    │
                ├─────────────────────────┤
                │  knowledge_base/*.txt   │
                │  knowledge_base/*.csv   │
                │  knowledge_base/*.pdf   │
                └────────────┬────────────┘
                             │
                  split into 512-char chunks
                  (with 64-char overlap)
                             │
                             ▼
                ┌─────────────────────────┐
                │   ChromaDB collection   │
                │   (cosine, in-process)  │
                └────────────┬────────────┘
                             │
                ┌────────────┴────────────┐
                │  2. RETRIEVAL (per Q)   │
                │  query → top-k chunks   │
                └────────────┬────────────┘
                             │
                             ▼
                ┌─────────────────────────┐
                │  3. AUGMENTED PROMPT    │
                │  system + context + Q   │
                └────────────┬────────────┘
                             │
                             ▼
                ┌─────────────────────────┐
                │  LLM generates answer   │
                │  grounded in context    │
                └────────────┬────────────┘
                             ▼
                ┌─────────────────────────┐
                │  Optional: faithfulness │
                │  + hallucination check  │
                └─────────────────────────┘
```

### 15.3  Chunking — Why 512 / 64?

The pipeline uses a sliding-window chunker:

```python
def _split_text(self, text, source, metadata):
    chunks = []
    start = 0; idx = 0
    while start < len(text):
        end = min(start + self.chunk_size, len(text))   # 512
        chunk_text = text[start:end].strip()
        if chunk_text:
            chunks.append(DocumentChunk(text=chunk_text, source=source, ...))
        start += self.chunk_size - self.chunk_overlap   # advance 512 - 64 = 448
        idx += 1
    return chunks
```

- **512 characters** is a useful unit: long enough to contain a complete
  thought, short enough that several can fit in one prompt.
- **64-character overlap** prevents losing context at chunk boundaries (a
  sentence split across chunks still appears intact in at least one).

### 15.4  Retrieval — the Dual Path

```python
def retrieve(self, query: str) -> list[DocumentChunk]:
    if self._collection is not None:        # ChromaDB available
        return self._retrieve_chromadb(query)
    return self._retrieve_keyword(query)    # fallback path
```

**ChromaDB path:** convert query to embedding (handled by ChromaDB's
default), do cosine similarity search, return top-4 chunks with similarity
scores in [0, 1].

**Keyword fallback:** simple Jaccard similarity of stemmed words. Less
accurate but **always works**, even on a stripped-down install where
`pip install chromadb` failed.

### 15.5  The Augmented Prompt

```python
system = "You are a helpful assistant. Answer the user's question using ONLY "
         "the provided context. If the answer is not in the context, say so clearly."

user_content = (
    "Context:\n"
    "[1] (Source: lab_info.txt)\nThe IRAI Lab is located in Building C, Room 305...\n\n"
    "[2] (Source: faq.txt)\nQ: What are the lab opening hours?\nA: Mon-Fri 08:00-20:00...\n\n"
    "Question: What are the lab hours?"
)

messages = [
    {"role": "system", "content": system},
    {"role": "user",   "content": user_content},
]
```

The "ONLY" instruction is critical. It tells the LLM to refuse to invent
information — the foundation of grounded answering.

### 15.6  Faithfulness Scoring

Optional. Costs an extra LLM call but gives a quantitative measure of
how well the answer used the retrieved context:

```python
prompt = (
    "You are a factuality judge. Score how faithfully the answer uses ONLY "
    "information from the given context (0.0 = completely hallucinated, "
    "1.0 = every claim is supported by the context).\n\n"
    f"Context:\n{context}\n\nQuestion: {question}\n\nAnswer: {answer}\n\n"
    'Respond ONLY with valid JSON: {"score": <float>, "reasoning": "..."}'
)
```

The score is recorded in the experiment log alongside latency and cost.

### 15.7  Hallucination Detection (Heuristic)

A cheap word-overlap check:

```python
def _detect_hallucination(self, answer, chunks):
    if not chunks:
        return False
    all_context = " ".join(c.text.lower() for c in chunks)
    answer_words = re.findall(r"\b\w{5,}\b", answer.lower())  # words ≥5 chars
    if not answer_words:
        return False
    found = sum(1 for w in answer_words if w in all_context)
    return (found / len(answer_words)) < 0.20   # < 20% overlap = suspect
```

This is a *flag*, not a verdict. False positives are common (the answer might
paraphrase the context). For final scoring, prefer the faithfulness LLM-as-
Judge.

\newpage

## Chapter 16 — `hri/classifier.py` and `hri/language_detector.py`

> **⚡ AT A GLANCE.** Two short files together produce the input metadata
> the agent graph needs. The classifier maps an utterance to one of T1–T4
> using keyword + regex scoring (rule-based, instant, no LLM call). The
> language detector uses Unicode script analysis, n-gram word matching, and
> optionally `langdetect`, to identify the language and recommend a model.

### 16.1  Why Rule-Based and Not LLM?

These are both pre-LLM steps. They run on every interaction. Latency is
critical. A rule-based classifier returns in 10–20 ms; an LLM call takes
500+ ms. For tasks this simple, the rules are accurate enough (~92% in
testing) that the latency saving is worth it.

That said, both modules **also** offer LLM-based variants for high-stakes
or ambiguous inputs (`classify_with_llm()`).

### 16.2  The Classifier — Keyword Scoring

Each task category has a keyword list and a regex-pattern list:

```python
_NAVIGATION_KEYWORDS = frozenset([
    "where", "room", "floor", "cafeteria", "toilet", "elevator", "lift",
    "point", "direction", "guide", "navigate", "take me", "show me",
    "find", "locate", "map", "route",
    # ...
])

_NAVIGATION_PATTERNS = [
    re.compile(r"\broom\s+\d+\b", re.IGNORECASE),       # "Room 305"
    re.compile(r"\bwhere\s+(is|are|can i find)\b", re.IGNORECASE),
    re.compile(r"\b(go to|take me to|guide me to)\b", re.IGNORECASE),
    # ...
]
```

The score for a category is computed by combining:

1. **Keyword overlap**: number of words in the utterance matching the
   keyword set, capped to 0.3.
2. **Phrase keyword bonus**: 0.15 per multi-word keyword like
   `"how do i get to"`.
3. **Pattern match bonus**: 0.25 per regex hit.

Score is capped at 1.0 per category. The category with the highest score
wins. If no category exceeds 0.1, default to `INFO_RETRIEVAL` with low
confidence.

Confidence is normalised so a score of 0.1 maps to 0.5, and scores ≥ 0.5
map to 0.95.

### 16.3  Why Multilingual Beats Everything

If `detected_language != "en"`, the classifier short-circuits to
`MULTILINGUAL` immediately:

```python
if detected_language != "en":
    return ClassificationResult(
        task_type=HRITaskType.MULTILINGUAL, confidence=0.99,
        reasoning=f"Non-English input detected (language={detected_language})",
        ...
    )
```

This is a deliberate design choice. A French-speaker asking "where is room
305?" will route to T4, not T2, because the **language barrier** is the
dominant problem to solve.

### 16.4  The Language Detector — Three-Tier Cascade

```
         ┌──────────────────────────┐
         │  Tier 1: Unicode script  │
         │  (instant, zero deps)    │
         └────────────┬─────────────┘
              dominant script?
              ╱           ╲
        Latin             non-Latin
          │                 │
          ▼                 ▼
  ┌──────────────┐    ┌────────────────────┐
  │ Tier 2: word │    │ script → language  │
  │ n-gram match │    │ table (e.g., Hangul│
  │              │    │ → ko, Cyrillic→ru) │
  └──────┬───────┘    └────────────────────┘
         │
   confident?
       ╱  ╲
     yes   no
      │     ▼
      │ ┌──────────────┐
      │ │ Tier 3:      │
      │ │ langdetect   │
      │ │ (if installed│
      │ │  optional)   │
      │ └──────┬───────┘
      ▼        ▼
  return result
```

Tier 1 catches Arabic, Chinese, Japanese, Korean, Russian, Greek, Hebrew,
Thai instantly via Unicode block analysis. Tier 2 catches French, German,
Spanish, Italian, Portuguese, Dutch, Turkish via high-frequency word
detection ("le", "der", "el", etc.). Tier 3 falls back to the
`langdetect` library when neither is decisive.

### 16.5  Language → Model Mapping

After detecting the language, the detector recommends a model:

```python
_LANGUAGE_MODEL_MAP = {
    "en": "openai-gpt4o-mini",   # English → cheap and accurate
    "fr": "gemini-flash",        # French → strong multilingual
    "de": "gemini-flash",
    "ja": "gemini-flash",
    "zh": "gemini-flash",
    "ar": "gemini-flash",
    # ...
}
```

The choice of Gemini Flash for non-English is empirical: it consistently
performs strongly across the multilingual axis at very low cost.

\newpage

## Chapter 17 — `hri/agent_graph.py` — The Brain of the Robot

> **⚡ AT A GLANCE.** This is the most complex file in the project. It builds
> the LangGraph state machine described in Chapter 7, with one factory
> function per node so the graph builder can wire them up. Every node is a
> closure over the gateway, RAG pipeline, and logger so it has the
> dependencies it needs without global state.

### 17.1  The `build_hri_graph()` Top Level

```python
def build_hri_graph(gateway, rag=None, logger=None,
                    default_model="openai-gpt4o-mini"):
    from langgraph.graph import StateGraph, END

    builder = StateGraph(dict)   # state is a plain dict

    builder.add_node("transcribe_audio", _make_transcribe_node(gateway))
    builder.add_node("detect_language",  _make_detect_language_node())
    builder.add_node("classify_task",    _make_classify_task_node())
    if rag is not None:
        builder.add_node("rag",     _make_rag_node(rag))
        builder.add_node("nav_rag", _make_nav_rag_node(rag))
    else:
        builder.add_node("rag",     _make_direct_llm_node(gateway, default_model))
        builder.add_node("nav_rag", _make_direct_llm_node(gateway, default_model))
    builder.add_node("direct_llm",       _make_direct_llm_node(gateway, default_model))
    builder.add_node("multilingual_llm", _make_multilingual_llm_node(gateway))
    builder.add_node("smart_router",     _make_smart_router_node(gateway))
    builder.add_node("generate_action_plan", _make_action_plan_node())
    builder.add_node("log_interaction",      _make_log_node(logger))

    builder.set_entry_point("transcribe_audio")
    builder.add_edge("transcribe_audio", "detect_language")
    builder.add_edge("detect_language",  "classify_task")

    builder.add_conditional_edges("classify_task", _route_by_task_type, {
        "rag":              "rag",
        "nav_rag":          "nav_rag",
        "direct_llm":       "direct_llm",
        "multilingual_llm": "multilingual_llm",
    })

    for n in ("rag", "nav_rag", "direct_llm", "multilingual_llm"):
        builder.add_edge(n, "smart_router")
    builder.add_edge("smart_router",         "generate_action_plan")
    builder.add_edge("generate_action_plan", "log_interaction")
    builder.add_edge("log_interaction",      END)

    return builder.compile()
```

### 17.2  The Closure Pattern

Each `_make_*_node` returns an `async` function (the actual node) that has
captured its dependencies. Example:

```python
def _make_transcribe_node(gateway):
    async def transcribe_audio(state: dict) -> dict:
        audio = state.get("audio_bytes", b"")
        if not audio:
            # Text-only mode: utterance already set
            return {"_start_time": time.monotonic()}
        try:
            from omnillm.robotics.whisper_stt import WhisperSTT
            stt = WhisperSTT()
            utterance = await stt.transcribe(audio)
            return {"utterance": utterance, "_start_time": time.monotonic()}
        except Exception as exc:
            return {"error": f"Transcription failed: {exc}",
                    "_start_time": time.monotonic()}
    return transcribe_audio
```

Closures are why this file is short despite each node being conceptually
distinct — there is no parameter passing, no global state, no class
hierarchy. Each node is a pure function of state.

### 17.3  The Conditional Edge Function

This is the dispatching logic that gives Conditions A–E their behaviour:

```python
def _route_by_task_type(state: dict) -> str:
    task_type   = state.get("task_type", "info_retrieval")
    condition   = state.get("condition", "A")
    rag_enabled = state.get("rag_enabled", True)

    # Condition E: RAG-Off Control always goes to direct LLM
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

Three things to notice:

1. **Condition E** wins over task type. The whole point of E is to disable
   RAG, so we always route to `direct_llm`.
2. **Other conditions** still respect task type. Condition A (cloud) and
   Condition B (local) both follow the task → branch routing. They differ
   only in *which model* the branch ends up calling — that decision is made
   in `smart_router` or by the default model.
3. **`rag_enabled=False`** also triggers `direct_llm` even within Conditions
   A/B/C/D (e.g., for ablation studies).

### 17.4  The Smart-Router Node

This is where Conditions C and D actually take effect:

```python
def _make_smart_router_node(gateway):
    async def smart_router(state: dict) -> dict:
        condition = state.get("condition", "A")
        if state.get("response_text") and condition not in ("C", "D"):
            return {}   # already answered, no further routing

        if condition == "D":
            # Consensus: query 3 models, synthesise
            from omnillm.consensus import ConsensusEngine
            engine = ConsensusEngine(gateway=gateway)
            council = ["openai-gpt4o-mini", "gemini-2.5-flash", "claude-haiku"]
            ...
            council_resp = await engine.query(council, messages)
            return {"response_text": council_resp.synthesis,
                    "model_id": "council:" + "+".join(council)}

        elif condition == "C":
            # Smart-route per task type
            from omnillm.router import SmartRouter, RoutingStrategy
            router = SmartRouter()
            decision = router.route_for_hri_task(
                task_type=state.get("task_type"),
                strategy=RoutingStrategy.TASK_TYPE,
            )
            target = decision.model_id
            ...
            resp = await gateway.query(target, messages)
            return {"response_text": resp.content, "model_id": resp.model_id, ...}
    return smart_router
```

### 17.5  Logging — the Final Node

This is where `ExperimentLogger` records the interaction. Wrapped in a
try/except because **logging failure should never crash the interaction**:

```python
def _make_log_node(logger):
    async def log_interaction(state: dict) -> dict:
        if logger is None:
            return {}
        start = state.get("_start_time", time.monotonic())
        total_latency = (time.monotonic() - start) * 1000
        try:
            logger.log_interaction(
                session_id=state.get("session_id", ""),
                participant_id=state.get("participant_id", ""),
                condition=state.get("condition", "A"),
                task_type=state.get("task_type"),
                utterance=state.get("utterance", ""),
                response=state.get("response_text", ""),
                model_id=state.get("model_id", ""),
                latency_ms=total_latency,
                # ... full set of fields ...
            )
        except Exception:
            pass
        return {"latency_ms": total_latency}
    return log_interaction
```

### 17.6  Testing the Graph

The graph is testable end-to-end without any robot:

```python
import asyncio
from omnillm.gateway import LLMGateway
from omnillm.rag import RAGPipeline
from omnillm.hri import build_hri_graph

async def main():
    gw = LLMGateway()
    rag = RAGPipeline(gateway=gw)
    rag.index_directory("knowledge_base/")
    graph = build_hri_graph(gateway=gw, rag=rag)

    result = await graph.ainvoke({
        "utterance":      "Where is Room 305?",
        "participant_id": "TEST",
        "session_id":     "test-1",
        "condition":      "C",
        "rag_enabled":    True,
    })
    print(result["response_text"])
    print(result["robot_action"])

asyncio.run(main())
```

\newpage

## Chapter 18 — `hri/experiment.py` — Conditions, Sessions, Counterbalancing

> **⚡ AT A GLANCE.** Defines the five experimental conditions A–E as
> dataclasses, manages participant sessions (UUIDs, start/end times,
> per-task logs), and stores per-condition `ConditionConfig` objects
> describing which model, RAG state, council, and routing strategy each
> condition uses.

### 18.1  The `ExperimentCondition` Enum

A simple string enum:

```python
class ExperimentCondition(str, Enum):
    A = "A"  # Fixed Cloud LLM (GPT-4o-mini)
    B = "B"  # Fixed Local LLM (Llama3:8b via Ollama)
    C = "C"  # Smart-Routed (per task type)
    D = "D"  # Consensus (3-model council)
    E = "E"  # RAG-Off Control (same as A but RAG=off)
```

### 18.2  The `ConditionConfig` Dataclass

Each condition has a configuration object:

```python
@dataclass
class ConditionConfig:
    condition:          ExperimentCondition
    model_id:           str | None        # None = dynamic (C/D)
    rag_enabled:        bool
    use_consensus:      bool = False
    use_smart_routing:  bool = False
    council_models:     list[str] = field(default_factory=list)
    description:        str = ""
```

The five default configs are wired up at module load:

| Cond | model_id | RAG | smart_routing | consensus |
|------|----------|-----|---------------|-----------|
| A | `openai-gpt4o-mini` | ✓ | — | — |
| B | `llama3-8b-local` | ✓ | — | — |
| C | None (dynamic) | ✓ | ✓ | — |
| D | None (dynamic) | ✓ | — | ✓ (gpt4o-mini + claude-haiku + gemini-flash) |
| E | `openai-gpt4o-mini` | ✗ | — | — |

### 18.3  The `ParticipantSession` Dataclass

A live record of one participant's session under one condition:

```python
@dataclass
class ParticipantSession:
    session_id:           str
    participant_id:       str
    condition:            ExperimentCondition
    condition_config:     ConditionConfig
    start_time:           str = ...   # ISO8601
    end_time:             str | None = None
    task_log:             list[dict] = []
    questionnaire_scores: dict[str, float] = {}
    notes:                str = ""

    def complete(self):
        self.end_time = datetime.now(timezone.utc).isoformat()

    def log_task(self, task_record):
        task_record.setdefault("timestamp", ...)
        self.task_log.append(task_record)

    def to_dict(self): ...
```

### 18.4  The `ExperimentManager`

The manager creates sessions, returns config for any condition, and provides
filters for analysis:

```python
manager = ExperimentManager()
session = manager.create_session("P001", "C")
print(session.condition_config.use_smart_routing)   # True
session.log_task({"task_type": "info_retrieval",
                  "utterance": "What time does the lab open?", ...})
session.complete()

# Analysis filters
manager.get_sessions_by_participant("P001")
manager.get_sessions_by_condition("C")
manager.summarise()           # totals, per-condition counts
manager.export_data()         # list of dicts for stats
```

### 18.5  Counterbalancing

The current implementation does **not** automatically generate Latin-square
condition orders — that's typically driven by a spreadsheet during
experiment planning. The manager simply tags each session with the
condition the experimenter chose, and the analysis step (R, SPSS, JASP)
handles the within-subjects ANOVA / Friedman test on the exported data.

If you want automated counterbalancing, you can add an
`assigned_conditions` method that returns a Latin-square slice for a given
participant index — but in practice, with N = 15–25 participants, manually
managing the order in a CSV is faster than coding it.

\newpage

## Chapter 19 — `robotics/` — Bridges, Gestures, Whisper

> **⚡ AT A GLANCE.** This sub-package contains everything that talks to a
> robot. The abstract `RobotBridge` defines the interface; concrete
> implementations exist for Pepper (`pepper.py`), NAO (`nao.py`), and Buddy
> (`buddy.py`). `gesture_planner.py` maps task type + response text →
> gesture name + LED hex. `whisper_stt.py` wraps OpenAI Whisper for both
> local and API backends.

### 19.1  The Abstract Bridge

```python
class RobotBridge(ABC):
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

The `RobotAction` dataclass is the universal command:

```python
@dataclass
class RobotAction:
    speech:      str = ""
    gesture:     str | None = None
    movement:    dict | None = None     # {direction, speed, distance_m}
    emotion_led: str | None = None      # "#00FF00" hex
    nav2_goal:   dict | None = None     # {position, orientation}
    metadata:    dict = field(default_factory=dict)
```

This is the **boundary between brain and body**. The brain produces a
`RobotAction`. The body (one of the bridge implementations) executes it.

### 19.2  The Pepper Bridge

| Bridge | Robot | Transport | NAOqi Python 2.7? |
|--------|-------|-----------|-------------------|
| `PepperBridge` | Pepper | HTTP to NAOqi bridge server | Yes (separate process) |

Earlier drafts of this codebase shipped two additional bridges
(`NAOBridge` for the smaller NAO robot, `BuddyBridge` for the Android-
based Buddy companion). They were removed to keep the surface area
focused on the platform actually used in the experiments. The bridge
interface (`omnillm/robotics/bridge.py`) is unchanged, so adding a new
robot back later is a one-file exercise.

### 19.3  Why HTTP to NAOqi (Not Direct)?

You might think "the AI server could `import naoqi` and call NAOqi
directly". This does not work because:

- **NAOqi is Python 2.7 only.**
- **Modern AI libraries (LangGraph, LiteLLM) require Python 3.11+.**
- **You cannot import both into the same Python process.**

So the AI server (Python 3) HTTPs into a small Flask process (Python 2.7)
running on or near the robot. The Python 2.7 side imports `naoqi` and
performs the actual hardware calls. See Chapter 26 for the full bridge
discussion.

### 19.4  `gesture_planner.py`

A small but high-leverage file. Three priority levels, in order:

1. **Direction patterns** (only for navigation tasks). If the response says
   "on your left", the gesture is `point_left`. Direct mapping wins over
   everything else.
2. **Content keywords**. "hello/hi/welcome" → `wave`. "goodbye" →
   `wave_goodbye`. "thinking/let me check" → `think`. "sorry/don't know"
   → `confused`. "absolutely/certainly/yes" → `nod`.
3. **Task-type defaults**. info_retrieval → `nod`. navigation →
   `point_forward`. social_conversation → `wave`. multilingual → `nod`.

Each gesture also carries a default LED colour:

| Gesture | LED |
|---------|-----|
| wave / nod / happy | `#00FF88` (friendly green) |
| wave_goodbye | `#FF8800` (warm orange) |
| point_* | `#00AAFF` (calm blue, navigation mode) |
| show_tablet | `#FFFFFF` (white) |
| think | `#FFFF00` (yellow) |
| confused | `#FF4400` (red-orange) |
| neutral | `#44AAFF` (default blue) |

### 19.5  `whisper_stt.py` — Local vs API

Two backends, same interface:

```python
stt = WhisperSTT(backend="local", model_size="base")
stt = WhisperSTT(backend="api")

text = await stt.transcribe(wav_bytes)
```

| Backend | Cost | Privacy | Performance | Install |
|---------|------|---------|-------------|---------|
| local | $0 | private | needs a GPU for "base" or larger | `pip install openai-whisper` |
| api | ~$0.006/min | sent to OpenAI | fast on any hardware | `pip install openai` + key |

Local Whisper sizes (in trade-off order):

| Size | RAM | Speed | Quality |
|------|-----|-------|---------|
| tiny | ~1 GB | fastest | lowest |
| base | ~1.5 GB | fast | good (default) |
| small | ~2 GB | moderate | better |
| medium | ~5 GB | slow | very good |
| large-v3 | ~10 GB | slowest | best |

For Pepper interactions, **base** is usually the right default — accurate
enough on simple lab utterances, fast enough to fit in the latency budget.

\newpage

## Chapter 20 — `server/app.py` — The Flask AI Server

> **⚡ AT A GLANCE.** Flask app with six endpoints. On startup it loads
> `config/models.yaml`, indexes `knowledge_base/`, and lazily compiles the
> LangGraph pipeline. `POST /interact` is the main endpoint — accepts audio
> or text, runs the graph, returns the `RobotAction` JSON. Falls back to
> `_fallback_interact` if LangGraph is not installed.

### 19.1 — Where the Server Sits

This is the **central nervous system** of the running project:

```
                     [.env file]   [config/models.yaml]   [knowledge_base/]
                          │                │                    │
                          ▼                ▼                    ▼
                  ┌────────────────────────────────────────────────┐
                  │   server/app.py  (Flask, Python 3.11+)         │
                  │   Listens on http://0.0.0.0:5000               │
                  │                                                │
                  │   On startup:                                  │
                  │     • LLMGateway()                             │
                  │     • RAGPipeline().index_directory(KB)        │
                  │     • ExperimentLogger()                       │
                  │     • build_hri_graph()  (lazy)                │
                  └────────────────────────────────────────────────┘
                          │                                  ▲
                          │ Pepper POSTs /interact           │
                          ▼                                  │
                  ┌────────────┐                       ┌──────────────┐
                  │  Pepper    │                       │  Operator/   │
                  │  NAOqi cli │                       │  curl client │
                  │  (Py 2.7)  │                       │  (text mode) │
                  └────────────┘                       └──────────────┘
```

### 20.2  The `create_app()` Factory

The whole Flask app is built by a factory function — useful for testing
and for `gunicorn`:

```python
def create_app(knowledge_base_dir=None, default_model=None,
               enable_rag=True, log_to_file=None):
    from flask import Flask, jsonify, request

    app = Flask(__name__)

    # Configuration via env vars, with sensible defaults
    _default_model = (default_model
        or os.getenv("OMNILLM_DEFAULT_MODEL", "openai-gpt4o-mini"))
    _kb_dir = Path(knowledge_base_dir
        or os.getenv("OMNILLM_KNOWLEDGE_BASE",
                     str(Path(__file__).parent.parent.parent / "knowledge_base")))

    # Initialise components
    gateway = LLMGateway()
    exp_logger = ExperimentLogger()
    rag = None
    if enable_rag:
        rag = RAGPipeline(gateway=gateway, model_id=_default_model)
        _load_knowledge_base(rag, _kb_dir)

    # Lazy LangGraph build (so tests don't need it)
    _graph = None
    def _get_graph():
        nonlocal _graph
        if _graph is None:
            try:
                from omnillm.hri.agent_graph import build_hri_graph
                _graph = build_hri_graph(gateway=gateway, rag=rag,
                                         logger=exp_logger,
                                         default_model=_default_model)
            except ImportError:
                logger.warning("LangGraph not installed — falling back.")
        return _graph

    # ... endpoints registered below ...

    return app
```

### 20.3  The `/interact` Endpoint, Annotated

This is the most important endpoint:

```python
@app.route("/interact", methods=["POST"])
def interact():
    data = request.get_json(force=True) or {}

    utterance      = data.get("text", "")
    audio_b64      = data.get("audio", "")
    participant_id = data.get("participant_id", "unknown")
    session_id     = data.get("session_id", "")
    condition      = data.get("condition", "A")
    rag_enabled    = bool(data.get("rag_enabled", True) and rag is not None)

    if not utterance and not audio_b64:
        return jsonify({"error": "Provide 'text' or 'audio' field"}), 400

    audio_bytes = base64.b64decode(audio_b64) if audio_b64 else b""

    graph = _get_graph()
    if graph is not None:
        state = {
            "utterance":      utterance,
            "audio_bytes":    audio_bytes,
            "participant_id": participant_id,
            "session_id":     session_id,
            "condition":      condition,
            "rag_enabled":    rag_enabled,
            "model_id":       _default_model,
        }
        result = _run_async(graph.ainvoke(state))
        return jsonify(result.get("robot_action",
                                  {"speech": result.get("response_text", "")}))

    # Fallback if LangGraph not installed
    return _fallback_interact(...)
```

### 20.4  The `_run_async` Helper

Flask is sync; LangGraph is async. The bridge:

```python
def _run_async(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()
```

A new event loop per request keeps the request-handling thread isolated.
For a higher-throughput deployment you would use an ASGI server (FastAPI +
uvicorn) instead — but for a single-robot HRI study, this is plenty.

### 20.5  The Other Endpoints

| Endpoint | Purpose | Notes |
|----------|---------|-------|
| `GET /health` | Liveness probe | returns `{status: "ok", version: ...}` |
| `GET /status` | Configuration dump | model list, RAG flag, KB path, etc. |
| `POST /transcribe` | STT only | for clients that do their own classification |
| `POST /evaluate` | Submit questionnaire | logged as a special interaction |
| `GET /export` | Dump all logs as JSON | used by experimenter at study end |

### 20.6  Running the Server

From the command line:

```bash
python -m omnillm.server.app                 # localhost:5000
python -m omnillm.server.app --host 0.0.0.0 --port 5000   # accept LAN
python -m omnillm.server.app --no-rag        # disable RAG (for debugging)
python -m omnillm.server.app --model gemini-flash         # change default
python -m omnillm.server.app --kb /path/to/my-kb          # custom KB
python -m omnillm.server.app --debug         # Flask debug mode
```

For production-ish deployment:

```bash
gunicorn 'omnillm.server.app:create_app()' --bind 0.0.0.0:5000 --workers 1
```

> ⚠️ **Use `--workers 1`** when serving a single robot. Multiple workers do
> not share the in-memory ChromaDB collection, the experiment logger, or the
> compiled LangGraph instance. Multiple workers would mean inconsistent
> state across requests.

\newpage

## Chapter 21 — `server/naoqi_client.py` — The Python 2.7 Side

> **⚡ AT A GLANCE.** This is the **only Python 2.7 file** in the project.
> It runs on or near Pepper, imports `qi` or `naoqi`, captures audio,
> POSTs it to the AI server over HTTP, receives the `RobotAction` JSON,
> and executes speech / gesture / LED on the robot. Falls back to
> "simulation mode" if NAOqi is not installed — useful for testing on a
> non-NAOqi machine.

### 21.1  Why Python 2.7

Pepper's NAOqi SDK is locked to Python 2.7. There is no Python 3 port that
runs all NAOqi services. SoftBank announced and abandoned a Python 3
binding called `qi 3.1.5` but several core services are broken in it
(touch detection, audio callbacks). For production, **assume Python 2.7**.

### 21.2  Two-Process Architecture

```
[ Pepper hardware ]   ←→   [ naoqi_client.py (Python 2.7) ]
                                    ↓ HTTP
                           [ server/app.py (Python 3.x) ]
                                    ↓
                              LangGraph, RAG, LiteLLM
```

The Python 2.7 process is **deliberately small**. It does I/O with the
robot and HTTP with the server. It does not import any AI library.
Everything that *could* break stays on the Python 3 side.

### 21.3  The Class Skeleton

```python
class PepperNAOqiClient(object):
    def __init__(self, robot_ip, robot_port, server_ip, server_port,
                 participant_id, condition):
        self.robot_ip       = robot_ip
        self.robot_port     = robot_port
        self.server_url     = "http://{}:{}".format(server_ip, server_port)
        self.participant_id = participant_id
        self.condition      = condition
        self.session_id     = str(uuid.uuid4())

        self._app             = None
        self._audio_device    = None
        self._animated_speech = None
        self._motion          = None
        self._leds            = None
        self._tablet          = None
        self._behavior        = None
        self._face_detection  = None
        self._connected       = False

    def connect(self): ...
    def run(self): ...
    def _interaction_loop(self): ...
    def _record_audio(self, duration_seconds=5): ...
    def _send_audio(self, audio_bytes): ...
    def _send_text(self, text): ...
    def _execute_action(self, action): ...
    def _speak(self, text): ...
    def _set_leds(self, hex_color): ...
    def _run_behavior_async(self, behavior_name): ...
    def _cleanup(self): ...
```

### 21.4  Connecting via NAOqi

```python
def connect(self):
    if not NAOQI_AVAILABLE:
        print("[SIM] NAOqi not available — simulation mode")
        self._connected = True
        return True
    try:
        self._app = qi.Application(["PepperClient",
            "--qi-url={}:{}".format(self.robot_ip, self.robot_port)])
        self._app.start()
        session = self._app.session

        self._audio_device    = session.service("ALAudioDevice")
        self._animated_speech = session.service("ALAnimatedSpeech")
        self._motion          = session.service("ALMotion")
        self._leds            = session.service("ALLeds")
        self._tablet          = session.service("ALTabletService")
        self._behavior        = session.service("ALBehaviorManager")
        self._face_detection  = session.service("ALFaceDetection")

        self._motion.wakeUp()    # turns on stiffness — must happen before any move
        self._connected = True
        return True
    except Exception as exc:
        print("[ERR] Failed to connect: {}".format(exc), file=sys.stderr)
        return False
```

### 21.5  The Main Loop

```python
def run(self):
    if not self._connected and not self.connect():
        return
    self._speak("Hello! I am Pepper, powered by OmniLLM. How can I help?")
    try:
        while True:
            self._interaction_loop()
    except KeyboardInterrupt:
        pass
    finally:
        self._cleanup()

def _interaction_loop(self):
    audio_bytes = self._record_audio(duration_seconds=5)
    if not audio_bytes:
        return
    response = self._send_audio(audio_bytes)
    if response is None:
        self._speak("I'm sorry, I could not connect to my AI brain.")
        return
    self._execute_action(response)
```

### 21.6  Executing the RobotAction

```python
def _execute_action(self, action):
    speech    = action.get("speech", "")
    gesture   = action.get("gesture")
    led_color = action.get("emotion_led")

    if led_color:
        self._set_leds(led_color)
    if gesture and gesture in GESTURE_TO_BEHAVIOR:
        self._run_behavior_async(GESTURE_TO_BEHAVIOR[gesture])
    if speech:
        self._speak(speech)

def _speak(self, text):
    config = {"bodyLanguageMode": "contextual"}
    self._animated_speech.say(str(text), config)

def _set_leds(self, hex_color):
    hex_color = hex_color.lstrip("#")
    r, g, b = (int(hex_color[i:i+2], 16) / 255.0 for i in (0, 2, 4))
    self._leds.fadeRGB("FaceLeds", r, g, b, 0.3)
```

The `bodyLanguageMode: "contextual"` setting is what makes Pepper move its
arms and head while speaking. Without it, you get a stiff, talking-head
robot. Chapter 23 explains why this matters.

### 21.7  The `GESTURE_TO_BEHAVIOR` Dictionary

This is the bridge between OmniLLM's gesture *names* (e.g. `"point_left"`)
and the actual NAOqi *behaviour paths* (e.g.
`"animations/Stand/Gestures/Explain_8"`):

```python
GESTURE_TO_BEHAVIOR = {
    "wave":          "animations/Stand/Gestures/Hey_1",
    "bow":           "animations/Stand/Gestures/BowShort_1",
    "wave_goodbye":  "animations/Stand/Gestures/Farewells_1",
    "point_left":    "animations/Stand/Gestures/Explain_8",
    "point_right":   "animations/Stand/Gestures/Explain_7",
    "point_forward": "animations/Stand/Gestures/Explain_1",
    "point_up":      "animations/Stand/Gestures/Explain_6",
    "show_tablet":   "animations/Stand/Gestures/ShowTablet_1",
    "nod":           "animations/Stand/Emotions/Positive/Enthusiastic_1",
    "think":         "animations/Stand/Emotions/Neutral/Thinking_1",
    "happy":         "animations/Stand/Emotions/Positive/Happy_4",
    "confused":      "animations/Stand/Emotions/Negative/Confused_1",
}
```

If you install custom Choregraphe behaviours, add them here.

### 21.8  Audio Capture — Currently a Placeholder

Look closely at `_record_audio`:

```python
def _record_audio(self, duration_seconds=5):
    if not NAOQI_AVAILABLE or self._audio_device is None:
        return b""
    try:
        self._audio_device.setClientPreferences(
            "OmniLLMCapture", 16000, 3, 0   # 16 kHz, front mic, deinterleaved=0
        )
        time.sleep(duration_seconds)
        # In real implementation: use ALAudioRecorder or callback-based capture
        return b""    # ← placeholder
    except Exception as exc:
        return b""
```

This is **deliberately incomplete** in the current source. To make it
production-ready you have two options:

1. **ALAudioRecorder** — record to a file on Pepper, SCP it back to your PC,
   then base64-encode and send. Simpler but adds a per-utterance file
   transfer.
2. **`processRemote` callback** — subclass `ALModule`, implement
   `processRemote(nbChannels, nbSamples, timeStamp, inputBuffer)`,
   accumulate raw int16 samples in a numpy array, write a WAV header,
   send. Real-time but requires more NAOqi knowledge.

For the present project, the workaround during development is to use the
**text-mode** path (`_send_text`) instead of audio capture.

### 21.9  Running the Client

```bash
# Set the pynaoqi path so Python 2.7 finds NAOqi
set PYTHONPATH=C:\pynaoqi\pynaoqi-python2.7-2.5.5.5-win32-vs2013\lib;%PYTHONPATH%

# Run
C:\Python27\python.exe omnillm/server/naoqi_client.py \
    --robot-ip 192.168.1.100 \
    --server-ip localhost \
    --participant P001 \
    --condition C
```

\newpage

## Chapter 22 — `utils/` — Logging, Cost Tracking, Questionnaires, Export

> **⚡ AT A GLANCE.** Four small utility modules. `cost_tracker.py` accumulates
> USD per model per session. `experiment_logger.py` records every HRI
> interaction with full metadata. `questionnaire.py` defines the 1–7 Likert,
> Godspeed, pairwise, and observer dataclasses. `export.py` writes CSV,
> JSON, or Markdown reports.

### 22.1  `cost_tracker.py`

A flat list of `_Record` objects with summarisation methods:

```python
tracker = CostTracker()
tracker.record("openai-gpt4o", input_tokens=500, output_tokens=300,
               cost_usd=0.0045, session_id="eval-1")
print(tracker.get_total_cost())          # 0.0045
print(tracker.get_cost_by_model())       # {'openai-gpt4o': 0.0045}
print(tracker.get_cost_by_session())     # {'eval-1': 0.0045}
print(tracker.get_token_usage())         # {'openai-gpt4o': {'input': 500, 'output': 300, 'total': 800}}
tracker.save("results/costs.json")
```

The CLI command `omnillm costs` builds and prints a Rich table from this
tracker.

### 22.2  `experiment_logger.py` — The Star of the Sub-package

This file produces the dataset that the entire experiment is about. Every
interaction creates an `InteractionRecord`:

```python
@dataclass
class InteractionRecord:
    session_id:        str
    participant_id:    str
    condition:         str          # "A"–"E"
    task_type:         str          # T1–T4
    utterance:         str
    response:          str
    model_id:          str
    latency_ms:        float = 0.0
    input_tokens:      int   = 0
    output_tokens:     int   = 0
    cost_usd:          float = 0.0
    rag_enabled:       bool  = False
    rag_faithfulness:  float = -1.0   # -1 = not scored
    rag_chunk_count:   int   = 0
    judge_score:       float = -1.0
    task_success:      bool | None = None
    language:          str   = "en"
    gesture_used:      str | None = None
    timestamp:         str   = ...    # ISO8601
    notes:             str   = ""
```

The logger has a `log_interaction(...)` method called from the LangGraph's
final node, plus convenience methods for analysis:

```python
logger.get_records(condition="C")
logger.get_records(model_id="claude-haiku")
logger.get_summary()       # by_model, by_condition, by_task_type
logger.save("results.json")
logger.save_csv("results.csv")
logger.load("results.json")
```

The CSV export is **flat** — every interaction is one row, every field a
column. This is the format that R, SPSS, and JASP love.

### 22.3  `questionnaire.py` — Four Dataclasses

| Dataclass | Scale | Items | When |
|-----------|-------|-------|------|
| `InteractionQuestionnaire` | 1–7 Likert | 5 (accuracy, naturalness, trust, gesture, speed) | After each condition |
| `GodspeedResponse` | 1–5 | 5 subscales (anthropomorphism, animacy, likeability, perceived intelligence, safety) | After each condition |
| `PairwisePreference` | A / B / tie | "Which Pepper did you prefer?" | End of session |
| `ObserverRating` | 1–5 + counts | gesture-sync quality, breakdown count, task completion | Live during interaction |

A typical post-session collection flow:

```python
collector = QuestionnaireCollector()
collector.add_interaction_response(InteractionQuestionnaire(
    session_id="s1", participant_id="P001", condition="C",
    accuracy=6, naturalness=5, trust=6,
    gesture_appropriateness=5, response_speed=7,
))
collector.add_godspeed(GodspeedResponse(
    session_id="s1", participant_id="P001", condition="C",
    anthropomorphism=3.2, animacy=3.4, likeability=4.1,
    perceived_intelligence=4.0, perceived_safety=4.5,
))
collector.add_pairwise_preference(PairwisePreference(
    session_id="s1", participant_id="P001",
    condition_a="A", condition_b="C", preferred="C",
))

print(collector.summary_by_condition())     # mean Likert per condition
print(collector.pairwise_win_rates())       # for ELO updates

collector.save("results/questionnaires.json")
collector.to_csv("results/questionnaires.csv")
```

### 22.4  `export.py` — Three Output Formats

```python
exporter = ResultExporter()
exporter.to_json(results, "results/eval.json")
exporter.to_csv(results, "results/eval.csv")
exporter.to_markdown(results, "results/eval.md")
table = exporter.to_rich_table(results)   # for terminal display
stats = exporter.get_summary_stats(results)
```

The CLI command `omnillm export --format csv --input ... -o ...` is just a
thin wrapper around these methods.

\newpage
