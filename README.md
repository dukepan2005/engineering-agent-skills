# Engineering Agent Skills

Reusable, host-neutral agent skills for reliable software delivery. The skills
work with compatible hosts such as Codex and Claude Code; each skill defines
its own triggering and runtime instructions.

## Catalog

| Skill / Agent | Purpose |
|---|---|
| [`azure-devops-boards-skill`](skills/azure-devops-boards-skill/) | Safely read and mutate Azure DevOps Boards work items through the locally authenticated Azure CLI. |
| [`azure-task-implement`](skills/azure-task-implement/) | Implement code from a provided specification or ticket scope. |
| `task-boards-ops` | Semantic role for a cheap Boards-only child (Haiku or gpt-5.6-luna, low reasoning). Claude Code may optionally provide the [named agent](.claude/agents/task-boards-ops.md). |
| [`task-model-planner`](skills/task-model-planner/) | Recommend one named, lowest-reliable execution profile from a parent-provided work-item snapshot and linked specification authority. |
| [`azure-task-orchestrator`](skills/azure-task-orchestrator/) | Plan and deliver implementation-ready Azure Boards work items from a Story or an explicit item set: preflight via cheap agent, implement via named-profile agent, closeout via cheap agent. |

## Review Dependency

`azure-task-implement` embeds the local workflow from Matt Pocock's
`$implement` Skill. It does not require that Skill to be model-invocable. The
embedded workflow uses `$code-review` before committing, so the host must make
that Skill available in the same catalog.

The orchestrator also requires this repository's `$task-model-planner`,
`$azure-task-implement`, and `$azure-devops-boards-skill`. The parent
orchestrator invokes
dependencies by Skill name, stops when the host reports one unavailable, and
never requires users to supply installation paths or paste Skill bodies.

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

The orchestrator handles the full lifecycle of implementation-ready Azure
Boards work items. It accepts either a Story, whose direct New Task and Bug child items
it plans and delivers in dependency order, or an explicit item set, including a
single Task or Bug. It delegates Azure Boards mechanical operations (preflight,
closeout) to a cheap child in the semantic `task-boards-ops` role and code
implementation to a planner-specified agent:

```text
$azure-task-orchestrator AB#168
```

It first reads one planning snapshot through a direct `task-boards-ops` child,
then combines that Boards snapshot with any linked specification documents from
the accepted planning authority before invoking the read-only planner. For each work item it
runs three sequential subagents:
1. **Preflight** (cheap model, low reasoning) — reads the current Azure Boards
   item and returns a structured scope snapshot.
2. **Implement** (planner-specified model) — follows `$azure-task-implement`'s
   direct code, test, review, and commit workflow.
3. **Closeout** (cheap model, low reasoning) — checks evidence-backed
   Description checklist items, posts the completion comment, and closes the
   work item with optimistic revision checking.

Use `$azure-task-implement` whenever a specification or ticket scope is already
available and only local implementation work is required. In the three-stage
Azure delivery flow, the orchestrator supplies that scope to its implementation
worker.

#### Dependencies

These wrappers do not bundle or install their review dependency.

- `$azure-task-implement` requires `$code-review` from the same host Skill
  catalog. It does not require `$implement`.
- `$azure-task-orchestrator` requires `$task-model-planner`,
  `$azure-task-implement`, and `$azure-devops-boards-skill`.

The orchestrator checks its direct dependencies before reading or changing a
work item and stops when one is unavailable.

### Task model planning

Invoke the Skill with an authoritative parent-provided snapshot when a separate
planning pass is needed. The snapshot must include linked specification
documents when the work-item references require them:

```text
$task-model-planner <parent-provided-snapshot>
```

It returns one cost-aware execution-profile ID per work item, plus evidence,
confidence, and escalation triggers. The planner's bundled registry is the
single mapping from profile ID to model and reasoning effort.

### Recommended delivery flow

Use the orchestrator for full lifecycle delivery; it obtains the Boards
snapshot before invoking the planner:

```text
$azure-task-orchestrator <Story-or-explicit-work-item-set>
```

The orchestrator resolves each profile ID through `$task-model-planner`'s
canonical registry, then runs three sequential subagents per work item:
preflight (cheap model), implement (planner-specified model), closeout (cheap
model). It validates and displays the planner's ordered report, waits for
explicit user confirmation before dispatching, and stops the sequence on the
first unsuccessful worker. It never substitutes the parent model or runs work
items in parallel.

`$azure-task-implement` supplies its own implementation workflow and invokes
`$code-review` by Skill name before commit. The semantic
`task-boards-ops` role isolates Boards mechanics; the planning Skill never edits
code, Git state, or Azure Boards.

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
