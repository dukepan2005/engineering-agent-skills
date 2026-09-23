---
name: azure-task-orchestrator
description: Plan and deliver implementation-ready Azure DevOps Boards work items under a Story or in an explicit item set, in dependency order. Use when the user wants the task-model-planner skill to choose a built-in or caller-supplied execution candidate for each item, then wants the parent orchestrator to control implementation, flat two-axis review, repair, and closeout workers with that exact candidate.
---

# Azure Task Orchestrator

Create one read-only execution-candidate plan, validate it, obtain the user's
confirmation, then deliver exactly one Azure work item at a time. The parent
orchestrator owns the delivery control plane: it directly starts the
implementation worker, both read-only review-axis workers, any repair worker,
and the Boards closeout worker. It does not edit code or author review
findings itself. No implementation or review worker may spawn another worker.

Users may naturally ask to consider another model and reasoning strength for
this run, for example: “Also consider another model supported by this platform
at high reasoning effort; first verify it can be dispatched, then let the plan
decide whether it fits the work.” No structured parameter block is required.
If the user does not ask for extra choices, use the built-in profiles only.

Represent any requested choices internally as an optional
`additional_candidates` list. Candidates apply to the current host, so do not
ask the user to specify a host. The model and effort must be an exact pair
supported by that host; do not infer aliases or translate effort names. These
candidates are temporary for this invocation and never modify the canonical
profile registry. They add implementation choices only; helper agent profiles
remain unchanged.

## Require Skills and Spawn Control Before Work

**REQUIRED SKILLS:** Use `$task-model-planner`, `$azure-task-implement`, and
`$azure-devops-boards-skill`.

Invoke each dependency by Skill name and let the host resolve its enabled Skill
catalog. Do not require the user to provide an installation path or paste a
Skill body. If the host reports a required Skill as unavailable, stop before
reading tracker data, code, or Git state and report that missing Skill.

Also require a parent-level spawn primitive that accepts an explicit model and
its supported reasoning effort, can launch two review workers in parallel,
and returns their results to this conversation. Boards children use the semantic
`task-boards-ops` role defined by `$azure-devops-boards-skill`; no named-agent
configuration is required. The capability must be available in the parent;
do not rely on a child inheriting a spawn tool.

On Codex/ChatGPT, the parent uses `spawn_agent` with `model` and
`reasoning_effort` for every implementation or repair child and for both
review-axis children. On Claude Code, the bare `Agent` tool cannot set reasoning effort
explicitly, so profiled children must be started through the delivery
`Workflow` script's `agent(prompt, {model, effort, label})` calls. The Workflow
has no pause point for user input and must call those agents itself; neither an implementation child nor a review
child may call `Agent`, `Workflow`, or another spawn primitive. On Cursor, use
its equivalent only when the parent can set the exact model and supported
effort from the registry or a validated run-scoped candidate (omit effort for
models with no effort setting) and collect the
parallel review results. On any other host, use its equivalent only when the
parent can set the exact built-in or validated candidate configuration and
collect those results. Stop
without reading or changing code, Git state, or Azure Boards if the parent
cannot provide this flat dispatch capability. Do not silently run the work item
in the parent agent or fall back to the parent's profile.

## Freeze Tracker Connection Before Spawning Boards Children

Before the planning snapshot, resolve the current workspace's documented
tracker connection into one explicit `trackerConnection` object:

```text
{ organization: <organization>, project: <project>, team: <team> }
```

Read the repository tracker guidance once in the parent, or accept this object
from the caller. Require non-empty `organization` and `project`; require `team`
only when resolving a current Sprint. If the documented configuration cannot be
resolved unambiguously, return `Input not ready` before spawning a Boards child.
Do not make children search repository documentation or rely on
`AZURE_DEVOPS_*` environment variables.

Pass `--organization <organization> --project <project>` explicitly on every
Boards command. Pass `--team <team>` only to `current-sprint` or a create flow
that resolves the current Sprint. The values are project input, never literals
embedded in this reusable skill.

## Host-specific Helper-Agent Profiles

Use the matching profile for planning snapshot, preflight, flat-review, and
closeout helper agents:

