#!/usr/bin/env bash
# fullrun.sh
set -uo pipefail

here=$(cd "$(dirname "$0")" && pwd)
engine=${CC_FULLRUN_ENGINE:-}
for candidate in "$here/fullrun/engine.py" "${CLAUDE_CONFIG_DIR:-$HOME/.claude}/fullrun/engine.py"; do
  [ -z "$engine" ] && [ -f "$candidate" ] && engine=$candidate
done
[ -n "$engine" ] || { echo "fullrun engine not found (fullrun/engine.py next to this script or in ~/.claude/fullrun/)" >&2; exit 2; }
exec python3 "$engine" "$@"
