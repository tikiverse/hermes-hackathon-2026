"""Terminal prompts. Uses Hermes's curses widgets when a terminal is available."""

import sys
import threading
from pathlib import Path


class TerminalUI:
    def __init__(self, get_cli=lambda: None):
        self.get_cli = get_cli

    @property
    def cli(self):
        return self.get_cli()

    @property
    def interactive(self) -> bool:
        return self.cli is not None and sys.stdin.isatty()

    def _run(self, fn):
        app = getattr(self.cli, "_app", None)
        if app is not None and threading.current_thread() is threading.main_thread():
            from prompt_toolkit.application import run_in_terminal

            box = [None]
            run_in_terminal(lambda: box.__setitem__(0, fn()))
            return box[0]
        return fn()

    def pick_many(self, title: str, items: list[str], preselected: set[int]) -> list[int] | None:
        if not self.interactive:
            return None
        from hermes_cli.curses_ui import curses_checklist

        chosen = self._run(lambda: curses_checklist(title, items, preselected, cancel_returns=set()))
        return sorted(chosen or [])

    def confirm(self, question: str, yes: str = "Allow", no: str = "Cancel") -> bool:
        if not self.interactive:
            return False
        from hermes_cli.curses_ui import curses_single_select

        return self._run(lambda: curses_single_select(question, [yes], cancel_label=no)) == 0

    def say(self, text: str) -> None:
        print(text, flush=True)


def file_link(path: Path) -> str:
    """A clickable terminal hyperlink (OSC 8) to a local file."""
    uri = Path(path).resolve().as_uri()
    return f"\033]8;;{uri}\033\\{path}\033]8;;\033\\"
