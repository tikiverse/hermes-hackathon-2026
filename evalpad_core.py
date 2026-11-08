"""Evalpad core: read Hermes sessions, store evals as JSONL, compare against other models.

Framework-free on purpose. The same ``handle()`` dispatcher backs both the Hermes
dashboard router (``dashboard/plugin_api.py``) and the standalone server
(``standalone.py``), so the UI behaves identically in both.
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

_LOCK = threading.Lock()

DEFAULT_PRESETS = [
    {
        "label": "Hermes 4 405B (OpenRouter)",
        "model": "nousresearch/hermes-4-405b",
        "base_url": "https://openrouter.ai/api/v1",
        "api_key_env": "OPENROUTER_API_KEY",
    },
    {
        "label": "Claude Sonnet (OpenRouter)",
        "model": "anthropic/claude-sonnet-4.5",
        "base_url": "https://openrouter.ai/api/v1",
        "api_key_env": "OPENROUTER_API_KEY",
    },
    {
        "label": "DeepSeek V3 (OpenRouter)",
        "model": "deepseek/deepseek-chat",
        "base_url": "https://openrouter.ai/api/v1",
        "api_key_env": "OPENROUTER_API_KEY",
    },
]


# --------------------------------------------------------------------------- paths


def hermes_home() -> Path:
    return Path(os.environ.get("HERMES_HOME") or Path.home() / ".hermes")


def evals_dir() -> Path:
    d = Path(os.environ.get("EVALPAD_DIR") or hermes_home() / "evals")
    d.mkdir(parents=True, exist_ok=True)
    return d


def evals_path() -> Path:
    return evals_dir() / "evals.jsonl"


def state_db_path() -> Path:
    return Path(os.environ.get("EVALPAD_STATE_DB") or hermes_home() / "state.db")


# --------------------------------------------------------------------------- sessions


def _connect_ro() -> sqlite3.Connection:
    p = state_db_path()
    if not p.exists():
        raise FileNotFoundError(f"Hermes state db not found at {p}")
    conn = sqlite3.connect(f"file:{p}?mode=ro", uri=True, timeout=5)
    conn.row_factory = sqlite3.Row
    return conn


def list_sessions(q: str = "", limit: int = 50) -> List[Dict[str, Any]]:
    limit = max(1, min(int(limit), 500))
    sql = (
        "SELECT id, source, model, title, started_at, last_activity_at, message_count "
        "FROM sessions WHERE message_count > 0 "
    )
    args: List[Any] = []
    if q:
        sql += "AND (title LIKE ? OR id LIKE ? OR model LIKE ?) "
        args += [f"%{q}%"] * 3
    sql += "ORDER BY COALESCE(last_activity_at, started_at) DESC LIMIT ?"
    args.append(limit)
    conn = _connect_ro()
    try:
        rows = [dict(r) for r in conn.execute(sql, args)]
    finally:
        conn.close()
    counts = _eval_counts()
    for r in rows:
        r["eval_count"] = counts.get(r["id"], 0)
    return rows


def _loads(v: Any) -> Any:
    if v is None or v == "":
        return None
    if isinstance(v, (list, dict)):
        return v
    try:
        return json.loads(v)
    except Exception:
        return v


def _text(content: Any) -> str:
    """Message content may be a string or a list of content parts."""
    c = _loads(content) if isinstance(content, str) and content[:1] in "[{" else content
    if c is None:
        return ""
    if isinstance(c, str):
        return c
    if isinstance(c, list):
        out = []
        for part in c:
            if isinstance(part, dict):
                out.append(part.get("text") or part.get("content") or json.dumps(part))
            else:
                out.append(str(part))
        return "\n".join(out)
    return json.dumps(c, indent=2)


def get_turns(session_id: str) -> Dict[str, Any]:
    """Group a session's messages into turns: one user message + everything the agent did."""
    conn = _connect_ro()
    try:
        sess = conn.execute(
            "SELECT id, source, model, title, started_at, system_prompt FROM sessions WHERE id = ?",
            (session_id,),
        ).fetchone()
        if sess is None:
            raise KeyError(session_id)
        msgs = conn.execute(
            "SELECT id, role, content, tool_call_id, tool_calls, tool_name, timestamp, "
            "finish_reason, reasoning FROM messages "
            "WHERE session_id = ? AND COALESCE(active, 1) = 1 ORDER BY id",
            (session_id,),
        ).fetchall()
    finally:
        conn.close()

    turns: List[Dict[str, Any]] = []
    cur: Optional[Dict[str, Any]] = None
    results: Dict[str, Dict[str, Any]] = {}

    def new_turn(m: sqlite3.Row) -> Dict[str, Any]:
        return {
            "index": len(turns),
            "message_id": m["id"],
            "ts": m["timestamp"],
            "prompt": _text(m["content"]),
            "response": "",
            "response_message_id": None,
            "tools": [],
            "reasoning": "",
        }

    for m in msgs:
        role = m["role"]
        if role == "user":
            cur = new_turn(m)
            turns.append(cur)
            results = {}
        elif cur is None:
            continue
        elif role == "assistant":
            text = _text(m["content"])
            if text.strip():
                cur["response"] = text
                cur["response_message_id"] = m["id"]
            if m["reasoning"]:
                cur["reasoning"] = m["reasoning"]
            for tc in _loads(m["tool_calls"]) or []:
                if not isinstance(tc, dict):
                    continue
                fn = tc.get("function", {}) if isinstance(tc.get("function"), dict) else {}
                args = _loads(fn.get("arguments")) if fn.get("arguments") else tc.get("arguments")
                entry = {"id": tc.get("id"), "name": fn.get("name") or tc.get("name"), "arguments": args, "result": None}
                cur["tools"].append(entry)
                if entry["id"]:
                    results[entry["id"]] = entry
        elif role == "tool":
            entry = results.get(m["tool_call_id"] or "")
            body = _loads(m["content"]) if isinstance(m["content"], str) else m["content"]
            if entry is not None:
                entry["result"] = body
            else:
                cur["tools"].append({"id": m["tool_call_id"], "name": m["tool_name"], "arguments": None, "result": body})

    evald = {e["message_id"] for e in list_evals(session_id=session_id) if e.get("message_id")}
    for t in turns:
        t["evaluated"] = t["message_id"] in evald
    return {
        "session": {k: sess[k] for k in ("id", "source", "model", "title", "started_at")},
        "system_prompt": sess["system_prompt"],
        "turns": turns,
    }


