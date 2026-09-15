#!/usr/bin/env bash
# read-guard.sh
set -uo pipefail

LIMIT=${CC_READ_GUARD_LINES:-500}

payload=$(cat)
tool=$(printf '%s' "$payload" | jq -r '.tool_name // ""')
[ "$tool" = "Read" ] || exit 0

file=$(printf '%s' "$payload" | jq -r '.tool_input.file_path // ""')
has_limit=$(printf '%s' "$payload" | jq -r 'if (.tool_input.limit // null) != null then "1" else "0" end')
offset=$(printf '%s' "$payload" | jq -r '.tool_input.offset // 1')

[ -z "$file" ] && exit 0
[ "$has_limit" = "1" ] && exit 0
[ "$offset" != "1" ] && [ "$offset" != "0" ] && exit 0
[ -f "$file" ] || exit 0

case "$file" in
  */docs/plans/*|*/CLAUDE.md|*/.claude/*|*.json|*.toml|*.yaml|*.yml|*.lock|*.md) exit 0 ;;
esac

if file --mime "$file" 2>/dev/null | grep -qvE 'text|json|xml|empty'; then exit 0; fi

lines=$(wc -l < "$file" | tr -d ' ')
[ "$lines" -le "$LIMIT" ] && exit 0

base=$(basename "$file")
jq -n --arg r "$base has $lines lines (limit $LIMIT for whole-file reads). Locate the symbol first (Grep -n), then Read with offset and limit around the match. If you truly need the whole file, delegate it to the scout or researcher subagent and ask for a summary." \
  '{hookSpecificOutput:{hookEventName:"PreToolUse",permissionDecision:"deny",permissionDecisionReason:$r}}'
