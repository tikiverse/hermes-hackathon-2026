"""why: what the UI asks of the eval log: runs with their judgment, saving a judgment, stats, leaderboard."""
import time
from collections import Counter, defaultdict

import quickeval_log
import quickeval_paths as paths
import quickeval_schema as schema

TURN_KEYS = ("session_id", "message_id", "prompt", "response", "model")


def log():
    return quickeval_log.EvalLog(paths.evals_path())


def norm(text):
    return " ".join((text or "").split())


def with_judgment(judgments, run):
    return {**run, "judgment": judgments.get(run["id"])}


def answer_models(run):
    return {a.get("model") for a in run["answers"]}


def matches(query, run):
    since = time.time() - float(query["since"]) if query.get("since") else 0
    text = norm(query.get("q")).lower()
    return all((
        not query.get("session_id") or run.get("session_id") == query["session_id"],
        (run.get("ts") or 0) >= since,
        not query.get("model") or query["model"] in answer_models(run),
        not text or text in norm(run["prompt"]).lower(),
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
    by_message = [r for r in found if r.get("message_id") == turn.get("message_id")]
    pool = by_message or found
    return max(pool, key=quickeval_log.ts_of) if pool else None


def new_turn_run(current, turn):
    first = schema.answer("A", "original", turn.get("model"), turn.get("response"))
    record = schema.run_record(turn["prompt"], [first], session_id=turn.get("session_id"),
                               message_id=turn.get("message_id"))
    return current.append({**record, "context": "chat"})


def resolve_run(current, body):
    if body.get("run_id"):
        return current.find_run(body["run_id"])
    turn = {key: body.get(key) for key in TURN_KEYS}
    if not turn["prompt"]:
        raise ValueError("need run_id or a turn with a prompt")
    return turn_run(current.runs(), turn) or new_turn_run(current, turn)


def merged_scores(old, new):
    return {**(old or {}), **(new or {})}


def save_judgment(body):
    """why: the UI sends only what changed; merge onto the newest judgment and append a full one."""
    current = log()
    run = resolve_run(current, body)
    old = current.judgments().get(run["id"]) or {}
    winner = schema.check_winner(run, body["winner"] if "winner" in body else old.get("winner"))
    scores = schema.check_scores(run, merged_scores(old.get("scores"), body.get("scores")))
    note = body.get("note", old.get("note", ""))
    record = schema.judgment_record(run["id"], winner, scores, note, body.get("expected", old.get("expected", "")))
    current.append(record)
    return with_judgment({run["id"]: record}, run)


def score_entries(judgments):
    return [s for j in judgments for s in (j.get("scores") or {}).values()]


def ratio(part, whole):
    return part / whole if whole else None


def stats():
    current = log()
    judgments = list(current.judgments().values())
    entries = score_entries(judgments)
    verdicts = [s["verdict"] for s in entries if s.get("verdict")]
    scores = [s["score"] for s in entries if s.get("score")]
    return {"runs": len(current.runs()), "judged": len(judgments),
            "pass_rate": ratio(verdicts.count("pass"), len(verdicts)), "avg_score": ratio(sum(scores), len(scores))}


def judged_counts():
    current = log()
    judged = current.judgments()
    return Counter(r.get("session_id") for r in current.runs() if r["id"] in judged)


def add_answer(rows, run, a):
    judgment = run.get("judgment") or {}
    row = rows[a.get("model") or "unknown"]
    entry = (judgment.get("scores") or {}).get(a["label"]) or {}
    row["answers"] += 1
    row["judged"] += 1 if judgment else 0
    row["wins"] += 1 if judgment.get("winner") == a["label"] else 0
    row["ties"] += 1 if judgment.get("winner") == "tie" and len(run["answers"]) > 1 else 0
    row["errors"] += 1 if a.get("error") else 0
    row["scores"] += [entry["score"]] if entry.get("score") else []
    row["latency"] += [a["latency_ms"]] if a.get("latency_ms") else []
    row["cost"] += a.get("cost_usd") or 0
    row["contests"] += 1 if judgment.get("winner") and len(run["answers"]) > 1 else 0


def empty_row():
    return {"answers": 0, "judged": 0, "wins": 0, "ties": 0, "errors": 0, "scores": [], "latency": [], "cost": 0.0,
            "contests": 0}


def finish(model, row):
    return {"model": model, "answers": row["answers"], "judged": row["judged"], "wins": row["wins"],
            "ties": row["ties"], "contests": row["contests"], "win_rate": ratio(row["wins"], row["contests"]),
            "avg_score": ratio(sum(row["scores"]), len(row["scores"])), "errors": row["errors"],
            "avg_latency_ms": ratio(sum(row["latency"]), len(row["latency"])), "cost_usd": round(row["cost"], 6)}


def win_order(row):
    return (row["win_rate"] or 0, row["avg_score"] or 0, row["answers"])


def leaderboard(query):
    """why: one row per model across matching runs; win rate counts only runs with 2+ answers and a winner."""
    rows = defaultdict(empty_row)
    for run in list_runs(query):
        for a in run["answers"]:
            add_answer(rows, run, a)
    return sorted((finish(m, r) for m, r in rows.items()), key=win_order, reverse=True)
