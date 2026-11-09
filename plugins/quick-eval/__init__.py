"""why: quick-eval. /quick-eval asks other models your last question and lets you pick the best answer.

/quick-eval [model ...]                 ask; then pick a winner (terminal) or get a /quick-eval pick hint
/quick-eval pick A|A,B|tie|none [note]  record the good answer(s) of the last /quick-eval
/quick-eval open                        open the UI: review chats and their answers, leaderboard
"""
import sys
import threading
import webbrowser
from dataclasses import dataclass
from functools import partial
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import quickeval_log  # noqa: E402
import standalone  # noqa: E402

from . import discover, evals, settings  # noqa: E402
from .ui import TerminalUI, file_link  # noqa: E402

PORT = 8765
UI_URL = f"http://127.0.0.1:{PORT}/"
NO_TURN = "Nothing to evaluate yet. Ask the agent something first, then run /quick-eval."
TRUST_QUESTION = "quick-eval needs permission to send your last question to other models. Save this permission?"
PICK_TITLE = "Compare with which models? (space to toggle, enter to run)"
WINNER_TITLE = "Which answer wins? (Esc to skip)"


@dataclass
class Option:
    label: str
    target: evals.Target
    new_provider: dict | None = None


def open_ui():
    if not standalone.is_running(PORT):
        server = standalone.serve(PORT)
        threading.Thread(target=server.serve_forever, daemon=True).start()
    webbrowser.open(UI_URL)
    return f"quick-eval UI: {UI_URL}"


def alias_option(name, alias):
    if not isinstance(alias, dict) or not alias.get("model"):
        return None
    label = f"{name}: {alias['model']} · {alias.get('provider') or 'default'}"
    return Option(label, evals.Target(name, alias["model"], alias.get("provider")))


def local_options(server):
    return [Option(f"{m} · {server['name']} (local, adds it to Hermes)", evals.Target(m, m, server["slug"]), server)
            for m in server["models"]]


def winner_words(run):
    return [a["label"] for a in run["answers"]] + ["tie", "none"]


def winner_labels(run):
    return [f"{a['label']} · {a.get('model') or 'unknown'}" for a in run["answers"]] + ["All good", "No good answer"]


