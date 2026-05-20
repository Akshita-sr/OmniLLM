\newpage

# Appendix B — Complete Glossary

> *Every acronym and term used in this book, sorted alphabetically. Use this as a lookup whenever you forget what something means.*

\newpage

**`aiohttp`** — A Python library for asynchronous HTTP clients and servers, used in `omnillm/robotics/pepper.py` as the non-blocking HTTP client for the bridge server.

**Agent graph** — In LangGraph terminology, a directed graph of nodes (each a Python function) that share a state dict. OmniLLM's brain is a 9-node agent graph.

**`ALAnimatedSpeech`** — NAOqi service that handles text-to-speech with synchronised body animation. Pepper's "talking" subsystem.

**`ALAudioDevice`** — NAOqi service that provides access to Pepper's 4 head microphones.

**`ALAudioRecorder`** — NAOqi service that captures audio to a WAV file on Pepper's filesystem.

**`ALBroker`** — NAOqi's central message-routing service. Every NAOqi process must connect to a broker to talk to other NAOqi services.

**`ALLeds`** — NAOqi service that controls Pepper's RGB LEDs (eyes, ears, shoulders).

**`ALMotion`** — NAOqi service that handles joint movement and posture.

**`ALTabletService`** — NAOqi service that displays content on Pepper's chest-mounted tablet.

**`ALTracker`** — NAOqi service that tracks a target (face, sound source, NAO mark) and moves Pepper's head/body to maintain orientation toward it.

**ANOVA** — Analysis of Variance. Statistical test for differences in means across groups. In a within-subjects design, *repeated-measures ANOVA* is used.

**API key** — A secret password (typically a long random string) that authenticates a request to a cloud LLM provider. Stored in `.env`; loaded into environment variables; never committed to git.

**`async def`** — Python keyword to declare a coroutine function. Must be `await`ed (or scheduled via `asyncio.gather`/`asyncio.run`) to actually execute.

**Bartneck Godspeed** — The Godspeed Questionnaire (Bartneck et al. 2009). Standard HRI evaluation instrument with five subscales: anthropomorphism, animacy, likeability, perceived intelligence, perceived safety.

**Base64** — Encoding scheme that represents binary data as ASCII text. Used in OmniLLM to ship WAV audio over JSON HTTP.

**`bridge_server`** — Short for `naoqi_bridge_server.py`. The Python-2.7 HTTP server that translates JSON commands from the AI Layer into NAOqi RPCs.

**`ChromaDB`** — Embedded vector database used by `RAGPipeline` for semantic-similarity retrieval.

**Choregraphe** — SoftBank's official IDE for programming Pepper. Includes a virtual-robot simulator usable on Windows.

**Consensus / Council** — Asking multiple LLMs the same question in parallel and merging their answers. Implemented in `omnillm/consensus.py`. Used in Condition D.

**Cosine similarity** — Measure of similarity between two vectors. Used by ChromaDB to rank retrieved chunks.

**Counterbalancing** — Experimental design technique to cancel order effects by varying the presentation order across participants.

**`DejaVu Sans` / `DejaVu Sans Mono`** — Open-source fonts shipped with matplotlib. Used by the book's PDF builder because they cover Unicode arrows, box-drawing characters, and accented Latin.

**DIBRIS** — Dipartimento di Informatica, Bioingegneria, Robotica e Ingegneria dei Sistemi. The department at the University of Genoa hosting this thesis's robot.

**ELO** — Chess-derived rating system. A 100-point gap means the higher-rated player wins ~64% of the time. Used by OmniLLM's leaderboard.

**Embedded LLM Arena** — The name of the research study supported by OmniLLM. Pepper-mediated multi-LLM benchmark.

**Embedding** — Numeric vector representation of text. Sentence-transformers produces 384-dimensional embeddings; ChromaDB indexes and searches them.

**Environment variable** — OS-level key-value pair. Used for API keys (`OPENAI_API_KEY`, etc.). Read in Python via `os.environ.get(...)`.

**Faithfulness** (RAG) — How accurately an LLM's answer reflects the retrieved context. Scored 0–1 by an LLM-as-judge prompt.

**Flask** — Python web framework. OmniLLM's AI server uses Flask for `/interact`, `/health`, etc.

**G-Eval** — Referenceless LLM-as-judge methodology by Liu et al. 2023. Uses chain-of-thought prompting + form-filling to score open-ended LLM outputs.

**Gateway** — In OmniLLM, the unified entry point for any LLM call: `omnillm/gateway.py`.

**GDPR** — General Data Protection Regulation. EU privacy law governing personal-data handling. Drives several design choices in OmniLLM's logging.

**Gesture planner** — `omnillm/robotics/gesture_planner.py`. Rule-based mapping from `(task_type, response_text)` to `(gesture, LED colour)`.

**Godspeed** — See *Bartneck Godspeed*.

**HRI** — Human-Robot Interaction. The academic field this thesis lives in.

**`HRIGraphState`** — The dataclass that defines the shared state of the agent graph. Lives in `omnillm/hri/agent_graph.py`.

**HTTP** — HyperText Transfer Protocol. The protocol used by every cross-language boundary in OmniLLM.

**Hallucination** — When an LLM generates plausible-sounding but factually incorrect content. OmniLLM's RAG pipeline flags suspected hallucinations via a coverage heuristic.

**JSON** — JavaScript Object Notation. The data format used at every HTTP boundary in OmniLLM.

**JSON-Lines (JSONL)** — One JSON object per line. The format of `results/interactions_<date>.jsonl`.

