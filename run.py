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
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from typing import Any


DEFAULT_SERVER = "http://127.0.0.1:5000"


async def _post_interact(
    session, server: str, payload: dict[str, Any]
) -> dict[str, Any]:
    async with session.post(f"{server}/interact", json=payload) as resp:
        if resp.status != 200:
            body = await resp.text()
            return {"error": f"server {resp.status}: {body[:200]}"}
        return await resp.json()


async def _execute(bridge, action: dict[str, Any]) -> None:
    from omnillm.robotics.bridge import RobotAction

    speech = action.get("speech", "")
    if not speech:
        print("  [no speech]")
        return
    print(f"  Pepper: {speech}")
    meta = action.get("metadata") or {}
    print(
        f"  [task={meta.get('task_type', '?')}, lang={meta.get('language', '?')}, "
        f"model={meta.get('model_id', '?')}, {meta.get('latency_ms', 0):.0f}ms]"
    )
    if bridge is not None:
        await bridge.execute_action(RobotAction(
            speech=speech,
            gesture=action.get("gesture"),
            emotion_led=action.get("emotion_led"),
            metadata=meta,
        ))


async def _text_loop(server: str, bridge, council: bool) -> None:
    import aiohttp
    print("Text mode. Type a prompt and press Enter. Ctrl-C to quit.\n")
    async with aiohttp.ClientSession() as session:
        while True:
            try:
                utterance = input("> ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                return
            if not utterance:
                continue
            if utterance.lower() in {"quit", "exit", "q"}:
                return
            payload = {"text": utterance, "council": council}
            action = await _post_interact(session, server, payload)
            if "error" in action:
                print(f"  [error] {action['error']}")
                continue
            await _execute(bridge, action)


async def _mic_loop(server: str, bridge, council: bool, stt_backend: str) -> None:
    import base64
    import aiohttp
    from omnillm.robotics.audio import record_from_mic

    print(f"Mic mode (stt={stt_backend}). Ctrl-C to quit.\n")
    async with aiohttp.ClientSession() as session:
        while True:
            try:
                audio = await asyncio.to_thread(record_from_mic)
            except KeyboardInterrupt:
                print()
                return
            if not audio:
                print("  [no audio captured]")
                continue
            print(f"  captured {len(audio)} bytes — sending...")
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


async def _amain(args: argparse.Namespace) -> int:
    # Bridge setup (skippable for pure-text-no-Pepper runs)
    bridge = None
    if not args.no_pepper:
        from omnillm.robotics.pepper import make_pepper_bridge
        bridge = await make_pepper_bridge(
            robot_ip=args.robot_ip,
            robot_port=args.robot_port,
            bridge_port=args.bridge_port,
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
    parser.add_argument("--robot-port", type=int, default=None,
                        help="NAOqi port — defaults to 62763 (Choregraphe) "
                             "or 9559 (real). Pass explicitly to override.")
    parser.add_argument("--bridge-port", type=int, default=6000,
                        help="Python 2.7 NAOqi bridge HTTP port (default: 6000)")
    parser.add_argument("--no-pepper", action="store_true",
                        help="Skip Pepper output entirely (responses printed only)")
    args = parser.parse_args()

    try:
        return asyncio.run(_amain(args))
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    sys.exit(main())
