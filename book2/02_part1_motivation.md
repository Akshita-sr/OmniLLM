\newpage

# Part I — Motivation & Scope

> *Before you can fairly read a single line of code, you need to understand what the project is trying to be, why it exists at all, and what it deliberately is not. Part I answers exactly those three questions.*

\newpage

## Chapter 1 — What Is OmniLLM, in One Sentence and in 1,000 Words

### At a Glance (Owner's Recap)

**OmniLLM is an open-source Python framework that lets you compare, route between, and orchestrate every major Large Language Model — and then plug whichever one is winning today into a Pepper humanoid robot.** It started as a multi-LLM benchmark workbench (gateway, smart router, LLM-as-judge, ELO leaderboard) and grew a second body: a LangGraph-based Human-Robot Interaction pipeline that gives Pepper a brain assembled out of any combination of GPT-4o, Claude Haiku, Gemini 2.5, DeepSeek, Llama 3, Qwen 2.5, Mistral 7B, and twelve more models, with optional **RAG** grounding against a domain knowledge base — currently the DIBRIS / Sgorbissa lab — and full per-interaction logging for experimental study.

**Files you most often touch:**

| File | Role |
|---|---|
| [omnillm/gateway.py](../omnillm/gateway.py) | The single async door to every LLM provider |
| [omnillm/router.py](../omnillm/router.py) | Six strategies for picking the right model for a given query |
| [omnillm/hri/agent_graph.py](../omnillm/hri/agent_graph.py) | The nine-node LangGraph pipeline that is "Pepper's brain" |
| [omnillm/server/app.py](../omnillm/server/app.py) | The Flask HTTP bridge between Pepper (Python 2.7) and the AI stack (Python 3.x) |
| [config/models.yaml](../config/models.yaml) | The 19-model registry — add a new LLM here, no Python changes needed |

### The Walk-Through (Beginner's Path)

Let's unpack that one-sentence definition piece by piece, because each word in it carries a specific design decision.

#### "A Large Language Model"

A **Large Language Model (LLM)** is an artificial-intelligence system that reads and produces natural-language text. The most familiar examples are *ChatGPT* (which is a product wrapper around the **GPT** family of models from OpenAI), *Claude* (from Anthropic), *Gemini* (from Google DeepMind), and *Llama* (from Meta). Each LLM is, internally, a very large neural network with billions to trillions of parameters that has been trained on a substantial fraction of the public internet plus assorted licensed and curated corpora. From the outside, an LLM looks like a function `f("user message") -> "assistant message"` — but every provider implements that function with their own API, their own pricing, their own latency profile, and their own strengths and weaknesses. GPT-4o is famously good at reasoning. Claude is famously good at long-context document understanding. Gemini is famously good at multimodal input. Mistral and Llama are famously cheap and open-weight. **Nobody is best at everything**, and the model that is best for *your* particular question today may be different from the one that is best for the next question.

#### "Every Major Large Language Model"

OmniLLM currently registers **19 models from 6+ providers**. That registry is plain YAML (`config/models.yaml`), and adding a new LLM is a seven-line YAML change with zero Python edits required. As of the 2026-05-20 deployment, the active registry includes:

- **OpenAI:** GPT-4o, GPT-4o-mini, GPT-3.5-turbo
- **Anthropic:** Claude Sonnet, Claude Haiku
- **Google:** Gemini 2.5 Pro, Gemini 2.5 Flash, Gemini Flash
- **DeepSeek:** DeepSeek V3
- **Ollama (local, free, no API key):** Llama 3:8b (aliased `llama3-8b-local`), Llama 3.2:3b, Qwen 2.5:7b (aliased `qwen3-8b-local`), Mistral 7B, Phi-3, plus a handful of fine-tuned variants

The key word in *every major LLM* is **abstraction**. OmniLLM never talks to a provider's SDK directly. Instead it relies on **LiteLLM**, a Python library that translates a uniform interface (`litellm.completion(model="...", messages=[...])`) into the actual HTTPS POST that each provider expects. The benefit is that OmniLLM's own code only has to deal with one calling convention, regardless of whether the model lives in OpenAI's data centre, in Anthropic's, or in `ollama serve` running on `localhost:11434` on your laptop.

#### "Compare, Route Between, and Orchestrate"

These three verbs map to three different patterns in the codebase:

| Verb | What it does | Code path |
|---|---|---|
| **Compare** | Run the same prompt against many models in parallel, score each output with an LLM-as-Judge, and update an ELO leaderboard | `omnillm/evaluator.py` + `omnillm/scorer.py` |
| **Route** | Pick *one* model dynamically based on a strategy (cheapest / fastest / best-quality / best-for-task) | `omnillm/router.py` |
| **Orchestrate** | Fan out to N models in parallel and merge their answers via voting, weighted-sum, or judge-LLM synthesis | `omnillm/consensus.py` |

