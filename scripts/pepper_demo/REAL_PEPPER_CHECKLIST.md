# Real-Pepper Deployment Checklist — DIBRIS, 2026-05-21+

Use this checklist when you arrive at the lab with the real Pepper. Follow
the steps in order; each is short and gives you a hard yes/no before moving
on. All commands assume you launch terminals from the repo root
`c:\Users\akshi\OneDrive\Desktop\OmniLLM\` unless stated otherwise.

## 0. Pre-arrival on your laptop

- [ ] Latest code is pulled / your local edits are committed.
- [ ] `venv\Scripts\python.exe -m pytest tests/ -q` — expect **289 passed**.
- [ ] `.env` has all the API keys (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`,
      `GOOGLE_API_KEY`, `DEEPSEEK_API_KEY`, `QWEN_API_KEY`).
- [ ] Ollama is running locally with `llama3.2:3b` available
      (`curl http://localhost:11434/api/tags` should list it).
      Condition B depends on this.
- [ ] Wi-Fi: laptop and Pepper are on the **same LAN**. Pepper does NOT need
      internet — only LAN connectivity to your laptop.

## 1. Power up Pepper

- [ ] Press the chest button **once** and wait until Pepper says its IP
      aloud. Note the IP — call it `PEPPER_IP` from here on.
- [ ] Optional: tablet shows the same IP under About → Network.

## 2. Find your laptop's IP

```powershell
ipconfig
```

- [ ] Note the IPv4 address of the LAN adapter — call it `SERVER_IP`.
- [ ] Confirm `ping <PEPPER_IP>` succeeds.
- [ ] Confirm `ping <SERVER_IP>` from another machine on the LAN if possible
      (rules out asymmetric firewall behaviour).

## 3. Allow Python through Windows Firewall (one-off)

```powershell
New-NetFirewallRule -DisplayName "OmniLLM AI server"   `
  -Direction Inbound -Program "C:\Users\akshi\OneDrive\Desktop\OmniLLM\venv\Scripts\python.exe" `
  -Action Allow -Profile Private
New-NetFirewallRule -DisplayName "OmniLLM NAOqi bridge" `
  -Direction Inbound -Program "C:\Python27\python.exe" `
  -Action Allow -Profile Private
```

(Only needed once per laptop; skip if already configured.)

## 4. Start the AI server (Terminal 1, Python 3 venv)

```powershell
cd c:\Users\akshi\OneDrive\Desktop\OmniLLM
venv\Scripts\Activate.ps1
python -m omnillm.server.app --host 0.0.0.0 --port 5000
```

- [ ] `INFO:__main__:Knowledge base loaded — 49 total chunks` appears (give
      or take a few — depends on KB edits).
- [ ] `Running on http://0.0.0.0:5000`
- [ ] From a second window:
      ```powershell
      curl http://127.0.0.1:5000/status
      ```
      Expect `rag_enabled=true`, `langgraph_available=true`,
      `rag_uses_chromadb=true`.

## 5. Start the NAOqi bridge (Terminal 2, Python 2.7)

```powershell
C:\Python27\python.exe omnillm\server\naoqi_bridge_server.py `
    --robot-ip <PEPPER_IP> --robot-port 9559 `
    --bind 0.0.0.0 --bridge-port 6000
```

- [ ] First line should be:
      `[OK] NaoqiFacade connected to <PEPPER_IP>:9559 (listen=0.0.0.0)`
      If you see `[ERR] ALBroker construction failed`, check the IP, the
      port, and that Pepper is awake (not in rest mode).
- [ ] `[OK] NAOqi bridge listening on http://0.0.0.0:6000/`
- [ ] `curl http://127.0.0.1:6000/ping` returns
      `"naoqi": true, "simulation": false`.

## 6. One-shot sanity test (Pepper greets you)

```powershell
curl -X POST http://127.0.0.1:6000/action `
  -H "Content-Type: application/json" `
  -d "{\"speech\":\"Hello, I am Pepper at DIBRIS, ready for the OmniLLM experiment.\",\"gesture\":\"wave\",\"emotion_led\":\"#00FF88\"}"
```

- [ ] Pepper speaks the sentence.
- [ ] Pepper performs the wave gesture (on real Pepper the stock animation
      library is preinstalled; on virtual robot the gesture line may report
      "behavior not installed" — that's fine for now).
- [ ] Eye LEDs turn green.

## 7. Pilot run (you as participant P000)

Single subject, full 4×5 matrix, drives the real robot:

```powershell
venv\Scripts\python.exe scripts\pepper_demo\run_subject_experiment.py `
    --participant P000 `
    --server http://127.0.0.1:5000 `
    --bridge http://127.0.0.1:6000
```

- [ ] All 20 interactions speak through the real Pepper. Watch for:
      Condition A → answer "08:30" for lab hours (RAG-grounded).
      Condition B → `model=llama3-8b-local` in the on-screen log.
      Condition C → mixes claude-haiku and gpt-4o-mini per task.
      Condition D → `model=council:…` and noticeably longer latency.
      Condition E → answers "9 AM" or hedged for lab hours (RAG-off
      contrast).
- [ ] Final lines: `Wrote results/subject_run_P000_<timestamp>.json` and
      `subject_run_P000_<timestamp>.csv`.

## 8. Real-participant sessions

For each participant, change `--participant` to their assigned ID
(`P001`, `P002`, …). The Latin-square-ish ordering inside
`run_subject_experiment.py` is reused so you don't need to randomise
manually for a pilot — but if you go to a full study, switch to the
`ExperimentManager.create_session()` API from `omnillm.hri.experiment`
which supports per-participant condition assignment.

After each participant:

- [ ] CSV is saved under `results/` with their participant ID + UTC
      timestamp. Move it to a session folder (one folder per participant).
- [ ] If using paper questionnaires, write the participant ID on every
      sheet.
- [ ] Optional: POST the digital questionnaire scores to `/evaluate` for
      logging into the same ExperimentLogger.

## 9. Shutdown

- [ ] In Terminal 2, `Ctrl+C` to stop the NAOqi bridge cleanly (it sends
      `motion.rest()` on exit so Pepper relaxes its joints).
- [ ] In Terminal 1, `Ctrl+C` to stop the AI server.
- [ ] If Pepper is going on the shelf for the night, long-press the chest
      button so it shuts down properly.

## 10. Trouble-shooting cheat sheet

| Symptom | Likely cause | Fix |
|---|---|---|
| `ALBroker construction failed` | wrong robot IP / port / Pepper asleep | re-check `PEPPER_IP`; chest-button wake-up |
| All B-condition responses look cloud-shaped | Ollama not running | `ollama serve` / `ollama list` |
| `Path: fallback` in metadata | Anthropic or Gemini briefly overloaded | already handled by the retry; logged for transparency |
| Empty speech | LangGraph state-key mismatch | check server log — graph error message |
| `429 RESOURCE_EXHAUSTED` from Google | quota gone again | non-English already routes to claude-haiku, no action needed |
| Pepper doesn't move but speaks | virtual robot ran instead of real | check `/ping` returns `simulation: false` |
| Gesture "behavior not installed" | virtual robot lacks stock library | only happens on Choregraphe — real Pepper has them |
