# PART III — MODULE DEEP-DIVE

This is the longest part of the book — one chapter per source-code module.
The chapters follow a uniform template:

1. **At-a-glance** — what the file is and why it exists.
2. **File facts** — line count, dependencies, public API surface.
3. **Walk-through** — beginner-friendly explanation of the code.
4. **Real code** — annotated excerpts from the actual source file.
5. **Worked example** — usage you can run.
6. **Academic context** — research and design rationale (when relevant).

\newpage

## Chapter 9 — `gateway.py` — The Door to Every LLM

> **⚡ AT A GLANCE.** `omnillm/gateway.py` is the **most important file in
> the project**. It exposes one async method, `query(model_id, messages)`,
> which can talk to any registered LLM (cloud or local) by reading
> `config/models.yaml` and using LiteLLM as the universal adapter. Returns a
> structured `ModelResponse` with content, tokens, latency, cost, and any
> error. `query_multiple()` runs many models concurrently via
> `asyncio.gather`.

### 9.1  File Facts

| Attribute | Value |
|-----------|------:|
| Path | `omnillm/gateway.py` |
| Lines | 271 |
| External deps | `litellm`, `pyyaml` |
| Public classes | `LLMGateway`, `ModelResponse` |
| Imports `models.yaml` from | `<repo_root>/config/models.yaml` |

### 9.2  The 30-Second Walk-Through

`LLMGateway` does five things:

1. **Loads** `config/models.yaml` on `__init__`.
2. **Lists** registered models (`list_models`, `list_cloud_models`,
   `list_local_models`).
3. **Builds** the LiteLLM model string for each provider (`ollama/llama3:8b`
   for local, just `gpt-4o` for OpenAI, `gemini/<model>` for Google, etc.).
4. **Calls** `litellm.acompletion()` with API key from environment.
5. **Returns** a `ModelResponse` dataclass — never raises; errors are
   captured in the `error` field.

That's it. Everything else in OmniLLM depends on this contract.

### 9.3  The `ModelResponse` Contract

This dataclass is the universal return type. Every higher layer (router,
council, evaluator, RAG) reads exactly these fields:

```python
@dataclass
class ModelResponse:
    model_id:       str
    content:        str
    input_tokens:   int   = 0
    output_tokens:  int   = 0
    latency_ms:     float = 0.0
    cost_usd:       float = 0.0
    time_to_first_token_ms: float = 0.0
    error:          str | None = None
    metadata:       dict[str, Any] = field(default_factory=dict)

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    @property
    def is_error(self) -> bool:
        return self.error is not None
```

> 📖 **Why a dataclass and not a dict?** With a dataclass, your IDE auto-completes
> field names, your type-checker catches typos, and the structure is documented in
> one place. A dict would work but every consumer would have to remember the keys.

### 9.4  How the Model String Is Built

This is the only provider-specific code in the whole gateway:

```python
def _build_model_string(self, model_id: str) -> str:
    cfg = self._models[model_id]
    provider = cfg.get("provider", "openai")
    model    = cfg["model"]

    if provider == "ollama":              return f"ollama/{model}"
    if provider == "openai_compatible":   return f"openai/{model}"
    if provider == "deepseek":            return f"openai/{model}"
    if provider == "google":              return f"gemini/{model}"
    if provider == "anthropic":           return f"anthropic/{model}"
    return model   # default: OpenAI uses bare model names
```

LiteLLM uses the prefix to dispatch to the correct provider library.
DeepSeek and Qwen are OpenAI-compatible, so they use the `openai/` prefix
plus a custom `api_base` URL. Ollama gets its own prefix. Google's API uses
`gemini/`. Anthropic uses its own SDK under `anthropic/`.

### 9.5  The Heart of the File — `query()`

Annotated, the core method looks like this:

