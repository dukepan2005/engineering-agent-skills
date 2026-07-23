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

    def test_orchestrator_spawns_claude_code_children_through_workflow(self) -> None:
        text = self.read_skill("azure-task-orchestrator")

        self.assertIn(
            "the bare `Agent` tool cannot set reasoning\neffort explicitly",
            text,
        )
        self.assertIn("agent(prompt, {model: 'haiku', effort: 'low'})", text)
        self.assertIn("agent(prompt,\n{model, effort, label})`", text)
        self.assertIn("Claude Code has no pre-start capacity", text)

        # A Workflow script has no pause point for user input, so it must not
        # be asked to span the pre-confirmation planning steps: only the
        # post-confirmation per-item delivery loop may run inside one.
        self.assertIn("no pause point for user input", text)
        self.assertIn(
            "single `Workflow` script invoked once after the user confirms the plan",
            text,
        )
        self.assertNotIn(
            "run the entire delivery sequence — planning snapshot,\n"
            "preflight, implement, closeout — as one `Workflow` script",
            text,
        )

    def test_boards_skill_routes_claude_code_child_through_workflow(self) -> None:
        text = self.read_skill("azure-devops-boards-skill")

        self.assertIn("agent(prompt, {model: 'haiku', effort: 'low'})", text)
        self.assertIn("inside a `Workflow` script", text)

    def test_execution_profile_registry_has_per_host_tables(self) -> None:
        text = (
            REPO_ROOT
            / "skills"
            / "task-model-planner"
            / "references"
            / "execution-profiles.md"
        ).read_text()

        self.assertIn("## Codex", text)
        self.assertIn("## Claude Code", text)
        self.assertIn("| `terra-medium` | `sonnet` | `medium` |", text)
        self.assertIn("| `sol-high` | `opus` | `high` |", text)
        self.assertIn("| `sol-xhigh` | `fable` | `xhigh` |", text)
        self.assertIn("no pre-start capacity error signal", text)

    def test_confirm_plan_and_report_distinguish_fallback_by_host(self) -> None:
        text = self.read_skill("azure-task-orchestrator")

        # Confirm the Validated Plan section must clarify that Claude Code
        # omits the fallback column since it has no pre-start capacity signal.
        self.assertIn(
            "On Codex, also include\nthe pre-start capacity fallback profile if any; Claude Code has no such\nfallback, so omit that column there.",
            text,
        )

        # Report section must also clarify fallback is Codex-only.
        self.assertIn(
            "any pre-start capacity fallback error\n(Codex only)",
            text,
        )

    def test_claude_code_delivery_loop_script_exists_and_is_valid(self) -> None:
        script_path = REPO_ROOT / "skills" / "azure-task-orchestrator" / "references" / "claude-code-delivery-loop.js"
        self.assertTrue(
            script_path.exists(),
            f"Workflow script template not found at {script_path}",
        )

        script_text = script_path.read_text()

        # Verify meta block structure
        self.assertIn("export const meta = {", script_text)
        self.assertIn("'azure-task-orchestrator-delivery'", script_text)
        self.assertIn("phases:", script_text)

        # Verify PROFILES registry matches execution-profiles.md
        self.assertIn("const PROFILES = {", script_text)
        self.assertIn("'terra-medium': { model: 'sonnet', effort: 'medium' }", script_text)
        self.assertIn("'sol-xhigh': { model: 'fable', effort: 'xhigh' }", script_text)

        # Verify core agent() calls for three steps
        self.assertIn("agent(", script_text)
        self.assertIn("preflight", script_text.lower())
        self.assertIn("implement", script_text.lower())
        self.assertIn("closeout", script_text.lower())

        # Verify script returns a report structure
        self.assertIn("return report", script_text)
        self.assertIn("totalItems", script_text)
        self.assertIn("completedItems", script_text)


if __name__ == "__main__":
    unittest.main()
