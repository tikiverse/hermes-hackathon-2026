"""why: serve the same UI and API without the Hermes dashboard. Stdlib only, so it runs anywhere."""
import argparse
import json
import socket
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qsl, urlparse

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import quickeval_routes as routes  # noqa: E402

DIST = HERE / "dashboard" / "dist"
CTYPES = {".css": "text/css", ".js": "application/javascript"}
PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>Quick Eval</title><link rel="stylesheet" href="/dist/style.css"></head>
<body class="quickeval-standalone"><div id="root"></div>
<script src="/dist/index.js"></script>
<script>QuickEvalUI.mount(document.getElementById('root'), {apiBase: '/api'});</script>
</body></html>"""


def read_json(handler):
    size = int(handler.headers.get("Content-Length") or 0)
    try:
        return json.loads(handler.rfile.read(size) or b"{}")
    except ValueError:
        return {}


class Handler(BaseHTTPRequestHandler):
    server_version = "Quick Eval/1.0"

    def log_message(self, *_args):
        return None

    def send(self, status, body, ctype="application/json"):
        data = body if isinstance(body, bytes) else body.encode()
        self.send_response(status)
        self.send_header("Content-Type", ctype + "; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def api(self, method):
        url = urlparse(self.path)
        body = read_json(self) if method in ("POST", "PUT") else None
        status, payload = routes.handle(method, url.path[len("/api"):], dict(parse_qsl(url.query)), body)
        if isinstance(payload, tuple):
            return self.send(status, payload[1], "application/x-ndjson")
        return self.send(status, json.dumps(payload))

    def static(self, path):
        target = (DIST / path[len("/dist/"):]).resolve()
        if DIST not in target.parents or not target.is_file():
            return self.send(404, '{"error":"not found"}')
        return self.send(200, target.read_bytes(), CTYPES.get(target.suffix, "text/plain"))

    def dispatch(self, method):
        path = urlparse(self.path).path
        if path.startswith("/api/"):
            return self.api(method)
        if method == "GET" and path in ("/", "/index.html"):
            return self.send(200, PAGE, "text/html")
        if method == "GET" and path.startswith("/dist/"):
            return self.static(path)
        return self.send(404, '{"error":"not found"}')

    def do_GET(self):
        self.dispatch("GET")

    def do_POST(self):
        self.dispatch("POST")

    def do_PUT(self):
        self.dispatch("PUT")

    def do_DELETE(self):
        self.dispatch("DELETE")


def serve(port=8765, host="127.0.0.1", open_browser=False):
    server = ThreadingHTTPServer((host, port), Handler)
    if open_browser:
        threading.Timer(0.4, webbrowser.open, args=[f"http://{host}:{port}/"]).start()
    return server


def is_running(port=8765, host="127.0.0.1"):
    with socket.socket() as probe:
        probe.settimeout(0.3)
        return probe.connect_ex((host, port)) == 0


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--open", action="store_true")
    return parser.parse_args()


def main():
    args = parse_args()
    server = serve(args.port, args.host, args.open)
    print(f"Quick Eval running at http://{args.host}:{args.port}/  (Ctrl-C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        return


if __name__ == "__main__":
    main()
