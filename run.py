"""OmniLLM unified launcher — drives the AI server from text or laptop mic
and forwards the returned RobotAction to Pepper (real or Choregraphe virtual).

Usage::

    python run.py text                          # type prompts, send to Pepper
    python run.py mic                           # press Enter to record, again to stop
    python run.py mic --stt local               # use local faster-whisper
    python run.py text --council                # use multi-LLM council
    python run.py mic --no-pepper               # skip Pepper, just print the response

By default this script:
  - Talks to the AI server at http://127.0.0.1:5000
  - Connects PepperBridge to 127.0.0.1:62763 (Choregraphe locked port).
    If Choregraphe isn't listening, PepperBridge falls back to STUB mode
    (responses are still printed) — so the script never crashes on missing robot.

For real Pepper at the lab::

    python run.py text --robot-ip 192.168.1.42 --robot-port 9559

──────────────────────────────────────────────────────────────────────
BEGINNER ORIENTATION
──────────────────────────────────────────────────────────────────────
This is Terminal 3 of the 3-terminal run book (see OMNILLM_MASTER_BOOK.md
§2.2 and §4.1.7). It connects to:
  - The AI server (T1) over HTTP at http://127.0.0.1:5000
  - The Pepper bridge (T2) over HTTP at http://127.0.0.1:6000

What it does:
  1. Reads laptop mic OR keyboard input
  2. Sends the input to /interact and gets a RobotAction back
  3. Forwards the RobotAction to PepperBridge (which talks to Pepper)
──────────────────────────────────────────────────────────────────────
"""

from __future__ import annotations

# Standard library only at the top — keeps startup fast and import errors
# visible immediately. ``argparse`` parses CLI flags, ``asyncio`` runs our
# async coroutines, ``sys`` provides exit codes.
import argparse
import asyncio
import sys
from typing import Any


# Default AI server URL. Override with --server if you run the server on
# a different machine or port.
DEFAULT_SERVER = "http://127.0.0.1:5000"


# ──────────────────────────────────────────────────────────────────────
# Helper: POST a JSON body to /interact and read the JSON back.
# ──────────────────────────────────────────────────────────────────────
async def _post_interact(
    session, server: str, payload: dict[str, Any]
) -> dict[str, Any]:
    # ``session`` is an aiohttp.ClientSession — a reusable HTTP connection
    # pool. Reusing it across requests is faster than opening a new TCP
    # connection each time.
    async with session.post(f"{server}/interact", json=payload) as resp:
        # HTTP 200 = success. Anything else is an error; slice to 200 chars
        # so big error pages don't flood the console.
        if resp.status != 200:
            body = await resp.text()
            return {"error": f"server {resp.status}: {body[:200]}"}
        return await resp.json()


# ──────────────────────────────────────────────────────────────────────
# Helper: print the response and send it to Pepper.
# ──────────────────────────────────────────────────────────────────────
async def _execute(bridge, action: dict[str, Any]) -> None:
    # ``action`` is the RobotAction dict returned by /interact. It has
    # "speech", "gesture", "emotion_led", and "metadata".
    from omnillm.robotics.bridge import RobotAction

    speech = action.get("speech", "")
    if not speech:
        print("  [no speech]")
        return
    print(f"  Pepper: {speech}")
    # Metadata: task type, language, model used, latency. Visible at a glance.
    meta = action.get("metadata") or {}
    print(
        f"  [task={meta.get('task_type', '?')}, lang={meta.get('language', '?')}, "
        f"model={meta.get('model_id', '?')}, {meta.get('latency_ms', 0):.0f}ms]"
    )
    # If we have a bridge, forward the action so the robot actually speaks/
    # gestures/changes LED colour. None means --no-pepper was passed.
    if bridge is not None:
        await bridge.execute_action(RobotAction(
            speech=speech,
            gesture=action.get("gesture"),
            emotion_led=action.get("emotion_led"),
            metadata=meta,
        ))


# ──────────────────────────────────────────────────────────────────────
# TEXT MODE — read keyboard input, send to server, execute on Pepper.
# ──────────────────────────────────────────────────────────────────────
async def _text_loop(server: str, bridge, council: bool) -> None:
    # Lazy import so the script can show --help without aiohttp installed.
    import aiohttp
    print("Text mode. Type a prompt and press Enter. Ctrl-C to quit.\n")
    async with aiohttp.ClientSession() as session:
        while True:
            # beginner: ``input()`` blocks the event loop, but that's fine
            # here — in interactive mode we have nothing else to do while
            # waiting for the user to type.
            try:
                utterance = input("> ").strip()
            except (EOFError, KeyboardInterrupt):
                # Clean Ctrl-D / Ctrl-C handling instead of a traceback.
                print()
                return
            if not utterance:
                continue
            if utterance.lower() in {"quit", "exit", "q"}:
                return
            payload = {"text": utterance, "council": council}
            action = await _post_interact(session, server, payload)
            if "error" in action:
                # Server errors come back as {"error": "..."}. Print and
                # continue — the user might just need to retry.
                print(f"  [error] {action['error']}")
                continue
            await _execute(bridge, action)


