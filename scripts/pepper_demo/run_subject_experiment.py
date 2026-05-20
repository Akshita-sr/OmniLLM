"""20-interaction subject experiment for the OmniLLM Embodied LLM Arena.

Coverage: 4 HRI task types (T1 info_retrieval, T2 navigation, T3 social,
T4 multilingual) crossed with 5 experimental conditions (A, B, C, D, E),
plus one mid-condition counterbalancing tweak to detect order effects.

For each interaction we:
  1. POST /interact to the AI server with (text, condition, rag_enabled).
  2. POST /action to the NAOqi bridge so the virtual Pepper actually says it
     (gesture failures are non-fatal — virtual robot lacks the animation
     library, but speech + LED still work).
  3. Log a row with: question, response, model, latency, RAG path, gesture.

Outputs:
  - results/subject_run_<timestamp>.json  (machine-readable transcript)
  - results/subject_run_<timestamp>.csv   (spreadsheet-friendly summary)
  - stdout                                 (live progress)

Run from the OmniLLM venv (Python 3.13):
    python scripts/pepper_demo/run_subject_experiment.py \
        --participant P000 \
        --bridge http://127.0.0.1:6000 \
        --server http://127.0.0.1:5000

Add --no-robot to skip the bridge entirely (pure server validation).
"""

from __future__ import annotations

import argparse
import csv
import json
import time
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path


# ── Experiment design ─────────────────────────────────────────────────────────

# Each tuple is (task_label, prompt_text, expect_rag_to_help).
# We reuse the same 4 task prompts across all 5 conditions so latency,
# faithfulness, and judge scores are directly comparable.
TASKS: dict[str, tuple[str, str, bool]] = {
    "T1": ("T1_info_retrieval",
           "What time does the lab open?", True),
    "T2": ("T2_navigation",
           "Where is the Pepper room at DIBRIS?", True),
    "T3": ("T3_social",
           "Hello Pepper, how are you today?", False),
    "T4": ("T4_multilingual",
           "Ciao Pepper, dove si trova la stazione di Brignole?", True),
}

# Latin-square-ish counterbalanced order: each condition starts at a
# different task so order effects are at least partly cancelled.
ORDER: list[tuple[str, str]] = [
    ("A", "T1"), ("A", "T2"), ("A", "T3"), ("A", "T4"),
    ("B", "T2"), ("B", "T3"), ("B", "T4"), ("B", "T1"),
    ("C", "T3"), ("C", "T4"), ("C", "T1"), ("C", "T2"),
    ("D", "T4"), ("D", "T1"), ("D", "T2"), ("D", "T3"),
    ("E", "T1"), ("E", "T2"), ("E", "T3"), ("E", "T4"),
]


def post_json(url: str, payload: dict, timeout: float = 90.0) -> dict:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read())


def ask_server(server_url: str, text: str, participant: str, session: str,
               condition: str, rag_enabled: bool) -> dict:
    return post_json(server_url + "/interact", {
        "text": text,
        "participant_id": participant,
        "session_id": session,
        "condition": condition,
        "rag_enabled": rag_enabled,
    }, timeout=90)


def push_to_robot(bridge_url: str, action: dict) -> dict | None:
    try:
        return post_json(bridge_url + "/action", {
            "speech": action.get("speech", ""),
            "gesture": action.get("gesture"),
            "emotion_led": action.get("emotion_led"),
            "movement": action.get("movement"),
            "metadata": action.get("metadata", {}),
        }, timeout=30)
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc)}


