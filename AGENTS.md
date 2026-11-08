# hermes-hackathon-2026

## UI (quick-eval review page)
- Shared design rules: skill `site-taste` (`taste.py rules --area layout`). This page is an app: one screen, no page scroll.
- `tools/site/ui.json` names the dock (`.ep-bar`); `tools/site/viewports.json` adds a 320 px touch phone.
- Check: `ops site-check shots <tailnet url> <dir> --ready .ep-bar`. Colors, sizes and timing come from the tokens at the top of `plugins/quick-eval/dashboard/dist/style.css`.
