# PART VIII — APPENDICES

\newpage

## Appendix A — Python Primer (Just the Parts You Need for OmniLLM)

This is **not** a Python tutorial. It is a focused tour of the *specific*
Python features OmniLLM uses heavily, so you can read the source code
fluently. If you are already comfortable with `async`, dataclasses, type
hints, and dictionary literals, skip this appendix.

### A.1  Type Hints

Modern Python adds optional type annotations:

```python
def add(a: int, b: int) -> int:
    return a + b

names: list[str] = ["Alice", "Bob"]
config: dict[str, int] = {"port": 5000}
maybe_value: str | None = None       # might be a str, might be None
```

OmniLLM uses these everywhere. They are **not enforced at runtime** —
they are documentation that tools (mypy, your IDE) can verify. When you
see `model_id: str` it means "this argument should be a string"; the code
won't crash if you pass something else, but you should not.

### A.2  Dataclasses

`@dataclass` auto-generates `__init__`, `__repr__`, equality:

```python
from dataclasses import dataclass, field

@dataclass
class Point:
    x: float
    y: float
    z: float = 0.0          # default value
    tags: list[str] = field(default_factory=list)   # default mutable

p = Point(1.0, 2.0)        # Point(x=1.0, y=2.0, z=0.0, tags=[])
print(p)                    # nice automatic repr
```

OmniLLM's `ModelResponse`, `RobotAction`, `EvalTask`, `InteractionRecord`
are all dataclasses. Look for `@dataclass` to identify them.

### A.3  Async / Await

LLM calls are I/O-bound; you wait for the network. Async lets one
program do other useful work during the wait:

```python
import asyncio

async def fetch_one(url: str) -> str:
    # imagine this calls an LLM
    await asyncio.sleep(1)              # simulate 1 s of network wait
    return f"Response for {url}"

async def main() -> None:
    # Sequential — takes 3 s total
    a = await fetch_one("a"); b = await fetch_one("b"); c = await fetch_one("c")

    # Concurrent — takes 1 s total
    a, b, c = await asyncio.gather(
        fetch_one("a"), fetch_one("b"), fetch_one("c"),
    )

asyncio.run(main())
```

Rules:

- `async def` declares a function that *returns a coroutine*. Calling it
  produces a coroutine; `await` runs it.
- Inside an `async def`, you can `await` other coroutines.
- Outside any async function, you call `asyncio.run(main())` to start
  the event loop.
- `asyncio.gather(c1, c2, c3)` runs three coroutines concurrently and
  returns their results in order.

OmniLLM's `LLMGateway.query_multiple` uses exactly this pattern.

### A.4  F-Strings

Modern string formatting:

```python
name = "Pepper"
n = 42
print(f"Hello {name}, your number is {n}.")             # plain
print(f"Cost: ${cost:.6f}")                              # 6 decimal places
print(f"Latency: {latency_ms:.0f}ms")                    # 0 decimals
print(f"Score: {score:.2%}")                             # as percentage
```

### A.5  Dictionary Literals and Unpacking

```python
config = {"port": 5000, "host": "0.0.0.0"}

# Lookup with default
port = config.get("port", 8000)

# Merge
default = {"port": 8000, "debug": False}
merged = {**default, **config}        # config wins where keys overlap

# Iterate
for key, value in config.items():
    print(key, value)
```

OmniLLM's models registry is a deeply nested dict; you'll see lots of
`.get(key, default)` calls because YAML files don't always have every
optional field.

### A.6  Decorators

Functions that wrap other functions:

```python
def log_calls(func):
    def wrapper(*args, **kwargs):
        print(f"calling {func.__name__}")
        return func(*args, **kwargs)
    return wrapper

@log_calls
def greet(name):
    return f"Hello {name}"

greet("Alice")    # prints "calling greet" then returns "Hello Alice"
```

In OmniLLM you'll see `@dataclass`, `@click.command(...)`, `@app.route(...)`.
Each is a decorator that transforms the function below it.

### A.7  Click (CLI Framework)

```python
import click

@click.group()
def cli():
    """My CLI."""

@cli.command("greet")
@click.argument("name")
@click.option("--loud", is_flag=True)
def greet_cmd(name: str, loud: bool):
    msg = f"Hello {name}"
    if loud: msg = msg.upper()
    click.echo(msg)

if __name__ == "__main__":
    cli()
```

OmniLLM's CLI follows this pattern — `cli.py` defines a Click `group()`
and adds many commands.

### A.8  Flask (Web Framework)

```python
from flask import Flask, jsonify, request

app = Flask(__name__)

@app.route("/health")
def health():
    return jsonify({"status": "ok"})

@app.route("/echo", methods=["POST"])
def echo():
    data = request.get_json(force=True)
    return jsonify({"received": data})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
```

OmniLLM's `server/app.py` is a larger version of this — many endpoints,
each registered with `@app.route`.

### A.9  Context Managers (`with`)

Used for setup/teardown around a block:

```python
with open("file.txt", "r") as fh:
    data = fh.read()
# fh is automatically closed here, even if an exception was raised
```

