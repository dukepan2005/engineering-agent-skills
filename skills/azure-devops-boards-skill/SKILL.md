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

## Router mode: delegate every operation to a Boards child

When the current prompt does **not** assign the semantic `task-boards-ops`
role, your first action on an Azure Boards request is to spawn one isolated
child and assign that role. On Codex, use
`model=gpt-5.6-luna` and `reasoning_effort=low`. On Claude Code, use
`agent(prompt, {model: 'haiku', effort: 'low'})` inside a `Workflow` script;
the bare `Agent` tool cannot set `effort` explicitly. If the caller is itself
already running inside a `Workflow` script (for example, when the
`$azure-task-orchestrator` is in the post-confirmation delivery loop on Claude
Code), make this call from within that same script rather than opening a
second one. A host may use a named `task-boards-ops` agent when available, but
named-agent configuration is not required.

The spawn instruction must be self-contained. Tell the child to use
`$azure-devops-boards-skill` in the semantic role and name the exact operation
and parameters. The child returns structured JSON.

Do not run any helper command yourself. Do not read
`references/commands.md` into this router context. Do not search for duplicate
work items before creating one.

## Boards child mode: execute the local helper

When the current prompt already assigns the semantic `task-boards-ops` role,
do not spawn another child. After this Skill is loaded, your first operational
action is to read [references/commands.md](references/commands.md). Then follow
this sequence:

1. Resolve its absolute helper path and invoke only the requested operation with
   `sh "$HELPER"`.
2. Return the helper's structured output without inferring missing data.

When the requested operation creates a Bug, route reproduction steps and
environment information to the native Bug fields when the caller supplies
them (`Microsoft.VSTS.TCM.ReproSteps` via `--repro-steps-file` and
`Microsoft.VSTS.TCM.SystemInfo` via `--system-info-file`). If the operation
provides one creation-time `--comment-file` and no Repro Steps file, treat that
payload as the Bug's Repro Steps. This fallback applies only inside creation;
later `add-comment` calls are real Discussion comments. A Discussion comment
is otherwise supplemental context, not a substitute when those values are
known. Bug field files are Markdown: pass their contents through verbatim, do
not convert them to HTML, and do not attach Description's Markdown metadata to
the Bug fields.

Before resolving, inspecting, selecting, or testing anything, read that command
reference. There is no separate capability-discovery step.

The helper is a local shell command, not an Azure MCP tool. Do not use
`ALL_TOOLS` or the absence of an Azure MCP tool to decide whether the helper is
available. If the command reference cannot be read, the helper cannot be
resolved or run, or the helper returns an installation, authentication, or
network failure, report that concrete error; do not replace it with a generic
capability verdict.

## Fallback (agent spawning unavailable)

Only if the host cannot spawn a Boards child, read
[references/commands.md](references/commands.md) and execute the operation
directly with the `Bash(sh *)` tool. This path is more expensive and should be
rare.
