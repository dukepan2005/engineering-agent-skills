---
name: task-model-planner
description: Analyze a parent-provided Azure work-item snapshot produced after the grill-with-docs, to-spec, and to-tickets skills, then recommend one source-backed execution candidate for each item. Use when the user asks which model profile, reasoning effort, or cost-aware execution configuration should implement a Story's child items or an explicit work-item set, including Tasks and Bugs.
---

# Task Model Planner

Produce a read-only implementation model plan. Do not implement or mutate the
tracker.

## Establish the Work Set

1. Require an authoritative tracker snapshot from the parent. It may be provided
   inline when bounded, or as a parent-validated JSON file in a filesystem shared
   with this planner. For a file, require its exact path plus verified byte count
   and SHA-256, read the complete file, and treat a missing, invalid, or digest-
   mismatched file as `Input not ready`. A file supplied by the parent is scope
   input, not permission to read Azure Boards. The snapshot must include
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
3. Analyze each target item explicitly supplied in the snapshot, regardless of
   its current state. When the upstream orchestrator starts from a Story, it
   may provide only direct New Task/Bug children; that is an orchestration
   work-set decision, not a planner validation rule. For an explicit work-item
   set, analyze every named Task or Bug, including Active or Closed items.
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

## Verify Model and Evaluation Evidence

Before recommending a profile, consult both required source types using the
latest information available on the planning date:

1. **Official model documentation.** Check the provider's current model
   documentation and, when using a host such as Claude Code or Cursor, that
   host's current model/effort availability documentation. Confirm the model or
   alias, supported reasoning efforts, and host-specific limits. The
   execution-profile registry remains the source of built-in mappings for this
   workflow; provider API options alone do not establish that a model/effort
   pair is available through the active host's child-spawn interface. The
   parent may supply separately validated run-scoped candidates.
2. **Benchmark reports.** Read the latest relevant report for coding, agentic
   coding, or the work item's closest task category. Prefer results for the
   exact model version, reasoning effort, and agent/harness in use. Consult an
   independent, reproducible evaluation when one is available; vendor-published
   reports are useful but must be identified as vendor-reported. Use the
   original report or benchmark maintainer's results and methodology; secondary
   summaries may help locate a source but are not evidence by themselves.

Supplement these sources with model/system cards and release notes, benchmark
methodology or leaderboard documentation, and representative project-level
blind evaluations or delivery-history measurements when available. These help
interpret the required sources; they do not replace them.

For every benchmark result used, capture the report date and direct source, the
exact model/version and effort, benchmark and revision, harness/tool access, and
any reported sample size or uncertainty. Note whether comparisons use the same
harness, self-reported results, or an independent evaluator. Benchmark results
describe the tested setup, not a universal model ranking or a substitute for the
work-item risk and verification analysis below. Do not infer a model or effort
ranking from names, version numbers, or a single score.

When using benchmark evidence to claim that a stronger model or effort is worth
selecting over a lower-cost option, prefer a matched comparison on the same task
set, harness, and tool access. For an effort-level claim, compare effort levels
of the same model under matched conditions. If the report does not provide that
comparison, state that the performance benefit is unverified.

If no report covers the exact current model/configuration, state that plainly.
You may cite the closest relevant report as a proxy, but label the mismatch and
do not make an exact-model or cross-model performance claim from it. Never
present a report for an older model version as evidence for a newer one. If the
official docs or active host show that a registry profile is unavailable or
resolve it to a materially different model/effort, do not invent a profile or
silently substitute another; report the discrepancy and stop profile selection
until the approved mapping is resolved.

Apply the same documentation and benchmark checks to every parent-supplied
candidate. An option is not recommended merely because the caller included it.

Use this evidence together with the task's residual uncertainty, failure cost,
and verification strength. Where representative project evaluations or
delivery-history measurements exist, use them as additional evidence for the
project's actual workload; do not let general benchmark scores override them.

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

## Choose the Execution Candidate

Read [the canonical execution-profile registry](references/execution-profiles.md)
before selecting a candidate. The parent may optionally provide an
`additional_candidates` list for this invocation. Each entry has a parent-
assigned invocation-local `candidate_id` (such as `additional-1`), the exact
model identifier, and `reasoning_effort` supported by the current host (or
`unset` when the model has no effort setting). The parent must verify that the
pair is spawnable on the current host before passing it to the planner. If no
list is supplied, use only the built-in execution-profile IDs for the current
host. Never invent candidate IDs or model/effort combinations. Output only the
selected candidate ID, not a free-form model/effort pair; the parent resolves
built-in IDs from the registry and additional IDs from its validated map.
Additional candidates expand the eligible choice set; their presence does not
require selecting them or override the source-backed risk and effort rules.

Choose only from the candidate pool for the active host; never transfer a
model/effort choice across hosts. Apply the host-specific guidance below to
evaluate candidates. For a model family not covered by that guidance, rely on
its current official documentation and benchmark evidence without inferring a
ranking from the family name.

For the built-in Codex/ChatGPT candidates, use these regular profiles:

- `luna-high`: decisions are resolved and focused verification can catch a
  wrong implementation; Codex/ChatGPT do not offer a lower Luna effort;
- `sol-medium`: material residual judgment remains, but the decision is bounded
  and no deep implementation hazard is present;
- `sol-high`: residual judgment and deep implementation reasoning are both
  required.

Treat `luna-high` and `sol-medium` as the two primary Codex/ChatGPT profiles
for agent-ready work items. Use `sol-high` when residual judgment and deep
implementation reasoning both remain. Neither primary profile is an automatic
fallback for the other.

