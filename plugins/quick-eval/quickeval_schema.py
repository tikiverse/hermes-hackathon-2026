"""why: one home for the two eval-log line shapes: `run` (a prompt + answers) and `judgment` (your call on it)."""
import time
import uuid

RUN = "run"
JUDGMENT = "judgment"
OUTCOMES = ("tie", "none")
VERDICTS = (None, "pass", "fail")


def new_id(prefix):
    return f"{prefix}_{uuid.uuid4().hex[:10]}"


def run_record(prompt, answers, session_id=None, message_id=None):
    return {"v": 1, "type": RUN, "id": new_id("r"), "ts": time.time(), "session_id": session_id,
            "message_id": message_id, "prompt": prompt, "answers": answers}


def answer(label, model, text, **extra):
    """why: answer A is the reply the user saw; B.. were asked again by /eval."""
    return {"label": label, "model": model, "text": text or "", **extra}


def judgment_record(run_id, winner=None, verdict=None, note="", expected=""):
    return {"v": 1, "type": JUDGMENT, "id": new_id("j"), "ts": time.time(), "run_id": run_id, "winner": winner,
            "verdict": verdict, "note": note or "", "expected": expected or ""}


def check_winner(run, winner):
    labels = [a["label"] for a in run["answers"]]
    if winner is not None and winner not in labels and winner not in OUTCOMES:
        raise ValueError(f"unknown winner {winner!r}; use {'|'.join(labels + list(OUTCOMES))}")
    return winner


def check_verdict(verdict):
    if verdict not in VERDICTS:
        raise ValueError("verdict must be 'pass', 'fail' or null")
    return verdict


def winner_model(run, winner):
    match = next((a for a in run["answers"] if a["label"] == winner), None)
    return match.get("model") if match else None
