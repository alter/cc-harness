#!/usr/bin/env bash
# guard-subagent.sh
set -uo pipefail
case ",${CC_DISABLED_HOOKS:-}," in *",guard-subagent,"*) exit 0 ;; esac

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

rank() {
  case "$(printf '%s' "$1" | tr '[:upper:]' '[:lower:]')" in
    *fable*) echo 4 ;; *opus*) echo 3 ;; *sonnet*) echo 2 ;; *haiku*) echo 1 ;; *) echo 0 ;;
  esac
}

asked=$(printf '%s' "$payload" | jq -r '.tool_input.model // empty')
cwd=$(printf '%s' "$payload" | jq -r '.cwd // empty')
if [ -n "$asked" ] && [ "$atype" != "fork" ]; then
  defined=""
  for d in ${cwd:+"$cwd/.claude/agents"} "$HOME/.claude/agents"; do
    f="$d/$atype.md"
    [ -f "$f" ] || f=$(grep -lxE "name: *$atype" "$d"/*.md 2>/dev/null | head -n 1)
    [ -n "$f" ] && [ -f "$f" ] || continue
    defined=$(awk 'NR==1 && $0!="---" {exit} NR>1 && $0=="---" {exit} /^model:/ {sub(/^model: */, ""); print; exit}' "$f")
    break
  done
  case "$defined" in ''|inherit) cap=${CLAUDE_CODE_SUBAGENT_MODEL:-} ;; *) cap=$defined ;; esac
  if [ "$(rank "$asked")" -gt "$(rank "$cap")" ] && [ "$(rank "$cap")" -gt 0 ]; then
    printf '%s' "$payload" | jq --arg r "model $asked dropped: $atype runs on $cap; change its definition to raise it" \
      '{hookSpecificOutput:{hookEventName:"PreToolUse",permissionDecision:"allow",permissionDecisionReason:$r,updatedInput:(.tool_input | del(.model))}}'
    exit 0
  fi
fi

jq -n '{hookSpecificOutput:{hookEventName:"PreToolUse",permissionDecision:"allow"}}'
