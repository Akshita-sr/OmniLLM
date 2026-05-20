\newpage

## Chapter 11 — Core LLM Modules

> Five files, none more than ~450 lines, between them handle every LLM call OmniLLM ever makes. This chapter walks through each one in the order they get imported during a typical interaction.

\newpage

### 11.1 `omnillm/gateway.py` — The Single Door to Every LLM

#### At a Glance

`gateway.py` is the smallest, most-used, and most-stable file in the project. Every LLM call — from a `omnillm ask` CLI invocation to a Condition D consensus inside the LangGraph — funnels through one async method: `LLMGateway.query(model_id, messages)`. The job of that method is to translate "I want to ask model X this question" into a single HTTPS call to whichever cloud or local provider owns model X, and to return a structured `ModelResponse` that carries the answer plus latency, token usage, and cost.

| Component | Lines | Role |
|---|---|---|
| `ModelResponse` dataclass | 30 | Standardised return type — content + tokens + latency + cost + error |
| `LLMGateway.__init__` | 15 | Reads `config/models.yaml`; no network I/O |
| `LLMGateway._build_model_string` | 25 | Provider routing prefix (`ollama/`, `gemini/`, `anthropic/`, …) |
| `LLMGateway._calculate_cost` | 8 | Per-million-token cost from the registry |
| `LLMGateway.query` | 75 | The one async call. ~100ms typical overhead before the cloud round-trip. |
| `LLMGateway.query_multiple` | 25 | `asyncio.gather()` for concurrent multi-model queries |
| `list_models / list_cloud_models / list_local_models / get_model_info` | 20 | Pure registry accessors |

#### The Walk-Through

**(Beginner) Why "Gateway" and not "Client"?** A *client* implies one-to-one with a server: "the OpenAI client", "the Anthropic client". A *gateway* is one-to-many: it accepts a uniform call and routes it. Since OmniLLM needs to look identical whether you call OpenAI or Ollama, we use the gateway terminology.

**The model registry.** When `LLMGateway()` is constructed it reads `config/models.yaml`. That file is the *source of truth* for which models exist. The relevant slice looks like this:

```yaml
models:
  openai-gpt4o-mini:
    id: openai-gpt4o-mini
    provider: openai
    model: gpt-4o-mini-2024-07-18
    api_key_env: OPENAI_API_KEY
    cost_per_1m_input: 0.15
    cost_per_1m_output: 0.60
    type: cloud
    description: "OpenAI's fast and cheap default. Good general purpose."
    hri_strengths: ["info_retrieval", "social_conversation"]

  llama3-8b-local:
    id: llama3-8b-local
    provider: ollama
    model: llama3.2:3b      # name as Ollama knows it
    api_base: http://localhost:11434
    cost_per_1m_input: 0.0
    cost_per_1m_output: 0.0
    type: local
    description: "Llama 3.2 3B running locally via Ollama. Free."
    hri_strengths: ["social_conversation"]
```

After the May 2026 cleanup, the `model:` field of `llama3-8b-local` points at `llama3.2:3b` — the model size that actually exists in the lab's Ollama installation. The historical name `llama3-8b-local` is preserved because Condition B's code references it. (!) **The OmniLLM ID and the upstream model name are not the same thing.** That separation is deliberate: when Ollama drops a model or the OpenAI catalogue renames `gpt-4o-mini`, you only edit `config/models.yaml`, not any Python source.

**The provider prefix trick.** LiteLLM uses prefixes to route. `_build_model_string` is six lines but it is the entire reason this codebase doesn't have 19 different SDK imports:

```python
def _build_model_string(self, model_id: str) -> str:
    cfg = self._models[model_id]
    provider = cfg.get("provider", "openai")
    model = cfg["model"]
    if provider == "ollama":             return f"ollama/{model}"
    if provider == "openai_compatible":  return f"openai/{model}"
    if provider == "deepseek":           return f"openai/{model}"
    if provider == "google":             return f"gemini/{model}"
    if provider == "anthropic":          return f"anthropic/{model}"
    return model  # openai
```

LiteLLM internally dispatches `ollama/llama3.2:3b` to its `ollama` backend, `gemini/gemini-2.5-flash` to its Gemini backend, and so on. We never have to import `openai`, `anthropic`, `google.generativeai` directly.

**The async query method.** This is the centre of gravity. The flow:

1. Look up the model in the registry. If absent, return an error `ModelResponse` (do NOT raise — the rest of the pipeline tolerates per-model errors).
2. Build the LiteLLM model string and assemble kwargs (`api_base`, `api_key`, `temperature`, `max_tokens`).
3. Read the API key from `os.environ` based on `api_key_env`. If the env var is missing, LiteLLM will raise downstream — we don't pre-check, because users on Ollama-only setups don't need any cloud keys.
4. Start a `time.perf_counter()`.
5. `await litellm.acompletion(**kwargs)` — the single line that actually goes over the network.
6. Stop the timer; extract tokens; calculate cost; return `ModelResponse`.
7. Any exception is caught and returned as a `ModelResponse` with `error=str(exc)`.

(Beginner) **Why catch all exceptions?** Robustness. The pipeline calls many models sometimes (Condition D council). A transient 429 from Anthropic should not abort the whole interaction. The downstream nodes check `if resp.is_error:` and decide whether to retry, fall back, or surface the error to the participant.

**The `litellm.drop_params = True` at module top.** OpenAI's o-series models (`o1`, `o1-mini`) reject `temperature` as an argument. So does GPT-5. Without `drop_params=True`, calling those models would crash on the first call. With it, LiteLLM silently drops `temperature` for the providers that don't accept it.

**`query_multiple` — parallel calls.** Used by Condition D and by `omnillm ask --all`. The implementation is one line: `asyncio.gather(*[self.query(...) for mid in model_ids])`. Three models in parallel run in `max(latency_1, latency_2, latency_3)` wall-clock, not their sum. This matters: a 3-model council can return in 1.5 seconds instead of 4.5.

#### Academic Context

The "one gateway per language" pattern is consistent with how production AI applications are structured at scale (e.g. *RouteLLM* — Ong et al. 2025). The choice of LiteLLM specifically follows BerriAI's open-source gateway pattern (LiteLLM proxy 2024); we use only the SDK, not the proxy server. The cost accounting code follows the LiteLLM-published per-token prices, which we cache locally in `config/models.yaml` to avoid making a network call just to ask "how much does this token cost?"

\newpage

### 11.2 `omnillm/router.py` — The Smart Model Selector

#### At a Glance

`router.py` answers the question *"given a query and some constraints, which one of the 19 registered models should I send it to?"* The `SmartRouter` class implements six strategies (`BEST_QUALITY`, `LOWEST_COST`, `LOWEST_LATENCY`, `BEST_VALUE`, `LOCAL_PREFERRED`, `TASK_TYPE`) and is *the* mechanism that makes **Condition C** (smart-routed) of the Embodied LLM Arena experiment a real, distinct condition. It also exports a `route_for_hri_task(hri_task_type, …)` shortcut that the agent graph calls during Condition C handling.

#### The Six Strategies

| Strategy | What it optimises | Used for |
|---|---|---|
| `BEST_QUALITY` | The highest quality score, ignoring cost & latency | When the task is hard reasoning and money/time are no object |
| `LOWEST_COST` | The cheapest model that still passes a minimum quality bar | Bulk batch evaluation; cost-sensitive deployments |
| `LOWEST_LATENCY` | The fastest model | Live HRI where responses ≤ 2s feel natural |
| `BEST_VALUE` | Composite score (quality 50%, cost 30%, latency 20%) | The default. A sensible compromise. |
| `LOCAL_PREFERRED` | Always prefer Ollama-based models when one passes the quality bar | Offline / privacy-sensitive deployments |
| `TASK_TYPE` | Look up `routing.hri_task_routing` in `models.yaml`. If matched, use the configured per-task model. Else fall through to `BEST_VALUE`. | Condition C of the Embodied LLM Arena |

#### The Composite Value Score (BEST_VALUE)

This is the formula that drives the default routing decision. It is also reused inside the gesture-planning logic and the consensus reward function:

```
value = 0.50 * quality
      + 0.30 * cost_score      where cost_score = max(0, 1 - cost / 0.05)
      + 0.20 * latency_score   where latency_score = max(0, 1 - (latency - 500) / 9500)
```

In words:
- *quality* is the LLM-as-judge score (0–1) for past evaluations of this model on this task category. If no eval data exists, fall back to a static defaults table in `SmartRouter._DEFAULT_SCORES`.
- *cost_score* normalises the per-query USD cost: $0 → 1.0, $0.05 → 0.0. (Most LLM calls are far under $0.001, so cheap models almost always score 1.0 here.)
- *latency_score* normalises latency: 500 ms → 1.0, 10,000 ms → 0.0.

