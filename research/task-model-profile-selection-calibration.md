# Task model profile selection calibration

Date: 2026-07-18

## Question

Should any cross-module, cross-boundary, or cross-repository Task automatically
receive the strongest model at `xhigh` reasoning effort? If not, what evidence
should drive the model and effort choices?

## Conclusion

No. Neither OpenAI's current model guidance nor the comparable agent-engineering
guidance reviewed here supports topology alone as an automatic
`sol-xhigh` trigger.

The reliable rule is:

1. Choose the **model family** from the amount of judgment the Task requires:
   unresolved semantics, authority conflicts, weak feedback, and the consequence
   of a wrong decision.
2. Choose the **reasoning effort** separately from the depth and duration of the
   reasoning path: non-local invariants, ordering or concurrency, migration
   design, repeated tool use, and long-horizon exploration.
3. Treat module/repository/contract count only as evidence that may create those
   conditions. A boundary whose contract is already authoritative, mechanical,
   and independently verified is not by itself a reason to select Sol or
   `xhigh`.

The current planner does not literally say “any boundary means `sol-xhigh`.”
It says Sol is appropriate when cross-boundary coupling *requires stronger
judgment*, and says `xhigh` requires high failure cost combined with another
hazard. However, listing “cross-boundary coupling” in the Sol clause and
“cross-repository risk” in the `xhigh` clause gives an agent enough ambiguity
to treat topology as a shortcut. The criteria should therefore use explicit
gates rather than a list of loosely connected signals.

## Workflow premise

In the intended workflow, model planning does not start from an unrefined
request. `/grill-with-docs`, `/to-spec`, and `/to-tickets` have already:

- challenged the design and recorded the resulting decisions;
- turned the accepted direction into an authoritative Story description or a
  linked implementation specification;
- decomposed that specification into Azure Tasks with scope, acceptance
  criteria, relations, and execution order.

This changes the planner's job. It should classify **residual implementation
uncertainty**, not charge again for ambiguity and coupling that the upstream
workflow has already resolved. Cross-repository scope recorded in a
specification and dependency graph is coordination metadata, not evidence that
the implementation worker needs the strongest model.

The premise must nevertheless be verified rather than assumed. The current
planner can also be invoked directly on an arbitrary Story, ticket, or
specification. It should therefore confirm that the authoritative Story
description or linked specification and agent-ready Tasks exist and are
mutually consistent. Missing upstream artifacts should produce an
incomplete-input report or route back to the planning workflow; they should not
be converted into a stronger execution profile.

## Evidence

### Official OpenAI guidance

