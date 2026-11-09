"""why: the PR's try-it command must work twice in a row and never touch the user's own clone."""
import os
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "try-branch.sh"


def git(*args, cwd):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


@pytest.mark.hermes
def test_try_branch_links_the_plugin_and_reruns_cleanly(tmp_path):
    src = tmp_path / "src"
    git("clone", "-q", str(ROOT), str(src), cwd=tmp_path)
    git("checkout", "-q", "-b", "try", cwd=src)
    env = {**os.environ, "QE_REPO": str(src), "QE_DIR": str(tmp_path / "copy"), "HERMES_HOME": str(tmp_path / "home")}
    for _ in range(2):
        subprocess.run(["sh", str(SCRIPT), "try"], env=env, check=True, capture_output=True, timeout=180)
    link = tmp_path / "home" / "plugins" / "quick-eval"
    assert link.resolve() == (tmp_path / "copy" / "plugins" / "quick-eval").resolve()
    assert "quick-eval" in (tmp_path / "home" / "config.yaml").read_text()
