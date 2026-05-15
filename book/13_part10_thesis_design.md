\newpage

# PART X — THESIS DESIGN REFERENCE

> This part is the **research design half** of the book. It consolidates
> the `thesis_guidelines.pdf` material — the literature you must cite,
> the gap you fill, the three hypotheses, the four task types in full
> detail, the five experimental conditions, the metrics, and the
> one-month execution plan. If Part VII gave you the high-level "what",
> Part X gives you the academic framing and the practical schedule.

\newpage

## Chapter 48 — Literature Landscape: What Exists, What's Missing

> **AT A GLANCE.** Five 2024 publications connect LLMs to social
> robots. Every one of them uses a **single** LLM. Every one
> identifies multi-LLM comparison as a gap. OmniLLM fills it.

### 48.1  Key Scientific Papers

| Paper | Venue | What They Did | Gap Remaining |
|---|---|---|---|
| **Irfan et al. (2024)** — *Between Reality and Delusion: Challenges of Applying LLMs to Social Robots* | HRI 2024 Workshop | Identified challenges of integrating ChatGPT with Pepper; single-LLM only. | No multi-LLM comparison, no smart routing, no RAG. |
| **Nichols et al. (2024)** — *Can ChatGPT Control a Pepper Robot Adequately?* | arXiv | Connected GPT-4 to Pepper for dialogue; evaluated a single model. | Only one LLM tested, no systematic comparison, no user study with multiple backends. |
| **Grassi et al. (2024)** — *ChatGPT-based Pepper Robot for Restaurant Service* | HAI 2024 | Pepper as a restaurant assistant using ChatGPT. | Single LLM, no routing, no domain-specific RAG. |
| **Spitale et al. (2024)** — *Vita: An LLM-Powered Social Robot for Wellbeing* | arXiv | Pepper-like robot for mental wellbeing conversations using LLM. | Single LLM, no model comparison, no evaluation framework. |
| **Billing et al. (2024)** — *Language Models for Human-Robot Interaction* | Frontiers in Robotics & AI | Survey paper on LLM-HRI. | Calls out multi-LLM comparison as an open problem. |

### 48.2  Key GitHub Repositories and Resources

| Repository / Resource | What It Contains |
|---|---|
| Awesome-LLM-Robotics | Curated collection of 200+ papers on LLMs + robotics |
| PromptCraft-Robotics | Microsoft's framework for ChatGPT + robot control |
| LiteLLM | Unified API gateway for 100+ LLM providers |
| LangChain | RAG pipelines, document loaders, chains |
| LangGraph | Stateful agent graphs with conditional routing |
| SoftBank Robotics Labs | Official Pepper/NAO community examples |
| pepper-chatgpt-integration | Various community projects connecting Pepper to ChatGPT |
| Awesome-LLM-Ensemble | Multi-model consensus and ensemble methods |
| ChromaDB | Vector store for RAG |
| LMSYS Chatbot Arena | Human preference ELO leaderboard for LLMs |

### 48.3  Blog Posts and Practical Resources

- **HuggingFace Blog: "DeepSeek R1 Controls Robotic Arm"** — open-source
  LLM controlling a physical robot.
- **Latitude AI Blog: "LLM Routing Cost Reduction in RAG"** — 75 % cost
  savings with routing.
- **SoftBank Developer Portal:** NAOqi SDK documentation for Pepper.
- **Ollama Blog:** Running local models for robotics applications.

\newpage

## Chapter 49 — The Critical Research Gap You Will Fill

### 49.1  What No One Has Done

- **No study** has systematically compared multiple LLMs as
  interchangeable backends for a social robot through human experiments.
- **No work** has applied smart routing between LLMs in an embodied
  social robot context.
- **No research** has used RAG-augmented social robots to compare LLM
  performance on domain-specific knowledge tasks with real users.
- **No study** has compared LLM rankings derived from embodied HRI with
  standard text-only benchmark rankings.
- **No work** has combined LangGraph-based agent orchestration with
  social robot interaction management.

### 49.2  Why This Matters

Current LLM evaluations (MMLU, Chatbot Arena, LiveBench) are
**entirely text-based**. Social robot studies that use LLMs connect
**only a single model** (typically ChatGPT). No prior study has:

1. compared multiple LLMs as interchangeable backends for a social
   robot;
2. applied dynamic smart routing between models during live HRI; or
3. evaluated whether LLM rankings change when evaluated through
   embodied interaction rather than text-only benchmarks.

