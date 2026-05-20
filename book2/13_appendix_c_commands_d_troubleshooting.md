\newpage

# Appendix C — Complete Terminal Command Reference

> *Every command used anywhere in the book, organised by goal. PowerShell first; Bash equivalent below when different.*

\newpage

## C.1 — Project Setup

```powershell
# Clone
cd C:\Users\akshi\OneDrive\Desktop
git clone https://github.com/Akshita-sr/OmniLLM.git
cd OmniLLM

# Create + activate virtual environment
python -m venv venv
.\venv\Scripts\Activate.ps1                 # PowerShell
# source venv/bin/activate                  # Bash

# Install
pip install --upgrade pip
pip install -e ".[all]"                     # all extras

# (Optional) Set up env
Copy-Item .env.example .env
notepad .env                                # PowerShell
# nano .env                                 # Bash

# (Optional) Ollama
ollama --version
ollama pull llama3.2:3b
ollama pull qwen2.5:7b
ollama serve

# Verify
omnillm --version
omnillm models
pytest tests/ -q
```

## C.2 — The AI Server

```powershell
# Default — listen on 0.0.0.0:5000 for LAN access
python -m omnillm.server.app --host 0.0.0.0 --port 5000

# Localhost only (development)
python -m omnillm.server.app --host 127.0.0.1 --port 5000

# Disable RAG (faster startup; not for the study)
python -m omnillm.server.app --no-rag

# Different default model
python -m omnillm.server.app --model llama3-8b-local

# Different knowledge base directory
python -m omnillm.server.app --kb knowledge_base\_legacy_irai

# Flask debug mode (auto-restarts on code change)
python -m omnillm.server.app --debug
```

## C.3 — The NAOqi Bridge Server (Python 2.7)

```powershell
# Real Pepper at DIBRIS
C:\Python27\python.exe omnillm\server\naoqi_bridge_server.py `
    --robot-ip 192.168.1.42 --robot-port 9559 `
    --bind 0.0.0.0 --bridge-port 6000

# Choregraphe virtual robot (port varies per launch)
C:\Python27\python.exe omnillm\server\naoqi_bridge_server.py `
    --robot-ip 127.0.0.1 --robot-port 49959 `
    --bind 0.0.0.0 --bridge-port 6000
```

## C.4 — The NAOqi Client (Topology 1; Three Triggers)

```powershell
# Text trigger (works on virtual robot too)
C:\Python27\python.exe omnillm\server\naoqi_client.py `
    --robot-ip 127.0.0.1 --robot-port 49959 `
    --trigger text --condition A

# Touch trigger (real Pepper only; head touch triggers 5s capture)
C:\Python27\python.exe omnillm\server\naoqi_client.py `
    --robot-ip 192.168.1.42 `
    --trigger touch --record-seconds 5 `
    --condition C --track-face

# VAD trigger (real Pepper only; continuous energy-gated)
C:\Python27\python.exe omnillm\server\naoqi_client.py `
    --robot-ip 192.168.1.42 `
    --trigger vad --condition C
```

## C.5 — The Demo Scripts

```powershell
# NAOqi sanity check (no AI; robot only)
C:\Python27\python.exe scripts\pepper_demo\demo_pepper_omnillm.py `
    --check-only --robot-port 49959

# Single-shot demo (AI -> robot)
C:\Python27\python.exe scripts\pepper_demo\demo_pepper_omnillm.py `
    --condition A --rag --question "What time does the lab open?" `
    --robot-port 49959

# Batch test all 5 conditions × 4 tasks (no robot needed)
python scripts\pepper_demo\test_all_conditions.py

# Proof that routing routes correctly
python scripts\pepper_demo\proof_of_routing.py
```

## C.6 — The Experiment Driver

```powershell
# Full subject session, real robot
.\venv\Scripts\python.exe scripts\pepper_demo\run_subject_experiment.py `
    --participant P003 `
    --server http://127.0.0.1:5000 `
    --bridge http://127.0.0.1:6000

# Full subject session, no robot (driver dry-run)
.\venv\Scripts\python.exe scripts\pepper_demo\run_subject_experiment.py `
    --participant P000-dryrun `
    --server http://127.0.0.1:5000 `
    --no-robot
```

## C.7 — The CLI

```powershell
omnillm models                                          # list all models
omnillm models --type cloud                             # cloud-only
omnillm models --type local                             # local-only (Ollama)

omnillm ask "Hello" -m openai-gpt4o-mini                # one model
omnillm ask "Hello" -m openai-gpt4o-mini -m claude-haiku  # multiple
omnillm ask "Hello" --all                                # every registered model

