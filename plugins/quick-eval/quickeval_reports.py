"""why: what the UI asks of the eval log: runs with their judgment, saving a judgment, stats, leaderboard."""
import time
from collections import Counter, defaultdict

import quickeval_log
import quickeval_paths as paths
import quickeval_schema as schema

TURN_KEYS = ("session_id", "message_id", "prompt", "response", "model")
JUDGMENT_KEYS = ("winner", "verdict", "note", "expected")


def log():
    return quickeval_log.EvalLog(paths.evals_path())


def norm(text):
    return " ".join((text or "").split())


def with_judgment(judgments, run):
    return {**run, "judgment": judgments.get(run["id"])}


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


def save_judgment(body):
    """why: the UI sends only what changed; merge onto the newest judgment and append a full one."""
    current = log()
    run = resolve_run(current, body)
    old = current.judgments().get(run["id"]) or {}
    merged = {key: body[key] if key in body else old.get(key) for key in JUDGMENT_KEYS}
    record = schema.judgment_record(run["id"], schema.check_winner(run, merged["winner"]),
                                    schema.check_verdict(merged["verdict"]), merged["note"], merged["expected"])
    current.append(record)
    return with_judgment({run["id"]: record}, run)


def stats():
    current = log()
    return {"runs": len(current.runs()), "judged": len(current.judgments())}


def judged_counts():
    current = log()
    judged = current.judgments()
    return Counter(r.get("session_id") for r in current.runs() if r["id"] in judged)


def add_answer(rows, winner, a):
    row = rows[a.get("model") or "unknown"]
    row["answers"] += 1
    row["contests"] += 1 if winner else 0
    row["wins"] += 1 if winner == a["label"] else 0


def win_rate(model, row):
    rate = row["wins"] / row["contests"] if row["contests"] else None
    return {"model": model, **row, "win_rate": rate}


def win_order(row):
    return (row["win_rate"] or 0, row["wins"], row["answers"])


def leaderboard(query):
    """why: one row per model; a contest is a run with 2+ answers and a picked winner (tie/none count as losses)."""
    rows = defaultdict(empty_row)
    for run in list_runs({**query, "multi": "1"}):
        winner = (run["judgment"] or {}).get("winner")
        for a in run["answers"]:
            add_answer(rows, winner, a)
    return sorted((win_rate(m, r) for m, r in rows.items()), key=win_order, reverse=True)


def empty_row():
    return {"answers": 0, "wins": 0, "contests": 0}
