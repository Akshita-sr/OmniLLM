# PART VI — BUILDING THIS FROM SCRATCH

If you wanted to build OmniLLM from zero, the order of operations matters.
This part is the chronological roadmap. Three chapters: the 13-week plan,
the critical first mile, and when to add the robot.

\newpage

## Chapter 33 — The Build Order — A 13-Week Plan

> **⚡ AT A GLANCE.** OmniLLM took roughly 13 weeks of focused work to build.
> The order is dictated by dependencies, not by interest. The mistakes you
> avoid by following this order are bigger than the time saved by skipping
> ahead.

### 33.1  The Milestone Map

```
   Week 1 ─── Foundation ─── "I can talk to one LLM" ────────────┐
   Week 2 ─── Foundation ──── (continued)                         │
                                                                  ▼
   Week 3 ─── Intelligence ─ "I can route between LLMs" ─────────┐
   Week 4 ─── Intelligence ── (Council, Evaluator, Scorer)        │
                                                                  ▼
   Week 5 ─── Knowledge ──── "It can answer about MY data" ──────┐
   Week 6 ─── Knowledge ──── (RAG with ChromaDB)                  │
                                                                  ▼
   Week 7 ─── HRI components ─ "Each piece works in isolation" ──┐
   Week 8 ─── HRI components ── (classifier, language, gesture)   │
                                                                  ▼
   Week 9 ─── Pipeline ───── "End-to-end works in text mode" ────┐
   Week 10 ── Pipeline ───── (LangGraph + Flask + NAOqi client)   │
                                                                  ▼
   Week 11 ── Experiment ──── "I can run a full session" ────────┐
   Week 12 ── Experiment ──── (logging, questionnaire, ELO)       │
                                                                  ▼
   Week 13+── Polish ─────── "Documentation, tests, demos"
```

Every milestone is a complete, testable system. Don't skip ahead — the
joy of "I can route between LLMs" is much harder to feel if you never
first felt "I can talk to one LLM".

### 33.2  Week 1–2: Foundation

**Goal:** the gateway works for one model.

| Day | File | Why |
|-----|------|-----|
| 1 | `.env.example` | Document the API keys you'll need before writing any code |
| 1 | `pyproject.toml` | Lock in dependencies up front: litellm, flask, click, rich, pyyaml, dotenv |
| 2 | `config/models.yaml` | Define the registry. Start with 2–3 models (one cloud, one Ollama) |
| 3–4 | `omnillm/__init__.py`, `omnillm/gateway.py` | The most important file. Get one query working end-to-end. |
| 5 | `omnillm/cli.py` (just `models` and `ask`) | Build a CLI early — you'll use it to debug everything else |

**Milestone**: `omnillm ask "Hello" -m openai-gpt4o-mini` returns a real
response.

### 33.3  Week 3–4: Intelligence

**Goal:** the system can pick a model, run a council, judge a response, and
keep an ELO leaderboard.

| Day | File | Why |
|-----|------|-----|
| 8–9 | `omnillm/router.py` | Start with two strategies (`LOWEST_COST`, `BEST_QUALITY`). Add more later. |
| 10 | `omnillm/consensus.py` | Synthesis strategy first; majority_vote and weighted are extensions. |
| 11–12 | `omnillm/evaluator.py` | Referenceless first. Reference-based requires you to have gold answers. Pairwise needs swap logic. |
| 13–14 | `omnillm/scorer.py` | ELO math is in `_update_ratings`. Save/load JSON. |

**Milestone**: `omnillm council "Is P=NP?"` produces synthesized output
from 3 models with an agreement score.

### 33.4  Week 5–6: Knowledge

**Goal:** ground answers in your own documents.

| Day | File | Why |
|-----|------|-----|
| 15–16 | `omnillm/rag/pipeline.py` (keyword fallback) | Start with simple keyword search. Get the augmented prompt pattern working. |
| 17 | `knowledge_base/lab_info.txt` | Write a short text file with real data. Test retrieval against it. |
| 18 | `omnillm/rag/pipeline.py` (ChromaDB) | Add the ChromaDB path. Verify both backends produce similar results. |
| 19 | More `knowledge_base/` files | CSV (visitors), TXT (research projects), PDF (papers) |
| 20 | Faithfulness scoring | LLM-as-judge call inside `query()` |
| 21 | Hallucination heuristic | Word-overlap check |

**Milestone**: ask a question whose answer is *only* in your KB; verify
the system uses the KB context (faithfulness > 0.8).

### 33.5  Week 7–8: HRI Components

**Goal:** each robotics component works in isolation.

