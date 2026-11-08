/* why: quick-eval UI, framework-free. Review a chat, compare models on one prompt, see a leaderboard. */
"use strict"

const TAGS = ["wrong", "hallucination", "refusal", "censored", "too-long", "great", "style"]
const SCORES = [1, 2, 3, 4, 5]
const RAIL_CHARS = 24 /* why: rail is 232px; a longer label gets cut mid-glyph by CSS */
const TABS = { review: "Review", compare: "Compare", board: "Leaderboard" }
const AGO_STEPS = [
  { lt: 3600, div: 60, suffix: "m ago" },
  { lt: 86400, div: 3600, suffix: "h ago" },
  { lt: Infinity, div: 86400, suffix: "d ago" },
]
const RANGES = {
  hour: { label: "Hour", secs: 3600 }, day: { label: "Day", secs: 86400 },
  week: { label: "Week", secs: 604800 }, all: { label: "All time", secs: Infinity },
}
const SETTERS = { class: setClass, text: setText, value: setValue }
const EP = freshState()

function freshCompare() {
  return { runs: [], sel: 0, draft: emptyVerdict(), focus: 0, blind: false, unjudged: false, dirty: false }
}

function freshState() {
  return {
    root: null, api: "", fetchJSON: null, els: {}, sessions: [], sessionId: null, session: null, turns: [], sel: 0,
    runs: [], stats: {}, live: true, view: "chat", tab: "review", range: "all", model: "", q: "", draft: null,
    dirty: false, toast: "", lastMsgCount: 0, toastTimer: null, pollTimer: null, cmp: freshCompare(), board: [],
  }
}

function emptyVerdict() { return { winner: null, scores: {}, note: "" } }
function pick(a, b) { return a || b }
function ignore() { return undefined }
function noJson() { return {} }
function notEqual(a, b) { return a !== b }
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

function oneLine(v) {
  const s = typeof v === "string" ? v : JSON.stringify(v)
  return (s || "").replace(/\s+/g, " ")
}

function norm(s) { return (s || "").replace(/\s+/g, " ").trim() }
function pct(x) { return x == null ? "–" : Math.round(x * 100) + "%" }
function num(x, digits) { return x == null ? "–" : x.toFixed(digits) }
function secs(ms) { return ms == null ? "–" : (ms / 1000).toFixed(1) + " s" }
function usd(x) { return x ? "$" + x.toFixed(4) : "–" }

function keyLabel(key) { return key == null ? null : h("span", { class: "ep-jk", text: key + ": " }) }
function jsonRow(key, node) { return h("div", { class: "ep-jrow" }, keyLabel(key), node) }
function indexPair(v, i) { return [i, v] }
function toEntries(v) { return Array.isArray(v) ? v.map(indexPair) : Object.entries(v) }
function brackets(v) { return Array.isArray(v) ? ["[", "]"] : ["{", "}"] }
function noun(v) { return Array.isArray(v) ? "items" : "keys" }
function isLongText(v) { return typeof v === "string" && (v.includes("\n") || v.length > 120) }
function leafText(v) { return isLongText(v) ? v : String(JSON.stringify(v)) }
function longSuffix(text) { return text.length > 120 ? " ep-jlong" : "" }

function leafClass(v) {
  if (typeof v === "number") return "ep-jn"
  if (typeof v === "boolean" || v === null) return "ep-jb"
  return "ep-js"
}

function childNode(depth, entry) { return jsonNode(entry[1], entry[0], depth) }

function branchSummary(value, key, count) {
  const [open, close] = brackets(value)
  return h("summary", {}, keyLabel(key), h("span", { class: "ep-jp", text: open }),
    h("span", { class: "ep-jc", text: ` ${count} ${noun(value)} ${close}` }))
}

function jsonBranch(value, key, depth) {
  const entries = toEntries(value)
  if (!entries.length) return jsonRow(key, h("span", { class: "ep-jp", text: brackets(value).join("") }))
  const kids = h("div", { class: "ep-jkids" }, entries.map(childNode.bind(null, depth + 1)))
  const details = h("details", { class: "ep-jd" }, branchSummary(value, key, entries.length), kids)
  details.open = depth < 2
  return details
}

function jsonLeaf(value, key) {
  const text = leafText(value)
  return jsonRow(key, h("span", { class: leafClass(value) + longSuffix(text), text }))
}

function jsonNode(value, key, depth) {
  if (value && typeof value === "object") return jsonBranch(value, key, depth)
  return jsonLeaf(value, key)
}