```python
async def query(
    self,
    model_id: str,
    messages: list[dict[str, str]],
    temperature: float = 0.7,
    max_tokens: int = 2048,
) -> ModelResponse:
    # 1. Validate the model is registered.
    if model_id not in self._models:
        return ModelResponse(model_id=model_id, content="",
                             error=f"Model '{model_id}' not found in registry.")

    cfg = self._models[model_id]

    # 2. Build the LiteLLM model string, e.g. "ollama/llama3:8b".
    kwargs = {
        "model":       self._build_model_string(model_id),
        "messages":    messages,
        "temperature": temperature,
        "max_tokens":  max_tokens,
    }

    # 3. Per-model API base / key from YAML and environment.
    if cfg.get("api_base"):
        kwargs["api_base"] = cfg["api_base"]
    if cfg.get("api_key_env"):
        api_key = os.environ.get(cfg["api_key_env"], "")
        if api_key:
            kwargs["api_key"] = api_key

    # 4. Time the call so we can record latency_ms.
    start = time.perf_counter()
    try:
        resp = await litellm.acompletion(**kwargs)
        latency_ms = (time.perf_counter() - start) * 1000

        content        = resp.choices[0].message.content or ""
        usage          = getattr(resp, "usage", None)
        input_tokens   = getattr(usage, "prompt_tokens", 0) or 0
        output_tokens  = getattr(usage, "completion_tokens", 0) or 0
        cost           = self._calculate_cost(model_id, input_tokens, output_tokens)

        return ModelResponse(
            model_id=model_id, content=content,
            input_tokens=input_tokens, output_tokens=output_tokens,
            latency_ms=latency_ms, cost_usd=cost,
        )
    except Exception as exc:
        # 5. Never raise — return a structured error response.
        latency_ms = (time.perf_counter() - start) * 1000
        return ModelResponse(model_id=model_id, content="",
                             latency_ms=latency_ms, error=str(exc))
```

### 9.6  Concurrent Querying

This is one of the small details that makes OmniLLM fast:

```python
async def query_multiple(self, model_ids, messages, temperature=0.7,
                        max_tokens=2048):
    tasks = [self.query(mid, messages, temperature, max_tokens)
             for mid in model_ids]
    return list(await asyncio.gather(*tasks))
```

`asyncio.gather` dispatches all the queries **simultaneously**. Querying 5
models takes the wall-clock time of the slowest one, not the sum. This is
critical for the LLM Council (Condition D) and for the multi-model
evaluation runs.

### 9.7  The `litellm.drop_params = True` Footnote

At the top of the file you will find this line:

```python
litellm.drop_params = True
```

This is **important** and easy to miss. Some new models (OpenAI's o1, o3,
gpt-5 reasoning models) **do not accept** the `temperature` parameter. By
default LiteLLM raises `UnsupportedParamsError`. With `drop_params=True`,
LiteLLM silently strips unsupported parameters and continues. This single
line makes OmniLLM future-proof against model API changes.

### 9.8  Worked Example

A complete, runnable script:

```python
import asyncio
from omnillm.gateway import LLMGateway

async def main():
    gw = LLMGateway()

    # Single model
    resp = await gw.query("openai-gpt4o-mini",
                          [{"role": "user", "content": "Hi!"}])
    print(resp.content)
    print(f"Cost: ${resp.cost_usd:.6f}")

    # Many models in parallel
    responses = await gw.query_multiple(
        ["openai-gpt4o-mini", "claude-haiku", "gemini-flash"],
        [{"role": "user", "content": "What is the speed of light?"}]
    )
    for r in responses:
        print(f"{r.model_id} ({r.latency_ms:.0f} ms): {r.content[:80]}")

asyncio.run(main())
```

### 9.9  Adding a New Model — Zero Code

This is the payoff of YAML-driven design. To add a new model you append to
`config/models.yaml`:

```yaml
my-new-model:
  id: my-new-model
  provider: openai           # or anthropic | google | ollama | deepseek
  model: my-actual-model-name
  api_key_env: MY_API_KEY
  cost_per_1m_input: 1.00
  cost_per_1m_output: 3.00
  type: cloud
  description: "What this model is for"
  hri_strengths: ["info_retrieval"]   # optional, for HRI routing
```

…and the model is now usable across the entire system: gateway, router,
council, evaluator, CLI, RAG, agent graph. **No Python changes.** This is
why YAML lives in `config/`, not as Python constants.

\newpage

## Chapter 10 — `router.py` — The Smart Model Selector

> **⚡ AT A GLANCE.** `omnillm/router.py` answers the question "given a task
> and constraints, which model should I use?" Six strategies: BEST_QUALITY,
> LOWEST_COST, LOWEST_LATENCY, BEST_VALUE (composite), LOCAL_PREFERRED, and
> TASK_TYPE (HRI-specific). Hard constraints (`budget_usd`,
> `max_latency_ms`) are filters; the strategy then picks the best of
> what survives.

### 10.1  File Facts

