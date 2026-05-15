\newpage

# Appendix G — End-to-End Flow Diagram (Spoken Question to Robot Action)

This appendix consolidates everything in the book into a single annotated
diagram. Use it as a poster. The flow shows what happens when a person
speaks to Pepper, from the audio captured by the microphone to the speech,
gesture and LED change that the robot produces in reply — including how the
Smart Router, the Consensus Council, the LLM-as-Judge and the ELO leaderboard
all plug in.

## G.1  Stage 0 — Person Speaks to Pepper

```
Person  ── speaks ──▶  Pepper microphone  (NAOqi, Python 2.7)
                            │
                            │  POST /interact
                            │  {
                            │    "audio": "<base64 WAV>",
                            │    "text"?: "...",
                            │    "participant_id": "P001",
                            │    "session_id": "...",
                            │    "condition": "A|B|C|D|E",
                            │    "rag_enabled": true
                            │  }
                            ▼
   ┌────────────────────────────────────────────────────────────┐
   │  omnillm/server/app.py   ← Flask AI server (Python 3.x)    │
   │  create_app() / @app.post("/interact")                     │
   │  Hands the request to the LangGraph pipeline.              │
   └────────────────────────────────────────────────────────────┘
                            │
                            ▼
```

## G.2  Stage 1 — LangGraph Pipeline `omnillm/hri/agent_graph.py`

The graph is compiled by `build_hri_graph()`. Each box below is one node;
each node is an `async` function that reads state and returns state updates.

```
  [transcribe_audio]   ──▶  omnillm/robotics/whisper_stt.py  (WhisperSTT)
        │                    audio bytes → utterance (text)
        ▼
  [detect_language]    ──▶  omnillm/hri/language_detector.py
        │                    utterance → ISO code "en"/"fr"/...
        ▼
  [classify_task]      ──▶  omnillm/hri/classifier.py  (HRITaskClassifier)
        │                    Returns one of:
        │                       T1 info_retrieval
        │                       T2 navigation
        │                       T3 social_conversation
        │                       T4 multilingual
        │
        ▼  (conditional edges, function _route_by_task_type)
        │
   ┌────┼─────────────┬────────────────┬─────────────────┐
   ▼ T1 │          T2 ▼             T3 ▼              T4 ▼
  [rag]            [nav_rag]       [direct_llm]   [multilingual_llm]
  rag/pipeline.py  rag/pipeline.py gateway.query   gateway.query
  RAGPipeline.query +gesture_plan  (LiteLLM call)  (lang-optimal model)
   │                │               │                │
   └────────┬───────┴───────────────┴────────────────┘
            ▼
      [smart_router]   ← only acts for conditions C and D
      ┌──────────────────────────────────────────────────────────────┐
      │  condition == "C"  ──▶ omnillm/router.py    SmartRouter     │
      │     route_for_hri_task(task_type)                            │
      │     strategy = TASK_TYPE                                     │
      │     Picks ONE best model from config/models.yaml             │
      │     Then gateway.query(model, ...)                           │
      │                                                              │
      │  condition == "D"  ──▶ omnillm/consensus.py ConsensusEngine  │
      │     Council = [gpt-4o-mini, gemini-2.5-flash, claude-haiku]  │
      │     gateway.query_multiple(...)   (parallel fan-out)         │
      │     strategy = "synthesis"  (default)                        │
      └──────────────────────────────────────────────────────────────┘
            │
            ▼
      [generate_action_plan]  ── omnillm/robotics/gesture_planner.py
            │                    Builds RobotAction dict:
            │                    { speech, gesture, emotion_led, metadata }
            ▼
      [log_interaction]      ── omnillm/utils/experiment_logger.py
            │                    Writes JSONL row
            │                    (latency, tokens, $, judge_score)
            ▼
          [END] ── HTTP 200 RobotAction JSON ──▶ Pepper
                                                 executes speech + gesture + LED
```

## G.3  Stage 2 — Smart Routing `omnillm/router.py :: SmartRouter`

```
  Inputs: task_category, budget_usd?, max_latency_ms?, strategy
  Config: config/models.yaml
          (cost_per_1m_input/output, latency, hri_strengths)
  Memory: past EvalResults loaded via _load_results()
          → quality / latency table

         ┌─────────  candidates = all models  ────────┐
         │  filter by budget_usd cap                  │
         │  filter by max_latency_ms cap              │
         │  if empty → routing.fallback_models        │
         └────────────────────┬───────────────────────┘
                              ▼
              ┌──────────  pick strategy  ──────────┐
              │ BEST_QUALITY    → max quality       │
              │ LOWEST_COST     → min $/query       │
              │ LOWEST_LATENCY  → min ms            │
              │ BEST_VALUE      → 0.5·Q + 0.3·C̃ + 0.2·L̃ (composite)
              │ LOCAL_PREFERRED → local-only first  │
              │ TASK_TYPE       → hri_task_routing[task]  (used by Pepper)
              └──────────────────┬──────────────────┘
                                 ▼
                  RouteDecision{ model_id, confidence,
                                 estimated_cost,
                                 estimated_latency_ms }
```

