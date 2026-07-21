---
name: azure-devops-boards-skill
description: Safely create, inspect, update, comment on, and link Azure DevOps Boards work items using the locally authenticated Azure CLI. Use when Codex or Claude Code needs to manage Azure Boards Epics, Features, Stories, Tasks, Bugs, Markdown descriptions or comments, Sprint assignment, parent-child relations, blocking dependencies, or related links across any repository or Azure DevOps project. Also use when the to-spec, to-tickets, or implement skill needs to publish or update Azure DevOps work items.
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

Set `HELPER` to the resolved path, then use `sh "$HELPER"` in the examples below. If
`${CLAUDE_SKILL_DIR}` is unset (e.g. outside a skill invocation), resolve the path
directly: under Claude Code the skill lives at `~/.claude/skills/azure-devops-boards-skill/`,
so the helper is `~/.claude/skills/azure-devops-boards-skill/scripts/azure-devops-boards.sh`
(under the plugin cache for plugin installs).

## Require configuration

Require an installed, authenticated Azure CLI with the `azure-devops` extension. Pass connection flags explicitly or use:

- `AZURE_DEVOPS_ORG`
- `AZURE_DEVOPS_PROJECT`
- `AZURE_DEVOPS_TEAM`
- `AZURE_CLI_PYTHON` when the launcher cannot locate Azure CLI's Python runtime

The helper reads `AZURE_DEVOPS_ORG`/`AZURE_DEVOPS_PROJECT`/`AZURE_DEVOPS_TEAM` as
defaults and makes those flags optional when set, so exporting them once per shell
session avoids repeating `--organization`/`--project` on every call.

Read the repository's tracker instructions before operating. Treat its work-item types, states, Sprint rules, tags, acceptance criteria, and workflow gates as authoritative.

## Follow the safety workflow

1. Read the relevant work item before changing it.
2. Prepare long descriptions and comments in temporary Markdown files.
3. When repository rules require checklist synchronization, update only acceptance criteria backed by implementation and verification evidence, and keep the work item out of any completed state until every required criterion is checked. Preserve the rest of the Description and verify it before changing state.
4. **Default:** run a mutation once with `--apply`. The helper validates server-side, applies, and read-back-checks the persisted result in a single call — that internal validate-plus-read-back is the safety net, so a separate dry-run is not required for routine writes.
5. **Opt-in two-phase** for high-risk changes or when a human should review before the write: run the identical command without `--apply` (dry-run), review the validated summary, then repeat it with `--apply`.
6. Accept success only after the helper's persisted read-back succeeds.

`az boards work-item update --discussion` is off-limits: it posts plain text, not a native relation. Express dependencies with `add-link` instead.

## Use the commands

```bash
sh "$HELPER" current-sprint
sh "$HELPER" show --id 61               # compact default (id/rev/type/state/title/relations)
sh "$HELPER" show --id 61 --full        # raw Azure JSON
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
  --id 123 --expected-rev 8 --state Closed --comment-file /tmp/completion.md \
  --check-ac all     # or --check-ac 'ships the contract' to toggle matching AC only
```

Add `--apply` after validation. `--check-ac` reads the live Description, toggles the matching markdown checkboxes (`all` or a case-insensitive fragment), and patches it back in the same mutation — use it instead of fetching and rewriting the whole Description. It is mutually exclusive with `--description-file`. For `predecessor`, `--target-id` blocks the current `--id`. For `parent`, the target is the current item's parent. Re-adding an existing relation returns `unchanged`.

## Keep implementation synchronization compact

For one implementation-ready work item, run `implement-preflight` once before
editing. It returns a compact snapshot of the revision, type, state, title,
structured acceptance criteria (or the full Description when it cannot safely
extract them), and relation IDs. Keep it as the scope authority for the current
thread. Re-run only after an item, branch, or session change, or when a scope
conflict appears.

At closeout, run `close-task` once with `--apply`, passing the preflight `rev`
as `--expected-rev` to avoid an extra pre-write read. If the rev advanced in the
meantime (for example a commit's `Refs AB#123` auto-link bumped it), the helper
detects the forward move, re-reads the live rev, and retries the mutation once —
only an irreconcilable conflict (or a second consecutive rev change) surfaces.
Toggle acceptance criteria with `--check-ac all|FRAGMENT` instead of fetching
and rewriting the whole Description. `close-task` can update Description and
state in one work-item mutation and post one Markdown completion comment; it
verifies both persisted results, and the two Azure operations are not atomic.
For a high-risk closeout, the opt-in two-phase dry-run (run without `--apply`,
then with) is still available.

Read [references/azure-boards-api.md](references/azure-boards-api.md) only when endpoint behavior or relation semantics need investigation.