**LangChain** — Python framework for LLM application development. OmniLLM uses only its document-loader and text-splitter components.

**LangGraph** — Python library by the LangChain team for building stateful, branching agent pipelines. OmniLLM's agent graph is built with LangGraph.

**`langdetect`** — Python library for language detection. Used as a fallback in `LanguageDetector`.

**Latency** — Time from input received to output produced. Measured in milliseconds throughout OmniLLM.

**LED** — Light-Emitting Diode. Pepper has them in its eyes (and elsewhere) and OmniLLM uses them as an emotional/state cue.

**Likert scale** — Survey scale with N points (typically 5 or 7) ranging from "strongly disagree" to "strongly agree." Primary outcome of OmniLLM's experimental study.

**`litellm`** — Python library by BerriAI that wraps 100+ LLM providers behind a unified API. OmniLLM's gateway is built on litellm.

**LLM** — Large Language Model. AI system trained on natural-language data; takes text in, produces text out.

**LLM-as-judge** — Using one LLM to score the output of another. Implemented in `omnillm/evaluator.py`. Used for RAG faithfulness and benchmark scoring.

**LLM Council** — See *Consensus*.

**MMLU** — Massive Multitask Language Understanding benchmark (Hendrycks et al. 2021). A 57-subject knowledge test. OmniLLM compares its embodied rankings against MMLU rankings (H1).

**NAOqi** — Pepper's middleware operating system. Locked to Python 2.7. Provides the AL\* services (`ALMotion`, `ALAnimatedSpeech`, …).

**Ollama** — Free local LLM runtime. Listens on `http://localhost:11434`. Runs open-weight models (Llama, Qwen, Mistral, Phi) on your own CPU/GPU.

**Pairwise preference** — Question that asks the participant to choose between two options. The basis of the ELO scorer.

**Participant ID** — Anonymous code (P001, P002, …) used everywhere in OmniLLM logs. The mapping to real identity lives only on paper, in the experimenter's binder.

**`PepperBridge`** — The Python-3 `RobotBridge` subclass that drives Pepper via HTTP to `naoqi_bridge_server`.

**`pip`** — Python's package installer.

**Position bias** — In pairwise LLM-as-judge, the tendency of the judge to favour whichever response is presented first. Mitigated by swap-and-aggregate.

**`pypdf`** — Python library for extracting text from PDF documents. Used optionally by RAG pipeline.

**`pyproject.toml`** — Modern Python package metadata file. Defines OmniLLM's dependencies and console scripts.

**`pytest`** — Python testing framework. OmniLLM has 289 tests, all mocked.

**RAG** — Retrieval-Augmented Generation. Search a corpus, then prompt the LLM with retrieved context.

**Repeated-measures ANOVA** — ANOVA variant for within-subjects designs. Each participant is their own block.

**`ReportLab`** — Python PDF library, used by `xhtml2pdf` (which the book uses).

**Robot bridge** — Generic name for the layer between the AI Layer and the robot. Abstract in `omnillm/robotics/bridge.py`.

**`RobotAction`** — Dataclass in `omnillm/robotics/bridge.py`. The canonical "what should the robot do?" message.

**`RobotSensorData`** — Dataclass. The canonical "what is the robot sensing?" message.

**Sentence-Transformers** — Python library for sentence embeddings. Used by RAGPipeline (model `all-MiniLM-L6-v2` by default).

**Sgorbissa, Antonio** — Professor at DIBRIS, University of Genoa. Director of the HRI lab where this thesis's Pepper lives.

**SoftBank Robotics** — Manufacturer of Pepper (formerly Aldebaran Robotics).

**Spearman ρ** — Rank-correlation coefficient. Used to test H1 (embodied ranking vs text ranking).

**STT** — Speech-to-Text. Done locally by Whisper in OmniLLM.

**Synthesis** (consensus strategy) — Default consensus mode. A judge LLM combines N parallel answers into one synthesised response.

**Tablet** — Pepper's chest-mounted touchscreen. Accessible via `ALTabletService`.

**Task type** — T1 (Information Retrieval), T2 (Navigation), T3 (Social Conversation), T4 (Multilingual). The four task categories of the Embodied LLM Arena.

**Topology 1** — Pepper polls the AI server. Conversation initiated by the robot.

**Topology 2** — AI server drives Pepper via the bridge server. Conversation initiated by the AI Layer.

**TTS** — Text-to-Speech. Done by Pepper's `ALAnimatedSpeech`.

**Unicode script** — Category of a Unicode character (Latin, Arabic, CJK, Hangul, …). Used as the first signal in language detection.

**Utterance** — One spoken-and-transcribed turn from the participant. The `utterance` field in `HRIGraphState`.

**VAD** — Voice Activity Detection. Energy-thresholded detection of when the participant is speaking. One of the three trigger modes in `naoqi_client.py`.

**venv** — Python virtual environment. See Appendix A.1.

**Vision-language model (VLM)** — LLM extended to accept image input alongside text. Out of scope in this thesis; discussed in Chapter 33.

**WAV** — Waveform Audio File format. The audio format used between Pepper's microphone and Whisper.

**Whisper** — OpenAI's speech-to-text model. Used locally in OmniLLM (not the cloud API).

**Within-subjects design** — Each participant experiences every condition. Higher statistical power than between-subjects for the same N.

**`xhtml2pdf`** — Pure-Python HTML→PDF library. Used to render this book.

**YAML** — YAML Ain't Markup Language. Human-readable data format. Used for `config/models.yaml` and benchmark task definitions.

\newpage
