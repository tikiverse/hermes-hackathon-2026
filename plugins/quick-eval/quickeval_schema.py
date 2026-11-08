"""why: one home for eval-log line shapes (v1 `run` + `judgment`) and for reading older lines."""
import time
import uuid

VERSION = 1
RUN = "run"
JUDGMENT = "judgment"
HUMAN = "human"
VERDICTS = (None, "pass", "fail")
SCORE_WORDS = ("tie", "none")


def new_id(prefix):
    return f"{prefix}_{uuid.uuid4().hex[:10]}"


def run_record(prompt, answers, session_id=None, message_id=None, turn_id=None, suite=None):
    return {"v": VERSION, "type": RUN, "id": new_id("r"), "ts": time.time(), "session_id": session_id,
            "message_id": message_id, "turn_id": turn_id, "suite": suite, "prompt": prompt,
            "context": "prompt_only", "answers": answers}


def answer(label, role, model, text, **extra):
    """why: `role` is `original` (the reply the user saw) or `rerun` (asked again by /eval)."""
    return {"label": label, "role": role, "model": model, "text": text or "", **extra}


def judgment_record(run_id, winner=None, scores=None, note="", expected="", judge=HUMAN):
    return {"v": VERSION, "type": JUDGMENT, "id": new_id("j"), "ts": time.time(), "run_id": run_id, "judge": judge,
            "winner": winner, "scores": scores or {}, "note": note or "", "expected": expected or ""}


def check_winner(run, winner):
    labels = [a["label"] for a in run["answers"]]
    if winner is not None and winner not in labels and winner not in SCORE_WORDS:
        raise ValueError(f"unknown winner {winner!r}; use {'|'.join(labels + list(SCORE_WORDS))}")
    return winner


def check_score(entry):
    score = entry.get("score")
    if score is not None and not 1 <= int(score) <= 5:
        raise ValueError("score must be 1-5")
    if entry.get("verdict") not in VERDICTS:
        raise ValueError("verdict must be 'pass', 'fail' or null")
    tags = [str(t).strip() for t in entry.get("tags") or [] if str(t).strip()]
    return {"score": None if score is None else int(score), "verdict": entry.get("verdict"), "tags": tags}


def check_scores(run, scores):
    labels = {a["label"] for a in run["answers"]}
    unknown = set(scores or {}) - labels
    if unknown:
        raise ValueError(f"unknown answer labels {sorted(unknown)}")
    return {label: check_score(entry or {}) for label, entry in (scores or {}).items()}


def winner_model(run, winner):
    match = next((a for a in run["answers"] if a["label"] == winner), None)
    return match.get("model") if match else None


def from_eval(line):
    """why: pre-v1 quick-eval `eval` line: `source` became `role`."""
    answers = [{**a, "role": a.get("source", "rerun")} for a in line.get("answers", [])]
    return [{**line, "v": VERSION, "type": RUN, "answers": answers}]


def from_score(line):
    return [{"v": VERSION, "type": JUDGMENT, "id": "j_" + str(line.get("eval_id")) + str(line.get("ts")),
             "ts": line.get("ts", 0), "run_id": line.get("eval_id"), "judge": HUMAN, "winner": line.get("winner"),
             "scores": {}, "note": line.get("note", ""), "expected": ""}]


def legacy_answers(line):
    first = answer("A", "original", line.get("model"), line.get("response"))
    rest = [answer(chr(66 + i), "rerun", c.get("model"), c.get("response"), latency_ms=c.get("latency_ms"))
            for i, c in enumerate(line.get("comparisons") or [])]
    return [first, *rest]


def from_grade(line):
    """why: pre-v1 UI grade line -> one run (answer A + any old comparisons) + its judgment."""
    run_id = "r_" + str(line.get("id"))
    run = {"v": VERSION, "type": RUN, "id": run_id, "ts": line.get("ts", 0), "session_id": line.get("session_id"),
           "message_id": line.get("message_id"), "turn_id": None, "suite": None, "prompt": line.get("prompt", ""),
           "context": "chat", "answers": legacy_answers(line)}
    score = {"score": line.get("score"), "verdict": line.get("verdict"), "tags": line.get("tags") or []}
    preferred = next((chr(66 + i) for i, c in enumerate(line.get("comparisons") or []) if c.get("preferred")), None)
    judged = {**judgment_record(run_id, preferred, {"A": score}, line.get("notes"), line.get("expected")),
              "id": "j_" + str(line.get("id")), "ts": line.get("updated_ts") or line.get("ts", 0)}
    return [run, judged]


def keep(line):
    return [line]


READERS = {RUN: keep, JUDGMENT: keep, "eval": from_eval, "score": from_score, "grade": from_grade}


def normalize(line):
    """why: every reader sees only v1 lines, whatever wrote the file."""
    reader = READERS.get(line.get("type", "grade"))
    return reader(line) if reader else []
