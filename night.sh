#!/usr/bin/env bash
# night.sh
set -euo pipefail

plan=${1:?usage: night.sh docs/plans/<slug>.md [project-dir]}
project=${2:-$(pwd)}

cd "$project"
[ -f "$plan" ] || { echo "no such plan: $plan" >&2; exit 1; }

if ! head -n 8 "$plan" | grep -qE '^status: *(running|draft) *$'; then
  echo "plan status must be draft or running" >&2; exit 1
fi
sed -i.bak -E '1,8s/^status: *draft *$/status: running/' "$plan" && rm -f "$plan.bak"
rm -f .claude/plan-pause

name="night:$(basename "$plan" .md)"

exec claude \
  --dangerously-skip-permissions \
  --effort high \
  --name "$name" \
  --settings '{"autoContinueAtUsageLimit":true}' \
  "/run $plan"
