"""End-to-end demo: AI server -> virtual or real Pepper.

Runs in Python 2.7 (NAOqi side). Two modes:

    1. Default (full demo): Asks OmniLLM a question over HTTP, then makes
       Pepper speak the reply via NAOqi.

    2. --check-only: Skip the AI server. Just verify the Python <-> Pepper
       bridge works (reads language list, makes Pepper say a fixed sentence).
       Use this first when something seems broken -- if --check-only fails,
       the robot/NAOqi connection is the issue, not OmniLLM.

Prerequisites:
    - Choregraphe open and "Connected to AKSHITA" (virtual), OR real Pepper booted
    - For full demo: AI server running (python -m omnillm.server.app)
    - PYTHONPATH includes pynaoqi (set globally on this machine)

Usage examples:
    REM Sanity check only -- no AI server needed:
    C:\\Python27\\python.exe demo_pepper_omnillm.py --check-only --robot-port 49959

    REM Full AI demo on virtual Pepper:
    C:\\Python27\\python.exe demo_pepper_omnillm.py --robot-port 49959 --condition A --rag --question "What time does the lab open?"

    REM Real Pepper at the lab (default port 9559, IP from chest button):
    C:\\Python27\\python.exe demo_pepper_omnillm.py --robot-ip 192.168.1.42 --condition A --rag --question "What time does the lab open?"

Condition cheat sheet:
    A: GPT-4o-mini (cloud) + RAG on    -- main experimental arm
    B: Llama 3 8B (local Ollama)        -- local-only baseline
    C: Smart-routed                     -- chooses best model per task
    D: Consensus / council              -- queries 3 models and synthesises
    E: GPT-4o-mini, RAG off             -- control arm (cheapest)
"""

import argparse
import json
import urllib2

from naoqi import ALBroker, ALProxy


def _safe(text):
    """Encode unicode/emoji safely for Windows cp850 console."""
    if hasattr(text, "encode"):
        return text.encode("ascii", "replace")
    return text


def ask_ai_server(server_url, question, condition, rag_enabled):
    """POST a question to OmniLLM's AI server and return the parsed JSON reply."""
    payload = json.dumps({
        "text": question,
        "participant_id": "P001",
        "session_id": "demo-session",
        "condition": condition,
        "rag_enabled": rag_enabled,
    })
    request = urllib2.Request(
        server_url,
        data=payload.encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    response = urllib2.urlopen(request, timeout=60)
    return json.loads(response.read())


def run_check_only(tts):
    """Bridge sanity test -- no AI server involved."""
    print("[check] Current language:", _safe(tts.getLanguage()))
    print("[check] Available languages:", [_safe(l)
          for l in tts.getAvailableLanguages()])
    print("[check] Saying a test sentence...")
    tts.say("Hello from my own Python script")
    print("[check] All bridge checks passed.")


def run_ai_demo(tts, server_url, question, condition, rag_enabled):
    """Full demo: ask AI server, then make Pepper speak the reply."""
    print("[1/3] Asking the AI server...")
    print("       Question : " + question)
    print("       Condition: " + condition +
          (" (RAG ON)" if rag_enabled else " (RAG OFF)"))
    result = ask_ai_server(server_url, question, condition, rag_enabled)

    print("[1/3] Raw server reply:")
    print("       " + json.dumps(result, indent=2).replace("\n", "\n       "))

    speech = result.get("speech") or result.get("response_text") or ""
    gesture = result.get("gesture", "(none)")
    metadata = result.get("metadata", {})
    model = metadata.get("model_id", "(unknown)")

    print("[2/3] Parsed:")
    print("       Speech : " + _safe(speech))
    print("       Gesture: " + _safe(gesture))
    print("       Model  : " + _safe(model))

    if not speech:
        print("[ERR] No speech in the reply. Nothing to say.")
        return

    print("[3/3] Making Pepper speak...")
    tts.say(speech.encode("utf-8") if hasattr(speech, "encode") else speech)
    print("Done. Look at Choregraphe's Dialog panel (or listen to Pepper).")


def main():
    parser = argparse.ArgumentParser(
        description="OmniLLM Pepper demo (full AI flow + optional bridge check).")
    parser.add_argument("--robot-ip", default="127.0.0.1",
                        help="Pepper IP. Use real Pepper's IP at the lab.")
    parser.add_argument("--robot-port", type=int, default=9559,
                        help="NAOqi port. Real Pepper: 9559. Virtual: variable -- check Choregraphe.")
    parser.add_argument("--server-url", default="http://localhost:5000/interact",
                        help="OmniLLM AI server URL.")
    parser.add_argument("--question", default="Hello Pepper, what time does the lab open?",
                        help="The question to ask the AI server (ignored in --check-only mode).")
    parser.add_argument("--condition", default="E", choices=["A", "B", "C", "D", "E"],
                        help="Experimental condition (default: E).")
    parser.add_argument("--rag", action="store_true",
                        help="Enable RAG. Server must be started WITHOUT --no-rag.")
    parser.add_argument("--check-only", action="store_true",
                        help="Skip the AI server. Only run the Pepper bridge sanity test.")
    args = parser.parse_args()

    # Listen on 127.0.0.1 for virtual Pepper (Windows 11 loopback workaround).
    # Listen on 0.0.0.0 for real Pepper so the robot can call back via LAN.
    listen_ip = "127.0.0.1" if args.robot_ip in (
        "127.0.0.1", "localhost") else "0.0.0.0"

    print("Connecting to Pepper at {}:{} (broker listens on {})...".format(
        args.robot_ip, args.robot_port, listen_ip))
    broker = ALBroker("demoBroker", listen_ip, 0,
                      args.robot_ip, args.robot_port)

    try:
        tts = ALProxy("ALTextToSpeech")
        if args.check_only:
            run_check_only(tts)
        else:
            run_ai_demo(tts, args.server_url, args.question,
                        args.condition, args.rag)
    finally:
        broker.shutdown()


if __name__ == "__main__":
    main()


# C:\Python27\python.exe scripts\pepper_demo\demo_pepper_omnillm.py --check-only --robot-port 49959
# C:\Python27\python.exe "C:\Users\akshi\OneDrive\Desktop\demo_pepper_omnillm.py" --condition E --question "Ciao, come stai?" --robot-port 49959
