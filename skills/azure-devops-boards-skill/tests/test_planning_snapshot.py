"""Read-only planning-snapshot and type-neutral preflight contracts."""
import io
import json
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest import mock


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "scripts"))

from fakes import FakeClient, PatchOp  # noqa: E402
from azure_devops_boards import AzureClient, parser, planning_snapshot, preflight  # noqa: E402


ORG, PROJECT = "https://dev.azure.com/o", "P"


def _run(func, fake, args):
    with redirect_stdout(io.StringIO()) as buf, \
            mock.patch("azure_devops_boards.connect", return_value=(fake, PatchOp)):
        func(args)
    return json.loads(buf.getvalue())


class PlanningSnapshotTests(unittest.TestCase):
    STORY, NEW_TASK, ACTIVE_TASK, NEW_BUG = 1, 2, 3, 4

    def _seeded(self):
        story = FakeClient.with_item(self.STORY, rev=7, item_type="User Story")
        story.items[self.STORY]["fields"].update({
            "System.Title": "Deliver planning snapshot",
            "System.State": "New",
            "System.Description": "Story authority",
        })
        for item_id, item_type, state in (
            (self.NEW_TASK, "Task", "New"),
            (self.ACTIVE_TASK, "Task", "Active"),
            (self.NEW_BUG, "Bug", "New"),
        ):
            item = FakeClient.blank(item_type)
            item["id"] = item_id
            item["fields"].update({"System.Title": f"{item_type} {item_id}", "System.State": state})
            story.items[item_id] = item
        story.items[self.NEW_TASK]["fields"]["System.Description"] = "- [ ] Implement snapshot"
        story.items[self.NEW_BUG]["fields"].update({
            "Microsoft.VSTS.TCM.ReproSteps": "Open planning then observe missing scope",
            "Microsoft.VSTS.TCM.SystemInfo": "iOS 18",
        })
        story.items[self.STORY]["relations"] = [
            {"rel": "System.LinkTypes.Hierarchy-Forward", "url": f"{ORG}/{PROJECT}/_apis/wit/workItems/{item_id}"}
            for item_id in (self.NEW_TASK, self.ACTIVE_TASK, self.NEW_BUG)
        ]
        story.items[self.NEW_BUG]["relations"] = [
            {"rel": "System.LinkTypes.Dependency-Reverse", "url": f"{ORG}/{PROJECT}/_apis/wit/workItems/{self.ACTIVE_TASK}"},
            {"rel": "AttachedFile", "url": "https://storage.example/spec.md", "attributes": {"name": "spec.md"}},
            {"rel": "Hyperlink", "url": "https://docs.example/spec"},
        ]
        story.comments[self.NEW_BUG] = [{"id": 8, "format": "markdown", "text": "Reproduces in production."}]
        return story

    def test_snapshot_reads_only_direct_new_task_and_bug_targets_with_full_planning_authority(self):
        fake = self._seeded()
        out = _run(planning_snapshot, fake, SimpleNamespace(organization=ORG, project=PROJECT, story=self.STORY))

        self.assertEqual(out["source"], {"kind": "story", "id": self.STORY})
        self.assertEqual(out["parent"]["id"], self.STORY)
        self.assertEqual([item["id"] for item in out["targets"]], [self.NEW_TASK, self.NEW_BUG])
        self.assertNotIn(self.ACTIVE_TASK, [item["id"] for item in out["targets"]])
        bug = out["targets"][1]
        self.assertEqual(bug["fields"]["Microsoft.VSTS.TCM.ReproSteps"], "Open planning then observe missing scope")
        self.assertEqual(bug["comments"], [{"id": 8, "format": "markdown", "text": "Reproduces in production."}])
        self.assertEqual(bug["discussion"]["comments"], bug["comments"])
        self.assertEqual(bug["scope"]["source"], "type-specific-fields")
        self.assertIn("Microsoft.VSTS.TCM.ReproSteps", bug["scope"]["fields"])
        self.assertIn("Microsoft.VSTS.TCM.SystemInfo", bug["scope"]["fields"])
        self.assertEqual(
            bug["scope"]["knownBugFields"],
            {
                "Microsoft.VSTS.TCM.ReproSteps": "Open planning then observe missing scope",
                "Microsoft.VSTS.TCM.SystemInfo": "iOS 18",
            },
        )
        self.assertEqual(
            bug["relations"],
            [
                {"rel": "System.LinkTypes.Dependency-Reverse", "url": f"{ORG}/{PROJECT}/_apis/wit/workItems/{self.ACTIVE_TASK}"},
                {"rel": "AttachedFile", "url": "https://storage.example/spec.md", "attributes": {"name": "spec.md"}},
                {"rel": "Hyperlink", "url": "https://docs.example/spec"},
            ],
        )
        self.assertEqual(
            bug["linkedReferences"],
            [
                {"rel": "AttachedFile", "url": "https://storage.example/spec.md", "attributes": {"name": "spec.md"}},
                {"rel": "Hyperlink", "url": "https://docs.example/spec"},
            ],
        )

    def test_explicit_snapshot_preserves_requested_order_without_parent(self):
        fake = self._seeded()
        out = _run(
            planning_snapshot,
            fake,
            SimpleNamespace(organization=ORG, project=PROJECT, story=None,
                             item_ids=[self.NEW_BUG, self.NEW_TASK]),
        )

        self.assertEqual(out["source"], {"kind": "explicit", "ids": [self.NEW_BUG, self.NEW_TASK]})
        self.assertIsNone(out["parent"])
        self.assertEqual([item["id"] for item in out["targets"]], [self.NEW_BUG, self.NEW_TASK])

    def test_explicit_snapshot_accepts_active_task_when_given_by_id(self):
        fake = self._seeded()
        out = _run(
            planning_snapshot,
            fake,
            SimpleNamespace(organization=ORG, project=PROJECT, story=None,
                             item_ids=[self.ACTIVE_TASK]),
        )

        self.assertEqual([item["id"] for item in out["targets"]], [self.ACTIVE_TASK])

    def test_story_snapshot_rejects_non_story_parent(self):
        fake = FakeClient.with_item(self.STORY, item_type="Task")
        with self.assertRaisesRegex(RuntimeError, "requires a Story parent"):
            _run(planning_snapshot, fake, SimpleNamespace(organization=ORG, project=PROJECT, story=self.STORY))

    def test_story_snapshot_allows_closed_parent_when_children_are_new(self):
        fake = self._seeded()
        fake.items[self.STORY]["fields"]["System.State"] = "Closed"
        out = _run(planning_snapshot, fake, SimpleNamespace(organization=ORG, project=PROJECT, story=self.STORY))
        self.assertEqual([item["id"] for item in out["targets"]], [self.NEW_TASK, self.NEW_BUG])

    def test_story_state_is_not_validated_as_a_new_planning_target(self):
        fake = self._seeded()
        fake.items[self.STORY]["fields"]["System.State"] = "Active"
        fake.new_direct_implementation_children = lambda story_id: [self.STORY, self.NEW_TASK]

        out = _run(planning_snapshot, fake, SimpleNamespace(organization=ORG, project=PROJECT, story=self.STORY))

        self.assertEqual([item["id"] for item in out["targets"]], [self.NEW_TASK])

    def test_story_snapshot_rejects_target_that_is_no_longer_new(self):
        fake = self._seeded()
        fake.items[self.NEW_TASK]["fields"]["System.State"] = "Active"
        fake.new_direct_implementation_children = lambda story_id: [self.NEW_TASK]

        with self.assertRaisesRegex(RuntimeError, "changed from New"):
            _run(planning_snapshot, fake, SimpleNamespace(organization=ORG, project=PROJECT, story=self.STORY))

    def test_explicit_snapshot_rejects_non_task_or_bug_target(self):
        fake = self._seeded()
        with self.assertRaisesRegex(RuntimeError, "must be Task or Bug"):
            _run(
                planning_snapshot,
                fake,
                SimpleNamespace(organization=ORG, project=PROJECT, story=None,
                                 item_ids=[self.STORY]),
            )

    def test_parser_accepts_story_or_repeated_explicit_ids(self):
        story_args = parser().parse_args([
            "planning-snapshot", "--organization", ORG, "--project", PROJECT,
            "--story", str(self.STORY),
        ])
        explicit_args = parser().parse_args([
            "planning-snapshot", "--organization", ORG, "--project", PROJECT,
            "--id", str(self.NEW_BUG), "--id", str(self.NEW_TASK),
        ])

        self.assertEqual(story_args.story, self.STORY)
        self.assertIsNone(story_args.item_ids)
        self.assertEqual(explicit_args.item_ids, [self.NEW_BUG, self.NEW_TASK])
        self.assertIsNone(explicit_args.story)


