---
name: task-model-planner
description: Analyze a Story, ticket, or implementation specification and produce a source-backed report recommending one named execution profile for each Task. Use when the user asks which model profile, reasoning effort, or cost-aware execution configuration should implement a Story's child Tasks or a set of tickets.
---

# Task Model Planner

Produce a read-only implementation model plan. Do not implement or mutate the
tracker.

## Establish the Work Set

1. Read the nearest `AGENTS.md` and every repository guidance file it requires.
2. Read the current authoritative Story or ticket, including revision, state,
   acceptance criteria, relations, comments, attachments, and linked
   specification documents that affect scope.
3. For a Story, analyze each directly related child Task separately. For a Task
   or standalone ticket, analyze only that item unless the user explicitly names
   a larger set.
4. Read blocking, prerequisite, replacement, or cross-repository tickets only
   when they materially affect a recommendation.
5. Use the existing Azure Boards skill and repository tracker guidance for
   Azure Boards reads. Do not duplicate tracker mechanics.
6. Inspect current code or tests only when the ticket and its documents do not
   provide enough evidence to classify complexity. Label any conclusion based
   on incomplete evidence with lower confidence.

Treat the current tracker, linked specifications, and current code as
authoritative over earlier plans or summaries. State conflicts instead of
silently resolving them.

## Keep the Analysis Read-Only

- Do not edit code, documents, Git state, configuration, or tracker items.
- Do not build, test, migrate, generate, install, commit, push, or invoke
  `$implement`.
- Do not split, rewrite, create, or reprioritize Tasks.
- Record missing information and its effect on confidence.
- Stop after returning the report.

## Classify the Task

Choose the lowest-cost profile that has a credible path to meeting acceptance
criteria and focused verification requirements. Do not assign a stronger model
merely because a Task is large.

For each Task, assess only source-backed evidence:

- Ambiguity: are acceptance criteria, ownership, and expected behavior clear?
- Coupling: how many modules, repositories, contracts, or lifecycle stages change?
- Failure cost: could a wrong change cause data loss, security exposure,
  compatibility breakage, or difficult rollback?
- Reasoning hazards: concurrency, ordering, migrations, deletion/cutover,
  negative paths, or non-local invariants.
- Verification strength: do focused tests, types, migrations, or established
  patterns independently detect a wrong implementation?

## Choose the Execution Profile

Read [the canonical execution-profile registry](references/execution-profiles.md)
before selecting a profile. Output only its profile ID; do not output a free-form
model and thinking-level pair.

Choose a Terra profile when scope is bounded and current authority plus focused
verification make incorrect assumptions cheap to detect. Choose a Sol profile
when unresolved ambiguity, cross-boundary coupling, or failure cost requires
stronger judgment before implementation.

Use `medium` by default for a clear, bounded Task with a credible focused
verification plan. Use `high` only for multiple coordinated changes or one
material reasoning hazard. Use `xhigh` only when high failure cost combines with
concrete uncertainty, concurrency/ordering, migration/compatibility, or
cross-repository risk. Do not invent profiles, and do not recommend `max` as an
initial profile.

## Explain Every Recommendation

For each Task:

1. Cite the scope and risk signals that drive the choice.
2. Give one primary recommendation, not a menu.
3. Explain why a lower-cost profile is insufficient.
4. Give concrete escalation triggers that can be checked during implementation.
5. Assign confidence as `high`, `medium`, or `low`, based on source completeness.

Keep sequencing separate from profile selection. Different Tasks under one Story
may use different profiles.

Always return every planned Task exactly once in execution order. Derive the
order from authoritative blocker, prerequisite, replacement, and
cross-repository relations. When no authority imposes an order, use the order
in which the Tasks were read and label it `no dependency; stable order`.

## Return the Report

Use this structure:

```markdown
# Task Execution Profile Report: <Story or ticket>

## Authority snapshot
- Source, revision, state, and relations
- Documents and code inspected
- Missing or conflicting authority

## Recommendations

| Task | Scope summary | Execution profile | Why not lower | Confidence |
|---|---|---|---|---|
| AB#... | ... | terra-medium | ... | high |

## Task analysis

### AB#... — <title>
- Evidence and complexity signals:
- Execution profile:
- Why this is the lowest-cost reliable profile:
- Escalation triggers:
- Unknowns:

## Execution plan

1. AB#... — dependency or ordering reason
2. AB#... — dependency or ordering reason

## Cost and sequencing summary
- Tasks by execution profile:
- Recommended execution order when authority defines one:
- Conditions that require re-planning:

This report is planning guidance only. Before implementing each Task, re-read
its current revision, relations, repository state, and relevant code. If they
conflict with this report, current authority and code win.
```

Keep reasons specific and compact. Avoid generic claims such as “complex task”
without naming the coupling, ambiguity, or failure mode.
