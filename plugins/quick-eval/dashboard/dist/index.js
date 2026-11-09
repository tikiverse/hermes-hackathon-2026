/* why: quick-eval UI, framework-free. Review a chat turn and its /eval answers, see which model wins. */
"use strict"

const TABS = { review: "Review", board: "Leaderboard" }
const RAIL_CHARS = 30 /* why: rail is 280px; a longer label gets cut mid-glyph by CSS */
const AGO_STEPS = [
  { lt: 3600, div: 60, suffix: "m ago" },
  { lt: 86400, div: 3600, suffix: "h ago" },
  { lt: Infinity, div: 86400, suffix: "d ago" },
]
const RANGES = {
  hour: { label: "Hour", secs: 3600 }, day: { label: "Day", secs: 86400 },
  week: { label: "Week", secs: 604800 }, all: { label: "All", secs: Infinity },
}
const SETTERS = { class: setClass, text: setText, value: setValue }
const EP = freshState()

function freshState() {
  return {
    root: null, api: "", fetchJSON: null, els: {}, tab: "review", range: "all", q: "", stats: {}, toast: "",
    toastTimer: null, pollTimer: null, sessions: [], sessionId: null, live: true, session: null, turns: [], sel: 0,
    runs: [], draft: emptyDraft(), dirty: false, lastMsgCount: 0, board: [],
  }
}

function emptyDraft() { return { good: null, note: "", expected: "" } }
function pick(a, b) { return a || b }
function ignore() { return undefined }
function noJson() { return {} }
function sameId(id, s) { return s.id === id }
function isKid(k) { return k != null && k !== false }
function toNode(k) { return k.nodeType ? k : document.createTextNode(String(k)) }
function skipProp(v) { return v == null || v === false }
function setClass(el, k, v) { el.className = v }
function setText(el, k, v) { el.textContent = v }
function setValue(el, k, v) { el.value = v }
function setAttr(el, k, v) { el.setAttribute(k, v === true ? "" : v) }
function onClass(flag) { return flag ? " on" : "" }

function applyProp(el, entry) {
  const [k, v] = entry
  if (skipProp(v)) return
  if (k.startsWith("on")) { el.addEventListener(k.slice(2), v); return }
  const setter = SETTERS[k] || setAttr
  setter(el, k, v)
}

function h(tag, props, ...kids) {
  const el = document.createElement(tag)
  Object.entries(props || {}).forEach(applyProp.bind(null, el))
  el.append(...kids.flat(3).filter(isKid).map(toNode))
  return el
}

/* why: replaceChildren turns a null kid into the text "null"; optional parts return null */
function fill(el, ...kids) { el.replaceChildren(...kids.flat(3).filter(isKid)) }

function findStep(s, step) { return s < step.lt }

function ago(ts) {
  if (!ts) return ""
  const s = Math.max(0, Date.now() / 1000 - ts)
  if (s < 60) return "just now"
  const step = AGO_STEPS.find(findStep.bind(null, s))
  return Math.floor(s / step.div) + step.suffix
}

function clip(s, n) {
  const t = s || ""
  return t.length > n ? t.slice(0, n - 1) + "…" : t
}

function oneLine(s) { return (s || "").replace(/\s+/g, " ").trim() }
function pct(x) { return x == null ? "–" : Math.round(x * 100) + "%" }
function secs(ms) { return ms == null ? null : (ms / 1000).toFixed(1) + " s" }
function kbd(key) { return h("kbd", { text: key }) }
function grow() { return h("span", { class: "ep-grow" }) }

async function call(path, init) {
  if (EP.fetchJSON) return EP.fetchJSON(EP.api + path, init)
  const r = await fetch(EP.api + path, init)
  const j = await r.json().catch(noJson)
  if (!r.ok) throw new Error(j.error || r.statusText)
  return j
}

function send(path, body) {
  return call(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) })
}

function renderToast() {
  EP.els.toast.textContent = EP.toast
  EP.els.toast.classList.toggle("on", !!EP.toast)
}

function clearToast() { EP.toast = ""; renderToast() }

function toast(message) {
  EP.toast = message
  renderToast()
  clearTimeout(EP.toastTimer)
  EP.toastTimer = setTimeout(clearToast, 2200)
}

