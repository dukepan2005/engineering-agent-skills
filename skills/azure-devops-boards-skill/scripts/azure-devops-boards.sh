#!/bin/sh
set -eu

if ! command -v az >/dev/null 2>&1; then
  echo "Azure CLI is required." >&2
  exit 1
fi

python_bin="${AZURE_CLI_PYTHON:-}"
if [ -z "$python_bin" ] && command -v brew >/dev/null 2>&1; then
  prefix="$(brew --prefix azure-cli 2>/dev/null || true)"
  python_bin="${prefix}/libexec/bin/python"
fi
for candidate in "$python_bin" /opt/homebrew/opt/azure-cli/libexec/bin/python /usr/local/opt/azure-cli/libexec/bin/python; do
  if [ -n "$candidate" ] && [ -x "$candidate" ]; then python_bin="$candidate"; break; fi
done
if [ ! -x "$python_bin" ]; then
  echo "Unable to locate Azure CLI Python. Set AZURE_CLI_PYTHON." >&2
  exit 1
fi

dir="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
export PYTHONDONTWRITEBYTECODE=1
exec "$python_bin" "$dir/azure_devops_boards.py" "$@"
