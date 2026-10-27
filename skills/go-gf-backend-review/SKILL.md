---
name: go-gf-backend-review
description: Run an evidence-backed, read-only Go or GoFrame backend review through one independent reviewer, covering the exact change delta, production paths, project boundaries, and focused verification.
---

# Go / GoFrame Backend Review

Review the actual change delta, not a hypothetical function in isolation. Report only issues introduced by the change that can be reached through a real production path. This skill coordinates one independent reviewer and produces a human review, not `review.json` or GitHub comments.

Use this workflow after each task in subagent-driven implementation, after a major Go feature, before merge, or whenever the user requests an independent review.

## Authority and Workspace Safety

- Preserve pre-existing changes; do not reset, switch branches, or create commits.
- Read repository `AGENTS.md` first. It overrides generic Go guidance: do not flag an established GoFrame layer, generated-code boundary, project test framework, or project router solely because generic Go advice prefers another design.
- Use the Go version declared by `go.mod` and the repository instructions. Do not recommend newer language or library features merely because a general Go skill describes them.

## Workflow

1. Record the checkout, branch, `HEAD`, and worktree status before inspecting. Resolve exactly one input mode and record the immutable endpoints:
   - For a PR, resolve its actual base, head, and merge-base; review only `merge-base...head`. Do not assume the default branch is the base.
   - For a single commit `C`, resolve `C` and its first parent; review `C^1...C`. For a merge commit, state that the first parent was used unless the user supplies another parent.
   - For an explicit commit range `A..B`, resolve both commits and require `A` to be an ancestor of `B`; review the fixed endpoint delta `A...B` and list commits with `A..B`. If they are not ancestral, stop and request an explicit base or permission to use their merge-base. Do not turn a two-commit request into a PR review.
   - For `base branch -> target branch` (or equivalent `base` to `target` wording), resolve both branch tips, compute their merge-base, and review `merge-base...target`. Record both branch names and do not substitute a default branch.
   - If the refs or mode are ambiguous, stop and request the missing baseline. Never silently compare the current checkout, infer PR metadata, or treat an unresolved ref as a file path.
   Record the selected mode, resolved base/head or commit endpoints, merge-base when applicable, commit list, and exact diff command. The coordinator and reviewer use these fixed endpoints as the review scope; surrounding code may be read as context. Exclude uncommitted changes and unrelated submodule changes unless they are inside the selected delta.
2. Read the repository's `AGENTS.md` before applying Go or GoFrame guidance. Read the applicable PR description or commit message(s), and the task/specification that owns the change. For a commit or branch comparison, do not invent PR metadata. Keep changed-hunk attribution separate from pre-existing context.
3. Prepare a compact, self-contained review brief and dispatch exactly one independent reviewer as the default workflow. Include the repository path, selected mode and immutable endpoints, exact diff command, concise change description, paths to authoritative requirements and repository instructions, read-only limits, and expected finding format. Require the reviewer to read those source documents and follow this skill's checklist. Do not pass the full conversation history. The reviewer performs the review alone and does not delegate further. If this agent was explicitly assigned as the reviewer, execute the review without dispatching another reviewer. If independent review is unavailable, review locally and state that limitation.
4. The reviewer traces every suspected defect from its actual production entry point (such as an HTTP handler, RPC method, message consumer, or scheduled job), through the repository's existing modules, to persistence and external dependencies. Follow the project's actual architecture rather than requiring specific layers. Direct invocation of an internal helper is not proof of a production defect.
5. Check changed behavior and integration boundaries that exist in the project or are introduced by the delta:
   - framework layering and generated-file boundaries, where used;
   - errors and nil output, including typed business rejections and client-facing mappings where used;
   - serialization/import boundaries and protocol compatibility, including protobuf where used;
   - transactions, idempotency, and sharding keys where used, plus cancellation, goroutine ownership, and external failures;
   - focused tests for new or changed branches.
6. Review changed Go business logic for correct error propagation, context handling across I/O, cancellation and deadlines, goroutine ownership, bounded concurrency, shared-state safety, and tests for distinct behavior. Use only Go APIs supported by `go.mod`; report behavioral defects or project-rule violations, not preferences about syntax, package layout, or style.
7. Apply GoFrame v2 checks only where the changed path uses the framework: verify request parsing and routing, service registration, ORM/query and transaction behavior, and generated-code boundaries against this repository's actual conventions and configuration. Generic GoFrame advice does not override `AGENTS.md`; in particular, do not prescribe a different `logic/`/`service/` layout or blanket error API.
8. When feasible, run focused verification without modifying tracked files. Inspect or create a temporary worktree at the selected target snapshot when the current checkout does not match the reviewed endpoint; never switch the user's checkout just to test a range. Start with focused checks on changed packages, following the target repository's test commands and isolation requirements; widen only when cross-package behavior warrants it. Report exact commands and results; label checks that could not run.
9. The coordinator checks every proposed finding against the fixed diff and the finding standard, rejects false positives, and reports the reviewer's verification results. Treat confirmed critical or important findings as blockers for ongoing implementation; return them to the implementation owner and review the repaired delta before proceeding. This remains a read-only workflow: do not edit, stage, commit, push, or merge.

## Finding Standard

Report a finding only when all of the following are true:

- It is in the PR delta or the delta makes a previously safe path unsafe.
- It has a precise head `file:line`.
- A real call or data path reaches it.
- A trigger condition or reproduction is concrete.
- Existing tests do not already prove the behavior safe.

Do not report style preferences, broad refactors, theoretical nil risks, or pre-existing defects as PR findings.

## Output

State the selected review mode, resolved endpoints/merge-base, and exact diff command first. For every P0/P1/P2 finding provide the priority, exact `file:line`, changed-hunk evidence, production path, trigger/reproduction, impact, focused fix direction, and test gap. If none meet the standard, say `No actionable findings`, then list checked paths and verification limitations. Do not use an absence of local test execution as evidence that no issue exists.
