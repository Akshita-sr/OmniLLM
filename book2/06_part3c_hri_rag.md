\newpage

## Chapter 12 — HRI & RAG Modules

> *The five files in this chapter are the ones that transform OmniLLM from "a benchmarking framework" into "Pepper's brain." Every file is small (under 700 lines), every file does one thing, and they compose into the 9-node LangGraph pipeline that drives every interaction.*

\newpage

### 12.1 `omnillm/hri/agent_graph.py` — The Brain of Pepper

#### At a Glance

`agent_graph.py` is the **single most important file in the project**. The `build_hri_graph(gateway, rag, logger, default_model)` function returns a compiled LangGraph `CompiledGraph` that accepts a state dict, runs it through 9 nodes, and returns the updated dict containing the `robot_action` JSON. Every interaction with Pepper — voice, touch, or typed — flows through exactly one invocation of `graph.ainvoke(state)`.

The graph has three layers of complexity:

1. **The node functions** (one async function per node, ~30 lines each). These are the *what happens at each step*.
2. **The state wrapping** — a `_merge_state(fn)` closure that wraps every node so its return value *merges* with the existing state instead of *replacing* it. This is a single line of code that fixes a class of bugs we will discuss below.
3. **The graph wiring** — `builder.add_node()` and `builder.add_edge()` calls that connect the nodes, plus one `builder.add_conditional_edges()` that branches on task type.

#### The Nine Nodes

| # | Node | What it computes | Output fields added to state |
|---|---|---|---|
| 1 | `transcribe_audio` | If `audio_bytes` is non-empty, calls `WhisperSTT.transcribe()`. Otherwise pass-through (text mode). Sets `_start_time` for end-to-end latency measurement. | `utterance`, `_start_time` |
| 2 | `detect_language` | Calls `LanguageDetector.detect(utterance)`. Returns the ISO 639-1 code. | `detected_language` |
| 3 | `classify_task` | Calls `HRITaskClassifier.classify(utterance, language)`. Rule-based by default. | `task_type`, `task_confidence` |
| 4 | (conditional edge) | Branches on `(task_type, condition, rag_enabled)`. T1→`rag`, T2→`nav_rag`, T3→`direct_llm`, T4→`multilingual_llm`. Cond E always → `direct_llm`. | — |
| 5a | `rag` (T1) | `RAGPipeline.query(utterance, model_id=…)`. Retrieves k=4 chunks; generates answer with `model_id`. | `rag_context`, `rag_chunks`, `rag_faithfulness`, `response_text`, `model_id`, `latency_ms` |
| 5b | `nav_rag` (T2) | Same as `rag` + `GesturePlanner.plan("navigation", answer)`. | All of `rag` + `gesture`, `led_color` |
| 5c | `direct_llm` (T3) | Direct gateway call with social system prompt. Adds gesture via planner. | `response_text`, `model_id`, tokens, cost, latency, gesture, led_color |
| 5d | `multilingual_llm` (T4) | Tries language-optimal model (Claude Haiku for non-English) first; falls back to GPT-4o-mini on error. | Same as `direct_llm` |
| 6 | `smart_router` | Cond C: re-routes the LLM call via `SmartRouter.route_for_hri_task()`. Cond D: fires the 3-model consensus. Other conditions: pass-through. | Possibly overwrites `response_text`, `model_id` |
| 7 | `generate_action_plan` | Assembles the final `RobotAction` JSON. If no gesture set yet, calls the planner. | `robot_action`, `gesture`, `led_color` |
| 8 | `log_interaction` | Computes end-to-end latency from `_start_time`. Calls `ExperimentLogger.log_interaction()`. | `latency_ms` (end-to-end) |

#### The `_merge_state` Wrapper — A 5-Line Fix to a Whole Class of Bugs

LangGraph 1.x's `StateGraph(dict)` has an important behaviour: **each node's return value REPLACES the state, it does not merge.** So if node 1 sets `state["utterance"] = "Hi"` and node 2 returns `{"detected_language": "en"}`, after node 2 the state contains *only* `{"detected_language": "en"}` — `utterance` is gone.

This caused the empty-speech bug that first surfaced during the May 2026 pilot's first P000 run. The symptom: Pepper's `robot_action.speech` field was empty. The cause: the LLM nodes were returning `{"response_text": "..."}` which replaced (not merged into) the state, and the downstream `generate_action_plan` node looked for `response_text` but found only the LLM node's narrow output.

