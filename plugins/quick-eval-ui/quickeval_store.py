"""why: evals are an append-friendly JSONL file; this module is the only writer."""
import json
import os
import threading
import time
import uuid
from collections import Counter

import quickeval_paths as paths

LOCK = threading.Lock()
EDITABLE = ("verdict", "score", "tags", "notes", "expected", "comparisons", "prompt", "response")
GRADE = "grade"
SCORE_WORDS = ("tie", "none")


def is_grade(item):
    """why: the file also holds quick-eval's `eval`/`score` lines; untyped lines are older grades."""
    return item.get("type", GRADE) == GRADE


def parse_line(line):
    try:
        return json.loads(line)
    except ValueError:
        return None


def read_all():
    path = paths.evals_path()
    if not path.exists():
        return []
    parsed = [parse_line(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    return [item for item in parsed if item]


def write_all(items):
    path = paths.evals_path()
    tmp = path.with_suffix(".tmp")
    tmp.write_text("".join(json.dumps(i, ensure_ascii=False) + "\n" for i in items), encoding="utf-8")
    os.replace(tmp, path)


def check_verdict(value):
    if value not in (None, "pass", "fail"):
        raise ValueError("verdict must be 'pass', 'fail' or null")
    return value


def check_score(value):
    if value is None:
        return None
    score = int(value)
    if not 1 <= score <= 5:
        raise ValueError("score must be 1-5")
    return score


def check_tags(value):
    return [str(tag).strip() for tag in (value or []) if str(tag).strip()]


def keep(value):
    return value


CHECKS = {"verdict": check_verdict, "score": check_score, "tags": check_tags}


def clean(body):
    return {key: CHECKS.get(key, keep)(body[key]) for key in EDITABLE if key in body}


def new_item(body):
    base = {"type": GRADE, "id": uuid.uuid4().hex[:12], "ts": time.time(), "session_id": body.get("session_id"),
            "message_id": body.get("message_id"), "turn_index": body.get("turn_index"), "model": body.get("model"),
            "prompt": "", "response": "", "verdict": None, "score": None, "tags": [], "notes": "",
            "expected": "", "comparisons": []}
    return {**base, **clean(body)}


def same_turn(item, other):
    ours = (item["message_id"], item["session_id"])
    return bool(item["message_id"]) and ours == (other.get("message_id"), other.get("session_id"))


def upsert(items, item, body):
    """why: saving the same turn twice must update its eval, never duplicate it."""
    match = next((e for e in items if same_turn(item, e)), None)
    if match is None:
        items.append(item)
        return item
    match.update({**clean(body), "updated_ts": time.time()})
    return match


def create_eval(body):
    item = new_item(body)
    with LOCK:
        items = read_all()
        saved = upsert(items, item, body)
        write_all(items)
    return saved


def find(items, eval_id):
    for item in items:
        if item.get("id") == eval_id:
            return item
    raise KeyError(eval_id)


def update_eval(eval_id, body):
    with LOCK:
        items = read_all()
        item = find(items, eval_id)
        item.update({**clean(body), "updated_ts": time.time()})
        write_all(items)
    return item


def delete_eval(eval_id):
    with LOCK:
        items = read_all()
        find(items, eval_id)
        write_all([item for item in items if item.get("id") != eval_id])


def ts_of(item):
    return item.get("ts", 0)


def list_evals(session_id=""):
    with LOCK:
        items = read_all()
    kept = [item for item in items if is_grade(item) and (not session_id or item.get("session_id") == session_id)]
    return sorted(kept, key=ts_of, reverse=True)


def latest_scores(items):
    """why: quick-eval appends a new `score` line per /score; the newest one wins."""
    scores = sorted((item for item in items if item.get("type") == "score"), key=ts_of)
    return {item.get("eval_id"): item for item in scores}


def list_runs(session_id):
    """why: quick-eval `/eval` runs for one session, each with its current score."""
    with LOCK:
        items = read_all()
    scores = latest_scores(items)
    runs = [item for item in items if item.get("type") == "eval" and item.get("session_id") == session_id]
    return [{**run, "score": scores.get(run.get("id"))} for run in runs]


def winner_model(run, winner):
    match = next((a for a in run.get("answers", []) if a.get("label") == winner), None)
    if match is None and winner not in SCORE_WORDS:
        raise ValueError(f"unknown winner {winner!r}")
    return match.get("model") if match else None


def add_score(body):
    """why: same line shape as quick-eval's /score, so both tools read one history."""
    with LOCK:
        items = read_all()
        run = find(items, body.get("eval_id"))
        winner = str(body.get("winner") or "")
        record = {"type": "score", "eval_id": run["id"], "ts": time.time(), "winner": winner,
                  "winner_model": winner_model(run, winner), "note": str(body.get("note") or "")}
        with paths.evals_path().open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    return record


def eval_counts():
    return Counter(item.get("session_id") for item in list_evals())


def evaluated_ids(session_id):
    return {item["message_id"] for item in list_evals(session_id) if item.get("message_id")}


def export_jsonl():
    with LOCK:
        items = read_all()
    return "".join(json.dumps(item, ensure_ascii=False) + "\n" for item in items)


def ratio(part, whole):
    return part / whole if whole else None


def stats():
    items = list_evals()
    judged = [item["verdict"] for item in items if item.get("verdict")]
    scores = [item["score"] for item in items if item.get("score")]
    return {"total": len(items), "judged": len(judged), "pass_rate": ratio(judged.count("pass"), len(judged)),
            "avg_score": ratio(sum(scores), len(scores))}
