\newpage

# Part IV — Setup, Execution, & Building from Scratch

> *Parts I, II, and III explained the project. Part IV gets it running on your machine and, in Chapter 21, on the real Pepper at the lab tomorrow.*

\newpage

## Chapter 17 — Installing OmniLLM From Zero

### At a Glance

OmniLLM installs cleanly on Windows 10/11, macOS, and modern Linux distributions, given a Python ≥ 3.11 interpreter and ~3 GB of free disk (most of which is the optional ChromaDB / Whisper model cache). Cloud LLM access is optional — Ollama-only local inference works without a single API key.

This chapter walks through the installation **on the author's laptop (Windows 11 + Anaconda + venv)** in detail. macOS and Linux instructions are given afterwards in collapsed form because they are simpler.

### Prerequisites

| Requirement | Check it | Why |
|---|---|---|
| **Python ≥ 3.11** | `python --version` | Required for `litellm`, `langgraph`, `chromadb`. |
| **pip** | `pip --version` | Standard install tool. |
| **git** | `git --version` | To clone the repo. |
| **Visual Studio Code** (recommended editor) | — | For IntelliSense + the integrated terminal. |
| **PowerShell ≥ 5.1** (Windows) | `$PSVersionTable.PSVersion` | The shell every command in this book is written in. |
| **Choregraphe ≥ 2.5.10** (optional, virtual Pepper only) | Run the installer once | SoftBank's IDE + virtual Pepper. Windows-only officially. |
| **Python 2.7** (optional, real Pepper only) | `C:\Python27\python.exe --version` | NAOqi SDK runs on this and only this. |
| **NAOqi Python 2.7 SDK** (optional, real Pepper) | `import naoqi` succeeds in `C:\Python27\python.exe` | The actual NAOqi Python bindings. |
| **Ollama** (optional, local LLM) | `ollama --version` | Free local model runtime. |

### Step-by-Step on Windows 11

#### 1. Clone the repository

Open a PowerShell window and run:

```powershell
cd C:\Users\akshi\OneDrive\Desktop
git clone https://github.com/Akshita-sr/OmniLLM.git
cd OmniLLM
```

#### 2. Create and activate the virtual environment

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

After activation your prompt should show `(venv)` at the front. If PowerShell refuses to run `Activate.ps1` with an *"execution policy"* error, run once per machine:

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

#### 3. Install the package and all extras

```powershell
pip install --upgrade pip
pip install -e ".[all]"
```

The `.[all]` extra installs dev tools (`pytest`, `pytest-asyncio`, `pytest-mock`), robotics extras (`flask`, `aiohttp`), HRI extras (`langgraph`, `langchain`, `chromadb`, `sentence-transformers`, `langdetect`), and book-build tools (`reportlab`, `xhtml2pdf`, `markdown`). Total ~600 MB on disk after first install.

#### 4. (Optional) Configure your `.env` for cloud LLMs

```powershell
Copy-Item .env.example .env
notepad .env
```

Edit the file to add the API keys you actually have:

```
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
GOOGLE_API_KEY=AIza...
DEEPSEEK_API_KEY=sk-...
QWEN_API_KEY=...
```

You only need the keys for models you intend to use. Leave the rest blank or delete the lines.

#### 5. (Optional) Install Ollama and pull a free local model

```powershell
# Install from https://ollama.com (one-click MSI installer on Windows)
ollama --version            # confirm install
ollama pull llama3.2:3b     # ~2 GB; required for Condition B of the study
ollama pull qwen2.5:7b      # ~4 GB; optional second local model
ollama serve                # start the daemon (it auto-starts on Windows boot)
```

#### 6. (Optional) Install Python 2.7 + NAOqi SDK for real-Pepper work

Skip this section entirely if you are not connecting to a real Pepper or to Choregraphe's virtual Pepper.