For built-in Claude Code candidates, prefer a Sonnet profile when material
decisions are resolved; use Opus when source-backed residual judgment or a
deeper implementation hazard remains. On Cursor, built-in Composer 2.5 has no
effort setting, while Grok 4.6 and 4.7 support `high` and `xhigh`. Consider
additional candidates only when the parent supplied them and verified their
availability. Do not infer a
capability ranking or fallback from model names or version numbers. If neither
a usable built-in profile nor a parent-supplied candidate is available, ask
which one to use. Built-in profile IDs and mappings are defined in the
registry.

Use only built-in profile IDs supported by the current host registry or exact
candidate IDs supplied by the parent; never infer or create an additional
model-and-effort combination.

### Qualified Luna max candidate (Codex/ChatGPT only)

`luna-max` is outside the regular profiles. Choose it only when every condition
below is evidenced:

1. The work is tightly bounded to a clear, repeatable implementation slice;
   its product semantics, ownership, and interfaces are already fixed.
2. It has no cross-repository contract change, migration, security-sensitive
   decision, concurrency/lifecycle hazard, or other material non-local
   invariant.
3. Focused tests or deterministic checks make an incorrect implementation
   quickly observable and cheap to correct.
4. The remaining work still needs a long local reasoning loop, such as dense
   edge-case handling or exhaustive deterministic test construction.

Do not choose `luna-max` merely for cost, ticket size, or multiple files. If a
gate is missing, choose `luna-high`, `sol-medium`, or `sol-high` according to
the evidence. This profile exists only for Codex/ChatGPT; on another host,
select from that host's registry without substituting a different model for it.

### Choose the Model Family

For built-in Codex/ChatGPT choices, choose Luna when the specification has already fixed the
intended behavior, ownership, contracts, and rollout semantics, and focused
verification makes an incorrect implementation cheap to detect. This remains
true when mechanical or independently verifiable edits span multiple modules
or repositories.

For built-in Claude Code choices, choose Sonnet when the specification resolves
material decisions; choose Opus when source-backed residual judgment remains, such as:

- the specification, work item, current code, or another current authority
  conflicts;
- the work item explicitly delegates a material product, domain, or architectural
  decision to the implementer;
- the implementation must invent or renegotiate a boundary contract;
- a high-consequence design choice cannot be distinguished reliably by focused
  verification;
- ownership, lifecycle, security, migration, or compatibility semantics remain
  unresolved.

For built-in Codex/ChatGPT choices, these residual-judgment cases are Sol
triggers. For additional candidates or on Cursor, apply effort only where the
candidate supports it and use current source evidence to evaluate the model.
Treat cross-boundary scope as a prompt to inspect the seam, never as a
model-family trigger by itself.

### Choose Reasoning Effort

For built-in Codex/ChatGPT choices, use `medium` only with Sol. Select
`sol-medium` when residual judgment is bounded, feedback is strong, and no
material non-local invariant must remain correct across many steps. For
built-in Claude Code choices, use the Sonnet or Opus effort listed in the
registry. Built-in Cursor Grok profiles support `high` or `xhigh`; Composer 2.5
has no reasoning-effort setting. For an additional candidate, use only the
effort passed by the parent after host validation.

Use `high` when one material reasoning hazard or several interdependent
implementation decisions remain, including concurrency, ordering, lifecycle,
retry/idempotency, a coordinated migration or compatibility transition,
non-local invariants, or repeated hypothesis-and-test loops. Select
`luna-high` when these hazards remain but the specification has resolved
material judgment; select `sol-high` when deeper implementation reasoning
combines with a Sol judgment gate. Apply the equivalent host-specific model and
effort profiles from the registry on Claude Code and Cursor.

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
case, not the default Sol profile, and treat host-supported `xhigh` profiles as
exceptional. Do not invent profiles. `luna-max` is the only built-in `max`
profile for
Codex/ChatGPT and requires every qualified-Luna gate above; Sol does not offer
`max` on those hosts.

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
# Work Item Execution Candidate Report: <Story or ticket>

## Authority snapshot
- Source, revision, state, and relations
- Documents and code inspected
- Missing or conflicting authority

## Model and evaluation evidence
- Official model and host documentation: title, URL, publication/update date
  or access date, model/alias, supported effort, and relevant limits
- Benchmark reports consulted: title, URL, date, model/version, effort,
  benchmark revision, harness, relevant result, and limitations
- Exact-match status: whether the current host configuration was evaluated;
  identify any proxy or unavailable evidence
- Project-specific evaluations or delivery-history evidence, when available

## Recommendations

| Work item | Scope summary | Execution candidate ID | Why not lower | Confidence |
|---|---|---|---|---|
| AB#... | ... | profile-id or additional-id | ... | high |

## Work-item analysis

### AB#... — <title>
- Evidence and complexity signals:
- Execution candidate ID:
- Why this is the lowest-cost reliable profile:
- Escalation triggers:
- Unknowns:

## Execution plan

1. AB#... — dependency or ordering reason
2. AB#... — dependency or ordering reason

## Cost and sequencing summary
- Work items by execution candidate ID:
- Recommended execution order when authority defines one:
- Conditions that require re-planning:

This report is planning guidance only. Before implementing each work item, the
parent must re-preflight its current revision and relations. If they conflict
with this report, current authority and code win.
```

Keep reasons specific and compact. Avoid generic claims such as “complex task”
without naming the coupling, ambiguity, or failure mode.