OpenAI describes GPT-5.6 Sol as the flagship for “complex reasoning and coding”
and Terra as the option that balances intelligence and cost. It does not define
cross-module or cross-repository work as an automatic Sol condition. Both
models support the same documented reasoning-effort range, so model family and
effort are technically separate choices. [OpenAI model
selection](https://developers.openai.com/api/docs/models)

OpenAI's GPT-5 developer guidance says higher effort tends toward quality and
lower effort toward speed, but explicitly warns that tasks benefit unequally
from extra reasoning and recommends evaluating the actual use case. It gives
simple long-context retrieval as an example where reasoning above `low` added
little, while a visual-reasoning benchmark benefited materially. That is direct
evidence against a single structural proxy such as repository count.
[OpenAI GPT-5 developer
guidance](https://openai.com/index/introducing-gpt-5-for-developers/)

OpenAI reports several coding and tool-use benchmarks at `high` reasoning
effort. Those results establish that stronger reasoning can help hard coding and
agentic work, but do not establish that `xhigh` is a universal coding default or
that crossing a boundary requires it. [OpenAI GPT-5 coding and agentic
evaluations](https://openai.com/index/introducing-gpt-5-for-developers/)

### Official Anthropic guidance, used only as a cross-vendor analogue

Anthropic's current effort documentation gives workload-shaped definitions:
`medium` balances speed, cost, and performance; `high` is for complex reasoning,
difficult coding, and agentic tasks; and `xhigh` is for long-horizon coding and
agentic work, described as more than 30 minutes with token budgets in the
millions. It also recommends testing the actual use case and dynamically
adjusting effort to task complexity. It does not use module or repository count
as the classifier. [Anthropic effort
documentation](https://platform.claude.com/docs/en/build-with-claude/effort)

This is not evidence about the exact performance curve of GPT-5.6 Sol or Terra.
It is relevant engineering evidence that an effort tier represents depth,
duration, and token/tool budget rather than codebase topology.

Anthropic also documented a real Claude Code calibration failure: changing the
default from `high` to `medium` reduced latency but users perceived lower
intelligence, so Anthropic restored the stronger default while preserving lower
effort as an opt-in for simple tasks. The same report says medium had slightly
lower intelligence with substantially lower latency on most internal tasks.
The lesson is not “always use high”; it is that effort has a measured
quality/latency tradeoff and should be calibrated against representative tasks,
not guessed from one metadata field. [Anthropic Claude Code effort
postmortem](https://www.anthropic.com/engineering/april-23-postmortem)

### Community experience, not official policy

An open Codex feature request proposes choosing an initial effort tier from
external signals, then retuning as local uncertainty, risk, and reversibility
become clearer. It also reports practitioner failure modes from
over-allocation: over-planning, second-guessing clear errors, architectural
wandering, and unnecessarily large patches. This is a user proposal, not an
accepted OpenAI design or benchmark, so it should be treated as a useful
hypothesis rather than authority. [OpenAI Codex issue
#20855](https://github.com/openai/codex/issues/20855)

## Diagnosis of the current planner

The current [`task-model-planner`
instructions](../skills/task-model-planner/SKILL.md) correctly contain three
important safeguards:

- choose the lowest-cost credible profile;
- do not escalate merely because a Task is large;
- require high failure cost plus a concrete hazard for `xhigh`.

The remaining problem is classifier leakage:

- “cross-boundary coupling” appears alongside unresolved ambiguity and failure
  cost in the Sol sentence, so a reader can incorrectly treat any boundary as
  sufficient;
- “cross-repository risk” appears in the `xhigh` sentence without defining what
  makes that risk material;
- model family and effort are described sequentially, but there is no explicit
  instruction to decide them independently;
- “why not lower” can bias the report toward defending escalation instead of
  testing whether the lower profile is sufficient.

## Recommended inference standard

Use two independent gates. Do not add points for repository or module count.
Counts identify where to inspect; evidence about decisions and verification
determines the profile.

Use four regular profiles for agent-ready Tasks: `terra-medium`, `terra-high`,
`sol-medium`, and `sol-high`. Make `terra-high` and `sol-medium` the two primary
profiles. `terra-high` fits implementation whose decisions are settled but
whose mechanics retain a material hazard; `sol-medium` fits bounded work whose
hard part is residual judgment rather than a long implementation path. They are
the two central rungs in the scenario-specific regular escalation order:
`terra-medium` → `terra-high` → `sol-medium` → `sol-high`. Reserve
`terra-medium` for genuinely straightforward execution, `sol-high` for the
compounded case, and every `xhigh` profile for exceptions outside that ladder.

### Gate A: choose Terra or Sol

Choose **Terra** when all of the following are true:

- the specification and Tasks contain the decisions expected from the upstream
  grilling and decomposition workflow;
- the required behavior and ownership are already authoritative;
- boundary contracts are fixed, generated, versioned, or demonstrated by an
  established pattern;
- implementation choices are local or mechanical even if edits span several
  modules or repositories;
- focused tests, compilation, schema checks, contract tests, or reversible
  rollout independently expose a wrong change;
- no unresolved decision has high security, data-integrity, compatibility, or
  rollback consequences.

Choose **Sol** only when at least one judgment gate is supported by evidence:

- the specification, Task, current code, or another current authority conflict;
- the Task explicitly delegates a still-open product, domain, or architectural
  decision to the implementer;
- the implementation must invent or renegotiate a boundary contract rather
  than consume an established one;
- a wrong design decision has material consequences and verification is weak,
  delayed, or unable to distinguish competing interpretations;
- ownership, lifecycle, security, data migration, or compatibility decisions
  remain unresolved before coding;
- current evidence is incomplete enough that choosing the implementation path,
  not merely finding the files, is the hard part.

Cross-boundary work is therefore a **review prompt**, not a Sol trigger. It asks:
“Is this an established seam being followed, or a seam whose meaning must be
decided?”

Do not treat missing acceptance criteria or an absent specification as a Sol
gate. Those are planning-input failures. Raising the model would hide a broken
workflow contract instead of repairing it.

### Gate B: choose medium, high, or xhigh

Choose **`medium`** when the implementation path is bounded, the feedback loop
is strong, and no material non-local invariant must be held across many steps.
This can include a mechanical cross-repository propagation such as updating a
pinned generated contract and running authoritative builds in each consumer.

Choose **`high`** when there is one material reasoning hazard or several
coordinated changes, for example:

- concurrency, ordering, shutdown, retries, or idempotency must remain correct;
- a migration or compatibility transition has a clear design but multiple
  coordinated steps;
- debugging requires several hypotheses or repeated tool/test loops;
- correctness depends on a non-local invariant across components;
- the verification plan is credible but interpreting failures requires
  substantial reasoning.

Choose **`xhigh`** only when both conditions below hold:

1. The Task requires extended exploration or a genuinely long reasoning
   horizon: many interdependent tool loops, large-context synthesis, repeated
   hypothesis testing, or an expected long-running autonomous implementation.
2. At least one severe hazard remains: unresolved semantics, concurrency or
   ordering with weak observability, irreversible migration/cutover,
   compatibility across independently changing systems, high-consequence
   failure with weak verification, or a non-decomposable cross-repository
   invariant.

If the work can be decomposed into independently verifiable Tasks, decompose or
plan those Tasks separately instead of using `xhigh` to compensate for an
over-broad scope. Within the current six-profile registry, `sol-high` should be
the normal ceiling for difficult but bounded implementation; `sol-xhigh` should
be exceptional.

### Examples

| Task shape | Recommended starting profile | Reason |
|---|---|---|
| Update a generated protocol in two repositories; contract and regeneration commands are authoritative; both consumers compile and test | `terra-medium` or `terra-high` | Cross-repository, but semantic choices are already made and verification is strong |
| Rename an API and update three known call sites with focused tests | `terra-medium` | Multiple modules do not create a reasoning hazard |
| Implement a clear compatibility shim across producer and consumer with a specified rollout order | `terra-high` | Coordinated boundary work with a known design |
| Ticket lacks the linked specification or omits the acceptance criteria expected from the upstream workflow | No profile; incomplete input | Missing planning authority is not an execution-model problem |
| Decide ambiguous ownership between two runtimes where shutdown ordering and cleanup can race | `sol-high` | The hard part is judgment over lifecycle semantics and concurrency |
| Design and execute an irreversible data cutover across independently deployed systems with incomplete compatibility authority and weak rollback proof | `sol-xhigh` | Long horizon plus unresolved semantics, high failure cost, and weak verification |
| Change one local authorization rule whose acceptance criteria conflict and whose negative paths are poorly tested | `sol-high` | Same-repository work can require Sol; repository count is irrelevant |

## Proposed planner wording principles

The skill should encode these rules explicitly:

- “Cross-module, cross-boundary, and cross-repository scope never determines a
  profile by itself.”
- “Select model family and reasoning effort independently.”
- “Use Sol for unresolved judgment, not for file or repository count.”
- “Use `xhigh` only when long-horizon exploration combines with a severe
  reasoning hazard; otherwise prefer `high`.”
- “For every recommendation, state which exact gate disqualifies the next lower
  profile. If no gate is evidenced, choose the lower profile.”
- “Treat strong verification and reversibility as reasons to stay lower, even
  when coupling is broad.”

## Validation recommendation

The thresholds remain an inference until measured on this repository's own
delivery history. Build a small calibration set containing at least:

- bounded cross-repository propagation with strong tests;
- local but ambiguous lifecycle/concurrency work;
- reversible and irreversible migrations;
- tasks with strong and weak verification;
- examples previously assigned `sol-xhigh`.

Blindly score each Task at adjacent profiles, then compare completion,
review findings, retries, patch size, latency, and token/tool use. The planner
should be adjusted from those results. Official guidance consistently recommends
workload-specific evaluation; no source reviewed provides a universal
topology-to-profile mapping.
