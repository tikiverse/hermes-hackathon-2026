"""why: browser checks for the quick-eval page. Playwright is a dev dependency: a missing one fails, never skips."""
import sqlite3
import sys
import threading
import time
from pathlib import Path

import pytest
from playwright import sync_api

PLUGIN = Path(__file__).resolve().parent.parent / "plugins" / "quick-eval"
SEED = Path(__file__).resolve().parent / "quick_eval_ui_seed.sql"
sys.path.insert(0, str(PLUGIN))

import quickeval_log  # noqa: E402
import quickeval_schema as schema  # noqa: E402
import standalone  # noqa: E402

LONG_TITLE = "Newest chat about a topic far too long to fit on one small phone line"
HF_PATH = "/Users/x/.cache/huggingface/hub/models--org--Long-Model-4bit/snapshots/" + "0123456789abcdef" * 3
SESSIONS = (("newest", "m-new", LONG_TITLE, 60), ("older", HF_PATH, "Older chat", 3 * 86400))


SESSION_SQL = Path(__file__).resolve().parent / "quick_eval_ui_session.sql"


def add_session(conn, row, now):
    sid, model, title, age = row
    params = {"id": sid, "model": model, "title": title, "ts": now - age, "prompt": f"ask {sid}"}
    for statement in SESSION_SQL.read_text().split(";"):
        if statement.strip():
            conn.execute(statement, params)


def add_run(path):
    answers = [schema.answer("A", "m-new", "ok"), schema.answer("B", "m-rival", "better", latency_ms=900),
               schema.answer("C", HF_PATH, "local", latency_ms=9000)]
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
    page.fill(".ep-search", "long-model")
    sync_api.expect(rail_titles(page)).to_have_text(["Current chat", "Older chat"])


def test_mark_one_answer_good_and_leaderboard(page):
    assert page.locator(".ep-now .ep-cgrid .ep-col").count() == 3
    page.keyboard.press("b")
    assert page.locator(".ep-col.won").count() == 1
    page.click(".ep-bar .ep-btn.pri")
    page.wait_for_selector(".ep-toast:has-text('good: B')")
    assert [j["winner"] for j in judgments(page.evals_path)] == ["B"]
    page.click(".ep-head .ep-segb:has-text('Leaderboard')")
    page.wait_for_selector(".ep-table tbody tr")
    assert page.inner_text(".ep-table tbody tr:first-child td:first-child") == "m-rival"


def test_several_answers_can_be_good(page):
    page.click(".ep-cgrid .ep-col >> nth=1")
    page.click(".ep-cgrid .ep-col >> nth=2")
    assert page.locator(".ep-col.won").count() == 2
    page.click(".ep-bar .ep-btn.pri")
    page.wait_for_selector(".ep-toast:has-text('good: B C')")
    saved = judgments(page.evals_path)[-1]
    assert (saved["good"], saved["winner"]) == (["B", "C"], "tie")


def test_single_answer_turn_is_good_or_not(page):
    page.click(".ep-rail-list .ep-item:has-text('Older chat')")
    page.click(".ep-bar .ep-segb:has-text('Not good')")
    page.click(".ep-bar .ep-btn.pri")
    page.wait_for_selector(".ep-toast:has-text('good: none')")
    assert [(j["good"], j["winner"]) for j in judgments(page.evals_path)] == [([], "none")]


def test_no_null_text_anywhere(page):
    for tab in ("Review", "Leaderboard"):
        page.click(f".ep-head .ep-segb:has-text('{tab}')")
        page.wait_for_timeout(300)
        assert "null" not in page.inner_text(".quickeval")


DECK = '.ep-now.multi .ep-cgrid'  # why: the phone answer deck scrolls sideways on purpose
SIDEWAYS = (f"[...document.querySelectorAll('.quickeval *')].filter(e => !e.matches('{DECK}')"
            " && e.scrollWidth > e.clientWidth + 1"
            " && ['auto', 'scroll'].includes(getComputedStyle(e).overflowX)).map(e => e.className)")


