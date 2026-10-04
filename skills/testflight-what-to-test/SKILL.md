---
name: testflight-what-to-test
description: Use when writing TestFlight What to Test notes, beta tester notes, or App Store Connect test instructions for a build. Default diff is HEAD vs origin/develop; also when the user names any two branches or two commits.
---

# TestFlight What to Test

Write notes a tester will actually read in the TestFlight app on a phone. English only. Paste-ready. No preamble.

## Steps

1. Diff two git refs. Default: `HEAD` vs `origin/develop`. User may name any two branches, any two commits, or a range (`a..b`). Tester-visible behavior only: screens, taps, errors, membership. Skip tests, refactors, docs, protocol-only sync. Unreachable refs: ask; do not guess.
2. Group by surface a tester can open. One line per surface. Drop a surface if the delta does not change it.
3. Emit **2–3 short lines** in a fenced block. Done when a tester can finish reading without scrolling.

## Shape

```
Surface: action → result; next action → result.
Surface: constraint; fallback.
Surface: cap or recovery; what must not break.
```

## Example

```
Recent: avatar/name → Profile, row → Chat.
Chat ⋯ and Continue Chat: same person; missing chat falls back to Opener.
Daily Discoveries: free daily cap; Continue Searching keeps cards; failures must not break AI Picks.
```

## Limits

- Testers glance; four bullets is a spec.
- Product names stay English (`Recent`, `Opener`, `Daily Discoveries`).
- If nothing is tester-visible, output `Nothing tester-facing in this build.`
