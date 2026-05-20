\newpage

# Appendix K — Walkthroughs, Feature Catalogue, and Execution Plans

> *This appendix is for the reader who wants concrete, granular detail. Five sections: a line-by-line trace of one question through the code, a complete worked first-session example, the eight evaluation axes enumerated, a complete feature reference catalogue, and a one-month study execution plan distinct from the 13-week build plan in Chapter 22.*

\newpage

## K.1 — Reading the Code: A Single Question's Journey, Line by Line

> *Take one user input — "Where is Room 305?" — and trace it through every Python function that touches it. If you can read this section top to bottom and recognise every step, you understand OmniLLM.*

### K.1.1 — The Scenario

You are running:

```powershell
# Terminal 1
python -m omnillm.server.app

# Terminal 2 (drives the AI server with curl)
curl -X POST http://localhost:5000/interact `
  -H "Content-Type: application/json" `
  -d '{"text": "Where is Room 305?",
       "participant_id": "DEMO",
       "session_id": "demo-1",
       "condition": "C",
       "rag_enabled": true}'
```

What happens between the `curl` and the JSON response?

### K.1.2 — Stage 1 — Flask Receives the Request

**File: `omnillm/server/app.py`, function `interact()`**

Flask matches `POST /interact` to a Python function. The body is parsed from JSON into a dict:

```python
@app.route("/interact", methods=["POST"])
def interact():
    data = request.get_json(force=True) or {}
    utterance = data.get("text", "")            # "Where is Room 305?"
    audio_b64 = data.get("audio", "")           # "" (text-only)
    participant_id = data.get("participant_id", "unknown")
    session_id = data.get("session_id", "")
    condition = data.get("condition", "A")
    rag_enabled = bool(data.get("rag_enabled", True) and rag is not None)
```

**Python notes for beginners:**

- `@app.route(...)` is a **decorator**. It wraps the function below it with Flask's URL routing logic. The function is still callable directly, but Flask also knows "if a `POST /interact` comes in, call `interact`".
- `data.get("text", "")` returns `data["text"]` if it exists, otherwise `""`. This is **safer than `data["text"]`** because the latter raises `KeyError` if the field is missing.

### K.1.3 — Stage 2 — Resolve the Per-Condition Model, Hand Off to LangGraph

**Same file, same function (continued)**

```python
audio_bytes = base64.b64decode(audio_b64) if audio_b64 else b""

# Resolve the per-condition model BEFORE invoking the graph.
from omnillm.hri.experiment import CONDITION_CONFIGS, ExperimentCondition
cond_cfg = CONDITION_CONFIGS.get(ExperimentCondition(condition))
effective_model = (cond_cfg.model_id if cond_cfg and cond_cfg.model_id
                                     else _default_model)

graph = _get_graph()
if graph is not None:
    state = {
        "utterance": utterance,
        "audio_bytes": audio_bytes,
        "participant_id": participant_id,
        "session_id": session_id,
        "condition": condition,
        "rag_enabled": rag_enabled,
        "model_id": effective_model,             # <-- the May-2026 fix
    }
    result = _run_async(graph.ainvoke(state))
    return jsonify(result.get("robot_action",
                              {"speech": result.get("response_text", "")}))
```

**What's happening:**

- The condition lookup ensures Condition B's `llama3-8b-local` actually reaches the LLM call inside the graph (the May 2026 fix from Chapter 12).
- `_get_graph()` returns a compiled LangGraph DAG. The first call takes ~10 seconds (imports + compile); subsequent calls are instant.
- `graph.ainvoke(state)` runs the **entire graph asynchronously** starting from the `state` dict. Each node reads keys it cares about and writes back updates.
- `_run_async(coro)` is a tiny helper that creates a fresh event loop per request — needed because Flask is synchronous but LangGraph is asynchronous.

### K.1.4 — Stage 3 — Inside the Graph (Node by Node)

The compiled graph:

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

#### Node 1 — `transcribe_audio`

```python
async def transcribe_audio(state: dict) -> dict:
    audio = state.get("audio_bytes", b"")
    if not audio:
        return {"_start_time": time.monotonic()}     # text-only mode
    from omnillm.robotics.whisper_stt import WhisperSTT
    stt = WhisperSTT()
    utterance = await stt.transcribe(audio)
    return {"utterance": utterance, "_start_time": time.monotonic()}
```

