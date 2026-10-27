"""Command-level tests: create / update / add_link wired through safe_mutate.

``connect`` is patched to inject the in-memory FakeClient, so the full command path
(patch construction → runner → emit) is exercised without Azure.
"""
import io
import json
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest import mock
import html

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))                     # tests/   → fakes
sys.path.insert(0, str(HERE.parent / "scripts"))  # scripts/ → azure_devops_boards

from fakes import FakeClient, PatchOp  # noqa: E402
from azure_devops_boards import RELATIONS, add_comment, add_link, close_task, create, parser, preflight, show_item, update  # noqa: E402

ORG, PROJECT = "https://dev.azure.com/o", "P"


def _file(text):
    """Stand-in for a --description-file / --comment-file Path."""
    return SimpleNamespace(read_text=lambda: text)


def _run(func, fake, args):
    with redirect_stdout(io.StringIO()) as buf, \
            mock.patch("azure_devops_boards.connect", return_value=(fake, PatchOp)):
        func(args)
    return json.loads(buf.getvalue())


class CreateCommandTests(unittest.TestCase):
    def test_parser_accepts_epic_and_feature(self):
        for item_type in ("Epic", "Feature"):
            args = parser().parse_args([
                "create", "--organization", ORG, "--project", PROJECT, "--team", "Team",
                "--type", item_type, "--title", "T", "--description-file", "/tmp/item.md",
            ])
            self.assertEqual(args.type, item_type)

    def test_update_parser_accepts_bug_field_files(self):
        args = parser().parse_args([
            "update", "--organization", ORG, "--project", PROJECT, "--id", "42",
            "--repro-steps-file", "/tmp/repro.md", "--system-info-file", "/tmp/system.md",
            "--acceptance-criteria-file", "/tmp/ac.md",
        ])
        self.assertEqual(str(args.repro_steps_file), "/tmp/repro.md")
        self.assertEqual(str(args.system_info_file), "/tmp/system.md")
        self.assertEqual(str(args.acceptance_criteria_file), "/tmp/ac.md")

    def _args(self, apply, text="body", iteration="Sprint 1"):
        return SimpleNamespace(organization=ORG, project=PROJECT, apply=apply, type="Task",
                               title="T", iteration=iteration, description_file=_file(text),
                               tags=[], parent=[], predecessor=[], related=[])

    def test_validated_mode_emits_without_writing(self):
        fake = FakeClient()
        out = _run(create, fake, self._args(apply=False))
        self.assertEqual(out, {"mode": "validated", "type": "Task", "title": "T", "iteration": "Sprint 1"})
        self.assertEqual(fake.applies, 0)

    def test_applied_mode_writes_and_assigns_id(self):
        fake = FakeClient()
        out = _run(create, fake, self._args(apply=True))
        self.assertEqual(out, {"mode": "applied", "id": 1000, "rev": 2})
        self.assertEqual(fake.applies, 1)

    def test_initial_comment_is_validated_or_persisted_with_creation(self):
        for apply in (False, True):
            with self.subTest(apply=apply):
                fake = FakeClient()
                args = self._args(apply=apply)
                args.comment_file = _file("initial context")
                out = _run(create, fake, args)
                self.assertEqual(out["mode"], "applied" if apply else "validated")
                self.assertEqual(fake.applies, int(apply))
                if apply:
                    self.assertEqual(out["commentId"], 1)
                    self.assertEqual(fake.comments[out["id"]][0]["text"], "initial context")
                else:
                    self.assertEqual(fake.comments, {})

    def test_initial_comment_failure_reports_created_item_without_claiming_success(self):
        for response in (RuntimeError("comment unavailable"), None,
                         {"format": "html", "text": "initial context"},
                         {"format": "markdown", "text": "wrong context"}):
            with self.subTest(response=response):
                fake = FakeClient()
                args = self._args(apply=True)
                args.comment_file = _file("initial context")
                failure = {"side_effect": response} if isinstance(response, Exception) else {"return_value": response}
                with redirect_stdout(io.StringIO()) as output, \
                        mock.patch("azure_devops_boards.connect", return_value=(fake, PatchOp)), \
                        mock.patch.object(fake, "add_comment", **failure):
                    with self.assertRaisesRegex(RuntimeError, "Work item 1000 was created"):
                        create(args)
                result = json.loads(output.getvalue())
                self.assertEqual((result["mode"], result["id"], result["rev"]), ("partial", 1000, 2))
                self.assertEqual(result["failedStep"], "add-comment")
                self.assertTrue(result["error"])
                self.assertEqual(fake.applies, 1)
                self.assertEqual(fake.read(result["id"])["fields"]["System.Title"], "T")

    def test_task_creation_writes_acceptance_criteria_separately(self):
        fake = FakeClient()
        args = self._args(apply=True)
        args.acceptance_criteria_file = _file("- [ ] Reject invalid input")
        out = _run(create, fake, args)
        stored = fake.read(out["id"])
        self.assertEqual(stored["fields"]["System.Description"], "body")
        self.assertEqual(stored["fields"]["Microsoft.VSTS.Common.AcceptanceCriteria"],
                         "- [ ] Reject invalid input")
        self.assertEqual(stored["multilineFieldsFormat"]["Microsoft.VSTS.Common.AcceptanceCriteria"],
                         "markdown")

    def test_bug_creation_persists_repro_steps_and_system_info_fields(self):
        fake = FakeClient()
        args = self._args(apply=True)
        args.type = "Bug"
        args.repro_steps_file = _file("## Reproduction\n\n1. Open the screen\n2. Observe the `crash`")
        args.system_info_file = _file("**iOS 18.5**\n\n- iPhone 15")
        args.acceptance_criteria_file = _file("- [ ] The crash no longer occurs")
        out = _run(create, fake, args)
        self.assertEqual(out["mode"], "applied")
        item = fake.read(out["id"])
        stored = item["fields"]
        self.assertEqual(stored["Microsoft.VSTS.TCM.ReproSteps"], "## Reproduction\n\n1. Open the screen\n2. Observe the `crash`")
        self.assertEqual(stored["Microsoft.VSTS.TCM.SystemInfo"], "**iOS 18.5**\n\n- iPhone 15")
        self.assertEqual(fake.read(out["id"])["multilineFieldsFormat"]["Microsoft.VSTS.TCM.ReproSteps"], "markdown")
        self.assertEqual(fake.read(out["id"])["multilineFieldsFormat"]["Microsoft.VSTS.TCM.SystemInfo"], "markdown")
        self.assertEqual(stored["Microsoft.VSTS.Common.AcceptanceCriteria"],
                         "- [ ] The crash no longer occurs")
        self.assertEqual(item["multilineFieldsFormat"]["Microsoft.VSTS.Common.AcceptanceCriteria"],
                         "markdown")

    def test_acceptance_criteria_input_rejects_other_work_item_types(self):
        args = self._args(apply=True)
        args.type = "Epic"
        args.acceptance_criteria_file = _file("- [ ] Criterion")
        with self.assertRaisesRegex(RuntimeError, "Acceptance Criteria requires --type Task or Bug"):
            _run(create, FakeClient(), args)

    def test_bug_creation_uses_initial_comment_as_repro_steps_when_field_is_absent(self):
        fake = FakeClient()
        args = self._args(apply=True)
        args.type = "Bug"
        args.comment_file = _file("## Reproduction\n\n1. Open the screen\n2. Observe the `crash`")
        out = _run(create, fake, args)
        stored = fake.read(out["id"])["fields"]
        self.assertEqual(stored["Microsoft.VSTS.TCM.ReproSteps"], "## Reproduction\n\n1. Open the screen\n2. Observe the `crash`")
        self.assertEqual(fake.read(out["id"])["multilineFieldsFormat"]["Microsoft.VSTS.TCM.ReproSteps"], "markdown")
        self.assertEqual(fake.comments, {})

    def test_bug_creation_keeps_initial_comment_when_repro_steps_are_explicit(self):
        fake = FakeClient()
        args = self._args(apply=True)
        args.type = "Bug"
        args.repro_steps_file = _file("native repro steps")
        args.comment_file = _file("additional triage context")
        out = _run(create, fake, args)
        stored = fake.read(out["id"])["fields"]
        self.assertEqual(stored["Microsoft.VSTS.TCM.ReproSteps"], "native repro steps")
        self.assertEqual(fake.read(out["id"])["multilineFieldsFormat"]["Microsoft.VSTS.TCM.ReproSteps"], "markdown")
        self.assertEqual(fake.comments[out["id"]][0]["text"], "additional triage context")

    def test_bug_creation_preserves_markdown_extensions(self):
        fake = FakeClient()
        args = self._args(apply=True)
        args.type = "Bug"
        markdown = "![diagram](https://example.com/a.png)\n\n|a|b|\n|-|-|\n|1|2|"
        args.repro_steps_file = _file(markdown)
        out = _run(create, fake, args)
        self.assertEqual(fake.read(out["id"])["fields"]["Microsoft.VSTS.TCM.ReproSteps"], markdown)
        self.assertEqual(fake.read(out["id"])["multilineFieldsFormat"]["Microsoft.VSTS.TCM.ReproSteps"], "markdown")


