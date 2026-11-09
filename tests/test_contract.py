"""Checks every plugin under plugins/ against the rules Hermes expects."""

import json
import tomllib
from importlib.metadata import version
from pathlib import Path

import jsonschema
from packaging.version import Version

ROOT = Path(__file__).resolve().parent.parent


def test_manifest_has_required_fields(plugin):
    for key in ("name", "version", "description"):
        assert plugin.manifest.get(key), f"plugin.yaml is missing {key!r}"
    assert plugin.manifest["name"] == plugin.path.name


def test_provides_tools_matches_registered(plugin):
    assert set(plugin.manifest.get("provides_tools") or []) == set(plugin.ctx.tools)


def test_provides_hooks_matches_registered(plugin):
    assert set(plugin.manifest.get("provides_hooks") or []) == set(plugin.ctx.hooks)


def test_tool_schemas_are_valid(plugin):
    for name, tool in plugin.ctx.tools.items():
        schema = tool["schema"]
        assert schema["name"] == name
        assert schema.get("description"), f"{name} needs a description for the model"
        assert schema["parameters"]["type"] == "object"
        jsonschema.Draft202012Validator.check_schema(schema["parameters"])


def test_handlers_return_json_on_empty_args(plugin):
    for name, tool in plugin.ctx.tools.items():
        out = tool["handler"]({})
        assert isinstance(out, str), f"{name} must return a JSON string"
        json.loads(out)


def test_hooks_accept_extra_kwargs(plugin):
    for hook_name, callbacks in plugin.ctx.hooks.items():
        for cb in callbacks:
            cb(tool_name="x", args={}, result="{}", task_id="t", unexpected_field=1)



def hermes_floor():
    deps = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["dependencies"]
    return next(d for d in deps if d.startswith("hermes-agent")).removeprefix("hermes-agent")


def test_declared_min_hermes_is_the_one_tests_run_on(plugin):
    """why: a declared minimum the tests never ran on hides breakage, and hides CLI flags the dev Hermes lacks."""
    floor = hermes_floor()
    assert plugin.manifest["requires_hermes"] == floor
    assert Version(version("hermes-agent")).release[:2] == Version(floor.removeprefix(">=")).release[:2]
