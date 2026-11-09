# hermes-hackathon-2026

[Hermes Agent](https://hermes-agent.nousresearch.com/docs/user-guide/features/plugins) plugins, plus a test harness that checks them before Hermes sees them.

## quick-eval

Ask the agent something, then `/quick-eval`: other models answer the same prompt, you mark the good answers, and a leaderboard adds them up. Details and what it touches: [plugins/quick-eval/README.md](plugins/quick-eval/README.md).

![Tiananmen 1989: three Claude models answer, local Qwen refuses](docs/img/tiananmen.png)
*"What happened at Tiananmen Square in 1989?" Three Claude models answer; the local Qwen model refuses.*

### Install

Have Hermes (`hermes` runs in your terminal):
```
hermes plugins install tikiverse/hermes-hackathon-2026/plugins/quick-eval --enable
```
No Hermes yet: install it, pick a model provider, then run the line above.
```
curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash
hermes setup
```

### Try it (no account, no key, your Hermes untouched)

Setup once, copy and paste (skip what you have):
```
curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash -s -- --skip-setup   # Hermes
brew install ollama && brew services start ollama                                   # or the app: https://ollama.com/download
ollama pull qwen2.5:0.5b && ollama pull deepseek-r1:1.5b                                # ~1.5 GB
```
Then this line gives the plugin a Hermes home of its own and opens Hermes:
```
curl -fsSL https://raw.githubusercontent.com/tikiverse/hermes-hackathon-2026/quick-eval-ui/scripts/demo.sh | sh
```
Ask "What happened at Tiananmen Square in 1989? One sentence." Then `/quick-eval` (lists models + commands), `/quick-eval deepseek` (DeepSeek-R1 refuses), `/quick-eval pick A`, `/quick-eval open`.
Remove the demo (the last 2 lines only if you installed them for it; `hermes uninstall` keeps `~/.hermes`):
```
rm -rf ~/.hermes-quick-eval-demo ~/.cache/quick-eval-pr
ollama rm qwen2.5:0.5b deepseek-r1:1.5b
brew services stop ollama && brew uninstall ollama
hermes uninstall
```
llama-server or vLLM instead of Ollama: skip the demo, install into your Hermes (above); `/quick-eval` finds them.

Models: nothing to configure. `/quick-eval` lists the models Hermes is signed in to, plus Ollama, LM Studio or vLLM if one runs on this machine.

Restart `hermes` after installing.

### Use

| Where | How |
|---|---|
| Terminal (`hermes`) | `/quick-eval` lists models + commands → `/quick-eval deepseek` → `/quick-eval pick A,B` |
| Chat apps (Desktop, phone, gateways) | same commands |
| Review UI | `/quick-eval open` → http://127.0.0.1:8765. Also a tab in `hermes dashboard`. No Hermes: `uv run python plugins/quick-eval/standalone.py --open` |

## Develop

```
uv sync
uv run pytest                     # -m "not hermes" skips the real-Hermes subprocess tests
hermes plugins validate "$PWD/plugins/quick-eval"   # catalog check; needs Hermes >= 0.23.0
```

- `plugins/<name>/`: one folder per plugin, picked up by the tests automatically.
- `tests/test_contract.py`: manifest matches what `register()` adds. `tests/test_hermes_load.py`: Hermes's real loader. `tests/test_quick_eval_e2e.py`: `/quick-eval` through real Hermes against a fake model server.
- The fake context has no `ctx.llm`, like the validator's probe, so a `register()` that touches it fails here first.