class UpdateCommandTests(unittest.TestCase):
    def _args(self, apply, state="Active", iteration=None, description_file=None,
              repro_steps_file=None, system_info_file=None, acceptance_criteria_file=None):
        return SimpleNamespace(organization=ORG, project=PROJECT, apply=apply, id=42,
                               state=state, iteration=iteration, description_file=description_file,
                               repro_steps_file=repro_steps_file, system_info_file=system_info_file,
                               acceptance_criteria_file=acceptance_criteria_file)

    def _seeded(self):
        return FakeClient.with_item(42, rev=3)

    def test_validated_mode_emits_without_writing(self):
        fake = self._seeded()
        out = _run(update, fake, self._args(apply=False))
        self.assertEqual(out, {"mode": "validated", "id": 42, "fields": {"System.State": "Active"}})
        self.assertEqual(fake.applies, 0)

    def test_applied_mode_writes_and_bumps_rev(self):
        fake = self._seeded()
        out = _run(update, fake, self._args(apply=True))
        self.assertEqual(out, {"mode": "applied", "id": 42, "rev": 4, "fields": {"System.State": "Active"}})
        self.assertEqual(fake.applies, 1)

    def test_matching_expected_revision_guards_validation_and_apply(self):
        for apply in (False, True):
            with self.subTest(apply=apply):
                fake = self._seeded()
                args = parser().parse_args([
                    "update", "--organization", ORG, "--project", PROJECT,
                    "--id", "42", "--expected-rev", "3",
                    "--description-file", "/tmp/reviewed.md",
                ] + (["--apply"] if apply else []))
                args.description_file = _file("Reviewed body")
                with mock.patch.object(fake, "validate", wraps=fake.validate) as validate, \
                        mock.patch.object(fake, "apply", wraps=fake.apply) as persist:
                    out = _run(update, fake, args)
                self.assertEqual(out["mode"], "applied" if apply else "validated")
                for call in validate.call_args_list + persist.call_args_list:
                    guard = call.args[0][0]
                    self.assertEqual((guard.op, guard.path, guard.value), ("test", "/rev", 3))
                self.assertEqual(fake.validate_calls, 1)
                self.assertEqual(fake.applies, int(apply))
                stored = fake.read(42)
                self.assertEqual(stored["rev"], 4 if apply else 3)
                self.assertEqual(stored["fields"].get("System.Description"),
                                 "Reviewed body" if apply else None)

    def test_stale_expected_revision_stops_before_validation_or_write(self):
        for apply in (False, True):
            for revision in (2, 4):
                with self.subTest(apply=apply, revision=revision):
                    fake = self._seeded()
                    before = fake.read(42)
                    args = self._args(apply=apply, description_file=_file("Stale body"))
                    args.expected_rev = revision
                    with self.assertRaisesRegex(RuntimeError, "Revision mismatch"):
                        _run(update, fake, args)
                    self.assertEqual(fake.validate_calls, 0)
                    self.assertEqual(fake.applies, 0)
                    self.assertEqual(fake.read(42), before)

    def test_nonpositive_expected_revision_is_rejected_before_connect(self):
        for revision in (0, -1):
            with self.subTest(revision=revision):
                args = parser().parse_args([
                    "update", "--organization", ORG, "--project", PROJECT,
                    "--id", "42", "--state", "Active",
                    "--expected-rev", str(revision), "--apply",
                ])
                with mock.patch("azure_devops_boards.connect") as connect:
                    with self.assertRaisesRegex(RuntimeError, "positive integer"):
                        update(args)
                connect.assert_not_called()

    def test_no_field_to_update_raises(self):
        with self.assertRaises(RuntimeError) as cm:
            _run(update, self._seeded(), self._args(apply=True, state=None))
        self.assertIn("Specify a field to update.", str(cm.exception))

    def test_description_round_trips(self):
        fake = self._seeded()
        out = _run(update, fake, self._args(apply=True, state=None, description_file=_file("a && b")))
        self.assertEqual(out["mode"], "applied")
        self.assertEqual(fake.applies, 1)

    def test_bug_fields_update_as_markdown(self):
        fake = FakeClient.with_item(42, rev=3, item_type="Bug")
        out = _run(update, fake, self._args(
            apply=True,
            state=None,
            repro_steps_file=_file("## Reproduction\n\n1. Retry"),
            system_info_file=_file("- macOS"),
            acceptance_criteria_file=_file("- [ ] Fix the crash"),
        ))
        self.assertEqual(out["mode"], "applied")
        stored = fake.read(42)["fields"]
        self.assertEqual(stored["Microsoft.VSTS.TCM.ReproSteps"],
                         "## Reproduction\n\n1. Retry")
        self.assertEqual(stored["Microsoft.VSTS.TCM.SystemInfo"],
                         "- macOS")
        self.assertEqual(stored["Microsoft.VSTS.Common.AcceptanceCriteria"],
                         "- [ ] Fix the crash")
        formats = fake.read(42)["multilineFieldsFormat"]
        self.assertEqual(formats["Microsoft.VSTS.TCM.ReproSteps"], "markdown")
        self.assertEqual(formats["Microsoft.VSTS.TCM.SystemInfo"], "markdown")
        self.assertEqual(formats["Microsoft.VSTS.Common.AcceptanceCriteria"], "markdown")

    def test_task_acceptance_criteria_updates_its_native_field(self):
        fake = self._seeded()
        out = _run(update, fake, self._args(
            apply=True, state=None,
            acceptance_criteria_file=_file("- [ ] Handle empty input"),
        ))
        stored = fake.read(42)
        self.assertEqual(out["fields"]["Microsoft.VSTS.Common.AcceptanceCriteria"],
                         "- [ ] Handle empty input")
        self.assertNotIn("System.Description", stored["fields"])
        self.assertEqual(stored["fields"]["Microsoft.VSTS.Common.AcceptanceCriteria"],
                         "- [ ] Handle empty input")
        self.assertEqual(stored["multilineFieldsFormat"]["Microsoft.VSTS.Common.AcceptanceCriteria"],
                         "markdown")

    def test_acceptance_criteria_update_rejects_other_work_item_types(self):
        fake = FakeClient.with_item(42, item_type="User Story")
        with self.assertRaisesRegex(RuntimeError, "Acceptance Criteria requires a Task or Bug"):
            _run(update, fake, self._args(
                apply=True, state=None,
                acceptance_criteria_file=_file("- [ ] Criterion"),
            ))

    def test_bug_field_format_mismatch_at_validation_prevents_apply(self):
        class MissingBugFormat(FakeClient):
            def validate(self, document, target):
                item = super().validate(document, target)
                item["multilineFieldsFormat"].pop("Microsoft.VSTS.TCM.ReproSteps", None)
                return item

        fake = MissingBugFormat.with_item(42, rev=3, item_type="Bug")
        with self.assertRaises(RuntimeError) as cm:
            _run(update, fake, self._args(
                apply=True, state=None, repro_steps_file=_file("## Reproduction"),
            ))
        self.assertIn("Validation failed for Microsoft.VSTS.TCM.ReproSteps format", str(cm.exception))
        self.assertEqual(fake.applies, 0)

    def test_non_bug_rejects_bug_field_updates(self):
        with self.assertRaises(RuntimeError) as cm:
            _run(update, self._seeded(), self._args(
                apply=True, state=None, repro_steps_file=_file("1. Retry"),
            ))
        self.assertEqual(str(cm.exception), "Bug-specific fields require a Bug work item.")


