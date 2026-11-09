# PR planned: Hackathon entry: quick-eval in the Hermes plugin catalog

Status: planned (after PR 2 merges; due 2026-11-11 17:00 EST)

Branch: `plugin-catalog/quick-eval` in a fork of NousResearch/hermes-agent

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
| `hermes plugins validate` passes | done |
| `requires_hermes` (rule 14) | done, `>=0.22.7` |
| Plugin README at subdir (renders on catalog page) | done |
| Demo video | https://github.com/tikiverse/hermes-hackathon-2026/issues/3 |

## Implementation Checklist

### Tier 1 - Entry file

- [ ] Set `sha` in the draft to the main commit after PR 2 merges
- [ ] Copy draft to fork as `plugin-catalog/quick-eval.yaml`; run Hermes's catalog check on it

### Tier 2 - PR

- [ ] Title `Add quick-eval to plugin catalog (Plugin Hackathon entry)`; body: disclosure, screenshots (`ops site-check shots`), video link
- [ ] Open from Shaun's account (rule 5: repo owner submits)

## Smoke Tests

- [ ] **Install from catalog works** · as a new Hermes user
  1. `hermes plugins install quick-eval` (catalog branch)
  2. In chat: ask anything, then `/eval`

  **Pass if:**
  - other models' answers show beside yours
  - `/eval open` shows the Review page

## Non-Goals

- Hermes code changes. Plugin-side fixes go in this repo.
