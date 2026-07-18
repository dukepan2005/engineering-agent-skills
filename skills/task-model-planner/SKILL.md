---
name: task-model-planner
description: Analyze agent-ready Azure Tasks produced after /grill-with-docs, /to-spec, and /to-tickets, then recommend one source-backed execution profile for each Task. Use when the user asks which model profile, reasoning effort, or cost-aware execution configuration should implement a Story's child Tasks or an explicit Task set.
---

# Task Model Planner

Produce a read-only implementation model plan. Do not implement or mutate the
tracker.

## Establish the Work Set

1. Read the nearest `AGENTS.md` and every repository guidance file it requires.
2. Read the current authoritative Story or Task, including revision, state,
   acceptance criteria, relations, comments, attachments, and linked
   specification documents that affect scope.
3. For a Story, analyze each directly related child Task separately. For a Task
   set, analyze only the explicitly named items.
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

## Verify Planning Readiness

Treat `/grill-with-docs`, `/to-spec`, and `/to-tickets` as the required
upstream workflow. Before choosing any profile, verify that:

- the accepted decisions are recorded in the authoritative Story description
  or a linked implementation specification;
- every Task traces to that planning authority and has bounded scope, acceptance
  criteria, and focused verification requirements;
- prerequisite, blocker, replacement, and cross-repository relations are
  present when the specification requires them;
- the specification, Tasks, current tracker state, and any inspected current
  code do not materially conflict.

If an artifact is missing or materially inconsistent, return an
`Input not ready` report listing the affected Tasks and evidence, then stop
without recommending profiles. Do not compensate for an incomplete planning
workflow by selecting Sol or a higher reasoning effort.

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
merely because a Task is large or crosses a module, contract, lifecycle stage,
or repository.

Classify only residual implementation uncertainty that remains after the
upstream design and decomposition workflow. Do not charge again for decisions,
scope, coupling, or ordering already resolved by the specification and Task
graph.

For each ready Task, assess only source-backed evidence:

- Residual judgment: must the implementer still choose product semantics,
  ownership, architecture, lifecycle behavior, or a boundary contract?
- Coordination: do independently verifiable changes follow an established
  contract, or must one invariant remain correct across boundaries?
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

Choose the model family and reasoning effort independently. Use these four
profiles for regular planning:

- `terra-medium`: decisions are resolved and execution is straightforward or
  mechanical;
- `terra-high`: decisions are resolved but implementation retains a material
  reasoning hazard or several interdependent changes;
- `sol-medium`: material residual judgment remains, but the decision is bounded
  and no deep implementation hazard is present;
- `sol-high`: residual judgment and deep implementation reasoning are both
  required.

Treat `terra-high` and `sol-medium` as the two primary profiles for agent-ready
Tasks. Use `terra-medium` for genuinely straightforward work and `sol-high` for
the compounded case.

Use this regular escalation order:

`terra-medium` → `terra-high` → `sol-medium` → `sol-high`

Therefore `sol-medium` is the immediate next regular profile after
`terra-high`. Do not use an `xhigh` profile as part of this regular ladder.

### Choose Terra or Sol

Choose Terra when the specification has already fixed the intended behavior,
ownership, contracts, and rollout semantics, and focused verification makes an
incorrect implementation cheap to detect. This remains true when mechanical or
independently verifiable edits span multiple modules or repositories.

Choose Sol only when source-backed residual judgment remains, such as:

- the specification, Task, current code, or another current authority conflicts;
- the Task explicitly delegates a material product, domain, or architectural
  decision to the implementer;
- the implementation must invent or renegotiate a boundary contract;
- a high-consequence design choice cannot be distinguished reliably by focused
  verification;
- ownership, lifecycle, security, migration, or compatibility semantics remain
  unresolved.

Treat cross-boundary scope as a prompt to inspect the seam, never as a Sol
trigger by itself.

### Choose Reasoning Effort

Use `medium` when the reasoning path is bounded, feedback is strong, and no
material non-local invariant must remain correct across many steps. Select
`terra-medium` only for mechanical or straightforward execution after the
specification has resolved all material decisions.

Use `high` when one material reasoning hazard or several interdependent
implementation decisions remain, including concurrency, ordering, lifecycle,
retry/idempotency, a coordinated migration or compatibility transition,
non-local invariants, or repeated hypothesis-and-test loops. Select `sol-high`
only when this deeper implementation reasoning combines with a Sol judgment
gate.

Use `xhigh` only when all of these gates are evidenced:

1. The Task requires a genuinely long reasoning horizon, such as many
   interdependent tool loops, large-context synthesis, or repeated hypothesis
   testing.
2. A severe hazard remains, such as weakly observable concurrency/ordering,
   irreversible migration/cutover, independently deployed compatibility, or
   another high-consequence non-local invariant.
3. Verification is weak or rollback is difficult, or representative evaluations
   of this Task class show a material benefit over `high`.

Otherwise cap the initial effort at `high`. Treat `sol-high` as a compounded
case, not the default Sol profile, and treat every `xhigh` profile as
exceptional. Do not invent profiles, and do not recommend `max` as an initial
profile.

## Explain Every Recommendation

For each Task:

1. Cite the scope and risk signals that drive the choice.
2. Give one primary recommendation, not a menu.
3. Name the exact gate that disqualifies the next lower-cost profile. If no gate
   is evidenced, choose the lower profile.
4. Give concrete escalation triggers that can be checked during implementation.
5. Assign confidence as `high`, `medium`, or `low`, based on source completeness.

Keep sequencing separate from profile selection. Different Tasks under one Story
may use different profiles.

After the readiness gate passes, return every planned Task exactly once in
execution order. Derive the order from authoritative blocker, prerequisite,
replacement, and cross-repository relations. When no authority imposes an
order, use the order in which the Tasks were read and label it
`no dependency; stable order`.

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