OmniLLM uses `with open(...)` for all file I/O, and `async with` for
HTTP sessions in the bridge code.

### A.10  Imports You Will See Often

```python
from __future__ import annotations          # all type hints are strings (no fwd-ref issues)
from dataclasses import dataclass, field    # data classes
from pathlib import Path                    # cross-platform paths
from typing import Any, Literal, TYPE_CHECKING
                                            # type-check-only annotations
import asyncio, json, time, re              # standard library
import yaml                                 # PyYAML, the YAML loader
import litellm                              # LiteLLM provider gateway
from rich.console import Console            # coloured terminal output
from rich.table import Table
import click                                # CLI framework
```

\newpage

## Appendix B — Complete Terminal Command Reference

This is the unified cheat-sheet. Every command you might run while
working with OmniLLM, in one place.

### B.1  Install

```bash
git clone https://github.com/Akshita-sr/OmniLLM.git
cd OmniLLM
python -m venv .venv
source .venv/bin/activate                       # Linux / macOS
.venv\Scripts\activate                          # Windows CMD
.venv\Scripts\Activate.ps1                      # Windows PowerShell

pip install -e ".[dev]"                         # core only
pip install -e ".[dev,robotics]"                # + Flask
pip install -e ".[dev,hri]"                     # + RAG, LangGraph
pip install -e ".[all]"                         # everything

cp .env.example .env                            # then edit with API keys
pip install openai-whisper                      # local STT (optional)

curl -fsSL https://ollama.com/install.sh | sh   # Ollama (Linux/macOS)
ollama pull llama3:8b                           # ~4.7 GB, free local
ollama pull qwen2.5:7b                          # multilingual, ~4.4 GB
ollama pull mistral:7b                          # ~4.1 GB
ollama pull deepseek-r1:14b                     # reasoning, ~9 GB
```

### B.2  Verify

```bash
omnillm --version
omnillm models
omnillm models --type local
omnillm models --type cloud
pytest tests/ -v
pytest tests/ --cov=omnillm --cov-report=term-missing
```

### B.3  CLI — Talk to Models

```bash
omnillm ask "Hello" -m openai-gpt4o-mini
omnillm ask "Explain RAG" -m claude-haiku -m gemini-flash
omnillm ask "What is 2+2?" --all                    # all registered

omnillm route "Where is Room 305?" --strategy TASK_TYPE
omnillm route "Quick yes/no" --strategy LOWEST_COST --budget 0.001
omnillm route "Hard reasoning task" --strategy BEST_QUALITY

omnillm council "Is consciousness emergent?"
omnillm council "What is justice?" --strategy synthesis
omnillm council "P=NP?" --strategy majority_vote -m openai-gpt4o -m claude-sonnet -m gemini-2.5-pro
```

### B.4  CLI — Evaluate

```bash
omnillm evaluate                                # default cloud models, all categories
omnillm evaluate -m openai-gpt4o-mini
omnillm evaluate -c reasoning
omnillm evaluate -m claude-haiku -c code
omnillm evaluate -o results/eval_2026-05.json

omnillm compare "Write a haiku about robots"
omnillm compare "Debug this code" --model-a openai-gpt4o --model-b claude-sonnet
```

### B.5  CLI — Reports

```bash
omnillm leaderboard
omnillm leaderboard --category reasoning
omnillm leaderboard --category embodied_hri
omnillm costs

omnillm export --format csv      --input results/eval.json -o results/eval.csv
omnillm export --format markdown --input results/eval.json -o results/eval.md
omnillm export --format json     --input results/eval.json -o results/full.json
```

### B.6  AI Server

```bash
python -m omnillm.server.app
python -m omnillm.server.app --host 0.0.0.0 --port 5000
python -m omnillm.server.app --debug
python -m omnillm.server.app --no-rag
python -m omnillm.server.app --model claude-haiku
python -m omnillm.server.app --kb /path/to/your/knowledge_base

# Production-ish
gunicorn 'omnillm.server.app:create_app()' --bind 0.0.0.0:5000 --workers 1

# Smoke tests
curl http://localhost:5000/health
curl http://localhost:5000/status
curl -X POST http://localhost:5000/interact \
     -H "Content-Type: application/json" \
     -d '{"text":"Hello","participant_id":"T","condition":"A"}'
curl http://localhost:5000/export > results/all.json
```

### B.7  NAOqi Client (Python 2.7)

Windows CMD:

```bat
set PYTHONPATH=C:\pynaoqi\pynaoqi-python2.7-2.5.5.5-win32-vs2013\lib;%PYTHONPATH%
set PATH=C:\pynaoqi\pynaoqi-python2.7-2.5.5.5-win32-vs2013\lib;%PATH%

C:\Python27\python.exe omnillm\server\naoqi_client.py ^
    --robot-ip 192.168.1.100 ^
    --robot-port 9559 ^
    --server-ip 192.168.1.50 ^
    --server-port 5000 ^
    --participant P001 ^
    --condition C
```

Bash:

```bash
export PYTHONPATH="/c/pynaoqi/pynaoqi-python2.7-2.5.5.5-win32-vs2013/lib:$PYTHONPATH"
/c/Python27/python.exe omnillm/server/naoqi_client.py \
    --robot-ip 192.168.1.100 \
    --server-ip 192.168.1.50 \
    --participant P001 \
    --condition C
```

