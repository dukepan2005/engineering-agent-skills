# Execution Profile Registry

This registry is the canonical mapping from a planner output to the exact child
agent configuration. Use only these IDs. Do not override a mapped value in a
planner report or orchestrator dispatch.

Resolve the model or host configuration per host. The profile ID is the only
value the planner and orchestrator exchange; each host resolves it into its
own model/effort pair or combined model configuration only when spawning the
child agent.

## Codex

| Profile ID | Model | Reasoning effort | Pre-start capacity fallback |
|---|---|---|---|
| `terra-medium` | `gpt-5.6-terra` | `medium` | — |
| `terra-high` | `gpt-5.6-terra` | `high` | `terra-medium` |
| `terra-xhigh` | `gpt-5.6-terra` | `xhigh` | `terra-high` |
| `sol-medium` | `gpt-5.6-sol` | `medium` | — |
| `sol-high` | `gpt-5.6-sol` | `high` | `sol-medium` |
| `sol-max` | `gpt-5.6-sol` | `max` | `sol-high` |
| `sol-xhigh` | `gpt-5.6-sol` | `xhigh` | `sol-high` |

The fallback column is an orchestrator-only exception, not a second planning
recommendation. It permits one retry only before a worker starts and only when
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

| Profile ID | Model | Reasoning effort |
|---|---|---|
| `terra-medium` | `sonnet` | `medium` |
| `terra-high` | `sonnet` | `high` |
| `terra-xhigh` | `sonnet` | `xhigh` |
| `sol-medium` | `opus` | `medium` |
| `sol-high` | `claude-opus-5` | `high` |
| `sol-max` | `fable` | `max` |
| `sol-xhigh` | `claude-opus-5` | `xhigh` |

Claude Code's `terra` family uses `sonnet` (cost-optimized reasoning),
`sol-medium` uses `opus`, `sol-high` uses `claude-opus-5` (stronger judgment),
and `sol-max` uses Fable at `max` effort. `sol-xhigh` also uses `claude-opus-5`
at `xhigh` effort because this profile is reserved for cases where deep
reasoning, high-consequence judgment, and weaker verification converge.

`model` and `effort` here are exactly the `opts.model` and `opts.effort`
fields of a `Workflow` script's `agent()` call. The bare `Agent` tool cannot
set `effort` explicitly, so every profiled child on Claude Code must be
spawned through a `Workflow` script's `agent()` call, not through the `Agent`
tool directly.

## Cursor

Cursor resolves the regular profiles to `grok4.5 high`. The two exceptional
high-reasoning profiles use Cursor's `claude-opus-5 high` and `claude-opus-5 xhigh`
configurations. The Cursor mapping intentionally does not preserve the
profile's separate reasoning-effort semantics; the profile ID remains planner
metadata only. If Cursor exposes a different current label for these
configurations, use that host-provided label without changing the profile ID.
Do not silently replace an unavailable profile with a different profile.

| Profile ID | Cursor configuration |
|---|---|
| `terra-medium` | `grok4.5 high` |
| `terra-high` | `grok4.5 high` |
| `terra-xhigh` | `grok4.5 high` |
| `sol-medium` | `grok4.5 high` |
| `sol-high` | `claude-opus-5 high` |
| `sol-xhigh` | `claude-opus-5 xhigh` |

## Planning and review-recovery escalation

Use this regular planning order on every host:

`terra-medium` → `terra-high` → `sol-medium` → `sol-high`

Treat every `xhigh` profile as an exception outside the regular ladder. Apply
the gates in `../SKILL.md` before selecting one.

For one post-fix review recovery triggered by a returned P0/P1 or explicitly
blocking correctness, security, data-loss, or verification finding, use this
separate mapping:

`terra-medium`, `terra-high`, and `sol-medium` → `sol-high`; `sol-high` →
`sol-max`.

`sol-max` resolves to `gpt-5.6-sol` with `max` reasoning on Codex and Fable
with `max` effort on Claude Code. Cursor must report this recovery as
unavailable when requested; it must not substitute `sol-xhigh` or another
profile. This is not a capacity fallback, never jumps to `xhigh`, and stops
rather than escalating again if the recovery review remains blocking.