class AddLinkCommandTests(unittest.TestCase):
    ID, KIND, TARGET = 42, "predecessor", 7

    def _relation_value(self):
        return {"rel": RELATIONS[self.KIND],
                "url": f"{ORG}/{PROJECT}/_apis/wit/workItems/{self.TARGET}"}

    def _args(self, apply):
        return SimpleNamespace(organization=ORG, project=PROJECT, id=self.ID,
                               kind=self.KIND, target_id=self.TARGET, apply=apply)

    def _seeded(self):
        return FakeClient.with_item(self.ID, rev=3)

    def test_unchanged_when_relation_already_present(self):
        fake = self._seeded()
        fake.items[self.ID]["relations"] = [self._relation_value()]
        out = _run(add_link, fake, self._args(apply=True))
        self.assertEqual(out, {"mode": "unchanged", "id": self.ID})
        self.assertEqual(fake.applies, 0)

    def test_validated_mode_emits_without_writing(self):
        fake = self._seeded()
        out = _run(add_link, fake, self._args(apply=False))
        self.assertEqual(out, {"mode": "validated", "id": self.ID, "kind": self.KIND, "targetId": self.TARGET})
        self.assertEqual(fake.applies, 0)

    def test_applied_mode_reads_back_relation_when_validation_omits_it(self):
        fake = FakeClient.with_item(self.ID, rev=3, echo_relations_on_validate=False)
        out = _run(add_link, fake, self._args(apply=True))
        self.assertEqual(out, {"mode": "applied", "id": self.ID, "kind": self.KIND, "targetId": self.TARGET})
        self.assertEqual(fake.applies, 1)
        self.assertTrue(any(r["url"] == self._relation_value()["url"] for r in fake.read(self.ID)["relations"]))

    def test_applied_mode_writes_and_emits(self):
        fake = self._seeded()
        out = _run(add_link, fake, self._args(apply=True))
        self.assertEqual(out, {"mode": "applied", "id": self.ID, "kind": self.KIND, "targetId": self.TARGET})
        self.assertEqual(fake.applies, 1)
        rel = self._relation_value()
        stored = fake.read(self.ID)
        self.assertTrue(any(r["rel"] == rel["rel"] and r["url"] == rel["url"] for r in stored["relations"]))

    def test_applied_mode_accepts_project_guid_in_read_back_relation_url(self):
        class ProjectGuidRead(FakeClient):
            def read(self, item_id):
                item = super().read(item_id)
                for stored in item["relations"]:
                    stored["url"] = stored["url"].replace(f"/{PROJECT}/", "/project-guid/")
                return item

        fake = ProjectGuidRead.with_item(self.ID, rev=3)
        out = _run(add_link, fake, self._args(apply=True))
        self.assertEqual(out, {"mode": "applied", "id": self.ID, "kind": self.KIND, "targetId": self.TARGET})
        self.assertEqual(fake.applies, 1)

    def test_existing_project_guid_relation_is_unchanged(self):
        fake = self._seeded()
        stored = self._relation_value()
        stored["url"] = stored["url"].replace(f"/{PROJECT}/", "/project-guid/")
        fake.items[self.ID]["relations"] = [stored]
        out = _run(add_link, fake, self._args(apply=True))
        self.assertEqual(out, {"mode": "unchanged", "id": self.ID})
        self.assertEqual(fake.applies, 0)

    def test_different_organization_relation_with_same_id_is_not_treated_as_unchanged(self):
        fake = self._seeded()
        stored = self._relation_value()
        stored["url"] = stored["url"].replace(f"{ORG}/", "https://dev.azure.com/other-org/")
        fake.items[self.ID]["relations"] = [stored]
        out = _run(add_link, fake, self._args(apply=True))
        self.assertNotEqual(out, {"mode": "unchanged", "id": self.ID})
        self.assertEqual(out, {"mode": "applied", "id": self.ID, "kind": self.KIND, "targetId": self.TARGET})
        self.assertEqual(fake.applies, 1)