| Attribute | Value |
|-----------|------:|
| Path | `omnillm/router.py` |
| Lines | 372 |
| Public classes | `SmartRouter`, `RouteDecision`, `RoutingStrategy` |
| Reads | `config/models.yaml`, optional `results/*.json` |

### 10.2  Strategy Cheat-Sheet

| Strategy | Picks | Used for |
|----------|-------|----------|
| `BEST_QUALITY` | model with highest quality score | research, complex problems |
| `LOWEST_COST` | cheapest model meeting quality threshold | bulk, demos |
| `LOWEST_LATENCY` | historically fastest model | real-time HRI |
| `BEST_VALUE` | composite (quality 50% + cost 30% + latency 20%) | general |
| `LOCAL_PREFERRED` | Ollama first, cloud fallback | privacy / offline / free |
| `TASK_TYPE` | HRI: maps T1/T2/T3/T4 to specific models | Embodied LLM Arena |

### 10.3  The Composite Value Formula

`BEST_VALUE` is the default strategy. Its composite score is:

```python
def _calculate_value_score(self, quality, cost, latency_ms):
    # quality already in [0, 1]
    cost_score    = max(0.0, 1.0 - cost / 0.05)            # $0 → 1, $0.05 → 0
    latency_score = max(0.0, 1.0 - (latency_ms - 500) / 9500)  # 500ms→1, 10s→0
    return 0.50 * quality + 0.30 * cost_score + 0.20 * latency_score
```

The weights (50/30/20) are deliberate. Quality matters more than cost and
latency for *most* user-facing tasks. You can change these in code if your
deployment cares more about money or speed.

### 10.4  How the Router Learns

The router has two sources of model scores:

1. **Default scores** — hardcoded in `_DEFAULT_SCORES` at the top of the
   module. These are the cold-start values before any evaluation has run.
2. **Evaluation results** — when `results_path` is passed at construction,
   the router reads past evaluation JSON files and updates a running average
   per (category, model) of quality and latency.

Each call to `update_scores()` appends new evaluation data. The scores
**improve over time** as more evaluations are completed. This is how
"learns from past evaluations" is realised — there is no neural network;
it is a maintained running average.

### 10.5  TASK_TYPE Routing for HRI

Condition C of the Embodied LLM Arena uses this. It reads the
`hri_task_routing` block of `models.yaml`:

```yaml
routing:
  hri_task_routing:
    info_retrieval:      openai-gpt4o-mini   # T1
    navigation:          gemini-flash        # T2
    social_conversation: claude-haiku        # T3
    multilingual:        gemini-flash        # T4
```

The mapping was chosen based on each model's strengths: GPT-4o-mini is
factually accurate and good with RAG; Gemini Flash is fast and good with
spatial language; Claude Haiku is empathetic and natural.

The implementation in `route()` is:

```python
elif strategy == RoutingStrategy.TASK_TYPE:
    hri_map = self._routing_cfg.get("hri_task_routing", {})
    preferred = hri_map.get(task_category)
    if preferred and preferred in self._models and preferred in candidates:
        candidates = [preferred]
    else:
        # Fallback: models that list this task in their hri_strengths
        strength_matches = [m for m in candidates
                            if task_category in self._models[m].get("hri_strengths", [])]
        if strength_matches:
            candidates = strength_matches
```

### 10.6  Worked Example

```python
from omnillm.router import SmartRouter, RoutingStrategy

router = SmartRouter()

# Strategy 1: Best quality, no constraints
d1 = router.route(strategy=RoutingStrategy.BEST_QUALITY)
print(f"Best quality model: {d1.model_id}")
# → openai-o1 (highest default quality score)

# Strategy 2: Cheap mode with budget
d2 = router.route(budget_usd=0.001, strategy=RoutingStrategy.LOWEST_COST)
print(f"Cheap model under $0.001: {d2.model_id}")
# → gemini-flash or an Ollama model

# Strategy 3: HRI navigation task
d3 = router.route_for_hri_task("navigation")
print(f"Best for navigation: {d3.model_id}")
# → gemini-flash (per hri_task_routing config)

# Strategy 4: Composite value with latency cap
d4 = router.route(max_latency_ms=2000, strategy=RoutingStrategy.BEST_VALUE)
print(f"Best value under 2s: {d4.model_id}")
# → likely gemini-flash or claude-haiku
```

\newpage

## Chapter 11 — `consensus.py` — The LLM Council

