# PART VII — FEATURES, SCOPE, EVALUATION

This part is the **reference** for what OmniLLM does. Four chapters: a
complete feature catalogue, the five experimental conditions in detail,
the evaluation methodology, and an honest discussion of scope and limits.

\newpage

## Chapter 36 — The Complete Feature Reference

### 36.1  Core LLM Features

| Feature | Where | One-line description |
|---------|-------|----------------------|
| Unified gateway | `gateway.py` | One async `query()` to any of 19 registered models |
| Concurrent multi-model query | `gateway.py: query_multiple` | Ask N models simultaneously via `asyncio.gather` |
| Model registry (YAML) | `config/models.yaml` | Add a model in 7 lines, no code changes |
| Cost tracking | `gateway.py + utils/cost_tracker.py` | Per-call USD, aggregated by model and session |
| Latency measurement | `gateway.py` | `latency_ms` on every response |
| Token counting | `gateway.py` | `input_tokens` + `output_tokens` |
| Structured error handling | `gateway.py: ModelResponse.error` | Errors never raise, always returned as fields |
| Auto-drop unsupported params | `gateway.py: drop_params=True` | Future-proof against new model API constraints |

### 36.2  Smart Routing Features

| Feature | Where | One-line description |
|---------|-------|----------------------|
| 6 routing strategies | `router.py: RoutingStrategy` | BEST_QUALITY, LOWEST_COST, LOWEST_LATENCY, BEST_VALUE, LOCAL_PREFERRED, TASK_TYPE |
| Composite value score | `router.py: _calculate_value_score` | quality·0.5 + cost·0.3 + latency·0.2 |
| Hard constraints | `router.py: route()` | `budget_usd` and `max_latency_ms` filter candidates |
| Learning from history | `router.py: update_scores` | Running average of past evaluation scores |
| HRI task-type routing | `router.py: route_for_hri_task` | Maps T1–T4 → optimal model per `hri_task_routing` config |
| Complexity-based routing | `router.py: route_by_complexity` | Word-count heuristic for fast/cheap vs slow/quality |

### 36.3  Consensus / Council Features

| Feature | Where | One-line description |
|---------|-------|----------------------|
| 3 strategies | `consensus.py: ConsensusConfig.strategy` | majority_vote, weighted, synthesis |
| Synthesis judging | `consensus.py: _synthesis` | A judge LLM combines all responses |
| Jaccard similarity clustering | `consensus.py: _jaccard_similarity` | Lightweight semantic clustering, no embeddings |
| Agreement scoring | `consensus.py: _compute_agreement_score` | Fraction in majority cluster |
| Dissenting model identification | `consensus.py: ConsensusResult.dissenting_models` | Lists models in minority cluster |
| Configurable council membership | `consensus.py: ConsensusConfig.council_models` | Any subset of registered models |

### 36.4  Evaluation Features

| Feature | Where | One-line description |
|---------|-------|----------------------|
| Referenceless judge (G-Eval) | `evaluator.py: _judge_referenceless` | Quality scoring with no gold answer |
| Reference-based judge | `evaluator.py: _judge_reference_based` | Comparison to a gold answer |
| Pairwise judge | `evaluator.py: _judge_pairwise` | Two-response comparison |
| Position-bias cancellation | `evaluator.py: evaluate_pairwise` | Swap-and-aggregate runs |
| Programmatic grading escape | `evaluator.py: EvalTask.grading_fn` | Custom Python function bypasses LLM judge |
| Concurrent benchmark runs | `evaluator.py: run_benchmark` | Semaphore-limited `asyncio.gather` over tasks × models |
| 8 evaluation axes | `tasks/sample_tasks.py` | reasoning, knowledge, code, instruction, safety, robot, latency, cost |
| YAML task loader | `tasks/loader.py` | Custom task suites without code |

### 36.5  ELO Scoring Features

| Feature | Where | One-line description |
|---------|-------|----------------------|
| Standard chess ELO math | `scorer.py: _update_ratings` | K=32, default rating 1500 |
| Per-category leaderboards | `scorer.py: get_category_leaderboard` | Independent ratings per axis |
| Rating history | `scorer.py: get_rating_history` | Time series of every rating change |
| JSON persistence | `scorer.py: save / load` | Serialise full state |

