# Execution Profile Registry

This registry is the canonical mapping from a planner output to the exact child
agent configuration. Use only these IDs. Do not override a mapped value in a
planner report or orchestrator dispatch.

| Profile ID | Model | Reasoning effort | Pre-start capacity fallback |
|---|---|---|---|
| `terra-medium` | `gpt-5.6-terra` | `medium` | — |
| `terra-high` | `gpt-5.6-terra` | `high` | `terra-medium` |
| `terra-xhigh` | `gpt-5.6-terra` | `xhigh` | `terra-high` |
| `sol-medium` | `gpt-5.6-sol` | `medium` | — |
| `sol-high` | `gpt-5.6-sol` | `high` | `sol-medium` |
| `sol-xhigh` | `gpt-5.6-sol` | `xhigh` | `sol-high` |

Use this regular planning and escalation order:

`terra-medium` → `terra-high` → `sol-medium` → `sol-high`

Treat every `xhigh` profile as an exception outside the regular ladder. Apply
the gates in `../SKILL.md` before selecting one.

Treat the profile ID as the planner and orchestrator interface. Resolve the
model and reasoning effort only when spawning the child agent.

The fallback column is an orchestrator-only exception, not a second planning
recommendation. It permits one retry only before a worker starts and only when
the host explicitly reports that the requested reasoning effort or capacity is
unavailable. The retry must use the listed profile, preserve the model, and be
recorded with the planned profile, effective profile, and host error. A blank
fallback stops the run. Never use it after a worker starts, for a Task failure,
or for a model-wide availability error.
