# PART I — FOUNDATIONS

\newpage

## Chapter 1 — What Is OmniLLM, Really?

> **⚡ AT A GLANCE.** OmniLLM is a Python platform that lets you talk to many
> different AI models (OpenAI, Anthropic, Google, DeepSeek, Ollama-local) through
> *one* unified interface, automatically picks the best one for each kind of
> question, can ask several at once and synthesise their answers, scores them on
> an ELO leaderboard, grounds their replies in your own documents (RAG), and
> connects all of that to a Pepper humanoid robot for human-robot interaction
> research. The core innovation: **the robot's brain is never locked to a single
> model**.

### 1.1  The One-Sentence Definition

> *OmniLLM is a multi-LLM orchestration platform with a robot front-end.*

That sentence is technically correct, but it hides everything interesting. Let
us unpack it for each of our three readers.

### 1.2  For the Beginner — A Working Analogy

Imagine you are a small startup that needs legal advice. You could hire one
lawyer and use them for everything — divorce, tax, intellectual property,
employment law. They will be okay at all of those, but excellent at none.

Now imagine, instead, that you have an *office manager* with a Rolodex. The
office manager:

1. Listens to your problem.
2. Decides which lawyer in the Rolodex is the right specialist.
3. Forwards the question.
4. Compares quotes from cheap and expensive lawyers when you are budget-bound.
5. When the question is high-stakes, sends it to *three* lawyers and synthesises
   their answers.
6. Keeps a running scoreboard of each lawyer's track record so the next routing
   decision is even smarter.

**OmniLLM is that office manager. The lawyers are the LLMs.**

| Office-manager idea | OmniLLM equivalent |
|---------------------|---------------------|
| The Rolodex | `config/models.yaml` (the model registry) |
| Forwarding the question | `LLMGateway.query()` |
| Picking the right lawyer | `SmartRouter.route()` |
| Asking three lawyers at once | `ConsensusEngine.query_council()` |
| Grading the lawyer's answer | `Evaluator` (LLM-as-Judge) |
| The track-record scoreboard | `EloScorer` |
| The receptionist who repeats back what the lawyer said | The Pepper robot |

### 1.3  For the Owner — What You Actually Built

You built a system with **five logical layers** that sit on top of each other:

```
┌──────────────────────────────────────────────────────────────────────┐
│   5. ROBOT FRONT-END  —  Pepper / NAO / Buddy / virtual / text-only  │
├──────────────────────────────────────────────────────────────────────┤
│   4. AGENT PIPELINE  —  LangGraph: STT → classify → RAG → LLM → plan │
├──────────────────────────────────────────────────────────────────────┤
│   3. INTELLIGENCE LAYER  —  Router, Council, Evaluator, ELO Scorer   │
├──────────────────────────────────────────────────────────────────────┤
│   2. UNIFIED GATEWAY  —  LiteLLM, model registry, cost & latency     │
├──────────────────────────────────────────────────────────────────────┤
│   1. PROVIDER LAYER  —  OpenAI, Anthropic, Google, DeepSeek, Ollama  │
└──────────────────────────────────────────────────────────────────────┘
```

Each layer has a precise responsibility:

1. **Provider layer** — the actual LLM APIs. You did not write these. You wrote
   the way OmniLLM *talks to* them.
2. **Unified gateway** — your `gateway.py`. It hides every provider's quirks
   behind one Python coroutine call.
3. **Intelligence layer** — your `router.py`, `consensus.py`, `evaluator.py`,
   `scorer.py`. This is where "smart" happens.
4. **Agent pipeline** — your `hri/agent_graph.py`. A LangGraph DAG that turns
   raw audio into a robot action plan.
5. **Robot front-end** — your `robotics/`, `server/app.py`, `server/naoqi_client.py`.
   The bit that touches hardware (or simulates touching hardware).