class AddCommentCommandTests(unittest.TestCase):
    ID = 42

    def _args(self, apply, text="body"):
        return SimpleNamespace(organization=ORG, project=PROJECT, id=self.ID,
                               apply=apply, comment_file=_file(text))

    def test_validated_mode_emits_without_posting(self):
        fake = FakeClient()
        out = _run(add_comment, fake, self._args(apply=False))
        self.assertEqual(out, {"mode": "validated", "id": self.ID, "format": "markdown", "length": 4})
        self.assertEqual(fake.comments, {})

    def test_applied_mode_posts_and_round_trips(self):
        fake = FakeClient()
        out = _run(add_comment, fake, self._args(apply=True, text="see `a && b < c`"))
        self.assertEqual(out, {"mode": "applied", "id": self.ID, "commentId": 1})
        self.assertEqual(len(fake.comments[self.ID]), 1)

    def test_empty_comment_raises(self):
        with self.assertRaises(RuntimeError) as cm:
            _run(add_comment, FakeClient(), self._args(apply=True, text="   "))
        self.assertIn("Comment must not be empty.", str(cm.exception))


class ImplementationLifecycleTests(unittest.TestCase):
    ID = 42

    def _seeded(self):
        fake = FakeClient.with_item(self.ID, rev=3)
        fake.items[self.ID]["fields"].update({
            "System.Title": "Implement compact Boards flow",
            "System.State": "New",
            "System.Description": "Implementation context",
            "Microsoft.VSTS.Common.AcceptanceCriteria": "- [ ] Keep scope\n- [x] Preserve safety",
        })
        fake.items[self.ID]["relations"] = [{"rel": RELATIONS["predecessor"], "url": f"{ORG}/{PROJECT}/_apis/wit/workItems/7"}]
        return fake

    def test_preflight_emits_compact_scope_and_relation_summary(self):
        out = _run(preflight, self._seeded(), SimpleNamespace(organization=ORG, project=PROJECT, id=self.ID))
        self.assertEqual(out["id"], self.ID)
        self.assertEqual(out["rev"], 3)
        self.assertEqual(out["scope"], {
            "source": "acceptance-criteria-field",
            "acceptanceCriteria": "- [ ] Keep scope\n- [x] Preserve safety",
            "description": "Implementation context",
        })
        self.assertEqual(out["relations"], [{"rel": RELATIONS["predecessor"], "targetId": 7}])

    def test_description_checklist_is_not_misreported_as_acceptance_criteria(self):
        fake = self._seeded()
        fields = fake.items[self.ID]["fields"]
        fields["System.Description"] = "- [ ] Keep this descriptive checklist"
        fields.pop("Microsoft.VSTS.Common.AcceptanceCriteria")
        out = _run(preflight, fake, SimpleNamespace(organization=ORG, project=PROJECT, id=self.ID))
        self.assertEqual(out["scope"], {
            "source": "description-fallback",
            "description": "- [ ] Keep this descriptive checklist",
        })

    def _close_args(self, apply, expected_rev=3, state="Closed"):
        return SimpleNamespace(organization=ORG, project=PROJECT, id=self.ID, apply=apply,
                               expected_rev=expected_rev, state=state, description_file=None,
                               check_ac=None, comment_file=_file("## Completion\nDone"))

    def test_close_task_validates_without_writing(self):
        fake = self._seeded()
        out = _run(close_task, fake, self._close_args(apply=False))
        self.assertEqual(out["mode"], "validated")
        self.assertEqual(fake.applies, 0)
        self.assertEqual(fake.comments, {})

    def test_close_task_applies_one_mutation_and_one_markdown_comment(self):
        fake = self._seeded()
        out = _run(close_task, fake, self._close_args(apply=True))
        self.assertEqual(out, {"mode": "applied", "id": self.ID, "rev": 4,
                               "fields": {"System.State": "Closed"}, "commentId": 1})
        self.assertEqual(fake.applies, 1)
        self.assertEqual(len(fake.comments[self.ID]), 1)

    def test_close_task_unreconcilable_revision_prevents_patch_and_comment(self):
        # Any rev mismatch — the expected rev no longer matches the live rev,
        # whether behind or ahead — surfaces immediately; there is no retry.
        fake = self._seeded()
        with self.assertRaises(RuntimeError):
            _run(close_task, fake, self._close_args(apply=True, expected_rev=5))
        self.assertEqual(fake.applies, 0)
        self.assertEqual(fake.comments, {})

    def test_close_task_comment_only_does_not_send_an_empty_work_item_patch(self):
        fake = self._seeded()
        out = _run(close_task, fake, self._close_args(apply=True, state=None))
        self.assertEqual(out["rev"], None)
        self.assertEqual(fake.applies, 0)
        self.assertEqual(len(fake.comments[self.ID]), 1)