- Codex/ChatGPT: prefer GPT-6 Luna with `reasoning_effort=high`; if it cannot
  be spawned, use GPT-6 Sol with `reasoning_effort=medium`.
- Claude Code: use `haiku` with `effort: 'low'` for these bounded helper roles.
- Cursor: use `composer2.5` and leave reasoning effort unset.

The chosen host-specific helper profile applies at every helper stage below.

## Validate Optional Run-Scoped Candidates

If `additional_candidates` is omitted or empty, use only the current host's
entries in the canonical execution-profile registry. Otherwise, before asking
the planner to choose an implementation profile:

1. Identify the current host and validate every candidate against its
   authoritative model/effort availability list and child-spawn interface.
   Confirm that the exact pair can be dispatched; `unset` is valid only when
   the host exposes no effort setting for that model. For a host whose spawn
   interface encodes effort into a model slug, verify that exact host mapping
   without changing the candidate's meaning. Use read-only capability
   information; do not launch a test child before the plan is confirmed.
2. Reject the input before tracker reads if a candidate is incomplete,
   ambiguous, duplicated within the input, unsupported, or cannot be verified.
   If a supplied pair exactly matches a built-in profile for this host, resolve
   it to that built-in profile ID. Do not silently drop other candidates or
   substitute another model/effort.
3. Assign each remaining accepted candidate a stable, invocation-local ID such
   as `additional-1`, preserving input order. Pass the complete
   ID-to-model/effort mapping to `$task-model-planner`; it may choose from these
   candidates and the built-in profiles for the current host. The required
   official model/host documentation and benchmark evidence rules still apply
   to additional candidates.

Only built-in profile IDs have registry-defined capacity fallbacks or review
recovery mappings. A pair matching a built-in entry is resolved to that
built-in ID; every other additional candidate has neither. If a dynamically
selected candidate is rejected before starting, or later needs review
escalation with no registry mapping, stop and request replanning; do not infer
a fallback or recovery profile.

## Planning Snapshot — spawn task-boards-ops

Before invoking `$task-model-planner`, the parent orchestrator must obtain one
authoritative read-only snapshot through a direct `task-boards-ops` child.

Create one new, run-scoped temporary directory on a filesystem shared by the
parent and its Boards child. Reserve absolute paths `<tmpsnapshot>` and
`<tmpcomposite>` inside it. Do not reuse a caller-supplied path or place these
artifacts in the repository. The directory contains full tracker data, so the
parent must delete it after planning succeeds or stops; do not retain it while
waiting for plan confirmation.

Use the shared host-specific helper-agent profile above. On Claude Code, use
one `Workflow` call whose script makes exactly one
`agent(prompt, {model: 'haiku', effort: 'low'})` call. On Cursor, spawn one
child with model `composer2.5` and no effort field. This snapshot step runs
in the main loop, before the user confirms the plan, so use a single-child
`Workflow` call here rather than folding it into the post-confirmation flat
delivery `Workflow` described in **Flat delivery control plane**. Give it the Story or explicit
work-item set and this self-contained instruction:

```text
Use `$azure-devops-boards-skill` in its semantic `task-boards-ops` role. For a
Story, run `planning-snapshot --organization <organization> --project <project>
--story <story-id>` once. The Story's state does
not gate this read-only snapshot; the server-side query must select only its direct New Task and Bug children,
then write one JSON snapshot containing the Story and every selected target to
`<tmpsnapshot>`. Do not read a non-New child. For an explicit set, run
`planning-snapshot --organization <organization> --project <project> --id <id>
--id <id>` once for the requested Task/Bug set;
preserve the supplied order and do not invent a parent. For either Story or
explicit-set form, redirect the stdout of that one helper invocation unchanged to `<tmpsnapshot>` (for example,
`> "<tmpsnapshot>"`); do not return the snapshot JSON in a tool result or final
response, because a full snapshot can exceed host transport limits. After the
helper exits successfully, validate the exact file with
`jq -e . "<tmpsnapshot>"`, measure its byte count, and calculate its SHA-256.
Return only one compact JSON manifest with the exact path, byte count, SHA-256,
source kind/id, and ordered target IDs. If writing, validation, or manifest
construction fails, return an error and do not substitute a summary. For every included item
retain all fields, multiline formats, raw and
normalized relations, attachments, linked references, full comments/discussion,
and type-specific scope fields when Description is absent. Linked references
are raw attachment/hyperlink relations, not specification document bodies; the
parent must merge accepted linked specification documents from the upstream
planning authority before invoking the planner. For Bugs, preserve fields such as `Microsoft.VSTS.TCM.ReproSteps` and
`Microsoft.VSTS.TCM.SystemInfo` when they are populated, but do not discard
their comments when those fields are empty: many ticket-creation flows put
reproduction evidence in Discussion instead. `discussion.comments` comes from
the paginated Comments API and is not a synonym for full revision history. Do
not spawn another child or perform non-Boards work. Bug Repro Steps and System
Info may use Markdown; preserve their raw stored value and corresponding
`multilineFieldsFormat` metadata without converting either format.
```

