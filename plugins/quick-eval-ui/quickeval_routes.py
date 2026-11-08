"""why: one dispatcher serves both the Hermes dashboard router and the standalone server."""
import quickeval_compare as compare
import quickeval_sessions as sessions
import quickeval_store as store


def get_sessions(parts, query, _body):
    if len(parts) == 1:
        return {"sessions": sessions.list_sessions(query.get("q", ""), int(query.get("limit", 50)))}
    if len(parts) == 3 and parts[2] == "turns":
        return sessions.get_turns(parts[1])
    raise KeyError("/".join(parts))


def get_latest(_parts, _query, _body):
    return {"latest": sessions.latest_session()}


def get_evals(_parts, query, _body):
    return {"evals": store.list_evals(query.get("session_id", "")), "stats": store.stats()}


def post_eval(_parts, _query, body):
    return store.create_eval(body)


def put_eval(parts, _query, body):
    return store.update_eval(parts[1], body)


def delete_eval(parts, _query, _body):
    store.delete_eval(parts[1])
    return {"ok": True}


def get_export(_parts, _query, _body):
    return ("text", store.export_jsonl())


def get_presets(_parts, _query, _body):
    return {"presets": compare.presets()}


def post_compare(_parts, _query, body):
    return compare.compare(body)


def get_runs(_parts, query, _body):
    return {"runs": store.list_runs(query.get("session_id", ""))}


def post_score(_parts, _query, body):
    return store.add_score(body)


ROUTES = {
    ("GET", "sessions"): get_sessions, ("GET", "latest"): get_latest, ("GET", "evals"): get_evals,
    ("POST", "evals"): post_eval, ("PUT", "evals"): put_eval, ("DELETE", "evals"): delete_eval,
    ("GET", "export"): get_export, ("GET", "presets"): get_presets, ("POST", "compare"): post_compare,
    ("GET", "runs"): get_runs, ("POST", "scores"): post_score,
}
STATUS = ((KeyError, 404), (ValueError, 400), (TypeError, 400), (FileNotFoundError, 500), (RuntimeError, 502))
HANDLED = tuple(kind for kind, _ in STATUS)


def status_for(err):
    return next(code for kind, code in STATUS if isinstance(err, kind))


def message_for(err):
    return f"not found: {err.args[0]}" if isinstance(err, KeyError) and err.args else str(err)


def handle(method, path, query, body):
    """why: returns (status, payload); payload is ('text', str) for the JSONL export."""
    parts = [part for part in path.strip("/").split("/") if part]
    route = ROUTES.get((method, parts[0] if parts else ""))
    try:
        if route is None:
            raise KeyError(f"route {method} {path}")
        return 200, route(parts, query, body or {})
    except HANDLED as err:
        return status_for(err), {"error": message_for(err)}
