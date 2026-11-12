import copy
import json
import sys
from dataclasses import dataclass
from functools import partial
from pathlib import Path

import pytest

TRUSTED = {"plugins": {"entries": {"quick-eval": {
    "llm": {"allow_model_override": True, "allow_provider_override": True},
    "default": ["claude"],
    "models": {
        "claude": {"provider": "openrouter", "model": "anthropic/claude-sonnet-5-5"},
        "local": {"provider": "ollama", "model": "llama3.3"},
    },
}}}}
LMSTUDIO = {"slug": "lmstudio", "name": "LM Studio", "api": "http://localhost:1234/v1", "models": ["qwen3-8b"]}


@dataclass
class Result:
    text: str
    model: str
    provider: str


class FakeLLM:
    def __init__(self):
        self.calls = []

    def complete(self, messages, provider=None, model=None, **kwargs):
        self.calls.append({"messages": messages, "provider": provider, "model": model})
        if model == "broken":
            raise RuntimeError("model unavailable")
        if model == "thinker":
            return Result(text="", model=model, provider=provider or "main")
        return Result(text=f"answer from {model}", model=model, provider=provider or "main")


def deep_merge(base, patch):
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            deep_merge(base[key], value)
        else:
            base[key] = copy.deepcopy(value)


class FakeConfig:
    def __init__(self, data, home):
        self.data = copy.deepcopy(data)
        self._home = home
        self.saves = []

    def load(self):
        return copy.deepcopy(self.data)

    def save(self, patch):
        self.saves.append(patch)
        deep_merge(self.data, patch)

    def path(self):
        return self._home / "config.yaml"

    def home(self):
        return self._home


class Found:
    def __init__(self, items):
        self.items = list(items)

    def __call__(self):
        return list(self.items)


def silent(_text):
    return None


def build(module, home, config=TRUSTED, hermes=(), local=()):
    plugin = module.QuickEval(llm=FakeLLM(), config=FakeConfig(config, home), find_hermes=Found(hermes),
                              find_local=Found(local), say=silent)
    plugin.on_post_llm_call(session_id="s1", user_message="What happened at Tiananmen Square in 1989?",
                            assistant_response="Let's talk about something else.", model="deepseek/deepseek-r1")
    return plugin


@pytest.fixture
def module(load):
    return load("quick-eval").module


@pytest.fixture
def make(module, tmp_path):
    return partial(build, module, tmp_path)


def log(plugin):
    return [json.loads(line) for line in Path(plugin.store.path).read_text().splitlines()]


def test_eval_before_any_turn(module, tmp_path):
    plugin = module.QuickEval(llm=FakeLLM(), config=FakeConfig(TRUSTED, tmp_path), find_hermes=Found(()),
                              find_local=Found(()))
    assert "Ask the agent something first" in plugin.cmd_eval("claude")
    assert "Ask the agent something first" in plugin.cmd_eval("")


def test_hook_ignores_incomplete_turns(make):
    plugin = make()
    plugin.on_post_llm_call(session_id="s1", model="x")
    assert plugin.last_turn["prompt"].startswith("What happened")


def test_eval_writes_a_v1_run(make):
    plugin = make()
    out = plugin.cmd_eval("claude local")

    assert [(c["provider"], c["model"]) for c in plugin.llm.calls] == [
        ("openrouter", "anthropic/claude-sonnet-5-5"), ("ollama", "llama3.3")]
    for call in plugin.llm.calls:
        assert call["messages"] == [{"role": "user", "content": "What happened at Tiananmen Square in 1989?"}]

    run = log(plugin)[0]
    assert (run["v"], run["type"], run["session_id"]) == (1, "run", "s1")
    assert [a["label"] for a in run["answers"]] == ["A", "B", "C"]
    assert run["answers"][0] == {"label": "A", "model": "deepseek/deepseek-r1",
                                 "text": "Let's talk about something else."}
    rerun = run["answers"][1]
    assert (rerun["provider"], rerun["error"]) == ("openrouter", None)
    assert rerun["latency_ms"] >= 0
    assert "── B · anthropic/claude-sonnet-5-5" in out
    assert "Next: /quick-eval pick A,B [note]" in out


