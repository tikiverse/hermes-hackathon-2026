# Hackathon submission (Hermes Agent Plugin Hackathon, due 2026-11-11)

Source: https://coinfomania.com/nousresearch-launches-hermes-agent-plugin-hackathon-offering/ (tweet https://x.com/NousResearch/status/2118094256438936062). Rules: https://github.com/NousResearch/hermes-agent/blob/main/website/docs/developer-guide/plugins/catalog-submission.md

- Submit: PR adding `plugin-catalog/quick-eval.yaml` to NousResearch/hermes-agent + demo video. Other entries: titles end "(Plugin Hackathon entry)".
- Judged: usefulness, reliability, creativity. Accepted entries list in the Hermes plugin marketplace.

| Need | State |
|---|---|
| Public repo, `plugin.yaml` + `__init__.py` | done (`subdir: plugins/quick-eval`) |
| `hermes plugins validate` passes (v0.23.0) | done |
| `requires_hermes` in `plugin.yaml` + entry (rule 14) | done, `>=0.22.7` |
| Disclosure in README + PR body (rule 13) | done: `plugins/quick-eval/README.md` |
| Plugin README at subdir (renders on catalog page) | done |
| Entry draft | `docs/catalog/quick-eval.yaml`; sha after PR 2 merges |
| Screenshots in PR body (UI) | from `ops site-check shots` on committed tree |
| Demo video | Shaun |
| Catalog PR, from Shaun's account (rule 5: owner) | Shaun's go |
