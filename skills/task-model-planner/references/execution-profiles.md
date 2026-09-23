# Execution Profile Registry

This registry is the canonical mapping for built-in execution-profile IDs to
exact child-agent configurations. Do not override a mapped value in a planner
report or orchestrator dispatch. The orchestrator may also pass validated,
invocation-local candidate IDs; these are not registry entries and must not be
persisted here.

The planner and orchestrator exchange a candidate ID. Resolve built-in profile
IDs from this registry and any `additional-*` IDs only from the validated
invocation-local map. Each host resolves its own model/effort pair or combined
model configuration only when spawning the child agent.

## Codex / ChatGPT

| Profile ID | Model | Reasoning effort | Pre-start capacity fallback |
|---|---|---|---|
| `luna-high` | `gpt-6-luna` | `high` | — |
| `luna-xhigh` | `gpt-6-luna` | `xhigh` | `luna-high` |
| `luna-max` | `gpt-6-luna` | `max` | — |
| `sol-medium` | `gpt-6-sol` | `medium` | — |
| `sol-high` | `gpt-6-sol` | `high` | `sol-medium` |
| `sol-xhigh` | `gpt-6-sol` | `xhigh` | `sol-high` |

Codex/ChatGPT offer `high`, `xhigh`, and `max` for GPT-6 Luna, and `medium`,
`high`, and `xhigh` for GPT-6 Sol. Sol `max` and Luna `medium` are not valid
combinations on Codex/ChatGPT.

The fallback column applies to planned, profiled workers; it is an
orchestrator-only exception, not a second planning recommendation. It permits
one retry only before a worker starts and only when
the host explicitly reports that the requested reasoning effort or capacity is
unavailable. The retry must use the listed profile, preserve the model, and be
recorded with the planned profile, effective profile, and host error. A blank
fallback stops the run. Never use it after a worker starts, for a work-item failure,
or for a model-wide availability error. This does not govern the separate,
one-time post-fix-review escalation defined by `$azure-task-orchestrator`.

## Claude Code

Claude Code has no pre-start capacity error signal, so there is no fallback
column: if the requested `model`/`effort` combination is unavailable, the
orchestrator stops the run instead of retrying with a substitute profile.

Use Claude model-specific profile IDs:

| Profile ID | Model | Reasoning effort |
|---|---|---|
| `sonnet-medium` | `sonnet` | `medium` |
| `sonnet-high` | `sonnet` | `high` |
| `sonnet-xhigh` | `sonnet` | `xhigh` |
| `opus-medium` | `opus` | `medium` |
| `opus-high` | `opus` | `high` |
| `opus-max` | `opus` | `max` |
| `opus-xhigh` | `opus` | `xhigh` |

Use `opus-max` only for the single post-fix recovery mapped below; do not
select it for regular planning.

`model` and `effort` here are exactly the `opts.model` and `opts.effort`
fields of a `Workflow` script's `agent()` call. The bare `Agent` tool cannot
set `effort` explicitly, so every implementation or repair child on Claude
Code must be spawned through a `Workflow` script's `agent()` call, not through
the `Agent` tool directly.

## Cursor

Cursor supports Composer 2.5 without a reasoning-effort setting, plus Grok 4.6
and Grok 4.7 at `high` or `xhigh`. Leave effort unset for Composer 2.5. For a
built-in profile, use the exact model and effort in the table. A parent may
also supply a separately validated run-scoped candidate for the active host.
Do not infer a capability ranking or automatic fallback between Grok versions.

| Profile ID | Cursor model | Reasoning effort |
|---|---|---|
| `composer2.5` | `composer2.5` | — |
| `grok4.6-high` | `grok4.6` | `high` |
| `grok4.6-xhigh` | `grok4.6` | `xhigh` |
| `grok4.7-high` | `grok4.7` | `high` |
| `grok4.7-xhigh` | `grok4.7` | `xhigh` |

## Planning and review-recovery escalation

For Codex/ChatGPT, use `luna-high`, `sol-medium`, or `sol-high` according to
the model-family and effort guidance in `../SKILL.md`. For Claude Code, use a
Sonnet profile when material decisions are resolved and an Opus profile when
residual judgment or deeper implementation reasoning remains. For Cursor,
choose a host-configured built-in profile or a parent-supplied candidate
validated for this invocation. Treat `xhigh` profiles as exceptions and apply
the gates in `../SKILL.md` before selecting one.

Select `luna-max` only on Codex/ChatGPT and only when the separate Luna gates
in `../SKILL.md` are all met.

For one post-fix review recovery triggered by a returned P0/P1 or explicitly
blocking correctness, security, data-loss, or verification finding, use this
separate mapping. Do not automatically select an `xhigh` profile for recovery.

Codex/ChatGPT:

`luna-high`, `luna-max`, `sol-medium` → `sol-high`.

`luna-xhigh`, `sol-high`, and `sol-xhigh` have no recovery mapping; report
recovery as unavailable.

Claude Code:

`sonnet-medium`, `sonnet-high`, `opus-medium` → `opus-high`; `opus-high` →
`opus-max`.

Claude Code has no recovery mapping for `sonnet-xhigh`, `opus-max`, or
`opus-xhigh`; report recovery as unavailable rather than substituting another
profile.

Cursor:

Cursor defines no post-fix recovery mapping. Report recovery as unavailable
rather than selecting a different Grok version or automatically choosing
`xhigh`.

These are single post-fix-review recovery steps, not capacity fallbacks. A host
must report recovery as unavailable if it cannot resolve the mapped profile; it
must not substitute another profile. Stop if the recovery review remains
blocking.