def test_eval_raw_model_ids(make):
    plugin = make()
    plugin.cmd_eval("llama3.3@ollama openai/gpt-5")
    assert [(c["provider"], c["model"]) for c in plugin.llm.calls] == [("ollama", "llama3.3"), (None, "openai/gpt-5")]


def test_failing_model_does_not_sink_the_eval(make):
    plugin = make()
    out = plugin.cmd_eval("broken@openrouter claude")
    answers = log(plugin)[0]["answers"]
    assert answers[1]["error"] == "RuntimeError: model unavailable"
    assert answers[2]["text"] == "answer from anthropic/claude-sonnet-5-5"
    assert "[error] RuntimeError: model unavailable" in out


def test_untrusted_asks_for_allow_and_calls_nothing(make):
    plugin = make(config={})
    assert "/quick-eval allow" in plugin.cmd_eval("claude")
    assert "/quick-eval allow" in plugin.cmd_eval("")
    assert plugin.llm.calls == []


def test_allow_saves_permission_then_runs(make):
    plugin = make(config={})
    assert "Allowed" in plugin.cmd_eval("allow")
    llm = plugin.config.data["plugins"]["entries"]["quick-eval"]["llm"]
    assert llm == {"allow_model_override": True, "allow_provider_override": True}
    plugin.cmd_eval("openai/gpt-5")
    assert len(plugin.llm.calls) == 1


def test_consent_screen_hermes_grants_permission_itself(make, monkeypatch):
    """why: Hermes with a consent screen grants plugin.yaml's capabilities; /quick-eval allow must not write them."""
    monkeypatch.setitem(sys.modules, "hermes_cli.plugin_capabilities", type(sys)("plugin_capabilities"))
    plugin = make(config={})
    assert "hermes plugins enable quick-eval" in plugin.cmd_eval("allow")
    assert plugin.config.data == {}
    assert "hermes plugins enable quick-eval" in plugin.cmd_eval("claude")
    assert "hermes plugins enable quick-eval" in plugin.cmd_eval("")
    assert plugin.llm.calls == []


def test_manifest_declares_the_llm_capabilities(module):
    manifest = module.MANIFEST.read_text()
    assert "  - llm.model_override\n" in manifest and "  - llm.provider_override\n" in manifest


def listed_names(help_text):
    return [line.split()[0] for line in help_text.split("Models you can name:\n")[1].split("\n\n")[0].splitlines()]


def test_bare_command_is_help_with_question_models_and_commands(make):
    plugin = make(hermes=[("openrouter", "anthropic/claude-sonnet-5-5"), ("openrouter", "openai/gpt-5")],
                  local=[LMSTUDIO])
    out = plugin.cmd_eval("")
    assert plugin.llm.calls == []
    assert "Last question: What happened at Tiananmen Square in 1989?" in out
    assert listed_names(out) == ["claude", "local", "qwen3-8b", "anthropic/claude-sonnet-5-5", "openai/gpt-5"]
    assert "/quick-eval claude " in out and "/quick-eval pick A,B [note]" in out and "/quick-eval open" in out
    assert "/quick-eval allow" not in out


def test_help_caps_a_long_model_list(make):
    hermes = [("openrouter", f"m{i}") for i in range(20)]
    out = make(hermes=hermes).cmd_eval("")
    assert "more; any model also works as model@provider" in out


def test_naming_a_local_server_model_adds_the_server_once(make):
    plugin = make(local=[LMSTUDIO])
    plugin.cmd_eval("qwen3-8b")
    plugin.cmd_eval("qwen3-8b")
    assert plugin.config.data["providers"]["lmstudio"] == {"name": "LM Studio", "api": "http://localhost:1234/v1"}
    assert len(plugin.config.saves) == 1
    assert (plugin.llm.calls[0]["provider"], plugin.llm.calls[0]["model"]) == ("lmstudio", "qwen3-8b")


def test_help_shows_a_short_name_for_a_path_model_and_typing_it_works(make):
    path = "/home/u/.cache/huggingface/hub/models--org--Qwen3-8B-4bit/snapshots/abc"
    server = {"slug": "llamacpp", "name": "llama-server", "api": "http://localhost:8080/v1", "models": [path]}
    plugin = make(local=[server])
    assert "Qwen3-8B-4bit" in plugin.cmd_eval("") and path not in plugin.cmd_eval("")
    plugin.cmd_eval("Qwen3-8B-4bit")
    assert (plugin.llm.calls[0]["provider"], plugin.llm.calls[0]["model"]) == ("llamacpp", path)