The fix is six lines:

```python
def _merge_state(fn):
    async def wrapped(state):
        delta = await fn(state)
        if not isinstance(delta, dict):
            return state
        return {**state, **delta}
    return wrapped
```

Every node is registered via `builder.add_node("name", _merge_state(node_fn))`. The wrapper takes the node's return value and merges it into the existing state, so prior fields survive. This is the kind of fix that takes 30 seconds to write and four hours to find. **(Beginner)** **lesson:** when the framework you depend on has subtle semantics, *write a thin adapter once* rather than fighting the semantics at every node.

#### The Conditional Edge — Where the Four Task Types Diverge

```python
def _route_by_task_type(state):
    task_type = state.get("task_type", "info_retrieval")
    condition = state.get("condition", "A")
    rag_enabled = state.get("rag_enabled", True)
    if condition == "E":              # RAG-off control always goes direct
        return "direct_llm"
    routing = {
        "info_retrieval":      "rag"        if rag_enabled else "direct_llm",
        "navigation":          "nav_rag"    if rag_enabled else "direct_llm",
        "social_conversation": "direct_llm",
        "multilingual":        "multilingual_llm",
    }
    return routing.get(task_type, "direct_llm")
```

Two important details:

1. **Condition E short-circuits.** Even if the classifier says "this is an info_retrieval question that would benefit from RAG", Condition E refuses to call the RAG pipeline and goes straight to the LLM. This is what makes E the clean RAG-off control for hypothesis H3.
2. **The `rag_enabled` flag respected.** If the caller passes `rag_enabled=False` and the task is T1 or T2, the graph falls back to direct LLM. This is mostly used for testing: it lets you run the pipeline with no knowledge base indexed.

#### How Condition Resolution Happens *Before* the Graph

This is the most subtle fix in the May 2026 upgrade. Look at `omnillm/server/app.py:255–278`:

```python
# Resolve the per-condition model BEFORE invoking the graph so
# that Condition B (fixed local Llama) actually exercises the
# local Ollama backend rather than silently falling through to
# the server's default cloud model.
from omnillm.hri.experiment import CONDITION_CONFIGS, ExperimentCondition
try:
    cond_enum = ExperimentCondition(condition)
    cond_cfg = CONDITION_CONFIGS.get(cond_enum)
    effective_model = (
        cond_cfg.model_id if cond_cfg and cond_cfg.model_id
        else _default_model
    )
except ValueError:
    effective_model = _default_model

state["model_id"] = effective_model
```

The server *reads* the requested condition from the POST body, looks up the canonical model ID for that condition in `experiment.py`, and *injects* it into the state dict before calling `graph.ainvoke(state)`. The RAG and direct-LLM nodes then honour the `model_id` field they find in the state, passing it through to `gateway.query()`.

Before this fix, Condition B silently ran Condition A's model (GPT-4o-mini) because the RAG pipeline used its constructor-time `self.model_id`, which was always the server's default. The fix routes the per-condition model id explicitly through the state. Condition B now actually runs Llama via Ollama; the leaderboard rankings are no longer artefacts of all conditions using GPT-4o-mini under the hood.

(!) **If you ever add a new condition, you must update both `experiment.py: CONDITION_CONFIGS` AND make sure your new condition's `model_id` is honoured by the relevant LLM node.** The smart_router node (`_make_smart_router_node`) is where the routing happens for Conditions C and D; the per-condition-model handling for A, B, E happens in the upstream `rag`, `nav_rag`, `direct_llm`, and `multilingual_llm` nodes via their `model_id=state.get("model_id") or default` lookup.

#### The Multilingual Retry Logic

The T4 (multilingual) node has a built-in retry. Look at `_make_multilingual_llm_node`:

```python
for model in (target_model, backup_model):
    if model in models_tried:
        continue
    models_tried.append(model)
    try:
        resp = await gateway.query(model, messages, temperature=0.7)
    except Exception as exc:
        last_error = f"{model}: {exc}"
        resp = None
        continue
    if not resp.is_error:
        break
    last_error = f"{model}: {resp.error}"
    resp = None
```