The three patterns are not mutually exclusive — a single experimental condition can use them all. **Condition D** in the Embodied LLM Arena, for example, asks three models (GPT-4o-mini + Claude Haiku + Gemini Flash) the same question, then uses GPT-4o-mini *itself* as the judge to synthesise a final answer.

#### "Plug Into a Pepper Humanoid Robot"

**Pepper** is a 1.2-metre-tall, plastic-shelled humanoid robot manufactured by SoftBank Robotics (formerly Aldebaran Robotics) since 2014. It has:

- 20 degrees of freedom (DOF) for arm, head, and torso movement
- omnidirectional wheels on a triangular base (no legs — it cannot walk, but it can roll)
- 4 microphones on the head (used here for speech input)
- a 3-D depth sensor + 2 RGB cameras
- a touchscreen tablet on its chest
- coloured LEDs in its eyes (used here for emotional cues)
- a Linux-based on-board computer running the **NAOqi** middleware

The on-board computer is locked to **Python 2.7** because NAOqi's official SDK was last released in that era and has never been ported. This is the single most important fact about programming Pepper in 2026: **the modern AI stack you want to use does not run on the robot.** OmniLLM solves this by splitting itself into two processes that talk over HTTP, but we will return to that surprising amount of plumbing in Chapter 9 and Chapter 16.

#### "Open-Source Python Framework"

OmniLLM is MIT-licensed and lives on GitHub. The whole project is roughly **9,500 lines of Python plus 250 pages of documentation (this book)**. The codebase is deliberately structured as a *library* (`omnillm/` is a normal `pip install`-able package), a *CLI* (`omnillm` is a console script registered in `pyproject.toml`), and a *deployment* (`omnillm/server/app.py` is a Flask app you run with `python -m omnillm.server.app`). All three modes share the same gateway / router / RAG / agent-graph backbone.

### The Core Capabilities Table

This is the master "what does OmniLLM actually do" table — pin it to your wall.

| Capability | What it does | Why it exists |
|---|---|---|
| **Unified Gateway** | One `async` function call reaches any of 19 registered models from 6+ providers (cloud + local Ollama). | Without this, every script in the repo would carry per-provider try/except spaghetti. |
| **Smart Router** | Six strategies (`BEST_QUALITY`, `LOWEST_COST`, `LOWEST_LATENCY`, `BEST_VALUE`, `LOCAL_PREFERRED`, `TASK_TYPE`) that pick the right model per query. Learns from past evaluation results. | An LLM that is "best for one query" is not best for every query. Dynamic selection wins. |
| **Cost Tracker** | Real-time USD spend per model, per session, persisted to disk. | Cloud LLM bills can blow up silently mid-experiment. We want to see it. |
| **Consensus Engine (LLM Council)** | Fan out to N models in parallel, then synthesise via majority vote, confidence-weighted, or judge-LLM. | Implements **Condition D** of the Embodied LLM Arena (ensemble vs. single model). |
| **LLM-as-Judge** | Three research-backed patterns: Referenceless (G-Eval), Reference-Based, Pairwise (with position-bias swap-and-aggregate). | Open-ended HRI dialogues have no gold-standard answer. We need an LLM judge to score "naturalness" automatically. |
| **ELO Leaderboard** | Chatbot-Arena-style ratings, with per-category leaderboards (overall, reasoning, embodied_hri, …). | Lets us produce *the* central deliverable of this thesis: a leaderboard of LLMs ranked by their suitability as social-robot brains. |
| **RAG Pipeline** | ChromaDB-backed retrieval over our own documents (TXT, CSV, PDF), with optional faithfulness scoring. Falls back to keyword search if ChromaDB is unavailable. | Grounds the robot's answers in factual data about the DIBRIS lab and Prof. Sgorbissa's research instead of generic LLM trivia. |
| **LangGraph Agent Pipeline** | Whisper STT → language detect → task classify (T1–T4) → RAG / direct LLM / multilingual → robot action plan → log. Nine nodes. | The pipeline is the robot's brain. Every spoken interaction flows through this graph. |
| **Robotics Bridge** | Abstract `RobotBridge` with a concrete `PepperBridge` over HTTP. Auto-detects the robot. Falls back to **stub mode** when no robot is reachable — so the entire pipeline runs on a laptop with no robot at all. | Lets you develop the AI stack without ever booting Pepper. Critical for fast iteration. |
| **Three Trigger Modes** | `text`, `touch`, `vad` — the participant can type, head-touch, or just speak. | Mandatory for the experimental study: we need different conversational starts for different participants and different scenarios. |
| **Face Tracking** | NAOqi `ALTracker` follows the participant's face during conversation, increasing perceived attentiveness. | Increases experimental ecological validity and reduces "is it talking to me?" confusion. |
| **Plugin Architecture** | Adding a new LLM is 7 lines of YAML, zero Python changes. | Models change every two weeks in this field. Hard-coded provider lists become technical debt overnight. |
| **278+ Test Suite** | All pytest, all mocked, no API keys required. Currently 289 tests pass. | The whole codebase can be CI'd on a laptop with zero LLM cost. |

