"""Standalone Evalpad server: `python standalone.py [--port 8765] [--open]`.

Stdlib only, so it works anywhere Hermes does, even when the Hermes dashboard is not
running. Serves the same UI bundle and the same API as the dashboard plugin.
"""

import argparse
import json
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qsl, urlparse

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import evalpad_core as core  # noqa: E402

DIST = HERE / "dashboard" / "dist"

PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Evalpad</title><link rel="stylesheet" href="/dist/style.css"></head>
<body class="evalpad-standalone"><div id="root"></div>
<script src="/dist/ui.js"></script>
<script>EvalpadUI.mount(document.getElementById('root'), {apiBase: '/api'});</script>
</body></html>"""


class Handler(BaseHTTPRequestHandler):
    server_version = "Evalpad/1.0"

    def log_message(self, *a):  # quiet
        pass

    def _send(self, status, body, ctype="application/json"):
        data = body if isinstance(body, bytes) else body.encode()
        self.send_response(status)
        self.send_header("Content-Type", ctype + "; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _api(self, method):
        u = urlparse(self.path)
        body = None
        if method in ("POST", "PUT"):
            n = int(self.headers.get("Content-Length") or 0)
            try:
                body = json.loads(self.rfile.read(n) or b"{}")
            except json.JSONDecodeError:
                body = {}
        status, payload = core.handle(method, u.path[len("/api"):], dict(parse_qsl(u.query)), body)
        if isinstance(payload, tuple) and payload[0] == "text":
            return self._send(status, payload[1], "application/x-ndjson")
        self._send(status, json.dumps(payload))

    def do_GET(self):
        p = urlparse(self.path).path
        if p.startswith("/api/"):
            return self._api("GET")
        if p in ("/", "/index.html"):
            return self._send(200, PAGE, "text/html")
        if p.startswith("/dist/"):
            f = (DIST / p[len("/dist/"):]).resolve()
            if DIST in f.parents and f.is_file():
                ctype = "text/css" if f.suffix == ".css" else "application/javascript"
                return self._send(200, f.read_bytes(), ctype)
        self._send(404, '{"error":"not found"}')

    def do_POST(self):
        self._api("POST") if self.path.startswith("/api/") else self._send(404, "{}")

    def do_PUT(self):
        self._api("PUT") if self.path.startswith("/api/") else self._send(404, "{}")

    def do_DELETE(self):
        self._api("DELETE") if self.path.startswith("/api/") else self._send(404, "{}")


def serve(port: int = 8765, host: str = "127.0.0.1", open_browser: bool = False) -> ThreadingHTTPServer:
    srv = ThreadingHTTPServer((host, port), Handler)
    if open_browser:
        threading.Timer(0.4, lambda: webbrowser.open(f"http://{host}:{port}/")).start()
    return srv


def is_running(port: int = 8765, host: str = "127.0.0.1") -> bool:
    import socket

    with socket.socket() as s:
        s.settimeout(0.3)
        return s.connect_ex((host, port)) == 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--open", action="store_true")
    a = ap.parse_args()
    s = serve(a.port, a.host, a.open)
    print(f"Evalpad running at http://{a.host}:{a.port}/  (Ctrl-C to stop)")
    try:
        s.serve_forever()
    except KeyboardInterrupt:
        pass
