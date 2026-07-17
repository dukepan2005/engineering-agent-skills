# Engineering Agent Skills

Reusable, host-neutral agent skills for reliable software delivery. The skills
work with compatible hosts such as Codex and Claude Code; each skill defines
its own triggering and runtime instructions.

## Catalog

| Skill | Purpose |
|---|---|
| [`azure-devops-boards-skill`](skills/azure-devops-boards-skill/) | Safely read and mutate Azure DevOps Boards work items through the locally authenticated Azure CLI. |
| [`implementation-preread`](skills/implementation-preread/) | Produce a read-only, source-backed implementation readiness brief before implementation. |
| [`task-model-planner`](skills/task-model-planner/) | Recommend the lowest reliable `gpt-5.6-terra` or `gpt-5.6-sol` profile and thinking level for each Task. |

## Install a Skill

Clone this repository, then copy the desired directory from `skills/` into the
personal skill directory used by your agent host. For example, Codex discovers
skills from `~/.codex/skills/<skill-name>/`; Claude Code uses its corresponding
personal skill directory.

Each skill is self-contained. Preserve its relative `scripts/`, `references/`,
`agents/`, and `tests/` directories when installing it.

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
