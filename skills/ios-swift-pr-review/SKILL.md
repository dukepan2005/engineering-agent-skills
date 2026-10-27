---
name: ios-swift-pr-review
description: Run evidence-backed, read-only reviews of iOS Swift changes supplied as a pull request, commit, commit range, staged changes, or working-tree changes. Trace runtime and contract regressions using the target repository's AGENTS.md, architecture, dependencies, and verification workflow.
---

# iOS Swift PR Review

Review the selected change delta, not an isolated method. Report only regressions introduced by that delta that can occur through a real app, background, or testable integration path. Choose checks by changed behavior and risk; no fixed quota of hypotheses, experiments, screenshots or test suites is required. Produce a human review, not review JSON or provider comments.

## Authority and Workspace Safety

- Resolve the target repository from the request, PR metadata and checkout remotes. Ask only when the target remains ambiguous; do not infer a repository from this skill's installation path.
- Read the target repository's root `AGENTS.md`, applicable parent/control-repository instructions and any scoped `AGENTS.md` for changed paths. Follow their links to architecture, conventions, requirements and verification documents only as relevant. Project-specific rules belong there, not in this skill.
- Record checkout, branch, HEAD, worktree status and any relevant submodule state before inspection. Preserve pre-existing changes; do not reset, switch branches, regenerate dependencies or create commits.
- Discover workspace/project, schemes, deployment target, Swift mode, dependency manager, lockfiles, generated-source ownership and protocol source from repository instructions and build configuration. Do not assume names, paths, locale sets, frameworks, a submodule layout or a particular dependency manager. If `AGENTS.md` is absent or silent, use checked-in documentation/configuration and state consequential assumptions.
- Before builds/tests, inspect the applicable dependency inputs and lockfiles. Use the repository's documented workspace/project, cache, signing and package-resolution settings; preserve locked versions and avoid routine dependency updates. Generated artifacts are reviewed through their authoritative sources and documented generation checks; do not hand-edit them.

## Workflow

1. Resolve and record the review range before inspecting code:
   - For a PR, resolve its base, head, and merge-base; review `merge-base...head`. Never assume the default branch is the base.
   - For `review commit C`, resolve `C^1` and `C`; review `C^1...C`. For a merge commit, state that the first parent was used unless the user supplies another parent.
   - For `review A..B`, resolve both commits and require `A` to be an ancestor of `B`; review `A...B` and list commits with `A..B`. If they are not ancestral, stop and ask for an explicit base or permission to use their merge-base. Do not silently review an unrelated range.
   - For `review since F`, resolve `F` and `HEAD`; review `F...HEAD` only after reporting the chosen merge-base.
   - For `review staged changes`, inspect only `git diff --cached`; record `HEAD` as the index baseline and do not include unstaged or untracked files.
   - For `review uncommitted changes` or `review working tree`, inspect both `git diff --cached` and `git diff`, then inspect every untracked file listed by `git status --short`. Record staged, unstaged, and untracked scope separately; `git diff HEAD` alone is insufficient because it omits untracked files.
   - For `review unstaged changes`, inspect `git diff` and report staged or untracked files as excluded unless the user expands scope.
   - If the user supplies both a commit range and working-tree changes without saying whether they are additive, ask before reviewing.
   Record resolved base, head, merge-base, commit list, and exact diff command in the review.
