"""why: replay one prompt on another OpenAI-compatible model so the user can judge the difference."""
import json
import time
import urllib.error
import urllib.request

import quickeval_paths as paths

OPENROUTER = "https://openrouter.ai/api/v1"
DEFAULT_PRESETS = [
    {"label": "Hermes 4 405B (OpenRouter)", "model": "nousresearch/hermes-4-405b", "base_url": OPENROUTER,
     "api_key_env": "OPENROUTER_API_KEY"},
    {"label": "Claude Sonnet (OpenRouter)", "model": "anthropic/claude-sonnet-4.5", "base_url": OPENROUTER,
     "api_key_env": "OPENROUTER_API_KEY"},
    {"label": "DeepSeek V3 (OpenRouter)", "model": "deepseek/deepseek-chat", "base_url": OPENROUTER,
     "api_key_env": "OPENROUTER_API_KEY"},
]


def load_presets(cfg):
    if not cfg.exists():
        return DEFAULT_PRESETS
    try:
        return json.loads(cfg.read_text(encoding="utf-8")).get("presets", DEFAULT_PRESETS)
    except ValueError:
        return DEFAULT_PRESETS


def presets():
    items = load_presets(paths.evals_dir() / "config.json")
    return [{**item, "has_key": bool(paths.read_key(item.get("api_key_env", "")))} for item in items]


def pick_target(body):
    preset = next((p for p in presets() if p["label"] == body.get("preset")), {})
    model = body.get("model") or preset.get("model")
    base = (body.get("base_url") or preset.get("base_url") or "").rstrip("/")
    key_env = body.get("api_key_env") or preset.get("api_key_env") or "OPENROUTER_API_KEY"
    if not (model and base):
        raise ValueError("choose a preset or give model + base_url")
    return {"model": model, "base": base, "key_env": key_env, "label": preset.get("label") or model}


def with_key(target):
    key = paths.read_key(target["key_env"])
    if not key:
        raise ValueError(f"{target['key_env']} is not set (env or {paths.hermes_home() / '.env'})")
    return {**target, "key": key}


def post_json(url, key, payload):
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as err:
        detail = err.read().decode("utf-8", "ignore")[:300]
        raise RuntimeError(f"{payload['model']}: HTTP {err.code} {detail}") from None
    except urllib.error.URLError as err:
        raise RuntimeError(f"{payload['model']}: {err.reason}") from None


def build_messages(body):
    system = [{"role": "system", "content": body["system"]}] if body.get("system") else []
    return [*system, {"role": "user", "content": body["prompt"]}]


def compare(body):
    if not body.get("prompt"):
        raise ValueError("prompt is required")
    target = with_key(pick_target(body))
    payload = {"model": target["model"], "messages": build_messages(body)}
    started = time.time()
    data = post_json(f"{target['base']}/chat/completions", target["key"], payload)
    reply = (data.get("choices") or [{}])[0].get("message", {}).get("content", "")
    return {"model": target["model"], "label": target["label"], "response": reply,
            "latency_ms": int((time.time() - started) * 1000), "usage": data.get("usage"), "score": None}
