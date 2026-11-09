"""why: what the UI asks of the eval log: runs with their judgment, saving a judgment, stats, leaderboard."""
import time
from collections import Counter, defaultdict

import quickeval_log
import quickeval_paths as paths
import quickeval_schema as schema

TURN_KEYS = ("session_id", "message_id", "prompt", "response", "model")
JUDGMENT_KEYS = ("note", "expected")


def log():
    return quickeval_log.EvalLog(paths.evals_path())


def norm(text):
    return " ".join((text or "").split())


def with_judgment(judgments, run):
    """why: the UI reads `good` only; older judgments get theirs filled in here."""
    judgment = judgments.get(run["id"])
    return {**run, "judgment": judgment and {**judgment, "good": schema.good_of(run, judgment)}}


def matches(query, run):
    since = time.time() - float(query["since"]) if query.get("since") else 0
    text = norm(query.get("q")).lower()
    haystack = norm(run["prompt"] + " " + " ".join(a.get("model") or "" for a in run["answers"])).lower()
    return all((
        not query.get("session_id") or run.get("session_id") == query["session_id"],
        (run.get("ts") or 0) >= since,
        not text or text in haystack,
        not query.get("multi") or len(run["answers"]) > 1,
    ))


def list_runs(query):
    current = log()
    judgments = current.judgments()
    kept = [with_judgment(judgments, r) for r in current.runs() if matches(query, r)]
    return sorted(kept, key=quickeval_log.ts_of, reverse=True)


def turn_run(runs, turn):
    """why: /eval knows the session and prompt, not the state.db message id, so match on both."""
    key = (turn.get("session_id"), norm(turn["prompt"]))
    found = [r for r in runs if (r.get("session_id"), norm(r["prompt"])) == key]
    return max(found, key=quickeval_log.ts_of) if found else None


def new_turn_run(current, turn):
    first = schema.answer("A", turn.get("model"), turn.get("response"))
    record = schema.run_record(turn["prompt"], [first], session_id=turn.get("session_id"),
                               message_id=turn.get("message_id"))
    return current.append(record)


def resolve_run(current, body):
    if body.get("run_id"):
        return current.find_run(body["run_id"])
    turn = {key: body.get(key) for key in TURN_KEYS}
    if not turn["prompt"]:
        raise ValueError("need run_id or a turn with a prompt")
    return turn_run(current.runs(), turn) or new_turn_run(current, turn)


def picked(run, body, old):
    """why: `good` (several answers) is the UI's pick; a bare `winner` (CLI, older clients) still works."""
    if "good" in body:
        good = schema.check_good(run, body["good"])
        return (None if good is None else schema.winner_of(good)), good
    if "winner" in body:
        winner = schema.check_winner(run, body["winner"])
        return winner, schema.good_of(run, {"winner": winner})
    return old.get("winner"), schema.good_of(run, old)


def save_judgment(body):
    """why: the UI sends only what changed; merge onto the newest judgment and append a full one."""
    current = log()
    run = resolve_run(current, body)
    old = current.judgments().get(run["id"]) or {}
    merged = {key: body[key] if key in body else old.get(key) for key in JUDGMENT_KEYS}
    winner, good = picked(run, body, old)
    record = schema.judgment_record(run["id"], winner, merged["note"], merged["expected"], good=good)
    current.append(record)
    return with_judgment({run["id"]: record}, run)


def stats():
    current = log()
    return {"runs": len(current.runs()), "judged": len(current.judgments())}


def judged_counts():
    current = log()
    judged = current.judgments()
    return Counter(r.get("session_id") for r in current.runs() if r["id"] in judged)


def add_answer(rows, good, a):
    """why: good = acceptable in a judged run; a win = the only good answer in that run."""
    row = rows[a.get("model") or "unknown"]
    row["answers"] += 1
    if good is None:
        return
    row["judged"] += 1
    row["good"] += a["label"] in good
    row["wins"] += good == [a["label"]]


def rates(model, row):
    return {"model": model, **row, "good_rate": row["good"] / row["judged"] if row["judged"] else None}


def board_order(row):
    return (row["good_rate"] or 0, row["wins"], row["answers"])


def leaderboard(query):
    """why: one row per model over runs with 2+ answers; several answers can be good in one run."""
    rows = defaultdict(empty_row)
    for run in list_runs({**query, "multi": "1"}):
        good = schema.good_of(run, run["judgment"])
        for a in run["answers"]:
            add_answer(rows, good, a)
    return sorted((rates(m, r) for m, r in rows.items()), key=board_order, reverse=True)


def empty_row():
    return {"answers": 0, "judged": 0, "good": 0, "wins": 0}
