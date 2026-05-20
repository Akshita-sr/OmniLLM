\newpage

# Appendix E — End-to-End Flow Diagram (One Page)

> *Print this page and pin it above your desk. It is the entire system on one sheet.*

```
+============================================================================+
|                        HUMAN PARTICIPANT  (at DIBRIS lab)                  |
|                                                                            |
|  Says / Types / Head-touches  ----->  Hears / Watches / Reads tablet       |
+--------------------------------+-------------------------------------------+
                                 |  voice  /  head-touch  /  Wi-Fi           |
                                 v
+----------------------------------------------------------------------------+
|                     PEPPER ROBOT  (Python 2.7 + NAOqi 2.5)                 |
|                                                                            |
|   +------------------+      +-----------------+     +-------------------+  |
|   | ALAudioDevice    |      | ALAnimatedSpeech|     | ALMotion          |  |
|   | (4 mics)         |      | (TTS + sync)    |     | (20 DOF)          |  |
|   +--------+---------+      +--------+--------+     +---------+---------+  |
|            |                         ^                        ^            |
|            |       +-----------------+--------+               |            |
|            v       |                          |               |            |
|   +-----------------------------------------------------------+---------+  |
|   |          naoqi_bridge_server.py    (Topology 2)                     |  |
|   |   /ping   /action   /sensors   /audio/record   /tracker/{start|stop}|  |
|   |   /disconnect                                                       |  |
|   |                          OR                                         |  |
|   |          naoqi_client.py           (Topology 1)                     |  |
|   |   --trigger text  |  --trigger touch  |  --trigger vad              |  |
|   +------------------------------------+----------------------+--------+  |
+----------------------------------------|----------------------|-----------+
                                         |HTTP                  | HTTP
                                         | JSON                 |  WAV(b64)
                                         v                      v
+----------------------------------------------------------------------------+
|              AI SERVER  ( Python 3.11+   omnillm.server.app )              |
|                                                                            |
|  +----------------------------------------------------------------------+  |
|  |                           Flask endpoints                            |  |
|  |   POST /interact   POST /transcribe   POST /evaluate                 |  |
|  |   GET  /health     GET  /status        GET  /export                  |  |
|  +----------------------------------+-----------------------------------+  |
|                                     |                                      |
|                                     v                                      |
|  +----------------------------------------------------------------------+  |
|  |                  LangGraph Agent Graph  (9 nodes)                    |  |
|  |                                                                      |  |
|  |    [START]                                                           |  |
|  |       ↓                                                              |  |
|  |   transcribe_audio  (Whisper STT, local)                             |  |
|  |       ↓                                                              |  |
|  |   detect_language   (Unicode script + n-gram + langdetect)           |  |
|  |       ↓                                                              |  |
|  |   classify_task     (T1 / T2 / T3 / T4)                              |  |
|  |       ↓                                                              |  |
|  |   [conditional edge by (task_type, condition, rag_enabled)]          |  |
|  |       ↓     ↓     ↓     ↓                                            |  |
|  |     rag  nav_rag  direct_llm  multilingual_llm                       |  |
|  |       ↓     ↓     ↓     ↓                                            |  |
|  |       +-----+-----+-----+                                            |  |
|  |       ↓                                                              |  |
|  |   smart_router     (Cond C: route; Cond D: council; else: skip)      |  |
|  |       ↓                                                              |  |
|  |   generate_action_plan  (assemble RobotAction JSON)                  |  |
|  |       ↓                                                              |  |
|  |   log_interaction       (ExperimentLogger → JSONL + CSV)             |  |
|  |       ↓                                                              |  |
|  |    [END]  ──>  RobotAction JSON  back to Flask  back to Pepper       |  |
|  +----------------------------------------------------------------------+  |
|                                                                            |
|  +----------------------------+   +-----------------------------------+    |
|  | RAG Pipeline               |   | OmniLLM Core                      |    |
|  | ChromaDB + keyword         |   | LiteLLM Gateway  (19 models)      |    |
|  | fallback + PDF/CSV/TXT     |   | Smart Router     (6 strategies)   |    |
|  | + faithfulness scoring     |   | Consensus / Council (3 strategies)|    |
|  +----------------------------+   | LLM-as-Judge     (3 patterns)     |    |
|                                   | ELO Scorer       (per-category)   |    |
|                                   +-----------------------------------+    |
|                                                                            |
|  +----------------------------------------------------------------------+  |
|  |  LLM Backends  (via LiteLLM, unified async API)                      |  |
|  |   OpenAI       GPT-4o       GPT-4o-mini    GPT-3.5-turbo             |  |
|  |   Anthropic    Claude Sonnet   Claude Haiku                          |  |
|  |   Google       Gemini 2.5 Pro   Gemini 2.5 Flash   Gemini Flash      |  |
|  |   DeepSeek     DeepSeek V3                                           |  |
|  |   Ollama (local, $0):  Llama 3:8b   Llama 3.2:3b                     |  |
|  |                        Qwen 2.5:7b  Mistral 7B   Phi-3               |  |
|  +----------------------------------------------------------------------+  |
+============================================================================+

         CONDITIONS A–E (selected per request via /interact body)
         A: Fixed cloud (GPT-4o-mini) + RAG       (baseline)
         B: Fixed local (Llama 3:8b)  + RAG       (free / offline)
         C: Smart-routed              + RAG       (TASK_TYPE strategy)
         D: 3-model council           + RAG       (synthesis)
         E: GPT-4o-mini               +  no RAG   (control for H3)

         TASKS T1–T4 (classified from utterance)
         T1: Information Retrieval  ----> rag node
         T2: Navigation             ----> nav_rag node (+ pointing gesture)
         T3: Social Conversation    ----> direct_llm node
         T4: Multilingual           ----> multilingual_llm node (Claude Haiku)
```

