# Azure Boards helper commands

Reference for the `task-boards-ops` agent and the fallback path (when agent
spawning is unavailable). Documents how to resolve the helper, required
configuration, behavioral invariants, and every available command.

## Resolve the helper

The helper is `scripts/azure-devops-boards.sh`, invoked through `sh` by **absolute path** — a bare relative path fails, since the shell runs from the project root, not the skill folder. Resolve the exact path for your host from [setup.md](setup.md), set `HELPER` to it, then use `sh "$HELPER"` in the examples below.

## Require configuration

Require an installed, authenticated Azure CLI with the `azure-devops` extension. Pass connection flags explicitly, or set these once per shell session to make them optional on every call:

- `AZURE_DEVOPS_ORG`, `AZURE_DEVOPS_PROJECT`, `AZURE_DEVOPS_TEAM`
- `AZURE_CLI_PYTHON` when the launcher cannot locate Azure CLI's Python runtime

Read the repository's tracker instructions before operating. Treat its work-item types, states, Sprint rules, tags, acceptance criteria, and workflow gates as authoritative.

## Invariants

- Read the relevant work item before changing it.
- Do not search for duplicate work items before creating one. Create directly — the caller knows what it intends to create, and pre-creation duplicate queries cost more than the occasional duplicate they would prevent. Only search for existing items when the user explicitly asks to check.
- Prepare long descriptions and comments in temporary Markdown files.
- When closeout needs acceptance-criteria synchronization, read the full
  Description, preserve all non-checklist content, mark only checklist items
  backed by explicit implementation evidence, and pass the result with
  `close-task --description-file`. Post the completion comment in the same
  closeout call. `--check-ac` is an opt-in server-side alternative and is
  mutually exclusive with `--description-file`.
- Run a mutation once with `--apply` by default — the helper validates server-side, applies, and read-back-checks the persisted result in a single call. Use the opt-in two-phase form (the identical command without `--apply`, reviewed, then repeated with `--apply`) only for high-risk changes or when a human should review before the write.
- A stale `/rev` — the item changed since it was read — fails the mutation immediately, with no automatic retry. Re-read and reconcile before retrying.
- `az boards work-item update --discussion` is off-limits: it posts plain text, not a native relation. Express dependencies with `add-link` instead.

## Use the commands

```bash
sh "$HELPER" current-sprint
sh "$HELPER" show --id 61               # compact default (id/rev/type/state/title/relations)
sh "$HELPER" show --id 61 --full        # raw Azure JSON
sh "$HELPER" planning-snapshot --story 61 # Story + direct New Task/Bug targets only
sh "$HELPER" planning-snapshot --id 123 --id 124 # explicit Task/Bug set, stable input order
sh "$HELPER" implement-preflight --id 61

sh "$HELPER" create \
  --type Task --title 'Implement contract' \
  --description-file /tmp/task.md --parent 61 \
  --tags ready-for-agent

sh "$HELPER" create \
  --type Bug --title 'Crash during planning' \
  --description-file /tmp/bug.md \
  --repro-steps-file /tmp/repro-steps.md \
  --system-info-file /tmp/system-info.md

sh "$HELPER" create \
  --type Bug --title 'Crash during planning' \
  --description-file /tmp/bug.md \
  --comment-file /tmp/initial-repro.md

sh "$HELPER" update \
  --id 123 --state Active --description-file /tmp/task.md

sh "$HELPER" add-comment \
  --id 123 --comment-file /tmp/comment.md

sh "$HELPER" add-link \
  --id 124 --kind predecessor --target-id 123

sh "$HELPER" close-task \
  --id 123 --expected-rev 8 --state Closed \
  --description-file /tmp/description.md --comment-file /tmp/completion.md
```