Because we passed `text="Where is Room 305?"` (no audio), the node just records the start time and passes through. `_start_time` is what `log_interaction` later subtracts to compute end-to-end latency.

#### Node 2 — `detect_language`

```python
async def detect_language(state: dict) -> dict:
    utterance = state.get("utterance", "")
    from omnillm.hri.language_detector import LanguageDetector
    detector = LanguageDetector()
    result = detector.detect(utterance)
    return {"detected_language": result.language_code}
```

The detector inspects the script and word frequencies and returns `"en"`. Almost any English text is identified in under 10 ms by Tier 1 (Unicode script check) — no LLM call required.

#### Node 3 — `classify_task`

```python
async def classify_task(state: dict) -> dict:
    utterance = state.get("utterance", "")
    language = state.get("detected_language", "en")
    from omnillm.hri.classifier import HRITaskClassifier
    classifier = HRITaskClassifier()
    result = classifier.classify(utterance, detected_language=language)
    return {"task_type": result.task_type.value,
            "task_confidence": result.confidence}
```

The classifier hits the regex `\broom\s+\d+\b` ("Room 305") and the keyword `where`. Score for **navigation** wins → returns `{"task_type": "navigation", "task_confidence": 0.95}`.

#### Conditional Edge — Pick the Branch

```python
def _route_by_task_type(state: dict) -> str:
    task_type = state.get("task_type", "info_retrieval")
    condition = state.get("condition", "A")
    rag_enabled = state.get("rag_enabled", True)
    if condition == "E":
        return "direct_llm"                       # E always skips RAG
    routing = {
        "info_retrieval":      "rag" if rag_enabled else "direct_llm",
        "navigation":          "nav_rag" if rag_enabled else "direct_llm",
        "social_conversation": "direct_llm",
        "multilingual":        "multilingual_llm",
    }
    return routing.get(task_type, "direct_llm")
```

`task_type="navigation"` + `rag_enabled=True` + `condition="C"` → returns `"nav_rag"`. LangGraph dispatches to the `nav_rag` node.

#### Node 4 — `nav_rag` (RAG + Gesture Planner)

```python
async def run_nav_rag(state: dict) -> dict:
    utterance = state.get("utterance", "")
    target_model = state.get("model_id")
    rag_resp = await rag.query(utterance, model_id=target_model)
    from omnillm.robotics.gesture_planner import GesturePlanner
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

1. Convert "Where is Room 305?" into an embedding vector via sentence-transformers.
2. Search ChromaDB for the 4 most similar chunks from the DIBRIS knowledge base.
3. Build an augmented prompt: `system + "Use only this context: ..." + user`.
4. Call `gateway.query(model_id, messages)` — this returns the LLM's answer.
5. (Optional) Score the answer's faithfulness with a judge LLM.

The result is something like:

```
"Room 305 is on the third floor of the DIBRIS building. Take the
elevator on your left, then turn left at the corridor."
```

Then `planner.plan("navigation", answer)` sees the word "left", picks gesture `point_left`, picks LED `#00AAFF` (calm navigation blue).

#### Node 5 — `smart_router`

For `condition="C"`, the router fires:

```python
from omnillm.router import SmartRouter, RoutingStrategy
router = SmartRouter()
decision = router.route_for_hri_task(
    hri_task_type="navigation",
)
target = decision.model_id     # e.g. "openai-gpt4o-mini" per hri_task_routing
resp = await gateway.query(target, messages)
return {"response_text": resp.content, "model_id": resp.model_id, ...}
```

The router reads `config/models.yaml`'s `hri_task_routing.navigation`. The answer overrides what `nav_rag` produced. (For conditions A, B, E the smart_router node is a no-op — the previous answer wins.)

#### Node 6 — `generate_action_plan`

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

#### Node 7 — `log_interaction`

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
        # ...
    )
    return {"latency_ms": total_latency}
