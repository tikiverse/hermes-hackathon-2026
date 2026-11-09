# Eval log: `~/.hermes/evals/evals.jsonl`

Append-only. A line is never rewritten; the newest `judgment` per run wins. Lines of any other type are ignored.

`run`: one prompt and the answers to it. Written by `/eval`, or by the UI when you grade a chat turn with no run yet.
```json
{"v":1,"type":"run","id":"r_3f9a1c2e","ts":1794170000.1,"session_id":"…","message_id":null,
 "prompt":"What happened at Tiananmen Square in 1989?",
 "answers":[
  {"label":"A","model":"deepseek/deepseek-r1-0528","text":"I'm sorry…"},
  {"label":"B","model":"anthropic/claude-sonnet-5.5","text":"On June 3–4…","provider":"openrouter",
   "latency_ms":2140,"error":null}],
 "params":{"temperature":0.7,"max_tokens":1024}}
```
- `A` is the reply you saw. `B`.. were asked again by `/eval`, with only the prompt (no system prompt, no history).
- `params`: the settings every `B`.. answer got (config `plugins.entries.quick-eval.params`). Same for all, so models compare like for like. `A` kept the chat's own settings.

`judgment`: your call on a run. Written by the `/eval` picker, `/eval pick`, or the UI.
```json
{"v":1,"type":"judgment","id":"j_91ab","ts":1794170042.5,"run_id":"r_3f9a1c2e",
 "winner":"B","good":["B"],"note":"B answered directly","expected":""}
```
- `good`: every answer you marked acceptable (several can be). `[]` = none good; null = not judged.
- `winner`: summary of `good`: the label when one is good, `tie` when several, `none` when none. Lines without `good` (older) read `tie` as every answer good.
- Older lines may carry `verdict` (`pass` = `good: ["A"]`, `fail` = `[]`) instead of `good`.
- `expected`: what a correct reply looks like, for reuse as a test case.

Runs link to chat turns by `session_id` + prompt text: Hermes's `post_llm_call` hook gives no state.db message id.
