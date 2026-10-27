#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$PWD"
APPLY=false
APPROVAL_TOKEN=""

usage() {
  cat <<'USAGE'
Inventory or clean generated FlowCoach iOS and Go API build/test artifacts.

Usage:
  cleanup-build-artifacts.sh [--root <FlowCoach-workspace-or-repo>] [--apply --approval-token <sha256>]

The default is a dry run. --apply requires the token from the exact previewed
inventory and checks that Xcode, Swift, Go builds, and tests are idle. Go module
downloads and reusable Xcode package/module/compilation caches are retained.
USAGE
}

fail() {
  printf 'error: %s\n' "$1" >&2
  exit 1
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --root)
      [[ $# -ge 2 ]] || fail '--root requires a path'
      ROOT_DIR="$2"
      shift 2
      ;;
    --apply)
      APPLY=true
      shift
      ;;
    --approval-token)
      [[ $# -ge 2 ]] || fail '--approval-token requires the dry-run token'
      APPROVAL_TOKEN="$2"
      shift 2
      ;;
    --dry-run)
      APPLY=false
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      fail "unknown argument: $1"
      ;;
  esac
done

[[ "$APPLY" == true || -z "$APPROVAL_TOKEN" ]] || fail '--approval-token requires --apply'
[[ -d "$ROOT_DIR" ]] || fail "workspace or repository not found: $ROOT_DIR"
ROOT_DIR="$(cd "$ROOT_DIR" && pwd -P)"

IOS_ROOT=""
API_ROOT=""
ROOT_NAME="${ROOT_DIR##*/}"
if [[ -d "$ROOT_DIR/flowcoach-ios" ]]; then
  [[ ! -L "$ROOT_DIR/flowcoach-ios" ]] || fail "refusing symlinked FlowCoach iOS repository: $ROOT_DIR/flowcoach-ios"
  IOS_ROOT="$ROOT_DIR/flowcoach-ios"
elif [[ "$ROOT_NAME" == "flowcoach-ios" && ( -d "$ROOT_DIR/.derived_data" || -f "$ROOT_DIR/Podfile" ) ]]; then
  IOS_ROOT="$ROOT_DIR"
fi
if [[ -d "$ROOT_DIR/flowcoach-api" && -f "$ROOT_DIR/flowcoach-api/go.mod" ]]; then
  [[ ! -L "$ROOT_DIR/flowcoach-api" ]] || fail "refusing symlinked FlowCoach API repository: $ROOT_DIR/flowcoach-api"
  API_ROOT="$ROOT_DIR/flowcoach-api"
elif [[ "$ROOT_NAME" == "flowcoach-api" && -f "$ROOT_DIR/go.mod" ]]; then
  API_ROOT="$ROOT_DIR"
fi
[[ -n "$IOS_ROOT" || -n "$API_ROOT" ]] || fail 'expected a FlowCoach workspace, iOS repository, or Go API repository'

TARGETS=()
IOS_TARGETS=()
GO_TARGETS=()
GO_CACHE=""
GO_MOD_CACHE=""
GO_TMP_DIR=""
USER_HOME="${HOME:-}"
[[ "$USER_HOME" == /Users/* && -d "$USER_HOME" ]] || fail "refusing unsafe user home: $USER_HOME"
USER_HOME="$(cd "$USER_HOME" && pwd -P)"

path_is_within() {
  local path="$1"
  local boundary="${2%/}"
  [[ "$path/" == "$boundary/"* ]]
}

canonical_config_dir() {
  local path="$1"
  local label="$2"
  local current suffix real_current
  path="${path%/}"
  [[ "$path" == /* && "$path" != "/" ]] || fail "refusing unsafe $label path: $path"
  if [[ -e "$path" ]]; then
    [[ -d "$path" ]] || fail "$label path is not a directory: $path"
    real_current="$(cd "$path" && pwd -P)" || fail "cannot resolve $label path: $path"
    printf '%s\n' "$real_current"
    return 0
  fi
  suffix="${path##*/}"
  current="${path%/*}"
  while [[ ! -d "$current" ]]; do
    [[ ! -e "$current" ]] || fail "$label parent is not a directory: $current"
    suffix="${current##*/}/$suffix"
    current="${current%/*}"
    [[ -n "$current" ]] || current="/"
  done
  real_current="$(cd "$current" && pwd -P)" || fail "cannot resolve $label parent: $current"
  if [[ "$real_current" == "/" ]]; then
    printf '/%s\n' "$suffix"
  else
    printf '%s/%s\n' "${real_current%/}" "$suffix"
  fi
}

normalize_system_temp() {
  local path="$1"
  local physical
  [[ -d "$path" ]] || fail "temporary directory does not exist: $path"
  physical="$(cd "$path" && pwd -P)" || fail "cannot resolve temporary directory: $path"
  case "$physical" in
    /private/tmp|/private/tmp/*|/private/var/folders/*) ;;
    *) fail "refusing to scan unsafe temporary directory: $physical" ;;
  esac
  printf '%s\n' "$physical"
}

normalize_go_temp() {
  local path="$1"
  local physical
  [[ -n "$path" ]] || return 0
  [[ -d "$path" ]] || fail "Go temporary directory does not exist: $path"
  physical="$(cd "$path" && pwd -P)" || fail "cannot resolve Go temporary directory: $path"
  case "$physical" in
    /private/tmp|/private/tmp/*|/private/var/folders/*|/Users/*) ;;
    *) fail "refusing to scan unsafe Go temporary directory: $physical" ;;
  esac
  [[ "$physical" != "$USER_HOME" ]] || fail "refusing to scan the entire user home as Go temporary storage: $physical"
  case "$ROOT_DIR/" in
    "$physical/"*) fail "Go temporary directory contains the workspace: $physical" ;;
  esac
  printf '%s\n' "$physical"
}

add_target() {
  local candidate="$1"
  local category="$2"
  local boundary="$3"
  local existing parent real_parent
  [[ -e "$candidate" || -L "$candidate" ]] || return 0
  [[ ! -L "$candidate" ]] || fail "refusing symlinked cleanup target: $candidate"
  parent="${candidate%/*}"
  real_parent="$(cd "$parent" && pwd -P)" || fail "cannot resolve cleanup target parent: $parent"
  path_is_within "$real_parent" "$boundary" || fail "cleanup target resolves outside its allowed directory: $candidate"
  if [[ -n "$GO_CACHE" ]]; then
    path_is_within "$candidate" "$GO_CACHE" && return 0
    path_is_within "$GO_CACHE" "$candidate" && fail "cleanup target contains the Go build cache: $candidate"
  fi
  if [[ -n "$GO_MOD_CACHE" ]]; then
    path_is_within "$candidate" "$GO_MOD_CACHE" && return 0
    path_is_within "$GO_MOD_CACHE" "$candidate" && fail "cleanup target contains the preserved Go module cache: $candidate"
  fi
  if [[ ${#TARGETS[@]} -gt 0 ]]; then
    for existing in "${TARGETS[@]}"; do
      [[ "$existing" == "$candidate" ]] && return 0
    done
  fi
  TARGETS+=("$candidate")
  case "$category" in
    ios) IOS_TARGETS+=("$candidate") ;;
    go) GO_TARGETS+=("$candidate") ;;
    *) fail "unknown cleanup category: $category" ;;
  esac
}

scan_temp_glob() {
  local base="$1"
  local pattern="$2"
  local candidate
  for candidate in "$base"/$pattern; do
    [[ -e "$candidate" || -L "$candidate" ]] || continue
    add_target "$candidate" go "$base"
  done
}

scan_go_temp_artifacts() {
  local base="$1"
  local pattern
  for pattern in '*go-build*' '*gocache*' '*go-cache*'; do
    scan_temp_glob "$base" "$pattern"
  done
}

collect_targets() {
  TARGETS=()
  IOS_TARGETS=()
  GO_TARGETS=()
  GO_CACHE=""
  GO_MOD_CACHE=""
  GO_TMP_DIR=""

  if [[ -n "$IOS_ROOT" ]]; then
    for relative_path in \
      '.derived_data/Build' \
      '.derived_data/Logs' \
      '.derived_data/Index.noindex' \
      '.derived_data/TestResults' \
      '.build'
    do
      add_target "$IOS_ROOT/$relative_path" ios "$IOS_ROOT"
    done

    add_target "$USER_HOME/Library/Developer/XcodeBuildMCP/workspaces" ios "$USER_HOME"
    add_target "$USER_HOME/Library/Developer/XCTestDevices" ios "$USER_HOME"

    TEMP_BASE="$(normalize_system_temp "${TMPDIR:-/private/tmp}")"
    for candidate in "$TEMP_BASE"/flowcoach-ticket-*; do
      [[ -e "$candidate" || -L "$candidate" ]] || continue
      base="${candidate##*/}"
      [[ "$base" =~ ^flowcoach-ticket-[0-9]+$ ]] && add_target "$candidate" ios "$TEMP_BASE"
    done
  fi

  if [[ -n "$API_ROOT" ]]; then
    command -v go >/dev/null 2>&1 || fail 'Go is required to inspect and clean the API build/test cache'
    add_target "$API_ROOT/bin/flowcoach-api" go "$API_ROOT"
    GO_CACHE_RAW="$(cd "$API_ROOT" && go env GOCACHE)"
    GO_MOD_CACHE_RAW="$(cd "$API_ROOT" && go env GOMODCACHE)"
    [[ ! -L "$GO_CACHE_RAW" ]] || fail "refusing symlinked Go build cache: $GO_CACHE_RAW"
    GO_CACHE="$(canonical_config_dir "$GO_CACHE_RAW" 'Go build cache')"
    GO_MOD_CACHE="$(canonical_config_dir "$GO_MOD_CACHE_RAW" 'Go module cache')"
    [[ "$GO_CACHE" != '/' ]] || fail "refusing unsafe Go build cache path: $GO_CACHE"
    for broad_path in /Users /private /private/var /var /System /System/Volumes /Applications /Volumes "$USER_HOME" "$USER_HOME/Library" "$USER_HOME/Library/Caches" "$USER_HOME/Library/Developer" /private/tmp /private/var/folders; do
      [[ "$GO_CACHE" != "$broad_path" ]] || fail "refusing broad Go build cache path: $GO_CACHE"
    done
    for protected_path in "$ROOT_DIR" "$IOS_ROOT" "$API_ROOT" "$USER_HOME"; do
      [[ -n "$protected_path" ]] || continue
      path_is_within "$protected_path" "$GO_CACHE" && fail "Go build cache contains protected data: $protected_path"
    done
    [[ "$GO_CACHE" != "$GO_MOD_CACHE" ]] || fail 'Go build cache and module cache resolve to the same path'
    path_is_within "$GO_MOD_CACHE" "$GO_CACHE" && fail 'Go build cache would contain the preserved Go module cache'
    path_is_within "$GO_CACHE" "$GO_MOD_CACHE" && fail 'Go build cache is inside the preserved Go module cache'

    GO_TMP_RAW="$(cd "$API_ROOT" && go env GOTMPDIR)"
    GO_TMP_DIR="$(normalize_go_temp "$GO_TMP_RAW")"
    TEMP_BASE="$(normalize_system_temp "${TMPDIR:-/private/tmp}")"
    scan_go_temp_artifacts "$TEMP_BASE"
    [[ -z "$GO_TMP_DIR" ]] || scan_go_temp_artifacts "$GO_TMP_DIR"
    if [[ -d /private/tmp ]]; then
      scan_go_temp_artifacts /private/tmp
    fi
  fi
}

