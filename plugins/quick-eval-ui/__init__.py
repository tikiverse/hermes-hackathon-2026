"""why: browser UI for Hermes chats + quick-eval runs; /evals grades the last turn or opens the UI.

/evals [good|bad|1-5] [note]  record the last exchange
/evals open                   open the UI (compare runs come from /eval)
"""
import sys
import threading
import webbrowser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import quickeval_sessions as sessions  # noqa: E402
import quickeval_store as store  # noqa: E402
import standalone  # noqa: E402

PORT = 8765
URL = f"http://127.0.0.1:{PORT}/"
GOOD = ("good", "pass", "up", "+")
BAD = ("bad", "fail", "down", "-")


def verdict_for(score):
    if score is None:
        return None
    return "pass" if score >= 4 else "fail" if score <= 2 else None


def parse_args(raw):
    """why: 'good nice' -> pass/5, 'bad' -> fail/1, '4 note' -> score 4; the rest is the note."""
    words = (raw or "").split()
    head = words[0].lower() if words else ""
    scores = {**dict.fromkeys(GOOD, 5), **dict.fromkeys(BAD, 1), **{str(n): n for n in range(1, 6)}}
    score = scores.get(head)
    rest = words[1:] if score else words
    verdict = {5: "pass", 1: "fail"}.get(score) if head in GOOD + BAD else verdict_for(score)
    return verdict, score, " ".join(rest)


def open_ui():
    if not standalone.is_running(PORT):
        server = standalone.serve(PORT)
        threading.Thread(target=server.serve_forever, daemon=True).start()
    webbrowser.open(URL)
    return f"Quick Eval: {URL}"


def last_answered_turn():
    latest = sessions.latest_session()
    if not latest:
        return None, None
    data = sessions.get_turns(latest["id"])
    answered = [turn for turn in data["turns"] if turn["response"]]
    return data["session"], (answered[-1] if answered else None)


def save_last(raw):
    session, turn = last_answered_turn()
    if turn is None:
        return "Quick Eval: nothing to evaluate yet."
    verdict, score, note = parse_args(raw)
    store.create_eval({"session_id": session["id"], "message_id": turn["message_id"], "turn_index": turn["index"],
                       "model": session["model"], "prompt": turn["prompt"], "response": turn["response"],
                       "verdict": verdict, "score": score, "notes": note})
    return f"Quick Eval: saved ({verdict or 'unrated'}). {store.stats()['total']} evals total. `/evals open` to review."


def eval_command(raw_args=""):
    raw = (raw_args or "").strip()
    if raw.lower() in ("open", "ui"):
        return open_ui()
    try:
        return save_last(raw)
    except Exception as err:  # why: an eval must never break the chat
        return f"Quick Eval: could not read the session ({err})"


def register(ctx):
    ctx.register_command("evals", eval_command, description="Grade the last exchange, or `/evals open` for the UI",
                         args_hint="[good|bad|1-5] [note] | open")