> **⚡ AT A GLANCE.** `ConsensusEngine` queries N models in parallel, then
> applies one of three strategies — `majority_vote` (Jaccard-clustered),
> `weighted` (static weights), or `synthesis` (a judge LLM combines the
> answers). Returns `ConsensusResult` with the final answer, individual
> responses, agreement score, dissenting models, and synthesis reasoning.

### 11.1  Why a Council?

A single LLM can be **confidently wrong**. If three independent models all
give the same answer, you have much higher confidence the answer is correct.
For robotics this is critical — a single hallucinated "turn left" command
can be a safety problem. Consensus filters errors that appear in only one
model.

References for the design:
- arXiv:2601.07245 — "Learning to Trust the Crowd"
- Karpathy's "LLM Council" concept
- MDPI 2024 — "Multiple Large AI Models' Consensus for Object Detection"

### 11.2  The Three Strategies

#### Strategy 1: `majority_vote`

Cluster the responses by **Jaccard similarity** of word tokens. Pick the
representative of the largest cluster.

```python
def _jaccard_similarity(text_a, text_b):
    tok_a = set(re.findall(r"\b\w+\b", text_a.lower()))
    tok_b = set(re.findall(r"\b\w+\b", text_b.lower()))
    return len(tok_a & tok_b) / len(tok_a | tok_b)
```

Threshold = 0.15. Cheap and dependency-free (no embedding model needed).
Works well for short factual answers, less well for long creative answers.

#### Strategy 2: `weighted`

Each model has a static quality weight (`_WEIGHTS` dict in source). Pick the
response from the highest-weighted model. Effectively a "trust the strongest
model" fallback. Production should replace static weights with EloScorer
ratings.

#### Strategy 3: `synthesis` (default)

The most powerful. A **judge LLM** sees all council responses and is asked
to synthesise the best combined answer. The judge prompt:

```
You are a synthesis judge reviewing multiple AI responses to a question.
Your job is to produce the BEST possible answer by combining insights from
all responses.

**Original Question:**
<the question>

**Council Responses:**
### model-id-1
<response 1>

### model-id-2
<response 2>

...

Instructions:
1. Identify areas of agreement across responses (likely correct).
2. Note any disagreements or unique insights.
3. Synthesise a final answer that is more accurate and complete than any
   individual response.

Respond with valid JSON: {final_answer, agreement_score, reasoning,
dissenting_models}.
```

This is what Condition D of the Embodied LLM Arena uses.

### 11.3  Worked Example

```python
import asyncio
from omnillm.gateway import LLMGateway
from omnillm.consensus import ConsensusConfig, ConsensusEngine

async def main():
    gw = LLMGateway()
    cfg = ConsensusConfig(
        council_models=["openai-gpt4o-mini", "claude-haiku", "gemini-flash"],
        judge_model="openai-gpt4o-mini",
        strategy="synthesis",
    )
    engine = ConsensusEngine(gw, cfg)
    result = await engine.query_council(
        [{"role": "user", "content": "Is consciousness emergent or fundamental?"}]
    )
    print("Final answer:", result.final_answer)
    print(f"Agreement: {result.agreement_score:.0%}")
    print("Dissenting:", result.dissenting_models)

asyncio.run(main())
```

\newpage

## Chapter 12 — `evaluator.py` — The LLM-as-Judge Pipeline

> **⚡ AT A GLANCE.** Three judge patterns, all implemented as one class.
> *Referenceless* (G-Eval) scores quality without a gold answer.
> *Reference-Based* compares to a known-correct answer. *Pairwise* picks a
> winner between two responses, with **swap-and-aggregate** to cancel
> position bias. The judge is itself an LLM — by default GPT-4o.

### 12.1  Why LLM-as-Judge?

Human evaluation does not scale. Programmatic evaluation (regex, exact
match) only works for tightly-constrained answers. The middle ground is to
have an LLM evaluate the response. A 2024 survey (arXiv:2412.05579) found
LLM judges agree with human raters about as often as humans agree with each
other on most tasks — making LLM-as-Judge methodologically defensible for
benchmark studies.

### 12.2  The Three Judge Patterns

| Pattern | Inputs | Output | Use case |
|---------|--------|--------|----------|
| Referenceless (G-Eval) | prompt, response | score 0–1 + reasoning | open-ended, no gold answer |
| Reference-Based | prompt, response, **reference** | score 0–1 + reasoning | factual, gold known |
| Pairwise | prompt, **two** responses | winner: A / B / tie | leaderboard / ELO |

### 12.3  Referenceless Prompt (the actual one)

