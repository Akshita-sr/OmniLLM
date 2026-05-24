"""OmniLLM unified launcher — pick an operating mode, drive the AI server.

────────────────────────────────────────────────────────────────────────────────
THE FOUR OPERATING MODES
────────────────────────────────────────────────────────────────────────────────
  1. LAPTOP ONLY              — mic or text on the laptop, response printed
                                to the terminal. No robot involved at all.
                                Useful when there is no Choregraphe and no
                                real Pepper available (e.g. on the train,
                                debugging the LLM pipeline).
  2. LAPTOP + CHOREGRAPHE     — input from laptop (mic or text), output goes
                                to the *virtual* Pepper inside Choregraphe.
                                This is what you use for thesis development:
                                no real-robot risk, full gesture+speech
                                rendering on the simulator.
  3. REAL PEPPER (robot mic)  — input captured by the real robot's own
                                microphone, response spoken + gestured by
                                the real robot. The "lab demo" mode.
  4. REAL PEPPER + LAPTOP MIC — input from the laptop mic (because the
                                real robot's mic is unreliable in noisy
                                labs), output on the real robot. Hybrid
                                fallback mode for live demos.

────────────────────────────────────────────────────────────────────────────────
USAGE
────────────────────────────────────────────────────────────────────────────────
Two ways to launch:

  (a) INTERACTIVE  — recommended for beginners. Just run:

          python run.py

      You will get a menu prompting for the mode and (when relevant) the
      robot IP. The script then runs the right combination of bridge,
      audio source, and server target for you.

  (b) EXPLICIT     — for scripts / CI / experienced users. You can still
      pass the legacy positional `text`/`mic` subcommand to skip the menu:

          python run.py text --mode laptop --council
          python run.py mic  --mode choregraphe --stt local
          python run.py text --mode real --robot-ip 192.168.1.42

────────────────────────────────────────────────────────────────────────────────
WHAT THIS SCRIPT TALKS TO
────────────────────────────────────────────────────────────────────────────────
  - The AI server (Flask app from omnillm/server/app.py) on
    http://127.0.0.1:5000. Sends utterances via POST /interact.
  - The Pepper bridge (Python 2.7 NAOqi wrapper from
    omnillm/server/naoqi_bridge_server.py) on http://127.0.0.1:6000.
    Forwards the RobotAction (speech, gesture, LED) for execution.

This is "Terminal 3" of the standard 3-terminal run book. T1 runs the
server, T2 runs the bridge, T3 is this launcher.
"""

# ── future imports ────────────────────────────────────────────────────────────
# WHAT: enables modern type-hint syntax (`dict[str, Any]`, `X | None`) on
#       every Python from 3.9 onwards.
# WHY:  free correctness/readability win — never hurts to keep.
from __future__ import annotations

# ── stdlib imports (kept at top so startup stays fast) ────────────────────────
# WHAT: only the standard library is touched at import time — no aiohttp,
#       no robotics packages — so `python run.py --help` works even on a
#       machine where the optional extras (audio, robotics) aren't installed.
import argparse   # CLI flag parsing
import asyncio    # `asyncio.run(...)` drives the async pipeline below
import os         # environment-variable plumbing for the mode → server
import sys        # exit codes
import uuid       # auto-generate session IDs when the user doesn't supply one
from datetime import datetime, timezone  # readable session ID prefix (UTC)


# ──────────────────────────────────────────────────────────────────────────────
# CONSTANTS
# ──────────────────────────────────────────────────────────────────────────────
# Default AI-server URL. The server in [omnillm/server/app.py] listens on
# port 5000 by default. Override with --server if you moved it.
DEFAULT_SERVER = "http://127.0.0.1:5000"

# Internal mode identifiers. Used in the env vars OMNILLM_MODE /
# OMNILLM_AUDIO_SRC so the server can record them in the experiment log.
MODE_LAPTOP = "laptop"               # no robot at all
MODE_CHOREGRAPHE = "choregraphe"     # virtual Pepper in Choregraphe
MODE_REAL = "real"                   # real Pepper, robot mic
MODE_REAL_LAPTOP_MIC = "real_laptop_mic"  # real Pepper, laptop mic
VALID_MODES = (MODE_LAPTOP, MODE_CHOREGRAPHE, MODE_REAL, MODE_REAL_LAPTOP_MIC)


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 1: INTERACTIVE MODE PROMPT
# ══════════════════════════════════════════════════════════════════════════════
# WHAT:  Show a numbered menu and read the user's choice from stdin.
# WHY:   The user (a beginner) said "interactive prompt on launch" — easier
#        than memorising flags, and the chosen mode is shown back to them so
#        there's no ambiguity about what's running.
# HOW IT CONNECTS:  Sets argparse Namespace fields the rest of the script
#        already reads (args.mode, args.robot_ip, args.input_source, ...).

