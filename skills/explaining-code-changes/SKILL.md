---
name: explaining-code-changes
description: Use when the user asks to explain or analyze what a commit or commit range changed — 分析/解释/讲讲 commit、"改动了什么"、"为什么这样改", or passes a commit SHA, a range like a..b, HEAD~n, a tag, or any git-diff-style revision argument for a code analysis report
---

# Explaining Code Changes

## Overview

Produce a code analysis report for ordinary/junior developers: what changed, what each piece does, and why it was changed. The reader has no context on this code — the report teaches, it does not just summarize.

Core principle: the commit message is the author's claim, the diff is the fact, the surrounding docs and callers are the why. Read all three.

## Step 1 — Parse the argument

| Input | Meaning | Main commands |
|---|---|---|
| one rev (`abc1234`, `HEAD~1`, tag, branch) | single commit | `git show <rev> --stat`, then the full `git show <rev>` |
| `a..b` or `a...b` | commit range: what b has that a lacks | `git log --oneline a..b` (list commits), `git diff a..b --stat` (combined effect) |
| two revs separated by space (`a b`) | direct diff between two points | same as range; note this in the report |

- For a range, report the change **as one whole** grouped by concern. List the commits involved, but do NOT write one report per commit.
- Ambiguous or unreachable rev: ask the user instead of guessing.

## Step 2 — Investigate

1. Read `--stat` plus the full commit message first. Work-item refs (AB#xxx), Why/Verification sections, and linked ADRs usually live there.
2. Read the diff **in logical groups** (new files / moves+renames / call-site updates / deletions / docs), not as one giant dump.
3. For moves and renames, read with rename detection; fetch pre-change versions with `git show <rev>^:<path>` when the old shape matters.
4. Chase the why beyond the message: referenced work items, ADRs under `docs/`, directory layout, callers of changed symbols.
5. Decide and state the commit's nature — pure refactor (zero behavior change), fix, feature, or mixed — and how you know.

## Step 3 — Report contract

Five fixed sections, in this order. Section labels stay in the report language:

1. **Header**（头部）— commit id + title, nature (refactor/fix/feature; behavior change or not), related epic/ADR/work item.
2. **Change list**（改动清单）— grouped by category (moves+exports / call-site updates / new / deleted / docs), every item as a markdown link in host format `[path](path:line)` (repo-relative path, colon + 1-based line). Never use GitHub-style `#L` anchors or invented `blob/<sha>` URLs — if lines have moved since the commit, link the current tree and say so in the reading notes.
3. **What each piece does**（功能说明）— per file / per function: what this file, method, or function is for, phrased for someone who has never seen the module. Explain jargon on first use with one plain sentence.
4. **Why it was changed this way**（为什么这样改）— the benefit, the root cause (e.g. a language visibility rule), the architectural driver. Quote the commit message or ADR as evidence.
5. **Reading notes**（注意点）— risk boundary, review tips, suggestions for the reader.

## Rules

- Report language follows the user's question language; keep technical terms and identifiers in original form.
- Verify claims against the diff, not just the commit message; if they disagree, trust the diff and say so.
- Output the report in the chat unless the user asks for a file.

## Common mistakes

| Mistake | Do instead |
|---|---|
| Restating the commit message | Read every diff block; verify the message's claims |
| Reporting only what, never why | Chase work items / ADRs / callers for motivation |
| Unexplained project jargon for juniors | One plain-language sentence on first use |
| Range rendered as N separate reports | Synthesize one whole-range report, grouped by concern |
| Dumping a huge diff at once | Read in logical groups |
| GitHub-style `#L` anchors or `blob/<sha>` links | Host format `[path](path:line)` |
