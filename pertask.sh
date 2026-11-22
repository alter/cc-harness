#!/usr/bin/env bash
# pertask.sh
set -uo pipefail

here=$(cd "$(dirname "$0")" && pwd)
cli=${CC_PERTASK_CLI:-}
for candidate in "$here/pertask/cli.py" "${CLAUDE_CONFIG_DIR:-$HOME/.claude}/pertask/cli.py"; do
  [ -z "$cli" ] && [ -f "$candidate" ] && cli=$candidate
done
[ -n "$cli" ] || { echo "pertask package not found (pertask/cli.py next to this script or in ~/.claude/pertask/)" >&2; exit 2; }
exec python3 "$cli" "$@"
