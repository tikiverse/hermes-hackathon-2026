from dataclasses import dataclass
from pathlib import Path

from . import discover, evals, settings
from .store import EvalStore
from .ui import TerminalUI, file_link


@dataclass
class Option:
    label: str
    target: evals.Target
    new_provider: dict | None = None


class QuickEval:
    def __init__(self, llm, ui, config=None, store=None, find_hermes=None, find_local=None):
        self.llm = llm
        self.ui = ui
        self.config = config or settings.HermesConfig()
        self.store = store or EvalStore(Path(self.config.home()) / "evals" / "evals.jsonl")
        self.find_hermes = find_hermes or discover.hermes_models
        self.find_local = find_local or discover.local_servers
        self.last_turn = None
        self.last_eval = None

    def on_post_llm_call(self, user_message=None, assistant_response=None, model=None, session_id=None, **kwargs):
        if user_message and assistant_response:
            self.last_turn = {
                "prompt": user_message,
                "response": assistant_response,
                "model": model,
                "session_id": session_id,
            }

    def cmd_eval(self, raw_args: str = "") -> str:
        if not self.last_turn:
            return "Nothing to evaluate yet. Ask the agent something first, then run /eval."

        config = self.config.load()
        if not settings.is_trusted(config):
            allowed = self.ui.confirm(
                "quick-eval needs permission to send your last question to other models. "
                "Save this permission to config.yaml?"
            )
            if not allowed:
                return (
                    "quick-eval can't call other models until it's allowed. "
                    f"Run /eval in a terminal to approve it, or edit {file_link(self.config.path())}"
                )
            self.config.save(settings.trust_patch())
            config = self.config.load()

        names = raw_args.split()
        if names:
            targets = evals.resolve_targets(names, settings.aliases(config))
        else:
            targets = self._choose_targets(config)
            if isinstance(targets, str):
                return targets
        if not targets:
            return "No models picked."

        self.ui.say(f"Asking {', '.join(t.describe() for t in targets)}...")
        record = evals.run_eval(self.last_turn, targets, self.llm.complete)
        self.store.append(record)
        self.last_eval = record
        return evals.format_eval(record)

    def cmd_score(self, raw_args: str = "") -> str:
        record = self.last_eval or self.store.latest_eval()
        if not record:
            return "No eval to score yet. Run /eval first."
        score = evals.parse_score(raw_args, record)
        if isinstance(score, str):
            return score
        self.store.append(score)
        winner = score["winner"]
        if winner in ("tie", "none"):
            verdict = "tie" if winner == "tie" else "no good answer"
        else:
            verdict = f"{winner} wins ({score['winner_model']})"
        return f"Saved: {verdict} for eval {record['id']}. Log: {file_link(self.store.path)}"

    def _options(self, config: dict) -> list[Option]:
        options, seen = [], set()
        for name, alias in settings.aliases(config).items():
            if not isinstance(alias, dict) or not alias.get("model"):
                continue
            target = evals.Target(name, alias["model"], alias.get("provider"))
            seen.add((target.provider, target.model))
            options.append(Option(f"{name}: {alias['model']} · {alias.get('provider') or 'default'}", target))
        for provider, model in self.find_hermes():
            if (provider, model) not in seen:
                seen.add((provider, model))
                options.append(Option(f"{model} · {provider}", evals.Target(model, model, provider)))
        known_apis = settings.configured_provider_apis(config)
        for server in self.find_local():
            if server["api"].rstrip("/") in known_apis:
                continue
            for model in server["models"]:
                options.append(
                    Option(
                        f"{model} · {server['name']} (local, adds it to Hermes)",
                        evals.Target(model, model, server["slug"]),
                        new_provider=server,
                    )
                )
        return options

    def _choose_targets(self, config: dict) -> list[evals.Target] | str:
        default_names = settings.defaults(config)
        if not self.ui.interactive:
            if not default_names:
                return (
                    "No default models set. Use /eval <alias or model>, or add a default list in "
                    f"{file_link(self.config.path())}"
                )
            return evals.resolve_targets(default_names, settings.aliases(config))

        options = self._options(config)
        if not options:
            return f"No models found. Sign in to a provider with `hermes model`, or add aliases in {file_link(self.config.path())}"
        preselected = {i for i, o in enumerate(options) if o.target.name in default_names}
        picked = self.ui.pick_many("Compare with which models? (space to toggle, enter to run)", [o.label for o in options], preselected)
        chosen = [options[i] for i in picked or []]

        added = {}
        for option in chosen:
            server = option.new_provider
            if server and server["slug"] not in added:
                self.config.save(settings.provider_patch(server["slug"], server["name"], server["api"]))
                added[server["slug"]] = server
        if added:
            self.ui.say(f"Added {', '.join(s['name'] for s in added.values())} to {file_link(self.config.path())}")
        return [o.target for o in chosen]


def register(ctx):
    manager = getattr(ctx, "_manager", None)
    plugin = QuickEval(llm=ctx.llm, ui=TerminalUI(lambda: getattr(manager, "_cli_ref", None)))
    ctx.register_hook("post_llm_call", plugin.on_post_llm_call)
    ctx.register_command(
        "eval", plugin.cmd_eval, description="Compare your last answer with other models", args_hint="[model ...]"
    )
    ctx.register_command("score", plugin.cmd_score, description="Score the last /eval", args_hint="A|B|tie [note]")
