---
name: azure-task-orchestrator
description: Plan and deliver implementation-ready Azure DevOps Boards work items under a Story or in an explicit item set, in dependency order. Use when the user wants the task-model-planner skill to choose a named execution profile for each item, then wants each item delivered by the azure-task-implement skill in a sequential subagent with that exact profile.
---

# Azure Task Orchestrator

Create one read-only execution-profile plan, validate it, obtain the user's
confirmation, then run exactly one Azure work-item delivery worker at a time.
Do not implement, review, or close work items in the orchestrator itself.

## Require Skills and Spawn Control Before Work

**REQUIRED SKILLS:** Use `$task-model-planner`, `$azure-task-implement`, and
`$azure-devops-boards-skill`.

Invoke each dependency by Skill name and let the host resolve its enabled Skill
catalog. Do not require the user to provide an installation path or paste a
Skill body. If the host reports a required Skill as unavailable, stop before
reading tracker data, code, or Git state and report that missing Skill.

Also require a subagent spawn primitive that accepts an explicit model and
reasoning effort. Boards children use the semantic `task-boards-ops` role
defined by `$azure-devops-boards-skill`; no named-agent configuration is
required.

On Codex, use `spawn_agent` with `model` and `reasoning_effort` for every
profiled child. On Claude Code, the bare `Agent` tool cannot set reasoning
effort explicitly, so a profiled child must be spawned through a `Workflow`
script's `agent(prompt, {model, effort})` call instead. A `Workflow` script
runs as one asynchronous unit with no pause point for user input, so it can
only wrap steps that run after the user's plan confirmation: the per-item
preflight/implement/closeout loop in **Deliver Sequentially**. The planning
snapshot and the planner call happen before that confirmation and must stay in
the main conversation loop so the parent can inspect each result and pause for
confirmation before continuing. On Claude Code, the snapshot child is a spawn,
so it uses a single-child `Workflow` call with exactly one `agent()` inside it
(or the host's single-child-spawn equivalent); the planner is invoked as a
Skill in the current context, not as a spawned child. On
another host, use its equivalent only when it can set both values for each
child. Stop without reading or changing code, Git state, or Azure Boards if no
usable spawn primitive is available. Do not silently run the work item in the
parent agent or fall back to the parent's profile.

## Planning Snapshot — spawn task-boards-ops

Before invoking `$task-model-planner`, the parent orchestrator must obtain one
authoritative read-only snapshot through a direct `task-boards-ops` child. Do
not ask the planner child to read Boards or to spawn another child.

Spawn a child with `model=gpt-5.6-luna` and `reasoning_effort=low` on Codex, or
on Claude Code, one `Workflow` call whose script makes exactly one
`agent(prompt, {model: 'haiku', effort: 'low'})` call. This snapshot step runs
in the main loop, before the user confirms the plan, so use a single-child
`Workflow` call here rather than folding it into the per-item delivery
`Workflow` described in **Deliver Sequentially**. Give it the Story or explicit
work-item set and this self-contained instruction:

```text
Use `$azure-devops-boards-skill` in its semantic `task-boards-ops` role. For a
Story, run `planning-snapshot --story <story-id>` once. The Story's state does
not gate this read-only snapshot; the server-side query must select only its direct New Task and Bug children,
then return
one JSON snapshot containing the Story and every selected target. Do not read a
non-New child. For an explicit set, run
`planning-snapshot --id <id> --id <id>` once for the requested Task/Bug set;
preserve the supplied order and do not invent a parent. For every included item
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
Info remain Markdown and must be returned without HTML conversion.
```

One Boards child may make the helper calls needed to build this single snapshot;
never spawn one Boards child per ticket. Relations to excluded work items are
dependency context only, not planner targets.

If the snapshot child fails, returns incomplete data, or cannot spawn, stop
before invoking the planner. The parent may use the Boards Skill's documented
fallback only when the parent itself cannot spawn this direct Boards child.

## Build and Validate the Plan

1. Merge the planning snapshot with the accepted linked specification documents
   from the upstream planning authority, preserving the original Boards JSON
   and adding a `linkedSpecifications` collection with one
   `{reference, material, content}` decision per raw linked reference. A
   material specification must have non-empty full Markdown `content`. Then
   pass that composite snapshot to
   `$task-model-planner`. The planner is
   read-only planning logic; it must not read Azure Boards or spawn a Boards
   child. Treat its report as guidance, not tracker authority.
2. Read `$task-model-planner`'s canonical execution-profile registry. Resolve
   every profile ID from that one registry; do not reproduce or override its
   mapping here.
3. Accept both Task and Bug targets in the snapshot. Reject an explicit target
   of any other Azure type at the Boards snapshot boundary; do not convert its
   type or silently substitute another item.
4. Require a recommendation row and an execution-plan entry for every target
   work item, with each item appearing exactly once in each list.
5. Accept only an exact profile ID from the canonical registry. Reject a report
   that uses separate model or thinking-level fields, an unknown ID, or a
   profile whose resolved values are unavailable to the host.
6. Require the execution-plan work-item set to exactly match the recommendation
   table. Preserve its listed order; never reorder by model, cost, or title.
7. Stop before dispatching any worker if the report is missing, ambiguous,
   stale against a user-reported scope change, or contains an unsupported
   profile. Report the mismatch and request a corrected plan. Do not infer an
   order or profile from report prose.

## Confirm the Validated Plan

Before spawning any worker, present the complete validated plan in its planned
order. For every work item, include its ID, type, title, planned profile ID,
resolved model and reasoning effort, and order reason. On Codex, also include
the pre-start capacity fallback profile if any; Claude Code has no such
fallback, so omit that column there.
State that confirmation authorizes sequential delivery, including code changes,
one commit per successful work item, and Azure Boards closeout.

Wait for an explicit user confirmation of that displayed plan, for example
`确认执行该计划` or `confirm this plan`. Do not treat a prior approval, an
unrelated `ok`, silence, or a request to inspect the plan as confirmation. Do
not spawn a worker, modify code or Git state, or mutate Azure Boards while
waiting.

If the user changes a work item's scope, order, or profile before confirming,
invalidate the plan and return to **Build and Validate the Plan**. A changed
plan requires a newly displayed plan and new confirmation.

## Deliver Sequentially

For each work item in the validated execution plan, run three sequential steps.
Only one work item at a time. Do not start the next work item until the current
one is complete.

On Claude Code, this entire loop — every work item's preflight, implement, and
closeout step, for every item in the validated plan — runs as the body of a
single `Workflow` script invoked once after the user confirms the plan. Do not
open a new `Workflow` call per step or per item; call `agent()` sequentially
inside that one script so each item's three steps complete, in order, before
the next item's steps begin. No user input is needed once this script starts,
since confirmation already happened in the main loop before it was invoked.

See [references/claude-code-delivery-loop.js](references/claude-code-delivery-loop.js)
for the complete Workflow script template. The script takes the validated plan,
preflight results, and planner report as `args`, and returns an ordered delivery
report with completion status for each work item.

### 1. Preflight — spawn cheap agent

Spawn an agent with `model=gpt-5.6-luna` and `reasoning_effort=low` on Codex,
or `agent(prompt, {model: 'haiku', effort: 'low'})` on Claude Code. Give it the
work-item ID and this self-contained instruction:

```text
Use `$azure-devops-boards-skill` in its semantic `task-boards-ops` role. Run
`implement-preflight --id <id>` and return the JSON output unchanged. Do not
perform any non-Boards work.
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

### 2. Implement — spawn planner-specified agent

Resolve the work item's planned profile ID through the canonical registry for
the current host (Codex or Claude Code). On Codex, call `spawn_agent` with its
exact `model` and `reasoning_effort`, and a normalized `task_name` containing
the work-item ID and planned profile, for example `delivery_sol_xhigh_ab_175`.
The name is only a task label; it does not select a custom agent
configuration. On Claude Code, call the `Workflow` script's `agent(prompt,
{model, effort, label})` with the profile's exact Claude Code `model`/`effort`
mapping, and a `label` containing the work-item ID and planned profile.

If the host rejects that spawn before the worker starts and explicitly reports
the requested reasoning effort or capacity as unavailable, read the planned
profile's `Pre-start capacity fallback` from the canonical registry. This
fallback column exists for Codex only; Claude Code has no pre-start capacity
error signal, so on Claude Code any such rejection stops the sequence
immediately with no retry. On Codex, when the fallback has a value, retry
exactly once with that profile's exact mapping and a new `task_name`. Record
both profile IDs and the host error. If it has no value, the error is
model-wide availability, the error is not recognizable, or the retry fails,
stop the sequence. Do not retry after a worker begins, across models, or for a
work-item-level failure.

Give the worker its work-item ID and type, planned profile ID, effective
profile ID, relevant planner evidence and order reason, and the preflight scope
from step 1, plus this instruction:

```text
Use `$azure-task-implement` to implement work item <id> in the current workspace
and branch. The preflight scope is provided below. Re-read repository authority;
the planner is not a substitute for repo guidance. The effective execution
profile is fixed for this worker. Do not perform Azure Boards operations.

Return the compact delivery summary with commit hash, changed areas,
verification evidence, remaining work, and an acceptance-evidence table. Map
each supplied acceptance criterion to concrete verification evidence, or state
that it was not verified. Do not perform Azure Boards operations or closeout.

<preflight scope JSON>
```

Let `$azure-task-implement` own that work item's implementation,
verification, review, and commit. Do not duplicate any of those operations in
the parent. Require the worker to finish before inspecting its result. Keep the
shared workspace untouched while a worker runs. On failure, incomplete
verification, uncommitted result, blocker, or uncertain outcome, stop
immediately. Do not dispatch later work items.

### 3. Closeout — spawn cheap agent

Spawn an agent with `model=gpt-5.6-luna` and `reasoning_effort=low` on Codex,
or `agent(prompt, {model: 'haiku', effort: 'low'})` on Claude Code.

Closeout policy (apply before spawning):
- Read the current full Description and preserve its non-checklist content and
  formatting. Mark an unchecked Markdown checklist item as checked only when
  the implementation summary provides explicit implementation evidence for
  that criterion. Do not infer evidence from the item's final state, commit
  title, or a general success claim.
- If an unchecked checklist item lacks explicit evidence, or its text cannot
  be mapped unambiguously to the acceptance-evidence table, stop without
  closing the item. Do not overwrite the Description or post a completion
  comment.
- Write the resulting Description to a temporary Markdown file and write a
  completion comment from the implementation summary to another temporary
  Markdown file.
- Close the work item to `Closed`: pass `--state Closed`. If repository guidance
  names a different terminal state for a non-Task type, use that stated value.
- Pass the rewritten Description with `--description-file`; do not combine it
  with `--check-ac` because those options are mutually exclusive.
- Always pass `--expected-rev` (the preflight revision from step 1). It binds
  the Description read and final mutation to the same work-item version; a
  stale revision stops the closeout.

Give the agent the work-item ID, the preflight revision from step 1, the
implementation delivery summary, and this self-contained instruction:

```text
Use `$azure-devops-boards-skill` in its semantic `task-boards-ops` role. Read
the current full Description with `show --full --id <id>`. Apply only the
evidence-backed Markdown checklist changes specified by the implementation
summary, preserving all other Description content. Write the rewritten
Description to `<tmpdescription>` and a Markdown completion comment to
`<tmpcomment>`. Then run `close-task --apply --id <id> --expected-rev <rev>
--state Closed --description-file <tmpdescription> --comment-file <tmpcomment>`.
Return the JSON output unchanged. Do not use `--check-ac`, and do not perform
any non-Boards work.
```

Collect the closeout result. If the closeout fails because the expected rev is
stale, stop immediately; do not retry automatically. The work item changed
since preflight, so the current item must be re-preflighted and the
implementation result reconciled before closeout is attempted again. Do not
proceed to the next work item.

Dispatch the next work item only after all three steps complete successfully.

## Report

Return one ordered summary. For every completed work item, include the planned
and effective execution profile IDs, any pre-start capacity fallback error
(Codex only), worker-reported commit and verification, final tracker state,
and closeout result. For a stopped run, identify the work item that stopped
the sequence, retain earlier completed results, and state that later work
items were not dispatched.
