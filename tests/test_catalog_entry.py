"""why: the catalog draft restates facts the plugin owns; it must not drift, and pinning must be exact."""
import importlib.util
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
SHA = "0123456789abcdef0123456789abcdef01234567"
MANIFEST = yaml.safe_load((ROOT / "plugins" / "quick-eval" / "plugin.yaml").read_text())


@pytest.fixture(scope="module")
def tool():
    spec = importlib.util.spec_from_file_location("catalog_entry", ROOT / "scripts" / "catalog_entry.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def draft(tool):
    return yaml.safe_load(tool.DRAFT.read_text().replace(tool.PLACEHOLDER, SHA))


def test_draft_matches_the_plugin_manifest(draft):
    assert draft["name"] == MANIFEST["name"]
    assert draft["version"] == MANIFEST["version"]
    assert draft["requires_hermes"] == MANIFEST["requires_hermes"]
    assert draft["capabilities"]["provides_hooks"] == MANIFEST["provides_hooks"]


def test_rendered_entry_pins_the_sha_everywhere(tool):
    entry = tool.render(tool.DRAFT.read_text(), SHA)
    assert tool.PLACEHOLDER not in entry
    assert yaml.safe_load(entry)["sha"] == SHA
    assert all(SHA in url for url in yaml.safe_load(entry)["screenshots"])


def test_the_draft_has_no_comment_lines_because_it_is_posted_as_is(tool):
    assert not [line for line in tool.DRAFT.read_text().splitlines() if line.lstrip().startswith("#")]


@pytest.mark.parametrize("bad",["", "abc1234", SHA.upper(), SHA + "0", "main"])
def test_a_sha_that_is_not_40_lowercase_hex_is_refused(tool, bad):
    with pytest.raises(SystemExit):
        tool.render(tool.DRAFT.read_text(), bad)