function jsonView(v) { return h("div", { class: "ep-json" }, jsonNode(v, null, 0)) }

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

function sinceParam() { return EP.range === "all" ? "" : String(RANGES[EP.range].secs) }

function query(extra) {
  const params = new URLSearchParams({ since: sinceParam(), model: EP.model, q: EP.q, ...extra })
  return "?" + params.toString()
}

async function loadSessions() { EP.sessions = (await call("/sessions?limit=500")).sessions }
async function loadStats() { EP.stats = await call("/stats") }

async function loadRuns() {
  EP.runs = (await call(`/runs?session_id=${encodeURIComponent(EP.sessionId)}`)).runs
}

function messageCountOf(id) {
  const s = EP.sessions.find(sameId.bind(null, id))
  return s ? s.message_count : 0
}

async function openSession(id, selectLast) {
  EP.sessionId = id
  const r = await call(`/sessions/${encodeURIComponent(id)}/turns`)
  EP.session = r.session
  EP.turns = r.turns
  EP.lastMsgCount = messageCountOf(id)
  await loadRuns()
  await loadStats()
  select(selectLast ? EP.turns.length - 1 : EP.sel)
}

function samePrompt(t, run) { return norm(run.prompt) === norm(t.prompt) }

function runFor(t) {
  const runs = EP.runs.filter(samePrompt.bind(null, t))
  return runs[0] || null
}

function turn() { return EP.turns[EP.sel] }
function turnRun() { const t = turn(); return t ? runFor(t) : null }
function modelName() { return pick(EP.session && EP.session.model, "model") }
function judgmentOf(run) { return run ? run.judgment : null }
function scoreA(j) { return (j && j.scores && j.scores.A) || {} }

function emptyDraft() { return { verdict: null, score: null, tags: [], notes: "", expected: "" } }

function draftFrom(j) {
  const a = scoreA(j)
  return { verdict: a.verdict || null, score: a.score || null, tags: [...pick(a.tags, [])], notes: pick(j.note, ""),
    expected: pick(j.expected, "") }
}

function select(i) {
  EP.sel = Math.max(0, Math.min(i, EP.turns.length - 1))
  const j = judgmentOf(turnRun())
  EP.draft = j ? draftFrom(j) : emptyDraft()
  EP.dirty = false
  render()
}

function swap(selector, node) {
  const old = EP.els.body.querySelector(selector)
  if (old) old.replaceWith(node)
}

function renderBarInto() { swap(".ep-bar", EP.tab === "compare" ? compareBarEl() : barEl()) }

function patch(p) {
  Object.assign(EP.draft, p)
  EP.dirty = true
  renderBarInto()
}

function gradeBody(t) {
  const run = runFor(t)
  const target = run ? { run_id: run.id } : { session_id: EP.sessionId, message_id: t.message_id, prompt: t.prompt,
    response: t.response, model: EP.session && EP.session.model }
  const d = EP.draft
  return { ...target, scores: { A: { verdict: d.verdict, score: d.score, tags: d.tags } }, note: d.notes,
    expected: d.expected }
}

async function persist(t) {
  await send("/judgments", gradeBody(t))
  EP.dirty = false
  await loadRuns()
  await loadStats()
  toast("Saved ✓")
}

function afterSave(advance) {
  if (advance && EP.sel < EP.turns.length - 1) return select(EP.sel + 1)
  return render()
}

function save(advance) {
  const t = turn()
  if (!t) return Promise.resolve()
  return persist(t).then(afterSave.bind(null, advance)).catch(fail)
}

function onSaveClick() { return save(true) }
function kbd(key) { return h("kbd", { text: key }) }
function grow() { return h("span", { class: "ep-grow" }) }

function sessionLabel(s) {
  const parts = [clip(pick(s.title, s.id), 46), pick(s.model, "?"), ago(pick(s.last_activity_at, s.started_at))]
  if (s.eval_count) parts.push(s.eval_count + " ✓")
  return parts.join(" · ")
}

function sessionOption(s) { return h("option", { value: s.id, selected: s.id === EP.sessionId }, sessionLabel(s)) }
function newestId() { return EP.sessions.length ? EP.sessions[0].id : null }

function onSessionChange(e) {
  EP.live = e.target.value === newestId()
  openSession(e.target.value, true).catch(fail)
}

function onLiveChange(e) {
  EP.live = e.target.checked
  if (EP.live && newestId()) openSession(newestId(), true).catch(fail)
}