### Key Concepts in 60 Seconds (Beginner's Glossary)

If any of these are unfamiliar, here is the smallest possible definition you need to follow the rest of the book. The full glossary lives in Appendix B.

| Concept | One-line definition |
|---|---|
| **API key** | A secret password that lets your code call a cloud LLM provider's HTTPS service. |
| **Token** | A small chunk of text — roughly one short English word or a few characters — that LLMs charge per million. |
| **Ollama** | A free local LLM runtime that listens on `http://localhost:11434` and runs open-weight models on your own machine. No API key. |
| **LiteLLM** | A Python library that wraps 100+ LLM providers behind one identical interface. |
| **LangGraph** | A Python library by the LangChain team for building stateful, branching agent pipelines as directed graphs of nodes. |
| **ChromaDB** | A small embedded vector database. Used here as the storage for RAG document chunks. |
| **RAG** | Retrieval-Augmented Generation — search a corpus of documents, then ask the LLM to answer using the retrieved snippets as grounding. |
| **LLM-as-Judge** | The practice of using one LLM to grade the output of another. Surprisingly effective; well-studied since 2023. |
| **ELO** | A chess-derived rating system in which beating a higher-ranked opponent earns more points. +100 ≈ a 64% win rate. |
| **Consensus / Council** | Asking many models the same prompt in parallel and merging the answers. |
| **HRI** | Human-Robot Interaction — the academic research field this project lives in. |
| **NAOqi** | Pepper's on-board middleware operating system. Locked to Python 2.7. |
| **Choregraphe** | SoftBank's graphical IDE for programming Pepper. Ships a *virtual robot* (a simulator) that runs entirely in software with no real hardware required. |

### Academic Context (Researcher's Sidebar)

OmniLLM's design positions it squarely at the intersection of three active research streams:

1. **LLM evaluation and benchmarking.** Existing text-based benchmarks (MMLU [Hendrycks et al., 2021], HumanEval [Chen et al., 2021], GSM8K [Cobbe et al., 2021], LiveBench [White et al., 2024]) measure capabilities in isolation. Chatbot Arena [Chiang et al., 2024] introduced large-scale human pairwise ranking but remains text-only. OmniLLM's ELO scorer is directly inspired by Chatbot Arena's methodology and extends it to embodied interaction.
2. **LLM-as-Judge methodology.** G-Eval [Liu et al., 2023] established that GPT-4-class judges correlate strongly with human ratings on natural language generation tasks. Zheng et al. (2023) demonstrated that LLM judges can replicate human preferences in chatbot evaluation with >80% agreement. OmniLLM's `evaluator.py` implements all three patterns (referenceless, reference-based, pairwise with position-bias correction).
3. **Pepper-LLM integration.** The very first Pepper+LLM systems used a *single* model wired through a *single* speech pipeline (Hafez 2024; Mauliana et al. 2025). OmniLLM's contribution is to make the model *interchangeable* and to route between models dynamically based on task type — bringing the multi-model orchestration practice of the LLM benchmarking community into HRI for the first time.

For a complete annotated bibliography see Appendix G.

\newpage

## Chapter 2 — Why a Physical Humanoid Robot? The Motivation Behind Pepper

### At a Glance (Owner's Recap)

You could run every script in this repository against a terminal and never own a robot. The reason we run it through Pepper anyway is that **the body changes the conversation, and the conversation is what we are trying to study.** Five Pepper-specific properties motivate the embodiment: (1) Pepper is the most-cited humanoid robot in HRI literature, giving us a comparable baseline; (2) Pepper's social presence shifts how participants perceive an LLM's answers along dimensions like *trust*, *naturalness*, and *competence* that text alone cannot measure; (3) Pepper has a built-in gesture library, LEDs, a tablet, and microphones that map cleanly onto the affective and informational channels of natural human conversation; (4) Pepper is "good enough" hardware — not too expensive, not too fragile, deployed in hundreds of universities; (5) Pepper's NAOqi SDK forces the Python 2.7 ↔ 3.x split that, far from being a nuisance, is a fair model of how AI stacks will be deployed in real-world embodied systems for years to come.

### The Walk-Through (Beginner's Path)

