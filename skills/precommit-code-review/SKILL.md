---
name: precommit-code-review
description: "Review one Task's uncommitted worktree diff before commit along separate Standards and Spec axes. Use when an implementation must be reviewed against a captured baseline commit before creating its first commit, especially from $azure-task-implement."
---

# Pre-Commit Code Review

Review uncommitted work. Do not create, amend, or require a commit for review.
Use it to make the working-tree review boundary explicit while preserving
`$implement`'s required order: review first, then commit.

## Require a Clean Baseline

1. Require a baseline commit from the caller. Resolve it with
   `git rev-parse <baseline>`.
2. Require `HEAD` to still equal that baseline. If it differs, stop: a commit
   was created before review and the caller must choose a new review boundary.
3. Require a clean worktree at Task start. If pre-existing changes exist, stop
   rather than accidentally reviewing or committing another Task's changes.
4. Build the review input from `git diff --no-ext-diff <baseline>` plus every
   non-ignored untracked file. Do not omit staged changes or new files.
5. Stop without a review if the combined change set is empty.

The caller must provide the Task's current acceptance criteria or another
authoritative specification. Do not infer it from commit messages.

## Review Two Axes Separately

Run two isolated reviews in parallel when the host supports subagents; otherwise
run them sequentially without mixing their findings.

### Standards

Read applicable repository guidance and coding standards. Review the worktree
diff for documented rule violations and the following judgement-only smell
baseline: Mysterious Name, Duplicated Code, Feature Envy, Data Clumps, Primitive
Obsession, Repeated Switches, Shotgun Surgery, Divergent Change, Speculative
Generality, Message Chains, Middle Man, and Refused Bequest.

Report each finding with file/hunk, violated rule or smell label, severity, and
a concrete fix. Keep this report under 400 words.

### Spec

Compare the same worktree diff with the supplied Task scope. Report missing or
partial requirements, scope creep, and behavior that appears implemented but is
wrong. Cite the acceptance criterion or specification evidence for each finding.
Keep this report under 400 words.

## Finish Before Commit

Return `## Standards` and `## Spec` separately, followed by counts and the
worst finding in each axis. Do not rerank findings across axes.

If there are actionable findings, fix them, rerun relevant verification, and
review the current worktree diff again. Create a commit only after review has
no unresolved actionable finding. Never post tracker closeout while review is
unresolved.