### B.8  Quick NAOqi One-Liners (Python 2.7)

```bat
:: Wake up
C:\Python27\python.exe -c "from naoqi import ALProxy; ALProxy('ALMotion','192.168.1.100',9559).wakeUp()"

:: Speak
C:\Python27\python.exe -c "from naoqi import ALProxy; ALProxy('ALAnimatedSpeech','192.168.1.100',9559).say('Hello!')"

:: Wave
C:\Python27\python.exe -c "from naoqi import ALProxy; ALProxy('ALBehaviorManager','192.168.1.100',9559).runBehavior('animations/Stand/Gestures/Hey_1')"

:: Eyes blue
C:\Python27\python.exe -c "from naoqi import ALProxy; ALProxy('ALLeds','192.168.1.100',9559).fadeRGB('FaceLeds',0.0,0.67,1.0,0.5)"

:: Battery
C:\Python27\python.exe -c "from naoqi import ALProxy; print(ALProxy('ALBattery','192.168.1.100',9559).getBatteryCharge())"
```

### B.9  Tests

```bash
pytest tests/ -v
pytest tests/test_gateway.py -v
pytest tests/test_router.py -v
pytest tests/test_consensus.py -v
pytest tests/test_evaluator.py -v
pytest tests/test_scorer.py -v
pytest tests/test_rag.py -v
pytest tests/test_hri.py -v
pytest tests/test_gesture_planner.py -v
pytest tests/test_experiment_logger.py -v
pytest tests/test_new_components.py -v
pytest tests/ --cov=omnillm --cov-report=html
```

\newpage

## Appendix C — Complete Glossary

A consolidated alphabetical glossary. Every term used in the book.

