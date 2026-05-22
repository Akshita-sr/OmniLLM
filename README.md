# OmniLLM

> Multi-LLM orchestration for the **Pepper humanoid robot** in the Sgorbissa HRI lab (DIBRIS, University of Genoa). Type or talk to Pepper; the right LLM is picked per task and the answer comes back as speech + gesture + LED colour.

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Tests](https://img.shields.io/badge/tests-221%20passing-brightgreen.svg)](#testing)

---

## What this repo does

1. You give an utterance (typed in the terminal or spoken into your laptop mic).
2. The HRI pipeline detects the language, classifies the task (info / navigation / social / multilingual), picks the right LLM, and (if useful) grounds the answer in the DIBRIS knowledge base.
3. The reply is sent to Pepper — either the **real Pepper** at the lab or a **virtual Pepper** in Choregraphe on your laptop.

```
[ Mic / Keyboard ]
       │ run.py
       ▼
[ Flask AI server  :5000 ]    ────►  process_interaction()
       │                              ├─ LanguageDetector
       │                              ├─ HRITaskClassifier (T1–T4)
       │                              ├─ RAG (ChromaDB over knowledge_base/)
       │                              ├─ Council mode (optional, 3-LLM synthesis)
       │                              └─ GesturePlanner
       ▼
[ PepperBridge ]  ─POST /action─►  [ NAOqi bridge (Py2.7)  :6000 ]
                                         │ ALBroker
                                         ▼
                                   [ Pepper or Choregraphe :62763 / :9559 ]
```

---

## Quick start (Windows 11)

### 1. One-time install

```powershell
.\venv\Scripts\Activate.ps1
pip install -e .[all]
python -m omnillm.rag.builder --rebuild
```

The builder writes verified DIBRIS / Sgorbissa content to `knowledge_base/`, attempts to fetch the live UniGE pages, and re-embeds everything into ChromaDB at `.chroma_store/`. Failed URLs leave stub `.md` files you can fill in manually — nothing is fabricated.

### 2. Lock the Choregraphe virtual-robot port (one-time)

In Choregraphe: **Edit → Preferences → Virtual Robot → "Use fixed port" = 62763 → relaunch the virtual robot**.

Without this step the bridge can't find Choregraphe and falls back to stub mode (responses still print, but Pepper stays silent).

### 3. Run it (three terminals)

| Terminal | Role | Command |
|---|---|---|
| **T1** | AI server (Python 3 venv) | `python -m omnillm.server.app --port 5000` |
| **T2** | NAOqi bridge (Python 2.7) — Choregraphe | `C:\Python27\python.exe omnillm\server\naoqi_bridge_server.py --robot-ip 127.0.0.1 --robot-port 62763 --bind 127.0.0.1 --bridge-port 6000` |
| **T3** | Driver (Python 3 venv) | `python run.py text` &nbsp;&nbsp;_or_&nbsp;&nbsp; `python run.py mic` |

For **real Pepper** at the lab, only T2 changes:

```powershell
C:\Python27\python.exe omnillm\server\naoqi_bridge_server.py --robot-ip <PEPPER_LAN_IP> --robot-port 9559 --bind 0.0.0.0 --bridge-port 6000
```

### 4. Talk to Pepper

```text
> What time does the lab open?
  Pepper: Visitors should contact Prof. Sgorbissa to confirm — the lab is typically staffed from 09:00 on weekdays.
  [task=info_retrieval, lang=en, model=openai-gpt4o-mini, 980ms]

> Ciao, dove si trova il laboratorio?
  Pepper: Ciao! Il laboratorio si trova in Via Dodecaneso 35, al piano terra dell'edificio DIBRIS, sulla destra.
  [task=multilingual, lang=it, model=claude-haiku, 1320ms]
```

In `mic` mode press **Enter** to start recording and **Enter** again to stop. Output mode is the same as text mode (Pepper speaks + gestures).

---

## `run.py` flags

```text
python run.py text                          # type prompts
python run.py mic                           # press Enter to record / stop
python run.py text --council                # 3-LLM council instead of single model
python run.py mic  --stt local              # local faster-whisper instead of OpenAI API
python run.py text --no-pepper              # skip robot output (responses printed)
python run.py text --robot-ip 192.168.1.42 --robot-port 9559   # real Pepper
```

---

## File map

```
omnillm/
├── gateway.py          # LiteLLM wrapper — single .query() across 15+ models
├── router.py           # Smart routing: BEST_QUALITY / LOWEST_COST / TASK_TYPE / …
├── evaluator.py        # LLM-as-judge (referenceless / reference / pairwise)
├── consensus.py        # Multi-LLM council (majority vote / weighted / judge synthesis)
├── scorer.py           # ELO leaderboard
├── cli.py              # `omnillm` CLI (models, evaluate, council, route, leaderboard)
│
├── hri/
│   ├── classifier.py        # Rule-based T1–T4 classifier
│   ├── language_detector.py # Unicode script + n-gram language detection
│   └── pipeline.py          # Async process_interaction() — the HRI brain
│
├── rag/
│   ├── pipeline.py     # ChromaDB ingest + retrieve + answer
│   └── builder.py      # KB rebuilder (fetches DIBRIS, re-embeds)
│
├── robotics/
│   ├── bridge.py       # RobotAction dataclass + abstract RobotBridge
│   ├── pepper.py       # Python 3 HTTP client of the NAOqi bridge
│   ├── audio.py        # Mic capture + Whisper STT (API or local)
│   └── gesture_planner.py
│
├── server/
│   ├── app.py                  # Flask AI server (Python 3)
│   └── naoqi_bridge_server.py  # NAOqi bridge (Python 2.7)
│
└── utils/
    ├── experiment_logger.py
    ├── cost_tracker.py
    └── export.py

config/models.yaml       # Model registry + routing config
knowledge_base/          # DIBRIS / Sgorbissa-lab content (.md, .csv)
.chroma_store/           # Persisted ChromaDB index (generated, gitignored)
tests/                   # pytest suite (221 passing)
run.py                   # Unified text/mic launcher
```

---

## Server API

| Method | Path | Body | Returns |
|---|---|---|---|
| `GET`  | `/health` | – | `{"status": "ok", "version": "0.2.0"}` |
| `GET`  | `/status` | – | server config + model list |
| `POST` | `/interact` | `{"text": "...", "council": false}` or `{"audio": "<base64 WAV>", "stt_backend": "api"}` | RobotAction dict |
| `POST` | `/transcribe` | `{"audio": "<base64 WAV>", "backend": "api"}` | `{"text": "...", "language": "en"}` |
| `POST` | `/evaluate` | `{"session_id": "...", "participant_id": "...", "scores": {...}}` | `{"status": "ok"}` |
| `GET`  | `/export` | – | all logged interactions |

The RobotAction dict:

```json
{
  "speech": "The lab is on your left.",
  "gesture": "point_left",
  "emotion_led": "#00AAFF",
  "metadata": {
    "task_type": "navigation",
    "language": "en",
    "model_id": "claude-haiku",
    "latency_ms": 1320.7,
    "council": false,
    "rag_used": true
  }
}
```

---

## Adding a new LLM

Add it to `config/models.yaml`:

```yaml
my-new-model:
  id: my-new-model
  provider: anthropic
  model: claude-opus-4-7
  api_key_env: ANTHROPIC_API_KEY
  cost_per_1m_input: 15.00
  cost_per_1m_output: 75.00
  type: cloud
  hri_strengths: ["social_conversation"]
```

Restart the server and it's available everywhere (gateway, router, council, CLI).

---

## Testing

```powershell
pytest -q
```

221 tests pass, no internet required (every LLM call is mocked).

---

## Knowledge base

Rebuild any time:

```powershell
python -m omnillm.rag.builder --rebuild
```

What goes in `knowledge_base/`:

- `dibris.md`, `sgorbissa.md`, `faq.md`, `links.md` — verified content (baked into the builder so they always exist)
- `dibris_home_fetched.md`, `sgorbissa_rubrica_fetched.md`, `sgorbissa_researchgate_fetched.md` — live fetches; stubs when the URL fails

Edit any `.md` (or drop in `.txt` / `.csv` / `.pdf`) and re-run the builder to re-embed.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `PepperBridge mode=stub` despite Choregraphe running | The virtual-robot port isn't 62763. Lock it in Choregraphe → Edit → Preferences → Virtual Robot → "Use fixed port" = 62763 → relaunch. |
| `Indexed 0 chunks` at server start | `knowledge_base/` is empty. Run `python -m omnillm.rag.builder --rebuild`. |
| `Socket is not connected` from NAOqi on Windows 11 | NAOqi loopback bug — the bridge already uses the `ALBroker("127.0.0.1", 0, …)` workaround, but make sure Choregraphe is **Connected to a named virtual robot** (not "Connected to a virtual robot"). |
| `openai.AuthenticationError` | `.env` missing `OPENAI_API_KEY`. Copy `.env.example` to `.env` and fill in. |
| `python run.py mic` fails with PortAudio error | `pip install sounddevice` plus make sure a default mic exists in Windows Sound settings. |
| Italian (or other non-English) prompts answered in English | Use `run.py mic` (Whisper detects the language) or include enough non-English words to trip the text-based detector. |

---

## License

MIT. See [LICENSE](LICENSE).
