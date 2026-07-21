# Engineering Agent Skills

Reusable, host-neutral agent skills for reliable software delivery. The skills
work with compatible hosts such as Codex and Claude Code; each skill defines
its own triggering and runtime instructions.

## Catalog

| Skill / Agent | Purpose |
|---|---|
| [`azure-devops-boards-skill`](skills/azure-devops-boards-skill/) | Safely read and mutate Azure DevOps Boards work items through the locally authenticated Azure CLI. |
| [`azure-task-implement`](skills/azure-task-implement/) | Implement code for one Azure Boards work item, using the preflight scope from the orchestrator. |
| [`task-boards-ops`](.claude/agents/task-boards-ops.md) | Cheap agent (haiku, low reasoning) for all Azure Boards operations (show, preflight, create, update, close-task, add-comment, add-link, current-sprint). On Codex, use gpt-5.6-luna via spawn_agent. |
| [`task-model-planner`](skills/task-model-planner/) | Recommend one named, lowest-reliable execution profile for each work item. |
| [`azure-task-orchestrator`](skills/azure-task-orchestrator/) | Plan and deliver a Story's work items: preflight via cheap agent, implement via named-profile agent, closeout via cheap agent. |

## Third-Party Dependency

`azure-task-implement` and the orchestrator both wrap the third-party
`$implement` workflow. Installing this repository does **not** install Skills
from [`mattpocock/skills`](https://github.com/mattpocock/skills). Before using
either, install its required `$implement` Skill separately for the same agent
host; `$tdd` is recommended because `$implement` uses it when appropriate.

For Codex, for example:

```bash
npx skills@latest add mattpocock/skills
```

The orchestrator also requires this repository's `$azure-devops-boards-skill`
and the `task-boards-ops` agent. It checks every dependency before it begins a
work item, stops and reports a missing dependency, and never installs one
automatically.

`$azure-devops-boards-skill` also requires a locally authenticated Azure CLI
with the Azure DevOps extension:

```bash
az extension add --name azure-devops
az login
```

See the [Azure Boards Skill guide](skills/azure-devops-boards-skill/README.md)
for connection variables and Azure CLI Python configuration.

## Install a Skill

Use the [`skills`](https://skills.sh/) CLI. List the Skills in this repository:

```bash
npx skills add dukepan2005/engineering-agent-skills --list --full-depth
```

Install one Skill globally for Claude Code:

```bash
npx skills add dukepan2005/engineering-agent-skills \
  --skill azure-devops-boards-skill --agent claude-code --global --full-depth
```

Install every Skill for every supported agent host:

```bash
npx skills add dukepan2005/engineering-agent-skills --all --global --full-depth
```

Omit `--global` to install into the current project instead. Omit the explicit
`--agent` option to let the CLI detect the active host. Use `npx skills update
--global` later to update installed global Skills.

## Use the Skills

### Azure Boards

Invoke `$azure-devops-boards-skill` when reading or changing Azure Boards work
items. The Skill validates every mutation before it applies it; see its
[dedicated guide](skills/azure-devops-boards-skill/README.md) for prerequisites
and command examples.

### Azure Task delivery

The orchestrator handles the full lifecycle of a work item, delegating Azure
Boards mechanical operations (preflight, closeout) to a cheap `task-boards-ops`
agent and code implementation to a planner-specified agent:

```text
$azure-task-orchestrator AB#168
```

It runs three sequential subagents per work item:
1. **Preflight** (cheap model, low reasoning) — reads the Azure Boards work item
   and returns a structured scope snapshot.
2. **Implement** (planner-specified model) — delegates to the `$implement`
   workflow for code, tests, and commit.
3. **Closeout** (cheap model, low reasoning) — checks off acceptance criteria,
   posts a completion comment, and closes the work item.

Use `$azure-task-implement` directly only when the orchestrator has already
performed preflight and you need just the code implementation step:

```text
$azure-task-implement AB#169
```

#### Dependencies

These wrappers do not bundle or install third-party Skills.

- `$azure-task-implement` requires only `$implement` from
  [`mattpocock/skills`](https://github.com/mattpocock/skills).
- `$azure-task-orchestrator` requires `$implement`, this repository's
  `$azure-devops-boards-skill`, and the `task-boards-ops` agent.

The orchestrator checks all dependencies before reading or changing a work item
and stops with the relevant install command if one is unavailable. `$tdd` from
`mattpocock/skills` is recommended, because `$implement` uses it where
appropriate.

### Task model planning

Invoke the Skill to plan a Story or a set of tickets:

```text
$task-model-planner AB#167
```

It returns one cost-aware execution-profile ID per work item, plus evidence,
confidence, and escalation triggers. The planner's bundled registry is the
single mapping from profile ID to model and reasoning effort.

### Recommended delivery flow

Always use the orchestrator for full lifecycle delivery:

```text
$task-model-planner <Story>
$azure-task-orchestrator <Story>
```

The orchestrator resolves each profile ID through `$task-model-planner`'s
canonical registry, then runs three sequential subagents per work item:
preflight (cheap model), implement (planner-specified model), closeout (cheap
model). It validates and displays the planner's ordered report, waits for
explicit user confirmation before dispatching, and stops the sequence on the
first unsuccessful worker. It never substitutes the parent model or runs work
items in parallel.

`$implement` is supplied by the agent host or your own installed implementation
workflow. The orchestrator requires it plus `$azure-devops-boards-skill` and
`task-boards-ops`; the planning Skill never edits code, Git state, or Azure
Boards.

## Development

- Keep reusable agent instructions in `SKILL.md`; keep human-facing catalog and
  installation guidance here.
- Run the applicable skill validation before committing.
- Run `python3 -m unittest discover -s skills/azure-devops-boards-skill/tests`
  after changes to the Azure Boards helper.
- Never commit credentials, local Azure configuration, generated caches, or
  agent-host configuration.

## License

No license has been selected yet. Add one before accepting external
contributions or publishing reusable code under an open-source license.