```

The logger appends an `InteractionRecord` to disk (JSON-Lines) and to the in-memory list.

### K.1.5 — Stage 4 — Flask Returns the JSON

Back in `app.py`:

```python
return jsonify(result.get("robot_action", ...))
```

The dict is serialised to JSON and returned with HTTP 200:

```json
{
  "speech": "Room 305 is on the third floor of the DIBRIS building. Take the elevator on your left, then turn left at the corridor.",
  "gesture": "point_left",
  "emotion_led": "#00AAFF",
  "metadata": {
    "task_type": "navigation",
    "model_id":  "openai-gpt4o-mini",
    "rag_enabled": true
  }
}
```

### K.1.6 — Stage 5 — What Pepper Does With It

If a real Pepper is at the other end, `naoqi_client.py` would:

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
- `ALBehaviorManager.runBehavior("animations/Stand/Gestures/Explain_8")` starts the point-left gesture in a non-blocking thread.
- `ALAnimatedSpeech.say(speech, {"bodyLanguageMode": "contextual"})` speaks the answer with synchronised arm motion.

### K.1.7 — The Whole Picture

That is one question, end-to-end. Sub-2-second latency (~1.4–1.6 s typical for Condition A/C), all of it logged, every model swap configurable, every step testable in isolation.

If you can find the code for each step in the repository without re-reading this section, you understand OmniLLM.

\newpage

## K.2 — A Complete First Experimental Session — Worked Example

> *A pretend participant P003 walks into the DIBRIS / Sgorbissa lab. We run them through all five conditions of one slot of the Latin square. Every command you'd type, every JSON you'd see, every questionnaire score you'd enter — front to back.*

### K.2.1 — Before the Participant Arrives

```powershell
# 0. Pre-flight check
cd C:\Users\akshi\OneDrive\Desktop\OmniLLM
.\venv\Scripts\Activate.ps1

omnillm models                       # all 19 models load
pytest tests/ -q | Select-Object -Last 3   # 289 tests pass

# 1. Make sure Pepper is awake (real robot at DIBRIS)
C:\Python27\python.exe -c "from naoqi import ALProxy; ALProxy('ALMotion','192.168.1.100',9559).wakeUp()"

# 2. Start the AI server (Terminal 1)
python -m omnillm.server.app --host 0.0.0.0 --port 5000
```

Expected server log lines:

```
INFO:omnillm.rag.pipeline:Indexed 12 chunks from lab_info.txt
INFO:omnillm.rag.pipeline:Indexed 15 chunks from faq.txt
INFO:omnillm.rag.pipeline:Knowledge base loaded -- 49 total chunks
 * Running on all addresses (0.0.0.0)
 * Running on http://127.0.0.1:5000
```

```powershell
# 3. Start the NAOqi bridge (Terminal 2, Python 2.7)
C:\Python27\python.exe omnillm\server\naoqi_bridge_server.py `
  --robot-ip 192.168.1.100 --robot-port 9559 `
  --bind 0.0.0.0 --bridge-port 6000
```

Confirm both up:

```powershell
curl http://127.0.0.1:5000/status
curl http://127.0.0.1:6000/ping
```

You also have, on the desk:

- 5 paper questionnaire forms (one per condition)
- 1 final pairwise-preference sheet
- 2 consent forms
- 1 GDPR notice
- The Latin-square sheet that says "P003: conditions C, D, E, A, B in that order"

### K.2.2 — Participant Arrives — Briefing (5 minutes)

> *"Thank you for joining. Today you'll talk with Pepper in five different modes. Each mode has four short interactions. After each mode I'll hand you a brief paper questionnaire. The whole session takes about 30 minutes. You can stop at any time without giving a reason. There are no right or wrong answers — we're studying Pepper, not you. Please sign here..."*

Hand over the consent form and GDPR notice. Note demographics: P003 speaks English and Italian.

### K.2.3 — Run the Experiment Driver

```powershell
# Terminal 3
.\venv\Scripts\python.exe scripts\pepper_demo\run_subject_experiment.py `
    --participant P003 `
    --server http://127.0.0.1:5000 `
    --bridge http://127.0.0.1:6000
```

Progress on screen as conditions cycle (abridged):

```
Subject experiment -- participant=P003 session=578b023b
Server: http://127.0.0.1:5000
Robot bridge: http://127.0.0.1:6000

[01/20] C / T1_info_retrieval: What time does the lab open?
    -> The lab opens at 08:30 on weekdays...
    model=openai-gpt4o-mini  path=graph  latency=1430 ms
    robot: ok

[02/20] C / T2_navigation: Where is the Pepper room at DIBRIS?
    -> The Pepper room is at the end of the ground-floor corridor...
    model=openai-gpt4o-mini  path=graph  latency=1590 ms
    robot: ok

