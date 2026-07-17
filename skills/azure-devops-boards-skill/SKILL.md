---
name: azure-devops-boards-skill
description: Safely create, inspect, update, comment on, and link Azure DevOps Boards work items using the locally authenticated Azure CLI. Use when Codex or Claude Code needs to manage Azure Boards Stories, Tasks, Bugs, Markdown descriptions or comments, Sprint assignment, parent-child relations, blocking dependencies, or related links across any repository or Azure DevOps project. Also use when /to-spec, /to-tickets, /implement, or another workflow needs to publish or update work items in an Azure DevOps tracker.
allowed-tools: Bash(sh *)
---

# Azure DevOps Boards

Use the bundled helper for all Azure Boards operations. Do not reimplement Azure REST, CLI, or SDK orchestration inside a project.

## Resolve the helper

The helper is `scripts/azure-devops-boards.sh`, invoked through `sh` by **absolute path**. A bare relative path fails — the shell runs from the project root, not the skill folder — so resolve the absolute path for your host:

- **Claude Code** expands `${CLAUDE_SKILL_DIR}` to this skill's directory:
  `sh "${CLAUDE_SKILL_DIR}/scripts/azure-devops-boards.sh" …`
- **Codex** prints this skill's `SKILL.md` (e.g. `…/azure-devops-boards-skill/SKILL.md`) in its Skills section. Drop `SKILL.md` and append `scripts/azure-devops-boards.sh` for the helper's absolute path:
  `sh …/azure-devops-boards-skill/scripts/azure-devops-boards.sh …`

Set `HELPER` to the resolved path, then use `sh "$HELPER"` in the examples below.

## Require configuration

Require an installed, authenticated Azure CLI with the `azure-devops` extension. Pass connection flags explicitly or use:

- `AZURE_DEVOPS_ORG`
- `AZURE_DEVOPS_PROJECT`
- `AZURE_DEVOPS_TEAM`
- `AZURE_CLI_PYTHON` when the launcher cannot locate Azure CLI's Python runtime

Read the repository's tracker instructions before operating. Treat its work-item types, states, Sprint rules, tags, acceptance criteria, and workflow gates as authoritative.

## Follow the safety workflow

1. Read the relevant work item before changing it.
2. Prepare long descriptions and comments in temporary Markdown files.
3. When repository rules require checklist synchronization, update only acceptance criteria backed by implementation and verification evidence, and keep the work item out of any completed state until every required criterion is checked. Preserve the rest of the Description and verify it before changing state.
4. Run every mutation without `--apply` first.
5. Review the validated work item, fields, Sprint, Markdown metadata, and relations.
6. Repeat the identical command with `--apply` only when authorized.
7. Accept success only after the helper's persisted read-back succeeds.

`az boards work-item update --discussion` is off-limits: it posts plain text, not a native relation. Express dependencies with `add-link` instead.

## Use the commands

```bash
sh "$HELPER" current-sprint
sh "$HELPER" show --id 61
sh "$HELPER" implement-preflight --id 61

sh "$HELPER" create \
  --type Task --title 'Implement contract' \
  --description-file /tmp/task.md --parent 61 \
  --tags ready-for-agent

sh "$HELPER" update \
  --id 123 --state Active --description-file /tmp/task.md

sh "$HELPER" add-comment \
  --id 123 --comment-file /tmp/comment.md

sh "$HELPER" add-link \
  --id 124 --kind predecessor --target-id 123

sh "$HELPER" close-task \
  --id 123 --expected-rev 8 --state Closed --comment-file /tmp/completion.md
```

Add `--apply` after validation. For `predecessor`, `--target-id` blocks the current `--id`. For `parent`, the target is the current item's parent. Re-adding an existing relation returns `unchanged`.

## Keep implementation synchronization compact

For one Task, run `implement-preflight` once before editing. It returns a compact
snapshot of the revision, state, title, structured acceptance criteria (or the
full Description when it cannot safely extract them), and relation IDs. Keep it
as the scope authority for the current thread. Re-run only after a task, branch,
or session change, or when a scope conflict appears.

At closeout, run `close-task` once without `--apply`, then repeat it with
`--apply`. Pass the preflight `rev` as `--expected-rev` to avoid an extra
pre-write read; the JSON Patch revision test still fails safely if the work item
changed. `close-task` can update Description and state in one work-item mutation
and post one Markdown completion comment. It verifies both persisted results;
the two Azure operations are not represented as atomic.

Read [references/azure-boards-api.md](references/azure-boards-api.md) only when endpoint behavior or relation semantics need investigation.
