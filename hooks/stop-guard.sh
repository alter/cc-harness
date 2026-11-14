#!/usr/bin/env bash
# stop-guard.sh
set -uo pipefail
case ",${CC_DISABLED_HOOKS:-}," in *",stop-guard,"*) exit 0 ;; esac

CAP=${CC_STOP_GUARD_CAP:-300}
STALL=${CC_STOP_GUARD_STALL:-3}
NOTIFY="$HOME/.claude/hooks/notify.sh"

payload=$(cat)
cwd=$(printf '%s' "$payload" | jq -r '.cwd // empty')
session=$(printf '%s' "$payload" | jq -r '.session_id // "unknown"')
last=$(printf '%s' "$payload" | jq -r '.last_assistant_message // ""')
transcript=$(printf '%s' "$payload" | jq -r '.transcript_path // ""')

bg_task_live() {
  local hits ended now kind id val paths=()
  hits=$(grep -F -e 'background with ID: ' -e 'moved to the background (ID: ' -e 'Monitor started (task ' -e '<task-id>' "$1" 2>/dev/null) || return 1
  ended=$(grep -F '<status>' <<<"$hits" | grep -o '<task-id>[A-Za-z0-9_-]*</task-id>')
  now=$(date +%s)
  while IFS=$'\t' read -r kind id val; do
    [ -n "$id" ] || continue
    grep -qxF "<task-id>$id</task-id>" <<<"$ended" && continue
    case $kind in
      B) [ -e "$val" ] && paths+=("$val") ;;
      M) [ "$now" -lt "$val" ] && return 0 ;;
    esac
  done < <(jq -r '
    select(.type == "user")
    | ((.timestamp // "") | sub("\\.[0-9]+Z$"; "Z") | (try fromdateiso8601 catch 0)) as $ts
    | .message.content[]? | select(.type? == "tool_result")
    | (.content | if type == "string" then . else ([.[]? | .text? // empty] | join("\n")) end)
    | (capture("(background with ID: |moved to the background \\(ID: )(?<id>[A-Za-z0-9_-]+)\\)?\\. Output is being written to: (?<p>\\S+?\\.output)") | "B\t\(.id)\t\(.p)"),
      (capture("Monitor started \\(task (?<id>[A-Za-z0-9_-]+), expires in (?<n>[0-9]+)(?<u>[smh])") | "M\t\(.id)\t\($ts + (.n | tonumber) * ({"s": 1, "m": 60, "h": 3600}[.u]) | floor)")
  ' <<<"$hits" 2>/dev/null)
  [ ${#paths[@]} -gt 0 ] && command -v lsof >/dev/null && [ -n "$(lsof -t -- "${paths[@]}" 2>/dev/null)" ]
}

[ -z "$cwd" ] && exit 0
[ -f "$cwd/.claude/plan-pause" ] && exit 0
nap="${CLAUDE_STATE_DIR:-$HOME/.claude/state}/catnap/$session.json"
if [ -n "$(find "$nap" -mmin -15 2>/dev/null)" ] && jq -e '.pending == true' "$nap" >/dev/null 2>&1; then exit 0; fi
if [ -f "$transcript" ]; then
  last_tool=$(tail -n 400 "$transcript" | jq -r 'if .type == "system" and .subtype == "compact_boundary" then "compact_boundary" elif .type == "assistant" then (.message.content[]? | select(.type == "tool_use") | .name) else empty end' 2>/dev/null | tail -n 1)
  [ "$last_tool" = "mcp__catnap__compact_now" ] && exit 0
  idle=${CC_STOP_GUARD_AGENT_IDLE:-15}
  for meta in "${transcript%.jsonl}"/subagents/agent-*.meta.json; do
    [ -f "$meta" ] && [ -n "$(find "${meta%.meta.json}.jsonl" -mmin -"$idle" 2>/dev/null)" ] || continue
    jq -e '.requestShape == "background" and (.finished // false | not)' "$meta" >/dev/null 2>&1 && exit 0
  done
  bg_task_live "$transcript" && exit 0
fi

plan=""; open=0; blocked=0
{ IFS= read -r plan; IFS= read -r open; IFS= read -r blocked; } < <("$(dirname "$0")/plan-pick.sh" "$cwd" 2>/dev/null)
[ -z "$plan" ] && exit 0
rel=${plan#"$cwd"/}


if grep -q 'NEED_HUMAN' <<<"$last"; then
  [ -x "$NOTIFY" ] && "$NOTIFY" "Claude needs you" "$rel: $blocked blocked, $open open" || true
  exit 0
fi

state_dir="${XDG_STATE_HOME:-$HOME/.local/state}/cc-stop-guard"
mkdir -p "$state_dir"
find "$state_dir" -type f -name '*' ! -name 'freeze-*' -mtime +2 -delete 2>/dev/null || true

frozen_lines() {
  awk '
    /^## / { ac = ($0 ~ /^## Acceptance criteria/) ; next }
    ac && /^- \[[ x!]\] / { sub(/^- \[[ x!]\] /, ""); print "AC|" $0; next }
    /^- \[[ x!]\] T[0-9]+/ && / — verify: / {
      match($0, /T[0-9]+/); id = substr($0, RSTART, RLENGTH); v = $0; sub(/^.* — verify: /, "", v); print id "|" v
    }
  ' "$1"
}

created=$(awk 'NR > 8 { exit } /^created:/ { print; exit }' "$plan")
freeze="$state_dir/freeze-$(printf '%s|%s' "$plan" "$created" | cksum | cut -d' ' -f1)"
guard_reason=""
if [ ! -f "$freeze" ]; then
  frozen_lines "$plan" > "$freeze"
  git -C "$cwd" rev-parse HEAD > "$freeze.base" 2>/dev/null || rm -f "$freeze.base"
else
  current=$(frozen_lines "$plan")
  changed=""
  while IFS= read -r line; do
    [ -z "$line" ] && continue
    grep -qxF -- "$line" <<<"$current" || changed="$changed; ${line%%|*}: ${line#*|}"
  done < "$freeze"
  if [ -n "$changed" ]; then
    guard_reason="Plan $rel: acceptance criteria or verify commands changed since the plan started running (${changed#; }). The executor may not weaken or rewrite what proves the work; restore those lines exactly. Splitting a task adds lines, it does not rewrite them. Only the owner changes acceptance: they edit the plan and change its 'created:' line, or delete $freeze."
  fi
fi

integrity="$(dirname "$0")/integrity-check.py"
if [ -z "$guard_reason" ] && [ -f "$freeze.base" ] && [ -f "$integrity" ]; then
  report=$(cd "$cwd" && python3 "$integrity" --base "$(cat "$freeze.base")" --plan "$plan" 2>&1)
  [ $? -eq 1 ] && guard_reason="Plan $rel: $report"
fi

if [ -z "$guard_reason" ] && [ "$open" -eq 0 ]; then
  [ -x "$NOTIFY" ] && "$NOTIFY" "Plan finished" "$rel: all tasks done or blocked ($blocked blocked)" || true
  exit 0
fi
counter="$state_dir/$session"
count=0
[ -f "$counter" ] && count=$(cat "$counter" 2>/dev/null || echo 0)

if [ "$count" -ge "$CAP" ]; then
  [ -x "$NOTIFY" ] && "$NOTIFY" "Stop-guard cap reached" "$rel: $open open after $CAP continuations" || true
  exit 0
fi

# Release the turn when the plan stops advancing. Blocking is only justified while
# work is being closed: if the open-task count is unchanged across STALL
# consecutive blocks, the model has nothing it can do here (a stale plan left
# running, every remaining task waiting on something) and further blocks would
# just burn continuations until Claude Code overrides the hook anyway.
stall_file="$state_dir/$session.open"
prev=""
[ -f "$stall_file" ] && prev=$(cat "$stall_file" 2>/dev/null || echo "")
key="$open/$(printf '%s' "$guard_reason" | cksum | cut -d' ' -f1)"
prev_key=${prev%%:*}
prev_state=${prev#*:}
stalls=0
if [ -n "$prev" ] && [ "$prev_key" = "$key" ]; then
  # Already released on this count: stay out of the way until the plan moves.
  [ "$prev_state" = "stalled" ] && exit 0
  case "$prev_state" in ''|*[!0-9]*) stalls=0 ;; *) stalls=$prev_state ;; esac
fi
if [ "$stalls" -ge "$STALL" ]; then
  echo "$key:stalled" > "$stall_file"
  [ -x "$NOTIFY" ] && "$NOTIFY" "Plan not advancing" "$rel: $open open, unchanged after $STALL continuations${guard_reason:+ (a guard finding is still open)}" || true
  exit 0
fi
echo "$key:$(( stalls + 1 ))" > "$stall_file"
echo $(( count + 1 )) > "$counter"

if [ -n "$guard_reason" ]; then
  jq -n --arg r "$guard_reason" '{decision:"block",reason:$r}'
  exit 0
fi

next=$(grep -E '^- \[ \] T[0-9]' "$plan" | head -n 3 | sed -E 's/^- \[ \] //' | tr '\n' ';' | sed 's/;$//')

jq -n --arg r "Plan $rel still has $open unchecked task(s). Next: $next. Continue with the next unchecked task now. Mark it [x] only after its verify command passes, append a Log line, then take the following one. Do not stop while any '- [ ]' remains. Use '- [!] BLOCKED: <reason>' only for irreversible actions, missing credentials or a missing dependency." \
  '{decision:"block",reason:$r}'
