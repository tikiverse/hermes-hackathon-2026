"""why: quick-eval. Ask other models your last question, then mark which answers were good.

/quick-eval                        help: your last question, the models you can name, the commands
/quick-eval <model> [model ...]    ask them; answers print side by side
/quick-eval pick A,B [note]        mark the good answers of the last run (or: none)
/quick-eval open                   review page: Hermes Desktop's Quick Eval page when run there, else the browser
/quick-eval allow                  one-time permission to send your question to other models (Hermes before the
                                   consent screen; newer Hermes asks at `hermes plugins enable quick-eval`)

why text only: Hermes 0.19 runs plugin commands in the terminal, newer ones in the gateway; a typed command works
on both and in chat apps, where a terminal picker does not.
"""
import logging
import re
import sys
import threading
import webbrowser
from functools import partial
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import quickeval_log  # noqa: E402
import standalone  # noqa: E402

from . import discover, evals, settings  # noqa: E402

log = logging.getLogger(__name__)
# why: Desktop ships a Desktop page off until switched on once, and nothing tells us if it is on: name the switch
DESKTOP_OPENED = ("quick-eval: opened the Quick Eval page in Hermes Desktop (sidebar: Quick Eval). Nothing opened? "
                  "Turn Quick Eval on once in Desktop: Capabilities > Plugins")
PORT = 8765
UI_URL = f"http://127.0.0.1:{PORT}/"
NO_TURN = "Nothing to evaluate yet. Ask the agent something first, then run /quick-eval."
NOT_ALLOWED = "First run /quick-eval allow: it lets quick-eval send your last question to other models."
NOT_GRANTED = ("quick-eval needs your permission to send your last question to other models. In a terminal, run "
               "`hermes plugins enable quick-eval` and grant it.")
MAX_LISTED = 8
MANIFEST = Path(__file__).resolve().parent / "plugin.yaml"
COMMANDS = [
    ("/quick-eval {example}", "ask them (names from the list above)"),
    ("/quick-eval pick A,B [note]", "mark the good answers (or: none)"),
    ("/quick-eval open", "open the review page"),
]


def open_ui():
    if not standalone.is_running(PORT):
        server = standalone.serve(PORT)
        threading.Thread(target=server.serve_forever, daemon=True).start()
    webbrowser.open(UI_URL)
    return f"quick-eval UI: {UI_URL}"


def open_in_desktop():
    """why: a Desktop chat has its own Quick Eval page; ask that page to show itself (desktop/plugin.js listens)
    instead of opening a browser. Hermes without the plugin event stream falls back to the browser page."""
    try:
        from hermes_cli.plugin_events import broadcast_plugin_event
    except ImportError:
        return open_ui()
    broadcast_plugin_event("quick-eval", "open")
    return DESKTOP_OPENED


OPENERS = {"desktop": open_in_desktop}  # why: surface Hermes passes (`platform`) -> opener; others get the browser


def file_link(path: Path) -> str:
    """why: OSC 8 makes the path clickable in terminals that support it."""
    uri = Path(path).resolve().as_uri()
    return f"\033]8;;{uri}\033\\{path}\033]8;;\033\\"


def shorten(text, size=70):
    line = " ".join(str(text).split())
    return line if len(line) <= size else line[:size - 1] + "…"


def model_lines(rows):
    shown = [f"  {name:<24} {where}" for name, where in rows[:MAX_LISTED]]
    more = len(rows) - MAX_LISTED
    return shown + ([f"  … {more} more; any model also works as model@provider"] if more > 0 else [])


def version_tuple(text):
    return tuple(int(part) for part in re.findall(r"\d+", text)[:3])


def min_hermes():
    """why: plugin.yaml's requires_hermes is the one source; Hermes 0.19 ignores that key, so the plugin checks too."""
    return re.search(r'requires_hermes:\s*"?>=\s*([\d.]+)', MANIFEST.read_text()).group(1)


def too_old_message(version):
    """why: Hermes older than the tested floor lacks what this plugin calls; refuse with a fix, never half-work."""
    if version_tuple(version) >= version_tuple(min_hermes()):
        return None
    return f"quick-eval needs Hermes {min_hermes()} or newer; this is {version}. Run: hermes update"