The 50/30/20 weighting is editable (it lives in `_calculate_value_score`). The author tested several alternative weightings during development; this one produces the most stable rankings across the four HRI task types and is the weighting reported in the thesis.

#### The Self-Updating Quality Table

`SmartRouter` reads an optional `results_path` JSON file at construction. That file is the output of past `omnillm evaluate` runs, with the structure:

```json
[
  {"model_id": "openai-gpt4o-mini", "category": "info_retrieval",
   "score": 0.87, "latency_ms": 1340},
  {"model_id": "claude-haiku",     "category": "social_conversation",
   "score": 0.81, "latency_ms": 980},
  ...
]
```

The router rolls these into a per-category, per-model running mean (quality + latency) in `_load_results`. Calling `route(task_category="info_retrieval", strategy=TASK_TYPE)` will then prefer whichever model has the highest running-mean quality on `info_retrieval` queries.

In practice this means: **after one full run of the evaluation suite, the router's decisions become demonstrably better than the static `_DEFAULT_SCORES` defaults.** This is how OmniLLM "learns" — there is no training loop, no gradients; just running averages over past evaluation outcomes.

#### The `TASK_TYPE` Strategy and `hri_task_routing`

`config/models.yaml` contains a `routing.hri_task_routing` block:

```yaml
routing:
  hri_task_routing:
    info_retrieval: openai-gpt4o-mini
    navigation: openai-gpt4o-mini      # was gemini-flash; now stable choice
    social_conversation: claude-haiku
    multilingual: claude-haiku
  fallback_models:
    - openai-gpt4o-mini
    - claude-haiku
```

When Condition C asks for a `TASK_TYPE` route on `task_category="navigation"`, the router checks `hri_task_routing["navigation"]`, finds `openai-gpt4o-mini`, and returns that model. The lookup is intentionally simple — no LLM-based "meta-routing" — because the experimental design requires the routing decision to be reproducible and human-interpretable.

(!) **The May 2026 fix.** Until 2026-05-19, `hri_task_routing["multilingual"]` pointed at `gemini-flash`. The Google free-tier 429-rate-limited mid-pilot. The fix was a two-line YAML edit (`gemini-flash` → `claude-haiku`) and the multilingual node in `agent_graph.py` was updated to honour the same change. After the swap, the second pilot run on 2026-05-20 confirmed: Italian queries (the Brignole station prompt) now route cleanly to Claude Haiku and the response time is comparable.

#### Academic Context

The router's design follows the *strategy pattern* (Gamma et al. 1994). The composite value score is consistent with cost-aware LLM-router formulations in *FrugalGPT* (Chen et al. 2023) and *RouteLLM* (Ong et al. 2025) — both of which similarly weight quality against cost. Our weighting is lighter on cost than FrugalGPT (which emphasises minimising spend); we are running a single-session study where total cost is bounded and quality has higher marginal value to the experimental design.

\newpage

### 11.3 `omnillm/consensus.py` — The LLM Council

#### At a Glance

`consensus.py` implements **Condition D** of the experiment: ask three different LLMs the same question in parallel, then merge their answers into a single canonical response. Three merge strategies are supported (`majority_vote`, `weighted`, `synthesis`), of which `synthesis` is the default and the one used in the actual study.

#### The Three Synthesis Strategies

| Strategy | How it merges | When best |
|---|---|---|
| `majority_vote` | Cluster outputs by semantic similarity (cosine on embeddings ≥ 0.85). Pick the largest cluster's representative. | Closed-form QA where there is a single correct answer. |
| `weighted` | Each model's response is weighted by its historical quality score for the task category. Score-weighted text concatenation, then GPT-4o-mini summarises. | When some models are known to be better than others. |
| `synthesis` (default) | All N responses are presented to a *judge LLM* (default: GPT-4o-mini) with the prompt *"Here are N answers to the same question. Synthesise the best single answer, drawing on the strongest parts of each."* The judge's output is returned. | Open-ended HRI dialogue — where there is no single ground-truth answer but blending viewpoints improves quality. |

The Condition D council is configured in `omnillm/hri/experiment.py`:

