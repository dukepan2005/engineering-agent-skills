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

## Delegate every operation to a Boards child

Your first action on an Azure Boards request is to spawn one isolated child and
assign it the semantic `task-boards-ops` role. On Codex, use
`model=gpt-5.6-luna` and `reasoning_effort=low`. On Claude Code, use Haiku with
low reasoning. A host may use a named `task-boards-ops` agent when available,
but named-agent configuration is not required.

The spawn instruction must be self-contained. Tell the child to use
`$azure-devops-boards-skill` in the semantic role and name the exact operation
and parameters. The child returns structured JSON.

When the current prompt already assigns the semantic `task-boards-ops` role,
do not spawn another child. Read [references/commands.md](references/commands.md)
to resolve the helper, run only the requested Boards operation, and return its
structured output.

Do not run any helper command yourself. Do not read `references/commands.md`
into this context. Do not search for duplicate work items before creating one.

## Fallback (agent spawning unavailable)

Only if the host cannot spawn a Boards child, read
[references/commands.md](references/commands.md) and execute the operation
directly with the `Bash(sh *)` tool. This path is more expensive and should be
rare.
