"""Remove-link safety checks use in-memory clients only; no Azure or credentials."""
import copy
import io
import json
import sys
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "scripts"))

from fakes import FakeClient, PatchOp
from azure_devops_boards import AzureClient, ExistingItem, RELATIONS, parser, remove_link

ORG, PROJECT, ITEM, TARGET = "https://dev.azure.com/o", "P", 1257, 1254


def link(kind="predecessor", target=TARGET, org=ORG, project=PROJECT):
    return {"rel": RELATIONS[kind], "url": f"{org}/{project}/_apis/wit/workItems/{target}"}


class RemoveLinkTests(unittest.TestCase):
    def setUp(self):
        patcher = mock.patch("azure_devops_boards.sdk", side_effect=AssertionError("Real SDK forbidden"))
        patcher.start()
        self.addCleanup(patcher.stop)

    def args(self, apply=False, kind="predecessor", expected_rev=3):
        return SimpleNamespace(organization=ORG, project=PROJECT, id=ITEM,
                               target_id=TARGET, kind=kind, expected_rev=expected_rev, apply=apply)

    def seeded(self, kind="predecessor", **options):
        fake = FakeClient.with_item(ITEM, rev=3, **options)
        fake.items[ITEM]["relations"] = [link("related", 99), link(kind),
                                         link("parent", TARGET),
                                         {"rel": "System.LinkTypes.Dependency-Forward", "url": link()["url"]},
                                         {"rel": "ArtifactLink", "url": "vstfs:///Git/Commit/123"}]
        return fake

    def run_command(self, fake, args):
        with redirect_stdout(io.StringIO()) as output, \
                mock.patch("azure_devops_boards.connect", return_value=(fake, PatchOp)):
            remove_link(args)
        return json.loads(output.getvalue())

    def test_validate_only_preserves_entire_item(self):
        fake = self.seeded()
        before = copy.deepcopy(fake.items)
        result = self.run_command(fake, self.args())
        self.assertEqual(result, {"mode": "validated", "id": ITEM, "kind": "predecessor", "targetId": TARGET})
        self.assertEqual((fake.validate_calls, fake.applies), (1, 0))
        self.assertEqual(fake.items, before)

    def test_apply_deletes_only_the_exact_direction_and_preserves_other_data(self):
        for kind in RELATIONS:
            with self.subTest(kind=kind):
                fake = self.seeded(kind)
                # Keep just one exact match when the selected kind is parent.
                fake.items[ITEM]["relations"][2] = link("related", 88)
                fake.items[ITEM]["fields"].update({"System.Description": "keep", "System.State": "Active"})
                before = copy.deepcopy(fake.items[ITEM])
                result = self.run_command(fake, self.args(apply=True, kind=kind))
                expected = copy.deepcopy(before)
                expected["rev"] += 1
                del expected["relations"][1]
                self.assertEqual(fake.items[ITEM], expected)
                self.assertEqual(result, {"mode": "applied", "id": ITEM, "kind": kind, "targetId": TARGET})
                self.assertEqual((fake.validate_calls, fake.applies), (1, 1))

    def test_project_guid_relation_is_matched(self):
        fake = self.seeded()
        fake.items[ITEM]["relations"][1] = link(project="project-guid")
        self.run_command(fake, self.args(apply=True))
        self.assertEqual(len(fake.items[ITEM]["relations"]), 4)

    def test_missing_wrong_direction_and_other_organization_fail_without_writes(self):
        for relations in ([], [link("related")], [link(org="https://dev.azure.com/other")],
                          [{"rel": "System.LinkTypes.Dependency-Forward", "url": link()["url"]}],
                          [{"rel": RELATIONS["predecessor"], "url": "vstfs:///Git/Commit/1254"}]):
            for apply in (False, True):
                with self.subTest(relations=relations, apply=apply):
                    fake = self.seeded()
                    fake.items[ITEM]["relations"] = relations
                    before = copy.deepcopy(fake.items)
                    with self.assertRaisesRegex(RuntimeError, "No predecessor relation from work item 1257 to 1254"):
                        self.run_command(fake, self.args(apply=apply))
                    self.assertEqual((fake.validate_calls, fake.applies), (0, 0))
                    self.assertEqual(fake.items, before)

    def test_ambiguous_match_is_rejected(self):
        fake = self.seeded()
        fake.items[ITEM]["relations"].append(link(project="project-guid"))
        with self.assertRaisesRegex(RuntimeError, "Ambiguous predecessor relation.*2 matches"):
            self.run_command(fake, self.args(apply=True))
        self.assertEqual((fake.validate_calls, fake.applies), (0, 0))

    def test_stale_input_revision_is_rejected_before_validation(self):
        fake = self.seeded()
        with self.assertRaisesRegex(RuntimeError, "Revision mismatch.*expected 2, found 3"):
            self.run_command(fake, self.args(apply=True, expected_rev=2))
        self.assertEqual((fake.validate_calls, fake.applies), (0, 0))

    def test_revision_change_before_validation_is_not_retried(self):
        fake = self.seeded()
        validate = fake.validate
        def concurrent_validate(document, target):
            fake.items[ITEM]["rev"] += 1
            return validate(document, target)
        with mock.patch.object(fake, "validate", side_effect=concurrent_validate):
            with self.assertRaisesRegex(RuntimeError, "rev mismatch"):
                self.run_command(fake, self.args(apply=True))
        self.assertEqual((fake.validate_calls, fake.applies), (1, 0))
        self.assertEqual(len(fake.items[ITEM]["relations"]), 5)

    def test_revision_change_between_validate_and_apply_cannot_delete_shifted_index(self):
        fake = self.seeded()
        validate = fake.validate
        def concurrent_validate(document, target):
            projected = validate(document, target)
            fake.items[ITEM]["rev"] += 1
            fake.items[ITEM]["relations"].insert(0, link("related", 77))
            return projected
        with mock.patch.object(fake, "validate", side_effect=concurrent_validate):
            with self.assertRaisesRegex(RuntimeError, "rev mismatch"):
                self.run_command(fake, self.args(apply=True))
        self.assertEqual(fake.validate_calls, 1)
        self.assertEqual(len(fake.items[ITEM]["relations"]), 6)
        self.assertIn(link(), fake.items[ITEM]["relations"])

    def test_omitted_validation_relations_still_get_persisted_read_back(self):
        fake = self.seeded(echo_relations_on_validate=False)
        self.assertEqual(self.run_command(fake, self.args(apply=True))["mode"], "applied")
        self.assertNotIn(link(), fake.items[ITEM]["relations"])

    def test_unchanged_read_back_cannot_claim_applied_success(self):
        fake = self.seeded()
        with mock.patch.object(fake, "apply", return_value=ITEM):
            with self.assertRaisesRegex(RuntimeError, "Read-back failed.*removed relation"):
                self.run_command(fake, self.args(apply=True))

    def test_invalid_ids_or_revision_fail_before_connection(self):
        for option in ("id", "target_id", "expected_rev"):
            for invalid in (0, -1, None):
                with self.subTest(option=option, invalid=invalid):
                    args = self.args()
                    setattr(args, option, invalid)
                    with mock.patch("azure_devops_boards.connect") as connect:
                        with self.assertRaisesRegex(RuntimeError, "positive integer"):
                            remove_link(args)
                    connect.assert_not_called()

    def test_parser_requires_revision_and_accepts_only_work_item_targets(self):
        command = ["remove-link", "--organization", ORG, "--project", PROJECT,
                   "--id", str(ITEM), "--kind", "predecessor", "--target-id", str(TARGET)]
        with redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                parser().parse_args(command)
        args = parser().parse_args(command + ["--expected-rev", "3"])
        self.assertIs(args.run, remove_link)
        self.assertFalse(args.apply)
        for extra in (["--kind", "successor"], ["--kind", "ArtifactLink"],
                      ["--target-id", "https://example.com/1254"], ["--patch-file", "/tmp/patch.json"]):
            with self.subTest(extra=extra), redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit):
                    parser().parse_args(command + ["--expected-rev", "3"] + extra)

    def test_azure_transport_validates_then_applies_same_revision_bound_patch(self):
        for apply in (False, True):
            with self.subTest(apply=apply):
                state = self.seeded()
                api = mock.Mock()
                api._serialize.body.side_effect = lambda document, schema: document
                def send(**request):
                    item = state.read(ITEM) if request["http_method"] == "GET" else state.validate(
                        request["content"], ExistingItem(ITEM))
                    return SimpleNamespace(json=lambda: item)
                api._send.side_effect = send
                api.update_work_item.side_effect = lambda **request: state.apply(request["document"], ExistingItem(ITEM))
                with redirect_stdout(io.StringIO()) as output, mock.patch(
                        "azure_devops_boards.connect", return_value=(AzureClient(api, PROJECT), PatchOp)):
                    remove_link(self.args(apply=apply))
                self.assertEqual(json.loads(output.getvalue())["mode"], "applied" if apply else "validated")
                requests = [call.kwargs for call in api._send.call_args_list]
                self.assertEqual([request["http_method"] for request in requests], ["GET", "PATCH", "GET"] if apply else ["GET", "PATCH"])
                validation = requests[1]
                self.assertEqual(validation["route_values"], {"project": PROJECT, "id": ITEM})
                self.assertEqual(validation["location_id"], AzureClient.ITEM_ID)
                self.assertEqual(validation["query_parameters"], {"validateOnly": "true"})
                self.assertEqual(validation["media_type"], "application/json-patch+json")
                document = validation["content"]
                self.assertEqual([(o.op, o.path, o.value) for o in document], [("test", "/rev", 3), ("remove", "/relations/1", None)])
                if apply:
                    api.update_work_item.assert_called_once_with(document=document, id=ITEM, project=PROJECT, validate_only=False)
                else:
                    api.update_work_item.assert_not_called()


if __name__ == "__main__":
    unittest.main()
