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

    def test_planner_consumes_parent_snapshot_without_boards_dispatch(self) -> None:
        text = self.read_skill("task-model-planner")

        self.assertIn("authoritative tracker snapshot from the parent", text)
        self.assertIn("Do not read Azure Boards", text)
        self.assertNotIn("Use `$azure-devops-boards-skill`", text)
        self.assertNotIn("task-boards-ops", text)
        self.assertNotIn("spawn a child", text.lower())
        self.assertNotIn("<skill-dir>", text)
        self.assertNotIn("absolute path", text)

    def test_orchestrator_reads_planning_snapshot_before_planner(self) -> None:
        text = self.read_skill("azure-task-orchestrator")

        self.assertIn("Planning Snapshot — spawn task-boards-ops", text)
        self.assertIn("planning-snapshot --story <story-id>", text)
        self.assertIn("planning-snapshot --id <id> --id <id>", text)
        self.assertIn("direct New Task and Bug children", text)
        self.assertRegex(text, re.compile(r"Do not read a\s+non-New child"))
        self.assertRegex(text, re.compile(r"Then\s+pass that composite snapshot to\s+`\$task-model-planner`"))
        self.assertIn("linked specification documents", text)
        self.assertIn("`linkedSpecifications` collection", text)
        self.assertIn("`{reference, material, content}` decision", text)
        self.assertIn("Accept both Task and Bug targets", text)
        self.assertIn("planner is\n   read-only planning logic; it must not read Azure Boards", text)

    def test_planner_requires_type_specific_fields_when_description_is_absent(self) -> None:
        text = self.read_skill("task-model-planner")

        self.assertIn("all fields", text)
        self.assertIn("type-specific field data", text)
        self.assertIn("full Markdown", text)
        self.assertIn("`content`", text)
        self.assertIn("return `Input not ready`", text)

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