If the primary multilingual model (Claude Haiku) returns an error, the node retries with `openai-gpt4o-mini` while *preserving the multilingual system prompt*. This is important: the previous fallback path (in `app.py`'s `_fallback_interact` function) would silently switch to the English-only generic system prompt, which produced English replies to French input. The new retry preserves the T4 treatment so Condition C's multilingual handling remains a real T4 condition even on transient provider failure.

\newpage

### 12.2 `omnillm/hri/classifier.py` — The Task Classifier (T1–T4)

#### At a Glance

`HRITaskClassifier.classify(utterance, detected_language)` returns a `ClassificationResult(task_type, confidence, reasoning, detected_language, method)`. By default it uses a rule-based scorer (~30 ms, no LLM call). An optional `classify_with_llm()` method delegates to GPT-4o-mini for ambiguous cases (~700 ms).

#### Why Rule-Based by Default?

Three reasons:

1. **Latency.** A rule-based classifier returns in milliseconds; an LLM classifier adds ~700ms to every interaction. In an HRI pipeline that wants ≤ 4s end-to-end, every 700ms counts.
2. **Cost.** Zero per-query cost. Over 20 × 15 = 300 interactions in the study, an LLM classifier would cost an extra ~$0.50 — small in absolute terms, but unnecessary.
3. **Predictability.** The rule-based scoring is deterministic, easy to test, and easy to debug. When the pilot saw a misclassification, the author could inspect the keyword-and-pattern table directly. An LLM classifier would have been a black box.

#### How the Scoring Works

For each task type, the classifier maintains a frozenset of single-word keywords and a list of compiled regex patterns. For an utterance like *"Where is Room 305?"*:

```python
words = {"where", "is", "room", "305"}
nav_score    = score("navigation", words, _NAVIGATION_KEYWORDS, _NAVIGATION_PATTERNS)
social_score = score("social", words, _SOCIAL_KEYWORDS, _SOCIAL_PATTERNS)
info_score   = score("info", words, _INFO_RETRIEVAL_KEYWORDS, _INFO_RETRIEVAL_PATTERNS)
```

The `_score_category()` function adds:

- `0.1 × num_keyword_hits` (capped at 0.3)
- `0.15 × num_multi-word-phrase_hits`
- `0.25 × num_regex_pattern_matches`

For *"Where is Room 305?"*:
- `nav_score`: hits `where`, `room`, plus the pattern `\b(where (is|are)|...)\b` → 0.2 + 0.25 = 0.45
- `social_score`: 0
- `info_score`: tiny match on `what is the` pattern → 0.05

`max(scores)` picks `navigation` with confidence `min(0.95, 0.5 + 0.45 * 0.9) ≈ 0.91`.

#### Multilingual Always Wins

If `detected_language != "en"`, the classifier returns `MULTILINGUAL` with confidence 0.99 *immediately* — before any keyword scoring. This is the right behaviour because the rule keywords are English-only; running them on Italian or Chinese would produce nonsense scores. The downstream graph routing handles multilingual queries specifically (it has access to the language code and can pick a multilingual-strong LLM).

#### Why No Fine-Tuned Classifier?

The author considered training a small classifier (e.g. DistilBERT fine-tuned on labelled HRI utterances). Decided against it because:

1. **No labelled data.** We do not have a labelled corpus of "T1 / T2 / T3 / T4" HRI utterances at the scale required for fine-tuning.
2. **Distribution shift.** Even if we labelled 1,000 utterances from one lab, a different lab's prompts would distribute differently.
3. **The rule-based version is good enough.** The May 2026 pilot showed 100% correct classification on the 20 test prompts. The cost of training and maintaining a fine-tuned model is not justified by an improvement we cannot measure.

If a future deployment hits real ambiguity, swapping to `classify_with_llm` is a one-line change inside the agent graph's `_make_classify_task_node`.

\newpage

### 12.3 `omnillm/hri/language_detector.py` — How French Becomes "fr"

#### At a Glance

`LanguageDetector.detect(text)` returns a `LanguageDetectionResult(language, confidence, script, is_english, language_code, language_name, recommended_model)`. Detection is **rule-based first, library-based second** — this avoids a hard dependency on `langdetect` (which is heavier).

#### Three-Tier Detection

1. **Unicode script analysis** — fastest, works on zero-token inputs. *"こんにちは"* contains Hiragana → `ja`. *"مرحبا"* contains Arabic script → `ar`. *"привет"* contains Cyrillic → `ru`. Confidence: 0.85–0.97.
2. **Word-level n-gram signals** — for Latin-script languages where script is ambiguous. The detector has hand-picked high-frequency function-word lists for FR, DE, ES, IT, PT, NL. *"Bonjour, comment allez-vous?"* hits `bonjour`, `vous` → `fr`. Confidence: 0.6–0.9.
3. **`langdetect` fallback** — only invoked when the first two tiers fail to find anything stronger than English. Heavy but accurate. Ships as an optional `[hri]` extra.

#### Why Word-Boundary Matching, Not Substring Matching

A subtle but important bug fixed in the May 2026 upgrade. The original code did `if signal_word in text.lower(): score += 1`. That matches **anywhere** inside the text, so the Spanish function word `la` matches `lab`, `de` matches `does`, `en` matches `open`. The fix uses **tokenised word-boundary matching**: `words = set(re.findall(r"\b\w+\b", text.lower()))` and `signal_word in words`. A two-letter function word now only counts as a hit if it appears as a standalone token.

This is the kind of bug that shipped silently for months — it didn't crash anything; it just routed `"What time does the lab open?"` to Spanish because the substring match found `la`, `de`, `en` and counted them as Spanish function words. Caught only when the pilot's T1 prompts started occasionally getting Spanish answers.

#### The Language → Model Map

```python
_LANGUAGE_MODEL_MAP = {
    "en": "openai-gpt4o-mini",
    "fr": "claude-haiku",
    "de": "claude-haiku",
    ...
    "unknown": "claude-haiku",
}
```

As discussed: Claude Haiku is the default multilingual choice as of 2026-05-20 because it has wide language coverage *and* is not subject to the Google free-tier quota that knocked Gemini Flash offline mid-pilot. The map can be overridden per-instance:

```python
detector = LanguageDetector(custom_model_map={"it": "openai-gpt4o"})
```

#### The Compatibility Properties

The class has three deliberately redundant properties:

```python
@property
def language_code(self) -> str: return self.language
@property
def language_name(self) -> str: return _LANGUAGE_NAME_MAP[self.language]
@property
def recommended_model(self) -> str: return _LANGUAGE_MODEL_MAP[self.language]
```

These were added in the May 2026 upgrade because the multilingual node in `agent_graph.py` was calling `lang_result.recommended_model` and `lang_result.language_name`. Before adding the properties, those attribute accesses raised `AttributeError`, the multilingual node fell into its catch-all `except`, and Pepper produced empty speech. Five trivial properties later, T4 works.

\newpage

### 12.4 `omnillm/hri/experiment.py` — Conditions A–E, Participant Sessions

#### At a Glance

`experiment.py` is short (~280 lines) but central. It defines:

| Construct | Purpose |
|---|---|
| `ExperimentCondition` (enum) | The five conditions A–E |
| `ConditionConfig` (dataclass) | Per-condition: model_id, RAG on/off, consensus flag, smart_routing flag, council_models list, human-readable description |
| `CONDITION_CONFIGS` (dict) | The mapping `ExperimentCondition → ConditionConfig`. **This is the source of truth for how each condition is realised.** |
| `ParticipantSession` (dataclass) | A single participant's session: participant_id, session_id (UUID), conditions_assigned, start_time, end_time, observation_notes |
| `ExperimentManager` | Constructor and lifecycle management for sessions. `create_session(participant_id, conditions=None)` returns a new `ParticipantSession`. |

#### Why a Dataclass-Centric Design?

(Beginner) **A dataclass** is a Python class auto-generated by the `@dataclass` decorator that gives you `__init__`, `__repr__`, `__eq__`, and field defaults for free. Use them for "named tuples that need methods." The author uses dataclasses everywhere in OmniLLM (`ModelResponse`, `RobotAction`, `InteractionRecord`, `ConditionConfig`, etc.) because the alternative — hand-written classes — would be 5× more code with no benefit.

#### How Conditions Map to Code Paths

```python
CONDITION_CONFIGS = {
    ExperimentCondition.A: ConditionConfig(
        condition=A,
        model_id="openai-gpt4o-mini",
        rag_enabled=True,
        description="Fixed cloud LLM (GPT-4o-mini) with RAG — baseline"),

    ExperimentCondition.B: ConditionConfig(
        condition=B,
        model_id="llama3-8b-local",
        rag_enabled=True,
        description="Fixed local LLM (Llama3:8b via Ollama) with RAG"),

    ExperimentCondition.C: ConditionConfig(
        condition=C,
        model_id=None,                     # routed
        rag_enabled=True,
        use_smart_routing=True,
        description="Smart-routed — OmniLLM selects best model per task type"),

    ExperimentCondition.D: ConditionConfig(
        condition=D,
        model_id=None,                     # councilled
        rag_enabled=True,
        use_consensus=True,
        council_models=["openai-gpt4o-mini", "claude-haiku", "gemini-flash"],
        description="Consensus council — 3 models, best answer synthesised"),

    ExperimentCondition.E: ConditionConfig(
        condition=E,
        model_id="openai-gpt4o-mini",
        rag_enabled=False,                 # the only RAG-off
        description="RAG-off control — GPT-4o-mini without knowledge retrieval"),
}
```

The agent graph's smart-router node reads `cond_cfg.use_consensus` and `cond_cfg.use_smart_routing` to decide whether to fire the consensus engine or call the smart router. Conditions A, B, E pass through unchanged (`use_consensus=False, use_smart_routing=False`).

#### Counterbalancing — Where the Order Lives

The `run_subject_experiment.py` driver hard-codes a Latin-square-ish ordering at the top of the file:

```python
ORDER = [
    ("A", "T1"), ("A", "T2"), ("A", "T3"), ("A", "T4"),
    ("B", "T2"), ("B", "T3"), ("B", "T4"), ("B", "T1"),
    ("C", "T3"), ("C", "T4"), ("C", "T1"), ("C", "T2"),
    ("D", "T4"), ("D", "T1"), ("D", "T2"), ("D", "T3"),
    ("E", "T1"), ("E", "T2"), ("E", "T3"), ("E", "T4"),
]
```

Each condition starts at a different task — so task-order effects are partly cancelled within the participant.

For the full N=15 study, we additionally need to **rotate the condition order across participants** so that not every participant sees A first. The recommended assignment is a **5×5 Latin square over the condition order**:

| Participant | Cond 1 | Cond 2 | Cond 3 | Cond 4 | Cond 5 |
|---|---|---|---|---|---|
| P001 | A | B | C | D | E |
| P002 | B | C | D | E | A |
| P003 | C | D | E | A | B |
| P004 | D | E | A | B | C |
| P005 | E | A | B | C | D |
| P006 | A | C | E | B | D |
| P007 | B | D | A | C | E |
| P008 | C | E | B | D | A |
| P009 | D | A | C | E | B |
| P010 | E | B | D | A | C |
| P011 | A | D | B | E | C |
| P012 | B | E | C | A | D |
| P013 | C | A | D | B | E |
| P014 | D | B | E | C | A |
| P015 | E | C | A | D | B |

Within each condition the task order is the Latin-square-ish ordering above. The two squares together produce a balanced design: each condition appears in each of positions 1–5 exactly 3 times across the 15 participants. For replicating, see Chapter 25 for the detailed counterbalancing argument.

\newpage

### 12.5 `omnillm/rag/pipeline.py` — Retrieval-Augmented Generation

#### At a Glance

`RAGPipeline` does five things:

1. Indexes documents (TXT / CSV / PDF) from a directory into ChromaDB.
2. Retrieves top-k chunks for a query using ChromaDB's cosine similarity over sentence-transformer embeddings.
3. Falls back to a pure-Python keyword search if ChromaDB is unavailable (no graceful degradation gap).
4. Generates an answer via the LLM gateway with the retrieved chunks injected as context.
5. (Optional) Scores faithfulness with LLM-as-judge and runs a lightweight hallucination heuristic.

#### The Indexing Pipeline

`rag.index_directory("knowledge_base/")` walks the directory and dispatches per file extension:

- `.txt` → split into ~512-character chunks with 64-character overlap (`_split_text`), embed, index.
- `.csv` → one chunk per row, with `key: value | key: value | ...` formatting.
- `.pdf` → uses `pypdf` to extract text per page, then chunked like txt.

The chunk-size choice (512 chars, ~125 tokens) was based on three considerations:

1. **Embedding model context window.** Sentence-transformer `all-MiniLM-L6-v2` accepts up to 256 word-pieces; 512 chars is roughly 100–130 tokens — safely under the limit.
2. **Retrieval granularity.** Larger chunks (~2000 chars) retrieve more context but dilute the relevance score; smaller chunks (~100 chars) are too granular to be useful as standalone facts.
3. **Pepper's spoken-response window.** A response should be 2–4 sentences (~250 chars). Retrieved chunks of 512 chars give the LLM enough room to compose a faithful answer without padding.

#### The Retrieval Step

```python
def retrieve(self, query: str) -> list[DocumentChunk]:
    if self._collection is not None:
        return self._retrieve_chromadb(query)
    return self._retrieve_keyword(query)
```

If ChromaDB is alive, `_retrieve_chromadb` runs a semantic similarity search and returns up to `top_k=4` chunks ranked by cosine similarity. Each chunk carries `similarity_score` in [0, 1].

If ChromaDB is dead (the SQLite file is locked, the embedding model failed to load), `_retrieve_keyword` scores each in-memory chunk by overlap with the query's tokens. This is the **graceful degradation** path: faithfulness drops, but the pipeline doesn't crash.

#### The Per-Call `model_id` Override

The May 2026 upgrade added a `model_id=` parameter to `query()`:

```python
async def query(
    self,
    question: str,
    system_prompt: str | None = None,
    score_faithfulness: bool = False,
    model_id: str | None = None,
) -> RAGResponse:
    ...
    effective_model = model_id or self.model_id
    llm_response = await self.gateway.query(effective_model, messages)
```

Without this, the RAG pipeline always used `self.model_id` (the model passed at construction — typically GPT-4o-mini). The agent graph's RAG node now passes `model_id=state.get("model_id")`, which carries the per-condition model. This is what makes Condition B's "Llama via Ollama with RAG" actually run Llama via Ollama at the answer-generation step.

#### Faithfulness Scoring

When `score_faithfulness=True`, the pipeline asks the judge LLM:

> *"You are a factuality judge. Score how faithfully the answer uses ONLY information from the given context (0.0 = completely hallucinated, 1.0 = every claim is supported by the context).*
>
> *Context: [retrieved chunks]*
>
> *Question: …*
>
> *Answer: …*
>
> *Respond ONLY with valid JSON: {"score": <float 0.0-1.0>, "reasoning": "<brief>"}"*

The score is a continuous 0–1. We additionally run a cheap heuristic: if fewer than 20% of the answer's significant words (≥5 chars) appear in the retrieved chunks, set `hallucination_detected=True`. The heuristic occasionally false-positives on paraphrased answers and false-negatives on plausible-sounding fabrications, so the LLM-as-judge `faithfulness_score` is the canonical metric.

#### The DIBRIS Knowledge Base — Current Contents (May 2026)

| File | Purpose | Indexed chunks |
|---|---|---|
| `lab_info.txt` | DIBRIS lab description, hours, location, contact | ~12 |
| `faq.txt` | Common visitor questions ("Where is the bathroom?", "What is the wifi password?", etc.) | ~15 |
| `research_projects.txt` | Active research lines and recent papers | ~10 |
| `university_map.txt` | DIBRIS floor map, room locations, transit directions | ~8 |
| `event_schedule.csv` | Upcoming lab events | ~3 rows = 3 chunks |
| `visitor_profiles.csv` | Typical visitor categories | ~3 rows = 3 chunks |
| **Total** | — | **~49** chunks |

This is small for a ChromaDB collection (production RAG systems typically index 10k–100k chunks). The trade-off is intentional: a small, hand-curated knowledge base means the RAG faithfulness experiments measure *retrieval quality on a known corpus*, not "scaling RAG to a corporate document set." The methodology is transferable; the corpus size is bounded by what we can verify by hand.

The previous IRAI-Lab content (used in the first edition of the book) is preserved under `knowledge_base/_legacy_irai/` for reference. The two corpora can be swapped by setting `OMNILLM_KNOWLEDGE_BASE` to the desired directory:

```powershell
$env:OMNILLM_KNOWLEDGE_BASE = "C:\Users\akshi\OneDrive\Desktop\OmniLLM\knowledge_base\_legacy_irai"
python -m omnillm.server.app
```

#### Academic Context

The RAG architecture follows the canonical "retrieve-then-generate" pattern (Lewis et al. 2020, Karpukhin et al. 2020). The chunk-size and overlap choices are conservative defaults from LangChain's `RecursiveCharacterTextSplitter`. The faithfulness scoring is closest in spirit to RAGAS (Es et al. 2023) — same judge-LLM-with-context pattern, simpler implementation. The hallucination heuristic is intentionally crude; production systems use stronger entailment models (e.g. ALBERT-based natural-language-inference), which we considered out of scope for a deployment of this size.

\newpage