2. Read `AGENTS.md`, the PR description or commit message, and the owning task/specification. Derive the required behavior independently of the author’s explanation and tests. Resolve current task acceptance criteria when they materially determine scope; distinguish authoritative requirements from the author’s acceptance report. Attribute findings to changed hunks; separate pre-existing context. Before the detailed pass, identify the consequential risks and invariants using the guidance below.
3. Trace each suspected defect from a real entry point: app launch, scene/app delegate, the repository's root router, view-controller action, delegate/data source, notification, stream, timer, network completion, background task, or persisted-state restore. A direct call to an internal helper is not production-path evidence.
4. Check changed behavior and applicable integration boundaries:
   - UIKit/SwiftUI ownership, view-controller containment, existing XIB/Storyboard outlets, presentation/dismissal, navigation, accessibility and main-thread UI work;
   - Swift concurrency, `Task`/timer/stream cancellation, stale-result suppression, Rx disposal, retain cycles, and lifecycle ownership;
   - request construction, response/outcome decoding, typed business rejection versus system/transport failure, request IDs, retries, and user-facing error presentation;
   - generated-source/import boundaries, source protocol revisions, wire compatibility and dependency lockfile discipline according to the repository;
   - localization through the repository's lookup/formatting mechanism across its supported locales, privacy disclosures and state reconciliation after app backgrounding, relaunch or concurrent actions;
   - focused XCTest/Swift Testing coverage for consequential changed branches and races.
5. Apply Swift checks only to changed behavior: ownership and capture semantics, `@MainActor`/main-queue correctness at UI boundaries, error propagation, deterministic cancellation, value/reference mutation safety, and availability consistent with the deployment target. Do not turn style preferences into findings.
6. Select proportionate verification using the guidance below, without modifying tracked files. Resolve material uncertainties before expanding test scope; report exact commands, results and unexecuted checks.

## Risk-Directed Review and Counterexamples

- Prioritize by user impact and likelihood, especially changed ownership, persistence, authentication, concurrency, and boundaries between modules. State the leading risks briefly before the detailed pass; scale the depth to the delta rather than imposing a fixed number of hypotheses or agents.
- For consequential changed behavior, derive a concrete counterexample from the required invariant before relying on the author's tests: real entry point, triggering input/event order and observable failure. Try to disprove it through guards, callers, base behavior and relevant assertions. A passing test rules out only the trigger/interleaving it exercises; fixtures may repeat the implementation's mistaken assumption.
- Trace sequences across owners, not only individual functions: for example failure → back → reopen → edit → retry, or cancellation/account change while a response is suspended. Choose sequences suggested by the changed code. Include navigation, busy state, local input, persisted state and delayed callbacks where they interact.
- If existing evidence leaves a consequential trigger/interleaving unresolved, use the smallest discriminating check: a targeted existing test, controlled delay/failure injection or temporary reproduction through the actual caller. A private-helper test alone does not establish reachability. Keep experiments in scratch copies or supported overlays outside the reviewed checkout. If evidence already resolves the hypothesis, no new experiment is needed; if a check is infeasible, keep it unresolved and state the limit.
- When changed client behavior depends on server semantics, inspect the relevant source contract and available owning server implementation at a recorded revision. Verify assumptions such as version advancement, retry effects, partial success and resource identity. Matching generated files prove schema consistency, not matching behavior. Distinguish source inspection, fixture tests and real cross-end evidence; keep this check bounded to the assumptions the delta uses.
- For nontrivial deltas, update a compact ledger as evidence is read: inspected behavior/file groups, material hypotheses and their status — confirmed, ruled out or unresolved — with supporting evidence or the remaining gap. Record truncated/unread relevant ranges immediately, then fetch them or disclose the coverage gap; a file inventory is not proof of inspection. Generated files may be checked through authoritative sources and generation checks; identify that coverage method.
- On a re-review, re-resolve the range and revisit unresolved or weakly supported hypotheses. Reuse still-valid checks from the same revision with clear attribution; rerun only when the new hypothesis, code or environment warrants it. Earlier “no findings” is not evidence against a new hypothesis.

## SwiftUI Changes Only

Apply this section only when the delta changes SwiftUI behavior or its state/hosting integration. Select relevant risks; UIKit-only changes do not trigger it.

