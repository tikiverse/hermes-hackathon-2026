import copy
import json
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
class Usage:
    input_tokens: int = 10
    output_tokens: int = 20
    cost_usd: float = 0.001


@dataclass
class Result:
    text: str
    model: str
    provider: str
    usage: Usage


class FakeLLM:
    def __init__(self):
        self.calls = []

    def complete(self, messages, provider=None, model=None, **kwargs):
        self.calls.append({"messages": messages, "provider": provider, "model": model})
        if model == "broken":
            raise RuntimeError("model unavailable")
        return Result(text=f"answer from {model}", model=model, provider=provider or "main", usage=Usage())


def keep_preselected(items, preselected):
    return sorted(preselected)


def pick_last(items, preselected):
    return [len(items) - 1]


def pick_none(items, preselected):
    return []


class FakeUI:
    def __init__(self, interactive=False, confirm=True, pick=keep_preselected, winner=None):
        self.interactive = interactive
        self.confirm_answer = confirm
        self.pick = pick
        self.winner = winner
        self.picker_calls = []
        self.single_calls = []
        self.said = []

    def confirm(self, question, **kwargs):
        return self.confirm_answer

    def pick_many(self, title, items, preselected):
        self.picker_calls.append({"items": items, "preselected": preselected})
        return self.pick(items, preselected)

    def pick_one(self, title, items, cancel="Skip"):
        self.single_calls.append(items)
        return self.winner if self.interactive else None

    def say(self, text):
        self.said.append(text)


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


