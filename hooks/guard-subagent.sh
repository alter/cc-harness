#!/usr/bin/env bash
# guard-subagent.sh
set -uo pipefail

BUDGET=${CC_SUBAGENT_BUDGET:-12}

payload=$(cat)
session=$(printf '%s' "$payload" | jq -r '.session_id // "unknown"')
atype=$(printf '%s' "$payload" | jq -r '.tool_input.subagent_type // "general-purpose"')

state_dir="${XDG_STATE_HOME:-$HOME/.local/state}/cc-subagent-budget"
mkdir -p "$state_dir"
counter="$state_dir/$session"

find "$state_dir" -type f -mtime +2 -delete 2>/dev/null || true

count=0
[ -f "$counter" ] && count=$(cat "$counter" 2>/dev/null || echo 0)

if [ "$count" -ge "$BUDGET" ]; then
  jq -n --arg r "Subagent budget for this session is spent ($count/$BUDGET, type=$atype). Do the work in the main thread, or ask the user to raise CC_SUBAGENT_BUDGET." \
    '{hookSpecificOutput:{hookEventName:"PreToolUse",permissionDecision:"deny",permissionDecisionReason:$r}}'
  exit 0
fi

echo $(( count + 1 )) > "$counter"
jq -n '{hookSpecificOutput:{hookEventName:"PreToolUse",permissionDecision:"allow"}}'
