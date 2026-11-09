# hermes-hackathon-2026

Plugins for [Hermes Agent](https://hermes-agent.nousresearch.com/docs/user-guide/features/plugins), plus a test harness that checks them before Hermes ever sees them.

## quick-eval

Ask the agent something, then run `/eval` to ask other models the same question, see every answer side by side, and pick the winner. Runs and picks are appended to `~/.hermes/evals/evals.jsonl`; `/eval open` shows them in a browser.

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
```

- **Answer A** is the agent's reply exactly as you saw it. The other models get only your last question, with no system prompt or history, and run in parallel.
- **`/eval`** on its own opens a checklist with your default models pre-checked. `/eval claude local` skips the checklist and uses those aliases. You can also type a raw model id, or `model@provider`.
- **The first `/eval`** asks permission to call other models and saves it to `config.yaml`. Without a terminal to ask in (a gateway, for example), it refuses and links to the config file.
- **Local servers** running on their usual ports (Ollama on 11434, LM Studio on 1234, vLLM on 8000) show up in the checklist automatically. Picking one adds it to Hermes as a provider, so nobody has to edit the config by hand.
- **Known limit, local thinking models** (Qwen3 and similar): Hermes drops a custom provider's `extra_body` and `max_tokens` on plugin calls ([hermes-agent#124290](https://github.com/NousResearch/hermes-agent/pull/124290), [#50132](https://github.com/NousResearch/hermes-agent/issues/50132)). So the model thinks, and a server with a small default cap can return no answer; `/eval` then says so instead of showing a blank. Fix on the server until those land: turn thinking off by default (`mlx_lm.server --chat-template-args '{"enable_thinking": false}'`) or raise its default max tokens. Works on stock Hermes; no patch needed.

### Demo setup

Use DeepSeek-R1 as the agent's main model. It's the model most CCP-censorship research has tested, including Promptfoo's set of 1,360 sensitive prompts, so it reliably dodges questions like the one above. Then add aliases for the models you want to compare in `~/.hermes/config.yaml`:

```yaml
model:
  provider: openrouter
  model: deepseek/deepseek-r1-0528

plugins:
  enabled: [quick-eval]
  entries:
    quick-eval:
      llm:
        allow_model_override: true
        allow_provider_override: true
      default: [claude]
      params: {temperature: 0.7, max_tokens: 1024}   # same for every model; sweeps belong in MLflow
      models:
        claude: {provider: openrouter, model: anthropic/claude-sonnet-5.5}
        hermes: {provider: openrouter, model: nousresearch/hermes-4-405b}
        local:  {provider: ollama, model: llama3.3}
```

Check the model ids against OpenRouter before the demo; the checklist also lists the ids Hermes knows about. The `llm` block is the permission the first `/eval` would otherwise ask for.

### Run it in Docker

The image runs Hermes with quick-eval installed and the demo config above already in place, so all you need is an OpenRouter key:

```
export OPENROUTER_API_KEY=sk-or-...
docker compose run --rm hermes
```

The first start copies `docker/config.yaml` into a `hermes-home` volume. Hermes's config, sessions, and `evals/evals.jsonl` live in that volume and survive restarts. To start fresh, run `docker compose down -v`.

- **Change the config:** edit `docker/config.yaml` and reset the volume, or edit the live copy with `docker compose run --rm hermes sh -c 'vi $HERMES_HOME/config.yaml'`.
- **Read the eval log:** `docker compose run --rm hermes cat /data/hermes/evals/evals.jsonl`.
- **Local models:** the container looks for Ollama, LM Studio, and vLLM on your machine through `host.docker.internal`. Docker Desktop on a Mac reaches them as they are. On Linux, the servers must listen on all interfaces rather than only `localhost` (for Ollama, set `OLLAMA_HOST=0.0.0.0`).
- **Without Compose:** `docker build -t hermes-quick-eval .` then `docker run -it --rm -e OPENROUTER_API_KEY -v hermes-home:/data/hermes hermes-quick-eval`.

### Review UI

`/eval open` opens `http://127.0.0.1:8765` (also a **Quick Eval** tab in `hermes dashboard`; without Hermes: `uv run python plugins/quick-eval/standalone.py --open`). It reads `~/.hermes/state.db` read-only.

| Tab | Use | Keys |
|---|---|---|
| Review | your chats (current one pinned); grade a turn pass/fail, add a note or expected answer | `j`/`k`, `p`/`f`, `Cmd+Enter` |
| Compare | one prompt, a column per model; click the best, save & next unjudged | `j`/`k`, `a`-`e`, `t`, `n`, `Cmd+Enter` |
| Leaderboard | per model: wins and win % over the runs you judged | |

### Your evals are a plain file

Everything lands in `~/.hermes/evals/evals.jsonl`: one `run` line per `/eval`, one `judgment` line per pick or grade. Format: [docs/eval-log.md](docs/eval-log.md). **Export JSONL** in the UI downloads it.

## Setup

```
uv sync
uv run pytest
```

`uv sync` installs `hermes-agent` into the project's virtualenv, so the tests run against the real plugin system without touching your own Hermes install.

## Layout

```
plugins/<name>/             one folder per plugin, in the layout Hermes expects
  plugin.yaml               manifest
  __init__.py               register(ctx)
tests/
  conftest.py               FakeCtx and the plugin fixtures
  test_contract.py          rules every plugin must follow
  test_hermes_load.py       loads each plugin with Hermes's real PluginManager
  test_quick_eval.py        quick-eval behavior, with fake models, UI, and config
  test_quick_eval_e2e.py    quick-eval inside real Hermes, against a fake model server
  test_quick_eval_web.py    log format, reports, HTTP routes
  test_quick_eval_web_browser.py  the UI in Chromium (`uv run --with playwright pytest`)
scripts/link-plugins.sh
```

## What the tests check

Every folder in `plugins/` with a `plugin.yaml` is picked up automatically.

- **Contract tests** load the plugin with a `FakeCtx` that records each registration. They check that `provides_tools` and `provides_hooks` match what `register()` actually adds, that each tool schema is valid JSON Schema with a description, that handlers return a JSON string even when called with no arguments, and that hooks tolerate payload fields they don't know about.
- **Real-loader test** symlinks the plugin into a temporary `HERMES_HOME`, enables it, and runs Hermes's own `PluginManager` in a subprocess. It fails if Hermes can't discover the plugin, if `register()` raises, or if the registered tools and hooks differ from the manifest.
- **Plugin tests** cover one plugin's behavior. The quick-eval end-to-end test starts a fake OpenAI-compatible server, registers it as a Hermes provider, and runs `/eval` and `/eval pick` through Hermes's real plugin and LLM code, so it proves requests are routed to the right endpoint.

Tests marked `hermes` start real Hermes subprocesses. Skip them with `uv run pytest -m "not hermes"`.

## Trying a plugin in Hermes

```
scripts/link-plugins.sh               # every plugin
scripts/link-plugins.sh quick-eval    # just one
```

This symlinks each plugin into `~/.hermes/plugins/` (or `$HERMES_HOME/plugins/`) and enables it, so edits in this repo show up the next time Hermes starts. Inside a Hermes session, `/plugins` lists what loaded.

The docs also describe `hermes plugins doctor` and `hermes plugins validate`, but `hermes-agent` 0.19.0 on PyPI doesn't include them yet. The real-loader test covers the same ground until they ship.