> 💡 **Why this layering matters.** Each layer can be swapped without breaking
> the others. You can replace Ollama with vLLM (Layer 1) and the gateway above
> doesn't notice. You can replace LiteLLM with raw `requests` calls (Layer 2)
> and the router doesn't notice. You can swap Pepper for NAO (Layer 5) and the
> agent graph doesn't notice. **This separation is the entire engineering
> achievement of the project.**

### 1.4  For the Academic — The Research Contribution

🎓 The current LLM evaluation literature lives almost entirely on text:
*MMLU* (Hendrycks 2021), *MT-Bench* (Zheng 2023), *Chatbot Arena* (LMSYS 2023),
*LiveBench* (White 2024). The HRI literature, in parallel, has explored
single-LLM social robots: Irfan et al. (HRI 2024), Nichols et al. (2024
arXiv), Grassi et al. (HAI 2024), Spitale et al. (Vita, 2024).

**No prior work does both at once.** No published study has:

1. Compared **multiple** LLMs as interchangeable backends for the *same* social
   robot in the *same* HRI experimental protocol.
2. Applied **dynamic smart routing** between LLMs during live HRI based on
   task type, language, and budget.
3. Tested whether the **rankings** produced by embodied HRI agree with the
   rankings produced by text-only benchmarks.
4. Combined **RAG-augmented** social robotics with multi-LLM backend
   comparison.
5. Built a reusable **LangGraph-orchestrated** open-source platform for any
   HRI lab to repeat the study with their own robots, KB, and conditions.

The research gap is genuine; OmniLLM and the *Embodied LLM Arena* fill it.

### 1.5  Three Honest Questions and Answers

**Q. Is OmniLLM "just" a LiteLLM wrapper?**
A. No. LiteLLM solves "how do I call any provider with one API". OmniLLM
solves "given many providers, which should I call, why, with what context,
through what robot, and how do I prove the answer is good?". LiteLLM is
*Layer 2*. OmniLLM is layers 2 through 5.

**Q. Does the robot actually do anything intelligent?**
A. The robot is a thin client. **All intelligence lives on the AI server.**
Pepper records audio, sends it over HTTP, receives a JSON action plan, and
executes the plan. This is by design. If the robot were the brain, swapping
robots (NAO, Buddy) would mean rewriting the brain.

**Q. Can I run this without a robot?**
A. Yes — and most development happens that way. The Flask server has a
`/interact` endpoint that accepts plain text. You can talk to the system with
`curl`. The robot is the demonstration target, not the prerequisite.
Chapters 29 and 30 walk through robot-free use.

\newpage

## Chapter 2 — Why a Robot? The Motivation Behind This Project

> **⚡ AT A GLANCE.** A reasonable critic asks "if you're benchmarking LLMs,
> why involve a 28-kg robot at all? You could test models on a screen." This
> chapter is the reply. The short version: physical embodiment changes how
> humans evaluate AI responses (the *embodiment effect* in HRI literature),
> exposes failure modes that screens hide (latency feel, gesture-speech sync),
> and matches the actual deployment context that organisations care about
> (reception robots, hospital wayfinders, educational companions).

### 2.1  The Skeptic's Question

You may have heard, or thought, some variant of:

> "Adding a robot just adds complexity — Python 2.7 issues, network latency,
> physical logistics, hardware risk — without changing the underlying claim,
> which is about LLM quality. Why bother?"

This is a reasonable question. The honest answer takes four points.

### 2.2  Point 1 — The Embodiment Effect Is Real

Multiple decades of HRI research show that **the same AI text is evaluated
differently** when it is delivered through:

- a screen (the typical chatbot)
- a disembodied voice (a smart speaker)
- a physical robot that gestures and makes eye contact

Key references:

| Citation | Finding |
|----------|---------|
| Wainer et al. (2006) | Robots are perceived as more credible than equivalent on-screen agents on persuasion tasks |
| Li (2015), *IJSR* survey | Across 33 HRI experiments, embodied interaction produced reliably different ratings of trust, intelligence, and likeability |
| Bartneck et al. (2009), *Godspeed* | Established a validated multidimensional measurement instrument for robot perception |
| Bainbridge et al. (2011) | Physically present robots elicit greater compliance than the same robot via video |