#### Why Bother With Embodiment At All?

Every modern LLM benchmark we just cited in the previous chapter is conducted on text. You type a prompt, the LLM returns a string, a metric scores the string. Done. So why complicate things with a physical robot?

The honest answer is that **a chatbot in a browser and a chatbot inside a robot are different products even when the underlying LLM is identical.** Consider the same exchange in two media:

- **Text on a screen:** "Hello Pepper, how are you today?" → "Hello! I'm feeling bright and cheerful today, thank you! How about you?"
- **Real robot in a room:** A 1.2-metre humanoid turns its head to face you, its eye-LEDs glow soft green, it raises one arm in a wave, and a synthesised voice with mild prosodic variation says the same sentence.

The information content is identical. The **interaction** is not. The robot makes eye contact, holds gaze, has a body posture, and exists in your physical space. Decades of HRI research (see Bartneck et al. 2009, Fox & Gambino 2021, Bonarini 2020 — full citations in Appendix G) have established that participants:

- attribute more **agency** to embodied systems than to disembodied ones, even when both are running identical software (Horstmann & Krämer 2022);
- form trust in the embodied system through both verbal and non-verbal channels (Etemad-Sajadi et al. 2022);
- forgive errors more readily when an embodied robot apologises (Hoffmann et al. 2020);
- treat the conversation as more *social* and less *transactional* (Sugiyama 2021);
- experience more emotional engagement and report more enjoyment (Betriana et al. 2022; De Carolis et al. 2021).

If LLM-A and LLM-B produce equally accurate answers but participants rate LLM-A as more *trustworthy* when those answers come out of a robot, that gap is invisible to text benchmarks. The **Embodied LLM Arena** is designed precisely to measure that gap.

#### Why Pepper Specifically, and Not Another Robot?

The HRI research community has many humanoid platforms. The author's choice of Pepper is driven by:

1. **Citation density.** Pepper is, by a wide margin, the most-published humanoid robot in HRI between 2014 and 2026. The library accompanying this thesis (see Appendix G) contains over 80 peer-reviewed studies that use Pepper specifically. Choosing Pepper means our results are directly comparable to a deep prior literature.
2. **Availability.** Prof. Antonio Sgorbissa's HRI lab at DIBRIS, University of Genoa, owns a working Pepper. The unit is physically accessible to the author for the experimental study. (Several papers from the same lab — Chiang, Bruno, Menicatti, Recchiuto, Sgorbissa 2019 — exemplify the institutional context.)
3. **Built-in social affordances.** Pepper ships from the factory with:
   - a large pre-built animation library (over 100 named gestures: `wave`, `nod`, `point_left`, `Explain_7`, `Hey_1`, etc.)
   - text-to-speech in 20+ languages via NAOqi's `ALTextToSpeech` and `ALAnimatedSpeech`
   - a chest-mounted touchscreen tablet (`ALTabletService`) for fall-back text I/O
   - eye LEDs controllable by hex colour (`ALLeds`)
   - a face-tracking system (`ALTracker`) that finds and follows human faces
   - 4 directional microphones with energy-thresholded VAD (`ALAudioDevice`)
   - basic person-detection and engagement modules out of the box (`ALEngagementZones`, `ALPeoplePerception`)

   We use all of these. A bare-bones robot platform would force us to re-implement large chunks of social signal infrastructure before we could even start the LLM-comparison study.
4. **Affordable failure.** A new Pepper costs around €15,000 — expensive, but an order of magnitude cheaper than a humanoid robot like an iCub or an Atlas, and orders of magnitude cheaper than a research-grade dual-arm manipulator. If a participant trips over Pepper's base or a guest spills coffee on its tablet, the lab is not destroyed.
5. **The NAOqi / Python 2.7 constraint is realistic.** Pepper's middleware predates the modern AI stack by half a decade. We cannot upgrade it. Every choice we make in OmniLLM about *how the AI stack talks to the robot* has to confront this. In a sense the Python-2.7-vs-Python-3.11 boundary is a perfect miniature of the real-world deployment constraint that **AI moves faster than robot firmware**. By solving it explicitly here, we end up with a deployment pattern (HTTP bridge between an Old World and a New World) that generalises to any future legacy robot platform.

#### What Pepper is *Not* Good At

To set expectations honestly:

- **Pepper cannot walk.** It rolls on omnidirectional wheels and falls over on stairs.
- **Pepper's depth sensor is mediocre** in bright daylight (Bauer et al. 2019, Bauer et al. 2019b).
- **Pepper's microphones are noisy** at conversational range beyond 2 metres.
- **Pepper's on-board CPU cannot run modern LLMs.** Anything heavier than a 1B-parameter quantised model is out of the question. This is the central reason we need an off-board Python 3.x AI server.
- **NAOqi 2.5.5.5 on Windows 11 has a loopback bug** that requires binding `ALBroker` to `127.0.0.1` explicitly when connecting to Choregraphe's virtual robot. Real Pepper (running NAOqi natively on Linux) does not have this bug. (We will revisit this in Chapter 16.)