| Term | Definition |
|------|------------|
| **agent graph** | A directed graph of `async` functions sharing state. OmniLLM's lives in `hri/agent_graph.py`. |
| **`ALAnimatedSpeech`** | NAOqi service that speaks with synchronised body gestures. |
| **`ALAudioDevice`** | NAOqi service for microphone capture. |
| **`ALBehaviorManager`** | NAOqi service for running pre-installed behaviour animations. |
| **`ALLeds`** | NAOqi service for LED control. |
| **`ALMemory`** | NAOqi key-value store and event bus. |
| **`ALMotion`** | NAOqi service for joint control. `wakeUp()` enables motors. |
| **API key** | Secret string proving you have an account with a provider. |
| **async / await** | Python syntax for non-blocking I/O. `await` pauses for an I/O-bound operation. |
| **`asyncio.gather`** | Runs many coroutines concurrently. |
| **base64** | ASCII encoding of binary bytes; used to put audio in JSON. |
| **`bodyLanguageMode`** | `ALAnimatedSpeech` config option: `contextual`, `random`, or `disabled`. |
| **bridge (architecture)** | A layer that connects two incompatible systems. OmniLLM has the Python 2.7 ↔ Python 3 bridge. |
| **`Choregraphe`** | SoftBank's drag-and-drop IDE for Pepper / NAO. |
| **ChromaDB** | Pure-Python embedded vector database used by the RAG pipeline. |
| **chunk** | A short slice of a longer document, the unit of retrieval. OmniLLM uses 512-char with 64 overlap. |
| **CLI** | Command-line interface. OmniLLM's CLI is built with Click and Rich. |
| **Click** | Python library for building CLIs. Used in `cli.py`. |
| **closure** | A function that has captured variables from its enclosing scope. Used in `agent_graph.py`'s `_make_*_node`. |
| **condition (experimental)** | One of A, B, C, D, E in the Embodied LLM Arena. |
| **consensus** | Querying multiple models and combining their answers. See `consensus.py`. |
| **counterbalancing** | Varying the order of conditions across participants to cancel order effects. |
| **dataclass** | Python decorator (`@dataclass`) that auto-generates `__init__`, etc. |
| **embedding** | List of floats encoding the semantic meaning of text. |
| **embodiment effect** | HRI finding that the same AI text is rated differently when delivered through a robot vs a screen. |
| **ELO** | Rating system from chess; +100 ≈ 64% expected win rate. Used in `scorer.py`. |
| **evaluator** | LLM-as-Judge component. Three patterns: referenceless, reference-based, pairwise. |
| **f-string** | Python 3.6+ string formatting: `f"hello {name}"`. |
| **faithfulness** | How well a response uses the retrieved RAG context. 0–1, scored by judge LLM. |
| **Flask** | Python web framework. OmniLLM's AI server is a Flask app. |
| **gateway** | The unified LLM access layer. `gateway.py` in OmniLLM. |
| **gesture planner** | Maps task type + response text → gesture name + LED hex. `robotics/gesture_planner.py`. |
| **Godspeed** | Bartneck et al.'s validated 5-subscale HRI questionnaire. |
| **hallucination** | When an LLM states something not in the retrieved context. |
| **HRI** | Human-Robot Interaction; an academic field. |
| **HTTP** | The protocol used between OmniLLM's server and Pepper's NAOqi client. |
| **Jaccard similarity** | Intersection-over-union of word sets. Used in consensus clustering. |
| **JSON** | JavaScript Object Notation; OmniLLM's universal serialisation format. |
| **judge model** | The LLM used to evaluate responses in LLM-as-Judge. Default GPT-4o. |
| **K-factor** | ELO volatility constant; OmniLLM uses 32. |
| **knowledge base** | Documents indexed for RAG. Lives in `knowledge_base/`. |
| **LangChain** | Framework for LLM apps. OmniLLM uses it for document loaders. |
| **LangGraph** | LangChain's library for stateful multi-node agents. Used in `hri/agent_graph.py`. |
| **Latin square** | Counterbalancing design where each condition appears once in each ordinal position. |
| **latency** | Time from request to response, in ms. |
| **Likert scale** | 1–7 (or 1–5) rating of agreement. |
| **LiteLLM** | Python library exposing 100+ LLM providers under one API. The foundation of `gateway.py`. |
| **LLM** | Large Language Model. Examples: GPT-4o, Claude Sonnet, Gemini Flash, Llama 3. |
| **LLM-as-Judge** | Using one LLM to score another's response. Three patterns in OmniLLM. |
| **Llama 3** | Meta's open-weight LLM. Used as Condition B's local baseline. |
| **majority_vote** | Consensus strategy: pick the cluster with the most members. |
| **`ModelResponse`** | OmniLLM's universal LLM-response dataclass. Defined in `gateway.py`. |
| **NAO** | Pepper's smaller (58 cm) sibling. Same NAOqi OS. |
| **NAOqi** | Pepper / NAO's middleware OS. Service broker on port 9559. Python 2.7 only. |
| **Ollama** | Free local LLM runtime. `localhost:11434`. |
| **pairwise** | Judge pattern: compare two responses, pick the better. |
| **participant session** | One participant under one condition. UUID-tagged. |
| **Pepper** | 120 cm humanoid social robot from SoftBank Robotics. |
| **position bias** | LLM judges' tendency to prefer the first response shown. |
| **provider** | Company / service hosting an LLM. OpenAI, Anthropic, Google, etc. |
| **`pynaoqi`** | The Python 2.7 binding to NAOqi. |
| **RAG** | Retrieval-Augmented Generation. Search documents, prepend to prompt. |
| **referenceless** | Judge pattern: score quality without a gold answer. |
| **reference-based** | Judge pattern: compare to a known-correct answer. |
| **Rich** | Python library for coloured terminal output. Used in `cli.py`. |
| **`RobotAction`** | OmniLLM's universal action dataclass: speech + gesture + LED + movement. |
| **`RobotBridge`** | Abstract base class for robot integrations. |
| **router** | Component that picks the best model. `router.py`. |
| **session** | One participant's interaction under one condition. UUID-tagged. |
| **smart routing** | Strategy-based model selection. Six strategies in OmniLLM. |
| **SmartRouter** | The class implementing smart routing. |
| **STT** | Speech-to-Text. OmniLLM uses Whisper. |
| **synthesis** | Consensus strategy: a judge LLM combines multiple responses. |
| **T1–T4** | The four HRI task types: info_retrieval, navigation, social_conversation, multilingual. |
| **task category** | Evaluation axis. OmniLLM has 8 (reasoning, knowledge, code, instruction, safety, robot, latency, cost). |
| **temperature** | LLM sampling parameter. 0 = deterministic, 1 = creative. |
| **token** | Sub-word unit. LLMs charge per 1 million tokens. |
| **TTFT** | Time-To-First-Token. How long before the LLM starts streaming. |
| **TTS** | Text-to-Speech. OmniLLM uses Pepper's `ALAnimatedSpeech`. |
| **vector store** | Database storing embeddings + supporting similarity search. |
| **virtual environment** | Isolated Python sandbox per project. `.venv/` after `python -m venv .venv`. |
| **WAV** | Audio format used for transport. 16 kHz mono PCM in OmniLLM. |
| **WebSocket** | Persistent bi-directional protocol; used by Buddy bridge. |
| **Whisper** | OpenAI's open-source speech-to-text model. |
| **within-subjects design** | Every participant experiences every condition. |
| **YAML** | Human-readable config file format. `config/models.yaml`. |

\newpage

## Appendix D — Troubleshooting Reference

Solution-first table. If you see the symptom, apply the fix.

