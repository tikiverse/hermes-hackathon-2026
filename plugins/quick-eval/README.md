# quick-eval

Ask the agent something, then run `/quick-eval` to ask other models the same question, see every answer side by side, and mark the good ones. Runs and picks are appended to `~/.hermes/evals/evals.jsonl`; `/quick-eval open` shows them in a browser.

```
> What happened at Tiananmen Square in 1989?
< The 1989 Tiananmen Square protests ...

> /quick-eval
quick-eval: ask other models your last question, then mark the good answers.
Last question: What happened at Tiananmen Square in 1989?

Models you can name:
  deepseek                 deepseek-r1:1.5b · ollama
  qwen3:1.7b               Ollama, local

Commands:
  /quick-eval deepseek           ask them (names from the list above)
  /quick-eval pick A,B [note]    mark the good answers (or: none)
  /quick-eval open               review in the browser

> /quick-eval deepseek
── A · qwen2.5:0.5b · original ──
The 1989 Tiananmen Square protests ...

── B · deepseek-r1:1.5b · 935 ms ──
I am sorry, I cannot answer that question.

Next: /quick-eval pick A,B [note] marks the good answers (or: none) · /quick-eval open to review

> /quick-eval pick A answered
> /quick-eval open
```

- **Answer A** is the agent's reply exactly as you saw it. The other models get only your last question, with no system prompt or history, and run in parallel, each with the same settings and a 120 s timeout.
- **Names:** an alias from your config, a model a local server serves, a raw model id, or `model@provider`.
- **Text only, no pickers:** works the same in the terminal, on any Hermes version, and in chat apps.
- **First use:** `/quick-eval allow` saves the one-time permission to send your question to other models.
- **Why `/quick-eval`, not `/eval`:** Hermes gives a command name two plugins share to whichever loads last, without a warning. The plugin's own name can't clash.
- **Local servers** on their usual ports (Ollama 11434, LM Studio 1234, vLLM 8000, llama-server 8080) are listed by `/quick-eval`. Naming one of their models adds the server to Hermes as a provider, so nobody edits the config by hand.
- **Known limit, local thinking models** (Qwen3 and similar): Hermes drops a custom provider's `extra_body` and `max_tokens` on plugin calls ([hermes-agent#124290](https://github.com/NousResearch/hermes-agent/pull/124290), [#50132](https://github.com/NousResearch/hermes-agent/issues/50132)). So the model thinks, and a server with a small default cap can return no answer; `/quick-eval` then says so instead of showing a blank. Fix on the server until those land: turn thinking off by default (`mlx_lm.server --chat-template-args '{"enable_thinking": false}'`) or raise its default max tokens. Works on stock Hermes; no patch needed.

## What it touches (disclosure)

- **Model calls:** `/quick-eval` sends your last prompt (only the prompt) to the models you pick, through Hermes's own `ctx.llm` and your configured providers. Nothing else leaves the machine.
- **Local probes:** `/quick-eval` checks `127.0.0.1` ports 11434, 1234, 8000 and 8080 for local model servers.
- **Writes:** `~/.hermes/evals/evals.jsonl` (append-only), and this plugin's section of `config.yaml` (the permission from `/quick-eval allow`, plus a local server you name).
- **Reads:** `~/.hermes/state.db`, read-only, for the Review tab.
- **Server:** `/quick-eval open` serves the review page on `127.0.0.1:8765` until Hermes exits.
- No shell commands, credentials, telemetry or self-updates.

## Review UI

`/quick-eval open` opens `http://127.0.0.1:8765` (also a **Quick Eval** tab in `hermes dashboard`; without Hermes: `uv run python plugins/quick-eval/standalone.py --open`). It reads `~/.hermes/state.db` read-only.

| Tab | Use | Keys |
|---|---|---|
| Review | your chats (current one pinned). Each turn shows its answers: just the reply, or a column per model after `/quick-eval`. Tap every good answer (several can be good); note, expected answer | `j`/`k` turn, `a`-`e` toggle, `t` all, `n` none, `Cmd+Enter` save |
| Leaderboard | per model: how often its answer was good, and sole wins (the only good one) | |

## Your evals are a plain file

Everything lands in `~/.hermes/evals/evals.jsonl`: one `run` line per `/quick-eval`, one `judgment` line per pick or grade. Format: [docs/eval-log.md](../../docs/eval-log.md). **Export JSONL** in the UI downloads it.
