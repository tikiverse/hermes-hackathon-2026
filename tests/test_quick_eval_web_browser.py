"""why: browser checks for the quick-eval page; runs with `uv run --with playwright pytest`, skips otherwise."""
import sqlite3
import sys
import threading
import time
from pathlib import Path

import pytest

sync_api = pytest.importorskip("playwright.sync_api")

PLUGIN = Path(__file__).resolve().parent.parent / "plugins" / "quick-eval"
SEED = Path(__file__).resolve().parent / "quick_eval_ui_seed.sql"
sys.path.insert(0, str(PLUGIN))

import quickeval_log  # noqa: E402
import quickeval_schema as schema  # noqa: E402
import standalone  # noqa: E402

SESSIONS = (("newest", "m-new", "Newest chat", 60), ("older", "m-old", "Older chat", 3 * 86400))


SESSION_SQL = Path(__file__).resolve().parent / "quick_eval_ui_session.sql"


def add_session(conn, row, now):
    sid, model, title, age = row
    params = {"id": sid, "model": model, "title": title, "ts": now - age, "prompt": f"ask {sid}"}
    for statement in SESSION_SQL.read_text().split(";"):
        if statement.strip():
            conn.execute(statement, params)


def add_run(path):
    answers = [schema.answer("A", "m-new", "ok"), schema.answer("B", "m-rival", "better", latency_ms=900)]
    quickeval_log.EvalLog(path).append(schema.run_record("ask newest", answers, session_id="newest"))


def judgments(page_path):
    return quickeval_log.EvalLog(page_path).records("judgment")


def seed(db):
    conn = sqlite3.connect(db)
    conn.executescript(SEED.read_text())
    now = time.time()
    for row in SESSIONS:
        add_session(conn, row, now)
    conn.commit()
    conn.close()


@pytest.fixture
def page(tmp_path, monkeypatch):
    seed(tmp_path / "state.db")
    monkeypatch.setenv("QUICKEVAL_STATE_DB", str(tmp_path / "state.db"))
    monkeypatch.setenv("QUICKEVAL_DIR", str(tmp_path / "evals"))
    add_run(tmp_path / "evals" / "evals.jsonl")
    server = standalone.serve(0)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    with sync_api.sync_playwright() as pw:
        browser = pw.chromium.launch()
        tab = browser.new_page()
        tab.goto(f"http://127.0.0.1:{server.server_address[1]}/")
        tab.wait_for_selector(".ep-now")
        tab.evals_path = tmp_path / "evals" / "evals.jsonl"
        yield tab
        browser.close()
    server.shutdown()


def rail_titles(page):
    return page.locator(".ep-rail-list .ep-item .ep-item-t")


def test_current_chat_pinned_and_picked_chat_survives_poll(page):
    sync_api.expect(rail_titles(page).first).to_have_text("Current chat")
    page.click(".ep-rail-list .ep-item:has-text('Older chat')")
    page.wait_for_timeout(7000)
    assert page.locator(".ep-item.on").inner_text().startswith("Older chat")


def test_rail_filters_narrow_the_chat_list(page):
    page.click(".ep-rail .ep-segb:has-text('Day')")
    sync_api.expect(rail_titles(page)).to_have_text(["Current chat"])
    page.click(".ep-rail .ep-segb:has-text('All')")
    page.fill(".ep-search", "m-old")
    sync_api.expect(rail_titles(page)).to_have_text(["Current chat", "Older chat"])


def test_compare_pick_winner_and_leaderboard(page):
    page.click(".ep-link:has-text('Compare 2 answers')")
    page.wait_for_selector(".ep-cgrid .ep-col")
    assert page.locator(".ep-cgrid .ep-col").count() == 2
    page.keyboard.press("b")
    assert page.locator(".ep-col.won").count() == 1
    page.click(".ep-bar .ep-btn.pri")
    page.wait_for_selector(".ep-rail-list .ep-label:has-text('B')")
    assert [j["winner"] for j in judgments(page.evals_path)] == ["B"]
    page.click(".ep-head .ep-segb:has-text('Leaderboard')")
    page.wait_for_selector(".ep-table tbody tr")
    assert page.inner_text(".ep-table tbody tr:first-child td:first-child") == "m-rival"


def test_review_verdict_saves_a_judgment(page):
    page.keyboard.press("p")
    page.click(".ep-bar .ep-btn.pri")
    page.wait_for_selector(".ep-toast.on")
    assert [j["verdict"] for j in judgments(page.evals_path)] == ["pass"]


def test_blind_mode_hides_models_until_judged(page):
    page.click(".ep-head .ep-segb:has-text('Compare')")
    page.wait_for_selector(".ep-cgrid .ep-col")
    page.check(".ep-prompt .ep-check input")
    assert page.inner_text(".ep-cgrid .ep-col:nth-child(2) .ep-col-h b") == "Model B"


def test_no_null_text_anywhere(page):
    for tab in ("Review", "Compare", "Leaderboard"):
        page.click(f".ep-head .ep-segb:has-text('{tab}')")
        page.wait_for_timeout(300)
        assert "null" not in page.inner_text(".quickeval")
