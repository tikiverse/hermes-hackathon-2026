"""why: the one-line demo must work twice in a row, keep its own Hermes home, and pull exactly the models it uses."""
import os
import re
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "demo.sh"
CONFIG = ROOT / "demo" / "config.yaml"
FAKE_OLLAMA = '#!/bin/sh\n[ "$1" = pull ] && echo "$2" >> "$PULLS"\nexit 0\n'


def git(*args, cwd):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


def pull_line():
    return re.search(r"^# pull: (.+)$", CONFIG.read_text(), re.M).group(1).split()


def test_pull_line_names_every_model_the_demo_uses():
    config = yaml.safe_load(CONFIG.read_text())
    aliases = config["plugins"]["entries"]["quick-eval"]["models"].values()
    assert sorted(pull_line()) == sorted([config["model"]["default"], *(a["model"] for a in aliases)])


def fake_bin(tmp_path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    (bin_dir / "ollama").write_text(FAKE_OLLAMA)
    (bin_dir / "ollama").chmod(0o755)
    return bin_dir


@pytest.mark.hermes
def test_demo_sets_up_its_own_home_and_reruns_cleanly(tmp_path):
    src = tmp_path / "src"
    git("clone", "-q", str(ROOT), str(src), cwd=tmp_path)
    git("checkout", "-q", "-b", "try", cwd=src)
    home = tmp_path / "demo-home"
    env = {**os.environ, "HOME": str(tmp_path), "PATH": f"{fake_bin(tmp_path)}:{os.environ['PATH']}",
           "PULLS": str(tmp_path / "pulls"), "QE_REPO": str(src), "QE_BRANCH": "try", "QE_DIR": str(tmp_path / "copy"),
           "QE_DEMO_HOME": str(home), "QE_NO_LAUNCH": "1"}
    for _ in range(2):
        with SCRIPT.open() as piped:  # why: same as `curl | sh`, where stdin is the script itself
            subprocess.run(["sh"], stdin=piped, env=env, check=True, capture_output=True, timeout=180)
    assert (home / "plugins" / "quick-eval").resolve() == (tmp_path / "copy" / "plugins" / "quick-eval").resolve()
    assert yaml.safe_load((home / "config.yaml").read_text())["model"]["default"] == "qwen2.5:0.5b"
    assert (tmp_path / "pulls").read_text().split() == pull_line() * 2
