/* Evalpad UI: framework-free so the same code runs in the Hermes dashboard and standalone. */
(function () {
  "use strict";

  function h(tag, props, ...kids) {
    const el = document.createElement(tag);
    for (const [k, v] of Object.entries(props || {})) {
      if (v == null || v === false) continue;
      if (k === "class") el.className = v;
      else if (k === "text") el.textContent = v;
      else if (k.startsWith("on")) el.addEventListener(k.slice(2), v);
      else if (k === "value") el.value = v;
      else el.setAttribute(k, v === true ? "" : v);
    }
    for (const kid of kids.flat()) {
      if (kid == null || kid === false) continue;
      el.append(kid.nodeType ? kid : document.createTextNode(String(kid)));
    }
    return el;
  }

  const TAGS = ["wrong", "hallucination", "refusal", "censored", "too-long", "great", "style"];
  const ago = (ts) => {
    if (!ts) return "";
    const s = Math.max(0, Date.now() / 1000 - ts);
    if (s < 60) return "just now";
    if (s < 3600) return Math.floor(s / 60) + "m ago";
    if (s < 86400) return Math.floor(s / 3600) + "h ago";
    return Math.floor(s / 86400) + "d ago";
  };
  const clip = (s, n) => (s && s.length > n ? s.slice(0, n - 1) + "…" : s || "");

  /* ---------- pretty JSON tree ---------- */
  function jsonNode(value, key, depth) {
    const label = key != null ? h("span", { class: "ep-jk", text: key + ": " }) : null;
    if (value && typeof value === "object") {
      const entries = Array.isArray(value) ? value.map((v, i) => [i, v]) : Object.entries(value);
      const open = Array.isArray(value) ? "[" : "{";
      const close = Array.isArray(value) ? "]" : "}";
      if (!entries.length) return h("div", { class: "ep-jrow" }, label, h("span", { class: "ep-jp", text: open + close }));
      const d = h("details", { class: "ep-jd" });
      if (depth < 2) d.open = true;
      d.append(
        h("summary", {}, label, h("span", { class: "ep-jp", text: open }), h("span", { class: "ep-jc", text: ` ${entries.length} ${Array.isArray(value) ? "items" : "keys"} ${close}` })),
        h("div", { class: "ep-jkids" }, entries.map(([k, v]) => jsonNode(v, k, depth + 1)))
      );
      return d;
    }
    let cls = "ep-js", text = JSON.stringify(value);
    if (typeof value === "number") cls = "ep-jn";
    else if (typeof value === "boolean") cls = "ep-jb";
    else if (value === null) { cls = "ep-jb"; text = "null"; }
    else if (typeof value === "string") text = value.includes("\n") || value.length > 120 ? value : JSON.stringify(value);
    return h("div", { class: "ep-jrow" }, label, h("span", { class: cls + (text.length > 120 ? " ep-jlong" : ""), text }));
  }
  const jsonView = (v) => h("div", { class: "ep-json" }, jsonNode(v, null, 0));

  /* ---------- app ---------- */
  function mount(root, opts) {
    const api = opts.apiBase.replace(/\/$/, "");
    const call = opts.fetchJSON
      ? (path, init) => opts.fetchJSON(api + path, init)
      : (path, init) =>
          fetch(api + path, init).then(async (r) => {
            const j = await r.json().catch(() => ({}));
            if (!r.ok) throw new Error(j.error || r.statusText);
            return j;
          });
    const send = (method, path, body) =>
      call(path, { method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });

    const S = {
      sessions: [], sessionId: null, session: null, turns: [], sel: 0, evals: {}, stats: {},
      presets: [], preset: "", customModel: "", live: true, view: "turn", tab: "review",
      draft: null, dirty: false, toast: "", busy: "", saved: [], lastMsgCount: 0,
    };

    const toast = (m) => { S.toast = m; renderToast(); clearTimeout(toast.t); toast.t = setTimeout(() => { S.toast = ""; renderToast(); }, 2200); };
    const fail = (e) => toast("⚠ " + (e.message || e));

    root.classList.add("evalpad");
    const header = h("header", { class: "ep-head" });
    const body = h("div", { class: "ep-body" });
    const toastEl = h("div", { class: "ep-toast" });
    root.replaceChildren(header, body, toastEl);

    function renderToast() { toastEl.textContent = S.toast; toastEl.classList.toggle("on", !!S.toast); }

    /* ----- data ----- */
    async function loadSessions() {
      S.sessions = (await call("/sessions?limit=100")).sessions;
    }
    async function loadEvals() {
      const r = await call("/evals");
      S.saved = r.evals; S.stats = r.stats;
      S.evals = {};
      for (const e of r.evals) if (e.session_id === S.sessionId && e.message_id) S.evals[e.message_id] = e;
    }
    async function openSession(id, selectLast) {
      S.sessionId = id;
      const r = await call(`/sessions/${encodeURIComponent(id)}/turns`);
      S.session = r.session; S.turns = r.turns;
      S.lastMsgCount = (S.sessions.find((s) => s.id === id) || {}).message_count || 0;
      await loadEvals();
      select(selectLast ? Math.max(0, S.turns.length - 1) : Math.min(S.sel, Math.max(0, S.turns.length - 1)));
    }
    function select(i) {
      S.sel = Math.max(0, Math.min(i, S.turns.length - 1));
      const t = S.turns[S.sel];
      const ex = t && S.evals[t.message_id];
      S.draft = ex
        ? { verdict: ex.verdict, score: ex.score, tags: [...(ex.tags || [])], notes: ex.notes || "", expected: ex.expected || "", comparisons: ex.comparisons || [] }
        : { verdict: null, score: null, tags: [], notes: "", expected: "", comparisons: [] };
      S.dirty = false;
      render();
    }

    /* ----- actions ----- */
    const turn = () => S.turns[S.sel];
    function patch(p) { Object.assign(S.draft, p); S.dirty = true; renderPanel(); renderHead(); }
    async function save(advance = true) {
      const t = turn();
      if (!t) return;
      try {
        const saved = await send("POST", "/evals", {
          session_id: S.sessionId, message_id: t.message_id, turn_index: t.index,
          model: S.session && S.session.model, prompt: t.prompt, response: t.response, ...S.draft,
        });
        S.evals[t.message_id] = saved; t.evaluated = true; S.dirty = false;
        await loadEvals();
        toast("Saved ✓");
        if (advance && S.sel < S.turns.length - 1) select(S.sel + 1); else render();
      } catch (e) { fail(e); }
    }
    async function runCompare() {
      const t = turn();
      if (!t) return;
      const model = S.customModel.trim();
      if (!model && !S.preset) return toast("Pick a model to compare with");
      S.busy = "compare"; renderDetail();
      try {
        const r = await send("POST", "/compare", { prompt: t.prompt, preset: model ? undefined : S.preset, model: model || undefined, base_url: model ? (S.presets[0] || {}).base_url : undefined });
        S.draft.comparisons = [...S.draft.comparisons, r]; S.dirty = true;
      } catch (e) { fail(e); }
      S.busy = ""; render();
    }
    async function remove(id) {
      try { await call("/evals/" + id, { method: "DELETE" }); await loadEvals(); toast("Deleted"); render(); } catch (e) { fail(e); }
    }

    /* ----- render ----- */
    function renderHead() {
      const st = S.stats || {};
      header.replaceChildren(
        h("div", { class: "ep-brand" }, h("b", { text: "Evalpad" }), h("span", { class: "ep-sub", text: "evals from live Hermes chats" })),
        h("select", { class: "ep-select", onchange: (e) => openSession(e.target.value, true).catch(fail) },
          S.sessions.map((s) => h("option", { value: s.id, selected: s.id === S.sessionId }, `${clip(s.title || s.id, 46)} · ${s.model || "?"} · ${ago(s.last_activity_at || s.started_at)}${s.eval_count ? " · " + s.eval_count + " ✓" : ""}`))),
        h("label", { class: "ep-live" }, h("input", { type: "checkbox", checked: S.live, onchange: (e) => { S.live = e.target.checked; } }), " follow latest"),
        h("div", { class: "ep-tabs" },
          ["review", "saved"].map((t) => h("button", { class: "ep-tab" + (S.tab === t ? " on" : ""), onclick: () => { S.tab = t; render(); } }, t === "review" ? "Review" : `Saved (${st.total || 0})`))),
        h("div", { class: "ep-stats" },
          h("span", { text: st.pass_rate == null ? "pass –" : `pass ${Math.round(st.pass_rate * 100)}%` }),
          h("span", { text: st.avg_score == null ? "avg –" : `avg ${st.avg_score.toFixed(1)}` })),
        h("a", { class: "ep-btn", href: api + "/export", download: "evals.jsonl", text: "Export JSONL" })
      );
    }

    function renderTurns() {
      return h("nav", { class: "ep-turns" },
        S.turns.map((t, i) => h("button", { class: "ep-turn" + (i === S.sel ? " on" : ""), onclick: () => select(i) },
          h("span", { class: "ep-tn", text: "#" + (i + 1) }),
          h("span", { class: "ep-tp", text: clip(t.prompt.replace(/\s+/g, " "), 70) || "(empty)" }),
          S.evals[t.message_id] ? h("span", { class: "ep-dot " + (S.evals[t.message_id].verdict || "none"), title: "evaluated" }) : null)),
        !S.turns.length ? h("div", { class: "ep-empty", text: "No turns in this session." }) : null);
    }

    function responseCard(title, sub, text, extra) {
      return h("section", { class: "ep-card" }, h("div", { class: "ep-ct" }, h("b", { text: title }), h("span", { class: "ep-sub", text: sub })), h("div", { class: "ep-text", text: text || "(no text response)" }), extra);
    }

    function renderDetail() {
      const t = turn();
      if (!t) return h("main", { class: "ep-detail" }, h("div", { class: "ep-empty", text: "Start a chat with Hermes, then come back. New turns appear here live." }));
      const toggles = h("div", { class: "ep-seg" },
        ["turn", "json"].map((v) => h("button", { class: S.view === v ? "on" : "", onclick: () => { S.view = v; renderDetailInto(); } }, v === "turn" ? "Conversation" : "Raw JSON")));
      const cmps = S.draft.comparisons;
      const view = S.view === "json"
        ? jsonView({ session: S.session, turn: t, draft: S.draft })
        : h("div", {},
            responseCard("You", ago(t.ts), t.prompt),
            t.tools.length ? h("section", { class: "ep-card" }, h("div", { class: "ep-ct" }, h("b", { text: `Tool calls (${t.tools.length})` })),
              t.tools.map((tc) => h("details", { class: "ep-tool" }, h("summary", { text: tc.name || "tool" }), jsonView({ arguments: tc.arguments, result: tc.result })))) : null,
            h("div", { class: "ep-cmpgrid" + (cmps.length ? " two" : "") },
              responseCard(S.session.model || "model", "original", t.response),
              cmps.map((c, i) => responseCard(c.label || c.model, `${c.latency_ms} ms`, c.response, h("div", { class: "ep-cmpbar" },
                h("button", { class: "ep-btn sm" + (c.preferred ? " on" : ""), onclick: () => { c.preferred = !c.preferred; S.dirty = true; renderDetailInto(); renderPanel(); } }, c.preferred ? "★ preferred" : "☆ prefer this"),
                h("button", { class: "ep-btn sm", onclick: () => { S.draft.comparisons.splice(i, 1); S.dirty = true; renderDetailInto(); } }, "remove"))))));
      return h("main", { class: "ep-detail" },
        h("div", { class: "ep-dbar" }, toggles,
          h("div", { class: "ep-cmprow" },
            h("select", { class: "ep-select sm", onchange: (e) => { S.preset = e.target.value; S.customModel = ""; } },
              h("option", { value: "" }, "compare with…"), S.presets.map((p) => h("option", { value: p.label, selected: p.label === S.preset }, p.label + (p.has_key ? "" : " (no key)")))),
            h("input", { class: "ep-input sm", placeholder: "or model id", value: S.customModel, oninput: (e) => { S.customModel = e.target.value; } }),
            h("button", { class: "ep-btn pri", disabled: S.busy ? true : null, onclick: runCompare }, S.busy ? "Running…" : "Compare (c)"))),
        view);
    }
    function renderDetailInto() { const old = body.querySelector(".ep-detail"); if (old) old.replaceWith(renderDetail()); }

    function renderPanel() {
      const d = S.draft;
      const panel = h("aside", { class: "ep-panel" },
        h("div", { class: "ep-ct" }, h("b", { text: "Eval this turn" }), S.dirty ? h("span", { class: "ep-sub", text: "unsaved" }) : null),
        h("div", { class: "ep-verdict" },
          h("button", { class: "ep-btn v pass" + (d.verdict === "pass" ? " on" : ""), onclick: () => patch({ verdict: d.verdict === "pass" ? null : "pass" }) }, "👍 Pass (p)"),
          h("button", { class: "ep-btn v fail" + (d.verdict === "fail" ? " on" : ""), onclick: () => patch({ verdict: d.verdict === "fail" ? null : "fail" }) }, "👎 Fail (f)")),
        h("div", { class: "ep-stars" }, [1, 2, 3, 4, 5].map((n) => h("button", { class: "ep-star" + (d.score >= n ? " on" : ""), onclick: () => patch({ score: d.score === n ? null : n }), title: `score ${n}`, text: "★" })), h("span", { class: "ep-sub", text: d.score ? `${d.score}/5` : "score 1-5" })),
        h("div", { class: "ep-tagrow" }, TAGS.map((t) => h("button", { class: "ep-tag" + (d.tags.includes(t) ? " on" : ""), onclick: () => patch({ tags: d.tags.includes(t) ? d.tags.filter((x) => x !== t) : [...d.tags, t] }), text: t }))),
        h("label", { class: "ep-lbl", text: "Expected answer" }),
        h("textarea", { class: "ep-input", rows: 4, placeholder: "What a correct reply looks like (optional)", value: d.expected, oninput: (e) => { d.expected = e.target.value; S.dirty = true; } }),
        h("label", { class: "ep-lbl", text: "Notes" }),
        h("textarea", { class: "ep-input", rows: 3, placeholder: "Why? (optional)", value: d.notes, oninput: (e) => { d.notes = e.target.value; S.dirty = true; } }),
        h("button", { class: "ep-btn pri big", onclick: () => save(true) }, "Save eval  ⌘↵"),
        h("div", { class: "ep-keys", text: "j/k move · p/f verdict · 1-5 score · c compare · ⌘↵ save" }));
      const old = body.querySelector(".ep-panel");
      if (old) old.replaceWith(panel);
      return panel;
    }

    function renderSaved() {
      return h("div", { class: "ep-saved" },
        !S.saved.length ? h("div", { class: "ep-empty", text: "No evals saved yet. Score a turn in Review, or type /eval in Hermes." }) : null,
        S.saved.map((e) => h("section", { class: "ep-card" },
          h("div", { class: "ep-ct" },
            h("span", { class: "ep-badge " + (e.verdict || "none"), text: e.verdict || "unrated" }),
            e.score ? h("b", { text: "★".repeat(e.score) }) : null,
            h("span", { class: "ep-sub", text: `${e.model || ""} · ${ago(e.ts)}` }),
            h("span", { class: "ep-grow" }),
            h("button", { class: "ep-btn sm", onclick: () => remove(e.id) }, "delete")),
          h("div", { class: "ep-text", text: clip(e.prompt, 300) }),
          (e.tags || []).length ? h("div", { class: "ep-tagrow" }, e.tags.map((t) => h("span", { class: "ep-tag on", text: t }))) : null,
          h("details", { class: "ep-tool" }, h("summary", { text: "JSON" }), jsonView(e)))));
    }

    function render() {
      renderHead();
      if (S.tab === "saved") return body.replaceChildren(renderSaved());
      if (!S.draft) S.draft = { verdict: null, score: null, tags: [], notes: "", expected: "", comparisons: [] };
      body.replaceChildren(renderTurns(), renderDetail(), h("aside", { class: "ep-panel" }));
      renderPanel();
      const on = body.querySelector(".ep-turn.on");
      if (on && on.scrollIntoView) on.scrollIntoView({ block: "nearest" });
    }

    /* ----- keyboard ----- */
    function onKey(e) {
      const typing = /^(INPUT|TEXTAREA|SELECT)$/.test((e.target || {}).tagName || "");
      if ((e.metaKey || e.ctrlKey) && e.key === "Enter") { e.preventDefault(); return save(true); }
      if (typing || e.metaKey || e.ctrlKey || e.altKey || S.tab !== "review" || !S.draft) return;
      const k = e.key;
      if (k === "j" || k === "ArrowDown") { e.preventDefault(); select(S.sel + 1); }
      else if (k === "k" || k === "ArrowUp") { e.preventDefault(); select(S.sel - 1); }
      else if (k === "p") patch({ verdict: S.draft.verdict === "pass" ? null : "pass" });
      else if (k === "f") patch({ verdict: S.draft.verdict === "fail" ? null : "fail" });
      else if (/^[1-5]$/.test(k)) patch({ score: S.draft.score === +k ? null : +k });
      else if (k === "c") runCompare();
    }
    document.addEventListener("keydown", onKey);

    /* ----- live follow ----- */
    async function poll() {
      if (!root.isConnected) { document.removeEventListener("keydown", onKey); return; }
      try {
        if (S.live && S.tab === "review") {
          const { latest } = await call("/latest");
          if (latest && (latest.id !== S.sessionId || latest.message_count !== S.lastMsgCount) && !S.dirty) {
            await loadSessions();
            await openSession(latest.id, true);
          }
        }
      } catch (_) { /* transient; keep polling */ }
      setTimeout(poll, 3000);
    }

    /* ----- boot ----- */
    (async () => {
      renderHead();
      body.replaceChildren(h("div", { class: "ep-empty", text: "Loading…" }));
      try {
        S.presets = (await call("/presets")).presets;
        await loadSessions();
        if (S.sessions.length) await openSession(S.sessions[0].id, true);
        else { await loadEvals(); render(); }
      } catch (e) { body.replaceChildren(h("div", { class: "ep-empty", text: "⚠ " + (e.message || e) })); }
      setTimeout(poll, 3000);
    })();
  }

  window.EvalpadUI = { mount };
})();