function sessionTime(s) { return pick(s.last_activity_at, s.started_at) || 0 }
function inRange(ts) { return Date.now() / 1000 - (ts || 0) <= RANGES[EP.range].secs }
function matchesModel(s) { return !EP.model || s.model === EP.model }
function matchesText(s) { return !EP.q || sessionLabel(s).toLowerCase().includes(EP.q.toLowerCase()) }
function isVisible(s) { return inRange(sessionTime(s)) && matchesModel(s) && matchesText(s) }
function isCurrent(s) { return s.id === EP.sessionId }

function visibleSessions() {
  const shown = EP.sessions.filter(isVisible)
  const current = EP.sessions.find(isCurrent)
  return current && !shown.includes(current) ? [current, ...shown] : shown
}

function sessionSelect() {
  if (EP.tab !== "review") return null
  return h("select", { class: "ep-session", "aria-label": "Session", onchange: onSessionChange }, visibleSessions().map(sessionOption))
}

function liveEl() {
  if (EP.tab !== "review") return null
  return h("label", { class: "ep-live", title: "follow the newest Hermes chat" },
    h("input", { type: "checkbox", checked: EP.live, onchange: onLiveChange }), "live")
}

function filtersChanged() {
  renderFilters()
  renderHead()
  if (EP.tab !== "review") reloadTab().catch(fail)
}

function setRange(key) { EP.range = key; filtersChanged() }
function onModelFilter(e) { EP.model = e.target.value; filtersChanged() }

function onSearch(e) {
  EP.q = e.target.value
  renderHead()
  renderCount()
  if (EP.tab === "compare") reloadTab().catch(fail)
}

function modelOf(s) { return s.model }
function runModels(run) { return run.answers.map(modelOf) }

function uniqueModels() {
  const all = EP.sessions.map(modelOf).concat(EP.cmp.runs.flatMap(runModels), EP.board.map(modelOf))
  return [...new Set(all.filter(Boolean))].sort()
}

function rangeButton(key) {
  return h("button", { class: "ep-segb" + onClass(EP.range === key), onclick: setRange.bind(null, key) }, RANGES[key].label)
}

function modelOption(m) { return h("option", { value: m, selected: m === EP.model }, m) }

function modelFilter() {
  return h("select", { class: "ep-input ep-filter", "aria-label": "Filter by model", onchange: onModelFilter },
    h("option", { value: "" }, "All models"), uniqueModels().map(modelOption))
}

function countText() {
  if (EP.tab === "compare") return `${shownRuns().length} runs`
  if (EP.tab === "board") return `${EP.board.length} models`
  return `${EP.sessions.filter(isVisible).length} of ${EP.sessions.length} sessions`
}

function renderCount() {
  const el = EP.els.filters.querySelector(".ep-count")
  if (el) el.textContent = countText()
}

function renderFilters() {
  const search = h("input", { class: "ep-input ep-filter ep-search", type: "search", placeholder: "Search",
    "aria-label": "Search", value: EP.q, oninput: onSearch })
  EP.els.filters.replaceChildren(h("div", { class: "ep-seg" }, Object.keys(RANGES).map(rangeButton)), modelFilter(),
    EP.tab === "board" ? null : search, h("span", { class: "ep-meta ep-count", text: countText() }))
}

async function reloadTab() {
  if (EP.tab === "compare") await loadCompare()
  if (EP.tab === "board") await loadBoard()
  renderFilters()
  render()
}

function setTab(t) {
  EP.tab = t
  reloadTab().catch(fail)
}

function tabButton(t) {
  return h("button", { class: "ep-segb" + onClass(EP.tab === t), onclick: setTab.bind(null, t) }, TABS[t])
}

function tabsEl() { return h("div", { class: "ep-seg" }, Object.keys(TABS).map(tabButton)) }

function metaEl() {
  const st = EP.stats
  return h("span", { class: "ep-meta", text: `${pick(st.judged, 0)}/${pick(st.runs, 0)} judged · pass ${pct(st.pass_rate)}` })
}

function exportEl() {
  return h("a", { class: "ep-btn ep-wide", href: EP.api + "/export", download: "evals.jsonl", text: "Export JSONL" })
}

function renderHead() {
  EP.els.head.replaceChildren(h("span", { class: "ep-brand", text: "Quick Eval" }), sessionSelect(), liveEl(), grow(),
    metaEl(), tabsEl(), exportEl())
}

/* why: Review tab: one chat as a transcript; the bar grades answer A of the focused turn */

