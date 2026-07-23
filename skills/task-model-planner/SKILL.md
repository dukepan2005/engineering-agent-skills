---
name: task-model-planner
description: Analyze a parent-provided Azure work-item snapshot produced after the grill-with-docs, to-spec, and to-tickets skills, then recommend one source-backed execution profile for each item. Use when the user asks which model profile, reasoning effort, or cost-aware execution configuration should implement a Story's child items or an explicit work-item set, including Tasks and Bugs.
---

# Task Model Planner

Produce a read-only implementation model plan. Do not implement or mutate the
tracker.

## Establish the Work Set

1. Require an authoritative tracker snapshot from the parent. It must include
   the requested parent or target items, revisions, states, all fields and
   multiline formats, relations, comments/discussion, attachments, and raw
   linked specification references. When a referenced specification affects
   scope, the parent must also provide its document content in the composite
   snapshot. Each item without Description must include the complete
   type-specific field data returned by Boards, including empty native fields
   when Azure returns them. Missing field data or a stale/incomplete snapshot
   is `Input not ready`; empty Bug fields alone are not incomplete when the
   remaining authorities bound the work. Do not read Azure Boards to fill the
   gap.
2. Read the nearest `AGENTS.md` and every repository guidance file it requires.
3. For a Story, analyze only the direct New Task and Bug children returned in
   the snapshot, each separately. Do not treat a non-New child or a relation
   target outside that set as a planner target. For an explicit work-item set,
   analyze only the named items in the snapshot.
4. Use the snapshot's blocking, prerequisite, replacement, and
   cross-repository relations when they materially affect a recommendation.
5. Inspect current code or tests only when the snapshot and its documents do
   not provide enough evidence to classify complexity. Label any conclusion
   based on incomplete evidence with lower confidence.

Treat the parent-provided snapshot, linked specifications, and current code as
authoritative over earlier plans or summaries. State conflicts instead of
silently resolving them. Do not read Azure Boards or spawn a Boards child.

The Boards snapshot may contain only raw linked references. The parent-provided
composite snapshot must preserve that Boards JSON and add a
`linkedSpecifications` decision for each raw linked reference. Each decision
contains the matching `reference`, a `material` boolean, and full Markdown
`content` when `material` is true. A missing decision, an unmatched reference,
or empty/whitespace-only content for a material specification is `Input not
ready`; do not infer the specification from an attachment URL or relation
metadata.

Description is one possible scope authority, not a universal one. For a Bug or
another item without Description, classify scope and verification from the
snapshot's type-specific fields (for example Repro Steps/System Info),
comments/discussion, linked specification, and relations. If the Bug-specific
fields are empty, Discussion comments may be the actual reproduction evidence;
do not discard them or mark the snapshot incomplete for that reason.
`discussion.comments` is the current paginated Comments API result; it is not
the complete revision history unless a history/revisions payload was explicitly
supplied. Do not return `Input not ready` merely because Description or the
Bug-specific fields are empty; return it only when the combined authorities
cannot bound the work.

## Verify Planning Readiness

Treat the `grill-with-docs`, `to-spec`, and `to-tickets` skills as the required
upstream workflow. Before choosing any profile, verify that:

- the accepted decisions are recorded in the authoritative Story description
  or a linked implementation specification;
- every work item traces to that planning authority and has bounded scope,
  acceptance criteria, and focused verification requirements;
- prerequisite, blocker, replacement, and cross-repository relations are
  present when the specification requires them;
- the specification, snapshot state, and any inspected current
  code do not materially conflict.

If an artifact is missing or materially inconsistent, return an
`Input not ready` report listing the affected work items and evidence, then stop
without recommending profiles. Do not compensate for an incomplete planning
workflow by selecting Sol or a higher reasoning effort.

## Keep the Analysis Read-Only

- Do not edit code, documents, Git state, configuration, or tracker items.
- Do not build, test, migrate, generate, install, commit, push, or use the
  `implement` skill.
- Do not split, rewrite, create, reprioritize, or change the type of work items.
- Record missing information and its effect on confidence.
- Stop after returning the report.

## Classify the Work Item

Choose the lowest-cost profile that has a credible path to meeting acceptance
criteria and focused verification requirements. Do not assign a stronger model
merely because a work item is large or crosses a module, contract, lifecycle
stage, or repository.

Classify only residual implementation uncertainty that remains after the
upstream design and decomposition workflow. Do not charge again for decisions,
scope, coupling, or ordering already resolved by the specification and
work-item graph.

For each ready work item, assess only source-backed evidence:

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
work items. Use `terra-medium` for genuinely straightforward work and
`sol-high` for the compounded case.

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

- the specification, work item, current code, or another current authority
  conflicts;
- the work item explicitly delegates a material product, domain, or architectural
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

1. The work item requires a genuinely long reasoning horizon, such as many
   interdependent tool loops, large-context synthesis, or repeated hypothesis
   testing.
2. A severe hazard remains, such as weakly observable concurrency/ordering,
   irreversible migration/cutover, independently deployed compatibility, or
   another high-consequence non-local invariant.
3. Verification is weak or rollback is difficult, or representative evaluations
   of this work-item class show a material benefit over `high`.

Otherwise cap the initial effort at `high`. Treat `sol-high` as a compounded
case, not the default Sol profile, and treat every `xhigh` profile as
exceptional. Do not invent profiles, and do not recommend `max` as an initial
profile.

## Explain Every Recommendation

For each work item:

1. Cite the scope and risk signals that drive the choice.
2. Give one primary recommendation, not a menu.
3. Name the exact gate that disqualifies the next lower-cost profile. If no gate
   is evidenced, choose the lower profile.
4. Give concrete escalation triggers that can be checked during implementation.
5. Assign confidence as `high`, `medium`, or `low`, based on source completeness.

Keep sequencing separate from profile selection. Different work items under one
Story may use different profiles.

After the readiness gate passes, return every planned work item exactly once in
execution order. Derive the order from authoritative blocker, prerequisite,
replacement, and cross-repository relations. When no authority imposes an
order, use the order in which the work items were read and label it
`no dependency; stable order`.

## Return the Report

Use this structure:

```markdown
# Work Item Execution Profile Report: <Story or ticket>

## Authority snapshot
- Source, revision, state, and relations
- Documents and code inspected
- Missing or conflicting authority

## Recommendations

| Work item | Scope summary | Execution profile | Why not lower | Confidence |
|---|---|---|---|---|
| AB#... | ... | terra-medium | ... | high |

## Work-item analysis

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
- Work items by execution profile:
- Recommended execution order when authority defines one:
- Conditions that require re-planning:

This report is planning guidance only. Before implementing each work item, the
parent must re-preflight its current revision and relations. If they conflict
with this report, current authority and code win.
```

Keep reasons specific and compact. Avoid generic claims such as “complex task”
without naming the coupling, ambiguity, or failure mode.
