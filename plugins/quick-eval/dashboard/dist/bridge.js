/* why: inside Hermes Desktop the UI runs in a sandboxed frame with no network; its API calls go to the parent page,
   which forwards them to this plugin's backend with ctx.rest. */
const QE_PENDING = new Map()
let qeNext = 0

function isReply(m) { return !!m && m.type === "quickeval-rpc-reply" && QE_PENDING.has(m.id) }

function finish(waiter, m) {
  if (m.ok) waiter.resolve(m.data)
  else waiter.reject(new Error(m.error || "request failed"))
}

function settle(event) {
  if (!isReply(event.data)) return
  const waiter = QE_PENDING.get(event.data.id)
  QE_PENDING.delete(event.data.id)
  finish(waiter, event.data)
}

function ask(message, resolve, reject) {
  QE_PENDING.set(message.id, { resolve, reject })
  parent.postMessage(message, "*")
}

function rpc(path, init) {
  const options = init || {}
  qeNext += 1
  const body = options.body ? JSON.parse(options.body) : undefined
  const message = { type: "quickeval-rpc", id: qeNext, path, method: options.method || "GET", body }
  return new Promise(ask.bind(null, message))
}

window.addEventListener("message", settle)
window.QuickEvalUI.mount(document.getElementById("root"), { apiBase: "", fetchJSON: rpc, noExport: true })