function fail(e) { toast("⚠ " + pick(e.message, e)) }

function swap(selector, node) {
  const old = EP.els.body.querySelector(selector)
  if (old) old.replaceWith(node)
}

/* why: header: brand, tabs, export. Filters live on the rail they filter. */

function setTab(t) {
  EP.tab = t
  reloadTab().then(render).catch(fail)
}

function tabButton(t) {
  return h("button", { class: "ep-segb" + onClass(EP.tab === t), onclick: setTab.bind(null, t) }, TABS[t])
}

function renderHead() {
  const meta = `${pick(EP.stats.judged, 0)}/${pick(EP.stats.runs, 0)} judged`
  fill(EP.els.head, h("span", { class: "ep-brand", text: "Quick Eval" }), grow(), h("span", { class: "ep-meta", text: meta }),
    h("div", { class: "ep-seg ep-tabs" }, Object.keys(TABS).map(tabButton)),
    h("a", { class: "ep-btn ep-wide", href: EP.api + "/export", download: "evals.jsonl", text: "Export JSONL" }), railButton())
}

/* why: on a phone the rail is a full-screen picker opened from this button; on desktop the button is hidden */
const RAIL_LABELS = { review: currentChatLabel }

function currentChatLabel() {
  const s = EP.sessions.find(sameId.bind(null, EP.sessionId))
  return (EP.live ? "Current chat · " : "") + (s ? sessionTitle(s) : "Pick a chat")
}

function railButton() {
  const label = RAIL_LABELS[EP.tab]
  if (!label) return null
  return h("button", { class: "ep-btn ep-railbtn", onclick: toggleRail, "aria-label": "Show list" },
    h("span", { class: "ep-railbtn-t", text: label() }), h("span", { class: "ep-chev", text: "▾" }))
}

function toggleRail() {
  const open = EP.els.body.classList.toggle("rail-open")
  EP.els.head.classList.toggle("rail-open", open)
}

function setRange(key) { EP.range = key; filtersChanged() }
function onSearch(e) { EP.q = e.target.value; filtersChanged() }

function filtersChanged() {
  reloadTab().then(afterFilter).catch(fail)
}

function afterFilter() {
  if (EP.tab === "board") return render()
  EP.els.body.querySelectorAll(".ep-range .ep-segb").forEach(markRange)
  return renderRailList()
}

function markRange(btn, i) { btn.classList.toggle("on", Object.keys(RANGES)[i] === EP.range) }

function rangeButton(key) {
  return h("button", { class: "ep-segb" + onClass(EP.range === key), onclick: setRange.bind(null, key) }, RANGES[key].label)
}

function rangeEl() { return h("div", { class: "ep-seg ep-range" }, Object.keys(RANGES).map(rangeButton)) }

function searchEl(placeholder) {
  return h("input", { class: "ep-input ep-search", type: "search", placeholder, "aria-label": placeholder, value: EP.q,
    oninput: onSearch })
}

function railEl(title, placeholder) {
  return h("nav", { class: "ep-rail", "aria-label": title }, h("div", { class: "ep-rail-top" }, h("h2", { text: title }),
    rangeEl(), searchEl(placeholder)), h("div", { class: "ep-rail-list" }))
}

function renderRailList() {
  const list = EP.els.body.querySelector(".ep-rail-list")
  if (list) fill(list, sessionItems())
}

function sinceParam() { return EP.range === "all" ? "" : String(RANGES[EP.range].secs) }

function query(extra) { return "?" + new URLSearchParams({ since: sinceParam(), q: EP.q, ...extra }).toString() }

async function reloadTab() {
  EP.stats = await call("/stats")
  if (EP.tab === "board") EP.board = (await call("/leaderboard" + query({}))).rows
}

/* why: Review tab: a rail of chats (newest pinned as "Current chat"), the chosen chat as a transcript */

