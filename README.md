# hermes-hackathon-2026

[Hermes Agent](https://hermes-agent.nousresearch.com/docs/user-guide/features/plugins) plugins, plus a test harness that checks them before Hermes sees them.

## quick-eval

Ask the agent something, then `/eval`: other models answer the same prompt, you mark the good answers, and a leaderboard adds them up. Details and what it touches: [plugins/quick-eval/README.md](plugins/quick-eval/README.md).

### Install

```
git clone https://github.com/tikiverse/hermes-hackathon-2026
cd hermes-hackathon-2026 && scripts/link-plugins.sh quick-eval   # symlinks into ~/.hermes/plugins and enables it
```

Restart Hermes, then `/plugins` lists it. Once listed in the catalog: `hermes plugins install quick-eval`.

### Use

| Where | How |
|---|---|
| Terminal (`hermes`) | `/eval` → checklist of models → answers → pick the good ones |
| Chat apps (Desktop, phone, gateways) | `/eval claude local` (name the models), then `/eval pick A,B` |
| Review UI | `/eval open` → http://127.0.0.1:8765. Also a tab in `hermes dashboard`. No Hermes: `uv run python plugins/quick-eval/standalone.py --open` |

### Demo in Docker

```
export OPENROUTER_API_KEY=sk-or-...
docker compose run --rm hermes
```

Main model DeepSeek-R1 (it dodges "What happened at Tiananmen Square in 1989?"), compared against the aliases in [docker/config.yaml](docker/config.yaml). State lives in the `hermes-home` volume; `docker compose down -v` resets it.

## Develop

```
uv sync
uv run pytest                     # -m "not hermes" skips the real-Hermes subprocess tests
hermes plugins validate "$PWD/plugins/quick-eval"   # catalog check; needs Hermes >= 0.23.0
```

- `plugins/<name>/`: one folder per plugin, picked up by the tests automatically.
- `tests/test_contract.py`: manifest matches what `register()` adds. `tests/test_hermes_load.py`: Hermes's real loader. `tests/test_quick_eval_e2e.py`: `/eval` through real Hermes against a fake model server.
- The fake context has no `ctx.llm`, like the validator's probe, so a `register()` that touches it fails here first.
