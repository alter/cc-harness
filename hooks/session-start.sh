#!/usr/bin/env bash
# session-start.sh
set -uo pipefail
case ",${CC_DISABLED_HOOKS:-}," in *",session-start,"*) exit 0 ;; esac

payload=$(cat)
cwd=$(printf '%s' "$payload" | jq -r '.cwd // empty')
source=$(printf '%s' "$payload" | jq -r '.source // "startup"')
[ -z "$cwd" ] && exit 0
[ -f "$cwd/.claude/plan-pause" ] && exit 0

plan=""; open=0; blocked=0
{ IFS= read -r plan; IFS= read -r open; IFS= read -r blocked; } < <("$(dirname "$0")/plan-pick.sh" "$cwd" 2>/dev/null)
[ -z "$plan" ] && exit 0
[ "$open" -eq 0 ] && exit 0
rel=${plan#"$cwd"/}
next=$(grep -E '^- \[ \] T[0-9]' "$plan" | head -n 3 | sed -E 's/^- \[ \] //' | tr '\n' ';' | sed 's/;$//')
lastlog=$(awk '/^## Log/{f=1;next} /^## /{f=0} f && /^- /' "$plan" | tail -n 2 | tr '\n' ' ')

case "$source" in
  compact) lead="Context was just compacted." ;;
  resume)  lead="Session resumed." ;;
  clear)   lead="Fresh context." ;;
  fork)    lead="Forked session." ;;
  *)       lead="Session start." ;;
esac

jq -n --arg c "$lead Active plan: $rel — $open open, $blocked blocked. Next: $next. Last log: $lastlog. Do not ask questions; continue with /run semantics: take the next unchecked task, verify, mark [x], append Log." \
  '{hookSpecificOutput:{hookEventName:"SessionStart",additionalContext:$c}}'