One Boards child may make the helper calls needed to build this single snapshot;
never spawn one Boards child per ticket. Relations to excluded work items are
dependency context only, not planner targets.

Before invoking the planner, the parent must validate that the returned manifest
matches the reserved path; the file exists; `jq -e .` succeeds; and the measured
byte count and SHA-256 match the manifest. It must parse the file itself to
verify source kind/id and ordered target IDs before treating it as authoritative.
Then merge accepted linked specification documents without rewriting the Boards
JSON, write the composite snapshot to `<tmpcomposite>`, validate it as JSON,
and provide that file plus its verified digest to `$task-model-planner`. Do not
inline an oversized snapshot in a child prompt or tool result.

If the snapshot child fails, returns an incomplete/invalid manifest, the file
validation fails, or the snapshot is incomplete, stop before invoking the
planner. The parent may use the Boards Skill's documented fallback only when
the parent itself cannot spawn this direct Boards child.

## Build and Validate the Plan

1. In the parent agent's current context, invoke `$task-model-planner` with the
   validated composite snapshot file from the previous step and, when present,
   the validated candidates as `{candidate_id, model, reasoning_effort}`
   entries. Read the complete file as the
   provided authority, not Azure Boards. The composite preserves
   the original Boards JSON and adds a `linkedSpecifications` collection with one
   `{reference, material, content}` decision per raw linked reference. A
   material specification must have non-empty full Markdown `content`. Treat
   the planner's report as guidance, not tracker authority.
2. Read `$task-model-planner`'s canonical execution-profile registry. Resolve
   built-in profile IDs from that registry and `additional-*` candidate IDs
   only from the validated invocation-local map; do not reproduce or override
   the built-in mapping here.
3. Accept both Task and Bug targets in the snapshot. Reject an explicit target
   of any other Azure type at the Boards snapshot boundary; do not convert its
   type or silently substitute another item.
4. Require a recommendation row and an execution-plan entry for every target
   work item, with each item appearing exactly once in each list.
5. Accept only an exact built-in profile ID from the canonical registry or an
   exact `additional-*` ID from the validated invocation-local map. Reject a
   report that uses free-form model/effort fields, an unknown ID, or a
   candidate whose resolved values differ from the verified mapping.
6. Require the execution-plan work-item set to exactly match the recommendation
   table. Preserve its listed order; never reorder by model, cost, or title.
7. Stop before dispatching any worker if the report is missing, ambiguous,
   stale against a user-reported scope change, or contains an unsupported
   candidate. Report the mismatch and request a corrected plan. Do not infer an
   order or candidate from report prose.
8. Preserve each item's source-backed model-selection rationale and ordering
   explanation as `plannerEvidence` and `orderReason` in the validated delivery
   entry. The worker must receive those with the exact candidate mapping.

## Confirm the Validated Plan

Before spawning any worker, present the complete validated plan in its planned
order. For every work item, include its ID, type, title, planned candidate ID,
resolved model and supported reasoning effort (or `unset` when the model has
no effort setting), and order reason. For a built-in profile, include the
pre-start capacity fallback profile if one exists; for an additional candidate,
show that no fallback is defined. Claude Code and Cursor have no built-in
pre-start fallback, so omit that column there.
State that confirmation authorizes sequential delivery, including code changes,
one commit per successful work item, and Azure Boards closeout.