The mechanism is multi-causal: physical presence triggers social-norm
evaluations that screens do not; gestures and gaze provide multimodal
disambiguation; latency and timing matter more in face-to-face interaction.

The implication for OmniLLM is direct: **a model that scores best on MMLU may
not score best when delivered via Pepper.** That divergence — if it exists —
is itself a publishable finding.

### 2.3  Point 2 — Embodied Tasks Surface Failures Text Hides

Consider Task T2 ("Navigation / Guidance"). The user asks:

> "Where is Room 305?"

A text-only system can produce a perfectly graded answer:

> "Room 305 is on the third floor of Building C. Take the elevator on your
> left, then turn left at the corridor."

A *robot* must do more. It must produce that answer **and** point with the
correct arm **and** turn its head **and** light its eyes a colour appropriate
to navigation guidance. A model that produces the right text but the wrong
gesture (says "left", points right) is a robot failure. **No text benchmark
will ever detect this failure.** Multimodal coherence is invisible until the
robot is actually moving.

Similarly: a 3-second response is fine in text but ruinous in face-to-face
conversation. Latency is a quality variable only in embodied settings.

### 2.4  Point 3 — Real Deployment Targets Are Embodied

Universities, hospitals, hotels, and retail spaces increasingly deploy
Pepper-class robots as reception, wayfinding, and triage agents. The
question those organisations ask is not "which model has the highest MMLU
score" — it is "which model produces the best **face-to-face experience**
on **our** robot for **our** visitors talking about **our** information?"

OmniLLM's experiment design answers exactly that question. The five
experimental conditions (A–E, see Chapter 37) directly map to the choices a
deployment team must make: cloud vs local, single model vs ensemble, RAG vs
no RAG.

### 2.5  Point 4 — The Methodological Bridge

🎓 OmniLLM bridges two communities that rarely talk. The **NLP / LLM**
community publishes leaderboards (LMSYS, LiveBench, HELM). The **HRI**
community publishes user studies with validated psychological instruments
(Godspeed, NARS, RoSAS). OmniLLM applies the *NLP* benchmarking infrastructure
inside the *HRI* experimental framework. The Embodied LLM Arena is, in effect,
**Chatbot Arena rendered through a robot**.

A useful side-effect: any HRI lab can adopt the OmniLLM platform, swap in
their own robot bridge (the abstract `RobotBridge` makes this a 200-line job)
and their own knowledge base, and replicate the methodology. The platform is
itself a research contribution.

### 2.6  When You *Can* Skip the Robot

Be honest with yourself about scope. The robot is essential when:

- You are evaluating **embodied user experience** (the central thesis claim).
- You need **multimodal coherence** (gesture + speech + LED).
- You want **latency-aware** ratings (real-time feel).
- You are running **the experiment** with real participants.

The robot is **not** essential when:

- You are debugging the AI server or RAG pipeline.
- You are evaluating model quality on text benchmarks.
- You are demoing the routing logic.
- You are training a new component locally.

In other words: build the AI server first, debug it without Pepper, and only
involve the robot when the question being asked actually requires embodiment.
This sequence is reflected in the build order of Chapter 33.

\newpage

## Chapter 3 — The Five-Minute Tour of the Repository

> **⚡ AT A GLANCE.** The repository has one Python package (`omnillm/`) split
> into seven sub-packages, one config directory, one knowledge-base directory,
> one tests directory, and a small constellation of Markdown docs. This chapter
> is a guided walk through the file tree so you know where to look later.

### 3.1  The Top-Level Layout

When you `cd` into the project root you see this:

```
OmniLLM/
├── README.md                       # Project front page
├── GETTING_STARTED.md              # Beginner setup guide
├── EXPLANATION.md                  # Detailed file-by-file explanation
├── ARCHITECTURE.md                 # Architecture reference (large)
├── PEPPER_CHOREGRAPHE_GUIDE.md     # Pepper-specific walkthrough
├── OmniLLM_Complete_Beginners_Guide.md  # Choregraphe + virtual robot path
├── LICENSE                         # MIT licence
├── pyproject.toml                  # Python package metadata + extras
├── requirements.txt                # Flat dependency list
├── .env.example                    # Template for API keys
├── .gitignore                      # Files git should ignore
│
├── config/                         # YAML configuration
│   ├── models.yaml                 # ★ The model registry (every LLM lives here)
│   └── tasks/                      # Benchmark task YAML files
│       ├── reasoning.yaml
│       ├── knowledge.yaml
│       ├── code.yaml
│       ├── instruction.yaml
│       ├── safety.yaml
│       └── robot.yaml
│
├── omnillm/                        # ★ Main Python package
│   ├── __init__.py                 # Public API re-exports
│   ├── gateway.py                  # LLMGateway — unified LiteLLM wrapper
│   ├── router.py                   # SmartRouter — strategy-based selection
│   ├── consensus.py                # ConsensusEngine — multi-model council
│   ├── evaluator.py                # Evaluator — LLM-as-Judge patterns
│   ├── scorer.py                   # EloScorer — chess-style leaderboard
│   ├── cli.py                      # Click+Rich terminal dashboard
│   │
│   ├── hri/                        # Human-Robot Interaction module
│   │   ├── __init__.py
│   │   ├── classifier.py           # T1–T4 task classifier
│   │   ├── language_detector.py    # Multilingual routing
│   │   ├── experiment.py           # Conditions A–E, sessions
│   │   └── agent_graph.py          # ★ LangGraph multi-node pipeline
│   │
│   ├── rag/                        # Retrieval-Augmented Generation
│   │   ├── __init__.py
│   │   └── pipeline.py             # ChromaDB + keyword fallback
│   │
│   ├── robotics/                   # Robot bridges + helpers
│   │   ├── __init__.py
│   │   ├── bridge.py               # Abstract RobotBridge + RobotAction
│   │   ├── pepper.py               # Pepper HTTP bridge
│   │   ├── nao.py                  # NAO HTTP bridge
│   │   ├── buddy.py                # Buddy WebSocket bridge
│   │   ├── gesture_planner.py      # Task → gesture mapping
│   │   └── whisper_stt.py          # Whisper STT wrapper
│   │
│   ├── server/                     # AI server + NAOqi client
│   │   ├── __init__.py
│   │   ├── app.py                  # ★ Flask AI server (Python 3.x)
│   │   └── naoqi_client.py         # ★ NAOqi client (Python 2.7)
│   │
│   ├── tasks/                      # Built-in benchmark tasks
│   │   ├── __init__.py
│   │   ├── loader.py               # YAML/JSON task loader
│   │   └── sample_tasks.py         # 8 axes of built-in eval tasks
│   │
│   └── utils/                      # Shared utilities
│       ├── __init__.py
│       ├── cost_tracker.py         # USD spend per model/session
│       ├── experiment_logger.py    # InteractionRecord logging
│       ├── questionnaire.py        # Likert + Godspeed + pairwise
│       └── export.py               # CSV / JSON / Markdown exporters
│
├── knowledge_base/                 # ★ RAG document store
│   ├── lab_info.txt
│   ├── faq.txt
│   ├── visitor_profiles.csv
│   ├── event_schedule.csv
│   ├── research_projects.txt
│   └── university_map.txt
│
├── tests/                          # 278 pytest test cases
│   ├── test_gateway.py
│   ├── test_router.py
│   ├── test_evaluator.py
│   ├── test_scorer.py
│   ├── test_consensus.py
│   ├── test_rag.py
│   ├── test_hri.py
│   ├── test_gesture_planner.py
│   ├── test_experiment_logger.py
│   └── test_new_components.py
│
└── results/                        # Auto-created — eval JSON, CSV exports
```

The stars (★) mark the **most important files**. If you are reading
unfamiliar source code, start with those seven and the rest follows.

### 3.2  The Five Files To Know By Heart

