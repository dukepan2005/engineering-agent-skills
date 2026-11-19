#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$PWD"
ROOT_DIR_PROVIDED=false
APPLY=false
APPROVAL_TOKEN=""
INCLUDE_GLOBAL_GO_CACHE=false
EXPLICIT_MODE=false
EXPLICIT_TARGET_PATHS=()
TEMP_TARGET_PATHS=()
PRESERVE_PATHS=()

usage() {
  cat <<'USAGE'
Inventory or clean generated MatPace or FlowCoach iOS and Go API build/test artifacts,
or explicitly selected build/test targets in a safe workspace.

Usage:
  cleanup-build-artifacts.sh [--root <workspace-or-repo>] [--include-go-cache] [--apply --approval-token <sha256>]
  cleanup-build-artifacts.sh --root <workspace> [--target <relative-path>]... [--temp-target <absolute-path>]... [--preserve <relative-path>]... [--apply --approval-token <token>]

The default is a dry run. --apply requires the token from the exact previewed
inventory and checks that build/test processes are idle. The default global Go build
cache is retained unless explicitly included with --include-go-cache on both preview
and apply. Go module downloads and reusable Xcode package/module caches are retained.
Explicit targets are exact relative paths (no globbing) under a project subdirectory
of the user home or temporary directory. --temp-target selects exact paths under
/private/tmp or the active macOS temporary directory. Both flags can be combined.
--preserve protects workspace paths. In explicit mode, a changed target gets a
fresh preview while the approved targets that still match are removed.
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
      ROOT_DIR_PROVIDED=true
      shift 2
      ;;
    --target)
      [[ $# -ge 2 ]] || fail '--target requires a relative path'
      EXPLICIT_TARGET_PATHS+=("$2")
      shift 2
      ;;
    --temp-target)
      [[ $# -ge 2 ]] || fail '--temp-target requires an absolute path'
      TEMP_TARGET_PATHS+=("$2")
      shift 2
      ;;
    --preserve)
      [[ $# -ge 2 ]] || fail '--preserve requires a relative path'
      PRESERVE_PATHS+=("$2")
      shift 2
      ;;
    --include-go-cache)
      INCLUDE_GLOBAL_GO_CACHE=true
      shift
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

if [[ ${#EXPLICIT_TARGET_PATHS[@]} -gt 0 || ${#TEMP_TARGET_PATHS[@]} -gt 0 || ${#PRESERVE_PATHS[@]} -gt 0 ]]; then
  EXPLICIT_MODE=true
fi
[[ "$EXPLICIT_MODE" != true || "$ROOT_DIR_PROVIDED" == true ]] || fail 'explicit cleanup requires --root'
[[ "$EXPLICIT_MODE" != true || ${#EXPLICIT_TARGET_PATHS[@]} -gt 0 || ${#TEMP_TARGET_PATHS[@]} -gt 0 ]] || fail '--preserve requires at least one target'
[[ "$APPLY" == true || -z "$APPROVAL_TOKEN" ]] || fail '--approval-token requires --apply'
[[ -d "$ROOT_DIR" ]] || fail "workspace or repository not found: $ROOT_DIR"
[[ "$EXPLICIT_MODE" != true || ! -L "$ROOT_DIR" ]] || fail "refusing symlinked explicit workspace: $ROOT_DIR"
ROOT_DIR="$(cd "$ROOT_DIR" && pwd -P)"

IOS_ROOT=""
API_ROOT=""
if [[ "$EXPLICIT_MODE" != true ]]; then
  ROOT_NAME="${ROOT_DIR##*/}"
  for project_name in matpace-ios flowcoach-ios; do
    if [[ -d "$ROOT_DIR/$project_name" ]]; then
      [[ ! -L "$ROOT_DIR/$project_name" ]] || fail "refusing symlinked iOS repository: $ROOT_DIR/$project_name"
      [[ -z "$IOS_ROOT" ]] || fail 'multiple iOS repositories found; choose one explicitly'
      IOS_ROOT="$ROOT_DIR/$project_name"
    elif [[ "$ROOT_NAME" == "$project_name" && ( -d "$ROOT_DIR/.derived_data" || -f "$ROOT_DIR/Podfile" || -d "$ROOT_DIR/MatPace.xcodeproj" ) ]]; then
      IOS_ROOT="$ROOT_DIR"
    fi
  done
  for project_name in matpace-api flowcoach-api; do
    if [[ -d "$ROOT_DIR/$project_name" && -f "$ROOT_DIR/$project_name/go.mod" ]]; then
      [[ ! -L "$ROOT_DIR/$project_name" ]] || fail "refusing symlinked API repository: $ROOT_DIR/$project_name"
      [[ -z "$API_ROOT" ]] || fail 'multiple API repositories found; choose one explicitly'
      API_ROOT="$ROOT_DIR/$project_name"
    elif [[ "$ROOT_NAME" == "$project_name" && -f "$ROOT_DIR/go.mod" ]]; then
      API_ROOT="$ROOT_DIR"
    fi
  done
  [[ -n "$IOS_ROOT" || -n "$API_ROOT" ]] || fail 'expected a MatPace or FlowCoach workspace, iOS repository, or Go API repository'
fi

TARGETS=()
IOS_TARGETS=()
GO_TARGETS=()
SCRATCH_TARGETS=()
PROTECTED_PATHS=()
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

validate_relative_path() {
  local relative="$1"
  local label="$2"
  local component
  local -a components=()
  [[ -n "$relative" && "$relative" != /* && "$relative" != */ && "$relative" != *//* && "$relative" != *$'\n'* && "$relative" != *$'\r'* ]] || fail "refusing unsafe $label path: $relative"
  IFS='/' read -r -a components <<< "$relative"
  for component in "${components[@]}"; do
    [[ -n "$component" && "$component" != "." && "$component" != ".." ]] || fail "refusing unsafe $label path: $relative"
  done
}

if [[ "$EXPLICIT_MODE" == true ]]; then
  TEMP_ROOT="$(normalize_system_temp "${TMPDIR:-/private/tmp}")"
  ROOT_ALLOWED=false
  if [[ "$ROOT_DIR" != "$USER_HOME" ]] && path_is_within "$ROOT_DIR" "$USER_HOME"; then ROOT_ALLOWED=true; fi
  if [[ "$ROOT_DIR" != /private/tmp ]] && path_is_within "$ROOT_DIR" /private/tmp; then ROOT_ALLOWED=true; fi
  if [[ "$ROOT_DIR" != "$TEMP_ROOT" ]] && path_is_within "$ROOT_DIR" "$TEMP_ROOT"; then ROOT_ALLOWED=true; fi
  [[ "$ROOT_ALLOWED" == true ]] || fail "explicit workspace must be within the user home or a temporary directory: $ROOT_DIR"
  for broad_path in /Users /private /private/var /private/var/folders /private/tmp /System /System/Volumes /Applications /Volumes "$USER_HOME" "$USER_HOME/Library" "$USER_HOME/Library/Caches" "$USER_HOME/Library/Developer" "$TEMP_ROOT"; do
    [[ "$ROOT_DIR" != "$broad_path" ]] || fail "refusing broad explicit workspace: $ROOT_DIR"
  done
  for relative_path in "${EXPLICIT_TARGET_PATHS[@]-}"; do
    [[ -n "$relative_path" ]] || continue
    validate_relative_path "$relative_path" 'target'
  done
  for i in "${!TEMP_TARGET_PATHS[@]}"; do
    candidate="${TEMP_TARGET_PATHS[$i]}"
    case "$candidate" in /tmp/*|/var/folders/*) candidate="/private$candidate" ;; esac
    [[ "$candidate" == /* ]] || fail "--temp-target requires an absolute path: $candidate"
    validate_relative_path "${candidate#/}" 'temporary target'
    if [[ "$candidate" != /private/tmp/* ]] && ! [[ "$TEMP_ROOT" =~ ^/private/var/folders/[^/]+/[^/]+/T(/.*)?$ && "$candidate" == "$TEMP_ROOT/"* ]]; then
      fail "temporary target outside allowed directories: $candidate"
    fi
    path_is_within "$TEMP_ROOT" "$candidate" && fail "temporary target contains the active temporary directory: $candidate"
    path_is_within "$ROOT_DIR" "$candidate" && fail "temporary target contains the workspace: $candidate"
    TEMP_TARGET_PATHS[$i]="$candidate"
  done
  for relative_path in "${PRESERVE_PATHS[@]-}"; do
    [[ -n "$relative_path" ]] || continue
    validate_relative_path "$relative_path" 'preserved'
    candidate="$ROOT_DIR/$relative_path"
    [[ -e "$candidate" || -L "$candidate" ]] || fail "preserved path not found: $candidate"
    [[ ! -L "$candidate" ]] || fail "refusing symlinked preserved path: $candidate"
    parent="${candidate%/*}"
    real_parent="$(cd "$parent" && pwd -P)" || fail "cannot resolve preserved path parent: $parent"
    path_is_within "$real_parent" "$ROOT_DIR" || fail "preserved path resolves outside the workspace: $candidate"
    PROTECTED_PATHS+=("$real_parent/${candidate##*/}")
  done
fi

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
  local existing parent real_parent protected_path
  if [[ "$EXPLICIT_MODE" == true ]]; then
    parent="${candidate%/*}"
    while [[ "$parent" != "$boundary" ]]; do
      [[ ! -L "$parent" ]] || fail "refusing symlinked cleanup parent: $parent"
      parent="${parent%/*}"
    done
  fi
  [[ -e "$candidate" || -L "$candidate" ]] || return 0
  [[ ! -L "$candidate" ]] || fail "refusing symlinked cleanup target: $candidate"
  parent="${candidate%/*}"
  real_parent="$(cd "$parent" && pwd -P)" || fail "cannot resolve cleanup target parent: $parent"
  path_is_within "$real_parent" "$boundary" || fail "cleanup target resolves outside its allowed directory: $candidate"
  if [[ "$EXPLICIT_MODE" == true ]]; then
    candidate="$real_parent/${candidate##*/}"
    for protected_path in "${PROTECTED_PATHS[@]-}"; do
      [[ -n "$protected_path" ]] || continue
      if [[ "$candidate" == "$protected_path" ]] || path_is_within "$candidate" "$protected_path" || path_is_within "$protected_path" "$candidate"; then
        fail "cleanup target overlaps preserved path: $candidate ($protected_path)"
      fi
    done
  fi
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
      if [[ "$existing" == "$candidate" ]]; then
        [[ "$EXPLICIT_MODE" != true ]] || fail "duplicate explicit cleanup target: $candidate"
        return 0
      fi
      if [[ "$EXPLICIT_MODE" == true ]] && { path_is_within "$candidate" "$existing" || path_is_within "$existing" "$candidate"; }; then
        fail "overlapping explicit cleanup targets: $existing and $candidate"
      fi
    done
  fi
  TARGETS+=("$candidate")
  case "$category" in
    ios) IOS_TARGETS+=("$candidate") ;;
    go) GO_TARGETS+=("$candidate") ;;
    scratch) SCRATCH_TARGETS+=("$candidate") ;;
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
  SCRATCH_TARGETS=()
  GO_CACHE=""
  GO_MOD_CACHE=""
  GO_TMP_DIR=""

  if [[ "$EXPLICIT_MODE" == true ]]; then
    for relative_path in "${EXPLICIT_TARGET_PATHS[@]-}"; do
    [[ -n "$relative_path" ]] || continue
      add_target "$ROOT_DIR/$relative_path" scratch "$ROOT_DIR"
    done
    for candidate in "${TEMP_TARGET_PATHS[@]-}"; do
      [[ -n "$candidate" ]] || continue
      if [[ -e "$candidate" && ! -O "$candidate" ]]; then
        fail "temporary target is not owned by the current user: $candidate"
      fi
      boundary="$TEMP_ROOT"
      [[ "$candidate" != /private/tmp/* ]] || boundary=/private/tmp
      add_target "$candidate" scratch "$boundary"
    done
    return 0
  fi

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
    add_target "$API_ROOT/bin/${API_ROOT##*/}" go "$API_ROOT"
    GO_CACHE_RAW="$(cd "$API_ROOT" && go env GOCACHE)"
    GO_MOD_CACHE_RAW="$(cd "$API_ROOT" && go env GOMODCACHE)"
    [[ ! -L "$GO_CACHE_RAW" ]] || fail "refusing symlinked Go build cache: $GO_CACHE_RAW"
    GO_CACHE="$(canonical_config_dir "$GO_CACHE_RAW" 'Go build cache')"
    GO_MOD_CACHE="$(canonical_config_dir "$GO_MOD_CACHE_RAW" 'Go module cache')"
    GO_CACHE_CLEAN=true
    if [[ "$GO_CACHE" == "$USER_HOME/Library/Caches/go-build" && "$INCLUDE_GLOBAL_GO_CACHE" != true ]]; then GO_CACHE_CLEAN=false; fi
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
      scratch) SCRATCH_BYTES=$((SCRATCH_BYTES + size)) ;;
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
        printf 'go-cache-clean\0%s\0' "$GO_CACHE_CLEAN"
        if [[ "$GO_CACHE_CLEAN" != true ]]; then
          printf 'go-cache\0%s\0preserved\0' "$GO_CACHE"
        elif [[ -e "$GO_CACHE" ]]; then
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

run_dry_run() {
  local -a args=(--dry-run)
  [[ "$INCLUDE_GLOBAL_GO_CACHE" != true ]] || args+=(--include-go-cache)
  [[ "$ROOT_DIR_PROVIDED" != true ]] || args+=(--root "$ROOT_DIR")
  bash "$0" "${args[@]}"
}

assert_processes_idle() {
  local processes process name pid command args target open_files status
  local -a active=()
  if [[ "$EXPLICIT_MODE" == true ]]; then
    [[ ${#TARGETS[@]} -gt 0 ]] || return 0
    if ! processes="$(ps -ww -axo pid=,comm=,args= 2>/dev/null)"; then
      fail 'cannot inspect build/test processes; refusing cleanup'
    fi
    [[ -n "$processes" ]] || fail 'process inspection returned no data; refusing cleanup'
    while IFS= read -r process; do
      read -r pid command args <<< "$process"
      name="${command##*/}"
      case "$name" in
        Xcode|XcodeBuildService|xcodebuild|Simulator*|xctest|xcresulttool|testmanagerd|go|*.test|compile|link|asm|vet|cover|cgo|swift|swiftc|swift-frontend|swift-driver|swift-build|swift-test|SourceKitService|XCBBuildService)
          if [[ "$args" == *"$ROOT_DIR"* ]]; then active+=("$pid:$name"); continue; fi
          for target in "${TARGETS[@]}"; do
            if [[ "$args" == *"$target"* ]]; then active+=("$pid:$name"); break; fi
          done
          ;;
      esac
    done <<< "$processes"
    if [[ ${#active[@]} -gt 0 ]]; then
      printf 'Refusing cleanup while these build/test processes reference the workspace: %s\n' "${active[*]}" >&2
      exit 1
    fi
    command -v lsof >/dev/null 2>&1 || fail 'lsof is required to inspect open files in explicit cleanup targets'
    for target in "${TARGETS[@]}"; do
      if [[ -d "$target" ]]; then
        if open_files="$(lsof -n -t +D "$target" 2>&1)"; then
          [[ -n "$open_files" ]] || fail "lsof returned no process data for cleanup target: $target"
        else
          status=$?
          [[ "$status" -eq 1 && -z "$open_files" ]] || fail "cannot inspect open files in cleanup target: $target"
          continue
        fi
        printf 'Refusing cleanup while processes have files open under %s (PIDs: %s)\n' "$target" "$(printf '%s' "$open_files" | tr '\n' ' ')" >&2
        exit 1
      fi
      if open_files="$(lsof -n -t "$target" 2>&1)"; then
        [[ -n "$open_files" ]] || fail "lsof returned no process data for cleanup target: $target"
        printf 'Refusing cleanup while processes have the cleanup target open: %s (PIDs: %s)\n' "$target" "$(printf '%s' "$open_files" | tr '\n' ' ')" >&2
        exit 1
      else
        status=$?
        [[ "$status" -eq 1 && -z "$open_files" ]] || fail "cannot inspect open cleanup target: $target"
      fi
    done
    return 0
  fi
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

# Explicit approvals bind each path independently so a changed entry can be held back.
explicit_record() {
  local target="$1" parent before after size digest
  if [[ ! -e "$target" && ! -L "$target" ]]; then
    printf 'missing -\n'
    return
  fi
  [[ ! -L "$target" ]] || return 1
  parent="${target%/*}"
  [[ "$(cd "$parent" && pwd -P)" == "$parent" ]] || return 1
  before="$(stat -f '%d:%i:%p:%u:%z:%.9Fm:%.9Fc' "$target")" || return 1
  size="$(path_size_bytes "$target")" || return 1
  digest="$(
    {
      printf '%s\0%s\0%s\0' "$target" "$before" "$size"
      find -s "$target" -exec stat -f '%d:%i:%p:%u:%z:%.9Fm:%.9Fc:%N' {} +
    } | shasum -a 256 | awk '{print $1}'
  )" || return 1
  after="$(stat -f '%d:%i:%p:%u:%z:%.9Fm:%.9Fc' "$target")" || return 1
  [[ "$before" == "$after" ]] || return 1
  printf '%s %s\n' "$digest" "$size"
}

explicit_cleanup() {
  local -a paths=() flags=() approved=() selected=() selected_indexes=() refresh=()
  local path item i record digest size scope token total=0 removed=0
  for item in "${EXPLICIT_TARGET_PATHS[@]-}"; do
    [[ -n "$item" ]] || continue
    paths+=("$ROOT_DIR/$item")
    flags+=(--target)
  done
  for item in "${TEMP_TARGET_PATHS[@]-}"; do
    [[ -n "$item" ]] || continue
    paths+=("$item")
    flags+=(--temp-target)
  done
  scope="$(
    {
      printf 'explicit-v1\0%s\0' "$ROOT_DIR"
      for i in "${!paths[@]}"; do printf '%s\0%s\0' "${flags[$i]}" "${paths[$i]}"; done
      printf 'preserved\0%s\0' "${PROTECTED_PATHS[@]-}"
    } | shasum -a 256 | awk '{print $1}'
  )" || fail 'cannot create the explicit inventory token'
  collect_targets
  if [[ "$APPLY" != true ]]; then
    printf 'Cleanup inventory (%s):\n  Explicit build/test targets:\n' "$ROOT_DIR"
    token="$scope"
    for path in "${paths[@]}"; do
      record="$(explicit_record "$path")" || fail "cannot inspect cleanup target: $path"
      read -r digest size <<< "$record"
      token="$token.$digest"
      if [[ "$digest" == missing ]]; then
        printf '  missing: %s\n' "$path"
      else
        printf '%12s  %s\n' "$(format_bytes "$size")" "$path"
        total=$((total + size))
      fi
    done
    [[ ${#TARGETS[@]} -gt 0 ]] || printf '  none\n'
    for path in "${PROTECTED_PATHS[@]-}"; do
      [[ -n "$path" ]] || continue
      printf '  preserved: %s\n' "$path"
    done
    printf 'Estimated cleanup size: %s\n' "$(format_bytes "$total")"
    printf 'Approval token: %s\n' "$token"
    printf 'Dry run only. Approve this exact inventory, then pass its token with --apply.\n'
    return 0
  fi

  [[ "$APPROVAL_TOKEN" =~ ^[a-f0-9]{64}(\.([a-f0-9]{64}|missing))+$ ]] || fail '--apply requires the explicit token from the dry run'
  IFS=. read -r -a approved <<< "$APPROVAL_TOKEN"
  [[ "${approved[0]}" == "$scope" && ${#approved[@]} -eq $((${#paths[@]} + 1)) ]] || fail 'cleanup paths differ from the approved preview'
  for i in "${!paths[@]}"; do
    path="${paths[$i]}"
    record="$(explicit_record "$path")" || fail "cannot inspect cleanup target: $path"
    read -r digest size <<< "$record"
    if [[ "$digest" == missing ]]; then
      printf 'already absent %s\n' "$path"
    elif [[ "$digest" == "${approved[$((i + 1))]}" ]]; then
      selected+=("$path")
      selected_indexes+=("$i")
    else
      refresh+=("$i")
    fi
  done

  if [[ ${#selected[@]} -gt 0 ]]; then
    TARGETS=("${selected[@]}")
    assert_processes_idle
    collect_targets
    for i in "${selected_indexes[@]}"; do
      path="${paths[$i]}"
      record="$(explicit_record "$path")" || fail "cannot recheck cleanup target: $path"
      read -r digest size <<< "$record"
      if [[ "$digest" == missing ]]; then
        printf 'already absent %s\n' "$path"
      elif [[ "$digest" != "${approved[$((i + 1))]}" ]]; then
        refresh+=("$i")
      else
        rm -rf -- "$path"
        [[ ! -e "$path" && ! -L "$path" ]] || fail "cleanup target remains: $path"
        removed=$((removed + 1))
        total=$((total + size))
        printf 'removed %s\n' "$path"
      fi
    done
  fi
  printf 'Verified removal of %s explicit targets (%s before cleanup).\n' "$removed" "$(format_bytes "$total")"
  if [[ ${#refresh[@]} -gt 0 ]]; then
    local -a args=(--root "$ROOT_DIR")
    for i in "${refresh[@]}"; do
      item="${paths[$i]}"
      if [[ "${flags[$i]}" == --target ]]; then item="${item#"$ROOT_DIR/"}"; fi
      args+=("${flags[$i]}" "$item")
    done
    for item in "${PRESERVE_PATHS[@]-}"; do [[ -z "$item" ]] || args+=(--preserve "$item"); done
    printf 'Changed targets held for fresh approval. Retry only these targets after approval:\n  bash %q' "$0"
    printf ' %q' "${args[@]}"
    printf ' --apply --approval-token %q\n' '<new-token>'
    bash "$0" "${args[@]}"
    return 1
  fi
}

if [[ "$EXPLICIT_MODE" == true ]]; then
  explicit_cleanup
  exit $?
fi

collect_targets
INITIAL_TOKEN="$(inventory_token)" || INITIAL_TOKEN=""
IOS_BYTES=0
GO_BYTES=0
SCRATCH_BYTES=0
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
  if [[ "$GO_CACHE_CLEAN" != true ]]; then
    printf '  preserved global Go build/test cache: %s\n' "$GO_CACHE"
  elif [[ -e "$GO_CACHE" || -L "$GO_CACHE" ]]; then
    printf '  Go build/test cache (go clean -cache -testcache):\n'
    print_size "$GO_CACHE" go
  else
    printf '  Go build/test cache not present: %s\n' "$GO_CACHE"
  fi
  printf '  preserved Go module cache: %s\n' "$GO_MOD_CACHE"
fi
[[ "$GO_FOUND" == true || -n "$API_ROOT" ]] || printf '%12s  %s\n' '' 'none'
if [[ "$SIZES_KNOWN" == true ]]; then
  TOTAL_BYTES=$((IOS_BYTES + GO_BYTES + SCRATCH_BYTES))
  printf 'Estimated cleanup size (pre-clean disk usage): iOS %s; Go %s; explicit targets %s; total %s\n' "$(format_bytes "$IOS_BYTES")" "$(format_bytes "$GO_BYTES")" "$(format_bytes "$SCRATCH_BYTES")" "$(format_bytes "$TOTAL_BYTES")"
else
  printf 'Estimated cleanup size unavailable because at least one target size could not be read.\n'
fi
CURRENT_TOKEN="$(inventory_token)" || fail 'cannot create an inventory approval token'
if [[ -n "$INITIAL_TOKEN" && "$INITIAL_TOKEN" != "$CURRENT_TOKEN" ]]; then
  printf 'Inventory changed while preparing the preview. Refreshing the inventory:\n'
  run_dry_run
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
  run_dry_run
  fail 'review the refreshed inventory and approve its token before retrying'
fi
assert_processes_idle
FINAL_TOKEN="$(inventory_token)" || fail 'cannot recheck the inventory approval token'
if [[ "$FINAL_TOKEN" != "$APPROVAL_TOKEN" ]]; then
  printf 'Inventory changed during apply preparation; no artifacts were removed. Refreshing the inventory:\n'
  run_dry_run
  fail 'review the refreshed inventory and approve its token before retrying'
fi

if [[ ${#TARGETS[@]} -gt 0 ]]; then
  for target in "${TARGETS[@]}"; do
    rm -rf -- "$target"
    printf 'removed %s\n' "$target"
  done
fi

if [[ -n "$API_ROOT" && "$GO_CACHE_CLEAN" == true && ( -e "$GO_CACHE" || -L "$GO_CACHE" ) ]]; then
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
TOTAL_BYTES=$((IOS_BYTES + GO_BYTES + SCRATCH_BYTES))
printf 'Cleanup total (pre-clean disk usage): iOS %s; Go %s; explicit targets %s; combined %s\n' "$(format_bytes "$IOS_BYTES")" "$(format_bytes "$GO_BYTES")" "$(format_bytes "$SCRATCH_BYTES")" "$(format_bytes "$TOTAL_BYTES")"
