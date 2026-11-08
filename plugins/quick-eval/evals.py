"""why: ask other models the user's last question and build the v1 log lines for it."""
import string
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from functools import partial

from . import quickeval_schema as schema

LABELS = string.ascii_uppercase


@dataclass(frozen=True)
class Target:
    name: str
    model: str
    provider: str | None = None

    def describe(self) -> str:
        where = f" via {self.provider}" if self.provider else ""
        if self.name == self.model:
            return f"{self.model}{where}"
        return f"{self.name} ({self.model}{where})"


def target_for(name, aliases):
    """why: a typed name is an alias, `model@provider`, or a bare model id."""
    alias = aliases.get(name)
    if isinstance(alias, dict) and alias.get("model"):
        return Target(name, alias["model"], alias.get("provider"))
    if "@" in name:
        model, provider = name.rsplit("@", 1)
        return Target(name, model, provider or None)
    return Target(name, name)


def resolve_targets(names: list[str], aliases: dict) -> list[Target]:
    return [target_for(name, aliases) for name in names]


def usage_of(result):
    usage = getattr(result, "usage", None)
    return {"tokens_in": getattr(usage, "input_tokens", None), "tokens_out": getattr(usage, "output_tokens", None),
            "cost_usd": getattr(usage, "cost_usd", None)}


def call_model(complete, prompt, target):
    result = complete([{"role": "user", "content": prompt}], provider=target.provider, model=target.model,
                      purpose="quick-eval")
    return {"text": result.text or "", "model": getattr(result, "model", None) or target.model,
            "provider": target.provider or getattr(result, "provider", None), "error": None, **usage_of(result)}


def ask(complete, prompt, target, label):
    start = time.perf_counter()
    try:
        got = call_model(complete, prompt, target)
    except Exception as exc:  # why: one broken model must not sink the whole eval
        error = f"{type(exc).__name__}: {exc}"
        got = {"text": "", "model": target.model, "provider": target.provider, "error": error}
    latency = round((time.perf_counter() - start) * 1000)
    model, text = got.pop("model"), got.pop("text")
    return schema.answer(label, "rerun", model, text, alias=target.name, latency_ms=latency, **got)


def run_eval(turn: dict, targets: list[Target], complete) -> dict:
    """why: answer A is the reply the user saw; B.. are the targets, asked in parallel with only the prompt."""
    original = schema.answer("A", "original", turn.get("model"), turn["response"])
    jobs = [partial(ask, complete, turn["prompt"], t, label) for t, label in zip(targets, LABELS[1:], strict=False)]
    with ThreadPoolExecutor(max_workers=max(1, len(jobs))) as pool:
        reruns = list(pool.map(call_job, jobs))
    return schema.run_record(turn["prompt"], [original, *reruns], session_id=turn.get("session_id"),
                             turn_id=turn.get("turn_id"))


def call_job(job):
    return job()


def answer_lines(a):
    tag = "original" if a["role"] == "original" else f"{a.get('latency_ms', 0)} ms"
    body = f"[error] {a['error']}" if a.get("error") else a["text"].strip()
    return [f"── {a['label']} · {a.get('model') or 'unknown'} · {tag} ──", body, ""]


def choices(run):
    return "|".join([a["label"] for a in run["answers"]] + list(schema.SCORE_WORDS))


def format_eval(run: dict) -> str:
    lines = [f"Eval {run['id']}: {run['prompt']}", ""]
    lines += [line for a in run["answers"] for line in answer_lines(a)]
    return "\n".join(lines)


def pick_hint(run: dict) -> str:
    return f"Pick a winner: /eval pick {choices(run)} [note]"


def parse_pick(raw: str, run: dict) -> dict | str:
    """why: '/eval pick b great answer' -> judgment; returns a usage string on bad input."""
    parts = raw.strip().split(None, 1)
    if not parts:
        return f"Usage: /eval pick {choices(run)} [note]"
    word = parts[0]
    winner = word.lower() if word.lower() in schema.SCORE_WORDS else word.upper()
    try:
        schema.check_winner(run, winner)
    except ValueError:
        return f"Unknown choice {word!r}. Usage: /eval pick {choices(run)} [note]"
    return schema.judgment_record(run["id"], winner, note=parts[1].strip() if len(parts) > 1 else "")


def verdict_text(run: dict, winner: str) -> str:
    if winner == "tie":
        return "tie"
    if winner == "none":
        return "no good answer"
    return f"{winner} wins ({schema.winner_model(run, winner)})"
