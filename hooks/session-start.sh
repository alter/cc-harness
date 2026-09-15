#!/usr/bin/env bash
# session-start.sh
set -uo pipefail

payload=$(cat)
cwd=$(printf '%s' "$payload" | jq -r '.cwd // empty')
source=$(printf '%s' "$payload" | jq -r '.source // "startup"')
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
[ "$open" -eq 0 ] && exit 0
rel=${plan#"$cwd"/}
next=$(grep -E '^- \[ \] ' "$plan" | head -n 3 | sed -E 's/^- \[ \] //' | tr '\n' ';' | sed 's/;$//')
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
