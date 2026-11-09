# hermes-hackathon-2026

Plugins for [Hermes Agent](https://hermes-agent.nousresearch.com/docs/user-guide/features/plugins), plus a test harness that checks them before Hermes ever sees them.

## quick-eval

Ask the agent something, then `/eval` to ask other models the same question and mark the good answers. Usage, the review UI and what it touches: [plugins/quick-eval/README.md](plugins/quick-eval/README.md).

### Demo setup

Use DeepSeek-R1 as the agent's main model. It's the model most CCP-censorship research has tested, including Promptfoo's set of 1,360 sensitive prompts, so it reliably dodges questions like "What happened at Tiananmen Square in 1989?". Then add aliases for the models you want to compare in `~/.hermes/config.yaml`:

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
  test_quick_eval_web_browser.py  the UI in Chromium (Playwright is a dev dependency)
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

Before a catalog PR: `hermes plugins validate <abs path>/plugins/quick-eval` on Hermes ≥0.23.0 (the PyPI 0.19 in this venv lacks it). The test harness's fake context has no `ctx.llm`, like the validator's probe, so a `register()` that touches it fails here first.