def test_help_skips_a_local_model_an_alias_already_names(make):
    ollama = {"slug": "ollama", "name": "Ollama", "api": "http://localhost:11434/v1", "models": ["llama3.3", "qwen3"]}
    assert listed_names(make(local=[ollama]).cmd_eval("")) == ["claude", "local", "qwen3"]


def test_local_server_already_in_hermes_is_not_added_again(make):
    config = copy.deepcopy(TRUSTED)
    config["providers"] = {"lms": {"api": "http://localhost:1234/v1/"}}
    plugin = make(config=config, local=[LMSTUDIO])
    plugin.cmd_eval("qwen3-8b")
    assert plugin.config.saves == []


def test_every_model_gets_the_same_settings_and_a_timeout(make):
    plugin = make()
    plugin.cmd_eval("claude local")
    assert log(plugin)[0]["params"] == {"temperature": 0.7, "max_tokens": 1024, "timeout": 120}


def test_pick_flow(make):
    plugin = make()
    assert "Run /quick-eval first" in plugin.cmd_eval("pick B")
    plugin.cmd_eval("claude")
    assert "Usage: /quick-eval pick" in plugin.cmd_eval("pick")
    assert "Unknown choice 'Z'" in plugin.cmd_eval("pick Z")
    assert "Marked good: B (anthropic/claude-sonnet-5-5)" in plugin.cmd_eval("pick b answered directly")
    judged = log(plugin)[-1]
    assert (judged["run_id"], judged["winner"], judged["note"]) == (log(plugin)[0]["id"], "B", "answered directly")


def test_pick_several_good_answers(make):
    plugin = make()
    plugin.cmd_eval("claude")
    out = plugin.cmd_eval("pick a,b both fine")
    assert "Marked good: A (deepseek/deepseek-r1), B (anthropic/claude-sonnet-5-5)" in out
    judged = log(plugin)[-1]
    assert (judged["good"], judged["winner"], judged["note"]) == (["A", "B"], "tie", "both fine")


def test_pick_tie_and_none(make):
    plugin = make()
    plugin.cmd_eval("claude")
    assert "Marked good: A" in plugin.cmd_eval("pick tie")
    assert "Marked: no good answer" in plugin.cmd_eval("pick NONE")
    assert [r["winner"] for r in log(plugin)[1:]] == ["tie", "none"]


def test_pick_after_restart_reads_log(make, module, tmp_path):
    make().cmd_eval("claude")
    second = module.QuickEval(llm=FakeLLM(), config=FakeConfig(TRUSTED, tmp_path))
    assert "Marked good: B" in second.cmd_eval("pick B")


def test_one_command_named_after_the_plugin(load):
    ctx = load("quick-eval").ctx
    assert list(ctx.commands) == ["quick-eval"]
    assert "pick" in ctx.commands["quick-eval"]["args_hint"]


def refuse(api, timeout):
    if "11434" in api:
        return ["llama3.3", "qwen3"]
    raise ConnectionRefusedError


def test_local_server_probe(module):
    found = module.discover.local_servers(fetch=refuse)
    assert found == [{"slug": "ollama", "name": "Ollama", "api": "http://localhost:11434/v1",
                      "models": ["llama3.3", "qwen3"]}]


def test_local_server_host_override(module, monkeypatch):
    monkeypatch.setenv("QUICK_EVAL_LOCAL_HOST", "host.docker.internal")
    assert module.discover.default_servers()[0] == ("ollama", "Ollama", "http://host.docker.internal:11434/v1")


def test_file_link_is_clickable(module, tmp_path):
    link = module.file_link(tmp_path / "config.yaml")
    assert link.startswith("\033]8;;file://") and link.endswith("\033]8;;\033\\")


def test_local_model_path_shows_its_repo_name(module):
    path = "/Users/x/.cache/huggingface/hub/models--mlx-community--Qwen3-4bit/snapshots/" + "ab" * 20
    answer = {"label": "B", "model": path, "text": "hi", "latency_ms": 5}
    assert module.evals.answer_lines(answer)[0] == "── B · Qwen3-4bit · 5 ms ──"
    assert module.evals.Target("local", path, "Mac mini").describe() == "local (Qwen3-4bit via Mac mini)"


