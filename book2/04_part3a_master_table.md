\newpage

# Part III — Comprehensive Script & File Breakdown

> *Parts I and II were the bird's-eye view. Part III is the file-by-file ground tour. Every Python module that ships in the repository gets a chapter, a purpose statement, a list of its public symbols, an explanation of every non-trivial method, and an answer to the question "why is it written this way?"*
>
> *If you have only an hour and you want to understand the codebase end-to-end, read Chapter 10. If you have a day, read Chapters 10 through 16.*

\newpage

## Chapter 10 — The Master File Table — Every Script, Its Purpose, Its Execution Order

### At a Glance

The repository contains roughly **35 Python source files** organised into 7 sub-packages and 1 demo-script directory. The complete enumeration follows. The right-most column gives the **execution order** when you run a full subject session (`run_subject_experiment.py`) — files marked `*` are entry points that the user actually invokes; everything else is library code reached via import.

### The Master Table

| # | File | Sub-package | Lines | Imports from | Purpose | Exec. order |
|---|---|---|---|---|---|---|
| **Entry points (you actually run these)** |||||||
| 1 | [omnillm/cli.py](../omnillm/cli.py) | top | ~600 | gateway, router, consensus, evaluator, scorer, export, cost_tracker | The `omnillm` CLI: `models`, `ask`, `route`, `council`, `evaluate`, `leaderboard`, `costs`, `export` | * Optional |
| 2 | [omnillm/server/app.py](../omnillm/server/app.py) | server | ~480 | gateway, rag, hri.agent_graph, hri.experiment, utils.experiment_logger | Flask AI server. The HTTP bridge between Pepper and the AI stack. | * 1 (start first) |
| 3 | [omnillm/server/naoqi_bridge_server.py](../omnillm/server/naoqi_bridge_server.py) | server | ~600 | naoqi (Py2.7) | The Python-2.7 HTTP bridge that drives Pepper's NAOqi from the AI Layer | * 2 (start near robot) |
| 4 | [omnillm/server/naoqi_client.py](../omnillm/server/naoqi_client.py) | server | ~700 | naoqi (Py2.7), urllib (Py2.7) | The Python-2.7 conversation loop. Three trigger modes: text / touch / vad. | * Alt. to (3) for Topology 1 |
| 5 | [scripts/pepper_demo/run_subject_experiment.py](../scripts/pepper_demo/run_subject_experiment.py) | scripts | ~250 | (talks to server + bridge via HTTP only) | The 20-interaction subject experiment driver. Runs the full 5×4 matrix. | * 3 (per session) |
| 6 | [scripts/pepper_demo/demo_pepper_omnillm.py](../scripts/pepper_demo/demo_pepper_omnillm.py) | scripts (P2.7) | ~250 | naoqi | Single-shot demo: one question → AI server → Pepper speaks. Has `--check-only` for NAOqi-only sanity test. | * Optional |
| 7 | [scripts/pepper_demo/test_all_conditions.py](../scripts/pepper_demo/test_all_conditions.py) | scripts | ~180 | (talks to server via HTTP only) | Batch-tests all 5 conditions × 4 task types against the AI server. No robot needed. | * Optional |
| 8 | [scripts/pepper_demo/proof_of_routing.py](../scripts/pepper_demo/proof_of_routing.py) | scripts | ~120 | gateway, router | Demonstrates that Condition B actually invokes Llama-via-Ollama. Proof of the May 2026 fix. | * Optional |
| 9 | [book/build_pdf.py](../book/build_pdf.py) | book | ~300 | markdown, reportlab, xhtml2pdf | Rebuilds `OmniLLM_Book.pdf` from the master Markdown. | * Optional |
| **Core LLM modules — Chapter 11** |||||||
| 10 | [omnillm/gateway.py](../omnillm/gateway.py) | top | ~270 | litellm, yaml, asyncio | The single async door to every LLM provider. Wraps LiteLLM. | Imported by app.py |
| 11 | [omnillm/router.py](../omnillm/router.py) | top | ~370 | yaml | Six routing strategies; learns from past eval results. | Imported by agent_graph (Cond. C) |
| 12 | [omnillm/consensus.py](../omnillm/consensus.py) | top | ~400 | gateway, asyncio | LLM Council — majority vote / weighted / judge-LLM synthesis. | Imported by agent_graph (Cond. D) |
| 13 | [omnillm/evaluator.py](../omnillm/evaluator.py) | top | ~450 | gateway | LLM-as-Judge — referenceless (G-Eval), reference-based, pairwise with position-bias swap. | Imported by RAG faithfulness, CLI |
| 14 | [omnillm/scorer.py](../omnillm/scorer.py) | top | ~350 | json | ELO rating + per-category leaderboard. | Imported by CLI `leaderboard` |
| **HRI & RAG modules — Chapter 12** |||||||
| 15 | [omnillm/hri/agent_graph.py](../omnillm/hri/agent_graph.py) | hri | ~650 | gateway, rag, robotics.gesture_planner, robotics.whisper_stt, langgraph | THE BRAIN. The 9-node LangGraph pipeline. | 1 per interaction (called by app.py) |
| 16 | [omnillm/hri/classifier.py](../omnillm/hri/classifier.py) | hri | ~340 | re, gateway (opt.) | Rule-based + LLM-based task classifier (T1–T4). | Called by agent_graph node 3 |
| 17 | [omnillm/hri/language_detector.py](../omnillm/hri/language_detector.py) | hri | ~320 | unicodedata, langdetect (opt.) | Unicode-script + n-gram + langdetect language detection. | Called by agent_graph node 2 |
| 18 | [omnillm/hri/experiment.py](../omnillm/hri/experiment.py) | hri | ~280 | dataclasses | Experimental conditions (A–E), participant sessions, counterbalancing helpers. | Called by app.py to resolve Cond → model |
| 19 | [omnillm/rag/pipeline.py](../omnillm/rag/pipeline.py) | rag | ~600 | chromadb (opt.), pypdf (opt.), gateway | RAG retrieve + generate + faithfulness scoring + hallucination flag. | Called by agent_graph T1/T2 nodes |
| **Robotics modules — Chapter 13** |||||||
| 20 | [omnillm/robotics/bridge.py](../omnillm/robotics/bridge.py) | robotics | ~250 | json, abc | Abstract `RobotBridge` + shared `RobotAction` / `RobotSensorData` types. | Used as ABC by PepperBridge |
| 21 | [omnillm/robotics/pepper.py](../omnillm/robotics/pepper.py) | robotics | ~440 | aiohttp, socket, asyncio | Pepper-specific HTTP client; auto-discovery; three-mode fallback (server/direct/stub). | Imported by agent_graph if reverse topology |
| 22 | [omnillm/robotics/gesture_planner.py](../omnillm/robotics/gesture_planner.py) | robotics | ~200 | re | Maps (task_type, response_text) → (gesture, LED colour). | Called by agent_graph LLM nodes |
| 23 | [omnillm/robotics/whisper_stt.py](../omnillm/robotics/whisper_stt.py) | robotics | ~200 | openai-whisper (opt.) | Whisper STT — local or API backend; auto WAV→tensor. | Called by agent_graph node 1 |
| **Utilities — Chapter 15** |||||||
| 24 | [omnillm/utils/experiment_logger.py](../omnillm/utils/experiment_logger.py) | utils | ~280 | csv, json, dataclasses | `InteractionRecord` dataclass + append-only JSON-Lines logger; CSV export. | Called by agent_graph node 7 |
| 25 | [omnillm/utils/questionnaire.py](../omnillm/utils/questionnaire.py) | utils | ~390 | csv, json, dataclasses | Likert / Godspeed / pairwise / observer data models + `QuestionnaireCollector`. | Called by `/evaluate` endpoint |
| 26 | [omnillm/utils/cost_tracker.py](../omnillm/utils/cost_tracker.py) | utils | ~180 | json, datetime | Per-model running USD spend. | Called by CLI `costs` |
| 27 | [omnillm/utils/export.py](../omnillm/utils/export.py) | utils | ~200 | csv, json | Convert results JSON → CSV / Markdown. | Called by CLI `export` |
| **Tasks (model registry consumers) — supporting** |||||||
| 28 | [omnillm/tasks/loader.py](../omnillm/tasks/loader.py) | tasks | ~110 | yaml | Loads benchmark task definitions from `config/tasks/*.yaml`. | Called by CLI `evaluate` |
| 29 | [omnillm/tasks/sample_tasks.py](../omnillm/tasks/sample_tasks.py) | tasks | ~80 | — | Bundled benchmark prompts across 8 evaluation axes. | Imported by tasks.loader |
| **Tests — for confidence** |||||||
| 30 | [tests/test_gateway.py](../tests/test_gateway.py) | tests | ~280 | pytest, gateway | 21 tests: LiteLLM string construction, cost calc, error handling. | * pytest |
| 31 | [tests/test_router.py](../tests/test_router.py) | tests | ~330 | pytest, router | 24 tests: all 6 strategies, constraint enforcement. | * pytest |
| 32 | [tests/test_consensus.py](../tests/test_consensus.py) | tests | ~270 | pytest, consensus | 20 tests: majority / weighted / synthesis. | * pytest |
| 33 | [tests/test_evaluator.py](../tests/test_evaluator.py) | tests | ~210 | pytest, evaluator | 15 tests: 3 judge patterns. | * pytest |
| 34 | [tests/test_scorer.py](../tests/test_scorer.py) | tests | ~290 | pytest, scorer | 22 tests: ELO math + leaderboard correctness. | * pytest |
| 35 | [tests/test_rag.py](../tests/test_rag.py) | tests | ~330 | pytest, rag | 26 tests: indexing, retrieval, faithfulness, hallucination flag. | * pytest |
| 36 | [tests/test_hri.py](../tests/test_hri.py) | tests | ~650 | pytest, classifier, language_detector, experiment | 51 tests: classifier, language detection, experiment manager. | * pytest |
| 37 | [tests/test_gesture_planner.py](../tests/test_gesture_planner.py) | tests | ~390 | pytest, gesture_planner | 30 tests: gesture-selection rules. | * pytest |
| 38 | [tests/test_pepper_bridge.py](../tests/test_pepper_bridge.py) | tests | ~290 | pytest, pepper | Tests for stub/direct/server mode auto-detection. | * pytest |
| 39 | [tests/test_experiment_logger.py](../tests/test_experiment_logger.py) | tests | ~220 | pytest, experiment_logger | 16 tests: append-only log + CSV export. | * pytest |
| 40 | [tests/test_new_components.py](../tests/test_new_components.py) | tests | ~640 | many | 53 tests: agent_graph, whisper_stt, questionnaire, server, KB files. | * pytest |
| **Configuration files (read at startup)** |||||||
| 41 | [config/models.yaml](../config/models.yaml) | config | ~300 | — | The 19-model registry. Add LLMs here. | Loaded by gateway, router |
| 42 | [config/tasks/*.yaml](../config/tasks/) | config | varies | — | Benchmark task definitions across 8 axes. | Loaded by tasks.loader |
| 43 | `.env.example` | top | ~15 | — | Template for API keys. Copy to `.env` and edit. | Read by python-dotenv |
| 44 | [pyproject.toml](../pyproject.toml) | top | ~80 | — | Package metadata, dependencies, optional extras, console script registration. | Used by `pip install -e .` |
| 45 | [requirements.txt](../requirements.txt) | top | ~30 | — | Flat dependency list (mirrors pyproject `dependencies` for non-pip users). | Used by `pip install -r ...` |
| **Knowledge base (RAG-indexed)** |||||||
| 46 | [knowledge_base/lab_info.txt](../knowledge_base/lab_info.txt) | kb | ~80 | — | DIBRIS / Sgorbissa lab description (hours, location, research foci). | Read by RAGPipeline at server startup |
| 47 | [knowledge_base/faq.txt](../knowledge_base/faq.txt) | kb | ~120 | — | Common visitor questions and answers. | Read by RAGPipeline |
| 48 | [knowledge_base/research_projects.txt](../knowledge_base/research_projects.txt) | kb | ~150 | — | Active research lines and key publications. | Read by RAGPipeline |
| 49 | [knowledge_base/university_map.txt](../knowledge_base/university_map.txt) | kb | ~100 | — | DIBRIS floor map; room locations; transit directions. | Read by RAGPipeline |
| 50 | [knowledge_base/event_schedule.csv](../knowledge_base/event_schedule.csv) | kb | ~30 rows | — | Upcoming lab events; visitor-relevant dates. | Read by RAGPipeline |
| 51 | [knowledge_base/visitor_profiles.csv](../knowledge_base/visitor_profiles.csv) | kb | ~20 rows | — | Typical visitor categories (researcher, student, family). | Read by RAGPipeline |

### Execution Order — Live Subject Session

For a complete picture, here is the timeline of which processes start in which order, on which Python interpreter, when running the full study:

```
T+0:00  HUMAN starts experimenter laptop.
T+0:01  HUMAN presses Pepper's chest button.
T+0:25  Pepper says its IP aloud (e.g. "192.168.1.42").
                                  Note this as PEPPER_IP.
T+0:30  HUMAN opens PowerShell window #1.
        PS> cd C:\Users\akshi\OneDrive\Desktop\OmniLLM
        PS> .\venv\Scripts\Activate.ps1
        PS> python -m omnillm.server.app --host 0.0.0.0 --port 5000
                                            +--- starts the AI server (Py 3.11)
                                                  Loads LangGraph, RAG (49 chunks),
                                                  Gateway (19 models registered).
                                                  Listens on 0.0.0.0:5000.
T+0:35  HUMAN opens PowerShell window #2.
        PS> C:\Python27\python.exe omnillm\server\naoqi_bridge_server.py `
                --robot-ip <PEPPER_IP> --robot-port 9559 `
                --bind 0.0.0.0 --bridge-port 6000
                                            +--- starts the NAOqi bridge (Py 2.7)
                                                  Connects to ALBroker at Pepper.
                                                  Listens on 0.0.0.0:6000.
T+0:40  HUMAN starts PowerShell window #3.
        PS> .\venv\Scripts\python.exe scripts\pepper_demo\run_subject_experiment.py `
                --participant P003 --server http://127.0.0.1:5000 `
                --bridge http://127.0.0.1:6000
                                            +--- driver loop:
                                                  for each (condition, task) in ORDER:
                                                      POST /interact to AI server
                                                      receive RobotAction JSON
                                                      POST /action to bridge
                                                      bridge -> NAOqi -> Pepper
                                                      sleep 2 seconds
                                                  When all 20 done, write CSV+JSON.
T+25:00 Subject session ends. Driver writes
        results/subject_run_P003_<timestamp>.{json,csv}.
T+25:05 HUMAN administers paper questionnaires (Chapter 27).
T+30:00 HUMAN closes all three PowerShell windows.
```

### Reading Guide for the Rest of Part III

The remaining chapters of Part III dive into each file group:

| If you want to understand… | Read |
|---|---|
| How any model gets called and how cost is tracked | Chapter 11 (`gateway.py`) |
| How the router picks a model | Chapter 11 (`router.py`) |
| How the consensus council works | Chapter 11 (`consensus.py`) |
| How LLM-as-judge actually scores answers | Chapter 11 (`evaluator.py`) |
| How the ELO leaderboard updates | Chapter 11 (`scorer.py`) |
| The brain of Pepper — every LangGraph node | Chapter 12 (`agent_graph.py`) |
| How "Where is Room 305?" becomes `task_type=navigation` | Chapter 12 (`classifier.py`) |
| How Italian-vs-French is detected | Chapter 12 (`language_detector.py`) |
| How conditions A–E map to model IDs | Chapter 12 (`experiment.py`) |
| How RAG retrieves + scores faithfulness | Chapter 12 (`rag/pipeline.py`) |
| How Python 3 drives Pepper without owning NAOqi | Chapter 13 (`robotics/pepper.py`) |
| How `point_left` is chosen automatically | Chapter 13 (`gesture_planner.py`) |
| How audio gets transcribed locally | Chapter 13 (`whisper_stt.py`) |
| The HTTP API Pepper speaks to the AI server | Chapter 14 (`server/app.py`) |
| The HTTP API the AI server speaks to Pepper | Chapter 14 (`naoqi_bridge_server.py`) |
| Three trigger modes (text/touch/vad) | Chapter 14 (`naoqi_client.py`) |
| The complete data lifecycle | Chapter 15 (`experiment_logger.py`, `questionnaire.py`) |
| Why Python 2.7 + Python 3.11 sit in one project, and three ways we solve it | Chapter 16 |

\newpage
