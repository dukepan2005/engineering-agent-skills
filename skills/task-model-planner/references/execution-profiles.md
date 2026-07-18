# Execution Profile Registry

This registry is the canonical mapping from a planner output to the exact child
agent configuration. Use only these IDs. Do not override a mapped value in a
planner report or orchestrator dispatch.

| Profile ID | Model | Reasoning effort |
|---|---|---|
| `terra-medium` | `gpt-5.6-terra` | `medium` |
| `terra-high` | `gpt-5.6-terra` | `high` |
| `terra-xhigh` | `gpt-5.6-terra` | `xhigh` |
| `sol-medium` | `gpt-5.6-sol` | `medium` |
| `sol-high` | `gpt-5.6-sol` | `high` |
| `sol-xhigh` | `gpt-5.6-sol` | `xhigh` |

Treat the profile ID as the planner and orchestrator interface. Resolve the
model and reasoning effort only when spawning the child agent.
