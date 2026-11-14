#!/usr/bin/env bash
# plan-pick.sh
set -uo pipefail

cwd=${1:-}
[ -n "$cwd" ] || exit 1
fresh=${CC_STOP_GUARD_FRESH:-120}

blocked_tasks() { grep -cE '^- \[!\] T[0-9]' "$1"; }

finished=""
for f in "$cwd"/docs/plans/*.md "$cwd"/tasks/*/PLAN.md "$cwd"/tasks/*/*/PLAN.md; do
  [ -f "$f" ] || continue
  grep -qE '^status: *running *$' <<<"$(head -n 8 "$f")" || continue
  open=$(grep -cE '^- \[ \] T[0-9]' "$f")
  if [ "$open" -gt 0 ]; then
    printf '%s\n%s\n%s\n' "$f" "$open" "$(blocked_tasks "$f")"
    exit 0
  fi
  [ -z "$finished" ] && [ -n "$(find "$f" -mmin -"$fresh" 2>/dev/null)" ] && finished=$f
done
[ -n "$finished" ] || exit 1
printf '%s\n0\n%s\n' "$finished" "$(blocked_tasks "$finished")"