### 36.6  RAG Features

| Feature | Where | One-line description |
|---------|-------|----------------------|
| Multi-format ingestion | `rag/pipeline.py: index_file` | TXT, CSV, PDF |
| ChromaDB vector store | `rag/pipeline.py: _retrieve_chromadb` | Cosine similarity search |
| Keyword fallback | `rag/pipeline.py: _retrieve_keyword` | Works when ChromaDB not installed |
| Sliding-window chunking | `rag/pipeline.py: _split_text` | 512-char chunks with 64-char overlap |
| Faithfulness scoring | `rag/pipeline.py: _score_faithfulness` | LLM-as-Judge of grounding quality |
| Hallucination heuristic | `rag/pipeline.py: _detect_hallucination` | Word-overlap flag |
| Custom system prompt support | `rag/pipeline.py: query()` | Override default "use only context" prompt |
| Top-k configurable | `rag/pipeline.py: __init__` | Default 4, tune per use case |

### 36.7  HRI Features

| Feature | Where | One-line description |
|---------|-------|----------------------|
| T1–T4 task classifier | `hri/classifier.py` | Rule-based + optional LLM |
| Multilingual override | `hri/classifier.py: classify` | Non-English → T4 short-circuit |
| Three-tier language detector | `hri/language_detector.py` | Unicode script + n-gram + langdetect |
| Language→model mapping | `hri/language_detector.py: get_optimal_model` | Configurable per language |
| Five experimental conditions | `hri/experiment.py: CONDITION_CONFIGS` | A, B, C, D, E |
| Participant sessions | `hri/experiment.py: ParticipantSession` | UUID, task log, questionnaire scores |
| Per-condition / per-participant filtering | `hri/experiment.py: get_sessions_by_*` | Analysis-ready slices |

### 36.8  LangGraph Agent Pipeline Features

| Feature | Where | One-line description |
|---------|-------|----------------------|
| 9-node DAG | `hri/agent_graph.py: build_hri_graph` | Audio → action plan |
| Conditional routing | `hri/agent_graph.py: _route_by_task_type` | Per-task and per-condition branching |
| Closure-based dependency injection | `hri/agent_graph.py: _make_*_node` | No globals, no class hierarchy |
| Text-mode bypass | `hri/agent_graph.py: transcribe_audio` | Skips Whisper if `audio_bytes` empty |
| Optional logger plug-in | `hri/agent_graph.py: _make_log_node` | Disabled by passing `logger=None` |

### 36.9  Robot Bridge Features

| Feature | Where | One-line description |
|---------|-------|----------------------|
| Abstract `RobotBridge` | `robotics/bridge.py` | Interface for any robot |
| `RobotAction` dataclass | `robotics/bridge.py` | Universal action contract |
| `RobotSensorData` dataclass | `robotics/bridge.py` | Universal sensor reading |
| LLM-JSON-to-action parser | `robotics/bridge.py: parse_llm_to_action` | Tolerates Markdown code fences |
| ROS2 Nav2 goal parser | `robotics/bridge.py: parse_nav2_goal` | LLM → PoseStamped JSON |
| Pepper bridge | `robotics/pepper.py` | HTTP to NAOqi process |
| NAO bridge | `robotics/nao.py` | HTTP, with `walk_to`, `stand_up`, `sit_down` helpers |
| Buddy bridge | `robotics/buddy.py` | WebSocket with token streaming |

### 36.10  Robotics Helper Features

| Feature | Where | One-line description |
|---------|-------|----------------------|
| Gesture planner | `robotics/gesture_planner.py: plan` | Task + content → gesture name + LED hex |
| 12 named gestures | `robotics/gesture_planner.py: GESTURE_LED_COLORS` | wave, point_left/right/forward/up, nod, think, … |
| Whisper STT, two backends | `robotics/whisper_stt.py` | Local (`openai-whisper`) and API (`openai`) |
| Async transcription | `robotics/whisper_stt.py: transcribe` | `asyncio.to_thread` for local, native async for API |

### 36.11  Server Features

