"""why: one home for the two eval-log line shapes: `run` (a prompt + answers) and `judgment` (your call on it)."""
import time
import uuid

RUN = "run"
JUDGMENT = "judgment"
OUTCOMES = ("tie", "none")
LEGACY_VERDICT = {"pass": ["A"], "fail": []}


def new_id(prefix):
    return f"{prefix}_{uuid.uuid4().hex[:10]}"


def run_record(prompt, answers, session_id=None, message_id=None, params=None):
    """why: params = the settings every rerun answer got (B..); answer A kept the chat's own."""
    return {"v": 1, "type": RUN, "id": new_id("r"), "ts": time.time(), "session_id": session_id,
            "message_id": message_id, "prompt": prompt, "answers": answers, "params": params}


def answer(label, model, text, **extra):
    """why: answer A is the reply the user saw; B.. were asked again by /eval."""
    return {"label": label, "model": model, "text": text or "", **extra}


def judgment_record(run_id, winner=None, note="", expected="", good=None):
    """why: `good` = every acceptable answer (several can be right); `winner` stays its one-word summary."""
    return {"v": 1, "type": JUDGMENT, "id": new_id("j"), "ts": time.time(), "run_id": run_id, "winner": winner,
            "good": good, "note": note or "", "expected": expected or ""}


def labels_of(run):
    return [a["label"] for a in run["answers"]]


def check_good(run, good):
    unknown = [label for label in good or [] if label not in labels_of(run)]
    if unknown:
        raise ValueError(f"unknown answers {unknown}; use {'|'.join(labels_of(run))}")
    return None if good is None else [label for label in labels_of(run) if label in good]


def winner_of(good):
    """why: one good answer wins outright; several tie; none means no good answer."""
    return good[0] if len(good) == 1 else ("tie" if good else "none")


def good_of(run, judgment):
    """why: older lines name only a `winner` (tie = every answer good) or a Review `verdict` on answer A."""
    judgment = judgment or {}
    if judgment.get("good") is not None:
        return judgment["good"]
    if judgment.get("winner"):
        return legacy_good(run, judgment["winner"])
    return LEGACY_VERDICT.get(judgment.get("verdict"))


def legacy_good(run, winner):
    return labels_of(run) if winner == "tie" else [w for w in [winner] if w in labels_of(run)]


def check_winner(run, winner):
    labels = labels_of(run)
    if winner is not None and winner not in labels and winner not in OUTCOMES:
        raise ValueError(f"unknown winner {winner!r}; use {'|'.join(labels + list(OUTCOMES))}")
    return winner


def winner_model(run, winner):
    match = next((a for a in run["answers"] if a["label"] == winner), None)
    return match.get("model") if match else None
