/* Evalpad UI: framework-free, one file. Runs standalone via EvalpadUI.mount and auto-registers as a Hermes dashboard tab. */
"use strict"

const TAGS = ["wrong", "hallucination", "refusal", "censored", "too-long", "great", "style"]
const AGO_STEPS = [
  { lt: 3600, div: 60, suffix: "m ago" },
  { lt: 86400, div: 3600, suffix: "h ago" },
  { lt: Infinity, div: 86400, suffix: "d ago" },
]
const SETTERS = { class: setClass, text: setText, value: setValue }
const EP = freshState()

function freshState() {
  return {
    root: null, api: "", fetchJSON: null, els: {}, sessions: [], sessionId: null, session: null, turns: [], sel: 0,
    evals: {}, stats: {}, presets: [], preset: "", customModel: "", live: true, view: "turn", tab: "review",
    draft: null, dirty: false, toast: "", busy: "", saved: [], lastMsgCount: 0, toastTimer: null, pollTimer: null,
  }
}

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
  el.append(...kids.flat().filter(isKid).map(toNode))
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

function send(method, path, body) {
  return call(path, { method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) })
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

async function loadSessions() { EP.sessions = (await call("/sessions?limit=100")).sessions }
function inCurrentSession(e) { return e.session_id === EP.sessionId && !!e.message_id }
function indexEval(e) { EP.evals[e.message_id] = e }

async function loadEvals() {
  const r = await call("/evals")
  EP.saved = r.evals
  EP.stats = r.stats
  EP.evals = {}
  r.evals.filter(inCurrentSession).forEach(indexEval)
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
  await loadEvals()
  select(selectLast ? EP.turns.length - 1 : EP.sel)
}

function emptyDraft() { return { verdict: null, score: null, tags: [], notes: "", expected: "", comparisons: [] } }

function draftFrom(ex) {
  return {
    verdict: ex.verdict, score: ex.score, tags: [...pick(ex.tags, [])], notes: pick(ex.notes, ""),
    expected: pick(ex.expected, ""), comparisons: pick(ex.comparisons, []),
  }
}

function turn() { return EP.turns[EP.sel] }

function select(i) {
  EP.sel = Math.max(0, Math.min(i, EP.turns.length - 1))
  const t = turn()
  const ex = t && EP.evals[t.message_id]
  EP.draft = ex ? draftFrom(ex) : emptyDraft()
  EP.dirty = false
  render()
}

function patch(p) {
  Object.assign(EP.draft, p)
  EP.dirty = true
  renderPanel()
  renderHead()
}

function evalBody(t) {
  return {
    session_id: EP.sessionId, message_id: t.message_id, turn_index: t.index, model: EP.session && EP.session.model,
    prompt: t.prompt, response: t.response, ...EP.draft,
  }
}

