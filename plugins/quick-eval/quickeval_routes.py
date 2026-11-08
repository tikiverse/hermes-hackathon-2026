"""why: one dispatcher serves both the Hermes dashboard router and the standalone server."""
import quickeval_reports as reports
import quickeval_sessions as sessions


def get_sessions(parts, query, _body):
    if len(parts) == 1:
        return {"sessions": sessions.list_sessions(query.get("q", ""), int(query.get("limit", 50)))}
    if len(parts) == 3 and parts[2] == "turns":
        return sessions.get_turns(parts[1])
    raise KeyError("/".join(parts))


def get_latest(_parts, _query, _body):
    return {"latest": sessions.latest_session()}


def get_runs(_parts, query, _body):
    return {"runs": reports.list_runs(query)}


def post_judgment(_parts, _query, body):
    return reports.save_judgment(body)


def get_stats(_parts, _query, _body):
    return reports.stats()


def get_leaderboard(_parts, query, _body):
    return {"rows": reports.leaderboard(query)}


def get_export(_parts, _query, _body):
    return ("text", reports.log().raw())


ROUTES = {
    ("GET", "sessions"): get_sessions, ("GET", "latest"): get_latest, ("GET", "runs"): get_runs,
    ("POST", "judgments"): post_judgment, ("GET", "stats"): get_stats, ("GET", "leaderboard"): get_leaderboard,
    ("GET", "export"): get_export,
}
STATUS = ((KeyError, 404), (ValueError, 400), (TypeError, 400), (FileNotFoundError, 500))
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
