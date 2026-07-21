# Closeout comment template

Copy this into the `--comment-file` passed to `close-task`. Fill each section from
the work just done; drop a heading only when it has no content. Keep it concise —
the commit and the work item already carry the detail.

```markdown
## Completion
<one or two lines: what behaviour was delivered, referencing the work-item scope>

Implemented in <commit-sha>: <areas changed>.

## Verification
<focused commands run, with their pass evidence — not the full suite>

- `<command>` → <result, e.g. 42 passed, 0 failed>

## Remaining work
<follow-ups, deferred items, or blockers; or "None.">
```

Notes:

- Write the file once; `close-task` HTML-escapes and Markdown-stamps it. No manual
  escaping of `<`, `>`, `&`, or backticks is needed.
- Quote commands verbatim inside backticks so reviewers can reproduce them.
