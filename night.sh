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

status=$(awk 'NR > 8 { exit } /^status:/ { sub(/^status:[[:space:]]*/, ""); sub(/[[:space:]]*$/, ""); print; exit }' "$plan")
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

rc=0
claude \
  --dangerously-skip-permissions \
  --effort high \
  --name "$name" \
  --settings '{"autoContinueAtUsageLimit":true}' \
  "/run $plan" || rc=$?

fullrun=${CC_FULLRUN:-}
if [ -z "$fullrun" ]; then
  here=$(cd "$(dirname "$0")" && pwd)
  if [ -x "$here/fullrun.sh" ]; then fullrun="$here/fullrun.sh"; else fullrun=$(command -v cc-fullrun || true); fi
fi
if [ -n "$fullrun" ] && [ -f docs/PROJECT.md ] && grep -q '^### Full tier' docs/PROJECT.md; then
  echo "full run: every command of the full tier, report next to the plan"
  bash "$fullrun" --project "$project" --out "$(cd "$(dirname "$plan")" && pwd)" || true
else
  echo "full run skipped: no full tier in docs/PROJECT.md §6 or no fullrun.sh/cc-fullrun found"
fi

plan_dir=$(cd "$(dirname "$plan")" && pwd)
audit="$plan_dir/TEST-AUDIT.md"
last_run=$(ls "$plan_dir"/FULLRUN-*.md 2>/dev/null | sort | tail -n 1)
audit_due=""
if [ ! -f "$audit" ] || [ -n "$(find "$audit" -mtime +6 2>/dev/null)" ]; then audit_due="the last audit is 7+ days old or missing"; fi
if [ -n "$last_run" ] && grep -qE 'fast_doubled=1|full_over_budget=1' "$last_run"; then audit_due="the full run reports fast_doubled or full_over_budget"; fi
if [ "${CC_NIGHT_TEST_AUDIT:-1}" != 0 ] && [ -n "$audit_due" ]; then
  echo "test audit: $audit_due"
  claude \
    --dangerously-skip-permissions \
    --effort high \
    --name "$name:test-audit" \
    -p "/test-audit $plan_dir" < /dev/null || true
fi

if [ "${CC_NIGHT_PGSQL:-1}" != 0 ] && grep -rqlIE --exclude-dir=.git --exclude-dir=node_modules --exclude-dir=.venv 'psycopg|asyncpg|pg8000|jackc/pgx|lib/pq|sqlx::Postgres|tokio-postgres|org\.postgresql|node-postgres|"pg":|postgres(ql)?://' . 2>/dev/null; then
  echo "pgsql: /pgsql-slow-queries project"
  claude \
    --dangerously-skip-permissions \
    --effort high \
    --name "$name:pgsql" \
    -p "/pgsql-slow-queries project" < /dev/null || true
fi

if [ "${CC_NIGHT_ATTACK:-1}" != 0 ]; then
  echo "attack: /attack milestone, every catalog; ATTACK.md next to the plan"
  claude \
    --dangerously-skip-permissions \
    --effort high \
    --name "$name:attack" \
    -p "/attack milestone" < /dev/null || true
fi
exit "$rc"