async function loadSessions() { EP.sessions = (await call("/sessions?limit=500")).sessions }
async function loadRuns() { EP.runs = (await call("/runs?session_id=" + encodeURIComponent(EP.sessionId))).runs }
function newestId() { return EP.sessions.length ? EP.sessions[0].id : null }
function sessionTime(s) { return pick(s.last_activity_at, s.started_at) || 0 }
function inRange(s) { return Date.now() / 1000 - sessionTime(s) <= RANGES[EP.range].secs }
function sessionText(s) { return [s.title, s.model, s.id].join(" ").toLowerCase() }
function matchesText(s) { return !EP.q || sessionText(s).includes(EP.q.toLowerCase()) }
function isVisible(s) { return s.id !== newestId() && inRange(s) && matchesText(s) }

function messageCountOf(id) {
  const s = EP.sessions.find(sameId.bind(null, id))
  return s ? s.message_count : 0
}

async function openSession(id, live) {
  EP.sessionId = id
  EP.live = live
  const r = await call(`/sessions/${encodeURIComponent(id)}/turns`)
  Object.assign(EP, { session: r.session, turns: r.turns, lastMsgCount: messageCountOf(id) })
  await loadRuns()
  select(EP.turns.length - 1)
}

const HF_REPO = /models--[^/]*?--([^/]+)/

function shortModel(m) {
  const name = pick(m, "?"), hf = name.match(HF_REPO)
  return hf ? hf[1] : name.split("/").pop()
}

function sessionSub(s) {
  const parts = [ago(sessionTime(s)), shortModel(s.model)]
  if (s.eval_count) parts.unshift(s.eval_count + " judged")
  return clip(parts.join(" · "), RAIL_CHARS + 4)
}

function sessionTitle(s) { return clip(oneLine(pick(s.title, "Untitled chat")), RAIL_CHARS) }

function sessionButton(s, label) {
  const live = label ? h("span", { class: "ep-livedot", title: "follows your newest Hermes chat" }) : null
  return h("button", { class: "ep-item" + onClass(s.id === EP.sessionId), title: [s.title, s.model, s.id].join("\n"),
    onclick: openSession.bind(null, s.id, !!label) }, h("span", { class: "ep-item-t" }, live, pick(label, sessionTitle(s))),
  h("span", { class: "ep-item-s", text: label ? sessionTitle(s) : sessionSub(s) }))
}

function sessionButtonPlain(s) { return sessionButton(s, null) }

function sessionItems() {
  const current = EP.sessions[0]
  const shown = EP.sessions.filter(isVisible)
  const empty = shown.length ? null : h("div", { class: "ep-empty sm", text: "No other chats match." })
  return [current ? sessionButton(current, "Current chat") : null, h("h3", { text: `Earlier chats · ${shown.length}` }),
    shown.map(sessionButtonPlain), empty]
}

function samePrompt(t, run) { return oneLine(run.prompt) === oneLine(t.prompt) }
function runFor(t) { return EP.runs.find(samePrompt.bind(null, t)) || null }
function turn() { return EP.turns[EP.sel] }
function judgmentOf(run) { return run ? run.judgment : null }
function modelName() { return shortModel(pick(EP.session && EP.session.model, "model")) }

/* why: a turn without an /eval run is one answer, A (the reply you saw); a run puts B.. beside it */
function answersOf(t) {
  const run = runFor(t)
  return run ? run.answers : [{ label: "A", model: EP.session && EP.session.model, text: t.response }]
}

function labelOfAnswer(a) { return a.label }
function labels() { return answersOf(turn()).map(labelOfAnswer) }

function draftFrom(j) {
  return j ? { good: j.good, note: pick(j.note, ""), expected: pick(j.expected, "") } : emptyDraft()
}

function select(i) {
  EP.sel = Math.max(0, Math.min(i, EP.turns.length - 1))
  const t = turn()
  EP.draft = draftFrom(t && judgmentOf(runFor(t)))
  EP.dirty = false
  render()
}

function bubble(kind, who, text) {
  return h("div", { class: "ep-msg " + kind }, h("div", { class: "ep-who" }, h("b", { text: who })),
    h("div", { class: "ep-bubble", text }))
}

function goodText(good) { return good.length ? good.join(" ") : "none" }

function judgedDot(t) {
  const j = judgmentOf(runFor(t))
  if (!j || j.good == null) return null
  return h("i", { class: "ep-dot " + (j.good.length ? "pass" : "fail"), title: "good: " + goodText(j.good) })
}