function turnDot(t) {
  const verdict = scoreA(judgmentOf(runFor(t))).verdict
  return h("i", { class: "ep-dot " + pick(verdict, judgmentOf(runFor(t)) ? "none" : "") })
}

function turnButton(t, i) {
  const prompt = pick(clip(oneLine(t.prompt), RAIL_CHARS), "(empty)")
  return h("button", { class: "ep-turn" + onClass(i === EP.sel), onclick: select.bind(null, i), title: prompt },
    h("b", { text: "#" + (i + 1) }), h("span", { text: prompt }), turnDot(t))
}

function railEl() {
  const empty = EP.turns.length ? null : h("div", { class: "ep-empty", text: "No turns yet." })
  return h("nav", { class: "ep-rail", "aria-label": "Turns" }, h("h2", { text: "Turns" }), EP.turns.map(turnButton), empty)
}

function bubble(kind, who, sub, text) {
  return h("div", { class: "ep-msg " + kind },
    h("div", { class: "ep-who" }, h("b", { text: who }), sub), h("div", { class: "ep-bubble", text }))
}

function pastEl(t, i) {
  const reply = t.response ? bubble("asst", modelName(), "", clip(t.response, 360)) : null
  return h("div", { class: "ep-past", onclick: select.bind(null, i), title: "review this turn" },
    bubble("user", "You", "#" + (i + 1), clip(t.prompt, 360)), reply)
}

function toolChip(tc) {
  return h("details", { class: "ep-chip" },
    h("summary", {}, h("span", { class: "ep-fn", text: pick(tc.name, "tool") }),
      h("span", { class: "ep-arg", text: clip(oneLine(tc.arguments), 140) })),
    jsonView({ arguments: tc.arguments, result: tc.result }))
}

function chipsEl(t) { return t.tools.length ? h("div", { class: "ep-chips" }, t.tools.map(toolChip)) : null }

function reasoningEl(t) {
  if (!t.reasoning) return null
  return h("details", { class: "ep-fold" }, h("summary", { text: "Reasoning" }), h("div", { class: "ep-text", text: t.reasoning }))
}

function onField(field, e) { EP.draft[field] = e.target.value; EP.dirty = true }

function expectedEl() {
  const box = h("textarea", { class: "ep-input", rows: 3, placeholder: "What a correct reply looks like",
    value: EP.draft.expected, oninput: onField.bind(null, "expected") })
  const fold = h("details", { class: "ep-fold" }, h("summary", { text: "Expected answer (optional)" }), box)
  fold.open = !!EP.draft.expected
  return fold
}

function compareLink(t) {
  const run = runFor(t)
  if (!run || run.answers.length < 2) return null
  const winner = judgmentOf(run) && judgmentOf(run).winner
  const label = `Compare ${run.answers.length} answers` + (winner ? ` · winner ${winner}` : "") + " →"
  return h("button", { class: "ep-btn ep-link", onclick: openCompare.bind(null, run.id) }, label)
}

function focusEl(t) {
  return h("section", { class: "ep-now", "aria-label": "Turn under review" },
    h("span", { class: "ep-now-label", text: `TURN ${t.index + 1} · reviewing · ${ago(t.ts)}` }),
    bubble("user", "You", "", t.prompt), chipsEl(t), reasoningEl(t),
    bubble("asst", modelName(), "", pick(t.response, "(no text response)")), compareLink(t), expectedEl())
}

function turnEl(t, i) { return i === EP.sel ? focusEl(t) : pastEl(t, i) }
function setView(v) { EP.view = v; swap(".ep-stage", stageEl()) }

function viewButton(v) {
  return h("button", { class: "ep-segb" + onClass(EP.view === v), onclick: setView.bind(null, v) }, v === "chat" ? "Chat" : "JSON")
}

function toolbarEl() {
  return h("div", { class: "ep-toolbar" }, h("div", { class: "ep-seg" }, ["chat", "json"].map(viewButton)))
}

function threadEl(t) {
  if (EP.view === "json") return jsonView({ session: EP.session, turn: t, run: runFor(t) })
  return h("div", { class: "ep-thread" }, EP.turns.map(turnEl))
}

function stageEl() {
  const t = turn()
  if (!t) return h("main", { class: "ep-stage" }, h("div", { class: "ep-empty", text: "Start a chat with Hermes. New turns show up here live." }))
  return h("main", { class: "ep-stage" }, h("div", { class: "ep-wrap" }, toolbarEl(), threadEl(t)))
}

