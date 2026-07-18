---
name: azure-task-orchestrator
description: Plan and deliver all Tasks under an Azure DevOps Boards Story or explicit Task set in dependency order. Use when the user wants `$task-model-planner` to choose a named execution profile for each Task, then wants each Task delivered by `$azure-task-implement` in a sequential subagent with that exact profile.
---

# Azure Task Orchestrator

Create one read-only execution-profile plan, validate it, obtain the user's
confirmation, then run exactly one Azure Task delivery worker at a time. Do not
implement, review, or close Tasks in the orchestrator itself.

## Require Direct Skill Commands Before Work

Before reading tracker data or spawning a worker, use the direct Skill commands
`/task-model-planner` and `/azure-task-implement`, plus a subagent spawn
primitive that accepts an explicit model and reasoning effort.

For each direct Skill command, accept one of these ways to obtain its
instructions:

- **Slash command:** the host exposes the corresponding direct command.
- **Context:** the current conversation supplies its complete `<skill>` body.
- **Path:** the current conversation or host catalog supplies an absolute,
  readable `SKILL.md` path. Read that file completely before using it.

When a Skill is supplied by Context or Path, follow its instructions directly
as `/task-model-planner` or `/azure-task-implement` without adding a
host-specific invocation tool. Record how each Skill was supplied. Do not infer
a path from a Skill name or treat an installed directory that is neither
advertised nor supplied as available.

On Codex, use `spawn_agent` with `model` and `reasoning_effort`. On another
host, use its equivalent only when it can set both values for each child. Stop
without reading or changing code, Git state, or Azure Boards if no usable
source or spawn primitive is available. State what is missing; do not silently
run the Task in the parent agent or fall back to the parent's profile.

## Build and Validate the Plan

1. Run `/task-model-planner` for the Story or explicit Task set. When it is
   supplied by Context or Path, first read its complete supplied body or
   `SKILL.md`, then follow it directly. Treat its report as read-only planning
   guidance, not tracker authority.
2. Read `$task-model-planner`'s canonical
   `references/execution-profiles.md` registry. Resolve every profile ID from
   that one registry; do not reproduce or override its mapping here.
3. Require a recommendation row and an execution-plan entry for every target
   Task, with each Task appearing exactly once in each list.
4. Accept only an exact profile ID from the canonical registry. Reject a report
   that uses separate model or thinking-level fields, an unknown ID, or a
   profile whose resolved values are unavailable to the host.
5. Require the execution-plan Task set to exactly match the recommendation
   table. Preserve its listed order; never reorder by model, cost, or title.
6. Stop before dispatching any worker if the report is missing, ambiguous,
   stale against a user-reported scope change, or contains an unsupported
   profile. Report the mismatch and request a corrected plan. Do not infer an
   order or profile from report prose.

## Confirm the Validated Plan

Before spawning any worker, present the complete validated plan in its planned
order. For every Task, include its ID, title, planned profile ID, resolved model
and reasoning effort, pre-start capacity fallback if any, and order reason.
State that confirmation authorizes sequential delivery, including code changes,
one commit per successful Task, and Azure Boards closeout.

Wait for an explicit user confirmation of that displayed plan, for example
`确认执行该计划` or `confirm this plan`. Do not treat a prior approval, an
unrelated `ok`, silence, or a request to inspect the plan as confirmation. Do
not spawn a worker, modify code or Git state, or mutate Azure Boards while
waiting.

If the user changes a Task's scope, order, or profile before confirming,
invalidate the plan and return to **Build and Validate the Plan**. A changed
plan requires a newly displayed plan and new confirmation.

## Deliver Sequentially

For each Task in the validated execution plan:

1. Resolve the Task's planned profile ID through the canonical registry. On
   Codex, call `spawn_agent` with its exact `model` and `reasoning_effort`, and
   a normalized `task_name` containing the Task and planned profile, for example
   `delivery_sol_xhigh_ab_175`. The name is only a task label; it does not select
   a custom agent configuration. Do not start the next worker until this worker
   has returned a terminal result.
2. If the host rejects that spawn before the worker starts and explicitly reports
   the requested reasoning effort or capacity as unavailable, read the planned
   profile's `Pre-start capacity fallback` from the canonical registry. When it
   has a value, retry exactly once with that profile's exact mapping and a new
   `task_name`. Record both profile IDs and the host error. If it has no value,
   the error is model-wide availability, the error is not recognizable, or the
   retry fails, stop the sequence. Do not retry after a worker begins, across
   models, or for a Task-level failure.
3. Give the worker only its Task ID, planned profile ID, effective profile ID,
   relevant planner evidence and order reason, the resolved
   `$azure-task-implement` source, plus this instruction:

   ```text
   Run /azure-task-implement to deliver exactly <Task ID> in the current
   workspace and branch. When it is supplied by Context or Path, read its
   complete supplied body or resolved SKILL.md before acting. Re-read current
   tracker and repository authority; the planner is not a substitute for
   preflight. Do not implement another Task. The effective execution profile is
   fixed for this worker. Follow all repository guidance and return the compact
   delivery summary.
   ```

4. Let `$azure-task-implement` own that Task's preflight, implementation,
   verification, review, commit, and Azure closeout. Do not duplicate any of
   those operations in the parent.
5. Require the worker to finish before inspecting its result. Keep the shared
   workspace untouched while a worker runs.
6. On a successful worker result, record its compact summary and dispatch the
   next listed Task. On any failure, incomplete verification, uncommitted
   result, blocker, or uncertain closeout, stop immediately. Do not dispatch
   later Tasks, retry at a stronger profile, use a lower profile outside the
   pre-start capacity rule, or re-plan silently.

Run only one delivery worker at a time even when Tasks look independent. This
preserves the clean-worktree requirement of `$azure-task-implement`, preserves
the planned dependency order, and makes each Task's commit and tracker closeout
auditable.

## Report

Return one ordered summary with how the planning and delivery Skills were
supplied. For every completed Task, include the planned and effective execution
profile IDs, any pre-start capacity fallback error, worker-reported commit and
verification, final tracker state, and closeout result. For a stopped run,
identify the Task that stopped the sequence, retain earlier completed results,
and state that later Tasks were not dispatched.
