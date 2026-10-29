"""Offline regressions for move's relation preservation boundary."""
import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from azure_devops_boards import _assert_move_preserved, _move_relations

ORG = "https://dev.azure.com/o"
URL = ORG + "/source-guid/_apis/wit/workItems/41"


class MoveRelationTests(unittest.TestCase):
    def setUp(self):
        self.before = {
            "fields": {"System.Title": "Keep title", "System.State": "New"},
            "relations": [
                {"rel": "System.LinkTypes.Hierarchy-Forward", "url": URL,
                 "attributes": {"name": "Child", "comment": "Keep comment"}},
                {"rel": "ArtifactLink", "url": "vstfs:///Git/Commit/project%2frepo%2fcommit",
                 "attributes": {"id": 1, "authorizedDate": "old", "name": "Fixed in Commit",
                                "resourceCreatedDate": "created", "resourceModifiedDate": "modified",
                                "revisedDate": "9999"}},
            ],
        }
        self.after = copy.deepcopy(self.before)

    def assertRejected(self):
        with self.assertRaisesRegex(RuntimeError, "changed native relations"):
            _assert_move_preserved(self.before, self.after, ORG)

    def test_reordering_and_artifact_server_metadata_can_change_together(self):
        self.after["relations"][1]["attributes"].update(id=9, authorizedDate="new")
        self.after["relations"].reverse()
        _assert_move_preserved(self.before, self.after, ORG)

    def test_same_work_item_in_verified_organization_can_change_project(self):
        self.after["relations"][0]["url"] = URL.replace("source-guid", "target-guid")
        _assert_move_preserved(self.before, self.after, ORG + "/")

    def test_missing_added_or_duplicate_relations_are_rejected(self):
        for relations in (self.after["relations"][:1],
                          self.after["relations"] + [self.after["relations"][0]]):
            with self.subTest(relations=relations):
                self.after["relations"] = relations
                self.assertRejected()
        self.before["relations"].append(copy.deepcopy(self.before["relations"][0]))
        self.after = copy.deepcopy(self.before)
        self.after["relations"][2] = copy.deepcopy(self.before["relations"][1])
        self.assertRejected()  # Same total and same distinct targets, different multiplicities.

    def test_changed_target_host_organization_and_url_suffix_are_rejected(self):
        for url in (URL.replace("/41", "/42"),
                    URL.replace("dev.azure.com", "other.example.com"),
                    URL.replace("/o/", "/other-org/"),
                    URL + "?changed=1", URL + "/", URL + "#fragment"):
            with self.subTest(url=url):
                self.after["relations"][0]["url"] = url
                self.assertRejected()

    def test_project_normalization_does_not_apply_to_unverified_organization(self):
        self.before["relations"][0]["url"] = URL.replace("/o/", "/other-org/")
        self.after = copy.deepcopy(self.before)
        self.after["relations"][0]["url"] = self.after["relations"][0]["url"].replace("source-guid", "target-guid")
        self.assertRejected()

    def test_relation_type_and_direction_are_preserved(self):
        for rel in ("System.LinkTypes.Hierarchy-Reverse", "System.LinkTypes.Related"):
            with self.subTest(rel=rel):
                self.after["relations"][0]["rel"] = rel
                self.assertRejected()

    def test_artifact_url_is_exact_even_if_it_looks_like_a_work_item_url(self):
        for url in (self.before["relations"][1]["url"], URL):
            with self.subTest(url=url):
                self.before["relations"][1]["url"] = url
                self.after = copy.deepcopy(self.before)
                self.after["relations"][1]["url"] = url.replace("project", "other").replace("source-guid", "target-guid")
                self.assertRejected()

    def test_all_other_attributes_and_relation_metadata_are_preserved(self):
        for index, key in ((0, "name"), (0, "comment"), (0, "id"), (0, "authorizedDate"),
                           (1, "name"), (1, "comment"), (1, "resourceCreatedDate"),
                           (1, "resourceModifiedDate"), (1, "revisedDate"), (1, "unknown")):
            with self.subTest(index=index, key=key):
                self.after = copy.deepcopy(self.before)
                self.after["relations"][index]["attributes"][key] = "changed"
                self.assertRejected()
        self.after = copy.deepcopy(self.before)
        self.after["relations"][0]["unknown"] = "changed"
        self.assertRejected()

    def test_fields_and_markdown_checks_are_still_enforced(self):
        self.after["fields"]["System.State"] = "Active"
        with self.assertRaisesRegex(RuntimeError, "changed fields"):
            _assert_move_preserved(self.before, self.after, ORG)
        self.after = copy.deepcopy(self.before)
        self.after["multilineFieldsFormat"] = {"System.Description": "html"}
        with self.assertRaisesRegex(RuntimeError, "changed multiline"):
            _assert_move_preserved(self.before, self.after, ORG)

    def test_comparison_does_not_mutate_snapshots(self):
        original = copy.deepcopy(self.before)
        _move_relations(self.before, ORG)
        self.assertEqual(self.before, original)


if __name__ == "__main__":
    unittest.main()
