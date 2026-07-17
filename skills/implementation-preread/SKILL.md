---
name: implementation-preread
description: Prepare a read-only, source-backed implementation readiness brief from a ticket, issue, or specification before a separate implementation run. Use when the user asks to preread, orient on, inspect, or hand off upcoming implementation work, especially before invoking $implement. Use `--delegated` only when the user explicitly wants a fixed-model Codex subagent to perform the preread.
---

# Implementation Preread

Prepare orientation only. Do not implement the work.

## Select the Execution Mode

Treat `--delegated` as an execution flag, not part of the ticket identifier.

- Without `--delegated`, perform the Prereader Contract in the main agent. Do
  not create a subagent.
- With `--delegated` in Codex, use the custom subagent named
  `implementation-prereader`:
  1. Before inspecting the ticket or repository, spawn exactly one such
     subagent.
  2. Give it the ticket or specification identifier and request the readiness
     brief defined below.
  3. Wait for its result. Check only that the required sections are present,
     then return the report without independently repeating the investigation.
  4. If the named subagent is unavailable, report that its configuration must
     be installed and stop. Do not silently substitute the parent model or a
     differently configured subagent.
- With `--delegated` in a non-Codex host, report that fixed-model delegation is
  unavailable and stop. Do not fall back to main-agent execution.

Delegated runs may not create additional preread or nested subagents.

## Budget

- Default runs use no subagent. Delegated runs use one read-only subagent only.
- Inspect only current authority and directly relevant code, tests, and docs;
  do not scan unrelated directories.
- Do not run builds, tests, migrations, generators, or any mutation.
- Return a 600–900 token brief without raw command logs or long source
  excerpts. If the evidence is insufficient, name the missing source and stop
  rather than broadening the search.

## Prereader Contract

The main agent in default mode, or the fixed-model prereader in delegated mode,
performs the following read-only work.

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
- In delegated mode, do not override the prereader model or reasoning level.
  The installed custom agent configuration is authoritative for that preread.
- Stop after producing the readiness brief.

## Recommend the Implementation Profile

For the later implementation run, choose only between `gpt-5.6-terra` and
`gpt-5.6-sol`. Choose the lowest-cost profile that has a credible path to
meeting the acceptance criteria and focused verification requirements.

Use only evidence found during this preread:

- Ambiguity: are acceptance criteria, ownership, and expected behavior clear?
- Coupling: how many modules, repositories, contracts, or lifecycle stages change?
- Failure cost: could a wrong change cause data loss, security exposure,
  compatibility breakage, or difficult rollback?
- Reasoning hazards: concurrency, ordering, migrations, deletion/cutover,
  negative paths, or non-local invariants.
- Verification strength: do focused tests, types, migrations, or established
  patterns independently detect a wrong implementation?

Choose `gpt-5.6-terra` when scope is bounded and current authority plus focused
verification make incorrect assumptions cheap to detect. Choose `gpt-5.6-sol`
when unresolved ambiguity, cross-boundary coupling, or failure cost requires
stronger judgment before implementation.

Use `medium` by default for a clear, bounded Task with a credible focused
verification plan. Use `high` only for multiple coordinated changes or one
material reasoning hazard. Use `xhigh` only when high failure cost combines with
concrete uncertainty, concurrency/ordering, migration/compatibility, or
cross-repository risk. Never recommend `max` initially; name it only as an
escalation after a fresh authority/code read and an unsuccessful lower-effort
attempt leave a specific issue unresolved.

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
- Model: `gpt-5.6-terra` or `gpt-5.6-sol`
- Reasoning: `medium`, `high`, or `xhigh`
- Evidence: two to four concrete signals from the ticket or code
- Why not lower: one sentence
- Escalate when: observable condition(s), not a generic difficulty label

## Handoff
- Three to six compact instructions for the later `$implement` run

This brief is orientation only. Before editing, re-read the current
authoritative ticket or specification, relations, repository state, and
relevant code. If they conflict with this brief, current authority and code win.
```

Keep the brief compact and source-backed. Include paths, identifiers, and commit
hashes that help the implementation run relocate evidence, but omit raw command
logs and long source excerpts.
