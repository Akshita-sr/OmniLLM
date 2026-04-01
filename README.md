# 🧠 OmniLLM

> **Compare, Route, and Orchestrate Every LLM — Today and Tomorrow**  
> *Now powering the* ***Embodied LLM Arena*** *— the first study to benchmark LLMs through social robot interaction*

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Tests](https://img.shields.io/badge/tests-278%20passing-brightgreen.svg)](#-testing)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](https://github.com/Akshita-sr/OmniLLM/pulls)

> 🆕 **New to this project?** Start with **[GETTING_STARTED.md](GETTING_STARTED.md)** — a beginner-friendly guide from scratch.

---

## 📑 Table of Contents

1. [Goal & Vision](#-goal--vision)
2. [What's New — Embodied LLM Arena](#-whats-new--embodied-llm-arena)
3. [System Architecture](#-system-architecture)
4. [Module Overview](#-module-overview)
5. [State of the Art](#-state-of-the-art)
6. [Evaluation Axes](#-evaluation-axes)
7. [Installation & Setup](#-installation--setup)
8. [Usage Guide](#-usage-guide)
   - [CLI Commands](#cli-commands)
   - [Running the Pepper AI Server](#running-the-pepper-ai-server)
   - [LangGraph Agent Pipeline](#langgraph-agent-pipeline)
   - [RAG Knowledge Base](#rag-knowledge-base)
   - [HRI Experiment Manager](#hri-experiment-manager)
   - [Questionnaire & ELO Scoring](#questionnaire--elo-scoring)
9. [Experimental Design](#-experimental-design)
10. [Knowledge Base Files](#-knowledge-base-files)
11. [Automatic Evaluation Pipeline](#-automatic-evaluation-pipeline)
12. [Project Structure](#-project-structure)
13. [Contributing](#-contributing)
14. [License](#-license)

---

## 🎯 Goal & Vision

OmniLLM is a **living, extensible platform** for comparing, evaluating, and routing prompts across multiple Large Language Models simultaneously. It goes far beyond simple model comparison:

| Capability | Description |
|---|---|
| **🔀 Smart Routing** | Learns from evaluation history to auto-select the best model per task within budget/latency constraints |
| **💰 Cost Tracking** | Real-time spend tracking per model, per session |
| **🗳️ Consensus Ensembles** | "LLM Council" dispatches to multiple models and synthesises a superior combined answer |
| **🤖 Embodied LLM Arena** | Benchmarks LLMs through real human-robot interaction with Pepper — the world's first such study |
| **🧠 LangGraph Pipeline** | Full multi-node agent graph: Whisper STT → Language Detection → Task Classification → RAG / Direct LLM → Robot Action Plan |
| **📚 RAG Knowledge Base** | ChromaDB-backed retrieval-augmented generation over lab documents (visitor profiles, schedules, maps, FAQs) |
| **📊 LLM-as-Judge** | Three research-backed evaluation patterns (Referenceless, Reference-Based, Pairwise) |
| **🔌 Plugin Architecture** | Adding a new model requires only 5 lines of YAML — zero code changes |

The ultimate vision: connect the best LLM or ensemble of LLMs to social robots for truly capable embodied AI — **an AI brain that is never locked to a single model**.

---

## 🆕 What's New — Embodied LLM Arena

### The Research Gap

Current LLM evaluations (MMLU, Chatbot Arena, LiveBench) are **entirely text-based**. Social robot studies that use LLMs connect only a single model (typically ChatGPT). **No study has**:

- (a) compared multiple LLMs as interchangeable backends for a social robot
- (b) applied dynamic smart routing between models during live HRI
- (c) evaluated whether LLM rankings change when evaluated through embodied interaction rather than text-only benchmarks

### Research Hypotheses

| # | Hypothesis |
|---|---|
| **H1** | LLM quality rankings from embodied HRI will differ significantly from text-only benchmark rankings |
| **H2** | Dynamic smart routing between LLMs based on task type and language will produce higher user satisfaction than any single fixed-model configuration |
| **H3** | RAG-augmented responses will be rated significantly more accurate and trustworthy across all LLM backends |

### The Four Task Types

| Task | Name | Examples | Why Robot is Essential |
|---|---|---|---|
| **T1** | Information Retrieval | "What time does the lab open?" / "Tell me about Prof. X" | Pepper greets visitors, uses tablet to show info, gestures while explaining |
| **T2** | Navigation / Guidance | "Where is Room 305?" / "Point me to the cafeteria" | Pepper physically points in directions, shows map on tablet |
| **T3** | Social Conversation | "How are you?" / "What do you think about AI?" | Physical presence creates social pressure; eye contact and gestures change perceived quality |
| **T4** | Multilingual | Repeat any task in a different language | Robot's embodiment makes multilingual experience more immersive |

### Five Experimental Conditions

| Condition | Description | What It Tests |
|---|---|---|
| **A** | Fixed Cloud LLM (GPT-4o-mini for all tasks) | Baseline cloud performance |
| **B** | Fixed Local LLM (Llama3:8b via Ollama) | Baseline local/free performance |
| **C** | Smart-Routed (OmniLLM selects best model per task) | Smart routing effectiveness |
| **D** | Consensus / Council (3 models answer, best synthesised) | Consensus vs. single model |
| **E** | RAG-Off Control (same as A but without RAG) | Isolates RAG contribution |

---

## 🏛️ System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        HUMAN PARTICIPANT                             │
│           Speaks to Pepper → Sees tablet → Hears response            │
└────────────────────────────┬────────────────────────────────────────┘
                             │ Voice (microphone)
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│              PEPPER ROBOT  (Python 2.7 — NAOqi Process)             │
│                                                                      │
│  ALAudioDevice ──capture WAV──▶ HTTP POST to AI Server              │
│  ALAnimatedSpeech ◀── response text ── HTTP response                │
│  ALMotion       ◀── gesture commands ── JSON action plan            │
│  ALTabletService◀── display content ── HTML/image URL               │
│  ALFaceDetection → triggers interaction start                       │
│                                                                      │
│       ↕  HTTP (localhost:5000 / omnillm.server.app)  ↕              │
└─────────────────────────────────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│              AI SERVER  (Python 3.11+ — omnillm.server.app)         │
│                                                                      │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │              LangGraph Agent Graph  (hri/agent_graph.py)      │  │
│  │                                                                │  │
│  │  [START] → [Transcribe Audio (Whisper STT)]                   │  │
│  │         → [Detect Language]                                    │  │
│  │         → [Classify Task Type  T1/T2/T3/T4]                   │  │
│  │         → [CONDITIONAL ROUTING]                                │  │
│  │              ├─ T1 Info Retrieval  → [RAG Pipeline]           │  │
│  │              ├─ T2 Navigation      → [RAG + Gesture Planner]  │  │
│  │              ├─ T3 Social Chat     → [Direct LLM]             │  │
│  │              └─ T4 Multilingual    → [Language-Optimal LLM]   │  │
│  │         → [OmniLLM Smart Router / Council]                     │  │
│  │         → [Generate Robot Action Plan]                         │  │
│  │         → [Log Everything  (ExperimentLogger)]                 │  │
│  │         → [RESPOND to Pepper via HTTP]                         │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                                                                      │
│  ┌──────────────────┐  ┌──────────────────┐  ┌─────────────────┐   │
│  │   RAG Pipeline   │  │  OmniLLM Core    │  │  Data Logger    │   │
│  │  ChromaDB +      │  │  LiteLLM Gateway │  │  Timestamps     │   │
│  │  Fallback Search │  │  Smart Router    │  │  Latencies      │   │
│  │  PDF/CSV/TXT KB  │  │  LLM-as-Judge    │  │  Model used     │   │
│  └──────────────────┘  │  ELO Scorer      │  │  Transcripts    │   │
│                         │  Cost Tracker    │  │  Task success   │   │
│                         └──────────────────┘  └─────────────────┘   │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │              LLM Backends (via LiteLLM)                      │   │
│  │  ┌─────────┐ ┌────────┐ ┌──────────┐ ┌──────────┐          │   │
│  │  │GPT-4o-  │ │Claude  │ │Gemini    │ │DeepSeek  │          │   │
│  │  │mini     │ │Haiku   │ │Flash     │ │V3        │          │   │
│  │  └─────────┘ └────────┘ └──────────┘ └──────────┘          │   │
│  │  ┌─────────────────────────────────────────────┐             │   │
│  │  │  Ollama Local: Llama3:8b, Qwen2.5:7b,      │             │   │
│  │  │  Mistral:7b, DeepSeek-R1:14b                │             │   │
│  │  └─────────────────────────────────────────────┘             │   │
│  └──────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 🧩 Module Overview

```
omnillm/
├── gateway.py           # Unified LLM Gateway — LiteLLM bridge for 100+ providers
├── router.py            # Smart Router — 6 strategies incl. TASK_TYPE for HRI
├── consensus.py         # Consensus Engine — LLM Council with 5 synthesis strategies
├── evaluator.py         # LLM-as-Judge — Referenceless, Reference-Based, Pairwise
├── scorer.py            # ELO Rating System — Chatbot Arena-style leaderboard
├── cli.py               # Rich CLI — 10+ commands (ask, evaluate, compare, council…)
│
├── hri/                 # ── Embodied LLM Arena ──────────────────────────────────
│   ├── agent_graph.py   # LangGraph multi-node pipeline (NEW)
│   ├── classifier.py    # HRI Task Classifier — T1/T2/T3/T4 (rule-based + LLM)
│   ├── language_detector.py  # Language detection → optimal model mapping
│   └── experiment.py    # ExperimentManager — conditions A–E, participant sessions
│
├── rag/
│   └── pipeline.py      # RAG Pipeline — ChromaDB + fallback keyword search
│
├── robotics/
│   ├── bridge.py        # Abstract RobotBridge + RobotAction dataclass
│   ├── pepper.py        # Pepper HTTP bridge (Python 3.x ↔ NAOqi)
│   ├── nao.py           # NAO HTTP bridge
│   ├── buddy.py         # Buddy WebSocket bridge
│   ├── gesture_planner.py   # Task → gesture + LED colour mapping
│   └── whisper_stt.py   # Whisper STT wrapper — local & API (NEW)
│
├── server/              # ── AI Server ────────────────────────────────────────
│   ├── app.py           # Flask HTTP bridge (POST /interact, /transcribe…) (NEW)
│   └── naoqi_client.py  # Python 2.7 NAOqi client for Pepper (NEW)
│
├── utils/
│   ├── experiment_logger.py  # Interaction logging — latency, tokens, cost, RAG scores
│   ├── questionnaire.py      # Likert-scale questionnaires + Godspeed + ELO pref (NEW)
│   ├── cost_tracker.py       # Per-model, per-session cost tracking
│   └── export.py             # CSV, JSON, Markdown export
│
└── tasks/               # YAML task definitions for standard benchmarks
    └── loader.py

config/
└── models.yaml          # Model registry — add new models with 5 lines of YAML

knowledge_base/          # RAG knowledge base (dummy data — update with real data)
├── visitor_profiles.csv # Lab visitors: names, roles, visit times
├── lab_info.txt         # Room locations, hours, WiFi, safety rules
├── research_projects.txt# Active research project descriptions
├── event_schedule.csv   # Seminars, meetings, open days
├── university_map.txt   # Building layout and navigation directions
└── faq.txt              # Frequently asked questions
```

---

## 🏛️ State of the Art

### The Collapse of Static Benchmarks

Static benchmarks — MMLU, HumanEval, GSM8K — have become unreliable due to:

- **Data Contamination**: Models trained on web-scraped data that includes benchmark test sets. (arXiv:2502.17521)
- **Benchmark Saturation**: Top models all score >80% on MMLU, making it non-discriminative.
- **Benchmark Errors**: Many "wrong" model answers are actually correct responses to ambiguous questions. (arXiv:2506.23864)

**OmniLLM's solution**: Dynamic evaluation via YAML task files + LLM-as-Judge, analogous to [LiveBench](https://livebench.ai) (ICLR 2025).

### LLM-as-Judge — The New Evaluation Paradigm

Three research-validated patterns (arXiv:2412.05579):

1. **Referenceless (G-Eval)**: Judge evaluates response quality independently — coherence, accuracy, helpfulness, safety
2. **Reference-Based**: Judge compares response to a gold-standard answer — for factual/RAG tasks
3. **Pairwise (ELO)**: Judge compares two responses head-to-head — avoids position bias via answer swapping

### The Embodied LLM Arena — Novel Contribution

No prior work has:
- Compared multiple LLMs side-by-side through a social robot
- Applied dynamic LLM routing during live HRI
- Measured whether embodied rankings correlate with or diverge from text-only rankings

This study fills that gap, using Pepper as an interactive LLM evaluation platform.

---

## 📐 Evaluation Axes

OmniLLM evaluates models across **8 orthogonal axes**:

| # | Axis | What It Measures | Embodied Arena Relevance |
|---|------|-----------------|--------------------------|
| 1 | **Reasoning** | Logic, multi-step inference | T3 Social, T1 complex queries |
| 2 | **Knowledge** | Factual accuracy, MMLU-style | T1 Info Retrieval with RAG |
| 3 | **Code** | Write/debug/explain code | Background research tasks |
| 4 | **Instruction Following** | JSON schema, constraints | Robot action plan generation |
| 5 | **Safety** | Refusal, PII handling, bias | All interactions |
| 6 | **Latency** | TTFT, tokens/sec | Critical for robot response feel |
| 7 | **Cost Efficiency** | Quality per dollar | Choosing Ollama vs. cloud |
| 8 | **Robot-Readiness** | Structured JSON for robot control | Gesture + LED action plans |

---

## 🚀 Installation & Setup

### Basic Install (LLM evaluation only)

```bash
git clone https://github.com/Akshita-sr/OmniLLM.git
cd OmniLLM
python -m venv .venv
source .venv/bin/activate   # Linux/macOS
# .venv\Scripts\activate    # Windows

pip install -e ".[dev]"

# Configure API keys
cp .env.example .env
# Edit .env and add: OPENAI_API_KEY, ANTHROPIC_API_KEY, GOOGLE_API_KEY, etc.

# Verify
omnillm models
```

### Full Install — Embodied LLM Arena (adds RAG + LangGraph)

```bash
pip install -e ".[all]"

# For local LLMs (free, privacy-preserving):
curl -fsSL https://ollama.com/install.sh | sh
ollama pull llama3:8b
ollama pull qwen2.5:7b
ollama pull mistral:7b
ollama pull deepseek-r1:14b

# For local Whisper STT:
pip install openai-whisper
```

### Required API Keys (`.env` file)

```bash
OPENAI_API_KEY=sk-...          # GPT-4o-mini, Whisper API
ANTHROPIC_API_KEY=sk-ant-...   # Claude Haiku
GOOGLE_API_KEY=...              # Gemini Flash
DEEPSEEK_API_KEY=...            # DeepSeek V3
```

---

## 📖 Usage Guide

### CLI Commands

```bash
# List all registered models
omnillm models

# Ask all models a question
omnillm ask "Explain quantum computing" --all

# Ask specific models
omnillm ask "Hello" -m openai-gpt4o-mini -m claude-haiku

# Run benchmark evaluation
omnillm evaluate
omnillm evaluate -m openai-gpt4o-mini -c reasoning
omnillm evaluate -o results/eval_2026.json

# Pairwise comparison
omnillm compare "Write a poem about robots" \
    --model-a openai-gpt4o-mini --model-b gemini-2.5-flash

# LLM Council (consensus)
omnillm council "What is consciousness?"
omnillm council "Is P=NP?" --strategy majority_vote

# Smart routing
omnillm route "Where is Room 305?" --strategy TASK_TYPE
omnillm route "Debug this code" --strategy BEST_QUALITY --budget 0.01

# View ELO leaderboard
omnillm leaderboard
omnillm leaderboard --category reasoning

# View costs
omnillm costs
```

### Running the Pepper AI Server

The Flask server bridges Pepper (Python 2.7/NAOqi) with the Python 3.x AI stack:

```bash
# Start the AI server (runs on localhost:5000)
python -m omnillm.server.app

# With options:
python -m omnillm.server.app \
    --host 0.0.0.0 \
    --port 5000 \
    --model openai-gpt4o-mini \
    --kb knowledge_base/

# API endpoints:
# POST /interact    — main endpoint (audio or text → RobotAction JSON)
# POST /transcribe  — audio → text (Whisper STT)
# POST /evaluate    — submit questionnaire scores
# GET  /health      — liveness probe
# GET  /status      — server configuration
# GET  /export      — download all interaction logs as JSON
```

**Example request** (text mode):

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

**Example response**:
```json
{
  "speech": "Room 305 is on the 3rd floor. Take the lift or Staircase A on your left.",
  "gesture": "point_left",
  "emotion_led": "#00AAFF",
  "metadata": {
    "task_type": "navigation",
    "model_id": "openai-gpt4o-mini",
    "rag_enabled": true
  }
}
```

### Running the NAOqi Client (Python 2.7)

On the Pepper robot (or a machine with NAOqi SDK):

```bash
python omnillm/server/naoqi_client.py \
    --robot-ip 192.168.1.100 \
    --server-ip 192.168.1.50 \
    --participant P001 \
    --condition C
```

### LangGraph Agent Pipeline

Use the agent graph programmatically (Python 3.x):

```python
from omnillm.gateway import LLMGateway
from omnillm.rag import RAGPipeline
from omnillm.hri import build_hri_graph
from omnillm.utils import ExperimentLogger

gateway = LLMGateway()
rag = RAGPipeline(gateway=gateway)
rag.index_directory("knowledge_base/")
logger = ExperimentLogger()

graph = build_hri_graph(gateway=gateway, rag=rag, logger=logger)

# Text-only mode (no audio hardware needed)
result = await graph.ainvoke({
    "utterance": "Where is Room 305?",
    "participant_id": "P001",
    "session_id": "s1",
    "condition": "C",
    "rag_enabled": True,
})
print(result["response_text"])   # Grounded answer from RAG + LLM
print(result["robot_action"])    # {"speech": "...", "gesture": "point_left", ...}
```

**Graph nodes** (in execution order):

1. `transcribe_audio` — Whisper STT (skipped in text-only mode)
2. `detect_language` — ISO 639-1 language code
3. `classify_task` — T1/T2/T3/T4 classification
4. Conditional branch:
   - `rag` (T1 Info Retrieval) — ChromaDB retrieval + LLM answer
   - `nav_rag` (T2 Navigation) — ChromaDB + gesture planner
   - `direct_llm` (T3 Social / Condition E) — direct LLM call
   - `multilingual_llm` (T4) — language-optimal model
5. `smart_router` — OmniLLM routing/council (Conditions C & D)
6. `generate_action_plan` — builds RobotAction dict
7. `log_interaction` — ExperimentLogger records everything

### RAG Knowledge Base

Index documents and query them:

```python
from omnillm.rag import RAGPipeline
from omnillm.gateway import LLMGateway

rag = RAGPipeline(gateway=LLMGateway(), model_id="openai-gpt4o-mini")

# Index the knowledge base
rag.index_directory("knowledge_base/")   # auto-indexes all .txt, .csv, .pdf

# Query
resp = await rag.query("What is the WiFi password?")
print(resp.answer)            # "Visitor WiFi: UniGuest / Welcome2026!"
print(resp.faithfulness_score) # 0.95 (LLM-as-Judge score)
print(resp.hallucination_detected)  # False
```

**Knowledge base files** (in `knowledge_base/`):

| File | Content | Task Type |
|------|---------|-----------|
| `visitor_profiles.csv` | Names, roles, visit times | T1 — "What time does Alice arrive?" |
| `lab_info.txt` | Rooms, hours, WiFi, safety | T1 — "What is the WiFi password?" |
| `research_projects.txt` | Project descriptions | T1 — "What is OmniLLM about?" |
| `event_schedule.csv` | Seminars, open days, deadlines | T1 — "When is the next open day?" |
| `university_map.txt` | Building layout, directions | T2 — "How do I get to Room 305?" |
| `faq.txt` | Common questions & answers | T1 — Baseline evaluation |

Update these files with your real lab data before running the experiment.

### HRI Experiment Manager

```python
from omnillm.hri import ExperimentManager, ExperimentCondition

manager = ExperimentManager(n_participants=20)

# Create a session for participant P001, assign counterbalanced conditions
session = manager.create_session("P001")
print(session.assigned_conditions)   # e.g. ["C", "A", "D"] (counterbalanced)

# Classify an utterance
from omnillm.hri import HRITaskClassifier
classifier = HRITaskClassifier()
result = classifier.classify("Where is the cafeteria?")
print(result.task_type)    # HRITaskType.NAVIGATION
print(result.confidence)   # 0.92
```

### Questionnaire & ELO Scoring

Collect post-interaction ratings and update the Embodied LLM Leaderboard:

```python
from omnillm.utils.questionnaire import (
    InteractionQuestionnaire,
    GodspeedResponse,
    PairwisePreference,
    QuestionnaireCollector,
)
from omnillm.scorer import EloScorer

collector = QuestionnaireCollector()

# After each condition block
q = InteractionQuestionnaire(
    session_id="s1", participant_id="P001", condition="C",
    accuracy=6, naturalness=6, trust=6,
    gesture_appropriateness=5, response_speed=7,
)
collector.add_interaction_response(q)

# Pairwise preference (at end of session)
pref = PairwisePreference(
    session_id="s1", participant_id="P001",
    condition_a="A", condition_b="C", preferred="C",
)
collector.add_pairwise_preference(pref)

# Update Embodied ELO leaderboard
elo = EloScorer()
elo.record_match("condition-C", "condition-A", "model_a", category="embodied_hri")

# Save data
collector.save("results/questionnaire_data.json")
collector.to_csv("results/questionnaire_data.csv")
print(collector.summary_by_condition())
print(elo.get_leaderboard())
```

---

## 🔬 Experimental Design

### Participants

15–25 people (lab visitors, students, staff). Each participant interacts with Pepper under 3 different LLM conditions (counterbalanced via Latin square). Total: ~20 participants × 3 conditions × 4 tasks = **240 interaction data points**.

### Independent Variables

- **LLM Backend**: GPT-4o-mini / Claude Haiku / Gemini Flash / DeepSeek-V3 / Llama3:8b (Ollama) / Smart-Routed
- **RAG Condition**: RAG-on vs. RAG-off
- **Language**: Participant's native language (auto-detected by Whisper + LanguageDetector)

### Dependent Variables — Automatic (logged by `ExperimentLogger`)

| Variable | How Measured |
|----------|-------------|
| Which LLM was used | `model_id` field |
| Response latency | Wall clock from end-of-speech to start-of-speech |
| Token count (input + output) | LiteLLM usage |
| Cost per interaction | From `models.yaml` pricing |
| RAG retrieval score | ChromaDB cosine similarity |
| RAG faithfulness | LLM-as-Judge (0–1) |
| Hallucination detected | Response vs. retrieved chunks comparison |
| Language detected | WhisperSTT + LanguageDetector |
| Task classification | HRITaskClassifier (T1–T4) |

### Dependent Variables — Human-Rated (`InteractionQuestionnaire`)

- "The robot's answers were accurate" (1–7 Likert)
- "The robot was natural to talk to" (1–7 Likert)
- "I trust the information the robot gave me" (1–7 Likert)
- "The robot's gestures were appropriate" (1–7 Likert)
- "The robot responded quickly enough" (1–7 Likert)
- Godspeed subscales: Anthropomorphism, Animacy, Likeability, Perceived Intelligence, Perceived Safety (1–5)
- Pairwise preference: "Which version of Pepper did you prefer?" → feeds ELO leaderboard

---

## 📊 Automatic Evaluation Pipeline

After every interaction, OmniLLM automatically:

1. **Referenceless Evaluation**: Sends prompt + response to LLM-as-judge (GPT-4o-mini) — rates coherence, helpfulness, fluency, safety (1–10 each)
2. **RAG Faithfulness Score**: For T1/T2 tasks, evaluates whether the response faithfully uses retrieved document chunks
3. **Hallucination Detection**: Flags claims not supported by retrieved documents. Computes per-model hallucination rate
4. **Pairwise ELO Update**: Participant preference → updates the "Embodied LLM Leaderboard"
5. **Latency-Quality Composite Score**:
   ```
   value = quality × 0.5 + (1/latency_ms) × 0.3 + (1/cost_usd) × 0.2
   ```
6. **Cross-Reference with Standard Benchmarks**: Correlate embodied scores with MMLU/Chatbot Arena — the *discrepancy* is the key finding

---

## �� Testing

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run all 278 tests (no API keys needed — uses mocks)
pytest tests/ -v

# Run specific test files
pytest tests/test_hri.py -v
pytest tests/test_rag.py -v
pytest tests/test_new_components.py -v   # New: agent_graph, whisper, questionnaire

# Run with coverage
pytest tests/ --cov=omnillm --cov-report=term-missing
```

### Test Coverage by Module

| Module | Tests | Description |
|--------|-------|-------------|
| `test_gateway.py` | 21 | LiteLLM model strings, error handling |
| `test_router.py` | 24 | All 6 routing strategies incl. TASK_TYPE |
| `test_consensus.py` | 20 | All 5 synthesis strategies, ELO updates |
| `test_evaluator.py` | 15 | Referenceless, Reference-Based, Pairwise judge |
| `test_scorer.py` | 22 | ELO math, leaderboard, history |
| `test_hri.py` | 51 | Classifier T1–T4, LanguageDetector, ExperimentManager |
| `test_rag.py` | 26 | Indexing, retrieval, faithfulness, hallucination |
| `test_gesture_planner.py` | 30 | Task → gesture mapping for all 4 types |
| `test_experiment_logger.py` | 16 | Logging, CSV/JSON export |
| `test_new_components.py` | 53 | agent_graph, whisper_stt, questionnaire, server, KB files |

---

## 📁 Project Structure

```
OmniLLM/
├── omnillm/               # Main Python package
│   ├── hri/               # Embodied LLM Arena — HRI components
│   ├── rag/               # RAG pipeline (ChromaDB + fallback)
│   ├── robotics/          # Robot bridges + Whisper STT
│   ├── server/            # Flask AI server + NAOqi Python 2.7 client
│   └── utils/             # Logging, questionnaire, cost tracking, export
├── knowledge_base/        # RAG knowledge base (dummy data — update with real data)
├── config/
│   ├── models.yaml        # Model registry (add new models here)
│   └── tasks/             # Benchmark task YAML files
├── tests/                 # 278 unit tests (pytest)
├── results/               # Evaluation results (auto-created)
├── pyproject.toml         # Project metadata + optional dependencies
├── requirements.txt       # Core + optional dependencies
├── .env.example           # API key template
├── GETTING_STARTED.md     # Beginner-friendly guide
└── README.md              # This file
```

### Install Extras

| Extra | What it adds |
|-------|-------------|
| `pip install -e ".[dev]"` | pytest, mocks — for development |
| `pip install -e ".[robotics]"` | Flask, websockets — for the AI server |
| `pip install -e ".[hri]"` | ChromaDB, LangChain, LangGraph, langdetect — for RAG + agent |
| `pip install -e ".[all]"` | Everything above |

---

## 🤝 Contributing

### Adding a New LLM (5 lines of YAML)

Edit `config/models.yaml`:

```yaml
my-new-model:
  id: my-new-model
  provider: openai          # or anthropic, google, ollama, openai_compatible
  model: my-model-name
  api_key_env: MY_API_KEY
  cost_per_1m_input: 1.00
  cost_per_1m_output: 3.00
  type: cloud
```

No Python code changes required.

### Adding a Task to the HRI Routing

Edit `config/models.yaml` under the `routing.hri_task_routing` section to map task types to model IDs.

### Running the Full HRI Experiment

1. Update `knowledge_base/` files with real lab data
2. Start the AI server: `python -m omnillm.server.app`
3. Start the NAOqi client on/near Pepper: `python omnillm/server/naoqi_client.py --robot-ip <IP>`
4. Follow the protocol in the experimental design section
5. Export data: `GET http://localhost:5000/export`
6. Analyze: use `ExperimentLogger.save()` + `QuestionnaireCollector.save()`

---

## 📄 License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.

---

<div align="center">
<b>🧠 OmniLLM — Compare, Route, and Orchestrate Every LLM — Today and Tomorrow</b><br>
<i>Now also powering the Embodied LLM Arena: the first multi-LLM benchmark through social robot interaction</i><br><br>
Built with ❤️ for the open-source AI and HRI communities
</div>