### Academic Context (Researcher's Sidebar)

The research literature on Pepper falls into roughly four buckets:

1. **Pepper as receptionist / front-desk** (Gardecki et al. 2018; Stommel et al. 2022; De Gauquier et al. 2018; Carros et al. 2022). Question-answering dialogue is central; most use one rule-based or NLU pipeline; OmniLLM extends this by making the dialogue brain LLM-driven and multi-model.
2. **Pepper for education / therapy** (Lehmann & Rossi 2019; Pigureddu & Gena 2023; Castellano et al. 2022; Forbrig 2019). Tasks are highly structured. OmniLLM's open-ended T3 (Social Conversation) condition aligns with this literature.
3. **Pepper navigation / vision** (Alhmiedat et al. 2023; Bista et al. 2021; Ardón et al. 2019; Perera et al. 2017). Not the focus of this thesis but informs our T2 (Navigation) task design: we ground "where is Room 305?" in the RAG-indexed lab map rather than asking Pepper to actually locomote there.
4. **Pepper + LLM** (Hafez 2024; Mauliana et al. 2025; Rahimi et al. 2025; Dogan et al. 2025). The youngest cluster — almost all post-2024 — and the one this thesis pushes forward. To the author's knowledge, **no prior published work has compared multiple LLMs as interchangeable backends in the same Pepper deployment**. This gap is the entire raison d'être of the Embodied LLM Arena.

The four-task taxonomy (T1 Information Retrieval, T2 Navigation, T3 Social Conversation, T4 Multilingual) follows the standard HRI dialogue-act categorisation used by Hsieh et al. (2017) and Gross & Krenn (2023), translated into terms relevant for a knowledge-grounded campus deployment.

\newpage

## Chapter 3 — What Happens When the Robot is Absent — the Three Operating Modes

### At a Glance (Owner's Recap)

OmniLLM has been designed so that **the absence of a physical robot is a first-class operating mode, not a fallback or a hack.** Three modes are supported, and all three exercise the same Python 3.x AI pipeline (LangGraph → RAG → LLM → action plan) end-to-end:

| Mode | Robot | Microphone | Speakers | Gestures | Used for |
|---|---|---|---|---|---|
| **A — No Robot** | None | None (text-only via curl or CLI) | None | Printed JSON | All AI-stack development; CI; the 278 pytest tests; participant pre-screening |
| **B — Virtual Pepper (Choregraphe)** | Software simulator | None (text trigger only) | "Robot Dialog" panel in Choregraphe GUI | Animations attempted; many report "behavior not installed" — see below | Live demos when no real robot available; this book's diagrams; the 2026-05-20 pilot |
| **C — Real Pepper** | Hardware | 4 head microphones, VAD or head-touch trigger | Pepper's stereo speakers | Full NAOqi animation library | The actual experimental study at DIBRIS |

The two non-real modes both exist for a single reason: **iteration speed**. You should not need a €15,000 robot booted, networked, and woken up to test whether the LangGraph node graph still routes correctly after a code change. Most of OmniLLM's development happened in Mode A on a laptop.

### The Walk-Through (Beginner's Path)

#### Mode A — Pure Text, No Robot at All

This is the default operating mode if you just clone the repo, install dependencies, and run things. There are three sub-modes within Mode A:

**(A1) The CLI:**

```powershell
omnillm ask "What time does the lab open?" -m openai-gpt4o-mini
omnillm route "Where is Room 305?" --strategy TASK_TYPE
omnillm council "What is consciousness?" --strategy synthesis
omnillm evaluate --output results/eval_2026.json
omnillm leaderboard --category embodied_hri
```

The CLI is your fastest path to exercising the gateway / router / consensus / evaluator / scorer subsystems without any HRI infrastructure.

**(A2) The Flask AI server + curl:**

Start the server:

```powershell
python -m omnillm.server.app --host 127.0.0.1 --port 5000
```

Then talk to it with curl (Windows PowerShell):

```powershell
curl -X POST http://127.0.0.1:5000/interact `
  -H "Content-Type: application/json" `
  -d '{"text":"Where is Room 305?","participant_id":"P001","session_id":"s1","condition":"C","rag_enabled":true}'
```

You get back a JSON `RobotAction` — `speech`, `gesture`, `emotion_led`, and `metadata` — exactly what Pepper would receive over HTTP. No robot needed.

**(A3) Programmatic, from Python:**

