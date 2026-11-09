"""why: the one-line demo must work twice in a row, keep its own Hermes home, and pull exactly the models it uses."""
import os
import re
import subprocess
from pathlib import Path

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


def fake_docker(tmp_path):
    """why: record every docker call; `ps` reports nothing running, so the script starts Ollama."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    (bin_dir / "docker").write_text('#!/bin/sh\necho "$*" >> "$CALLS"\n')
    (bin_dir / "docker").chmod(0o755)
    return bin_dir


def run_demo(tmp_path, **extra):
    calls = tmp_path / "calls"
    env = {**os.environ, "PATH": f"{fake_docker(tmp_path)}:{os.environ['PATH']}", "CALLS": str(calls),
           "QE_SRC": "src", "QE_TTY": "/dev/null", **extra}
    with SCRIPT.open() as piped:  # why: same as `curl | sh`, where stdin is the script itself
        subprocess.run(["sh"], stdin=piped, env=env, check=True, capture_output=True, timeout=30)
    return [line.split()[0] for line in calls.read_text().splitlines()]


def test_demo_runs_everything_in_docker(tmp_path):
    assert run_demo(tmp_path) == ["info", "build", "ps", "run", "run", "stop"]


def test_clean_removes_the_container_volumes_and_image(tmp_path):
    assert run_demo(tmp_path, QE_CLEAN="1") == ["info", "rm", "volume", "rmi"]