Add `--apply` after validation. Before using `--description-file`, keep all
Description content other than the evidence-backed Markdown checklist markers
unchanged. `--check-ac` reads the live Description, checks matching markdown
checkboxes (`all`, or a case-insensitive fragment that must uniquely match
exactly one item — ambiguous fragments raise), and patches it back in the same
mutation; it is mutually exclusive with `--description-file`. For
`predecessor`, `--target-id` blocks the current `--id`. For `parent`, the target
is the current item's parent. Re-adding an existing relation returns `unchanged`.
When creating a Bug, pass reproduction and environment evidence through
`--repro-steps-file` and `--system-info-file`; do not put those authoritative
values only in a Discussion comment. If an initial `--comment-file` is supplied
for a Bug and no `--repro-steps-file` is supplied, the helper treats that one
creation-time payload as `Microsoft.VSTS.TCM.ReproSteps`. If Repro Steps are
explicit, or if `add-comment` is used after creation, the payload remains a
real Discussion comment. The Bug-specific flags are rejected for non-Bug work
items. Use comments for supplemental context. Repro Steps and System Info files
remain Markdown and are sent verbatim; the helper does not convert them to HTML
or add Description's Markdown metadata to those fields.

## Keep implementation synchronization compact

For Story planning, run `planning-snapshot --story` once. It validates the
parent as a Story/User Story, then uses a server-side direct link query to
select only the Story's direct `New` `Task` and `Bug` children; it does not read
a non-New child. For an explicit set, repeat `--id` in one
`planning-snapshot` call for each requested Task or Bug. It validates each type
and preserves the supplied order without inventing a parent. The single JSON
result includes the Story or explicit targets and
each selected target's full fields, multiline formats, raw and normalized
relations, attachment relations, linked references, complete comments/discussion,
and a scope summary. An empty Description falls back to type-specific fields, which is
required for Bugs that record repro data outside `System.Description`, such as
`Microsoft.VSTS.TCM.ReproSteps`, `Microsoft.VSTS.TCM.SystemInfo`, and (when
present) `Microsoft.VSTS.TCM.FoundInBuild` or acceptance/severity fields. If
those fields are empty, the complete Discussion comments remain authoritative
context; ticket creation must not hide that context behind a comment-only
summary.
`discussion.comments` is the paginated Work Item Comments API result. It is
separate from the optional full revision/update history; the latter is not
needed to determine the current planning scope.

`linkedReferences` contains raw attachment or hyperlink relations only. It does
not claim to contain specification documents. The parent orchestrator must
preserve that raw list and add one `linkedSpecifications` decision per raw
reference: `{reference, material, content}`. A material decision requires
non-empty full Markdown content; an unmatched reference or missing material
content means the planner must return `Input not ready`. The parent must not
infer specification content from a URL or relation metadata.

For one implementation-ready work item, run `implement-preflight` once before
editing. It returns the revision, type, state, title, all fields, multiline
formats, comments/discussion, attachments, relations, and a type-neutral scope
summary. For a Bug, inspect the complete `fields` map and
`scope.knownBugFields`; do not assume `System.Description` or those known
fields are populated. Use `discussion.comments` as the fallback source when
the ticket creator put the reproduction evidence there. Keep it as the scope
authority for the current thread. Re-run only
after an item, branch, or session change, or when a scope conflict appears.

At closeout, run `close-task` once with `--apply`, passing the preflight `rev`
as `--expected-rev` — the invariants above apply unchanged (one call, fail-fast
on a stale rev, no retry). It persists the evidence-backed Description rewrite,
terminal state, and one Markdown completion comment; it verifies both persisted
results, and the two Azure operations are not atomic.

Read [azure-boards-api.md](azure-boards-api.md) only when endpoint behavior or relation semantics need investigation.

For planning snapshots, the field/discussion boundary follows the Microsoft
documentation: [Work Items - Get Work Item](https://learn.microsoft.com/en-us/rest/api/azure/devops/wit/work-items/get-work-item?view=azure-devops-rest-7.1)
returns the current `fields` and `relations`, [Comments - Get
Comments](https://learn.microsoft.com/en-us/rest/api/azure/devops/wit/comments/get-comments?view=azure-devops-rest-7.1)
returns paginated Discussion comments, and [Define, capture, triage, and
manage bugs](https://learn.microsoft.com/en-us/azure/devops/boards/backlogs/manage-bugs?view=azure-devops)
documents Bug-specific Repro Steps, System Info, and Found in Build fields.
The [Revisions - List](https://learn.microsoft.com/en-us/rest/api/azure/devops/wit/revisions/list?view=azure-devops-rest-7.1)
and Updates APIs are historical change streams, not a replacement for the
current fields plus Discussion comments used by the planner.