| Feature | Where | One-line description |
|---------|-------|----------------------|
| Flask app factory | `server/app.py: create_app` | Test-friendly construction |
| 6 endpoints | `server/app.py` | health, status, interact, transcribe, evaluate, export |
| Lazy LangGraph build | `server/app.py: _get_graph` | Tests can run without `langgraph` installed |
| Sync→async bridge | `server/app.py: _run_async` | Per-request event loop |
| Knowledge base auto-loader | `server/app.py: _load_knowledge_base` | Indexes everything in `knowledge_base/` on startup |
| Graceful fallback | `server/app.py: _fallback_interact` | Direct gateway call when LangGraph absent |
| NAOqi client | `server/naoqi_client.py` | Python 2.7 compatible, simulation mode when SDK absent |
| 12-entry gesture map | `server/naoqi_client.py: GESTURE_TO_BEHAVIOR` | Maps OmniLLM names to NAOqi behaviour paths |

### 36.12  Logging / Reporting Features

| Feature | Where | One-line description |
|---------|-------|----------------------|
| `InteractionRecord` | `utils/experiment_logger.py` | Full per-turn data structure |
| Interaction filtering | `utils/experiment_logger.py: get_records` | by session/condition/task/model |
| Aggregate summaries | `utils/experiment_logger.py: get_summary` | per-model, per-condition, per-task means |
| JSON + CSV export | `utils/experiment_logger.py: save / save_csv` | Stats-tool ready |
| Likert questionnaire dataclass | `utils/questionnaire.py: InteractionQuestionnaire` | 5 items, 1–7 scale, mean & normalised score |
| Godspeed dataclass | `utils/questionnaire.py: GodspeedResponse` | 5 subscales, 1–5 scale |
| Pairwise preference dataclass | `utils/questionnaire.py: PairwisePreference` | Feeds the ELO scorer |
| Observer rating dataclass | `utils/questionnaire.py: ObserverRating` | Live experimenter notes |
| Cost tracker | `utils/cost_tracker.py` | Per-model, per-session USD |
| Evaluation result exporter | `utils/export.py: ResultExporter` | CSV, JSON, Markdown, Rich Table |

### 36.13  CLI Features

| Command | One-line description |
|---------|----------------------|
| `omnillm models` | List all registered models in a coloured table |
| `omnillm ask "<q>"` | Send to one or many or all models |
| `omnillm evaluate` | Run benchmark on tasks × models |
| `omnillm compare "<q>"` | Pairwise judge between two models |
| `omnillm council "<q>"` | LLM Council with synthesis / vote / weighted |
| `omnillm route "<q>"` | Show routing decision and rationale |
| `omnillm leaderboard` | ELO rankings, optionally per category |
| `omnillm costs` | USD spend per model |
| `omnillm export` | Convert results JSON to CSV / MD / JSON |

\newpage

## Chapter 37 — The Five Experimental Conditions, in Detail

> **⚡ AT A GLANCE.** Five conditions A–E systematically probe four design
> dimensions: (i) cloud vs local, (ii) fixed model vs dynamic, (iii) single
> model vs ensemble, and (iv) RAG vs no-RAG. Each is implemented as a
> `ConditionConfig` and selected per session via `--condition`.

### 37.1  The Conditions in One Picture

```
            ┌──────────────────────────────────────────────────────┐
            │                                                      │
            │              FIXED               DYNAMIC             │
            │  ┌──────────────────────┬──────────────────────┐    │
            │  │                       │                      │    │
   CLOUD    │  │  A: GPT-4o-mini      │  C: Smart-routed    │    │
            │  │  RAG: ON              │  RAG: ON             │    │
            │  │  Baseline cloud       │  Per-task selection │    │
            │  │                       │                      │    │
            │  ├──────────────────────┼──────────────────────┤    │
            │  │                       │                      │    │
   LOCAL    │  │  B: Llama3:8b        │  D: Council          │    │
            │  │  RAG: ON              │  3 models +          │    │
            │  │  Free baseline        │  synthesis           │    │
            │  │                       │  RAG: ON             │    │
            │  └──────────────────────┴──────────────────────┘    │
            │                                                      │
            │      E: GPT-4o-mini, RAG OFF (control)             │
            │                                                      │
            └──────────────────────────────────────────────────────┘
```

### 37.2  Condition A — Fixed Cloud LLM

**What it is:** GPT-4o-mini for every task, every utterance. RAG enabled.

