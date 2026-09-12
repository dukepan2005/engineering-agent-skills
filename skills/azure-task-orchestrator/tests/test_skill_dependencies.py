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
        self.assertIn("planning-snapshot --organization <organization> --project <project>\n--story <story-id>", text)
        self.assertIn("planning-snapshot --organization <organization> --project <project> --id <id>\n--id <id>", text)
        self.assertIn("direct New Task and Bug children", text)
        self.assertRegex(text, re.compile(r"Do not read a\s+non-New child"))
        self.assertRegex(text, re.compile(r"Give `\$task-model-planner` the validated composite snapshot file"))
        self.assertIn("linked specification documents", text)
        self.assertIn("`linkedSpecifications` collection", text)
        self.assertIn("`{reference, material, content}` decision", text)
        self.assertIn("Accept both Task and Bug targets", text)
        self.assertIn("planner is\n   read-only planning logic; it must not read Azure Boards", text)

    def test_orchestrator_uses_verified_file_handoff_for_large_snapshots(self) -> None:
        text = self.read_skill("azure-task-orchestrator")

        self.assertIn("run-scoped temporary directory", text)
        self.assertIn('> "<tmpsnapshot>"', text)
        self.assertIn("do not return the snapshot JSON", text)
        self.assertIn('`jq -e . "<tmpsnapshot>"`', text)
        self.assertIn("SHA-256", text)
        self.assertIn("compact JSON manifest", text)
        self.assertIn("byte count and SHA-256 match the manifest", text)
        self.assertIn("`<tmpcomposite>`", text)
        self.assertIn("inline an oversized snapshot", text)
        self.assertIn("must delete it after planning succeeds or stops", text)

    def test_planner_accepts_parent_validated_snapshot_file(self) -> None:
        text = self.read_skill("task-model-planner")

        self.assertIn("parent-validated JSON file", text)
        self.assertIn("verified byte count", text)
        self.assertIn("mismatched file as `Input not ready`", text)
        self.assertIn("not permission to read Azure Boards", text)

    def test_planner_requires_type_specific_fields_when_description_is_absent(self) -> None:
        text = self.read_skill("task-model-planner")

        self.assertIn("all fields", text)
        self.assertIn("type-specific field data", text)
        self.assertIn("full Markdown", text)
        self.assertIn("`content`", text)
        self.assertIn("return `Input not ready`", text)

    def test_implementation_preserves_standalone_and_parent_review_modes(self) -> None:
        text = self.read_skill("azure-task-implement")

        self.assertIn("Implement the work described by the provided scope in the current workspace", text)
        self.assertIn("Use `$tdd` where possible, at pre-agreed seams.", text)
        self.assertIn("Run typechecking regularly,", text)
        self.assertIn("single test files regularly,", text)
        self.assertIn("`reviewOwner=self` (the backward-compatible default)", text)
        self.assertIn("`reviewOwner=parent`", text)
        self.assertRegex(text, r"do not invoke `\$code-review`, spawn review\s+agents")
        self.assertIn('"outcome": "ready_for_review"', text)
        self.assertIn('`{"outcome":"ready_for_closeout", ...}`', text)
        self.assertIn("review_escalation_required", text)
        self.assertIn("P0/P1", text)
        self.assertIn("again against the same `reviewBase...HEAD` delta", text)
        self.assertIn("same task commit", text)
        self.assertRegex(text, r"Do not perform Azure Boards\s+operations in either mode")
        self.assertNotIn("working-tree review mode", text)
        self.assertNotIn("skills/azure-task-implement/references", text)

    def test_orchestrator_owns_flat_review_dispatch(self) -> None:
        text = self.read_skill("azure-task-orchestrator")

        self.assertRegex(text, r"parent\s+orchestrator owns the delivery control plane")
        self.assertIn("No implementation or review worker may spawn another worker", text)
        self.assertIn("two parallel read-only children", text)
        self.assertIn("reviewOwner=parent", text)
        self.assertIn("Review and repair — parent owns flat review dispatch", text)
        self.assertIn("references/flat-review-worker.md", text)
        self.assertIn("Promise.all", text)
        self.assertNotIn("Let `$azure-task-implement` own that work item's implementation,\nverification, review, and commit.", text)

    def test_flat_review_worker_contract_is_no_spawn_and_axis_scoped(self) -> None:
        text = (
            REPO_ROOT
            / "skills"
            / "azure-task-orchestrator"
            / "references"
            / "flat-review-worker.md"
        ).read_text()

        self.assertIn("parent starts exactly two read-only workers in", text)
        self.assertIn("do not start children", text)
        self.assertIn("reviewAxis", text)
        self.assertIn("reviewBase", text)
        self.assertIn("no_spec_available", text)
        self.assertIn("Return JSON only", text)
        self.assertNotIn("working-tree review mode", text)
        self.assertNotIn("skills/azure-task-implement/references", text)

    def test_closeout_rewrites_evidence_backed_checklists_and_posts_comment(self) -> None:
        text = self.read_skill("azure-task-orchestrator")

        self.assertIn("Read the current full Description", text)
        self.assertIn("current-code evidence", text)
        self.assertIn("explicit current-code implementation evidence", text)
        self.assertIn("--description-file <tmpdescription>", text)
        self.assertRegex(text, r"--comment-file\s+<tmpcomment>")
        self.assertNotIn("never pass `--check-ac` or `--description-file`", text)

    def test_boards_role_is_semantic_across_hosts(self) -> None:
        text = self.read_skill("azure-devops-boards-skill")

        self.assertIn("semantic `task-boards-ops` role", text)
        self.assertIn("prefer the currently available Luna", text)
        self.assertIn("if Luna is unavailable", text)
        self.assertIn("lightweight model, such as Terra with low reasoning", text)
        self.assertIn("On Cursor", text)
        self.assertIn("lightweight Composer model", text)
        self.assertRegex(text, r"Do not require a\s+specific Composer model ID")
        self.assertNotRegex(text, r"`model=[^`]+`")
        self.assertIn("`reasoning_effort=low`", text)

    def test_orchestrator_spawns_claude_code_children_through_workflow(self) -> None:
        text = self.read_skill("azure-task-orchestrator")

        self.assertRegex(
            text,
            r"the bare `Agent` tool cannot set reasoning\s+effort\s+explicitly",
        )
        self.assertIn("agent(prompt, {model: 'haiku', effort: 'low'})", text)
        self.assertRegex(text, r"agent\(prompt, \{model, effort, label\}\)")
        self.assertIn("Claude Code has no pre-start capacity", text)

        # The planning loop still stays in the conversation; only the
        # post-confirmation flat delivery loop runs inside one Workflow.
        self.assertIn("no pause point for user input", text)
        self.assertIn(
            "this entire post-confirmation loop runs as one `Workflow`",
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
        self.assertIn("## Cursor", text)
        self.assertIn("| `sol-max` | `gpt-5.6-sol` | `max` | `sol-high` |", text)
        self.assertIn("| `terra-medium` | `sonnet` | `medium` |", text)
        self.assertIn("| `sol-high` | `claude-opus-5` | `high` |", text)
        self.assertIn("| `sol-max` | `claude-opus-5` | `max` |", text)
        self.assertIn("| `sol-xhigh` | `claude-opus-5` | `xhigh` |", text)
        self.assertIn("Cursor resolves the regular profiles to `grok4.5 high`", text)
        self.assertIn("`claude-opus-5 high` and `claude-opus-5 xhigh`", text)
        self.assertRegex(text, r"does not preserve the\s+profile's separate reasoning-effort semantics")
        self.assertIn("| `terra-medium` | `grok4.5 high` |", text)
        self.assertIn("| `terra-high` | `grok4.5 high` |", text)
        self.assertIn("| `sol-medium` | `grok4.5 high` |", text)
        self.assertIn("| `sol-high` | `claude-opus-5 high` |", text)
        self.assertIn("| `sol-xhigh` | `claude-opus-5 xhigh` |", text)
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
        self.assertIn("'sol-high': { model: 'claude-opus-5', effort: 'high' }", script_text)
        self.assertIn("'sol-max': { model: 'claude-opus-5', effort: 'max' }", script_text)
        self.assertIn("'sol-xhigh': { model: 'claude-opus-5', effort: 'xhigh' }", script_text)

        # Verify core agent() calls for the flat stages.
        self.assertIn("agent(", script_text)
        self.assertIn("preflight", script_text.lower())
        self.assertIn("implement", script_text.lower())
        self.assertIn("Promise.all", script_text)
        self.assertIn("reviewAxis", script_text)
        self.assertIn("reviewBase", script_text)
        self.assertIn("reviewOwner=parent", script_text)
        self.assertIn("closeout", script_text.lower())

        # Verify script returns a report structure
        self.assertIn("return report", script_text)
        self.assertIn("totalItems", script_text)
        self.assertIn("completedItems", script_text)

    def test_orchestrator_requires_and_propagates_explicit_tracker_connection(self) -> None:
        skill = self.read_skill("azure-task-orchestrator")
        script = (
            REPO_ROOT
            / "skills"
            / "azure-task-orchestrator"
            / "references"
            / "claude-code-delivery-loop.js"
        ).read_text()

        self.assertIn("trackerConnection", skill)
        self.assertIn("--organization <organization>", skill)
        self.assertIn("--project <project>", skill)
        self.assertNotIn("implement-preflight --id <id>", skill)
        self.assertNotIn("show --full --id <id>", skill)

        self.assertIn("args.trackerConnection", script)
        self.assertIn("--organization ${shellQuote(trackerConnection.organization)}", script)
        self.assertIn("--project ${shellQuote(trackerConnection.project)}", script)
        self.assertNotIn("implement-preflight --id ${itemId}", script)
        self.assertNotIn("show --full --id ${itemId}", script)

    def test_orchestrator_escalates_only_blocking_post_fix_review_findings(self) -> None:
        skill = self.read_skill("azure-task-orchestrator")
        script = (
            REPO_ROOT
            / "skills"
            / "azure-task-orchestrator"
            / "references"
            / "claude-code-delivery-loop.js"
        ).read_text()

        self.assertIn("Review Escalation", skill)
        self.assertIn("review_escalation_required", skill)
        self.assertRegex(skill, r"do not run\s+closeout or\s+dispatch the next work item")
        self.assertIn("Do not auto-select an `xhigh` profile", skill)
        self.assertIn("REVIEW_ESCALATION", script)
        self.assertIn("review_escalation_required", script)
        self.assertIn("review_escalation_failed", script)
        self.assertIn("review_escalation_unavailable", script)
        self.assertIn("`terra-medium`, `terra-high`, and `sol-medium` → `sol-high`.", skill)
        self.assertIn("`sol-high` → `sol-max`.", skill)
        self.assertIn("'terra-medium': 'sol-high'", script)
        self.assertIn("'terra-high': 'sol-high'", script)
        self.assertIn("'sol-medium': 'sol-high'", script)
        self.assertIn("'sol-high': 'sol-max'", script)


if __name__ == "__main__":
    unittest.main()