def latest_session() -> Optional[Dict[str, Any]]:
    rows = list_sessions(limit=1)
    if not rows:
        return None
    r = rows[0]
    return {"id": r["id"], "message_count": r["message_count"], "last_activity_at": r["last_activity_at"]}


# --------------------------------------------------------------------------- eval store


def _read_all() -> List[Dict[str, Any]]:
    p = evals_path()
    if not p.exists():
        return []
    out = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue  # tolerate a torn line rather than losing the whole file
    return out


def _write_all(items: List[Dict[str, Any]]) -> None:
    p = evals_path()
    tmp = p.with_suffix(".tmp")
    tmp.write_text("".join(json.dumps(i, ensure_ascii=False) + "\n" for i in items), encoding="utf-8")
    os.replace(tmp, p)


def _eval_counts() -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for e in _read_all():
        sid = e.get("session_id")
        if sid:
            counts[sid] = counts.get(sid, 0) + 1
    return counts


def list_evals(session_id: str = "") -> List[Dict[str, Any]]:
    with _LOCK:
        items = _read_all()
    if session_id:
        items = [i for i in items if i.get("session_id") == session_id]
    return sorted(items, key=lambda i: i.get("ts", 0), reverse=True)


_EDITABLE = ("verdict", "score", "tags", "notes", "expected", "comparisons", "prompt", "response")