function pastEl(t, i) {
  const reply = t.response ? bubble("asst", modelName(), clip(t.response, 360)) : null
  return h("div", { class: "ep-past", onclick: select.bind(null, i), title: "review this turn" },
    h("span", { class: "ep-now-label" }, `TURN ${i + 1} `, judgedDot(t)), bubble("user", "You", clip(t.prompt, 360)), reply)
}

function asText(v) { return typeof v === "string" ? v : JSON.stringify(v, null, 2) }

function toolChip(tc) {
  return h("details", { class: "ep-chip" }, h("summary", {}, h("span", { class: "ep-fn", text: pick(tc.name, "tool") }),
    h("span", { class: "ep-arg", text: clip(oneLine(asText(tc.arguments)), 140) })),
  h("pre", { class: "ep-pre", text: pick(asText(tc.result), "") }))
}

function chipsEl(t) { return t.tools.length ? h("div", { class: "ep-chips" }, t.tools.map(toolChip)) : null }

function onField(field, e) { EP.draft[field] = e.target.value; EP.dirty = true }

function expectedEl() {
  const box = h("textarea", { class: "ep-input", rows: 3, placeholder: "What a correct reply looks like",
    value: EP.draft.expected, oninput: onField.bind(null, "expected") })
  const fold = h("details", { class: "ep-fold" }, h("summary", { text: "Expected answer (optional)" }), box)
  fold.open = !!EP.draft.expected
  return fold
}

/* why: every answer is a column you tap to mark good; several can be good */
function isGood(label) { return (EP.draft.good || []).includes(label) }
function answerName(a) { return shortModel(pick(a.model, "unknown")) }
function answerMeta(a) { return a.latency_ms == null ? "the reply you saw" : secs(a.latency_ms) }

function answerBody(a) {
  if (a.error) return h("span", { class: "ep-col-b ep-err", text: "⚠ " + a.error })
  return h("span", { class: "ep-col-b", text: pick(a.text, "(no text response)") })
}

function answerCol(a) {
  const good = isGood(a.label)
  return h("button", { class: "ep-col" + (good ? " won" : ""), onclick: toggleGood.bind(null, a.label),
    "aria-pressed": String(good), title: `${a.label} is good` },
    h("span", { class: "ep-col-h" }, h("span", { class: "ep-label", text: a.label }), h("b", { text: answerName(a) }),
      h("span", { class: "ep-col-meta", text: answerMeta(a) })), answerBody(a))
}

function gridEl(answers) {
  return h("div", { class: "ep-cgrid", style: `--ep-cols: ${Math.min(answers.length, 3)}` }, answers.map(answerCol))
}

function focusEl(t) {
  const answers = answersOf(t)
  const hint = answers.length > 1 ? null : h("p", { class: "ep-hint", text: "Run /eval in Hermes to compare this answer with other models." })
  return h("section", { class: "ep-now", "aria-label": "Turn under review" },
    h("span", { class: "ep-now-label", text: `TURN ${t.index + 1} · reviewing · ${ago(t.ts)}` }),
    bubble("user", "You", t.prompt), chipsEl(t), gridEl(answers), hint, expectedEl())
}

function turnEl(t, i) { return i === EP.sel ? focusEl(t) : pastEl(t, i) }

function stageEl() {
  if (!turn()) return h("main", { class: "ep-stage" }, h("div", { class: "ep-empty", text: "Start a chat with Hermes. New turns show up here live." }))
  return h("main", { class: "ep-stage" }, h("div", { class: "ep-thread" }, EP.turns.map(turnEl)))
}

function isIn(list, item) { return list.includes(item) }
function isNot(label, other) { return other !== label }

function setGood(good) {
  EP.draft.good = labels().filter(isIn.bind(null, good))
  EP.dirty = true
  swap(".ep-cgrid", gridEl(answersOf(turn())))
  swap(".ep-bar", barEl())
}

function toggleGood(label) {
  const good = EP.draft.good || []
  setGood(good.includes(label) ? good.filter(isNot.bind(null, label)) : good.concat(label))
}