def main() -> None:
    parser = argparse.ArgumentParser(
        description="OmniLLM Embodied LLM Arena — single-subject pilot run.")
    parser.add_argument("--participant", default="P000",
                        help="Participant ID (default: P000 = Akshita pilot).")
    parser.add_argument("--server", default="http://127.0.0.1:5000",
                        help="OmniLLM AI server base URL.")
    parser.add_argument("--bridge", default="http://127.0.0.1:6000",
                        help="NAOqi bridge base URL.")
    parser.add_argument("--no-robot", action="store_true",
                        help="Skip the NAOqi bridge (pure server validation).")
    parser.add_argument("--out-dir", default="results",
                        help="Output directory for transcripts.")
    args = parser.parse_args()

    session_id = str(uuid.uuid4())
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / f"subject_run_{args.participant}_{ts}.json"
    csv_path = out_dir / f"subject_run_{args.participant}_{ts}.csv"

    print(f"Subject experiment — participant={args.participant} "
          f"session={session_id[:8]}")
    print(f"Server: {args.server}")
    print(f"Robot bridge: {'disabled' if args.no_robot else args.bridge}")
    print()

    records: list[dict] = []
    csv_rows: list[dict] = []

    for idx, (condition, task_key) in enumerate(ORDER, start=1):
        task_label, prompt, _expect_rag = TASKS[task_key]
        rag_enabled = condition != "E"  # E is the no-RAG control

        print(f"[{idx:02d}/{len(ORDER)}] {condition} / {task_label}: {prompt[:60]}")
        t0 = time.time()
        try:
            response = ask_server(args.server, prompt, args.participant,
                                  session_id, condition, rag_enabled)
        except urllib.error.URLError as exc:
            print(f"    ERROR: server unreachable ({exc})")
            records.append({
                "step": idx, "condition": condition, "task": task_label,
                "prompt": prompt, "rag_enabled": rag_enabled,
                "error": str(exc),
            })
            continue

        latency_s = time.time() - t0
        speech = response.get("speech", "") or ""
        gesture = response.get("gesture")
        meta = response.get("metadata", {}) or {}
        model_id = meta.get("model_id", "")
        path = meta.get("path", "graph")
        rag_actual = meta.get("rag_enabled", rag_enabled)

        snippet = (speech[:90] + "...") if len(speech) > 90 else speech
        snippet_ascii = snippet.encode("ascii", "replace").decode("ascii")
        print(f"    -> {snippet_ascii}")
        print(f"    model={model_id}  path={path}  latency={latency_s*1000:.0f} ms")

        # Drive the robot for a short delay so we don't queue too many
        # speeches at once.
        robot_result: dict | None = None
        if not args.no_robot and speech:
            robot_result = push_to_robot(args.bridge, response)
            if robot_result and robot_result.get("ok") is False:
                # Speech may still have executed even if a gesture failed.
                executed = robot_result.get("executed", {})
                if executed.get("speech"):
                    print("    robot: spoke ok (gesture/tablet partial)")
                else:
                    print(f"    robot: {robot_result.get('errors', robot_result)}")
            elif robot_result:
                print("    robot: ok")

        record = {
            "step": idx,
            "condition": condition,
            "task": task_label,
            "prompt": prompt,
            "rag_enabled_requested": rag_enabled,
            "rag_enabled_actual": rag_actual,
            "response": speech,
            "gesture": gesture,
            "model_id": model_id,
            "path": path,
            "latency_s": round(latency_s, 3),
            "metadata": meta,
            "robot_result": robot_result,
        }
        records.append(record)
        csv_rows.append({
            "step": idx,
            "condition": condition,
            "task": task_label,
            "model": model_id,
            "path": path,
            "rag": "y" if rag_actual else "n",
            "latency_s": round(latency_s, 2),
            "prompt": prompt,
            "response": speech,
        })

        # Small gap between turns so the robot speech finishes and you can
        # observe the result in Choregraphe Dialog panel.
        if not args.no_robot:
            time.sleep(2.0)

    with json_path.open("w", encoding="utf-8") as fh:
        json.dump({
            "participant_id": args.participant,
            "session_id": session_id,
            "started_at": ts,
            "server": args.server,
            "bridge": args.bridge if not args.no_robot else None,
            "records": records,
        }, fh, indent=2, default=str)

    if csv_rows:
        with csv_path.open("w", encoding="utf-8", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=list(csv_rows[0].keys()))
            writer.writeheader()
            for row in csv_rows:
                writer.writerow(row)

    print()
    print(f"Wrote {json_path}")
    print(f"Wrote {csv_path}")

    # Server-side aggregate.
    try:
        with urllib.request.urlopen(args.server + "/export", timeout=10) as resp:
            data = json.loads(resp.read())
        print(f"Server-logged interactions for this run: {data.get('count')}")
    except Exception as exc:
        print(f"(could not fetch /export: {exc})")


if __name__ == "__main__":
    main()
