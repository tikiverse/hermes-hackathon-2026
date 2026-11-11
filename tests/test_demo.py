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


def fake_bin(tmp_path, models):
    """why: Hermes and Ollama stand-ins; `ollama list` shows only the given models."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    listing = "".join(f"{model} x 1 GB now\\n" for model in models)
    tools = {"hermes": "exit 0", "ollama": f'[ "$1" = list ] && printf "NAME\\n{listing}"; exit 0'}
    for name, body in tools.items():
        (bin_dir / name).write_text(f"#!/bin/sh\n{body}\n")
        (bin_dir / name).chmod(0o755)
    return bin_dir


def run_demo(tmp_path, models):
    src = tmp_path / "src"
    git("clone", "-q", str(ROOT), str(src), cwd=tmp_path)
    git("checkout", "-q", "-b", "try", cwd=src)
    env = {**os.environ, "HOME": str(tmp_path), "PATH": f"{fake_bin(tmp_path, models)}:{os.environ['PATH']}",
           "QE_REPO": str(src), "QE_BRANCH": "try", "QE_DIR": str(tmp_path / "copy"),
           "QE_DEMO_HOME": str(tmp_path / "home"), "QE_NO_LAUNCH": "1"}
    with SCRIPT.open() as piped:  # why: same as `curl | sh`, where stdin is the script itself
        return subprocess.run(["sh"], stdin=piped, env=env, capture_output=True, text=True, timeout=60)


def test_demo_sets_up_its_own_home_with_the_branch_plugin(tmp_path):
    assert run_demo(tmp_path, pull_line()).returncode == 0
    home = tmp_path / "home"
    assert (home / "plugins" / "quick-eval").resolve() == (tmp_path / "copy" / "plugins" / "quick-eval").resolve()
    assert yaml.safe_load((home / "config.yaml").read_text())["model"]["default"] == pull_line()[0]


def test_a_missing_model_prints_the_pull_command(tmp_path):
    done = run_demo(tmp_path, pull_line()[:1])
    assert done.returncode == 1
    assert f"ollama pull {pull_line()[1]}" in done.stderr


def test_readme_pulls_exactly_the_demo_models():
    readme = (ROOT / "README.md").read_text()
    assert re.findall(r"ollama pull (\S+)", readme) == pull_line()


def test_readme_cleanup_removes_what_the_demo_made():
    readme = (ROOT / "README.md").read_text()
    script = SCRIPT.read_text()
    made = [path.replace("$HOME", "~") for path in re.findall(r"QE_(?:DIR|DEMO_HOME):-([^}]+)}", script)]
    assert sorted(re.search(r"^rm -rf (.+)$", readme, re.M).group(1).split()) == sorted(made)
    assert re.search(r"^ollama rm (.+)$", readme, re.M).group(1).split() == pull_line()


def test_demo_steps_name_only_models_the_demo_config_has():
    named = set(re.findall(r"/quick-eval (\w[\w.:-]*)", SCRIPT.read_text())) - {"pick", "open", "allow"}
    aliases = yaml.safe_load(CONFIG.read_text())["plugins"]["entries"]["quick-eval"]["models"]
    assert named and named <= set(aliases)