def build(module, home, config=TRUSTED, ui=None, hermes=(), local=()):
    plugin = module.QuickEval(llm=FakeLLM(), ui=ui or FakeUI(), config=FakeConfig(config, home),
                              find_hermes=Found(hermes), find_local=Found(local))
    plugin.on_post_llm_call(session_id="s1", turn_id="t1", user_message="What happened at Tiananmen Square in 1989?",
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
    plugin = module.QuickEval(llm=FakeLLM(), ui=FakeUI(), config=FakeConfig(TRUSTED, tmp_path))
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
    assert (run["v"], run["type"], run["session_id"], run["turn_id"]) == (1, "run", "s1", "t1")
    assert [a["label"] for a in run["answers"]] == ["A", "B", "C"]
    assert run["answers"][0] == {"label": "A", "role": "original", "model": "deepseek/deepseek-r1",
                                 "text": "Let's talk about something else."}
    rerun = run["answers"][1]
    assert (rerun["role"], rerun["alias"], rerun["tokens_in"], rerun["tokens_out"]) == ("rerun", "claude", 10, 20)
    assert rerun["cost_usd"] == 0.001
    assert "── B · anthropic/claude-sonnet-5-5" in out
    assert "/eval pick A|B|C|tie|none" in out


def test_eval_raw_model_ids(make):
    plugin = make()
    plugin.cmd_eval("llama3.3@ollama openai/gpt-5")
    assert [(c["provider"], c["model"]) for c in plugin.llm.calls] == [("ollama", "llama3.3"), (None, "openai/gpt-5")]


def test_failing_model_does_not_sink_the_eval(make):
    plugin = make()
    out = plugin.cmd_eval("broken claude")
    answers = log(plugin)[0]["answers"]
    assert answers[1]["error"] == "RuntimeError: model unavailable"
    assert answers[2]["text"] == "answer from anthropic/claude-sonnet-5-5"
    assert "[error] RuntimeError: model unavailable" in out


def test_untrusted_and_declined(make):
    plugin = make(config={}, ui=FakeUI(confirm=False))
    assert "can't call other models" in plugin.cmd_eval("claude")
    assert plugin.llm.calls == []
    assert plugin.config.saves == []


def test_untrusted_and_approved_saves_permission(make):
    plugin = make(config={}, ui=FakeUI(confirm=True))
    plugin.cmd_eval("openai/gpt-5")
    llm = plugin.config.data["plugins"]["entries"]["quick-eval"]["llm"]
    assert llm == {"allow_model_override": True, "allow_provider_override": True}
    assert len(plugin.llm.calls) == 1


def test_bare_eval_without_terminal_uses_defaults(make):
    plugin = make(ui=FakeUI(interactive=False))
    plugin.cmd_eval("")
    assert [c["model"] for c in plugin.llm.calls] == ["anthropic/claude-sonnet-5-5"]


def test_bare_eval_without_terminal_or_defaults(make):
    config = copy.deepcopy(TRUSTED)
    del config["plugins"]["entries"]["quick-eval"]["default"]
    plugin = make(config=config, ui=FakeUI(interactive=False))
    assert "No default models set" in plugin.cmd_eval("")


def test_picker_lists_aliases_hermes_models_and_local_servers(make):
    ui = FakeUI(interactive=True)
    plugin = make(ui=ui, hermes=[("openrouter", "anthropic/claude-sonnet-5-5"), ("openrouter", "openai/gpt-5")],
                  local=[LMSTUDIO])
    plugin.cmd_eval("")
    assert ui.picker_calls[0]["items"] == [
        "claude: anthropic/claude-sonnet-5-5 · openrouter",
        "local: llama3.3 · ollama",
        "openai/gpt-5 · openrouter",
        "qwen3-8b · LM Studio (local, adds it to Hermes)",
    ]
    assert ui.picker_calls[0]["preselected"] == {0}
    assert [c["model"] for c in plugin.llm.calls] == ["anthropic/claude-sonnet-5-5"]


def test_picking_a_local_server_adds_it_to_hermes(make):
    plugin = make(ui=FakeUI(interactive=True, pick=pick_last), local=[LMSTUDIO])
    plugin.cmd_eval("")
    assert plugin.config.data["providers"]["lmstudio"] == {"name": "LM Studio", "api": "http://localhost:1234/v1"}
    assert (plugin.llm.calls[0]["provider"], plugin.llm.calls[0]["model"]) == ("lmstudio", "qwen3-8b")


def test_local_server_already_in_hermes_is_not_offered_again(make):
    config = copy.deepcopy(TRUSTED)
    config["providers"] = {"lms": {"api": "http://localhost:1234/v1/"}}
    ui = FakeUI(interactive=True)
    make(config=config, ui=ui, local=[LMSTUDIO]).cmd_eval("")
    assert not any("LM Studio" in item for item in ui.picker_calls[0]["items"])


def test_picker_cancelled(make):
    plugin = make(ui=FakeUI(interactive=True, pick=pick_none))
    assert plugin.cmd_eval("") == "No models picked."
    assert plugin.llm.calls == []


def test_inline_winner_picker_saves_a_judgment(make):
    ui = FakeUI(interactive=True, winner=1)
    plugin = make(ui=ui)
    out = plugin.cmd_eval("claude")
    assert ui.single_calls[0] == ["A · deepseek/deepseek-r1", "B · anthropic/claude-sonnet-5-5", "Tie",
                                  "No good answer"]
    assert "Saved: B wins (anthropic/claude-sonnet-5-5)" in out
    run, judged = log(plugin)
    assert (judged["type"], judged["run_id"], judged["winner"]) == ("judgment", run["id"], "B")
    assert judged["judge"] == "human"


def test_skipping_the_inline_picker_leaves_a_hint(make):
    plugin = make(ui=FakeUI(interactive=True, winner=None, pick=keep_preselected))
    assert "Pick a winner: /eval pick A|B|tie|none" in plugin.cmd_eval("claude")
    assert [r["type"] for r in log(plugin)] == ["run"]


def test_pick_flow(make):
    plugin = make()
    assert "Run /eval first" in plugin.cmd_eval("pick B")
    plugin.cmd_eval("claude")
    assert "Usage: /eval pick" in plugin.cmd_eval("pick")
    assert "Unknown choice 'Z'" in plugin.cmd_eval("pick Z")
    assert "B wins (anthropic/claude-sonnet-5-5)" in plugin.cmd_eval("pick b answered directly")
    judged = log(plugin)[-1]
    assert (judged["run_id"], judged["winner"], judged["note"]) == (log(plugin)[0]["id"], "B", "answered directly")


def test_pick_tie_and_none(make):
    plugin = make()
    plugin.cmd_eval("claude")
    assert "tie" in plugin.cmd_eval("pick tie")
    assert "no good answer" in plugin.cmd_eval("pick NONE")
    assert [r["winner"] for r in log(plugin)[1:]] == ["tie", "none"]


def test_pick_after_restart_reads_log(make, module, tmp_path):
    make().cmd_eval("claude")
    second = module.QuickEval(llm=FakeLLM(), ui=FakeUI(), config=FakeConfig(TRUSTED, tmp_path))
    assert "B wins" in second.cmd_eval("pick B")


def test_only_one_command_is_registered(load):
    ctx = load("quick-eval").ctx
    assert list(ctx.commands) == ["eval"]
    assert "pick" in ctx.commands["eval"]["args_hint"]


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
    link = module.ui.file_link(tmp_path / "config.yaml")
    assert link.startswith("\033]8;;file://") and link.endswith("\033]8;;\033\\")