If you only have time to remember five files, make them these:

| # | File | What it does | Reason |
|---|------|--------------|--------|
| 1 | `config/models.yaml` | Registry of every model | Adding a new LLM is 7 YAML lines, zero code |
| 2 | `omnillm/gateway.py` | One function call to any provider | Everything else depends on it |
| 3 | `omnillm/hri/agent_graph.py` | The robot's brain, as a graph | Where audio becomes a robot action |
| 4 | `omnillm/server/app.py` | Flask HTTP API for Pepper | The contact surface with the robot |
| 5 | `omnillm/server/naoqi_client.py` | Python 2.7 robot side | The only Python 2 file in the project |

Files 4 and 5 talk to each other over HTTP. Files 1, 2, and 3 talk to each
other through Python imports. The whole project is, in essence, those five
files plus their helpers.

### 3.3  How The Documentation Files Relate

You may have noticed there are six(!) Markdown files at the root. They serve
different audiences and were written at different times:

| File | Audience | What it covers | Status |
|------|----------|----------------|--------|
| `README.md` | First-time visitor | Project overview, install, key features | Current |
| `GETTING_STARTED.md` | Beginner setting up | Step-by-step install + first commands | Current |
| `EXPLANATION.md` | Deep-dive reader | File-by-file explanation, every command | Current |
| `ARCHITECTURE.md` | Architect | Diagrams, data flow, endpoint maps | Current |
| `PEPPER_CHOREGRAPHE_GUIDE.md` | Robot-stage user | Pepper + Choregraphe walk-through | Current |
| `OmniLLM_Complete_Beginners_Guide.md` | Local-only user | Choregraphe virtual robot, no API keys | Current |

This book is a *consolidation* of everything in those documents plus extensive
new material derived directly from the source code. When the book and a doc
disagree, the **source code** is the truth (the docs may have aged).

### 3.4  What Lives Outside the Repository

Some things you'll need are **not** in the repo and never will be:

- **API keys** for OpenAI, Anthropic, Google, DeepSeek, Qwen — they live in
  your `.env` file (which is in `.gitignore`).
- **Ollama models** (Llama 3, Qwen, Mistral, etc.) — stored by Ollama in its
  own directory, often `~/.ollama/`.
- **The Pepper robot** itself, obviously. But also the **NAOqi SDK** which
  is downloaded from SoftBank's developer portal (you have it at
  `C:\pynaoqi\`).
- **Choregraphe** — installed as a desktop application at
  `C:\Program Files (x86)\Aldebaran\Choregraphe Suite 2.5\`.
- **Python 2.7** — needed only for the NAOqi client; lives at
  `C:\Python27\python.exe`.

\newpage

## Chapter 4 — The Vocabulary You Need Before Chapter 5

> **⚡ AT A GLANCE.** This is the project's Rosetta Stone. Every term you'll
> meet later in the book is defined here once. Skim it; come back when a word
> trips you up. Each entry has a one-line definition and, where useful, a
> "first appears in" pointer.

> 📖 *Read this chapter as a glossary, not a narrative.* It will make later
> chapters dramatically easier.

### 4.1  AI / LLM Vocabulary

**LLM** — Large Language Model. An AI system that consumes and produces text.
Examples: GPT-4o, Claude Sonnet, Gemini Flash, Llama 3.

**Provider** — A company or service that hosts an LLM. OpenAI, Anthropic,
Google, DeepSeek, Alibaba (Qwen), and Ollama (free local) are the providers
OmniLLM uses.

**Model ID (in OmniLLM)** — A short string used inside the project to refer to
a model. Defined in `config/models.yaml`. Example: `openai-gpt4o-mini`.

**Token** — Roughly one short word, or a sub-word fragment. LLMs charge in
tokens. "Hello world" is two tokens; "antidisestablishmentarianism" might be
five.

**Prompt** — The input you send to an LLM. In OmniLLM, prompts are *messages*
in OpenAI chat format: `[{"role": "user", "content": "Hello"}]`.

**System prompt** — A leading message with `role: "system"` that sets the
model's behaviour. OmniLLM uses one to make the LLM "be Pepper".

**Temperature** — A 0.0-to-1.0 number controlling how random the model is.
0 = deterministic, 1 = creative. OmniLLM defaults to 0.7 for chat, 0.0 for
judge calls.

**API key** — A secret string proving you have an account with a provider.
Lives in `.env`. Never commit to git.

**LiteLLM** — A Python library that gives all providers a unified API. OmniLLM
uses it as the foundation of `gateway.py`.

**Ollama** — A free, local LLM runtime. Runs models like Llama 3 on your own
GPU or CPU. Has no API key. Listens on `http://localhost:11434`.

