/* why: Hermes Desktop half: a Quick Eval page + sidebar row. It shows the same UI as the dashboard tab inside the
   SDK's sandboxed frame; the frame has no network, so its API calls arrive here and go out through ctx.rest. */
import { ROUTES_AREA, SIDEBAR_NAV_AREA, SandboxedFrame, host } from "@hermes/plugin-sdk"
import { useEffect, useRef, useState } from "react"
import { jsx } from "react/jsx-runtime"

const PATH = "/quick-eval"
const OPEN_EVENT = "plugin.quick-eval.open"
const FRAME_STYLE = { width: "100%", height: "100%", border: 0, display: "block" }
const NOTE_STYLE = { padding: 16 }
const PLUGIN = { ctx: null }

function addByte(acc, b) { return acc + String.fromCharCode(b) }

function dataUrl(html) {
  return "data:text/html;charset=utf-8;base64," + btoa(new TextEncoder().encode(html).reduce(addByte, ""))
}

function reply(source, id, result) { source.postMessage({ type: "quickeval-rpc-reply", id, ...result }, "*") }
function replyOk(source, id, data) { reply(source, id, { ok: true, data }) }
function replyErr(source, id, err) { reply(source, id, { ok: false, error: String((err && err.message) || err) }) }

function isFromFrame(frame, event) {
  const m = event.data
  return !!m && m.type === "quickeval-rpc" && !!frame.current && event.source === frame.current.contentWindow
}

function restOptions(m) { return m.method === "GET" ? {} : { method: m.method, body: m.body } }

function forward(frame, event) {
  if (!isFromFrame(frame, event)) return
  const m = event.data
  PLUGIN.ctx.rest(m.path, restOptions(m))
    .then(replyOk.bind(null, event.source, m.id))
    .catch(replyErr.bind(null, event.source, m.id))
}

function showFrame(setSrc, r) { setSrc(dataUrl(r.html)) }
function showError(setError, e) { setError(String(e)) }

function loadFrame(setSrc, setError) {
  PLUGIN.ctx.rest("/frame").then(showFrame.bind(null, setSrc)).catch(showError.bind(null, setError))
}

function listen(frame) { return PLUGIN.ctx.addEventListener(window, "message", forward.bind(null, frame)) }

function note(text) { return jsx("div", { style: NOTE_STYLE, children: text }) }

function QuickEvalPage() {
  const frame = useRef(null)
  const [src, setSrc] = useState(null)
  const [error, setError] = useState(null)
  useEffect(loadFrame.bind(null, setSrc, setError), [])
  useEffect(listen.bind(null, frame), [])
  if (error) return note("Quick Eval backend unavailable: " + error)
  if (!src) return note("Loading Quick Eval…")
  return jsx(SandboxedFrame, { ref: frame, src, title: "Quick Eval", style: FRAME_STYLE })
}

function renderPage() { return jsx(QuickEvalPage, {}) }

function showPage() { host.navigate(PATH) }

function register(ctx) {
  PLUGIN.ctx = ctx
  // why: /quick-eval open in a Desktop chat emits this event (open_in_desktop in __init__.py) instead of opening a browser
  ctx.onEvent(OPEN_EVENT, showPage)
  ctx.registerMany([
    { id: "page", area: ROUTES_AREA, data: { path: PATH }, render: renderPage },
    { id: "nav", area: SIDEBAR_NAV_AREA, data: { path: PATH, label: "Quick Eval", codicon: "checklist" } },
  ])
}

export default { id: "quick-eval", name: "Quick Eval", register }