omnillm route "Where is Room 305?" --strategy TASK_TYPE  # smart-route
omnillm route "Quick yes/no" --strategy LOWEST_COST --budget 0.001

omnillm council "What is consciousness?"                # 3-model consensus
omnillm council "Is P=NP?" --strategy majority_vote
omnillm council "Climate" -m openai-gpt4o -m claude-sonnet -m gemini-2.5-pro

omnillm compare "Write a poem" --model-a openai-gpt4o-mini --model-b claude-haiku

omnillm evaluate                                         # benchmark all
omnillm evaluate -m openai-gpt4o-mini -c reasoning       # specific
omnillm evaluate -o results/eval_2026.json

omnillm leaderboard                                      # overall ELO
omnillm leaderboard --category embodied_hri              # thesis result
omnillm leaderboard --category reasoning

omnillm costs                                            # USD per model

omnillm export --format csv      --input results/eval.json -o results/eval.csv
omnillm export --format markdown --input results/eval.json -o results/eval.md
```

## C.8 — Testing

```powershell
pytest tests/ -v                              # verbose
pytest tests/ -q                              # quiet (just pass count)
pytest tests/ --cov=omnillm --cov-report=term-missing
pytest tests/test_gateway.py                  # one file
pytest tests/test_gateway.py::test_query_basic   # one test
pytest -k "router"                            # tests matching name pattern
```

## C.9 — Health Checks Against a Running Server

```powershell
# Liveness
curl http://127.0.0.1:5000/health

# Configuration dump
curl http://127.0.0.1:5000/status

# Text-only interaction
curl -X POST http://127.0.0.1:5000/interact `
  -H "Content-Type: application/json" `
  -d '{"text":"Hello","participant_id":"P-test","session_id":"s1","condition":"A","rag_enabled":true}'

# Just transcribe (no LLM)
$audio = [Convert]::ToBase64String([IO.File]::ReadAllBytes("test.wav"))
curl -X POST http://127.0.0.1:5000/transcribe `
  -H "Content-Type: application/json" `
  -d "{`"audio`": `"$audio`"}"

# Export all logged interactions
curl http://127.0.0.1:5000/export

# Submit questionnaire data
curl -X POST http://127.0.0.1:5000/evaluate `
  -H "Content-Type: application/json" `
  -d '{"session_id":"s1","participant_id":"P003","condition":"A","scores":{"accuracy":6,"naturalness":5}}'
```

## C.10 — Health Checks Against the Bridge Server

```powershell
# Ping (is bridge alive + connected to a robot?)
curl http://127.0.0.1:6000/ping

# Sensor read
curl http://127.0.0.1:6000/sensors

# Send a hand-crafted action
curl -X POST http://127.0.0.1:6000/action `
  -H "Content-Type: application/json" `
  -d '{"speech":"Hello!","gesture":"wave","emotion_led":"#00FF88"}'

# Start face tracking
curl -X POST http://127.0.0.1:6000/tracker/start `
  -H "Content-Type: application/json" -d '{"target":"Face"}'

# Stop face tracking
curl -X POST http://127.0.0.1:6000/tracker/stop

