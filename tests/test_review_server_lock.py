"""why: the review page's API reads every Hermes transcript; only the opener's URL may reach it (registry review)."""
import http.client
import sys
import threading
from pathlib import Path
from urllib.parse import urlparse

import pytest

PLUGIN = Path(__file__).resolve().parent.parent / "plugins" / "quick-eval"
sys.path.insert(0, str(PLUGIN))

import standalone  # noqa: E402

JSON = {"Content-Type": "application/json"}


@pytest.fixture
def server(tmp_path, monkeypatch):
    monkeypatch.setenv("QUICKEVAL_DIR", str(tmp_path / "evals"))
    monkeypatch.setenv("QUICKEVAL_STATE_DB", str(tmp_path / "state.db"))
    running = standalone.serve(0)
    threading.Thread(target=running.serve_forever, daemon=True).start()
    yield running
    running.shutdown()


def status(server, method, path, headers=None, body=None):
    port = server.server_address[1]
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    conn.request(method, path, body=body, headers={"Host": f"127.0.0.1:{port}", **(headers or {})})
    code = conn.getresponse().status
    conn.close()
    return code


def api(server, rest, token=None):
    return f"/api/{server.token if token is None else token}{rest}"


def test_page_url_carries_the_token(server):
    url = urlparse(standalone.page_url(server))
    assert (url.hostname, url.port, url.query) == ("127.0.0.1", server.server_address[1], f"token={server.token}")


def test_each_launch_makes_a_new_token(server):
    other = standalone.serve(0)
    assert other.token != server.token and len(server.token) >= 32
    other.server_close()


def test_api_needs_the_token(server):
    assert status(server, "GET", api(server, "/leaderboard")) == 200
    assert status(server, "GET", api(server, "/leaderboard", "wrong")) == 403
    assert status(server, "GET", "/api/leaderboard") == 403


@pytest.mark.parametrize("host", ["evil.example:{port}", "127.0.0.1:1", "localhost"])
def test_other_host_header_is_refused(server, host):
    wrong = host.format(port=server.server_address[1])
    assert status(server, "GET", api(server, "/leaderboard"), {"Host": wrong}) == 403
    assert status(server, "GET", "/", {"Host": wrong}) == 403


def test_localhost_host_header_is_allowed(server):
    port = server.server_address[1]
    assert status(server, "GET", api(server, "/leaderboard"), {"Host": f"localhost:{port}"}) == 200


@pytest.mark.parametrize("ctype", [None, "text/plain", "application/x-www-form-urlencoded", "multipart/form-data"])
def test_post_needs_json(server, ctype):
    headers = {"Content-Type": ctype} if ctype else {}
    assert status(server, "POST", api(server, "/judgments"), headers, b"{}") == 415


def test_json_post_passes_the_lock(server):
    assert status(server, "POST", api(server, "/judgments"), JSON, b"{}") not in (403, 415)
