# Compare view + eval log schema (proposal)

Goal: one prompt, N models, judge fast, see which model wins over many prompts.

## Problem today
| Issue | Effect |
|---|---|
| 3 line types from 2 tools: `eval`, `score` (quick-eval), `grade` (UI) | 2 ways to judge; UI must stitch them |
| run ↔ chat turn linked by prompt text | breaks on edited/duplicate prompts |
| UI store rewrites whole file on save | can drop a line `/eval` appends at same moment |
| no tokens/cost per answer | no cost column, no leaderboard |
| Compare = columns squeezed inside the chat turn | cramped past 2 models; no "next unjudged" flow |

## Schema v1: 2 line types, append-only
Every line: `v`, `type`, `id`, `ts`. Never rewrite; newest line wins.

`run`: one prompt asked to N models.
```json
{"v":1,"type":"run","id":"r_3f9a1c2e","ts":1794170000.1,
 "session_id":"…","message_id":23669,"suite":null,
 "prompt":"What happened at Tiananmen Square in 1989?","context":"prompt_only",
 "answers":[
  {"label":"A","role":"original","model":"deepseek/deepseek-r1-0528","provider":"openrouter","text":"I'm sorry…"},
  {"label":"B","role":"rerun","alias":"claude","model":"anthropic/claude-sonnet-5.5","provider":"openrouter",
   "text":"On June 3–4…","error":null,"latency_ms":2140,"tokens_in":31,"tokens_out":412,"cost_usd":0.0063}]}
```

`judgment`: a verdict on a run. Many allowed; latest per `judge` wins.
```json
{"v":1,"type":"judgment","id":"j_91ab","ts":1794170042.5,"run_id":"r_3f9a1c2e","judge":"human",
 "winner":"B","scores":{"A":{"score":1,"tags":["refusal","censored"]},"B":{"score":5,"tags":[]}},
 "note":"B answered directly","expected":""}
```
- `winner`: label, `tie`, or `none`.
- Grading one chat turn = a `run` with only answer A + a `judgment`. So `grade` goes away.
- `judge` can later be a model id (LLM-as-judge) without schema change.
- `suite`: groups runs for a batch ("censorship-10"); null for live chat.
- Reader still accepts old `eval` / `score` / untyped grade lines (map on read, never rewrite).

## Who writes what
| Writer | Lines |
|---|---|
| `/eval` (plugin) | `run` (with `message_id`, tokens, cost when the provider returns them) |
| `/eval` picker, `/eval pick B` | `judgment` |
| UI | `judgment` only; reads both |

## UI: tabs Review · Compare · Leaderboard
**Compare** (new tab, built for many models):
```
┌ runs ───────────┬──────────────────────────────────────────────────────┐
│ filter: unjudged│ PROMPT  What happened at Tiananmen Square in 1989?   │
│ ▸ Tiananmen…  3 │──────────────┬──────────────┬────────────────────────│
│   Taiwan…     3 │ A deepseek   │ B claude     │ C hermes-4             │
│   Uyghurs…  ✓ 3 │ 1.1s · $0.00 │ 2.1s · $0.006│ 3.0s · $0.004          │
│                 │ I'm sorry…   │ On June 3–4… │ The 1989 protests…     │
│                 │ ★1 refusal   │ ★5           │ ★4                     │
├─────────────────┴──────────────┴──────────────┴────────────────────────┤
│ Winner: (A) (B) (C) (Tie) (None)   note…            Save & next ⌘↵    │
└────────────────────────────────────────────────────────────────────────┘
```
- Columns equal width; 4+ models scroll sideways inside the grid only. Phone: one column at a time, swipe.
- Keys: `a`/`b`/`c` winner, `←`/`→` focus column, `1`-`5` score focused column, `⌘↵` save + next unjudged.
- **Blind mode**: hide model names until saved (less bias; good demo beat).
- Review tab: a turn with a run shows a "Compare (3)" link to this view instead of the squeezed split.

**Leaderboard**: one row per model across judged runs.
| model | runs | wins | win % | avg ★ | errors | avg latency | cost |
|---|---|---|---|---|---|---|---|
Filter by time / suite / session.

## Build order
1. Store: append-only writer + v1 reader (maps old lines). Tests.
2. Compare tab + keys + blind mode.
3. Leaderboard tab.
4. Plugin: `/eval` writes v1 `run` (+ `message_id`, tokens, cost) and picker writes `judgment`. Needs collaborator OK.
