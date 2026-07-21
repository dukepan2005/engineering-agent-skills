---
name: azure-devops-boards-skill
description: Safely create, inspect, update, comment on, and link Azure DevOps Boards work items using the locally authenticated Azure CLI. Use when Codex or Claude Code needs to manage Azure Boards Epics, Features, Stories, Tasks, Bugs, Markdown descriptions or comments, Sprint assignment, parent-child relations, blocking dependencies, or related links across any repository or Azure DevOps project. Also use when the to-spec, to-tickets, or implement skill needs to publish or update Azure DevOps work items.
allowed-tools: Bash(sh *)
---

# Azure DevOps Boards

This skill is a thin router. It contains **no command documentation** — you
cannot run Azure Boards operations from here. The commands live in
[references/commands.md](references/commands.md), which only the dedicated
agent reads.

## Delegate every operation to the task-boards-ops agent

Your first action on any Azure Boards request is to spawn the `task-boards-ops`
agent (`model=haiku`/`gpt-5.6-luna`, low reasoning). The spawn instruction must
be **self-contained** — it cannot assume the agent has any preloaded definition.
Tell the agent to read `<skill-dir>/references/commands.md` to resolve the
helper, then run the specific command (e.g. `create --type Bug ...`,
`show --id 42`, `close-task --apply ...`) with its parameters. The agent
returns structured JSON.

On Codex, spawn with `model=gpt-5.6-luna` and `reasoning_effort=low` via
`spawn_agent`. On hosts with named agent types, spawn `task-boards-ops` by name
(its definition already points at commands.md, but include the read step in the
instruction anyway, so the same instruction works on every host).

Do not run any helper command yourself. Do not read `references/commands.md`
into this context. Do not search for duplicate work items before creating one.

## Fallback (agent spawning unavailable)

Only if the host cannot spawn the `task-boards-ops` agent, read
[references/commands.md](references/commands.md) and execute the operation
directly with the `Bash(sh *)` tool. This path is more expensive and should be
rare.