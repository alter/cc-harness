#!/usr/bin/env bash
# guard-model-switch.sh
set -uo pipefail

LIMIT=${CC_SWITCH_CTX_LIMIT:-40000}

payload=$(cat)
ctx=$(printf '%s' "$payload" | jq -r '.context_tokens // 0 | floor')
from=$(printf '%s' "$payload" | jq -r '.from_model // "?"')
to=$(printf '%s' "$payload" | jq -r '.to_model // "?"')
src=$(printf '%s' "$payload" | jq -r '.source // "?"')

if [ "$ctx" -gt "$LIMIT" ]; then
  jq -n --arg r "Switching $from -> $to re-caches ${ctx} prompt tokens (limit ${LIMIT}). Use a subagent with an explicit model, or /clear first." \
    '{hookSpecificOutput:{hookEventName:"PreModelSwitch",permissionDecision:"ask",permissionDecisionReason:$r}}'
  exit 0
fi

jq -n '{hookSpecificOutput:{hookEventName:"PreModelSwitch",permissionDecision:"allow"}}'