1. Download Python 2.7 from python.org → install to `C:\Python27\` (the *exact* default location — the scripts in this repo hard-code this path).
2. Download the **pynaoqi SDK** for Python 2.7 from SoftBank's developer portal: `pynaoqi-python2.7-2.5.5.5-win32-vs2013.zip`. Extract to `C:\pynaoqi\`.
3. Tell Python 2.7 where to find the SDK by adding `C:\pynaoqi\pynaoqi-python2.7-2.5.5.5-win32-vs2013\lib` to `PYTHONPATH`. Confirm:

   ```cmd
   set PYTHONPATH=C:\pynaoqi\pynaoqi-python2.7-2.5.5.5-win32-vs2013\lib;%PYTHONPATH%
   C:\Python27\python.exe -c "import naoqi; print(naoqi.__file__)"
   ```

   If you see a path, you are done. If you see `ImportError`, the `PYTHONPATH` is not set correctly.

#### 7. Verify

```powershell
omnillm --version           # should print "OmniLLM 0.1.0"
omnillm models              # should print a coloured table of 19 models
pytest tests/ -q            # should print "289 passed"
```

If the three commands above succeed, your installation is complete.

### macOS / Linux

The flow is identical, with three substitutions:

- `python3 -m venv venv` (instead of `python -m venv venv`)
- `source venv/bin/activate` (instead of `.\venv\Scripts\Activate.ps1`)
- All PowerShell-specific syntax in later chapters has a Bash equivalent in Appendix C.

Real-Pepper work is harder on macOS/Linux because the official pynaoqi Python 2.7 SDK ships only for Windows and certain old Linux versions. If you must, build NAOqi on Linux using Aldebaran's old build instructions or use a Windows VM for the Python-2.7 side.

### Common Install Failures

| Symptom | Cause | Fix |
|---|---|---|
| `Microsoft Visual C++ 14.0 is required` | Some pip wheel missing on Windows | Install Microsoft Build Tools for C++; retry. |
| `chromadb` install fails | Older pip cannot resolve the dependency tree | `pip install --upgrade pip` then retry. |
| `whisper` complains about ffmpeg | Whisper needs ffmpeg on PATH for audio decoding | `winget install ffmpeg` (Windows) or `brew install ffmpeg` (mac) |
| `import naoqi` fails in Python 2.7 | `PYTHONPATH` not set or 64-bit Python tried to load 32-bit SDK | Confirm Python 2.7 is the **32-bit** build; reset PYTHONPATH. |
| `ollama serve` says "address already in use" | Ollama is already running as a service | That's fine; just close the manual `ollama serve`. |

\newpage

## Chapter 18 — Scenario A — Running Without Any Robot (Text-Only)

### At a Glance

The fastest way to confirm OmniLLM is working end-to-end on a fresh install. No robot, no Choregraphe, no NAOqi. Talk to the brain via curl or the CLI.

### Step 1 — Start the AI server

```powershell
cd C:\Users\akshi\OneDrive\Desktop\OmniLLM
.\venv\Scripts\Activate.ps1
python -m omnillm.server.app --host 127.0.0.1 --port 5000
```

Expected output:

```
INFO:omnillm.rag.pipeline:ChromaDB initialised at .chroma
INFO:__main__:Knowledge base loaded — 49 total chunks
 * Running on http://127.0.0.1:5000
 * Restarting with watchdog
```

The "49 total chunks" number depends on what's in `knowledge_base/`. Anything between 40 and 60 is normal as of the May 2026 DIBRIS knowledge base.

### Step 2 — Sanity check from a second terminal

```powershell
curl http://127.0.0.1:5000/status
```

Expected JSON response (formatted for readability):

```json
{
  "status": "ok",
  "default_model": "openai-gpt4o-mini",
  "rag_enabled": true,
  "knowledge_base": "C:\\Users\\akshi\\...\\knowledge_base",
  "knowledge_base_exists": true,
  "rag_uses_chromadb": true,
  "available_models": ["openai-gpt4o-mini", "claude-haiku", ...],
  "langgraph_available": true
}
```

If `rag_uses_chromadb` is `false`, ChromaDB failed to load — RAG will still work via the keyword-search fallback but the faithfulness scores will be lower. If `langgraph_available` is `false`, install the `[hri]` extra.

### Step 3 — Ask a question via curl

```powershell
curl -X POST http://127.0.0.1:5000/interact `
  -H "Content-Type: application/json" `
  -d '{"text":"What time does the lab open?","participant_id":"P-test","session_id":"s-1","condition":"A","rag_enabled":true}'
```

Expected response:

```json
{
  "speech": "The lab opens at 08:30 on weekdays.",
  "gesture": "nod",
  "emotion_led": "#00FF88",
  "metadata": {
    "task_type": "info_retrieval",
    "model_id": "openai-gpt4o-mini",
    "rag_enabled": true,
    "condition": "A"
  }
}
```

You now have proof that gateway, RAG, agent graph, gesture planner, and JSON marshalling are all working. The Pepper-specific layer is the only missing piece.

