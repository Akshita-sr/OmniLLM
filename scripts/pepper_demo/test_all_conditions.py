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
TESTS: list[tuple[str, str, bool, str]] = [
    ("A_lab_hours", "A", True, "What time does the lab open?"),
    ("A_wifi", "A", True, "What is the Wi-Fi password?"),
    ("A_room_305", "A", True, "Where is room 305?"),
    ("B_local_llama", "B", True, "Tell me a fun fact about robots."),
    ("C_smart", "C", True, "Where is the cafeteria?"),
    ("D_consensus", "D", True, "Tell me about the lab's research."),
    ("E_control", "E", False, "What is your name?"),
    ("multilingual_it", "E", False, "Ciao Pepper, come stai oggi?"),
    ("multilingual_es", "E", False, "Hola Pepper, donde estoy?"),
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
