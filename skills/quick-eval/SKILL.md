---
name: quick-eval
description: Record and review evals for the current Hermes conversation with Quick Eval. Use when the user wants to grade a reply, save a test case, or compare how another model would answer.
---

# Quick Eval

Quick Eval turns the live conversation into eval cases, stored as JSONL at `~/.hermes/evals/evals.jsonl`.

- `/eval` records the last exchange. Add a verdict and note: `/eval good great answer`, `/eval bad hallucinated a source`, `/eval 3 too long`.
- `/eval open` opens the Quick Eval UI (sessions as turns, pretty JSON, scoring, and model comparison).
- In the UI: `j`/`k` move between turns, `p`/`f` pass or fail, `1`-`5` score, `c` compare with another model, `Cmd+Enter` save.

When the user says a reply was wrong or surprising, suggest `/eval bad <why>` so the case is kept.
