#!/usr/bin/env python3
"""Standalone token-usage benchmark for the Azure Boards skill helper.

This is NOT part of the unittest suite (see ``test_commands.py`` /
``test_safe_mutation.py`` for the real correctness tests) and is not
discoverable by ``python3 -m unittest discover`` -- it defines no
``unittest.TestCase`` subclasses. It is a measurement tool for humans/agents
deciding whether a future change to ``azure_devops_boards.py`` helps or hurts
the amount of text an LLM agent has to read.

Run directly:

    cd skills/azure-devops-boards-skill
    python3 tests/token_benchmark.py

Every number below comes from actually calling the real production functions
(``show_item``, ``preflight``, ``close_task``) against the in-memory
``FakeClient`` test double from ``fakes.py`` and measuring the JSON text they
actually print to stdout -- via the same ``connect``-patching / SimpleNamespace
pattern ``test_commands.py`` uses. Nothing here is hardcoded or remembered
from a previous version of the code, and no removed feature (e.g. the
since-reverted auto-retry-on-revision-conflict behaviour) is simulated or
measured; the ``conflict`` fixture below only exercises the fail-immediately
path that exists in the current working tree.

Token counting is an approximation -- see ``_approx_tokens`` -- used only to
compare relative sizes (before/after, A vs B) within this report, not to
report an exact count from any specific tokenizer.
"""
import io
import sys
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))                     # tests/   → fakes
sys.path.insert(0, str(HERE.parent / "scripts"))  # scripts/ → azure_devops_boards

from fakes import FakeClient, PatchOp  # noqa: E402
from azure_devops_boards import RELATIONS, close_task, preflight, show_item  # noqa: E402

ORG, PROJECT, ITEM_ID = "https://dev.azure.com/o", "P", 42


