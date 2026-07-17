---
name: implementation-preread
description: Prepare a read-only, source-backed implementation readiness brief from a ticket, issue, or specification before a separate implementation run. Use when the user asks to preread, orient on, inspect, or hand off upcoming implementation work, especially before switching models and invoking $implement.
---

# Implementation Preread

Prepare orientation only. Do not implement the work.

## Read Current Authority

1. Read the nearest `AGENTS.md` and every repository guidance file it requires.
2. Resolve the authoritative ticket, issue, or specification. For an Azure
   Boards item, use the existing Azure Boards skill and repository tracker
   guidance rather than duplicating tracker commands. Read the target's current
   revision, state, description, acceptance criteria, and relations.
3. Read only the directly related parent, predecessor, successor, or replacement
   items needed to establish scope and ordering.
4. Record the current branch, HEAD, working-tree status, and any existing dirty
   changes. Preserve them.
5. Inspect the relevant current source, tests, documentation, and architecture
   decisions. Trace the current call flow and public seams. Use `rg` first for
   repository search.

Treat the current tracker or specification and current code as authoritative
over earlier plans, briefs, and handoffs. State conflicts explicitly.

## Keep the Preread Read-Only

- Do not edit files, source code, tests, tracker items, Git state, or
  configuration.
- Do not build, run full test suites, migrate databases, generate code, install
  dependencies, commit, push, or invoke `$implement`.
- Use narrowly scoped read-only inspection commands only. Do not run commands
  whose purpose is implementation verification.
- Record open questions instead of asking the user unless an unresolved
  ambiguity would materially change the implementation scope.
- Do not attempt to select or switch the model used for this preread. Model
  selection happens outside the Skill.
- Stop after producing the readiness brief.

## Recommend the Implementation Profile

For the later implementation run, choose only between `gpt-5.6-terra` and
`gpt-5.6-sol`:

- Prefer `gpt-5.6-terra` for bounded, well-specified, localized, or mechanical
  work.
- Prefer `gpt-5.6-sol` for cross-cutting architecture, concurrency, lifecycle,
  data-integrity, security, or materially ambiguous work.

Recommend the lowest reasoning level justified by the evidence: `medium` for
straightforward work, `high` for normal non-trivial implementation, and `xhigh`
only for concrete complexity or risk. Never recommend `max` as a default;
reserve it as an escalation trigger after a specific unresolved blocker is
identified. Explain the choice in one sentence and list concrete escalation
triggers.

## Return the Readiness Brief

Use this structure:

```markdown
# Implementation Readiness Brief: <ticket or spec>

## Authority snapshot
- Current source, revision, state, and relations
- Branch, HEAD, and working-tree state

## Scope
- Acceptance criteria
- Required invariants
- Explicitly out of scope

## Code map
- Relevant files and responsibilities
- Current call flow and public seams
- Existing tests and likely focused verification

## Risks and open questions
- Evidence-backed risks, conflicts, and unknowns

## Recommended implementation profile
- Model and reasoning level
- Why
- Escalation triggers

## Handoff
- Three to six compact instructions for the later `$implement` run

This brief is orientation only. Before editing, re-read the current
authoritative ticket or specification, relations, repository state, and
relevant code. If they conflict with this brief, current authority and code win.
```

Keep the brief compact and source-backed. Include paths, identifiers, and commit
hashes that help the implementation run relocate evidence, but omit raw command
logs and long source excerpts.