[03/20] C / T3_social: Hello Pepper, how are you today?
    -> Hello! I'm feeling bright and cheerful today, thank you!
    model=claude-haiku  path=graph  latency=920 ms
    robot: ok

[04/20] C / T4_multilingual: Ciao Pepper, dove si trova la stazione di Brignole?
    -> Ciao! La stazione di Brignole si trova a Genova...
    model=claude-haiku  path=graph  latency=1980 ms
    robot: ok

  --- [pause for Condition C questionnaire] ---
  Press Enter when ready to continue...
```

You hand the participant the Condition C questionnaire:

```
+-------------------------------------------------------------+
|  CONDITION C   PARTICIPANT P003                              |
|                                                              |
|  Strongly disagree  1  2  3  4  5  6  7  Strongly agree     |
|                                                              |
|  Q1 The robot's answers were accurate.        [_] [_] [_] [X] [_] [_] [_]   -> 4
|  Q2 The robot was natural to talk to.         [_] [_] [_] [_] [_] [X] [_]   -> 6
|  Q3 I trust the information given to me.     [_] [_] [_] [_] [_] [X] [_]   -> 6
|  Q4 The robot's gestures were appropriate.    [_] [_] [_] [_] [X] [_] [_]   -> 5
|  Q5 The robot responded quickly enough.       [_] [_] [_] [_] [_] [X] [_]   -> 6
+-------------------------------------------------------------+
```

P003 ticks 4/6/6/5/6. Continue with D, E, A, B in their assigned order. At each condition boundary, hand the matching questionnaire, collect after ~60 seconds, press Enter.

### K.2.4 — The Pairwise Preference at Session End

After all 20 interactions, ask three verbal questions:

> *"1. Which of the five Peppers did you prefer overall?"*
> *"2. Which one felt most natural to talk to?"*
> *"3. Which one would you most trust to give correct information?"*

P003 answers: "Overall I preferred C. Most natural — also C. Most trustworthy — D, the one that took longer." Record on the final sheet.

This produces seven pairwise records: C wins over A, B, D, E (overall); C wins over A, B, D, E (naturalness); D wins over A, B, C, E (trust). These feed `EloScorer.update_pairwise(...)` later.

### K.2.5 — Save Everything Within the Hour

```powershell
# Outputs are already at:
# results/subject_run_P003_<timestamp>.json
# results/subject_run_P003_<timestamp>.csv

# Move to per-participant folder
New-Item -ItemType Directory -Path "results/by_participant/P003"
Move-Item "results/subject_run_P003_*.json" "results/by_participant/P003/"
Move-Item "results/subject_run_P003_*.csv"  "results/by_participant/P003/"

# Digitise the questionnaires
python -c @'
from omnillm.utils.questionnaire import (
    InteractionQuestionnaire, PairwisePreference, QuestionnaireCollector)
c = QuestionnaireCollector()
c.add_interaction_response(InteractionQuestionnaire(
    session_id="578b023b", participant_id="P003", condition="A",
    accuracy=6, naturalness=5, trust=6,
    gesture_appropriateness=5, response_speed=7))
# ...repeat for B, C, D, E...
c.add_pairwise_preference(PairwisePreference(
    session_id="578b023b", participant_id="P003",
    condition_a="C", condition_b="A", preferred="C"))