**What it tests:** "How good is a single decent cloud model on this kind
of HRI task?"

**Why GPT-4o-mini:** Best balance of accuracy, cost, and latency in
April 2026. $0.15/$0.60 per 1M tokens makes it ~5× cheaper than GPT-4o
without dramatic quality loss for HRI tasks.

**Config:**
```python
ConditionConfig(
    condition=ExperimentCondition.A,
    model_id="openai-gpt4o-mini",
    rag_enabled=True,
    description="Fixed cloud LLM (GPT-4o-mini) with RAG — baseline",
)
```

### 37.3  Condition B — Fixed Local LLM

**What it is:** Llama3:8b via Ollama for every task. RAG enabled.

**What it tests:** "How good is a free, local, private model on the same
tasks?"

**Why Llama3:8b:** Best free open-weight model in the 7–8B size that
fits on a typical research-grade GPU. ~4.7 GB download. No data leaves
the lab.

**Config:**
```python
ConditionConfig(
    condition=ExperimentCondition.B,
    model_id="llama3-8b-local",
    rag_enabled=True,
    description="Fixed local LLM (Llama3:8b via Ollama) with RAG",
)
```

**Practical note:** B is markedly slower than A on a CPU-only laptop
(2–4 s per response vs 0.5–1.5 s). For real-time HRI you typically need
a GPU.

### 37.4  Condition C — Smart-Routed

**What it is:** Per-task model selection via `SmartRouter.route_for_hri_task`.

**What it tests:** "Does picking the right model per task type beat any
fixed model?" — the core OmniLLM hypothesis.

**Routing table** (`models.yaml: hri_task_routing`):
| Task | Model | Why |
|------|-------|-----|
| T1 info_retrieval | `openai-gpt4o-mini` | Accurate, cheap, RAG-friendly |
| T2 navigation | `gemini-flash` | Fast, strong spatial language |
| T3 social_conversation | `claude-haiku` | Most natural conversational tone |
| T4 multilingual | `gemini-flash` | Strong multilingual coverage |

**Config:**
```python
ConditionConfig(
    condition=ExperimentCondition.C,
    model_id=None,                    # dynamic
    rag_enabled=True,
    use_smart_routing=True,
    description="Smart-routed — OmniLLM selects best model per task type",
)
```

### 37.5  Condition D — Consensus / Council

**What it is:** Three models answer the same question, a judge LLM
synthesises the best combined answer.

**What it tests:** "Does an ensemble beat any single model?"

**Default council:** GPT-4o-mini + Gemini Flash + Claude Haiku. All
three are HRI-tuned (low-latency, conversational).

**Latency cost:** Three concurrent LLM calls + a synthesis call ≈ 2 LLM
latencies + a synthesis latency ≈ 1.5–3 s. Slowest of all conditions.

**Config:**
```python
ConditionConfig(
    condition=ExperimentCondition.D,
    model_id=None,
    rag_enabled=True,
    use_consensus=True,
    council_models=["openai-gpt4o-mini", "claude-haiku", "gemini-flash"],
    description="Consensus council — 3 models, best answer synthesised",
)
```

### 37.6  Condition E — RAG-Off Control

**What it is:** Same model as Condition A (GPT-4o-mini), but RAG disabled.

**What it tests:** "How much does RAG actually help?" — the A vs E
comparison **isolates** RAG's contribution holding everything else
constant.

**Config:**
```python
ConditionConfig(
    condition=ExperimentCondition.E,
    model_id="openai-gpt4o-mini",
    rag_enabled=False,
    description="RAG-off control — GPT-4o-mini without knowledge retrieval",
)
```

The `_route_by_task_type` function in `agent_graph.py` short-circuits
all task types to `direct_llm` when `condition == "E"`.

### 37.7  Why These Five and Not Others?

The five-condition design is the smallest set that probes all four
dimensions:

- **A vs B**: cloud vs local.
- **A vs C**: fixed vs smart-routed.
- **A vs D**: single vs ensemble.
- **A vs E**: with-RAG vs without-RAG.

