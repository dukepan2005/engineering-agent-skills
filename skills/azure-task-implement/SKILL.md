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

When the caller selects `reviewOwner=self`, keep the standalone wrapper flow:
after implementation and the task-only review commit, invoke `$code-review`,
fix every actionable finding, rerun the relevant verification, and invoke
`$code-review` again against the same `reviewBase...HEAD` delta. If the
post-fix review has a P0/P1 finding, another explicitly blocking
correctness/security/data-loss regression, or verification still cannot support
the task, return:

```json
{
  "outcome": "review_escalation_required",
  "blockingFindings": [{"priority": "P1", "location": "...", "summary": "..."}],
  "verification": ["..."],
  "commit": "<current task commit or null>"
}
```

Otherwise return `{"outcome":"ready_for_closeout", ...}` with the commit,
verification, and both review summaries. Do not perform Azure Boards
operations in either mode.
