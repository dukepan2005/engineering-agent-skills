# Azure DevOps Boards Skill

An [Agent Skills](https://agentskills.io/) package for safely managing Azure DevOps Boards work items from Codex, Claude Code, and other compatible agent hosts.

It provides a shared, project-neutral implementation for:

- Reading work items and the current team Sprint
- Creating Epics, Features, User Stories, Tasks, and Bugs
- Updating descriptions, workflow states, and iterations
- Posting comments with explicit Markdown format
- Creating native parent, predecessor, and related links
- Validating mutations before writing and verifying persisted results afterward
- Producing compact implementation preflight snapshots and closeout summaries

The authoritative agent workflow is in [`SKILL.md`](SKILL.md). Repository-specific tracker policies remain authoritative for work-item types, states, tags, Sprint selection, and delivery gates.

## Safety model

Mutating commands validate server-side, apply, and verify the persisted read-back in one `--apply` call. Two-phase validate-then-apply (the identical command run first without `--apply`, then repeated with it) is available as an opt-in for high-risk changes or human review.

Updates use Azure DevOps work-item revisions for optimistic concurrency: a stale revision fails the mutation immediately, with no automatic retry. Descriptions and comments are verified as Markdown, and persisted fields or relations are read back before success is reported.

The close flow sets the terminal state and posts one completion comment; it does not read or rewrite the Description. `close-task --check-ac` remains available as an opt-in that checks matching acceptance-criteria checkboxes server-side, but the default close path does not use it — acceptance status goes in the comment. The Skill does not decide which acceptance criteria have been satisfied.

The helper uses the locally authenticated Azure CLI SDK. It does not accept, read, or print a personal access token.

## Prerequisites

Install and authenticate Azure CLI with its Azure DevOps extension:

```bash
az extension add --name azure-devops
az login
```

If Azure CLI is installed outside a Homebrew location, set `AZURE_CLI_PYTHON` to its bundled Python executable.

## Installation

Install this Skill from the collection repository with the `skills` CLI.

### Codex

```bash
npx skills add dukepan2005/engineering-agent-skills \
  --skill azure-devops-boards-skill --agent codex --global --full-depth
```

Invoke it with `$azure-devops-boards-skill`.

### Claude Code

```bash
npx skills add dukepan2005/engineering-agent-skills \
  --skill azure-devops-boards-skill --agent claude-code --global --full-depth
```

Invoke it with `/azure-devops-boards-skill`.

Archive-based installers may not preserve executable file modes. Agents should invoke the launcher through `sh`, as documented in `SKILL.md`.

## Configuration

Pass connection options to each command or configure these environment variables:

```bash
export AZURE_DEVOPS_ORG='https://dev.azure.com/example'
export AZURE_DEVOPS_PROJECT='ExampleProject'
export AZURE_DEVOPS_TEAM='Example Team'
```

`AZURE_DEVOPS_TEAM` is required only for commands that resolve the current Sprint.

Agents locate the helper script themselves at runtime: Claude Code expands `${CLAUDE_SKILL_DIR}`, and Codex derives the path from the `SKILL.md` path it lists. For manual testing, set the skill directory explicitly:

```bash
SKILL_DIR="$HOME/.codex/skills/azure-devops-boards-skill"      # Codex
# or
SKILL_DIR="$HOME/.claude/skills/azure-devops-boards-skill"      # Claude Code
```

## Quick start

Read operations execute immediately:

```bash
sh "$SKILL_DIR/scripts/azure-devops-boards.sh" current-sprint
sh "$SKILL_DIR/scripts/azure-devops-boards.sh" show --id 61               # compact summary
sh "$SKILL_DIR/scripts/azure-devops-boards.sh" show --id 61 --full        # raw Azure JSON
sh "$SKILL_DIR/scripts/azure-devops-boards.sh" implement-preflight --id 61
```

Prepare long descriptions and comments as Markdown files. Mutating commands
default to a single `--apply` call — the helper validates server-side, applies,
and verifies the persisted read-back in that one call:

```bash
sh "$SKILL_DIR/scripts/azure-devops-boards.sh" create --apply \
  --type Task \
  --title 'Implement contract' \
  --description-file /tmp/task.md \
  --tags ready-for-agent \
  --parent 61

sh "$SKILL_DIR/scripts/azure-devops-boards.sh" update --apply \
  --id 123 --state Active

sh "$SKILL_DIR/scripts/azure-devops-boards.sh" add-comment --apply \
  --id 123 --comment-file /tmp/comment.md

sh "$SKILL_DIR/scripts/azure-devops-boards.sh" add-link --apply \
  --id 124 --kind predecessor --target-id 123
```

For a high-risk change, or when a human should review before the write, omit
`--apply` first to validate only, then repeat the identical command with
`--apply`.

For `predecessor`, the target work item blocks the current work item. For `parent`, the target is the current work item's parent. Re-adding an existing relation returns `unchanged`.

For an implementation Task, use one compact preflight snapshot before editing,
then one closeout command at the end:

```bash
sh "$SKILL_DIR/scripts/azure-devops-boards.sh" close-task --apply \
  --id 123 --expected-rev 8 --state Closed --comment-file /tmp/completion.md
```

`close-task` sets the terminal state and posts one Markdown completion comment
in a single call; it does not read or rewrite the Description. (`--check-ac
all|FRAGMENT` remains an opt-in that checks matching acceptance-criteria
checkboxes in the live Description server-side, without unchecking any that are
already done.) `implement-preflight` retains structured acceptance criteria, or
falls back to the complete Description when it cannot safely identify them. The
close call verifies both persisted results. The two Azure operations remain
separately verified rather than being presented as an atomic transaction. A
stale revision fails the mutation immediately, with no automatic retry.

## Workflow integration

The Skill description explicitly covers `/to-spec`, `/to-tickets`, `/implement`, and other workflows that publish or update Azure DevOps work items. For deterministic routing, projects should also state in their `AGENTS.md` (Codex) or `CLAUDE.md` (Claude Code) instructions that Azure Boards operations must use this Skill instead of reimplementing REST, CLI, or SDK orchestration.

## Scope

This Skill intentionally does not define a project's product workflow. It does not decide which Sprint, state, tags, hierarchy, or dependency graph is correct. It also does not create iterations or artifact links such as branches and commits. Keep those decisions in repository instructions and extend the Skill deliberately if reusable support is needed.

See [`references/azure-boards-api.md`](references/azure-boards-api.md) for the endpoint and relation mapping used by the helper.