path_size_bytes() {
  local size
  size="$(du -sk "$1" 2>/dev/null | LC_ALL=C awk 'NR == 1 { printf "%.0f", $1 * 1024 }')" || return 1
  [[ "$size" =~ ^[0-9]+$ ]] || return 1
  printf '%s\n' "$size"
}

format_bytes() {
  LC_ALL=C awk -v bytes="$1" 'BEGIN { if (bytes >= 1000000000) printf "%.2f GB", bytes / 1000000000; else printf "%.2f MB", bytes / 1000000 }'
}

print_size() {
  local path="$1" category="$2" size
  if size="$(path_size_bytes "$path")"; then
    printf '%12s  %s\n' "$(format_bytes "$size")" "$path"
    case "$category" in
      ios) IOS_BYTES=$((IOS_BYTES + size)) ;;
      go) GO_BYTES=$((GO_BYTES + size)) ;;
      *) fail "unknown cleanup category: $category" ;;
    esac
  else
    printf '%12s  %s\n' 'unknown' "$path"
    SIZES_KNOWN=false
  fi
}

inventory_token() {
  local target size digest
  command -v shasum >/dev/null 2>&1 || return 1
  digest="$(
    {
      for target in "${IOS_TARGETS[@]-}"; do
        [[ -n "$target" ]] || continue
        size="$(path_size_bytes "$target")" || exit 1
        printf 'ios\0%s\0%s\0' "$target" "$size"
      done
      for target in "${GO_TARGETS[@]-}"; do
        [[ -n "$target" ]] || continue
        size="$(path_size_bytes "$target")" || exit 1
        printf 'go\0%s\0%s\0' "$target" "$size"
      done
      if [[ -n "$API_ROOT" ]]; then
        if [[ -e "$GO_CACHE" ]]; then
          size="$(path_size_bytes "$GO_CACHE")" || exit 1
          printf 'go-cache\0%s\0present\0%s\0' "$GO_CACHE" "$size"
        else
          printf 'go-cache\0%s\0absent\0' "$GO_CACHE"
        fi
        printf 'module-cache\0%s\0preserved\0' "$GO_MOD_CACHE"
      fi
    } | shasum -a 256 | awk '{print $1}'
  )" || return 1
  [[ "$digest" =~ ^[[:xdigit:]]+$ && ${#digest} -eq 64 ]] || return 1
  printf '%s\n' "$digest"
}

assert_processes_idle() {
  local processes process name
  local -a active=()
  if ! processes="$(ps -axo comm= 2>/dev/null)"; then
    fail 'cannot inspect build/test processes; refusing cleanup'
  fi
  [[ -n "$processes" ]] || fail 'process inspection returned no data; refusing cleanup'
  while IFS= read -r process; do
    name="${process##*/}"
    case "$name" in
      Xcode|XcodeBuildService|xcodebuild|Simulator*|xctest|testmanagerd|go|*.test|swift|swiftc|swift-frontend|swift-driver|swift-build|swift-test|SourceKitService|XCBBuildService)
        active+=("$name")
        ;;
    esac
  done <<< "$processes"
  if [[ ${#active[@]} -gt 0 ]]; then
    printf 'Refusing cleanup while these build/test processes are active: %s\n' "${active[*]}" >&2
    exit 1
  fi
}

collect_targets
INITIAL_TOKEN="$(inventory_token)" || INITIAL_TOKEN=""
IOS_BYTES=0
GO_BYTES=0
SIZES_KNOWN=true
printf 'Cleanup inventory (%s):\n' "$ROOT_DIR"
printf '  iOS targets:\n'
IOS_FOUND=false
for target in "${IOS_TARGETS[@]-}"; do
  [[ -n "$target" ]] || continue
  IOS_FOUND=true
  print_size "$target" ios
done
[[ "$IOS_FOUND" == true ]] || printf '%12s  %s\n' '' 'none'
printf '  Go targets:\n'
GO_FOUND=false
for target in "${GO_TARGETS[@]-}"; do
  [[ -n "$target" ]] || continue
  GO_FOUND=true
  print_size "$target" go
done
if [[ -n "$API_ROOT" ]]; then
  if [[ -e "$GO_CACHE" || -L "$GO_CACHE" ]]; then
    printf '  Go build/test cache (go clean -cache -testcache):\n'
    print_size "$GO_CACHE" go
  else
    printf '  Go build/test cache not present: %s\n' "$GO_CACHE"
  fi
  printf '  preserved Go module cache: %s\n' "$GO_MOD_CACHE"
fi
[[ "$GO_FOUND" == true || -n "$API_ROOT" ]] || printf '%12s  %s\n' '' 'none'
if [[ "$SIZES_KNOWN" == true ]]; then
  TOTAL_BYTES=$((IOS_BYTES + GO_BYTES))
  printf 'Estimated cleanup size (pre-clean disk usage): iOS %s; Go %s; total %s\n' "$(format_bytes "$IOS_BYTES")" "$(format_bytes "$GO_BYTES")" "$(format_bytes "$TOTAL_BYTES")"
else
  printf 'Estimated cleanup size unavailable because at least one target size could not be read.\n'
fi
CURRENT_TOKEN="$(inventory_token)" || fail 'cannot create an inventory approval token'
if [[ -n "$INITIAL_TOKEN" && "$INITIAL_TOKEN" != "$CURRENT_TOKEN" ]]; then
  printf 'Inventory changed while preparing the preview. Refreshing the inventory:\n'
  bash "$0" --root "$ROOT_DIR" --dry-run
  fail 'review the refreshed inventory before approving cleanup'
fi
printf 'Approval token: %s\n' "$CURRENT_TOKEN"
if [[ "$APPLY" != true ]]; then
  printf 'Dry run only. Approve this exact inventory, then pass its token with --apply.\n'
  exit 0
fi
[[ "$SIZES_KNOWN" == true ]] || fail 'cannot report cleanup totals because at least one target size could not be read'
[[ "$APPROVAL_TOKEN" =~ ^[[:xdigit:]]+$ && ${#APPROVAL_TOKEN} -eq 64 ]] || fail '--apply requires a 64-character SHA-256 --approval-token from the dry run'
[[ "$APPROVAL_TOKEN" == "$CURRENT_TOKEN" ]] || fail 'inventory differs from the approved preview; no artifacts were removed'

assert_processes_idle
collect_targets
LATEST_TOKEN="$(inventory_token)" || fail 'cannot refresh the inventory approval token'
if [[ "$LATEST_TOKEN" != "$APPROVAL_TOKEN" ]]; then
  printf 'Inventory changed during apply preparation; no artifacts were removed. Refreshing the inventory:\n'
  bash "$0" --root "$ROOT_DIR" --dry-run
  fail 'review the refreshed inventory and approve its token before retrying'
fi
assert_processes_idle
FINAL_TOKEN="$(inventory_token)" || fail 'cannot recheck the inventory approval token'
if [[ "$FINAL_TOKEN" != "$APPROVAL_TOKEN" ]]; then
  printf 'Inventory changed during apply preparation; no artifacts were removed. Refreshing the inventory:\n'
  "$0" --root "$ROOT_DIR" --dry-run
  fail 'review the refreshed inventory and approve its token before retrying'
fi

if [[ ${#TARGETS[@]} -gt 0 ]]; then
  for target in "${TARGETS[@]}"; do
    rm -rf -- "$target"
    printf 'removed %s\n' "$target"
  done
fi

if [[ -n "$API_ROOT" && ( -e "$GO_CACHE" || -L "$GO_CACHE" ) ]]; then
  (cd "$API_ROOT" && go clean -cache -testcache)
  if [[ -d "$GO_CACHE" ]]; then
    shopt -s nullglob dotglob
    remaining=("$GO_CACHE"/*)
    shopt -u nullglob dotglob
    for entry in "${remaining[@]-}"; do
      [[ -n "$entry" ]] || continue
      case "${entry##*/}" in
        README|trim.txt) [[ -f "$entry" ]] || fail "unexpected Go build cache entry: $entry" ;;
        *) fail "Go build cache still has entries: $entry" ;;
      esac
    done
  fi
  printf 'verified Go build/test cache cleared: %s\n' "$GO_CACHE"
fi

if [[ ${#TARGETS[@]} -gt 0 ]]; then
  for target in "${TARGETS[@]}"; do
    [[ ! -e "$target" && ! -L "$target" ]] || fail "cleanup target remains: $target"
  done
fi
printf 'verified all listed cleanup targets are gone.\n'
TOTAL_BYTES=$((IOS_BYTES + GO_BYTES))
printf 'Cleanup total (pre-clean disk usage): iOS %s; Go %s; combined %s\n' "$(format_bytes "$IOS_BYTES")" "$(format_bytes "$GO_BYTES")" "$(format_bytes "$TOTAL_BYTES")"
