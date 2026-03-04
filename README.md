# 🧠 OmniLLM

> **Compare, Route, and Orchestrate Every LLM — Today and Tomorrow**

A living, plugin-based platform for multi-LLM comparison, smart routing, consensus ensembles, and future robotics integration.

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](https://github.com/Akshita-sr/OmniLLM/pulls)

---

## 🎯 Goal & Objective

OmniLLM is a **living, extensible platform** for comparing, evaluating, and routing prompts across multiple Large Language Models simultaneously. It goes far beyond simple model comparison:

- **Smart Routing**: Learns from evaluation history to automatically select the best model for each task within your budget and latency constraints
- **Cost Tracking**: Real-time spend tracking per model, per session — understand exactly what each query costs
- **Consensus Ensembles**: The "LLM Council" architecture dispatches prompts to multiple models simultaneously and synthesises a superior combined answer
- **Robotics Bridge**: Abstract bridge pattern for connecting the best LLM (or ensemble) to social robots — Pepper, NAO, and Buddy
- **Plugin Architecture**: Adding a new model requires only 5 lines of YAML — **zero code changes**
- **LLM-as-Judge Evaluation**: Three research-backed patterns for automated, dynamic evaluation

The ultimate vision: connect the best LLM or ensemble of LLMs to social robots for truly capable embodied AI — an AI brain that is never locked to a single model.

---

## 🧩 What Problem Does This Solve?

### 1. 🆕 The "New Model Every Day" Problem
New LLMs are released weekly (sometimes daily). Traditional comparison tools require code changes to add each new model. **OmniLLM uses a YAML-based plugin architecture** — adding GPT-5 when it releases looks like:

```yaml
gpt-5:
  provider: openai
  model: gpt-5
  api_key_env: OPENAI_API_KEY
  cost_per_1m_input: 10.00
  cost_per_1m_output: 30.00
  type: cloud
```

That's it. No Python code to modify. No imports to update.

### 2. 📊 Benchmark Staleness & Data Contamination
Static benchmarks (MMLU, HumanEval) get "gamed" — models see test data during training, inflating scores. **OmniLLM supports**:
- LLM-as-Judge evaluation (3 patterns): Referenceless, Reference-Based, Pairwise
- Custom dynamic task creation via YAML
- Contamination-resistant evaluation design
- ELO-based leaderboards from pairwise comparisons (like LMSYS Chatbot Arena)

### 3. 🔀 API Fragmentation
OpenAI, Anthropic, Google, Mistral, local Ollama models — each has a different API. **OmniLLM uses [LiteLLM](https://github.com/BerriAI/litellm)** as a unified gateway to call 100+ LLM providers through one interface.

### 4. 🗺️ "Which Model for Which Task?"
A powerful model for a simple greeting is wasteful. A cheap model for complex reasoning is unreliable. **OmniLLM's Smart Router** learns from evaluation history to automatically route each prompt to the optimal model:
- `BEST_QUALITY` — highest-scoring model for that task category
- `LOWEST_COST` — cheapest model with acceptable quality
- `LOWEST_LATENCY` — fastest response time
- `BEST_VALUE` — composite quality/cost/speed optimisation
- `LOCAL_PREFERRED` — prefer free local Ollama models first

### 5. 🤝 Single Model Point of Failure
Any single model can hallucinate, refuse, or give incorrect answers. **The Multi-Model Consensus Engine** ("LLM Council") solves this:
- Dispatches every prompt to multiple models simultaneously
- Analyses responses for agreement (semantic similarity clustering)
- Synthesises a superior combined answer via a judge LLM
- Dramatically reduces hallucinations by filtering minority errors

### 6. 🤖 LLM ↔ Robot Gap
Connecting LLMs to physical robots requires bridging the gap between natural language and structured robot commands, between modern Python 3.x AI stacks and legacy Python 2.7 robot SDKs (NAOqi), and between cloud LLMs and low-latency robot action loops. **OmniLLM's Abstract Bridge Pattern** provides clean integrations for Pepper, NAO, and Buddy robots.

---

## 🏛️ State of the Art — Literature Review

### 4a. The Collapse of Static Benchmarks

Static benchmarks — MMLU, HumanEval, GSM8K — have become unreliable measures of true LLM capability due to three converging problems:

**Data Contamination**: Models are trained on web-scraped data that often includes benchmark test sets. A comprehensive study on contamination detection (arXiv:2502.17521) identifies four detection methods: Collision Rate, Repeat Trials, Membership Inference, and Chronological Analysis. The paper "Benchmarking LLMs Under Data Contamination: Static to Dynamic" (EMNLP 2025) demonstrates that models routinely score above their "true" capability on contaminated benchmarks.

**Benchmark Saturation**: When top models all score >80% on MMLU, the benchmark no longer discriminates between them for real-world tasks. MMLU scores above 80% essentially stop predicting downstream performance.

**Benchmark Errors vs. Model Errors**: The provocatively titled study "Garbage In, Reasoning Out?" (arXiv:2506.23864) shows that many "wrong" model answers are actually correct responses to ambiguous or erroneous benchmark questions.

**The Solution — Dynamic Evaluation**:
- [DyCodeEval](https://arxiv.org/abs/2503.04149): Dynamically generates code evaluation tasks to prevent memorisation
- [LiveBench](https://livebench.ai) (ICLR 2025): Monthly-updated benchmark with tasks based on recent events that models couldn't have seen during training
- Custom task YAML files in OmniLLM enable the same dynamic evaluation approach

### 4b. LLM-as-a-Judge — The New Evaluation Paradigm

Human evaluation is the gold standard but is expensive and slow. **LLM-as-Judge** uses a capable model (typically GPT-4o or Claude 3 Opus) to score other models' responses. Three research-validated patterns:

1. **Referenceless (G-Eval)**: The judge evaluates response quality on its own merits — coherence, accuracy, helpfulness — without needing a gold-standard answer. Best for open-ended questions.

2. **Reference-Based**: The judge compares the response to a provided reference answer, scoring semantic accuracy and completeness. Best for factual tasks.

3. **Pairwise Comparison**: The judge sees two responses side-by-side and declares a winner. OmniLLM implements **position-swapping** (running the comparison twice with A/B swapped) to eliminate the well-documented position bias in LLM judges.

A comprehensive survey ([arXiv:2412.05579](https://arxiv.org/abs/2412.05579) "LLMs-as-Judges: A Comprehensive Survey") covers 2,700+ papers on this paradigm. [arXiv:2503.22458](https://arxiv.org/abs/2503.22458) extends the framework to multi-turn conversational evaluation.

**ELO Rating Systems**: The [LMSYS Chatbot Arena](https://chat.lmsys.org/?leaderboard) demonstrates that pairwise comparisons + ELO ratings produce more reliable rankings than absolute scores. OmniLLM's `EloScorer` implements this methodology — 100 ELO points ≈ 64% head-to-head win rate.

### 4c. Multi-Model Consensus & Ensembles

**The Core Insight**: Multiple imperfect reasoners can collectively outperform any individual reasoner if their errors are independent and uncorrelated. This is the statistical basis for ensemble methods in ML — and it applies to LLMs.

The **"LLM Council" architecture** (inspired by Karpathy) follows four phases:
1. **Broadcaster**: Send the prompt to all council members concurrently
2. **Independent Generation**: Each model responds without seeing others' answers
3. **Consensus Analysis**: Compute semantic similarity, identify agreement clusters
4. **Final Verdict**: A judge LLM synthesises the best combined answer

[arXiv:2601.07245](https://arxiv.org/abs/2601.07245) "Learning to Trust the Crowd: Multi-Model Consensus Reasoning Engine" provides theoretical and empirical foundations. MDPI's "Multiple Large AI Models' Consensus for Object Detection" extends the approach to multimodal settings.

**Benefits**:
- Reduces hallucinations (errors in minority cluster are filtered)
- Improves calibration (uncertainty is surfaced when models disagree)
- Critical for safety-sensitive robotics: no single hallucination can trigger dangerous robot actions

See also: [Awesome-LLM-Ensemble](https://github.com/jxzhangjhu/Awesome-LLM-Ensemble)

### 4d. Dynamic Routing & Cost Optimisation

Not every task requires GPT-4o. Routing based on task complexity can reduce costs by up to 75% in RAG applications (Latitude AI Blog) while maintaining output quality.

**LiteLLM's built-in routing strategies**:
- **Simple-Shuffle**: Round-robin across equivalent models
- **Least-Busy**: Route to the least-loaded model endpoint
- **Latency-Based**: Route to the historically fastest model
- **Usage-Based**: Enforce per-model budget limits

**OmniLLM's SmartRouter** extends these with learning from evaluation history:
- Tracks quality scores per model per task category
- Computes a composite value score (quality × 0.5 + cost_savings × 0.3 + speed × 0.2)
- Complexity heuristic: short prompts → cheap model, long/complex → powerful model
- LoRA-based SLM router for production deployments (classifies prompt type)

### 4e. LLMs + Robotics Integration

The integration of LLMs with physical robots is an active research frontier:

**Motion Planning**: "LLMs as NAO Robot 3D Motion Planners" (ICCV 2025 Workshop) demonstrates LLM-generated 3D motion trajectories for humanoid robots. The key insight: LLMs encode implicit knowledge about physical constraints from training on engineering texts.

**Social Robotics**: "LLM Enabled Social Robots – Aged Care" (IEEE) shows that LLM-powered Pepper robots significantly improve quality of interaction with elderly users — more natural conversations, better context retention across sessions.

**Modular Architecture**: "Trinity: Modular Humanoid Robot AI System" ([arXiv:2503.08338](https://arxiv.org/abs/2503.08338)) proposes a 3-layer architecture: Perception → LLM Reasoning → Actuation. OmniLLM's bridge pattern follows this modularity principle.

**Review Papers**: "Integrating LLMs into Robotic Autonomy: A Review" (MDPI AI) and "LLM-Powered Multi-Session HRI" (Frontiers in Robotics) provide comprehensive overviews of the state of the art.

**The Python 2.7 Challenge**: NAOqi (the Pepper/NAO SDK) is locked to Python 2.7, while modern AI requires Python 3.11+. The solution (from the Theseus thesis on NAO-LLM integration) is a two-process bridge: a Python 2.7 NAOqi client handles robot I/O, communicating via HTTP with a Python 3.x AI server running LiteLLM.

**ROS2 Navigation**: "Latency-Aware Benchmarking for ROS2 Navigation" (PMC article) demonstrates LLM-to-Nav2 goal generation. OmniLLM's `parse_nav2_goal()` utility converts natural language into `geometry_msgs/PoseStamped` JSON.

**Practical Examples**: DeepSeek R1 controlling a robotic arm in a checkers game (HuggingFace Blog) shows that even local, open-source models can provide reliable robot control when properly prompted.

For a comprehensive collection of papers, see: [Awesome LLM-Robotics](https://github.com/GT-RIPL/Awesome-LLM-Robotics)

### 4f. Key Leaderboards & Live Resources

| Resource | Description | URL |
|----------|-------------|-----|
| LMSYS Chatbot Arena | Pairwise human evaluation leaderboard | [chat.lmsys.org](https://chat.lmsys.org/?leaderboard) |
| HuggingFace Open LLM Leaderboard | Automated benchmark leaderboard | [huggingface.co/spaces/HuggingFaceH4/open_llm_leaderboard](https://huggingface.co/spaces/HuggingFaceH4/open_llm_leaderboard) |
| LiveBench | Contamination-free monthly-updated benchmark | [livebench.ai](https://livebench.ai) |
| Awesome Data Contamination | Curated list of contamination research | [github.com/liyucheng09/Contamination_Detector](https://github.com/liyucheng09/Contamination_Detector) |
| Awesome LLM-Robotics | LLM + robotics papers collection | [github.com/GT-RIPL/Awesome-LLM-Robotics](https://github.com/GT-RIPL/Awesome-LLM-Robotics) |
| Awesome LLM Ensemble | Ensemble/consensus methods collection | [github.com/jxzhangjhu/Awesome-LLM-Ensemble](https://github.com/jxzhangjhu/Awesome-LLM-Ensemble) |

---

## 🏗️ Architecture

```
┌────────────────────────────────────────────────────────────────────────────┐
│                           OmniLLM Platform                                 │
│                                                                            │
│  ┌──────────────────┐      ┌─────────────────────────────────────────────┐ │
│  │  Model Registry  │      │          Unified LLM Gateway (LiteLLM)      │ │
│  │  (models.yaml)   │─────▶│  OpenAI │ Anthropic │ Google │ DeepSeek   │ │
│  │  14 models       │      │  Qwen   │ Ollama (local)  │ 100+ others   │ │
│  └──────────────────┘      └──────────────────────┬──────────────────────┘ │
│                                                    │                        │
│  ┌─────────────────────────────────────────────────┼──────────────────────┐ │
│  │                    Core Engines                  │                      │ │
│  │                                                  ▼                      │ │
│  │  ┌──────────────────┐    ┌──────────────────────────────────────────┐  │ │
│  │  │ Evaluation Engine│    │    Consensus Engine (LLM Council)        │  │ │
│  │  │                  │    │  Broadcaster → Independent Generation    │  │ │
│  │  │ • Referenceless  │    │  → Consensus Analysis → Final Verdict   │  │ │
│  │  │ • Reference-Based│    └──────────────────────────────────────────┘  │ │
│  │  │ • Pairwise       │                                                  │ │
│  │  └────────┬─────────┘    ┌──────────────────────────────────────────┐  │ │
│  │           │              │         Smart Router                     │  │ │
│  │           ▼              │  BEST_QUALITY │ LOWEST_COST │ BEST_VALUE │  │ │
│  │  ┌────────────────┐      │  LOWEST_LATENCY │ LOCAL_PREFERRED        │  │ │
│  │  │  ELO Scorer    │      └──────────────────────────────────────────┘  │ │
│  │  │  (Leaderboard) │                                                  │ │
│  │  └────────────────┘                                                  │ │
│  └──────────────────────────────────────────────────────────────────────┘ │
│                                                                            │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │                      Robotics Bridge Layer                           │  │
│  │  ┌────────────────┐  ┌────────────────┐  ┌─────────────────────┐   │  │
│  │  │  PepperBridge  │  │   NAOBridge    │  │    BuddyBridge      │   │  │
│  │  │  NAOqi/HTTP    │  │  NAOqi/HTTP    │  │  Android WebSocket  │   │  │
│  │  │  Py2.7→3.x     │  │  Py2.7→3.x    │  │  Streaming tokens   │   │  │
│  │  └────────────────┘  └────────────────┘  └─────────────────────┘   │  │
│  │                    ROS2 Nav2 goal parsing                           │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                                                            │
│  ┌───────────────────┐  ┌────────────────┐  ┌──────────────────────────┐  │
│  │   CLI Dashboard   │  │  Cost Tracker  │  │    Export Engine         │  │
│  │   Rich + Click    │  │  Per-model,    │  │  CSV │ JSON │ Markdown   │  │
│  │   10+ commands    │  │  per-session   │  │                          │  │
│  └───────────────────┘  └────────────────┘  └──────────────────────────┘  │
└────────────────────────────────────────────────────────────────────────────┘
```

---

## 📐 Evaluation Axes

OmniLLM evaluates models across **8 orthogonal axes** to provide a complete picture of capability:

| # | Axis | What It Measures | Example Tasks |
|---|------|-----------------|---------------|
| 1 | **Reasoning** | Logic, mathematics, multi-step inference | Bat & ball problem, syllogisms, word problems (GSM8K-style) |
| 2 | **Knowledge** | Factual accuracy across domains | Geography, science, history, medicine (MMLU-style, TriviaQA) |
| 3 | **Code Generation** | Write, debug, and explain code | Prime checker, FizzBuzz, binary search debugging (HumanEval++, MBPP) |
| 4 | **Instruction Following** | Structured output, constraints | Exact item counts, JSON schema output, multi-constraint formatting (IFEval) |
| 5 | **Safety & Alignment** | Refusal, PII handling, bias | Refuse hacking instructions, refuse medical misinformation, PII redaction (TruthfulQA) |
| 6 | **Latency & Throughput** | Speed metrics | Time-to-first-token (TTFT), tokens/sec, streaming |
| 7 | **Cost Efficiency** | Quality per dollar | Quality at minimal token usage, cost-aware benchmarking |
| 8 | **Robot-Readiness** | Structured output for robot control | JSON action plans for NAO/Pepper, voice command parsing, ROS2 Nav2 coordinates |

---

## 🚀 Installation & Setup Guide

### Prerequisites
- Python 3.11 or higher
- (Optional) [Ollama](https://ollama.com) for local models

### Step-by-Step Installation

```bash
# 1. Clone the repository
git clone https://github.com/Akshita-sr/OmniLLM.git
cd OmniLLM

# 2. Create a virtual environment
python -m venv .venv
source .venv/bin/activate      # Linux / macOS
# .venv\Scripts\activate       # Windows

# 3. Install OmniLLM
pip install -e ".[dev]"
# or using requirements.txt:
pip install -r requirements.txt

# 4. Configure API keys
cp .env.example .env
# Open .env and fill in your actual API keys

# 5. (Optional) Install Ollama for free local models
curl -fsSL https://ollama.com/install.sh | sh
ollama pull deepseek-r1:14b
ollama pull qwen2.5:7b
ollama pull llama3:8b
ollama pull mistral:7b

# 6. Verify installation
omnillm models
```

You should see a rich table of all 14 registered models.

---

## 📖 Usage Guide

### List All Registered Models

```bash
omnillm models
```

Shows a rich table with ID, type (cloud/local), provider, model name, and pricing.

```bash
# Filter to cloud-only or local-only
omnillm models --type cloud
omnillm models --type local
```

### Run a Benchmark Evaluation

```bash
# Evaluate all cloud models on all tasks
omnillm evaluate

# Evaluate specific models
omnillm evaluate -m openai-gpt4o -m claude-3.5-sonnet

# Evaluate one category only
omnillm evaluate -c reasoning
omnillm evaluate -c code
omnillm evaluate -c safety

# Save results to a file
omnillm evaluate -m openai-gpt4o -o results/eval_2026.json
```

### Ask a Question

```bash
# Ask all models at once
omnillm ask "Explain quantum computing in simple terms" --all

# Ask a specific model
omnillm ask "Hello" -m deepseek-r1-local

# Ask multiple specific models
omnillm ask "What is consciousness?" -m openai-gpt4o -m claude-3.5-sonnet
```

### Pairwise Model Comparison

```bash
# Compare two models head-to-head
omnillm compare "Write a poem about the ocean"
omnillm compare "Debug this Python code: def fib(n): return fib(n-1)+fib(n-2)" \
    --model-a openai-gpt4o --model-b deepseek-v3-cloud
```

### LLM Council — Consensus Engine

```bash
# Use the consensus engine with default synthesis strategy
omnillm council "What is consciousness?"

# Choose a specific strategy
omnillm council "Is P=NP?" --strategy majority_vote
omnillm council "Explain the trolley problem" --strategy weighted

# Specify custom council members
omnillm council "What should I know about quantum computing?" \
    -m openai-gpt4o -m claude-3.5-sonnet -m gemini-2-pro
```

The council command shows:
1. Individual responses from each council member
2. The synthesised final answer
3. Agreement score (how much the models agreed)
4. Which models (if any) dissented from the majority

### Smart Routing

```bash
# Route based on complexity (auto-detects)
omnillm route "Hi"
omnillm route "Analyse the economic implications of AGI development on labour markets"

# Route with budget constraint
omnillm route "Simple greeting" --budget 0.001

# Route with specific strategy
omnillm route "Write a haiku" --strategy LOWEST_COST
omnillm route "Debug complex async Python code" --strategy BEST_QUALITY
omnillm route "Quick yes/no question" --strategy LOWEST_LATENCY
```

### ELO Leaderboard

```bash
# View overall leaderboard
omnillm leaderboard

# View category-specific leaderboard
omnillm leaderboard --category reasoning
omnillm leaderboard --category code
```

### Cost Tracking

```bash
omnillm costs
```

Shows a breakdown of API spend per model across all sessions.

### Export Results

```bash
# Export to different formats
omnillm export --format csv --input results/eval.json -o results/report.csv
omnillm export --format markdown --input results/eval.json -o results/report.md
omnillm export --format json --input results/eval.json -o results/clean.json
```

---

## ➕ Adding a New Model

OmniLLM's plugin architecture makes adding models trivial. Open `config/models.yaml` and add:

```yaml
# Example: Adding GPT-5 when it releases
openai-gpt5:
  id: openai-gpt5
  provider: openai
  model: gpt-5
  api_key_env: OPENAI_API_KEY
  cost_per_1m_input: 10.00
  cost_per_1m_output: 30.00
  type: cloud
  description: "OpenAI GPT-5 — next generation flagship"
```

**That's it. 6 lines of YAML. Zero Python code changes.**

The new model is immediately available in:
- `omnillm models` listing
- `omnillm ask ... -m openai-gpt5`
- `omnillm evaluate -m openai-gpt5`
- `omnillm council ... -m openai-gpt5`
- Smart Router decisions

### Adding a Local Ollama Model

```yaml
phi3-local:
  id: phi3-local
  provider: ollama
  model: phi3:mini
  api_base: http://localhost:11434
  cost_per_1m_input: 0.00
  cost_per_1m_output: 0.00
  type: local
  description: "Microsoft Phi-3 Mini — local via Ollama"
```

Then pull the model: `ollama pull phi3:mini`

---

## 🤖 Robotics Integration (Future Roadmap)

OmniLLM includes an abstract bridge layer for connecting LLMs to physical social robots.

### Supported Platforms

| Robot | SDK | Architecture |
|-------|-----|-------------|
| **Pepper** (SoftBank) | NAOqi (Python 2.7) | HTTP bridge to NAOqi process |
| **NAO** (SoftBank) | NAOqi (Python 2.7) | HTTP bridge to NAOqi process |
| **Buddy** (Blue Frog) | Android | WebSocket streaming |

### Pepper/NAO: Python 2.7 ↔ 3.x Bridge

```
┌─────────────────────────────────────────────────────────┐
│  Pepper/NAO Robot (Python 2.7 process — NAOqi)         │
│  - ALAudioDevice captures voice via microphones         │
│  - ALFaceDetection detects human faces                  │
│  - ALAnimatedSpeech plays expressive speech             │
│  - ALMotion controls movement                           │
│  ↕ HTTP (WAV upload / JSON download)                    │
├─────────────────────────────────────────────────────────┤
│  AI Server (Python 3.x — OmniLLM)                      │
│  - Receives WAV audio, transcribes with Whisper         │
│  - Routes to LiteLLM gateway (or Consensus Engine)      │
│  - Returns RobotAction JSON                             │
│  - PepperBridge.execute_action() dispatches to robot    │
└─────────────────────────────────────────────────────────┘
```

### Buddy: Android WebSocket Streaming

```
Buddy (Android) ──WebSocket──▶ FastAPI + LiteLLM ──tokens──▶ Buddy TTS
```

Buddy receives LLM response tokens in real time, enabling the robot to start speaking before the full response is generated — dramatically improving perceived latency in human-robot interaction.

### ROS2 Nav2 Integration

```python
from omnillm.robotics.bridge import parse_nav2_goal

# Natural language to ROS2 Nav2 PoseStamped
goal = parse_nav2_goal(
    llm_output='{"position": {"x": 5.0, "y": 0.0, "z": 0.0}, '
               '"orientation": {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0}}'
)
# Use with ROS2: rclpy.action.ActionClient → NavigateToPose
```

### Safety in Robotics

**The Consensus Engine is critical for robotics safety**. A single hallucinated robot action can cause physical harm. By requiring 3+ models to agree before dispatching any movement command, the consensus engine provides a multi-layer safety check:

```python
from omnillm.consensus import ConsensusConfig, ConsensusEngine

# Require 80% council agreement for robot actions
config = ConsensusConfig(
    council_models=["openai-gpt4o", "claude-3.5-sonnet", "gemini-2-pro"],
    strategy="synthesis",
    min_agreement=0.8,  # High bar for physical actions
)
```

### Use Cases

- **Elderly Care**: Pepper robots with LLM support for medication reminders, companionship, and health monitoring
- **Education**: NAO robots as interactive tutors that can answer any question via LLM
- **Accessibility**: Buddy robots as AI-powered assistants for people with disabilities
- **Warehouse Robotics**: ROS2-enabled robots with natural language task instructions

---

## 🗺️ Roadmap

- [x] **Phase 1: Core Engine** — LiteLLM gateway, evaluation framework, ELO scorer, Rich CLI
- [x] **Phase 2: Consensus Engine + Smart Router** — LLM Council, multi-strategy routing
- [ ] **Phase 3: Dynamic Task Generation** — Automatic task generation, contamination detection
- [ ] **Phase 4: Robotics Bridge** — Real Pepper/NAO/Buddy integration (beyond mocks)
- [ ] **Phase 5: ROS2 Nav2** — Full navigation integration with autonomous waypoint planning
- [ ] **Phase 6: Web Dashboard** — Optional Datasette/Streamlit dashboard for visual analytics
- [ ] **Phase 7: Multi-Robot Experiments** — Multi-robot collaborative tasks with LLM coordination

---

## 📚 Complete References & Literature

### LLM Evaluation & Benchmarking

- MMLU: [Measuring Massive Multitask Language Understanding](https://arxiv.org/abs/2009.03300)
- HumanEval: [Evaluating Large Language Models Trained on Code](https://arxiv.org/abs/2107.03374)
- GSM8K: [Training Verifiers to Solve Math Word Problems](https://arxiv.org/abs/2110.14168)
- LiveBench: [A Challenging, Contamination-Free LLM Benchmark](https://livebench.ai) (ICLR 2025)
- DyCodeEval: [Dynamic Code Evaluation](https://arxiv.org/abs/2503.04149)
- IFEval: [Instruction-Following Evaluation for Large Language Models](https://arxiv.org/abs/2311.07911)
- TruthfulQA: [Measuring How Models Mimic Human Falsehoods](https://arxiv.org/abs/2109.07958)

### Data Contamination

- [Benchmarking LLMs Under Data Contamination: Static to Dynamic](https://arxiv.org/abs/2406.04244) (EMNLP 2025)
- [Contamination Detection: A Comprehensive Survey](https://arxiv.org/abs/2502.17521) — Collision Rate, Repeat Trials, Membership Inference, Chronological Analysis
- [Garbage In, Reasoning Out?](https://arxiv.org/abs/2506.23864) — Benchmark errors vs. model errors
- [Awesome Data Contamination](https://github.com/liyucheng09/Contamination_Detector)

### LLM-as-Judge

- [LLMs-as-Judges: A Comprehensive Survey](https://arxiv.org/abs/2412.05579) — 2700+ papers
- [Evaluating LLM-based Agents for Multi-Turn Conversations](https://arxiv.org/abs/2503.22458)
- [G-Eval: NLG Evaluation using GPT-4 with Better Human Alignment](https://arxiv.org/abs/2303.16634)
- [Judging LLM-as-a-Judge with MT-Bench](https://arxiv.org/abs/2306.05685)
- [LMSYS Chatbot Arena: Benchmarking LLMs in the Wild](https://arxiv.org/abs/2403.04132)

### Consensus & Ensembles

- [Learning to Trust the Crowd: Multi-Model Consensus Reasoning Engine](https://arxiv.org/abs/2601.07245)
- [Multiple Large AI Models' Consensus for Object Detection](https://www.mdpi.com/2076-3417/14/14/6020)
- [Mixture of Experts: Scaling Laws for Language Models](https://arxiv.org/abs/2101.03961)
- [Awesome-LLM-Ensemble](https://github.com/jxzhangjhu/Awesome-LLM-Ensemble)

### Dynamic Routing

- [LiteLLM Router Documentation](https://docs.litellm.ai/docs/routing) — Simple-Shuffle, Least-Busy, Latency-Based, Usage-Based
- [Cost Reduction with LLM Routing in RAG](https://www.latitude.so/blog/llm-routing-cost-reduction) — 75% cost reduction
- [RouteLLM: Learning to Route LLMs with Preference Data](https://arxiv.org/abs/2406.18665)
- [FrugalGPT: How to Use Large Language Models While Reducing Cost and Improving Performance](https://arxiv.org/abs/2305.05176)

### LLMs + Robotics

- [LLMs as NAO Robot 3D Motion Planners](https://arxiv.org/abs/2410.01741) (ICCV 2025 Workshop)
- [LLM Enabled Social Robots – Aged Care](https://ieeexplore.ieee.org/document/10191898) (IEEE)
- [Trinity: Modular Humanoid Robot AI System](https://arxiv.org/abs/2503.08338)
- [Integrating LLMs into Robotic Autonomy: A Review](https://www.mdpi.com/2673-2688/5/2/30)
- [LLM-Powered Multi-Session HRI](https://www.frontiersin.org/articles/10.3389/frobt.2024.1345979/)
- [DeepSeek R1 Controls Robotic Arm in Checkers](https://huggingface.co/blog/lerobot-deepseek-r1)
- [Latency-Aware Benchmarking for ROS2 Navigation](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10853435/)
- [SoftBank Robotics NAOqi Documentation](https://developer.softbankrobotics.com/naoqi-sdk-doc)
- [Awesome LLM-Robotics](https://github.com/GT-RIPL/Awesome-LLM-Robotics)

### Tools & Frameworks

- [LiteLLM](https://github.com/BerriAI/litellm) — Unified LLM gateway (100+ providers)
- [Ollama](https://ollama.com) — Local LLM runtime
- [Rich](https://github.com/Textualize/rich) — Terminal formatting library
- [Click](https://click.palletsprojects.com) — CLI framework
- [FastAPI](https://fastapi.tiangolo.com) — For robot WebSocket server
- [websockets](https://websockets.readthedocs.io) — For Buddy robot integration

### Leaderboards & Resources

- [LMSYS Chatbot Arena](https://chat.lmsys.org/?leaderboard) — Human preference ELO leaderboard
- [HuggingFace Open LLM Leaderboard](https://huggingface.co/spaces/HuggingFaceH4/open_llm_leaderboard)
- [LiveBench](https://livebench.ai) — Contamination-free benchmark
- [Artificial Analysis](https://artificialanalysis.ai) — Quality, latency, and cost benchmarks
- [Scale HELM](https://crfm.stanford.edu/helm/) — Holistic Evaluation of Language Models

---

## 🤝 Contributing

Contributions are welcome! Here's how to contribute to different areas:

### Adding a New Model

Edit `config/models.yaml` — see the [Adding a New Model](#-adding-a-new-model) section above.

### Adding Evaluation Tasks

Create or edit a YAML file in `config/tasks/`:

```yaml
tasks:
  - id: my-new-task
    category: reasoning
    prompt: "Your task prompt here"
    reference_answer: "Expected answer (optional)"
    grading_type: llm_judge
    judge_pattern: reference_based
    judge_prompt: "Scoring rubric for the judge model"
```

### Adding a Robot Bridge

1. Create `omnillm/robotics/my_robot.py`
2. Subclass `RobotBridge` from `omnillm.robotics.bridge`
3. Implement all 6 abstract methods
4. Add to `omnillm/robotics/__init__.py`

### Running Tests

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run all tests (no API keys required — uses mocks)
pytest tests/ -v

# Run specific test file
pytest tests/test_consensus.py -v

# Run with coverage
pytest tests/ --cov=omnillm --cov-report=term-missing
```

### Code Style

- Python 3.11+ with type hints throughout
- Docstrings on all public classes and methods
- Async/await for all LLM calls
- Black/Ruff for formatting

---

## 📄 License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.

```
MIT License
Copyright (c) 2026 Akshita-sr
```

---

<div align="center">
<b>🧠 OmniLLM — Compare, Route, and Orchestrate Every LLM — Today and Tomorrow</b>
<br>
Built with ❤️ for the open-source AI community
</div>
