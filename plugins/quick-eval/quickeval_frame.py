"""why: Hermes Desktop shows the UI in a sandboxed data: frame, which cannot fetch files; ship it as one HTML page."""
from pathlib import Path

DIST = Path(__file__).resolve().parent / "dashboard" / "dist"
PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Quick Eval</title><style>{css}</style></head>
<body class="quickeval-standalone"><div id="root"></div>
<script>{js}</script>
<script>{bridge}</script>
</body></html>"""


def inline(text):
    """why: a literal </script> inside inlined code would end the tag early."""
    return text.replace("</script", "<\\/script")


def frame_html(dist=DIST):
    css, js, bridge = ((dist / name).read_text() for name in ("style.css", "index.js", "bridge.js"))
    return PAGE.format(css=css, js=inline(js), bridge=inline(bridge))