Wait for an explicit user confirmation of that displayed plan, for example
`确认执行该计划` or `confirm this plan`. Do not treat a prior approval, an
unrelated `ok`, silence, or a request to inspect the plan as confirmation. Do
not spawn a worker, modify code or Git state, or mutate Azure Boards while
waiting.

If the user changes a work item's scope, order, or candidate before confirming,
invalidate the plan and return to **Build and Validate the Plan**. A changed
plan requires a newly displayed plan and new confirmation.

## Flat delivery control plane

For each work item in the validated execution plan, run the stages below in
order. Only one work item may be active at a time. The parent starts every
child directly; no child may start another child.

| Stage | Parent-started children | Child responsibility |
| --- | --- | --- |
| Preflight | one cheap Boards child | read-only tracker snapshot |
| Implement | one planned-candidate child | implementation, tests, task commit |
| Review round | two parallel read-only children | Standards axis and Spec axis |
| Repair | one same-candidate child, only when findings exist | amend the same task commit and rerun verification |
| Final review | two parallel read-only children | verify the repaired delta |
| Recovery | one mapped stronger-profile child, only for blocking final findings | repair the existing delta; no review dispatch |
| Closeout | one cheap Boards child | evidence-backed Description update and close |

Use [references/flat-review-worker.md](references/flat-review-worker.md) as the
worker contract for both review axes. The parent may validate and aggregate
the returned JSON, but must not inspect the code itself to author findings or
silently downgrade a review result.

On Claude Code, this entire post-confirmation loop runs as one `Workflow`
script. Pass `validatedPlan` entries with `plannedCandidate`, `plannerEvidence`,
and `orderReason`, plus the validated invocation-local map as
`additionalCandidates` when present. The
script resolves built-in IDs from its registry and additional IDs only from
that map. It calls `agent()` directly for every child, uses
`Promise.all` for each pair of review axes, and never asks an implementation or
review child to call `Agent` or `Workflow`. On Codex/ChatGPT, the main
conversation uses `spawn_agent` directly for the same sequence. On Cursor, use
its parent-level dispatch equivalent for the same sequence when the capability
preflight above succeeds. See
[references/claude-code-delivery-loop.js](references/claude-code-delivery-loop.js)
for the complete template.

### 1. Preflight — spawn helper agent

Use the shared host-specific helper-agent profile above. On Claude Code, use
`agent(prompt, {model: 'haiku', effort: 'low'})`; on Cursor, use model
`composer2.5` without an effort field. Give it the work-item ID and this
self-contained instruction:

```text
Use `$azure-devops-boards-skill` in its semantic `task-boards-ops` role. Run
`implement-preflight --organization <organization> --project <project> --id
<id>` and return the JSON output unchanged. Do not perform any non-Boards work.
```

The preflight JSON must retain all fields, multiline formats, attachments, and
full comments/discussion in addition to the type-neutral scope summary; a Bug
without `System.Description` is scoped from its type-specific fields (including
Repro Steps/System Info when present) plus Discussion comments when those
fields are empty. The optional full revision/update stream is not required for
the planner's current-scope authority.

Collect the preflight result. If the spawn fails or the agent returns an error
(no such item, wrong state, blocked by a relation), stop immediately. Do not
proceed to the implement step.

### 2. Implement — spawn candidate-selected agent

Resolve the work item's planned candidate ID through either the canonical
registry or the validated invocation-local map for the current host. On
Codex/ChatGPT, call
`spawn_agent` with its exact `model` and `reasoning_effort`, and a normalized
`task_name` containing
the work-item ID and planned candidate, for example
`delivery_sol_xhigh_ab_175`. The name is only a task label; it does not select a
custom agent configuration. For an additional candidate, pass its exact
validated model/effort pair; omit the effort field when it is `unset`. On
Claude Code, call the `Workflow` script's
`agent(prompt, {model, effort, label})` with the exact resolved mapping, also
omitting `effort` when it is `unset`. On
Cursor, use the host's exact spawn representation for that validated pair;
omit effort only when it is `unset`. Include a label or task name containing
the work-item ID and candidate ID.

