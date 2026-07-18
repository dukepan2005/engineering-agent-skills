---
name: azure-task-orchestrator
description: Plan and deliver all Tasks under an Azure DevOps Boards Story or explicit Task set in dependency order. Use when the user wants `$task-model-planner` to choose a named execution profile for each Task, then wants each Task delivered by `$azure-task-implement` in a sequential subagent with that exact profile.
---

# Azure Task Orchestrator

Create one read-only execution-profile plan, validate it, then run exactly one Azure Task
delivery worker at a time. Do not implement, review, or close Tasks in the
orchestrator itself.

## Require Capabilities Before Work

Before reading tracker data or spawning a worker, confirm that the host can
invoke all of the following:

- `$task-model-planner`
- `$azure-task-implement`
- a subagent spawn primitive that accepts an explicit model and reasoning effort

On Codex, use `spawn_agent` with `model` and `reasoning_effort`. On another
host, use its equivalent only when it can set both values for each child. Stop
without reading or changing code, Git state, or Azure Boards if any capability
is unavailable. State the missing capability; do not silently run the Task in
the parent agent or fall back to the parent's profile.

## Build and Validate the Plan

1. Invoke `$task-model-planner` for the Story or explicit Task set. Treat its
   report as read-only planning guidance, not tracker authority.
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

## Deliver Sequentially

For each Task in the validated execution plan:

1. Resolve the Task's profile ID through the canonical registry. Spawn one child
   agent with the resolved `model` and `reasoning_effort`, and name the child
   from both Task and profile, for example `delivery_sol_xhigh_ab_175` on
   Codex. Do not start the next worker until this worker has returned a terminal
   result.
2. Give the worker only its Task ID, assigned profile ID, relevant planner evidence
   and order reason, plus this instruction:

   ```text
   Use $azure-task-implement to deliver exactly <Task ID> in the current
   workspace and branch. Re-read current tracker and repository authority;
   the planner is not a substitute for preflight. Do not implement another
   Task. Do not change the assigned execution profile. Follow all repository
   guidance and return the compact delivery summary.
   ```

3. Let `$azure-task-implement` own that Task's preflight, implementation,
   verification, review, commit, and Azure closeout. Do not duplicate any of
   those operations in the parent.
4. Require the worker to finish before inspecting its result. Keep the shared
   workspace untouched while a worker runs.
5. On a successful worker result, record its compact summary and dispatch the
   next listed Task. On any failure, incomplete verification, uncommitted
   result, blocker, or uncertain closeout, stop immediately. Do not dispatch
   later Tasks, retry at a stronger profile, or re-plan silently.

Run only one delivery worker at a time even when Tasks look independent. This
preserves the clean-worktree requirement of `$azure-task-implement`, preserves
the planned dependency order, and makes each Task's commit and tracker closeout
auditable.

## Report

Return one ordered summary with, for every completed Task, the assigned
execution profile ID, worker-reported commit and verification, final tracker
state, and closeout result. For a stopped run, identify the Task that stopped
the sequence, retain earlier completed results, and state that later Tasks were
not dispatched.