class CloseTaskCheckAcTests(unittest.TestCase):
    ID = 42

    def _seeded(self):
        fake = FakeClient.with_item(self.ID, rev=3)
        fake.items[self.ID]["fields"].update({
            "System.Title": "T", "System.State": "Active",
            "System.Description": "Keep this Description unchanged.",
            "Microsoft.VSTS.Common.AcceptanceCriteria": "- [ ] Write tests\n- [ ] Ship it\n- [x] Hold scope",
        })
        return fake

    def _seeded_without_description_projection(self):
        fake = FakeClient.with_item(
            self.ID, rev=3, echo_description_on_existing_validate=False,
        )
        fake.items[self.ID]["fields"].update({
            "System.Title": "T", "System.State": "Active",
            "System.Description": "Keep this Description unchanged.",
            "Microsoft.VSTS.Common.AcceptanceCriteria": "- [ ] Write tests\n- [ ] Ship it\n- [x] Hold scope",
        })
        return fake

    def _args(self, apply, check_ac, expected_rev=3, state="Closed"):
        return SimpleNamespace(organization=ORG, project=PROJECT, id=self.ID, apply=apply,
                               expected_rev=expected_rev, state=state,
                               description_file=None, acceptance_criteria_file=None, check_ac=check_ac,
                               comment_file=_file("## Completion\nDone"))

    def _description(self, fake):
        return html.unescape(fake.read(self.ID)["fields"]["System.Description"])

    def _acceptance_criteria(self, fake):
        return html.unescape(fake.read(self.ID)["fields"]["Microsoft.VSTS.Common.AcceptanceCriteria"])

    def test_check_ac_all_checks_incomplete_and_preserves_already_checked(self):
        fake = self._seeded()
        out = _run(close_task, fake, self._args(apply=True, check_ac="all"))
        self.assertEqual(out["mode"], "applied")
        self.assertEqual(self._acceptance_criteria(fake), "- [x] Write tests\n- [x] Ship it\n- [x] Hold scope")
        self.assertEqual(self._description(fake), "Keep this Description unchanged.")

    def test_close_task_applies_when_validation_omits_description_projection(self):
        fake = self._seeded_without_description_projection()
        out = _run(close_task, fake, self._args(apply=True, check_ac="all"))
        self.assertEqual(out, {"mode": "applied", "id": self.ID, "rev": 4,
                               "fields": {
                                   "Microsoft.VSTS.Common.AcceptanceCriteria": "- [x] Write tests\n- [x] Ship it\n- [x] Hold scope",
                                   "System.State": "Closed",
                               }, "commentId": 1})
        self.assertEqual(fake.validate_calls, 1)
        self.assertEqual(fake.applies, 1)
        stored = fake.read(self.ID)
        self.assertEqual(html.unescape(stored["fields"]["Microsoft.VSTS.Common.AcceptanceCriteria"]),
                         "- [x] Write tests\n- [x] Ship it\n- [x] Hold scope")
        self.assertEqual(stored["fields"]["System.Description"], "Keep this Description unchanged.")
        self.assertEqual(stored["multilineFieldsFormat"]["Microsoft.VSTS.Common.AcceptanceCriteria"], "markdown")
        self.assertEqual(len(fake.comments[self.ID]), 1)

    def test_stale_revision_with_omitted_description_prevents_patch_and_comment(self):
        fake = self._seeded_without_description_projection()
        with self.assertRaises(RuntimeError):
            _run(close_task, fake, self._args(apply=True, check_ac="all", expected_rev=2))
        self.assertEqual(fake.validate_calls, 1)
        self.assertEqual(fake.applies, 0)
        self.assertEqual(fake.comments, {})

    def test_check_ac_fragment_checks_single_match_case_insensitively(self):
        fake = self._seeded()
        _run(close_task, fake, self._args(apply=True, check_ac="WRITE"))
        self.assertEqual(self._acceptance_criteria(fake), "- [x] Write tests\n- [ ] Ship it\n- [x] Hold scope")
        self.assertEqual(self._description(fake), "Keep this Description unchanged.")

    def test_check_ac_all_is_idempotent_across_repeated_runs(self):
        fake = self._seeded()
        first = _run(close_task, fake, self._args(apply=True, check_ac="all", expected_rev=None))
        self.assertEqual(first["mode"], "applied")
        after_first = self._acceptance_criteria(fake)
        second = _run(close_task, fake, self._args(apply=True, check_ac="all", expected_rev=None))
        self.assertEqual(second["mode"], "applied")
        self.assertEqual(self._acceptance_criteria(fake), after_first)

    def test_check_ac_without_expected_rev_reuses_single_read_for_rev(self):
        class CountingReads(FakeClient):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.read_calls = 0

            def read(self, item_id):
                self.read_calls += 1
                return super().read(item_id)

        fake = CountingReads.with_item(self.ID, rev=3)
        fake.items[self.ID]["fields"].update({
            "System.Title": "T", "System.State": "Active",
            "System.Description": "Keep this Description unchanged.",
            "Microsoft.VSTS.Common.AcceptanceCriteria": "- [ ] Write tests\n- [ ] Ship it\n- [x] Hold scope",
        })
        out = _run(close_task, fake, self._args(apply=True, check_ac="all", expected_rev=None))
        self.assertEqual(out["mode"], "applied")
        # One read fetches Acceptance Criteria (and its rev) for --check-ac; one
        # read-back inside safe_mutate confirms the persisted result. No
        # separate read solely to fetch a fresh rev — that would reintroduce a
        # gap between two inconsistent reads (the criteria from the first,
        # the rev from the second) that a concurrent edit could land in.
        self.assertEqual(fake.read_calls, 2)
        self.assertEqual(self._acceptance_criteria(fake), "- [x] Write tests\n- [x] Ship it\n- [x] Hold scope")
        self.assertEqual(self._description(fake), "Keep this Description unchanged.")

    def test_check_ac_no_match_raises_without_writing(self):
        fake = self._seeded()
        with self.assertRaises(RuntimeError) as cm:
            _run(close_task, fake, self._args(apply=True, check_ac="nonexistent"))
        self.assertIn("No acceptance criteria matched", str(cm.exception))
        self.assertEqual(fake.applies, 0)
        self.assertEqual(fake.comments, {})

    def test_check_ac_ambiguous_fragment_raises(self):
        fake = FakeClient.with_item(self.ID, rev=3)
        fake.items[self.ID]["fields"].update({
            "System.Title": "T", "System.State": "Active",
            "System.Description": "Keep this Description unchanged.",
            "Microsoft.VSTS.Common.AcceptanceCriteria": "- [ ] Write unit tests\n- [ ] Write integration tests\n- [x] Hold scope",
        })
        with self.assertRaises(RuntimeError) as cm:
            _run(close_task, fake, self._args(apply=True, check_ac="write"))
        self.assertIn("Write unit tests", str(cm.exception))
        self.assertIn("Write integration tests", str(cm.exception))
        self.assertEqual(fake.applies, 0)
        self.assertEqual(fake.comments, {})

    def test_check_ac_can_close_while_preserving_a_separate_description(self):
        args = parser().parse_args(["close-task", "--organization", ORG, "--project", PROJECT,
                                    "--id", "42", "--check-ac", "all", "--description-file", "/tmp/x.md",
                                    "--comment-file", "/tmp/c.md"])
        self.assertEqual(str(args.description_file), "/tmp/x.md")

    def test_parser_rejects_two_acceptance_criteria_inputs(self):
        with self.assertRaises(SystemExit):
            parser().parse_args(["close-task", "--organization", ORG, "--project", PROJECT,
                                 "--id", "42", "--check-ac", "all", "--acceptance-criteria-file", "/tmp/ac.md",
                                 "--comment-file", "/tmp/c.md"])

    def test_close_task_updates_description_and_acceptance_criteria_separately(self):
        fake = self._seeded()
        args = self._args(apply=True, check_ac=None)
        args.description_file = _file("A revised implementation summary.")
        args.acceptance_criteria_file = _file("- [x] Write tests\n- [ ] Ship it\n- [x] Hold scope")
        out = _run(close_task, fake, args)
        self.assertEqual(out["fields"]["Microsoft.VSTS.Common.AcceptanceCriteria"],
                         "- [x] Write tests\n- [ ] Ship it\n- [x] Hold scope")
        self.assertEqual(self._description(fake), "A revised implementation summary.")
        self.assertEqual(self._acceptance_criteria(fake),
                         "- [x] Write tests\n- [ ] Ship it\n- [x] Hold scope")

    def test_close_task_rejects_acceptance_criteria_for_other_item_types(self):
        fake = FakeClient.with_item(self.ID, item_type="User Story")
        args = self._args(apply=True, check_ac=None)
        args.acceptance_criteria_file = _file("- [x] Criterion")
        with self.assertRaisesRegex(RuntimeError, "Acceptance Criteria requires a Task or Bug"):
            _run(close_task, fake, args)
        self.assertEqual(fake.applies, 0)
        self.assertEqual(fake.comments, {})

    def test_file_based_closeout_requires_source_revision_before_connecting(self):
        for option in ("description_file", "acceptance_criteria_file"):
            with self.subTest(option=option), mock.patch("azure_devops_boards.connect") as connect:
                args = self._args(apply=True, check_ac=None, expected_rev=None)
                setattr(args, option, _file("Replacement text"))
                with self.assertRaisesRegex(RuntimeError, "requires --expected-rev"):
                    close_task(args)
                connect.assert_not_called()


class ShowFullTests(unittest.TestCase):
    def test_show_default_emits_compact_summary(self):
        fake = FakeClient.with_item(42, rev=3)
        fake.items[42]["fields"].update({"System.Title": "T", "System.State": "Active"})
        out = _run_with_func(show_item, fake, SimpleNamespace(organization=ORG, project=PROJECT, id=42, full=False))
        self.assertEqual(out, {"id": 42, "rev": 3, "type": "Task", "state": "Active", "title": "T", "relations": []})
        self.assertNotIn("fields", out)

    def test_show_full_emits_full_item(self):
        fake = FakeClient.with_item(42, rev=3)
        fake.items[42]["fields"].update({"System.Title": "T", "System.State": "Active"})
        out = _run_with_func(show_item, fake, SimpleNamespace(organization=ORG, project=PROJECT, id=42, full=True))
        self.assertEqual(out["id"], 42)
        self.assertEqual(out["rev"], 3)
        self.assertIn("fields", out)


def _run_with_func(func, fake, args):
    with redirect_stdout(io.StringIO()) as buf, \
            mock.patch("azure_devops_boards.connect", return_value=(fake, PatchOp)):
        func(args)
    return json.loads(buf.getvalue())


if __name__ == "__main__":
    unittest.main()