## G.4  Stage 3 — Consensus / LLM Council `omnillm/consensus.py`

```
   user prompt
       │
       ▼
   gateway.query_multiple(council_models, messages)   ← fan-out, concurrent
       │
       ├──▶ model 1  (e.g. gpt-4o-mini)   ─┐
       ├──▶ model 2  (e.g. gemini-2.5)    ─┤ independent answers
       └──▶ model N  (e.g. claude-haiku)  ─┘
                       │
                       ▼  pick strategy
            ┌──────────────────────────────────────────────────────┐
            │ "majority_vote"  → Jaccard-cluster the texts,        │
            │                    return rep of largest cluster.    │
            │ "weighted"       → static weights per model,         │
            │                    pick highest-weighted answer.     │
            │ "synthesis"  ◀── DEFAULT                             │
            │   Build a synthesis prompt that contains all council │
            │   answers and ask the JUDGE LLM to merge them into   │
            │   the BEST combined answer.                          │
            │   Returns JSON:                                      │
            │   { final_answer, agreement_score,                   │
            │     reasoning, dissenting_models }                   │
            └──────────────────────────────────────────────────────┘
                       │
                       ▼
            ConsensusResult{ final_answer,
                             agreement_score (0-1),
                             dissenting_models,
                             synthesis_reasoning }
```

## G.5  Stage 4 — LLM-as-Judge `omnillm/evaluator.py`

> **Who is the judge?** Default `judge_model = "openai-gpt4o"` — i.e. **ChatGPT
> (GPT-4o)**. It is set in `consensus.py` (`ConsensusConfig.judge_model`),
> `evaluator.py` (`Evaluator(judge_model=...)`), and overridable from the CLI
> via `--judge`. The shipped default is OpenAI's GPT-4o, but you can swap in
> Claude, Gemini, or any registered model.

Three judge patterns:

```
      response  ──▶  ┌────────────────────────────────────────────┐
                     │ 1) referenceless (G-Eval)                  │
                     │    Judge scores the answer on its own.     │
                     │    → score ∈ [0,1] + reasoning             │
                     ├────────────────────────────────────────────┤
                     │ 2) reference_based                         │
                     │    Judge compares answer vs gold answer.   │
                     │    → score ∈ [0,1] + reasoning             │
                     ├────────────────────────────────────────────┤
                     │ 3) pairwise   (used to feed ELO)           │
                     │    Judge sees model A vs model B.          │
                     │    Position-swap to remove bias.           │
                     │    → winner ∈ {model_a, model_b, tie}      │
                     └────────────────┬───────────────────────────┘
                                      │
                                      ▼
                            EvalResult / PairwiseResult
```

## G.6  Stage 5 — ELO Scoring `omnillm/scorer.py :: EloScorer`

Pairwise judge verdicts feed here. Same method LMSYS Chatbot Arena uses.

```
   record_match(model_a, model_b, winner, category)
        │
        │  Each model starts at default_rating = 1500
        │
        ▼
   Expected score:

                          1
         E_A  =  ───────────────────────────
                 1 + 10^((R_B − R_A) / 400)

         E_B  =  1 − E_A
        │
        ▼
   Actual score S:   win = 1.0   loss = 0.0   tie = 0.5
        │
        ▼
   Update rule (K = 32):
        R_A'  =  R_A + K · (S_A − E_A)
        R_B'  =  R_B + K · (S_B − E_B)
        │
        ▼
   Stored in:
        ratings[model]                ← overall ELO
        _category_ratings[cat][model] ← per-category ELO
        _history (every match)        ← audit trail
        _rating_history[model]        ← time-series for plots
        │
        ▼
   get_leaderboard()               → overall rank
   get_category_leaderboard(cat)   → reasoning / code / robot / etc.
   save() / load()  → JSON on disk → fed BACK into
                                     SmartRouter._load_results()
```

## G.7  The Feedback Loop (the whole point of the system)

```
      Pepper question ──▶ LangGraph ──▶ answer to user
                                │
                                ├──(council/consensus runs)──▶ judge LLM
                                │                                    │
                                │                                    ▼
                                └──▶ Evaluator (pairwise) ──▶ EloScorer.record_match
                                                                     │
                                                                     ▼
                                                          results/*.json
                                                                     │
                                                                     ▼
                                                  SmartRouter._load_results()
                                                                     │
                                                                     ▼
              Next question is routed to a model whose ELO / quality for
              that task category has gone UP from past wins.
```

> **Short answer to the question "who is the LLM judge in this project?":**
> the default judge is **GPT-4o (ChatGPT)** — `judge_model = "openai-gpt4o"`
> in `consensus.py:54` and `evaluator.py:117`. It is configurable (pass
> Claude, Gemini, etc. via `--judge` or `ConsensusConfig.judge_model`), but
> the shipped default is OpenAI's GPT-4o.

\newpage