function setAllGood() { setGood(labels()) }
function setNoneGood() { setGood([]) }
function isAll() { const g = EP.draft.good; return !!g && g.length === labels().length }
function isNone() { const g = EP.draft.good; return !!g && !g.length }

function choice(text, on, onclick) {
  return h("button", { class: "ep-segb" + onClass(on), "aria-pressed": String(on), onclick }, text)
}

function labelButton(a) { return choice(a.label, isGood(a.label), toggleGood.bind(null, a.label)) }

/* why: one answer reads as Good / Not good; several as A B C + All / None */
function choicesEl(answers) {
  if (answers.length < 2) return [choice("Good", isAll(), setAllGood), choice("Not good", isNone(), setNoneGood)]
  return [answers.map(labelButton), choice("All", isAll(), setAllGood), choice("None", isNone(), setNoneGood)]
}

function saveButton() {
  const dot = EP.dirty ? h("span", { class: "ep-unsaved", title: "unsaved" }) : null
  return h("button", { class: "ep-btn pri", onclick: saveReview }, dot, "Save & next", kbd("⌘↵"))
}

function barEl() {
  const note = h("input", { class: "ep-input ep-note", placeholder: "Note: why?", "aria-label": "Note", value: EP.draft.note,
    oninput: onField.bind(null, "note") })
  return h("footer", { class: "ep-bar", "aria-label": "Mark the good answers" }, h("div", { class: "ep-bar-in" },
    h("span", { class: "ep-meta", text: "Good" }), h("div", { class: "ep-seg" }, choicesEl(answersOf(turn()))), note,
    saveButton()))
}

function gradeBody(t) {
  const run = runFor(t)
  const target = run ? { run_id: run.id } : { session_id: EP.sessionId, message_id: t.message_id, prompt: t.prompt,
    response: t.response, model: EP.session && EP.session.model }
  return { ...target, ...EP.draft }
}

async function persistReview(t) {
  await send("/judgments", gradeBody(t))
  await loadRuns()
  EP.stats = await call("/stats")
  toast(EP.draft.good ? `Saved ✓ · good: ${goodText(EP.draft.good)}` : "Saved ✓")
}

function saveReview() {
  const t = turn()
  if (!t) return Promise.resolve()
  return persistReview(t).then(select.bind(null, EP.sel + 1)).catch(fail)
}

function renderReview() {
  fill(EP.els.body, railEl("Chats", "Search chats or models"), h("div", { class: "ep-main" }, stageEl(), turn() ? barEl() : null))
  renderRailList()
  const now = EP.els.body.querySelector(".ep-now")
  if (now && now.scrollIntoView) now.scrollIntoView({ block: "start" })
}

/* why: Leaderboard tab: one row per model across the runs in range */

const BOARD_COLS = [["Model", boardModel], ["Good", boardGood], ["Good %", boardGoodRate], ["Sole wins", boardWins],
  ["Answers", boardAnswers]]

function boardModel(r) { return shortModel(r.model) }
function boardGood(r) { return `${r.good} / ${r.judged}` }
function boardGoodRate(r) { return pct(r.good_rate) }
function boardWins(r) { return String(r.wins) }
function boardAnswers(r) { return String(r.answers) }
function headCell(col) { return h("th", { text: col[0] }) }
function cell(row, col) { return h("td", { text: col[1](row) }) }
function boardRow(row) { return h("tr", {}, BOARD_COLS.map(cell.bind(null, row))) }

function renderBoard() {
  const empty = h("div", { class: "ep-empty", text: "No /eval runs in this range yet." })
  const table = h("table", { class: "ep-table" }, h("thead", {}, h("tr", {}, BOARD_COLS.map(headCell))),
    h("tbody", {}, EP.board.map(boardRow)))
  const note = h("p", { class: "ep-hint", text: "Good / judged: how often this model gave an answer you marked good. Sole win: it was the only good one." })
  fill(EP.els.body, h("div", { class: "ep-board" }, h("div", { class: "ep-toolbar" }, rangeEl()),
    EP.board.length ? table : empty, note))
}

const RENDERERS = { review: renderReview, board: renderBoard }

function render() {
  renderHead()
  EP.els.head.classList.remove("rail-open")
  EP.els.body.className = "ep-body tab-" + EP.tab
  RENDERERS[EP.tab]()
}