function toggleVerdict(kind) { patch({ verdict: EP.draft.verdict === kind ? null : kind }) }
function toggleScore(n) { patch({ score: EP.draft.score === n ? null : n }) }

function toggleTag(t) {
  const tags = EP.draft.tags
  patch({ tags: tags.includes(t) ? tags.filter(notEqual.bind(null, t)) : [...tags, t] })
}

function verdictButton(kind, label, key) {
  const on = onClass(EP.draft.verdict === kind)
  return h("button", { class: `ep-segb ${kind}${on}`, onclick: toggleVerdict.bind(null, kind) }, label, kbd(key))
}

function scoreButton(n) {
  return h("button", { class: "ep-segb score" + onClass(EP.draft.score === n), onclick: toggleScore.bind(null, n), title: `score ${n}` }, String(n))
}

function tagButton(t) {
  return h("button", { class: "ep-tag" + onClass(EP.draft.tags.includes(t)), onclick: toggleTag.bind(null, t), text: t })
}

function saveButton(dirty, onclick, label) {
  const dot = dirty ? h("span", { class: "ep-unsaved", title: "unsaved" }) : null
  return h("button", { class: "ep-btn pri", onclick }, dot, label, kbd("⌘↵"))
}

function barEl() {
  const note = h("input", { class: "ep-input ep-note", placeholder: "Note: why?", "aria-label": "Note",
    value: EP.draft.notes, oninput: onField.bind(null, "notes") })
  return h("footer", { class: "ep-bar", "aria-label": "Grade turn" }, h("div", { class: "ep-bar-in" },
    h("div", { class: "ep-seg" }, verdictButton("pass", "Pass", "p"), verdictButton("fail", "Fail", "f")),
    h("div", { class: "ep-seg" }, SCORES.map(scoreButton)), h("div", { class: "ep-tags" }, TAGS.map(tagButton)), note,
    saveButton(EP.dirty, onSaveClick, "Save & next")))
}

function renderReview() {
  const bar = turn() ? barEl() : null
  EP.els.body.replaceChildren(railEl(), h("div", { class: "ep-main" }, stageEl(), bar))
  scrollFocus()
}

/* why: Compare tab: one prompt, one column per model, pick a winner, next unjudged */

function isUnjudged(run) { return !run.judgment || !run.judgment.winner }
function shownRuns() { return EP.cmp.unjudged ? EP.cmp.runs.filter(isUnjudged) : EP.cmp.runs }
function cmpRun() { return shownRuns()[EP.cmp.sel] || null }

function verdictFrom(j) {
  if (!j) return emptyVerdict()
  return { winner: j.winner, scores: JSON.parse(JSON.stringify(j.scores || {})), note: pick(j.note, "") }
}

function cmpSelect(i) {
  const runs = shownRuns()
  EP.cmp.sel = Math.max(0, Math.min(i, runs.length - 1))
  EP.cmp.draft = verdictFrom(judgmentOf(cmpRun()))
  EP.cmp.focus = 0
  EP.cmp.dirty = false
  render()
}

async function loadCompare() {
  const keep = cmpRun() && cmpRun().id
  EP.cmp.runs = (await call("/runs" + query({ multi: "1" }))).runs
  const i = shownRuns().findIndex(sameId.bind(null, keep))
  EP.cmp.sel = Math.max(0, i)
  EP.cmp.draft = verdictFrom(judgmentOf(cmpRun()))
  EP.cmp.dirty = false
}

async function openCompare(runId) {
  EP.tab = "compare"
  EP.q = ""
  await loadCompare()
  const i = shownRuns().findIndex(sameId.bind(null, runId))
  renderFilters()
  cmpSelect(Math.max(0, i))
}

function patchCmp(p) {
  Object.assign(EP.cmp.draft, p)
  EP.cmp.dirty = true
  swap(".ep-cgrid", gridEl(cmpRun()))
  renderBarInto()
}

function setWinner(w) { patchCmp({ winner: EP.cmp.draft.winner === w ? null : w }) }

function setColScore(label, n) {
  const scores = EP.cmp.draft.scores
  const old = scores[label] || {}
  scores[label] = { ...old, score: old.score === n ? null : n }
  EP.cmp.focus = cmpRun().answers.findIndex(hasLabel.bind(null, label))
  patchCmp({ scores })
}

