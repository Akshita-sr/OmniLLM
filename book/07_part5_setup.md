# PART V — SETUP & RUNNING

This part is action-oriented. By the end, you will have a clean install,
running tests, a server you can talk to with `curl`, and (optionally) a
working robot connection.

\newpage

## Chapter 28 — Installing OmniLLM From Zero

> **⚡ AT A GLANCE.** Six steps: install Python 3.11+, install Git, clone
> the repo, create a venv, `pip install -e .[all]`, configure `.env`. Total
> time: 15–20 minutes on a clean machine.

### 28.1  Prerequisite Software

Install these once per machine. None of them are OmniLLM-specific.

| Tool | Why | Where |
|------|-----|-------|
| **Python 3.11+** | Run the AI stack | python.org / brew / apt |
| **Git** | Clone the repo, pull updates | git-scm.com |
| **A code editor** | Read / edit code (VS Code recommended) | code.visualstudio.com |
| **Ollama** *(optional)* | Free local LLMs | ollama.com |
| **Choregraphe 2.5** *(robot only)* | Talk to Pepper visually | softbankrobotics.com (developer portal) |
| **Python 2.7** *(robot only)* | NAOqi client | python.org/downloads/release/python-2718 |
| **pynaoqi SDK** *(robot only)* | Python 2.7 bindings to NAOqi | softbankrobotics.com (developer portal) |

### 28.2  The Six Setup Steps

```bash
# ── 1. Clone ───────────────────────────────────────────────
git clone https://github.com/Akshita-sr/OmniLLM.git
cd OmniLLM

# ── 2. Create a virtual environment ────────────────────────
python -m venv .venv
# Activate:
# Linux/macOS:  source .venv/bin/activate
# Windows CMD:  .venv\Scripts\activate.bat
# PowerShell:   .venv\Scripts\Activate.ps1
# Git Bash:     source .venv/Scripts/activate

# ── 3. Install OmniLLM with all extras ─────────────────────
pip install -e ".[all]"

# ── 4. Configure API keys ──────────────────────────────────
cp .env.example .env       # Linux/macOS
copy .env.example .env     # Windows CMD
# Then open .env in your editor and paste your real keys

# ── 5. (Optional) Install Whisper for local STT ────────────
pip install openai-whisper

# ── 6. (Optional) Pull Ollama models for free local LLMs ───
ollama pull llama3:8b
ollama pull qwen2.5:7b
```

### 28.3  Verify the Install

```bash
# Should print version + register all 19 models in a table
omnillm --version
omnillm models
```

If both work, you have a healthy base install.

```bash
# Run the tests (no API keys needed — uses mocks)
pytest tests/ -v
```

You should see 278 tests pass. Failures here usually mean a missing
dependency.

### 28.4  The `.env` File

`.env.example` lists every supported environment variable. You only need
the ones for providers you actually want to use:

```dotenv
# OpenAI (GPT-4o, GPT-5.4, o1, o3-mini, GPT-4o-mini)
OPENAI_API_KEY=sk-proj-...

# Anthropic (Claude Sonnet/Opus/Haiku)
ANTHROPIC_API_KEY=sk-ant-...

# Google (Gemini 2.5 Pro, Flash, 2.0 Flash)
GOOGLE_API_KEY=AIzaSy...

# DeepSeek
DEEPSEEK_API_KEY=...

# Qwen / DashScope
QWEN_API_KEY=...

# Optional — override defaults
OMNILLM_DEFAULT_MODEL=openai-gpt4o-mini
OMNILLM_KNOWLEDGE_BASE=knowledge_base/
```

> 💡 **No keys at all?** You can still run the project. Use Ollama models
> exclusively (`-m llama3-8b-local`). The tests work without any keys
> because they mock LLM calls.

### 28.5  Optional Install Extras

Pyproject defines four optional extras. The `all` extra installs all of
them, but if you want to be selective:

| Extra | What it adds | When |
|-------|--------------|------|
| `[dev]` | pytest, pytest-asyncio, pytest-mock | Always (you'll want tests) |
| `[robotics]` | flask, websockets | When you want to run the AI server |
| `[hri]` | chromadb, langchain-community, sentence-transformers, pypdf, langdetect, langgraph | When you want full RAG + agent graph |
| `[all]` | Everything above | Default recommendation |

```bash
pip install -e ".[dev]"            # minimum
pip install -e ".[dev,robotics]"   # + AI server
pip install -e ".[dev,hri]"        # + RAG + LangGraph
pip install -e ".[all]"            # everything
```

### 28.6  Common First-Run Issues

| Symptom | Fix |
|---------|-----|
| `command not found: omnillm` | venv not activated, or install failed |
| `ModuleNotFoundError: chromadb` | `pip install -e ".[hri]"` |
| `ModuleNotFoundError: flask` | `pip install -e ".[robotics]"` |
| `APIConnectionError` | wrong / missing key in `.env` |
| `Error code: 401` | key has a typo or hasn't been activated |
| `litellm.exceptions.BadRequestError` | model name in YAML doesn't match provider's actual name |
| `Ollama: connection refused` | `ollama serve` not running |

\newpage

## Chapter 29 — Running Without a Robot (The Default Path)

> **⚡ AT A GLANCE.** Most development happens with no robot. The Flask
> server accepts text via `/interact` and returns `RobotAction` JSON. You
> can drive it with `curl`, Postman, a Python script, or a test
> dashboard. This is the path you should use 80% of the time.

### 29.1  Why Robot-Free Is the Default

You should not start the robot when:

- Your changes are in the AI layer (LLM logic, RAG, evaluation).
- You are debugging the agent graph.
- You are running benchmarks (`omnillm evaluate`).
- You are adding a new model to the registry.
- You are running tests.
- The robot is busy with another study.
- The robot is not in the room.
- You want to iterate quickly.

The robot is for **embodied user studies**. For everything else, plain
HTTP requests are faster, cheaper, and give you better debug logs.

### 29.2  Starting the Server

```bash
# Activate venv (Linux / macOS)
source .venv/bin/activate

# Start with defaults
python -m omnillm.server.app

# Or with custom options
python -m omnillm.server.app --host 0.0.0.0 --port 5000 --debug
```

You will see:

```
INFO:omnillm.rag.pipeline:Indexed 12 chunks from lab_info.txt
INFO:omnillm.rag.pipeline:Indexed 8 chunks from faq.txt
INFO:omnillm.rag.pipeline:Knowledge base loaded — 42 total chunks
 * Running on all addresses (0.0.0.0)
 * Running on http://127.0.0.1:5000
```

### 29.3  Driving It With `curl`

The single most useful command for testing:

```bash
curl -X POST http://localhost:5000/interact \
  -H "Content-Type: application/json" \
  -d '{
    "text": "What is the WiFi password?",
    "participant_id": "TEST",
    "session_id": "smoke-1",
    "condition": "A",
    "rag_enabled": true
  }'
```

You should get back something like:

```json
{
  "speech": "The visitor WiFi network is 'UniGuest' with the password 'Welcome2026!'.",
  "gesture": "nod",
  "emotion_led": "#00FF88",
  "metadata": {
    "task_type": "info_retrieval",
    "model_id":  "openai-gpt4o-mini",
    "rag_enabled": true
  }
}
```

### 29.4  Driving It From Python

A useful test script:

```python
# test_interact.py
import requests

def ask(text, condition="A"):
    r = requests.post("http://localhost:5000/interact", json={
        "text": text, "participant_id": "T",
        "session_id": "test", "condition": condition,
    })
    return r.json()

print(ask("What time does the lab open?"))
print(ask("Where is Room 305?"))
print(ask("How are you today, Pepper?"))
print(ask("Bonjour, comment allez-vous?"))   # multilingual
```

Run it with `python test_interact.py`. Each call exercises a different
task type and routing branch.

### 29.5  Driving It From the CLI

For LLM evaluation (no robot involved at all):

```bash
omnillm models                              # list registered models
omnillm ask "Explain RAG simply" --all      # query every model
omnillm evaluate -m openai-gpt4o-mini       # run benchmark on this model
omnillm council "Is P=NP?"                  # 3-model consensus
omnillm route "Cheap question" --budget 0.001
omnillm leaderboard
omnillm costs
```

These commands talk to providers directly through `gateway.py` — they do
not use the Flask server at all. Useful for evaluating models in
isolation.

### 29.6  Driving the Agent Graph From a Python REPL

Sometimes you want to invoke the LangGraph pipeline directly from Python,
without the HTTP layer:

```python
import asyncio
from omnillm.gateway import LLMGateway
from omnillm.rag import RAGPipeline
from omnillm.hri import build_hri_graph

async def main():
    gw = LLMGateway()
    rag = RAGPipeline(gateway=gw, model_id="openai-gpt4o-mini")
    rag.index_directory("knowledge_base/")
    graph = build_hri_graph(gateway=gw, rag=rag)

    state = {
        "utterance":      "What is the WiFi password?",
        "participant_id": "P001",
        "session_id":     "test-1",
        "condition":      "C",
        "rag_enabled":    True,
    }
    result = await graph.ainvoke(state)
    print(result["response_text"])
    print(result["robot_action"])

asyncio.run(main())
```

This is the fastest way to debug the graph without HTTP overhead.

\newpage

## Chapter 30 — Running With Choregraphe's Virtual Robot

> **⚡ AT A GLANCE.** Choregraphe ships with a virtual Pepper. Connect to
> it with `Connection → Connect to virtual robot` and you can see speech,
> gestures, and LED changes in the 3D viewport. The virtual robot has no
> real microphone, so audio mode does not work — use text mode.

### 30.1  Why the Virtual Robot Helps

When the physical robot is unavailable (or not yet bought), Choregraphe's
virtual robot lets you:

- See what gestures look like.
- Verify NAOqi services are reachable on `localhost:9559`.
- Test the `naoqi_client.py` end-to-end.
- Demo the system to others without hardware.

### 30.2  Limitations of the Virtual Robot

| Feature | Virtual | Real |
|---------|---------|------|
| ALAnimatedSpeech (TTS) | ✓ via PC speakers | ✓ via Pepper speakers |
| ALMotion gestures | ✓ in 3D view | ✓ on the robot |
| ALLeds | ✓ in 3D view | ✓ real LEDs |
| ALBehaviorManager (pre-installed behaviours) | ✓ | ✓ |
| ALAudioDevice (microphone) | **✗** | ✓ |
| ALTabletService | partial | ✓ |
| ALFaceDetection | **✗** (no camera) | ✓ |

The biggest limitation is the missing microphone. For OmniLLM testing,
that means **send text instead of audio**.

### 30.3  Three-Terminal Setup

```bash
# Terminal 1: Ollama (optional, for local models)
ollama serve

# Terminal 2: AI server
cd C:\Users\akshi\OneDrive\Desktop\OmniLLM
.venv\Scripts\activate
python -m omnillm.server.app --model llama3-8b-local
```

```
Choregraphe (GUI):
  • Open Choregraphe 2.5
  • Menu: Connection → Connect to virtual robot
  • Wait for the robot to appear in the 3D viewport
  • Status bar shows: "Connected to localhost:9559 (virtual)"
```

```bash
# Terminal 3: send a text question
curl -X POST http://localhost:5000/interact \
  -H "Content-Type: application/json" \
  -d '{"text":"Where is Room 305?","participant_id":"T","condition":"B"}'
```

Then in Choregraphe's Script Editor (Alt+5), play back the response to
see the virtual Pepper move:

```python
# Use the values returned by curl
tts = ALProxy("ALAnimatedSpeech", "localhost", 9559)
behavior = ALProxy("ALBehaviorManager", "localhost", 9559)
leds = ALProxy("ALLeds", "localhost", 9559)

leds.fadeRGB("FaceLeds", 0.0, 0.67, 1.0, 0.3)            # #00AAFF
behavior.post.runBehavior("animations/Stand/Gestures/Explain_8")  # point_left
tts.say("Room 305 is on your left on the third floor.",
        {"bodyLanguageMode": "contextual"})
```

### 30.4  Running the NAOqi Client Against the Virtual Robot

Once the virtual robot is connected in Choregraphe, you can also run the
full `naoqi_client.py` against it. The client will not be able to capture
real audio, but it will exercise everything else (HTTP, action dispatch,
NAOqi calls):

```bash
set PYTHONPATH=C:\pynaoqi\pynaoqi-python2.7-2.5.5.5-win32-vs2013\lib;%PYTHONPATH%
set PATH=C:\pynaoqi\pynaoqi-python2.7-2.5.5.5-win32-vs2013\lib;%PATH%

C:\Python27\python.exe omnillm\server\naoqi_client.py ^
    --robot-ip localhost ^
    --robot-port 9559 ^
    --server-ip localhost ^
    --server-port 5000 ^
    --participant TEST ^
    --condition B
```

### 30.5  Useful Quick-Tests in Choregraphe

These let you verify the underlying NAOqi services are healthy *before*
worrying about OmniLLM:

```python
# Test ALAnimatedSpeech
ALProxy("ALAnimatedSpeech", "localhost", 9559).say("OmniLLM ready.")

# Test ALMotion (must wakeUp first or you'll get a stiffness error)
m = ALProxy("ALMotion", "localhost", 9559)
m.wakeUp()
m.setStiffnesses("Body", 1.0)

# Test all of OmniLLM's gestures one by one
b = ALProxy("ALBehaviorManager", "localhost", 9559)
for behavior in [
    "animations/Stand/Gestures/Hey_1",          # wave
    "animations/Stand/Gestures/Explain_8",      # point_left
    "animations/Stand/Gestures/Explain_7",      # point_right
    "animations/Stand/Gestures/Explain_1",      # point_forward
    "animations/Stand/Emotions/Positive/Enthusiastic_1",  # nod
    "animations/Stand/Emotions/Neutral/Thinking_1",       # think
    "animations/Stand/Emotions/Negative/Confused_1",      # confused
]:
    if b.isBehaviorInstalled(behavior):
        b.runBehavior(behavior)
        time.sleep(2)
```

\newpage

## Chapter 31 — Running With a Physical Pepper

> **⚡ AT A GLANCE.** The full real-robot run. Connect to Pepper over
> Wi-Fi, run the AI server on your laptop, run the NAOqi client on
> Pepper (or your laptop with the SDK). Pepper greets, listens, replies
> with speech + gesture + LED.

### 31.1  Pre-Flight Checklist

Before connecting, check all of these:

- [ ] Pepper is powered on and showing a solid green chest LED.
- [ ] Pepper is plugged into a charger if the battery is below ~30%.
- [ ] Your PC and Pepper are on the **same Wi-Fi** (not a hotspot vs a
      LAN, not a cellular network).
- [ ] You can ping Pepper from your PC: `ping 192.168.1.100`.
- [ ] You can browse to Pepper's diagnostic page in a browser:
      `http://<pepper-ip>` (sometimes shows a status page).
- [ ] Your `.env` has the API keys for the conditions you'll use, **or**
      Ollama is running for condition B.

### 31.2  Find Pepper's IP

Press the **chest button** once. Pepper says:
*"My IP address is one nine two dot one six eight dot one dot one zero
zero. My battery is at eighty-two percent."*

Write down the IP. It probably won't change (DHCP usually re-leases the
same address) but it can.