### Step 4 — Run the batch test for all conditions

This is the canonical pre-flight check before any robot work:

```powershell
python scripts\pepper_demo\test_all_conditions.py
```

Output (abridged):

```
[01/15] A / T1 / "What time does the lab open?" → "The lab opens at 08:30 on weekdays."
[02/15] A / T2 / "Where is the Pepper room?"   → "The Pepper room is at the end..."
[03/15] B / T1 / ...                            → (Llama 3.2 3B via Ollama)
...
Wrote scripts/pepper_demo/test_results.txt
```

A full pass takes ~3 minutes on a typical laptop with Ollama running. If any test errors out, the failing condition is the one to debug *before* moving to the robot scenarios.

\newpage

## Chapter 19 — Scenario B — Running With Choregraphe's Virtual Robot

### At a Glance

A simulated Pepper from SoftBank. The full HRI pipeline executes; only the **gestures** silently fall back to "behavior not installed" because the virtual robot's animation library is a placeholder. Speech and LEDs work fine; audio I/O does not (no microphone). Use `--trigger text` for any conversational testing.

### Step 1 — Launch Choregraphe

Double-click the Choregraphe shortcut. The IDE opens. From the menu bar:

`Connection → Connect to…` → select the **AKSHITA** virtual robot in the list → **Connect**.

A small popup window shows the assigned virtual-robot port (e.g. `49959`). **Write this number down** — call it `VIRTUAL_PORT`. It changes every launch.

### Step 2 — Start the AI server

In PowerShell window #1:

```powershell
cd C:\Users\akshi\OneDrive\Desktop\OmniLLM
.\venv\Scripts\Activate.ps1
python -m omnillm.server.app --host 127.0.0.1 --port 5000
```

### Step 3 — Sanity-check NAOqi alone (no AI)

In PowerShell window #2 (Python 2.7):

```cmd
C:\Python27\python.exe scripts\pepper_demo\demo_pepper_omnillm.py --check-only --robot-port 49959
```

Replace `49959` with your actual `VIRTUAL_PORT`. Expected output:

```
[OK] Connected to robot at 127.0.0.1:49959
[OK] ALAnimatedSpeech proxy created
[OK] ALMotion proxy created
[OK] Pepper says: "Hello from my own Python script"
[OK] All sanity checks passed.
```

The virtual robot speaks the sentence via its "Robot Dialog" panel in the Choregraphe UI. If you see the sentence in the dialog panel: green light. If you see `ALBroker construction failed`, see Chapter 16 (Windows 11 loopback bug).

### Step 4 — Single-shot demo

```cmd
C:\Python27\python.exe scripts\pepper_demo\demo_pepper_omnillm.py ^
    --condition A --rag --question "What time does the lab open?" ^
    --robot-port 49959
```

Expected: the virtual Pepper says *"The lab opens at 08:30 on weekdays."* in the dialog panel.

### Step 5 — Interactive text-trigger client

```cmd
C:\Python27\python.exe omnillm\server\naoqi_client.py ^
    --robot-ip 127.0.0.1 --robot-port 49959 ^
    --trigger text --condition A
```

The client prints a prompt; type a question; Pepper answers via the dialog panel; loop until you enter an empty line.

```
[ready] You ask: Where is Room 305?
[interact] sending to server...
[server] model=openai-gpt4o-mini path=graph latency=1430ms
[robot] Pepper says: "Room 305 is on the 3rd floor. Take the lift or staircase on your left."
[robot] gesture point_left (behavior not installed; speech still executed)
[robot] LED → #00AAFF
[ready] You ask: _
```

The `behavior not installed` line is expected on the virtual robot — Chapter 3 documented this. Speech and LED still work.

### Step 6 — Drive a full subject session against the virtual robot

This is the pre-real-Pepper rehearsal:

```powershell
# In PowerShell window #1 (AI server already running)
# In PowerShell window #3 (the driver):
.\venv\Scripts\python.exe scripts\pepper_demo\run_subject_experiment.py `
    --participant P000-rehearsal `
    --server http://127.0.0.1:5000 `
    --no-robot
