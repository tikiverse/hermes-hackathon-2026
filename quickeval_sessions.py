"""why: read Hermes sessions straight from state.db (read-only) and group them into reviewable turns."""
import json
import sqlite3

import quickeval_paths as paths
import quickeval_store as store

SESSION_KEYS = ("id", "source", "model", "title", "started_at")


def connect():
    path = paths.state_db_path()
    if not path.exists():
        raise FileNotFoundError(f"Hermes state db not found at {path}")
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=5)
    conn.row_factory = sqlite3.Row
    return conn


def query(name, params):
    conn = connect()
    try:
        return [dict(row) for row in conn.execute(paths.sql(name), params)]
    finally:
        conn.close()


def list_sessions(q="", limit=50):
    rows = query("list_sessions", {"q": q, "limit": max(1, min(int(limit), 500))})
    counts = store.eval_counts()
    return [{**row, "eval_count": counts.get(row["id"], 0)} for row in rows]


def latest_session():
    rows = list_sessions(limit=1)
    if not rows:
        return None
    return {key: rows[0][key] for key in ("id", "message_count", "last_activity_at")}


def loads(value):
    if not isinstance(value, str) or not value.strip():
        return value or None
    try:
        return json.loads(value)
    except ValueError:
        return value


def part_text(part):
    if isinstance(part, dict):
        return part.get("text") or part.get("content") or json.dumps(part)
    return str(part)


def text(content):
    """why: message content is either a string or a list of content parts."""
    parsed = loads(content) if str(content)[:1] in ("[", "{") else content
    if parsed is None:
        return ""
    if isinstance(parsed, str):
        return parsed
    if isinstance(parsed, list):
        return "\n".join(part_text(part) for part in parsed)
    return json.dumps(parsed, indent=2)


def function_of(call):
    fn = call.get("function")
    return fn if isinstance(fn, dict) else {}


def call_entry(call):
    fn = function_of(call)
    raw = fn.get("arguments")
    args = loads(raw) if raw else call.get("arguments")
    return {"id": call.get("id"), "name": fn.get("name") or call.get("name"), "arguments": args, "result": None}


class Turns:
    """why: turns are built incrementally from the ordered message stream."""

    def __init__(self):
        self.turns = []
        self.calls = {}

    def current(self):
        return self.turns[-1] if self.turns else None

    def feed(self, msg):
        handler = getattr(self, "on_" + str(msg["role"]), None)
        if handler:
            handler(msg)

    def on_user(self, msg):
        self.turns.append({"index": len(self.turns), "message_id": msg["id"], "ts": msg["timestamp"],
                           "prompt": text(msg["content"]), "response": "", "response_message_id": None,
                           "tools": [], "reasoning": ""})
        self.calls = {}

    def on_assistant(self, msg):
        turn = self.current()
        if turn is None:
            return
        self.take_text(turn, msg)
        for call in loads(msg["tool_calls"]) or []:
            self.add_call(turn, call)

    def take_text(self, turn, msg):
        body = text(msg["content"])
        if body.strip():
            turn["response"] = body
            turn["response_message_id"] = msg["id"]
        if msg["reasoning"]:
            turn["reasoning"] = msg["reasoning"]

    def add_call(self, turn, call):
        if not isinstance(call, dict):
            return
        entry = call_entry(call)
        turn["tools"].append(entry)
        self.calls[entry["id"]] = entry

    def on_tool(self, msg):
        turn = self.current()
        if turn is None:
            return
        entry = self.calls.get(msg["tool_call_id"])
        if entry is None:
            entry = {"id": msg["tool_call_id"], "name": msg["tool_name"], "arguments": None}
            turn["tools"].append(entry)
        entry["result"] = loads(msg["content"])


def get_turns(session_id):
    sessions = query("session", (session_id,))
    if not sessions:
        raise KeyError(session_id)
    builder = Turns()
    for msg in query("messages", (session_id,)):
        builder.feed(msg)
    done = store.evaluated_ids(session_id)
    turns = [{**turn, "evaluated": turn["message_id"] in done} for turn in builder.turns]
    session = {key: sessions[0][key] for key in SESSION_KEYS}
    return {"session": session, "system_prompt": sessions[0]["system_prompt"], "turns": turns}