```python
import asyncio
from omnillm.gateway import LLMGateway
from omnillm.rag.pipeline import RAGPipeline
from omnillm.hri.agent_graph import build_hri_graph

async def main():
    gw = LLMGateway()
    rag = RAGPipeline(gateway=gw)
    rag.index_directory("knowledge_base/")
    graph = build_hri_graph(gateway=gw, rag=rag)
    result = await graph.ainvoke({
        "utterance": "What time does the lab open?",
        "participant_id": "P001",
        "session_id": "s1",
        "condition": "A",
        "rag_enabled": True,
    })
    print(result["response_text"])      # the spoken text
    print(result["robot_action"])       # the full JSON action plan

asyncio.run(main())
```

This is what the test suite does. All 289 tests run in Mode A.

#### Mode B — Choregraphe's Virtual Pepper

**Choregraphe** is SoftBank's official IDE for Pepper development. It ships with a *virtual robot* — effectively a full Pepper simulator with a rendered 3-D body, working text-to-speech, a placeholder set of gestures, and a faked sensor stream. It is everything an embodied developer needs short of an actual robot, and SoftBank distributes it free for research.

Choregraphe runs only on Windows (officially) and works by listening on a local TCP port that changes every launch — it picks a random port in the 40000–60000 range. When you launch Choregraphe you must:

1. Pull down **Connection → Connect to…**
2. Select the AKSHITA virtual robot in the list
3. Read off the **port number** in the connection dialog (e.g. `49959`)
4. Pass that port to OmniLLM via `--robot-port 49959`

The `make_pepper_bridge()` helper in [omnillm/robotics/pepper.py](../omnillm/robotics/pepper.py) will probe `127.0.0.1:49959` (and a list of recently-seen ports) automatically, so in practice you rarely need the `--robot-port` flag once you have run the system once on a given machine.

(!) **Two well-known Choregraphe limitations:**

1. **No real microphone or camera.** The virtual robot's `ALAudioRecorder` returns silence; its `ALVideoDevice` returns a black frame. This means you must use `--trigger text` (typed input) for any conversational test on the virtual robot — `--trigger touch` and `--trigger vad` cannot work.
2. **Animations may report "behavior not installed."** Choregraphe ships a *placeholder* animation library that does not include the full set of named animations real Pepper carries (`animations/Stand/Emotions/Positive/Enthusiastic_1`, `animations/Stand/Gestures/Explain_7`, `animations/Stand/Gestures/Hey_1`, etc.). When you send Pepper a gesture command in Choregraphe, NAOqi returns `behavior not installed`. **This is expected, not a bug.** Pepper still speaks the text and changes its LED colour; only the gesture is silently dropped. The 2026-05-20 pilot run with the author as P000 logged exactly these errors — see Chapter 29.

(Beginner) **Why this gesture limitation does not break the experiment.** The pilot ran the full 20-interaction matrix (5 conditions × 4 task types) on Choregraphe's virtual robot and produced fully usable speech, latency, RAG, and routing data even when gestures failed. The experimenter sees `gesture: false` in `robot_result.executed` but the speech, model_id, condition, latency, and faithfulness fields are all populated correctly. We can therefore *develop* and *pilot* in Mode B before ever booting real Pepper, then run the actual study in Mode C with no code changes — only a configuration flip.

#### Mode C — The Physical Pepper at DIBRIS

This is the mode that matters for the thesis. Pepper lives in Prof. Sgorbissa's HRI lab. The connection sequence is:

1. **Press the chest button once.** Pepper says its IP aloud over the speaker (e.g. "*One nine two, dot one six eight, dot one, dot one hundred*"). Call this `PEPPER_IP`. The same IP appears in the tablet's *About → Network* screen.
2. **Make sure laptop and Pepper are on the same Wi-Fi LAN.** Pepper does not need internet access; only LAN reachability to your laptop. `ping <PEPPER_IP>` from a PowerShell prompt should succeed.
3. **Start the AI server** on your laptop, bound to `0.0.0.0` so Pepper can reach it:

   ```powershell
   python -m omnillm.server.app --host 0.0.0.0 --port 5000
   ```
4. **Start the NAOqi bridge** — the small Python 2.7 HTTP server that lives near (or on) Pepper:

   ```powershell
   C:\Python27\python.exe omnillm\server\naoqi_bridge_server.py `
       --robot-ip <PEPPER_IP> --robot-port 9559 `
       --bind 0.0.0.0 --bridge-port 6000
   ```