/* why: keys differ per tab; one table each */

function isTyping(e) { return /^(INPUT|TEXTAREA|SELECT)$/.test(e.target.tagName || "") }
function hasModifier(e) { return e.metaKey || e.ctrlKey || e.altKey }
function isSaveCombo(e) { return (e.metaKey || e.ctrlKey) && e.key === "Enter" }
function nextTurn(e) { e.preventDefault(); select(EP.sel + 1) }
function prevTurn(e) { e.preventDefault(); select(EP.sel - 1) }

function goodKey(e) {
  const label = e.key.toUpperCase()
  if (labels().includes(label)) toggleGood(label)
}

const KEYMAPS = {
  review: { j: nextTurn, ArrowDown: nextTurn, k: prevTurn, ArrowUp: prevTurn, t: setAllGood, n: setNoneGood,
    a: goodKey, b: goodKey, c: goodKey, d: goodKey, e: goodKey },
  board: {},
}

const SAVERS = { review: saveReview, board: ignore }

function keyHandler(e) { return turn() ? KEYMAPS[EP.tab][e.key] : null }

function onKey(e) {
  if (isSaveCombo(e)) { e.preventDefault(); SAVERS[EP.tab](); return }
  if (isTyping(e) || hasModifier(e)) return
  const handler = keyHandler(e)
  if (handler) handler(e)
}

/* why: polling keeps "Current chat" and new /eval runs fresh without a reload */

function shouldFollow(l) { return !!l && !EP.dirty && (l.id !== EP.sessionId || l.message_count !== EP.lastMsgCount) }

async function refreshRuns() {
  if (EP.dirty || !EP.sessionId) return
  const before = EP.runs.length
  await loadRuns()
  if (EP.runs.length !== before) select(EP.sel)
}

async function pollReview() {
  if (!EP.live) return refreshRuns()
  const { latest } = await call("/latest")
  if (!shouldFollow(latest)) return refreshRuns()
  await loadSessions()
  return openSession(latest.id, true)
}

const POLLERS = { review: pollReview, board: ignore }

async function poll() {
  if (!EP.root.isConnected) { document.removeEventListener("keydown", onKey); return }
  await Promise.resolve(POLLERS[EP.tab]()).catch(ignore)
  EP.pollTimer = setTimeout(poll, 3000)
}

async function load() {
  await loadSessions()
  EP.stats = await call("/stats")
  if (EP.sessions.length) return openSession(EP.sessions[0].id, true)
  return render()
}

function showBootError(e) { fill(EP.els.body, h("div", { class: "ep-empty", text: "⚠ " + pick(e.message, e) })) }

async function boot() {
  renderHead()
  fill(EP.els.body, h("div", { class: "ep-empty", text: "Loading…" }))
  await load().catch(showBootError)
  EP.pollTimer = setTimeout(poll, 3000)
}

function mount(root, opts) {
  clearTimeout(EP.pollTimer)
  Object.assign(EP, freshState(), { root, api: opts.apiBase.replace(/\/$/, ""), fetchJSON: opts.fetchJSON || null })
  root.classList.add("quickeval")
  EP.els = { head: h("header", { class: "ep-head" }), body: h("div", { class: "ep-body" }), toast: h("div", { class: "ep-toast" }) }
  fill(root, EP.els.head, EP.els.body, EP.els.toast)
  document.addEventListener("keydown", onKey)
  boot()
}

function mountInto(ref, sdk) {
  if (ref.current) mount(ref.current, { apiBase: "/api/plugins/quick-eval", fetchJSON: sdk.fetchJSON })
}

function QuickEvalPage() {
  const sdk = window.__HERMES_PLUGIN_SDK__
  const ref = sdk.React.useRef(null)
  sdk.React.useEffect(mountInto.bind(null, ref, sdk), [])
  return sdk.React.createElement("div", { ref })
}

function registerDashboard() {
  if (!window.__HERMES_PLUGINS__ || !window.__HERMES_PLUGIN_SDK__) return
  window.__HERMES_PLUGINS__.register("quick-eval", QuickEvalPage)
}

window.QuickEvalUI = { mount }
registerDashboard()