def test_no_tab_scrolls_sideways_on_phone(page):
    page.set_viewport_size({"width": 390, "height": 844})
    for tab in ("Review", "Leaderboard"):
        page.click(f".ep-head .ep-segb:has-text('{tab}')")
        page.wait_for_timeout(300)
        assert page.evaluate(SIDEWAYS) == [], tab


def test_phone_picker_opens_and_closes(page):
    page.set_viewport_size({"width": 390, "height": 844})
    assert not page.is_visible(".ep-rail")
    page.click(".ep-railbtn")
    page.click(".ep-rail-list .ep-item:has-text('Older chat')")
    page.wait_for_selector(".ep-railbtn:has-text('Older chat')")
    assert not page.is_visible(".ep-rail")
    assert page.evaluate("document.documentElement.scrollWidth") <= 390
    assert page.evaluate("(s => s.scrollWidth - s.clientWidth)(document.querySelector('.ep-stage'))") <= 1
    assert page.is_visible(".ep-col-h b:has-text('Long-Model-4bit')")



def test_leaderboard_headers_never_break_inside_a_word_on_phone(page):
    page.set_viewport_size({"width": 320, "height": 640})
    page.click(".ep-head .ep-segb:has-text('Leaderboard')")
    page.wait_for_selector(".ep-table th")
    wraps = page.eval_on_selector_all(".ep-table th", "ths => ths.map(t => getComputedStyle(t).overflowWrap)")
    assert set(wraps) == {"normal"}


def test_chat_picker_button_is_phone_only(page):
    page.set_viewport_size({"width": 1440, "height": 900})
    assert not page.is_visible(".ep-railbtn")
    page.set_viewport_size({"width": 390, "height": 844})
    assert page.is_visible(".ep-railbtn")


def test_several_answers_sit_in_one_full_width_row_on_desktop(page):
    """why: Shaun: cards wrapped under each other with blank space left and right; scrolling to compare."""
    page.set_viewport_size({"width": 1440, "height": 900})
    tops = page.eval_on_selector_all(".ep-now .ep-col", "cs => cs.map(c => Math.round(c.getBoundingClientRect().top))")
    assert len(tops) == 3 and len(set(tops)) == 1
    stage = page.eval_on_selector(".ep-stage", "e => e.clientWidth - 48")
    now = page.eval_on_selector(".ep-now", "e => e.getBoundingClientRect().width")
    assert now >= stage
    height = page.eval_on_selector(".ep-stage", "e => e.clientHeight - 46")
    assert page.eval_on_selector(".ep-now", "e => e.getBoundingClientRect().height") >= height


def test_several_answers_are_a_swipe_deck_on_phone(page):
    """why: Shaun: stacked answers meant scrolling far down on an iPhone."""
    page.set_viewport_size({"width": 390, "height": 844})
    tops = page.eval_on_selector_all(".ep-now .ep-col", "cs => cs.map(c => Math.round(c.getBoundingClientRect().top))")
    assert len(set(tops)) == 1
    assert page.eval_on_selector(".ep-now .ep-cgrid", "g => getComputedStyle(g).scrollSnapType").startswith("x")


def test_marking_a_card_keeps_the_phone_deck_on_that_card(page):
    """why: Shaun: tapping card 2+ jumped the deck back to card A."""
    page.set_viewport_size({"width": 390, "height": 844})
    page.eval_on_selector(".ep-now .ep-col >> nth=2", "c => c.scrollIntoView({inline: 'center'})")
    page.wait_for_timeout(300)
    before = page.eval_on_selector(".ep-now .ep-cgrid", "g => g.scrollLeft")
    page.click(".ep-now .ep-col >> nth=2")
    assert before > 0
    assert page.eval_on_selector(".ep-now .ep-cgrid", "g => g.scrollLeft") == before
    assert page.locator(".ep-col.won").count() == 1
