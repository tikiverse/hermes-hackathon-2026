<!-- Body for the NousResearch/hermes-agent PR "plugin-catalog: add quick-eval (Plugin Hackathon entry)". Replace <sha> before posting. -->
Hermes Agent Plugin Hackathon entry.

Plugin: https://github.com/tikiverse/quick-eval (subdir `plugins/quick-eval`)
Pinned SHA: <sha>
Demo video: https://x.com/ShaunPorwal/status/2120623874555396133

![The six steps of a Quick Eval run, in Hermes Desktop](https://raw.githubusercontent.com/tikiverse/quick-eval/<sha>/docs/img/demo.gif)

## What it does

Quick Eval gets a second opinion on an answer. After the agent replies, `/quick-eval` sends your last question to other models, prints the answers side by side, and records which ones you mark good (`/quick-eval pick A,B`). Every run and pick is appended to a local JSONL file, so the questions you ask become an evaluation dataset, and a leaderboard shows which models you trust most.

- `/quick-eval` lists your last question, the models you can name (the providers Hermes is signed in to, plus local Ollama, LM Studio, vLLM and llama-server), and the commands.
- `/quick-eval <model> ...` asks them in parallel with the same settings and no system prompt or history.
- `/quick-eval open` shows the review page: the **Quick Eval** page inside Hermes Desktop when run from a Desktop chat, a browser page on `127.0.0.1:8765` from a terminal.

## Hermes surfaces used

- `ctx.register_command("quick-eval", ...)`: the one command. Text only, so it works the same in the terminal, Desktop and chat gateways. The handler names `platform` to learn its surface.
- `ctx.register_hook("post_llm_call", ...)`: remembers the last question and answer.
- `ctx.llm`: the model calls, through your configured providers.
- Desktop plugin SDK (`desktop/plugin.js`): a sidebar page. Only `@hermes/plugin-sdk` and `react` are imported; it listens for `plugin.quick-eval.open` (sent with `broadcast_plugin_event`) and calls `host.navigate`.
- Dashboard tab (`dashboard/manifest.json`, `plugin_api.py`): the same review page in `hermes dashboard`.
- Desktop ships a plugin's Desktop page off until it is switched on once (Capabilities > Plugins). Installing through Desktop's installer turns it on; the plugin README shows the switch with a GIF for other installs.

## Disclosure (rule 13)

- **Model calls:** only your last question, to the models you name, through `ctx.llm`. It declares `llm.model_override` and `llm.provider_override`, so Hermes asks for them on its consent screen; older Hermes uses `/quick-eval allow` once.
- **Local probes:** `localhost` ports 11434, 1234, 8000 and 8080, to find local model servers.
- **Files written:** `~/.hermes/evals/evals.jsonl` (append-only); the plugin's own section of `config.yaml` after the permission is granted or when you name a local server.
- **Files read:** `~/.hermes/state.db`, read-only, for the review page.
- **Local server:** `/quick-eval open` from a terminal serves the page on `127.0.0.1:8765` (a free port if another Hermes holds it) until Hermes exits. The page is locked: a new random token each launch, carried only by the URL it opens and required on every API call; requests must name `127.0.0.1` or `localhost` as Host; POSTs must be JSON. In Hermes Desktop it starts no server.
- No shell commands, credentials, telemetry or self-updates. The README's demo (`docs/demo.md`, outside the plugin folder) has a `curl | sh` line that users run themselves; the plugin never runs it.

## Validation

`hermes plugins validate <plugin dir>` at the pinned SHA passes (including `desktop surface` and `no core override`). One warning remains:

- `private core imports`: `hermes_cli.__version__` (`__init__.py`) and `hermes_cli.model_switch.list_authenticated_providers` (`discover.py`). Hermes 0.19 ignores `requires_hermes`, so the version read lets an older Hermes show "update Hermes" instead of a half-working command; there is no public call for it. The provider list has no public equivalent either. Both are wrapped so a change in Hermes empties that part of the list instead of breaking the command. I opened https://github.com/NousResearch/hermes-agent/issues/153833 asking for both; happy to move to a public seam when one exists.

`requires_hermes: ">=0.19"` is declared in both `plugin.yaml` and the entry; the tests run on 0.19 and 0.23.

Tests: 266 pass in the plugin repo (`uv run pytest -m "not hermes"`), plus 4 that start the real Hermes CLI.
