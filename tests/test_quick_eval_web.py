"""quick-eval web side: log schema, append-only log, reports, HTTP routes."""
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

@pytest.fixture(autouse=True)
def state(tmp_path, monkeypatch):
    monkeypatch.setenv("QUICKEVAL_DIR", str(tmp_path / "evals"))
    monkeypatch.setenv("QUICKEVAL_STATE_DB", str(tmp_path / "state.db"))
    conn = sqlite3.connect(tmp_path / "state.db")
    conn.executescript(SEED.read_text())
    conn.commit()
    conn.close()


def two_model_run(prompt="hi", ts=None, models=("m0", "m1")):
    answers = [schema.answer("A", models[0], "x")]
    answers += [schema.answer(chr(ord("B") + i), m, "y", latency_ms=200) for i, m in enumerate(models[1:])]
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
    first = reports.save_judgment({**body, "good": ["A"]})
    second = reports.save_judgment({**body, "note": "ok"})
    assert first["id"] == second["id"]
    assert second["judgment"]["good"] == ["A"]
    assert second["judgment"]["note"] == "ok"
    types = [json.loads(line)["type"] for line in reports.log().raw().splitlines()]
    assert types == ["run", "judgment", "judgment"]
    assert sessions.list_sessions()[0]["eval_count"] == 1


def test_validation():
    run = two_model_run()
    with pytest.raises(ValueError):
        reports.save_judgment({"run_id": run["id"], "winner": "Z"})
    with pytest.raises(ValueError):
        reports.save_judgment({"prompt": ""})


def test_winner_kept_unless_sent():
    run = two_model_run()
    reports.save_judgment({"run_id": run["id"], "winner": "B"})
    kept = reports.save_judgment({"run_id": run["id"], "note": "close call"})
    assert (kept["judgment"]["winner"], kept["judgment"]["note"]) == ("B", "close call")
    cleared = reports.save_judgment({"run_id": run["id"], "winner": None})
    assert cleared["judgment"]["winner"] is None
    assert cleared["judgment"]["note"] == "close call"


def test_torn_line_tolerated():
    two_model_run()
    with reports.log().path.open("a") as handle:
        handle.write('{"broken\n')
    assert len(reports.list_runs({})) == 1


def test_unknown_line_types_ignored():
    write_lines({"type": "grade", "prompt": "old"}, {"no": "type"})
    two_model_run()
    assert len(reports.list_runs({})) == 1


def test_filters():
    two_model_run("cats", ts=1)
    two_model_run("dogs", models=("m0", "m2"))
    reports.log().append(schema.run_record("solo", [schema.answer("A", "m0", "x")], session_id="s1"))
    prompts = [r["prompt"] for r in reports.list_runs({"multi": "1"})]
    assert prompts == ["dogs", "cats"]
    assert [r["prompt"] for r in reports.list_runs({"since": "3600", "multi": "1"})] == ["dogs"]
    assert [r["prompt"] for r in reports.list_runs({"q": "m2"})] == ["dogs"]
    assert [r["prompt"] for r in reports.list_runs({"q": "CAT"})] == ["cats"]


def test_leaderboard_counts_good_answers_and_sole_wins():
    first, second = two_model_run("a"), two_model_run("b")
    two_model_run("unjudged")
    reports.save_judgment({"run_id": first["id"], "winner": "B"})
    reports.save_judgment({"run_id": second["id"], "winner": "tie"})
    rows = {r["model"]: r for r in reports.leaderboard({})}
    assert rows["m1"] == {"model": "m1", "answers": 3, "judged": 2, "good": 2, "wins": 1, "good_rate": 1.0}
    assert (rows["m0"]["good"], rows["m0"]["wins"], rows["m0"]["good_rate"]) == (1, 0, 0.5)
    assert reports.leaderboard({})[0]["model"] == "m1"


def test_several_answers_can_be_good():
    run = two_model_run("x", models=("m0", "m1", "m2"))
    saved = reports.save_judgment({"run_id": run["id"], "good": ["C", "A"]})
    assert (saved["judgment"]["good"], saved["judgment"]["winner"]) == (["A", "C"], "tie")
    one = reports.save_judgment({"run_id": run["id"], "good": ["B"]})
    assert one["judgment"]["winner"] == "B"
    assert reports.save_judgment({"run_id": run["id"], "good": []})["judgment"]["winner"] == "none"
    with pytest.raises(ValueError):
        reports.save_judgment({"run_id": run["id"], "good": ["Z"]})


def test_a_judgment_from_before_good_existed_still_counts():
    run = two_model_run("old")
    reports.log().append({"v": 1, "type": "judgment", "id": "j_old", "ts": 2, "run_id": run["id"], "winner": "B",
                          "verdict": None, "note": "", "expected": ""})
    rows = {r["model"]: r for r in reports.leaderboard({})}
    assert (rows["m1"]["good"], rows["m0"]["good"]) == (1, 0)
    assert reports.list_runs({})[0]["judgment"]["good"] == ["B"]


def test_an_old_pass_fail_verdict_reads_as_good():
    solo = reports.log().append(schema.run_record("solo", [schema.answer("A", "m0", "x")]))
    reports.log().append({"v": 1, "type": "judgment", "id": "j_v", "ts": 2, "run_id": solo["id"], "winner": None,
                          "verdict": "pass", "note": "", "expected": ""})
    assert reports.list_runs({})[0]["judgment"]["good"] == ["A"]


def test_stats():
    run = two_model_run()
    two_model_run()
    reports.save_judgment({"run_id": run["id"], "winner": "A"})
    assert reports.stats() == {"runs": 2, "judged": 1}


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
