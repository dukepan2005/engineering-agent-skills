---
name: azure-task-implement
description: "Deliver one Azure DevOps Boards Task through a compact lifecycle: preflight its current scope, invoke $implement, then validate and persist a Markdown-safe closeout. Use when the user asks to implement, deliver, finish, or close a specific Azure Boards Task such as AB#169 and wants Azure tracking synchronized without project-specific workflow gates."
---

# Azure Task Implement

Wrap the host-provided `$implement` workflow for exactly one Azure Boards Task.
Use `$azure-devops-boards-skill` for all tracker operations. Keep repository
guidance authoritative for code, tests, state names, and checklist policy; this
Skill provides the reusable lifecycle, not a replacement project process.

## Start Once

1. Read repository guidance and resolve the Azure Boards helper through
   `$azure-devops-boards-skill`.
2. Run `implement-preflight --id <task-number>` once. Keep its compact snapshot
   (revision, scope, and relation IDs) as the tracker authority for this thread.
3. Stop if the item state, replacement relation, or blocker makes implementation
   invalid. Do not change a tracker state merely to begin work.
4. Invoke `$implement` for that Task, using the preflight scope as the active
   task boundary. Do not run a second full tracker read before editing.

Run preflight again only when the session or branch changes, the user says the
Task changed, a relation/scope conflict appears, or closeout reports a stale
revision.

## Implement One Task

- Implement, test, review, and commit through `$implement`.
- Do not fetch or mutate Azure Boards for each file change, test run, or commit
  attempt.
- If implementation fails or verification is incomplete, do not close the Task.
  Report the local evidence; add a tracker blocker comment only when the user
  asks or repository guidance requires it.

## Close Out Automatically After Success

1. Collect the committed hash, implemented behavior, focused verification, and
   remaining work.
2. If repository policy requires supported Markdown checklist changes, read the
   current Description once, update only evidence-backed items, and prepare a
   complete replacement Description. Otherwise do not read or rewrite it.
3. Prepare one concise Markdown comment with `## Completion`, `## Verification`,
   and `## Remaining work`.
4. Determine the final state only from explicit user input or repository
   guidance. If neither specifies one, leave state unchanged; do not assume
   `Closed` is universally valid.
5. Run `close-task` without `--apply`, then repeat the identical command with
   `--apply`, passing the preflight revision as `--expected-rev`. Include a
   Description file and state only when required.
6. Accept completion only after the helper verifies the final work-item mutation
   and Markdown comment. If optimistic concurrency rejects the revision, rerun
   preflight, reconcile the changed scope, and revalidate closeout.

The helper may perform a work-item patch and a comment write. Treat their
separate persisted checks as required; never describe them as one atomic Azure
operation.

## Report

Return only a compact delivery summary:

- Task ID, final tracker state, and revision
- Commit hash and changed areas
- Verification evidence
- Checklist or Description changes, if any
- Remaining work or blocker