_MENU = """
─────────────────────────────────────────────────────────────────────
  Select operating mode:
    [1] Laptop only          — mic/text in, text out, no robot
    [2] Laptop + Choregraphe — laptop input → virtual Pepper in Choregraphe
    [3] Real Pepper          — robot's mic + real robot responds
    [4] Real Pepper + laptop — laptop mic (fallback) + real robot responds
─────────────────────────────────────────────────────────────────────
"""


def _prompt_mode() -> str:
    """Show the mode menu and return one of the MODE_* constants.

    Loops until the user enters a valid digit. Ctrl-C / EOF returns
    MODE_LAPTOP as a safe default (no robot is touched).
    """
    print(_MENU)
    while True:
        try:
            choice = input("Choice [1-4]: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n(no choice — defaulting to laptop-only)")
            return MODE_LAPTOP

        mapping = {
            "1": MODE_LAPTOP,
            "2": MODE_CHOREGRAPHE,
            "3": MODE_REAL,
            "4": MODE_REAL_LAPTOP_MIC,
        }
        if choice in mapping:
            return mapping[choice]
        print(f"  '{choice}' is not a valid choice — please type 1, 2, 3 or 4.")


def _prompt_input_source(mode: str) -> str:
    """Return 'text' or 'mic' — what the user wants to use for INPUT.

    For mode 3 (real Pepper with robot mic) we hard-code "mic" because the
    point of that mode is to use the robot mic — but we still ask for modes
    that genuinely have a choice (1, 2, 4 can do either).
    """
    if mode == MODE_REAL:
        # Robot-mic-only mode — the choice is fixed.
        return "mic"
    while True:
        try:
            ans = input("Input source — [m]ic or [t]ext (press Enter for text): ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            return "text"
        if ans in ("", "t", "text"):
            return "text"
        if ans in ("m", "mic"):
            return "mic"
        print("  please type 'm' or 't'")


def _prompt_participant_id() -> str:
    """Ask for a participant label (e.g. P001). Defaults to 'P001' if blank.

    WHY:  Without this the server logs every row under participant_id='anon',
          and the 15-person within-subjects protocol (OMNILLM_MASTER_BOOK Part 5)
          cannot separate participants in post-session analysis.
    """
    try:
        pid = input("Participant ID [P001]: ").strip()
    except (EOFError, KeyboardInterrupt):
        return "P001"
    return pid or "P001"


def _auto_session_id() -> str:
    """Generate a fresh session ID. UTC timestamp + 6 random hex chars.

    Format: YYYYMMDDTHHMMSS_xxxxxx — sorts chronologically AND is collision-
    safe across simultaneous launches. Never blocks the user with a prompt.
    """
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    return f"{stamp}_{uuid.uuid4().hex[:6]}"


def _prompt_robot_ip(mode: str) -> str:
    """Ask for the real Pepper's IP address. Defaults to 127.0.0.1 if blank."""
    if mode not in (MODE_REAL, MODE_REAL_LAPTOP_MIC):
        return "127.0.0.1"  # not used; Choregraphe runs on loopback
    try:
        ip = input("Real Pepper IP (blank = 127.0.0.1): ").strip()
    except (EOFError, KeyboardInterrupt):
        return "127.0.0.1"
    return ip or "127.0.0.1"


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 2: TURN A MODE INTO CONCRETE CONFIG
# ══════════════════════════════════════════════════════════════════════════════
# WHAT:  Map "user picked mode 2" → dict of (robot_ip, robot_port,
#        no_pepper, audio_source) values that the rest of the script and
#        the server need to know about.
# WHY:   One source of truth for the mode → config mapping. If we later
#        change the Choregraphe loopback port we change it here once.
# HOW IT CONNECTS:  Called from _apply_mode_to_args() before either the
#        text loop or the mic loop runs.

def _mode_config(mode: str, robot_ip: str, robot_port: int | None) -> dict[str, Any]:
    """Return a dict of concrete settings derived from the chosen mode.

    Keys returned:
      - audio_source : "laptop_mic" | "robot_mic" | "text_only"
      - no_pepper    : True if we should skip the Pepper bridge entirely
      - robot_ip     : the IP to give to PepperBridge
      - robot_port   : explicit NAOqi port or None for auto-detect
    """
    if mode == MODE_LAPTOP:
        # Pure-laptop mode: no robot, no bridge. The server still runs and
        # gives us a RobotAction back, but we don't forward it anywhere.
        return {"audio_source": "laptop_mic", "no_pepper": True,
                "robot_ip": "127.0.0.1", "robot_port": robot_port}

    if mode == MODE_CHOREGRAPHE:
        # Choregraphe: virtual Pepper on loopback. Port 62763 is the
        # Choregraphe-locked NAOqi port per pepper_windows_quirks.md.
        return {"audio_source": "laptop_mic", "no_pepper": False,
                "robot_ip": "127.0.0.1", "robot_port": robot_port}

    if mode == MODE_REAL:
        # Real Pepper, robot mic. Port 9559 is the standard NAOqi port on
        # the real robot. The bridge will use the robot's own microphone.
        return {"audio_source": "robot_mic", "no_pepper": False,
                "robot_ip": robot_ip, "robot_port": robot_port}

    if mode == MODE_REAL_LAPTOP_MIC:
        # Real Pepper, laptop mic. Same robot config as MODE_REAL but
        # audio comes from the laptop (because the real robot's mic is
        # unreliable in noisy lab environments).
        return {"audio_source": "laptop_mic", "no_pepper": False,
                "robot_ip": robot_ip, "robot_port": robot_port}

    raise ValueError(f"Unknown mode: {mode!r}")  # defensive — should never hit


def _apply_mode_to_args(args: argparse.Namespace) -> None:
    """Resolve args.mode → fill in args.robot_ip / args.no_pepper / etc.

    Also exports OMNILLM_MODE and OMNILLM_AUDIO_SRC env vars so the server
    (which we don't control directly from here) can stamp them into the
    experiment log for every interaction.
    """
    cfg = _mode_config(args.mode, args.robot_ip, args.robot_port)
    args.robot_ip = cfg["robot_ip"]
    args.robot_port = cfg["robot_port"]
    args.no_pepper = cfg["no_pepper"]
    args.audio_source = cfg["audio_source"]

    # The server reads these on startup AND on every /interact call so it
    # can write the right `mode` field into each logged JSONL row. See
    # omnillm/server/app.py for the lookup.
    os.environ["OMNILLM_MODE"] = args.mode
    os.environ["OMNILLM_AUDIO_SRC"] = cfg["audio_source"]


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 3: HELPERS — talk to the AI server, then to Pepper
# ══════════════════════════════════════════════════════════════════════════════
# WHAT:  `_post_interact` POSTs a JSON body to /interact and returns the
#        parsed JSON reply. `_execute` prints the reply and forwards the
#        gesture/LED/speech to PepperBridge if there is one.
# WHY:   These two helpers are reused by BOTH the text loop and the mic
#        loop, so extracting them keeps the loops tiny.

async def _post_interact(session, server: str, payload: dict[str, Any]) -> dict[str, Any]:
    """POST /interact and decode the JSON response.

    `session` is an aiohttp.ClientSession — a reusable TCP connection pool.
    Reusing one session across many turns is faster than opening a new
    connection per turn.

    On any non-200 response we wrap the body in {"error": "..."} so the
    caller can print it instead of crashing.
    """
    async with session.post(f"{server}/interact", json=payload) as resp:
        if resp.status != 200:
            body = await resp.text()
            return {"error": f"server {resp.status}: {body[:200]}"}
        return await resp.json()


async def _execute(bridge, action: dict[str, Any]) -> None:
    """Print the response and (if we have a bridge) execute it on Pepper.

    `action` is the RobotAction dict returned by /interact:
        {speech, gesture, emotion_led, metadata}
    `bridge` is the PepperBridge instance, or None for laptop-only mode.
    """
    # Lazy import — keeps the robotics package out of the import graph when
    # we're running in laptop-only mode without that extra installed.
    from omnillm.robotics.bridge import RobotAction

    speech = action.get("speech", "")
    if not speech:
        print("  [no speech]")
        return

    print(f"  Pepper: {speech}")
    # Print a one-line metadata trail so the user can SEE what triage chose,
    # which model answered, how long it took.
    meta = action.get("metadata") or {}
    print(
        f"  [task={meta.get('task_type', '?')}, lang={meta.get('language', '?')}, "
        f"model={meta.get('model_id', '?')}, {meta.get('latency_ms', 0):.0f}ms]"
    )

    # If we have a bridge, forward the full RobotAction. None = mode 1.
    if bridge is not None:
        await bridge.execute_action(RobotAction(
            speech=speech,
            gesture=action.get("gesture"),
            emotion_led=action.get("emotion_led"),
            metadata=meta,
        ))


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 4: THE TWO INPUT LOOPS (text / mic)
# ══════════════════════════════════════════════════════════════════════════════
# WHAT:  Each loop reads input, calls /interact, executes the result. They
#        only differ in HOW they get the input (keyboard vs microphone).
# WHY:   Splitting them keeps each loop straight-line readable.

async def _text_loop(
    server: str,
    bridge,
    strategy_override: str,
    session_id: str,
    participant_id: str,
) -> None:
    """Read keyboard input one line at a time. Type 'quit' or Ctrl-C to exit.

    Every /interact POST carries session_id + participant_id so the server's
    ExperimentLogger can attribute the row to the correct participant. Without
    these fields the server defaults participant_id to 'anon' and the
    15-person protocol can't separate participants post-hoc.
    """
    # Lazy import so `python run.py --help` works without aiohttp installed.
    import aiohttp
    print(
        f"Text mode (strategy={strategy_override}, participant={participant_id}, "
        f"session={session_id}). Press Ctrl-C to quit.\n"
    )
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
            payload = {
                "text": utterance,
                "strategy_override": strategy_override,
                "session_id": session_id,
                "participant_id": participant_id,
            }
            action = await _post_interact(session, server, payload)
            if "error" in action:
                print(f"  [error] {action['error']}")
                continue
            await _execute(bridge, action)


async def _mic_loop(
    server: str,
    bridge,
    strategy_override: str,
    stt_backend: str,
    session_id: str,
    participant_id: str,
) -> None:
    """Record from the laptop mic, send the audio bytes to the server.

    See _text_loop for why session_id + participant_id are required on every
    payload (server-side default is 'anon' which breaks per-participant logs).
    """
    import base64
    import aiohttp
    from omnillm.robotics.audio import record_from_mic

    print(
        f"Mic mode (stt={stt_backend}, strategy={strategy_override}, "
        f"participant={participant_id}, session={session_id}). Ctrl-C to quit.\n"
    )
    async with aiohttp.ClientSession() as session:
        while True:
            try:
                # ``record_from_mic`` is synchronous — wrap it with
                # ``asyncio.to_thread`` so the event loop is not blocked
                # while the user holds Enter to record.
                audio = await asyncio.to_thread(record_from_mic)
            except KeyboardInterrupt:
                print()
                return
            if not audio:
                print("  [no audio captured]")
                continue
            print(f"  captured {len(audio)} bytes — sending...")
            payload = {
                # Base64-encode the WAV bytes so they fit in JSON.
                "audio": base64.b64encode(audio).decode("ascii"),
                "strategy_override": strategy_override,
                "stt_backend": stt_backend,
                "session_id": session_id,
                "participant_id": participant_id,
            }
            action = await _post_interact(session, server, payload)
            if "error" in action:
                print(f"  [error] {action['error']}")
                continue
            await _execute(bridge, action)


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 5: ASYNC MAIN — build the bridge, pick a loop, run.
# ══════════════════════════════════════════════════════════════════════════════
async def _amain(args: argparse.Namespace) -> int:
    """The actual program. Returns 0 on clean exit."""
    # ── Set up the Pepper bridge (skippable in mode 1) ─────────────────────────
    bridge = None
    if not args.no_pepper:
        # Lazy import so mode-1 runs don't need the robotics extras.
        from omnillm.robotics.pepper import make_pepper_bridge
        bridge = await make_pepper_bridge(
            robot_ip=args.robot_ip,
            robot_port=args.robot_port,
            bridge_port=args.bridge_port,
            # "auto" = try server mode first; if the bridge HTTP server
            # isn't reachable, silently fall back to "stub" so the script
            # still works without a live robot. See [omnillm/robotics/pepper.py].
            fallback="auto",
        )
        print(f"PepperBridge mode={bridge.mode}  (operating mode={args.mode})")
    else:
        print(f"PepperBridge: SKIPPED  (operating mode={args.mode}, laptop-only)")

    # ── Resolve strategy override (legacy --council alias) ─────────────────────
    strategy_override = args.force_strategy
    if args.council and strategy_override == "auto":
        strategy_override = "council"

    # ── Run the chosen input loop ──────────────────────────────────────────────
    if args.input_source == "text":
        await _text_loop(
            args.server, bridge, strategy_override,
            args.session_id, args.participant_id,
        )
    else:
        await _mic_loop(
            args.server, bridge, strategy_override, args.stt,
            args.session_id, args.participant_id,
        )

    # ── Clean up ───────────────────────────────────────────────────────────────
    if bridge is not None:
        await bridge.disconnect()
    return 0


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 6: SYNC WRAPPER + ARGPARSE
# ══════════════════════════════════════════════════════════════════════════════
# WHAT:  Parse CLI flags, then either show the interactive menu (if none of
#        the explicit-mode args were given) or honour the explicit ones.
# WHY:   We want BOTH a beginner-friendly menu AND a scriptable CLI from the
#        same launcher.

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="OmniLLM unified launcher.",
        epilog="If you don't pass --mode, you'll see an interactive menu.",
    )
    # The legacy positional `text` / `mic` argument is now OPTIONAL — if it's
    # missing we'll ask for it interactively.
    parser.add_argument(
        "input_source",
        nargs="?",
        choices=["text", "mic"],
        default=None,
        help="Input source (text or mic). Omit to be prompted.",
    )
    parser.add_argument(
        "--mode",
        choices=list(VALID_MODES),
        default=None,
        help="Operating mode: laptop / choregraphe / real / real_laptop_mic. "
             "Omit to be prompted.",
    )
    parser.add_argument("--server", default=DEFAULT_SERVER,
                        help=f"AI server base URL (default: {DEFAULT_SERVER})")
    parser.add_argument(
        "--force-strategy",
        choices=["auto", "direct", "rag", "council"],
        default="auto",
        help="Override autonomous triage. 'auto' (default) = triage decides; "
             "'council' = multi-LLM consensus (~$0.01/prompt — beware on long sessions).",
    )
    parser.add_argument("--council", action="store_true",
                        help="Legacy alias for --force-strategy council.")
    parser.add_argument("--stt", choices=["api", "local"], default="api",
                        help="Whisper backend for mic mode (default: api)")
    parser.add_argument("--robot-ip", default=None,
                        help="Pepper IP — auto-set per mode if omitted.")
    parser.add_argument("--robot-port", type=int, default=None,
                        help="NAOqi port — defaults to 62763 (Choregraphe) "
                             "or 9559 (real). Pass explicitly to override.")
    parser.add_argument("--bridge-port", type=int, default=6000,
                        help="Python 2.7 NAOqi bridge HTTP port (default: 6000)")
    # ``--no-pepper`` is still accepted explicitly. It forces mode "laptop"
    # regardless of what --mode says, for compatibility with old scripts.
    parser.add_argument("--no-pepper", action="store_true",
                        help="Force laptop-only mode (no Pepper bridge).")
    # ── Experiment-tracking IDs (required for the 15-person protocol) ─────────
    # WHY:  Without these, the server logs every row under participant_id='anon'.
    #       Post-session analysis (scripts/evaluate_session.py + analysis.ipynb)
    #       cannot separate participants. Interactive prompt fills the gap if
    #       the launcher is run without --participant-id.
    parser.add_argument("--participant-id", default=None,
                        help="Participant label, e.g. P001. Prompted if omitted.")
    parser.add_argument("--session-id", default=None,
                        help="Session ID. Auto-generated (UTC timestamp + uuid) if omitted.")
    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    # ── Resolve the operating mode ────────────────────────────────────────────
    if args.no_pepper:
        # Explicit --no-pepper overrides everything else.
        args.mode = MODE_LAPTOP
    elif args.mode is None:
        # No mode given → show the interactive menu.
        args.mode = _prompt_mode()

    # ── Resolve the input source ──────────────────────────────────────────────
    if args.input_source is None:
        args.input_source = _prompt_input_source(args.mode)

    # ── Resolve the real-Pepper IP (only prompts in modes 3/4 if not given) ──
    if args.robot_ip is None:
        args.robot_ip = _prompt_robot_ip(args.mode)

    # ── Resolve the participant + session IDs ────────────────────────────────
    # CRITICAL: without these the server stamps participant_id='anon' on every
    # row, which breaks the 15-person within-subjects protocol.
    if args.participant_id is None:
        args.participant_id = _prompt_participant_id()
    if args.session_id is None:
        args.session_id = _auto_session_id()

    # ── Stamp mode → concrete config (env vars, no_pepper, audio source) ─────
    _apply_mode_to_args(args)

    # ── Run the async pipeline ────────────────────────────────────────────────
    # asyncio.run sets up an event loop, runs _amain to completion, tears
    # the loop down cleanly. KeyboardInterrupt → exit 0 (tidy Ctrl-C).
    try:
        return asyncio.run(_amain(args))
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    sys.exit(main())
