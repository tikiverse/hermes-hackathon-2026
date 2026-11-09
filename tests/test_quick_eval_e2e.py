"""quick-eval end to end: real Hermes plugin loader and LLM routing, fake OpenAI-compatible server."""

import json
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest
import yaml

from conftest import PLUGINS_DIR

pytestmark = pytest.mark.hermes
pytest.importorskip("hermes_cli.plugins")

SCRIPT = Path(__file__).with_name("hermes_eval_e2e.py")


@pytest.fixture
def fake_server():
    requests = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def _send(self, body):
            data = json.dumps(body).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            self._send({"object": "list", "data": [{"id": "fake-model", "object": "model"}]})

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            requests.append({"path": self.path, "body": body})
            self._send({
                "id": "c1",
                "object": "chat.completion",
                "created": 0,
                "model": body.get("model"),
                "choices": [{
                    "index": 0,
                    "finish_reason": "stop",
                    "message": {"role": "assistant", "content": "Troops fired on protesters on June 4, 1989."},
                }],
                "usage": {"prompt_tokens": 10, "completion_tokens": 10, "total_tokens": 20},
            })

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_port}/v1", requests
    server.shutdown()


def run(home: Path, eval_args: str, score_args: str) -> dict:
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), eval_args, score_args],
        capture_output=True,
        text=True,
        timeout=120,
        env={"HERMES_HOME": str(home), "PATH": "/usr/bin:/bin", "NO_PROXY": "*"},
        stdin=subprocess.DEVNULL,
    )
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout.strip().splitlines()[-1])


def setup_home(home: Path, api: str, trusted: bool) -> None:
    (home / "plugins").mkdir(parents=True, exist_ok=True)
    (home / "plugins" / "quick-eval").symlink_to(PLUGINS_DIR / "quick-eval")
    entry = {"models": {"fake": {"provider": "fakelocal", "model": "fake-model"}},
             "params": {"temperature": 0.3, "max_tokens": 512}}
    if trusted:
        entry["llm"] = {"allow_model_override": True, "allow_provider_override": True}
    config = {
        "providers": {"fakelocal": {"name": "Fake Local", "api": api}},
        "plugins": {"enabled": ["quick-eval"], "entries": {"quick-eval": entry}},
    }
    (home / "config.yaml").write_text(yaml.safe_dump(config))


def test_eval_and_score_through_real_hermes(tmp_path, fake_server):
    api, requests = fake_server
    setup_home(tmp_path, api, trusted=True)

    out = run(tmp_path, "fake", "B direct answer")

    assert "Troops fired on protesters" in out["eval"], out["eval"]
    assert "I can't discuss that." in out["eval"]
    assert "B wins" in out["score"]

    assert len(requests) == 1
    assert requests[0]["body"]["model"] == "fake-model"
    user_messages = [m for m in requests[0]["body"]["messages"] if m["role"] == "user"]
    assert user_messages[-1]["content"] == "What happened at Tiananmen Square in 1989?"

    lines = [json.loads(line) for line in (tmp_path / "evals" / "evals.jsonl").read_text().splitlines()]
    assert [r["type"] for r in lines] == ["run", "judgment"]
    assert lines[0]["answers"][1]["model"] == "fake-model"
    assert lines[1]["winner"] == "B"


def test_every_model_gets_the_same_params(tmp_path, fake_server):
    api, requests = fake_server
    setup_home(tmp_path, api, trusted=True)
    run(tmp_path, "fake", "B")
    assert requests[0]["body"]["temperature"] == 0.3
    first = json.loads((tmp_path / "evals" / "evals.jsonl").read_text().splitlines()[0])
    assert first["params"] == {"temperature": 0.3, "max_tokens": 512}


def test_untrusted_plugin_cannot_call_models_without_a_terminal(tmp_path, fake_server):
    api, requests = fake_server
    setup_home(tmp_path, api, trusted=False)

    out = run(tmp_path, "fake", "B")

    assert "can't call other models" in out["eval"]
    assert requests == []