def is_model_id(name):
    """why: a provider-style id (org/model) or model@provider names a model the list may not show; a bare unknown
    word is far more often a typo (`/quick-eval pikc A`) that must not call models."""
    return "/" in name or "@" in name


def aliased_models(config):
    return [(n, a["model"]) for n, a in settings.aliases(config).items() if isinstance(a, dict) and a.get("model")]


def command_lines(example):
    return [f"  {cmd.format(example=example):<30} {what}" for cmd, what in COMMANDS]


class QuickEval:
    def __init__(self, llm, config=None, store=None, find_hermes=None, find_local=None, say=print):
        self.llm = llm
        self.config = config or settings.HermesConfig()
        self.store = store or quickeval_log.EvalLog(Path(self.config.home()) / "evals" / "evals.jsonl")
        self.find_hermes = find_hermes or discover.hermes_models
        self.find_local = find_local or discover.local_servers
        self.say = say
        self.last_turn = None
        self.last_run = None
        self.subcommands = {"open": self.cmd_open, "pick": self.cmd_pick, "allow": self.cmd_allow}

    def on_post_llm_call(self, user_message=None, assistant_response=None, model=None, session_id=None, **kwargs):
        if user_message and assistant_response:
            self.last_turn = {"prompt": user_message, "response": assistant_response, "model": model,
                              "session_id": session_id}

    def cmd_eval(self, raw_args: str = "", platform: str | None = None) -> str:
        """why: Hermes passes the surface a command ran on (`platform`) to handlers that name it; 0.19 passes none."""
        words = (raw_args or "").split()
        if not words:
            return self.help()
        handler = self.subcommands.get(words[0].lower())
        return handler(" ".join(words[1:]), platform=platform) if handler else self.run(words)

    def cmd_open(self, _raw: str = "", platform: str | None = None) -> str:
        """why: the log line names the surface Hermes passed, so a browser page in Desktop can be traced
        (a chat started in a terminal and resumed in Desktop keeps the surface `tui`)."""
        log.info("quick_eval.open surface=%s", platform)
        return OPENERS.get(platform, open_ui)()

    def cmd_allow(self, _raw: str = "", **_surface) -> str:
        if has_consent_screen():
            return NOT_GRANTED
        self.config.save(settings.trust_patch())
        return f"Allowed. Saved in {file_link(self.config.path())}. Now: /quick-eval <model>"

    def cmd_pick(self, raw: str = "", **_surface) -> str:
        run = self.last_run or self.store.latest_run()
        if not run:
            return "No eval to pick from yet. Run /quick-eval first."
        return self.save_pick(run, raw)

    def help(self) -> str:
        config = self.config.load()
        rows = self.model_rows(config)
        asked = f"Last question: {shorten(self.last_turn['prompt'])}" if self.last_turn else NO_TURN
        example = " ".join((settings.defaults(config) or [name for name, _ in rows[:2]] or ["<model>"])[:2])
        lines = ["quick-eval: ask other models your last question, then mark the good answers.", asked, ""]
        lines += ["Models you can name:", *(model_lines(rows) or ["  none found: name one as model@provider"]), ""]
        lines += ["Commands:", *command_lines(example)]
        return "\n".join(lines + ([] if settings.is_trusted(config) else ["", not_allowed()]))

    def model_rows(self, config):
        """why: aliases first (the user named them), then local servers, then models Hermes is signed in to; the
        model that wrote the answer you saw is left out: asking it again compares it with itself."""
        aliased = [(n, f"{a['model']} · {a.get('provider') or 'default'}")
                   for n, a in settings.aliases(config).items() if isinstance(a, dict) and a.get("model")]
        covered = {a for _, a in aliased_models(config)}
        local = [(name, f"{s['name']}, local") for name, (s, m) in self.local_models().items() if m not in covered]
        signed_in = [(m, p) for p, m in dict.fromkeys(self.find_hermes())]
        seen = {(self.last_turn or {}).get("model")}
        rows = []
        for name, where in aliased + local + signed_in:
            if name not in seen:
                seen.add(name)
                rows.append((name, where))
        return rows

    def run(self, names):
        if not self.last_turn:
            return NO_TURN
        config = self.config.load()
        if not settings.is_trusted(config):
            return not_allowed()
        unknown = self.unknown_names(names, config)
        if unknown:
            return unknown
        targets = self.targets_for(names, config)
        kept, skipped = evals.split_same(targets, self.last_turn.get("model"))
        note = evals.skipped_note(skipped)
        if not kept:
            return f"{note} Name a different model: /quick-eval lists them."
        return "\n".join(filter(None, [note, self.ask(kept, settings.params(config))]))

    def unknown_names(self, names, config):
        listed = {name for name, _ in self.model_rows(config)} | set(settings.aliases(config))
        listed.add((self.last_turn or {}).get("model"))
        unknown = [n for n in names if n not in listed and not is_model_id(n)]
        if not unknown:
            return None
        return (f"Unknown model {', '.join(unknown)}. Run /quick-eval to see the names you can use, "
                "or name one as model@provider.")

    def targets_for(self, names, config):
        """why: a name served by a local server it finds becomes that server's model; the server joins Hermes once."""
        aliases = settings.aliases(config)
        found = self.local_models()
        served = {n: found[n] for n in names if n in found and n not in aliases}
        self.add_servers({s["slug"]: s for s, _ in served.values()}.values(), settings.configured_provider_apis(config))
        return [evals.Target(n, served[n][1], served[n][0]["slug"]) if n in served else evals.target_for(n, aliases)
                for n in names]

    def local_models(self):
        """why: a server can name its model by a cache path; the user types the short name the help shows."""
        return {evals.short_model(m): (s, m) for s in self.find_local() for m in s["models"]}

    def add_servers(self, servers, known):
        for server in servers:
            if server["api"].rstrip("/") not in known:
                self.config.save(settings.provider_patch(server["slug"], server["name"], server["api"]))

    def ask(self, targets, params):
        self.say(f"Asking {', '.join(t.describe() for t in targets)}...")
        run = self.store.append(evals.run_eval(self.last_turn, targets, self.llm.complete, params))
        self.last_run = run
        return evals.format_eval(run) + "\n" + evals.pick_hint(run)

    def save_pick(self, run, raw):
        judged = evals.parse_pick(raw, run)
        if isinstance(judged, str):
            return judged
        self.store.append(judged)
        verdict = evals.verdict_text(run, judged["winner"], judged.get("good"))
        return f"{verdict}. See it: /quick-eval open"


