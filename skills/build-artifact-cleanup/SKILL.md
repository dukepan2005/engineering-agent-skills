---
name: build-artifact-cleanup
description: Use to inventory FlowCoach Xcode/iOS or Go build and test artifacts. Deletion requires the user to approve the exact previewed targets.
---

# Build Artifact Cleanup

Use `scripts/cleanup-build-artifacts.sh` from this skill for a FlowCoach workspace, a repository named `flowcoach-ios`, or a repository named `flowcoach-api`. The script accepts `--root <path>`; without it, the current directory is used. Other repositories are rejected.

## Safety gate

The skill invocation and requests such as “clean”, “cleanup”, “清理”, or “cache” authorize inventory only. Start by running the script without `--apply`, then show the user every full target path and its size in MB/GB, rounded to two decimal places (decimal units: 1 GB = 1,000 MB), plus the approval token. Stop there and wait for separate, explicit approval of that exact list. Only then run `--apply --approval-token <token>` with the token from that preview. A request made before seeing the inventory does not approve later-discovered targets. If the inventory changes, the script prints a refreshed inventory and token, then stops for fresh approval.

The script fails closed if process inspection fails, detects Xcode, Swift, Go, and test processes, and rechecks the approved inventory immediately before deletion. It rejects cleanup targets whose physical parent resolves outside their allowed repository, user-home, or temporary directory. If process activity cannot be checked, or deletion is blocked by filesystem permissions, stop and report the result; do not retry with elevated permissions. The inventory includes the shared `XcodeBuildMCP/workspaces` and `XCTestDevices` directories, so the user can approve their scope explicitly. After a successful cleanup and verification, report the amount removed for iOS and Go separately, plus the combined total. Calculate these totals from each target's pre-cleanup disk usage and label them as pre-cleanup usage.

The script retains reusable dependency caches, including the Go module download cache. It scans `*go-build*`, `*gocache*`, and `*go-cache*` under `TMPDIR`, `GOTMPDIR`, and `/private/tmp`. Matching build/test cache paths are deleted even when their names contain an `AB` work-item ID, such as `/private/tmp/flowcoach-ab1245-authdiag-go-cache`; unrelated source files remain outside the cleanup targets.

Keep this skill as the single source for this cleanup behavior. Do not add a second copy of its cleanup script or rules to a component repository.
