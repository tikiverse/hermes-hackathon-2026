# Hermes issue: posted

Posted 2026-11-11 from the `shaunporwal` account: https://github.com/NousResearch/hermes-agent/issues/153833

Title: [Feature]: Plugins have no public way to read the Hermes version or list signed-in providers

Text as posted:

### Problem or Use Case

A catalog plugin that needs the Hermes version, or the providers Hermes is signed in to, must import private core modules. `hermes plugins validate` then warns `private core imports` for each one.

| Fact | Private import used today | Why a plugin needs it |
|---|---|---|
| Hermes version | `hermes_cli.__version__` | Hermes 0.19 ignores `requires_hermes`, so the plugin reads the version itself and refuses to load on a Hermes that is too old |
| Signed-in providers | `hermes_cli.model_switch.list_authenticated_providers` | The plugin lists the (provider, model) pairs Hermes already has credentials for. With no access, the list is empty |

The plugin is [quick-eval](https://github.com/tikiverse/quick-eval). It catches a failed provider import, and the validator still warns for both imports. At the pinned commit these are the only 2 warnings.

### Proposed Solution

1. `ctx.hermes_version` (a string), or `hermes_cli.plugin_api.hermes_version()`.
2. `ctx.list_signed_in_providers()`: read only, returns provider names and model ids, no keys.

Either shape works for both.

### Related

- #153245 asks for `hermes models --json`, which prints the same data as `list_authenticated_providers`. This issue asks for the call inside the plugin process.
- #129003 and #150066: the version a loader resolves for `requires_hermes` can differ from `hermes_cli.__version__` (stale git tag, Nix stamp `0.0.0`). A public call would give plugins the loader's own answer.
- #141982 tracks other plugin API gaps. These 2 are not in it.

### Evidence

- Plugin code: `plugins/quick-eval/__init__.py` and `plugins/quick-eval/discover.py` in https://github.com/tikiverse/quick-eval.
- Catalog entry (draft): `docs/catalog/quick-eval.yaml` in the same repo.