# ---------------------------------------------------------------------------
# Approximate token counter
#
# This is a rough heuristic (~4 characters per token -- a commonly used rule
# of thumb for English/JSON text), NOT an exact count from any specific
# tokenizer (e.g. tiktoken). It exists purely so the numbers in this report
# can be compared to each other (before/after, compact vs full, two-call vs
# one-call) -- never treat them as an exact token count for context-window
# budgeting or billing.
# ---------------------------------------------------------------------------
def _approx_tokens(text):
    if not text:
        return 0
    return max(1, len(text) // 4)


def _file(text):
    """Stand-in for a --description-file / --comment-file Path (matches the
    pattern used throughout tests/test_commands.py)."""
    return SimpleNamespace(read_text=lambda: text)


def _capture(func, fake, args):
    """Call a real command function against a fake client and return exactly
    what it printed -- the text that would enter an agent's context."""
    with redirect_stdout(io.StringIO()) as buf, \
            mock.patch("azure_devops_boards.connect", return_value=(fake, PatchOp)):
        func(args)
    return buf.getvalue()


def _relation(kind, target_id):
    return {"rel": RELATIONS[kind], "url": f"{ORG}/{PROJECT}/_apis/wit/workItems/{target_id}",
            "attributes": {"comment": "Added by azure-devops-boards skill"}}


# ---------------------------------------------------------------------------
# Fixture content
# ---------------------------------------------------------------------------
_LONG_DESCRIPTION = "\n\n".join([
    "This work item tracks migrating the legacy notification dispatcher off "
    "the deprecated queueing library and onto the shared event bus used by "
    "the rest of the platform. The dispatcher currently polls a database "
    "table every thirty seconds, which was an acceptable design when the "
    "system handled a few hundred notifications a day, but it now creates a "
    "visible lag for customers who expect near-real-time delivery of order "
    "status updates, shipment confirmations, and account alerts. Several "
    "customers have already filed support tickets citing delays of up to two "
    "minutes between an event occurring and the corresponding notification "
    "arriving in their inbox or mobile app.",

    "The proposed approach replaces the polling loop with a subscription to "
    "the event bus topic that the order service, shipment service, and "
    "account service already publish to. Each service currently emits a "
    "well-formed event whenever a relevant state transition occurs, so no "
    "upstream changes should be required. The dispatcher will instead "
    "maintain a small in-memory buffer of recently processed event "
    "identifiers to guard against duplicate delivery, since the event bus "
    "offers at-least-once delivery semantics rather than exactly-once. This "
    "buffer should be bounded and time-limited so it does not grow unbounded "
    "during a burst of traffic or a partial outage upstream.",

    "Backwards compatibility matters here: some downstream consumers still "
    "poll the notification history table directly rather than subscribing to "
    "push updates, so the migration must continue to write a row to that "
    "table for every notification even after the dispatch mechanism changes. "
    "The team should also preserve the existing retry behavior for failed "
    "deliveries, including the exponential backoff schedule and the "
    "dead-letter queue for notifications that fail after the maximum number "
    "of attempts. Any change to that schedule should be called out "
    "explicitly in the pull request description and discussed with the "
    "on-call rotation before merging, since it directly affects incident "
    "response time for downstream teams that depend on timely alerts.",

    "Testing should include both the existing unit test suite for the "
    "dispatcher and a new integration test that publishes a synthetic event "
    "onto a local test topic and asserts that a notification is both queued "
    "and recorded in the history table within a reasonable time bound. "
    "Manual verification in the staging environment, watching a handful of "
    "end-to-end notifications flow through the new path, is also expected "
    "before this is considered done. Please document any operational runbook "
    "changes needed for the on-call team, including how to inspect the new "
    "subscription's lag and how to manually replay a missed event if the "
    "buffer above drops it unexpectedly.",
])


def _twenty_ac_description():
    """20 markdown checklist lines, a mix of checked and unchecked."""
    topics = [
        "Add input validation for the new endpoint",
        "Write unit tests for the request parser",
        "Update the OpenAPI schema",
        "Add a database migration for the new column",
        "Backfill existing rows with a default value",
        "Wire the new field through the API response",
        "Add integration tests for the happy path",
        "Add integration tests for the error path",
        "Update the client SDK to expose the new field",
        "Add a feature flag to gate the rollout",
        "Document the new field in the API reference",
        "Add monitoring for the new code path",
        "Add an alert for elevated error rates",
        "Review the change with the security team",
        "Load test the new endpoint",
        "Update the changelog",
        "Notify downstream consumers of the change",
        "Add a rollback plan to the runbook",
        "Get sign-off from the on-call lead",
        "Verify the fix in staging",
    ]
    lines = [f"{'- [x]' if index % 3 == 0 else '- [ ]'} {topic}" for index, topic in enumerate(topics)]
    return "\n".join(lines)


_HEAVY_METADATA_DESCRIPTION = "\n\n".join([
    "This task depends on several upstream and downstream work items and "
    "carries a moderate amount of Azure-side relation metadata: a parent "
    "feature, two predecessor tasks that must land first, and one related "
    "item tracked for context. The description itself is intentionally "
    "shorter than a fully verbose write-up, but the relation graph attached "
    "to this item is representative of a task embedded deep in a larger "
    "initiative.",

    "Coordinate the rollout order with the predecessor tasks before starting "
    "any implementation work here, since this task's acceptance criteria "
    "assume both predecessors have already merged and deployed to "
    "production. Reach out in the team channel if either predecessor slips.",
])


def _fake_small():
    fake = FakeClient.with_item(ITEM_ID, rev=3, item_type="Task")
    fake.items[ITEM_ID]["fields"].update({
        "System.Title": "Fix off-by-one in pagination",
        "System.State": "Active",
        "System.Description": "Fix the off-by-one error in the page-size calculation.",
    })
    return fake


def _fake_long_description():
    fake = FakeClient.with_item(ITEM_ID, rev=3, item_type="Task")
    fake.items[ITEM_ID]["fields"].update({
        "System.Title": "Migrate notification dispatcher to the event bus",
        "System.State": "Active",
        "System.Description": _LONG_DESCRIPTION,
    })
    return fake


def _fake_twenty_ac():
    fake = FakeClient.with_item(ITEM_ID, rev=3, item_type="Task")
    fake.items[ITEM_ID]["fields"].update({
        "System.Title": "Ship the new account field end-to-end",
        "System.State": "Active",
        "System.Description": _twenty_ac_description(),
    })
    return fake


def _fake_heavy_metadata():
    fake = FakeClient.with_item(ITEM_ID, rev=3, item_type="Task")
    fake.items[ITEM_ID]["fields"].update({
        "System.Title": "Implement the second phase of the rollout",
        "System.State": "Active",
        "System.Description": _HEAVY_METADATA_DESCRIPTION,
    })
    fake.items[ITEM_ID]["relations"] = [
        _relation("parent", 10),
        _relation("predecessor", 11),
        _relation("predecessor", 12),
        _relation("related", 13),
    ]
    return fake


def _fake_conflict():
    fake = FakeClient.with_item(ITEM_ID, rev=5, item_type="Task")
    fake.items[ITEM_ID]["fields"].update({
        "System.Title": "Patch the rate limiter",
        "System.State": "Active",
        "System.Description": "Patch the rate limiter to use a sliding window.",
    })
    return fake


# Fixtures 1-4. ``close_kwargs`` picks the patch each fixture uses to give
# close-task a valid mutation: the checklist fixture drives it via
# --check-ac, the rest via a plain --state field patch.
FIXTURES = [
    {"name": "small", "make": _fake_small, "description": "Fix the off-by-one error in the page-size calculation.",
     "close_kwargs": {"state": "Active", "check_ac": None}},
    {"name": "long_description", "make": _fake_long_description, "description": _LONG_DESCRIPTION,
     "close_kwargs": {"state": "Active", "check_ac": None}},
    {"name": "twenty_ac", "make": _fake_twenty_ac, "description": _twenty_ac_description(),
     "close_kwargs": {"state": None, "check_ac": "all"}},
    {"name": "heavy_metadata", "make": _fake_heavy_metadata, "description": _HEAVY_METADATA_DESCRIPTION,
     "close_kwargs": {"state": "Active", "check_ac": None}},
]


# ---------------------------------------------------------------------------
# Measurements
# ---------------------------------------------------------------------------
def _show_args(full):
    return SimpleNamespace(organization=ORG, project=PROJECT, id=ITEM_ID, full=full)


def _measure_show(fixture):
    compact = _capture(show_item, fixture["make"](), _show_args(full=False))
    full = _capture(show_item, fixture["make"](), _show_args(full=True))
    return _approx_tokens(compact), _approx_tokens(full)


def _measure_preflight(fixture):
    args = SimpleNamespace(organization=ORG, project=PROJECT, id=ITEM_ID)
    out = _capture(preflight, fixture["make"](), args)
    return _approx_tokens(out)


def _close_args(fixture, apply, expected_rev=None):
    kwargs = fixture["close_kwargs"]
    return SimpleNamespace(organization=ORG, project=PROJECT, id=ITEM_ID, apply=apply,
                           expected_rev=expected_rev, state=kwargs["state"], description_file=None,
                           check_ac=kwargs["check_ac"], comment_file=_file("## Completion\nDone. Verified in staging."))


def _measure_close_task(fixture):
    """Two-phase (a --apply=False validate call, then a fresh --apply=True
    call) vs single --apply-only call, each on its own fresh fixture copy so
    no call's mutation leaks into another's measurement."""
    validate_only = _capture(close_task, fixture["make"](), _close_args(fixture, apply=False))
    apply_after_validate = _capture(close_task, fixture["make"](), _close_args(fixture, apply=True))
    single_apply = _capture(close_task, fixture["make"](), _close_args(fixture, apply=True))

    two_phase_tokens = _approx_tokens(validate_only) + _approx_tokens(apply_after_validate)
    single_tokens = _approx_tokens(single_apply)
    return two_phase_tokens, single_tokens


def _measure_conflict():
    """A stale --expected-rev must fail immediately, with no retry. There is
    no retry path left to measure -- an earlier auto-retry-on-conflict
    feature was reverted and no longer exists in this working tree."""
    fake = _fake_conflict()
    actual_rev = fake.items[ITEM_ID]["rev"]
    args = SimpleNamespace(organization=ORG, project=PROJECT, id=ITEM_ID, apply=True,
                           expected_rev=actual_rev - 1, state="Active", description_file=None,
                           check_ac=None, comment_file=_file("## Completion\nDone."))
    try:
        _capture(close_task, fake, args)
    except RuntimeError as exc:
        return str(exc), _approx_tokens(str(exc))
    raise AssertionError("expected close_task to raise RuntimeError for a stale --expected-rev")


def _measure_skill_md():
    boards_skill = HERE.parent / "SKILL.md"
    implement_skill = HERE.parent.parent / "azure-task-implement" / "SKILL.md"
    return [
        ("azure-devops-boards-skill/SKILL.md", _approx_tokens(boards_skill.read_text())),
        ("azure-task-implement/SKILL.md", _approx_tokens(implement_skill.read_text())),
    ]


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------
def _pct(reduction, baseline):
    return (reduction / baseline * 100) if baseline else 0.0


def _print_header():
    print("=" * 78)
    print("Azure Boards helper -- token usage benchmark (approximate, relative)")
    print("=" * 78)
    print(
        "Every number below comes from calling the real show_item / preflight /\n"
        "close_task functions against the in-memory FakeClient test double and\n"
        "measuring the JSON text they actually print. Token counts use a rough\n"
        "~4-characters-per-token heuristic (see _approx_tokens) -- they are NOT an\n"
        "exact count from any specific tokenizer, and are only meaningful as\n"
        "relative comparisons (before/after, A vs B) within this report.\n"
    )


def _print_fixture_report(fixture):
    print("-" * 78)
    print(f"Fixture: {fixture['name']}")
    print("-" * 78)

    compact_tokens, full_tokens = _measure_show(fixture)
    show_reduction = full_tokens - compact_tokens
    print("  show (compact, default) vs show --full:")
    print(f"    compact = {compact_tokens} tokens, full = {full_tokens} tokens")
    print(f"    reduction = {show_reduction} tokens ({_pct(show_reduction, full_tokens):.1f}%)")

    preflight_tokens = _measure_preflight(fixture)
    print("  implement-preflight output size (no prior-implementation comparison; new command):")
    print(f"    {preflight_tokens} tokens")

    two_phase_tokens, single_tokens = _measure_close_task(fixture)
    close_reduction = two_phase_tokens - single_tokens
    print("  close-task: two-phase (validate-only call + apply call) vs single --apply call:")
    print(f"    two-phase total = {two_phase_tokens} tokens, single --apply = {single_tokens} tokens")
    print(f"    reduction = {close_reduction} tokens ({_pct(close_reduction, two_phase_tokens):.1f}%)")

    description_tokens = _approx_tokens(fixture["description"])
    print("  avoided model-context cost for --check-ac (counterfactual, not measured")
    print("  against any specific past implementation -- close-task/--check-ac never")
    print("  puts the Description text itself in the output; this is what a model would")
    print("  have had to additionally read and re-emit if it had to edit the Description itself):")
    print(f"    {description_tokens} tokens")
    print()


def _print_conflict_report():
    print("-" * 78)
    print("Fixture: conflict (stale --expected-rev)")
    print("-" * 78)
    message, tokens = _measure_conflict()
    print("  conflict-signal cost: fails immediately, no retry -- recovery requires one")
    print("  fresh implement-preflight call (there is no auto-retry path in the current")
    print("  code to measure):")
    print(f"    error message: {message!r}")
    print(f"    {tokens} tokens")
    print()


def _print_skill_md_report():
    print("-" * 78)
    print("Fixed cost per skill load (SKILL.md, read fresh off disk)")
    print("-" * 78)
    for label, tokens in _measure_skill_md():
        print(f"  {label}: {tokens} tokens")
    print()


def main():
    _print_header()
    for fixture in FIXTURES:
        _print_fixture_report(fixture)
    _print_conflict_report()
    _print_skill_md_report()
    print("=" * 78)
    print("Note: this is a directional/relative measurement tool, not a CI gate -- "
          "hard pass/fail thresholds could be layered on top later if wanted.")


if __name__ == "__main__":
    main()
