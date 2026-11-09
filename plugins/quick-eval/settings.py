"""Reads and writes this plugin's section of Hermes's config.yaml.

    plugins:
      entries:
        quick-eval:
          llm: {allow_model_override: true, allow_provider_override: true}
          default: [claude]
          params: {temperature: 0.7, max_tokens: 1024}
          models:
            claude: {provider: openrouter, model: anthropic/claude-sonnet-5-5}
"""

from pathlib import Path

PLUGIN_ID = "quick-eval"
# why: every model in one run gets the same settings, so answers compare like for like.
DEFAULT_PARAMS = {"temperature": 0.7, "max_tokens": 1024}


class HermesConfig:
    def load(self) -> dict:
        from hermes_cli.config import load_config

        return load_config() or {}

    def save(self, patch: dict) -> None:
        from hermes_cli.config import save_config

        save_config(patch, merge_existing=True)

    def path(self) -> Path:
        from hermes_cli.config import get_config_path

        return get_config_path()

    def home(self) -> Path:
        from hermes_constants import get_hermes_home

        return get_hermes_home()


def entry(config: dict) -> dict:
    value = ((config.get("plugins") or {}).get("entries") or {}).get(PLUGIN_ID)
    return value if isinstance(value, dict) else {}


def aliases(config: dict) -> dict:
    value = entry(config).get("models")
    return value if isinstance(value, dict) else {}


def params(config: dict) -> dict:
    value = entry(config).get("params")
    given = value if isinstance(value, dict) else {}
    return {key: given.get(key, default) for key, default in DEFAULT_PARAMS.items()}


def defaults(config: dict) -> list[str]:
    value = entry(config).get("default")
    if isinstance(value, str):
        return [value]
    return [v for v in value or [] if isinstance(v, str)]


def is_trusted(config: dict) -> bool:
    llm = entry(config).get("llm") or {}
    return bool(llm.get("allow_model_override") and llm.get("allow_provider_override"))


def trust_patch() -> dict:
    llm = {"allow_model_override": True, "allow_provider_override": True}
    return {"plugins": {"entries": {PLUGIN_ID: {"llm": llm}}}}


def provider_patch(slug: str, name: str, api: str) -> dict:
    return {"providers": {slug: {"name": name, "api": api}}}


def configured_provider_apis(config: dict) -> set[str]:
    providers = config.get("providers") or {}
    return {
        str(p.get("api") or p.get("base_url") or "").rstrip("/")
        for p in providers.values()
        if isinstance(p, dict)
    }
