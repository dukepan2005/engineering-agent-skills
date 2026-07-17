---
name: task-model-planner
description: Analyze a Story, ticket, or implementation specification and produce a source-backed report recommending an implementation model and thinking level for each Task. Use when the user asks which model, reasoning effort, or cost-aware execution profile should implement a Story's child Tasks or a set of tickets.
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

## Choose the Model

Choose only between `gpt-5.6-terra` and `gpt-5.6-sol`.

- Choose `gpt-5.6-terra` for bounded, well-specified, localized, repetitive, or
  mechanical work with clear verification.
- Choose `gpt-5.6-sol` for cross-module or cross-repository contracts,
  architecture decisions, concurrency, lifecycle, migrations, compatibility,
  security, data integrity, deletion or cutover work, or material ambiguity.

Do not assign a stronger model merely because a Task is large. Base the choice
on reasoning risk, coupling, reversibility, and the quality of the specification.

## Choose the Thinking Level

Recommend the lowest level that is likely to complete the Task reliably:

- `medium`: Clear acceptance criteria, narrow surface, established pattern, and
  focused verification.
- `high`: Normal non-trivial implementation, multiple coordinated files, or
  moderate edge-case analysis.
- `xhigh`: Concrete architectural ambiguity, concurrency or ordering hazards,
  compatibility or migration risk, cross-repository coordination, or difficult
  negative-path reasoning.

Do not recommend `max` as an initial assignment. List it only as a later
escalation option when a specific blocker remains after current authority and
code have been re-read. Prefer changing from Terra to Sol before escalating to
`max`.

## Explain Every Recommendation

For each Task:

1. Cite the scope and risk signals that drive the choice.
2. Give one primary recommendation, not a menu.
3. Explain why a cheaper model or lower level is insufficient when recommending
   Sol or `xhigh`.
4. Give concrete escalation triggers that can be checked during implementation.
5. Assign confidence as `high`, `medium`, or `low`, based on source completeness.

Keep sequencing separate from model selection. Different Tasks under one Story
may use different profiles.

## Return the Report

Use this structure:

```markdown
# Task Implementation Model Report: <Story or ticket>

## Authority snapshot
- Source, revision, state, and relations
- Documents and code inspected
- Missing or conflicting authority

## Recommendations

| Task | Scope summary | Model | Thinking level | Primary reason | Confidence |
|---|---|---|---|---|---|
| AB#... | ... | gpt-5.6-terra | high | ... | high |

## Task analysis

### AB#... — <title>
- Evidence and complexity signals:
- Recommended profile:
- Why this is the lowest reliable profile:
- Escalation triggers:
- Unknowns:

## Cost and sequencing summary
- Tasks suitable for Terra:
- Tasks requiring Sol:
- Recommended execution order when authority defines one:
- Conditions that require re-planning:

This report is planning guidance only. Before implementing each Task, re-read
its current revision, relations, repository state, and relevant code. If they
conflict with this report, current authority and code win.
```

Keep reasons specific and compact. Avoid generic claims such as “complex task”
without naming the coupling, ambiguity, or failure mode.