| Day | File | Why |
|-----|------|-----|
| 22 | `omnillm/hri/classifier.py` | Rule-based first. Keywords + regex. Test with 20 sample utterances. |
| 23 | `omnillm/hri/language_detector.py` | Tier 1 (script analysis) first. Tier 2 (n-grams) only if needed. |
| 24 | `omnillm/robotics/whisper_stt.py` | Local backend first. API backend is a 10-line addition. |
| 25 | `omnillm/robotics/gesture_planner.py` | Rule-based mapping. No LLM call. |
| 26 | `omnillm/robotics/bridge.py` | Abstract base + `RobotAction` dataclass. |
| 27 | `omnillm/robotics/pepper.py` (placeholder) | Mock the HTTP calls; real implementation comes after the AI server. |
| 28 | `omnillm/hri/experiment.py` | Conditions A–E + `ParticipantSession`. Pure dataclasses. |

**Milestone**: each component has its own pytest file and passes.

### 33.6  Week 9–10: Pipeline

**Goal:** end-to-end works (audio in, action out).

| Day | File | Why |
|-----|------|-----|
| 29–30 | `omnillm/hri/agent_graph.py` | Build LangGraph. One node at a time. Start with text-only mode (skip transcribe). |
| 31 | Wire RAG and gesture planner into nodes | These are the substantive nodes. |
| 32 | Smart router and consensus nodes | Conditions C and D. |
| 33–34 | `omnillm/server/app.py` | Flask. `/health`, then `/interact`, then everything else. |
| 35 | `omnillm/server/naoqi_client.py` | **Last.** Without this everything else still works. |

**Milestone**: `curl POST /interact` with text returns a valid
`RobotAction`. With Choregraphe's virtual robot, the action visibly
animates.

### 33.7  Week 11–12: Experiment Infrastructure

**Goal:** one experimenter can run a full session and analyse the data.

| Day | File | Why |
|-----|------|-----|
| 36 | `omnillm/utils/experiment_logger.py` | The `InteractionRecord` is the central data structure of the study. |
| 37 | `omnillm/utils/questionnaire.py` | Likert + Godspeed + pairwise + observer dataclasses. |
| 38 | `omnillm/utils/cost_tracker.py` | Necessary for budget reports. |
| 39 | `omnillm/utils/export.py` | CSV / JSON / Markdown for analysis tools (R, JASP). |
| 40–41 | Tests for everything | At least one happy-path test per file. |
| 42 | Pilot session | One colleague, full protocol. |

**Milestone**: `python -m omnillm.server.app` + `naoqi_client.py` +
questionnaire form = a complete session that produces analysable data.

### 33.8  Week 13+: Polish

| Task | Output |
|------|--------|
| README, GETTING_STARTED, EXPLANATION | Docs |
| ARCHITECTURE.md | Diagrams for thesis |
| Demo video | 5-min recording of a full session |
| Code review pass | Type hints, docstrings, linting |
| Empirical evaluation | Run the experiment with N participants |

The book you are reading is the consolidation of week 13.

\newpage

## Chapter 34 — The Critical First Mile — Foundations Before Anything Else

> **⚡ AT A GLANCE.** Three rules for the first mile: (1) the gateway is
> the first thing that must work, (2) ship the CLI early so you can
> debug, (3) a YAML registry is worth more than it looks.

### 34.1  Rule 1 — The Gateway Is Not an Afterthought

Many "multi-LLM" projects begin by writing a chatbot for one model, then
trying to retrofit the second model in. This always goes badly. The
second model has a different SDK, different parameter names, different
response shapes. By the time you've added the third, you have three sets
of branching code.

**Build the gateway first.** Put YAML at the centre. By the time you call
your second LLM, the codepath is: read YAML → call gateway → done. Adding
the third is the same.

OmniLLM's `gateway.py` is the *entire* abstraction. Everything else is a
caller of `gateway.query()`.

### 34.2  Rule 2 — Ship the CLI on Day Three

A CLI is *not* a user feature. It is your **debugging tool**. Without it,
you debug with `print()` statements inside test scripts. With it, you can
ask any question of any model in two seconds.

OmniLLM's CLI was useful long before any user touched it:

- `omnillm models` — verify your YAML is parseable.
- `omnillm ask "test" -m <model_id>` — verify the gateway works for that model.
- `omnillm ask "test" --all` — verify *every* model works simultaneously.
- `omnillm route "test"` — verify the router picks the model you expect.
- `omnillm leaderboard` — verify ELO scoring.

Build it on day 3. Use it for everything after.

### 34.3  Rule 3 — YAML Is a Force Multiplier

The decision to put model metadata in YAML — not Python constants — is
small in code but huge in consequence:

| If models are in YAML… | If models are in Python… |
|------------------------|--------------------------|
| Adding a model = editing config | Adding a model = editing code |
| Non-Python users can contribute | Only Python users can contribute |
| Configs can be diffed in PRs | Code diffs mix logic and data |
| Different deployments can have different configs (override file path) | Different deployments fork the code |
| Hot-reload is straightforward | Requires Python module reload tricks |

OmniLLM commits to YAML throughout: model registry, task definitions
(`config/tasks/*.yaml`), routing rules (`hri_task_routing` block).
Code is logic, YAML is data. They are kept apart on purpose.

### 34.4  Anti-Patterns to Avoid

Things you might be tempted to do that will hurt later:

- **Hardcoding API keys.** Use `.env`. Always. Even on day 1.
- **Calling LiteLLM directly from many places.** All calls should go
  through `LLMGateway` — this is what gives you cost tracking, latency
  measurement, and unified error handling.
- **Letting the gateway raise exceptions.** Errors should be captured in
  the `error` field of `ModelResponse`. Higher layers (router, council)
  should never have to wrap gateway calls in try/except.
- **Threading instead of asyncio.** LLM calls are I/O-bound. Asyncio is
  the correct tool. Threading adds complexity without performance.
- **Putting business logic in `cli.py`.** The CLI should be a thin
  wrapper. Logic lives in modules that can be imported and tested.

\newpage

## Chapter 35 — When (and How) to Add the Robot

> **⚡ AT A GLANCE.** Add the robot **last**. Build everything else first.
> When you do add it, build the abstract bridge before any concrete
> implementation. When you build the concrete bridge, mock it before you
> implement it.

### 35.1  Why "Last"?

The robot is a giant fragility multiplier. Pepper has:

- A battery that runs down.
- Wi-Fi that flakes.
- Speech that fails to register.
- Behaviours that need to be installed.
- A Python 2.7 process that has to be running.
- Stiffness that has to be enabled.
- An IP address that occasionally changes.

Every one of these can break the system in ways unrelated to your AI
code. If your AI server isn't already rock-solid in text mode, you will
spend days chasing bugs that turn out to be Wi-Fi problems.

So: **make the AI server bulletproof first**. Test every condition with
text-mode `curl` calls. Only then turn on the robot.

### 35.2  The Bridge-First Approach

When you do add the robot, write the **abstract bridge** first:

```python
class RobotBridge(ABC):
    @abstractmethod async def connect(self): ...
    @abstractmethod async def disconnect(self): ...
    @abstractmethod async def execute_action(self, action: RobotAction): ...
    @abstractmethod async def say(self, text: str): ...
    @abstractmethod async def gesture(self, name: str): ...
    @abstractmethod async def get_sensor_data(self): ...
```

Then write a **mock concrete implementation** that just prints what would
happen:

```python
class MockBridge(RobotBridge):
    async def connect(self):    return True
    async def disconnect(self): return True
    async def execute_action(self, action):
        print(f"[MOCK] speak: {action.speech!r}")
        print(f"[MOCK] gesture: {action.gesture}")
        print(f"[MOCK] led: {action.emotion_led}")
        return True
    # ...
```

Develop the rest of the system against the mock. Only when the system
works end-to-end against the mock do you implement `PepperBridge` for
real.

This pattern is exactly what `omnillm/robotics/pepper.py` implements
today — the HTTP calls are commented placeholders, with `print()`
statements that simulate the action. Replacing those placeholders with
real `aiohttp` calls is a small, isolated change once everything else
is working.

### 35.3  When to Build the Python 2.7 Side

The Python 2.7 NAOqi client is the very last thing to build. It does
nothing the rest of the system depends on — it is purely the consumer
of the AI server's HTTP API. You can write and test the AI server
completely without it.

The order:

1. AI server runs.
2. AI server returns valid `RobotAction` JSON via `/interact`.
3. AI server's responses are reasonable across all 5 conditions.
4. **Then** write `naoqi_client.py`.
5. Test it against Choregraphe's virtual robot first.
6. Test it against a physical robot last.

### 35.4  When the Robot Misbehaves

The robot will misbehave. When it does, debug from the **most reliable
end** outward:

1. **Does the AI server work in text mode?** `curl` it directly. If yes,
   the brain is fine.
2. **Does Choregraphe see Pepper?** If no, it's a network/Wi-Fi issue.
3. **Does Pepper accept basic commands?** Use Choregraphe's Script
   Editor: `tts.say("test")`. If no, NAOqi service is down.
4. **Does `naoqi_client.py` start?** Check `import qi` works in your
   Python 2.7. If no, `PYTHONPATH` is wrong.
5. **Does the client connect to the server?** Check the URL,
   firewall, port.
6. **Only now** look at audio capture / behaviours / LEDs.

Do not start at step 6. You will waste hours.

\newpage