# Clean shutdown
curl -X POST http://127.0.0.1:6000/disconnect
```

## C.11 — Building the Book PDF

```powershell
python book\build_pdf.py            # rebuild PDF + HTML
```

\newpage

# Appendix D — Troubleshooting Reference

> *Symptom → likely cause → fix. Organised by where in the stack the failure shows up.*

\newpage

## D.1 — Installation

| Symptom | Cause | Fix |
|---|---|---|
| `python: command not found` | Python not on PATH | Reinstall Python with the "Add to PATH" checkbox |
| `Microsoft Visual C++ 14.0 is required` | Some pip wheel needs a C++ compiler | Install Microsoft Build Tools for C++; retry |
| `chromadb` install fails | Outdated pip resolver | `pip install --upgrade pip`; retry |
| `whisper: command not found ffmpeg` | Whisper requires ffmpeg | `winget install ffmpeg` |
| Activating venv: *"execution policy"* error | PowerShell forbids unsigned scripts | `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` |
| `pip install -e ".[all]"` says *"could not find a version that satisfies"* | Python < 3.11 | Upgrade Python |
| Python 2.7 + `import naoqi` fails | PYTHONPATH not set | `set PYTHONPATH=C:\pynaoqi\...\lib;%PYTHONPATH%` |
| `omnillm: command not found` after install | venv not activated | `.\venv\Scripts\Activate.ps1` |

## D.2 — AI Server (Python 3)

| Symptom | Cause | Fix |
|---|---|---|
| Server starts but `/status` shows `rag_enabled=false` | KB directory empty / wrong path | Check `--kb` flag; verify files exist |
| Server starts but `/status` shows `langgraph_available=false` | LangGraph not installed | `pip install -e ".[hri]"` |
| `/interact` returns 500 with empty body | LLM call timed out | Check provider status page; bump `litellm` timeout |
| `/interact` returns `"path": "fallback"` | LangGraph crashed; fell back to direct gateway | Check server log for the actual graph error |
| `/interact` returns empty speech | (Pre-May-2026) `_merge_state` wrapper missing | This was fixed; if it returns, check that the agent graph is up-to-date |
| `KeyError: 'openai-gpt4o-mini'` | `models.yaml` does not contain that ID | Edit `config/models.yaml` |
| `429 RESOURCE_EXHAUSTED` from Google | Google free-tier quota | Set `GOOGLE_API_KEY=""` or upgrade tier |
| `401 Unauthorized` from OpenAI | Wrong / missing API key | Check `.env`; sk- prefix; correct env var name |
| Server takes >30 s to start | First-time embedding-model download | One-time only; wait |

## D.3 — NAOqi Bridge (Python 2.7)

| Symptom | Cause | Fix |
|---|---|---|
| `[ERR] ALBroker construction failed` | Wrong IP / wrong port / Pepper asleep / firewall | Re-check `--robot-ip`; chest-button to wake; check firewall rule |
| `[ERR] ImportError: No module named naoqi` | PYTHONPATH not set in this terminal | `set PYTHONPATH=C:\pynaoqi\...\lib;%PYTHONPATH%` |
| `/ping` returns `"simulation": true` | Connected to Choregraphe, not real Pepper | Re-check `--robot-ip` and `--robot-port` |
| `/action` returns `"errors": {"gesture": "behavior not installed"}` | Animation library does not include that gesture | Pre-install via Choregraphe (Behavior Manager) OR limit the gesture planner to a known-good subset |
| `/action` returns `200 OK` but Pepper doesn't move | NAOqi safety-mode active (low battery / overheat) | Plug Pepper into charger; let cool down |
| Bridge crashes on shutdown | `motion.rest()` race condition | Harmless on exit; ignore |

## D.4 — Real-Pepper Connectivity

| Symptom | Cause | Fix |
|---|---|---|
| `ping <PEPPER_IP>` times out | Different subnet / wrong Wi-Fi / Pepper offline | Confirm Pepper's IP; join correct SSID; chest-button to wake |
| Pepper speaks but gestures all fail | Connected to virtual robot | Re-check `--robot-ip`; not `127.0.0.1` |
| Pepper's TTS is silent | Speakers muted at OS level | Use Choregraphe Volume slider; or `ALAudioDevice.setOutputVolume(80)` |
| Whisper transcribes Italian as garbage English | `model_size="base"` weak on accent | Bump to `"small"` in `whisper_stt.py` |
| Touch trigger fires randomly | Hair / clothing brushing head sensor | Re-instruct participant; use VAD or text trigger |

## D.5 — Experiment Driver

| Symptom | Cause | Fix |
|---|---|---|
| `ERROR: server unreachable` mid-session | AI server restarted / crashed | Restart server in window #1; re-run driver |
| Latency suddenly > 10 s | OpenAI outage | Check status.openai.com; switch to Condition B |
| CSV missing rows | Server log JSONL not flushed | Add explicit `fh.flush()` in `experiment_logger.py`; for now check `/export` |
| Driver exits with `BrokenPipeError` | aiohttp session closed unexpectedly | Re-run; if persistent, switch to wired Ethernet |
| Condition B returns cloud-shaped responses | Ollama not running | `ollama serve`; `ollama list` confirms model is pulled |

## D.6 — Book PDF Build

| Symptom | Cause | Fix |
|---|---|---|
| `reportlab.pdfbase` font registration warns about missing DejaVu | Matplotlib not installed | `pip install matplotlib` (it ships with the DejaVu fonts) |
| Box-drawing characters render as `■` squares in the PDF | Character not in DejaVu Sans Mono / not in `_BOX_REPLACE` map | Add the offending Unicode codepoint to `_BOX_REPLACE` in `build_pdf.py` and rerun |
| Emoji rendered as squares | Not in `_EMOJI_REPLACE` map | Same: add to map, rerun |
| `xhtml2pdf` warns about CSS | Some unsupported property | Cosmetic; PDF still builds |

\newpage
