\newpage

# Appendix J — AI-Stack Library Rationale

> *Chapter 8 listed every direct dependency in a one-line table. This appendix expands each one into a paragraph: **what it is, why we picked it, what we'd have used otherwise, and where in the codebase it lives.** Read this when you need to defend a tooling choice or evaluate a replacement.*

\newpage

## J.1 — LiteLLM

**What it is.** A Python library that exposes 100+ LLM providers behind one identical function call. You pass `model="openai/gpt-4o"` or `model="anthropic/claude-haiku"` or `model="ollama/llama3:8b"` — the call signature is the same.

**Why we picked it.** Without it, OmniLLM would need separate adapter code for each provider, each with its own pagination, error-handling, and token-counting quirks. LiteLLM normalises this in one library that's actively maintained by BerriAI. The cost-per-token table is built in, the async API is uniform, and the provider prefix system (`ollama/`, `gemini/`, `anthropic/`) is intuitive once you've learned it.

**Alternatives considered.** Direct provider SDKs (`openai`, `anthropic`, `google-generativeai`) — more control, more code; the gateway alone would have been 800 lines instead of 270. **`aisuite`** (Andrew Ng's lightweight alternative) — smaller, but covers fewer providers and no Ollama. **`openrouter`** — a paid hosted gateway with similar surface but you must route through their cloud. LiteLLM was the lowest-friction choice for a self-hosted setup.

**Where used.** Imported by [omnillm/gateway.py](../omnillm/gateway.py). Every LLM call in the entire project funnels through `litellm.acompletion(...)`.

\newpage

## J.2 — LangGraph

**What it is.** A library on top of LangChain for building **stateful agent graphs** — directed graphs whose nodes are async functions sharing a single state dict, with conditional edges between them. Visualisable as Mermaid or Graphviz at runtime.

**Why we picked it.** OmniLLM's HRI pipeline is genuinely a graph (transcribe → detect → classify → branch → answer → plan → log) with conditional routing. Writing this as one 200-line `async` function with `if/elif` branches would work but be untestable, unreadable, and impossible to visualise. LangGraph gives us named nodes, a typed state dataclass, and `add_conditional_edges` for the T1/T2/T3/T4 branch point.

**Alternatives considered.** **Plain async functions** — more verbose, no diagram. **LangChain's deprecated `AgentExecutor`** — limited routing, deprecated in favour of LangGraph itself. **Custom DAG libraries** (`prefect`, `airflow`) — overkill, batch-oriented, don't compose well with async. LangGraph was the only framework purpose-built for async LLM-node graphs.

**Where used.** [omnillm/hri/agent_graph.py](../omnillm/hri/agent_graph.py). The 9-node pipeline that is Pepper's brain.

\newpage

## J.3 — ChromaDB

**What it is.** A pure-Python embedded vector database. Stores embeddings + their source text + metadata in a local SQLite file. Supports cosine similarity search with HNSW indexing.

**Why we picked it.** Embedded (no separate process), persistent across restarts, zero configuration, pip-installable. For a single researcher with a < 10 k-document knowledge base, this is plenty. The fallback path — keyword search over in-memory documents — also lives in the same file (`RAGPipeline._retrieve_keyword`), so the rest of the pipeline is unaffected if ChromaDB fails to load.

**Alternatives considered.** **Qdrant**, **Weaviate**, **Pinecone** — heavier, require running a server (Docker or cloud). **FAISS** — fast but lower-level, no metadata filtering, requires a C++ build chain. **LanceDB** — newer, comparable; we briefly evaluated it but ChromaDB's documentation maturity won. For OmniLLM's ~50-chunk DIBRIS knowledge base, the speed difference between any of these is irrelevant.

**Where used.** [omnillm/rag/pipeline.py](../omnillm/rag/pipeline.py). One `Collection` per running pipeline.

\newpage

## J.4 — LangChain

**What it is.** A broader framework for LLM apps. OmniLLM uses **only** its document loaders (`PyPDFLoader`, `CSVLoader`, `TextLoader`) and the `RecursiveCharacterTextSplitter` — **not** the larger Chain or Agent abstractions, which are opinionated and easy to outgrow.

**Why we picked it.** The document loaders save dozens of lines per file format. They're tested by a large community and they normalise output so each chunk has `.page_content` and `.metadata` — making the rest of the RAG pipeline cleaner. The text splitter handles edge cases (Unicode normalisation, sentence-boundary detection) that we'd otherwise re-implement.

**Alternatives considered.** **Write our own loaders.** For PDFs, use `pypdf` directly (which we already do as a fallback). For CSVs, use `pandas`. We could do this — but LangChain's loaders normalise the output shape, which makes downstream code simpler. We deliberately do *not* use LangChain's `Chain` classes, `LCEL`, or `RunnableLambda` — those abstractions are powerful but opinionated, and LangGraph (J.2) is the more appropriate orchestration layer.

**Where used.** [omnillm/rag/pipeline.py](../omnillm/rag/pipeline.py) for document loading and chunking.

\newpage

## J.5 — sentence-transformers

**What it is.** A Python library that turns text into embedding vectors using small (~100 MB), fast, locally-runnable models. Default model: `all-MiniLM-L6-v2` (384-dimensional embeddings, 23 MB on disk).

**Why we picked it.** ChromaDB's default embedding is `all-MiniLM-L6-v2` from sentence-transformers — **fast (~5 ms per short text on CPU), small, and free**. No need to pay OpenAI for embeddings during indexing. The model is multilingual-aware enough for the DIBRIS knowledge base.

**Alternatives considered.** **OpenAI's `text-embedding-3-small` API** — higher-quality embeddings (~10–15% better on the MTEB benchmark), $0.02 per million tokens, requires internet. For a small lab KB of ~50 chunks, the quality difference does not justify the cost or the cloud round-trip. **Cohere embeddings** — similar trade-off. **BGE-large** (sentence-transformers can load it) — 5× larger, ~3× slower, marginally better; not worth it at our scale.

**Where used.** Indirectly via ChromaDB.

\newpage

## J.6 — OpenAI Whisper

**What it is.** A speech-to-text model trained by OpenAI on 680,000 hours of multilingual audio. Available as a downloadable model (`pip install openai-whisper`) **or** via the OpenAI cloud API. OmniLLM uses the local download.

**Why we picked it.** Best-in-class accuracy at the **multilingual** level, robust to noise, free if you run it locally. Pepper's onboard `ALSpeechRecognition` is widely regarded as unusable for open-domain speech. Running Whisper locally also keeps participant audio off third-party servers — a meaningful GDPR concern.

**Alternatives considered.** **Vosk** (lighter, fully offline, lower accuracy on Italian/French). **Google Speech-to-Text API** (cloud, faster, GDPR-flagged). **Faster-Whisper** (a 4× faster C++ port — recommended for production deployments but adds setup complexity). For a research prototype, plain Whisper is the right pick.

**Where used.** [omnillm/robotics/whisper_stt.py](../omnillm/robotics/whisper_stt.py). Called by the agent graph's `transcribe_audio` node and by the `/transcribe` HTTP endpoint.

\newpage

## J.7 — asyncio

**What it is.** Python's **standard-library** module for non-blocking I/O. `async def` declares a coroutine; `await` pauses it until an I/O operation completes; `asyncio.gather(...)` runs many coroutines concurrently.

**Why we picked it.** LLM calls are I/O-bound — most of the time is spent waiting for the network. Asyncio lets us query 5 models in the wall-clock time of the slowest one, not the sum. Condition D's 3-model council finishes in ~1.8 s instead of ~5.4 s thanks to this single design choice.

**Alternatives considered.** **Threading** — works but introduces GIL contention and shared-state bugs. **multiprocessing** — overkill for I/O work, slow startup, no easy state sharing. **Trio** / **Curio** — better async APIs in some respects but smaller ecosystems; LangGraph and litellm both use asyncio. For pure-I/O work, asyncio wins.

**Where used.** Pervasive — [gateway.py](../omnillm/gateway.py), [consensus.py](../omnillm/consensus.py), [evaluator.py](../omnillm/evaluator.py), [agent_graph.py](../omnillm/hri/agent_graph.py), [server/app.py](../omnillm/server/app.py), [robotics/pepper.py](../omnillm/robotics/pepper.py).

\newpage

## J.8 — Flask

**What it is.** A minimalist Python web framework. Serves HTTP endpoints with decorators (`@app.route("/path", methods=[...])`).

**Why we picked it.** Tiny, well-documented, easy to test, single-worker is the right concurrency model for one robot. The synchronous-to-async bridge (`_run_async`) inside the Flask app is six lines of code.

**Alternatives considered.** **FastAPI** (async-native, faster, more modern) — genuinely better for high-throughput services with auto-generated OpenAPI docs. We didn't pick it because Flask's simplicity matched the single-robot single-worker use case, and the dependency footprint is smaller (Flask + Jinja vs FastAPI + Pydantic + Starlette + uvicorn). **Bottle** — even smaller than Flask but less mature ecosystem. **Django** — orders of magnitude too heavy. If you ever serve many robots simultaneously, swap to FastAPI + uvicorn (the migration is ~30 lines).

**Where used.** [omnillm/server/app.py](../omnillm/server/app.py). Six endpoints.

\newpage

## J.9 — Click

**What it is.** A Python library for building command-line interfaces with decorators (`@click.command`, `@click.option`, `@click.group`). Auto-generates `--help`.

**Why we picked it.** Better than `argparse` (less boilerplate per command), supports nested command groups (`omnillm ask`, `omnillm evaluate`, `omnillm leaderboard`), auto-generates type-aware `--help` text, and integrates cleanly with `rich` for coloured output.

**Alternatives considered.** **Typer** (built on Click, uses type hints — slightly nicer for greenfield projects). Genuinely tempting; we stayed on Click for consistency with the broader Python ecosystem where Click is more familiar. **argparse** (stdlib, more verbose). **Fire** (auto-generates CLI from any Python class — magic, opinionated).

**Where used.** [omnillm/cli.py](../omnillm/cli.py). Every `omnillm` subcommand.

\newpage

## J.10 — Rich

**What it is.** A Python library for beautiful coloured terminal output — tables, panels, progress bars, syntax-highlighted code, markdown rendering, tracebacks.

**Why we picked it.** OmniLLM's CLI is a research dashboard. A coloured table of model latencies is dramatically more readable than `print(dict)`. Rich is the de-facto standard for Python CLI UX in 2026.

**Alternatives considered.** **tabulate** (tables only, ASCII-art). **prettytable** (similar to tabulate). **Plain `print()`** (grey, unreadable for long output). None of these get close to Rich's quality.

**Where used.** [omnillm/cli.py](../omnillm/cli.py). Every command that emits structured output.

\newpage

## J.11 — Ollama

**What it is.** A free local LLM runtime. `ollama serve` starts a daemon on `localhost:11434`; `ollama pull llama3:8b` downloads a model; `ollama list` shows what's installed. Exposes an OpenAI-compatible HTTP API.

**Why we picked it.** Free, private, fast on a laptop with a GPU (and acceptable on CPU). The Condition B (Fixed Local LLM) experimental condition **depends on it** — without Ollama there is no "no-API-key baseline." The OpenAI-compatible API means LiteLLM speaks to it via the same `openai/` prefix machinery.

**Alternatives considered.** **vLLM** (faster, GPU-required, more setup). **LM Studio** (GUI, less scriptable). **GGUF + llama.cpp** directly (more control, more setup). **Text-Generation-WebUI** (heavyweight). Ollama is the easiest for a research lab and the only one with one-line install on Windows.

**Where used.** Via LiteLLM in [omnillm/gateway.py](../omnillm/gateway.py). Models registered in [config/models.yaml](../config/models.yaml) with `provider: ollama`. Required for Condition B.

\newpage

## J.12 — ReportLab + xhtml2pdf

**What they are.** Two pure-Python libraries that together produce PDFs from HTML. **xhtml2pdf** orchestrates: it accepts an HTML string + CSS and emits a PDF. **ReportLab** does the actual page-laying-out. We register **DejaVu Sans + DejaVu Sans Mono** with ReportLab so Unicode glyphs (arrows, box-drawing characters, accented Latin) render correctly inside the PDF.

**Why we picked them.** **No native dependencies** (no `libgobject`, Pango, Cairo, or wkhtmltopdf binary) — installable on Windows with pip alone. WeasyPrint produces visually better output but requires GTK on Windows which is a multi-hour install per machine. xhtml2pdf is the **lowest-friction choice** for cross-platform PDF generation.

**Alternatives considered.** **WeasyPrint** (best quality, needs GTK). **wkhtmltopdf** (good quality, separate ~100 MB binary, increasingly bit-rotted). **mPDF** (PHP). **LaTeX** (best quality, huge install, complex source files). For a thesis-supporting reference book that must be rebuildable in five minutes on any machine, xhtml2pdf wins.

**Where used.** [book2/build_pdf.py](../book2/build_pdf.py). Run after editing any of the 16 source files.

\newpage

## J.13 — pytest, pytest-asyncio, pytest-mock

**What they are.** The Python testing trinity. **pytest** is the framework; **pytest-asyncio** runs `async def test_…` functions; **pytest-mock** provides the `mocker` fixture for patching dependencies.

**Why we picked them.** Standard in the Python ecosystem. The 289 tests in [tests/](../tests/) run in ~5 seconds without a single real API call — because pytest-mock fakes out the LLM calls and the robot bridge. This is how the codebase can be CI'd on a laptop with zero LLM cost and zero hardware.

**Alternatives considered.** **unittest** (stdlib, more verbose, worse fixtures). **nose2** (largely abandoned). **Hypothesis** for property-based tests (we use a tiny bit, indirectly, via `pytest-randomly` for ordering robustness). pytest is the only framework in active mainstream Python use.

**Where used.** [tests/](../tests/). All 11 test files.

\newpage

## J.14 — pyyaml

**What it is.** Python's YAML parser. Reads `.yaml` files into nested Python dicts/lists.

**Why we picked it.** YAML is the right format for the model registry and benchmark tasks: human-editable, comment-friendly, supports lists and nested dicts without the verbosity of XML. pyyaml is the canonical Python parser.

**Alternatives considered.** **ruamel.yaml** (preserves comments on round-trip — useful for code-modifying-YAML, irrelevant for us). **TOML** (no nested-list support, weaker for the routing config). **JSON** (no comments — disqualifying for human-edited configs).

**Where used.** [omnillm/gateway.py](../omnillm/gateway.py) and [omnillm/router.py](../omnillm/router.py) load [config/models.yaml](../config/models.yaml).

\newpage

## J.15 — python-dotenv

**What it is.** Loads environment variables from a `.env` file into the process's `os.environ`. Called once at startup.

**Why we picked it.** API keys must never be hard-coded or committed to git. The standard pattern is `.env.example` (committed, no real keys) plus a local `.env` (in `.gitignore`, contains real keys). python-dotenv reads `.env` so application code can `os.environ.get("OPENAI_API_KEY")` without knowing where it came from.

**Alternatives considered.** **Reading the keys from a YAML config** — pulls them into a file format we already use, but makes accidental commits more likely. **OS-level env vars** — works but requires the user to set them in their shell profile, which is platform-specific.

**Where used.** Imported once in [omnillm/cli.py](../omnillm/cli.py) and [omnillm/server/app.py](../omnillm/server/app.py).

\newpage

## J.16 — aiohttp

**What it is.** A Python library for asynchronous HTTP — both client and server. The async equivalent of `requests`.

**Why we picked it.** [omnillm/robotics/pepper.py](../omnillm/robotics/pepper.py) is async (because LangGraph is async). The bridge client therefore needs an async HTTP library. `requests` is synchronous and would block the event loop.

**Alternatives considered.** **httpx** (similar feature set; we briefly evaluated it). **Curl-via-subprocess** (would work, ugly). aiohttp was the first to mature and is what LiteLLM also uses internally.

**Where used.** [omnillm/robotics/pepper.py](../omnillm/robotics/pepper.py) — `_post`, `_get`, `_ping_bridge_server`.

\newpage

## J.17 — markdown (the python-markdown library)

**What it is.** Python's most-popular Markdown → HTML converter. Supports extensions: `tables`, `fenced_code`, `codehilite` (syntax highlighting), `toc` (auto table of contents), `sane_lists`.

**Why we picked it.** Used by [book2/build_pdf.py](../book2/build_pdf.py) to turn the assembled `OmniLLM_Book.md` into HTML before xhtml2pdf renders it to PDF. The extension list above is the canonical "reads like GitHub Markdown" config.

**Alternatives considered.** **mistune** (faster). **commonmark-py** (stricter CommonMark). **pandoc** (best quality but requires the pandoc binary, defeats the pure-Python promise). For our scale, the difference is invisible.

**Where used.** [book2/build_pdf.py](../book2/build_pdf.py).

\newpage

## J.18 — pypdf

**What it is.** Python library for reading and (limited) writing of PDF files. OmniLLM uses only the reading side: extracting text per page from PDF documents in the knowledge base.

**Why we picked it.** Pure Python, no native dependencies, handles the PDF formats we encounter. ChromaDB's persistence already pulls in a SQLite dependency; we wanted the PDF reading path to add no new native deps.

**Alternatives considered.** **PyMuPDF** (`fitz`) — faster, better quality, requires native build chain. **pdfplumber** (better at tables). **pdf2text** subprocess (Linux-only). For occasional PDF indexing during RAG setup, pypdf is sufficient.

**Where used.** [omnillm/rag/pipeline.py](../omnillm/rag/pipeline.py) — `_index_pdf` method.

\newpage

## J.19 — langdetect

**What it is.** A Python port of Google's language-detection library. Statistical n-gram classifier; supports ~55 languages.

**Why we picked it.** A backup signal in [omnillm/hri/language_detector.py](../omnillm/hri/language_detector.py). The first-pass language detection is Unicode-script-based (super fast); the second pass is high-frequency-word matching for Latin-script languages; **langdetect** is the third-tier fallback when the first two fail.

**Alternatives considered.** **fasttext-langid** (better accuracy, larger model — but adds a 1 GB binary). **whisper-detect-language** (Whisper itself returns a language probability — we could use this, but only after transcription; the rule-based path is faster and works without audio). **langid.py** (similar feature set, less maintained).

**Where used.** [omnillm/hri/language_detector.py](../omnillm/hri/language_detector.py) — `_try_langdetect()` fallback.

\newpage

## J.20 — Why We Did NOT Use…

A short anti-resume:

| Library | Why we did not use it |
|---|---|
| **LangChain Chains, LCEL, RunnableLambda** | LangGraph (J.2) is the more appropriate orchestration layer; LangChain's chains are opinionated and easy to outgrow. |
| **ROS / ROS 2** | 4–8 GB install footprint; Python version trap (ROS 1 = Py2, ROS 2 = Py3.8+); cross-platform fragility. The HTTP bridge is sufficient at our scale. |
| **Docker** | Adds setup friction for a single-developer thesis project. The repo runs with `pip install -e .` and that's it. A `Dockerfile` is a one-day add-on if needed. |
| **Pydantic** | We use plain `@dataclass` everywhere. Pydantic gives us runtime validation we don't need for trusted internal data, at the cost of an extra dependency and slower import time. |
| **Celery / RQ** | No background-job queue is needed; the interaction-per-request shape fits Flask's sync model. |
| **Redis** | No cross-process state to share. ChromaDB's SQLite file is the only persistent state. |
| **PostgreSQL / any RDBMS** | All persistent data is small enough to live in JSON-Lines + CSV files. The analysis pipeline (Chapter 30) loads them into pandas. |
| **scikit-learn / PyTorch / TensorFlow** | We are *evaluating* models, not training them. Adding ML frameworks would imply we should be training, which we explicitly are not. |

The pattern: **OmniLLM is intentionally small.** Every dependency must earn its place by being the most-direct solution to a real problem, not a "we might need this later" hedge.

\newpage
