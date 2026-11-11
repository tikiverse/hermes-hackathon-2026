---
name: quick-eval
description: Compare the current Hermes reply with other models and judge the answers. Use when the user wants to check a reply against other models, pick the best answer, or review past evals.
---

# Quick Eval

One command, one log at `~/.hermes/evals/evals.jsonl`.

- `/quick-eval` shows the user's last question, the models they can name, and the commands.
- `/quick-eval <model> [<model> ...]` asks those models the last question and prints every answer. Names can be listed aliases, provider model IDs, or `model@provider`.
- `/quick-eval pick A,B [note]` marks the good answers of the last run (`none` if no answer is good).
- `/quick-eval open` opens the UI: Review (your chats; each turn's answers side by side, mark the good ones), Leaderboard (which model wins).

When a reply looks wrong, refused, or surprising, suggest `/quick-eval` so the case is kept and compared.
