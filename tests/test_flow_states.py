"""why: a small model check of the /quick-eval flow, TLC style: every command in every reachable state.

State = (asked the agent yet, permission given, a run to pick from, models found). Invariants, for every pair:
1. the reply is never empty and names the next command to type (only `open`, which ends in the browser, is exempt);
2. no model is called unless there is a question, permission, and only known names.
"""
import copy
import itertools

import pytest
from test_quick_eval import TRUSTED, FakeConfig, FakeLLM, Found, silent

QUESTION = {"session_id": "s1", "user_message": "What happened at Tiananmen Square in 1989?",
            "assistant_response": "I can't discuss that.", "model": "qwen2.5:0.5b"}
OLLAMA = {"slug": "ollama", "name": "Ollama", "api": "http://localhost:11434/v1", "models": ["deepseek-r1:1.5b"]}
COMMANDS = ["", "allow", "claude", "deepseek-r1:1.5b", "qwen2.5:0.5b", "pikc A", "pick", "pick A", "pick Z", "open"]
STATES = list(itertools.product([False, True], repeat=4))


def plugin_in(module, home, asked, trusted, has_run, models):
    config = copy.deepcopy(TRUSTED) if trusted else {}
    plugin = module.QuickEval(llm=FakeLLM(), config=FakeConfig(config, home), find_hermes=Found(()),
                              find_local=Found([OLLAMA] if models else []), say=silent)
    if has_run and trusted:
        plugin.on_post_llm_call(**QUESTION)
        plugin.cmd_eval("claude")
        plugin.llm.calls.clear()
        plugin.last_turn = None
    if asked:
        plugin.on_post_llm_call(**QUESTION)
    return plugin


def may_call(command, asked, trusted, models):
    known = command == "claude" or (command == "deepseek-r1:1.5b" and models)
    return asked and trusted and known


def state_id(state):
    return "asked={}-trusted={}-run={}-models={}".format(*state)


def fake_open():
    return "quick-eval UI: http://127.0.0.1:8765/"


@pytest.mark.parametrize("state", STATES, ids=state_id)
@pytest.mark.parametrize("command", COMMANDS)
def test_every_command_in_every_state_says_what_next_and_calls_only_when_allowed(load, tmp_path, monkeypatch,
                                                                                    state, command):
    module = load("quick-eval").module
    monkeypatch.setattr(module, "open_ui", fake_open)
    asked, trusted, has_run, models = state
    plugin = plugin_in(module, tmp_path, *state)
    reply = plugin.cmd_eval(command)
    assert reply.strip()
    if command != "open":
        assert "/quick-eval" in reply, reply
    if command == "qwen2.5:0.5b" and asked and trusted:
        assert "wrote the reply you saw" in reply
    assert bool(plugin.llm.calls) == may_call(command, asked, trusted, models), reply
