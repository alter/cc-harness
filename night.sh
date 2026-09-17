#!/usr/bin/env bash
# night.sh
set -euo pipefail

plan=${1:?usage: night.sh <plan.md | task directory> [project-dir]}
project=${2:-$(pwd)}

cd "$project"

if [ -d "$plan" ]; then
  plan="${plan%/}/PLAN.md"
  [ -f "$plan" ] || { echo "no PLAN.md in that task directory: $plan" >&2
                      echo "Run /plan on the directory first." >&2; exit 1; }
fi
[ -f "$plan" ] || { echo "no such plan: $plan" >&2; exit 1; }

if [ "$(head -n 1 "$plan")" != "---" ]; then
  echo "not a plan: $plan has no front matter." >&2
  echo "A plan opens with '---', 'status:' and 'created:', and its tasks are '- [ ] T01 … — verify: <command>'." >&2
  echo "A document about the work is not a plan for it: /run has nothing to close and the Stop hook would never let go." >&2
  exit 1
fi

status=$(sed -n '1,8{/^status:/{s/^status:[[:space:]]*//;s/[[:space:]]*$//;p;q;}}' "$plan")
case "$status" in
  draft|running) ;;
  paused)
    echo "plan is paused: a previous run ended with NEED_HUMAN." >&2
    echo "Read '## Log' and BLOCKED.md, settle what stopped it, then set 'status: running' by hand." >&2
    echo "Starting an unattended run against an unanswered blocker just burns the limit." >&2
    exit 1 ;;
  done)
    echo "plan is already done: $plan" >&2; exit 1 ;;
  "")
    echo "no 'status:' in the first 8 lines of $plan" >&2; exit 1 ;;
  *)
    echo "plan status is '$status'; it must be draft or running" >&2; exit 1 ;;
esac

if ! grep -qE '^- \[[ x!]\] T[0-9]' "$plan"; then
  echo "no tasks in $plan: a plan carries '- [ ] T01 … — verify: <command>' lines." >&2
  echo "Checklist bullets without a T-number and a verify command cannot be closed or checked." >&2
  exit 1
fi

open=$(grep -cE '^- \[ \] T[0-9]' "$plan" || true)
if [ "$open" -eq 0 ]; then
  echo "nothing open in $plan: every task is [x] or [!]." >&2; exit 1
fi

sed -i.bak -E '1,8s/^status: *draft *$/status: running/' "$plan" && rm -f "$plan.bak"
rm -f .claude/plan-pause

name="night:$(basename "$(dirname "$plan")")"
[ "$(basename "$plan")" != "PLAN.md" ] && name="night:$(basename "$plan" .md)"

plural=s; [ "$open" -eq 1 ] && plural=""
echo "starting $name — $open open task$plural in $plan"

exec claude \
  --dangerously-skip-permissions \
  --effort high \
  --name "$name" \
  --settings '{"autoContinueAtUsageLimit":true}' \
  "/run $plan"
