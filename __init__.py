"""Evalpad: create evals from a live Hermes conversation, in one keystroke.

Slash commands
  /eval                 record the last exchange (optionally: /eval good|bad|1-5 your note)
  /eval open            open the Evalpad UI in your browser (starts it if needed)
Dashboard
  An "Evalpad" tab renders sessions as turns with pretty JSON, a one-click eval form,
  and side-by-side comparison against another model.
"""

import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import evalpad_core as core  # noqa: E402

PORT = 8765
URL = f"http://127.0.0.1:{PORT}/"


def _parse(raw: str):
    """'good nice answer' / 'bad' / '4 too long' -> (verdict, score, note)."""
    words = (raw or "").split()
    verdict = score = None
    if words:
        w = words[0].lower()
        if w in ("good", "pass", "up", "+"):
            verdict, score, words = "pass", 5, words[1:]
        elif w in ("bad", "fail", "down", "-"):
            verdict, score, words = "fail", 1, words[1:]
        elif w.isdigit() and 1 <= int(w) <= 5:
            score = int(w)
            verdict = "pass" if score >= 4 else "fail" if score <= 2 else None
            words = words[1:]
    return verdict, score, " ".join(words)


def _open_ui() -> str:
    import standalone

    if not standalone.is_running(PORT):
        subprocess.Popen(
            [sys.executable, str(HERE / "standalone.py"), "--port", str(PORT), "--open"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    else:
        import webbrowser

        webbrowser.open(URL)
    return f"Evalpad: {URL}"


def _eval_command(raw_args: str = "") -> str:
    raw = (raw_args or "").strip()
    if raw.lower() in ("open", "ui"):
        return _open_ui()
    try:
        latest = core.latest_session()
        if not latest:
            return "Evalpad: no sessions found yet."
        data = core.get_turns(latest["id"])
    except Exception as e:  # never break the chat over an eval
        return f"Evalpad: could not read the session ({e})"
    turns = [t for t in data["turns"] if t["response"]]
    if not turns:
        return "Evalpad: nothing to evaluate yet."
    t = turns[-1]
    verdict, score, note = _parse(raw)
    core.create_eval(
        {
            "session_id": data["session"]["id"],
            "message_id": t["message_id"],
            "turn_index": t["index"],
            "model": data["session"]["model"],
            "prompt": t["prompt"],
            "response": t["response"],
            "verdict": verdict,
            "score": score,
            "notes": note,
        }
    )
    s = core.stats()
    label = verdict or "unrated"
    return f"Evalpad: saved ({label}). {s['total']} evals total. `/eval open` to review and compare."


def register(ctx):
    ctx.register_command(
        "eval",
        _eval_command,
        description="Record an eval for the last exchange, or `/eval open` for the Evalpad UI",
        args_hint="[good|bad|1-5] [note] | open",
    )
