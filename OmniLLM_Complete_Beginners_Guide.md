# OmniLLM + Choregraphe: Complete Beginner's Guide (Local Models Only, No Physical Robot)

> **Author**: Akshita | **Last Updated**: April 2026
>
> This guide is for absolute beginners who want to test OmniLLM using **Choregraphe's virtual robot** and **local LLMs via Ollama** — no physical Pepper robot, no cloud API keys, no cost.

---

## Table of Contents

1. [What is Choregraphe? (Beginner Overview)](#1-what-is-choregraphe-beginner-overview)
2. [What You Need Installed](#2-what-you-need-installed)
3. [Step 1 — Start Ollama (Your Free Local LLM)](#3-step-1--start-ollama-your-free-local-llm)
4. [Step 2 — Start the OmniLLM AI Server](#4-step-2--start-the-omnillm-ai-server)
5. [Step 3 — Open and Learn Choregraphe](#5-step-3--open-and-learn-choregraphe)
6. [Step 4 — Connect to the Virtual Robot](#6-step-4--connect-to-the-virtual-robot)
7. [Step 5 — Test the Virtual Robot (Your First Interactions)](#7-step-5--test-the-virtual-robot-your-first-interactions)
8. [Step 6 — Connect OmniLLM to the Virtual Robot](#8-step-6--connect-omnillm-to-the-virtual-robot)
9. [Step 7 — Test the Full Pipeline (OmniLLM + Virtual Pepper)](#9-step-7--test-the-full-pipeline-omnillm--virtual-pepper)
10. [Choregraphe Interface Tour (Beginner's Walkthrough)](#10-choregraphe-interface-tour-beginners-walkthrough)
11. [Creating Your First Choregraphe Behavior](#11-creating-your-first-choregraphe-behavior)
12. [How Choregraphe Fits Into OmniLLM's Architecture](#12-how-choregraphe-fits-into-omnillms-architecture)
13. [Useful GitHub Repos for Choregraphe + LLMs](#13-useful-github-repos-for-choregraphe--llms)
14. [Troubleshooting](#14-troubleshooting)
15. [Quick Reference — All Commands in Order](#15-quick-reference--all-commands-in-order)
16. [Glossary](#16-glossary)

---

## 1. What is Choregraphe? (Beginner Overview)

**Choregraphe** is a desktop application made by Aldebaran (the company that built Pepper and NAO robots). Think of it as a **visual remote control + simulator + programming tool** for Pepper.

### What it lets you do:

| Feature | What it means |
|---------|---------------|
| **3D Robot Simulator** | A virtual Pepper robot appears on screen. You can see it move, gesture, change eye colors — all without a physical robot |
| **Visual Programming** | Drag-and-drop "boxes" to make the robot speak, wave, walk, etc. No coding required for basic actions |
| **Python Scripting** | Write Python 2.7 scripts that control the robot (speech, gestures, LEDs, etc.) |
| **Behavior Testing** | Test animations and behaviors before running them on a real robot |
| **NAOqi Connection** | Connects to the robot's "brain" (NAOqi) either on a real Pepper or a simulated one on your PC |

### Key concepts for beginners:

- **NAOqi** = The robot's operating system / brain. It runs services like speech (`ALAnimatedSpeech`), movement (`ALMotion`), and LED control (`ALLeds`). When you "connect to the virtual robot," Choregraphe starts a NAOqi process on your PC at `localhost:9559`.
- **ALProxy** = A Python function that lets you talk to NAOqi services. For example, `ALProxy("ALAnimatedSpeech", "localhost", 9559)` gives you a handle to the speech service.
- **Behaviors** = Pre-built animations (wave, bow, point, dance, etc.) that the robot can play. They live in folders like `animations/Stand/Gestures/Hey_1`.
- **Boxes** = The drag-and-drop visual blocks in Choregraphe. Each box does one thing (say text, play animation, wait, etc.). You connect boxes together to create sequences.
- **Flow Diagram** = The main canvas where you connect boxes. Execution flows from left to right.

### Why do we use Choregraphe with OmniLLM?

OmniLLM is the AI brain (it decides *what* Pepper should say and do). Choregraphe is the body simulator (it shows you *how* Pepper would look and sound while doing it). Together, you can test the full experience — from "user asks a question" to "Pepper speaks the answer while waving" — entirely on your laptop.

---

## 2. What You Need Installed

Before you start, make sure you have these on your PC:

| Component | How to check | If missing |
|-----------|-------------|------------|
| **Choregraphe 2.5** | Look in `C:\Program Files (x86)\Aldebaran\Choregraphe Suite 2.5\` | You should already have this installed |
| **Python 2.7** | Run `C:\Python27\python.exe --version` in CMD | Download from python.org/downloads/release/python-2718 |
| **pynaoqi SDK** | Run `C:\Python27\python.exe -c "import naoqi; print('OK')"` | Should be at `C:\pynaoqi\` |
| **Python 3.11+** | Run `python --version` in CMD | Download from python.org |
| **Ollama** | Run `ollama --version` in CMD | Download from ollama.com |
| **OmniLLM** | The project folder at `C:\Users\akshi\OneDrive\Desktop\OmniLLM\` | You already have this |

---

## 3. Step 1 — Start Ollama (Your Free Local LLM)

Ollama runs LLMs locally on your PC — completely free, no API keys, no internet required after downloading.

### 3.1 Open a terminal (CMD or PowerShell) and start the Ollama server:

```cmd
ollama serve
```

You should see:
```
Listening on 127.0.0.1:11434
```

**Leave this terminal open.** Ollama needs to keep running.

### 3.2 Open a SECOND terminal and pull the models you want:

```cmd
:: Pull Llama 3 (Meta's model, ~4.7 GB download, only needed once)
ollama pull llama3:8b

:: Optional: Pull more models for variety
ollama pull qwen2.5:7b
ollama pull mistral:7b
```

> **How long does this take?** The first download takes 5-15 minutes depending on your internet. After that, the model is cached locally and starts instantly.

### 3.3 Quick test — make sure Ollama works:

```cmd
ollama run llama3:8b "Hello, who are you?"
```

You should get a response like: *"Hello! I'm LLaMA, a large language model trained by Meta AI..."*

Press `Ctrl+C` to exit the interactive mode and go back to the terminal.

### 3.4 Verify the API is accessible:

```cmd
curl http://localhost:11434/api/tags
```

This should return a JSON list of your downloaded models. If `curl` is not available, open `http://localhost:11434` in your browser — you should see "Ollama is running".

---

## 4. Step 2 — Start the OmniLLM AI Server

The AI server is the "brain" that processes questions and generates answers using your local Ollama models.

### 4.1 Open a NEW terminal (Terminal 2):

```cmd
cd C:\Users\akshi\OneDrive\Desktop\OmniLLM

:: Activate the Python 3.x virtual environment
:: In CMD:
venv\Scripts\activate.bat
:: In PowerShell:
venv\Scripts\Activate.ps1
:: In Git Bash:
source venv/Scripts/activate
```

### 4.2 Start the server pointing to a LOCAL model:

```cmd
:: Use llama3:8b as the default model (free, local, no API key)
python -m omnillm.server.app --host 0.0.0.0 --port 5000 --model llama3-8b-local
```

You should see output like:
```
INFO:omnillm.rag.pipeline:Indexed 12 chunks from lab_info.txt
INFO:omnillm.rag.pipeline:Knowledge base loaded — 42 total chunks
 * Running on all addresses (0.0.0.0)
 * Running on http://127.0.0.1:5000
```

> **What does `--model llama3-8b-local` mean?** This tells OmniLLM to use the local Llama 3 model through Ollama instead of cloud APIs. No internet or API keys needed.

### 4.3 Quick test — verify the server is alive:

Open a THIRD terminal (or your browser):

```cmd
:: Health check
curl http://localhost:5000/health
```

Expected response:
```json
{"status": "ok", "version": "0.1.0"}
```

```cmd
:: Full status (shows models, RAG status, etc.)
curl http://localhost:5000/status
```

### 4.4 Test a question (text mode):

```cmd
curl -X POST http://localhost:5000/interact -H "Content-Type: application/json" -d "{\"text\": \"Where is Room 305?\", \"participant_id\": \"TEST\", \"session_id\": \"test-001\", \"condition\": \"B\"}"
```

> **Why `condition B`?** Condition B = fixed local LLM. This ensures the server uses your Ollama model.

Expected response (something like):
```json
{
    "speech": "Room 305 is on the third floor of Building C...",
    "gesture": "point_left",
    "emotion_led": "#0088FF"
}
```

If you get a response, your AI server is working. **Leave this terminal running.**

---

## 5. Step 3 — Open and Learn Choregraphe

Now let's open Choregraphe and get familiar with it.

### 5.1 Launch Choregraphe:

**Option A** — From the Start Menu:
- Click Start > search for "Choregraphe" > click "Choregraphe 2.5.5"

**Option B** — From the file system:
- Navigate to: `C:\Program Files (x86)\Aldebaran\Choregraphe Suite 2.5\bin\`
- Double-click `choregraphe.exe`

**Option C** — From a terminal:
```cmd
"C:\Program Files (x86)\Aldebaran\Choregraphe Suite 2.5\bin\choregraphe.exe"
```

### 5.2 First launch — what you see:

When Choregraphe opens, you'll see several panels. Don't be overwhelmed — here's what each one does:

```
┌─────────────────────────────────────────────────────────────────────────┐
│  Menu bar: File | Edit | Connection | View | Help                       │
├──────────────┬──────────────────────────────┬───────────────────────────┤
│              │                              │                           │
│  BOX         │     FLOW DIAGRAM             │      3D ROBOT VIEW        │
│  LIBRARIES   │     (main canvas)            │      (virtual Pepper)     │
│              │                              │                           │
│  This is     │     This is where you        │      This is where you    │
│  your        │     drag boxes and           │      see the virtual      │
│  toolbox     │     connect them             │      robot move and       │
│  of robot    │     together to create       │      gesture. It updates  │
│  actions     │     behavior sequences       │      in real-time when    │
│              │                              │      you play behaviors   │
│              │                              │                           │
├──────────────┴──────────────────────────────┴───────────────────────────┤
│  LOG VIEWER / SCRIPT EDITOR (bottom panel)                              │
│  Shows output messages, errors, and lets you write Python scripts       │
└─────────────────────────────────────────────────────────────────────────┘
```

**Key panels:**
- **Box Libraries (left)**: Your toolbox. Contains categories like "Speech," "Movement," "LEDs," etc.
- **Flow Diagram (center)**: The main workspace. Drag boxes here and connect them.
- **3D Robot View (right)**: Shows the virtual Pepper. You'll see it move when you play behaviors.
- **Log Viewer (bottom)**: Shows system messages and errors. Very useful for debugging.

### 5.3 Important toolbar buttons:

| Button | What it does |
|--------|-------------|
| **Green Play triangle** | Plays the current flow diagram on the connected robot |
| **Red Stop square** | Immediately stops all running behaviors |
| **Green robot icon** (bottom bar) | Connects to / starts the virtual robot |
| **Connection indicator** (bottom bar) | Shows if you're connected (green = connected, red = disconnected) |

---

## 6. Step 4 — Connect to the Virtual Robot

This is the key step — you need to tell Choregraphe to start a virtual Pepper on your PC.

### 6.1 Connect to the virtual robot:

1. In Choregraphe, go to the menu: **Connection** > **Connect to virtual robot**
   - OR click the **green robot icon** in the bottom toolbar
   - OR press `Ctrl+Shift+C` and click "Connect to a virtual robot"

2. Wait a few seconds. Choregraphe starts a NAOqi process on `localhost:9559`.

3. You should see:
   - The **3D view** (right panel) shows a Pepper robot standing upright
   - The **connection indicator** (bottom bar) turns green
   - The **Log Viewer** shows something like: `[INFO] Connected to virtual robot on localhost:9559`

### 6.2 If the virtual robot doesn't appear:

1. Go to **Edit** > **Preferences** > **Virtual Robot**
2. Make sure "Autostart virtual NAOqi" is checked
3. Set the robot model to **Pepper** (not NAO)
4. Click OK, then try **Connection** > **Connect to virtual robot** again

### 6.3 Verify the connection:

The bottom status bar should show:
```
Connected to localhost:9559 (virtual)
```

If you see this, you're ready.

---

## 7. Step 5 — Test the Virtual Robot (Your First Interactions)

Let's make the virtual Pepper do things to confirm everything works.

### 7.1 Make Pepper speak (drag-and-drop method):

1. In the **Box Libraries** panel (left side), expand **Speech**
2. Find the **Say** box and drag it onto the **Flow Diagram** (center canvas)
3. Double-click the **Say** box — a text field appears
4. Type: `Hello! I am Pepper, powered by OmniLLM. Nice to meet you!`
5. Click the **Play** button (green triangle in the top toolbar)

**What happens:**
- You hear the speech through your PC speakers (the virtual robot speaks!)
- The virtual Pepper in the 3D view moves its mouth and makes small gestures
- The Log Viewer shows the execution status

### 7.2 Make Pepper wave:

1. In **Box Libraries**, expand **Movement** > **Animations** > **Gestures**
2. Drag **Hey_1** onto the flow diagram (this is a wave gesture)
3. Connect the output of the **Say** box to the input of the **Hey_1** box:
   - Click the small circle on the right side of the Say box
   - Drag it to the small circle on the left side of the Hey_1 box
4. Click **Play**

**What happens:**
- Pepper speaks first, then waves (because they're connected in sequence)
- You can see the wave animation in the 3D view

### 7.3 Make Pepper's eyes change color:

1. In **Box Libraries**, expand **LEDs**
2. Drag a **Set LEDs** box onto the flow diagram
3. Double-click it and set the color to green
4. Connect it after the wave gesture
5. Click **Play**

**What happens:**
- Pepper speaks > waves > eyes turn green
- You built your first behavior sequence!

### 7.4 Test via Python script (more powerful):

1. Go to **View** > **Script Editor** (or press `Alt+5`)
2. In the script area at the bottom, type:

```python
# Make Pepper speak with animated gestures
tts = ALProxy("ALAnimatedSpeech", "localhost", 9559)
tts.say("I can answer questions about the lab, give directions, and chat with you!")

# Make Pepper wave
behavior = ALProxy("ALBehaviorManager", "localhost", 9559)
behavior.runBehavior("animations/Stand/Gestures/Hey_1")

# Change Pepper's eye color to blue
leds = ALProxy("ALLeds", "localhost", 9559)
leds.fadeRGB("FaceLeds", 0.0, 0.5, 1.0, 0.5)

# Make Pepper think (tilt head, look away)
behavior.runBehavior("animations/Stand/Emotions/Neutral/Thinking_1")

# Make Pepper happy (smile gesture)
behavior.runBehavior("animations/Stand/Emotions/Positive/Happy_4")
```

3. Click **Run** (or press F5)
4. Watch the virtual Pepper perform each action in sequence

### 7.5 Test all OmniLLM gestures in Choregraphe:

These are the gestures that OmniLLM's AI can trigger. Test each one to see what they look like:

```python
# Run these one at a time in the Script Editor to see each gesture

behavior = ALProxy("ALBehaviorManager", "localhost", 9559)

# Greeting gestures
behavior.runBehavior("animations/Stand/Gestures/Hey_1")           # wave
behavior.runBehavior("animations/Stand/Gestures/BowShort_1")      # bow
behavior.runBehavior("animations/Stand/Gestures/Farewells_1")     # goodbye wave

# Pointing gestures (for navigation answers)
behavior.runBehavior("animations/Stand/Gestures/Explain_8")       # point left
behavior.runBehavior("animations/Stand/Gestures/Explain_7")       # point right
behavior.runBehavior("animations/Stand/Gestures/Explain_1")       # point forward
behavior.runBehavior("animations/Stand/Gestures/Explain_6")       # point up

# Emotion gestures
behavior.runBehavior("animations/Stand/Emotions/Neutral/Thinking_1")    # thinking
behavior.runBehavior("animations/Stand/Emotions/Positive/Happy_4")      # happy
behavior.runBehavior("animations/Stand/Emotions/Negative/Confused_1")   # confused
behavior.runBehavior("animations/Stand/Emotions/Positive/Enthusiastic_1") # nod
```

---

## 8. Step 6 — Connect OmniLLM to the Virtual Robot

Now let's connect the AI brain (OmniLLM server) to the virtual Pepper body (Choregraphe).

### What you should have running at this point:

| Terminal | What's running | Status |
|----------|---------------|--------|
| Terminal 1 | `ollama serve` | Ollama server running on port 11434 |
| Terminal 2 | `python -m omnillm.server.app ...` | OmniLLM AI server running on port 5000 |
| Choregraphe | Virtual robot connected | Green connection indicator, virtual Pepper visible |

### 8.1 Open a NEW terminal (Terminal 3) for the NAOqi client:

This is the bridge script that connects the OmniLLM AI server to Pepper (virtual or real).

**In Windows CMD:**
```cmd
:: Step 1: Set the pynaoqi path so Python 2.7 can find the NAOqi SDK
set PYTHONPATH=C:\pynaoqi\pynaoqi-python2.7-2.5.5.5-win32-vs2013\lib;%PYTHONPATH%
set PATH=C:\pynaoqi\pynaoqi-python2.7-2.5.5.5-win32-vs2013\lib;%PATH%

:: Step 2: Run the NAOqi client pointing to the VIRTUAL robot (localhost)
C:\Python27\python.exe C:\Users\akshi\OneDrive\Desktop\OmniLLM\omnillm\server\naoqi_client.py ^
    --robot-ip localhost ^
    --robot-port 9559 ^
    --server-ip localhost ^
    --server-port 5000 ^
    --participant TEST001 ^
    --condition B
```

**In Git Bash:**
```bash
# Step 1: Set the pynaoqi path
export PYTHONPATH="C:/pynaoqi/pynaoqi-python2.7-2.5.5.5-win32-vs2013/lib:$PYTHONPATH"

# Step 2: Run the NAOqi client
C:/Python27/python.exe C:/Users/akshi/OneDrive/Desktop/OmniLLM/omnillm/server/naoqi_client.py \
    --robot-ip localhost \
    --robot-port 9559 \
    --server-ip localhost \
    --server-port 5000 \
    --participant TEST001 \
    --condition B
```

**In PowerShell:**
```powershell
# Step 1: Set the pynaoqi path
$env:PYTHONPATH = "C:\pynaoqi\pynaoqi-python2.7-2.5.5.5-win32-vs2013\lib;$env:PYTHONPATH"

# Step 2: Run the NAOqi client
C:\Python27\python.exe C:\Users\akshi\OneDrive\Desktop\OmniLLM\omnillm\server\naoqi_client.py `
    --robot-ip localhost `
    --robot-port 9559 `
    --server-ip localhost `
    --server-port 5000 `
    --participant TEST001 `
    --condition B
```

### 8.2 What each flag means:

| Flag | Value | Meaning |
|------|-------|---------|
| `--robot-ip localhost` | `localhost` | Connect to the **virtual** robot in Choregraphe (not a physical one) |
| `--robot-port 9559` | `9559` | Default NAOqi port (Choregraphe uses this) |
| `--server-ip localhost` | `localhost` | The OmniLLM AI server is on this same PC |
| `--server-port 5000` | `5000` | Port the AI server is listening on |
| `--participant TEST001` | Any ID | Identifies this test session in the logs |
| `--condition B` | `B` | Use the local LLM (Ollama/Llama3). Use `B` for local-only testing |

### 8.3 What happens when you run this:

```
[INFO] Connecting to Pepper at localhost:9559...
[INFO] Connected to virtual robot
[INFO] Waking up robot...
[INFO] SPEECH: Hello! I am Pepper, powered by OmniLLM. How can I help you today?
[INFO] Entering interaction loop...
[INFO] Recording audio (5 seconds)...
```

In Choregraphe's 3D view, you should see the virtual Pepper:
- Stand up straight (wakeUp)
- Speak the greeting (you hear it through your PC speakers)
- Start the interaction loop

### 8.4 Important limitation: Virtual robot has NO microphone

The virtual robot cannot record audio from your physical microphone. The interaction loop will capture empty audio, which means Whisper will transcribe silence. This is normal for virtual testing.

**Solutions:**
- Use **text mode** to test the AI pipeline (see Step 7 below)
- The NAOqi client will still send requests to the AI server and execute responses on the virtual robot
- For full voice testing, you need a physical Pepper robot

---

## 9. Step 7 — Test the Full Pipeline (OmniLLM + Virtual Pepper)

Since the virtual robot can't hear you, use text mode to send questions and watch the virtual Pepper respond.

### 9.1 Send questions via curl (in a NEW terminal):

```cmd
:: Test 1: Information retrieval — "What time does the lab open?"
curl -X POST http://localhost:5000/interact ^
    -H "Content-Type: application/json" ^
    -d "{\"text\": \"What time does the lab open?\", \"participant_id\": \"TEST001\", \"session_id\": \"test-001\", \"condition\": \"B\"}"
```

**Expected response:**
```json
{
    "speech": "The lab opens at 8 AM on weekdays and 10 AM on weekends.",
    "gesture": "nod",
    "emotion_led": "#00FF88"
}
```

```cmd
:: Test 2: Navigation — "Where is Room 305?"
curl -X POST http://localhost:5000/interact ^
    -H "Content-Type: application/json" ^
    -d "{\"text\": \"Where is Room 305?\", \"participant_id\": \"TEST001\", \"session_id\": \"test-002\", \"condition\": \"B\"}"
```

```cmd
:: Test 3: Social conversation — "How are you today?"
curl -X POST http://localhost:5000/interact ^
    -H "Content-Type: application/json" ^
    -d "{\"text\": \"How are you today?\", \"participant_id\": \"TEST001\", \"session_id\": \"test-003\", \"condition\": \"B\"}"
```

```cmd
:: Test 4: Multilingual — "Ou est la salle 305?" (French)
curl -X POST http://localhost:5000/interact ^
    -H "Content-Type: application/json" ^
    -d "{\"text\": \"Ou est la salle 305?\", \"participant_id\": \"TEST001\", \"session_id\": \"test-004\", \"condition\": \"B\"}"
```

### 9.2 Manually play the response on the virtual robot:

After you get a response from the AI server, you can manually execute the actions in Choregraphe's script editor to see what they would look like on the robot:

```python
# Copy the "speech" from the AI response and play it
tts = ALProxy("ALAnimatedSpeech", "localhost", 9559)
tts.say("The lab opens at 8 AM on weekdays and 10 AM on weekends.")

# Copy the "gesture" from the AI response and play it
behavior = ALProxy("ALBehaviorManager", "localhost", 9559)
behavior.runBehavior("animations/Stand/Emotions/Positive/Enthusiastic_1")  # "nod"

# Convert the "emotion_led" hex color to RGB and set it
leds = ALProxy("ALLeds", "localhost", 9559)
leds.fadeRGB("FaceLeds", 0.0, 1.0, 0.53, 0.5)  # #00FF88 = green-ish
```

### 9.3 What to verify (checklist):

- [ ] Ollama responds to queries (test with `ollama run llama3:8b "hello"`)
- [ ] AI server returns valid JSON with `speech`, `gesture`, and `emotion_led` fields
- [ ] RAG is working (answers about the lab should reference specific knowledge base info)
- [ ] Task classification works (navigation questions get pointing gestures, social gets nods/smiles)
- [ ] Virtual robot speaks through PC speakers when you run scripts in Choregraphe
- [ ] Virtual robot animates gestures visibly in the 3D view
- [ ] Virtual robot eye LEDs change color in the 3D view

---

## 10. Choregraphe Interface Tour (Beginner's Walkthrough)

### 10.1 The Menu Bar

| Menu | Key items |
|------|-----------|
| **File** | New Project, Open Project, Save Project |
| **Edit** | Preferences (robot type, virtual robot settings), Script Editor |
| **Connection** | Connect to virtual robot, Connect to real robot (by IP), Disconnect |
| **View** | Toggle panels: Box Libraries, Flow Diagram, 3D View, Log Viewer, Script Editor |
| **Help** | Documentation, About |

### 10.2 Box Libraries Panel (Left)

This is your toolbox. Categories include:

| Category | What's inside |
|----------|---------------|
| **Speech** | Say (text-to-speech), Animated Say (speech + gestures), Listen (voice recognition) |
| **Movement** > **Animations** | Pre-built animations organized by: Gestures, Emotions, Reactions, Dances |
| **Movement** > **Postures** | Stand, Sit, Crouch, Rest |
| **LEDs** | Set LED color, Blink, Rainbow, etc. |
| **Sensing** | Face detection, Touch sensors, Sonar |
| **Flow Control** | Wait, Switch, Counter, Timer |

### 10.3 Flow Diagram (Center)

- **onStart** (left edge): This is where execution begins when you press Play
- **onStop** (right edge): This is where execution ends
- Boxes have **input** (left circle) and **output** (right circle) connectors
- Connect output of one box to input of another to create a sequence
- Boxes execute from left to right

### 10.4 3D Robot View (Right)

- Shows the virtual Pepper in real-time
- **Left-click + drag** to rotate the view
- **Scroll wheel** to zoom in/out
- **Right-click** > Wake Up / Rest to change the robot's state
- The robot moves when you play behaviors

### 10.5 Log Viewer (Bottom)

- Shows [INFO], [WARN], [ERR] messages from NAOqi
- Very useful for debugging — if something doesn't work, check here first
- You can filter by severity level

### 10.6 Script Editor (Bottom, toggle with Alt+5)

- Write Python 2.7 scripts that execute on the connected robot
- Uses `ALProxy()` to access NAOqi modules
- Click **Run** or press **F5** to execute

### 10.7 Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl+Shift+C` | Connect to robot dialog |
| `Ctrl+P` or green Play | Play current flow diagram |
| `Ctrl+.` or red Stop | Stop all behaviors |
| `Alt+5` | Toggle Script Editor |
| `Ctrl+S` | Save project |
| `Ctrl+Z` | Undo |
| `Ctrl+N` | New behavior |
| `Delete` | Delete selected box |

---

## 11. Creating Your First Choregraphe Behavior

Let's create a simple behavior that demonstrates what OmniLLM would do when a user asks "Where is Room 305?"

### 11.1 Create a new project:

1. **File** > **New Project**
2. Name it: `OmniLLM_Test`
3. Click **OK**

### 11.2 Build the behavior:

1. From **Box Libraries** > **Speech**, drag a **Say** box to the flow diagram
2. Double-click the Say box and type: `Room 305 is on the third floor of Building C. Take the elevator on your left and then turn left.`
3. From **Box Libraries** > **Movement** > **Animations** > **Gestures**, drag **Explain_8** (this is the "point left" gesture) next to the Say box
4. Connect the output of **onStart** to the input of both **Say** and **Explain_8** (they'll run in parallel — Pepper speaks AND points at the same time)
5. From **Box Libraries** > **LEDs**, drag a **Set LEDs** box
6. Connect it to run before the Say box. Set the color to blue (#0088FF) — this represents navigation mode

### 11.3 Play it:

1. Make sure the virtual robot is connected (green indicator)
2. Click the **green Play** button
3. Watch: Pepper's eyes turn blue > Pepper speaks the directions > Pepper points left

This is exactly what OmniLLM does automatically when it classifies a question as "navigation" (T2).

---

## 12. How Choregraphe Fits Into OmniLLM's Architecture

Here's the complete picture of how everything connects:

```
YOU (typing test questions)
  |
  |  curl POST /interact
  |  {"text": "Where is Room 305?", "condition": "B"}
  v
+--------------------------------------------------------+
|  TERMINAL 2: OmniLLM AI Server (Python 3.11+)         |
|  Port 5000                                             |
|                                                        |
|  1. Receives your text question                        |
|  2. Classifies it: "navigation" (T2)                   |
|  3. Queries RAG knowledge base (finds Room 305 info)   |
|  4. Sends to Ollama llama3:8b for answer generation    |
|  5. Plans gesture: "point_left" (for navigation)       |
|  6. Plans LED: "#0088FF" (blue = navigation mode)      |
|  7. Returns RobotAction JSON                           |
+----------------------------+---------------------------+
                             |  JSON response
                             v
+--------------------------------------------------------+
|  TERMINAL 3: NAOqi Client (Python 2.7)                 |
|                                                        |
|  1. Receives the RobotAction JSON                      |
|  2. Calls ALLeds.fadeRGB("FaceLeds", blue)             |
|  3. Calls ALBehaviorManager.runBehavior(point_left)    |
|  4. Calls ALAnimatedSpeech.say("Room 305 is on...")    |
+----------------------------+---------------------------+
                             |  NAOqi SDK calls
                             v
+--------------------------------------------------------+
|  CHOREGRAPHE: Virtual Robot (localhost:9559)            |
|                                                        |
|  3D View shows:                                        |
|  - Eyes turn blue                                      |
|  - Pepper points to the left                           |
|  - Pepper speaks the answer through your PC speakers   |
+--------------------------------------------------------+
                             ^
                             |
+--------------------------------------------------------+
|  TERMINAL 1: Ollama (Port 11434)                       |
|                                                        |
|  Running llama3:8b locally                             |
|  Generates the text response (free, no API key)        |
+--------------------------------------------------------+
```

### Which condition to use for local-only testing:

| Condition | What happens | Needs internet? |
|-----------|-------------|-----------------|
| **B** (recommended) | Uses Ollama llama3:8b for ALL tasks | **No** |
| A | Uses GPT-4o-mini (cloud) | Yes + API key |
| C | Smart-routes between models | Depends on routing |
| D | Queries 3 models (council) | Likely yes |
| E | Same as A but without RAG | Yes + API key |

**For local-only testing, always use `--condition B`.**

---

## 13. Useful GitHub Repos for Choregraphe + LLMs

These are open-source projects that combine Pepper/Choregraphe with LLM capabilities:

### Pepper + Choregraphe Repos

| Repository | Description | Best for |
|-----------|-------------|----------|
| [lillypiri/pepper](https://github.com/lillypiri/pepper) | Simple starter programs for Choregraphe 2.5.5.5 with Pepper robot | Beginners learning Choregraphe |
| [incognite-lab/Pepper-Controller](https://github.com/incognite-lab/Pepper-Controller) | Python controller for Pepper with GUI, full Python SDK alternative to Choregraphe | Advanced Python control |
| [Vicken-Ghoubiguian/pepperApplications](https://github.com/Vicken-Ghoubiguian/pepperApplications) | Collection of real Pepper applications used at events (trade fairs, open days) | Real-world behavior examples |
| [UoA-CARES/pepper-demo](https://github.com/UoA-CARES/pepper-demo) | Instructions for running Pepper demos + developer environment setup | Setting up dev environment |
| [zorniffler/Pepper-behaviors](https://github.com/zorniffler/Pepper-behaviors) | Custom Pepper behavior library | Custom animations |
| [PenguinZhou/Pepper_Nao_Basic_Tutorial](https://github.com/PenguinZhou/Pepper_Nao_Basic_Tutorial) | HKUST university tutorial for Pepper/NAO programming | Academic HRI projects |
| [PierreJac/Project-NAO-Control](https://github.com/PierreJac/Project-NAO-Control) | NAO robot control project with Python | NAO (Pepper's sibling) |

### Ollama + Local LLM Chatbot Repos

| Repository | Description | Best for |
|-----------|-------------|----------|
| [ollama/ollama](https://github.com/ollama/ollama) | Official Ollama — run local LLMs (Llama, Qwen, Mistral, DeepSeek, etc.) | Running local models |
| [jeromeboivin/ollama-chat](https://github.com/jeromeboivin/ollama-chat) | Python CLI for Ollama with conversation memory, plugins, and ChromaDB RAG | Testing RAG with local models |
| [sugarforever/chat-ollama](https://github.com/sugarforever/chat-ollama) | Open-source AI chatbot with knowledge bases, voice chat, and MCP | Full chatbot UI with Ollama |
| [lavanyajayanthi2004-ux/ollama-memory-chatbot](https://github.com/lavanyajayanthi2004-ux/ollama-memory-chatbot) | Local LLM chatbot with conversational memory | Simple memory-enabled chat |

### Official Documentation

| Resource | Link | Description |
|----------|------|-------------|
| Aldebaran Simulated Robots | [doc.aldebaran.com](http://doc.aldebaran.com/2-4/dev/tools/robot-simulation.html) | Official guide for virtual robot simulation |
| SoftBank Hello World (Python) | [developer.softbankrobotics.com](https://developer.softbankrobotics.com/pepper-naoqi-25/naoqi-developer-guide/getting-started/hello-world/hello-world-2-using-python) | Official Python + Choregraphe tutorial |
| Pepper Chat API | [softbankroboticstraining.github.io](https://softbankroboticstraining.github.io/pepper-chatbot-api/) | Building chatbots on Pepper |
| NEP+ Pepper Without Pepper | [coronadoenrique.gitbook.io](https://coronadoenrique.gitbook.io/nep+/other-tutorials/pepper-and-nao-robots/using-pepper-without-pepper-in-choregraphe) | Using Choregraphe without a physical robot |

---

## 14. Troubleshooting

### "Choregraphe won't start the virtual robot"

**Symptoms**: No robot in 3D view, connection stays red.

**Fixes**:
1. Close ALL Choregraphe instances (check Task Manager for leftover processes)
2. Check if port 9559 is already in use: `netstat -ano | findstr 9559`
3. Kill any leftover naoqi-bin processes in Task Manager
4. Reopen Choregraphe and try Connection > Connect to virtual robot
5. If still failing, manually start NAOqi:
   ```cmd
   "C:\Program Files (x86)\Aldebaran\Choregraphe Suite 2.5\bin\naoqi-bin.exe"
   ```
   Then in Choregraphe: Connection > Connect to > `localhost:9559`

### "import naoqi" fails in Python 2.7

```
ImportError: No module named naoqi
```

**Fix**: Your PYTHONPATH is not set correctly.
```cmd
:: Check what's set
echo %PYTHONPATH%

:: Set it
set PYTHONPATH=C:\pynaoqi\pynaoqi-python2.7-2.5.5.5-win32-vs2013\lib;%PYTHONPATH%

:: Verify
C:\Python27\python.exe -c "import naoqi; print('NAOqi OK')"
```

### "DLL load failed" error with pynaoqi

```
ImportError: DLL load failed: The specified module could not be found.
```

**Fix**: Add the pynaoqi lib to your system PATH (not just PYTHONPATH):
```cmd
set PATH=C:\pynaoqi\pynaoqi-python2.7-2.5.5.5-win32-vs2013\lib;%PATH%
```

### "Ollama connection refused"

**Fix**: Make sure `ollama serve` is running in Terminal 1. Check:
```cmd
curl http://localhost:11434/api/tags
```

If it fails, restart Ollama:
```cmd
:: Kill any existing Ollama process
taskkill /IM ollama.exe /F

:: Restart
ollama serve
```

### "AI server returns error about model not found"

**Fix**: The model ID in OmniLLM must match what's configured in `config/models.yaml`. For Ollama:
- Correct: `--model llama3-8b-local` (this is the OmniLLM ID)
- Wrong: `--model llama3:8b` (this is the Ollama name, not the OmniLLM ID)

Check available model IDs:
```cmd
curl http://localhost:5000/status
```

### "Virtual robot speaks but doesn't move"

**Fix**: The robot is probably in rest mode. In Choregraphe:
1. Right-click the robot in 3D view > **Wake Up**
2. Or run in Script Editor:
```python
motion = ALProxy("ALMotion", "localhost", 9559)
motion.wakeUp()
motion.setStiffnesses("Body", 1.0)
```

### "AI server is very slow with local models"

This is expected — local models on a laptop are slower than cloud APIs. Tips:
- Use `llama3:8b` or `qwen2.5:7b` (not 14B+ models) for faster responses
- Close other heavy applications to free up RAM
- If you have an NVIDIA GPU, Ollama will use it automatically (much faster)
- Check GPU usage: `nvidia-smi` (if you have NVIDIA GPU drivers installed)

---

## 15. Quick Reference — All Commands in Order

Here's everything you need to run, in the exact order, copy-paste ready:

```cmd
:: ===============================================================
:: TERMINAL 1: Start Ollama (local LLM server)
:: ===============================================================
ollama serve

:: (First time only — pull the model in a separate terminal:)
:: ollama pull llama3:8b


:: ===============================================================
:: TERMINAL 2: Start the OmniLLM AI Server
:: ===============================================================
cd C:\Users\akshi\OneDrive\Desktop\OmniLLM
venv\Scripts\activate.bat
python -m omnillm.server.app --host 0.0.0.0 --port 5000 --model llama3-8b-local


:: ===============================================================
:: CHOREGRAPHE: Open and connect to virtual robot
:: ===============================================================
:: 1. Open: "C:\Program Files (x86)\Aldebaran\Choregraphe Suite 2.5\bin\choregraphe.exe"
:: 2. Menu: Connection > Connect to virtual robot
:: 3. Wait for green connection indicator and Pepper in 3D view


:: ===============================================================
:: TERMINAL 3: Connect OmniLLM to the Virtual Robot
:: ===============================================================
set PYTHONPATH=C:\pynaoqi\pynaoqi-python2.7-2.5.5.5-win32-vs2013\lib;%PYTHONPATH%
set PATH=C:\pynaoqi\pynaoqi-python2.7-2.5.5.5-win32-vs2013\lib;%PATH%

C:\Python27\python.exe C:\Users\akshi\OneDrive\Desktop\OmniLLM\omnillm\server\naoqi_client.py ^
    --robot-ip localhost ^
    --robot-port 9559 ^
    --server-ip localhost ^
    --server-port 5000 ^
    --participant TEST001 ^
    --condition B


:: ===============================================================
:: TERMINAL 4: Test with text queries (virtual robot has no mic)
:: ===============================================================
:: Health check
curl http://localhost:5000/health

:: Test question
curl -X POST http://localhost:5000/interact ^
    -H "Content-Type: application/json" ^
    -d "{\"text\": \"Where is Room 305?\", \"participant_id\": \"TEST001\", \"session_id\": \"test-001\", \"condition\": \"B\"}"

:: Try different questions
curl -X POST http://localhost:5000/interact ^
    -H "Content-Type: application/json" ^
    -d "{\"text\": \"What time does the lab open?\", \"participant_id\": \"TEST001\", \"session_id\": \"test-002\", \"condition\": \"B\"}"

curl -X POST http://localhost:5000/interact ^
    -H "Content-Type: application/json" ^
    -d "{\"text\": \"How are you today, Pepper?\", \"participant_id\": \"TEST001\", \"session_id\": \"test-003\", \"condition\": \"B\"}"
```

---

## 16. Glossary

| Term | Meaning |
|------|---------|
| **NAOqi** | The robot's operating system. Runs services like speech, motion, LEDs. Port 9559. |
| **ALProxy** | Python function to access NAOqi services. `ALProxy("ServiceName", "ip", port)` |
| **ALAnimatedSpeech** | NAOqi service that makes Pepper speak with body animations |
| **ALMotion** | NAOqi service that controls Pepper's joints and posture |
| **ALLeds** | NAOqi service that controls Pepper's LED lights (eyes, ears, etc.) |
| **ALBehaviorManager** | NAOqi service that plays pre-built animations/behaviors |
| **Behavior** | A pre-built animation (wave, bow, point, dance). Stored as paths like `animations/Stand/Gestures/Hey_1` |
| **Choregraphe** | Desktop app for programming and simulating Pepper/NAO robots |
| **Virtual robot** | A simulated Pepper running inside Choregraphe on your PC |
| **Ollama** | Local LLM runner. Runs models like Llama 3, Qwen, Mistral on your PC for free |
| **LiteLLM** | Python library that OmniLLM uses to talk to any LLM provider (cloud or local) with the same code |
| **RAG** | Retrieval-Augmented Generation. The AI looks up facts in the knowledge base before answering |
| **RobotAction** | The JSON response from OmniLLM: `{"speech": "...", "gesture": "...", "emotion_led": "..."}` |
| **Condition B** | Experimental condition using a fixed local LLM (Ollama). Best for offline/free testing |
| **T1-T4** | Task types: T1=Info Retrieval, T2=Navigation, T3=Social, T4=Multilingual |
| **Flask** | Python web framework that OmniLLM uses for its HTTP server (port 5000) |
| **pynaoqi** | Python 2.7 SDK for controlling Pepper. Installed at `C:\pynaoqi\` |

---

*This guide is part of the [OmniLLM](https://github.com/Akshita-sr/OmniLLM) project. For the full Pepper + Choregraphe reference (including physical robot setup), see [PEPPER_CHOREGRAPHE_GUIDE.md](PEPPER_CHOREGRAPHE_GUIDE.md).*
