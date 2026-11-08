"""why: terminal prompts through Hermes's curses widgets when a terminal is available."""

import sys
import threading
from functools import partial
from pathlib import Path


def no_cli():
    return None


def into(box, fn):
    box[0] = fn()


def checklist(title, items, preselected):
    from hermes_cli.curses_ui import curses_checklist

    return curses_checklist(title, items, preselected, cancel_returns=set())


def single(title, items, cancel_label):
    from hermes_cli.curses_ui import curses_single_select

    return curses_single_select(title, items, cancel_label=cancel_label)


class TerminalUI:
    def __init__(self, get_cli=no_cli):
        self.get_cli = get_cli

    @property
    def cli(self):
        return self.get_cli()

    @property
    def interactive(self) -> bool:
        return self.cli is not None and sys.stdin.isatty()

    def _run(self, fn):
        """why: inside the prompt_toolkit app, curses must run via run_in_terminal on the main thread."""
        app = getattr(self.cli, "_app", None)
        if app is None or threading.current_thread() is not threading.main_thread():
            return fn()
        from prompt_toolkit.application import run_in_terminal

        box = [None]
        run_in_terminal(partial(into, box, fn))
        return box[0]

    def pick_many(self, title: str, items: list[str], preselected: set[int]) -> list[int] | None:
        if not self.interactive:
            return None
        return sorted(self._run(partial(checklist, title, items, preselected)) or [])

    def pick_one(self, title: str, items: list[str], cancel: str = "Skip") -> int | None:
        if not self.interactive:
            return None
        return self._run(partial(single, title, items, cancel))

    def confirm(self, question: str, yes: str = "Allow", no: str = "Cancel") -> bool:
        return self.pick_one(question, [yes], no) == 0

    def say(self, text: str) -> None:
        print(text, flush=True)


def file_link(path: Path) -> str:
    """why: OSC 8 makes the path clickable in terminals that support it."""
    uri = Path(path).resolve().as_uri()
    return f"\033]8;;{uri}\033\\{path}\033]8;;\033\\"
