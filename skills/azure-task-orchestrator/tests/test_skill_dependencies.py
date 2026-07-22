import unittest
from pathlib import Path
import re


REPO_ROOT = Path(__file__).resolve().parents[3]


class SkillDependencyContractTests(unittest.TestCase):
    def read_skill(self, name: str) -> str:
        return (REPO_ROOT / "skills" / name / "SKILL.md").read_text()

    def test_orchestrator_uses_skill_names_without_source_provenance(self) -> None:
        text = self.read_skill("azure-task-orchestrator")

        self.assertRegex(
            text,
            re.compile(
                r"\*\*REQUIRED SKILLS:\*\* Use `\$task-model-planner`,\s+"
                r"`\$azure-task-implement`, and\s+`\$azure-devops-boards-skill`\."
            ),
        )
        self.assertIn("Use `$task-model-planner`", text)
        self.assertIn("Use `$azure-task-implement`", text)
        self.assertIn("Use `$azure-devops-boards-skill`", text)

        for forbidden in (
            "Slash command:",
            "Context:",
            "Path:",
            "supplied Skill",
            "Skill source",
            "<skill-dir>",
            "resolved absolute path",
        ):
            self.assertNotIn(forbidden, text)

    def test_planner_delegates_boards_by_skill_name(self) -> None:
        text = self.read_skill("task-model-planner")

        self.assertIn("Use `$azure-devops-boards-skill`", text)
        self.assertIn("`model=gpt-5.6-luna` and `reasoning_effort=low`", text)
        self.assertIn("on Claude\n   Code, use Haiku with low reasoning", text)
        self.assertNotIn("<skill-dir>", text)
        self.assertNotIn("absolute path", text)

    def test_implementation_embeds_the_local_implement_flow_only(self) -> None:
        text = self.read_skill("azure-task-implement")

        self.assertIn("Implement the work described by the provided scope.", text)
        self.assertIn("Use `$tdd` where possible, at pre-agreed seams.", text)
        self.assertIn("Run typechecking regularly, single test files regularly,", text)
        self.assertIn("Once done, use `$code-review` to review the work.", text)
        self.assertIn("Commit your work to the current branch.", text)
        self.assertNotIn("`$implement`", text)
        self.assertNotIn("orchestrator", text.lower())
        self.assertNotIn("preflight", text.lower())
        self.assertNotIn("closeout", text.lower())
        self.assertNotIn("working-tree review mode", text)
        self.assertNotIn("skills/azure-task-implement/references", text)

    def test_closeout_rewrites_evidence_backed_checklists_and_posts_comment(self) -> None:
        text = self.read_skill("azure-task-orchestrator")

        self.assertIn("Read the current full Description", text)
        self.assertIn("explicit implementation evidence", text)
        self.assertIn("--description-file <tmpdescription>", text)
        self.assertIn("--comment-file <tmpcomment>", text)
        self.assertNotIn("never pass `--check-ac` or `--description-file`", text)

    def test_boards_role_is_semantic_on_codex(self) -> None:
        text = self.read_skill("azure-devops-boards-skill")

        self.assertIn("semantic `task-boards-ops` role", text)
        self.assertIn("`model=gpt-5.6-luna`", text)
        self.assertIn("`reasoning_effort=low`", text)


if __name__ == "__main__":
    unittest.main()
