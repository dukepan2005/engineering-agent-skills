# Resolve the helper path

The helper is `scripts/azure-devops-boards.sh`, invoked through `sh` by **absolute
path**. A bare relative path fails — the shell runs from the project root, not
the skill folder — so resolve the absolute path for your host:

- **Claude Code** expands `${CLAUDE_SKILL_DIR}` to this skill's directory:
  `sh "${CLAUDE_SKILL_DIR}/scripts/azure-devops-boards.sh" …`
- **Codex** prints this skill's `SKILL.md` (e.g. `…/azure-devops-boards-skill/SKILL.md`)
  in its Skills section. Drop `SKILL.md` and append
  `scripts/azure-devops-boards.sh` for the helper's absolute path:
  `sh …/azure-devops-boards-skill/scripts/azure-devops-boards.sh …`
- If `${CLAUDE_SKILL_DIR}` is unset (e.g. outside a skill invocation), resolve
  the path directly: under Claude Code the skill lives at
  `~/.claude/skills/azure-devops-boards-skill/`, so the helper is
  `~/.claude/skills/azure-devops-boards-skill/scripts/azure-devops-boards.sh`
  (under the plugin cache for plugin installs).

Set `HELPER` to the resolved path, then use `sh "$HELPER"` for every command.
