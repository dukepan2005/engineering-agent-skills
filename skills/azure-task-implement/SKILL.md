---
name: azure-task-implement
description: "Deliver one implementation-ready Azure DevOps Boards work item through a compact lifecycle: preflight its current scope, use the complete third-party implement skill workflow, then validate and persist a Markdown-safe closeout. Use when the user asks to implement, deliver, finish, or close a specific Azure Boards item such as a Task or Bug and wants Azure tracking synchronized without project-specific workflow gates."
---

# Azure Task Implement

Wrap the host-provided `implement` skill workflow for exactly one
implementation-ready Azure Boards work item. Use the
`azure-devops-boards-skill` skill for all tracker operations. Keep repository
guidance authoritative for code, tests, state names, and checklist policy; this
Skill provides the reusable lifecycle, not a replacement project process.

## Decide Eligibility by Scope

- Accept a Task, Bug, or another work-item type when it represents one bounded,
  directly implementable change with acceptance and verification authority.
- Never require, duplicate, or convert a Bug or another item into a Task merely
  to use this Skill. `System.WorkItemType` is metadata, not an eligibility gate.
- Stop when the selected item is only an aggregate planning container, still
  requires unresolved decomposition, or delegates multiple independently
  deliverable child items. Report that scope problem without changing its type.
- Let repository tracker guidance impose any stricter type or hierarchy rule.

## Take the trivial fast-path when the change is small

This Skill's full lifecycle (preflight → implement → `close-task`) is built for a
code Task that carries an acceptance-criteria checklist. Not every item needs it.
Before starting, self-assess the scope:

- **Trivial change** — documentation, a one-to-two-file edit with no logic change,
  or a fix whose correctness is obvious by inspection — takes the fast-path:
  edit, commit, then a single `update` (state only, if needed) plus one
  `add-comment` with the completion summary. Skip `implement-preflight` and
  `close-task`; do not check checklist items that were never the authority for
  the work.
- **Trivial never applies, regardless of file count**, when the change touches:
  CI/CD or workflow configuration; permissions, auth, or other security-sensitive
  code; data migrations; API or contract changes; dependency or version bumps;
  or production configuration — or when the work item carries its own explicit
  acceptance criteria. Those always take the full lifecycle below.
- **Anything else** — logic changes, multi-file behaviour, an item whose
  acceptance criteria are the source of truth — runs the full lifecycle below.

When in doubt, take the full lifecycle. The fast-path exists to avoid tracker
bookkeeping that outweighs a +N-line change, not to skip verification.

## Require Dependencies Before Work

Before reading a work item, confirm that the current host can invoke all of these
Skills:

- the `implement` skill from `mattpocock/skills`
- the `azure-devops-boards-skill` skill from this repository

If any is unavailable, stop without inspecting or changing the tracker, code,
or Git state. State the missing Skill and print only the relevant install
command for the current host, for example:

```bash
npx skills@latest add mattpocock/skills

npx skills@latest add dukepan2005/engineering-agent-skills
```

Choose the required Skills for the active host interactively. Do not install a
missing dependency during a delivery run.

## Start Once

1. Read repository guidance and resolve the Azure Boards helper through
   `azure-devops-boards-skill` skill.
2. Run `implement-preflight --id <work-item-number>` once. Keep its compact snapshot
   (revision, scope, and relation IDs) as the tracker authority for this thread.
3. Stop if the item state, replacement relation, or blocker makes implementation
   invalid. Do not change a tracker state merely to begin work.
4. Require a clean worktree before editing so the work-item commit and review
   cover only this work item.

Run preflight again only when the session or branch changes, the user says the
work item changed, a relation/scope conflict appears, or closeout reports a stale
revision.

## Implement One Work Item

- Use the complete `implement` skill workflow with the current work-item scope and
  acceptance criteria from preflight. Let it use TDD where appropriate, run
  its verification, review the work, and create the one work-item commit in its
  defined order. Do not replace or duplicate its review or commit steps.
- Do not fetch or mutate Azure Boards for each file change, test run, or commit
  attempt.
- If implementation fails or verification is incomplete, do not close the work
  item. Report the local evidence; add a tracker blocker comment only when the
  user asks or repository guidance requires it.

## Close Out Automatically After Success

1. Collect the committed hash, implemented behavior, focused verification, and
   remaining work.
2. If repository policy requires checklist synchronization, check off each
   evidence-backed item with `close-task --check-ac` (see
   `azure-devops-boards-skill`) instead of reading and rewriting the
   Description yourself. Fall back to `--description-file` only when
   acceptance criteria are not expressed as a markdown checklist.
3. Prepare one concise Markdown comment from the
   [closeout-comment template](references/closeout-comment.md)
   (`## Completion`, `## Verification`, `## Remaining work`).
4. Determine the final state only from explicit user input or repository
   guidance. If neither specifies one, leave state unchanged; do not assume
   `Closed` is universally valid.
5. Run `close-task --apply`, passing the preflight revision as
   `--expected-rev`, `--check-ac` for evidence-backed acceptance criteria, and
   a state only when required. Follow the safety contract defined by
   `azure-devops-boards-skill`: one call validates, applies, and
   read-back-checks; a stale rev fails immediately with no automatic retry.
6. Accept completion only after the helper verifies the final work-item
   mutation and Markdown comment. If a rev conflict surfaces, rerun preflight,
   reconcile the changed scope, and revalidate closeout.

The helper may perform a work-item patch and a comment write. Treat their
separate persisted checks as required; never describe them as one atomic Azure
operation.

## Report

Return only a compact delivery summary:

- Work-item ID, type, final tracker state, and revision
- Commit hash and changed areas
- Verification evidence
- Checklist or Description changes, if any
- Remaining work or blocker