5. **Run the participant session driver:**

   ```powershell
   .\venv\Scripts\python.exe scripts\pepper_demo\run_subject_experiment.py `
       --participant P001 `
       --server http://127.0.0.1:5000 `
       --bridge http://127.0.0.1:6000
   ```

The complete walk-through (with expected output and a symptom→cause→fix table) is **Chapter 21: Day Zero**.

### Academic Context (Researcher's Sidebar)

The decision to support a no-robot mode with the *same* code path that drives a real robot has a methodological pay-off: every result reported in the thesis is **reproducible by any reader who downloads the repo, even if they do not own a Pepper.** They will not get the embodied questionnaire data (which intrinsically requires a body), but they will get identical text outputs, identical RAG faithfulness scores, identical latency profiles, and identical cost tracking from the AI server. This is the open-science equivalent of providing both the Jupyter notebook *and* the raw data alongside a paper.

The "fall back to stub mode" design of `make_pepper_bridge()` is borrowed from established robot-software practice — most robotics frameworks (ROS, NAOqi itself, the Webots simulator) support a "simulated" vs "real" toggle. OmniLLM goes a step further by making the toggle automatic: the same `await bridge.execute_action(action)` call works in all three modes; only the bridge's `mode` attribute changes (`"server"` / `"naoqi"` / `"stub"`). For a code-level walkthrough see Chapter 13.

\newpage

## Chapter 4 — Scope, Hypotheses, and the Embodied LLM Arena Study

### At a Glance (Owner's Recap)

OmniLLM is the *engineering substrate* for a single research study: the **Embodied LLM Arena**. The study has three formal hypotheses (H1, H2, H3), four task types (T1–T4), five experimental conditions (A–E), one robot (Pepper), one knowledge base (DIBRIS / Sgorbissa lab), and ~15 participants run individually over a ~one-month window. The leaderboard output of the study (per-condition mean Likert scores + pairwise ELO ratings) is the central scientific contribution.

### The Walk-Through

#### The Research Gap

As established in Chapters 1–2, existing LLM benchmarks are entirely text-based. The handful of Pepper-LLM studies that exist (Hafez 2024; Mauliana et al. 2025) use a *single* LLM and report a single set of HRI metrics, with no inter-model comparison. **No prior work has:**

1. compared multiple LLMs as interchangeable backends for the *same* social robot;
2. applied dynamic smart routing between LLMs *during live HRI*;
3. tested whether embodied rankings agree with text-only rankings.

The Embodied LLM Arena fills exactly this gap.

#### The Three Hypotheses

| # | Hypothesis | How we test it |
|---|---|---|
| **H1** | Embodied HRI rankings differ significantly from text-only benchmark rankings. | Compare per-condition mean Likert score (this study) against MMLU + Chatbot-Arena rank for the same model. Spearman correlation; expect ρ < 0.7. |
| **H2** | Dynamic smart routing (Condition C) produces higher participant satisfaction than any single fixed model. | Pairwise win-rate of C vs A and C vs B in the final preference question. Expect C to win >55% of comparisons. |
| **H3** | RAG-augmented responses (A vs E) are rated more accurate and trustworthy across all backends. | Within-subject contrast: A.accuracy minus E.accuracy. Expect positive mean difference; one-sided t-test. |

#### The Four Task Types (T1–T4)

| Task | Name | Example prompt | Why a robot matters | Routing |
|---|---|---|---|---|
| **T1** | Information Retrieval | *"What time does the lab open?"* | Pepper greets a visitor and explains while gesturing. Tests RAG faithfulness directly. | → RAG pipeline → LLM |
| **T2** | Navigation / Guidance | *"Where is the Pepper room at DIBRIS?"* | Pepper *physically points* with its arm and shows a map on its tablet. Tests gesture-speech synchrony. | → RAG + Gesture Planner → LLM |
| **T3** | Social Conversation | *"Hello Pepper, how are you today?"* | Physical presence transforms a vacuous-sounding exchange into something perceived as warm. Tests naturalness. | → Direct LLM, no RAG |
| **T4** | Multilingual | *"Ciao Pepper, dove si trova la stazione di Brignole?"* | Embodiment makes multilingual feel more immersive (cf. Carolis et al. 2021). Tests cross-language gracefulness. | → Language detector → claude-haiku |

Participants are explicitly told they may **ask in any language and may switch languages mid-conversation.** The language detector and multilingual routing handle this automatically.

#### The Five Experimental Conditions (A–E)

| Condition | LLM | RAG | What it isolates |
|---|---|---|---|
| **A** | GPT-4o-mini (fixed cloud baseline) | ON | Cloud-baseline upper bound |
| **B** | Llama 3:8b via Ollama (fixed local) | ON | Free / offline baseline. Tests whether a local model is "good enough." |
| **C** | OmniLLM smart-routed (different LLM per task type) | ON | The effect of dynamic routing itself |
| **D** | Consensus council (GPT-4o-mini + Claude Haiku + Gemini Flash, synthesised) | ON | Ensemble vs single model |
| **E** | GPT-4o-mini, RAG disabled (control) | OFF | RAG's contribution, all else held constant |

Condition E is the **control** for H3: A and E differ only in whether RAG is enabled, so any difference in accuracy/trust ratings is attributable to RAG. (The May 2026 pilot caught a routing bug where Condition B was silently running Condition A's model; this is documented in detail in Chapter 29.)

#### Participants: How Many, How Often, Which Conditions

This is the question the README and the first edition of the book never quite answered. The answer is below — and the reasoning is worth knowing because it will come up if you ever defend the design choice.

**Target N = 15 participants.** Recruited over a ~one-month window in summer 2026, run individually at the lab (one participant per session, no overlap).

**Each participant experiences ALL FIVE conditions** in a single ~30-minute session. The pilot confirmed that 20 interactions (5 conditions × 4 task types) takes ~25 minutes including questionnaires — comfortably within the participant's attention window. This is the **within-subjects, fully-crossed design**.

| Design choice | Why |
|---|---|
| **All 5 conditions per participant** (not 3 of 5) | Maximises statistical power (each participant is their own control). The `experiment.py` docstring describes a 3-of-5 design as an alternative for studies where session length must be ≤15 minutes; in our case the pilot showed 30 minutes is acceptable. |
| **N = 15** (not 30 or 50) | Pragmatic — DIBRIS is a single-robot lab. A power analysis for paired t-test of A vs E accuracy at α=0.05 power=0.80 medium effect size d=0.5 gives n ≈ 27, but with a within-subjects 5-condition repeated-measures ANOVA the same effect requires only n ≈ 11. We over-provision to 15 to allow for two drop-outs. |
| **~One-month spread** | Avoids fatigue and lets us recruit through department mailing lists rather than a single batch. Also: if the model API costs or the robot itself behave differently across days, the temporal spread reduces a single-day artefact. |
| **Counterbalanced condition order** | Latin-square; see Chapter 25 for the explicit assignment table. |
| **Pilot participant (P000 — the author)** | Not counted in the final N. The two P000 runs on 2026-05-20 served only to debug the system. Their data is excluded from the analysis. |

(!) **If you change N or the design, document it in [omnillm/hri/experiment.py](../omnillm/hri/experiment.py)** — the docstring should always state the canonical design, not the alternatives.

#### Ethics, Consent, GDPR

A live human-subjects study at the University of Genoa requires:

- a **consent form** signed by each participant before any data is recorded;
- a **GDPR data-handling notice** explaining what data is collected, how long it is stored, who can access it, and how to request deletion;
- **anonymisation at logging time**: participants are referred to by code (P001, P002, …) in all stored files. The mapping from code to real identity is held by the experimenter on paper, separately from the digital data, and destroyed at the end of the study;
- **ethics committee approval** (Comitato Etico di Ateneo). At the time of writing, the protocol has been drafted and is being prepared for submission. The book reflects best-practice defaults; readers running their own version of this study elsewhere must obtain their own institutional approval.

The exact templates the author uses are reproduced in Chapter 28.

#### What is *Not* in Scope

To keep the project finite:

- **No fine-tuning of any LLM.** All models are used out-of-the-box. The thesis benchmarks them as-shipped.
- **No autonomous locomotion.** Pepper stays put (or rolls only on command in T2). We do not study navigation as a robotics-research task.
- **No vision-based interaction.** Face detection and tracking are used purely for engagement signal (look-at-the-speaker). We do not extract emotion, identity, or object recognition from the camera.
- **No multi-party dialogue.** One participant at a time. Group-interaction effects are documented in the future-scope chapter.
- **No deception or distress protocols.** The robot never lies about its nature, and the interactions are designed to be pleasant. (Compare with adversarial-prompting studies which are entirely out of scope.)

### Academic Context (Researcher's Sidebar)

The experimental design follows the **within-subjects repeated-measures** paradigm standard in HRI (Mavrogiannis et al. 2019; Lo et al. 2019; Stommel et al. 2022 for similar Pepper-based survey studies). Counterbalancing addresses order effects (Bartneck et al. 2009 noted that early-exposure conditions tend to receive more generous ratings). A Latin-square assignment per condition × per task ensures every condition appears in every ordinal position across the N=15 participants. The full assignment table is given in Chapter 25.

The five-condition factorial is deliberately *modest*: it crosses model-source (fixed vs. routed vs. council) with RAG presence, not with prompt-style or speech speed or gesture density. The choice keeps the participant cognitive load tractable and the statistical model interpretable, at the cost of not exploring some interesting interactions (e.g. *gesture density × model strength*). Future-scope variants are discussed in Chapter 32.

\newpage