class TypeNeutralPreflightTests(unittest.TestCase):
    def test_bug_preflight_returns_all_fields_comments_and_type_specific_scope(self):
        fake = FakeClient.with_item(42, rev=3, item_type="Bug")
        fake.items[42]["fields"].update({
            "System.Title": "Planner omits bug scope",
            "System.State": "New",
            "System.Description": " \n  ",
            "Microsoft.VSTS.TCM.ReproSteps": "Plan a Story with a Bug child",
        })
        fake.comments[42] = [{"id": 3, "format": "markdown", "text": "Observed after triage."}]

        out = _run(preflight, fake, SimpleNamespace(organization=ORG, project=PROJECT, id=42))

        self.assertEqual(out["scope"]["source"], "type-specific-fields")
        self.assertEqual(out["fields"]["Microsoft.VSTS.TCM.ReproSteps"], "Plan a Story with a Bug child")
        self.assertEqual(out["comments"], [{"id": 3, "format": "markdown", "text": "Observed after triage."}])
        self.assertEqual(out["discussion"]["comments"], out["comments"])


class AzurePlanningQueryTests(unittest.TestCase):
    def test_story_target_query_is_direct_and_server_filters_new_task_bug(self):
        class Api:
            def _send(self, **kwargs):
                self.request = kwargs
                return SimpleNamespace(json=lambda: {"workItemRelations": [
                    {"target": {"id": 1}},
                    {"target": {"id": 9}},
                    {"target": {"id": 4}},
                ]})

        api = Api()
        ids = AzureClient(api, PROJECT).new_direct_implementation_children(1)

        self.assertEqual(ids, [9, 4])
        self.assertEqual(api.request["route_values"], {"project": PROJECT})
        self.assertEqual(api.request["location_id"], AzureClient.WIQL_ID)
        self.assertIn("[Source].[System.Id] = 1", api.request["content"]["query"])
        self.assertIn("Hierarchy-Forward", api.request["content"]["query"])
        self.assertIn("[Target].[System.State] = 'New'", api.request["content"]["query"])
        self.assertIn("[Target].[System.WorkItemType] IN ('Task', 'Bug')", api.request["content"]["query"])
        self.assertIn("MODE (MustContain)", api.request["content"]["query"])

    def test_comment_reader_follows_all_continuation_pages(self):
        class Api:
            def __init__(self):
                self.requests = []

            def _send(self, **kwargs):
                self.requests.append(kwargs)
                token = kwargs["query_parameters"].get("continuationToken")
                page = (
                    {"comments": [{"id": 1}], "continuationToken": "next"}
                    if token is None else
                    {"comments": [{"id": 2}], "continuationToken": None}
                )
                return SimpleNamespace(json=lambda: page)

        api = Api()
        comments = AzureClient(api, PROJECT).read_comments(42)

        self.assertEqual(comments, [{"id": 1}, {"id": 2}])
        self.assertNotIn("continuationToken", api.requests[0]["query_parameters"])
        self.assertEqual(api.requests[1]["query_parameters"]["continuationToken"], "next")

    def test_add_comment_matches_get_payload_that_uses_comment_id(self):
        class Api:
            def __init__(self):
                self.requests = []

            def _send(self, **kwargs):
                self.requests.append(kwargs)
                if kwargs["http_method"] == "POST":
                    return SimpleNamespace(json=lambda: {
                        "id": 17, "format": "markdown", "text": "Added context",
                    })
                return SimpleNamespace(json=lambda: {
                    "comments": [{"commentId": 17, "format": "markdown", "text": "Added context"}],
                    "continuationToken": None,
                })

        api = Api()
        saved = AzureClient(api, PROJECT).add_comment(42, "Added context")

        self.assertEqual(saved["commentId"], 17)


if __name__ == "__main__":
    unittest.main()