```

The `--no-robot` flag bypasses the bridge entirely and only exercises the AI server. The 20-interaction matrix runs in ~5 minutes and produces:

```
results/subject_run_P000-rehearsal_<timestamp>.json
results/subject_run_P000-rehearsal_<timestamp>.csv
```

These are the exact files the actual study session produces — review them to confirm latency, model selection, condition routing, and RAG faithfulness all look right *before* you go to the lab.

\newpage

## Chapter 20 — Scenario C — Running With the Physical Pepper Robot

### At a Glance

Same as Scenario B, but with the real Pepper at DIBRIS. Two terminals minimum (server + bridge), or three if you also run the experiment driver. The next chapter (Chapter 21) walks through Day Zero step-by-step with expected outputs at every stage; this chapter is the conceptual overview.

### The Connection Sequence

```
+----------------+         +--------------------+         +---------------------+
| Your laptop    |  HTTP   | naoqi_bridge_      |  NAOqi  | Real Pepper at       |
| (Py 3.11+)     | ------> | server.py          | ------> | 192.168.x.x:9559     |
|                |         | (Py 2.7)           |         |                      |
| LangGraph +    |         | ALBroker bound to  |         | Microphones,         |
| Gateway +      |         | 0.0.0.0:<eph>      |         | speakers, gestures,  |
| RAG +          |         | (or 127.0.0.1)     |         | tablet, LEDs,        |
| ExperimentLog  |         |                    |         | face-tracking        |
+----------------+         +--------------------+         +---------------------+
   |                                                                          ^
   |  POST /interact (from Pepper or driver)                                  |
   +--------------------------------------------------------------------------+
                              voice round-trip
```

### Network Requirements

- Laptop and Pepper on the **same Wi-Fi LAN**. Pepper does not need internet (and at DIBRIS, it does not have it). Only laptop ↔ Pepper LAN reachability.
- The lab Wi-Fi at DIBRIS that Pepper is on may be different from the eduroam Wi-Fi your laptop joins by default. **Confirm with Prof. Sgorbissa or the lab technician which SSID Pepper is paired to.**
- `ping <PEPPER_IP>` must succeed from PowerShell *before* you start any OmniLLM process.

### Firewall

Windows Firewall typically blocks inbound TCP to a freshly-installed Python interpreter. Allow Python through once:

```powershell
New-NetFirewallRule -DisplayName "OmniLLM AI server" `
  -Direction Inbound -Program "C:\Users\akshi\OneDrive\Desktop\OmniLLM\venv\Scripts\python.exe" `
  -Action Allow -Profile Private
New-NetFirewallRule -DisplayName "OmniLLM NAOqi bridge" `
  -Direction Inbound -Program "C:\Python27\python.exe" `
  -Action Allow -Profile Private
