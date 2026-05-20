# Table of Contents

## Part I — Motivation & Scope

- **Chapter 1** — What Is OmniLLM, in One Sentence and in 1,000 Words
- **Chapter 2** — Why a Physical Humanoid Robot? The Motivation Behind Pepper
- **Chapter 3** — What Happens When the Robot is Absent — the Three Operating Modes
- **Chapter 4** — Scope, Hypotheses, and the Embodied LLM Arena Study

## Part II — Architecture, Flow, & Tech Stack

- **Chapter 5** — The Three-Layer System Architecture
- **Chapter 6** — The Lifecycle of a Single Question, End to End
- **Chapter 7** — The LangGraph Agent Pipeline, Node by Node
- **Chapter 8** — The Tech Stack — Every Library, and Why That One
- **Chapter 9** — Two Topologies for Driving Pepper (Polling vs. Bridge Server)

## Part III — Comprehensive Script & File Breakdown

- **Chapter 10** — The Master File Table — Every Script, Its Purpose, Its Execution Order
- **Chapter 11** — Core LLM Modules: `gateway.py`, `router.py`, `consensus.py`, `evaluator.py`, `scorer.py`, `cli.py`
- **Chapter 12** — HRI & RAG Modules: `hri/classifier.py`, `hri/language_detector.py`, `hri/agent_graph.py`, `hri/experiment.py`, `rag/pipeline.py`
- **Chapter 13** — Robotics Modules: `robotics/bridge.py`, `robotics/pepper.py`, `robotics/gesture_planner.py`, `robotics/whisper_stt.py`
- **Chapter 14** — Server & NAOqi Bridge: `server/app.py`, `server/naoqi_bridge_server.py`, `server/naoqi_client.py`
- **Chapter 15** — Utilities: `utils/experiment_logger.py`, `utils/questionnaire.py`, `utils/cost_tracker.py`, `utils/export.py`
- **Chapter 16** — The Python 2.7 ↔ Python 3.x Bridge Problem (and Three Different Solutions to It)

## Part IV — Setup, Execution, & Building from Scratch

- **Chapter 17** — Installing OmniLLM From Zero (Windows, macOS, Linux)
- **Chapter 18** — Scenario A — Running Without Any Robot (Text-Only)
- **Chapter 19** — Scenario B — Running With Choregraphe's Virtual Pepper
- **Chapter 20** — Scenario C — Running With the Physical Pepper Robot
- **Chapter 21** — Day Zero — The Real-Pepper Deployment at DIBRIS, Step by Step
- **Chapter 22** — Building This Project From Scratch — A 13-Week Plan for a Replicator

## Part V — Conducting Experiments & Logging

- **Chapter 23** — The Experimental Design — Five Conditions, Four Task Types, One Hypothesis Set
- **Chapter 24** — Running a Single Subject Session (Step by Step)
- **Chapter 25** — Counterbalancing and Why It Matters (Latin-Square Designs Explained)
- **Chapter 26** — The Data Logging Pipeline — From Microphone to CSV
- **Chapter 27** — Questionnaires — Likert, Godspeed, Pairwise, Observer (Concrete Examples)
- **Chapter 28** — Ethics, Consent, GDPR, and the UniGE Process
- **Chapter 29** — Insights From the May 2026 Pilot — What the Two P000 Runs Actually Showed
- **Chapter 30** — Data Analysis with pandas and Jupyter — A Beginner-Friendly Workflow

## Part VI — Future Scope & Improvements

- **Chapter 31** — Current Limitations — Honest Assessment
- **Chapter 32** — Short-Term Improvements (Next 3 Months)
- **Chapter 33** — Medium-Term Research Directions (Next 12 Months)
- **Chapter 34** — Long-Term Vision — Where Embodied LLM Research Is Going

## Appendices

- **Appendix A** — Python Primer — Just the Parts You Need for OmniLLM
- **Appendix B** — Complete Glossary
- **Appendix C** — Complete Terminal Command Reference (Windows PowerShell + macOS/Linux Bash)
- **Appendix D** — Troubleshooting Reference (Symptom → Cause → Fix)
- **Appendix E** — End-to-End Flow Diagram (One Page)
- **Appendix F** — File Index — Every File in the Repository, One Line Each
- **Appendix G** — External Resources — Papers, Libraries, Repositories (Annotated)
- **Appendix H** — Pepper-LLM Integration Survey — The State of the Field, May 2026
- **Appendix I** — The Pepper Platform Reference — Hardware, NAOqi, Choregraphe, the Five Bridge Patterns
- **Appendix J** — AI-Stack Library Rationale — What, Why, Alternatives, Where Used
- **Appendix K** — Walkthroughs, Feature Catalogue, and Execution Plans (Line-by-Line Code Journey, Worked Session, Eight Axes, Complete Feature Reference, One-Month Plan)

\newpage