- **State and identity:** trace owned versus injected state, intentional one-time seeds versus changing parent inputs, and view/list identity across insertion, reordering or account changes. Look for stale input, unintended resets or state attached to the wrong item.
- **Async lifecycle:** trace `.task`, `.task(id:)` and appearance-driven work through re-entry, changed inputs and cancellation; check duplicate effects and late results overwriting newer state.
- **Navigation and presentation:** reconcile paths, selection and presentation bindings through back, dismissal, reopen and supported restoration; check stale destinations or lost edits.
- **UIKit integration:** follow representable creation/update/teardown, Coordinator and hosting ownership, and both directions of state propagation; check missing updates, lingering work or feedback loops.

Use the same reachable-trigger and evidence standard as other findings. Property-wrapper preferences or modernization alone are not defects; these prompts add no mandatory test matrix or migration.

## Conditional Companion Checks

- Use an available UIKit or SwiftUI companion skill when it adds relevant implementation guidance or repository instructions require it. Apply it only to the corresponding UI technology; repository rules override companion conventions.
- Use an iOS Simulator debugger skill only when runtime reproduction, UI inspection, or logs are needed; do not launch the app merely to make a speculative finding.
- Use protocol or backend review guidance only when the PR changes source protocol definitions, generated artifacts, or a cross-repository contract. Do not hand-edit generated Swift protobuf solely to satisfy a review preference.
- Use a design/spec reviewer only when a PRD, RFC, acceptance criteria, or product decision materially governs the change.

## Finding Standard

Report a finding only when all of the following are true:

- It is in the PR delta, or the delta makes a previously safe path unsafe.
- It has a precise head `file:line`.
- A real runtime or data path reaches it.
- A trigger condition or reproduction is concrete.
- Existing tests do not already prove the behavior safe.

Do not report broad refactors, optional modernization, theoretical retain cycles, generic force-unwrap concerns, or pre-existing defects as PR findings.

## Output

Lead with the resolved range and exact diff command. For each P0/P1/P2 finding, give priority, head `file:line`, changed-hunk evidence, reachable path, trigger, impact, focused fix and test gap. If none qualify, say `No actionable findings` and state coverage and limitations; this does not resolve outstanding hypotheses.

For material hypotheses, use explicit confirmed/ruled-out/unresolved statuses with evidence or gaps; avoid ambiguous “not confirmed” conclusions. Keep this proportional: a short inline ledger is enough, with a separate report only when useful. Identify single-agent versus independent review. Separate newly executed checks from reused results at recorded revisions, and static reasoning, controlled tests, visual inspection and real integration. Include failures, skips and exclusions; test totals do not guarantee correctness.

## Proportionate Verification

- Start with `git diff --check` and applicable repository static checks. For localized copy, check resource syntax, supported locale coverage, placeholders and fallbacks.
- Prefer affected XCTest/Swift Testing methods first, then related recovery/boundary tests. Expand to classes or suites only for a concrete shared impact, failure or coverage gap, and explain why. A class may be the smallest useful selection when its tests are tightly coupled or finer selection is unavailable. Stop when the selected risk is resolved unless repository requirements demand more.
- For material layout, typography, navigation or input-presentation changes, visually inspect a small representative set of affected screens/states against the governing design or expected behavior. Choose long text, text scaling, keyboard or failure states where the delta creates risk; do not require a device/locale matrix. Reuse suitable screenshots from the reviewed revision; capture new ones only when needed. Generated attachments and geometry assertions alone are not visual review. If inspection is unavailable, report the visual gap.
- Use the repository's build entrypoint, reusable caches and an available compatible destination; record actual signing, Keychain or software-keyboard prerequisites. Preserve unrelated simulator settings and data.
- Separate static reasoning, controlled tests, visual inspection and real integration. Report focused/full-suite results, failures, skips and deliberately excluded tests accurately; compilation, fixture success and test totals do not establish unexercised behavior.
- Do not flag architecture merely because the app uses UIKit, SwiftUI, RxSwift, XIBs, CocoaPods or existing navigation conventions. Require a reachable regression or violation of an established repository contract.
