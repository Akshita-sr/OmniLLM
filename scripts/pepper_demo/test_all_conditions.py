"""Batch test: run every OmniLLM experimental condition through the AI server.

Saves the transcript to test_results.txt next to this script for review.
Does NOT touch the robot -- pure server-side validation.

Prerequisites:
    - AI server running: `python -m omnillm.server.app` (from venv'd PowerShell)

Run from the OmniLLM venv (Python 3):
    python scripts/pepper_demo/test_all_conditions.py
"""

from __future__ import annotations

import json
import time
import urllib.request
from pathlib import Path

SERVER = "http://localhost:5000/interact"
TIMEOUT = 90  # seconds; consensus can be slow

# (label, condition, rag_enabled, question)
# Coverage matrix: every (condition, task_type) combination is exercised at
# least once.  Task types are T1 info_retrieval, T2 navigation, T3 social,
# T4 multilingual.
TESTS: list[tuple[str, str, bool, str]] = [
    # Condition A — fixed GPT-4o-mini + RAG
    ("A_T1_lab_hours", "A", True, "What time does the lab open?"),
    ("A_T2_pepper_room", "A", True, "Where is the Pepper room at DIBRIS?"),
    ("A_T3_hello", "A", True, "Hello Pepper, how are you?"),
    ("A_T4_italian", "A", True, "Ciao Pepper, come stai oggi?"),
    # Condition B — local Llama (skip if Ollama not running; will return error)
    ("B_T1_who_runs_lab", "B", True, "Who runs this lab?"),
    ("B_T3_fun_fact", "B", True, "Tell me a fun fact about robots."),
    # Condition C — smart router
    ("C_T1_wifi", "C", True, "How do I connect to Wi-Fi here?"),
    ("C_T2_train_station", "C", True, "How do I get to Brignole train station?"),
    ("C_T3_joke", "C", True, "Tell me a joke."),
    ("C_T4_spanish", "C", True, "Hola Pepper, donde estoy?"),
    # Condition D — consensus council
    ("D_T1_research", "D", True, "Tell me about Prof. Sgorbissa's research."),
    ("D_T3_consciousness", "D", True, "Do you think robots can be conscious?"),
    # Condition E — RAG-off control
    ("E_T1_hours_no_rag", "E", False, "What time does the lab open?"),
    ("E_T3_name", "E", False, "What is your name?"),
    ("E_T4_french", "E", False, "Bonjour Pepper, comment vas-tu?"),
]


def ask(condition: str, rag: bool, text: str) -> dict:
    payload = json.dumps({
        "text": text,
        "participant_id": "P_test",
        "session_id": "batch-validation",
        "condition": condition,
        "rag_enabled": rag,
    }).encode("utf-8")
    req = urllib.request.Request(
        SERVER, data=payload, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return json.loads(resp.read())


def main() -> None:
    out_path = Path(__file__).parent / "test_results.txt"
    print(f"Writing results to {out_path}")

    with out_path.open("w", encoding="utf-8") as fh:
        fh.write("OmniLLM batch validation\n")
        fh.write(f"Started: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        fh.write(f"Server: {SERVER}\n")
        fh.write("=" * 70 + "\n\n")

        passes = 0
        fails = 0
        for label, cond, rag, q in TESTS:
            print(f"[{label}] {cond}/{q[:50]}...", end=" ", flush=True)
            t0 = time.time()
            try:
                resp = ask(cond, rag, q)
                latency = (time.time() - t0) * 1000
                speech = resp.get("speech", "")
                gesture = resp.get("gesture", "")
                meta = resp.get("metadata", {})

                if speech:
                    passes += 1
                    verdict = "PASS"
                else:
                    fails += 1
                    verdict = "FAIL (empty speech)"

                print(f"{verdict} ({latency:.0f} ms)")

                fh.write(f"### {label} | Condition {cond} | RAG={rag} | {verdict}\n")
                fh.write(f"Q: {q}\n")
                fh.write(f"A: {speech}\n")
                fh.write(f"Gesture: {gesture}\n")
                fh.write(f"Model: {meta.get('model_id', '(unknown)')}\n")
                fh.write(f"Path: {meta.get('path', 'graph')}\n")
                fh.write(f"Latency: {latency:.0f} ms\n\n")
            except Exception as exc:
                fails += 1
                print(f"ERROR: {exc}")
                fh.write(f"### {label} | ERROR\n{exc}\n\n")

        fh.write("=" * 70 + "\n")
        fh.write(f"Summary: {passes} passed, {fails} failed, {len(TESTS)} total\n")

    print()
    print(f"Done. {passes}/{len(TESTS)} passed. Results in {out_path}.")


if __name__ == "__main__":
    main()
