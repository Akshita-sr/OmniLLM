# Pepper demo scripts

Five entry points to test OmniLLM end-to-end against either Choregraphe's
virtual Pepper or a real Pepper robot.

## Files

| File | Python | What it does | Needs AI server? |
| --- | --- | --- | --- |
| `demo_pepper_omnillm.py` | 2.7 | Single-shot demo: text question → AI server → Pepper speaks. `--check-only` runs just the NAOqi bridge sanity test (no AI). | Only without `--check-only` |
| `test_all_conditions.py` | 3.x | Batch tests all 5 experimental conditions + multilingual against the AI server. Writes transcript to `test_results.txt`. | Yes |
| `omnillm/server/naoqi_client.py` | 2.7 | Interactive loop. `--trigger text` / `touch` / `vad` picks the input mode. Touch uses the front-head sensor + ALAudioRecorder; vad uses energy-gated capture; text reads stdin. | Yes |
| `omnillm/server/naoqi_bridge_server.py` | 2.7 | HTTP bridge near Pepper. Lets the Python 3 `PepperBridge` drive Pepper directly via `aiohttp`. Exposes `/action`, `/sensors`, `/audio/record`, `/tracker/{start,stop}`, `/ping`, `/disconnect`. | No (but you usually run it alongside) |
| `omnillm.robotics.PepperBridge` | 3.x | Async Python 3 client of the bridge server. Used inside LangGraph nodes. Auto-detects the bridge; falls back to stub mode (printed actions) if nothing is reachable. | n/a |

## Quick reference

### 1. Start the AI server (one terminal, Python 3 venv)

```powershell
cd "C:\Users\akshi\OneDrive\Desktop\OmniLLM"
.\venv\Scripts\Activate.ps1
python -m omnillm.server.app
```

Wait for `Indexed 40 chunks` and `Running on http://127.0.0.1:5000`.

### 2. Bridge sanity check — robot only, no AI (Python 2.7)

```cmd
C:\Python27\python.exe scripts\pepper_demo\demo_pepper_omnillm.py --check-only --robot-port 49959
```

Use this first when something seems broken. If it fails, the robot/NAOqi connection is the issue — not OmniLLM.