# ...etc for all pairwise records...
c.save("results/by_participant/P003/questionnaire.json")
'@
```

### K.2.6 — What the JSON Logs Look Like

A typical `InteractionRecord` row in the JSON file:

```json
{
  "timestamp": "2026-06-12T14:23:51.842Z",
  "session_id": "578b023b-09af-4da3-a047-e742e25c5913",
  "participant_id": "P003",
  "condition": "A",
  "task_type": "info_retrieval",
  "utterance": "What time does the lab open?",
  "response":  "The lab opens at 08:30 on weekdays.",
  "model_id":  "openai-gpt4o-mini",
  "latency_ms": 1437.3,
  "input_tokens": 412,
  "output_tokens": 13,
  "cost_usd": 0.0000687,
  "rag_enabled": true,
  "rag_faithfulness": 0.94,
  "rag_chunk_count": 3,
  "judge_score": 0.91,
  "task_success": true,
  "language": "en",
  "gesture_used": "nod"
}
```

After 15 participants × 5 conditions × 4 tasks, you have **300 such rows** plus 75 questionnaire rows plus ~45 pairwise preferences. That is your dataset.

### K.2.7 — Final Backup Step

```powershell
# Copy results/ to a backup location at the end of every day
Copy-Item -Recurse -Force "results\" "D:\thesis-backup\results-2026-06-12\"
```

Data loss after a participant has gone home is the worst-case scenario in HRI studies. Don't be the person it happens to.

\newpage

## K.3 — The Eight Evaluation Axes (Enumerated)

OmniLLM's built-in benchmark tasks (`tasks/sample_tasks.py`) span eight axes chosen to be **orthogonal**: a model that scores high on one does not necessarily score high on the others. These axes power the `omnillm evaluate` command and the leaderboard categories.

| # | Axis | What it measures | Sample tasks |
|---|------|-----------------|--------------|
| 1 | **Reasoning** | Multi-step logic, mathematics | Bat-and-ball puzzle; syllogism; Gambler's Fallacy |
| 2 | **Knowledge** | Factual accuracy | Capital cities; speed of light; DNA discoverers |
| 3 | **Code** | Generate, debug, explain code | `is_prime`; FizzBuzz; binary search bug |
| 4 | **Instruction Following** | Strict format / constraints | Numbered list of 5; pure JSON output; exact 3 sentences |
| 5 | **Safety** | Refusal of harmful / PII requests | Refuse hacking; refuse misinformation; redact PII |
| 6 | **Robot-Readiness** | Structured JSON for robot control | Generate NAO action plan; parse voice command; ROS2 Nav2 goal |
| 7 | **Latency** | Time-to-first-token | One-sentence greeting; "Answer with only the number" |
| 8 | **Cost-Efficiency** | Quality at minimum tokens | Define "recursion" in one sentence; Yes/No questions |

### K.3.1 — The Three Judge Patterns (Recap)

| Pattern | When to use it | Output |
|---------|----------------|--------|
| **Referenceless (G-Eval)** | No gold answer; open-ended | Score 0–1 + reasoning |
| **Reference-Based** | You know the right answer | Score 0–1 + reasoning |
| **Pairwise** | Comparing two models | Winner: A / B / tie |

### K.3.2 — The Twelve Per-Interaction Metrics (HRI)

Automatically recorded for every Embodied LLM Arena interaction:

1. **Latency** — end-of-utterance to start-of-robot-speech, in ms.
2. **Input tokens** — prompt token count.
3. **Output tokens** — completion token count.
4. **Cost (USD)** — calculated from `models.yaml` pricing.
5. **RAG retrieval scores** — cosine similarity of top-k chunks.
6. **RAG faithfulness** — LLM-as-Judge of grounding (0–1).
7. **Hallucination flag** — word-overlap heuristic.
8. **LLM-as-Judge quality** — referenceless score (0–1, optional).
9. **Language detected** — ISO 639-1 code.
10. **Task classification** — T1/T2/T3/T4 + confidence.
11. **Model used** — the actual `model_id` (matters for Conditions C and D).
12. **Gesture used** — what Pepper actually did.

All twelve fields land in `InteractionRecord` and export cleanly to CSV.

### K.3.3 — Composite Scoring (the `BEST_VALUE` Formula)

```
value = 0.50 * quality + 0.30 * cost_score + 0.20 * latency_score
```

Where:

- `quality` ∈ [0, 1] from LLM-as-Judge or running mean of past evaluations
- `cost_score` = `max(0, 1 - cost / 0.05)` (normalised against $0–$0.05 per query)
- `latency_score` = `max(0, 1 - (latency_ms - 500) / 9500)` (normalised against 500ms–10s)

This is the formula the smart router uses for `BEST_VALUE` strategy. The 50/30/20 weighting was the most stable across all four HRI task types in development; it lives in `_calculate_value_score` and is editable.

\newpage

## K.4 — Complete Feature Reference Catalogue

> *Every shipped feature, organised by category. Use this as a checklist when comparing OmniLLM against another HRI framework, or when answering "what does this project actually do?"*

### K.4.1 — Core LLM Features

- Unified `LLMGateway.query(model_id, messages)` across **19 registered models** from 6+ providers (OpenAI, Anthropic, Google, DeepSeek, Ollama, openai-compatible)
- `LLMGateway.query_multiple(model_ids, messages)` — parallel queries via `asyncio.gather`
- Per-call cost calculation in USD from the `config/models.yaml` registry
- Latency measurement with `time.perf_counter()` high-resolution timer
- Graceful per-call error handling — errors return as `ModelResponse(error=...)` rather than raising
- `litellm.drop_params = True` — automatically strips unsupported parameters (e.g. `temperature` for o-series models)
- Provider prefix routing (`ollama/`, `gemini/`, `anthropic/`, `openai/`)

### K.4.2 — Smart Routing Features

- Six routing strategies: `BEST_QUALITY`, `LOWEST_COST`, `LOWEST_LATENCY`, `BEST_VALUE`, `LOCAL_PREFERRED`, `TASK_TYPE`
- Composite `BEST_VALUE` score (quality 50% + cost 30% + latency 20%)
- Hard constraints: `budget_usd`, `max_latency_ms`
- Fallback model list in `config/models.yaml` (`routing.fallback_models`)
- Per-HRI-task routing via `routing.hri_task_routing` block
- Static default scores in `SmartRouter._DEFAULT_SCORES` for the cold-start case
- Self-updating quality table from past `omnillm evaluate` results
- `route_by_complexity()` — short prompts → cheap model; long → quality model

### K.4.3 — Consensus / Council Features

- Three synthesis strategies: `majority_vote`, `weighted`, `synthesis` (default)
- Default 3-model council (configurable)
- Position-bias mitigation via response shuffling on synthesis
- Graceful per-model degradation (council continues if one model fails)
- Cost-aware: configurable per-call budget cap

### K.4.4 — Evaluation Features (LLM-as-Judge)

- **Referenceless (G-Eval)** — score open-ended responses
- **Reference-Based** — score against a known gold answer
- **Pairwise** — winner: A / B / tie, with position-bias swap-and-aggregate
- 8 evaluation axes (Reasoning, Knowledge, Code, Instruction-Following, Safety, Robot-Readiness, Latency, Cost-Efficiency)
- Configurable judge model (default GPT-4o-mini)
- Used internally by RAG pipeline for faithfulness scoring

### K.4.5 — ELO Scoring Features

- Standard ELO maths (K=32 below 2000, K=16 above)
- Per-category leaderboards: `overall`, `reasoning`, `embodied_hri`, plus the four HRI task types
- `update_pairwise(model_a, model_b, winner, category=...)`
- `leaderboard(category=...)` returns sorted ratings
- Persistent JSON file across runs
- Initial rating 1000 per category

### K.4.6 — RAG Features

- ChromaDB-backed semantic retrieval (HNSW cosine)
- Keyword-search fallback when ChromaDB unavailable
- Document loaders for `.txt`, `.csv`, `.pdf` (via pypdf)
- Recursive character text splitter (chunk_size 512, overlap 64)
- Configurable `top_k` (default 4)
- LLM-as-Judge faithfulness scoring (0–1)
- Lightweight hallucination heuristic (answer-word coverage)
- Per-call `model_id=` override (May 2026 addition)
- Persistent SQLite-backed ChromaDB store

### K.4.7 — HRI Features

- Rule-based task classifier (T1–T4) with optional LLM fallback
- 3-tier language detector: Unicode script, n-gram, langdetect
- `LanguageDetector.recommended_model` per detected language
- 5 experimental conditions (A–E) with declarative `CONDITION_CONFIGS`
- `ParticipantSession` dataclass with UUID session IDs
- `ExperimentManager` for Latin-square assignment (optional)
- Per-condition model resolution at `/interact` endpoint (May 2026 fix)
- Multilingual retry-with-backup-model in T4 node

### K.4.8 — LangGraph Agent Pipeline Features

- 9 nodes, all async
- `_merge_state` wrapper preserves prior fields through every node
- Conditional edge based on `(task_type, condition, rag_enabled)`
- Fully visualisable as Mermaid / Graphviz
- Lazy LangGraph import (server still runs without it via fallback)
- End-to-end latency measurement via `_start_time` field

### K.4.9 — Robot Bridge Features

- Abstract `RobotBridge` ABC with 6 async methods
- Pepper concrete implementation with 3-mode auto-detection (`server` / `direct` / `stub`)
- aiohttp async HTTP client
- Choregraphe virtual-robot port auto-discovery
- Three trigger modes (`text`, `touch`, `vad`) in `naoqi_client.py`
- Face tracking via `ALTracker` (`--track-face`)
- Two topologies (Pepper-polls and AI-server-drives)

### K.4.10 — Robotics Helper Features

- `GesturePlanner` — rule-based (task_type + response_text) → (gesture, LED)
- Direction-pattern regex matching for navigation gestures
- Content-triggered gesture overrides (hello → wave, goodbye → wave_goodbye)
- 7-colour eye-LED palette tied to interaction mode
- Local `WhisperSTT` (privacy-preserving, free, ~700ms on CPU)
- `parse_llm_to_action()` — LLM JSON → `RobotAction`
- `parse_nav2_goal()` — for future ROS2 integration

### K.4.11 — Server Features

- Flask AI server with 6 HTTP endpoints (`/interact`, `/transcribe`, `/evaluate`, `/health`, `/status`, `/export`)
- Stdlib-only NAOqi bridge server (Python 2.7-compatible)
- Three trigger modes in NAOqi client
- Automatic fallback to direct gateway if LangGraph unavailable
- CORS-off by default (same-LAN only)
- Environment-variable-based config (`OMNILLM_DEFAULT_MODEL`, `OMNILLM_KNOWLEDGE_BASE`)

### K.4.12 — Logging / Reporting Features

- `ExperimentLogger` with append-only JSON-Lines persistence
- `InteractionRecord` dataclass — 20 fields per interaction
- `QuestionnaireCollector` — Likert + Godspeed + Pairwise + Observer
- `CostTracker` — per-model running USD spend
- `export.py` — JSON ↔ CSV ↔ Markdown converter
- `summary_by_condition()` for the per-condition Likert means table
- `pairwise_win_rates()` for the ELO updates

### K.4.13 — CLI Features

- `omnillm models` (filterable by cloud/local)
- `omnillm ask` — one or many models or `--all`
- `omnillm route` — six strategies with optional budget/latency constraints
- `omnillm council` — three synthesis strategies
- `omnillm compare` — pairwise with position-bias swap
- `omnillm evaluate` — full 8-axis benchmark sweep
- `omnillm leaderboard` — per-category ELO leaderboard
- `omnillm costs` — per-model spend
- `omnillm export` — CSV / Markdown / JSON

### K.4.14 — Test Suite Features

- 289 tests covering every public function
- All LLM calls mocked — no API keys or real network required
- pytest-asyncio for async test functions
- pytest-mock for the `mocker` fixture
- ~5 second total run-time
- CI-friendly (Linux, macOS, Windows)

### K.4.15 — Documentation Features

- This 250-page book (rebuildable from Markdown via pure-Python pipeline)
- DejaVu-based PDF with Unicode glyph coverage
- 18 chapters + 11 appendices
- Three-reader structure (Owner / Beginner / Academic) consistent across every chapter

\newpage

## K.5 — One-Month Execution Plan (Distinct From the 13-Week Build Plan)

> *Chapter 22 gave a **13-week build plan** for someone replicating OmniLLM from a blank repo. This section gives a **one-month execution plan** for someone whose OmniLLM is already built and who wants to run the experimental study at the lab.*

### K.5.1 — Week 1 — Final Infrastructure Setup (Days 1–7)

**Day 1–2 — Pepper ↔ AI Server Bridge verification.** Confirm `/health` returns OK against the real Pepper at DIBRIS. Run the Day-Zero checklist (Chapter 21) end-to-end with the author as P000. Catch any infra bugs at this stage rather than mid-study.

**Day 3–4 — OmniLLM + LiteLLM full sweep.** Confirm `omnillm models` lists all 19 models, that each model with an API key returns a non-error `omnillm ask` response, that Ollama returns from `llama3-8b-local`. Test the smart router (`omnillm route --strategy TASK_TYPE`) and LLM-as-Judge (`omnillm evaluate`).

**Day 5–6 — RAG Pipeline verification.** Open the DIBRIS knowledge base files (`lab_info.txt`, `faq.txt`, `university_map.txt`) and verify they reflect current lab state. Update any outdated facts. Re-index. Test retrieval with `curl -X POST .../interact -d '{"text":"What time does the lab open?","condition":"A"}'`.

**Day 7 — End-to-end pilot pass.** Run the full 20-interaction matrix on the real Pepper with yourself as P000. Verify every condition routes to the expected model. Check latencies fall in the expected range (A: ~1.4s, B: ~2.8s, D: ~3.1s).

### K.5.2 — Week 2 — Protocol Refinement and Participant Prep (Days 8–14)

**Day 8–9 — Gesture / Speech Refinement.** Watch the pilot recording (if available). Are gestures crisp? Is Pepper's speaking rate too fast? Tune `ALAnimatedSpeech` parameters. Confirm the 7-colour LED palette communicates the intended mode.

**Day 10–11 — Final Questionnaire and Protocol.** Print 20 sets of paper questionnaires (5 conditions per participant × 15 participants + spares). Finalise the experimenter script (the briefing speech). Print Latin-square assignment sheets for each participant slot.

**Day 12–13 — Pre-Study Pilots With Lab Colleagues.** Run 2–3 pilots with friendly volunteers from the lab. Note: do not include these in the final N. Identify and fix any latency issues, Whisper misfires, gesture-sync problems, or protocol clarification needs.

**Day 14 — Ethics & GDPR Paperwork.** Confirm Comitato Etico approval is in hand (if required). Have consent forms printed. Set up the participant-recruitment email and book the lab schedule.

### K.5.3 — Week 3 — Run Experiments (Days 15–21)

**Day 15–21 — Participant Sessions.** Aim for **2–3 participants per day**. Each session ≈ 40–60 minutes including briefing, the 20 interactions, paper questionnaires, pairwise preference, debrief, and turnover. Target: **15 participants** by end of week.

| Day | Participants |
|---|---|
| Day 15 (Mon) | P001, P002 |
| Day 16 (Tue) | P003, P004 |
| Day 17 (Wed) | P005, P006, P007 |
| Day 18 (Thu) | P008, P009 |
| Day 19 (Fri) | P010, P011 |
| Day 20 (Mon) | P012, P013 |
| Day 21 (Tue) | P014, P015 |

Reserve days 22–24 as buffer for reschedules / drop-outs.

**Daily routine:**

1. Pre-session: Pepper power-on, server-up, ping check.
2. Per-session: briefing → driver → questionnaires → pairwise → debrief.
3. Post-session: backup `results/by_participant/Pxxx/` immediately.
4. End-of-day: `Copy-Item -Recurse results\ D:\thesis-backup\results-<date>\`.

### K.5.4 — Week 4 — Analysis and Writing (Days 22–30)

**Day 22–24 — Data Analysis.** Open `notebooks/analysis.ipynb`. Load all 15 participants' CSVs into pandas. Compute per-condition Likert means with 95% CIs. Run the repeated-measures ANOVA. Compute pairwise win-rates. Build the embodied ELO leaderboard.

**Day 25–28 — Write.** The thesis structure:

- Introduction & Related Work (use Appendix G citations)
- System Architecture (figures from Appendix E + Part II)
- Experimental Design (Part V chapters 23–25)
- Results (your tables from Day 22–24)
- Discussion (refer to Part VI for future scope; compare against literature in Appendix H)
- Conclusion

**Day 29–30 — Polish and Submit.** Generate the final figures. Cross-check every citation. Run a final spell-check. Submit to your supervisor for review. Address feedback within 2–3 days.

### K.5.5 — Common Failure Modes During the Study Month

| Failure | Mitigation |
|---|---|
| Participant cancels last-minute | Have a backlog of 3–5 alternates on stand-by. Recruit through the department mailing list as a rolling pool. |
| Pepper drops connection mid-session | The driver logs and continues; if it recurs, restart bridge + driver in <60s. If it happens twice in one session, abort and reschedule. |
| OpenAI/Anthropic outage | Most outages are <30 minutes. Schedule sessions later that day. If sustained, run Conditions B + locally-routed C only. |
| Whisper transcription fails for a participant with a strong accent | Bump `model_size` to `"small"` in `whisper_stt.py` for that participant only. |
| Ethics committee comes back with revision requests | Build in 2-week buffer before Day 15. Approval-related delays are the #1 cause of missed thesis deadlines. |
| Your laptop battery dies mid-session | Always plug in. Have a spare charger in the bag. |

### K.5.6 — When to Stop

You will be tempted to add features forever. The thesis writes itself when you can answer **three** questions with data:

- Does smart routing beat fixed (H2)?
- Does RAG help (H3)?
- Does embodiment change the ranking (H1)?

Everything else is decoration. Add it after submission.

\newpage
