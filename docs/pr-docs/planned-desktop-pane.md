# PR planned: quick-eval pane inside Hermes Desktop

Status: planned (after PR 2 merges). Partly done in [PR 10](./archive/10-hackathon-wrap-up.md): the Desktop page shows the existing UI in the SDK's sandboxed frame and `/quick-eval open` opens it. What stays planned here: rebuilding the page from Desktop's own components.

Branch: `quick-eval-desktop-pane`

## Goal

`/quick-eval open` in Hermes Desktop opens a pane in the app, built from Desktop's own components, instead of a browser tab on `127.0.0.1:8765`. Terminal-only users keep the browser page.

## Facts (checked in Hermes 0.23 source)

| Fact | Where |
|---|---|
| Desktop loads `<HERMES_HOME>/plugins/<name>/desktop/plugin.js` (the agent plugin's desktop half) | `apps/desktop/src/contrib/runtime-loader.ts` |
| Plain ESM; imports allowed: `@hermes/plugin-sdk` + `react*` only | same |
| SDK gives app components (`ListRow`, `ToggleRow`, panes, palette), `ctx.rest` to plugin API routes, `ctx.storage` | `apps/desktop/src/sdk/index.ts`, `contrib/plugin.ts` |
| Example | `apps/desktop/src/plugins/hello-runtime/plugin.runtime.js` |
| Today already: a **Quick Eval** tab in `hermes dashboard` (Hermes's own server, no extra port) | `plugins/quick-eval/dashboard/manifest.json` |

## Plan

| Step | Detail |
|---|---|
| 1 | `plugins/quick-eval/desktop/plugin.js`: Review + Leaderboard panes, SDK components, data from `dashboard/plugin_api.py` routes via `ctx.rest` |
| 2 | `/quick-eval open`: Desktop attached → open the pane; else browser page (unchanged) |
| 3 | Test: load `plugin.js` through Desktop's runtime loader rules (import allowlist) + `hermes_cli/plugin_validate_desktop.py` lint |

## Trade-offs

| Choice | Cost |
|---|---|
| Second UI (SDK pane) beside the browser page | two UIs to keep in step; share the API routes, not the markup |
| Desktop SDK is new ("runtime-fetched third-party plugins: next phase") | may change between Hermes releases; pin `requires_hermes` to the tested Desktop |
| Hermes 0.19 has no Desktop loader | 0.19 users keep the browser page |