If the host rejects that spawn before the worker starts and explicitly reports
the requested reasoning effort or capacity as unavailable, read the planned
profile's `Pre-start capacity fallback` from the canonical registry. This
fallback applies only to a built-in profile with a defined mapping. An
additional candidate has no fallback and must stop on rejection. The fallback
column exists for Codex/ChatGPT only. Claude Code has no pre-start
capacity error signal, and Cursor defines no pre-start fallback, so either
host stops immediately on a rejected spawn. On Codex/ChatGPT, when the fallback
has a value, retry exactly once with that profile's exact mapping and a new
`task_name`. Record
both candidate IDs and the host error. If it has no value, the error is
model-wide availability, the error is not recognizable, or the retry fails,
stop the sequence. Do not retry after a worker begins, across models, or for a
work-item-level failure.

Give the worker its work-item ID and type, planned candidate ID, effective
candidate ID and exact model/effort mapping, relevant planner evidence and
order reason, and the preflight scope from step 1, plus this instruction:

```text
Use `$azure-task-implement` with `reviewOwner=parent` to implement work item
<id> in the current workspace and branch. The preflight scope is provided
below. Re-read repository authority; the planner is not a substitute for repo
guidance. The effective execution candidate is fixed for this worker. Do not
perform Azure Boards operations, invoke `$code-review`, or spawn any child.

Return JSON with `outcome` set to `ready_for_review` only after implementation,
verification, the task-only commit, and the acceptance-evidence table are
complete. Include `reviewBase`/`taskStartCommit`, `commit`, changed areas,
verification evidence, remaining work, and map every supplied acceptance
criterion to concrete evidence or state that it was not verified. If
implementation or verification fails, return `implementation_failed` with the
concrete blocker; do not claim review or closeout readiness.

<preflight scope JSON>
```

Require the worker to finish before inspecting its result. Validate that the
result is `ready_for_review`, that `reviewBase` and `taskStartCommit` match,
that the commit exists, and that the acceptance-evidence table is present.
Keep the shared workspace untouched while a worker runs. On failure,
incomplete verification, an uncommitted result, a blocker, or an uncertain
outcome, stop immediately. Do not dispatch later work items.

### 3. Review and repair — parent owns flat review dispatch

For each review round, the parent starts two read-only children in parallel,
one with `reviewAxis=standards` and one with `reviewAxis=spec`, using the exact
`reviewBase` and current task commit returned by the implementation worker.
Give both workers the work-item scope, acceptance evidence, and
[the flat worker contract](references/flat-review-worker.md). They must return
the contract's JSON without editing code, Git, Boards, or spawning children.
Use the shared host-specific helper-agent profile above; on Claude Code use
`agent(prompt, {model: 'haiku', effort: 'low', label})` for both axes. On
Cursor, use `composer2.5` without an effort field for both axes.

Validate both axis labels, the fixed point, and the non-empty diff before
aggregating. A malformed or mismatched review result is a failed review, not a
clean result. The parent may combine the reports and pass them to a repair
worker, but must not author findings or change the code itself.

Run a first review round immediately after implementation. If it contains any
actionable finding, spawn one repair worker at the same effective candidate with
`reviewOwner=parent`, the original preflight scope, `reviewBase`, current task
commit, and both complete review reports. Require it to repair the existing
delta, rerun verification, and amend the same task commit; it must not invoke
`$code-review`, spawn a child, create a second task commit, or perform Boards
operations. If the repair fails, stop. Whether or not repair was needed, run a
second pair of review workers against the resulting `reviewBase...HEAD` delta.

If the second review has no blocking finding, the parent may mark the item
`ready_for_closeout` while retaining both axis reports and any non-blocking
findings in the delivery evidence. A blocking finding is P0/P1 or an explicitly
blocking correctness, security, data-loss, or verification problem. Do not
close the item or dispatch the next item while the second review is malformed
or unresolved.

### Review Escalation

