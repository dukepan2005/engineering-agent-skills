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

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))                     # tests/   → fakes
sys.path.insert(0, str(HERE.parent / "scripts"))  # scripts/ → azure_devops_boards

from fakes import FakeClient, PatchOp  # noqa: E402
from azure_devops_boards import RELATIONS, add_comment, add_link, create, update  # noqa: E402

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


class UpdateCommandTests(unittest.TestCase):
    def _args(self, apply, state="Active", iteration=None, description_file=None):
        return SimpleNamespace(organization=ORG, project=PROJECT, apply=apply, id=42,
                               state=state, iteration=iteration, description_file=description_file)

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

    def test_no_field_to_update_raises(self):
        with self.assertRaises(RuntimeError) as cm:
            _run(update, self._seeded(), self._args(apply=True, state=None))
        self.assertIn("Specify a field to update.", str(cm.exception))

    def test_description_round_trips(self):
        fake = self._seeded()
        out = _run(update, fake, self._args(apply=True, state=None, description_file=_file("a && b")))
        self.assertEqual(out["mode"], "applied")
        self.assertEqual(fake.applies, 1)


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

    def test_applied_mode_writes_and_emits(self):
        fake = self._seeded()
        out = _run(add_link, fake, self._args(apply=True))
        self.assertEqual(out, {"mode": "applied", "id": self.ID, "kind": self.KIND, "targetId": self.TARGET})
        self.assertEqual(fake.applies, 1)
        rel = self._relation_value()
        stored = fake.read(self.ID)
        self.assertTrue(any(r["rel"] == rel["rel"] and r["url"] == rel["url"] for r in stored["relations"]))


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


if __name__ == "__main__":
    unittest.main()