```

Run once per laptop. The `Private` profile means the rule applies only when connected to a private/work network — not when you're on a coffee-shop Wi-Fi.

### Topology Choice

| You want to… | Use topology |
|---|---|
| Demo to a colleague — text-trigger, no study driver | Topology 1 (`naoqi_client.py`) |
| Run the formal study with `run_subject_experiment.py` | **Topology 2** (`naoqi_bridge_server.py` + bridge client) |
| Touch-triggered VAD-based always-on conversation | Topology 1 with `--trigger touch` or `--trigger vad` |
| Streaming partial responses spoken before the LLM finishes | Topology 2 (only topology that allows multi-action mid-reasoning) |

For the N=15 study at DIBRIS, the canonical setup is **Topology 2 with `run_subject_experiment.py`** (see Day Zero).

\newpage

## Chapter 21 — Day Zero — The Real-Pepper Deployment at DIBRIS

> *This chapter is the one to print out and bring to the lab. Follow it top-to-bottom. Tick the boxes as you go.*
>
> *Every step lists the expected output. If reality matches the expected output, move on. If not, the troubleshooting table at the end will tell you what to do.*

### 0 — Pre-arrival Checklist (the night before)

Do this on your laptop at home, not at the lab. If anything below fails, *fix it before you leave*.

- [ ] Latest code pulled: `git pull origin main && git status` shows "clean".
- [ ] Test suite passes: `.\venv\Scripts\python.exe -m pytest tests/ -q` → **`289 passed`**.
- [ ] `.env` is populated with all five keys (OPENAI, ANTHROPIC, GOOGLE, DEEPSEEK, QWEN). Confirm by sourcing:
  ```powershell
  Get-Content .env | Select-String '_API_KEY' | Measure-Object -Line
  ```
  Should report **5 lines**.
- [ ] Ollama is running locally and `llama3.2:3b` is pulled:
  ```powershell
  ollama list
  ```
  Output should include a line for `llama3.2:3b`.
- [ ] Confirm Condition B works locally:
  ```powershell
  $env:OMNILLM_DEFAULT_MODEL = "llama3-8b-local"
  omnillm ask "Hello" -m llama3-8b-local
  ```
  Should return a Llama-flavoured greeting within ~3 seconds.
- [ ] Charged laptop. Spare USB-C cable. Network cable (in case Wi-Fi flakes).
- [ ] Paper questionnaire forms × 1 per planned participant.
- [ ] Pen.

### 1 — At the lab: power up Pepper

- [ ] Press Pepper's chest button **once**. Pepper boots (LEDs cycle, takes ~30 seconds).
- [ ] Wait until Pepper says its IP aloud (e.g. *"My IP address is one nine two, dot one six eight, dot one, dot one hundred"*). **Write this down. Call it `PEPPER_IP`.**
- [ ] Confirm the same IP is shown on Pepper's chest tablet: tap → *About → Network*.

Expected: an IPv4 like `192.168.x.x` corresponding to the lab subnet.

If Pepper does not say its IP aloud after 60 seconds: long-press the chest button to shut down, wait 30 seconds, power on again.

### 2 — Confirm laptop ↔ Pepper LAN connectivity

- [ ] Connect your laptop to the same Wi-Fi as Pepper (ask the lab technician which SSID).
- [ ] `ipconfig` → note your laptop's IPv4 on the LAN adapter. Call this `SERVER_IP`.
- [ ] `ping <PEPPER_IP>` from PowerShell.

Expected:

```
Reply from 192.168.1.100: bytes=32 time=4ms TTL=64
Reply from 192.168.1.100: bytes=32 time=3ms TTL=64
```

If 0% replies: you are not on Pepper's subnet. Re-join the correct Wi-Fi.

### 3 — Start the AI server (Terminal 1, Python 3 venv)

- [ ] Open PowerShell window #1:
  ```powershell
  cd C:\Users\akshi\OneDrive\Desktop\OmniLLM
  .\venv\Scripts\Activate.ps1
  python -m omnillm.server.app --host 0.0.0.0 --port 5000
  ```

Expected output (line for line):

```
INFO:omnillm.rag.pipeline:ChromaDB initialised at .chroma
INFO:__main__:Knowledge base loaded — 49 total chunks
 * Serving Flask app 'omnillm.server.app'
 * Running on all addresses (0.0.0.0)
 * Running on http://127.0.0.1:5000
 * Running on http://192.168.x.x:5000
```

- [ ] In a second PowerShell window (or your phone's browser), verify:
  ```powershell
  curl http://127.0.0.1:5000/status
  ```

Expected JSON contains:

- `"rag_enabled": true`
- `"langgraph_available": true`
- `"rag_uses_chromadb": true`

If any of these is `false`: stop and consult the troubleshooting table at the end.

### 4 — Start the NAOqi bridge (Terminal 2, Python 2.7)

- [ ] Open PowerShell window #2:
  ```powershell
  cd C:\Users\akshi\OneDrive\Desktop\OmniLLM
  C:\Python27\python.exe omnillm\server\naoqi_bridge_server.py `
      --robot-ip <PEPPER_IP> --robot-port 9559 `
      --bind 0.0.0.0 --bridge-port 6000
  ```
  (Replace `<PEPPER_IP>` with the actual IP you wrote down in step 1.)

Expected output:

```
[INFO] Connecting to NAOqi at <PEPPER_IP>:9559 ...
[OK] NaoqiFacade connected to <PEPPER_IP>:9559 (listen=0.0.0.0)
[OK] NAOqi bridge listening on http://0.0.0.0:6000/
[INFO] Endpoints: /ping /action /audio/record /sensors /tracker/start /tracker/stop /disconnect
```

If you see `[ERR] ALBroker construction failed`:
- Wrong IP — re-check `PEPPER_IP`.
- Pepper is asleep — press the chest button to wake.
- Firewall blocking inbound to Python 2.7 — see firewall step in Chapter 20.

- [ ] Verify the bridge:
  ```powershell
  curl http://127.0.0.1:6000/ping
  ```

Expected:

```json
{"ok": true, "naoqi": true, "simulation": false, "robot_ip": "<PEPPER_IP>", "robot_port": 9559}
```

The critical fields are `"naoqi": true` (NAOqi is connected) and `"simulation": false` (it's the real robot, not Choregraphe).

### 5 — One-shot Pepper-greets-you sanity test

This sends a single hand-crafted RobotAction to the bridge without any LLM in the loop. Use it to confirm Pepper itself responds to bridge commands.

- [ ] In any spare terminal:
  ```powershell
  curl -X POST http://127.0.0.1:6000/action `
    -H "Content-Type: application/json" `
    -d '{"speech":"Hello, I am Pepper at DIBRIS, ready for the OmniLLM experiment.","gesture":"wave","emotion_led":"#00FF88"}'
  ```

