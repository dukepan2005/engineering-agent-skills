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
