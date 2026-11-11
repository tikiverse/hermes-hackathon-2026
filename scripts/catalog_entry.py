"""why: the Hermes catalog entry pins one commit; render it from the draft the same way every time, never by hand.

Usage: uv run python -I scripts/catalog_entry.py <40-hex sha> [<out.yaml>]   (default out: stdout)
"""
import re
import sys
from pathlib import Path

DRAFT = Path(__file__).resolve().parent.parent / "docs" / "catalog" / "quick-eval.yaml"
PLACEHOLDER = "<sha>"
SHA = re.compile(r"[0-9a-f]{40}")


def render(draft, sha):
    if not SHA.fullmatch(sha):
        raise SystemExit(f"sha must be 40 lowercase hex characters, got {sha!r}")
    return draft.replace(PLACEHOLDER, sha)


def main(argv):
    entry = render(DRAFT.read_text(), argv[1])
    if len(argv) > 2:
        Path(argv[2]).write_text(entry)
    else:
        sys.stdout.write(entry)


if __name__ == "__main__":
    main(sys.argv)
