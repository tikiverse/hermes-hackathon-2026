"""quick-eval web side: v1 schema, append-only log, reports, HTTP routes, legacy lines."""
import json
import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent / "plugins" / "quick-eval"
SEED = Path(__file__).resolve().parent / "quick_eval_ui_seed.sql"
sys.path.insert(0, str(ROOT))

import quickeval_reports as reports  # noqa: E402
import quickeval_routes as routes  # noqa: E402
import quickeval_schema as schema  # noqa: E402
import quickeval_sessions as sessions  # noqa: E402

LEGACY_EVAL = {"type": "eval", "id": "abc12345", "ts": 1, "session_id": "s1", "prompt": "hi",
               "answers": [{"label": "A", "source": "original", "model": "m0", "text": "x"},
                           {"label": "B", "source": "rerun", "model": "m1", "text": "y"}]}
LEGACY_SCORE = {"type": "score", "eval_id": "abc12345", "ts": 2, "winner": "B", "note": "old"}
LEGACY_GRADE = {"id": "g1", "ts": 3, "session_id": "s1", "message_id": 1, "prompt": "2+2?", "response": "4",
                "model": "m0", "verdict": "pass", "score": 5, "tags": ["great"], "notes": "fine"}


@pytest.fixture(autouse=True)
def state(tmp_path, monkeypatch):
    monkeypatch.setenv("QUICKEVAL_DIR", str(tmp_path / "evals"))
    monkeypatch.setenv("QUICKEVAL_STATE_DB", str(tmp_path / "state.db"))
    conn = sqlite3.connect(tmp_path / "state.db")
    conn.executescript(SEED.read_text())
    conn.commit()
    conn.close()


def two_model_run(prompt="hi", ts=None, models=("m0", "m1")):
    answers = [schema.answer("A", "original", models[0], "x"),
               schema.answer("B", "rerun", models[1], "y", latency_ms=200, cost_usd=0.01)]
    record = schema.run_record(prompt, answers, session_id="s1")
    return reports.log().append({**record, "ts": ts or record["ts"]})


def write_lines(*lines):
    reports.log().path.write_text("".join(json.dumps(line) + "\n" for line in lines))


def test_sessions_listed():
    assert [s["id"] for s in sessions.list_sessions()] == ["s1"]


def test_turns_group_tools():
    turns = sessions.get_turns("s1")["turns"]
    assert [t["response"] for t in turns] == ["4", "Found 3 hits."]
    call = turns[1]["tools"][0]
    assert (call["name"], call["arguments"], call["result"]) == ("web_search", {"q": "cats"}, {"hits": 3})


def test_grading_a_chat_turn_makes_one_run_and_appends_judgments():
    turn = sessions.get_turns("s1")["turns"][0]
    body = {"session_id": "s1", "message_id": turn["message_id"], "prompt": turn["prompt"], "response": "4",
            "model": "m0"}
    first = reports.save_judgment({**body, "scores": {"A": {"verdict": "pass", "score": 5, "tags": ["great"]}}})
    second = reports.save_judgment({**body, "note": "ok"})
    assert first["id"] == second["id"]
    assert second["judgment"]["scores"]["A"]["verdict"] == "pass"
    assert second["judgment"]["note"] == "ok"
    types = [json.loads(line)["type"] for line in reports.log().raw().splitlines()]
    assert types == ["run", "judgment", "judgment"]
    assert sessions.list_sessions()[0]["eval_count"] == 1


def test_validation():
    run = two_model_run()
    with pytest.raises(ValueError):
        reports.save_judgment({"run_id": run["id"], "scores": {"A": {"score": 9}}})
    with pytest.raises(ValueError):
        reports.save_judgment({"run_id": run["id"], "scores": {"A": {"verdict": "maybe"}}})
    with pytest.raises(ValueError):
        reports.save_judgment({"run_id": run["id"], "winner": "Z"})
    with pytest.raises(ValueError):
        reports.save_judgment({"run_id": run["id"], "scores": {"Q": {"score": 3}}})
    with pytest.raises(ValueError):
        reports.save_judgment({"prompt": ""})


