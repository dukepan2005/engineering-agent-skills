---
name: azure-task-implement
description: "Use when implementing code from a provided specification or ticket scope."
---

# Azure Task Implement

Implement the work described by the provided scope in the current workspace
and branch. This Skill supports two explicit review-ownership modes so it can
remain a complete standalone `$implement` wrapper while also serving the flat
Azure delivery orchestrator:

- `reviewOwner=self` (the backward-compatible default): this worker owns the
  implementation and the `$code-review` handoff.
- `reviewOwner=parent`: this worker owns only implementation, tests, and the
  task commit; its parent owns review dispatch, aggregation, repair dispatch,
  and Azure Boards closeout.

If the caller omits the mode, treat it as `reviewOwner=self` for backward
compatibility. The Azure orchestrator must state and always use
`reviewOwner=parent`.

In standalone `reviewOwner=self` mode, require an Azure work-item ID, the
explicit tracker organization and project, and a current preflight revision.
Resolve the connection from repository tracker guidance; if it is ambiguous,
stop and request it. If the caller did not provide a current preflight, use
`$azure-devops-boards-skill` in the `task-boards-ops` role to run
`implement-preflight` once with the explicit connection and item ID before
editing. Use its full result as current scope authority and retain its `rev`
for closeout. In `reviewOwner=parent` mode, use the parent's supplied
preflight and connection.

Use `$tdd` where possible, at pre-agreed seams. Run typechecking regularly,
single test files regularly, and the full test suite once at the end. Re-read
repository authority before editing, and protect unrelated user changes.

## Commit and review handoff

Capture the task's starting commit before editing. If unrelated user changes
cannot be isolated, stop and report that blocker. Before returning a successful
implementation, create one task-only, unpushed commit on the current branch.
Return the starting commit as `reviewBase` (also `taskStartCommit`) and the
current task commit as `commit`; the parent will review
`git diff <reviewBase>...HEAD`.

In `reviewOwner=parent` mode, do not invoke `$code-review`, spawn review
agents, or perform Azure Boards operations. The parent orchestrator launches
the Standards and Spec review workers directly and supplies their reports when
a repair is needed. This mode must not assume that a child-spawn primitive
exists.

For a normal implementation in `reviewOwner=parent` mode, return JSON with
this shape:

```json
{
  "outcome": "ready_for_review",
  "reviewBase": "<starting commit>",
  "taskStartCommit": "<starting commit>",
  "commit": "<task commit>",
  "changedAreas": ["..."],
  "verification": ["..."],
  "acceptanceEvidence": [{"criterion": "...", "evidence": "..."}],
  "remainingWork": []
}
```

If implementation or verification cannot complete, return
`{"outcome":"implementation_failed", ...}` with the concrete blocker and
the current commit (or `null`). Do not claim review or closeout readiness.

## Parent-owned review repair mode

When the parent supplies review findings in `reviewOwner=parent` mode, preserve
the existing task delta and `reviewBase`, repair every actionable finding that
is in scope, rerun the relevant verification, and amend the same task commit.
Do not create a second task commit merely to address review findings. Return
the same `ready_for_review` shape with updated evidence. If repair or
verification fails, return `implementation_failed` and the concrete blocker.
Never discard user-owned changes.

## Standalone review-owner=self mode

When the caller selects `reviewOwner=self`, after implementation and the
task-only commit, run a dual-axis `$code-review`. If the first review is clean,
proceed directly to Boards closeout; do not run an unneeded second review. If
it reports findings, repair them, rerun relevant verification, and run the
second dual-axis review against the same `reviewBase...HEAD` delta. Two review
rounds is the maximum. If the second review still reports any findings, stop
without closeout and return the findings for human direction. A failed or
malformed review is never clean and also stops the workflow. Return:

```json
{
  "outcome": "review_action_required",
  "remainingFindings": [{"priority": "P1", "location": "...", "summary": "..."}],
  "verification": ["..."],
  "commit": "<current task commit or null>"
}
```

When either review round is clean, close the work item through
`$azure-devops-boards-skill` in its semantic `task-boards-ops` role. Map every
Acceptance criterion to concrete current-code evidence; update only checklist
markers supported by that mapping, preserve the rest of the Description, post a
completion comment, and close to the repository's documented terminal state
(normally `Closed`). Use `close-task --apply` with the preflight revision as
`--expected-rev`; if it is stale, stop without retrying or claiming completion.
Return `{"outcome":"completed", ...}` with the commit, verification, review
summary, final tracker state, and closeout result. If closeout cannot be
performed after a clean review, stop and report the concrete blocker rather
than claiming completion.

## Parent-owned review-owner=parent mode

The parent owns both review rounds and Boards closeout. Run at most two
dual-axis rounds: if round one is clean, the parent may close out immediately;
if it has findings, repair and run round two; if round two still has any
findings, stop for human direction. After implementation, return
`ready_for_review` as specified above. Do not close the work item in this mode.
