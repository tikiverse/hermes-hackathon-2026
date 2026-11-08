"""Finds models the user can pick without typing: Hermes's signed-in providers and local servers."""

import json
import urllib.request
from concurrent.futures import ThreadPoolExecutor

LOCAL_SERVERS = [
    ("ollama", "Ollama", "http://localhost:11434/v1"),
    ("lmstudio", "LM Studio", "http://localhost:1234/v1"),
    ("vllm", "vLLM", "http://localhost:8000/v1"),
]


def _fetch_models(api: str, timeout: float) -> list[str]:
    with urllib.request.urlopen(f"{api}/models", timeout=timeout) as resp:
        data = json.load(resp)
    return [m["id"] for m in data.get("data", []) if isinstance(m, dict) and m.get("id")]


def local_servers(servers=LOCAL_SERVERS, fetch=_fetch_models, timeout: float = 0.5) -> list[dict]:
    """Probe common local OpenAI-compatible servers and list the models each one serves."""

    def probe(server):
        slug, name, api = server
        try:
            models = fetch(api, timeout)
        except Exception:
            return None
        return {"slug": slug, "name": name, "api": api, "models": models} if models else None

    with ThreadPoolExecutor(max_workers=max(1, len(servers))) as pool:
        return [s for s in pool.map(probe, servers) if s]


def hermes_models(max_models: int = 6) -> list[tuple[str, str]]:
    """(provider, model) pairs Hermes already has credentials for."""
    try:
        from hermes_cli.model_switch import list_authenticated_providers

        providers = list_authenticated_providers(
            max_models=max_models, probe_custom_providers=False, for_picker=True
        )
    except Exception:
        return []
    return [(p["slug"], m) for p in providers for m in p.get("models") or []]
