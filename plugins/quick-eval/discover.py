"""Finds models the user can pick without typing: Hermes's signed-in providers and local servers."""

import json
import os
import urllib.request
from concurrent.futures import ThreadPoolExecutor

LOCAL_PORTS = [("ollama", "Ollama", 11434), ("lmstudio", "LM Studio", 1234), ("vllm", "vLLM", 8000),
               ("llamacpp", "llama-server", 8080)]


def default_servers() -> list[tuple[str, str, str]]:
    host = os.environ.get("QUICK_EVAL_LOCAL_HOST", "localhost")
    return [(slug, name, f"http://{host}:{port}/v1") for slug, name, port in LOCAL_PORTS]


def _fetch_models(api: str, timeout: float) -> list[str]:
    with urllib.request.urlopen(f"{api}/models", timeout=timeout) as resp:
        data = json.load(resp)
    return [m["id"] for m in data.get("data", []) if isinstance(m, dict) and m.get("id")]


def local_servers(servers=None, fetch=_fetch_models, timeout: float = 0.5) -> list[dict]:
    """Probe common local OpenAI-compatible servers and list the models each one serves."""
    servers = servers if servers is not None else default_servers()

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