Furthermore, **no RAG-augmented social robot has been tested with
multiple LLM backends** to compare domain-specific knowledge delivery
performance.

### 49.3  The Recommended Thesis Title

> **"Embodied LLM Arena: Multi-Model Smart Routing and RAG-Augmented
> Knowledge Grounding for Task-Based Human-Robot Interaction with
> Pepper"**

This title captures all four contributions: *Embodied LLM Arena* (the
methodology), *Multi-Model* (the comparison), *Smart Routing* (the
routing study), *RAG-Augmented* (the grounding study), *Task-Based*
(the T1–T4 design), *Human-Robot Interaction with Pepper* (the platform).

\newpage

## Chapter 50 — Three Hypotheses

> **AT A GLANCE.** Three hypotheses, in falsifiable form, each tied to
> the data OmniLLM logs automatically. If you can rebuild the book from
> the source code (you can — see `book/build_pdf.py`), you can also
> derive every statistical test from the logged JSON (you can — see
> `omnillm/utils/experiment_logger.py`).

### 50.1  H1 — Embodied vs Text Rankings Diverge

> **H1: LLM quality rankings obtained through embodied human-robot
> interaction will differ significantly from text-only benchmark
> rankings.**

**Why we expect this:** physical presence, latency sensitivity, and
multimodal feedback change how humans perceive response quality. A
model that wins MMLU may lose on naturalness; a model that scores
poorly on coding benchmarks may score highly on warmth in a navigation
task.

**How to test:** correlate the Embodied LLM Leaderboard (Chapter 13's
`EloScorer.get_category_leaderboard("embodied_hri")`) with each model's
public Chatbot Arena ELO. **Spearman's ρ** is the right statistic;
a low or negative ρ supports H1.

### 50.2  H2 — Smart Routing Beats Any Fixed Model

> **H2: Dynamic smart routing between LLMs based on task type and
> language will produce higher user satisfaction than any single
> fixed-model configuration.**

**Why we expect this:** different models excel at different tasks
(claude-haiku is natural in chat, gemini-flash is fast on navigation,
gpt-4o-mini is accurate on RAG). Picking the right one per task should
dominate the best single model.

**How to test:** compare mean Likert scores across all five conditions
A–E (Chapter 52). A repeated-measures ANOVA, with condition C (smart
routed) significantly above A (cloud baseline) and B (local baseline),
supports H2.

### 50.3  H3 — RAG Lifts Every Backend

> **H3: RAG-augmented responses will be rated significantly more
> accurate and trustworthy than non-RAG responses across all LLM
> backends.**

**Why we expect this:** RAG grounds answers in your lab's actual
documents (WiFi password, opening hours, room locations) which no LLM
could have seen during training.

**How to test:** compare condition A (GPT-4o-mini + RAG) against
condition E (GPT-4o-mini, RAG off). The pair holds the model constant
and isolates RAG. A paired t-test on the "I trust the information"
Likert item, with A > E, supports H3.

### 50.4  Sample Size and Power

