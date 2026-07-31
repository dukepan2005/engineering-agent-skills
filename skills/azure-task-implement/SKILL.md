---
name: azure-task-implement
description: "Use when implementing code from a provided specification or ticket scope."
---

# Azure Task Implement

Implement the work described by the provided scope.

Use `$tdd` where possible, at pre-agreed seams.

Run typechecking regularly, single test files regularly, and the full test
suite once at the end.

Capture the task's starting commit before editing. Before the first review,
create one task-only, unpushed review commit so `$code-review` can inspect the
actual fixed-point delta. If unrelated user changes cannot be isolated, stop
and report that blocker. Amend that same commit for review fixes; never create
a second task commit merely to address review findings.

Once done, use `$code-review` to review the work.

Fix every actionable review finding, rerun the relevant verification, then use
`$code-review` again against the repaired task delta. Do not treat the first
review as final when it found actionable issues.

If the post-fix review has a P0 or P1 finding, another explicitly blocking
correctness/security/data-loss regression, or verification still cannot support
the task, stop and return:

```json
{
  "outcome": "review_escalation_required",
  "blockingFindings": [{"priority": "P1", "location": "...", "summary": "..."}],
  "verification": ["..."],
  "commit": "<current task commit or null>"
}
```

Otherwise commit your work to the current branch (or retain the one amended
review commit) and return
`{"outcome":"ready_for_closeout", ...}` with the commit, verification, and
both review summaries. If the prompt identifies this as review recovery, repair
the supplied findings in the existing task delta, rerun verification and review,
and do not discard user-owned changes.