\newpage

# Appendix F — File Index — Every File in the Repository, One Line Each

> *Look-up reference. Files are grouped by directory.*

\newpage

## `omnillm/`  (the main Python package)

| File | Lines | Purpose (one line) |
|---|---|---|
| `__init__.py` | ~10 | Re-exports the public API of the package |
| `gateway.py` | ~270 | Unified LLM gateway; LiteLLM-backed; async query |
| `router.py` | ~370 | Smart router; 6 strategies; eval-result learning |
| `consensus.py` | ~400 | 3-model LLM council; majority/weighted/synthesis |
| `evaluator.py` | ~450 | LLM-as-judge: referenceless / reference / pairwise |
| `scorer.py` | ~350 | ELO leaderboard, per-category |
| `cli.py` | ~600 | `omnillm` console-script entry point (click + rich) |

## `omnillm/hri/`  (Embodied LLM Arena)

| File | Lines | Purpose |
|---|---|---|
| `__init__.py` | ~5 | Re-exports `build_hri_graph`, the experiment manager |
| `agent_graph.py` | ~650 | The 9-node LangGraph pipeline. Pepper's brain. |
| `classifier.py` | ~340 | Rule-based + LLM HRI task classifier (T1–T4) |
| `language_detector.py` | ~320 | Script + n-gram + langdetect language detection |
| `experiment.py` | ~280 | Conditions A–E; ParticipantSession; ExperimentManager |

## `omnillm/rag/`

| File | Lines | Purpose |
|---|---|---|
| `__init__.py` | ~5 | Re-exports `RAGPipeline`, `DocumentChunk`, `RAGResponse` |
| `pipeline.py` | ~600 | ChromaDB indexing + retrieval + faithfulness scoring |

## `omnillm/robotics/`

| File | Lines | Purpose |
|---|---|---|
| `__init__.py` | ~5 | Re-exports the bridge factory + types |
| `bridge.py` | ~250 | Abstract RobotBridge + RobotAction / RobotSensorData |
| `pepper.py` | ~440 | Python-3 client of the bridge server; 3-mode fallback |
| `gesture_planner.py` | ~200 | (task_type, response_text) → (gesture, LED) |
| `whisper_stt.py` | ~200 | Local or API Whisper STT |

## `omnillm/server/`

| File | Lines | Purpose |
|---|---|---|
| `__init__.py` | ~5 | (Empty re-export shell) |
| `app.py` | ~480 | Flask AI server. Six HTTP endpoints. |
| `naoqi_bridge_server.py` | ~600 | Python-2.7 HTTP bridge; stdlib only |
| `naoqi_client.py` | ~700 | Python-2.7 conversation loop; text/touch/vad triggers |

## `omnillm/tasks/`

| File | Lines | Purpose |
|---|---|---|
| `__init__.py` | ~5 | Re-exports loader |
| `loader.py` | ~110 | Loads benchmark task YAML files from `config/tasks/` |
| `sample_tasks.py` | ~80 | Bundled benchmark prompts across 8 evaluation axes |

## `omnillm/utils/`

| File | Lines | Purpose |
|---|---|---|
| `__init__.py` | ~5 | Re-exports the logger + collector + exporter |
| `experiment_logger.py` | ~280 | InteractionRecord + JSONL + CSV export |
| `questionnaire.py` | ~390 | Likert / Godspeed / pairwise / observer dataclasses |
| `cost_tracker.py` | ~180 | Per-model running USD spend |
| `export.py` | ~200 | JSON ↔ CSV ↔ Markdown converter |