class QuickEval:
    def __init__(self, llm, ui, config=None, store=None, find_hermes=None, find_local=None):
        self.llm = llm
        self.ui = ui
        self.config = config or settings.HermesConfig()
        self.store = store or quickeval_log.EvalLog(Path(self.config.home()) / "evals" / "evals.jsonl")
        self.find_hermes = find_hermes or discover.hermes_models
        self.find_local = find_local or discover.local_servers
        self.last_turn = None
        self.last_run = None
        self.subcommands = {"open": self.cmd_open, "pick": self.cmd_pick}

    def on_post_llm_call(self, user_message=None, assistant_response=None, model=None, session_id=None, **kwargs):
        if user_message and assistant_response:
            self.last_turn = {"prompt": user_message, "response": assistant_response, "model": model,
                              "session_id": session_id}

    def cmd_eval(self, raw_args: str = "") -> str:
        words = (raw_args or "").split()
        handler = self.subcommands.get(words[0].lower()) if words else None
        if handler:
            return handler(" ".join(words[1:]))
        return self.run(words)

    def cmd_open(self, _raw: str = "") -> str:
        return open_ui()

    def cmd_pick(self, raw: str = "") -> str:
        run = self.last_run or self.store.latest_run()
        if not run:
            return "No eval to pick from yet. Run /quick-eval first."
        return self.save_pick(run, raw)

    def run(self, names):
        if not self.last_turn:
            return NO_TURN
        config = self.ensure_trusted()
        if isinstance(config, str):
            return config
        targets = self.targets_for(names, config)
        if isinstance(targets, str) or not targets:
            return targets or "No models picked."
        kept, skipped = evals.split_same(targets, self.last_turn.get("model"))
        note = evals.skipped_note(skipped)
        if not kept:
            return f"{note} Pick a different model."
        return "\n".join(filter(None, [note, self.ask(kept, settings.params(config))]))

    def ensure_trusted(self):
        config = self.config.load()
        if settings.is_trusted(config):
            return config
        if not self.ui.confirm(TRUST_QUESTION):
            return ("quick-eval can't call other models until it's allowed. "
                    f"Run /quick-eval in a terminal to approve it, or edit {file_link(self.config.path())}")
        self.config.save(settings.trust_patch())
        return self.config.load()

    def targets_for(self, names, config):
        if names:
            return evals.resolve_targets(names, settings.aliases(config))
        return self._choose_targets(config)

    def ask(self, targets, params):
        self.ui.say(f"Asking {', '.join(t.describe() for t in targets)}...")
        run = self.store.append(evals.run_eval(self.last_turn, targets, self.llm.complete, params))
        self.last_run = run
        return evals.format_eval(run) + "\n" + self.prompt_winner(run)

    def prompt_winner(self, run):
        picked = self.ui.pick_one(WINNER_TITLE, winner_labels(run))
        if picked is None:
            return evals.pick_hint(run)
        return self.save_pick(run, winner_words(run)[picked])

    def save_pick(self, run, raw):
        judged = evals.parse_pick(raw, run)
        if isinstance(judged, str):
            return judged
        self.store.append(judged)
        verdict = evals.verdict_text(run, judged["winner"], judged.get("good"))
        return f"Saved: {verdict} for eval {run['id']}. Log: {file_link(self.store.path)}"

    def _options(self, config: dict) -> list[Option]:
        aliased = [o for o in (alias_option(n, a) for n, a in settings.aliases(config).items()) if o]
        seen = {(o.target.provider, o.target.model) for o in aliased}
        found = [Option(f"{model} · {provider}", evals.Target(model, model, provider))
                 for provider, model in dict.fromkeys(self.find_hermes()) if (provider, model) not in seen]
        known = settings.configured_provider_apis(config)
        local = [o for s in self.find_local() if s["api"].rstrip("/") not in known for o in local_options(s)]
        return aliased + found + local

    def default_targets(self, defaults, config):
        if not defaults:
            return ("No default models set. Use /quick-eval <alias or model>, or add a default list in "
                    f"{file_link(self.config.path())}")
        return evals.resolve_targets(defaults, settings.aliases(config))

    def _choose_targets(self, config: dict):
        defaults = settings.defaults(config)
        if not self.ui.interactive:
            return self.default_targets(defaults, config)
        options = self._options(config)
        if not options:
            return ("No models found. Sign in to a provider with `hermes model`, or add aliases in "
                    f"{file_link(self.config.path())}")
        preselected = {i for i, o in enumerate(options) if o.target.name in defaults}
        chosen = [options[i] for i in self.ui.pick_many(PICK_TITLE, [o.label for o in options], preselected) or []]
        self.add_local_providers(chosen)
        return [o.target for o in chosen]

    def add_local_providers(self, chosen):
        servers = {o.new_provider["slug"]: o.new_provider for o in chosen if o.new_provider}
        for server in servers.values():
            self.config.save(settings.provider_patch(server["slug"], server["name"], server["api"]))
        if servers:
            self.ui.say(f"Added {', '.join(s['name'] for s in servers.values())} to {file_link(self.config.path())}")


class LazyLLM:
    """why: `ctx.llm` exists only once Hermes runs; the catalog's capability probe calls register() without it."""

    def __init__(self, ctx):
        self.ctx = ctx

    def complete(self, *args, **kwargs):
        return self.ctx.llm.complete(*args, **kwargs)


def register(ctx):
    manager = getattr(ctx, "_manager", None)
    plugin = QuickEval(llm=LazyLLM(ctx), ui=TerminalUI(partial(getattr, manager, "_cli_ref", None)))
    ctx.register_hook("post_llm_call", plugin.on_post_llm_call)
    # why: Hermes silently gives a shared command name to the last-loaded plugin; the plugin's own name can't clash
    ctx.register_command("quick-eval", plugin.cmd_eval,
                         description="Ask other models your last question; pick the best",
                         args_hint="[model ...] | pick A|A,B|tie|none [note] | open")
