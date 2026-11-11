# PR 10: Hackathon wrap-up: demo GIF, validator warnings, `/quick-eval open` in Desktop

Status: underway

Branch: `hackathon-wrap-up`

## Goal

Reply per item, for example `1 yes, 3 no`:

1. Demo steps move to [`docs/demo.md`](../demo.md). Plugin README keeps a 1-line link. Why: `hermes plugins validate` scans the plugin folder's README; `curl_pipe_shell` + `destructive_home_rm` came from the demo section. Result: both gone, one-line `curl | sh` demo stays. Alt: PR 9 (clone, then run; `rm` line stays, still a warning).
2. `/quick-eval open`: Desktop chat → Desktop **Quick Eval** page. Terminal or any other surface → browser page, even with Desktop installed. Hermes tells the command its surface (`platform`).
3. Desktop page (PR 4) is folded in here. Close PR 4 and PR 9 after merge (both superseded).
4. 2 `private core imports` warnings stay: no public API for Hermes version or signed-in providers. Both guarded by try; reviewer sees them. Hermes issue to ask for the 2 seams: not posted (needs your OK).
5. Demo GIF: 5 stills from the recording, app window only. Webcam overlay + burned-in captions removed (no faces in a public README). Rebuild: `scripts/make-demo-gif.py`.
6. Registry PR: fork `shaunporwal/hermes-agent`, branch `plugin-catalog/quick-eval`. `tikiverse` (repo owner, catalog rule 5) opens the PR from the compare link below. `sha` = merge commit of this PR.

This PR finishes the Hermes Agent Plugin Hackathon entry: it clears the validator warnings it can, makes `/quick-eval open` use Desktop when it runs in Desktop, adds the demo GIF, and prepares the catalog PR.

Links:

- Repo (renamed from `hermes-hackathon-2026`): https://github.com/tikiverse/quick-eval
- Demo GIF: https://raw.githubusercontent.com/tikiverse/quick-eval/main/docs/img/demo.gif
- Demo video task: https://github.com/tikiverse/quick-eval/issues/3
- PR 4, Desktop page (folded in): https://github.com/tikiverse/quick-eval/pull/4
- PR 9, validator warnings (superseded): https://github.com/tikiverse/quick-eval/pull/9
- Hackathon post: https://x.com/NousResearch/status/2118094256438936062
- Catalog rules: https://github.com/NousResearch/hermes-agent/blob/main/website/docs/developer-guide/plugins/catalog-submission.md
- Catalog entry schema: https://github.com/NousResearch/hermes-agent/blob/main/plugin-catalog/README.md
- Example entry PR: https://github.com/NousResearch/hermes-agent/pull/152582
- Catalog PR plan: docs/pr-docs/planned-catalog-entry.md
- Catalog PR body (draft): docs/catalog/pr-body.md

## Facts (checked in Hermes 0.23 source)

| Fact | Where |
|---|---|
| A command handler that names `platform` gets the surface; Desktop chat = `desktop`, terminal = `tui`/`cli`, Hermes 0.19 passes none | `hermes_cli/plugin_command_dispatch.py`, `tui_gateway/agent_factory.py` |
| Python → Desktop page: `broadcast_plugin_event(plugin, event)`; page listens with `ctx.onEvent("plugin.<id>.<event>")` | `hermes_cli/plugin_events.py`, `website/docs/developer-guide/desktop-plugin-sdk.md` |
| Page opens itself with `host.navigate(path)` | same SDK doc |
| `plugin_events` is a documented module: the validator does not flag it | `hermes plugins validate` run |

## Implementation Checklist

### Tier 1 - Validator warnings

- [x] Demo section moves to `docs/demo.md`; tests read the new file
- [x] `curl_pipe_shell` and `destructive_home_rm` no longer reported
- [x] 2 `private core imports` kept, reasons in Decision 4

### Tier 2 - Desktop open

- [x] Desktop page folded in from PR 4 (`desktop/plugin.js`, `quickeval_frame.py`, `bridge.js`)
- [x] `/quick-eval open` picks Desktop page or browser by `platform`; Hermes without `plugin_events` falls back to the browser
- [x] Desktop half listens for the open event and navigates to its page
- [x] Unit tests: Desktop → event, other surfaces → browser, old Hermes → browser
- [x] Real Hermes 0.23 command dispatcher: `desktop` sends the event, `tui`/`cli`/`telegram` open the browser, old one-argument call works
- [ ] Click-through in the Hermes Desktop app (not done; Smoke Test 1)

### Tier 3 - Demo GIF

- [x] 5-step GIF in both READMEs and the catalog draft
- [x] `scripts/make-demo-gif.py` rebuilds it from the recording

### Tier 4 - Catalog PR (after merge)

- [ ] Merge this PR; set `sha` in `docs/catalog/quick-eval.yaml` to the merge commit
- [ ] Fork `NousResearch/hermes-agent`; add `plugin-catalog/quick-eval.yaml`; run Hermes's `scripts/validate_plugin_catalog.py` and `hermes plugins validate` at that sha
- [ ] `tikiverse` opens the PR from the compare link; body in `docs/catalog/pr-body.md`

## Smoke Tests

- [ ] **Desktop** · in Hermes Desktop with the plugin enabled
  1. Ask anything, then `/quick-eval open`

  **Pass if:**
  - the Quick Eval page shows in the app
  - no browser tab opens

- [ ] **Terminal** · in `hermes` (Desktop installed or not)
  1. Ask anything, then `/quick-eval open`

  **Pass if:**
  - a browser tab opens at `http://127.0.0.1:8765`

- [ ] **Validator** · `hermes plugins validate "$PWD/plugins/quick-eval"`

  **Pass if:**
  - `Validation passed`
  - the only warning is `private core imports` (2 lines)

## Non-Goals

- Hermes code changes. Seams we need go in a Hermes issue.
- Closing PR 4 and PR 9 before this merges.
