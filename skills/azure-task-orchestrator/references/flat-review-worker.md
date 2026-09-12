# Flat Review Worker Contract

The Azure orchestrator uses this contract after an implementation worker has
created a task-only commit. The parent starts exactly two read-only workers in
parallel for each review round: one `standards` worker and one `spec` worker.
The workers do not start children, edit files, create commits, or call Azure
Boards.

## Inputs

The parent supplies each worker with:

- `reviewAxis`: `standards` or `spec`;
- `reviewBase`: the implementation worker's starting commit;
- `head`: the implementation worker's current task commit;
- the work-item scope and acceptance evidence;
- the first-round review reports and repair findings when this is a later
  round.

The worker must resolve `reviewBase`, confirm that
`git diff <reviewBase>...HEAD` is non-empty, and inspect the actual diff. Do
not review a guessed range, a PR's advertised base, or only the latest commit.
The worker must not change the working tree or Git refs while reviewing.

## Axis rules

This contract extracts the two review criteria from `$code-review` for a
parent-started axis worker. Execute only the supplied axis in this worker. Do
not invoke the external review coordinator, do not ask it to spawn another
worker, and do not treat an inability to spawn as a reason to run both axes in
this worker. The parent has already provided the other axis to a separate
worker.

For `standards`, find the repository's documented coding standards and apply
this smell baseline. Documented repository rules override the baseline, and
baseline smells remain judgement calls:

- Mysterious Name → rename it to reveal its purpose.
- Duplicated Code → extract the shared shape.
- Feature Envy → move behavior onto the data it uses.
- Data Clumps → bundle the repeated fields into a type.
- Primitive Obsession → introduce a small domain type.
- Repeated Switches → centralize the dispatch or use polymorphism.
- Shotgun Surgery → gather the change in one module.
- Divergent Change → split unrelated reasons to change.
- Speculative Generality → remove abstractions without a real use.
- Message Chains → hide long navigation behind one method.
- Middle Man → call the real target directly.
- Refused Bequest → prefer composition when inheritance is not used.

Skip anything tooling already enforces. Report the file/hunk and the governing
rule or smell for every finding.

For `spec`, identify the originating issue from commit messages, then a
user-supplied path, then a matching file under `docs/`, `specs/`, or `.scratch/`.
If the parent has explicitly established that no specification exists, report
`no_spec_available` rather than inventing requirements. If the source is still
unresolved, return a review failure; do not silently treat an unresolved path
as an absent specification. Compare the actual diff with the available
requirements and report missing, extra, or incorrect behavior with concrete
evidence.

## Result contract

Return JSON only:

```json
{
  "axis": "standards",
  "reviewBase": "<sha>",
  "head": "<sha>",
  "status": "clean",
  "findings": [],
  "summary": "..."
}
```

`axis` must match the requested axis and `reviewBase` must match the supplied
fixed point. Use `status: "findings"` when findings exist and
`status: "no_spec_available"` only for the Spec axis. Every finding must
include `priority` (`P0`–`P3`), `location`, `summary`, and `evidence`; set
`blocking: true` only for a P0/P1 or an explicitly blocking correctness,
security, data-loss, or verification problem. A malformed result, mismatched
fixed point, or failed diff check is a review failure, not a clean result.