```
You are an expert evaluator. Evaluate the following AI response on a scale
from 0.0 to 1.0 where 1.0 is perfect.

**Original question:**
<prompt>

**AI Response:**
<response>

Evaluate for: accuracy, completeness, clarity, and helpfulness.

Respond ONLY with a valid JSON object in this exact format:
{ "score": <float 0.0-1.0>, "reasoning": "<one-paragraph explanation>" }
```

### 12.4  Reference-Based Prompt

Same idea but the judge sees the gold answer and is asked to rate similarity:

```
**Question:** <prompt>
**Reference Answer:** <gold>
**AI Response:** <response>

Score from 0.0 (wrong) to 1.0 (perfectly correct).
{"score": ..., "reasoning": ...}
```

### 12.5  Pairwise — The Position-Bias Trick

LLM judges have a documented preference for the **first** response shown.
OmniLLM cancels this by running the comparison twice with positions swapped:

```python
async def evaluate_pairwise(self, task, model_a, model_b):
    resp_a, resp_b = await asyncio.gather(
        self.gateway.query(model_a, messages),
        self.gateway.query(model_b, messages),
    )
    w1, _ = await self._judge_pairwise(task, resp_a, resp_b, swap=False)
    w2, _ = await self._judge_pairwise(task, resp_a, resp_b, swap=True)
    final = w1 if w1 == w2 else "tie"
    return PairwiseResult(...)
```

If both runs agree, that's the winner. If they disagree, the comparison is
declared a **tie** — the position bias was the deciding factor, so neither
response is reliably better.

### 12.6  The Programmatic Escape Hatch

