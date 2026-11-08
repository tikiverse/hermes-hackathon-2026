/* Quick Eval UI: framework-free, one file. Runs standalone via QuickEvalUI.mount and auto-registers as a Hermes dashboard tab. */
"use strict"

const TAGS = ["wrong", "hallucination", "refusal", "censored", "too-long", "great", "style"]
const SCORES = [1, 2, 3, 4, 5]
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
    evals: {}, stats: {}, presets: [], preset: "", customModel: "", live: true, view: "chat", tab: "review",
    compare: false, runs: [], draft: null, dirty: false, toast: "", busy: "", saved: [], lastMsgCount: 0, toastTimer: null,
    pollTimer: null,
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
  el.append(...kids.flat(2).filter(isKid).map(toNode))
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

async function loadRuns() { EP.runs = (await call(`/runs?session_id=${encodeURIComponent(EP.sessionId)}`)).runs }

async function openSession(id, selectLast) {
  EP.sessionId = id
  const r = await call(`/sessions/${encodeURIComponent(id)}/turns`)
  EP.session = r.session
  EP.turns = r.turns
  EP.lastMsgCount = messageCountOf(id)
  await loadEvals()
  await loadRuns()
  select(selectLast ? EP.turns.length - 1 : EP.sel)
}

function samePrompt(t, run) { return (run.prompt || "").trim() === (t.prompt || "").trim() }

function runFor(t) {
  const runs = EP.runs.filter(samePrompt.bind(null, t))
  return runs[runs.length - 1] || null
}

function turnRun() { const t = turn(); return t ? runFor(t) : null }
function runWinner(run) { return run && run.score ? run.score.winner : null }

function emptyDraft() { return { verdict: null, score: null, tags: [], notes: "", expected: "", comparisons: [] } }

function draftFrom(ex) {
  return {
    verdict: ex.verdict, score: ex.score, tags: [...pick(ex.tags, [])], notes: pick(ex.notes, ""),
    expected: pick(ex.expected, ""), comparisons: pick(ex.comparisons, []),
  }
}

function turn() { return EP.turns[EP.sel] }
function modelName() { return pick(EP.session && EP.session.model, "model") }

function select(i) {
  EP.sel = Math.max(0, Math.min(i, EP.turns.length - 1))
  const t = turn()
  const ex = t && EP.evals[t.message_id]
  EP.draft = ex ? draftFrom(ex) : emptyDraft()
  EP.draft.winner = runWinner(turnRun())
  EP.compare = !!turnRun()
  EP.dirty = false
  render()
}

function swap(selector, node) {
  const old = EP.els.body.querySelector(selector)
  if (old) old.replaceWith(node)
}

function renderBarInto() { swap(".ep-bar", barEl()) }
function renderStageInto() { swap(".ep-stage", stageEl()) }

function patch(p) {
  Object.assign(EP.draft, p)
  EP.dirty = true
  renderBarInto()
}

function evalBody(t) {
  return {
    session_id: EP.sessionId, message_id: t.message_id, turn_index: t.index, model: EP.session && EP.session.model,
    prompt: t.prompt, response: t.response, ...EP.draft,
  }
}

async function saveWinner() {
  const run = turnRun()
  const winner = EP.draft.winner
  if (!run || !winner || winner === runWinner(run)) return
  await send("POST", "/scores", { eval_id: run.id, winner, note: EP.draft.notes })
  await loadRuns()
}

async function persist(t) {
  const winner = EP.draft.winner
  const saved = await send("POST", "/evals", evalBody(t))
  EP.evals[t.message_id] = saved
  t.evaluated = true
  await saveWinner()
  EP.dirty = false
  await loadEvals()
  toast(winner ? `Saved ✓ · winner ${winner}` : "Saved ✓")
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
  renderStageInto()
  await send("POST", "/compare", compareBody(t, model)).then(addComparison).catch(fail)
  EP.busy = ""
  renderStageInto()
}

function toggleCompare() { EP.compare = !EP.compare; renderStageInto() }
function afterRemove() { toast("Deleted"); render() }

function remove(id) {
  return call("/evals/" + id, { method: "DELETE" }).then(loadEvals).then(afterRemove).catch(fail)
}

function kbd(key) { return h("kbd", { text: key }) }
function grow() { return h("span", { class: "ep-grow" }) }

