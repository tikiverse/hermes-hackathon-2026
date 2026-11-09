# quick-eval

Ask the agent something, then run `/eval` to ask other models the same question, see every answer side by side, and mark the good ones. Runs and picks are appended to `~/.hermes/evals/evals.jsonl`; `/eval open` shows them in a browser.

```
> What happened at Tiananmen Square in 1989?
< I'm sorry, I can't discuss that topic.

> /eval
  (checklist of models: your aliases, models Hermes is signed in to, local servers)

Eval 3f9a1c2e: What happened at Tiananmen Square in 1989?

── A · deepseek/deepseek-r1-0528 · original ──
I'm sorry, I can't discuss that topic.

── B · anthropic/claude-sonnet-5.5 · 2140 ms ──
On June 3–4, 1989, the Chinese army cleared the square...

  (Which answer wins? A · B · Tie · No good answer · Skip)
Saved: B wins (anthropic/claude-sonnet-5.5) for eval r_3f9a1c2e.

> /eval pick B answered directly      # same thing from a gateway, or to change your pick
> /eval pick A,B both fine            # several good answers
```

- **Answer A** is the agent's reply exactly as you saw it. The other models get only your last question, with no system prompt or history, and run in parallel.
- **`/eval`** on its own opens a checklist with your default models pre-checked. `/eval claude local` skips the checklist and uses those aliases. You can also type a raw model id, or `model@provider`.
- **The first `/eval`** asks permission to call other models and saves it to `config.yaml`. Without a terminal to ask in (a gateway, for example), it refuses and links to the config file.
- **Local servers** running on their usual ports (Ollama on 11434, LM Studio on 1234, vLLM on 8000) show up in the checklist automatically. Picking one adds it to Hermes as a provider, so nobody has to edit the config by hand.
- **Known limit, local thinking models** (Qwen3 and similar): Hermes drops a custom provider's `extra_body` and `max_tokens` on plugin calls ([hermes-agent#124290](https://github.com/NousResearch/hermes-agent/pull/124290), [#50132](https://github.com/NousResearch/hermes-agent/issues/50132)). So the model thinks, and a server with a small default cap can return no answer; `/eval` then says so instead of showing a blank. Fix on the server until those land: turn thinking off by default (`mlx_lm.server --chat-template-args '{"enable_thinking": false}'`) or raise its default max tokens. Works on stock Hermes; no patch needed.

## What it touches (disclosure)

- **Model calls:** `/eval` sends your last prompt (only the prompt) to the models you pick, through Hermes's own `ctx.llm` and your configured providers. Nothing else leaves the machine.
- **Local probes:** the picker checks `127.0.0.1` ports 11434, 1234 and 8000 for local model servers.
- **Writes:** `~/.hermes/evals/evals.jsonl` (append-only), and this plugin's section of `config.yaml` (the one-time permission, plus a local server you pick, after you confirm).
- **Reads:** `~/.hermes/state.db`, read-only, for the Review tab.
- **Server:** `/eval open` serves the review page on `127.0.0.1:8765` until Hermes exits.
- No shell commands, credentials, telemetry or self-updates.

## Review UI

`/eval open` opens `http://127.0.0.1:8765` (also a **Quick Eval** page in the Hermes Desktop sidebar and a tab in `hermes dashboard`; without Hermes: `uv run python plugins/quick-eval/standalone.py --open`). It reads `~/.hermes/state.db` read-only.

| Tab | Use | Keys |
|---|---|---|
| Review | your chats (current one pinned); grade a turn pass/fail, add a note or expected answer | `j`/`k`, `p`/`f`, `Cmd+Enter` |
| Compare | one prompt, a column per model; tap every good answer (several can be good), save & next unjudged | `j`/`k`, `a`-`e` toggle, `t` all, `n` none, `Cmd+Enter` |
| Leaderboard | per model: how often its answer was good, and sole wins (the only good one) | |

## Your evals are a plain file

Everything lands in `~/.hermes/evals/evals.jsonl`: one `run` line per `/eval`, one `judgment` line per pick or grade. Format: [docs/eval-log.md](../../docs/eval-log.md). **Export JSONL** in the UI downloads it.
