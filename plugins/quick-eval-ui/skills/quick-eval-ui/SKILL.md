---
name: quick-eval-ui
description: Grade replies from the current Hermes conversation and review quick-eval comparisons in a browser. Use when the user wants to grade a reply, save a test case, or pick a winner between model answers.
---

# Quick Eval UI

Grades and quick-eval runs share one JSONL log at `~/.hermes/evals/evals.jsonl`.

- `/evals` grades the last exchange: `/evals good great answer`, `/evals bad hallucinated a source`, `/evals 3 too long`.
- `/evals open` opens the UI: the chat as a transcript, tool calls, a grading bar, and Compare.
- `/eval` (quick-eval plugin) asks other models the same question. Its answers show up in the UI's Compare view, where the user picks a winner.
- In the UI: `j`/`k` move between turns, `p`/`f` pass or fail, `1`-`5` score, `c` Compare, `Cmd+Enter` save.

When the user says a reply was wrong or surprising, suggest `/evals bad <why>` so the case is kept.