function sessionLabel(s) {
  const parts = [clip(pick(s.title, s.id), 46), pick(s.model, "?"), ago(pick(s.last_activity_at, s.started_at))]
  if (s.eval_count) parts.push(s.eval_count + " ✓")
  return parts.join(" · ")
}

function sessionOption(s) { return h("option", { value: s.id, selected: s.id === EP.sessionId }, sessionLabel(s)) }
function onSessionChange(e) { openSession(e.target.value, true).catch(fail) }
function onLiveChange(e) { EP.live = e.target.checked }

function sessionSelect() {
  return h("select", { class: "ep-session", "aria-label": "Session", onchange: onSessionChange }, EP.sessions.map(sessionOption))
}

function liveEl() {
  return h("label", { class: "ep-live", title: "follow the newest Hermes turn" },
    h("input", { type: "checkbox", checked: EP.live, onchange: onLiveChange }), "live")
}

function setTab(t) { EP.tab = t; render() }
function tabLabel(t) { return t === "review" ? "Review" : `Saved ${pick(EP.stats.total, 0)}` }

function tabButton(t) {
  return h("button", { class: "ep-segb" + onClass(EP.tab === t), onclick: setTab.bind(null, t) }, tabLabel(t))
}

function tabsEl() { return h("div", { class: "ep-seg" }, ["review", "saved"].map(tabButton)) }
function passText(st) { return st.pass_rate == null ? "pass –" : `pass ${Math.round(st.pass_rate * 100)}%` }
function avgText(st) { return st.avg_score == null ? "avg –" : `avg ${st.avg_score.toFixed(1)}` }
function metaEl() { return h("span", { class: "ep-meta", text: `${passText(EP.stats)} · ${avgText(EP.stats)}` }) }

function exportEl() {
  return h("a", { class: "ep-btn ep-wide", href: EP.api + "/export", download: "evals.jsonl", text: "Export JSONL" })
}

function renderHead() {
  EP.els.head.replaceChildren(h("span", { class: "ep-brand", text: "Quick Eval" }), sessionSelect(), liveEl(), grow(),
    metaEl(), tabsEl(), exportEl())
}

function turnDot(t) {
  const e = EP.evals[t.message_id]
  return h("i", { class: "ep-dot " + (e ? pick(e.verdict, "none") : "") })
}

