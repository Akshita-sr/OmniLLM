# OmniLLM + Pepper Robot + Choregraphe: Complete Practical Guide

> **Author**: Akshita | **Last Updated**: April 2026
>
> This guide covers everything you need to run OmniLLM experiments with the Pepper robot and Choregraphe on your Windows PC, including: how to set up the environment, start every service, test without a physical robot, conduct real experiments with participants, and troubleshoot common issues like `ALAnimatedSpeech` failures.

---

## Table of Contents

1. [Your System Overview](#1-your-system-overview)
2. [Understanding the Architecture](#2-understanding-the-architecture)
3. [Environment Setup (One-Time)](#3-environment-setup-one-time)
4. [Starting the OmniLLM AI Server (Python 3.x)](#4-starting-the-omnillm-ai-server-python-3x)
5. [Starting Ollama for Local LLMs (Optional)](#5-starting-ollama-for-local-llms-optional)
6. [Using Choregraphe WITHOUT a Physical Pepper Robot](#6-using-choregraphe-without-a-physical-pepper-robot)
7. [Using Choregraphe WITH a Physical Pepper Robot](#7-using-choregraphe-with-a-physical-pepper-robot)
8. [Running the NAOqi Client to Connect Pepper to OmniLLM](#8-running-the-naoqi-client-to-connect-pepper-to-omnillm)
9. [Conducting Experiments with Participants](#9-conducting-experiments-with-participants)
10. [Troubleshooting: ALAnimatedSpeech and Other Module Errors](#10-troubleshooting-alanimatedspeech-and-other-module-errors)
11. [Troubleshooting: Common Issues and Fixes](#11-troubleshooting-common-issues-and-fixes)
12. [Quick Reference: All Commands in Order](#12-quick-reference-all-commands-in-order)
13. [Why Use a Robot? Motivation and Research Value](#13-why-use-a-robot-motivation-and-research-value)

---

## 1. Your System Overview

Your Windows PC has the following relevant installations:

| Component | Location | Version | Purpose |
|-----------|----------|---------|---------|
| **Python 2.7** | `C:\Python27\python.exe` | 2.7.18 | Required by NAOqi SDK (Pepper's native language) |
| **pynaoqi SDK** | `C:\pynaoqi\pynaoqi-python2.7-2.5.5.5-win32-vs2013\` | 2.5.5.5 | Python bindings to control Pepper hardware |
| **Choregraphe Suite** | `C:\Program Files (x86)\Aldebaran\Choregraphe Suite 2.5\` | 2.5.5.5 | Visual programming tool + virtual robot simulator |
| **OmniLLM Project** | `C:\Users\akshi\OneDrive\Desktop\OmniLLM\` | 0.1.0 | The AI server, LangGraph agent, RAG, experiment system |
| **Python 3.11+** | Your system Python / venv | 3.11+ | Required by OmniLLM AI stack |

**Key insight**: The Pepper robot runs on Python 2.7 (NAOqi SDK), but the OmniLLM AI stack needs Python 3.11+. These two cannot run in the same process. OmniLLM solves this with a **two-process HTTP bridge** architecture.

---

## 2. Understanding the Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  TERMINAL 1: OmniLLM AI Server (Python 3.11+)                  │
│  Location: C:\Users\akshi\OneDrive\Desktop\OmniLLM\            │
│                                                                  │
│  python -m omnillm.server.app --host 0.0.0.0 --port 5000       │
│                                                                  │
│  Runs: Whisper STT, LangGraph agent, LiteLLM gateway,          │
│        RAG pipeline, experiment logger                           │
│  Listens on: http://0.0.0.0:5000                                │
└──────────────────────────────┬──────────────────────────────────┘
                               │
                    HTTP POST /interact
                    (audio or text + session info)
                               │
                    HTTP JSON response
                    {"speech": "...", "gesture": "wave", "emotion_led": "#00FF88"}
                               │
┌──────────────────────────────┴──────────────────────────────────┐
│  TERMINAL 2: NAOqi Client (Python 2.7)                          │
│                                                                  │
│  C:\Python27\python.exe omnillm\server\naoqi_client.py          │
│      --robot-ip <PEPPER_IP> --server-ip localhost               │
│                                                                  │
│  Does: Records audio from Pepper's mic, sends to AI server,    │
│        receives response, executes speech + gesture + LEDs      │
│        on Pepper hardware via NAOqi                              │
└──────────────────────────────┬──────────────────────────────────┘
                               │
                    NAOqi SDK calls
                    (ALAnimatedSpeech, ALMotion, ALLeds, etc.)
                               │
┌──────────────────────────────┴──────────────────────────────────┐
│  PEPPER ROBOT (or Choregraphe Virtual Robot)                     │
│                                                                  │
│  Hardware: Microphones, speakers, motors, LEDs, tablet          │
│  NAOqi services: ALAnimatedSpeech, ALMotion, ALLeds,            │
│                  ALAudioDevice, ALBehaviorManager,               │
│                  ALTabletService, ALFaceDetection                │
└─────────────────────────────────────────────────────────────────┘
```

**In short**: You always need TWO terminals open:
1. **Terminal 1** (Python 3.x): The OmniLLM AI server
2. **Terminal 2** (Python 2.7): The NAOqi client that talks to Pepper

---

## 3. Environment Setup (One-Time)

### 3.1 Set the PYTHONPATH for pynaoqi

The NAOqi Python SDK needs to be on Python 2.7's path. You have two options:

**Option A: Set it permanently via Environment Variables (recommended)**

1. Open **Settings** > **System** > **About** > **Advanced system settings** > **Environment Variables**
2. Under **User variables for akshi**, click **New**:
   - Variable name: `PYTHONPATH`
   - Variable value: `C:\pynaoqi\pynaoqi-python2.7-2.5.5.5-win32-vs2013\lib`
3. Also add the pynaoqi lib to the **Path** variable:
   - Edit the `Path` variable and add: `C:\pynaoqi\pynaoqi-python2.7-2.5.5.5-win32-vs2013\lib`
4. Click OK and close. **Restart any open terminals** for changes to take effect.

**Option B: Set it per-session in the terminal**

```bash
# In Git Bash / MSYS2:
export PYTHONPATH="C:/pynaoqi/pynaoqi-python2.7-2.5.5.5-win32-vs2013/lib:$PYTHONPATH"

# In Windows CMD:
set PYTHONPATH=C:\pynaoqi\pynaoqi-python2.7-2.5.5.5-win32-vs2013\lib;%PYTHONPATH%

# In PowerShell:
$env:PYTHONPATH = "C:\pynaoqi\pynaoqi-python2.7-2.5.5.5-win32-vs2013\lib;$env:PYTHONPATH"
```

**Verify it works:**

```bash
C:\Python27\python.exe -c "import naoqi; print('NAOqi OK')"
```

If it prints `NAOqi OK`, you are set. If it fails, see [Troubleshooting](#11-troubleshooting-common-issues-and-fixes).

### 3.2 Set up the OmniLLM Python 3.x environment

```bash
cd C:\Users\akshi\OneDrive\Desktop\OmniLLM

# Create a virtual environment (if not already done)
python -m venv .venv

# Activate it
# Git Bash:
source .venv/Scripts/activate
# CMD:
.venv\Scripts\activate.bat
# PowerShell:
.venv\Scripts\Activate.ps1

# Install OmniLLM with all dependencies
pip install -e ".[all]"
```

### 3.3 Configure API keys

```bash
# Copy the example .env if you haven't already
cp .env.example .env

# Edit .env and fill in your API keys:
# OPENAI_API_KEY=sk-proj-...
# ANTHROPIC_API_KEY=sk-ant-...
# GOOGLE_API_KEY=AIzaSy...
# (etc.)
```

---

## 4. Starting the OmniLLM AI Server (Python 3.x)

Open **Terminal 1** (Git Bash, CMD, or PowerShell):

```bash
cd C:\Users\akshi\OneDrive\Desktop\OmniLLM

# Activate the Python 3.x virtual environment
source .venv/Scripts/activate   # Git Bash
# or: .venv\Scripts\activate.bat   # CMD

# Start the AI server
python -m omnillm.server.app --host 0.0.0.0 --port 5000
```

You should see:

```
INFO:omnillm.rag.pipeline:Indexed 12 chunks from lab_info.txt
INFO:omnillm.rag.pipeline:Indexed 8 chunks from faq.txt
INFO:omnillm.rag.pipeline:Knowledge base loaded — 42 total chunks
 * Running on all addresses (0.0.0.0)
 * Running on http://127.0.0.1:5000
```

**Test it's working** (open a new terminal or browser):

```bash
curl http://localhost:5000/health
# Should return: {"status": "ok", "version": "0.1.0"}

curl http://localhost:5000/status
# Returns: model list, RAG status, LangGraph availability
```

Or open `http://localhost:5000/health` in your browser.

**Server flags:**

| Flag | Purpose | Example |
|------|---------|---------|
| `--host` | Network interface to bind | `--host 0.0.0.0` (all interfaces) |
| `--port` | Port number | `--port 5000` |
| `--debug` | Enable Flask debug mode (auto-reload) | `--debug` |
| `--no-rag` | Disable the RAG pipeline | `--no-rag` |
| `--model` | Override default LLM model | `--model claude-sonnet` |
| `--kb` | Custom knowledge base directory | `--kb ./my_kb/` |

**Leave this terminal running.** The AI server must stay active for the entire experiment session.

---

## 5. Starting Ollama for Local LLMs (Optional)

If you want to use free, local LLMs (no API key needed), open **Terminal 2**:

```bash
ollama serve
```

Then in another terminal, pull the models you want:

```bash
ollama pull llama3:8b        # Meta Llama 3 (~4.7 GB)
ollama pull qwen2.5:7b       # Alibaba Qwen 2.5 (~4.4 GB)
ollama pull mistral:7b       # Mistral (~4.1 GB)
```

Ollama runs on `http://localhost:11434`. The OmniLLM server detects it automatically.

> **Note**: Local models are used in **Condition B** (fixed local LLM) of the experiment. If you only use cloud models (Conditions A, C, D, E), you can skip Ollama.

---

## 6. Using Choregraphe WITHOUT a Physical Pepper Robot

This is how you test and develop when no physical Pepper robot is available.

### 6.1 Launch Choregraphe

1. Navigate to: `C:\Program Files (x86)\Aldebaran\Choregraphe Suite 2.5\`
2. Open the `bin` folder
3. Double-click `choregraphe.exe`

Or use the shortcut: Start Menu > Aldebaran > Choregraphe 2.5.5

### 6.2 Connect to the Virtual Robot (Simulated Pepper)

When Choregraphe opens:

1. Go to **Connection** > **Connect to...** (or press `Ctrl+Shift+C`)
2. In the dialog, you should see a **virtual robot** already listed (or click **Connect to a virtual robot**)
3. If no virtual robot appears:
   - Click the **green robot icon** in the bottom toolbar (or go to **Connection** > **Connect to virtual robot**)
   - A virtual NAOqi process starts on `localhost:9559`
4. The virtual robot appears in the **3D view** panel (right side)

**What the virtual robot can and cannot do:**

| Feature | Works in Simulator? | Notes |
|---------|---------------------|-------|
| ALAnimatedSpeech (TTS) | Yes (audio through PC speakers) | Text is spoken via PC audio |
| ALMotion (gestures) | Yes (visible in 3D view) | Robot moves in the 3D panel |
| ALLeds (eye colors) | Yes (visible in 3D view) | LEDs change on the virtual robot face |
| ALBehaviorManager | Yes | Pre-installed behaviors work |
| ALAudioDevice (microphone) | **No** | No real mic input in simulator |
| ALTabletService (tablet) | **Partial** | No physical tablet; limited support |
| ALFaceDetection | **No** | No camera in simulator |

### 6.3 Test NAOqi Modules in Choregraphe's Script Editor

To verify that modules like ALAnimatedSpeech work:

1. In Choregraphe, go to the **Box libraries** panel (left side)
2. Drag a **Say** box onto the flow diagram
3. Double-click the **Say** box to edit the text
4. Type: `Hello, I am Pepper powered by OmniLLM`
5. Click the **Play** button (green triangle) at the top
6. The virtual robot should speak the text through your PC speakers and move its body

**To test via Python script inside Choregraphe:**

1. Go to **Edit** > **Script** (or press `Alt+5`)
2. In the Python script area, type:

```python
# This runs inside Choregraphe's Python 2.7 environment
tts = ALProxy("ALAnimatedSpeech", "localhost", 9559)
tts.say("Hello from OmniLLM!")

# Test motion
motion = ALProxy("ALMotion", "localhost", 9559)
motion.wakeUp()

# Test LEDs
leds = ALProxy("ALLeds", "localhost", 9559)
leds.fadeRGB("FaceLeds", 0.0, 1.0, 0.0, 0.5)  # Green eyes
```

3. Click **Run** to execute

### 6.4 Connect OmniLLM's NAOqi Client to the Virtual Robot

Since the virtual robot's microphone does not work, you will use **text mode** instead of audio:

**Step 1**: Make sure Choregraphe is running with the virtual robot connected (on `localhost:9559`).

**Step 2**: Open a new terminal and run the NAOqi client against `localhost`:

```bash
# Set pynaoqi on the path
set PYTHONPATH=C:\pynaoqi\pynaoqi-python2.7-2.5.5.5-win32-vs2013\lib;%PYTHONPATH%

# Run the client (pointing to virtual robot on localhost)
C:\Python27\python.exe C:\Users\akshi\OneDrive\Desktop\OmniLLM\omnillm\server\naoqi_client.py ^
    --robot-ip localhost ^
    --robot-port 9559 ^
    --server-ip localhost ^
    --server-port 5000 ^
    --participant P001 ^
    --condition A
```

> **Note**: Since the virtual robot has no microphone, the audio capture returns empty data. The client will still send requests to the AI server, and the virtual robot will speak responses through ALAnimatedSpeech and perform gestures visible in the 3D view.

**Step 3 (Alternative - Text mode for testing without mic)**: You can also test the AI server directly without the NAOqi client:

```bash
# Send a text query directly to the AI server
curl -X POST http://localhost:5000/interact ^
    -H "Content-Type: application/json" ^
    -d "{\"text\": \"Where is Room 305?\", \"participant_id\": \"P001\", \"session_id\": \"test-001\", \"condition\": \"A\"}"
```

This returns a RobotAction JSON like:

```json
{
    "speech": "Room 305 is on the third floor. Take the elevator and turn left.",
    "gesture": "point_left",
    "emotion_led": "#0088FF"
}
```

You can then manually test these actions in Choregraphe to see how they would look on the robot.

### 6.5 Testing Behaviors in Choregraphe's 3D View

To see what OmniLLM's gestures look like on the virtual robot:

1. In Choregraphe, go to **Box libraries** > **Movement** > **Animations**
2. Drag animation boxes onto the flow diagram:
   - `Gestures/Hey_1` (this is OmniLLM's "wave" gesture)
   - `Gestures/Explain_8` (this is "point_left")
   - `Gestures/Explain_7` (this is "point_right")
   - `Emotions/Neutral/Thinking_1` (this is "think")
   - `Emotions/Positive/Happy_4` (this is "happy")
3. Play them to see the animation in the 3D view

**OmniLLM's gesture mapping** (from `naoqi_client.py`):

| OmniLLM Gesture Name | Choregraphe Behavior Path |
|-----------------------|---------------------------|
| `wave` | `animations/Stand/Gestures/Hey_1` |
| `bow` | `animations/Stand/Gestures/BowShort_1` |
| `wave_goodbye` | `animations/Stand/Gestures/Farewells_1` |
| `point_left` | `animations/Stand/Gestures/Explain_8` |
| `point_right` | `animations/Stand/Gestures/Explain_7` |
| `point_forward` | `animations/Stand/Gestures/Explain_1` |
| `point_up` | `animations/Stand/Gestures/Explain_6` |
| `show_tablet` | `animations/Stand/Gestures/ShowTablet_1` |
| `nod` | `animations/Stand/Emotions/Positive/Enthusiastic_1` |
| `think` | `animations/Stand/Emotions/Neutral/Thinking_1` |
| `happy` | `animations/Stand/Emotions/Positive/Happy_4` |
| `confused` | `animations/Stand/Emotions/Negative/Confused_1` |

---

## 7. Using Choregraphe WITH a Physical Pepper Robot

### 7.1 Find Pepper's IP Address

There are several ways:

1. **Press the chest button once** — Pepper will say its IP address out loud (e.g., "My IP address is 192.168.1.100")
2. **Check your router's connected devices list** — Look for a device named "pepper" or a SoftBank Robotics MAC address
3. **If Pepper is on the same Wi-Fi** — it appears in Choregraphe's connection dialog automatically

### 7.2 Connect Choregraphe to the Physical Robot

1. Open Choregraphe: `C:\Program Files (x86)\Aldebaran\Choregraphe Suite 2.5\bin\choregraphe.exe`
2. Go to **Connection** > **Connect to...** (or `Ctrl+Shift+C`)
3. Enter Pepper's IP address: e.g., `192.168.1.100`
4. Port: `9559` (default NAOqi port)
5. Click **Connect**
6. The 3D view should now mirror the physical robot's posture

**Important**: Your PC and Pepper must be on the **same Wi-Fi network** (or connected via Ethernet to the same LAN).

### 7.3 Wake Up Pepper

If Pepper is in rest mode (hunched over, eyes dim):

**In Choregraphe**: Right-click the robot in the 3D view > **Wake Up**

**Or via Python**:
```python
motion = ALProxy("ALMotion", "192.168.1.100", 9559)
motion.wakeUp()
```

**Or from the terminal**:
```bash
C:\Python27\python.exe -c "from naoqi import ALProxy; ALProxy('ALMotion','192.168.1.100',9559).wakeUp()"
```

### 7.4 Test Basic Functions on the Physical Robot

Before running an experiment, verify Pepper's basic capabilities:

```bash
# Set pynaoqi path
set PYTHONPATH=C:\pynaoqi\pynaoqi-python2.7-2.5.5.5-win32-vs2013\lib;%PYTHONPATH%

# Test speech
C:\Python27\python.exe -c "from naoqi import ALProxy; ALProxy('ALAnimatedSpeech','192.168.1.100',9559).say('Hello, I am Pepper!')"

# Test LEDs (turn eyes green)
C:\Python27\python.exe -c "from naoqi import ALProxy; ALProxy('ALLeds','192.168.1.100',9559).fadeRGB('FaceLeds',0.0,1.0,0.0,0.5)"

# Test gesture (wave)
C:\Python27\python.exe -c "from naoqi import ALProxy; ALProxy('ALBehaviorManager','192.168.1.100',9559).runBehavior('animations/Stand/Gestures/Hey_1')"

# Check battery level
C:\Python27\python.exe -c "from naoqi import ALProxy; print(ALProxy('ALBattery','192.168.1.100',9559).getBatteryCharge())"
```

Replace `192.168.1.100` with Pepper's actual IP address.

### 7.5 Using Choregraphe to Monitor During Experiments

While an OmniLLM experiment is running, you can keep Choregraphe open to:

1. **Monitor the robot's state** in the 3D view (posture, LED colors)
2. **Check the Log Viewer** (View > Log Viewer) for NAOqi warnings/errors
3. **Inspect running behaviors** in the Behavior Manager panel
4. **Emergency stop**: Click the red **Stop** button in Choregraphe to immediately halt all robot movement

> **Tip**: Choregraphe and OmniLLM's NAOqi client can connect to the same robot simultaneously. Choregraphe is read-only by default when another client is controlling the robot.

---

## 8. Running the NAOqi Client to Connect Pepper to OmniLLM

This is the key step that bridges the physical Pepper robot to the OmniLLM AI server.

### 8.1 Prerequisites Checklist

Before running the client, confirm:

- [ ] **AI Server is running** (Terminal 1): `python -m omnillm.server.app --host 0.0.0.0 --port 5000`
- [ ] **Pepper is powered on** and on the same network as your PC
- [ ] **Pepper's IP is known** (e.g., `192.168.1.100`)
- [ ] **PYTHONPATH includes pynaoqi** (see Section 3.1)

### 8.2 Start the NAOqi Client

Open **Terminal 2** (separate from the AI server terminal):

```bash
# Windows CMD:
set PYTHONPATH=C:\pynaoqi\pynaoqi-python2.7-2.5.5.5-win32-vs2013\lib;%PYTHONPATH%

C:\Python27\python.exe C:\Users\akshi\OneDrive\Desktop\OmniLLM\omnillm\server\naoqi_client.py ^
    --robot-ip 192.168.1.100 ^
    --robot-port 9559 ^
    --server-ip localhost ^
    --server-port 5000 ^
    --participant P001 ^
    --condition C
```

```bash
# Git Bash:
export PYTHONPATH="C:/pynaoqi/pynaoqi-python2.7-2.5.5.5-win32-vs2013/lib:$PYTHONPATH"

C:/Python27/python.exe C:/Users/akshi/OneDrive/Desktop/OmniLLM/omnillm/server/naoqi_client.py \
    --robot-ip 192.168.1.100 \
    --robot-port 9559 \
    --server-ip localhost \
    --server-port 5000 \
    --participant P001 \
    --condition C
```

### 8.3 What Happens When the Client Starts

1. The client connects to Pepper via NAOqi at `192.168.1.100:9559`
2. It calls `ALMotion.wakeUp()` to wake up the robot
3. Pepper says: **"Hello! I am Pepper, powered by OmniLLM. How can I help you today?"**
4. The client enters its **interaction loop**:
   - Waits 5 seconds while recording audio from Pepper's front microphone
   - Sends the audio (base64-encoded WAV) to `http://localhost:5000/interact`
   - The AI server transcribes with Whisper, classifies the task, queries the LLM, plans gestures
   - The server returns a `RobotAction` JSON with `speech`, `gesture`, and `emotion_led`
   - The client executes the action on Pepper:
     - Sets LED color via `ALLeds.fadeRGB()`
     - Starts gesture via `ALBehaviorManager.post.runBehavior()`
     - Speaks response via `ALAnimatedSpeech.say()`
   - Loops back to recording

### 8.4 Command-Line Arguments Reference

| Argument | Default | Description |
|----------|---------|-------------|
| `--robot-ip` | `localhost` | IP address of the Pepper robot |
| `--robot-port` | `9559` | NAOqi SDK port |
| `--server-ip` | `localhost` | IP of the machine running the OmniLLM AI server |
| `--server-port` | `5000` | Port of the OmniLLM AI server |
| `--participant` | `P000` | Participant ID for logging (e.g., `P001`, `P002`) |
| `--condition` | `A` | Experimental condition: `A`, `B`, `C`, `D`, or `E` |

### 8.5 Simulation Mode (No NAOqi SDK)

If the NAOqi SDK is not available (e.g., `import naoqi` fails), the client automatically falls back to **simulation mode**:

- All speech, gesture, and LED commands are **printed to the terminal** instead of sent to the robot
- The audio recording returns empty bytes
- Useful for testing the AI server pipeline without hardware

```
[WARN] NAOqi SDK not available — running in simulation mode.
[SIM] SPEECH: Hello! I am Pepper, powered by OmniLLM. How can I help you today?
[...] Waiting for speech input...
[SIM] SPEECH: Room 305 is on the third floor. Take the elevator and turn left.
[SIM] GESTURE: animations/Stand/Gestures/Explain_8
[SIM] LED: #0088FF
```

---

## 9. Conducting Experiments with Participants

### 9.1 Experiment Design Overview

OmniLLM uses a **within-subjects design** with 5 experimental conditions:

| Condition | Name | What It Does |
|-----------|------|-------------|
| **A** | Fixed Cloud LLM (Baseline) | Uses GPT-4o-mini for all tasks. RAG enabled. |
| **B** | Fixed Local LLM | Uses Llama3:8b (via Ollama, free). RAG enabled. |
| **C** | Smart-Routed | Dynamically selects the best model per task type. RAG enabled. |
| **D** | Consensus Council | Queries 3 models and synthesizes the best answer. RAG enabled. |
| **E** | RAG-Off Control | Uses GPT-4o-mini but without RAG (no knowledge base). |

Each participant experiences multiple conditions (counterbalanced order) and rates each one.

### 9.2 Step-by-Step Experiment Procedure

**Before the participant arrives:**

1. **Start the AI server** (Terminal 1):
   ```bash
   cd C:\Users\akshi\OneDrive\Desktop\OmniLLM
   source .venv/Scripts/activate
   python -m omnillm.server.app --host 0.0.0.0 --port 5000
   ```

2. **Start Ollama** if using Condition B (Terminal 2, optional):
   ```bash
   ollama serve
   ```

3. **Wake up Pepper** and verify speech works:
   ```bash
   C:\Python27\python.exe -c "from naoqi import ALProxy; ALProxy('ALMotion','PEPPER_IP',9559).wakeUp()"
   C:\Python27\python.exe -c "from naoqi import ALProxy; ALProxy('ALAnimatedSpeech','PEPPER_IP',9559).say('System check. Ready.')"
   ```

4. **Position Pepper**: Place the robot facing the participant's chair, ~1 metre away, at table height.

5. **Open Choregraphe** (optional): Connect to Pepper for monitoring (Connection > Connect > Pepper IP).

**For each experimental condition:**

6. **Start the NAOqi client** with the correct participant ID and condition:
   ```bash
   set PYTHONPATH=C:\pynaoqi\pynaoqi-python2.7-2.5.5.5-win32-vs2013\lib;%PYTHONPATH%

   C:\Python27\python.exe C:\Users\akshi\OneDrive\Desktop\OmniLLM\omnillm\server\naoqi_client.py ^
       --robot-ip PEPPER_IP ^
       --server-ip localhost ^
       --participant P001 ^
       --condition A
   ```

7. **Brief the participant**: "Please speak naturally to the robot. Ask it questions about the lab, directions, or just have a conversation."

8. **Run the task set**: The participant asks Pepper 4 types of questions:
   - **T1 (Info Retrieval)**: "What time does the lab open?" / "What is the WiFi password?"
   - **T2 (Navigation)**: "Where is Room 305?" / "How do I get to the elevator?"
   - **T3 (Social Conversation)**: "How are you today?" / "Tell me about yourself"
   - **T4 (Multilingual)**: "Où se trouve la salle 305?" (French) / "Wo ist der Aufzug?" (German)

9. **Stop the NAOqi client** after the condition block: Press `Ctrl+C` in Terminal 2.

10. **Administer the questionnaire** — use the OmniLLM CLI or a paper form:

    ```bash
    # Via the CLI
    python -m omnillm evaluate --participant P001 --condition A
    ```

    Or submit via the API:
    ```bash
    curl -X POST http://localhost:5000/evaluate ^
        -H "Content-Type: application/json" ^
        -d "{\"session_id\": \"s1\", \"participant_id\": \"P001\", \"condition\": \"A\", \"scores\": {\"accuracy\": 6, \"naturalness\": 5, \"trust\": 6, \"gesture_appropriateness\": 5, \"response_speed\": 7}}"
    ```

    The questionnaire includes:
    - **Interaction Questionnaire** (5 items, 1-7 Likert): accuracy, naturalness, trust, gesture appropriateness, response speed
    - **Godspeed Scales** (Bartneck et al., 2009): anthropomorphism, animacy, likeability, perceived intelligence, perceived safety

11. **Repeat steps 6-10** for each condition (A through E), changing `--condition` each time.

12. **Pairwise preference** — at the end, ask: "Which version of the robot did you prefer?"

**After all participants:**

13. **Export all data**:
    ```bash
    curl http://localhost:5000/export > results/experiment_data.json
    ```

### 9.3 Tips for Smooth Experiments

- **Test everything 30 minutes before the first participant** — APIs can be down, Pepper's battery can be low.
- **Keep Pepper charged**: Plug in between sessions. Check battery: `ALProxy('ALBattery', IP, 9559).getBatteryCharge()`
- **Speak within 1 metre** of Pepper's front microphone for best audio capture.
- **If Pepper freezes**: Press the chest button for 3 seconds to soft-restart, or use Choregraphe's emergency stop.
- **If the AI server is slow**: Check which model is active. Condition D (Council) is slowest because it queries 3 models.
- **Counterbalance condition order**: If P001 gets A-B-C-D-E, P002 gets B-C-D-E-A, etc. (Latin square design).

---

## 10. Troubleshooting: ALAnimatedSpeech and Other Module Errors

### ALAnimatedSpeech Not Working

This is one of the most common issues. Here are the causes and solutions:

#### Cause 1: Robot is in "Rest" mode

**Symptom**: `ALAnimatedSpeech.say()` throws an error, or the robot speaks but does not move.

**Fix**: Wake up the robot first:
```python
from naoqi import ALProxy
motion = ALProxy("ALMotion", "PEPPER_IP", 9559)
motion.wakeUp()  # This MUST be called before ALAnimatedSpeech works properly
```

`ALAnimatedSpeech` requires the robot to be in "stand" posture to animate while speaking. If the robot is in rest mode (motors off), it can only use basic `ALTextToSpeech` (voice without body movement).

#### Cause 2: Stiffness is off

**Symptom**: Robot speaks but arms/body do not move.

**Fix**: Enable stiffness (motor power):
```python
motion = ALProxy("ALMotion", "PEPPER_IP", 9559)
motion.setStiffnesses("Body", 1.0)  # Enable all motors
```

#### Cause 3: `bodyLanguageMode` configuration error

**Symptom**: Error about configuration parameter.

**Fix**: Use the correct configuration dict:
```python
tts = ALProxy("ALAnimatedSpeech", "PEPPER_IP", 9559)

# Correct usage:
config = {"bodyLanguageMode": "contextual"}  # or "random" or "disabled"
tts.say("Hello!", config)

# The mode must be one of: "contextual", "random", "disabled"
# "contextual" = gestures match speech content (recommended)
# "random" = random gestures while speaking
# "disabled" = no body movement, voice only
```

#### Cause 4: NAOqi version mismatch

**Symptom**: `ALAnimatedSpeech` service not found.

**Fix**: `ALAnimatedSpeech` was introduced in NAOqi 2.x. If you are using NAOqi 1.x, use `ALTextToSpeech` instead:
```python
# NAOqi 1.x fallback
tts = ALProxy("ALTextToSpeech", "PEPPER_IP", 9559)
tts.say("Hello!")  # Voice only, no gestures
```

Your pynaoqi SDK is version 2.5.5.5, so `ALAnimatedSpeech` should be available.

#### Cause 5: Another behavior is already running

**Symptom**: `ALAnimatedSpeech.say()` blocks or times out.

**Fix**: Stop all running behaviors first:
```python
behavior = ALProxy("ALBehaviorManager", "PEPPER_IP", 9559)
behavior.stopAllBehaviors()

# Then try speaking again
tts = ALProxy("ALAnimatedSpeech", "PEPPER_IP", 9559)
tts.say("Hello!", {"bodyLanguageMode": "contextual"})
```

#### Cause 6: Virtual robot limitations in Choregraphe

**Symptom**: `ALAnimatedSpeech` works differently in the simulator than on real Pepper.

**Explanation**: In Choregraphe's virtual robot:
- Speech comes through your PC speakers (not robot speakers)
- Body animations are visible in the 3D view but may be less fluid
- Some behaviors that require physical sensors may not trigger
- This is normal — test on the real robot for final validation

### Other NAOqi Module Errors

| Module | Common Error | Fix |
|--------|-------------|-----|
| `ALAudioDevice` | "Service not available" | Only works on real robot or NAOqi process, not raw Python |
| `ALTabletService` | "Service not found" | Only available on Pepper (not NAO). Virtual robot has limited support |
| `ALFaceDetection` | "Service not available" | Requires camera — not available in simulator |
| `ALBehaviorManager` | "Behavior not installed" | Check behavior path: use `behavior.getInstalledBehaviors()` to list available ones |
| `ALMotion` | "DCM is not running" | Robot hardware issue — try restarting Pepper (hold chest button 5 sec) |
| Any module | "Connection refused" | Check IP address, check robot is on, check port 9559 |

---

## 11. Troubleshooting: Common Issues and Fixes

### "import naoqi" fails in Python 2.7

```
ImportError: No module named naoqi
```

**Fix**: Your PYTHONPATH does not include the pynaoqi lib directory.

```bash
# Check current PYTHONPATH
echo %PYTHONPATH%

# Set it correctly
set PYTHONPATH=C:\pynaoqi\pynaoqi-python2.7-2.5.5.5-win32-vs2013\lib;%PYTHONPATH%

# Verify
C:\Python27\python.exe -c "import naoqi; print('OK')"
```

The key files that must be accessible are:
- `C:\pynaoqi\pynaoqi-python2.7-2.5.5.5-win32-vs2013\lib\naoqi.py`
- `C:\pynaoqi\pynaoqi-python2.7-2.5.5.5-win32-vs2013\lib\_inaoqi.pyd`
- `C:\pynaoqi\pynaoqi-python2.7-2.5.5.5-win32-vs2013\lib\qi.py` (if using modern qi module)

### "Connection refused" when connecting to Pepper

```
[ERR] Failed to connect to Pepper: Connection refused
```

**Causes and fixes:**
1. **Wrong IP address** — Press Pepper's chest button to hear the current IP
2. **Different network** — Your PC and Pepper must be on the same Wi-Fi/LAN
3. **Pepper is off** — Check the chest LED is solid green
4. **Firewall blocking** — Temporarily disable Windows Firewall or add port 9559 exception
5. **NAOqi not started** — On rare occasions, NAOqi crashes on boot. Restart Pepper.

### AI server returns "Transcription failed"

```
{"error": "Whisper not installed — pip install openai-whisper"}
```

**Fix**: Install Whisper in your Python 3.x environment:
```bash
cd C:\Users\akshi\OneDrive\Desktop\OmniLLM
source .venv/Scripts/activate
pip install openai-whisper
```

### AI server returns "Response generation failed"

**Causes:**
1. **API key missing or invalid** — Check `.env` file has valid keys
2. **API rate limit** — Wait and retry, or switch to a different model
3. **Ollama not running** — If using Condition B (local LLM), start `ollama serve`
4. **Network issue** — Check internet connection for cloud models

### Choregraphe cannot find the virtual robot

1. Close and reopen Choregraphe
2. Go to **Edit** > **Preferences** > **Virtual Robot** and ensure "Autostart virtual NAOqi" is checked
3. Check if another instance of Choregraphe or NAOqi is already running (only one can use port 9559)
4. Try manually starting NAOqi: `C:\Program Files (x86)\Aldebaran\Choregraphe Suite 2.5\bin\naoqi-bin.exe`

### Pepper's battery is low during an experiment

- Pepper can be plugged in while operating (use the charger cable in the back)
- Check battery: `ALProxy('ALBattery', IP, 9559).getBatteryCharge()` (returns 0-100)
- Below 15%, Pepper will enter safe mode and disable motors

### Python 2.7 DLL load errors on Windows

```
ImportError: DLL load failed: The specified module could not be found.
```

This means the pynaoqi DLLs cannot find their dependencies (Boost, etc.).

**Fix**: Add the pynaoqi lib directory to your system PATH:
```bash
set PATH=C:\pynaoqi\pynaoqi-python2.7-2.5.5.5-win32-vs2013\lib;%PATH%
```

The `lib` directory contains many `.dll` files (boost, inaoqi, etc.) that must be discoverable.

---

## 12. Quick Reference: All Commands in Order

Here is the complete sequence of commands to run an experiment:

```bash
# ═══════════════════════════════════════════════════════════════
# TERMINAL 1: Start the OmniLLM AI Server (keep running)
# ═══════════════════════════════════════════════════════════════
cd C:\Users\akshi\OneDrive\Desktop\OmniLLM
.venv\Scripts\activate.bat
python -m omnillm.server.app --host 0.0.0.0 --port 5000


# ═══════════════════════════════════════════════════════════════
# TERMINAL 2 (Optional): Start Ollama for local models
# ═══════════════════════════════════════════════════════════════
ollama serve


# ═══════════════════════════════════════════════════════════════
# TERMINAL 3: Connect Pepper to OmniLLM
# ═══════════════════════════════════════════════════════════════
set PYTHONPATH=C:\pynaoqi\pynaoqi-python2.7-2.5.5.5-win32-vs2013\lib;%PYTHONPATH%
set PATH=C:\pynaoqi\pynaoqi-python2.7-2.5.5.5-win32-vs2013\lib;%PATH%

:: Replace PEPPER_IP with actual IP (e.g., 192.168.1.100)
:: Replace P001 with participant ID
:: Replace A with condition letter (A/B/C/D/E)

C:\Python27\python.exe C:\Users\akshi\OneDrive\Desktop\OmniLLM\omnillm\server\naoqi_client.py ^
    --robot-ip PEPPER_IP ^
    --server-ip localhost ^
    --participant P001 ^
    --condition A

:: Press Ctrl+C to stop after each condition block


# ═══════════════════════════════════════════════════════════════
# TERMINAL 4 (Optional): Test the AI server directly
# ═══════════════════════════════════════════════════════════════
:: Health check
curl http://localhost:5000/health

:: Send a test query
curl -X POST http://localhost:5000/interact ^
    -H "Content-Type: application/json" ^
    -d "{\"text\": \"Where is Room 305?\", \"participant_id\": \"TEST\", \"condition\": \"A\"}"

:: Export experiment data
curl http://localhost:5000/export > results/experiment_data.json


# ═══════════════════════════════════════════════════════════════
# CHOREGRAPHE (Optional): Visual monitoring
# ═══════════════════════════════════════════════════════════════
:: Open: C:\Program Files (x86)\Aldebaran\Choregraphe Suite 2.5\bin\choregraphe.exe
:: Connect to Pepper: Connection > Connect > enter PEPPER_IP
:: Or use virtual robot: Connection > Connect to virtual robot
```

---

## 13. Why Use a Robot? Motivation and Research Value

### The Core Question

OmniLLM is a platform for benchmarking LLMs. One might reasonably ask: *"Why involve a physical robot at all? You can benchmark LLMs perfectly well through a terminal, a web interface, or even automated scripts. Adding a robot introduces hardware complexity, Python 2.7 constraints, network latency, and physical logistics. What does the robot actually contribute?"*

This is a legitimate question, and the answer reveals why this research is genuinely valuable and not merely a technical demonstration.

### What the Robot Adds: Embodied Cognition and Social Presence

**1. Embodiment changes how humans evaluate AI responses.**

Research in Human-Robot Interaction (HRI) consistently shows that people evaluate the *same* AI-generated text differently depending on whether it comes from a screen, a disembodied voice, or a physical robot. This is known as the **embodiment effect** (Li, 2015; Wainer et al., 2006). A robot that gestures while explaining directions, makes eye contact via LED attention cues, and physically turns toward a room being discussed creates a fundamentally different evaluation context than reading the same text on a screen.

OmniLLM's experiment design explicitly tests this: **Condition E** (RAG-off, text-only baseline) versus **Conditions A-D** (same models but delivered through Pepper's embodied speech, gestures, and LEDs). If the LLM quality scores differ between conditions, the embodiment is a confounding — or contributing — variable that pure text benchmarks would completely miss.

**2. Multimodal interaction surfaces LLM strengths and weaknesses that text-only benchmarks cannot.**

When a person asks Pepper "Where is Room 305?" and the robot responds with speech + a pointing gesture + blue navigation LEDs, the user evaluates not just the text content but the *coherence of the full multimodal package*. A factually correct response that says "turn left" while the robot points right is a failure that no text-only benchmark would detect. OmniLLM's gesture planner and task classifier add layers of evaluation that are only meaningful in an embodied context.

**3. Real-time voice interaction exposes latency and naturalness issues invisible in text benchmarks.**

In a text benchmark, a model that takes 3 seconds vs 0.5 seconds both produce the same quality score. In a face-to-face conversation with a robot, that 3-second pause is the difference between a natural interaction and an awkward silence. OmniLLM logs latency per interaction and correlates it with participant satisfaction scores — data that is only ecologically valid when collected in a real-time conversational setting.

**4. Social robots are the deployment context that matters for service-oriented LLMs.**

The vision behind projects like OmniLLM is not just "which LLM is best at answering questions" but "which LLM is best at powering a helpful, trustworthy social robot in a lab, hospital, hotel, or campus?" This is a real and growing deployment scenario. University reception robots, hospital wayfinding robots, and retail assistant robots are increasingly integrating LLMs. Benchmarking these models *in situ* — through the actual robot platform they will be deployed on — produces results that are directly applicable to real-world deployment decisions, rather than abstract leaderboard rankings.

### Why This is Good Research

**1. It fills a genuine gap in the literature.**

The LLM benchmarking space (MMLU, HumanEval, MT-Bench, Chatbot Arena, etc.) is overwhelmingly text-based. There is a significant gap in **embodied LLM evaluation** — benchmarking LLMs as they perform in physical, social, real-time interactive settings. OmniLLM is one of the first platforms to systematically compare LLM routing strategies (fixed model, smart routing, consensus council, local vs. cloud) through a standardized embodied HRI experimental protocol.

**2. It uses validated, reproducible methodology.**

The experiment design uses established HRI evaluation instruments:
- **Godspeed Questionnaire Series** (Bartneck et al., 2009) — the most widely used standardized measure for robot perception in HRI
- **Likert-scale interaction quality measures** — aligned with prior work in social robot evaluation
- **Pairwise preference and ELO scoring** — the same methodology used by Chatbot Arena (LMSYS), adapted for embodied interaction
- **Latin square counterbalancing** — controls for order effects across conditions
- **Within-subjects design** — each participant experiences all conditions, maximizing statistical power

**3. It addresses practical deployment decisions.**

Real organizations choosing an LLM for their robot need to answer questions like:
- "Is a free local model (Llama) good enough, or do we need expensive cloud APIs (GPT-4o)?"
- "Does smart routing across multiple models actually improve perceived quality?"
- "Does RAG (retrieval-augmented generation) make a meaningful difference for domain-specific tasks?"
- "How much does response latency affect user satisfaction in face-to-face interaction?"

OmniLLM's five experimental conditions directly answer these questions with empirical data from real human participants interacting with a real robot.

**4. It bridges two communities that rarely talk to each other.**

The **LLM/NLP community** publishes benchmarks, leaderboards, and model comparisons. The **HRI community** publishes user studies with robots measuring social presence, trust, and perceived intelligence. OmniLLM sits at the intersection: it uses NLP tools (LiteLLM, LangGraph, ChromaDB, Whisper) within an HRI experimental framework (Godspeed, Likert, within-subjects design). This cross-pollination is where the most impactful and novel contributions emerge.

**5. The platform itself is a contribution.**

Beyond the experiment results, the OmniLLM platform — with its modular architecture, 19+ registered models, pluggable robot bridges, automated experiment logging, and questionnaire system — is a reusable research tool. Other HRI researchers can adopt it for their own embodied LLM studies, swapping in their own robots (NAO, Buddy, or custom platforms), knowledge bases, and experimental conditions. This is the kind of research infrastructure that accelerates an entire subfield.

### In Summary

Using a robot is not a complication added for novelty — it is the *entire point*. OmniLLM is testing the hypothesis that **how an LLM is embodied and delivered matters as much as the model's raw capability**. A model that scores highest on MMLU might not produce the best human experience when delivered through a social robot. The only way to test this is to actually put the models in a robot and have real people interact with them. That is what OmniLLM does, and that is what makes this research valuable.

---

*This guide is part of the [OmniLLM](https://github.com/Akshita-sr/OmniLLM) project. For additional documentation, see [README.md](README.md), [GETTING_STARTED.md](GETTING_STARTED.md), and [EXPLANATION.md](EXPLANATION.md).*