```python
ExperimentCondition.D: ConditionConfig(
    condition=ExperimentCondition.D,
    model_id=None,
    rag_enabled=True,
    use_consensus=True,
    council_models=["openai-gpt4o-mini", "claude-haiku", "gemini-flash"],
    description="Consensus council — 3 models, best answer synthesised",
),
```

#### Why a 3-Model Council, Not 5 or 7?

Three reasons:

1. **Latency budget.** Pepper's audible feedback should land ≤ 4 seconds after the participant stops speaking. A 3-model council with `asyncio.gather()` runs in `max(t1, t2, t3) + synthesis_time` ≈ 1.8 + 1.0 = 2.8 seconds. A 5-model council with one slower outlier easily exceeds 4 seconds.
2. **Cost.** Each interaction in Condition D incurs ~3× the per-query cost of Condition A. Five models would be ~5×. Over 20 interactions × 15 participants the cost difference is non-trivial.
3. **Diminishing returns.** *Kallem (2026)* — a recent multi-model consensus paper — found that beyond 4 models, the marginal accuracy gain falls below the latency penalty. Three is a defensible Pareto point.

#### Position-Bias Mitigation in Synthesis

The judge LLM is sensitive to **position bias** — the order in which the N responses appear inside its prompt can shift which one it favours. The consensus engine mitigates this by **shuffling** the order of the N responses on each call. For the experimental analysis we additionally re-run a sample of Condition D interactions with swapped orderings and verify the synthesised answer's similarity is ≥ 0.95 across orderings (a sanity check; not a hard gate).

#### Council Fallback

If one of the three council models returns an error (`resp.is_error`), the engine drops that model from the synthesis and proceeds with the remaining two. If *all three* fail, the engine returns an error response and the agent graph falls back to the per-condition default model (in practice, GPT-4o-mini). This degradation strategy ensures Pepper always speaks *something* — silence is the worst possible interaction outcome from a participant's perspective.

\newpage

### 11.4 `omnillm/evaluator.py` — The LLM-as-Judge Pipeline

#### At a Glance

`evaluator.py` implements the three best-known LLM-as-judge patterns from the recent literature:

| Pattern | Function | Output | Reference |
|---|---|---|---|
| Referenceless (G-Eval) | `evaluate_referenceless(prompt, response, criteria)` | Score 0–1 + reasoning | Liu et al. 2023 |
| Reference-Based | `evaluate_reference_based(prompt, response, gold_answer)` | Score 0–1 + reasoning | Standard rubric scoring |
| Pairwise | `evaluate_pairwise(prompt, response_a, response_b)` | Winner: A / B / tie | Chatbot-Arena style (Zheng et al. 2023) |

The pairwise evaluator includes a **position-bias correction**: it calls the judge twice with the order of A and B swapped, then aggregates. If the two calls agree (both say A or both say B), the result is confident. If they disagree, the result is a `tie`. This is a published mitigation from Zheng et al. 2023.

#### Use in the Pipeline

The agent graph's RAG node optionally calls `RAGPipeline._score_faithfulness()`, which internally uses the same judge-LLM pattern (referenceless, with the retrieved chunks as context, scoring how well the answer is grounded in the context). The result populates `rag_faithfulness` in the state and ends up in the logged CSV row.

The CLI's `omnillm evaluate` command runs the full benchmark suite (8 axes × all registered models × all sample prompts), uses the referenceless judge to score every (model, prompt) pair, writes to `results/eval_*.json`, and updates the ELO scorer (see next section).

#### Why GPT-4o-mini as Judge?

The default judge is `openai-gpt4o-mini` (`evaluator.py: DEFAULT_JUDGE_MODEL`). Three reasons:

1. **Cost.** GPT-4o-mini is one of the cheapest "GPT-4 class" models. The full evaluation suite runs ~500 (model, prompt) pairs. Using `gpt-4o` would 10× the bill.
2. **Speed.** GPT-4o-mini is also fast enough to score in-the-loop (e.g. faithfulness scoring during a live HRI interaction).
3. **Agreement with human ratings.** Liu et al. 2023 and Zheng et al. 2023 both report strong correlation between GPT-4-class judges and human ratings on dialogue evaluation tasks. We do not need a frontier model.

The judge model is configurable via the `judge_model=` kwarg on the evaluator and on the RAG pipeline. For the published thesis runs, every LLM-as-judge call uses GPT-4o-mini.

#### A Known Limitation: Judge Self-Preference

