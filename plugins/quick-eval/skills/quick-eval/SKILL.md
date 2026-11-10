---
name: quick-eval
description: Compare the current Hermes reply with other models and judge the answers. Use when the user wants to check a reply against other models, pick the best answer, or review past evals.
---

# Quick Eval

Two commands, one log at `~/.hermes/evals/evals.jsonl`.

- `/quick-eval` asks other models the user's last question, shows every answer, then asks which wins.
- `/quick-eval claude local` uses those aliases; raw ids and `model@provider` work too.
- `/quick-eval-full claude` does the same, but the other models also see the chat so far (earlier user and assistant messages). Suggest it when the last question depends on earlier turns.
- `/quick-eval pick A|B|tie|none [note]` records or changes the winner of the last run.
- `/quick-eval open` opens the UI: Review (your chats; each turn's answers side by side, mark the good ones), Leaderboard (which model wins).

When a reply looks wrong, refused, or surprising, suggest `/quick-eval` so the case is kept and compared.
