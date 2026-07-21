---
name: azure-task-orchestrator
description: Plan and deliver implementation-ready Azure DevOps Boards work items under a Story or in an explicit item set, in dependency order. Use when the user wants the task-model-planner skill to choose a named execution profile for each item, then wants each item delivered by the azure-task-implement skill in a sequential subagent with that exact profile.
---

# Azure Task Orchestrator

Create one read-only execution-profile plan, validate it, obtain the user's
confirmation, then run exactly one Azure work-item delivery worker at a time.
Do not implement, review, or close work items in the orchestrator itself.

## Require Direct Skills Before Work

Before reading tracker data or spawning a worker, use the `task-model-planner`,
`azure-task-implement`, and `task-boards-ops` agents, plus a subagent spawn
primitive that accepts an explicit model and reasoning effort. The
`task-boards-ops` agent has a fixed model in its definition; spawn it by name
without a model override. It covers all Azure Boards reads and mutations
(show, preflight, create, update, close-task, add-comment, add-link,
current-sprint).

For each Skill, accept one of these ways to obtain its instructions:

- **Slash command:** the host exposes the corresponding enabled Skill.
- **Context:** the current conversation supplies its complete `<skill>` body.
- **Path:** the current conversation or host catalog supplies an absolute,
  readable `SKILL.md` path. Read that file completely before using it.

When a Skill is supplied by Context or Path, follow the `task-model-planner` or
`azure-task-implement` skill instructions directly without adding a host-specific
invocation tool. Record how each Skill was supplied. Do not infer a path from a
Skill name or treat an installed directory that is neither advertised nor
supplied as available.

On Codex, use `spawn_agent` with `model` and `reasoning_effort`. On another
host, use its equivalent only when it can set both values for each child. Stop
without reading or changing code, Git state, or Azure Boards if no usable
source or spawn primitive is available. State what is missing; do not silently
run the work item in the parent agent or fall back to the parent's profile.

## Build and Validate the Plan

1. Use the `task-model-planner` skill for the Story or explicit work-item set.
   When it is supplied by Context or Path, first read its complete supplied body
   or `SKILL.md`, then follow it directly. Treat its report as read-only planning
   guidance, not tracker authority.
2. Read the `task-model-planner` skill's canonical
   `references/execution-profiles.md` registry. Resolve every profile ID from
   that one registry; do not reproduce or override its mapping here.
3. Do not omit or reject a target solely because its Azure type is not Task,
   and do not require a type conversion before planning or delivery.
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
resolved model and reasoning effort, pre-start capacity fallback if any, and
order reason.
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

### 1. Preflight — spawn cheap agent

Spawn an agent with `model=gpt-5.6-luna` and `reasoning_effort=low`. On Codex,
call `spawn_agent` with these parameters directly. On a host that supports
named agent types, spawn the `task-boards-ops` agent instead.

Give it the work-item ID, the repo root path, and the instruction:

```text
Perform preflight for work item <id>. The skill directory is at <repo-root>/skills/azure-devops-boards-skill. Return the structured scope JSON.
```

Collect the preflight result. If the spawn fails or the agent returns an error
(no such item, wrong state, blocked by a relation), stop immediately. Do not
proceed to the implement step.

### 2. Implement — spawn planner-specified agent

Resolve the work item's planned profile ID through the canonical registry. On
Codex, call `spawn_agent` with its exact `model` and `reasoning_effort`, and
a normalized `task_name` containing the work-item ID and planned profile, for
example `delivery_sol_xhigh_ab_175`. The name is only a task label; it does
not select a custom agent configuration.

If the host rejects that spawn before the worker starts and explicitly reports
the requested reasoning effort or capacity as unavailable, read the planned
profile's `Pre-start capacity fallback` from the canonical registry. When it
has a value, retry exactly once with that profile's exact mapping and a new
`task_name`. Record both profile IDs and the host error. If it has no value,
the error is model-wide availability, the error is not recognizable, or the
retry fails, stop the sequence. Do not retry after a worker begins, across
models, or for a work-item-level failure.

Give the worker its work-item ID and type, planned profile ID, effective
profile ID, relevant planner evidence and order reason, the resolved
`azure-task-implement` skill source, the preflight scope from step 1, plus
this instruction:

```text
Use the `azure-task-implement` skill to implement work item <id> in the current
workspace and branch. The preflight scope is provided below. Read the resolved
SKILL.md before acting. Re-read repository authority; the planner is not a
substitute for repo guidance. The effective execution profile is fixed for this
worker. Do not perform Azure Boards operations.

Return the compact delivery summary with commit hash, changed areas,
verification evidence, remaining work, and a filled closeout comment based on
the template at <repo-root>/skills/azure-task-implement/references/closeout-comment.md.

<preflight scope JSON>
```

Let the `azure-task-implement` skill own that work item's implementation,
verification, review, and commit. Do not duplicate any of those operations in
the parent. Require the worker to finish before inspecting its result. Keep the
shared workspace untouched while a worker runs. On failure, incomplete
verification, uncommitted result, blocker, or uncertain outcome, stop
immediately. Do not dispatch later work items.

### 3. Closeout — spawn cheap agent

Spawn an agent with `model=gpt-5.6-luna` and `reasoning_effort=low` (same as
step 1: Codex uses `spawn_agent` directly; hosts with named agent types use
`task-boards-ops`).

Closeout policy (apply before spawning):
- Write the closeout comment returned by step 2 into a temporary Markdown file.
- Use `--check-ac all` unless only a specific subset of acceptance criteria are
  evidence-backed, in which case use a fragment that uniquely matches that item.
- Pass `--state` only when the user or repository guidance explicitly requires
  a final state. If neither specifies one, leave the state unchanged.

Give the agent the work-item ID, the preflight revision from step 1, the
repo root path, the skill directory path (`<repo-root>/skills/azure-devops-boards-skill`), and the temporary comment file path:

```text
Run `close-task --apply --id <id> --expected-rev <rev> --check-ac <all|fragment> --comment-file <tmpfile> [--state <state>]`. The skill directory is at <repo-root>/skills/azure-devops-boards-skill. Return the result JSON.
```

Collect the closeout result. If the closeout fails because the expected rev is
stale, stop immediately; do not retry automatically. The work item changed
since preflight, so the current item must be re-preflighted and the
implementation result reconciled before closeout is attempted again. Do not
proceed to the next work item.

Dispatch the next work item only after all three steps complete successfully.

## Report

Return one ordered summary with how the planning and delivery Skills were
supplied. For every completed work item, include the planned and effective
execution profile IDs, any pre-start capacity fallback error, worker-reported
commit and verification, final tracker state, and closeout result. For a stopped
run, identify the work item that stopped the sequence, retain earlier completed
results, and state that later work items were not dispatched.
