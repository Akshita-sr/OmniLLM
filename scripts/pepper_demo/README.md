# Pepper demo scripts

Two small scripts to test OmniLLM end-to-end against either Choregraphe's
virtual Pepper or a real Pepper robot.

## Files

| File | Python | What it does | Needs AI server? |
|---|---|---|---|
| `demo_pepper_omnillm.py` | 2.7 | Default mode: full AI demo (AI server -> Pepper speaks). With `--check-only`: bridge sanity test only (no AI). | Only without `--check-only` |
| `test_all_conditions.py` | 3.x | Batch tests all 5 experimental conditions + multilingual against the AI server. Writes transcript to `test_results.txt`. | Yes |

## Quick reference

### Start the AI server (one terminal, Python 3 venv)

```powershell
cd "C:\Users\akshi\OneDrive\Desktop\OmniLLM"
.\venv\Scripts\Activate.ps1
python -m omnillm.server.app
```

Wait for `Indexed 40 chunks` and `Running on http://127.0.0.1:5000`.

### Bridge sanity check — robot only, no AI (Python 2.7)

```cmd
C:\Python27\python.exe scripts\pepper_demo\demo_pepper_omnillm.py --check-only --robot-port 49959
```

Use this first when something seems broken. If it fails, the robot/NAOqi connection is the issue — not OmniLLM.

(Replace `49959` with the port shown in Choregraphe's Connect-to dialog; real Pepper uses `9559`.)

### Full demo — AI -> robot (Python 2.7)

```cmd
:: Virtual Pepper, condition A (RAG), library question
C:\Python27\python.exe scripts\pepper_demo\demo_pepper_omnillm.py --condition A --rag --question "What time does the lab open?" --robot-port 49959

:: Real Pepper at the lab (IP from chest button, port defaults to 9559)
C:\Python27\python.exe scripts\pepper_demo\demo_pepper_omnillm.py --robot-ip 192.168.1.42 --condition A --rag --question "What time does the lab open?"
```

### Batch validation — server only, no robot (Python 3)

```powershell
python scripts\pepper_demo\test_all_conditions.py
```

This runs all 9 test scenarios and writes results to `scripts/pepper_demo/test_results.txt`.

## Setup gotchas

1. **Virtual Pepper port changes every Choregraphe launch.** Open Choregraphe → Connection → Connect to... → select AKSHITA → note the port → pass it via `--robot-port`.
2. **Real Pepper port is always `9559`** and its IP is announced when you press the chest button.
3. **Always use `C:\Python27\python.exe` (full path) for the demo** — `python` on your PATH is Python 3, which can't import NAOqi.
4. **Windows 11 + NAOqi 2.5 loopback bug:** the script handles this by binding the broker to `127.0.0.1` explicitly for virtual Pepper. Real Pepper has no such bug.

## Sequence for tomorrow's real-robot demo

1. Power on Pepper, press chest button, write down the IP.
2. Join the same Wi-Fi network. Test with `ping <pepper-ip>`.
3. Start the AI server (see above).
4. **First:** sanity-check the bridge:
   ```cmd
   C:\Python27\python.exe scripts\pepper_demo\demo_pepper_omnillm.py --check-only --robot-ip <pepper-ip>
   ```
   If Pepper says "Hello from my own Python script" — green light.
5. Then run the full demo with `--robot-ip <pepper-ip>`.

## Condition cheat sheet

| Condition | LLM | RAG | Cost per query |
|---|---|---|---|
| **A** | GPT-4o-mini (cloud) | ON | ~$0.0001 |
| **B** | Llama 3 8B (local Ollama) | ON | $0 |
| **C** | Smart-routed (best model per task) | ON | varies |
| **D** | Consensus (3-model council) | ON | ~$0.0005 |
| **E** | GPT-4o-mini, RAG off (control) | OFF | ~$0.00005 |