Expected at the robot:
- Pepper speaks the sentence aloud through its speakers.
- Pepper raises its arm and waves.
- Pepper's eye LEDs turn green.

Expected JSON return:

```json
{"ok": true, "executed": {"speech": true, "gesture": true, "emotion_led": true}, "errors": {}}
```

If `gesture: false` and the error reads `"behavior not installed: animations/Stand/..."`, you are talking to **Choregraphe's virtual robot**, not the real one. Check `--robot-ip` of step 4 — it should be the real Pepper IP, not `127.0.0.1`.

### 6 — Pilot run — you as participant P000-realPepper

Do this once before any real participant arrives. The pilot exercises the full 20-interaction matrix, drives the real robot, and writes a CSV you can scan for anomalies.

- [ ] Open PowerShell window #3:
  ```powershell
  cd C:\Users\akshi\OneDrive\Desktop\OmniLLM
  .\venv\Scripts\Activate.ps1
  .\venv\Scripts\python.exe scripts\pepper_demo\run_subject_experiment.py `
      --participant P000-realPepper `
      --server http://127.0.0.1:5000 `
      --bridge http://127.0.0.1:6000
  ```

Expected progress output (one line every ~6 seconds):

```
Subject experiment — participant=P000-realPepper session=578b023b
Server: http://127.0.0.1:5000
Robot bridge: http://127.0.0.1:6000

[01/20] A / T1_info_retrieval: What time does the lab open?
    -> The lab opens at 08:30 on weekdays.
    model=openai-gpt4o-mini  path=graph  latency=1437 ms
    robot: ok
[02/20] A / T2_navigation: Where is the Pepper room at DIBRIS?
    -> The Pepper room is located at the end of the ground-floor corridor...
    model=openai-gpt4o-mini  path=graph  latency=1592 ms
    robot: ok
[03/20] A / T3_social: Hello Pepper, how are you today?
    ...
[04/20] A / T4_multilingual: Ciao Pepper, dove si trova la stazione di Brignole?
    -> Ciao! La stazione di Brignole si trova...
    model=claude-haiku  path=graph  latency=1980 ms
    robot: ok
[05/20] B / T2_navigation: Where is the Pepper room at DIBRIS?
    -> [Llama 3.2 3B answer]
    model=llama3-8b-local  path=graph  latency=2840 ms
    robot: ok
...
[13/20] D / T4_multilingual: ...
    model=council:openai-gpt4o-mini+claude-haiku+gemini-flash  latency=3140 ms
    robot: ok
...
[20/20] E / T4_multilingual: ...
    model=openai-gpt4o-mini  path=graph  latency=1750 ms
    rag=n   <-- RAG-off control
    robot: ok

