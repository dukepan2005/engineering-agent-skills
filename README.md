# Engineering Agent Skills

Reusable, host-neutral agent skills for reliable software delivery. The skills
work with compatible hosts such as Codex and Claude Code; each skill defines
its own triggering and runtime instructions.

## Catalog

| Skill | Purpose |
|---|---|
| [`azure-devops-boards-skill`](skills/azure-devops-boards-skill/) | Safely read and mutate Azure DevOps Boards work items through the locally authenticated Azure CLI. |
| [`azure-task-implement`](skills/azure-task-implement/) | Wrap `$implement` with compact Azure Boards Task preflight and closeout. |
| [`task-model-planner`](skills/task-model-planner/) | Recommend the lowest reliable `gpt-5.6-terra` or `gpt-5.6-sol` profile and thinking level for each Task. |

## Third-Party Dependency

`azure-task-implement` wraps the third-party `$implement` workflow. Installing
this repository does **not** install Skills from
[`mattpocock/skills`](https://github.com/mattpocock/skills). Before using the
wrapper, install its required `$implement` and `$code-review` Skills separately
for the same agent host; `$tdd` is recommended because `$implement` uses it
when appropriate.

For Codex, for example:

```bash
npx skills@latest add mattpocock/skills
```

The wrapper checks these dependencies together with this repository's
`$azure-devops-boards-skill` before it begins a Task. It stops and reports a
missing dependency; it never installs one automatically.

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

It runs one compact tracker preflight, invokes `$implement`, and performs a
validated Markdown-safe closeout after successful verification and commit. Use
`$azure-task-implement AB#169 --state Closed` only when the final state is
explicitly known; otherwise the wrapper preserves the current state.

#### Dependencies

This wrapper does not bundle or install third-party Skills. Before invoking it,
install `$implement` and `$code-review` from
[`mattpocock/skills`](https://github.com/mattpocock/skills), and install this
repository's `$azure-devops-boards-skill` for the same agent host. It checks for
all three before reading or changing a Task and stops with the relevant install
command if one is unavailable. `$tdd` from `mattpocock/skills` is recommended,
because `$implement` uses it where appropriate.

### Task model planning

Invoke the Skill to plan a Story or a set of tickets:

```text
$task-model-planner AB#167
```

It returns one cost-aware recommendation per Task: `gpt-5.6-terra` or
`gpt-5.6-sol`, a thinking level, evidence, confidence, and escalation triggers.

### Recommended delivery flow

```text
$task-model-planner <Story>
$azure-task-implement <Task>
```

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
