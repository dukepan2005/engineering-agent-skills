# Azure DevOps Boards Skill

An [Agent Skills](https://agentskills.io/) package for safely managing Azure DevOps Boards work items from Codex, Claude Code, and other compatible agent hosts.

It provides a shared, project-neutral implementation for:

- Reading work items and the current team Sprint
- Creating User Stories, Tasks, and Bugs
- Updating descriptions, workflow states, and iterations
- Posting comments with explicit Markdown format
- Creating native parent, predecessor, and related links
- Validating mutations before writing and verifying persisted results afterward

The authoritative agent workflow is in [`SKILL.md`](SKILL.md). Repository-specific tracker policies remain authoritative for work-item types, states, tags, Sprint selection, and delivery gates.

## Safety model

Mutation commands are validate-only by default. A write occurs only when the same command is repeated with `--apply`.

Updates use Azure DevOps work-item revisions for optimistic concurrency. Descriptions and comments are verified as Markdown, and persisted fields or relations are read back before success is reported.

When a repository requires checklist synchronization, update and verify the Markdown description before changing the work-item state. The Skill does not decide which acceptance criteria have been satisfied.

The helper uses the locally authenticated Azure CLI SDK. It does not accept, read, or print a personal access token.

## Prerequisites

Install and authenticate Azure CLI with its Azure DevOps extension:

```bash
az extension add --name azure-devops
az login
```

If Azure CLI is installed outside a Homebrew location, set `AZURE_CLI_PYTHON` to its bundled Python executable.

## Installation

Clone this collection repository, then copy the Azure Boards Skill directory
into the personal Skill directory used by your agent host.

### Codex

```bash
git clone https://github.com/dukepan2005/engineering-agent-skills.git /tmp/engineering-agent-skills
cp -R /tmp/engineering-agent-skills/skills/azure-devops-boards-skill \
  ~/.codex/skills/azure-devops-boards-skill
```

Invoke it with `$azure-devops-boards-skill`.

### Claude Code

```bash
git clone https://github.com/dukepan2005/engineering-agent-skills.git /tmp/engineering-agent-skills
cp -R /tmp/engineering-agent-skills/skills/azure-devops-boards-skill \
  ~/.claude/skills/azure-devops-boards-skill
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
sh "$SKILL_DIR/scripts/azure-devops-boards.sh" show --id 61
```

Prepare long descriptions and comments as Markdown files. Validate a Task creation without writing:

```bash
sh "$SKILL_DIR/scripts/azure-devops-boards.sh" create \
  --type Task \
  --title 'Implement contract' \
  --description-file /tmp/task.md \
  --tags ready-for-agent \
  --parent 61
```

Review the validation result, then repeat the identical command with `--apply`:

```bash
sh "$SKILL_DIR/scripts/azure-devops-boards.sh" create --apply \
  --type Task \
  --title 'Implement contract' \
  --description-file /tmp/task.md \
  --tags ready-for-agent \
  --parent 61
```

The same two-step rule applies to updates, comments, and links:

```bash
sh "$SKILL_DIR/scripts/azure-devops-boards.sh" update \
  --id 123 --state Active

sh "$SKILL_DIR/scripts/azure-devops-boards.sh" add-comment \
  --id 123 --comment-file /tmp/comment.md

sh "$SKILL_DIR/scripts/azure-devops-boards.sh" add-link \
  --id 124 --kind predecessor --target-id 123
```

For `predecessor`, the target work item blocks the current work item. For `parent`, the target is the current work item's parent. Re-adding an existing relation returns `unchanged`.

## Workflow integration

The Skill description explicitly covers `/to-spec`, `/to-tickets`, `/implement`, and other workflows that publish or update Azure DevOps work items. For deterministic routing, projects should also state in their `AGENTS.md` (Codex) or `CLAUDE.md` (Claude Code) instructions that Azure Boards operations must use this Skill instead of reimplementing REST, CLI, or SDK orchestration.

## Scope

This Skill intentionally does not define a project's product workflow. It does not decide which Sprint, state, tags, hierarchy, or dependency graph is correct. It also does not create iterations or artifact links such as branches and commits. Keep those decisions in repository instructions and extend the Skill deliberately if reusable support is needed.

See [`references/azure-boards-api.md`](references/azure-boards-api.md) for the endpoint and relation mapping used by the helper.
