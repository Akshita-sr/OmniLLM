\newpage

# Appendix A — Python Primer: Just the Parts You Need for OmniLLM

> *This appendix is for the reader who knows what `print()` does and can write `for x in [1,2,3]`, but has not used `async`/`await`, dataclasses, type hints, virtual environments, or context managers. Everything you need to read every line of the OmniLLM source. If you already know modern Python, skip to Appendix B.*

\newpage

## A.1 — Virtual Environments (`venv`)

When you `pip install` a package, it normally goes into your system's Python installation. That's bad for two reasons:

1. **Version conflicts.** Project A needs `flask==1.1.4`. Project B needs `flask==3.0.0`. They can't coexist system-wide.
2. **Permissions.** Some systems require admin/sudo to install system-wide packages.

A **virtual environment** is a self-contained Python installation inside one directory. You activate it; while active, every `pip install` goes into that directory, and every `python` invocation finds packages from there. Deactivate it (or close the terminal), and your system Python is unchanged.

```powershell
python -m venv venv                # creates a "venv" directory
.\venv\Scripts\Activate.ps1        # activate (Windows)
source venv/bin/activate           # activate (mac/Linux)
deactivate                          # leave the venv
```

When the venv is active, your prompt typically shows `(venv)` at the front. Every script in this book assumes you have activated the venv first.

## A.2 — Type Hints

Python is **dynamically typed**: a variable's type is whatever you most recently assigned to it. But since Python 3.5, you can *annotate* types as documentation (and as input to tools like `mypy`):

```python
def add(a: int, b: int) -> int:
    return a + b

name: str = "Akshita"
ages: list[int] = [21, 22, 25]
config: dict[str, int] = {"port": 5000, "timeout": 30}
```

Important: **Python does not enforce these annotations at runtime.** They are documentation that an IDE and type checker can verify. You can pass a `str` to `add(a, b)` and Python won't object — it will just blow up when it tries to do `+`.

Modern OmniLLM annotations:

| Hint | Means |
|---|---|
| `int`, `str`, `bool`, `float`, `bytes` | The standard primitives |
| `list[int]` | A list of ints |
| `dict[str, Any]` | Dict from str to anything |
| `Optional[X]` or `X \| None` | Either an X or None |
| `Callable[[int], str]` | A function that takes an int and returns a str |
| `Literal["A", "B"]` | One of the specific values listed |
| `Any` | "I don't want to commit to a type" |

`from __future__ import annotations` (used in almost every OmniLLM file) is a deferred-evaluation pragma — it means all type hints are stored as strings, so forward references (e.g. `def foo() -> "LLMGateway"`) work without circular-import gymnastics.

## A.3 — Dataclasses

A dataclass is the boilerplate-free way to write "a class that mostly just holds some named fields":

```python
from dataclasses import dataclass, field

@dataclass
class ModelResponse:
    model_id: str
    content: str
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    metadata: dict = field(default_factory=dict)
```

The `@dataclass` decorator auto-generates:
- `__init__(self, model_id, content, input_tokens=0, ...)`
- `__repr__` (a useful string representation)
- `__eq__` (equal if all fields are equal)

`field(default_factory=dict)` is the right way to default to a mutable type. Writing `metadata: dict = {}` would mean *all instances share the same dict* — a classic Python gotcha.

OmniLLM uses dataclasses for every record type: `ModelResponse`, `RobotAction`, `RobotSensorData`, `InteractionRecord`, `RouteDecision`, `DocumentChunk`, `RAGResponse`, `LanguageDetectionResult`, `ClassificationResult`, `ConditionConfig`, `ParticipantSession`, `InteractionQuestionnaire`, `GodspeedResponse`, `PairwisePreference`, `ObserverRating`.

## A.4 — `async` and `await`

A normal Python function runs to completion before returning. An `async` function returns a *coroutine* — a paused piece of work that you must `await` for it to actually execute.

```python
import asyncio

async def fetch(url: str) -> str:
    # ...network I/O here...
    return "response body"

async def main():
    text = await fetch("https://example.com")
    print(text)

asyncio.run(main())
```

The magic happens when you have *many* I/O-bound operations to do in parallel:

```python
async def main():
    results = await asyncio.gather(
        fetch("https://example.com/a"),
        fetch("https://example.com/b"),
        fetch("https://example.com/c"),
    )
```

The three fetches run concurrently. Total wall-clock = `max(t_a, t_b, t_c)`, not their sum. **This is exactly how OmniLLM's `query_multiple` runs three LLM calls in parallel for Condition D's council.**

Things that bite you:

- You cannot `await` outside an `async def`.
- You cannot call a regular function with `await`. (You can call an `async def` with regular `()`, but it returns a coroutine object that does nothing until awaited.)
- Don't `time.sleep()` inside an async function — it blocks the whole event loop. Use `await asyncio.sleep()` instead.

## A.5 — Context Managers (`with`)

The `with` statement guarantees that cleanup code runs when a block ends, even if an exception is raised inside:

```python
with open("data.txt") as fh:
    contents = fh.read()
# file is automatically closed here, even if read() raised
```

OmniLLM uses context managers for file I/O, network sockets (`socket.socket(...)`), and aiohttp sessions (`async with aiohttp.ClientSession(...) as session:`).

You can write your own:

