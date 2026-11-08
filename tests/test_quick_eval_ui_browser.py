"""why: browser checks for the quick-eval-ui page; runs with `uv run --with playwright pytest`, skips otherwise."""
import sqlite3
import sys
import threading
import time
from pathlib import Path

import pytest

sync_api = pytest.importorskip("playwright.sync_api")

PLUGIN = Path(__file__).resolve().parent.parent / "plugins" / "quick-eval-ui"
SEED = Path(__file__).resolve().parent / "quick_eval_ui_seed.sql"
sys.path.insert(0, str(PLUGIN))

import standalone  # noqa: E402

SESSIONS = (("newest", "m-new", "Newest chat", 60), ("older", "m-old", "Older chat", 3 * 86400))


SESSION_SQL = Path(__file__).resolve().parent / "quick_eval_ui_session.sql"


def add_session(conn, row, now):
    sid, model, title, age = row
    params = {"id": sid, "model": model, "title": title, "ts": now - age, "prompt": f"ask {sid}"}
    for statement in SESSION_SQL.read_text().split(";"):
        if statement.strip():
            conn.execute(statement, params)


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
    server = standalone.serve(0)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    with sync_api.sync_playwright() as pw:
        browser = pw.chromium.launch()
        tab = browser.new_page()
        tab.goto(f"http://127.0.0.1:{server.server_address[1]}/")
        tab.wait_for_selector(".ep-now")
        yield tab
        browser.close()
    server.shutdown()


def test_picked_session_survives_live_poll(page):
    page.select_option(".ep-session", "older")
    page.wait_for_timeout(7000)
    assert page.input_value(".ep-session") == "older"
    assert not page.is_checked(".ep-live input")


def test_filters_narrow_session_list(page):
    page.click(".ep-filters .ep-segb:has-text('Day')")
    assert page.locator(".ep-session option").count() == 1
    page.click(".ep-filters .ep-segb:has-text('All time')")
    page.select_option(".ep-filters select", "m-old")
    assert "1 of" in page.inner_text(".ep-count")
    page.select_option(".ep-filters select", "")
    page.fill(".ep-search", "older")
    assert "1 of" in page.inner_text(".ep-count")


def test_selected_turn_has_no_accent_bar(page):
    shadow = page.eval_on_selector(".ep-turn.on", "el => getComputedStyle(el).boxShadow")
    assert shadow == "none"