def test_winner_kept_unless_sent():
    run = two_model_run()
    reports.save_judgment({"run_id": run["id"], "winner": "B"})
    kept = reports.save_judgment({"run_id": run["id"], "scores": {"A": {"score": 2}}})
    assert kept["judgment"]["winner"] == "B"
    cleared = reports.save_judgment({"run_id": run["id"], "winner": None})
    assert cleared["judgment"]["winner"] is None
    assert cleared["judgment"]["scores"]["A"]["score"] == 2


def test_torn_line_tolerated():
    two_model_run()
    with reports.log().path.open("a") as handle:
        handle.write('{"broken\n')
    assert len(reports.list_runs({})) == 1


def test_legacy_lines_read_as_v1():
    write_lines(LEGACY_EVAL, LEGACY_SCORE, LEGACY_GRADE)
    runs = {r["id"]: r for r in reports.list_runs({})}
    old_eval = runs["abc12345"]
    assert [a["role"] for a in old_eval["answers"]] == ["original", "rerun"]
    assert (old_eval["judgment"]["winner"], old_eval["judgment"]["note"]) == ("B", "old")
    grade = runs["r_g1"]
    assert grade["answers"][0]["text"] == "4"
    assert grade["judgment"]["scores"]["A"] == {"score": 5, "verdict": "pass", "tags": ["great"]}


def test_filters():
    two_model_run("cats", ts=1)
    two_model_run("dogs", models=("m0", "m2"))
    reports.log().append(schema.run_record("solo", [schema.answer("A", "original", "m0", "x")], session_id="s1"))
    prompts = [r["prompt"] for r in reports.list_runs({"multi": "1"})]
    assert prompts == ["dogs", "cats"]
    assert [r["prompt"] for r in reports.list_runs({"since": "3600", "multi": "1"})] == ["dogs"]
    assert [r["prompt"] for r in reports.list_runs({"model": "m2"})] == ["dogs"]
    assert [r["prompt"] for r in reports.list_runs({"q": "CAT"})] == ["cats"]


def test_leaderboard_counts_wins_only_in_contests():
    first, second = two_model_run("a"), two_model_run("b")
    reports.save_judgment({"run_id": first["id"], "winner": "B", "scores": {"B": {"score": 4}}})
    reports.save_judgment({"run_id": second["id"], "winner": "tie"})
    rows = {r["model"]: r for r in reports.leaderboard({})}
    assert (rows["m1"]["wins"], rows["m1"]["contests"], rows["m1"]["win_rate"]) == (1, 2, 0.5)
    assert (rows["m0"]["wins"], rows["m0"]["ties"], rows["m0"]["win_rate"]) == (0, 1, 0.0)
    assert rows["m1"]["avg_score"] == 4
    assert (rows["m1"]["avg_latency_ms"], rows["m1"]["cost_usd"]) == (200, 0.02)
    assert reports.leaderboard({})[0]["model"] == "m1"


def test_stats():
    run = two_model_run()
    reports.save_judgment({"run_id": run["id"], "scores": {"A": {"verdict": "pass", "score": 4},
                                                           "B": {"verdict": "fail", "score": 2}}})
    assert reports.stats() == {"runs": 1, "judged": 1, "pass_rate": 0.5, "avg_score": 3}


def test_routes():
    run = two_model_run()
    status, body = routes.handle("GET", "/sessions/s1/turns", {}, None)
    assert (status, len(body["turns"])) == (200, 2)
    assert routes.handle("GET", "/sessions/nope/turns", {}, None)[0] == 404
    assert routes.handle("GET", "/nothing", {}, None)[0] == 404
    assert routes.handle("POST", "/judgments", {}, {"run_id": "missing"})[0] == 404
    assert routes.handle("POST", "/judgments", {}, {"run_id": run["id"], "winner": "Z"})[0] == 400
    status, saved = routes.handle("POST", "/judgments", {}, {"run_id": run["id"], "winner": "B"})
    assert (status, saved["judgment"]["winner"]) == (200, "B")
    assert routes.handle("GET", "/runs", {"multi": "1"}, None)[1]["runs"][0]["judgment"]["winner"] == "B"
    assert routes.handle("GET", "/leaderboard", {}, None)[1]["rows"][0]["model"] == "m1"
    kind, text = routes.handle("GET", "/export", {}, None)[1]
    assert kind == "text" and '"type": "judgment"' in text
