# OmniLLM

> **Compare, Route, and Orchestrate Every LLM — and Put Them Inside a Robot.**
> Now powering the **Embodied LLM Arena** — the first study to benchmark LLMs through social-robot interaction.

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Tests](https://img.shields.io/badge/tests-278%20passing-brightgreen.svg)](#testing)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](https://github.com/Akshita-sr/OmniLLM/pulls)

> **The complete book lives at [`book/OmniLLM_Book.pdf`](book/OmniLLM_Book.pdf)** — 168 pages covering every line of code, every endpoint, the Pepper / NAOqi / Choregraphe stack, and the experimental design. Rebuild it with `python book/build_pdf.py`. This README is the fast tour.

---

## Table of Contents

1. [What Is OmniLLM? (Plain English)](#what-is-omnillm-plain-english)
2. [Embodied LLM Arena — The Research Story](#embodied-llm-arena--the-research-story)
3. [System Architecture](#system-architecture)
4. [Quick Start — From Zero in 5 Minutes](#quick-start--from-zero-in-5-minutes)
5. [Module Overview](#module-overview)
6. [CLI Commands](#cli-commands)
7. [AI Server + Pepper Robot](#ai-server--pepper-robot)
8. [Adding a New LLM (5 lines of YAML)](#adding-a-new-llm-5-lines-of-yaml)
9. [Evaluation Methodology](#evaluation-methodology)
10. [Testing](#testing)
11. [Project Structure](#project-structure)
12. [Troubleshooting](#troubleshooting)
13. [License](#license)

---

## What Is OmniLLM? (Plain English)

**A Large Language Model (LLM)** is an AI system — GPT-4o, Claude, Gemini, Llama 3 — that reads and writes natural language. Each provider has its own API, pricing, strengths, and quirks.

**OmniLLM is the office manager with a Rolodex.** It:

| Capability | What it does |
|---|---|
| **Unified Gateway** | One `async` call reaches any of 19 registered models from 6+ providers (cloud + local Ollama). |
| **Smart Router** | 6 strategies — `BEST_QUALITY`, `LOWEST_COST`, `LOWEST_LATENCY`, `BEST_VALUE` (composite), `LOCAL_PREFERRED`, `TASK_TYPE`. Learns from past evaluation results. |
| **Cost Tracking** | Real-time USD spend per model, per session. |
| **Consensus / LLM Council** | Fan-out to N models in parallel; combine via majority vote, weighted, or judge-LLM synthesis. |
| **LLM-as-Judge** | Three research-backed patterns: Referenceless (G-Eval), Reference-Based, Pairwise (with position-bias swap). |
| **ELO Leaderboard** | Chatbot-Arena-style ratings, with per-category leaderboards. |
| **RAG Pipeline** | ChromaDB-backed retrieval over your own documents (TXT, CSV, PDF), with optional faithfulness scoring. |
| **LangGraph Agent Pipeline** | Whisper STT → language detect → task classify (T1-T4) → RAG / direct LLM → robot action plan. |
| **Robotics Bridge** | Abstract `RobotBridge` with a concrete bridge for Pepper. The robot's brain is never locked to a single model. |
| **Plugin Architecture** | Adding a new LLM is 7 lines of YAML, zero Python changes. |

### Key Concepts in 60 Seconds

| Concept | One-line definition |
|---|---|
| **API key** | Secret password that lets you call a cloud LLM provider's service |
| **Token** | Roughly one short word; LLMs charge per million tokens |
| **Ollama** | Free local LLM runtime (`localhost:11434`) — no API key needed |
| **LiteLLM** | Python library that wraps 100+ providers behind one interface |
| **LLM-as-Judge** | Using one LLM to score another's output |
| **ELO** | Chess-style rating; +100 ≈ 64% win-rate |
| **RAG** | Retrieval-Augmented Generation — search docs then answer |
| **Consensus** | Asking many models the same thing and merging |
| **HRI** | Human-Robot Interaction (the research field) |
| **NAOqi** | Pepper's middleware OS — locked to Python 2.7 |

---

## Embodied LLM Arena — The Research Story

### The Gap

Existing LLM benchmarks (MMLU, Chatbot Arena, LiveBench) are **entirely text-based**. Existing Pepper-LLM studies use a **single** model. **No prior work has**:

1. compared multiple LLMs as interchangeable backends for the *same* social robot;
2. applied dynamic smart routing between LLMs *during live HRI*;
3. tested whether embodied rankings agree with text-only rankings.

### Research Hypotheses

| # | Hypothesis |
|---|---|
| **H1** | Embodied HRI rankings differ significantly from text-only benchmark rankings. |
| **H2** | Dynamic smart routing produces higher satisfaction than any single fixed model. |
| **H3** | RAG-augmented responses are rated more accurate and trustworthy across all backends. |

### Four Task Types (T1–T4)

| Task | Name | Example | Why a robot matters |
|---|---|---|---|
| **T1** | Information Retrieval | "What time does the lab open?" | Pepper greets visitors, shows info on tablet, gestures while explaining |
| **T2** | Navigation / Guidance | "Where is Room 305?" | Pepper *physically* points and shows a map |
| **T3** | Social Conversation | "How are you?" | Physical presence changes perceived naturalness |
| **T4** | Multilingual | Same as above in another language | Embodiment makes multilingual feel more immersive |

### Five Experimental Conditions

| Cond. | LLM | RAG | What it isolates |
|---|---|---|---|
| **A** | GPT-4o-mini (fixed cloud) | ON | Cloud baseline |
| **B** | Llama 3:8b via Ollama (fixed local) | ON | Local / free baseline |
| **C** | Smart-routed (per task type) | ON | Effect of routing |
| **D** | Consensus council (3 models + synthesis) | ON | Single vs. ensemble |
| **E** | GPT-4o-mini, RAG-off (control) | OFF | RAG's contribution |

---

## System Architecture

```
+---------------------------------------------------------------------+
|                        HUMAN PARTICIPANT                            |
|         Speaks to Pepper -> Sees tablet -> Hears response           |
+----------------------------+----------------------------------------+
                             | Voice (microphone)
                             v
+---------------------------------------------------------------------+
|              PEPPER ROBOT  (Python 2.7 -- NAOqi process)            |
|                                                                     |
|  ALAudioDevice ----capture WAV----> HTTP POST to AI server          |
|  ALAnimatedSpeech <--- response text -- HTTP response               |
|  ALMotion       <--- gesture commands -- JSON action plan           |
|  ALLeds         <--- LED colour       -- JSON action plan           |
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
|  |  PDF/CSV/TXT KB |  |  LLM-as-Judge    |  |  Transcripts    |     |
|  +-----------------+  |  ELO Scorer      |  |  Task success   |     |
|                       +------------------+  +-----------------+     |
|                                                                     |
|  +--------------------------------------------------------------+   |
|  |               LLM Backends (via LiteLLM)                     |   |
|  |   GPT-4o-mini | Claude Haiku | Gemini Flash | DeepSeek V3   |   |
|  |   Ollama local: Llama 3:8b | Qwen 2.5:7b | Mistral:7b ...   |   |
|  +--------------------------------------------------------------+   |
+---------------------------------------------------------------------+
```

> For the full annotated end-to-end flow (including who the LLM judge is, how the ELO updates feed back into the router, and where every byte goes), see **Appendix G** of the book.

---

## Quick Start — From Zero in 5 Minutes

### Prerequisites

| Requirement | Check command | Minimum |
|---|---|---|
| Python | `python --version` | 3.11 |
| pip | `pip --version` | latest |
| git | `git --version` | any |
| Ollama (optional, for free local models) | `ollama --version` | any |

> **No API keys required to start** — the 278 tests use mocks, and Ollama models are free and local.

### Install

```bash
git clone https://github.com/Akshita-sr/OmniLLM.git
cd OmniLLM

# Isolated environment
python -m venv .venv
source .venv/bin/activate            # Linux / macOS
# .venv\Scripts\activate              # Windows CMD
# .venv\Scripts\Activate.ps1          # Windows PowerShell

# Install (editable, with dev/test deps)
pip install -e ".[dev]"

# Full install — RAG + LangGraph + Pepper server
pip install -e ".[all]"

# API keys (optional — Ollama works without them)
cp .env.example .env
# Edit .env and add OPENAI_API_KEY, ANTHROPIC_API_KEY, GOOGLE_API_KEY, etc.

# Verify — should print a coloured table of 19 models
omnillm models
```

### Install Extras

| Extra | What it adds |
|-------|-------------|
| `.[dev]` | pytest, pytest-asyncio, pytest-mock |
| `.[robotics]` | Flask, websockets — for the AI server |
| `.[hri]` | ChromaDB, LangChain, LangGraph, sentence-transformers, langdetect — for RAG + agent graph |
| `.[all]` | Everything above |

### Free Local Path (No API Key)

Ollama runs open-weight models on your own machine — zero cost.

```bash
# Install Ollama: https://ollama.com  (Windows installer / curl one-liner on Linux/macOS)
ollama pull llama3:8b        # ~4.7 GB, general purpose
ollama pull qwen2.5:7b       # ~4.4 GB, multilingual

omnillm ask "Explain quantum entanglement simply" -m llama3-8b-local
```

### Cloud Path

```bash
# After filling .env
omnillm ask "What is the capital of France?" -m openai-gpt4o
omnillm ask "Write a haiku about autumn"     -m claude-sonnet
omnillm ask "What is consciousness?"         --all   # query every registered model
```

---

## Module Overview

```
omnillm/
+- gateway.py           # Unified LLM Gateway -- LiteLLM bridge to 100+ providers
+- router.py            # Smart Router -- 6 strategies, learns from past evals
+- consensus.py         # LLM Council -- majority_vote / weighted / synthesis
+- evaluator.py         # LLM-as-Judge -- referenceless / reference / pairwise
+- scorer.py            # ELO Rating -- per-category leaderboards
+- cli.py               # Rich + Click CLI
|
+- hri/                 # -- Embodied LLM Arena --
|   +- agent_graph.py   # LangGraph 9-node pipeline
|   +- classifier.py    # HRI task classifier (T1-T4)
|   +- language_detector.py
|   +- experiment.py    # Conditions A-E, participant sessions
|
+- rag/
|   +- pipeline.py      # ChromaDB + keyword fallback + faithfulness scoring
|
+- robotics/
|   +- bridge.py        # Abstract RobotBridge + RobotAction
|   +- pepper.py        # Pepper HTTP bridge
|   +- gesture_planner.py
|   +- whisper_stt.py   # Whisper STT (local + API)
|
+- server/
|   +- app.py           # Flask AI server (Python 3.x)
|   +- naoqi_client.py  # NAOqi client (Python 2.7) for Pepper
|
+- utils/
|   +- experiment_logger.py   # InteractionRecord -- the central dataset
|   +- questionnaire.py       # Likert + Godspeed + pairwise + observer
|   +- cost_tracker.py        # Per-model USD spend
|   +- export.py              # CSV / JSON / Markdown

config/
+- models.yaml          # Model registry (add new models here)
+- tasks/               # Benchmark task YAML files (8 axes)

knowledge_base/         # RAG knowledge base -- replace dummy data with yours
+- lab_info.txt
+- faq.txt
+- visitor_profiles.csv
+- event_schedule.csv
+- research_projects.txt
+- university_map.txt

book/                   # The full 168-page reference book
+- OmniLLM_Book.pdf     # The output PDF
+- OmniLLM_Book.md      # The master Markdown
+- 00_front_matter.md ... 11_appendix_flow_diagram.md
+- build_pdf.py         # Regenerate the PDF after edits

tests/                  # 278 pytest tests (no API keys needed -- uses mocks)
results/                # Eval JSON, exports (auto-created)
```

---

## CLI Commands

```bash
# List all registered models
omnillm models
omnillm models --type cloud      # cloud only
omnillm models --type local      # Ollama only

# Ask one or many models
omnillm ask "Hello" -m openai-gpt4o-mini
omnillm ask "Explain RAG" -m openai-gpt4o -m claude-sonnet
omnillm ask "What year is it?" --all

# Benchmark
omnillm evaluate                                   # all models, all categories
omnillm evaluate -m openai-gpt4o-mini -c reasoning
omnillm evaluate -o results/eval_2026.json

# Pairwise comparison
omnillm compare "Write a poem about robots" \
    --model-a openai-gpt4o-mini --model-b gemini-2.5-flash

# Consensus / LLM Council
omnillm council "What is consciousness?"           # default: synthesis
omnillm council "Is P=NP?" --strategy majority_vote
omnillm council "Climate solutions" \
    -m openai-gpt4o -m claude-sonnet -m gemini-2.5-pro

# Smart routing
omnillm route "Where is Room 305?" --strategy TASK_TYPE
omnillm route "Quick yes/no"       --strategy LOWEST_COST --budget 0.001
omnillm route "Hard reasoning"     --strategy BEST_QUALITY

# Reports
omnillm leaderboard                                # overall ELO
omnillm leaderboard --category reasoning
omnillm leaderboard --category embodied_hri        # the Embodied LLM Leaderboard
omnillm costs                                       # USD spend per model
omnillm export --format csv      --input results/eval.json -o results/eval.csv
omnillm export --format markdown --input results/eval.json -o results/eval.md
```

---

## AI Server + Pepper Robot

### Why Two Processes?

Pepper's NAOqi SDK is locked to **Python 2.7**. OmniLLM's AI stack needs **Python 3.11+**. They cannot live in the same process — so OmniLLM splits them and bridges over HTTP:

```
Your machine (Python 3.11+)             Pepper robot (Python 2.7 + NAOqi)
+--------------------------+              +--------------------------------+
| python -m omnillm.       | <--HTTP--    | python naoqi_client.py         |
| server.app               |              | (captures audio,               |
| AI server, LangGraph,    | -- JSON -->  |  executes speech + gesture +   |
| RAG, LiteLLM, Whisper    |              |  LED via NAOqi services)       |
+--------------------------+              +--------------------------------+
```

### Run the AI Server

```bash
python -m omnillm.server.app                          # localhost:5000
python -m omnillm.server.app --host 0.0.0.0 --port 5000
python -m omnillm.server.app --model openai-gpt4o-mini --kb knowledge_base/
python -m omnillm.server.app --no-rag                 # disable RAG
python -m omnillm.server.app --debug                  # Flask debug mode
```

Endpoints:

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/interact` | Main: audio or text → RobotAction JSON |
| `POST` | `/transcribe` | Whisper STT only |
| `POST` | `/evaluate` | Submit questionnaire scores |
| `GET`  | `/health` | Liveness probe |
| `GET`  | `/status` | Server configuration dump |
| `GET`  | `/export` | Download all interaction logs |

### Talk to the Server Without a Robot

```bash
curl -X POST http://localhost:5000/interact \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Where is Room 305?",
    "participant_id": "P001",
    "session_id": "s-abc-123",
    "condition": "C",
    "rag_enabled": true
  }'
```

Returns:

```json
{
  "speech": "Room 305 is on the 3rd floor. Take the lift or staircase on your left.",
  "gesture": "point_left",
  "emotion_led": "#00AAFF",
  "metadata": {
    "task_type": "navigation",
    "model_id": "openai-gpt4o-mini",
    "rag_enabled": true
  }
}
```

### Programmatic Use (LangGraph)

```python
import asyncio
from omnillm.gateway import LLMGateway
from omnillm.rag import RAGPipeline
from omnillm.hri import build_hri_graph
from omnillm.utils import ExperimentLogger

async def main():
    gw = LLMGateway()
    rag = RAGPipeline(gateway=gw)
    rag.index_directory("knowledge_base/")
    logger = ExperimentLogger()

    graph = build_hri_graph(gateway=gw, rag=rag, logger=logger)
    result = await graph.ainvoke({
        "utterance": "Where is Room 305?",
        "participant_id": "P001",
        "session_id": "s1",
        "condition": "C",
        "rag_enabled": True,
    })
    print(result["response_text"])
    print(result["robot_action"])

asyncio.run(main())
```

### Connect a Physical Pepper (Quick Path)

1. **Find Pepper's IP** — press its chest button once; it speaks the IP aloud (e.g., `192.168.1.100`).
2. **Wake Pepper** — `motion.wakeUp()` so its motors hold position.
3. **Start the AI server** on your laptop:

   ```bash
   python -m omnillm.server.app --host 0.0.0.0 --port 5000
   ```

4. **Find your laptop's IP** — `ipconfig` (Windows) or `ip addr show` (Linux/macOS).
5. **Run the NAOqi client** (Python 2.7, on your laptop or on Pepper):

   ```bash
   # Windows CMD
   set PYTHONPATH=C:\pynaoqi\pynaoqi-python2.7-2.5.5.5-win32-vs2013\lib;%PYTHONPATH%
   C:\Python27\python.exe omnillm\server\naoqi_client.py ^
       --robot-ip 192.168.1.100 ^
       --robot-port 9559 ^
       --server-ip 192.168.1.50 ^
       --server-port 5000 ^
       --participant P001 ^
       --condition C
   ```

   Pepper says: *"Hello! I am Pepper, powered by OmniLLM. How can I help you today?"*

For the full Pepper / Choregraphe / NAOqi setup, including how to upload custom behaviours and use Choregraphe's virtual robot, see **Part IV** of `book/OmniLLM_Book.pdf`.

---

## Adding a New LLM (5 lines of YAML)

Edit `config/models.yaml` and append:

```yaml
my-new-model:
  id: my-new-model
  provider: openai          # openai | anthropic | google | ollama | deepseek | openai_compatible
  model: gpt-5              # exact name the provider's API expects
  api_key_env: OPENAI_API_KEY
  cost_per_1m_input: 2.50   # USD per million input tokens
  cost_per_1m_output: 10.00 # USD per million output tokens
  type: cloud               # cloud | local
  description: "What this model is good at"
  hri_strengths: ["info_retrieval"]   # optional: which T1-T4 tasks it shines at
```

No Python code changes. The model is immediately available across the gateway, router, council, evaluator, CLI, RAG, and agent graph.

To route an HRI task type to a specific model, edit the `routing.hri_task_routing` block in the same YAML:

```yaml
routing:
  hri_task_routing:
    info_retrieval: openai-gpt4o-mini
    navigation: gemini-flash
    social_conversation: claude-haiku
    multilingual: gemini-flash
```

---

## Evaluation Methodology

OmniLLM scores models across **8 orthogonal axes**:

| # | Axis | What it measures |
|---|------|------------------|
| 1 | **Reasoning** | Multi-step logic, mathematics |
| 2 | **Knowledge** | Factual accuracy |
| 3 | **Code** | Generate / debug / explain code |
| 4 | **Instruction Following** | Strict format / constraints |
| 5 | **Safety** | Refusal, PII handling |
| 6 | **Robot-Readiness** | Structured JSON for robot control |
| 7 | **Latency** | Time-to-first-token |
| 8 | **Cost Efficiency** | Quality per dollar |

### Three Judge Patterns

| Pattern | When | Output |
|---|---|---|
| **Referenceless (G-Eval)** | Open-ended, no gold answer | Score 0–1 + reasoning |
| **Reference-Based** | You know the right answer | Score 0–1 + reasoning |
| **Pairwise** | Comparing two models head-to-head | Winner: A / B / tie (swap-and-aggregate to cancel position bias) |

### The Composite Value Score (used by `BEST_VALUE` routing)

```
value = quality * 0.5 + cost_score * 0.3 + latency_score * 0.2
```

`quality ∈ [0,1]` from the judge, `cost_score` normalised against $0–$0.05/query, `latency_score` normalised against 500ms–10s.

### Per-Interaction Metrics (auto-logged by `ExperimentLogger`)

Every interaction records: `model_id`, latency_ms, input/output tokens, cost_usd, RAG retrieval scores, RAG faithfulness (LLM-as-Judge), hallucination flag, judge_score, detected_language, task_type, gesture_used, task_success.

The full HRI session questionnaire is in `omnillm/utils/questionnaire.py` — 5-item Likert (accuracy, naturalness, trust, gesture appropriateness, response speed) plus optional Godspeed (1–5 on five subscales) and a final pairwise preference that feeds the **Embodied LLM Leaderboard** via the ELO scorer.

---

## Testing

The 278-test suite uses mocks for all LLM calls — no API keys or Ollama required.

```bash
pip install -e ".[dev]"
pytest tests/ -v
pytest tests/ --cov=omnillm --cov-report=term-missing
```

### Coverage by Module

| File | Tests | What it tests |
|---|---|---|
| `test_gateway.py` | 21 | LiteLLM model strings, costs, error handling |
| `test_router.py` | 24 | All 6 routing strategies |
| `test_consensus.py` | 20 | All 3 synthesis strategies |
| `test_evaluator.py` | 15 | Referenceless / reference-based / pairwise judges |
| `test_scorer.py` | 22 | ELO math + leaderboard |
| `test_hri.py` | 51 | Classifier T1–T4, language detector, experiment manager |
| `test_rag.py` | 26 | Indexing, retrieval, faithfulness, hallucination |
| `test_gesture_planner.py` | 30 | Task → gesture mapping |
| `test_experiment_logger.py` | 16 | Logging, CSV / JSON export |
| `test_new_components.py` | 53 | agent_graph, whisper_stt, questionnaire, server, KB files |

---

## Project Structure

```
OmniLLM/
+- omnillm/             # Main Python package (see Module Overview above)
+- knowledge_base/      # RAG knowledge base -- replace with your data
+- config/
|   +- models.yaml      # Model registry (add new models here)
|   +- tasks/           # Benchmark task YAML files
+- book/                # The full 168-page book (PDF + sources + builder)
+- tests/               # 278 pytest tests
+- results/             # Eval / experiment outputs (auto-created)
+- pyproject.toml       # Package metadata + optional extras
+- requirements.txt     # Flat dependency list
+- .env.example         # API key template
+- LICENSE              # MIT
+- README.md            # This file
```

---

## Troubleshooting

### `omnillm: command not found`

Virtual environment not active, or install failed.

```bash
source .venv/bin/activate     # Linux / macOS
# .venv\Scripts\activate      # Windows
pip install -e ".[dev]"
omnillm --version
```

### `Model 'X' not found in registry`

The model ID doesn't match any key in `config/models.yaml`. Run `omnillm models` to see the exact IDs.

### `APIConnectionError` / `AuthenticationError`

API key missing or wrong.

1. Check that `.env` exists (copy from `.env.example` if not).
2. Check the key has the right prefix (`sk-` for OpenAI, `sk-ant-` for Anthropic).
3. Check the env variable name matches what `models.yaml` expects (e.g., `OPENAI_API_KEY`, not `OPENAI_KEY`).

### Ollama model not responding

```bash
ollama list                   # should show downloaded models
ollama serve                  # start the daemon if it isn't running
ollama pull llama3:8b         # download if missing
```

### `ModuleNotFoundError: chromadb` / `flask` / `langgraph`

You need an optional extra:

```bash
pip install -e ".[hri]"        # chromadb, langgraph, langchain, sentence-transformers
pip install -e ".[robotics]"   # flask, websockets
pip install -e ".[all]"        # everything
```

### Python version error

OmniLLM requires Python 3.11+:

```bash
python --version              # must be 3.11.x or higher
```

### PDF book renders boxes as squares

This was fixed by registering DejaVu fonts and pre-processing in `book/build_pdf.py`. If you see new tofu squares after adding content, check the non-ASCII characters in your new section and add them to either `_EMOJI_REPLACE` or `_BOX_REPLACE` in `build_pdf.py`, then rerun `python book/build_pdf.py`.

---

## Extending the Book

The book is built from `book/OmniLLM_Book.md` (the master Markdown) by `book/build_pdf.py`. To add new content, edit the master and rebuild:

```bash
python book/build_pdf.py
```

For example, to fold the `compass_artifact_*.md` research notes into the book as an appendix:

```bash
# 1. Append the artifact to the master, with a page break and heading
printf "\n\n\\\\newpage\n\n# Appendix H — Pepper-LLM Integration Survey\n\n" \
    >> book/OmniLLM_Book.md
cat compass_artifact_wf-*.md >> book/OmniLLM_Book.md

# 2. (Optional) Add an entry to the Table of Contents in book/OmniLLM_Book.md
#    just below the "Appendix G" line.

# 3. Rebuild the PDF
python book/build_pdf.py
```

The builder will:

* convert Markdown → HTML (with `tables`, `fenced_code`, `codehilite`, `toc`, `sane_lists`)
* register DejaVu Sans + DejaVu Sans Mono with ReportLab (so arrows, em-dashes, and Greek letters render correctly)
* substitute Unicode box-drawing characters with ASCII equivalents inside code fences (because xhtml2pdf doesn't honour `@font-face` inside `<pre>` blocks)
* swap emoji DejaVu can't render for short text labels (👤 → `[Human]`, ⚠ → `(!)`, etc.)
* emit `book/OmniLLM_Book.pdf` and `book/OmniLLM_Book.html`

If you add new emoji or special characters and they render as `■` squares in the PDF, add them to `_EMOJI_REPLACE` or `_BOX_REPLACE` in `book/build_pdf.py` and rerun the build.

---

## Contributing

1. Update `knowledge_base/` files with real data for your lab / deployment.
2. Add new models via `config/models.yaml`.
3. Add new HRI task routings via the `routing.hri_task_routing` block in the same YAML.
4. Run `pytest tests/ -v` before opening a PR.

---

## License

MIT — see [LICENSE](LICENSE).

---

<div align="center">
<b>OmniLLM — Compare, Route, and Orchestrate Every LLM — and Put Them Inside a Robot.</b><br>
<i>Powering the Embodied LLM Arena: the first multi-LLM benchmark through social-robot interaction.</i><br><br>
Built for the open-source AI and HRI communities.
</div>
