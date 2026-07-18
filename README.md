# Engineering Agent Skills

Reusable, host-neutral agent skills for reliable software delivery. The skills
work with compatible hosts such as Codex and Claude Code; each skill defines
its own triggering and runtime instructions.

## Catalog

| Skill | Purpose |
|---|---|
| [`azure-devops-boards-skill`](skills/azure-devops-boards-skill/) | Safely read and mutate Azure DevOps Boards work items through the locally authenticated Azure CLI. |
| [`azure-task-implement`](skills/azure-task-implement/) | Wrap `$implement` with compact Azure Boards Task preflight and closeout. |
| [`task-model-planner`](skills/task-model-planner/) | Recommend one named, lowest-reliable execution profile for each Task. |
| [`azure-task-orchestrator`](skills/azure-task-orchestrator/) | Plan and deliver a Story's Azure Tasks in order, each in a named-profile subagent. |

## Third-Party Dependency

`azure-task-implement` wraps the third-party `$implement` workflow. Installing
this repository does **not** install Skills from
[`mattpocock/skills`](https://github.com/mattpocock/skills). Before using the
wrapper, install its required `$implement` Skill separately for the same agent
host; `$tdd` is recommended because `$implement` uses it when appropriate.

For Codex, for example:

```bash
npx skills@latest add mattpocock/skills
```

The wrapper also requires this repository's `$azure-devops-boards-skill`. It
checks every dependency before it begins a Task, stops and reports a missing
dependency, and never installs one automatically.

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

Invoke this wrapper to implement one Azure Boards Task without reproducing a
project-specific tracker gate:

```text
$azure-task-implement AB#169
```

It runs one compact tracker preflight, then delegates implementation, testing,
review, and commit to the complete `$implement` workflow before performing
validated Markdown-safe closeout. Use `$azure-task-implement AB#169 --state
Closed` only when the final state is explicitly known; otherwise the wrapper
preserves the current state.

#### Dependencies

This wrapper does not bundle or install third-party Skills. Before invoking it,
install `$implement` from
[`mattpocock/skills`](https://github.com/mattpocock/skills), and install this
repository's `$azure-devops-boards-skill` for the same agent host. It checks
both before reading or changing a Task and stops with the relevant install
command if one is unavailable. `$tdd` from `mattpocock/skills` is recommended,
because `$implement` uses it where appropriate.

### Task model planning

Invoke the Skill to plan a Story or a set of tickets:

```text
$task-model-planner AB#167
```

It returns one cost-aware execution-profile ID per Task, plus evidence,
confidence, and escalation triggers. The planner's bundled registry is the
single mapping from profile ID to model and reasoning effort.

### Recommended delivery flow

```text
$task-model-planner <Story>
$azure-task-implement <Task>
```

### Profile-planned sequential delivery

Use the orchestrator when every Task in a Story or explicit set should be
planned first and then delivered sequentially by subagents with the recommended
execution profile:

```text
$azure-task-orchestrator AB#168
```

It resolves each profile ID through `$task-model-planner`'s canonical registry,
then creates a named subagent with that exact model and reasoning effort. If
the host rejects the requested effort before the worker starts, it may make one
same-model, lower-effort retry from that registry and records both profiles.
It validates the planner's ordered report before dispatching any Task and stops the
sequence on the first unsuccessful worker; it never substitutes the parent
model or runs Tasks in parallel.

`$implement` is supplied by the agent host or your own installed implementation
workflow. `$azure-task-implement` requires it plus
`$azure-devops-boards-skill`; the planning Skill never edits code, Git state, or
Azure Boards.

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
