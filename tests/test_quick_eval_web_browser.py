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


def test_compare_pick_winner_and_leaderboard(page):
    page.click(".ep-link:has-text('Compare 3 answers')")
    page.wait_for_selector(".ep-cgrid .ep-col")
    assert page.locator(".ep-cgrid .ep-col").count() == 3
    page.keyboard.press("b")
    assert page.locator(".ep-col.won").count() == 1
    page.click(".ep-bar .ep-btn.pri")
    page.wait_for_selector(".ep-rail-list .ep-label:has-text('B')")
    assert [j["winner"] for j in judgments(page.evals_path)] == ["B"]
    page.click(".ep-head .ep-segb:has-text('Leaderboard')")
    page.wait_for_selector(".ep-table tbody tr")
    assert page.inner_text(".ep-table tbody tr:first-child td:first-child") == "m-rival"


def test_compare_marks_several_answers_good(page):
    page.click(".ep-link:has-text('Compare 3 answers')")
    page.wait_for_selector(".ep-cgrid .ep-col")
    page.click(".ep-cgrid .ep-col >> nth=1")
    page.click(".ep-cgrid .ep-col >> nth=2")
    assert page.locator(".ep-col.won").count() == 2
    page.click(".ep-bar .ep-btn.pri")
    page.wait_for_selector(".ep-rail-list .ep-label:has-text('B C')")
    saved = judgments(page.evals_path)[-1]
    assert (saved["good"], saved["winner"]) == (["B", "C"], "tie")
    page.click(".ep-head .ep-segb:has-text('Leaderboard')")
    page.wait_for_selector(".ep-table tbody tr")
    assert "Good %" in page.text_content(".ep-table thead")


def test_review_verdict_saves_a_judgment(page):
    page.keyboard.press("p")
    page.click(".ep-bar .ep-btn.pri")
    page.wait_for_selector(".ep-toast.on")
    assert [j["verdict"] for j in judgments(page.evals_path)] == ["pass"]


def test_no_null_text_anywhere(page):
    for tab in ("Review", "Compare", "Leaderboard"):
        page.click(f".ep-head .ep-segb:has-text('{tab}')")
        page.wait_for_timeout(300)
        assert "null" not in page.inner_text(".quickeval")


SIDEWAYS = "[...document.querySelectorAll('.quickeval *')].filter(e => e.scrollWidth > e.clientWidth + 1"
SIDEWAYS += " && ['auto', 'scroll'].includes(getComputedStyle(e).overflowX)).map(e => e.className)"


def test_no_tab_scrolls_sideways_on_phone(page):
    page.set_viewport_size({"width": 390, "height": 844})
    for tab in ("Review", "Compare", "Leaderboard"):
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
    assert page.is_visible(".ep-who b:has-text('Long-Model-4bit')")



def test_leaderboard_headers_never_break_inside_a_word_on_phone(page):
    page.set_viewport_size({"width": 320, "height": 640})
    page.click(".ep-head .ep-segb:has-text('Leaderboard')")
    page.wait_for_selector(".ep-table th")
    wraps = page.eval_on_selector_all(".ep-table th", "ths => ths.map(t => getComputedStyle(t).overflowWrap)")
    assert set(wraps) == {"normal"}


DESKTOP_PARENT = """async () => {
  const html = (await (await fetch('/api/frame')).json()).html
  const frame = document.createElement('iframe')
  frame.setAttribute('sandbox', 'allow-scripts')
  frame.style.cssText = 'width:100%;height:100vh;border:0'
  frame.src = 'data:text/html;charset=utf-8;base64,' + btoa(unescape(encodeURIComponent(html)))
  window.addEventListener('message', async (e) => {
    const m = e.data
    if (!m || m.type !== 'quickeval-rpc' || e.source !== frame.contentWindow) return
    const init = m.method === 'GET' ? {} : {method: m.method, headers: {'Content-Type': 'application/json'},
                                             body: JSON.stringify(m.body)}
    const r = await fetch('/api' + m.path, init)
    e.source.postMessage({type: 'quickeval-rpc-reply', id: m.id, ok: r.ok, data: await r.json()}, '*')
  })
  document.body.replaceChildren(frame)
}"""


def test_desktop_frame_works_through_the_parent_bridge(page):
    """why: Hermes Desktop runs the UI in a sandboxed data: frame; every call must go through postMessage."""
    page.evaluate(DESKTOP_PARENT)
    frame = page.frame_locator("iframe")
    frame.locator(".ep-head .ep-segb:has-text('Compare')").click()
    frame.locator(".ep-cgrid .ep-col").nth(1).click()
    frame.locator(".ep-bar .ep-btn.pri").click()
    frame.locator(".ep-rail-list .ep-label:has-text('B')").wait_for()
    assert judgments(page.evals_path)[-1]["good"] == ["B"]
    assert frame.locator("a:has-text('Export JSONL')").count() == 0