Wrote results/subject_run_P000-realPepper_<timestamp>.json
Wrote results/subject_run_P000-realPepper_<timestamp>.csv
Server-logged interactions for this run: 20
```

The critical things to verify *during* the pilot:

- [ ] Pepper actually speaks each line through its physical speakers (not just text on Choregraphe).
- [ ] Pepper's gestures execute physically (you see the arm move).
- [ ] The `model=` line shows the **expected** model for each condition:
  - Condition A → `openai-gpt4o-mini`
  - Condition B → `llama3-8b-local` (**not** GPT-4o-mini)
  - Condition C → varies by task (Claude Haiku for T3, GPT-4o-mini for T1/T2, Claude Haiku for T4)
  - Condition D → `council:...` with a plus-separated list
  - Condition E → `openai-gpt4o-mini` with `rag=n`
- [ ] Latencies stay under 4 seconds for A/B/C/E; D may go up to 4-5s (council is slower).

If any condition routes to the wrong model: stop, check `omnillm/hri/experiment.py: CONDITION_CONFIGS`, restart the server, retry. This is the May 2026 routing-bug class — see Chapter 12.

### 7 — Real-participant sessions

For each participant `P001`, `P002`, ... `P015`:

#### 7.1 — Welcome the participant

- [ ] Greet, seat in the designated participant chair (Pepper roughly 1.2 m away facing the chair).
- [ ] Explain in plain language what's about to happen:
  > *"You'll have a short conversation with Pepper. We will run five different 'personalities' of Pepper, four short questions each. After each personality, I'll hand you a brief paper questionnaire. The whole thing takes about half an hour. You can stop at any time."*
- [ ] Hand over the **consent form**, give time to read, collect signed form.
- [ ] Hand over the **GDPR notice**, give time to read, collect signed receipt.

#### 7.2 — Start the session

- [ ] Run the driver with the participant's assigned ID:
  ```powershell
  .\venv\Scripts\python.exe scripts\pepper_demo\run_subject_experiment.py `
      --participant P003 `
      --server http://127.0.0.1:5000 `
      --bridge http://127.0.0.1:6000
  ```

- [ ] At each condition boundary (every 4 interactions), the driver pauses; the experimenter hands the participant the questionnaire for that condition, collects after ~60 seconds, resumes.

#### 7.3 — After the session

- [ ] CSV/JSON saved under `results/`. Move them to `results/by_participant/P003/` for tidiness.
- [ ] Write the participant ID on every questionnaire page in pen.
- [ ] Digitise the Likert scores into `results/by_participant/P003/questionnaire.json` within an hour (memory fades; do it now).

### 8 — Optional: live face tracking during the session

If you want Pepper to follow the participant's face while they answer:

```powershell
# In a fourth terminal, while the bridge is running:
curl -X POST http://127.0.0.1:6000/tracker/start -H "Content-Type: application/json" -d '{"target":"Face"}'
```

Pepper's head will now track detected faces. Stop with:

```powershell
curl -X POST http://127.0.0.1:6000/tracker/stop
```

For the actual study, set this up **once per session** at session start, stop at session end. Pepper's head will track even between conversational turns, which feels much more natural to participants than a frozen-staring robot.

### 9 — Shutdown (end of day)

- [ ] In Terminal 2, `Ctrl+C` to stop the NAOqi bridge cleanly. The bridge sends `motion.rest()` on shutdown so Pepper relaxes its joints.
- [ ] In Terminal 1, `Ctrl+C` to stop the AI server.
- [ ] If Pepper is going on the shelf overnight, **long-press the chest button** until the shutdown chime sounds. Wait until LEDs are dark before unplugging.
- [ ] Plug Pepper into its charging dock.

### 10 — Troubleshooting Cheat Sheet

| Symptom | Likely cause | Fix |
|---|---|---|
| `ALBroker construction failed` | Wrong robot IP / port / Pepper asleep | Re-check `PEPPER_IP`; chest-button wake-up; confirm `ping` works |
| All Condition B responses look like GPT-4o-mini | Ollama not running or model not pulled | `ollama serve`; `ollama list` |
| `path: fallback` in metadata | Anthropic / Gemini briefly overloaded | Handled by retry; no action needed; the interaction is still logged |
| Empty `speech` field | LangGraph state-key mismatch — `_merge_state` broken | Check server log for graph error message |
| `429 RESOURCE_EXHAUSTED` from Google | Free-tier quota exhausted | Non-English already routes to claude-haiku, so harmless; if it persists, set `GOOGLE_API_KEY=""` |
| Pepper doesn't move but speaks | You're talking to the virtual robot instead of the real one | `curl /ping` and check `simulation: false` |
| Gesture says `behavior not installed` on **real** Pepper | NAOqi animation library missing — extremely rare on real Pepper | Re-flash NAOqi with full animation library, or skip (speech still works) |
| Whisper transcription is wrong | Participant has a strong accent and `model_size="base"` | Bump to `model_size="small"` in `whisper_stt.py`; restart server |
| Latency suddenly jumps to >10s | OpenAI is having an outage | Check status.openai.com; switch to Condition B (Llama) temporarily |
| Bridge server prints `[WARN] aiohttp ClientTimeout` | Network hiccup between bridge and Pepper | Re-run; if persistent, switch Pepper to a wired Ethernet adapter |
| `ImportError: chromadb` | The `[hri]` extra was not installed | `pip install -e ".[all]"` |
| `omnillm: command not found` | venv not activated | `.\venv\Scripts\Activate.ps1` |

\newpage

## Chapter 22 — Building This Project From Scratch — A 13-Week Plan for a Replicator

> *Suppose you wanted to rebuild OmniLLM from a blank repo. How long would it take, and in what order? This chapter answers exactly that. The plan is calibrated to a single developer with intermediate Python skills working ~10–15 hours/week.*

### Week-by-Week

| Week | Milestone | Files / capabilities added |
|---|---|---|
| **1** | Project skeleton + LLM gateway | `pyproject.toml`, `omnillm/gateway.py`, `config/models.yaml` (3 models), `tests/test_gateway.py` |
| **2** | Smart router | `omnillm/router.py`, 6 strategies; `tests/test_router.py` (24 tests) |
| **3** | Consensus + evaluator + scorer | `omnillm/consensus.py`, `omnillm/evaluator.py`, `omnillm/scorer.py`; ELO leaderboard CLI |
| **4** | CLI dashboard | `omnillm/cli.py` (click + rich); `omnillm models`, `ask`, `route`, `council`, `evaluate`, `leaderboard` |
| **5** | RAG pipeline | `omnillm/rag/pipeline.py`; ChromaDB integration; keyword fallback; faithfulness scoring |
| **6** | HRI primitives | `omnillm/hri/classifier.py`, `omnillm/hri/language_detector.py`; `tests/test_hri.py` |
| **7** | Experimental design layer | `omnillm/hri/experiment.py`; Conditions A–E; `ExperimentManager`; counterbalancing utilities |
| **8** | The agent graph | `omnillm/hri/agent_graph.py`; 9-node LangGraph pipeline; `_merge_state` wrapper |
| **9** | Robot bridge abstraction | `omnillm/robotics/bridge.py`, `omnillm/robotics/gesture_planner.py`, `omnillm/robotics/whisper_stt.py` |
| **10** | Pepper bridge — Python 3 client | `omnillm/robotics/pepper.py`; aiohttp client; Choregraphe port discovery; stub-mode fallback |
| **11** | Pepper bridge — Python 2.7 server | `omnillm/server/naoqi_bridge_server.py` (stdlib HTTP); `omnillm/server/naoqi_client.py` (three triggers) |
| **12** | AI server | `omnillm/server/app.py` (Flask); `/interact`, `/transcribe`, `/evaluate`, `/status`, `/health`, `/export` |
| **13** | Experimental pipeline + book | `scripts/pepper_demo/run_subject_experiment.py`; `omnillm/utils/experiment_logger.py`, `questionnaire.py`, `cost_tracker.py`, `export.py`; `book/build_pdf.py` |

### Key Sequencing Constraints

- **`gateway.py` first.** Everything else depends on it.
- **`router.py` and `consensus.py` are parallel.** They both consume `gateway.py` but do not depend on each other.
- **`agent_graph.py` last among non-server files.** It depends on gateway, router, consensus, RAG, classifier, language_detector, gesture_planner, whisper_stt, experiment, and experiment_logger.
- **The two `server/` files are parallel.** `app.py` depends on `agent_graph.py`; `naoqi_bridge_server.py` is Python-2.7-only and depends on no OmniLLM code at all (it only imports NAOqi).
- **Tests are written alongside each module**, not at the end. The 289-test suite is what made the May 2026 refactor possible.

### Critical First Mile

Weeks 1–4 produce a **usable LLM benchmarking workbench** by themselves — no robot, no HRI, no RAG. This is the smallest viable slice you should build before adding anything else. Get `omnillm ask`, `omnillm route`, `omnillm council`, `omnillm leaderboard` working against three real LLM providers, and write 50+ tests around those four commands, before touching anything robotics-related.

### When (and How) to Add the Robot

The robot is **Week 9 in the plan**. Earlier than that, you do not have enough infrastructure to make the robot useful. Specifically:

- You need RAG (Week 5) before T1 (Info Retrieval) makes sense.
- You need the task classifier (Week 6) before any conditional routing.
- You need conditions A–E defined (Week 7) before there is anything to compare across.
- You need the agent graph (Week 8) before the robot is more than a one-shot voice toy.

Adding the robot before Week 9 produces a robot that talks to a single LLM in a single mode — interesting, but not a research contribution.

### How to Test Without a Robot

For 8 of the 13 weeks, you have no robot. The work is *not* blocked by that:

- All 289 tests run with mocks (no API keys, no robot).
- Scenarios A (text-only) and Scenarios B (virtual robot via Choregraphe) cover the full HRI pipeline without real hardware.
- The bridge's *stub mode* prints actions to stdout — letting you exercise `bridge.execute_action(action)` with zero hardware.

Only **Week 13 (live pilot)** strictly requires real Pepper access. Plan your lab time accordingly.

\newpage