### D.1  Install / Environment

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| `command not found: omnillm` | venv not activated, or `pip install -e` failed | activate, then `pip install -e ".[dev]"` |
| `ModuleNotFoundError: chromadb` | `[hri]` extra not installed | `pip install -e ".[hri]"` |
| `ModuleNotFoundError: flask` | `[robotics]` extra not installed | `pip install -e ".[robotics]"` |
| `ModuleNotFoundError: langgraph` | same | `pip install -e ".[hri]"` |
| `ModuleNotFoundError: openai-whisper` | not installed (it's optional) | `pip install openai-whisper` |
| `python: command not found` | python not on PATH | reinstall, check "Add to PATH" |
| Tests fail with import errors | venv mixing | rebuild: `rm -rf .venv && python -m venv .venv && pip install -e ".[all]"` |

### D.2  API Keys / Providers

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| `APIConnectionError` | wrong key or no internet | check `.env`; try `curl https://api.openai.com` |
| `Error code: 401` | invalid key | regenerate key in provider's portal |
| `Error code: 429` | rate limit | wait, retry; reduce `max_concurrent` |
| `BadRequestError: model not found` | YAML model name doesn't match provider | check `config/models.yaml`'s `model:` field |
| Ollama: connection refused | `ollama serve` not running | `ollama serve` in a terminal |
| Ollama returns instant gibberish | model not pulled | `ollama pull <name>` |

### D.3  Server / HTTP

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| `curl: connection refused` to localhost:5000 | server not running | `python -m omnillm.server.app` |
| `400 Bad Request: provide 'text' or 'audio'` | empty body | include at least one field |
| `500 Internal Server Error` | exception in handler | check server logs (run with `--debug`) |
| Server hangs on first `/interact` | LangGraph importing slowly | wait ~10 s on first call (lazy import) |
| Knowledge base loaded — 0 chunks | KB directory empty or wrong path | check `--kb` flag, `OMNILLM_KNOWLEDGE_BASE` env |

### D.4  Pepper / NAOqi

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| `import naoqi`: ModuleNotFoundError | wrong PYTHONPATH | `set PYTHONPATH=C:\pynaoqi\...\lib;%PYTHONPATH%` |
| `import naoqi`: DLL load failed | missing PATH for `lib/` | also add `lib/` to PATH |
| Cannot connect to Pepper | wrong IP / not on same Wi-Fi | re-press chest button; ping IP |
| Pepper speaks but does not move | no stiffness | `motion.wakeUp()` first |
| `ALAnimatedSpeech` says nothing | volume zero / robot rest | check Pepper volume; wakeUp |
| Behaviour not installed | not uploaded to robot | Choregraphe → Upload to robot |
| Choregraphe virtual robot won't start | port 9559 in use | kill leftover NAOqi process; restart Choregraphe |

### D.5  RAG

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| RAG returns empty chunks | KB not indexed | check server logs for "Knowledge base loaded — N chunks" |
| Faithfulness score is `-1.0` | scoring is off by default | pass `score_faithfulness=True` to `query()` |
| Slow RAG queries | ChromaDB persistent on slow disk | use in-memory mode (`persist_directory=None`) |
| Hallucination always flagged | heuristic too strict | use `_score_faithfulness` instead |

### D.6  Tests

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| Tests need API keys | shouldn't — they mock | pull latest, ensure `pytest-mock` installed |
| `pytest: command not found` | `[dev]` extra not installed | `pip install -e ".[dev]"` |
| Coverage report blank | not running with `--cov` | `pytest tests/ --cov=omnillm` |

\newpage

## Appendix E — External Resources

A curated list of papers, repositories, and documentation.

### E.1  LLM Evaluation

- Hendrycks et al. (2021), *Measuring Massive Multitask Language Understanding*. The original MMLU paper.
- Zheng et al. (2023), *Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena*. arXiv:2306.05685.
- White et al. (2024), *LiveBench: A Challenging, Contamination-Free LLM Benchmark*.
- Liu et al. (2024), *G-Eval: NLG Evaluation using GPT-4 with Better Human Alignment*. arXiv:2412.05579 survey.
- LMSYS Chatbot Arena: <https://chat.lmsys.org/?leaderboard>

### E.2  HRI / Embodied LLMs

- Wainer et al. (2006), *The Role of Physical Embodiment in HRI*. Used in Chapter 2.
- Li (2015), *The Benefit of Being Physically Present: A Survey of Experimental Works Comparing Copresent Robots, Telepresent Robots and Virtual Agents*.
- Bartneck et al. (2009), *Measurement Instruments for the Anthropomorphism, Animacy, Likeability, Perceived Intelligence, and Perceived Safety of Robots*. The Godspeed paper.
- Irfan et al. (2024 HRI Workshop), *Between Reality and Delusion: Challenges of Applying LLMs to Social Robots*.
- Nichols et al. (2024 arXiv), *Can ChatGPT Control a Pepper Robot Adequately?*.
- Grassi et al. (2024 HAI), *ChatGPT-based Pepper Robot for Restaurant Service*.
- Spitale et al. (2024 arXiv), *Vita: An LLM-Powered Social Robot for Wellbeing*.
- Billing et al. (2024 Frontiers), *Language Models for Human-Robot Interaction*.

### E.3  RAG and Vector Stores

- Lewis et al. (2020), *Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks*. The original RAG paper.
- ChromaDB: <https://www.trychroma.com>.
- LangChain: <https://python.langchain.com>.
- Sentence-Transformers: <https://www.sbert.net>.

### E.4  LangGraph and Agent Frameworks

- LangGraph: <https://langchain-ai.github.io/langgraph/>.
- *LangGraph Architecture and Design*, Medium 2024.
- *LangGraph in 2026: Build Multi-Agent AI Systems*, dev.to 2026.

### E.5  LiteLLM and Provider Tooling

- LiteLLM: <https://github.com/BerriAI/litellm>.
- *LiteLLM Routing & Load Balancing Documentation*: <https://docs.litellm.ai/docs/routing>.
- Ollama: <https://ollama.com>.

### E.6  Pepper / NAO / Choregraphe

- SoftBank Developer Portal (NAOqi 2.5 docs): <https://developer.softbankrobotics.com>.
- Aldebaran NAOqi documentation: <http://doc.aldebaran.com/2-5/index.html>.
- *Pepper Robot NAOqi Python SDK*, ProvenRobotics.
- *Pepper Robot + ChatGPT Real-World Interactions*, BransonBots 2025.
- ROS2 NAOqi driver: <https://github.com/ros-naoqi/naoqi_driver2>.

### E.7  Github Repositories You May Want to Browse

| Repository | What |
|------------|------|
| `Akshita-sr/OmniLLM` | This project |
| `BerriAI/litellm` | The provider gateway library |
| `langchain-ai/langgraph` | The agent graph library |
| `chroma-core/chroma` | The vector store |
| `ollama/ollama` | Local LLM runtime |
| `openai/whisper` | Speech-to-text |
| `ilabsweden/pepperchat` | Reference Pepper-LLM project (2023) |
| `UoA-CARES/Pepper-GPT` | University of Auckland, socket-based |
| `studerus/pepper-android-realtime-chat` | NAOqi 2.9 / Android, state-of-art (HRI 2026) |
| `ros-naoqi/naoqi_driver2` | ROS2 bridge for NAOqi |
| `ros-naoqi/pepper_robot` | Pepper meta-package for ROS |

\newpage

## Appendix F — File Index

Every file in the repository, one line each.

### F.1  Top-Level

| File | Purpose |
|------|---------|
| `README.md` | Project front page |
| `GETTING_STARTED.md` | Beginner setup guide |
| `EXPLANATION.md` | File-by-file explanation |
| `ARCHITECTURE.md` | Architecture reference with diagrams |
| `PEPPER_CHOREGRAPHE_GUIDE.md` | Pepper-specific walk-through |
| `OmniLLM_Complete_Beginners_Guide.md` | Choregraphe virtual-robot path |
| `LICENSE` | MIT licence text |
| `pyproject.toml` | Package metadata, dependency extras |
| `requirements.txt` | Flat dependency list |
| `.env.example` | API-key template |
| `.gitignore` | Git ignore patterns |

### F.2  `config/`

| File | Purpose |
|------|---------|
| `config/models.yaml` | The model registry (★ 19 models) |
| `config/tasks/reasoning.yaml` | Reasoning eval tasks |
| `config/tasks/knowledge.yaml` | Knowledge eval tasks |
| `config/tasks/code.yaml` | Code eval tasks |
| `config/tasks/instruction.yaml` | Instruction-following tasks |
| `config/tasks/safety.yaml` | Safety / refusal tasks |
| `config/tasks/robot.yaml` | Robot-readiness tasks |

### F.3  `omnillm/` — Core

| File | Purpose | Lines |
|------|---------|------:|
| `omnillm/__init__.py` | Public API re-exports | 56 |
| `omnillm/gateway.py` | LLMGateway, ModelResponse | 271 |
| `omnillm/router.py` | SmartRouter, RoutingStrategy | 372 |
| `omnillm/consensus.py` | ConsensusEngine, 3 strategies | 409 |
| `omnillm/evaluator.py` | LLM-as-Judge, 3 patterns | 423 |
| `omnillm/scorer.py` | EloScorer | 286 |
| `omnillm/cli.py` | Click + Rich terminal dashboard | 549 |

### F.4  `omnillm/hri/`

| File | Purpose | Lines |
|------|---------|------:|
| `omnillm/hri/__init__.py` | Re-exports + lazy LangGraph import | 73 |
| `omnillm/hri/classifier.py` | T1–T4 task classifier | 335 |
| `omnillm/hri/language_detector.py` | Three-tier language detection | 288 |
| `omnillm/hri/experiment.py` | Conditions, sessions, manager | 339 |
| `omnillm/hri/agent_graph.py` | LangGraph 9-node pipeline | 608 |

### F.5  `omnillm/rag/`

| File | Purpose | Lines |
|------|---------|------:|
| `omnillm/rag/__init__.py` | Re-exports | 39 |
| `omnillm/rag/pipeline.py` | RAGPipeline, ChromaDB + fallback | 553 |

### F.6  `omnillm/robotics/`

| File | Purpose | Lines |
|------|---------|------:|
| `omnillm/robotics/__init__.py` | Re-exports | 33 |
| `omnillm/robotics/bridge.py` | Abstract bridge + RobotAction | 253 |
| `omnillm/robotics/pepper.py` | Pepper HTTP bridge | 235 |
| `omnillm/robotics/nao.py` | NAO HTTP bridge | 208 |
| `omnillm/robotics/buddy.py` | Buddy WebSocket bridge | 246 |
| `omnillm/robotics/gesture_planner.py` | Task → gesture mapping | 200 |
| `omnillm/robotics/whisper_stt.py` | Whisper STT (local + API) | 219 |

### F.7  `omnillm/server/`

| File | Purpose | Lines |
|------|---------|------:|
| `omnillm/server/__init__.py` | Package docstring | 16 |
| `omnillm/server/app.py` | Flask AI server (Python 3) | 437 |
| `omnillm/server/naoqi_client.py` | NAOqi client (Python 2.7) | 360 |

### F.8  `omnillm/tasks/`

| File | Purpose | Lines |
|------|---------|------:|
| `omnillm/tasks/__init__.py` | Re-exports | 33 |
| `omnillm/tasks/loader.py` | YAML / JSON task loader | 183 |
| `omnillm/tasks/sample_tasks.py` | 8 axes of built-in tasks | 349 |

### F.9  `omnillm/utils/`

| File | Purpose | Lines |
|------|---------|------:|
| `omnillm/utils/__init__.py` | Re-exports | 25 |
| `omnillm/utils/cost_tracker.py` | CostTracker | 184 |
| `omnillm/utils/experiment_logger.py` | ExperimentLogger, InteractionRecord | 393 |
| `omnillm/utils/questionnaire.py` | Likert + Godspeed + pairwise + observer | 388 |
| `omnillm/utils/export.py` | CSV / JSON / Markdown / Rich | 188 |

### F.10  `knowledge_base/`

| File | Purpose |
|------|---------|
| `knowledge_base/lab_info.txt` | Lab location, hours, WiFi, safety |
| `knowledge_base/faq.txt` | Frequently asked questions |
| `knowledge_base/visitor_profiles.csv` | Visitor names, roles, schedules |
| `knowledge_base/event_schedule.csv` | Seminars, deadlines |
| `knowledge_base/research_projects.txt` | Active research project descriptions |
| `knowledge_base/university_map.txt` | Building layout, directions |

### F.11  `tests/`

| File | What it tests |
|------|---------------|
| `tests/__init__.py` | Empty marker |
| `tests/test_gateway.py` | LLMGateway: model strings, costs, query |
| `tests/test_router.py` | All 6 routing strategies |
| `tests/test_evaluator.py` | All 3 judge patterns |
| `tests/test_scorer.py` | ELO math, leaderboard |
| `tests/test_consensus.py` | All 3 consensus strategies |
| `tests/test_rag.py` | Indexing, retrieval, faithfulness |
| `tests/test_hri.py` | Classifier, language detector, experiment |
| `tests/test_gesture_planner.py` | Task → gesture mapping |
| `tests/test_experiment_logger.py` | InteractionRecord + filters + CSV |
| `tests/test_new_components.py` | Agent graph, Whisper, questionnaire, server |

### F.12  Auto-Created at Runtime

| Path | What |
|------|------|
| `.venv/` | Virtual environment |
| `results/` | Eval JSON files, exported reports, KB persistence |
| `__pycache__/` | Python bytecode caches |

\newpage

## Appendix G — Field Notes: Bringing OmniLLM up on Windows 11

This appendix captures the gotchas and fixes discovered while standing
OmniLLM up end-to-end on a Windows 11 laptop talking to Choregraphe's
virtual Pepper. None of this is exotic — but every one of these consumed
hours the first time. They're written down so future-you doesn't lose the
same hours.

### G.1  Choregraphe's "Connect to..." dialog gotcha

When you launch Choregraphe it auto-spawns a virtual Pepper in the
background on a random port (e.g. 56471). The title bar may say
*"Connected to a virtual robot"*, but **external Python clients cannot
talk to that auto-spawned instance** — only Choregraphe itself can.

To make the virtual robot reachable from your scripts:

1. Top menu → **Connection** → **Connect to...**
2. **Untick** both "Use fixed port" and "Use fixed IP/hostname".
3. Click on the robot in the list (named after your user, e.g. *AKSHITA*).
4. Click **Select**.

After this the title bar says *"Connected to AKSHITA"* (or your user
name). Only now can `omnillm`/`demo_pepper_omnillm.py`/etc. open a NAOqi
session.

**The port shown in the dialog changes every Choregraphe restart.** Note
it and pass it via `--robot-port`. The "Use fixed port" checkbox does
**not** start a new server on the fixed port; it only changes the
*target* of subsequent connection attempts.

### G.2  Windows 11 TCP loopback bug in NAOqi 2.5

Symptom: After a successful TCP connect, the very first RPC call
(`tts.say(...)`, even `tts.getLanguage()`) fails with:

```text
RuntimeError: ALTextToSpeech::getLanguage  Socket is not connected
```

Diagnosis: Windows 11's TCP fast-path for `127.0.0.1` interacts badly
with NAOqi 2.5's qimessaging reply socket. The connection appears
established at the kernel level but the qi handshake silently drops.
The same code against a *real* Pepper at a LAN IP (e.g. 192.168.x.x)
works perfectly — the bug is specific to loopback on Win11.

Workaround: use the older `naoqi` ALBroker API with an explicit listen
IP of `127.0.0.1`, instead of `qi.Application` or `qi.Session()`:

```python
from naoqi import ALBroker, ALProxy

broker = ALBroker("myBroker", "127.0.0.1", 0, ROBOT_IP, ROBOT_PORT)
try:
    tts = ALProxy("ALTextToSpeech")
    tts.say("Hello")
finally:
    broker.shutdown()
```

The 2nd argument (`"127.0.0.1"`) forces NAOqi's reply listener onto the
loopback interface only. For real Pepper, set it to `"0.0.0.0"` instead
so the robot can reach back via LAN.

`scripts/pepper_demo/demo_pepper_omnillm.py` chooses the right value
automatically based on `--robot-ip`. `omnillm/server/naoqi_client.py`
supports both modes via the `--use-broker` flag.

### G.3  LangGraph 1.x replaces dict state instead of merging

OmniLLM uses LangGraph's `StateGraph(dict)` as its agent state container.
In LangGraph 1.0–1.2 (the version installed today), each node's return
**replaces** the entire state by default; it does not merge keys. The
graph was originally written expecting accumulation behaviour, which
caused every RPC to come back as `{"speech": ""}` even though every node
ran and the LLM completed successfully.

Fix in `omnillm/hri/agent_graph.py`: wrap every node with a `_merge_state`
helper so it returns `{**state, **delta}` instead of just `delta`:

```python
def _merge_state(fn):
    async def wrapped(state):
        delta = await fn(state)
        return {**state, **delta} if isinstance(delta, dict) else state
    return wrapped

builder.add_node("classify_task", _merge_state(_make_classify_task_node()))
# ... wrap every node the same way
```

If you upgrade to a LangGraph version that supports `Annotated` reducers
on the state schema, you can revert this wrapper and use the official
mechanism instead.

### G.4  Three module-signature mismatches inside the graph

When the graph wrapper above was applied, three latent bugs surfaced
because nodes started running through to completion:

| Caller | Wrong call | Correct call |
|--------|------------|--------------|
| `_make_rag_node` | `rag.query(utterance, model_id=...)` | `rag.query(utterance)` |
| `_make_smart_router_node` (C) | `route_for_hri_task(task_type=..., strategy=...)` | `route_for_hri_task(hri_task_type=...)` |
| `_make_smart_router_node` (D) | `ConsensusEngine(gateway=...)` + `engine.query(models, msgs)` + `resp.synthesis` | `ConsensusEngine(gateway=..., config=ConsensusConfig(council_models=...))` + `engine.query_council(msgs)` + `resp.final_answer` |

All three are fixed in the current source.

### G.5  Defensive fallback in `app.py`

Even after G.3 and G.4, if a graph node hits an unexpected error the user
still gets a usable response. `omnillm/server/app.py` now treats an
empty `robot_action.speech` as "graph failed silently" and falls back to
the direct gateway call:

```python
action = result.get("robot_action") or {"speech": result.get("response_text", "")}
if not action.get("speech"):
    logger.warning("LangGraph returned empty speech — falling back.")
    # falls through to _fallback_interact(...)
else:
    return jsonify(action)
```

This is belt-and-braces insurance for live demos.

### G.6  The `scripts/pepper_demo/` folder

Three small files live here:

| File | Python | Purpose |
|------|--------|---------|
| `demo_pepper_omnillm.py` | 2.7 | Default mode: full AI demo (server → Pepper). With `--check-only`: bridge sanity test only. |
| `test_all_conditions.py` | 3.x | Batch tests all 5 experimental conditions + multilingual against the AI server. Writes `test_results.txt`. |
| `README.md` | – | How to run everything. |

These do not depend on any code in `omnillm/` other than the live HTTP
endpoint at `localhost:5000`. They are deliberately self-contained so a
demo-day failure in one part doesn't break the others.

### G.7  Always invoke the right Python interpreter

On Windows, `python` on PATH is whatever interpreter the user installed
most recently — often Python 3. The NAOqi side **must** run under
Python 2.7 (NAOqi 2.5 was never ported). Always invoke it by full path:

```cmd
C:\Python27\python.exe scripts\pepper_demo\demo_pepper_omnillm.py
```

The Python 3 side (`python -m omnillm.server.app`) should be run from
the project venv where `pip install -e .` has been executed.

\newpage

## Closing Note

You have reached the end of the book. By now you should be able to:

- **Explain** in plain English what OmniLLM is, why it exists, and what
  the robot adds (Parts I, II, VII).
- **Read** any source file and know what each function does without
  guessing (Part III).
- **Connect** to a Pepper robot (or simulate one in Choregraphe) and
  drive it through the AI server (Part IV, V).
- **Re-build** the project from scratch in a sensible order if you ever
  needed to (Part VI).
- **Run** an experimental session, collect the data, and analyse it
  (Chapter 32, 38).
- **Look up** any term, command, or file in seconds (Appendices).

The codebase will continue to evolve; this book will not. When the book
and the source disagree, **trust the source**. The book's job was to
get you fluent enough that you can read the source for yourself.

Good luck with the thesis. And remember that the most interesting result
might be the one you didn't predict — Embodied LLM rankings might agree
with text rankings, or they might not. Both findings advance the field.

— *End of book.*

\newpage
