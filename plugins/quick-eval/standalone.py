"""why: serve the same UI and API without the Hermes dashboard. Stdlib only, so it runs anywhere.

why locked: the API reads every Hermes transcript. Other local processes and web pages (DNS rebinding) can reach
127.0.0.1, so each launch makes a random token that only the opened URL carries; every /api/ request needs it, the
Host header must name this server, and POST/PUT bodies must be JSON (a plain form post cannot set that type).
"""
import argparse
import hmac
import json
import secrets
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
LOCAL_HOSTS = ("127.0.0.1", "localhost")
JSON_TYPE = "application/json"
BODY_METHODS = ("POST", "PUT")
PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>Quick Eval</title><link rel="stylesheet" href="/dist/style.css"></head>
<body class="quickeval-standalone"><div id="root"></div>
<script src="/dist/index.js"></script>
<script>QuickEvalUI.mount(document.getElementById('root'),
  {apiBase: '/api/' + encodeURIComponent(new URLSearchParams(location.search).get('token') || '')});</script>
</body></html>"""


def read_json(handler):
    size = int(handler.headers.get("Content-Length") or 0)
    try:
        return json.loads(handler.rfile.read(size) or b"{}")
    except ValueError:
        return {}


def is_json(content_type):
    return (content_type or "").split(";")[0].strip().lower() == JSON_TYPE


def allowed_hosts(port):
    return {f"{host}:{port}" for host in LOCAL_HOSTS}


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

    def api(self, method, path):
        token, _, rest = path[len("/api/"):].partition("/")
        if not hmac.compare_digest(token.encode(), self.server.token.encode()):
            return self.send(403, '{"error":"missing or wrong token: reopen the page with /quick-eval open"}')
        if method in BODY_METHODS and not is_json(self.headers.get("Content-Type")):
            return self.send(415, '{"error":"send application/json"}')
        url = urlparse(self.path)
        body = read_json(self) if method in BODY_METHODS else None
        status, payload = routes.handle(method, "/" + rest, dict(parse_qsl(url.query)), body)
        if isinstance(payload, tuple):
            return self.send(status, payload[1], "application/x-ndjson")
        return self.send(status, json.dumps(payload))

    def static(self, path):
        target = (DIST / path[len("/dist/"):]).resolve()
        if DIST not in target.parents or not target.is_file():
            return self.send(404, '{"error":"not found"}')
        return self.send(200, target.read_bytes(), CTYPES.get(target.suffix, "text/plain"))

    def dispatch(self, method):
        if self.headers.get("Host") not in allowed_hosts(self.server.server_address[1]):
            return self.send(403, '{"error":"wrong Host"}')
        path = urlparse(self.path).path
        if path.startswith("/api/"):
            return self.api(method, path)
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
    server.token = secrets.token_urlsafe(32)
    if open_browser:
        threading.Timer(0.4, webbrowser.open, args=[page_url(server)]).start()
    return server


def page_url(server):
    """why: the only place the token leaves this process: the URL the user opens."""
    return f"http://127.0.0.1:{server.server_address[1]}/?token={server.token}"


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
    print(f"Quick Eval running at {page_url(server)}  (Ctrl-C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        return


if __name__ == "__main__":
    main()
