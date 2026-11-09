import importlib.util
import sys
from dataclasses import dataclass, field
from pathlib import Path

import pytest
import yaml

PLUGINS_DIR = Path(__file__).resolve().parent.parent / "plugins"
PLUGIN_DIRS = sorted(p for p in PLUGINS_DIR.iterdir() if (p / "plugin.yaml").exists())


@dataclass
class FakeCtx:
    """Stands in for the ctx Hermes passes to register(ctx) and records what a plugin registers."""

    tools: dict = field(default_factory=dict)
    hooks: dict = field(default_factory=dict)
    commands: dict = field(default_factory=dict)
    cli_commands: dict = field(default_factory=dict)
    skills: dict = field(default_factory=dict)
    injected: list = field(default_factory=list)
    posted: list = field(default_factory=list)

    def register_tool(self, name, toolset, schema, handler, **kwargs):
        self.tools[name] = {"toolset": toolset, "schema": schema, "handler": handler, **kwargs}

    def register_hook(self, hook_name, callback):
        self.hooks.setdefault(hook_name, []).append(callback)

    def register_command(self, name, handler, description="", args_hint=""):
        self.commands[name] = {"handler": handler, "description": description, "args_hint": args_hint}

    def register_cli_command(self, name, help, setup_fn, handler_fn):
        self.cli_commands[name] = {"help": help, "setup_fn": setup_fn, "handler_fn": handler_fn}

    def register_skill(self, name, path):
        self.skills[name] = path

    def dispatch_tool(self, name, args):
        return self.tools[name]["handler"](args)

    def inject_message(self, content, role="user", **kwargs):
        self.injected.append({"content": content, "role": role, **kwargs})

    def post_message(self, text):
        self.posted.append(text)

    def fire(self, hook_name, **payload):
        return [cb(**payload) for cb in self.hooks.get(hook_name, [])]


@dataclass
class LoadedPlugin:
    path: Path
    manifest: dict
    module: object
    ctx: FakeCtx


def load_plugin(path: Path) -> LoadedPlugin:
    manifest = yaml.safe_load((path / "plugin.yaml").read_text())
    mod_name = f"hermes_plugin_{path.name}"
    for key in [k for k in sys.modules if k == mod_name or k.startswith(mod_name + ".")]:
        del sys.modules[key]
    spec = importlib.util.spec_from_file_location(
        mod_name, path / "__init__.py", submodule_search_locations=[str(path)]
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = module
    spec.loader.exec_module(module)
    ctx = FakeCtx()
    module.register(ctx)
    return LoadedPlugin(path, manifest, module, ctx)


@pytest.fixture(autouse=True)
def isolated_hermes_home(tmp_path, monkeypatch):
    home = tmp_path / "hermes-home"
    home.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(home))
    return home


@pytest.fixture(params=PLUGIN_DIRS, ids=[p.name for p in PLUGIN_DIRS])
def plugin(request) -> LoadedPlugin:
    return load_plugin(request.param)


@pytest.fixture
def load():
    return lambda name: load_plugin(PLUGINS_DIR / name)
