"""why: the only code that touches evals.jsonl. Append-only: a line is never rewritten or dropped."""
import json
import threading
from pathlib import Path

import quickeval_schema as schema

LOCK = threading.Lock()


def parse(line):
    try:
        value = json.loads(line)
    except ValueError:
        return None
    return value if isinstance(value, dict) else None


def ts_of(record):
    return record.get("ts") or 0


class EvalLog:
    """why: one object per log file so the plugin and the UI share read/append rules."""

    def __init__(self, path):
        self.path = Path(path)

    def append(self, record):
        with LOCK:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        return record

    def raw(self):
        if not self.path.exists():
            return ""
        return self.path.read_text(encoding="utf-8")

    def records(self, kind):
        parsed = [parse(line) for line in self.raw().splitlines() if line.strip()]
        return [rec for rec in parsed if rec and rec.get("type") == kind]

    def runs(self):
        return self.records(schema.RUN)

    def judgments(self):
        """why: newest judgment per run wins; older ones stay in the file as history."""
        return {rec["run_id"]: rec for rec in sorted(self.records(schema.JUDGMENT), key=ts_of)}

    def latest_run(self):
        runs = sorted(self.runs(), key=ts_of)
        return runs[-1] if runs else None

    def find_run(self, run_id):
        match = next((r for r in self.runs() if r["id"] == run_id), None)
        if match is None:
            raise KeyError(run_id)
        return match
