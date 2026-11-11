"""Drive quick-eval inside real Hermes: load plugins, fire post_llm_call, run /quick-eval and /quick-eval pick.

Run in a subprocess with HERMES_HOME already set up. Prints the command outputs as JSON.
Optional args: the command to run (default quick-eval) and the turn's conversation_history as JSON.
"""

import json
import sys

from hermes_cli.plugins import discover_plugins, get_plugin_command_handler, invoke_hook

eval_args, score_args = sys.argv[1], sys.argv[2]
command = sys.argv[3] if len(sys.argv) > 3 else "quick-eval"
history = json.loads(sys.argv[4]) if len(sys.argv) > 4 else []

discover_plugins()
invoke_hook(
    "post_llm_call",
    session_id="e2e",
    task_id="t",
    turn_id="1",
    user_message="What happened at Tiananmen Square in 1989?",
    assistant_response="I can't discuss that.",
    conversation_history=history,
    model="deepseek/deepseek-r1",
    platform="cli",
)
eval_out = get_plugin_command_handler(command)(eval_args)
score_out = get_plugin_command_handler("quick-eval")("pick " + score_args)
print(json.dumps({"eval": eval_out, "score": score_out}))