**Whisper** — OpenAI's open-source speech-to-text model. Comes in sizes
`tiny`, `base`, `small`, `medium`, `large`. OmniLLM can use Whisper *locally*
(free, no API call) or via the OpenAI Whisper API.

### 4.2  RAG and Evaluation Vocabulary

**RAG** — Retrieval-Augmented Generation. Search a document store for
relevant text chunks, then prepend them to the LLM prompt. Reduces
hallucination dramatically.

**Vector store / Vector database** — A specialised database that stores
*embeddings* (lists of numbers representing text meaning) and supports
"find the K most similar items" queries. OmniLLM uses **ChromaDB** as its
vector store.

**Embedding** — A list of (typically 384–1536) floating-point numbers that
encodes the semantic meaning of a piece of text. Two pieces of text with
similar meaning have similar embeddings.

**Chunk** — A short slice of a longer document, used as the unit of retrieval.
OmniLLM chunks documents into 512-character pieces with 64-character overlap.

**Faithfulness** — A 0–1 score measuring whether an LLM's answer actually
uses the retrieved context (vs making things up). OmniLLM computes this via
LLM-as-Judge.

**Hallucination** — When the LLM confidently states something not in the
retrieved context. OmniLLM uses a word-overlap heuristic to flag candidates.

**LLM-as-Judge** — Using one LLM to evaluate another LLM's response. OmniLLM
implements three variants: Referenceless (G-Eval), Reference-Based, and
Pairwise.

**ELO** — A rating system from chess. After many head-to-head matches, models
get a numeric rating where +100 ≈ 64% expected win-rate. Used by LMSYS
Chatbot Arena. OmniLLM has its own `EloScorer`.

**Pairwise comparison** — A judge sees two responses and picks the better one.
OmniLLM runs each comparison **twice** with positions swapped, to cancel
position bias.

**Position bias** — The well-documented tendency of LLM judges to prefer the
*first* response they see. Mitigated by swap-and-aggregate.

### 4.3  Robotics / HRI Vocabulary

**HRI** — Human-Robot Interaction. The academic field studying how people
interact with robots.

**Pepper** — A 120 cm humanoid social robot from SoftBank Robotics (originally
Aldebaran). 20 degrees of freedom, eye LEDs, chest tablet, four microphones,
two speakers. Runs Python 2.7 NAOqi.

**NAO** — Pepper's smaller sibling (58 cm, 25 DoF). Same NAOqi OS. Common in
education and RoboCup.

**Buddy** — A different companion robot from Blue Frog Robotics. Android-based,
no NAOqi. OmniLLM has a separate WebSocket bridge for it.

**NAOqi** — Pepper / NAO's middleware operating system. Provides services like
`ALAnimatedSpeech`, `ALMotion`, `ALLeds`. **Locked to Python 2.7**, which is
the source of the Python-version bridge problem.

**ALAnimatedSpeech** — The NAOqi service that makes Pepper speak with
synchronised body animations. Cleaner than `ALTextToSpeech` (which is
voice-only).

**ALMotion** — The NAOqi service controlling Pepper's joints (motors). You
must call `motion.wakeUp()` before the robot can move.

**ALLeds** — The NAOqi service controlling the eye and ear LEDs.
`fadeRGB("FaceLeds", r, g, b, duration)` changes eye colour.