Adding more conditions (e.g. "smart-routed but local-only", "consensus
without synthesis") gives more data but also exponentially harder
recruitment. With ~20 participants × 3 of 5 conditions × 4 tasks = 240
data points, the design has enough power for repeated-measures ANOVA on
the main effects.

\newpage

## Chapter 38 — Evaluation Methodology — Eight Axes, Three Judge Patterns

### 38.1  The Eight Evaluation Axes

OmniLLM's built-in tasks (`tasks/sample_tasks.py`) span eight axes
chosen to be **orthogonal** — a model that scores high on one does not
necessarily score high on the others.

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

### 38.2  The Three Judge Patterns (Recap)

| Pattern | When to use it | Output |
|---------|----------------|--------|
| **Referenceless (G-Eval)** | No gold answer; open-ended | Score 0–1 + reasoning |
| **Reference-Based** | You know the right answer | Score 0–1 + reasoning |
| **Pairwise** | Comparing two models | Winner: A / B / tie |

### 38.3  Automatic Per-Interaction Metrics (HRI)

For each Embodied LLM Arena interaction the system automatically
records:

1. **Latency** — end-of-utterance to start-of-robot-speech, in ms.
2. **Token counts** — input + output (LLM cost driver).
3. **Cost** — USD, calculated from `models.yaml` pricing.
4. **RAG retrieval scores** — similarity scores of top-k chunks.
5. **RAG faithfulness** — LLM-as-Judge of grounding (0–1).
6. **Hallucination flag** — word-overlap heuristic.
7. **LLM-as-Judge quality** — referenceless score (0–1).
8. **Language detected** — ISO 639-1 code.
9. **Task classification** — T1/T2/T3/T4 + confidence.
10. **Model used** — the actual `model_id` (matters for Conditions C and D).
11. **Gesture used** — what Pepper did.
12. **Task success** — observer-coded binary.

All twelve fields land in `InteractionRecord` and export cleanly to CSV.

### 38.4  Human-Rated Metrics (Per Condition)

The `InteractionQuestionnaire` (1–7 Likert):

1. The robot's answers were accurate.
2. The robot was natural to talk to.
3. I trust the information the robot gave me.
4. The robot's gestures were appropriate.
5. The robot responded quickly enough.

Plus optional Godspeed (1–5 Likert across 5 subscales) and the pairwise
preference at session end.

### 38.5  Composite Scoring

OmniLLM's documented composite for choosing models in deployment:

```
value = quality × 0.5 + (1 / latency_normalised) × 0.3 + (1 / cost_normalised) × 0.2
```

This is the same formula used by `BEST_VALUE` in the smart router.
Quality is the LLM-as-Judge score; latency normalised against the 500ms
–10s range; cost normalised against the $0–$0.05 per query range.

### 38.6  ELO and the Embodied LLM Leaderboard

Every pairwise preference at the end of a session produces an ELO match:

```python
elo.record_match("condition-C", "condition-A", "model_a",
                 category="embodied_hri")
```

After all participants are run, the **embodied_hri** category leaderboard
is the headline result of the study.

### 38.7  Statistical Analysis

The expected analysis pipeline:

1. **Export.** `curl /export > all_data.json` then load into R or Python.
2. **Per-condition means.** Mean Likert per condition, with 95% CI.
3. **Within-subjects ANOVA.** Repeated-measures ANOVA on the 1–7 Likert
   means, with Greenhouse-Geisser correction.
4. **Pairwise post-hoc.** Bonferroni-corrected paired t-tests for the
   meaningful contrasts (A vs B, A vs C, A vs D, A vs E).
5. **ELO convergence.** Plot ELO as a time series; report final ratings.
6. **Cross-comparison.** Correlate the embodied ELO leaderboard with
   each model's MMLU/Chatbot Arena score. Discrepancy is the headline.

\newpage

## Chapter 39 — Scope, Limits, and What Comes Next

> **⚡ AT A GLANCE.** OmniLLM is intentionally focused. It is *not* a
> general-purpose chatbot framework, *not* a robotics simulator, *not* a
> production deployment platform. This chapter is the honest list of
> what it does not do.

### 39.1  What OmniLLM Is Not

| Not… | …because |
|------|----------|
| A general chatbot framework | Designed around HRI evaluation; lacks user-facing UI, accounts, history |
| A production deployment | Single-worker Flask, no auth, no rate limiting, no monitoring |
| A robotics simulator | The virtual robot is Choregraphe's, not ours |
| A multi-tenant service | One AI server serves one robot session at a time |
| A model training framework | We use models, we don't train them |
| A speech recognition framework | Whisper is a thin wrapper; we don't compete with `faster-whisper` |
| An embedding framework | ChromaDB does the embedding; we don't engineer embeddings |
| A real-time streaming framework | Buddy bridge has streaming, but the rest is request/response |

### 39.2  Known Limitations

**Audio capture is a placeholder.** The `_record_audio` method in
`naoqi_client.py` returns empty bytes. Real production audio capture
needs `ALAudioRecorder` or `processRemote` callbacks. See Chapter 21.8.

**RAG faithfulness scoring is opt-in and slow.** It costs an extra LLM
call per interaction. Disabled by default. Enable only for offline
analysis runs.

**ELO updates are session-end, not real-time.** Every pairwise
preference triggers exactly one ELO update; we don't do per-interaction
preference updates.

**Conditions A and E are different RAG regimes, but otherwise share a
model.** This is a feature (clean ablation) but means N participants in
A and E need to be ≥ N to detect the RAG main effect.

**No automated counterbalancing.** The experimenter is responsible for
the Latin square. With small N, this is not a code requirement, but for
larger studies you'd add a `LatinSquareGenerator`.

**Choregraphe is locked to NAOqi 2.5.** SoftBank's NAOqi 2.9 (Android
QiSDK) is not supported. Migrating to QiSDK is a substantial rewrite.