def _clean(body: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for k in _EDITABLE:
        if k not in body:
            continue
        v = body[k]
        if k == "verdict" and v not in (None, "pass", "fail"):
            raise ValueError("verdict must be 'pass', 'fail' or null")
        if k == "score" and v is not None:
            v = int(v)
            if not 1 <= v <= 5:
                raise ValueError("score must be 1-5")
        if k == "tags":
            v = [str(t).strip() for t in (v or []) if str(t).strip()]
        out[k] = v
    return out


def create_eval(body: Dict[str, Any]) -> Dict[str, Any]:
    item = {
        "id": uuid.uuid4().hex[:12],
        "ts": time.time(),
        "session_id": body.get("session_id"),
        "message_id": body.get("message_id"),
        "turn_index": body.get("turn_index"),
        "model": body.get("model"),
        "prompt": body.get("prompt", ""),
        "response": body.get("response", ""),
        "verdict": None,
        "score": None,
        "tags": [],
        "notes": "",
        "expected": "",
        "comparisons": [],
    }
    item.update(_clean(body))
    with _LOCK:
        items = _read_all()
        # One eval per (session, message): saving again updates it instead of duplicating.
        for existing in items:
            if item["message_id"] and existing.get("message_id") == item["message_id"] and existing.get("session_id") == item["session_id"]:
                existing.update(_clean(body))
                existing["updated_ts"] = time.time()
                _write_all(items)
                return existing
        items.append(item)
        _write_all(items)
    return item


def update_eval(eval_id: str, body: Dict[str, Any]) -> Dict[str, Any]:
    with _LOCK:
        items = _read_all()
        for e in items:
            if e.get("id") == eval_id:
                e.update(_clean(body))
                e["updated_ts"] = time.time()
                _write_all(items)
                return e
    raise KeyError(eval_id)


def delete_eval(eval_id: str) -> None:
    with _LOCK:
        items = _read_all()
        kept = [e for e in items if e.get("id") != eval_id]
        if len(kept) == len(items):
            raise KeyError(eval_id)
        _write_all(kept)


def export_jsonl() -> str:
    return "".join(json.dumps(e, ensure_ascii=False) + "\n" for e in list_evals())


def stats() -> Dict[str, Any]:
    items = list_evals()
    judged = [i for i in items if i.get("verdict")]
    passed = [i for i in judged if i["verdict"] == "pass"]
    scores = [i["score"] for i in items if i.get("score")]
    return {
        "total": len(items),
        "judged": len(judged),
        "pass_rate": (len(passed) / len(judged)) if judged else None,
        "avg_score": (sum(scores) / len(scores)) if scores else None,
    }


# --------------------------------------------------------------------------- compare


def _load_dotenv_key(name: str) -> Optional[str]:
    if os.environ.get(name):
        return os.environ[name]
    env = hermes_home() / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = line.strip()
            if line.startswith(name + "="):
                return line.split("=", 1)[1].strip().strip("'\"")
    return None


def presets() -> List[Dict[str, Any]]:
    cfg = evals_dir() / "config.json"
    items = list(DEFAULT_PRESETS)
    if cfg.exists():
        try:
            items = json.loads(cfg.read_text(encoding="utf-8")).get("presets", items)
        except Exception:
            pass
    return [{**p, "has_key": bool(_load_dotenv_key(p.get("api_key_env", "")))} for p in items]


def compare(body: Dict[str, Any]) -> Dict[str, Any]:
    """Replay the same prompt against another OpenAI-compatible model."""
    prompt = body.get("prompt")
    if not prompt:
        raise ValueError("prompt is required")
    preset = next((p for p in presets() if p["label"] == body.get("preset")), None) or {}
    model = body.get("model") or preset.get("model")
    base_url = (body.get("base_url") or preset.get("base_url") or "").rstrip("/")
    key_env = body.get("api_key_env") or preset.get("api_key_env") or "OPENROUTER_API_KEY"
    if not model or not base_url:
        raise ValueError("choose a preset or give model + base_url")
    key = _load_dotenv_key(key_env)
    if not key:
        raise ValueError(f"{key_env} is not set (env or {hermes_home() / '.env'})")
    messages = []
    if body.get("system"):
        messages.append({"role": "system", "content": body["system"]})
    messages.append({"role": "user", "content": prompt})
    req = urllib.request.Request(
        f"{base_url}/chat/completions",
        data=json.dumps({"model": model, "messages": messages}).encode(),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        method="POST",
    )
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "ignore")[:300]
        raise RuntimeError(f"{model}: HTTP {e.code} {detail}") from None
    except urllib.error.URLError as e:
        raise RuntimeError(f"{model}: {e.reason}") from None
    text = (data.get("choices") or [{}])[0].get("message", {}).get("content", "")
    return {
        "model": model,
        "label": preset.get("label") or model,
        "response": text,
        "latency_ms": int((time.time() - t0) * 1000),
        "usage": data.get("usage"),
        "score": None,
    }


# --------------------------------------------------------------------------- dispatcher


def handle(method: str, path: str, query: Dict[str, str], body: Optional[Dict[str, Any]]) -> Tuple[int, Any]:
    """Route a request. Returns (status, json-serialisable object | ('text', str))."""
    path = "/" + path.strip("/")
    body = body or {}
    try:
        if method == "GET" and path == "/sessions":
            return 200, {"sessions": list_sessions(query.get("q", ""), int(query.get("limit", 50)))}
        if method == "GET" and path == "/latest":
            return 200, {"latest": latest_session()}
        if method == "GET" and path.startswith("/sessions/") and path.endswith("/turns"):
            return 200, get_turns(path[len("/sessions/") : -len("/turns")])
        if method == "GET" and path == "/evals":
            return 200, {"evals": list_evals(query.get("session_id", "")), "stats": stats()}
        if method == "POST" and path == "/evals":
            return 200, create_eval(body)
        if path.startswith("/evals/"):
            eid = path.split("/", 2)[2]
            if method == "PUT":
                return 200, update_eval(eid, body)
            if method == "DELETE":
                delete_eval(eid)
                return 200, {"ok": True}
        if method == "GET" and path == "/export":
            return 200, ("text", export_jsonl())
        if method == "GET" and path == "/presets":
            return 200, {"presets": presets()}
        if method == "POST" and path == "/compare":
            return 200, compare(body)
        return 404, {"error": f"no route {method} {path}"}
    except KeyError as e:
        return 404, {"error": f"not found: {e}"}
    except (ValueError, TypeError) as e:
        return 400, {"error": str(e)}
    except FileNotFoundError as e:
        return 500, {"error": str(e)}
    except RuntimeError as e:
        return 502, {"error": str(e)}
