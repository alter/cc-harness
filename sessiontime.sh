#!/usr/bin/env bash
# sessiontime.sh
set -uo pipefail

here=$(cd "$(dirname "$0")" && pwd)
cli=${CC_SESSIONTIME_CLI:-}
for candidate in "$here/sessiontime/cli.py" "${CLAUDE_CONFIG_DIR:-$HOME/.claude}/sessiontime/cli.py"; do
  [ -z "$cli" ] && [ -f "$candidate" ] && cli=$candidate
done
[ -n "$cli" ] || { echo "sessiontime package not found (sessiontime/cli.py next to this script or in ~/.claude/sessiontime/)" >&2; exit 2; }
exec python3 "$cli" "$@"