### 31.3  Wake Pepper Up

A freshly-booted Pepper has zero stiffness — its motors are dead weight.
You must wake it before it can move:

**From Choregraphe:** right-click the robot in the 3D view → **Wake Up**.

**From a Python 2.7 one-liner:**
```bash
C:\Python27\python.exe -c ^
"from naoqi import ALProxy; ALProxy('ALMotion','192.168.1.100',9559).wakeUp()"
```

After waking up, Pepper will hold itself upright and the head will move.
This is normal.

### 31.4  Three-Terminal Run

```bash
# Terminal 1 (your PC): AI server
cd C:\Users\akshi\OneDrive\Desktop\OmniLLM
.venv\Scripts\activate
python -m omnillm.server.app --host 0.0.0.0 --port 5000

# Terminal 2 (your PC): find your local IP
ipconfig    # Windows — look for the 192.168.x.x of your Wi-Fi adapter

# Terminal 3 (your PC, Python 2.7): NAOqi client
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

Replace `192.168.1.100` with Pepper's IP and `192.168.1.50` with your PC's
IP. Pepper now greets:

> *"Hello! I am Pepper, powered by OmniLLM. How can I help you today?"*

### 31.5  Speaking to Pepper

Stand within ~1 metre of Pepper, facing the head microphones. Speak
clearly. The current `_record_audio` is a 5-second placeholder; you'll
need to replace it with `ALAudioRecorder` or callback-based capture for
production use (see Chapter 21.8). For now, use the text-mode workaround:

```python
# In naoqi_client.py, _interaction_loop, replace:
audio_bytes = self._record_audio(duration_seconds=5)
response = self._send_audio(audio_bytes)
# With:
text = raw_input("You: ")     # Python 2 input
response = self._send_text(text)
```

### 31.6  Live Monitoring With Choregraphe

Open Choregraphe and connect to the **same** Pepper IP. The 3D view will
mirror what the real robot is doing — useful for debugging. Choregraphe's
Log Viewer shows NAOqi messages in real time, including any service
errors.

> ⚠️ **Two clients can connect to one Pepper.** Choregraphe's connection
> is read-only by default when another client is actively driving the
> robot — you can monitor without conflicting.

### 31.7  Battery Management

Pepper's battery is the limiting factor in long sessions. Tactics:

- **Plug in between sessions.** Pepper can charge while idle in rest
  posture.
- **Plug in during sessions** if you have a long extension. Pepper can
  operate while plugged in.
- **Check battery programmatically:**

```python
battery = ALProxy("ALBattery", "192.168.1.100", 9559).getBatteryCharge()
# returns 0–100
```

Below ~15% Pepper enters safe mode and disables motors. Plan accordingly.

### 31.8  Cleanup at End of Session

Press `Ctrl+C` in the NAOqi client terminal. The `_cleanup()` method
calls `motion.rest()` which lowers Pepper into a safe rest posture.

\newpage

## Chapter 32 — Running an Experimental Session With a Real Participant

> **⚡ AT A GLANCE.** A complete protocol for running one participant
> through all five conditions of the Embodied LLM Arena. Total session
> time: ~30 minutes including questionnaire.

### 32.1  Materials

Before the participant arrives, prepare:

- [ ] **Consent form** (printed, two copies — one for them, one for you).
- [ ] **Participant ID** assigned (`P001`, `P002`, …).
- [ ] **Counterbalancing sheet** showing the order in which this
  participant will see conditions A–E (Latin square).
- [ ] **Task script** — the four task prompts each condition will have to
  handle.
- [ ] **Questionnaire form** (paper or Google Forms) ready.
- [ ] **Pepper charged** (>50%) and woken up.
- [ ] **AI server running** with all extras installed.

### 32.2  Pre-Session Briefing (~5 minutes)

> "Thank you for participating. Today you'll talk with our robot, Pepper,
> in a few different modes. After each mode you'll fill in a short
> questionnaire about your experience. The whole session is about 30
> minutes. You can stop at any time without giving a reason."
>
> "I'll explain the tasks now. You'll ask Pepper four kinds of question:
> first, a factual question about the lab; second, a navigation
> question; third, a casual conversation; fourth, the same again but in
> another language if you speak one. There are no right or wrong
> answers — we're studying *Pepper*, not *you*."

Sign the consent form. Note the participant's spoken languages.

### 32.3  The Per-Condition Loop

For each condition (in the participant's counterbalanced order):

```bash
# Terminal 3 — kill the previous client (Ctrl+C) and restart
C:\Python27\python.exe omnillm\server\naoqi_client.py ^
    --robot-ip 192.168.1.100 ^
    --server-ip 192.168.1.50 ^
    --participant P001 ^
    --condition <X>          # change for each condition