function hasLabel(label, a) { return a.label === label }
function isRevealed() { return !EP.cmp.blind || !!(judgmentOf(cmpRun()) && judgmentOf(cmpRun()).winner) }
function answerName(a) { return isRevealed() ? pick(a.model, a.alias) : `Model ${a.label}` }

function runButton(run, i) {
  const j = run.judgment
  const badge = j && j.winner ? h("span", { class: "ep-label", text: j.winner }) : h("i", { class: "ep-dot" })
  return h("button", { class: "ep-turn ep-runbtn" + onClass(i === EP.cmp.sel), onclick: cmpSelect.bind(null, i),
    title: run.prompt }, h("b", { text: run.answers.length + "×" }), h("span", { text: clip(oneLine(run.prompt), RAIL_CHARS) }), badge)
}

function onUnjudged(e) { EP.cmp.unjudged = e.target.checked; cmpSelect(0); renderCount() }

function cmpRailEl() {
  const runs = shownRuns()
  const empty = runs.length ? null : h("div", { class: "ep-empty", text: "No /eval runs here. Run /eval in Hermes." })
  const toggle = h("label", { class: "ep-live" }, h("input", { type: "checkbox", checked: EP.cmp.unjudged, onchange: onUnjudged }), "unjudged only")
  return h("nav", { class: "ep-rail", "aria-label": "Runs" }, h("h2", { text: "Runs" }), toggle, runs.map(runButton), empty)
}

function colScoreButton(label, n) {
  const entry = EP.cmp.draft.scores[label] || {}
  return h("button", { class: "ep-segb score" + onClass(entry.score === n), onclick: setColScore.bind(null, label, n) }, String(n))
}

function answerMeta(a) {
  if (a.role === "original") return "original"
  return [secs(a.latency_ms), a.tokens_out ? a.tokens_out + " tok" : null, usd(a.cost_usd)].filter(Boolean).join(" · ")
}

function answerCol(a, i) {
  const won = EP.cmp.draft.winner === a.label
  const cls = "ep-col" + (won ? " won" : "") + (i === EP.cmp.focus ? " focus" : "")
  const body = a.error ? h("div", { class: "ep-col-b ep-text ep-err", text: "⚠ " + a.error }) : h("div", { class: "ep-col-b ep-text", text: pick(a.text, "(empty)") })
  return h("div", { class: cls }, h("div", { class: "ep-col-h" }, h("span", { class: "ep-label", text: a.label }),
    h("b", { text: answerName(a) }), grow(), h("span", { text: answerMeta(a) })), body,
    h("div", { class: "ep-col-f" }, h("div", { class: "ep-seg" }, SCORES.map(colScoreButton.bind(null, a.label)))))
}

function gridEl(run) {
  return h("div", { class: "ep-cgrid", style: `--ep-cols: ${Math.min(run.answers.length, 4)}` }, run.answers.map(answerCol))
}

function onBlind(e) { EP.cmp.blind = e.target.checked; render() }

function cmpStageEl(run) {
  if (!run) return h("main", { class: "ep-stage" }, h("div", { class: "ep-empty", text: "Nothing to compare. In Hermes: ask something, then /eval." }))
  const blind = h("label", { class: "ep-live" }, h("input", { type: "checkbox", checked: EP.cmp.blind, onchange: onBlind }), "blind")
  return h("main", { class: "ep-stage" }, h("div", { class: "ep-cwrap" },
    h("div", { class: "ep-toolbar" }, h("span", { class: "ep-meta", text: `${ago(run.ts)} · ${run.answers.length} answers` }), grow(), blind),
    h("div", { class: "ep-prompt" }, h("span", { class: "ep-now-label", text: "PROMPT" }), h("div", { class: "ep-text", text: run.prompt })),
    gridEl(run)))
}

function winnerButton(w, label) {
  return h("button", { class: "ep-segb" + onClass(EP.cmp.draft.winner === w), onclick: setWinner.bind(null, w) }, label)
}

function onCmpNote(e) { EP.cmp.draft.note = e.target.value; EP.cmp.dirty = true }
function answerLabel(a) { return a.label }

function compareBarEl() {
  const run = cmpRun()
  const labels = run ? run.answers.map(answerLabel) : []
  const note = h("input", { class: "ep-input ep-note", placeholder: "Note: why this one?", "aria-label": "Note",
    value: EP.cmp.draft.note, oninput: onCmpNote })
  return h("footer", { class: "ep-bar", "aria-label": "Pick a winner" }, h("div", { class: "ep-bar-in" },
    h("span", { class: "ep-meta", text: "Winner" }), h("div", { class: "ep-seg" }, labels.map(winnerButtonFor),
      winnerButton("tie", "Tie"), winnerButton("none", "None")), note, saveButton(EP.cmp.dirty, saveCompareNext, "Save & next")))
}

