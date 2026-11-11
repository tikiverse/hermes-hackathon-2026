# PR planned: Hackathon entry: quick-eval in the Hermes plugin catalog

Status: planned (after the [hackathon wrap-up PR](./planned-hackathon-wrap-up.md) merges; due 2026-11-11 17:00 EST)

Branch: `plugin-catalog/quick-eval` in a fork of NousResearch/hermes-agent (`shaunporwal/hermes-agent`)

## Goal

Enter quick-eval in the Hermes Agent Plugin Hackathon. The entry **is** this PR: one file, `plugin-catalog/quick-eval.yaml`, added to NousResearch/hermes-agent, plus a demo video. Accepted → listed in the Hermes plugin catalog; anyone installs with `hermes plugins install quick-eval` (today: clone + `scripts/link-plugins.sh`).

## Context

- Rules: https://github.com/NousResearch/hermes-agent/blob/main/website/docs/developer-guide/plugins/catalog-submission.md
- Source: https://x.com/NousResearch/status/2118094256438936062
- Judged: usefulness, reliability, creativity. Other entries' titles end "(Plugin Hackathon entry)".
- Entry draft: [`docs/catalog/quick-eval.yaml`](../catalog/quick-eval.yaml). Disclosure (rule 13): [`plugins/quick-eval/README.md`](../../plugins/quick-eval/README.md).

| Need | State |
|---|---|
| Public repo, `plugin.yaml` + `__init__.py`, `subdir: plugins/quick-eval` | done |
| `hermes plugins validate` passes | done; only warning left: 2 `private core imports` (see wrap-up doc, Decision 4) |
| `requires_hermes` (rule 14) | done; equals the Hermes the tests run on (`tests/test_contract.py`) |
| Plugin README at subdir (renders on catalog page) | done |
| Demo video | https://github.com/tikiverse/quick-eval/issues/3 |
| Demo GIF | https://raw.githubusercontent.com/tikiverse/quick-eval/main/docs/img/demo.gif |
| Fork | https://github.com/shaunporwal/hermes-agent |

## Implementation Checklist

### Tier 1 - Entry file

- [ ] Set `sha` in the draft to the main commit after the wrap-up PR merges
- [ ] Copy draft to fork as `plugin-catalog/quick-eval.yaml`; run Hermes's `scripts/validate_plugin_catalog.py` on it

### Tier 2 - PR

- [ ] Title `plugin-catalog: add quick-eval (Plugin Hackathon entry)` (same shape as other entries); body in [`docs/catalog/pr-body.md`](../catalog/pr-body.md): disclosure, GIF, video link
- [ ] `tikiverse` (repo owner, rule 5) opens it from the compare link: https://github.com/NousResearch/hermes-agent/compare/main...shaunporwal:hermes-agent:plugin-catalog/quick-eval

## Smoke Tests

- [ ] **Install from catalog works** · as a new Hermes user
  1. `hermes plugins install quick-eval` (catalog branch)
  2. In chat: ask anything, then `/quick-eval`

  **Pass if:**
  - other models' answers show beside yours
  - `/quick-eval open` shows the Review page (Quick Eval page in Desktop, browser page in a terminal)

## Non-Goals

- Hermes code changes. Plugin-side fixes go in this repo.
