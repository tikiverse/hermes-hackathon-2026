# PR 10: Hackathon wrap-up: demo GIF, validator warnings, `/quick-eval open` in Desktop

Status: underway

Branch: `hackathon-wrap-up`

## Goal

Reply per item, for example `1 yes, 3 no`:

1. Demo steps move to [`docs/demo.md`](../demo.md). Plugin README keeps a 1-line link. Why: `hermes plugins validate` scans the plugin folder's README; `curl_pipe_shell` + `destructive_home_rm` came from the demo section. Result: both gone, one-line `curl | sh` demo stays. Alt: PR 9 (clone, then run; `rm` line stays, still a warning).
2. `/quick-eval open`: Desktop chat → Desktop **Quick Eval** page. Terminal or any other surface → browser page, even with Desktop installed. Hermes tells the command its surface (`platform`).
3. Desktop page (PR 4) is folded in here. PR 9 closed 2026-11-11 as superseded (branch `validator-warnings` kept; reopen it if you pick clone-then-run in decision 1). Close PR 4 after merge.
4. 2 `private core imports` warnings stay: no public API for Hermes version or signed-in providers. Both guarded by try; reviewer sees them. Hermes issue asking for the 2 seams, posted 2026-11-11: https://github.com/NousResearch/hermes-agent/issues/153833
5. Demo GIFs: a 6-step demo recorded in the real Hermes Desktop app, and a 3-step GIF that shows where to turn the plugin on in Desktop. Cropped so no session list, other chats or file path show. Replaces the screen-recording GIF (webcam, captions). Rebuild: `docs/demo.md`, last section.
6. Registry PR: fork `shaunporwal/hermes-agent`, branch `plugin-catalog/quick-eval`. `tikiverse` (repo owner, catalog rule 5) opens the PR from the compare link below. `sha` = merge commit of this PR.
7. Minimum Hermes version. The Desktop page needs Hermes 0.22.3 or newer. Older Hermes (0.19 to 0.22.2) still works: `/quick-eval open` opens the browser page there. Rec: keep `requires_hermes: ">=0.19"`, so older users keep the plugin. Alt: `>=0.22.3` (drops those users from the whole plugin).

This PR finishes the Hermes Agent Plugin Hackathon entry: it clears the validator warnings it can, makes `/quick-eval open` use Desktop when it runs in Desktop, adds the demo GIF, and prepares the catalog PR.

Links:

- Repo (renamed from `hermes-hackathon-2026`): https://github.com/tikiverse/quick-eval
- Demo GIF: https://raw.githubusercontent.com/tikiverse/quick-eval/main/docs/img/demo.gif
- Demo video task: https://github.com/tikiverse/quick-eval/issues/3
- PR 4, Desktop page (folded in): https://github.com/tikiverse/quick-eval/pull/4
- PR 9, validator warnings (closed, superseded): https://github.com/tikiverse/quick-eval/pull/9
- Hermes seams issue (posted): https://github.com/NousResearch/hermes-agent/issues/153833
- Hackathon post: https://x.com/NousResearch/status/2118094256438936062
- Catalog rules: https://github.com/NousResearch/hermes-agent/blob/main/website/docs/developer-guide/plugins/catalog-submission.md
- Catalog entry schema: https://github.com/NousResearch/hermes-agent/blob/main/plugin-catalog/README.md
- Example entry PR: https://github.com/NousResearch/hermes-agent/pull/152582
- Catalog branch (fork): https://github.com/shaunporwal/hermes-agent/tree/plugin-catalog/quick-eval
- Open the catalog PR from here (`tikiverse`): https://github.com/NousResearch/hermes-agent/compare/main...shaunporwal:hermes-agent:plugin-catalog/quick-eval
- Catalog PR plan: docs/pr-docs/planned-catalog-entry.md
- Catalog PR body (draft): docs/catalog/pr-body.md

## Notes: why the first Desktop tries failed (2026-11-11)

| Try | Cause | Now |
|---|---|---|
| 1 | The Hermes gateway had started before this change and ran the old code | Gateway restarted |
| 1 | The chat was created in a terminal (surface `tui`); a chat created in Desktop reports `desktop` | README says: use a chat created in Desktop |
| 2 | Desktop ships a plugin's Desktop page off until the user turns it on once; the plugin cannot preset it | README shows the switch (GIF); the `/quick-eval open` reply names it |

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
- [x] README and catalog text say the Desktop page needs Hermes 0.22.3 or newer; older Hermes opens the browser page
- [x] README and the `/quick-eval open` reply name the one-time Desktop switch (Capabilities > Plugins > Quick Eval)
- [x] Click-through in the Hermes Desktop app (backend v0.23.0), 2026-11-11: new Desktop chat, Quick Eval switched on in Capabilities > Plugins, `/quick-eval open` showed the page in the app, no browser tab. The 6 steps of the demo GIF are that run. Earlier tries failed for the 3 reasons in Decision 7

### Tier 3 - Demo GIF

- [x] 6-step GIF recorded in Hermes Desktop, in both READMEs and the catalog draft
- [x] `scripts/make-desktop-gifs.py` rebuilds both GIFs from window captures; `tests/test_desktop_gifs.py` checks the builder and the committed GIFs
- [x] Plugin README, Install > Hermes Desktop: steps for the one-time Desktop switch, with `docs/img/desktop-install.gif` (Capabilities > Plugins > Filters > Installed > Desktop)
- [x] Old `scripts/make-demo-gif.py` (screen recording) removed

### Tier 4 - Catalog PR (after merge)

- [x] Fork `shaunporwal/hermes-agent`; branch `plugin-catalog/quick-eval` holds `plugin-catalog/quick-eval.yaml` (`scripts/catalog-push.sh <sha>`), provisional pin = this PR's branch
- [x] Hermes's `validate_plugin_catalog.py` passes on the entry; `hermes plugins validate --install-deps` passes in a clean clone at the pin (only the 2 `private core imports` warnings)
- [ ] Merge this PR, then `scripts/catalog-push.sh <merge commit sha>` and rerun both checks
- [ ] `tikiverse` opens the PR from the compare link; body in `docs/catalog/pr-body.md`

## Smoke Tests

- [x] **Desktop** · in a NEW Hermes Desktop chat (not one resumed from a terminal), with the plugin enabled and the backend restarted after the plugin updated
  1. Once: Capabilities > Plugins > turn Quick Eval on
  2. Ask anything, then `/quick-eval open`

  **Pass if:**
  - the Quick Eval page shows in the app
  - no browser tab opens

- [ ] **Terminal** · in `hermes` (Desktop installed or not)
  1. Ask anything, then `/quick-eval open`

  **Pass if:**
  - a browser tab opens at `http://127.0.0.1:8765`

- [x] **Validator** · `hermes plugins validate "$PWD/plugins/quick-eval"`

  **Pass if:**
  - `Validation passed`
  - the only warning is `private core imports` (2 lines)

## Non-Goals

- Hermes code changes. Seams we need go in a Hermes issue.
- Closing PR 4 before this merges.