For tasks with a deterministic correctness check (e.g. "does this response
parse as JSON with the right schema?"), you can bypass the judge entirely
by setting `task.grading_fn`:

```python
EvalTask(
    id="cost-yes-no",
    prompt="Is Python interpreted? Answer only Yes or No.",
    reference_answer="Yes",
    grading_fn=lambda r: 1.0 if "yes" in r.strip().lower()[:10] else 0.0,
    judge_pattern="referenceless",  # ignored when grading_fn is set
)
```

`grading_fn` takes priority over the judge.

### 12.7  Running a Full Benchmark

The evaluator concurrent-runs the full task × model matrix:

```python
async def run_benchmark(self, tasks, model_ids, max_concurrent=5):
    semaphore = asyncio.Semaphore(max_concurrent)
    async def _limited(task, model_id):
        async with semaphore:
            return await self.evaluate_task(task, model_id)
    coros = [_limited(t, m) for t in tasks for m in model_ids]
    return list(await asyncio.gather(*coros))
```

The semaphore caps simultaneous calls so you don't trigger rate limits.

\newpage

## Chapter 13 — `scorer.py` — The ELO Leaderboard

> **⚡ AT A GLANCE.** Implements chess-style ELO ratings. Every pairwise
> match updates two ratings. K-factor 32, default 1500. Supports per-category
> leaderboards, rating history, and JSON save/load. Same methodology as
> LMSYS Chatbot Arena.

### 13.1  The ELO Formula

For two players with ratings $R_a$ and $R_b$, the **expected score** for A is:

$$ E_a = \frac{1}{1 + 10^{(R_b - R_a) / 400}} $$

After a match where the actual score for A is $S_a \in \{0, 0.5, 1\}$ (loss /
tie / win), the new rating is:

$$ R_a' = R_a + K \cdot (S_a - E_a) $$

K is the volatility constant (32 in OmniLLM). Higher K = ratings move
faster but are noisier. 100 ELO points ≈ 64% expected win rate.

### 13.2  Why ELO and Not Plain Win-Rate?

Plain win-rate has a flaw: beating a strong opponent is worth the same as
beating a weak one. ELO rewards strength of opposition. After enough
matches, ELO converges to a stable relative ranking even if matches are
not uniformly distributed.

### 13.3  Implementation Walk-Through

```python
class EloScorer:
    def __init__(self, k_factor=32, default_rating=1500):
        self.k_factor       = k_factor
        self.default_rating = default_rating
        self.ratings:        dict[str, float] = {}
        self.matches_played: dict[str, int]   = {}
        self._history:       list[_MatchRecord] = []
        self._rating_history:    dict[str, list[(str, float)]] = {}
        self._category_ratings:  dict[str, dict[str, float]]    = {}

    def expected_score(self, ra, rb):
        return 1.0 / (1.0 + math.pow(10, (rb - ra) / 400.0))

    def record_match(self, model_a, model_b, winner, category="general"):
        # Initialise ratings if first match
        for m in (model_a, model_b):
            self.ratings.setdefault(m, self.default_rating)
            self.matches_played.setdefault(m, 0)

        ra_before = self.ratings[model_a]
        rb_before = self.ratings[model_b]
        ra_after, rb_after = self._update_ratings(ra_before, rb_before, winner)

        # Update overall + category + history
        self.ratings[model_a] = ra_after
        self.ratings[model_b] = rb_after
        self.matches_played[model_a] += 1
        self.matches_played[model_b] += 1
        # ... category and history bookkeeping ...
```

### 13.4  Per-Category Leaderboards

Each match is also tracked under a category (e.g. `"reasoning"` or
`"embodied_hri"`). Per-category ratings start fresh at 1500 and converge
independently.

```python
scorer.record_match("gpt-4o", "claude-sonnet", "model_a", category="reasoning")
scorer.record_match("gpt-4o", "claude-sonnet", "model_b", category="code")

scorer.get_leaderboard()                          # overall
scorer.get_category_leaderboard("reasoning")      # only reasoning matches
scorer.get_category_leaderboard("embodied_hri")   # only HRI matches
```

For the Embodied LLM Arena, every pairwise participant preference produces
a match in `category="embodied_hri"`, building the *Embodied LLM Leaderboard*.

\newpage

## Chapter 14 — `cli.py` — Your Terminal Dashboard

> **⚡ AT A GLANCE.** A Click CLI with 10 commands and Rich-formatted output.
> Lets you talk to every layer of OmniLLM from the terminal: list models,
> ask one or many models, run benchmarks, compare two models, run the LLM
> Council, demo the smart router, see the ELO leaderboard, see costs, and
> export results. Loaded as the `omnillm` shell command after install.

### 14.1  The Command Map

| Command | What it does | Most-used flags |
|---------|--------------|-----------------|
| `omnillm models` | List registered models | `--type cloud|local` |
| `omnillm ask "<prompt>"` | Send to one or many models | `--all`, `-m id` |
| `omnillm evaluate` | Run benchmark on tasks × models | `-m`, `-c`, `-o` |
| `omnillm compare "<prompt>"` | Pairwise judge | `--model-a`, `--model-b` |
| `omnillm council "<prompt>"` | LLM Council | `--strategy`, `-m` |
| `omnillm route "<prompt>"` | Show routing decision | `--budget`, `--strategy` |
| `omnillm leaderboard` | ELO rankings | `--category` |
| `omnillm costs` | USD spend per model | `--data-file` |
| `omnillm export` | CSV / JSON / Markdown | `--format`, `--input`, `-o` |

### 14.2  How Click + Rich Work Together

Click handles **argument parsing and validation**. Rich handles **output
formatting**. Each command is a function decorated with `@cli.command(...)`
that builds a `rich.Table` or `rich.Panel` and prints it.

```python
@cli.command("models")
@click.option("--config", "-c", default=None)
@click.option("--type", "model_type", default=None,
              type=click.Choice(["cloud", "local"]))
def models_cmd(config, model_type):
    gateway = _get_gateway(config)
    table = Table(title="Registered LLM Models", header_style="bold cyan")
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Type", style="magenta")
    # ...
    for model_id in gateway.list_models():
        info = gateway.get_model_info(model_id)
        if model_type and info.get("type") != model_type:
            continue
        table.add_row(model_id, info["type"], info["provider"], ...)
    console.print(table)
```

### 14.3  Async-from-Sync Pattern

Click runs synchronously but our gateway is async. Each command wraps the
async work in a local helper:

```python
async def _run():
    return await gateway.query_multiple(model_ids, messages)
responses = asyncio.run(_run())
```

`asyncio.run()` creates a fresh event loop, runs the coroutine, and closes
the loop. This is the safe way to call async code from a sync entry point.

### 14.4  Beautiful Output Tricks

A few Rich tricks worth knowing:

- **Coloured score column**: green ≥ 0.8, yellow ≥ 0.5, red otherwise.
- **Progress spinner**: `Progress(SpinnerColumn(), TextColumn("…"))` for
  multi-second waits.
- **Panels**: `Panel(content, title=..., border_style="cyan")` for boxed
  responses.
- **Medals**: `🥇 🥈 🥉` for the top 3 leaderboard rows.

\newpage
