# Quick Eval

Quick Eval is a [Hermes Agent](https://hermes-agent.nousresearch.com/) plugin for getting a second opinion on an answer. After the agent replies, run `/quick-eval` to send the same question to other models, compare the answers side by side, and mark the ones that are good. Every comparison is saved to a local JSONL file, so over time you build an evaluation dataset from the questions you ask, and a leaderboard shows which models you trust most.

![Six steps in Hermes Desktop: Hermes answers, /quick-eval lists models, two more models answer, /quick-eval open shows the answers side by side, you mark the good ones, and save](https://raw.githubusercontent.com/tikiverse/quick-eval/main/docs/img/demo.gif)

*The six steps of a Quick Eval run, recorded in the Hermes Desktop app.*

![Three Claude models answer a question about Tiananmen Square in 1989, while a local Qwen model refuses](https://raw.githubusercontent.com/tikiverse/quick-eval/main/docs/img/tiananmen.png)

*The review page after asking four models "What happened at Tiananmen Square in 1989?". Three Claude models answer, and the local Qwen model refuses.*

Quick Eval was created for the Hermes Agent Plugin Hackathon 2026.

## Features

- **One command.** `/quick-eval` works the same way in the terminal, Hermes Desktop, and chat gateways, because it uses typed text commands instead of interactive pickers.
- **Fair comparisons.** Each model receives only your last question, with no system prompt or history, and every model runs with the same settings.
- **No model setup.** Quick Eval lists the providers Hermes is already signed in to, and it finds local model servers such as Ollama, LM Studio, vLLM, and llama-server.
- **Review page.** A browser view shows each chat turn with its answers in columns, plus a leaderboard of how often each model's answer was marked good.
- **Plain data.** Runs and judgments are appended to `~/.hermes/evals/evals.jsonl`, which you can export, query, or reuse as test cases.

## Requirements

- Hermes Agent 0.19 or later. Quick Eval is tested on 0.19 and 0.23.
- At least one model besides the one you chat with. This can be any provider Hermes is configured for, or a local OpenAI-compatible server.

## Install

Install the plugin from the Hermes plugin catalog:

```sh
hermes plugins install quick-eval
```

To install it directly from GitHub instead:

```sh
hermes plugins install tikiverse/quick-eval/plugins/quick-eval --enable
```

Restart `hermes` after you install the plugin.

## Demo

A local demo runs two small Ollama models, so it needs no account or API key. The steps are in [docs/demo.md](https://github.com/tikiverse/quick-eval/blob/main/docs/demo.md).

## Usage

### Commands

| Command | Description |
|---|---|
| `/quick-eval` | Shows your last question, the models you can name, and the available commands. |
| `/quick-eval <model> [<model> ...]` | Sends your last question to each named model in parallel and prints the answers. |
| `/quick-eval pick A,B [note]` | Marks the good answers of the last run. Several answers can be good. Use `none` if no answer is good. |
| `/quick-eval open` | Opens the review page: the **Quick Eval** page in Hermes Desktop when you run it in a Desktop chat, otherwise a browser page at `http://127.0.0.1:8765`. |
| `/quick-eval allow` | Grants the one-time permission to send your questions to other models. Quick Eval asks for this on first use. |

A model name can be any name that `/quick-eval` lists, a provider model ID such as `anthropic/claude-sonnet-5.5`, or `model@provider`. A name that matches none of these is treated as a typo, and Quick Eval calls no model.

### Choose models

You don't need to configure models. `/quick-eval` lists the models available through the providers Hermes is signed in to. It also checks for local servers on their default ports:

| Server | Port |
|---|---|
| Ollama | 11434 |
| LM Studio | 1234 |
| vLLM | 8000 |
| llama-server | 8080 |

When you name a model from a local server, Quick Eval adds that server to your Hermes configuration as a provider, so you don't have to edit the configuration by hand.

### Configure

Quick Eval stores its settings in the `plugins.entries.quick-eval` section of your Hermes `config.yaml`. All keys are optional.

```yaml
plugins:
  entries:
    quick-eval:
      llm: {allow_model_override: true, allow_provider_override: true}
      default: [claude]
      params: {temperature: 0.7, max_tokens: 1024, timeout: 120}
      models:
        claude: {provider: openrouter, model: anthropic/claude-sonnet-5.5}
```

| Key | Description |
|---|---|
| `llm` | The permission that `/quick-eval allow` writes. |
| `default` | Models that `/quick-eval` uses in its example command. |
| `params` | Settings that every compared model receives. `timeout` is in seconds and applies to each model separately. |
| `models` | Short names (aliases) for models you compare often. |

### Review page

Run `/quick-eval open`, or open the **Quick Eval** tab in `hermes dashboard`. In Hermes Desktop, the command shows the **Quick Eval** page from the sidebar. That needs Hermes 0.22.3 or newer behind Desktop, a chat created in Desktop, and the one-time switch **Capabilities > Plugins > Quick Eval** (Desktop ships a plugin's Desktop page off; installing through Desktop's own plugin installer turns it on for you); on an older Hermes, or in a chat started in a terminal, the command opens the browser page instead. In a terminal, it always opens the browser page, even when Hermes Desktop is installed. The page reads your Hermes chat history and has two tabs:

- **Review** lists your chats, with the current one pinned. Each chat turn shows the agent's reply, or one column per model after a `/quick-eval` run. Select every good answer, then optionally add a note and the answer you expected.
- **Leaderboard** shows, for each model, how often its answer was marked good and how many times it was the only good answer.

| Key | Action |
|---|---|
| `j` / `k` | Move to the next or previous turn. |
| `a`–`e` | Toggle an answer as good. |
| `t` | Mark all answers good. |
| `n` | Mark no answer good. |
| `Cmd+Enter` | Save. |

To export your data, select **Export JSONL** on the review page.

### Eval log

Quick Eval appends one `run` line per `/quick-eval` and one `judgment` line per pick to `~/.hermes/evals/evals.jsonl`. Lines are never rewritten. For the full format, see [Eval log format](https://github.com/tikiverse/quick-eval/blob/main/docs/eval-log.md).

## Data and network access

- **Model calls.** `/quick-eval` sends only your last question to the models you name. Calls go through Hermes's plugin LLM API (`ctx.llm`) and your configured providers.
- **Local probes.** `/quick-eval` checks `localhost` ports 11434, 1234, 8000, and 8080 for local model servers.
- **Files written.** `~/.hermes/evals/evals.jsonl` (append-only), and the plugin's own section of `config.yaml` for the `/quick-eval allow` permission and any local server you name.
- **Files read.** `~/.hermes/state.db`, read-only, for the review page.
- **Local server.** `/quick-eval open` in a terminal serves the review page on `127.0.0.1:8765` until Hermes exits. In Hermes Desktop it uses the plugin's Desktop page and starts no server.

Quick Eval runs no shell commands, stores no credentials, sends no telemetry, and doesn't update itself.

## Known limitations

- **Hermes versions before 0.19.** On older versions, `/quick-eval` replies with a message to update Hermes.
- **Local reasoning models.** Hermes doesn't pass a custom provider's `extra_body` or `max_tokens` on plugin calls ([hermes-agent#124290](https://github.com/NousResearch/hermes-agent/pull/124290), [#50132](https://github.com/NousResearch/hermes-agent/issues/50132)). As a result, models such as Qwen3 always think, and a server with a small default token limit can return an empty answer. Quick Eval reports this instead of showing a blank answer. To work around it, turn off thinking on the server, for example `mlx_lm.server --chat-template-args '{"enable_thinking": false}'`, or raise the server's default token limit.
- **Command name.** The command is `/quick-eval` instead of `/eval` because Hermes gives a command name that two plugins share to whichever plugin loads last, without a warning.

## Development

You need [uv](https://docs.astral.sh/uv/) and Python 3.11 to 3.13.

1. Clone the repository and install the development dependencies:

   ```sh
   git clone https://github.com/tikiverse/quick-eval.git
   cd quick-eval
   uv sync
   ```

1. Run the tests:

   ```sh
   uv run pytest
   ```

   Tests marked `hermes` start the real Hermes CLI as a subprocess. To skip them, run `uv run pytest -m "not hermes"`.

1. Link the plugin into a Hermes home so your edits load on the next `hermes` start. The script creates symlinks under `$HERMES_HOME/plugins` (default `~/.hermes/plugins`) and enables the plugin.

   ```sh
   scripts/link-plugins.sh quick-eval
   ```

   To keep your own Hermes home separate, set `HERMES_HOME`, for example `HERMES_HOME=~/.hermes-dev scripts/link-plugins.sh quick-eval`.

1. Work on the review page without Hermes. The page has no build step: edit `dashboard/dist/index.js` and `dashboard/dist/style.css`, then reload.

   ```sh
   uv run python plugins/quick-eval/standalone.py --open
   ```

1. Before you submit a change, run the catalog validator. It requires Hermes 0.23 or later.

   ```sh
   hermes plugins validate "$PWD/plugins/quick-eval" --install-deps
   ```

### Project layout

| Path | Contents |
|---|---|
| `plugins/quick-eval/__init__.py` | Plugin entry point: registers the `/quick-eval` command and the `post_llm_call` hook. |
| `plugins/quick-eval/discover.py` | Finds signed-in providers and local model servers. |
| `plugins/quick-eval/evals.py`, `quickeval_log.py` | Runs comparisons and reads and writes the eval log. |
| `plugins/quick-eval/settings.py` | Reads and writes the plugin's section of `config.yaml`. |
| `plugins/quick-eval/standalone.py`, `quickeval_*.py`, `sql/` | Review page server and its API. |
| `plugins/quick-eval/dashboard/` | Review page assets and the `hermes dashboard` tab manifest. |
| `tests/test_contract.py` | Checks that `plugin.yaml` declares exactly what `register()` registers. |
| `tests/test_hermes_load.py` | Loads the plugin with Hermes's own plugin loader. |
| `tests/test_quick_eval_e2e.py` | Runs `/quick-eval` through Hermes against a fake model server. |
| `scripts/demo.sh`, `demo/config.yaml` | The one-line demo. |
| `docs/catalog/quick-eval.yaml` | Draft entry for the Hermes plugin catalog. |

The test harness gives `register()` a plugin context without `ctx.llm`, like the validator's probe does. A `register()` that uses `ctx.llm` too early fails in the tests before it fails in Hermes.

## License

Quick Eval is released under the [MIT License](LICENSE).