**ALBehaviorManager** — The NAOqi service that runs pre-built animations
("behaviors") like waving, bowing, pointing.

**Behavior** — A named animation file installed on the robot. Lives at paths
like `animations/Stand/Gestures/Hey_1` (which is the wave gesture).

**Choregraphe** — A drag-and-drop desktop IDE from SoftBank for programming
Pepper / NAO. Includes a virtual robot simulator. **Only works with NAOqi
2.5** (the version Pepper uses).

**Pepper SDK / pynaoqi** — The Python 2.7 binding to NAOqi services. Imported
as `import qi` (modern) or `import naoqi` (legacy).

**RobotAction** — In OmniLLM, a dataclass with fields `speech`, `gesture`,
`movement`, `emotion_led`, `nav2_goal`, `metadata`. The contract between the
brain (Python 3) and the body (Python 2.7).

**Embodiment effect** — The HRI finding that the *same* AI text is rated
differently when delivered through a physical robot versus a screen.

**Godspeed Questionnaire Series** — Bartneck et al.'s validated five-subscale
instrument for measuring perceived anthropomorphism, animacy, likeability,
intelligence, and safety of robots. OmniLLM has a dataclass for it.

**Likert scale** — A 1–7 (or 1–5) rating of agreement. OmniLLM uses 1–7 for
custom questionnaire items, 1–5 for Godspeed.

**Within-subjects design** — An experimental design where every participant
experiences every condition. OmniLLM uses this for the 5 conditions A–E.

**Counterbalancing / Latin square** — A method of varying the *order* in
which participants meet the conditions, to cancel out fatigue and
order-of-presentation effects.

### 4.4  Software Engineering Vocabulary

**Async / await / coroutine** — Python's syntax for non-blocking I/O.
`async def` declares a coroutine; `await` pauses it until the awaited
operation completes; `asyncio.gather()` runs many coroutines concurrently.
OmniLLM uses async heavily because LLM calls are I/O-bound.

**Dataclass** — A Python class created with `@dataclass` decorator. Auto-
generates `__init__`, `__repr__`, etc. OmniLLM uses dataclasses everywhere
for structured data.

**LangGraph** — A library on top of LangChain for building multi-node agent
graphs (DAGs of functions sharing state). Used in `hri/agent_graph.py`.

**LangChain** — A broader framework for LLM apps. OmniLLM uses LangChain's
document loaders for PDF and CSV ingestion in the RAG pipeline.

**ChromaDB** — A pure-Python embedded vector database. Used in `rag/pipeline.py`
when available; the pipeline falls back to keyword search if not installed.

**Flask** — A minimalist Python web framework. Used in `server/app.py` to
expose the AI server's HTTP API.

**Click** — A Python library for building command-line interfaces. Used in
`cli.py` to build the `omnillm` command.

**Rich** — A Python library for beautiful coloured terminal output. Used in
`cli.py` for tables, panels, and progress bars.

**Pyproject.toml** — The modern Python project metadata file. Defines
package name, version, dependencies, optional extras (`[dev]`, `[hri]`,
`[robotics]`, `[all]`).

**Virtual environment / venv** — An isolated Python sandbox per project.
OmniLLM lives in `.venv/` after `python -m venv .venv`.

**Editable install** — `pip install -e .` makes a package importable without
copying files; changes to source code take effect immediately. OmniLLM is
always installed editable for development.

**HTTP / REST** — The web protocol used between OmniLLM's Flask server and
Pepper's NAOqi client. All payloads are JSON.

**WebSocket** — A persistent bi-directional protocol used between OmniLLM
and the Buddy robot for token-by-token streaming.

**JSON** — JavaScript Object Notation. OmniLLM uses it as the universal
serialisation format for inter-process communication.

**WAV / PCM** — The audio format used for voice transport. 16 kHz mono, 16-bit
signed PCM, optionally base64-encoded for HTTP transport.

**Base64** — A way to encode binary bytes as ASCII text so they fit in JSON.

\newpage
