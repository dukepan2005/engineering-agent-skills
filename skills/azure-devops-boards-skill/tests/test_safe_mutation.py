"""Lifecycle-invariant tests for the safe-mutation runner (candidate C).

Driven through the in-memory FakeClient — no Azure, no network. These pin the
runner's safety contract:

- validate-then-check ordering — any expectation failing at validation prevents the write;
- read-back is checked before applied-mode success is reported (and a read-back
  failure means a write already occurred);
- validate-only mode never writes;
- ``/rev`` optimistic concurrency is honoured.
"""
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))                     # tests/   → fakes
sys.path.insert(0, str(HERE.parent / "scripts"))  # scripts/ → azure_devops_boards

from fakes import FakeClient, PatchOp  # noqa: E402
from azure_devops_boards import (  # noqa: E402
    Expectation, ExistingItem, NewItem, safe_mutate,
)


class _RevAdvances(FakeClient):
    """The rev advances on every validate — there is no reconciliation left to
    attempt, so a conflict must surface on the very first attempt."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.validate_calls = 0

    def validate(self, document, target):
        self.validate_calls += 1
        if not self._is_new(target):
            self.items[target.item_id]["rev"] += 1
            raise RuntimeError("rev mismatch (optimistic concurrency)")
        return super().validate(document, target)


class _FieldMismatchWithAdvancedRev(FakeClient):
    """Validation reports an unrelated field mismatch while also reflecting a
    rev that moved forward — the coincidence must never resurrect a retry."""

    def validate(self, document, target):
        item = super().validate(document, target)
        item["rev"] += 1
        return item


class ValidationGuardsTheWriteTests(unittest.TestCase):
    """Any expectation that fails at validation must prevent the write entirely."""

    def test_field_mismatch_at_validation_prevents_write(self):
        fake = FakeClient.with_item(42)
        with self.assertRaises(RuntimeError) as cm:
            safe_mutate(client=fake, target=ExistingItem(42),
                        document=[PatchOp("add", "/fields/System.State", "Active")],
                        expectation=Expectation(fields={"System.State": "Done"}), apply=True)
        self.assertIn("Validation failed for System.State", str(cm.exception))
        self.assertEqual(fake.applies, 0)

    def test_iteration_mismatch_displays_requested_and_returned_paths(self):
        class NormalizedIteration(FakeClient):
            def validate(self, document, target):
                item = super().validate(document, target)
                item["fields"]["System.IterationPath"] = "GayDating\\Sprint_2026_S02"
                return item

        requested = "GayDating\\\\Sprint_2026_S02"
        fake = NormalizedIteration.with_item(42)
        with self.assertRaises(RuntimeError) as cm:
            safe_mutate(client=fake, target=ExistingItem(42),
                        document=[PatchOp("add", "/fields/System.IterationPath", requested)],
                        expectation=Expectation(fields={"System.IterationPath": requested}), apply=True)
        self.assertEqual(
            str(cm.exception),
            'Validation failed for System.IterationPath: requested "GayDating\\\\\\\\Sprint_2026_S02", '
            'but Azure returned "GayDating\\\\Sprint_2026_S02".'
        )
        self.assertEqual(fake.applies, 0)

    def test_description_mismatch_at_validation_prevents_write(self):
        fake = FakeClient.with_item(42)
        with self.assertRaises(RuntimeError) as cm:
            safe_mutate(client=fake, target=ExistingItem(42),
                        document=[PatchOp("add", "/fields/System.Description", "stored"),
                                  PatchOp("add", "/multilineFieldsFormat/System.Description", "markdown")],
                        expectation=Expectation(description="expected"), apply=True)
        self.assertIn("Description or Markdown metadata did not persist.", str(cm.exception))
        self.assertEqual(fake.applies, 0)

    def test_relation_not_projected_at_validation_is_accepted(self):
        fake = FakeClient.with_item(42, echo_relations_on_validate=False)
        result = safe_mutate(client=fake, target=ExistingItem(42),
                             document=[PatchOp("add", "/relations/-", {"rel": "X", "url": "u"})],
                             expectation=Expectation(relation=("X", "u")), apply=False)
        self.assertEqual(result, {"mode": "validated"})
        self.assertEqual(fake.applies, 0)

    def test_create_relation_not_projected_at_validation_prevents_write(self):
        fake = FakeClient(echo_relations_on_validate=False)
        with self.assertRaises(RuntimeError) as cm:
            safe_mutate(client=fake, target=NewItem("Task"),
                        document=[PatchOp("add", "/relations/-", {"rel": "X", "url": "u"})],
                        expectation=Expectation(relation=("X", "u")), apply=True)
        self.assertIn("Validation failed for relation", str(cm.exception))
        self.assertEqual(fake.applies, 0)


class ReadBackGuardsAppliedSuccessTests(unittest.TestCase):
    """Validation passing but read-back mismatching must raise AFTER a write occurred."""

    def test_read_back_mismatch_raises_after_write(self):
        class CorruptRead(FakeClient):
            def read(self, item_id):
                item = super().read(item_id)
                item["fields"]["System.State"] = "CORRUPT"
                return item

        fake = CorruptRead.with_item(42)
        with self.assertRaises(RuntimeError) as cm:
            safe_mutate(client=fake, target=ExistingItem(42),
                        document=[PatchOp("add", "/fields/System.State", "Active")],
                        expectation=Expectation(fields={"System.State": "Active"}), apply=True)
        self.assertIn("Read-back failed for System.State", str(cm.exception))
        self.assertEqual(fake.applies, 1, "a write occurred before the read-back check")

    def test_applied_success_requires_read_back_to_match(self):
        fake = FakeClient.with_item(42)
        r = safe_mutate(client=fake, target=ExistingItem(42),
                        document=[PatchOp("add", "/fields/System.State", "Active")],
                        expectation=Expectation(fields={"System.State": "Active"}), apply=True)
        self.assertEqual(r, {"mode": "applied", "id": 42, "rev": 2})
        self.assertEqual(fake.applies, 1)


class ValidateOnlyNeverWritesTests(unittest.TestCase):
    def test_validate_only_mode_skips_write_on_success(self):
        fake = FakeClient()
        r = safe_mutate(client=fake, target=NewItem("Task"),
                        document=[PatchOp("add", "/fields/System.Title", "T")],
                        expectation=Expectation(), apply=False)
        self.assertEqual(r, {"mode": "validated"})
        self.assertEqual(fake.applies, 0)


class OptimisticConcurrencyTests(unittest.TestCase):
    def test_stale_rev_raises_and_prevents_write(self):
        fake = FakeClient.with_item(42)  # rev == 1
        with self.assertRaises(RuntimeError) as cm:
            safe_mutate(client=fake, target=ExistingItem(42),
                        document=[PatchOp("test", "/rev", 99)],  # never the live rev
                        expectation=Expectation(), apply=True)
        self.assertIn("rev mismatch", str(cm.exception))
        self.assertEqual(fake.applies, 0)

    def test_rev_conflict_surfaces_on_first_attempt_without_retry(self):
        # The rev advances on the very first validate — there is no retry left
        # to attempt, so the conflict must surface immediately.
        fake = _RevAdvances.with_item(42)
        with self.assertRaises(RuntimeError) as cm:
            safe_mutate(client=fake, target=ExistingItem(42),
                        document=[PatchOp("test", "/rev", 1),
                                  PatchOp("add", "/fields/System.State", "Active")],
                        expectation=Expectation(fields={"System.State": "Active"}), apply=True)
        self.assertIn("rev mismatch", str(cm.exception))
        self.assertEqual(fake.applies, 0)
        self.assertEqual(fake.validate_calls, 1)

    def test_field_mismatch_with_advanced_rev_still_raises_immediately(self):
        # Guard against resurrecting the reverted auto-retry: an unrelated
        # field mismatch must surface immediately even when the rev happens to
        # look reconcilable (moved forward) — no code path is left that
        # inspects the raised exception to special-case it.
        fake = _FieldMismatchWithAdvancedRev.with_item(42)
        with self.assertRaises(RuntimeError) as cm:
            safe_mutate(client=fake, target=ExistingItem(42),
                        document=[PatchOp("test", "/rev", 1),
                                  PatchOp("add", "/fields/System.State", "Active")],
                        expectation=Expectation(fields={"System.State": "Done"}), apply=True)
        self.assertIn("Validation failed for System.State", str(cm.exception))
        self.assertNotIn("rev mismatch", str(cm.exception))
        self.assertEqual(fake.applies, 0)


class DescriptionRoundTripTests(unittest.TestCase):
    def test_description_with_html_chars_round_trips(self):
        # Mirrors the exact failing case from commit b9232a0.
        text = "run `a && b < c > d` & repeat."
        fake = FakeClient()
        doc = [PatchOp("add", "/fields/System.Description", text),
               PatchOp("add", "/multilineFieldsFormat/System.Description", "markdown")]
        r = safe_mutate(client=fake, target=NewItem("Task"), document=doc,
                        expectation=Expectation(description=text), apply=True)
        self.assertEqual(r["mode"], "applied")


if __name__ == "__main__":
    unittest.main()