# ──────────────────────────────────────────────────────────────────────
# MIC MODE — record from laptop mic, transcribe + answer + execute.
# ──────────────────────────────────────────────────────────────────────
async def _mic_loop(server: str, bridge, council: bool, stt_backend: str) -> None:
    # base64 lets us encode raw WAV bytes as ASCII so they can ride inside
    # a JSON HTTP payload.
    import base64
    import aiohttp
    from omnillm.robotics.audio import record_from_mic

    print(f"Mic mode (stt={stt_backend}). Ctrl-C to quit.\n")
    async with aiohttp.ClientSession() as session:
        while True:
            try:
                # beginner: ``record_from_mic`` is a BLOCKING function (it
                # waits for the user to press Enter twice). We wrap it in
                # ``asyncio.to_thread`` so it runs on a background thread
                # and doesn't freeze the event loop.
                audio = await asyncio.to_thread(record_from_mic)
            except KeyboardInterrupt:
                print()
                return
            if not audio:
                # Empty audio = pressed Enter twice without speaking, OR
                # mic capture failed silently. Skip and try again.
                print("  [no audio captured]")
                continue
            print(f"  captured {len(audio)} bytes — sending...")
            # The server handles transcription internally when "audio" is
            # provided; we pass stt_backend so it knows whether to use
            # OpenAI Whisper or local faster-whisper.
            payload = {
                "audio": base64.b64encode(audio).decode("ascii"),
                "council": council,
                "stt_backend": stt_backend,
            }
            action = await _post_interact(session, server, payload)
            if "error" in action:
                print(f"  [error] {action['error']}")
                continue
            await _execute(bridge, action)


# ──────────────────────────────────────────────────────────────────────
# Async main: set up the bridge and run the chosen loop.
# ──────────────────────────────────────────────────────────────────────
async def _amain(args: argparse.Namespace) -> int:
    # Bridge setup (skippable for pure-text-no-Pepper runs)
    bridge = None
    if not args.no_pepper:
        # Lazy import so --no-pepper doesn't require the robotics extras.
        from omnillm.robotics.pepper import make_pepper_bridge
        bridge = await make_pepper_bridge(
            robot_ip=args.robot_ip,
            robot_port=args.robot_port,
            bridge_port=args.bridge_port,
            # "auto" = try server mode first; if the bridge HTTP server
            # isn't reachable, silently fall back to "stub" mode so the
            # script keeps working without a robot.
            fallback="auto",
        )
        print(f"PepperBridge mode={bridge.mode}")

    if args.mode == "text":
        await _text_loop(args.server, bridge, args.council)
    else:
        await _mic_loop(args.server, bridge, args.council, args.stt)

    if bridge is not None:
        await bridge.disconnect()
    return 0


# ──────────────────────────────────────────────────────────────────────
# Synchronous wrapper + CLI parsing.
# ──────────────────────────────────────────────────────────────────────
def main() -> int:
    parser = argparse.ArgumentParser(description="OmniLLM unified launcher.")
    parser.add_argument("mode", choices=["text", "mic"], help="input mode")
    parser.add_argument("--server", default=DEFAULT_SERVER,
                        help=f"AI server base URL (default: {DEFAULT_SERVER})")
    parser.add_argument("--council", action="store_true",
                        help="use multi-LLM council instead of single model")
    parser.add_argument("--stt", choices=["api", "local"], default="api",
                        help="Whisper backend for mic mode (default: api)")
    parser.add_argument("--robot-ip", default="127.0.0.1",
                        help="Pepper IP — 127.0.0.1 for Choregraphe, LAN IP for real")
    # robot-port=None lets PepperBridge auto-detect: 62763 (Choregraphe)
    # then 9559 (real Pepper) based on the IP.
    parser.add_argument("--robot-port", type=int, default=None,
                        help="NAOqi port — defaults to 62763 (Choregraphe) "
                             "or 9559 (real). Pass explicitly to override.")
    parser.add_argument("--bridge-port", type=int, default=6000,
                        help="Python 2.7 NAOqi bridge HTTP port (default: 6000)")
    parser.add_argument("--no-pepper", action="store_true",
                        help="Skip Pepper output entirely (responses printed only)")
    args = parser.parse_args()

    # beginner: ``asyncio.run`` is the standard way to run an async function
    # from synchronous code. It creates an event loop, runs the coroutine,
    # and tears the loop down cleanly.
    try:
        return asyncio.run(_amain(args))
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    sys.exit(main())
