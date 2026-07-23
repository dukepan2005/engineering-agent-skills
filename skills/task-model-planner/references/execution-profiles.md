# Execution Profile Registry

This registry is the canonical mapping from a planner output to the exact child
agent configuration. Use only these IDs. Do not override a mapped value in a
planner report or orchestrator dispatch.

Resolve the model and reasoning effort per host. The profile ID is the only
value the planner and orchestrator exchange; each host resolves it into its
own model/effort pair only when spawning the child agent.

## Codex

| Profile ID | Model | Reasoning effort | Pre-start capacity fallback |
|---|---|---|---|
| `terra-medium` | `gpt-5.6-terra` | `medium` | — |
| `terra-high` | `gpt-5.6-terra` | `high` | `terra-medium` |
| `terra-xhigh` | `gpt-5.6-terra` | `xhigh` | `terra-high` |
| `sol-medium` | `gpt-5.6-sol` | `medium` | — |
| `sol-high` | `gpt-5.6-sol` | `high` | `sol-medium` |
| `sol-xhigh` | `gpt-5.6-sol` | `xhigh` | `sol-high` |

The fallback column is an orchestrator-only exception, not a second planning
recommendation. It permits one retry only before a worker starts and only when
the host explicitly reports that the requested reasoning effort or capacity is
unavailable. The retry must use the listed profile, preserve the model, and be
recorded with the planned profile, effective profile, and host error. A blank
fallback stops the run. Never use it after a worker starts, for a work-item failure,
or for a model-wide availability error.

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
| `sol-high` | `opus` | `high` |
| `sol-xhigh` | `fable` | `xhigh` |

Claude Code's `terra` family uses `sonnet` (cost-optimized reasoning), `sol-medium`
and `sol-high` use `opus` (stronger judgment). `sol-xhigh` escalates to `fable`
(latest, most capable tier) because this profile is reserved for cases where
deep reasoning, high-consequence judgment, and weaker verification converge —
situations where Codex's second-highest reasoning level (`gpt-5.6-sol`) is not
sufficient. On Claude Code, `fable` is the semantic equivalent of this
severity level.

`model` and `effort` here are exactly the `opts.model` and `opts.effort`
fields of a `Workflow` script's `agent()` call. The bare `Agent` tool cannot
set `effort` explicitly, so every profiled child on Claude Code must be
spawned through a `Workflow` script's `agent()` call, not through the `Agent`
tool directly.

## Shared escalation order

Use this regular planning and escalation order on every host:

`terra-medium` → `terra-high` → `sol-medium` → `sol-high`

Treat every `xhigh` profile as an exception outside the regular ladder. Apply
the gates in `../SKILL.md` before selecting one.
