"""Loads each plugin with the real Hermes plugin loader, in a throwaway HERMES_HOME."""

import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from conftest import PLUGIN_DIRS

pytestmark = pytest.mark.hermes
pytest.importorskip("hermes_cli.plugins")

LOADER = Path(__file__).with_name("hermes_load.py")


def run_hermes_load(path: Path, home: Path, calls: dict | None = None) -> dict:
    (home / "plugins").mkdir(parents=True)
    (home / "plugins" / path.name).symlink_to(path)
    (home / "config.yaml").write_text(yaml.safe_dump({"plugins": {"enabled": [path.name]}}))
    proc = subprocess.run(
        [sys.executable, str(LOADER), path.name, json.dumps(calls or {})],
        capture_output=True,
        text=True,
        timeout=120,
        env={"HERMES_HOME": str(home), "PATH": "/usr/bin:/bin"},
    )
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout.strip().splitlines()[-1])


@pytest.mark.parametrize("path", PLUGIN_DIRS, ids=[p.name for p in PLUGIN_DIRS])
def test_hermes_loads_plugin(path, tmp_path):
    manifest = yaml.safe_load((path / "plugin.yaml").read_text())
    calls = {tool: {} for tool in manifest.get("provides_tools") or []}
    result = run_hermes_load(path, tmp_path, calls)

    assert result["found"], "Hermes did not discover the plugin"
    assert result["enabled"], result["error"]
    assert result["error"] is None
    assert result["tools"] == sorted(manifest.get("provides_tools") or [])
    assert result["hooks"] == sorted(manifest.get("provides_hooks") or [])
    for tool, out in result["dispatch"].items():
        assert isinstance(out, str), f"{tool} returned {out!r}"
        json.loads(out)