## `config/`

| File | Lines | Purpose |
|---|---|---|
| `models.yaml` | ~300 | 19-model registry + routing config |
| `tasks/*.yaml` | varies | Benchmark task definitions (one file per evaluation axis) |

## `knowledge_base/`  (RAG-indexed)

| File | Lines | Purpose |
|---|---|---|
| `lab_info.txt` | ~80 | DIBRIS / Sgorbissa lab description |
| `faq.txt` | ~120 | Common visitor questions and answers |
| `research_projects.txt` | ~150 | Active research lines, key publications |
| `university_map.txt` | ~100 | DIBRIS floor map, room locations, transit |
| `event_schedule.csv` | ~30 rows | Upcoming lab events |
| `visitor_profiles.csv` | ~20 rows | Typical visitor categories |
| `_legacy_irai/` | — | Old IRAI-Lab content preserved for reference |

## `scripts/pepper_demo/`

| File | Lines | Purpose |
|---|---|---|
| `README.md` | ~160 | Quick reference for all demo scripts |
| `REAL_PEPPER_CHECKLIST.md` | ~150 | The Day-Zero checklist (mirrored in Chapter 21) |
| `demo_pepper_omnillm.py` | ~250 | Python-2.7 single-shot demo |
| `test_all_conditions.py` | ~180 | Python-3 batch test of all 5 × 4 conditions |
| `run_subject_experiment.py` | ~250 | The subject experiment driver |
| `proof_of_routing.py` | ~120 | Demonstrates that Condition B actually runs Llama |
| `launch_real_pepper.ps1` | ~50 | PowerShell helper to launch server + bridge in one go |

## `tests/`

| File | Tests | Purpose |
|---|---|---|
| `test_gateway.py` | 21 | LiteLLM strings, cost calc, error handling |
| `test_router.py` | 24 | All 6 strategies, constraint enforcement |
| `test_consensus.py` | 20 | Majority / weighted / synthesis |
| `test_evaluator.py` | 15 | 3 judge patterns |
| `test_scorer.py` | 22 | ELO math + leaderboard |
| `test_hri.py` | 51 | Classifier, language detector, experiment manager |
| `test_rag.py` | 26 | Indexing, retrieval, faithfulness, hallucination |
| `test_gesture_planner.py` | 30 | Gesture-selection rules |
| `test_pepper_bridge.py` | (variable) | Stub/direct/server mode auto-detection |
| `test_experiment_logger.py` | 16 | Append-only log + CSV export |
| `test_new_components.py` | 53 | agent_graph, whisper_stt, questionnaire, server, KB |
| **Total** | **278+** | All mocked. No API keys or robot needed. |

## `book2/`  (this book)

| File | Lines | Purpose |
|---|---|---|
| `00_front_matter.md` | ~200 | Title page, copyright, preface |
| `01_toc.md` | ~80 | Table of contents |
| `02_part1_motivation.md` | ~750 | Part I — Motivation & Scope |
| `03_part2_architecture.md` | ~700 | Part II — Architecture, Flow, Tech Stack |
| `04_part3a_master_table.md` | ~250 | Part III, Chapter 10 — Master file table |
| `05_part3b_core_modules.md` | ~600 | Part III, Chapter 11 — Core LLM modules |
| `06_part3c_hri_rag.md` | ~700 | Part III, Chapter 12 — HRI & RAG modules |
| `07_part3d_robotics_server_utils_bridge.md` | ~900 | Part III, Chapters 13–16 |
| `08_part4_setup_and_day_zero.md` | ~900 | Part IV — Setup + Day Zero |
| `09_part5_experiments.md` | ~1000 | Part V — Experiments |
| `10_part6_future.md` | ~500 | Part VI — Future Scope |
| `11_appendix_a_python_primer.md` | ~400 | Python primer for beginners |
| `12_appendix_b_glossary.md` | ~280 | Glossary |
| `13_appendix_c_commands_d_troubleshooting.md` | ~400 | Commands + troubleshooting |
| `14_appendix_e_flow_f_file_index.md` | ~250 | Flow diagram + file index (this appendix) |
| `15_appendix_g_h_references.md` | ~800 | External resources + Pepper-LLM survey |
| `OmniLLM_Book.md` | ~9500 | Master concatenated copy for the PDF builder |
| `build_pdf.py` | ~330 | Markdown → HTML → PDF pipeline |

## Root

| File | Purpose |
|---|---|
| `README.md` | The README on GitHub |
| `LICENSE` | MIT |
| `pyproject.toml` | Package metadata, dependencies, optional extras |
| `requirements.txt` | Flat dependency list |
| `.env.example` | API key template |

\newpage
