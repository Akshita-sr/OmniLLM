# 🚀 Getting Started with OmniLLM — From Absolute Zero

This guide explains OmniLLM **from scratch** — no prior knowledge of LLMs, Python packaging, or AI tooling assumed. By the end you will know what the project does, how its code is organised, which technologies power it, and exactly how to run it.

> 📖 **Want even more depth?** See [EXPLANATION.md](EXPLANATION.md) — a comprehensive walkthrough of every single file, every terminal command, all tools and libraries, and a complete guide to connecting OmniLLM to an old Pepper robot that uses NAOqi, Choregraphe, and Python 2.7.

---

## Table of Contents

1. [What Is OmniLLM? (Plain English)](#1-what-is-omnillm-plain-english)
2. [Key Concepts in 60 Seconds](#2-key-concepts-in-60-seconds)
3. [Technologies Used](#3-technologies-used)
4. [Repository Layout — Every File Explained](#4-repository-layout--every-file-explained)
5. [Module-by-Module Code Walkthrough](#5-module-by-module-code-walkthrough)
6. [Prerequisites](#6-prerequisites)
7. [Step-by-Step Installation](#7-step-by-step-installation)
8. [Running the Project](#8-running-the-project)
9. [Running the Tests](#9-running-the-tests)
10. [Pepper Robot + NAOqi + Choregraphe Quick-Start](#10-pepper-robot--naoqi--choregraphe-quick-start)
11. [Common Troubleshooting](#11-common-troubleshooting)

---

## 1. What Is OmniLLM? (Plain English)

**A Large Language Model (LLM)** is an AI system — like ChatGPT, Claude, or Gemini — that can read and write natural language. Many companies now offer their own LLM accessible via an **API** (a URL you call from code to get a response).

**The problem**: There are dozens of LLMs, each with its own API, pricing, strengths, and quirks. If you want to:

- Find out which model gives the best answer for your specific task
- Automatically use the cheapest model that still meets quality requirements
- Get a more reliable answer by asking several models and combining their responses
- Connect an LLM to a physical robot

…you would normally have to write separate code for each provider and manually stitch everything together.

**OmniLLM solves this** by providing a single, unified platform that:

| Feature | What it does |
|---|---|
| **Unified Gateway** | One function call reaches any of 19 models from 6+ providers |
| **Smart Router** | Automatically picks the right model for each task and budget |
| **Evaluation Engine** | Scores model responses using an AI judge (LLM-as-Judge) |
| **Consensus Engine** | Asks several models the same question and merges their answers |
| **ELO Leaderboard** | Ranks models like a chess tournament based on head-to-head comparisons |
| **RAG Pipeline** | Grounds answers in your own documents to reduce hallucinations |
| **Robotics Bridge** | Sends LLM output as commands to Pepper, NAO, and Buddy robots |
| **CLI Dashboard** | Rich, coloured terminal interface — no GUI required |

The entire model registry is **YAML-based**: adding a brand-new LLM requires only 7–8 lines of YAML and zero Python changes.

---

## 2. Key Concepts in 60 Seconds

| Concept | One-line definition |
|---|---|
| **LLM** | AI model that generates text (GPT-4o, Claude, Gemini, Llama…) |
| **API key** | Secret password that lets you call a cloud LLM provider's service |
| **Token** | Roughly one word; LLMs charge by the number of tokens they process |
| **Provider** | Company that hosts and sells access to an LLM (OpenAI, Anthropic…) |
| **Ollama** | Free tool that runs open-source LLMs on your own computer |
| **LiteLLM** | Python library that wraps 100+ LLM provider APIs behind one interface |
| **LLM-as-Judge** | Using one LLM to automatically score the output of another |
| **ELO score** | A rating system (like in chess) for ranking models by win rate |
| **RAG** | Retrieval-Augmented Generation — searching your documents before answering |
| **Consensus** | Asking multiple models the same question and synthesising one best answer |
| **CLI** | Command-Line Interface — a text-based terminal tool |

---

## 3. Technologies Used

### Core Runtime
| Library | Version | Why it is used |
|---|---|---|
| **Python** | ≥ 3.11 | Primary language; `asyncio` enables concurrent LLM calls |
| **[LiteLLM](https://github.com/BerriAI/litellm)** | ≥ 1.40 | Unified gateway to 100+ providers through one API |
| **[Rich](https://github.com/Textualize/rich)** | ≥ 13.0 | Coloured tables, panels, progress bars in the terminal |
| **[Click](https://click.palletsprojects.com)** | ≥ 8.1 | Builds the `omnillm` CLI with commands and options |
| **[PyYAML](https://pyyaml.org)** | ≥ 6.0 | Reads `config/models.yaml` and task YAML files |
| **[aiohttp](https://docs.aiohttp.org)** | ≥ 3.9 | Async HTTP client used for robot bridge communication |
| **[python-dotenv](https://pypi.org/project/python-dotenv/)** | ≥ 1.0 | Loads `.env` API keys into environment variables |

### Optional / Feature-gated
| Library | Optional group | Why it is used |
|---|---|---|
| **[ChromaDB](https://www.trychroma.com)** | `[hri]` | Vector database for semantic document search in the RAG pipeline |
| **[langchain-community](https://python.langchain.com)** | `[hri]` | PDF / CSV document loaders for RAG ingestion |
| **[sentence-transformers](https://www.sbert.net)** | `[hri]` | Local embedding model for semantic similarity |
| **[pypdf](https://pypdf.readthedocs.io)** | `[hri]` | Parses PDF files for RAG indexing |
| **[langdetect](https://pypi.org/project/langdetect/)** | `[hri]` | Detects the language of a text (used in HRI multilingual routing) |
| **[websockets](https://websockets.readthedocs.io)** | `[robotics]` | WebSocket streaming for Buddy robot integration |
| **[Flask](https://flask.palletsprojects.com)** | `[robotics]` | HTTP server for NAOqi Python 2.7 bridge |

### Development / Testing
| Library | Why it is used |
|---|---|
| **pytest** | Test framework |
| **pytest-asyncio** | Runs `async` test functions with pytest |
| **pytest-mock** | Provides `mocker` fixture for mocking LLM calls |

---

## 4. Repository Layout — Every File Explained

```
OmniLLM/
│
├── README.md                   # Full project documentation and literature review
├── GETTING_STARTED.md          # ← This file — beginner-friendly from-scratch guide
├── LICENSE                     # MIT licence text
├── pyproject.toml              # Python package metadata and dependency groups
├── requirements.txt            # Flat list of core dependencies (alternative to pyproject)
├── .env.example                # Template showing every environment variable to set
├── .gitignore                  # Files/folders excluded from git
│
├── config/                     # ── Configuration ──────────────────────────────
│   ├── models.yaml             # The model registry: every LLM available,
│   │                           # its provider, API key env var, and pricing
│   └── tasks/                  # YAML task files used by the evaluation engine
│       ├── reasoning.yaml      # Logical reasoning tasks
│       ├── knowledge.yaml      # World-knowledge / factual tasks
│       ├── code.yaml           # Code generation / debugging tasks
│       ├── instruction.yaml    # Instruction-following tasks
│       ├── safety.yaml         # Safety and refusal tasks
│       └── robot.yaml          # HRI / robotics-specific tasks
│
├── omnillm/                    # ── Main Python Package ─────────────────────
│   ├── __init__.py             # Public API: exports every important class
│   ├── gateway.py              # LLMGateway — unified interface to all models
│   ├── router.py               # SmartRouter — picks the best model per task
│   ├── evaluator.py            # Evaluator — runs LLM-as-Judge scoring
│   ├── scorer.py               # EloScorer — ELO leaderboard from pairwise results
│   ├── consensus.py            # ConsensusEngine — the LLM Council architecture
│   ├── cli.py                  # CLI entry point (Click commands)
│   │
│   ├── rag/                    # ── Retrieval-Augmented Generation ──────────
│   │   ├── __init__.py
│   │   └── pipeline.py         # RAGPipeline — index docs, semantic search, augment prompts
│   │
│   ├── hri/                    # ── Human-Robot Interaction research module ──
│   │   ├── __init__.py
│   │   ├── classifier.py       # HRITaskClassifier — labels utterances T1–T4
│   │   ├── language_detector.py# LanguageDetector — identifies language, routes multilingual
│   │   └── experiment.py       # ExperimentManager — conditions A–E, sessions, data collection
│   │
│   ├── robotics/               # ── Robot Integration Layer ──────────────────
│   │   ├── __init__.py
│   │   ├── bridge.py           # RobotBridge (abstract base class) + RobotAction dataclass
│   │   ├── pepper.py           # PepperBridge — HTTP bridge to NAOqi Python 2.7
│   │   ├── nao.py              # NAOBridge — HTTP bridge to NAOqi Python 2.7
│   │   ├── buddy.py            # BuddyBridge — WebSocket streaming to Buddy Android
│   │   └── gesture_planner.py  # GesturePlanner — maps LLM text to robot gestures
│   │
│   ├── tasks/                  # ── Task Loading ─────────────────────────────
│   │   ├── __init__.py
│   │   ├── loader.py           # TaskLoader — reads YAML task files, validates schema
│   │   └── sample_tasks.py     # Built-in sample tasks (no YAML file needed for demos)
│   │
│   └── utils/                  # ── Shared Utilities ─────────────────────────
│       ├── __init__.py
│       ├── cost_tracker.py     # CostTracker — accumulates USD spend per model per session
│       ├── experiment_logger.py# ExperimentLogger — records HRI interactions as JSONL
│       └── export.py           # Export — converts results to CSV / Markdown / JSON
│
├── tests/                      # ── Test Suite ───────────────────────────────
│   ├── __init__.py
│   ├── test_gateway.py         # Tests for LLMGateway (model string, cost, query)
│   ├── test_router.py          # Tests for SmartRouter routing strategies
│   ├── test_evaluator.py       # Tests for Evaluator judge patterns
│   ├── test_scorer.py          # Tests for EloScorer
│   ├── test_consensus.py       # Tests for ConsensusEngine
│   ├── test_rag.py             # Tests for RAGPipeline
│   ├── test_hri.py             # Tests for HRI classifier, language detector, experiment
│   ├── test_gesture_planner.py # Tests for GesturePlanner
│   └── test_experiment_logger.py # Tests for ExperimentLogger
│
└── results/                    # ── Output Directory ─────────────────────────
    (auto-created)              # Evaluation JSON files, exported CSV/MD reports
```

---

## 5. Module-by-Module Code Walkthrough

This section explains what each module does, how the pieces connect, and shows the key class for each.

### 5.1 `gateway.py` — The Unified LLM Gateway

**What it does**: Provides a single `async` function call that reaches any registered LLM, regardless of whether it lives at OpenAI, Anthropic, Google, DeepSeek, or locally via Ollama.

**Key class**: `LLMGateway`

```
models.yaml  →  LLMGateway._load_config()
                LLMGateway._build_model_string()  →  "ollama/llama3:8b"
                                                    "gpt-4o"
                                                    "gemini/gemini-2.5-pro"
                LLMGateway.query()  →  litellm.acompletion()  →  ModelResponse
```

- **`_build_model_string(model_id)`** converts the YAML model ID (e.g., `llama3-8b-local`) into the prefix format LiteLLM expects (e.g., `ollama/llama3:8b`).
- **`query(model_id, messages)`** is `async`: it sends the messages and returns a `ModelResponse` dataclass containing `content`, `input_tokens`, `output_tokens`, `latency_ms`, `cost_usd`, and any `error`.
- **`query_multiple(model_ids, messages)`** fires all queries **concurrently** with `asyncio.gather`, so querying 5 models takes roughly the same time as querying 1.

**The `litellm.drop_params = True` setting** means unsupported parameters (like `temperature` for OpenAI's o-series reasoning models) are silently ignored instead of raising an error.

---

### 5.2 `router.py` — The Smart Router

**What it does**: Given a task and constraints, automatically picks the best model from the registry.

**Key class**: `SmartRouter`

```
SmartRouter.route(task_category, budget_usd, strategy)
    → RouteDecision(model_id, confidence, reason, estimated_cost, strategy_used)
```

**Routing strategies** (choose one per call):

| Strategy | Logic |
|---|---|
| `BEST_QUALITY` | Highest evaluation score across all registered models |
| `LOWEST_COST` | Cheapest model that meets a minimum quality threshold |
| `LOWEST_LATENCY` | Historically fastest model |
| `BEST_VALUE` | Composite: quality × 0.5 + cost savings × 0.3 + speed × 0.2 |
| `LOCAL_PREFERRED` | Free Ollama models first; cloud as fallback |
| `TASK_TYPE` | HRI experiment: maps T1–T4 task types via `hri_task_routing` in models.yaml |

The router **learns over time**: it reads past `EvalResult` JSON files and updates its internal score table, so routes improve as more evaluation data is collected.

---

### 5.3 `evaluator.py` — The Evaluation Engine

**What it does**: Runs a prompt against a model, then uses an **LLM-as-Judge** to score the response.

**Key classes**: `Evaluator`, `EvalTask`, `EvalResult`

```
EvalTask(id, category, prompt, reference_answer?, judge_pattern)
    ↓
Evaluator.evaluate(model_id, task, judge_model_id)
    ↓
EvalResult(score, judge_reasoning, latency_ms, cost_usd)
```

**Three judge patterns**:

1. **`referenceless`** (G-Eval) — the judge scores the response on its own merits (coherence, accuracy, helpfulness). No gold answer needed.
2. **`reference_based`** — the judge compares the response to a provided reference answer. Good for factual tasks.
3. **`pairwise`** — the judge sees two model responses side-by-side and picks a winner. OmniLLM runs this **twice with A/B swapped** to cancel out position bias.

---

### 5.4 `scorer.py` — The ELO Leaderboard

**What it does**: Maintains an ELO rating for every model based on pairwise comparison results.

**Key class**: `EloScorer`

```
EloScorer.update(winner_id, loser_id)   # called after each pairwise comparison
EloScorer.get_leaderboard()             # returns sorted list of (model_id, elo_score)
```

ELO works like chess rankings: beating a strong opponent earns more points than beating a weak one. A 100-point difference translates to ~64% expected win rate.

---

### 5.5 `consensus.py` — The LLM Council

**What it does**: Sends the same prompt to multiple models simultaneously, analyses their responses for agreement, and synthesises a single best answer.

**Key classes**: `ConsensusEngine`, `ConsensusConfig`, `ConsensusResult`

```
ConsensusConfig(council_models=[...], strategy="synthesis", min_agreement=0.7)
    ↓
ConsensusEngine.run(messages)
    ↓
    Phase 1: gateway.query_multiple()  →  all responses in parallel
    Phase 2: semantic similarity clustering  →  majority/minority groups
    Phase 3: judge LLM synthesises best answer
    ↓
ConsensusResult(final_answer, agreement_score, individual_responses, dissenting_models)
```

This is especially important for **robotics safety**: a robot should not execute an action unless multiple models independently agree on it.

---

### 5.6 `rag/pipeline.py` — Retrieval-Augmented Generation

**What it does**: Indexes your own documents (PDFs, CSVs, text files) and uses them to ground LLM responses, dramatically reducing hallucinations.

**Key class**: `RAGPipeline`

```
RAGPipeline(gateway, model_id)
    ↓
rag.index_directory("knowledge_base/")
    → loads PDFs/CSVs/TXT → splits into chunks → stores in ChromaDB
    ↓
rag.query("What time does the lab open?")
    → embeds query → semantic search → top-k chunks retrieved
    → augmented prompt: "Based on these documents: ... Answer: ..."
    → LLM generates grounded response
    ↓
RAGResponse(answer, retrieved_chunks, faithfulness_score, hallucination_detected)
```

**Fallback**: If `chromadb` is not installed, the pipeline falls back to simple keyword matching over an in-memory list — fully functional, just less accurate.

---

### 5.7 `hri/` — Human-Robot Interaction Research Module

**What it does**: Implements the full experimental design for the *Embodied LLM Arena* study — comparing different LLM routing strategies for a Pepper robot interacting with humans.

**Key classes**:

- **`HRITaskClassifier`** — classifies any utterance into one of four task types:
  - `T1`: Info retrieval ("What time does the lab open?")
  - `T2`: Navigation ("Where is Room 305?")
  - `T3`: Social conversation ("How are you?")
  - `T4`: Multilingual (any non-English utterance)

- **`LanguageDetector`** — detects the language of a text (uses `langdetect` if installed, otherwise a fast heuristic) and maps it to the optimal LLM for that language.

- **`ExperimentManager`** — manages 5 experimental conditions (A–E), each using a different LLM strategy, and records every interaction for later statistical analysis.

---

### 5.8 `robotics/` — Robot Bridge Layer

**What it does**: Provides an abstract bridge pattern that decouples the LLM reasoning layer from robot-specific SDKs.

**Abstract base**: `RobotBridge` (in `bridge.py`) defines the interface every robot class must implement:

```python
class RobotBridge(ABC):
    async def connect(self) -> None: ...
    async def disconnect(self) -> None: ...
    async def speak(self, text: str) -> None: ...
    async def execute_action(self, action: RobotAction) -> None: ...
    async def get_sensor_data(self) -> dict: ...
    def parse_llm_to_action(self, llm_output: str) -> RobotAction: ...
```

**Concrete implementations**:

| File | Robot | Communication |
|---|---|---|
| `pepper.py` | Pepper (SoftBank) | HTTP to NAOqi Python 2.7 process |
| `nao.py` | NAO (SoftBank) | HTTP to NAOqi Python 2.7 process |
| `buddy.py` | Buddy (Blue Frog) | WebSocket streaming (Android) |

**`gesture_planner.py`** — maps LLM response sentiment/intent to named robot gestures (e.g., a greeting response triggers a `"wave"` gesture).

---

### 5.9 `cli.py` — The Terminal Dashboard

**What it does**: Exposes all OmniLLM features as named sub-commands via a `Click` CLI, with Rich formatting for beautiful terminal output.

```
omnillm
  ├── models      — list all registered models
  ├── ask         — query one or more models with a prompt
  ├── evaluate    — run the evaluation engine
  ├── compare     — pairwise comparison of two models
  ├── council     — run the LLM Council (consensus)
  ├── route       — demonstrate the smart router
  ├── leaderboard — show ELO rankings
  ├── costs       — show accumulated USD spend
  └── export      — export results to CSV / Markdown / JSON
```

---

### 5.10 `config/models.yaml` — The Model Registry

Every model available in OmniLLM is declared here. Adding a new model is just 6–8 lines of YAML:

```yaml
my-new-model:
  id: my-new-model
  provider: openai          # openai | anthropic | google | ollama | deepseek | openai_compatible
  model: gpt-5              # exact model name used by the provider API
  api_key_env: OPENAI_API_KEY   # name of the environment variable holding the key
  cost_per_1m_input: 2.50   # USD per million input tokens
  cost_per_1m_output: 10.00 # USD per million output tokens
  type: cloud               # cloud | local
  description: "Short description"
```

---

## 6. Prerequisites

Before you install, make sure you have:

| Requirement | Check command | Minimum version |
|---|---|---|
| **Python** | `python --version` | 3.11 |
| **pip** | `pip --version` | latest recommended |
| **git** | `git --version` | any |
| **Ollama** *(optional, for free local models)* | `ollama --version` | any |

> **No API keys required to start** — the test suite uses mocks, and Ollama models are free and local.

---

## 7. Step-by-Step Installation

### Step 1 — Clone the repository

```bash
git clone https://github.com/Akshita-sr/OmniLLM.git
cd OmniLLM
```

### Step 2 — Create an isolated Python environment

Using a virtual environment keeps OmniLLM's dependencies separate from your system Python:

```bash
# Create the environment
python -m venv .venv

# Activate it
source .venv/bin/activate        # Linux / macOS
# .venv\Scripts\activate         # Windows (Command Prompt)
# .venv\Scripts\Activate.ps1     # Windows (PowerShell)
```

You will see `(.venv)` at the start of your terminal prompt when it is active.

### Step 3 — Install OmniLLM

```bash
# Standard install (core + dev/test dependencies)
pip install -e ".[dev]"
```

The `-e` flag installs in *editable* mode so any change you make to the source code is immediately reflected without re-installing.

**Optional extras**:

```bash
# Add RAG pipeline + HRI module dependencies
pip install -e ".[dev,hri]"

# Add robotics bridge dependencies
pip install -e ".[dev,robotics]"

# Install everything
pip install -e ".[all]"
```

### Step 4 — Set your API keys

```bash
# Copy the template
cp .env.example .env
```

Open `.env` in any text editor and fill in the keys for the providers you want to use:

```dotenv
# You only need keys for the providers you actually want to call.
# Leave others blank or delete them.

OPENAI_API_KEY=sk-...            # https://platform.openai.com/api-keys
ANTHROPIC_API_KEY=sk-ant-...     # https://console.anthropic.com/
GOOGLE_API_KEY=...               # https://aistudio.google.com/app/apikey
DEEPSEEK_API_KEY=...             # https://platform.deepseek.com/
```

> **No paid API key?** Skip to [Running with Local Models (Ollama)](#81-option-a--run-with-local-models-completely-free) below — it's completely free.

### Step 5 — Verify the installation

```bash
omnillm models
```

You should see a coloured table listing all 19 registered models. If you see this, OmniLLM is installed correctly.

---

## 8. Running the Project

### 8.1 Option A — Run with Local Models (Completely Free)

Ollama runs open-source LLMs on your own hardware — no API key, no cost.

**Install Ollama**:

```bash
# Linux / macOS
curl -fsSL https://ollama.com/install.sh | sh

# Windows: download the installer from https://ollama.com
```

**Pull a model** (this downloads it once, ~4–8 GB):

```bash
ollama pull llama3:8b        # Meta Llama 3 — general purpose (~4.7 GB)
ollama pull qwen2.5:7b       # Alibaba Qwen — multilingual (~4.4 GB)
ollama pull qwen2.5:3b       # Qwen 2.5 compact — lighter and faster (~2.0 GB)
ollama pull llama3.2:3b      # Meta Llama 3.2 compact (~2.0 GB)
```

**Verify Ollama is running** (it starts automatically after install):

```bash
ollama list   # shows all downloaded models
```

**Ask a question**:

```bash
omnillm ask "Explain quantum entanglement simply" -m llama3-8b-local
```

### 8.2 Option B — Run with Cloud Models (API Key Required)

Once your `.env` file has API keys, all cloud commands work automatically:

```bash
# Ask GPT-4o
omnillm ask "What is the capital of France?" -m openai-gpt4o

# Ask Claude
omnillm ask "Write a haiku about autumn" -m claude-sonnet

# Ask all models at once
omnillm ask "What is consciousness?" --all
```

### 8.3 Core Commands Reference

#### List all registered models

```bash
omnillm models              # all models
omnillm models --type cloud # cloud only
omnillm models --type local # local (Ollama) only
```

#### Ask a question

```bash
# Ask a specific model
omnillm ask "Hello" -m llama3-8b-local

# Ask multiple models
omnillm ask "Explain RAG" -m openai-gpt4o -m claude-sonnet

# Ask every registered model
omnillm ask "What year is it?" --all
```

#### Run the evaluation engine

```bash
# Evaluate all cloud models across all task categories
omnillm evaluate

# Evaluate specific models
omnillm evaluate -m openai-gpt4o -m claude-sonnet

# Evaluate one category only
omnillm evaluate -c reasoning
omnillm evaluate -c code

# Save results to a file
omnillm evaluate -m openai-gpt4o -o results/my_eval.json
```

#### Pairwise model comparison

```bash
omnillm compare "Debug this code: def fib(n): return fib(n-1)+fib(n-2)"
omnillm compare "Write a poem" --model-a openai-gpt4o --model-b claude-sonnet
```

#### LLM Council — multi-model consensus

```bash
# Synthesis strategy (judge LLM merges all responses into one best answer)
omnillm council "What is the trolley problem?"

# Majority vote strategy
omnillm council "Is P=NP?" --strategy majority_vote

# Custom council members
omnillm council "Analyse climate change solutions" \
    -m openai-gpt4o -m claude-sonnet -m gemini-2.5-pro
```

The council output shows each model's individual response, the synthesised final answer, and an agreement score.

#### Smart routing

```bash
# Auto-detect task complexity and route accordingly
omnillm route "Hi"                                              # → cheapest model
omnillm route "Prove Fermat's Last Theorem step-by-step"        # → most capable

# Apply a budget cap (USD per query)
omnillm route "Summarise this paragraph" --budget 0.001

# Force a specific strategy
omnillm route "Debug async Python code" --strategy BEST_QUALITY
omnillm route "Quick yes/no question"   --strategy LOWEST_COST
omnillm route "Need an answer now"      --strategy LOWEST_LATENCY
```

#### ELO leaderboard

```bash
omnillm leaderboard                     # overall ranking
omnillm leaderboard --category reasoning # ranking for reasoning tasks
```

#### Cost tracking

```bash
omnillm costs   # shows USD spend breakdown per model
```

#### Export results

```bash
omnillm export --format csv      --input results/eval.json -o results/report.csv
omnillm export --format markdown --input results/eval.json -o results/report.md
```

### 8.4 Add a New Model in 30 Seconds

Open `config/models.yaml` and append:

```yaml
my-model:
  id: my-model
  provider: openai
  model: gpt-5
  api_key_env: OPENAI_API_KEY
  cost_per_1m_input: 10.00
  cost_per_1m_output: 30.00
  type: cloud
  description: "My new model"
```

That is all. No Python code changes needed. The model is immediately available in every CLI command.

---

## 9. Running the Tests

The test suite uses **mocks** for all LLM calls — no real API keys or Ollama are needed to run tests.

```bash
# Install dev dependencies (if not already done)
pip install -e ".[dev]"

# Run the full test suite
pytest tests/ -v

# Run a specific test file
pytest tests/test_gateway.py -v
pytest tests/test_router.py -v
pytest tests/test_consensus.py -v

# Run with coverage report
pytest tests/ --cov=omnillm --cov-report=term-missing
```

A green `PASSED` next to every test name means everything is working correctly.

---

## 10. Pepper Robot + NAOqi + Choregraphe Quick-Start

> For a full step-by-step guide with detailed troubleshooting, see **[EXPLANATION.md — Section 9](EXPLANATION.md#9-connecting-to-the-old-pepper-robot-naoqi--choregraphe--python-27)**.

### Why Two Processes?

Pepper's NAOqi SDK is locked to **Python 2.7**. OmniLLM's AI stack needs **Python 3.11+**. OmniLLM solves this with two separate processes that communicate over HTTP:

```
Your Computer (Python 3.11+)          Pepper Robot (Python 2.7 / NAOqi)
┌──────────────────────────┐           ┌──────────────────────────────┐
│  python -m omnillm.      │◄──────────│  python naoqi_client.py      │
│  server.app              │  HTTP     │  (captures audio, executes   │
│  AI server, LangGraph,   │──────────►│  speech + gesture + LED)     │
│  RAG, LiteLLM, Whisper   │           └──────────────────────────────┘
└──────────────────────────┘
```

### Quick Setup (5 Steps)

**Step 1 — Find Pepper's IP**

Press Pepper's chest button once — it says its IP address aloud (e.g., `192.168.1.100`).

**Step 2 — Start the AI server** (on your Python 3.11+ machine)

```bash
source .venv/bin/activate
pip install -e ".[all]"
pip install openai-whisper         # for local speech-to-text

python -m omnillm.server.app --host 0.0.0.0 --port 5000
```

Test it:
```bash
curl http://localhost:5000/health   # should return {"status": "ok"}
```

**Step 3 — Find your machine's IP**

```bash
ip addr show   # Linux/macOS — look for your 192.168.x.x address
ipconfig       # Windows
```

**Step 4 — Run the NAOqi client** (in Python 2.7, with NAOqi SDK installed)

```bash
# Replace 192.168.1.100 with Pepper's IP, 192.168.1.50 with your machine's IP
python omnillm/server/naoqi_client.py \
    --robot-ip 192.168.1.100 \
    --server-ip 192.168.1.50 \
    --participant P001 \
    --condition C
```

Pepper will say: *"Hello! I am Pepper, powered by OmniLLM. How can I help you today?"*

**Step 5 — Speak to Pepper**

Talk within ~1 metre of Pepper's microphone. OmniLLM will:
1. Capture 5 seconds of audio
2. Transcribe with Whisper STT
3. Classify the question type (T1–T4)
4. Get an AI response via LangGraph + LiteLLM
5. Return gesture + speech + LED colour to Pepper

### Using Choregraphe Alongside OmniLLM

| Choregraphe | OmniLLM |
|---|---|
| Install / test individual robot behaviors | Decide *which* behavior to trigger based on AI reasoning |
| Test ALAnimatedSpeech, ALMotion in isolation | Drive speech + motion from LLM output |
| Good for scripted interactions | Good for open-ended conversations |

To add a Choregraphe-created behavior to OmniLLM's gesture planner, add it to `GESTURE_TO_BEHAVIOR` in `omnillm/server/naoqi_client.py`:

```python
GESTURE_TO_BEHAVIOR = {
    "wave": "animations/Stand/Gestures/Hey_1",
    "my_custom_welcome": "myBehaviors/WelcomeDance",  # ← your behavior
    # ...
}
```

### Experimental Conditions

| Flag | What Pepper Uses |
|---|---|
| `--condition A` | GPT-4o-mini (cloud baseline) |
| `--condition B` | Llama3:8b via Ollama (free local baseline) |
| `--condition C` | OmniLLM smart router (best model per task type) |
| `--condition D` | LLM Council (3 models → synthesised answer) |
| `--condition E` | GPT-4o-mini without RAG (isolates RAG benefit) |

---

## 11. Common Troubleshooting

### `omnillm: command not found`

The virtual environment is not active, or the install failed.

```bash
# Re-activate the environment
source .venv/bin/activate       # Linux / macOS
# .venv\Scripts\activate        # Windows

# Re-install
pip install -e ".[dev]"

# Verify
omnillm --version
```

### `Model 'X' not found in registry`

The model ID you typed does not match any key in `config/models.yaml`. Run `omnillm models` to see the exact IDs.

### `APIConnectionError` or `AuthenticationError`

Your API key is missing or incorrect.

1. Check that `.env` exists (copy from `.env.example` if not).
2. Check that the key value starts with the correct prefix (e.g., `sk-` for OpenAI).
3. Check that the correct env variable name is set (e.g., `OPENAI_API_KEY`, not `OPENAI_KEY`).

### Ollama model not responding

1. Check Ollama is running: `ollama list` should return a list of models.
2. If Ollama is not running, start it: `ollama serve` (runs in the foreground) or it starts automatically on most systems.
3. Check the model is downloaded: `ollama pull llama3:8b`

### `ModuleNotFoundError: No module named 'chromadb'`

The RAG pipeline requires the optional `[hri]` dependencies:

```bash
pip install -e ".[hri]"
```

### Python version error

OmniLLM requires Python 3.11+. Check your version:

```bash
python --version   # must be 3.11.x or higher
```

If you have multiple Python versions installed, try `python3.11` or use `pyenv` to manage versions.

---

## Quick Reference Card

```
# Install
git clone https://github.com/Akshita-sr/OmniLLM.git && cd OmniLLM
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env   # then add your API keys

# Local free models (no API key needed)
ollama pull llama3:8b
omnillm ask "Hello" -m llama3-8b-local

# Cloud models (API key required)
omnillm ask "Hello" -m openai-gpt4o

# Core features
omnillm models                            # list all 19 models
omnillm evaluate -m openai-gpt4o          # evaluate a model
omnillm council "Your question"           # multi-model consensus
omnillm route "Your prompt"               # smart routing demo
omnillm leaderboard                       # ELO rankings
omnillm costs                             # spend tracking

# Pepper robot integration
python -m omnillm.server.app --host 0.0.0.0 --port 5000   # start AI server
python omnillm/server/naoqi_client.py --robot-ip <IP>     # run NAOqi client (Python 2.7)

# Tests (no API key needed)
pytest tests/ -v
```

---

*For full documentation, academic references, architecture diagrams, and the complete roadmap, see [README.md](README.md).*  
*For a complete explanation of every file, every command, and how to connect Pepper, see [EXPLANATION.md](EXPLANATION.md).*
