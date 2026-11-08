import string
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

LABELS = string.ascii_uppercase
SCORE_WORDS = {"TIE", "NONE"}


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


def resolve_targets(names: list[str], aliases: dict) -> list[Target]:
    """Turn typed names into targets: an alias, `model@provider`, or a bare model id."""
    targets = []
    for name in names:
        alias = aliases.get(name)
        if isinstance(alias, dict) and alias.get("model"):
            targets.append(Target(name, alias["model"], alias.get("provider")))
        elif "@" in name:
            model, provider = name.rsplit("@", 1)
            targets.append(Target(name, model, provider or None))
        else:
            targets.append(Target(name, name))
    return targets


def _ask(complete, prompt: str, target: Target) -> dict:
    answer = {"alias": target.name, "provider": target.provider, "model": target.model}
    start = time.perf_counter()
    try:
        result = complete(
            [{"role": "user", "content": prompt}],
            provider=target.provider,
            model=target.model,
            purpose="quick-eval",
        )
        answer["text"] = result.text or ""
        answer["model"] = getattr(result, "model", None) or target.model
        answer["provider"] = target.provider or getattr(result, "provider", None)
    except Exception as exc:
        answer["text"] = ""
        answer["error"] = f"{type(exc).__name__}: {exc}"
    answer["latency_ms"] = round((time.perf_counter() - start) * 1000)
    return answer


def run_eval(turn: dict, targets: list[Target], complete) -> dict:
    """Ask every target the turn's question in parallel. Answer A is the original reply."""
    answers = [
        {
            "label": "A",
            "source": "original",
            "model": turn.get("model"),
            "text": turn["response"],
        }
    ]
    with ThreadPoolExecutor(max_workers=max(1, len(targets))) as pool:
        futures = [pool.submit(_ask, complete, turn["prompt"], t) for t in targets]
        for label, future in zip(LABELS[1:], futures):
            answers.append({"label": label, "source": "rerun", **future.result()})
    return {
        "type": "eval",
        "id": uuid.uuid4().hex[:8],
        "ts": time.time(),
        "session_id": turn.get("session_id"),
        "prompt": turn["prompt"],
        "answers": answers,
    }


def format_eval(record: dict) -> str:
    lines = [f"Eval {record['id']}: {record['prompt']}", ""]
    for answer in record["answers"]:
        tag = "original" if answer.get("source") == "original" else f"{answer.get('latency_ms', 0)} ms"
        lines.append(f"── {answer['label']} · {answer.get('model') or 'unknown'} · {tag} ──")
        lines.append(answer.get("error") and f"[error] {answer['error']}" or answer["text"].strip())
        lines.append("")
    labels = "|".join(a["label"] for a in record["answers"])
    lines.append(f"Score it: /score {labels}|tie|none [note]")
    return "\n".join(lines)


def parse_score(raw: str, record: dict) -> dict | str:
    """Return a score record, or an error message string."""
    labels = [a["label"] for a in record["answers"]]
    usage = f"Usage: /score {'|'.join(labels)}|tie|none [note]"
    parts = raw.strip().split(None, 1)
    if not parts:
        return usage
    winner = parts[0].upper()
    if winner not in labels and winner not in SCORE_WORDS:
        return f"Unknown choice {parts[0]!r}. {usage}"
    winner_answer = next((a for a in record["answers"] if a["label"] == winner), None)
    return {
        "type": "score",
        "eval_id": record["id"],
        "ts": time.time(),
        "winner": winner.lower() if winner in SCORE_WORDS else winner,
        "winner_model": winner_answer.get("model") if winner_answer else None,
        "note": parts[1].strip() if len(parts) > 1 else "",
    }
