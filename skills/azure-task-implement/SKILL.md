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
cannot be isolated, stop and report that blocker. After implementation, create
one task-only, unpushed commit on the current branch. If review findings require
repair, make a separate task-only repair commit after verification. Keep the
implementation commit intact and leave both commits unpushed. Return the
starting commit as `reviewBase` (also `taskStartCommit`) and the latest task
commit as `commit`; the parent will review
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

## Incomplete work and recovery checkpoints

Keep repairing in-scope code, tests and recoverable environment failures using
existing authorization. A red test or an unavailable test helper is not itself
a request for human intervention. For parent-owned execution, use the
[autonomous recovery policy](../azure-task-orchestrator/SKILL.md#autonomous-recovery-and-diagnostic-escalation).
Keep the assigned model/effort fixed during a worker turn; yield a checkpoint
to the parent to perform an approved diagnostic escalation. Checkpoint within
10 minutes of diagnosis (finish an already running bounded test first), or
earlier after two rejected candidate fixes or a concrete external blocker.

Return an incomplete checkpoint with the original fixed point and current
commit (or `null`):

```json
{
  "outcome": "implementation_failed",
  "reviewBase": "<starting commit>",
  "taskStartCommit": "<starting commit>",
  "commit": null,
  "recovery": {
    "disposition": "retry",
    "reason": "<exact incomplete behavior>",
    "evidence": "<red command/result or relevant artifact>",
    "nextAction": "<permitted local recovery>"
  },
  "diagnostics": {"noProgressMinutes": 0, "rejectedFixes": 0}
}
```

Use `retry` when the current authorized scope still has a concrete local
recovery. Use `blocked` only for evidence-backed missing external access,
credentials, conflicting scope or user-owned changes, or a required decision
that cannot be resolved locally. State the exact missing input in `nextAction`.
For a denied operation, retain `deniedAction`; a retry also requires a different
permitted `safeAlternative`, with the reason it respects the rejection. Never
repeat or indirectly bypass a denied action. An uncertain or unavailable safe
alternative is `blocked`, not a speculative retry.

Measure `noProgressMinutes` from the last new causal evidence, and
`rejectedFixes` since the latest diagnostic candidate escalation. Include
supporting timestamps, the exact loop and results, rejected hypotheses,
source/build identity, running commands, and remaining verification in the
handoff. Repeated green runs alone are not causal progress. A diagnostic
method reporting that it cannot reproduce the symptom is a checkpoint; it is
not by itself evidence that only the user can unblock the work.

`implementation_failed` blocks review and closeout until recovery succeeds;
it does not automatically end the authorized task. In standalone mode the
owning conversation applies the same recovery policy and requests a model
change only when its approved plan or host cannot dispatch it. No incomplete
checkpoint may claim review or closeout readiness.

## Parent-owned review repair mode

When the parent supplies review findings in `reviewOwner=parent` mode, preserve
the existing task delta and `reviewBase`, repair every actionable finding that
is in scope, rerun the relevant verification, and create one separate repair
commit on top of the implementation commit. Confirm the starting HEAD is the
commit supplied by the parent and the new commit's parent is that same commit.
Return the same `ready_for_review` shape with the repair commit as `commit` and
the original `reviewBase`. If repair or
verification remains incomplete, return the recovery checkpoint above; the
parent recovers this repair before the next review round.
Never discard user-owned changes.

## Standalone review-owner=self mode

When the caller selects `reviewOwner=self`, after implementation and the
task-only commit, run a dual-axis `$code-review`. If the first review is clean,
proceed directly to Boards closeout; do not run an unneeded second review. If
it reports findings, repair them, rerun relevant verification, create a separate
repair commit, and run review round 2 against the same `reviewBase...HEAD`
delta. If round 2 still reports findings, raise the implementation/repair
`reasoning_effort` by one supported level while keeping the same model, then
make one final repair commit and run review round 3. Keep the review model and
effort from the approved plan unchanged. If round 3 still reports findings,
stop without closeout and return them for human direction. If no higher
supported implementation effort is available after round 2, stop and return
the findings for human direction without attempting an unsupported spawn. A
failed or malformed review is never clean and also stops the workflow. Return:

```json
{
  "outcome": "review_action_required",
  "remainingFindings": [{"priority": "P1", "location": "...", "summary": "..."}],
  "verification": ["..."],
  "commit": "<current task commit or null>"
}
```

When any review round is clean, close the work item through
`$azure-devops-boards-skill` in its semantic `task-boards-ops` role. Map every
Acceptance criterion to concrete current-code evidence. For Task/Bug items,
update only supported checklist markers in the native
`Microsoft.VSTS.Common.AcceptanceCriteria` field, preserve Description, post a
completion comment, and close to the repository's documented terminal state
(normally `Closed`). When criteria need updating, pass the revised field through
`close-task --acceptance-criteria-file`; use the preflight revision as
`--expected-rev`. If it is stale, stop without retrying or claiming completion.
Return `{"outcome":"completed", ...}` with both commit IDs when repair was
needed, verification, review summary, final tracker state, and closeout result.
If closeout cannot be performed after a clean review, stop and report the
concrete blocker rather than claiming completion.

## Parent-owned review-owner=parent mode

The parent owns review dispatch, repair, aggregation, and Boards closeout. Run
at most three dual-axis rounds: if round one is clean, the parent may close out
immediately; if it has findings, repair and run round two; if round two still
has findings, the parent raises the implementation/repair `reasoning_effort`
by one supported level while keeping the same model, then runs one final repair
and review round. Keep the approved review model and effort unchanged. If round
three still has findings, or no higher supported implementation effort is
available after round two, stop for human direction. After implementation,
return `ready_for_review` as specified above. Do not close the work item in
this mode.
