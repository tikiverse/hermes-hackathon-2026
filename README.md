# Quick Eval: evals from live Hermes chats

Grade a Hermes reply in one keystroke, see the full turn as clean JSON, and replay the same prompt on another model side by side. Evals land on disk as JSONL, ready for any harness.

Built for the Hermes Hackathon 2026. Nothing a skill or a prompt can do: it reads live session state, serves its own UI, and calls other models.

## What you get

| Piece | What it does |
|---|---|
| `/eval [good\|bad\|1-5] [note]` | Records the last exchange as an eval from inside the chat |
| `/eval open` | Opens the Quick Eval UI (starts it if needed) |
| Dashboard tab **Quick Eval** | Same UI inside `hermes dashboard`, themed with your dashboard |
| Review view | Turns list, conversation, tool calls, collapsible **Raw JSON** tree |
| One-keystroke grading | `p`/`f` pass or fail, `1`-`5` score, tags, expected answer, notes, `Cmd+Enter` saves and jumps to the next turn |
| Compare | `c` replays the prompt on another model (any OpenAI-compatible endpoint) and shows it next to the original; mark the winner |
| Follow latest | New turns show up within ~3 seconds while you chat |
| Export | `~/.hermes/evals/evals.jsonl`, or the **Export JSONL** button |

## Install

```bash
hermes plugins install tikiverse/hermes-hackathon-2026
hermes plugins enable quick-eval
```

Or for local development:

```bash
ln -s "$PWD" ~/.hermes/plugins/quick-eval
hermes plugins enable quick-eval
```

Run the UI without the dashboard:

```bash
python standalone.py --open        # http://127.0.0.1:8765
```

## Comparing models

Compare uses an OpenAI-compatible `/chat/completions` endpoint. Defaults point at OpenRouter with `OPENROUTER_API_KEY` (read from the environment or `~/.hermes/.env`). Add your own presets in `~/.hermes/evals/config.json`:

```json
{"presets": [{"label": "Arete", "model": "<model-id>", "base_url": "https://<host>/v1", "api_key_env": "ARETE_API_KEY"}]}
```

## Eval record

```json
{"id": "a1b2c3d4e5f6", "ts": 1794171710.8, "session_id": "...", "message_id": 23669,
 "model": "claude-haiku-5-5", "prompt": "...", "response": "...",
 "verdict": "pass", "score": 4, "tags": ["great"], "notes": "", "expected": "",
 "comparisons": [{"model": "...", "response": "...", "latency_ms": 2100, "preferred": true}]}
```

Saving the same turn twice updates its eval instead of duplicating it.

## Layout

```
plugin.yaml, __init__.py      plugin entry: registers /eval
quickeval_paths.py              where state, evals and SQL live
quickeval_sessions.py           reads Hermes sessions (read-only) and groups them into turns
quickeval_store.py              JSONL eval store
quickeval_compare.py            replay a prompt on another model
quickeval_routes.py             one dispatcher for the dashboard and the standalone server
standalone.py                 stdlib HTTP server (same UI + API)
sql/                          queries against Hermes state.db
dashboard/manifest.json       dashboard tab
dashboard/plugin_api.py       FastAPI router at /api/plugins/quick-eval
dashboard/dist/index.js       the UI (framework-free; also registers the dashboard tab)
skills/quick-eval/SKILL.md       teaches the agent when to suggest /eval
tests/                        python -m unittest discover -s tests
```

## Notes

- Hermes state is opened read-only; Quick Eval never writes to `state.db`.
- No telemetry. Compare sends only the user prompt of the selected turn to the model you choose.
