"""why: ask other models the user's last question and build the v1 log lines for it."""
import re
import string
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from functools import partial

from . import quickeval_schema as schema

LABELS = string.ascii_uppercase
# why: a reasoning model can spend its whole output budget thinking and return no text; say so, never show a blank.
EMPTY = "empty answer: the model returned no text (a reasoning model may have used its token limit thinking)"
HF_REPO = re.compile(r"models--[^/]*?--([^/]+)")


def short_model(model):
    """why: a local server names its model by a cache path; show the repo name instead."""
    if not model or not model.startswith("/"):
        return model
    found = HF_REPO.search(model)
    return found.group(1) if found else model.rstrip("/").rsplit("/", 1)[-1]


@dataclass(frozen=True)
class Target:
    name: str
    model: str
    provider: str | None = None

    def describe(self) -> str:
        where = f" via {self.provider}" if self.provider else ""
        model = short_model(self.model)
        if self.name == self.model:
            return f"{model}{where}"
        return f"{self.name} ({model}{where})"


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


def split_same(targets, model):
    """why: asking the model that wrote answer A again compares it with itself."""
    kept = [t for t in targets if t.model != model]
    return kept, [t for t in targets if t.model == model]


def skipped_note(skipped):
    names = ", ".join(t.name for t in skipped)
    return f"Skipped {names}: it wrote the reply you saw." if skipped else ""


def text_of(content):
    """why: a message's content is a string, or a list of parts of which only the text parts carry words."""
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts = [p.get("text") or "" for p in content if isinstance(p, dict) and p.get("type") == "text"]
        return "\n".join(parts).strip()
    return ""


def earlier_messages(history):
    """why: /quick-eval-full shows other models the chat so far. Only user and assistant text goes: tool calls and
    results are Hermes's own, and the other models have no tools. Everything from the last user message on is cut,
    so the reply being judged, and the steps that made it, stay out. Same-role neighbours merge into one message."""
    kept = []
    for message in history or []:
        role = message.get("role") if isinstance(message, dict) else None
        text = text_of(message.get("content")) if role in ("user", "assistant") else ""
        if not text:
            continue
        if kept and kept[-1]["role"] == role:
            kept[-1]["content"] += "\n\n" + text
        else:
            kept.append({"role": role, "content": text})
    last_user = max((i for i, m in enumerate(kept) if m["role"] == "user"), default=None)
    return kept[:last_user] if last_user is not None else kept


def call_model(complete, messages, target, params):
    result = complete(messages, provider=target.provider, model=target.model, purpose="quick-eval", **params)
    text = (result.text or "").strip()
    return {"text": text, "model": getattr(result, "model", None) or target.model, "error": None if text else EMPTY}


def ask(complete, messages, target, label, params):
    start = time.perf_counter()
    try:
        got = call_model(complete, messages, target, params)
    except Exception as exc:  # why: one broken model must not sink the whole eval
        got = {"text": "", "model": target.model, "error": f"{type(exc).__name__}: {exc}"}
    latency = round((time.perf_counter() - start) * 1000)
    return schema.answer(label, got["model"], got["text"], provider=target.provider, latency_ms=latency,
                         error=got["error"])


def run_eval(turn: dict, targets: list[Target], complete, params: dict, history: list | None = None) -> dict:
    """why: answer A is the reply the user saw; B.. are the targets, asked in parallel with the prompt + same params.
    history (from /quick-eval-full) = the earlier messages every target sees before the prompt."""
    original = schema.answer("A", turn.get("model"), turn["response"])
    messages = [*(history or []), {"role": "user", "content": turn["prompt"]}]
    labels = zip(targets, LABELS[1:], strict=False)
    jobs = [partial(ask, complete, messages, t, label, params) for t, label in labels]
    with ThreadPoolExecutor(max_workers=max(1, len(jobs))) as pool:
        reruns = list(pool.map(call_job, jobs))
    return schema.run_record(turn["prompt"], [original, *reruns], session_id=turn.get("session_id"), params=params,
                             history=history)


def call_job(job):
    return job()


def answer_lines(a):
    tag = f"{a['latency_ms']} ms" if a.get("latency_ms") is not None else "original"
    body = f"[error] {a['error']}" if a.get("error") else a["text"].strip()
    return [f"── {a['label']} · {short_model(a.get('model')) or 'unknown'} · {tag} ──", body, ""]


def context_note(run: dict) -> str:
    history = run.get("history")
    if history is None:
        return ""
    count = len(history)
    return f" (with the {count} earlier message{'s' if count != 1 else ''})"


def format_eval(run: dict) -> str:
    lines = [f"Eval {run['id']}{context_note(run)}: {run['prompt']}", ""]
    lines += [line for a in run["answers"] for line in answer_lines(a)]
    return "\n".join(lines)


def pick_hint(run: dict) -> str:
    good = ",".join(a["label"] for a in run["answers"][:2])
    return f"Next: /quick-eval pick {good} [note] marks the good answers (or: none) · /quick-eval open to review"


def pick_words(word: str, run: dict) -> tuple:
    """why: 'b' is one winner, 'a,b,c' marks several good answers, tie/none are outcomes."""
    if word.lower() in schema.OUTCOMES:
        winner = schema.check_winner(run, word.lower())
        return winner, schema.good_of(run, {"winner": winner})
    good = schema.check_good(run, [w.strip().upper() for w in word.split(",") if w.strip()])
    return schema.winner_of(good), good


def parse_pick(raw: str, run: dict) -> dict | str:
    """why: '/quick-eval pick b great answer' -> judgment; returns a usage string on bad input."""
    usage = f"Usage: /quick-eval pick A,B [note]: the good answers ({', '.join(schema.labels_of(run))}), or none"
    parts = raw.strip().split(None, 1)
    if not parts:
        return usage
    try:
        winner, good = pick_words(parts[0], run)
    except ValueError:
        return f"Unknown choice {parts[0]!r}. {usage}"
    return schema.judgment_record(run["id"], winner, note=parts[1].strip() if len(parts) > 1 else "", good=good)


def verdict_text(run: dict, winner: str, good: list | None = None) -> str:
    if winner == "none":
        return "Marked: no good answer"
    labels = good or (schema.labels_of(run) if winner == "tie" else [winner])
    return "Marked good: " + ", ".join(f"{label} ({short_model(schema.winner_model(run, label))})" for label in labels)
