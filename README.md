# Engineering Agent Skills

Reusable, host-neutral agent skills for reliable software delivery. The skills
work with compatible hosts such as Codex and Claude Code; each skill defines
its own triggering and runtime instructions.

## Catalog

| Skill | Purpose |
|---|---|
| [`azure-devops-boards-skill`](skills/azure-devops-boards-skill/) | Safely read and mutate Azure DevOps Boards work items through the locally authenticated Azure CLI. |
| [`implementation-preread`](skills/implementation-preread/) | In Codex, delegate one fixed-model, read-only preread before implementation. |
| [`task-model-planner`](skills/task-model-planner/) | Recommend the lowest reliable `gpt-5.6-terra` or `gpt-5.6-sol` profile and thinking level for each Task. |

## Install a Skill

Use the [`skills`](https://skills.sh/) CLI. List the Skills in this repository:

```bash
npx skills add dukepan2005/engineering-agent-skills --list --full-depth
```

Install one Skill globally for Codex:

```bash
npx skills add dukepan2005/engineering-agent-skills \
  --skill implementation-preread --agent codex --global --full-depth
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

### Implementation preread

Invoke the Skill before starting an implementation run:

```text
$implementation-preread AB#169
```

It returns a read-only readiness brief covering current authority, scope, code
map, risks, a recommended implementation profile, and a compact handoff. The
later implementation must independently re-read current authority and code.

This default form runs in the main agent and creates no subagent. To opt into a
fixed-model Codex subagent, use:

```text
$implementation-preread --delegated AB#169
```

For the delegated form, install the fixed prereader agent once after installing
the Skill:

```bash
mkdir -p ~/.codex/agents
cp ~/.codex/skills/implementation-preread/assets/codex/implementation-prereader.toml \
  ~/.codex/agents/implementation-prereader.toml
```

Start the next Codex task after copying the file. A delegated invocation creates
exactly one `gpt-5.6-terra` / `medium` read-only subagent and forwards its
600–900-token brief. It performs no verification commands and does not fall
back to a different model if the agent is unavailable. This integration is
Codex-specific; `--delegated` fails closed in other hosts.

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
$implementation-preread <Task>
$implement <Task>
```

`$implement` is supplied by the agent host or your own installed implementation
workflow. The two planning Skills never edit code, Git state, or Azure Boards.

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
