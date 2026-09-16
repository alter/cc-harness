#!/usr/bin/env bash
# stop-guard.sh
set -uo pipefail

CAP=${CC_STOP_GUARD_CAP:-300}
STALL=${CC_STOP_GUARD_STALL:-3}
NOTIFY="$HOME/.claude/hooks/notify.sh"

payload=$(cat)
cwd=$(printf '%s' "$payload" | jq -r '.cwd // empty')
session=$(printf '%s' "$payload" | jq -r '.session_id // "unknown"')
last=$(printf '%s' "$payload" | jq -r '.last_assistant_message // ""')

[ -z "$cwd" ] && exit 0
[ -f "$cwd/.claude/plan-pause" ] && exit 0

plan=""
for f in "$cwd"/docs/plans/*.md "$cwd"/tasks/*/PLAN.md "$cwd"/tasks/*/*/PLAN.md; do
  [ -f "$f" ] || continue
  if head -n 8 "$f" | grep -qE '^status: *running *$'; then plan="$f"; break; fi
done
[ -z "$plan" ] && exit 0

open=$(grep -cE '^- \[ \] ' "$plan" || true)
blocked=$(grep -cE '^- \[!\] ' "$plan" || true)
rel=${plan#"$cwd"/}


if printf '%s' "$last" | grep -q 'NEED_HUMAN'; then
  [ -x "$NOTIFY" ] && "$NOTIFY" "Claude needs you" "$rel: $blocked blocked, $open open" || true
  exit 0
fi

if [ "$open" -eq 0 ]; then
  [ -x "$NOTIFY" ] && "$NOTIFY" "Plan finished" "$rel: all tasks done or blocked ($blocked blocked)" || true
  exit 0
fi

state_dir="${XDG_STATE_HOME:-$HOME/.local/state}/cc-stop-guard"
mkdir -p "$state_dir"
find "$state_dir" -type f -mtime +2 -delete 2>/dev/null || true
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
prev_open=${prev%%:*}
prev_state=${prev#*:}
stalls=0
if [ -n "$prev" ] && [ "$prev_open" = "$open" ]; then
  # Already released on this count: stay out of the way until the plan moves.
  [ "$prev_state" = "stalled" ] && exit 0
  case "$prev_state" in ''|*[!0-9]*) stalls=0 ;; *) stalls=$prev_state ;; esac
fi
if [ "$stalls" -ge "$STALL" ]; then
  echo "$open:stalled" > "$stall_file"
  [ -x "$NOTIFY" ] && "$NOTIFY" "Plan not advancing" "$rel: $open open, unchanged after $STALL continuations" || true
  exit 0
fi
echo "$open:$(( stalls + 1 ))" > "$stall_file"
echo $(( count + 1 )) > "$counter"

next=$(grep -E '^- \[ \] ' "$plan" | head -n 3 | sed -E 's/^- \[ \] //' | tr '\n' ';' | sed 's/;$//')

jq -n --arg r "Plan $rel still has $open unchecked task(s). Next: $next. Continue with the next unchecked task now. Mark it [x] only after its verify command passes, append a Log line, then take the following one. Do not stop while any '- [ ]' remains. Use '- [!] BLOCKED: <reason>' only for irreversible actions, missing credentials or a missing dependency." \
  '{decision:"block",reason:$r}'