function winnerButtonFor(label) { return winnerButton(label, label) }

async function saveCompare() {
  const run = cmpRun()
  if (!run) return
  const d = EP.cmp.draft
  const saved = await send("/judgments", { run_id: run.id, winner: d.winner, scores: d.scores, note: d.note })
  EP.cmp.runs = EP.cmp.runs.map(replaceRun.bind(null, saved))
  EP.cmp.dirty = false
  await loadStats()
  toast(d.winner ? `Saved ✓ · winner ${d.winner}` : "Saved ✓")
}

function replaceRun(saved, run) { return run.id === saved.id ? saved : run }

function nextUnjudged() {
  const runs = shownRuns()
  const after = runs.findIndex(isAfterUnjudged.bind(null, EP.cmp.sel))
  return after >= 0 ? after : Math.min(EP.cmp.sel + 1, runs.length - 1)
}

function isAfterUnjudged(sel, run, i) { return i > sel && isUnjudged(run) }

function saveCompareNext() {
  return saveCompare().then(advanceCompare).catch(fail)
}

function advanceCompare() { cmpSelect(EP.cmp.unjudged ? EP.cmp.sel : nextUnjudged()) }

function renderCompare() {
  const run = cmpRun()
  EP.els.body.replaceChildren(cmpRailEl(), h("div", { class: "ep-main" }, cmpStageEl(run), run ? compareBarEl() : null))
}

/* why: Leaderboard tab: one row per model across the runs in range */

async function loadBoard() { EP.board = (await call("/leaderboard" + query({}))).rows }

const BOARD_COLS = [
  ["Model", boardModel], ["Answers", boardAnswers], ["Wins", boardWins], ["Win %", boardWinRate], ["Ties", boardTies],
  ["Avg ★", boardScore], ["Errors", boardErrors], ["Avg latency", boardLatency], ["Cost", boardCost],
]

function boardModel(r) { return r.model }
function boardAnswers(r) { return String(r.answers) }
function boardWins(r) { return `${r.wins}/${r.contests}` }
function boardWinRate(r) { return pct(r.win_rate) }
function boardTies(r) { return String(r.ties) }
function boardScore(r) { return num(r.avg_score, 1) }
function boardErrors(r) { return String(r.errors) }
function boardLatency(r) { return secs(r.avg_latency_ms) }
function boardCost(r) { return usd(r.cost_usd) }
function headCell(col) { return h("th", { text: col[0] }) }
function cell(row, col) { return h("td", { text: col[1](row) }) }
function boardRow(row) { return h("tr", {}, BOARD_COLS.map(cell.bind(null, row))) }

function renderBoard() {
  const empty = EP.board.length ? null : h("div", { class: "ep-empty", text: "No runs in this range yet. Run /eval in Hermes." })
  const table = EP.board.length ? h("table", { class: "ep-table" }, h("thead", {}, h("tr", {}, BOARD_COLS.map(headCell))),
    h("tbody", {}, EP.board.map(boardRow))) : null
  const note = h("p", { class: "ep-hint", text: "Win % counts runs with 2+ answers and a picked winner. ★ = your 1-5 scores." })
  EP.els.body.replaceChildren(h("div", { class: "ep-board" }, h("div", { class: "ep-scroll" }, table), empty, note))
}

const RENDERERS = { review: renderReview, compare: renderCompare, board: renderBoard }

function scrollFocus() {
  const rail = EP.els.body.querySelector(".ep-turn.on")
  const now = EP.els.body.querySelector(".ep-now")
  if (rail && rail.scrollIntoView) rail.scrollIntoView({ block: "nearest" })
  if (now && now.scrollIntoView) now.scrollIntoView({ block: "start" })
}

function render() {
  renderHead()
  EP.els.body.className = "ep-body tab-" + EP.tab
  if (!EP.draft) EP.draft = emptyDraft()
  RENDERERS[EP.tab]()
}

/* why: keys differ per tab; one table each */