async function persist(t) {
  const saved = await send("POST", "/evals", evalBody(t))
  EP.evals[t.message_id] = saved
  t.evaluated = true
  EP.dirty = false
  await loadEvals()
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
function firstBaseUrl() { const p = EP.presets[0]; return p ? p.base_url : undefined }

function compareBody(t, model) {
  const body = { prompt: t.prompt }
  if (model) return { ...body, model, base_url: firstBaseUrl() }
  return { ...body, preset: EP.preset }
}

function addComparison(r) {
  EP.draft.comparisons = [...EP.draft.comparisons, r]
  EP.dirty = true
}

async function runCompare() {
  const t = turn()
  if (!t) return
  const model = EP.customModel.trim()
  if (!model && !EP.preset) { toast("Pick a model to compare with"); return }
  EP.busy = "compare"
  renderDetailInto()
  await send("POST", "/compare", compareBody(t, model)).then(addComparison).catch(fail)
  EP.busy = ""
  render()
}

function afterRemove() { toast("Deleted"); render() }

function remove(id) {
  return call("/evals/" + id, { method: "DELETE" }).then(loadEvals).then(afterRemove).catch(fail)
}

function brandEl() {
  return h("div", { class: "ep-brand" }, h("b", { text: "Evalpad" }),
    h("span", { class: "ep-sub", text: "evals from live Hermes chats" }))
}

function sessionLabel(s) {
  const parts = [clip(pick(s.title, s.id), 46), pick(s.model, "?"), ago(pick(s.last_activity_at, s.started_at))]
  if (s.eval_count) parts.push(s.eval_count + " ✓")
  return parts.join(" · ")
}

function sessionOption(s) { return h("option", { value: s.id, selected: s.id === EP.sessionId }, sessionLabel(s)) }
function onSessionChange(e) { openSession(e.target.value, true).catch(fail) }
function onLiveChange(e) { EP.live = e.target.checked }

function sessionSelect() {
  return h("select", { class: "ep-select", onchange: onSessionChange }, EP.sessions.map(sessionOption))
}

function liveEl() {
  return h("label", { class: "ep-live" },
    h("input", { type: "checkbox", checked: EP.live, onchange: onLiveChange }), " follow latest")
}

function setTab(t) { EP.tab = t; render() }
function tabLabel(t) { return t === "review" ? "Review" : `Saved (${pick(EP.stats.total, 0)})` }

function tabButton(t) {
  const on = EP.tab === t ? " on" : ""
  return h("button", { class: "ep-tab" + on, onclick: setTab.bind(null, t) }, tabLabel(t))
}

function tabsEl() { return h("div", { class: "ep-tabs" }, ["review", "saved"].map(tabButton)) }
function passText(st) { return st.pass_rate == null ? "pass –" : `pass ${Math.round(st.pass_rate * 100)}%` }
function avgText(st) { return st.avg_score == null ? "avg –" : `avg ${st.avg_score.toFixed(1)}` }

function statsEl() {
  return h("div", { class: "ep-stats" }, h("span", { text: passText(EP.stats) }), h("span", { text: avgText(EP.stats) }))
}

function exportEl() {
  return h("a", { class: "ep-btn", href: EP.api + "/export", download: "evals.jsonl", text: "Export JSONL" })
}

function renderHead() {
  EP.els.head.replaceChildren(brandEl(), sessionSelect(), liveEl(), tabsEl(), statsEl(), exportEl())
}

function turnDot(t) {
  const e = EP.evals[t.message_id]
  return e ? h("span", { class: "ep-dot " + pick(e.verdict, "none"), title: "evaluated" }) : null
}

function turnButton(t, i) {
  const on = i === EP.sel ? " on" : ""
  const prompt = clip(t.prompt.replace(/\s+/g, " "), 70)
  return h("button", { class: "ep-turn" + on, onclick: select.bind(null, i) },
    h("span", { class: "ep-tn", text: "#" + (i + 1) }), h("span", { class: "ep-tp", text: pick(prompt, "(empty)") }), turnDot(t))
}

function renderTurns() {
  const kids = EP.turns.map(turnButton)
  if (!EP.turns.length) kids.push(h("div", { class: "ep-empty", text: "No turns in this session." }))
  return h("nav", { class: "ep-turns" }, kids)
}

function responseCard(title, sub, text, extra) {
  return h("section", { class: "ep-card" },
    h("div", { class: "ep-ct" }, h("b", { text: title }), h("span", { class: "ep-sub", text: sub })),
    h("div", { class: "ep-text", text: pick(text, "(no text response)") }), extra)
}

function toolDetail(tc) {
  return h("details", { class: "ep-tool" }, h("summary", { text: pick(tc.name, "tool") }),
    jsonView({ arguments: tc.arguments, result: tc.result }))
}

function toolsCard(t) {
  if (!t.tools.length) return null
  return h("section", { class: "ep-card" },
    h("div", { class: "ep-ct" }, h("b", { text: `Tool calls (${t.tools.length})` })), t.tools.map(toolDetail))
}

function togglePreferred(c) {
  c.preferred = !c.preferred
  EP.dirty = true
  renderDetailInto()
  renderPanel()
}

function removeComparison(i) {
  EP.draft.comparisons.splice(i, 1)
  EP.dirty = true
  renderDetailInto()
}

function preferButton(c) {
  const on = c.preferred ? " on" : ""
  return h("button", { class: "ep-btn sm" + on, onclick: togglePreferred.bind(null, c) },
    c.preferred ? "★ preferred" : "☆ prefer this")
}

function compareBar(c, i) {
  return h("div", { class: "ep-cmpbar" }, preferButton(c),
    h("button", { class: "ep-btn sm", onclick: removeComparison.bind(null, i) }, "remove"))
}

function compareCard(c, i) {
  return responseCard(pick(c.label, c.model), `${c.latency_ms} ms`, c.response, compareBar(c, i))
}

function convoDetail(t) {
  const cmps = EP.draft.comparisons
  const two = cmps.length ? " two" : ""
  return h("div", {}, responseCard("You", ago(t.ts), t.prompt), toolsCard(t),
    h("div", { class: "ep-cmpgrid" + two }, responseCard(pick(EP.session.model, "model"), "original", t.response),
      cmps.map(compareCard)))
}

function jsonDetail(t) { return jsonView({ session: EP.session, turn: t, draft: EP.draft }) }
function setView(v) { EP.view = v; renderDetailInto() }

function viewButton(v) {
  const on = EP.view === v ? "on" : ""
  return h("button", { class: on, onclick: setView.bind(null, v) }, v === "turn" ? "Conversation" : "Raw JSON")
}

function viewToggle() { return h("div", { class: "ep-seg" }, ["turn", "json"].map(viewButton)) }
function onPresetChange(e) { EP.preset = e.target.value; EP.customModel = "" }
function onCustomModel(e) { EP.customModel = e.target.value }

function presetOption(p) {
  const label = p.label + (p.has_key ? "" : " (no key)")
  return h("option", { value: p.label, selected: p.label === EP.preset }, label)
}

function presetSelect() {
  return h("select", { class: "ep-select sm", onchange: onPresetChange },
    h("option", { value: "" }, "compare with…"), EP.presets.map(presetOption))
}

function compareButton() {
  const label = EP.busy ? "Running…" : "Compare (c)"
  return h("button", { class: "ep-btn pri", disabled: !!EP.busy, onclick: runCompare }, label)
}

function compareRow() {
  const model = h("input", { class: "ep-input sm", placeholder: "or model id", value: EP.customModel, oninput: onCustomModel })
  return h("div", { class: "ep-cmprow" }, presetSelect(), model, compareButton())
}

function emptyDetail() {
  const text = "Start a chat with Hermes, then come back. New turns appear here live."
  return h("main", { class: "ep-detail" }, h("div", { class: "ep-empty", text }))
}

function renderDetail() {
  const t = turn()
  if (!t) return emptyDetail()
  const view = EP.view === "json" ? jsonDetail(t) : convoDetail(t)
  return h("main", { class: "ep-detail" }, h("div", { class: "ep-dbar" }, viewToggle(), compareRow()), view)
}

function renderDetailInto() {
  const old = EP.els.body.querySelector(".ep-detail")
  if (old) old.replaceWith(renderDetail())
}

function toggleVerdict(kind) { patch({ verdict: EP.draft.verdict === kind ? null : kind }) }
function toggleScore(n) { patch({ score: EP.draft.score === n ? null : n }) }
function onField(field, e) { EP.draft[field] = e.target.value; EP.dirty = true }
function labelEl(text) { return h("label", { class: "ep-lbl", text }) }

function toggleTag(t) {
  const tags = EP.draft.tags
  patch({ tags: tags.includes(t) ? tags.filter(notEqual.bind(null, t)) : [...tags, t] })
}

function verdictButton(kind, label) {
  const on = EP.draft.verdict === kind ? " on" : ""
  return h("button", { class: `ep-btn v ${kind}${on}`, onclick: toggleVerdict.bind(null, kind) }, label)
}

function verdictRow() {
  return h("div", { class: "ep-verdict" }, verdictButton("pass", "👍 Pass (p)"), verdictButton("fail", "👎 Fail (f)"))
}

function starButton(n) {
  const on = EP.draft.score >= n ? " on" : ""
  return h("button", { class: "ep-star" + on, onclick: toggleScore.bind(null, n), title: `score ${n}`, text: "★" })
}

function starsRow() {
  const score = EP.draft.score ? `${EP.draft.score}/5` : "score 1-5"
  return h("div", { class: "ep-stars" }, [1, 2, 3, 4, 5].map(starButton), h("span", { class: "ep-sub", text: score }))
}

function tagButton(t) {
  const on = EP.draft.tags.includes(t) ? " on" : ""
  return h("button", { class: "ep-tag" + on, onclick: toggleTag.bind(null, t), text: t })
}

function textBox(field, placeholder, rows) {
  return h("textarea", { class: "ep-input", rows, placeholder, value: EP.draft[field], oninput: onField.bind(null, field) })
}

function panelTitle() {
  const unsaved = EP.dirty ? h("span", { class: "ep-sub", text: "unsaved" }) : null
  return h("div", { class: "ep-ct" }, h("b", { text: "Eval this turn" }), unsaved)
}

function panelEl() {
  return h("aside", { class: "ep-panel" }, panelTitle(), verdictRow(), starsRow(),
    h("div", { class: "ep-tagrow" }, TAGS.map(tagButton)),
    labelEl("Expected answer"), textBox("expected", "What a correct reply looks like (optional)", 4),
    labelEl("Notes"), textBox("notes", "Why? (optional)", 3),
    h("button", { class: "ep-btn pri big", onclick: onSaveClick }, "Save eval  ⌘↵"),
    h("div", { class: "ep-keys", text: "j/k move · p/f verdict · 1-5 score · c compare · ⌘↵ save" }))
}

function renderPanel() {
  const panel = panelEl()
  const old = EP.els.body.querySelector(".ep-panel")
  if (old) old.replaceWith(panel)
  return panel
}

function savedTag(t) { return h("span", { class: "ep-tag on", text: t }) }

function savedTags(e) {
  const tags = pick(e.tags, [])
  return tags.length ? h("div", { class: "ep-tagrow" }, tags.map(savedTag)) : null
}

function savedHead(e) {
  const stars = e.score ? h("b", { text: "★".repeat(e.score) }) : null
  return h("div", { class: "ep-ct" },
    h("span", { class: "ep-badge " + pick(e.verdict, "none"), text: pick(e.verdict, "unrated") }), stars,
    h("span", { class: "ep-sub", text: `${pick(e.model, "")} · ${ago(e.ts)}` }), h("span", { class: "ep-grow" }),
    h("button", { class: "ep-btn sm", onclick: remove.bind(null, e.id) }, "delete"))
}

function savedCard(e) {
  return h("section", { class: "ep-card" }, savedHead(e), h("div", { class: "ep-text", text: clip(e.prompt, 300) }),
    savedTags(e), h("details", { class: "ep-tool" }, h("summary", { text: "JSON" }), jsonView(e)))
}

function renderSaved() {
  const text = "No evals saved yet. Score a turn in Review, or type /eval in Hermes."
  const empty = EP.saved.length ? null : h("div", { class: "ep-empty", text })
  return h("div", { class: "ep-saved" }, empty, EP.saved.map(savedCard))
}

function scrollSelected() {
  const on = EP.els.body.querySelector(".ep-turn.on")
  if (on && on.scrollIntoView) on.scrollIntoView({ block: "nearest" })
}

function render() {
  renderHead()
  if (EP.tab === "saved") { EP.els.body.replaceChildren(renderSaved()); return }
  if (!EP.draft) EP.draft = emptyDraft()
  EP.els.body.replaceChildren(renderTurns(), renderDetail(), h("aside", { class: "ep-panel" }))
  renderPanel()
  scrollSelected()
}

function isTyping(e) { return /^(INPUT|TEXTAREA|SELECT)$/.test(e.target.tagName || "") }
function hasModifier(e) { return e.metaKey || e.ctrlKey || e.altKey }
function isSaveCombo(e) { return (e.metaKey || e.ctrlKey) && e.key === "Enter" }
function keysActive(e) { return !isTyping(e) && !hasModifier(e) && EP.tab === "review" && !!EP.draft }
function nextTurn(e) { e.preventDefault(); select(EP.sel + 1) }
function prevTurn(e) { e.preventDefault(); select(EP.sel - 1) }
function scoreKey(e) { toggleScore(Number(e.key)) }

const KEYMAP = {
  j: nextTurn, ArrowDown: nextTurn, k: prevTurn, ArrowUp: prevTurn, c: runCompare,
  p: toggleVerdict.bind(null, "pass"), f: toggleVerdict.bind(null, "fail"),
  1: scoreKey, 2: scoreKey, 3: scoreKey, 4: scoreKey, 5: scoreKey,
}

function onKey(e) {
  if (isSaveCombo(e)) { e.preventDefault(); save(true); return }
  if (!keysActive(e)) return
  const handler = KEYMAP[e.key]
  if (handler) handler(e)
}

function shouldFollow(l) { return !!l && !EP.dirty && (l.id !== EP.sessionId || l.message_count !== EP.lastMsgCount) }

async function pollOnce() {
  if (!EP.live || EP.tab !== "review") return
  const { latest } = await call("/latest")
  if (!shouldFollow(latest)) return
  await loadSessions()
  await openSession(latest.id, true)
}

async function poll() {
  if (!EP.root.isConnected) { document.removeEventListener("keydown", onKey); return }
  await pollOnce().catch(ignore)
  EP.pollTimer = setTimeout(poll, 3000)
}

function showBootError(e) {
  EP.els.body.replaceChildren(h("div", { class: "ep-empty", text: "⚠ " + pick(e.message, e) }))
}

async function load() {
  EP.presets = (await call("/presets")).presets
  await loadSessions()
  if (EP.sessions.length) return openSession(EP.sessions[0].id, true)
  await loadEvals()
  return render()
}

async function boot() {
  renderHead()
  EP.els.body.replaceChildren(h("div", { class: "ep-empty", text: "Loading…" }))
  await load().catch(showBootError)
  EP.pollTimer = setTimeout(poll, 3000)
}

function buildShell(root) {
  root.classList.add("evalpad")
  EP.els = { head: h("header", { class: "ep-head" }), body: h("div", { class: "ep-body" }), toast: h("div", { class: "ep-toast" }) }
  root.replaceChildren(EP.els.head, EP.els.body, EP.els.toast)
}

function mount(root, opts) {
  clearTimeout(EP.pollTimer)
  Object.assign(EP, freshState(), { root, api: opts.apiBase.replace(/\/$/, ""), fetchJSON: opts.fetchJSON || null })
  buildShell(root)
  document.addEventListener("keydown", onKey)
  boot()
}

function mountInto(ref, sdk) {
  if (ref.current) mount(ref.current, { apiBase: "/api/plugins/evalpad", fetchJSON: sdk.fetchJSON })
}

function EvalpadPage() {
  const sdk = window.__HERMES_PLUGIN_SDK__
  const ref = sdk.React.useRef(null)
  sdk.React.useEffect(mountInto.bind(null, ref, sdk), [])
  return sdk.React.createElement("div", { ref })
}

function registerDashboard() {
  if (!window.__HERMES_PLUGIN_SDK__ || !window.__HERMES_PLUGINS__) return
  window.__HERMES_PLUGINS__.register("evalpad", EvalpadPage)
}

window.EvalpadUI = { mount }
registerDashboard()
