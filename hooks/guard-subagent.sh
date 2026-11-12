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

effort_rank() {
  case "$(printf '%s' "$1" | tr '[:upper:]' '[:lower:]')" in
    low) echo 1 ;; medium) echo 2 ;; high) echo 3 ;; xhigh) echo 4 ;; max) echo 5 ;; *) echo 0 ;;
  esac
}

asked=$(printf '%s' "$payload" | jq -r '.tool_input.model // empty')
asked_effort=$(printf '%s' "$payload" | jq -r '.tool_input.effort // empty')
cwd=$(printf '%s' "$payload" | jq -r '.cwd // empty')
drop=()
reasons=()
if { [ -n "$asked" ] || [ -n "$asked_effort" ]; } && [ "$atype" != "fork" ]; then
  defined=""
  defined_effort=""
  { IFS= read -r defined; IFS= read -r defined_effort; } < <("${BASH_SOURCE[0]%/*}/agent-def.sh" "$cwd" "$atype" model effort 2>/dev/null) || true
  case "$defined" in ''|inherit) cap=${CLAUDE_CODE_SUBAGENT_MODEL:-} ;; *) cap=$defined ;; esac
  if [ -n "$asked" ] && [ "$(rank "$asked")" -gt "$(rank "$cap")" ] && [ "$(rank "$cap")" -gt 0 ]; then
    drop+=(model)
    reasons+=("model $asked dropped: $atype runs on $cap")
  fi
  effort_cap=${defined_effort:-${CLAUDE_CODE_SUBAGENT_EFFORT:-}}
  if [ -n "$asked_effort" ] && [ "$(effort_rank "$asked_effort")" -gt "$(effort_rank "$effort_cap")" ] && [ "$(effort_rank "$effort_cap")" -gt 0 ]; then
    drop+=(effort)
    reasons+=("effort $asked_effort dropped: $atype runs at $effort_cap")
  fi
fi

if [ "${#drop[@]}" -gt 0 ]; then
  reason="$(IFS=';'; printf '%s' "${reasons[*]}"); change its definition to raise it"
  keys=$(printf '%s\n' "${drop[@]}" | jq -R . | jq -s .)
  printf '%s' "$payload" | jq --arg r "$reason" --argjson k "$keys" \
    '{hookSpecificOutput:{hookEventName:"PreToolUse",permissionDecision:"allow",permissionDecisionReason:$r,updatedInput:(.tool_input | delpaths($k | map([.])))}}'
  exit 0
fi

jq -n '{hookSpecificOutput:{hookEventName:"PreToolUse",permissionDecision:"allow"}}'
