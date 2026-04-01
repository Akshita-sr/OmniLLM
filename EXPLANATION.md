# 📖 OmniLLM — Complete Explanation for Beginners

> **What this file is:** A thorough, plain-English walkthrough of *every* part of OmniLLM — what each file does, why the code is structured the way it is, all terminal commands you will ever type, every tool and library used, and a complete guide to connecting OmniLLM to an old Pepper robot that runs Python 2.7, NAOqi, and Choregraphe.
>
> **Who this is for:** Absolute beginners in programming who want to understand this project from zero.

---

## Table of Contents

1. [What Is OmniLLM? (No Jargon)](#1-what-is-omnillm-no-jargon)
2. [Why Does This Project Exist?](#2-why-does-this-project-exist)
3. [The Big Picture — How All Parts Connect](#3-the-big-picture--how-all-parts-connect)
4. [Every File and Folder Explained](#4-every-file-and-folder-explained)
5. [Module Deep-Dive — What Each Python File Does and Why](#5-module-deep-dive--what-each-python-file-does-and-why)
6. [Features Reference — Everything OmniLLM Can Do](#6-features-reference--everything-omnillm-can-do)
7. [Complete Terminal Commands Reference](#7-complete-terminal-commands-reference)
8. [All Tools and Libraries Used](#8-all-all-tools-and-libraries-used)
9. [Connecting to the Old Pepper Robot (NAOqi + Choregraphe + Python 2.7)](#9-connecting-to-the-old-pepper-robot-naoqi--choregraphe--python-27)
10. [Step-by-Step Setup from Zero](#10-step-by-step-setup-from-zero)
11. [Troubleshooting for Beginners](#11-troubleshooting-for-beginners)
12. [Glossary — Every Technical Word Explained](#12-glossary--every-technical-word-explained)

---

## 1. What Is OmniLLM? (No Jargon)

Imagine you want to ask a question and you have access to five different experts: one from OpenAI (ChatGPT), one from Anthropic (Claude), one from Google (Gemini), one from DeepSeek, and a free local expert running on your own computer (Llama via Ollama). Each expert has different strengths, prices, and speeds.

**OmniLLM is the manager of all those experts.** It lets you:

- Talk to all of them through a single, simple command
- Automatically figure out which expert is best for each type of question
- Ask several experts and combine their answers into one reliable answer
- Grade and score every expert so you always know who is performing best
- Connect all those experts to a physical robot (Pepper) so the robot can hold intelligent conversations

### In One Sentence

> OmniLLM is a Python platform that lets you compare, route, evaluate, and ensemble multiple AI language models — and connect them to physical robots.

---

## 2. Why Does This Project Exist?

### The Problem with Current AI Evaluation

Most AI benchmarks (tests) are done entirely in text on a computer screen. Nobody had ever:

1. Put **multiple** AI models side-by-side and tested them through a **physical robot**
2. Let the robot **automatically switch** between models depending on what kind of question is being asked
3. Measured whether the AI model rankings **change** when you test them through a robot versus testing them on paper

OmniLLM was built to fill that gap — it is the backend for the **Embodied LLM Arena**, a research study where real people interact with a Pepper robot and each interaction is powered by a different AI model.

### Why the Code Is Structured This Way

| Design Decision | Reason |
|---|---|
| **YAML model registry** | Adding a new AI model should take 30 seconds, not hours of coding |
| **Two-process architecture (Python 3 server + Python 2.7 NAOqi client)** | Pepper's robot SDK (NAOqi) is permanently locked to Python 2.7; the AI stack needs Python 3.11+; an HTTP bridge solves the incompatibility |
| **LiteLLM as the gateway** | Writing separate code for each AI provider would be 1000+ lines; LiteLLM wraps them all in one API |
| **LangGraph for the agent pipeline** | The robot's decision process has multiple steps with conditional branching (if French → use French model; if navigation question → show map); LangGraph makes this readable and testable |
| **ChromaDB for RAG** | The robot needs to answer questions about a specific lab — training a new AI model is expensive; RAG lets you just upload lab documents |
| **Abstract RobotBridge class** | The same LLM logic should work with Pepper, NAO, or Buddy — only the last step (sending the command) differs |

---

## 3. The Big Picture — How All Parts Connect

Here is the complete data flow when someone speaks to Pepper:

```
Person speaks to Pepper
        │
        ▼
Pepper microphone captures audio (WAV file)
        │
        ▼  (Python 2.7 / NAOqi process)
naoqi_client.py — sends WAV bytes to AI server via HTTP POST
        │
        ▼  (HTTP, localhost:5000)
server/app.py — Flask AI server receives the audio
        │
        ▼
whisper_stt.py — OpenAI Whisper converts audio to text
                 "Where is Room 305?"
        │
        ▼
hri/agent_graph.py — LangGraph pipeline:
    1. language_detector.py  → detects language ("en")
    2. classifier.py         → classifies task type ("navigation" = T2)
    3. Conditional branch:
       │
       ├─ T1 Info Retrieval  → rag/pipeline.py (search lab documents)
       ├─ T2 Navigation      → rag/pipeline.py + gesture_planner.py
       ├─ T3 Social Chat     → gateway.py (direct LLM call)
       └─ T4 Multilingual    → gateway.py (language-appropriate model)
        │
        ▼
gateway.py — LiteLLM sends to chosen AI model
              (GPT-4o-mini / Claude / Gemini / Llama...)
        │
        ▼
gesture_planner.py — decides gesture ("point_left") + LED colour ("#00AAFF")
        │
        ▼
utils/experiment_logger.py — logs everything (latency, model used, score...)
        │
        ▼  (HTTP JSON response)
naoqi_client.py — receives: { "speech": "Room 305 is on the 3rd floor...",
                               "gesture": "point_left",
                               "emotion_led": "#00AAFF" }
        │
        ▼
Pepper robot:
  ALAnimatedSpeech.say("Room 305 is on the 3rd floor...")
  ALBehaviorManager.runBehavior("animations/Stand/Gestures/Explain_8")
  ALLeds.fadeRGB("FaceLeds", 0.0, 0.67, 1.0, 0.3)
```

---

## 4. Every File and Folder Explained

### Root-Level Files

| File | What it is | Why it exists |
|---|---|---|
| `README.md` | Main project documentation with academic references | The "homepage" for anyone visiting the repository |
| `GETTING_STARTED.md` | Beginner installation and usage guide | Step-by-step setup for new users |
| `EXPLANATION.md` | ← This file | Deep explanation of everything |
| `LICENSE` | MIT open-source licence text | Tells others they can use/modify this code freely |
| `pyproject.toml` | Python package configuration | Defines dependencies, version, and how to install the package |
| `requirements.txt` | Flat list of dependencies | Alternative install method (used by some systems) |
| `.env.example` | Template for secret API keys | Shows you what keys to set without exposing real secrets |
| `.gitignore` | List of files Git should ignore | Prevents accidentally committing `.env` files, `__pycache__`, etc. |

### `config/` — Configuration

| File | What it is |
|---|---|
| `config/models.yaml` | **The model registry** — every AI model available, with its provider, API key variable, and pricing. Adding a new model = adding 7 lines here. |
| `config/tasks/reasoning.yaml` | Test questions for logical reasoning (e.g., "If all A are B and all B are C, are all A C?") |
| `config/tasks/knowledge.yaml` | Test questions for factual knowledge (e.g., "What is the capital of France?") |
| `config/tasks/code.yaml` | Test questions for code generation/debugging |
| `config/tasks/instruction.yaml` | Test questions for following complex instructions |
| `config/tasks/safety.yaml` | Test questions that check if a model refuses dangerous requests |
| `config/tasks/robot.yaml` | Test questions specific to robot interaction (e.g., "Generate a JSON action plan for navigating to Room 305") |

### `omnillm/` — Main Python Package

| File/Folder | Purpose |
|---|---|
| `__init__.py` | Makes `omnillm` a Python package; exports key classes |
| `gateway.py` | **LLMGateway** — the single door to all AI models |
| `router.py` | **SmartRouter** — picks the best model for each task |
| `evaluator.py` | **Evaluator** — uses an AI judge to score responses |
| `scorer.py` | **EloScorer** — chess-style leaderboard for models |
| `consensus.py` | **ConsensusEngine** — the LLM Council that merges multiple answers |
| `cli.py` | The `omnillm` terminal command |
| `hri/` | Human-Robot Interaction research module |
| `rag/` | Retrieval-Augmented Generation (RAG) pipeline |
| `robotics/` | Robot integration layer |
| `server/` | Flask AI server + NAOqi client |
| `tasks/` | Task loading from YAML |
| `utils/` | Shared utilities (logging, cost tracking, export) |

### `omnillm/hri/` — HRI Research Module

| File | What it does |
|---|---|
| `agent_graph.py` | **The brain** — full LangGraph multi-node pipeline: audio → text → task type → response → robot action |
| `classifier.py` | **HRITaskClassifier** — labels any utterance as T1 (info), T2 (navigation), T3 (social), or T4 (multilingual) |
| `language_detector.py` | **LanguageDetector** — detects what language was spoken, maps to best model for that language |
| `experiment.py` | **ExperimentManager** — manages the 5 experimental conditions (A–E) and participant sessions |

### `omnillm/rag/` — RAG Pipeline

| File | What it does |
|---|---|
| `pipeline.py` | **RAGPipeline** — indexes documents (TXT, CSV, PDF) and answers questions by searching them. Uses ChromaDB when installed, falls back to keyword search if not. |

### `omnillm/robotics/` — Robot Bridges

| File | What it does |
|---|---|
| `bridge.py` | Abstract base class `RobotBridge` that all robot integrations must follow. Also defines `RobotAction` (speech + gesture + LED) and `RobotSensorData` dataclasses. |
| `pepper.py` | **PepperBridge** — sends commands to Pepper via HTTP to the NAOqi bridge server |
| `nao.py` | **NAOBridge** — same but for NAO robot |
| `buddy.py` | **BuddyBridge** — sends commands to Buddy robot via WebSocket |
| `gesture_planner.py` | **GesturePlanner** — reads LLM response text and decides the right gesture (e.g., "on your left" → "point_left") and LED colour |
| `whisper_stt.py` | **WhisperSTT** — converts audio bytes to text using either local Whisper or the OpenAI Whisper API |

### `omnillm/server/` — The AI Server

| File | What it does |
|---|---|
| `app.py` | **Flask HTTP server** (Python 3.x) — the main AI brain. Receives requests from Pepper, runs the LangGraph pipeline, returns robot action JSON. Endpoints: `POST /interact`, `POST /transcribe`, `POST /evaluate`, `GET /health`, `GET /status`, `GET /export` |
| `naoqi_client.py` | **Python 2.7 NAOqi client** — runs on/near Pepper. Captures audio, posts it to the server, executes the returned action on the robot. This is the only file in the project written for Python 2.7. |

### `omnillm/utils/` — Utilities

| File | What it does |
|---|---|
| `experiment_logger.py` | **ExperimentLogger** — records every HRI interaction (utterance, response, model used, latency, cost, RAG scores) to a JSONL log file |
| `questionnaire.py` | **QuestionnaireCollector** — collects and stores participant ratings (Likert 1–7, Godspeed subscales, pairwise preferences) |
| `cost_tracker.py` | **CostTracker** — accumulates USD spend per model per session |
| `export.py` | **Export** — converts log data to CSV, Markdown, or JSON reports |

### `knowledge_base/` — RAG Documents

These are the files Pepper uses to answer questions. Replace the placeholder content with your real lab data.

| File | What is in it | Example query it answers |
|---|---|---|
| `lab_info.txt` | Room numbers, opening hours, WiFi password, safety rules | "What is the WiFi password?" |
| `university_map.txt` | Building layout, floor plans, directions | "How do I get from the entrance to Room 305?" |
| `research_projects.txt` | Descriptions of active research projects | "What is the IRAI lab working on?" |
| `faq.txt` | Frequently asked questions and their answers | "Is there parking nearby?" |
| `visitor_profiles.csv` | Names, roles, and visit times of registered visitors | "What time does Dr. Smith arrive?" |
| `event_schedule.csv` | Seminars, open days, deadlines | "When is the next open day?" |

### `tests/` — Automated Tests

| File | What it tests |
|---|---|
| `test_gateway.py` | LLMGateway — model strings, error handling, cost calculation |
| `test_router.py` | SmartRouter — all 6 routing strategies |
| `test_evaluator.py` | Evaluator — all 3 judge patterns |
| `test_scorer.py` | EloScorer — ELO maths, leaderboard |
| `test_consensus.py` | ConsensusEngine — all 5 synthesis strategies |
| `test_rag.py` | RAGPipeline — indexing, retrieval, faithfulness, hallucination detection |
| `test_hri.py` | HRI module — classifier T1–T4, language detector, experiment manager |
| `test_gesture_planner.py` | GesturePlanner — gesture and LED mappings |
| `test_experiment_logger.py` | ExperimentLogger — recording and export |
| `test_new_components.py` | New components — agent graph, Whisper STT, questionnaire, server, KB files |

---

## 5. Module Deep-Dive — What Each Python File Does and Why

### 5.1 `gateway.py` — The Door to All AI Models

**The problem it solves:** Every AI company has a different API. OpenAI uses one format, Anthropic uses another, Google uses another. Writing separate code for each would be unmaintainable.

**The solution:** One class (`LLMGateway`) that reads `config/models.yaml` and uses LiteLLM under the hood. LiteLLM is a library that already knows how to talk to 100+ AI providers — OmniLLM just configures it via YAML.

**Key methods you need to know:**

```python
gateway = LLMGateway()

# Ask one model
response = await gateway.query("openai-gpt4o-mini", [
    {"role": "user", "content": "Hello!"}
])
print(response.content)       # The answer text
print(response.latency_ms)    # How long it took (milliseconds)
print(response.cost_usd)      # How much it cost in dollars

# Ask many models at the same time (runs in parallel)
responses = await gateway.query_multiple(
    ["openai-gpt4o-mini", "claude-haiku", "gemini-flash"],
    [{"role": "user", "content": "What is the capital of France?"}]
)
```

**Why `async`?** The `async/await` syntax means Python can send requests to multiple AI providers simultaneously, rather than waiting for one to finish before starting the next. Querying 5 models takes the same time as querying 1.

**The `litellm.drop_params = True` setting:** OpenAI's newer "o-series" reasoning models (o1, o3-mini) do not support the `temperature` parameter. Rather than crashing with an error, this setting silently removes unsupported parameters.

---

### 5.2 `router.py` — The Smart Router

**The problem it solves:** Different questions are best answered by different models. A maths puzzle needs a reasoning model; a quick greeting needs the fastest, cheapest model; a French question needs a model good at French.

**The solution:** `SmartRouter` reads past evaluation results and picks the best model according to a chosen strategy.

**Six routing strategies:**

| Strategy name | When to use it | How it picks |
|---|---|---|
| `BEST_QUALITY` | Research tasks, complex questions | Highest evaluation score |
| `LOWEST_COST` | Bulk processing, demos | Cheapest model that meets quality threshold |
| `LOWEST_LATENCY` | Real-time robot responses | Historically fastest model |
| `BEST_VALUE` | General use | Combines quality (50%), cost savings (30%), speed (20%) |
| `LOCAL_PREFERRED` | Privacy / offline / free | Ollama models first, cloud as fallback |
| `TASK_TYPE` | HRI experiment | Maps T1→GPT-4o-mini, T2→Gemini Flash, T3→Claude Haiku, T4→Gemini Flash |

**The router learns:** Every time you run an evaluation (`omnillm evaluate`), the results are saved to the `results/` folder. On the next run, the router reads those files and improves its decisions.

---

### 5.3 `evaluator.py` — The AI Judge

**The problem it solves:** How do you know if a response is good? Human evaluation is slow and expensive. OmniLLM uses *another* AI model as the judge.

**Three judge patterns:**

1. **Referenceless (G-Eval):** "Score this response on a scale of 1–10 for accuracy, helpfulness, fluency, and safety." No correct answer needed.

2. **Reference-Based:** "Compare this response to the correct answer. Score how close it is." Used for factual questions where you know the right answer.

3. **Pairwise:** "Here are two responses. Which is better?" Runs twice (A vs B, then B vs A) to cancel out the AI judge's tendency to prefer whichever response it sees first.

---

### 5.4 `scorer.py` — The ELO Leaderboard

**What ELO is:** Borrowed from chess. Every model starts with 1500 points. When model A beats model B in a pairwise comparison:
- A gains points (more if B was previously stronger)
- B loses points

After many comparisons, the rankings become statistically meaningful.

---

### 5.5 `consensus.py` — The LLM Council

**The problem it solves:** A single AI model can be confidently wrong. If three independent models all give the same answer, you can trust it more.

**How it works:**
1. Send the same question to all council models simultaneously
2. Compute semantic similarity between responses to find clusters of agreement
3. A judge LLM synthesises the best answer from the majority cluster
4. Report the agreement score and which models dissented

**Why this matters for robots:** A robot should not perform a potentially dangerous action unless multiple models independently agree on it.

---

### 5.6 `rag/pipeline.py` — Retrieval-Augmented Generation

**The problem it solves:** A general AI model doesn't know anything about your specific lab — room numbers, staff names, event schedules. You could fine-tune a model (very expensive), or you can just show it the relevant documents at query time.

**How RAG works:**
1. **Indexing:** Read all documents in `knowledge_base/`. Split each into ~500-word chunks. Store chunks in a vector database (ChromaDB) where similar text is stored near each other.
2. **Querying:** When a question comes in, convert the question to a vector (a list of numbers representing its meaning) and find the 3–5 most similar document chunks.
3. **Augmenting:** Prepend the retrieved chunks to the prompt: "Based on these documents: [chunks]. Answer: [question]"
4. **Answering:** The LLM answers with grounding in real documents — dramatically fewer hallucinations.

**Fallback:** If ChromaDB is not installed (`pip install chromadb`), the pipeline falls back to simple keyword search. Less accurate but still functional.

---

### 5.7 `hri/classifier.py` — Task Classifier

Labels any utterance into one of four task types:

| Code | Name | Example utterance | Why it matters |
|---|---|---|---|
| T1 | Info Retrieval | "What time does the lab open?" | Needs RAG (lab documents) |
| T2 | Navigation / Guidance | "Where is Room 305?" | Needs RAG + pointing gesture |
| T3 | Social Conversation | "How are you?" | Needs natural, empathetic response |
| T4 | Multilingual | "Où se trouve la salle 305 ?" | Needs language-appropriate model |

---

### 5.8 `hri/agent_graph.py` — The LangGraph Brain

This is the most complex file. It implements a multi-node **agent graph** using LangGraph — think of it as a flowchart where each box is a Python function and the arrows between them carry shared state.

**Nodes in execution order:**

1. `transcribe_audio` — converts WAV bytes to text via Whisper
2. `detect_language` — identifies the language (e.g., "fr" for French)
3. `classify_task` — assigns T1/T2/T3/T4
4. Conditional branch based on task type:
   - `rag_node` (T1) — RAG retrieval
   - `nav_rag_node` (T2) — RAG retrieval + gesture planning
   - `direct_llm_node` (T3) — direct LLM call
   - `multilingual_llm_node` (T4) — best-for-language model
5. `smart_router_node` — applies OmniLLM routing/council (for conditions C & D)
6. `generate_action_plan` — builds the final `RobotAction` dict
7. `log_interaction` — records everything in `ExperimentLogger`

**Why LangGraph?** A simple `if/elif` chain would work for 4 branches, but LangGraph makes the flow visualisable, testable at each node, and easy to extend with new branches.

---

### 5.9 `server/app.py` — The Flask AI Server

This is the Python 3.x server that receives requests from the Pepper robot.

**Endpoints:**

| Method | Path | What it does |
|---|---|---|
| `POST` | `/interact` | Main endpoint. Accepts `{"text": "..."}` or `{"audio": "<base64 WAV>"}`. Runs the LangGraph pipeline. Returns `{"speech": "...", "gesture": "...", "emotion_led": "..."}` |
| `POST` | `/transcribe` | Audio-only. Returns `{"text": "...", "language": "en"}` |
| `POST` | `/evaluate` | Submit questionnaire scores from participants |
| `GET` | `/health` | Returns `{"status": "ok"}` — used to check if server is running |
| `GET` | `/status` | Returns server configuration (model, RAG status, available models) |
| `GET` | `/export` | Downloads all interaction logs as JSON |

---

### 5.10 `server/naoqi_client.py` — The Pepper Side (Python 2.7)

This file runs **on Pepper** (or on a computer near Pepper). It is the only file in OmniLLM written for Python 2.7.

**What it does:**
1. Connects to Pepper via the NAOqi SDK
2. Wakes Pepper up and says the greeting
3. Loops forever:
   a. Records 5 seconds of audio from Pepper's front microphone
   b. Sends the WAV bytes to the AI server via HTTP POST
   c. Receives the `RobotAction` JSON back
   d. Executes: speech (`ALAnimatedSpeech`), gesture (`ALBehaviorManager`), LED colour (`ALLeds`)

**Simulation mode:** If NAOqi is not installed (e.g., you are testing on a regular laptop), the script runs in simulation mode and prints what would happen on the real robot.

---

### 5.11 `robotics/gesture_planner.py` — Gesture Planner

Maps response text to robot gestures by looking for direction keywords and task type:

| Trigger | Gesture | LED Colour |
|---|---|---|
| Response contains "on your left" | `point_left` | Blue `#00AAFF` |
| Response contains "on your right" | `point_right` | Blue `#00AAFF` |
| Greeting / social T3 task | `wave` | Green `#00FF88` |
| Thinking / complex question | `think` | Yellow `#FFFF00` |
| Showing tablet content | `show_tablet` | White `#FFFFFF` |
| Farewell | `wave_goodbye` | Orange `#FF8800` |

---

## 6. Features Reference — Everything OmniLLM Can Do

### Core Features

| Feature | Description | How to use |
|---|---|---|
| **Unified Model Gateway** | Query any of 19 registered AI models with one function call | `omnillm ask "question" -m model-id` |
| **Concurrent Multi-Model Querying** | Ask multiple models simultaneously — no extra wait time | `omnillm ask "question" --all` |
| **Smart Routing** | Automatically picks the best model based on task type, budget, or quality history | `omnillm route "question" --strategy BEST_QUALITY` |
| **LLM-as-Judge Evaluation** | Use one AI to score another's response (Referenceless, Reference-Based, Pairwise) | `omnillm evaluate -m openai-gpt4o-mini` |
| **ELO Leaderboard** | Chess-style ranking updated after every pairwise comparison | `omnillm leaderboard` |
| **LLM Council (Consensus)** | Multiple models answer, judge synthesises the best answer | `omnillm council "question"` |
| **Cost Tracking** | Real-time USD spend per model, per session | `omnillm costs` |
| **RAG Pipeline** | Ground answers in your own documents — reduces hallucinations | Python API (see Section 7) |
| **YAML Model Registry** | Add a new AI model in 7 lines of YAML, zero code changes | Edit `config/models.yaml` |

### HRI / Robot Features

| Feature | Description |
|---|---|
| **LangGraph Agent Pipeline** | Full multi-node graph: audio → STT → language detection → task classification → RAG/LLM → robot action |
| **Whisper STT** | Converts Pepper's audio to text (local GPU or OpenAI cloud API) |
| **Task Classifier T1–T4** | Classifies utterances into info retrieval, navigation, social conversation, multilingual |
| **Language Detector** | Detects spoken language and routes to the optimal multilingual model |
| **Gesture Planner** | Maps response text to Pepper gestures and eye LED colours |
| **Flask AI Server** | HTTP bridge between Python 2.7 NAOqi and Python 3.x AI stack |
| **NAOqi Client (Python 2.7)** | Runs on/near Pepper — captures audio, sends to server, executes response |
| **Experiment Manager** | Manages 5 experimental conditions (A–E), participant sessions, counterbalancing |
| **Interaction Logger** | Records every interaction: utterance, response, model, latency, cost, RAG faithfulness |
| **Questionnaire Collector** | Collects post-interaction ratings (Likert, Godspeed, pairwise preference) |

### Registered AI Models (19 total, April 2026)

#### Cloud Models

| OmniLLM ID | Provider | Real Model Name | Cost (input/output per 1M tokens) | Best For |
|---|---|---|---|---|
| `openai-gpt54` | OpenAI | GPT-5.4 | $2.50 / $15.00 | Complex professional tasks |
| `openai-gpt4o` | OpenAI | GPT-4o | $2.50 / $10.00 | Multimodal, flagship |
| `openai-o1` | OpenAI | o1 | $15.00 / $60.00 | Advanced reasoning |
| `openai-o3-mini` | OpenAI | o3-mini | $1.10 / $4.40 | Efficient reasoning |
| `openai-gpt4o-mini` | OpenAI | GPT-4o-mini | $0.15 / $0.60 | HRI baseline (fast, affordable) |
| `claude-sonnet` | Anthropic | Claude Sonnet 4.6 | $3.00 / $15.00 | Balanced intelligence + speed |
| `claude-opus` | Anthropic | Claude Opus 4.6 | $15.00 / $75.00 | Most powerful Claude |
| `claude-haiku` | Anthropic | Claude Haiku 4.5 | $0.80 / $4.00 | Ultra-fast HRI responses |
| `gemini-2.5-pro` | Google | Gemini 2.5 Pro | $1.25 / $10.00 | Deep reasoning, long context |
| `gemini-2.5-flash` | Google | Gemini 2.5 Flash | $0.15 / $0.60 | Fast and affordable |
| `gemini-flash` | Google | Gemini 2.0 Flash | $0.10 / $0.40 | Sub-second HRI latency |
| `google-studio-pro` | Google AI Studio | Gemini 2.5 Pro | $1.25 / $10.00 | Via AI Studio endpoint |
| `deepseek-v3-cloud` | DeepSeek | DeepSeek-V3 | $0.27 / $1.10 | Very cheap, good quality |
| `deepseek-r1-cloud` | DeepSeek | DeepSeek-R1 | $0.55 / $2.19 | Cheap reasoning model |
| `qwen-2.5-72b` | Alibaba | Qwen 2.5 72B | $1.10 / $3.40 | Multilingual via DashScope |

#### Local Models (completely free via Ollama)

| OmniLLM ID | Ollama Model | Download Size | Best For |
|---|---|---|---|
| `llama3-8b-local` | `llama3:8b` | ~4.7 GB | General, HRI baseline |
| `qwen-2.5-7b-local` | `qwen2.5:7b` | ~4.4 GB | Multilingual, info retrieval |
| `qwen-2.5-local` | `qwen2.5:3b` | ~2.0 GB | Lightweight local |
| `llama3.2-local` | `llama3.2:3b` | ~2.0 GB | Compact, fast local |

---

## 7. Complete Terminal Commands Reference

> **Assumption:** Your virtual environment is activated (`source .venv/bin/activate`) and OmniLLM is installed (`pip install -e ".[dev]"`).

### Installation Commands

```bash
# Clone the project
git clone https://github.com/Akshita-sr/OmniLLM.git
cd OmniLLM

# Create a virtual environment (isolated Python sandbox)
python -m venv .venv

# Activate the virtual environment
source .venv/bin/activate           # Linux / macOS
.venv\Scripts\activate              # Windows (Command Prompt)
.venv\Scripts\Activate.ps1          # Windows (PowerShell)

# Install (core + dev/test tools)
pip install -e ".[dev]"

# Install with RAG + LangGraph + HRI support
pip install -e ".[dev,hri]"

# Install with robot bridge (Flask + WebSockets)
pip install -e ".[dev,robotics]"

# Install everything
pip install -e ".[all]"

# Copy API key template
cp .env.example .env
# Then open .env in a text editor and fill in your API keys

# Verify the install worked
omnillm --version
omnillm models
```

### Local Models (Free — No API Key)

```bash
# Install Ollama (runs AI models locally, for free)
curl -fsSL https://ollama.com/install.sh | sh          # Linux / macOS
# Windows: download from https://ollama.com

# Download models (one-time, takes a few minutes)
ollama pull llama3:8b           # ~4.7 GB — good general model
ollama pull qwen2.5:7b          # ~4.4 GB — best multilingual model
ollama pull qwen2.5:3b          # ~2.0 GB — smaller, faster
ollama pull llama3.2:3b         # ~2.0 GB — compact Meta model

# Verify models are downloaded
ollama list

# Test a local model
omnillm ask "Hello" -m llama3-8b-local
```

### CLI Commands (The `omnillm` Command)

```bash
# ─────────────────────────────────────────────────────────────────
# MODELS — see what is registered
# ─────────────────────────────────────────────────────────────────

omnillm models                    # all 19 models
omnillm models --type cloud       # only cloud models
omnillm models --type local       # only local Ollama models


# ─────────────────────────────────────────────────────────────────
# ASK — query one or many models
# ─────────────────────────────────────────────────────────────────

omnillm ask "What is the capital of France?" -m openai-gpt4o-mini
omnillm ask "Write a haiku" -m claude-haiku
omnillm ask "Explain quantum computing simply" -m llama3-8b-local
omnillm ask "Translate 'hello' to French" -m gemini-flash

# Ask multiple specific models at once
omnillm ask "What is consciousness?" -m openai-gpt4o-mini -m claude-haiku

# Ask ALL registered models (they run in parallel)
omnillm ask "What is 2+2?" --all


# ─────────────────────────────────────────────────────────────────
# EVALUATE — benchmark a model using LLM-as-Judge
# ─────────────────────────────────────────────────────────────────

omnillm evaluate                                  # all cloud models, all tasks
omnillm evaluate -m openai-gpt4o-mini             # one model, all tasks
omnillm evaluate -m openai-gpt4o-mini -c reasoning  # one model, one category
omnillm evaluate -c code                          # all models, code tasks
omnillm evaluate -m claude-haiku -o results/my_eval.json  # save to file


# ─────────────────────────────────────────────────────────────────
# COMPARE — pairwise comparison between two models
# ─────────────────────────────────────────────────────────────────

omnillm compare "Write a function to reverse a string"
omnillm compare "Explain black holes" --model-a openai-gpt4o --model-b claude-sonnet


# ─────────────────────────────────────────────────────────────────
# COUNCIL — LLM Council consensus (multiple models → one answer)
# ─────────────────────────────────────────────────────────────────

omnillm council "What is the trolley problem?"
omnillm council "Is P=NP?" --strategy majority_vote

# Custom council members
omnillm council "Summarise climate policy" \
    -m openai-gpt4o -m claude-sonnet -m gemini-2.5-pro


# ─────────────────────────────────────────────────────────────────
# ROUTE — smart routing demo
# ─────────────────────────────────────────────────────────────────

omnillm route "Hi"                                # → cheapest model
omnillm route "Prove Fermat's Last Theorem"       # → most capable model
omnillm route "Translate this to Japanese"        # → multilingual model
omnillm route "Quick maths question" --budget 0.001    # max $0.001 per query
omnillm route "Debug this code" --strategy BEST_QUALITY
omnillm route "Fast answer needed" --strategy LOWEST_LATENCY
omnillm route "Cheap question" --strategy LOWEST_COST


# ─────────────────────────────────────────────────────────────────
# LEADERBOARD — ELO rankings
# ─────────────────────────────────────────────────────────────────

omnillm leaderboard                     # overall ranking
omnillm leaderboard --category reasoning
omnillm leaderboard --category code


# ─────────────────────────────────────────────────────────────────
# COSTS — USD spend breakdown
# ─────────────────────────────────────────────────────────────────

omnillm costs                           # total spend per model


# ─────────────────────────────────────────────────────────────────
# EXPORT — save results to CSV / Markdown
# ─────────────────────────────────────────────────────────────────

omnillm export --format csv      --input results/eval.json -o results/report.csv
omnillm export --format markdown --input results/eval.json -o results/report.md
omnillm export --format json     --input results/eval.json -o results/full.json
```

### Flask AI Server Commands

```bash
# ─────────────────────────────────────────────────────────────────
# START the AI server (required for Pepper robot integration)
# ─────────────────────────────────────────────────────────────────

# Basic start (listens on localhost:5000)
python -m omnillm.server.app

# Custom host and port
python -m omnillm.server.app --host 0.0.0.0 --port 5000

# With a specific default model
python -m omnillm.server.app --model openai-gpt4o-mini

# With a custom knowledge base directory
python -m omnillm.server.app --kb /path/to/your/knowledge_base

# Disable RAG (for testing without documents)
python -m omnillm.server.app --no-rag

# Enable debug mode (shows detailed error messages)
python -m omnillm.server.app --debug

# Full example with all options
python -m omnillm.server.app \
    --host 0.0.0.0 \
    --port 5000 \
    --model openai-gpt4o-mini \
    --kb knowledge_base/ \
    --debug


# ─────────────────────────────────────────────────────────────────
# TEST the server with curl (once it is running)
# ─────────────────────────────────────────────────────────────────

# Health check (is the server running?)
curl http://localhost:5000/health

# Server status (what model? RAG enabled?)
curl http://localhost:5000/status

# Send a text message
curl -X POST http://localhost:5000/interact \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Where is Room 305?",
    "participant_id": "P001",
    "session_id": "s-test-001",
    "condition": "C",
    "rag_enabled": true
  }'

# Download all interaction logs
curl http://localhost:5000/export
```

### NAOqi Client Commands (Run on/near Pepper)

```bash
# ─────────────────────────────────────────────────────────────────
# RUN the NAOqi client on Pepper (Python 2.7)
# ─────────────────────────────────────────────────────────────────

# Robot and server are on the same machine (testing)
python omnillm/server/naoqi_client.py

# Robot IP is 192.168.1.100, server IP is 192.168.1.50
python omnillm/server/naoqi_client.py \
    --robot-ip 192.168.1.100 \
    --server-ip 192.168.1.50

# With participant and condition
python omnillm/server/naoqi_client.py \
    --robot-ip 192.168.1.100 \
    --server-ip 192.168.1.50 \
    --participant P001 \
    --condition C
```

### Test Commands

```bash
# ─────────────────────────────────────────────────────────────────
# TESTS — run the test suite (no API keys or Ollama needed)
# ─────────────────────────────────────────────────────────────────

# Run all tests
pytest tests/ -v

# Run one specific test file
pytest tests/test_gateway.py -v
pytest tests/test_router.py -v
pytest tests/test_hri.py -v
pytest tests/test_rag.py -v

# Run with coverage report (shows which lines are tested)
pytest tests/ --cov=omnillm --cov-report=term-missing
```

---

## 8. All Tools and Libraries Used

### Core Libraries (Always Installed)

| Library | Version | What It Does | Why OmniLLM Uses It |
|---|---|---|---|
| **Python** | ≥ 3.11 | The programming language | asyncio for concurrent LLM calls; modern type hints |
| **[LiteLLM](https://github.com/BerriAI/litellm)** | ≥ 1.40 | Unified interface to 100+ AI providers | One function call works with OpenAI, Anthropic, Google, Ollama, etc. |
| **[Rich](https://github.com/Textualize/rich)** | ≥ 13.0 | Beautiful terminal output | Coloured tables, panels, and progress bars in the CLI |
| **[Click](https://click.palletsprojects.com)** | ≥ 8.1 | CLI framework | Builds the `omnillm` command with sub-commands and `--option` flags |
| **[PyYAML](https://pyyaml.org)** | ≥ 6.0 | Reads YAML files | Loads `config/models.yaml` and all task files |
| **[aiohttp](https://docs.aiohttp.org)** | ≥ 3.9 | Async HTTP client | Used in robot bridge for non-blocking network calls |
| **[python-dotenv](https://pypi.org/project/python-dotenv/)** | ≥ 1.0 | Loads `.env` files | Reads API keys from the `.env` file into environment variables |

### Optional — HRI and RAG Features (`pip install ".[hri]"`)

| Library | What It Does | Why OmniLLM Uses It |
|---|---|---|
| **[ChromaDB](https://www.trychroma.com)** | Vector database | Stores and searches document chunks by semantic meaning for RAG |
| **[LangChain Community](https://python.langchain.com)** | Document loaders | Loads PDFs, CSVs, and TXT files for RAG indexing |
| **[sentence-transformers](https://www.sbert.net)** | Local embedding model | Converts text to vectors for semantic search without calling an API |
| **[pypdf](https://pypdf.readthedocs.io)** | PDF parser | Extracts text from PDF files for RAG indexing |
| **[langdetect](https://pypi.org/project/langdetect/)** | Language detection | Identifies what language a text is written in |
| **[LangGraph](https://langchain-ai.github.io/langgraph/)** | Agent graph framework | Builds the multi-node decision pipeline for the HRI agent |

### Optional — Robotics Server (`pip install ".[robotics]"`)

| Library | What It Does | Why OmniLLM Uses It |
|---|---|---|
| **[Flask](https://flask.palletsprojects.com)** | Web framework | Powers the HTTP AI server that Pepper communicates with |
| **[websockets](https://websockets.readthedocs.io)** | WebSocket library | Used for real-time streaming with the Buddy robot |

### Optional — Speech Recognition (Install Separately)

| Library | What It Does | Install Command |
|---|---|---|
| **[openai-whisper](https://github.com/openai/whisper)** | Local speech-to-text | `pip install openai-whisper` |
| **[openai](https://pypi.org/project/openai/)** | OpenAI SDK (Whisper cloud API) | `pip install openai` |

### Development / Testing (`pip install ".[dev]"`)

| Library | What It Does |
|---|---|
| **pytest** | Runs all the automated tests |
| **pytest-asyncio** | Lets pytest run `async` test functions |
| **pytest-mock** | Lets tests replace real API calls with fake responses (so tests run without internet access or API keys) |

### External Tools (Not Python Libraries)

| Tool | What It Is | Download |
|---|---|---|
| **Ollama** | Runs open-source AI models locally for free (no API key) | [ollama.com](https://ollama.com) |
| **NAOqi SDK** | Pepper/NAO robot programming SDK (Python 2.7) | [developer.softbankrobotics.com](https://developer.softbankrobotics.com) |
| **Choregraphe** | Graphical programming environment for Pepper/NAO | [SoftBank Robotics](https://developer.softbankrobotics.com/nao6/choregraphe-suite) |
| **Git** | Version control — used to clone the repository | [git-scm.com](https://git-scm.com) |

---

## 9. Connecting to the Old Pepper Robot (NAOqi + Choregraphe + Python 2.7)

This section is specifically for users who have an older Pepper robot that runs the NAOqi 2.x operating system and uses Choregraphe for programming.

### Understanding the Python 2.7 / Python 3 Incompatibility

**The core problem:** Pepper's brain (NAOqi) was built when Python 2.7 was the standard. Modern AI libraries (LangGraph, LiteLLM, ChromaDB) require Python 3.11 or higher. You cannot run them in the same Python process.

**OmniLLM's solution:** Run two separate processes and have them communicate over HTTP:

```
Your Computer / Server                    Pepper Robot
(Python 3.11+)                            (Python 2.7 / NAOqi)
┌───────────────────────────┐             ┌──────────────────────────┐
│  omnillm.server.app       │◄────────────│  naoqi_client.py         │
│  Flask AI server          │  HTTP JSON  │  ALAudioDevice           │
│  LangGraph pipeline       │────────────►│  ALAnimatedSpeech        │
│  LiteLLM gateway          │             │  ALMotion                │
│  ChromaDB RAG             │             │  ALLeds                  │
│  Whisper STT              │             │  ALTabletService         │
└───────────────────────────┘             └──────────────────────────┘
```

The AI server can run on:
- The same computer on the same Wi-Fi network as Pepper
- A cloud server (if your Pepper has internet access)
- A Raspberry Pi or NUC attached to Pepper's charging station

### Step-by-Step: First Connection

#### Step 1 — Find Pepper's IP address

Press Pepper's **chest button** once. Pepper will say its IP address out loud (e.g., "My IP address is 192.168.1.100"). Write this down.

Alternatively, check your router's connected devices list.

#### Step 2 — Test NAOqi connection with Choregraphe

1. Open **Choregraphe** on your computer
2. Click **Connection** → **Connect to** → type Pepper's IP address → **Connect**
3. If you see Pepper's live video feed in Choregraphe, the connection works

Choregraphe is useful for:
- Testing individual behaviors (make Pepper wave, speak, etc.)
- Checking if ALAnimatedSpeech is working
- Installing custom behaviors that OmniLLM's gesture planner will call
- Debugging NAOqi service issues

#### Step 3 — Install NAOqi Python SDK on your computer

Download the **Python SDK** (not the full NAOqi OS) from the SoftBank Robotics developer site. The SDK includes the `qi` module (for NAOqi 2.x) and `naoqi` module (for legacy 1.x).

After installing the SDK, test it:
```python
# Run with Python 2.7
python2 -c "import qi; print('qi SDK works')"
```

#### Step 4 — Start the OmniLLM AI server (Python 3, on your computer)

```bash
# In your Python 3.11+ environment (on your computer):
source .venv/bin/activate

# Install robotics dependencies
pip install -e ".[robotics,hri]"

# Start the server (listens on all network interfaces)
python -m omnillm.server.app --host 0.0.0.0 --port 5000

# You should see:
# INFO - Knowledge base loaded — N total chunks
# * Running on http://0.0.0.0:5000
```

Make sure your firewall allows incoming connections on port 5000.

#### Step 5 — Find your computer's IP address

```bash
# Linux / macOS
ip addr show           # or: ifconfig

# Windows
ipconfig
```

Look for the IP address on the same network as Pepper (e.g., `192.168.1.50`).

Test the server is reachable from Pepper's network:
```bash
# From any computer on the same network:
curl http://192.168.1.50:5000/health
# Should return: {"status": "ok", "version": "0.1.0"}
```

#### Step 6 — Run the NAOqi client (Python 2.7)

```bash
# In Python 2.7 with the NAOqi SDK installed:
python omnillm/server/naoqi_client.py \
    --robot-ip 192.168.1.100 \     # Pepper's IP (from Step 1)
    --server-ip 192.168.1.50 \     # Your computer's IP (from Step 5)
    --participant P001 \
    --condition A
```

You should see:
```
[OK] Connected to Pepper at 192.168.1.100:9559
[OK] OmniLLM Pepper client running. Session: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
[OK] Press Ctrl+C to stop.
```

Pepper will say: *"Hello! I am Pepper, powered by OmniLLM. How can I help you today?"*

#### Step 7 — Speak to Pepper

Speak to Pepper (within ~1 metre, facing the microphone). After 5 seconds, the system will:
1. Send the audio to the AI server
2. Transcribe it with Whisper
3. Classify the question
4. Get an answer from the LLM
5. Return a gesture + speech + LED colour
6. Pepper speaks the answer and gestures

### Using Choregraphe with OmniLLM

**Choregraphe and OmniLLM serve different purposes and are used together:**

| Choregraphe | OmniLLM |
|---|---|
| Creates and installs robot behaviors (animations, gestures) | Decides **what** behavior to run based on AI reasoning |
| Tests individual NAOqi services | Manages the AI brain that drives the behaviors |
| Good for scripted, pre-planned interactions | Good for dynamic, open-ended conversations |

**Workflow:**
1. Use Choregraphe to **install custom behaviors** on Pepper (e.g., a pointing animation, a welcome dance)
2. Add the behavior name to `GESTURE_TO_BEHAVIOR` in `naoqi_client.py`
3. OmniLLM will automatically trigger that behavior when appropriate

**Example: Adding a custom behavior**

In `omnillm/server/naoqi_client.py`, find the `GESTURE_TO_BEHAVIOR` dictionary and add your custom behavior:

```python
GESTURE_TO_BEHAVIOR = {
    "wave": "animations/Stand/Gestures/Hey_1",
    "bow": "animations/Stand/Gestures/BowShort_1",
    # ... existing entries ...
    "my_custom_welcome": "myBehaviors/WelcomeDance",  # ← Your custom behavior
}
```

Then in `omnillm/robotics/gesture_planner.py`, add a rule that triggers your behavior:

```python
# In the _KEYWORD_GESTURE_MAP or the plan() method:
if "welcome" in response_text.lower():
    return "my_custom_welcome", "#00FF88"
```

### Troubleshooting Pepper Connection

**Pepper says its IP but Choregraphe cannot connect:**
- Make sure your computer and Pepper are on the same Wi-Fi network (not mobile hotspot vs Wi-Fi)
- Try pinging Pepper: `ping 192.168.1.100`
- Check Pepper's firewall — press chest button, go to Settings → Network

**NAOqi SDK import error:**
```bash
# Wrong: using Python 3
python3 omnillm/server/naoqi_client.py

# Correct: using Python 2.7
python2 omnillm/server/naoqi_client.py
# or
python omnillm/server/naoqi_client.py  # if Python 2.7 is your default
```

**Pepper says "I'm sorry, I could not connect to my AI brain":**
- Make sure the Flask server is running on your computer
- Check the server IP and port in the NAOqi client command
- Verify port 5000 is not blocked: `curl http://<server-ip>:5000/health`

**Audio recording returns empty bytes:**
- The current `_record_audio` method is a placeholder that returns empty bytes. For production use, replace it with real ALAudioRecorder capture or ALSpeechRecognition callback-based capture.
- The simplest workaround for testing: use `_send_text("Where is Room 305?")` directly in the client instead of recording.

**Pepper's ALAnimatedSpeech does nothing:**
- Check in Choregraphe that ALAnimatedSpeech service is running
- Ensure Pepper is in "Standing" posture (ALMotion.wakeUp() must have run)
- Check Pepper's volume: use Choregraphe's audio panel to verify

**NAOqi version differences:**
- NAOqi 2.x (newer): uses `import qi` and `qi.Application`
- NAOqi 1.x (older): uses `import naoqi` and `naoqi.ALProxy`
- `naoqi_client.py` tries `qi` first, then `naoqi`, so it should work with both

### The Experimental Conditions

When running the HRI experiment, the `--condition` flag controls which AI backend Pepper uses:

| Condition | Flag | What Pepper Uses | What You Are Testing |
|---|---|---|---|
| A | `--condition A` | GPT-4o-mini (fixed cloud) | Cloud baseline |
| B | `--condition B` | Llama3:8b local (Ollama) | Free local baseline |
| C | `--condition C` | OmniLLM smart router (picks best per task) | Smart routing effectiveness |
| D | `--condition D` | LLM Council (3 models, synthesised) | Consensus vs single model |
| E | `--condition E` | GPT-4o-mini without RAG | Isolates RAG contribution |

---

## 10. Step-by-Step Setup from Zero

This section assumes you have never used Python, AI APIs, or robots before.

### Part A — Install Required Software

1. **Install Python 3.11+**
   - Windows: [python.org/downloads](https://www.python.org/downloads/) — check "Add Python to PATH" during install
   - macOS: `brew install python@3.11` (requires [Homebrew](https://brew.sh))
   - Linux (Ubuntu): `sudo apt install python3.11 python3.11-venv python3-pip`
   - Verify: `python --version` should show `3.11.x` or higher

2. **Install Git**
   - Windows: [git-scm.com/download/win](https://git-scm.com/download/win)
   - macOS: `brew install git`
   - Linux: `sudo apt install git`
   - Verify: `git --version`

3. **Install Ollama** (for free local models)
   ```bash
   curl -fsSL https://ollama.com/install.sh | sh   # Linux/macOS
   # Windows: download from https://ollama.com
   ```

### Part B — Get the Code

```bash
git clone https://github.com/Akshita-sr/OmniLLM.git
cd OmniLLM
```

### Part C — Set Up Python Environment

```bash
# Create an isolated environment (prevents conflicts with other Python projects)
python -m venv .venv

# Activate it
source .venv/bin/activate     # Linux/macOS
.venv\Scripts\activate        # Windows
```

### Part D — Install OmniLLM

```bash
# Core install with test tools
pip install -e ".[dev]"

# For Pepper robot support (Flask server + WebSockets)
pip install -e ".[dev,robotics]"

# For full AI capabilities (RAG, LangGraph, language detection)
pip install -e ".[dev,hri]"

# Install everything at once
pip install -e ".[all]"
```

### Part E — Set API Keys (Optional)

```bash
cp .env.example .env
# Open .env in Notepad / TextEdit / VS Code and fill in your keys
```

If you do not have any API keys, skip this — the local Ollama models are completely free.

### Part F — Download a Free Local Model

```bash
ollama pull llama3:8b      # ~4.7 GB — good general-purpose model
```

### Part G — Test the Installation

```bash
omnillm models              # should show a table of 19 models
omnillm ask "Hello" -m llama3-8b-local    # tests local model (no API key needed)
pytest tests/ -v            # runs all 278 tests (no API keys or Ollama needed)
```

### Part H (Optional) — Start the Pepper AI Server

```bash
python -m omnillm.server.app --debug
```

Open a second terminal and test it:
```bash
curl -X POST http://localhost:5000/interact \
  -H "Content-Type: application/json" \
  -d '{"text": "Hello, what can you do?", "participant_id": "test"}'
```

---

## 11. Troubleshooting for Beginners

### "command not found: omnillm"

Your virtual environment is not activated, or the install failed.

```bash
# Step 1: Activate the virtual environment
source .venv/bin/activate     # Linux/macOS
.venv\Scripts\activate        # Windows

# Step 2: Re-install
pip install -e ".[dev]"

# Step 3: Check
omnillm --version
```

### "Python 3.11 required but found 3.9"

```bash
# Check what version you have
python --version

# Install Python 3.11 and use it explicitly
python3.11 -m venv .venv
```

### "ModuleNotFoundError: No module named 'chromadb'"

Install the HRI extras:
```bash
pip install -e ".[hri]"
```

### "ModuleNotFoundError: No module named 'flask'"

Install the robotics extras:
```bash
pip install -e ".[robotics]"
```

### "APIConnectionError" from OpenAI/Anthropic/Google

1. Make sure `.env` exists: `ls -la .env`
2. Check the key is correct (no extra spaces or quotes in the file)
3. Test with a free local model first: `omnillm ask "test" -m llama3-8b-local`

### Ollama not responding

```bash
# Check if Ollama is running
ollama list

# If not running, start it
ollama serve

# Check the model is downloaded
ollama pull llama3:8b
```

### Tests are failing

```bash
# Run one test file at a time to isolate the failure
pytest tests/test_gateway.py -v

# Check if there is a missing import
pip install -e ".[all]"
```

---

## 12. Glossary — Every Technical Word Explained

| Word | What it means |
|---|---|
| **API** | Application Programming Interface — a URL you call from code to get a service (e.g., call OpenAI's API to get a response from GPT-4) |
| **API key** | A secret password (like `sk-xxxx`) that proves you have an account with a provider and bills you for usage |
| **asyncio** | Python's built-in library for running multiple things simultaneously without creating multiple threads |
| **async / await** | Python keywords that let you write concurrent code that looks like normal sequential code |
| **ChromaDB** | A vector database — stores chunks of text as numbers (vectors) so you can search by meaning rather than exact keywords |
| **CLI** | Command-Line Interface — a text-based program you run in a terminal by typing commands |
| **embedding** | Converting text to a list of numbers (a vector) that represents its meaning — similar texts have similar vectors |
| **ELO score** | A numerical rating system (from chess) that goes up when you win against a strong opponent and down when you lose |
| **Flask** | A lightweight Python web framework — used to create the AI server's HTTP endpoints |
| **hallucination** | When an AI confidently states something that is false — RAG reduces this by grounding answers in real documents |
| **HRI** | Human-Robot Interaction — the academic field studying how people interact with robots |
| **LangGraph** | A Python library for building multi-step AI agent pipelines as a graph (flowchart) |
| **LiteLLM** | A Python library that provides a single API for 100+ AI providers |
| **LLM** | Large Language Model — an AI that generates text (GPT, Claude, Gemini, Llama, etc.) |
| **LLM-as-Judge** | Using one AI model to score or compare the output of another AI model |
| **NAOqi** | The operating system and SDK of SoftBank Robotics robots (Pepper, NAO). Only supports Python 2.7. |
| **Ollama** | A tool that downloads and runs open-source AI models locally on your computer for free |
| **RAG** | Retrieval-Augmented Generation — searching documents for relevant passages before asking an LLM to answer |
| **token** | Roughly one word (or part of a word) — AI providers charge by the number of tokens processed |
| **TTFT** | Time To First Token — how long before the AI starts generating its response |
| **vector** | A list of numbers representing meaning — used in ChromaDB for semantic search |
| **virtual environment** | An isolated Python installation that does not affect your system's Python |
| **YAML** | A human-readable configuration file format (like `config/models.yaml`) |

---

*For installation instructions and quick-start commands, see [GETTING_STARTED.md](GETTING_STARTED.md).*
*For the full academic context, architecture diagrams, and research hypotheses, see [README.md](README.md).*