For a within-subjects design with 3 conditions per participant, a
medium effect size (Cohen's $d$ ≈ 0.5) and α = 0.05, **N ≈ 15–25**
participants yields ~80 % statistical power for the main contrasts.
This is the standard sample for an HRI study of this design.

\newpage

## Chapter 51 — The Four Task Types in Full Detail

OmniLLM's classifier (`omnillm/hri/classifier.py`) labels every
utterance T1, T2, T3 or T4. The LangGraph router branches on the
result. Here is what each task type tests and why a physical robot
is essential for each.

### 51.1  T1 — Information Retrieval (RAG-Dependent)

**Example utterances:**

- "What time does the lab open?"
- "Tell me about Professor X's research."
- "What is the WiFi password?"
- "When is the next open day?"

**What is tested:** factual accuracy + RAG faithfulness. The
underlying knowledge is in `knowledge_base/*.txt|csv|pdf`. The LLM's
job is to use the retrieved chunks faithfully, not invent.

**Why a robot is essential:** Pepper greets the visitor, uses the
tablet to show extra context (a photo of the professor, the lab map),
and gestures while explaining. A pure chatbot loses the
greeting-warmth dimension that affects perceived accuracy.

**Metrics:** RAG faithfulness score, retrieval similarity, judge
score for factual accuracy.

### 51.2  T2 — Navigation / Guidance (Robot Body Essential)

**Example utterances:**

- "Where is Room 305?"
- "Can you point me to the cafeteria?"
- "How do I get to the seminar room?"

**What is tested:** spatial-language grounding + gesture-speech
synchronisation. The LLM must produce a direction; the robot must
point with the matching arm.

**Why a robot is essential:** Pepper **physically points** in
directions, shows a map on its tablet, can walk partway to guide the
person. A chatbot cannot point.

**Metrics:** gesture appropriateness (observer-rated), navigation
success (binary), Likert "the robot's gestures were appropriate".

### 51.3  T3 — Social Conversation (Tests Naturalness)

**Example utterances:**

- "How are you?"
- "Tell me something interesting."
- "What do you think about AI?"

**What is tested:** fluency, warmth, empathy, openness. There is no
correct answer; the LLM is judged on style.

**Why a robot is essential:** physical presence creates social
pressure and engagement that text chat does not. Eye contact, head
tracking, animated gestures change perceived naturalness.

**Metrics:** Likert "the robot was natural to talk to", Godspeed
Anthropomorphism and Likeability subscales.

### 51.4  T4 — Multilingual Interaction (Tests Language Routing)

**Example utterances:**

- "Où est la salle 305 ?" (French)
- "Wo ist der Kaffeeraum?" (German)
- "¿Cuándo es el próximo seminario?" (Spanish)

**What is tested:** automatic language detection + per-language model
routing. The system must detect the language and pick the model with
the best coverage for that language.

**Why a robot is essential:** the robot's physical embodiment makes
multilingual experience more immersive and testable than a screen
chatbot. Foreign visitors meeting a robot is a higher-stakes
interaction than typing into a translation box.

**Metrics:** language-detection accuracy, response-in-correct-language
rate (observer-rated), Likert "the robot understood me".

\newpage

## Chapter 52 — The Five Experimental Conditions

Each participant experiences **three of the five** conditions in a
counterbalanced Latin-square order. Across 20 participants this
yields 60 condition-runs × 4 tasks = **240 interaction data points**.

| Condition | Description | What It Tests |
|---|---|---|
| **A — Fixed Cloud LLM** | GPT-4o-mini for all tasks | Baseline cloud performance |
| **B — Fixed Local LLM** | Llama 3:8b via Ollama for all tasks | Baseline local / free performance |
| **C — Smart-Routed** | OmniLLM selects the best model per task type | Smart routing effectiveness |
| **D — Consensus / Council** | 3 models answer; judge synthesises | Consensus vs. single model |
| **E — RAG-Off Control** | Same as A but without RAG | Isolates RAG contribution |

### 52.1  Why These Five and Not Others

The design is the smallest set that probes all four dimensions:

- **A vs B** — cloud vs local.
- **A vs C** — fixed vs smart-routed.
- **A vs D** — single vs ensemble.
- **A vs E** — with-RAG vs without-RAG.

Adding more conditions (e.g., "smart-routed but local-only", "consensus
without synthesis") gives more data but quadruples recruitment cost.
The five-condition design has enough power for repeated-measures ANOVA
on the main effects.

### 52.2  Counterbalancing — A Worked Latin Square

For 5 conditions and 5 participants per cell, a balanced Latin square
distributes order:

| Participant | Block 1 | Block 2 | Block 3 |
|---|---|---|---|
| P001 | A | C | E |
| P002 | B | A | D |
| P003 | C | E | A |
| P004 | D | B | C |
| P005 | E | D | B |
| P006 | A | E | C |
| P007 | B | D | A |
| P008 | C | A | E |
| P009 | D | C | B |
| P010 | E | B | D |

You can also use a Williams design or simple randomisation; with N = 15
the exact assignment matters less than ensuring **no condition is
always first** and **no condition is always last**.

\newpage

## Chapter 53 — Automatic and Human-Rated Metrics

### 53.1  Automatic Metrics (logged by `ExperimentLogger`)

Every interaction creates an `InteractionRecord` with:

| Field | Source |
|---|---|
| `model_id` | The model that ultimately answered |
| `latency_ms` | Wall clock from end-of-speech to start-of-speech |
| `input_tokens` / `output_tokens` | LiteLLM usage |
| `cost_usd` | Computed from `models.yaml` pricing |
| `rag_retrieval_scores` | ChromaDB cosine similarity (top-k) |
| `rag_faithfulness` | LLM-as-Judge score (0–1) |
| `hallucination_detected` | Heuristic flag (word-overlap < 20 %) |
| `judge_score` | Referenceless judge quality (0–1) |
| `detected_language` | LanguageDetector result |
| `task_type` | HRITaskClassifier output (T1–T4) |
| `gesture_used` | What Pepper actually did |
| `task_success` | Observer-coded binary |

All twelve fields land in CSV/JSON exports — directly loadable into R,
SPSS, JASP or pandas.

### 53.2  Human-Rated Metrics (After Each Condition)

The `InteractionQuestionnaire` dataclass collects five 1–7 Likert items:

1. The robot's answers were **accurate**.
2. The robot was **natural** to talk to.
3. I **trust** the information the robot gave me.
4. The robot's **gestures** were appropriate.
5. The robot responded **quickly enough**.

Optional: full **Godspeed** five-subscale (1–5 each):
Anthropomorphism, Animacy, Likeability, Perceived Intelligence,
Perceived Safety.

### 53.3  Pairwise Preference (At End of Session)

> "Which version of Pepper did you prefer overall? Why?"

This produces a `PairwisePreference` record that updates the **Embodied
LLM Leaderboard** via `EloScorer.record_match(...,
category="embodied_hri")`. After all participants, the leaderboard
ranks the five conditions and (indirectly) the models that powered
each.

### 53.4  Observer Ratings (Live During Each Interaction)

The `ObserverRating` dataclass captures:

- gesture-speech synchronisation quality (1–5)
- breakdown count (number of "wait, what?" moments)
- task completion (binary)
- any qualitative notes

\newpage

## Chapter 54 — One-Month Execution Plan

A working schedule used by labs that have completed similar studies.
Calibrate dates to your own timeline; the **dependencies between
days** are what matters, not the absolute dates.

### 54.1  Week 1 — Infrastructure Setup (Days 1–7)

**Day 1–2 — Pepper ↔ AI Server Bridge.** Set up the Flask server
(`python -m omnillm.server.app`). Verify `/health` returns OK. On
Pepper (Python 2.7), write the NAOqi client. Test with a hard-coded
response first, then with a single LLM.

**Day 3–4 — OmniLLM + LiteLLM Integration.** Configure
`config/models.yaml` with all target models (GPT-4o-mini, Claude
Haiku, Gemini Flash, DeepSeek + 3 Ollama models). Test the smart
router and LLM-as-Judge.

**Day 5–6 — RAG Pipeline.** Populate
`knowledge_base/{lab_info,faq,visitor_profiles,...}` with **real lab
data**. Index. Test retrieval with `omnillm ask --rag "What is the WiFi
password?"`.

**Day 7 — LangGraph + End-to-End Integration.** Build the agent graph
(transcribe → classify → route → RAG/LLM → action plan → respond).
End-to-end smoke test: speak to Pepper, get a RAG-augmented,
gesture-synchronised response.

### 54.2  Week 2 — Refinement and Experiment Prep (Days 8–14)

**Day 8–9 — Refine Robot Behaviours.** Map response types to
gestures (greeting → wave, information → open palms, pointing → arm
raise toward direction). Set up tablet displays. Tune Whisper for
your acoustic environment.

**Day 10–11 — Experiment Protocol Design.** Write the experimenter
script. Create task prompts for T1–T4. Design the questionnaire
(Google Forms or paper). Create consent forms. Set up automatic
logging.

**Day 12–13 — Pilot Testing.** Run 3–4 pilot sessions with lab
colleagues. Identify and fix latency, STT errors, gesture timing.
Refine task prompts.

**Day 14 — Final Preparations.** Schedule participants. Prepare the
physical lab space. Create a backup plan: if cloud APIs fail, fall back
to Ollama. Finalise data-collection scripts.

### 54.3  Week 3 — Run Experiments (Days 15–21)

**Day 15–21 — Participant Sessions.** 3–4 participants per day. Each
session ≈ 20–30 minutes (brief intro, 3 conditions × 4 tasks,
questionnaire, debrief). Target: **15–20 participants minimum**.
Experimenter takes observer notes. **Back up data daily.**

### 54.4  Week 4 — Analysis and Writing (Days 22–30)

**Day 22–24 — Data Analysis.** Aggregate the automatic metrics. Run
repeated-measures ANOVA or Friedman test on the Likert means. Compute
ELO rankings from pairwise preferences. Build the Embodied LLM
Leaderboard. Cross-correlate with Chatbot Arena rankings.

**Day 25–28 — Write.** Introduction + Related Work (use the literature
in Chapter 48). System Architecture (use the diagrams in Parts II and
Appendix G). Experimental Design (use Chapters 51–53). Results.
Discussion. Conclusions + Future Work (Chapter 60).

**Day 29–30 — Polish and Submit.** Create figures. Proofread. Prepare
the code repository for open-source release. Record a demo video.

\newpage

## Chapter 55 — Recommended Tools and the OpenClaw Question

### 55.1  The Recommended Stack

| Layer | Tool | Why |
|---|---|---|
| Robot | Pepper (NAOqi 2.5, Python 2.7 client) | The platform under study |
| Orchestration | OmniLLM | Your central platform |
| LLM Gateway | LiteLLM | Unified API across 100+ providers |
| Agent Graph | LangGraph | Stateful conversation with conditional routing |
| RAG | LangChain + ChromaDB | Document loaders + vector store |
| Local LLMs | Ollama | Llama 3:8b, Qwen 2.5:7b, Mistral:7b, DeepSeek-R1 14b |
| Cloud APIs | OpenAI, Anthropic, Google, DeepSeek | Cloud baselines |
| Speech-to-Text | OpenAI Whisper (local or API) | Cross-lingual, robust |
| Bridge | Flask | Python 2.7 ↔ 3.x HTTP |
| Surveys | Google Forms or paper | Standard HRI questionnaire delivery |

### 55.2  The OpenClaw Question

If you have access to **OpenClaw** (an agent-orchestration framework
sometimes mentioned alongside LangGraph):

- Use it as an alternative to LangGraph for the multi-step pipeline:
  perceive → classify → retrieve → generate → act.
- It can manage tool-calling: the agent calls RAG retrieval as a tool,
  calls the OmniLLM router as a tool, calls the robot action API as
  a tool.
- If OpenClaw supports multi-agent patterns, you can split the work
  across agents: a "Retrieval Agent" (handles RAG), a "Router Agent"
  (selects LLM), a "Robot Agent" (generates action plans), a "Judge
  Agent" (evaluates quality).
- If OpenClaw has its own LLM routing capabilities, you can compare
  OpenClaw routing vs. OmniLLM routing as **an additional experimental
  condition**.

OmniLLM does not depend on OpenClaw; LangGraph already covers the same
ground. Use whichever you are more comfortable with.

### 55.3  Why the Robot Is Essential (Direct Answers)

The user always asks: *"Could you do this without the robot?"*

**You cannot** because:

1. **The core research question is about embodied evaluation** — does
   physical presence change LLM quality perception? Removing the robot
   removes the question.
2. **Gesture-speech coordination timing** is a robot-specific variable.
3. **Navigation and pointing tasks** (T2) require a physical body.
4. **The tablet displays visual information** (maps, schedules)
   synchronised with speech.
5. **Physical-presence effects** (documented extensively in HRI
   literature — Bartneck, Wainer, Li, Bainbridge) are the confound
   that makes this study novel compared to any chatbot study.

You can, however, build and debug **most of OmniLLM** without a robot.
Chapter 58 covers the Choregraphe-only path.

### 55.4  Risks and Mitigations

| Risk | Mitigation |
|---|---|
| Pepper's speech recognition is unreliable | Use external microphone + Whisper API |
| Python 2.7 ↔ 3.x bridge latency | Optimise HTTP calls; co-locate the Flask server on a fast LAN |
| 1-month timeline is tight | Use a minimal viable task set; recruit from lab visitors |
| Cloud API costs | Use mini / haiku / flash tier models + Ollama local for most testing |
| Small sample size | Use within-subjects design to increase statistical power |
| Hardware failure (battery, motors) | Have a backup Pepper or rescheduling plan; keep charger plugged |
| Participant no-shows | Over-recruit by 25 %; have a confirmation email 24 h before |

### 55.5  Expected Contributions

If the experiment succeeds:

1. **First systematic multi-LLM comparison in embodied social robot HRI.**
2. **First evidence on whether embodied LLM rankings differ from
   text-only rankings.**
3. **First application of smart routing in social robotics.**
4. **First RAG-augmented social robot with multi-model backend
   comparison.**
5. **Open-source architecture** (OmniLLM + Pepper bridge) for
   reproducibility.
6. **Novel "Embodied LLM Arena" evaluation methodology** — a direct
   extension of LMSYS Chatbot Arena to physical space.

Suitable venues: **HRI Conference**, **ICRA**, **IEEE RO-MAN**,
**Frontiers in Robotics and AI**, **MDPI Robotics**.

\newpage
