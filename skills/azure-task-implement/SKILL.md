---
name: azure-task-implement
description: "Implement code for one implementation-ready Azure DevOps Boards work item. Use when the orchestrator has already performed preflight and will handle closeout; this skill covers only the code implementation step."
---

# Azure Task Implement

Implement code for one Azure Boards work item. The orchestrator has already
performed preflight and will handle closeout; this skill covers only the code
implementation step. Do not read or mutate Azure Boards.

## Require Dependencies Before Work

**REQUIRED SUB-SKILL:** Use `$implement`.

Invoke it by Skill name and let the host resolve its enabled Skill catalog. If
the host reports `$implement` as unavailable, stop without inspecting or
changing code, Git state, or Azure Boards. Print only the relevant install
command for `mattpocock/skills`.

## Implement One Work Item

1. Read repository guidance.
2. Require a clean worktree before editing so the commit covers only this work
   item.
3. Use the complete `$implement` workflow with the preflight scope from
   the orchestrator. Let it use TDD where appropriate, run its verification,
   review the work, and create the commit.
4. Do not fetch or mutate Azure Boards. Do not read or update the work item in
   Azure DevOps.
5. If implementation fails or verification is incomplete, do not close the work
   item. Report the local evidence.
6. Fill the [closeout-comment template](references/closeout-comment.md) using
   the committed hash, changed areas, focused verification evidence, and
   remaining work. Return the filled comment text in the delivery summary.

## Report

Return a compact delivery summary:

- Commit hash and changed areas
- Verification evidence
- Remaining work or blocker
- Closeout comment text (filled from the template)
