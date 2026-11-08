"""Load one plugin with Hermes's real PluginManager and print the result as JSON.

Run in a subprocess with HERMES_HOME pointing at a throwaway directory that
already contains plugins/<name> and a config.yaml enabling it.
"""

import json
import sys

from hermes_cli.plugins import PluginManager
from tools.registry import registry

name = sys.argv[1]
calls = json.loads(sys.argv[2]) if len(sys.argv) > 2 else {}

manager = PluginManager()
manager.discover_and_load()
loaded = manager._plugins.get(name)

result = {
    "found": loaded is not None,
    "enabled": bool(loaded and loaded.enabled),
    "error": loaded.error if loaded else None,
    "tools": sorted(loaded.tools_registered) if loaded else [],
    "hooks": sorted(loaded.hooks_registered) if loaded else [],
    "dispatch": {tool: registry.dispatch(tool, args) for tool, args in calls.items()},
}
print(json.dumps(result, default=str))