(Replace `49959` with the port shown in Choregraphe's Connect-to dialog; real Pepper uses `9559`.)

### 3a. Single-shot demo (AI → robot, Python 2.7)

```cmd
:: Virtual Pepper, condition A (RAG), library question
C:\Python27\python.exe scripts\pepper_demo\demo_pepper_omnillm.py --condition A --rag --question "What time does the lab open?" --robot-port 49959

:: Real Pepper at the lab (IP from chest button, port defaults to 9559)
C:\Python27\python.exe scripts\pepper_demo\demo_pepper_omnillm.py --robot-ip 192.168.1.42 --condition A --rag --question "What time does the lab open?"
```

### 3b. Interactive client loop (Python 2.7) — recommended for live demos

```cmd
:: Virtual Pepper, text input via stdin (works without a microphone)
C:\Python27\python.exe omnillm\server\naoqi_client.py --robot-ip 127.0.0.1 --robot-port 49959 --trigger text --condition A

:: Real Pepper at the lab, head-touch starts a 5s recording
C:\Python27\python.exe omnillm\server\naoqi_client.py --robot-ip 192.168.1.42 --trigger touch --record-seconds 5 --condition A --track-face

:: Real Pepper, always-on voice via energy-threshold VAD
C:\Python27\python.exe omnillm\server\naoqi_client.py --robot-ip 192.168.1.42 --trigger vad --condition C
```

The `--trigger` flag picks how a conversational turn starts:

* `text` — type a question, hit Enter. Empty line quits. Works everywhere (incl. virtual Pepper which has no mic).
* `touch` — touch Pepper's front head sensor to start a fixed-duration recording (default 5 s). Requires real Pepper.
* `vad` — continuous capture with energy-gated voice-activity detection. Requires real Pepper.

Add `--track-face` to enable ALTracker face-follow during the session (head moves to look at the speaker).

### 3c. Bridge server pattern (Python 2.7 near robot + Python 3 PepperBridge)

This is the topology where Python 3 LangGraph nodes drive Pepper directly via HTTP, instead of Pepper polling the AI server. Useful when the LLM should choose actions reactively (e.g. trigger gestures from inside the agent graph).

```cmd
:: Terminal 1: start the bridge server (Python 2.7, near or on Pepper)
C:\Python27\python.exe omnillm\server\naoqi_bridge_server.py --robot-ip 127.0.0.1 --robot-port 49959 --bridge-port 6000

:: GET /ping should return {"ok": true, "naoqi": true, "simulation": false, ...}
curl http://127.0.0.1:6000/ping
```

Then from any Python 3 code:

```python
import asyncio
from omnillm.robotics import make_pepper_bridge
from omnillm.robotics.bridge import RobotAction

async def main():
    bridge = await make_pepper_bridge(robot_ip="127.0.0.1", bridge_port=6000)
    print("mode:", bridge.mode)  # "server" if bridge reachable, else "stub"
    await bridge.execute_action(RobotAction(
        speech="Hello from Python 3!",
        gesture="wave",
        emotion_led="#00FF00",
    ))
    await bridge.disconnect()

asyncio.run(main())
```

`make_pepper_bridge(robot_ip="127.0.0.1", robot_port=None)` auto-discovers the Choregraphe virtual-robot port via TCP probing. When nothing is listening, the bridge silently drops to **stub mode** so tests never crash.

### 4. Batch validation — server only, no robot (Python 3)

```powershell
python scripts\pepper_demo\test_all_conditions.py
```

This runs all 9 test scenarios and writes results to `scripts/pepper_demo/test_results.txt`.

## Setup gotchas

1. **Virtual Pepper port changes every Choregraphe launch.** Open Choregraphe → Connection → Connect to... → select AKSHITA → note the port → pass it via `--robot-port`. `make_pepper_bridge(robot_port=None)` will try to auto-discover it on `127.0.0.1` (probes a few recently-seen ports first, then scans).
2. **Real Pepper port is always `9559`** and its IP is announced when you press the chest button.
3. **Always use `C:\Python27\python.exe` (full path) for the Python 2 entry points** — `python` on your PATH is Python 3, which can't import NAOqi.
4. **Windows 11 + NAOqi 2.5 loopback bug:** every Python 2 entry point binds the ALBroker to `127.0.0.1` explicitly for virtual Pepper. Real Pepper has no such bug.
5. **Choregraphe virtual robot has no microphone / camera / tablet.** ALAudioRecorder, ALFaceDetection, ALTabletService all return "simulated" responses. Use `--trigger text` for virtual.
6. **Bridge server falls back to simulation if it can't reach the robot.** `GET /ping` returns `simulation=true` in that case — actions still come back `200 OK` but only print to the bridge's stdout.

## Sequence for tomorrow's real-robot demo

1. Power on Pepper, press chest button, write down the IP.
2. Join the same Wi-Fi network. Test with `ping <pepper-ip>`.
3. Start the AI server (see above).
4. **First:** sanity-check the bridge:

   ```cmd
   C:\Python27\python.exe scripts\pepper_demo\demo_pepper_omnillm.py --check-only --robot-ip <pepper-ip>
   ```

   If Pepper says "Hello from my own Python script" — green light.
5. Then choose your interaction style:

   * Quick text demo:

     ```cmd
     C:\Python27\python.exe omnillm\server\naoqi_client.py --robot-ip <pepper-ip> --trigger text --condition A
     ```

   * Touch-to-talk:

     ```cmd
     C:\Python27\python.exe omnillm\server\naoqi_client.py --robot-ip <pepper-ip> --trigger touch --track-face --condition A
     ```

## Condition cheat sheet

| Condition | LLM | RAG | Cost per query |
| --- | --- | --- | --- |
| **A** | GPT-4o-mini (cloud) | ON | ~$0.0001 |
| **B** | Llama 3.2 3B (local Ollama) | ON | $0 |
| **C** | Smart-routed (best model per task) | ON | varies |
| **D** | Consensus (3-model council) | ON | ~$0.0005 |
| **E** | GPT-4o-mini, RAG off (control) | OFF | ~$0.00005 |

## What changed in 2026-05 upgrade

* `omnillm/robotics/pepper.py` (Python 3) — rewritten from placeholders into a real async HTTP client of the new bridge server, with auto-discovery and stub fallback.
* `omnillm/server/naoqi_bridge_server.py` (Python 2.7) — new HTTP bridge for the "Python 3 drives Pepper" topology. Stdlib only — no Flask pip install needed.
* `omnillm/server/naoqi_client.py` (Python 2.7) — added `--trigger touch|vad|text`, real ALAudioRecorder capture, ALTabletService support, ALTracker face-follow.
* `omnillm/hri/language_detector.py` — added `language_code`, `language_name`, `recommended_model` compatibility properties (fixes empty-speech bug in multilingual path).
* `config/models.yaml` — removed invalid `openai-gpt54`/`gpt-5.4`; pointed `llama3-8b-local` and `qwen3-8b-local` at the models actually installed in Ollama.