### 39.3  Future Work — High-Value Extensions

In rough priority order:

1. **Real audio capture** in `naoqi_client.py`. Replace the placeholder
   with `ALAudioRecorder`-based or callback-based capture. Critical for
   actual study runs.

2. **Streaming responses.** Pepper's TTS could start speaking as soon as
   the first sentence is generated, rather than waiting for the whole
   response. Reduces perceived latency by 30–60%. The Buddy bridge
   already implements this; Pepper would need a parallel
   `stream_response` path.

3. **Vision integration.** Pepper has cameras + a depth sensor. The
   agent graph could consume "what does Pepper see" as an additional
   input. Multi-modal LLMs (Gemini, GPT-4o) accept image inputs natively.

4. **QiSDK migration.** For deployments on a NAOqi 2.9 Pepper (newer
   robots, post-Aldebaran-bankruptcy), the entire NAOqi client would be
   rewritten in Kotlin/Java. This eliminates the Python 2.7 problem.

5. **Realtime API support.** OpenAI's Realtime API and Google Gemini
   Live can do speech-to-speech without an STT step. For Pepper, this
   means the audio path becomes a single low-latency loop.

6. **Adversarial / robustness testing.** A separate evaluation pass
   that probes how well each condition handles noisy speech, ambiguous
   questions, off-topic chatter, and minor adversarial inputs.

7. **Larger-scale study.** Current design assumes ~20 participants.
   Scaling to 100+ requires automated counterbalancing, faster session
   throughput, and a more sophisticated logging schema.

### 39.4  Limits of the Embodied LLM Arena Methodology

The research design is sound but has its limits:

- **External validity** — results from a single university lab may not
  generalise to hospitals, retail, or hotels. The platform is reusable
  precisely so others can replicate in different contexts.
- **Within-subjects fatigue** — a participant's questionnaire ratings
  for the *third* condition are influenced by experience with the
  first two. Counterbalancing controls for order, but cumulative
  fatigue is real.
- **LLM-as-Judge is itself an LLM.** Using GPT-4o to judge GPT-4o is
  partial self-evaluation. For best practice, use a *different*
  provider as the judge (e.g., Claude judging OpenAI outputs).
- **Hallucination heuristic is conservative.** False positives are
  common; treat the heuristic as a flag, not a verdict.

### 39.5  What This Project Will Likely Become

Two natural successors:

1. **The thesis.** This codebase + a participant study + a few months of
   analysis = a publishable paper. Suggested venues: HRI, RO-MAN,
   ICRA, Frontiers in Robotics & AI, MDPI Robotics.

2. **The reusable platform.** Other HRI labs can fork, swap the
   knowledge base, swap the robot bridge, and re-run the methodology.
   The abstract `RobotBridge` and YAML model registry make this almost
   parameter-only adaptation.

\newpage