A documented bias is that an LLM judge sometimes prefers its own family's outputs over those of other models (cf. Zheng et al. 2023 §6.3). Since OmniLLM's default judge is from the OpenAI family, GPT-4o-mini may sub-tly favour `openai-gpt4o-mini` and `openai-gpt4o` over Claude / Gemini / Llama responses in the leaderboard.

**Mitigations** built into the pipeline:

- The thesis's *primary* condition-level metric is the **human Likert questionnaire**, not the LLM-judge score. The judge feeds the leaderboard and the router's quality table, both of which influence Condition C's routing but do not directly score Conditions A–E for the human study.
- We additionally report **per-condition human pairwise preferences** (the questionnaire's final question), which are unaffected by the judge.
- For replication, the judge model can be swapped via a YAML edit. A Claude-Haiku-judge variant of the leaderboard is included in Appendix G as a robustness check.

\newpage

### 11.5 `omnillm/scorer.py` — The ELO Leaderboard

#### At a Glance

`scorer.py` implements a Chatbot-Arena-style ELO rating system. Every pairwise comparison (from the `evaluator.evaluate_pairwise` function or from the human questionnaire's pairwise preference question) updates the ratings of the two models involved. Categories are supported: there is an "overall" leaderboard but also `reasoning`, `code`, `embodied_hri`, and the four HRI task types.

#### The ELO Math

Standard ELO. Each model starts at rating `1000`. After a pairwise comparison:

```
expected_score_A = 1 / (1 + 10^((rating_B - rating_A) / 400))
new_rating_A    = rating_A + K * (actual_A - expected_score_A)
new_rating_B    = rating_B + K * (actual_B - expected_score_B)
```

where `actual_A` is `1.0` if A won, `0.5` for a tie, `0.0` if A lost; `actual_B = 1 - actual_A`. The K-factor is `32` for ratings under 2000 and `16` above. This matches the FIDE chess convention.

A 100-point ELO gap corresponds to a `1 / (1 + 10^(100/400)) ≈ 0.36` expected loss rate — i.e. the higher-rated model wins ~64% of the time. We use this 100-point unit as the operational threshold for "meaningfully better."

#### The Embodied LLM Leaderboard

After the experimental study completes, the human pairwise preferences are POSTed to `/evaluate` (the AI server's questionnaire endpoint). They are fed into the scorer under category `embodied_hri`. The resulting leaderboard is the **central scientific contribution of the thesis** — it is the first ELO leaderboard for LLMs ranked by their performance as social-robot brains.

#### Outputting the Leaderboard

```powershell
omnillm leaderboard                        # the overall ELO
omnillm leaderboard --category embodied_hri    # the thesis result
omnillm leaderboard --category multilingual    # T4-only
omnillm export --format csv --input results/leaderboard_embodied_hri.json
```

\newpage

### 11.6 `omnillm/cli.py` — Your Terminal Dashboard

#### At a Glance

`cli.py` is the `omnillm` console-script entry point registered in `pyproject.toml`:

```toml
[project.scripts]
omnillm = "omnillm.cli:main"
```

It is built on `click` (for argument parsing) and `rich` (for coloured terminal tables). The available commands are:

| Command | What it does |
|---|---|
| `omnillm models` | List all registered models in a coloured table (cloud + local) |
| `omnillm ask "..."` | Single-model query. `-m model_id` repeatable. `--all` queries every model. |
| `omnillm route "..."` | Show the router's decision and reasoning for a prompt |
| `omnillm council "..."` | Run a 3-model consensus and print the synthesised answer |
| `omnillm evaluate` | Run the full benchmark suite (8 axes × all models). Output JSON. |
| `omnillm compare "..." --model-a ... --model-b ...` | Pairwise comparison with position-bias swap |
| `omnillm leaderboard [--category ...]` | Print the ELO leaderboard |
| `omnillm costs` | Print per-model USD spend across all logged interactions |
| `omnillm export --format csv --input ... --output ...` | Convert results JSON to CSV / Markdown |

The CLI is the fastest way to exercise any single subsystem in isolation, *without* booting the Flask server or the robot. During development, the author's typical workflow is:

```powershell
# 1. Edit a router strategy in router.py
# 2. Re-run a sanity test:
omnillm route "Where is Room 305?" --strategy TASK_TYPE
# 3. Result printed in 1.2 seconds. Iterate.
```

This shortens the inner-loop iteration time from ~30 seconds (rebooting the Flask server) to ~1.5 seconds.

\newpage