```

Run the four tasks (T1–T4). The experimenter prompts the participant:

| Task | Prompt to participant |
|------|----------------------|
| T1 (Info Retrieval) | "Ask Pepper a factual question about the lab — like the WiFi password, or what time it opens." |
| T2 (Navigation) | "Ask Pepper to direct you somewhere — like Room 305 or the cafeteria." |
| T3 (Social Conversation) | "Have a casual chat with Pepper — say hello, ask how it is, ask what it thinks about something." |
| T4 (Multilingual) | "If you speak another language, ask any of those questions again in that language." |

After all four tasks: hand the participant the questionnaire. While they
fill it in, save the data:

```bash
# Save logs incrementally
curl http://localhost:5000/export > results/session_P001_cond<X>.json
```

### 32.4  The Questionnaire

Five 1–7 Likert items (`InteractionQuestionnaire`):

1. The robot's answers were accurate.
2. The robot was natural to talk to.
3. I trust the information the robot gave me.
4. The robot's gestures were appropriate.
5. The robot responded quickly enough.

Optional Godspeed five-subscale (1–5 each, ~5 minutes longer):

- Anthropomorphism, Animacy, Likeability, Perceived Intelligence, Perceived Safety.

After the **last** condition, also run a **pairwise preference**:

> "Which version of Pepper did you prefer overall? Why?"

This produces the `PairwisePreference` records that update the ELO
leaderboard.

### 32.5  Post-Session

```bash
# Final export
curl http://localhost:5000/export > results/session_P001_full.json