function isTyping(e) { return /^(INPUT|TEXTAREA|SELECT)$/.test(e.target.tagName || "") }
function hasModifier(e) { return e.metaKey || e.ctrlKey || e.altKey }
function isSaveCombo(e) { return (e.metaKey || e.ctrlKey) && e.key === "Enter" }
function nextTurn(e) { e.preventDefault(); select(EP.sel + 1) }
function prevTurn(e) { e.preventDefault(); select(EP.sel - 1) }
function scoreKey(e) { toggleScore(Number(e.key)) }
function nextRun(e) { e.preventDefault(); cmpSelect(EP.cmp.sel + 1) }
function prevRun(e) { e.preventDefault(); cmpSelect(EP.cmp.sel - 1) }

function moveFocus(step, e) {
  const run = cmpRun()
  if (!run) return
  e.preventDefault()
  EP.cmp.focus = (EP.cmp.focus + step + run.answers.length) % run.answers.length
  swap(".ep-cgrid", gridEl(run))
}

function colScoreKey(e) {
  const run = cmpRun()
  if (run) setColScore(run.answers[EP.cmp.focus].label, Number(e.key))
}

function winnerKey(e) {
  const run = cmpRun()
  const label = e.key.toUpperCase()
  if (run && run.answers.some(hasLabel.bind(null, label))) setWinner(label)
}

const KEYMAPS = {
  review: {
    j: nextTurn, ArrowDown: nextTurn, k: prevTurn, ArrowUp: prevTurn,
    p: toggleVerdict.bind(null, "pass"), f: toggleVerdict.bind(null, "fail"),
    1: scoreKey, 2: scoreKey, 3: scoreKey, 4: scoreKey, 5: scoreKey,
  },
  compare: {
    j: nextRun, ArrowDown: nextRun, k: prevRun, ArrowUp: prevRun, ArrowLeft: moveFocus.bind(null, -1),
    ArrowRight: moveFocus.bind(null, 1), t: setWinner.bind(null, "tie"), n: setWinner.bind(null, "none"),
    a: winnerKey, b: winnerKey, c: winnerKey, d: winnerKey, e: winnerKey,
    1: colScoreKey, 2: colScoreKey, 3: colScoreKey, 4: colScoreKey, 5: colScoreKey,
  },
  board: {},
}

const SAVERS = { review: onSaveClick, compare: saveCompareNext, board: ignore }

function onKey(e) {
  if (isSaveCombo(e)) { e.preventDefault(); SAVERS[EP.tab](); return }
  if (isTyping(e) || hasModifier(e)) return
  const handler = KEYMAPS[EP.tab][e.key]
  if (handler) handler(e)
}

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
  renderCount()
  await openSession(latest.id, true)
}

async function pollCompare() {
  if (EP.cmp.dirty) return
  const before = EP.cmp.runs.length
  const runs = (await call("/runs" + query({ multi: "1" }))).runs
  if (runs.length === before) return
  await loadCompare()
  renderFilters()
  render()
}

const POLLERS = { review: pollReview, compare: pollCompare, board: ignore }

async function poll() {
  if (!EP.root.isConnected) { document.removeEventListener("keydown", onKey); return }
  await Promise.resolve(POLLERS[EP.tab]()).catch(ignore)
  EP.pollTimer = setTimeout(poll, 3000)
}

function showBootError(e) {
  EP.els.body.replaceChildren(h("div", { class: "ep-empty", text: "⚠ " + pick(e.message, e) }))
}

async function load() {
  await loadSessions()
  await loadStats()
  renderFilters()
  if (EP.sessions.length) return openSession(EP.sessions[0].id, true)
  return render()
}

async function boot() {
  renderHead()
  EP.els.body.replaceChildren(h("div", { class: "ep-empty", text: "Loading…" }))
  await load().catch(showBootError)
  EP.pollTimer = setTimeout(poll, 3000)
}

function buildShell(root) {
  root.classList.add("quickeval")
  EP.els = { head: h("header", { class: "ep-head" }), filters: h("div", { class: "ep-filters" }),
    body: h("div", { class: "ep-body" }), toast: h("div", { class: "ep-toast" }) }
  root.replaceChildren(EP.els.head, EP.els.filters, EP.els.body, EP.els.toast)
}

function mount(root, opts) {
  clearTimeout(EP.pollTimer)
  Object.assign(EP, freshState(), { root, api: opts.apiBase.replace(/\/$/, ""), fetchJSON: opts.fetchJSON || null })
  buildShell(root)
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
  if (!window.__HERMES_PLUGIN_SDK__ || !window.__HERMES_PLUGINS__) return
  window.__HERMES_PLUGINS__.register("quick-eval", QuickEvalPage)
}

window.QuickEvalUI = { mount }
registerDashboard()
