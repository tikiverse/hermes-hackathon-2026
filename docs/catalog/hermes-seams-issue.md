# Draft: NousResearch/hermes-agent issue (NOT posted)

Status: draft. Posting is Shaun's call (message in his name). Upstream search 2026-11-11: no issue asks for either seam. Related, different asks: https://github.com/NousResearch/hermes-agent/issues/153245, https://github.com/NousResearch/hermes-agent/issues/148137.

Title: Plugins have no public way to read the Hermes version or list signed-in providers

## Problem

A catalog plugin that needs these two facts must import private core modules. `hermes plugins validate` then warns `private core imports` for each. Today the quick-eval plugin catches a failed provider import, and the validator still warns for both.

| Fact | Private import used today | Why a plugin needs it |
|---|---|---|
| Hermes version | `hermes_cli.__version__` | Hermes 0.19 ignores `requires_hermes`; the plugin reads the version itself and refuses to load on a too-old Hermes |
| Signed-in providers | `hermes_cli.model_switch.list_authenticated_providers` | `/quick-eval` lists the (provider, model) pairs Hermes already has credentials for; with no access the list is empty |

## Ask

1. `ctx.hermes_version` (string), or `hermes_cli.plugin_api.hermes_version()`.
2. `ctx.list_signed_in_providers()` (read only; names and model ids, no keys).

Either shape works. Both are read only.

## Evidence

- Validator output at the pinned commit: 2 warnings, both `private core imports`, no other warnings.
- Plugin: https://github.com/tikiverse/quick-eval (`plugins/quick-eval/__init__.py`, `plugins/quick-eval/discover.py`).
- Catalog entry: `docs/catalog/quick-eval.yaml` in that repo.