# Save questionnaire scores via the API
curl -X POST http://localhost:5000/evaluate \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "P001-A",
    "participant_id": "P001",
    "condition": "A",
    "scores": {
      "accuracy": 6, "naturalness": 5, "trust": 6,
      "gesture_appropriateness": 5, "response_speed": 7
    }
  }'
```

Or programmatically populate `QuestionnaireCollector` and save:

```python
from omnillm.utils.questionnaire import (
    InteractionQuestionnaire, PairwisePreference, QuestionnaireCollector,
)

c = QuestionnaireCollector()
c.add_interaction_response(InteractionQuestionnaire(
    session_id="P001-A", participant_id="P001", condition="A",
    accuracy=6, naturalness=5, trust=6,
    gesture_appropriateness=5, response_speed=7,
))
# ... add the rest of the conditions ...
c.add_pairwise_preference(PairwisePreference(
    session_id="P001", participant_id="P001",
    condition_a="A", condition_b="C", preferred="C",
))
c.save("results/P001_questionnaires.json")
c.to_csv("results/P001_questionnaires.csv")
```

### 32.6  Daily Backups

After each participant, copy the `results/` folder to a separate
location (a USB stick, cloud drive, second laptop). Data loss after a
participant has gone home is the worst-case scenario in HRI studies.

\newpage