class LazyLLM:
    """why: `ctx.llm` exists only once Hermes runs; the catalog's capability probe calls register() without it."""

    def __init__(self, ctx):
        self.ctx = ctx

    def complete(self, *args, **kwargs):
        return self.ctx.llm.complete(*args, **kwargs)


def has_consent_screen():
    """why: newer Hermes grants plugin.yaml's `capabilities` on its own consent screen; the plugin must not
    write the grant itself there. Older Hermes has no such screen, so /quick-eval allow writes it."""
    try:
        import hermes_cli.plugin_capabilities  # noqa: F401
    except ImportError:
        return False
    return True


def not_allowed():
    return NOT_GRANTED if has_consent_screen() else NOT_ALLOWED


def hermes_version():
    from hermes_cli import __version__

    return __version__


def refuse(message, _raw=""):
    return message


def register(ctx):
    old = too_old_message(hermes_version())
    if old:
        ctx.register_command("quick-eval", partial(refuse, old), description=old)
        return
    plugin = QuickEval(llm=LazyLLM(ctx))
    ctx.register_hook("post_llm_call", plugin.on_post_llm_call)
    # why: Hermes silently gives a shared command name to the last-loaded plugin; the plugin's own name can't clash
    ctx.register_command("quick-eval", plugin.cmd_eval,
                         description="Ask other models your last question; mark the good answers",
                         args_hint="[model ...] | pick A,B [note] | open | allow")
