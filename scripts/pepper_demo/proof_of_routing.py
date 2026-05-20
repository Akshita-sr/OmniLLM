"""Proof-of-routing demonstration.

For each condition (A B C D E) and each task type (T1 T2 T3 T4), POST the
exact same prompt to /interact and print the model_id the server actually
used. This is the cleanest evidence that the routing is working — if every
row showed openai-gpt4o-mini, the "smart routing" would be a lie.

Run with the AI server already up:
    python -m omnillm.server.app --host 127.0.0.1 --port 5000

Then:
    python scripts/pepper_demo/proof_of_routing.py
"""

from __future__ import annotations

import json
import urllib.request
from typing import NamedTuple


SERVER = "http://127.0.0.1:5000/interact"

PROMPTS: dict[str, str] = {
    "T1": "What time does the lab open?",
    "T2": "Where is the Pepper room at DIBRIS?",
    "T3": "Hello Pepper, how are you today?",
    "T4": "Ciao Pepper, dove si trova la stazione di Brignole?",
}

CONDITIONS = ["A", "B", "C", "D", "E"]


class Result(NamedTuple):
    condition: str
    task: str
    model: str
    path: str
    rag: bool
    answer_head: str


def ask(condition: str, prompt: str) -> Result:
    payload = json.dumps({
        "text": prompt,
        "participant_id": "proof",
        "session_id": "proof",
        "condition": condition,
        "rag_enabled": condition != "E",
    }).encode("utf-8")
    req = urllib.request.Request(
        SERVER, data=payload, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=90) as resp:
        data = json.loads(resp.read())
    meta = data.get("metadata", {}) or {}
    speech = (data.get("speech") or "").replace("\n", " ")
    return Result(
        condition=condition,
        task="",
        model=meta.get("model_id", "?"),
        path=meta.get("path", "graph"),
        rag=bool(meta.get("rag_enabled", False)),
        answer_head=speech[:80],
    )


def main() -> None:
    print(f"{'Cond':<5}{'Task':<6}{'Path':<10}{'RAG':<5}{'Model':<55}First 80 chars of reply")
    print("-" * 140)
    for task, prompt in PROMPTS.items():
        for cond in CONDITIONS:
            try:
                r = ask(cond, prompt)
                head = r.answer_head.encode("ascii", "replace").decode("ascii")
                print(f"{cond:<5}{task:<6}{r.path:<10}{('y' if r.rag else 'n'):<5}"
                      f"{r.model:<55}{head}")
            except Exception as exc:
                print(f"{cond:<5}{task:<6}ERROR  {exc}")
        print()


if __name__ == "__main__":
    main()
