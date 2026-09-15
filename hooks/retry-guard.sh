#!/usr/bin/env bash
# retry-guard.sh
set -uo pipefail

payload=$(cat)
tool=$(printf '%s' "$payload" | jq -r '.tool_name // ""')
[ "$tool" = "Bash" ] || exit 0

session=$(printf '%s' "$payload" | jq -r '.session_id // "unknown"')
cmd=$(printf '%s' "$payload" | jq -r '.tool_input.command // ""')
[ -z "$cmd" ] && exit 0

event=$(printf '%s' "$payload" | jq -r '.hook_event_name // "PostToolUse"')
code=$(printf '%s' "$payload" | jq -r '.tool_response.code // .tool_response.exit_code // empty')
interrupted=$(printf '%s' "$payload" | jq -r '.tool_response.interrupted // false')

failed=0
if [ "$event" = "PostToolUseFailure" ]; then failed=1; fi
if [ -n "$code" ] && [ "$code" != "0" ] && [ "$code" != "null" ]; then failed=1; fi
[ "$interrupted" = "true" ] && exit 0

norm=$(printf '%s' "$cmd" | tr -s ' \t' ' ' | sed -E 's/^ +| +$//g')
key=$(printf '%s' "$norm" | shasum -a 1 2>/dev/null | cut -c1-16 || printf '%s' "$norm" | sha1sum | cut -c1-16)

state_dir="${XDG_STATE_HOME:-$HOME/.local/state}/cc-retry-guard/$session"
mkdir -p "$state_dir"
find "${XDG_STATE_HOME:-$HOME/.local/state}/cc-retry-guard" -type d -mtime +2 -empty -delete 2>/dev/null || true
counter="$state_dir/$key"

if [ "$failed" -eq 0 ]; then
  rm -f "$counter"
  exit 0
fi

count=0
[ -f "$counter" ] && count=$(cat "$counter" 2>/dev/null || echo 0)
count=$(( count + 1 ))
echo "$count" > "$counter"

short=$(printf '%s' "$norm" | cut -c1-120)

if [ "$count" -eq 2 ]; then
  msg="RETRY GUARD: this command has now failed twice unchanged: \`$short\`. A third identical attempt is prohibited. Switch to /diagnose: capture the full error to a file, pin the versions involved, read the stack trace bottom-up to the first frame in this repo, list three hypotheses, and state ROOT CAUSE with evidence before changing anything."
elif [ "$count" -ge 3 ]; then
  msg="RETRY GUARD: \`$short\` has failed $count times unchanged. You are in a trial-and-error loop. Stop executing. Write ROOT CAUSE: <sentence> and EVIDENCE: <log line / doc quote for the pinned version / experiment result> before the next tool call. If two hypotheses conflict, consult the advisor. If the cause is outside your control, mark the task '- [!] BLOCKED: <reason>' and move on."
else
  exit 0
fi

jq -n --arg e "$event" --arg m "$msg" '{hookSpecificOutput:{hookEventName:$e,additionalContext:$m}}'
