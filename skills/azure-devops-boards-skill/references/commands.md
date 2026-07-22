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
sh "$HELPER" implement-preflight --id 61

sh "$HELPER" create \
  --type Task --title 'Implement contract' \
  --description-file /tmp/task.md --parent 61 \
  --tags ready-for-agent

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

## Keep implementation synchronization compact

For one implementation-ready work item, run `implement-preflight` once before
editing. It returns a compact snapshot of the revision, type, state, title,
structured acceptance criteria (or the full Description when it cannot safely
extract them), and relation IDs. Keep it as the scope authority for the current
thread. Re-run only after an item, branch, or session change, or when a scope
conflict appears.

At closeout, run `close-task` once with `--apply`, passing the preflight `rev`
as `--expected-rev` — the invariants above apply unchanged (one call, fail-fast
on a stale rev, no retry). It persists the evidence-backed Description rewrite,
terminal state, and one Markdown completion comment; it verifies both persisted
results, and the two Azure operations are not atomic.

Read [azure-boards-api.md](azure-boards-api.md) only when endpoint behavior or relation semantics need investigation.
