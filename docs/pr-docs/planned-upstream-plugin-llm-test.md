# PR planned: Hermes test: plugin ctx.llm keeps a custom provider's extra_body

Status: planned (after https://github.com/NousResearch/hermes-agent/pull/124290 merges)

Branch: `test/plugin-llm-extra-body` in a fork of NousResearch/hermes-agent

## Goal

Guard the bug that breaks quick-eval on local thinking models: a plugin's `ctx.llm.complete(provider=<custom entry>)` drops that entry's `extra_body` (e.g. `enable_thinking: false`), so the model thinks until its token cap and returns no text. PR 124290 fixes the matcher; this adds the one test for the plugin path so it can't regress.

## Context

- Root cause: provider matcher accepts only `custom` / `custom:<x>`; plugin calls pass the bare entry name. https://github.com/NousResearch/hermes-agent/blob/c59b667c76dc75e07bb96e98630de78c14d7a008/agent/agent_init.py#L180-L210
- Fix in flight: https://github.com/NousResearch/hermes-agent/pull/124290 (we commented with our repro). Related: issue 124289, issue 50132 (`max_tokens`).
- Existing tests cover only the main chat route: `tests/agent/test_auxiliary_named_custom_providers.py` (`TestAuxInheritsCustomProviderExtraBody`).

## Implementation Checklist

- [ ] Test: `call_llm(provider="<entry name>")` on a non-main custom entry sends its `extra_body`; fails on main before 124290
- [ ] PR body: "Depends on 124290"; repro from our closed issue 151595

## Smoke Tests

No UI walk: Hermes core test only. Automated: the new test passes on 124290's head, fails without it.

## Product Decisions

- Test only, no second matcher: a fix of our own would conflict with 124290 and add debt.

## Non-Goals

- `max_tokens` drop (issue 50132): tracked upstream.