If the second flat review still has a blocking finding, do not run closeout or
dispatch the next work item. Use the single post-fix recovery profile mapped
for the current host in the canonical execution-profile registry. Do not
duplicate or infer that mapping here; if the selected candidate is additional
and has no exact registry mapping, report recovery as unavailable.

Spawn exactly one recovery worker at that higher profile with the same work-item
scope, the unresolved findings, and the current workspace. It must use
`$azure-task-implement` with `reviewOwner=parent`, repair the existing task
delta, rerun verification, and amend the same task commit. It must not invoke
`$code-review`, spawn a child, or perform Boards operations. After recovery,
the parent starts exactly one more pair of flat review workers. Record planned,
initial effective, and recovery profiles. A host that cannot resolve its mapped
profile must report `review_escalation_unavailable`; it must not substitute
another profile. Do not auto-select an `xhigh` profile. Do not retry a second
recovery worker, close the item, or dispatch later work while recovery is
unresolved. If no mapped recovery profile is available, the
recovery worker fails, or its final flat review still has a blocking finding,
return `review_escalation_required` with the concrete findings and stop for
human replanning.

### 4. Closeout — spawn helper agent

Use the shared host-specific helper-agent profile above. On Claude Code, use
`agent(prompt, {model: 'haiku', effort: 'low'})`; on Cursor, use
`composer2.5` without an effort field.

Closeout policy (apply before spawning):
- The parent (or a standalone closeout agent) must map every Acceptance
  criterion to current-code evidence: file/type/function, plus the required
  test seam when the AC asks for one. That mapping is the only explicit current-code implementation evidence
  that may check an item. An implementation summary, commit title, PR merge,
  or “tests passed” claim is not enough.
- Read the current full Description and preserve its non-checklist content and
  formatting. Mark an unchecked Markdown checklist item as checked only when
  that code mapping exists and matches the criterion text. Do not infer
  evidence from the item's final state, commit title, or a general success
  claim.
- If an unchecked checklist item lacks code evidence, or its text cannot
  be mapped unambiguously to a concrete implementation, stop without
  closing the item. Do not overwrite the Description or post a completion
  comment.
- Write the resulting Description to a temporary Markdown file and write a
  completion comment from the code-vs-AC mapping to another temporary
  Markdown file.
- Close the work item to `Closed`: pass `--state Closed`. If repository guidance
  names a different terminal state for a non-Task type, use that stated value.
- Pass the rewritten Description with `--description-file`; do not combine it
  with `--check-ac` because those options are mutually exclusive.
- Always pass `--expected-rev` (the preflight revision from step 1). It binds
  the Description read and final mutation to the same work-item version; a
  stale revision stops the closeout.

Give the agent the work-item ID, the preflight revision from step 1, the
code-vs-AC mapping, and this self-contained instruction:

```text
Use `$azure-devops-boards-skill` in its semantic `task-boards-ops` role. Read
the current full Description with `show --organization <organization> --project
<project> --full --id <id>`. Apply only the evidence-backed Markdown checklist
changes specified by the parent code-vs-AC mapping, preserving all other
Description content. Write the rewritten Description to `<tmpdescription>` and
a Markdown completion comment to `<tmpcomment>`. Then run `close-task --apply
--organization <organization> --project <project> --id <id> --expected-rev
<rev> --state Closed --description-file <tmpdescription> --comment-file
<tmpcomment>`.
Return the JSON output unchanged. Do not use `--check-ac`, and do not perform
any non-Boards work.
```

Collect the closeout result. If the closeout fails because the expected rev is
stale, stop immediately; do not retry automatically. The work item changed
since preflight, so the current item must be re-preflighted and the
implementation result reconciled before closeout is attempted again. Do not
proceed to the next work item.

Dispatch the next work item only after implementation, every required flat
review/repair stage, and closeout complete successfully.

## Report

Return one ordered summary. For every completed work item, include the planned
and effective execution candidate IDs and exact model/effort mapping, any
pre-start capacity fallback error (Codex/ChatGPT only), `reviewBase`, worker-reported commit and verification, both
review-round axis reports, any repair/recovery profile, final tracker state,
and closeout result. For a stopped run, identify the work item and stage that
stopped the sequence, retain earlier completed results, and state that later
work items were not dispatched.
