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
        self.assertRegex(
            text,
            re.compile(
                r"In the parent agent's current context, invoke `\$task-model-planner` with the\s+"
                r"validated composite snapshot file"
            ),
        )
        self.assertIn("linked specification documents", text)
        self.assertIn("`linkedSpecifications` collection", text)
        self.assertIn("`{reference, material, content}` decision", text)
        self.assertIn("Accept both Task and Bug targets", text)
        self.assertIn("planner's report as guidance, not tracker authority", text)

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

    def test_planner_requires_current_model_docs_and_benchmark_evidence(self) -> None:
        text = self.read_skill("task-model-planner")

        self.assertIn("## Verify Model and Evaluation Evidence", text)
        self.assertIn("**Official model documentation.**", text)
        self.assertIn("**Benchmark reports.**", text)
        self.assertIn("latest relevant report", text)
        self.assertIn("original report or benchmark maintainer's results", text)
        self.assertIn("exact model version, reasoning effort, and agent/harness", text)
        self.assertIn("do not make an exact-model or cross-model performance claim", text)
        self.assertIn("compare effort levels", text)
        self.assertIn("performance benefit is unverified", text)
        self.assertIn("## Model and evaluation evidence", text)

    def test_orchestrator_accepts_optional_current_host_candidates(self) -> None:
        text = self.read_skill("azure-task-orchestrator")

        self.assertIn("Users may naturally ask to consider another model", text)
        self.assertIn("No structured parameter block is required", text)
        self.assertIn("If the user does not ask for extra choices, use the built-in profiles only", text)
        self.assertIn("Represent any requested choices internally as an optional\n`additional_candidates` list", text)
        self.assertIn("Candidates apply to the current host, so do not\nask the user to specify a host", text)
        self.assertIn("never modify the canonical\nprofile registry", text)
        self.assertIn("Assign each remaining accepted candidate a stable, invocation-local ID such\n   as `additional-1`", text)
        self.assertIn("additional candidate has no fallback", text)
        self.assertIn("additional-*` candidate IDs", text)
        self.assertIn("`plannedCandidate`", text)
        self.assertIn("`additionalCandidates`", text)

    def test_planner_only_selects_parent_validated_dynamic_candidates(self) -> None:
        text = self.read_skill("task-model-planner")

        self.assertIn("parent may optionally provide an\n`additional_candidates` list", text)
        self.assertRegex(text, r"parent[-\s]+assigned invocation-local `candidate_id`")
        self.assertIn("parent must verify that the\npair is spawnable on the current host", text)
        self.assertIn("only from the candidate pool for the active host", text)
        self.assertIn("Output only the\nselected candidate ID", text)
        self.assertIn("Execution candidate ID", text)
        self.assertIn("profile-id or additional-id", text)

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
        self.assertIn("prefer GPT-6 Luna", text)
        self.assertIn("if it is unavailable, use GPT-6 Sol", text)
        self.assertIn("`reasoning_effort=high`", text)
        self.assertIn("`reasoning_effort=medium`", text)
        self.assertIn("On Cursor", text)
        self.assertIn("use `composer2.5`", text)
        self.assertIn("reasoning-effort setting", text)
        self.assertNotRegex(text, r"`model=[^`]+`")

    def test_readme_boards_role_uses_current_helper_profiles(self) -> None:
        text = (REPO_ROOT / "README.md").read_text()

        self.assertIn("GPT-6 Luna high", text)
        self.assertIn("GPT-6 Sol medium", text)
        self.assertIn("Composer 2.5", text)
        self.assertIn("effort unset", text)

    def test_readme_documents_optional_run_scoped_candidates(self) -> None:
        text = (REPO_ROOT / "README.md").read_text()

        self.assertIn("caller-supplied candidates", text)
        self.assertIn("Users may naturally ask the orchestrator", text)
        self.assertIn("No structured parameter block is\nrequired", text)
        self.assertIn("remain scoped to that invocation", text)

    def test_orchestrator_spawns_claude_code_children_through_workflow(self) -> None:
        text = self.read_skill("azure-task-orchestrator")

        self.assertRegex(
            text,
            r"the bare `Agent` tool cannot set reasoning\s+effort\s+explicitly",
        )
        self.assertIn("agent(prompt, {model: 'haiku', effort: 'low'})", text)
        self.assertRegex(text, r"agent\(prompt, \{model, effort, label\}\)")
        self.assertRegex(text, r"Claude Code has no pre-start\s+capacity error signal")

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

        self.assertIn("## Codex / ChatGPT", text)
        self.assertIn("## Claude Code", text)
        self.assertIn("## Cursor", text)
        self.assertIn("| `luna-high` | `gpt-6-luna` | `high` | — |", text)
        self.assertIn("| `luna-xhigh` | `gpt-6-luna` | `xhigh` | `luna-high` |", text)
        self.assertIn("| `luna-max` | `gpt-6-luna` | `max` | — |", text)
        self.assertIn("| `sol-medium` | `gpt-6-sol` | `medium` | — |", text)
        self.assertIn("| `sol-xhigh` | `gpt-6-sol` | `xhigh` | `sol-high` |", text)
        claude = text.split("## Claude Code", 1)[1].split("## Cursor", 1)[0]
        self.assertIn("| `sonnet-medium` | `sonnet` | `medium` |", claude)
        self.assertIn("| `sonnet-high` | `sonnet` | `high` |", claude)
        self.assertIn("| `sonnet-xhigh` | `sonnet` | `xhigh` |", claude)
        self.assertIn("| `opus-medium` | `opus` | `medium` |", claude)
        self.assertIn("| `opus-high` | `opus` | `high` |", claude)
        self.assertIn("| `opus-max` | `opus` | `max` |", claude)
        self.assertIn("| `opus-xhigh` | `opus` | `xhigh` |", claude)
        self.assertIn("Use `opus-max` only for the single post-fix recovery", claude)
        self.assertNotRegex(claude, r"`(?:luna|sol)-")

        cursor = text.split("## Cursor", 1)[1].split("## Planning", 1)[0]
        self.assertIn("| `composer2.5` | `composer2.5` | — |", cursor)
        self.assertEqual(
            [
                ("composer2.5", "composer2.5", "—"),
                ("grok4.6-high", "grok4.6", "`high`"),
                ("grok4.6-xhigh", "grok4.6", "`xhigh`"),
                ("grok4.7-high", "grok4.7", "`high`"),
                ("grok4.7-xhigh", "grok4.7", "`xhigh`"),
            ],
            re.findall(
                r"^\| `([^`]+)` \| `([^`]+)` \| (`[^`]+`|—) \|$",
                cursor,
                re.MULTILINE,
            ),
        )
        self.assertNotIn("opus", cursor.lower())
        self.assertIn("no pre-start capacity error signal", text)

    def test_confirm_plan_and_report_distinguish_fallback_by_host(self) -> None:
        text = self.read_skill("azure-task-orchestrator")

        # Confirm fallback data is shown for built-in profiles, not invented
        # for additional candidates.
        self.assertIn(
            "pre-start capacity fallback profile if one exists; for an additional candidate,\n"
            "show that no fallback is defined.",
            text,
        )
        self.assertIn("(Codex/ChatGPT only)", text)

        # Report section must also clarify fallback is Codex-only.
        self.assertRegex(
            text,
            r"any\s+pre-start capacity fallback error \(Codex/ChatGPT only\)",
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
        self.assertIn("'sonnet-medium': { model: 'sonnet', effort: 'medium' }", script_text)
        self.assertIn("'sonnet-high': { model: 'sonnet', effort: 'high' }", script_text)
        self.assertIn("'sonnet-xhigh': { model: 'sonnet', effort: 'xhigh' }", script_text)
        self.assertIn("'opus-medium': { model: 'opus', effort: 'medium' }", script_text)
        self.assertIn("'opus-high': { model: 'opus', effort: 'high' }", script_text)
        self.assertIn("'opus-max': { model: 'opus', effort: 'max' }", script_text)
        self.assertIn("'opus-xhigh': { model: 'opus', effort: 'xhigh' }", script_text)

        # Verify core agent() calls for the flat stages.
        self.assertIn("agent(", script_text)
        self.assertIn("preflight", script_text.lower())
        self.assertIn("implement", script_text.lower())
        self.assertIn("Promise.all", script_text)
        self.assertIn("reviewAxis", script_text)
        self.assertIn("reviewBase", script_text)
        self.assertIn("reviewOwner=parent", script_text)
        self.assertIn("closeout", script_text.lower())
        self.assertIn("additionalCandidates", script_text)
        self.assertIn("plannedCandidate", script_text)
        self.assertIn("resolveCandidate(candidateId)", script_text)
        self.assertIn("agentOptions(candidate, label)", script_text)
        self.assertIn("plannedMapping: describeCandidate", script_text)
        self.assertIn("plannerEvidence and orderReason are required", script_text)
        self.assertIn("Exact model/effort mapping:", script_text)
        self.assertNotIn("plannedProfile", script_text)

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
        self.assertIn("REVIEW_ESCALATION", script)
        self.assertIn("review_escalation_required", script)
        self.assertIn("review_escalation_failed", script)
        self.assertIn("review_escalation_unavailable", script)
        self.assertIn("canonical execution-profile registry", skill)
        self.assertIn("Do not auto-select an `xhigh` profile", skill)
        self.assertNotIn("`luna-high`, `sol-medium` →", skill)
        registry = (
            REPO_ROOT
            / "skills"
            / "task-model-planner"
            / "references"
            / "execution-profiles.md"
        ).read_text()
        self.assertIn(
            "`sonnet-medium`, `sonnet-high`, `opus-medium` → `opus-high`;",
            registry,
        )
        self.assertRegex(registry, r"`opus-high` →\s+`opus-max`\.")
        self.assertIn("'sonnet-medium': 'opus-high'", script)
        self.assertIn("'sonnet-high': 'opus-high'", script)
        recovery_map = script.split("const REVIEW_ESCALATION = {", 1)[1].split("}", 1)[0]
        self.assertNotRegex(recovery_map, r"xhigh")
        self.assertIn("'opus-medium': 'opus-high'", script)
        self.assertIn("'opus-high': 'opus-max'", script)


if __name__ == "__main__":
    unittest.main()