def test_model_that_wrote_the_reply_is_not_asked_again(make):
    plugin = make()
    out = plugin.cmd_eval("deepseek/deepseek-r1 claude")
    assert [c["model"] for c in plugin.llm.calls] == ["anthropic/claude-sonnet-5-5"]
    assert "Skipped deepseek/deepseek-r1: it wrote the reply you saw." in out
    assert [a["label"] for a in log(plugin)[0]["answers"]] == ["A", "B"]


def test_only_the_same_model_picked_asks_nothing(make):
    plugin = make()
    out = plugin.cmd_eval("deepseek/deepseek-r1")
    assert plugin.llm.calls == []
    assert "Name a different model: /quick-eval lists them." in out


def test_empty_answer_is_an_error_with_a_reason(make):
    plugin = make()
    out = plugin.cmd_eval("thinker@ollama")
    answer = log(plugin)[0]["answers"][1]
    assert answer["error"].startswith("empty answer")
    assert "[error] empty answer" in out


def test_a_typo_calls_no_model_and_points_at_the_list(make):
    plugin = make()
    out = plugin.cmd_eval("pikc A")
    assert "Unknown model pikc, A" in out and "Run /quick-eval" in out
    assert plugin.llm.calls == []


def test_help_leaves_out_the_model_that_wrote_the_answer(make):
    out = make(hermes=[("openrouter", "deepseek/deepseek-r1"), ("openrouter", "openai/gpt-5")]).cmd_eval("")
    assert "deepseek/deepseek-r1" not in listed_names(out)


@pytest.mark.parametrize(("version", "refused"), [("0.18.9", True), ("0.19.0", False), ("0.23.0", False)])
def test_hermes_older_than_the_manifest_floor_is_refused_with_a_fix(module, version, refused):
    message = module.too_old_message(version)
    assert (message is not None) == refused
    if refused:
        assert "hermes update" in message and module.min_hermes() in message


class Events:
    """why: stands in for hermes_cli.plugin_events, which Hermes 0.19 (the test env) lacks."""

    def __init__(self):
        self.sent = []

    def broadcast_plugin_event(self, plugin_id, event, payload=None):
        self.sent.append((plugin_id, event, payload))


class Browser:
    """why: stands in for open_ui, so no test starts a server or a browser."""

    def __init__(self):
        self.seen = []

    def open_ui(self):
        self.seen.append("browser")
        return "quick-eval UI: browser"


@pytest.fixture
def opened(module, monkeypatch):
    """why: record which opener ran; no test starts a server or a browser."""
    browser = Browser()
    monkeypatch.setattr(module, "open_ui", browser.open_ui)
    return browser.seen


@pytest.fixture
def events(monkeypatch):
    fake = Events()
    monkeypatch.setitem(sys.modules, "hermes_cli.plugin_events", fake)
    return fake


def test_open_in_a_desktop_chat_asks_the_desktop_page_to_show_itself(make, opened, events):
    out = make().cmd_eval("open", platform="desktop")
    assert events.sent == [("quick-eval", "open", None)]
    assert opened == [] and "Hermes Desktop" in out
    assert "Capabilities > Plugins" in out  # why: Desktop's Desktop page is off until switched on once


@pytest.mark.parametrize("platform", [None, "tui", "cli", "telegram"])
def test_open_anywhere_else_opens_the_browser_page_even_with_desktop_installed(make, opened, events, platform):
    make().cmd_eval("open", platform=platform)
    assert opened == ["browser"] and events.sent == []


def test_open_logs_the_surface_hermes_passed(make, opened, caplog):
    """why: a Desktop chat that resumed a terminal session reports `tui`; the log says so."""
    with caplog.at_level("INFO"):
        make().cmd_eval("open", platform="tui")
    assert "quick_eval.open surface=tui" in caplog.text


def test_open_in_desktop_on_a_hermes_without_plugin_events_opens_the_browser(make, opened, monkeypatch):
    monkeypatch.setitem(sys.modules, "hermes_cli.plugin_events", None)
    assert "browser" in make().cmd_eval("open", platform="desktop")
    assert opened == ["browser"]


def test_every_subcommand_accepts_the_surface_hermes_passes(make):
    plugin = make()
    for words in ("allow", "pick none", ""):
        assert plugin.cmd_eval(words, platform="desktop").strip()