```python
from contextlib import contextmanager

@contextmanager
def timer(label: str):
    import time
    t0 = time.time()
    yield
    print(f"{label}: {time.time() - t0:.2f}s")

with timer("RAG retrieval"):
    chunks = rag.retrieve(query)
```

## A.6 — `pathlib.Path`

The modern replacement for string-based path manipulation. Instead of `os.path.join(a, b, c)`, you write `Path(a) / b / c`. Cross-platform — `\` vs `/` is handled automatically.

```python
from pathlib import Path

repo_root = Path(__file__).parent.parent
kb_dir = repo_root / "knowledge_base"
for txt_file in kb_dir.glob("*.txt"):
    text = txt_file.read_text(encoding="utf-8")
```

OmniLLM uses `pathlib.Path` exclusively. Never `os.path`. Never raw strings for paths.

## A.7 — Decorators

A decorator is a function that takes a function and returns a (usually modified) function. The `@name` syntax is shorthand:

```python
def loud(fn):
    def wrapped(*args, **kwargs):
        print(f"Calling {fn.__name__}")
        return fn(*args, **kwargs)
    return wrapped

@loud
def add(a, b):
    return a + b

add(2, 3)   # prints "Calling add", then returns 5
```

OmniLLM uses decorators for:

- `@dataclass` — class decoration (above)
- `@app.route("/health", methods=["GET"])` — Flask URL routing
- `@property` — turn a method into a read-only attribute
- `@classmethod`, `@staticmethod` — class-level methods
- `@pytest.fixture` — define a reusable test fixture
- `@abstractmethod` — mark a method as required-by-subclasses on an ABC

## A.8 — `*args` and `**kwargs`

`*args` collects positional arguments into a tuple; `**kwargs` collects keyword arguments into a dict:

```python
def query(model_id, *args, **kwargs):
    print(model_id)            # the first positional
    print(args)                # any other positionals as a tuple
    print(kwargs)              # any keyword args as a dict
    return litellm.completion(**kwargs)   # unpack the dict back into kwargs

query("openai-gpt4o-mini", temperature=0.7, max_tokens=100)
# model_id = "openai-gpt4o-mini"
# args = ()
# kwargs = {"temperature": 0.7, "max_tokens": 100}
```

The `**kwargs` pattern is heavily used in `gateway.py` to pass provider-specific options through to LiteLLM without enumerating every possible parameter.

## A.9 — `Enum` and `Literal`

Two ways to type a value as "one of a fixed set":

```python
from enum import Enum

class RoutingStrategy(str, Enum):
    BEST_QUALITY = "BEST_QUALITY"
    LOWEST_COST = "LOWEST_COST"
    # ...

s = RoutingStrategy.BEST_QUALITY
print(s.value)  # "BEST_QUALITY"
print(s == "BEST_QUALITY")  # True (because it inherits from str)
```

For lighter-weight cases where you only need the type hint:

```python
from typing import Literal

Mode = Literal["server", "direct", "stub"]

def use_mode(m: Mode) -> None: ...
```

`Mode` is not a class; it's just a type alias. `use_mode("server")` works; `use_mode("hello")` would be flagged by `mypy` but still runs.

## A.10 — `abc.ABC` and `@abstractmethod`

Abstract base classes declare a contract that subclasses must fulfill:

```python
from abc import ABC, abstractmethod

class RobotBridge(ABC):
    @abstractmethod
    async def connect(self) -> bool: ...
    @abstractmethod
    async def execute_action(self, action) -> bool: ...

class PepperBridge(RobotBridge):
    async def connect(self) -> bool:
        # ... real implementation ...
        return True
    async def execute_action(self, action):
        # ... real implementation ...
        return True

# bridge = RobotBridge()   # TypeError: cannot instantiate abstract class
bridge = PepperBridge()   # OK
```

If you forget to implement an abstract method in a subclass, the error fires at *instance construction time* — not at method-call time. That's the safety net.

## A.11 — F-Strings

The modern Python string-formatting syntax:

```python
name = "Akshita"
age = 22
print(f"Hello {name}, you are {age} years old.")
print(f"Hex: {255:#04x}")     # "Hex: 0xff" — same format specifiers as %-format
print(f"Pi to 3dp: {3.14159:.3f}")
```

You can put any expression inside the `{}`:

```python
print(f"Sum: {2+3}")
print(f"Model count: {len(gateway.list_models())}")
```

The `=` flag (Python 3.8+) auto-shows the expression name:

```python
x = 42
print(f"{x=}")     # "x=42"
```

## A.12 — Reading the Type-Hint-Heavy Source

When you open a file like `gateway.py` and the first non-import line is:

```python
async def query(
    self,
    model_id: str,
    messages: list[dict[str, str]],
    temperature: float = 0.7,
    max_tokens: int = 2048,
) -> ModelResponse:
```

That's a single function signature spread across lines for readability. Parse it as:

- *`async def`* — coroutine function (must be `await`ed)
- *`query`* — method name
- *`self`* — first arg is the instance (it's a method on a class)
- *`model_id: str`* — second arg is a string
- *`messages: list[dict[str, str]]`* — third arg is a list of dicts that map string-to-string
- *`temperature: float = 0.7`* — fourth arg is a float with default `0.7`
- *`max_tokens: int = 2048`* — fifth arg, default `2048`
- *`-> ModelResponse:`* — returns an instance of `ModelResponse`

Reading dense type-hinted Python is a skill that comes quickly with practice. The hints help you, even if you're not using a type checker.

\newpage