function turnButton(t, i) {
  const prompt = pick(clip(oneLine(t.prompt), 70), "(empty)")
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

function markPreferred(i, c, j) { c.preferred = j === i }

function setPreferred(i) {
  EP.draft.comparisons.forEach(markPreferred.bind(null, i))
  EP.dirty = true
  renderStageInto()
}

function removeComparison(i) {
  EP.draft.comparisons.splice(i, 1)
  EP.dirty = true
  renderStageInto()
}

function preferEl(on, i) {
  return h("label", { class: "ep-pref" },
    h("input", { type: "radio", name: "ep-pref", checked: on, onchange: setPreferred.bind(null, i) }), "Prefer")
}

function colEl(head, text, foot) {
  return h("div", { class: "ep-col" }, h("div", { class: "ep-col-h" }, head),
    h("div", { class: "ep-col-b ep-text", text: pick(text, "(no text response)") }), h("div", { class: "ep-col-f" }, foot))
}

function noneSelected() { return !EP.draft.comparisons.some(isPreferred) }
function isPreferred(c) { return !!c.preferred }

function originalCol(t) {
  return colEl([h("b", { text: modelName() }), "original"], t.response, preferEl(noneSelected(), -1))
}

function compareCol(c, i) {
  const remover = h("button", { class: "ep-btn sm", onclick: removeComparison.bind(null, i) }, "remove")
  return colEl([h("b", { text: pick(c.label, c.model) }), `${c.latency_ms} ms`], c.response,
    [preferEl(!!c.preferred, i), grow(), remover])
}

function onPresetChange(e) { EP.preset = e.target.value; EP.customModel = "" }
function onCustomModel(e) { EP.customModel = e.target.value }

function presetOption(p) {
  const label = p.label + (p.has_key ? "" : " (no key)")
  return h("option", { value: p.label, selected: p.label === EP.preset }, label)
}

function presetSelect() {
  return h("select", { class: "ep-input", "aria-label": "Compare model", onchange: onPresetChange },
    h("option", { value: "" }, "pick a model…"), EP.presets.map(presetOption))
}

function pickerCol() {
  const model = h("input", { class: "ep-input", placeholder: "or any model id", value: EP.customModel, oninput: onCustomModel })
  const run = h("button", { class: "ep-btn pri", disabled: !!EP.busy, onclick: runCompare }, EP.busy ? "Running…" : "Run")
  const hint = h("p", { class: "ep-hint", text: "Or type /eval in Hermes: your quick-eval models answer and show up here." })
  return h("div", { class: "ep-col ep-picker" }, h("div", { class: "ep-col-h" }, h("b", { text: "Same prompt, other model" })),
    h("div", { class: "ep-col-b" }, presetSelect(), model, run, hint))
}

function setWinner(label) {
  EP.draft.winner = label
  EP.dirty = true
  renderStageInto()
  renderBarInto()
}

function winnerEl(label, text) {
  return h("label", { class: "ep-pref" }, h("input", { type: "radio", name: "ep-win", checked: EP.draft.winner === label,
    onchange: setWinner.bind(null, label) }), text)
}

function labelChip(label) { return h("span", { class: "ep-label", text: label }) }
function isRerun(a) { return a.source !== "original" }
function answerText(a) { return a.error ? "⚠ " + a.error : a.text }

function answerCol(a) {
  return colEl([labelChip(a.label), h("b", { text: pick(a.model, a.alias) }), `${a.latency_ms} ms`], answerText(a),
    winnerEl(a.label, "Winner"))
}

function runCols(t, run) {
  const original = colEl([labelChip("A"), h("b", { text: modelName() }), "original"], t.response, winnerEl("A", "Winner"))
  return [original, run.answers.filter(isRerun).map(answerCol)]
}

function tieRow() {
  return h("div", { class: "ep-tie" }, "Neither?", winnerEl("tie", "Tie"), winnerEl("none", "No good answer"))
}

function splitEl(t) {
  const run = runFor(t)
  const cols = run ? runCols(t, run) : originalCol(t)
  return [h("div", { class: "ep-split" }, cols, EP.draft.comparisons.map(compareCol), pickerCol()), run ? tieRow() : null]
}

function replyEl(t) {
  if (EP.compare) return splitEl(t)
  return bubble("asst", modelName(), "", pick(t.response, "(no text response)"))
}

function focusEl(t) {
  return h("section", { class: "ep-now", "aria-label": "Turn under review" },
    h("span", { class: "ep-now-label", text: `TURN ${t.index + 1} · reviewing · ${ago(t.ts)}` }),
    bubble("user", "You", "", t.prompt), chipsEl(t), reasoningEl(t), replyEl(t), expectedEl())
}

function turnEl(t, i) { return i === EP.sel ? focusEl(t) : pastEl(t, i) }
function setView(v) { EP.view = v; renderStageInto() }

function viewButton(v) {
  return h("button", { class: "ep-segb" + onClass(EP.view === v), onclick: setView.bind(null, v) }, v === "chat" ? "Chat" : "JSON")
}

function toolbarEl() {
  const cmp = h("button", { class: "ep-segb" + onClass(EP.compare), onclick: toggleCompare }, "Compare", kbd("c"))
  return h("div", { class: "ep-toolbar" }, h("div", { class: "ep-seg" }, ["chat", "json"].map(viewButton)), grow(),
    h("div", { class: "ep-seg" }, cmp))
}

function threadEl(t) {
  if (EP.view === "json") return jsonView({ session: EP.session, turn: t, draft: EP.draft })
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

function saveButton() {
  const dirty = EP.dirty ? h("span", { class: "ep-unsaved", title: "unsaved" }) : null
  return h("button", { class: "ep-btn pri", onclick: onSaveClick }, dirty, "Save & next", kbd("⌘↵"))
}

function barEl() {
  const note = h("input", { class: "ep-input ep-note", placeholder: "Note: why?", "aria-label": "Note",
    value: EP.draft.notes, oninput: onField.bind(null, "notes") })
  return h("footer", { class: "ep-bar", "aria-label": "Annotate turn" }, h("div", { class: "ep-bar-in" },
    h("div", { class: "ep-seg" }, verdictButton("pass", "Pass", "p"), verdictButton("fail", "Fail", "f")),
    h("div", { class: "ep-seg" }, SCORES.map(scoreButton)), h("div", { class: "ep-tags" }, TAGS.map(tagButton)), note, saveButton()))
}

function savedTag(t) { return h("span", { class: "ep-tag on", text: t }) }

function savedTags(e) {
  const tags = pick(e.tags, [])
  return tags.length ? h("div", { class: "ep-tags" }, tags.map(savedTag)) : null
}

function savedHead(e) {
  const score = e.score ? h("b", { class: "ep-meta", text: `${e.score}/5` }) : null
  return h("div", { class: "ep-col-h" },
    h("span", { class: "ep-badge " + pick(e.verdict, "none"), text: pick(e.verdict, "unrated") }), score,
    h("span", { text: `${pick(e.model, "")} · ${ago(e.ts)}` }), grow(),
    h("button", { class: "ep-btn sm", onclick: remove.bind(null, e.id) }, "delete"))
}

function savedCard(e) {
  return h("section", { class: "ep-col" }, savedHead(e),
    h("div", { class: "ep-col-b" }, h("div", { class: "ep-text", text: clip(e.prompt, 300) }), savedTags(e),
      h("details", { class: "ep-fold" }, h("summary", { text: "JSON" }), jsonView(e))))
}

function renderSaved() {
  const text = "No evals saved yet. Grade a turn in Review, or type /eval in Hermes."
  const empty = EP.saved.length ? null : h("div", { class: "ep-empty", text })
  return h("div", { class: "ep-saved" }, empty, EP.saved.map(savedCard))
}

function scrollFocus() {
  const rail = EP.els.body.querySelector(".ep-turn.on")
  const now = EP.els.body.querySelector(".ep-now")
  if (rail && rail.scrollIntoView) rail.scrollIntoView({ block: "nearest" })
  if (now && now.scrollIntoView) now.scrollIntoView({ block: "start" })
}

function render() {
  renderHead()
  EP.els.body.classList.toggle("saved", EP.tab === "saved")
  if (EP.tab === "saved") { EP.els.body.replaceChildren(renderSaved()); return }
  if (!EP.draft) EP.draft = emptyDraft()
  const bar = turn() ? barEl() : null
  EP.els.body.replaceChildren(railEl(), h("div", { class: "ep-main" }, stageEl(), bar))
  scrollFocus()
}

function isTyping(e) { return /^(INPUT|TEXTAREA|SELECT)$/.test(e.target.tagName || "") }
function hasModifier(e) { return e.metaKey || e.ctrlKey || e.altKey }
function isSaveCombo(e) { return (e.metaKey || e.ctrlKey) && e.key === "Enter" }
function keysActive(e) { return !isTyping(e) && !hasModifier(e) && EP.tab === "review" && !!turn() }
function nextTurn(e) { e.preventDefault(); select(EP.sel + 1) }
function prevTurn(e) { e.preventDefault(); select(EP.sel - 1) }
function scoreKey(e) { toggleScore(Number(e.key)) }

const KEYMAP = {
  j: nextTurn, ArrowDown: nextTurn, k: prevTurn, ArrowUp: prevTurn, c: toggleCompare,
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

async function refreshRuns() {
  if (EP.dirty || !EP.sessionId) return
  const before = EP.runs.length
  await loadRuns()
  if (EP.runs.length !== before) select(EP.sel)
}

async function pollOnce() {
  if (!EP.live || EP.tab !== "review") return
  const { latest } = await call("/latest")
  if (!shouldFollow(latest)) return refreshRuns()
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
  root.classList.add("quickeval")
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
  if (ref.current) mount(ref.current, { apiBase: "/api/plugins/quick-eval-ui", fetchJSON: sdk.fetchJSON })
}

function QuickEvalPage() {
  const sdk = window.__HERMES_PLUGIN_SDK__
  const ref = sdk.React.useRef(null)
  sdk.React.useEffect(mountInto.bind(null, ref, sdk), [])
  return sdk.React.createElement("div", { ref })
}

function registerDashboard() {
  if (!window.__HERMES_PLUGIN_SDK__ || !window.__HERMES_PLUGINS__) return
  window.__HERMES_PLUGINS__.register("quick-eval-ui", QuickEvalPage)
}

window.QuickEvalUI = { mount }
registerDashboard()
