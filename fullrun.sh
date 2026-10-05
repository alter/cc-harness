#!/usr/bin/env bash
# fullrun.sh
set -uo pipefail

project=$(pwd)
out=""
while [ $# -gt 0 ]; do
  case "$1" in
    --project) project=$2; shift 2 ;;
    --out) out=$2; shift 2 ;;
    -h|--help)
      echo "usage: fullrun.sh [--project DIR] [--out REPORT_DIR]" >&2
      echo "  runs every command of the full tier in docs/PROJECT.md §6, never stops at a failure," >&2
      echo "  times the fast tier against T00 and writes FULLRUN-<stamp>.md compared with the previous run." >&2
      exit 0 ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done
cd "$project" || exit 2
P=docs/PROJECT.md
[ -f "$P" ] || { echo "no $P in $project: run /intake first" >&2; exit 2; }
[ -n "$out" ] || out="$project/.claude/reports"
mkdir -p "$out"

tier() {
  awk -v want="### $1 tier" '
    /^## / && !/^## 6\./ { if (in6) exit }
    /^## 6\./ { in6 = 1; next }
    in6 && $0 == want { found = 1; next }
    found && /^```/ { if (code) exit; code = 1; next }
    found && code && NF && !/^#/ && $0 != "_unanswered_" { print }
  ' "$P"
}

stamp=$(date +%Y-%m-%d-%H%M%S)
n=0; while [ -e "$out/FULLRUN-$stamp.md" ]; do n=$((n+1)); stamp="$(date +%Y-%m-%d-%H%M%S)-$n"; done
logs="$project/.claude/scratch/fullrun/$stamp"; mkdir -p "$logs"
prev=$(ls "$out"/FULLRUN-*.tsv 2>/dev/null | sort | tail -n 1)
tsv="$out/FULLRUN-$stamp.tsv"; md="$out/FULLRUN-$stamp.md"
: > "$tsv"

full_cmds=$(tier Full)
[ -n "$full_cmds" ] || { echo "no full tier declared in $P §6 (### Full tier)" >&2; exit 2; }

total=0; pass=0; fail=0; stale=0; i=0
rows=""
while IFS= read -r cmd; do
  [ -z "$cmd" ] && continue
  i=$((i+1)); total=$((total+1))
  log="$logs/$i.log"
  t0=$(date +%s)
  bash -c "$cmd" > "$log" 2>&1 < /dev/null
  rc=$?
  secs=$(( $(date +%s) - t0 ))
  if [ "$rc" -eq 0 ]; then
    status=pass; pass=$((pass+1))
  elif [ "$rc" -eq 127 ] || [ "$rc" -eq 126 ] || { grep -qE 'No such file or directory|command not found' "$log" && [ "$(wc -l < "$log")" -le 3 ]; }; then
    status=stale; stale=$((stale+1))
  else
    status=fail; fail=$((fail+1))
  fi
  printf '%s\t%s\n' "$status" "$cmd" >> "$tsv"
  rows="$rows| $i | $status | $rc | ${secs}s | \`$cmd\` | $log |"$'\n'
done <<< "$full_cmds"

new_red=0; still_red=0; fixed=0
compare=""
while IFS=$'\t' read -r status cmd; do
  before=""
  [ -n "$prev" ] && before=$(awk -F'\t' -v c="$cmd" '$2 == c { print $1; exit }' "$prev")
  case "$status:$before" in
    fail:fail|stale:stale|fail:stale|stale:fail) still_red=$((still_red+1)); compare="$compare- still red: \`$cmd\`"$'\n' ;;
    fail:*|stale:*) new_red=$((new_red+1)); compare="$compare- **new red**: \`$cmd\`"$'\n' ;;
    pass:fail|pass:stale) fixed=$((fixed+1)); compare="$compare- fixed: \`$cmd\`"$'\n' ;;
  esac
done < "$tsv"

fast_note="fast tier: not declared"; fast_doubled=0
fast_cmds=$(tier Fast)
if [ -n "$fast_cmds" ]; then
  t0=$(date +%s)
  while IFS= read -r cmd; do [ -n "$cmd" ] && bash -c "$cmd" > "$logs/fast.log" 2>&1 < /dev/null; done <<< "$fast_cmds"
  fast_secs=$(( $(date +%s) - t0 ))
  base=$(grep -E '^\| Fast tier wall time' "$P" | awk -F'|' '{print $3}' | tr -dc '0-9')
  if [ -n "$base" ] && [ "$base" -gt 0 ] && [ "$fast_secs" -gt $((base * 2)) ]; then
    fast_doubled=1
    fast_note="fast tier: ${fast_secs}s against ${base}s at T00 — **more than doubled**; move slow tests to the full tier (finding, does not block)"
  elif [ -n "$base" ]; then
    fast_note="fast tier: ${fast_secs}s against ${base}s at T00"
  else
    fast_note="fast tier: ${fast_secs}s (no T00 time recorded in §6)"
  fi
fi

summary="fullrun: total=$total pass=$pass fail=$fail stale=$stale new_red=$new_red still_red=$still_red fixed=$fixed fast_doubled=$fast_doubled"
{
  echo "# Full run $stamp"
  echo
  echo "$summary"
  echo
  echo "Compared with: ${prev:-nothing (first run)}"
  echo
  echo "| # | status | exit | time | command | log |"
  echo "|---|---|---|---|---|---|"
  printf '%s' "$rows"
  echo
  echo "## Changes since the previous run"
  printf '%s' "${compare:-- none}"
  echo
  echo
  echo "## Fast tier"
  echo "$fast_note"
  [ "$stale" -gt 0 ] && { echo; echo "## Stale declarations"; echo "A command in §6 no longer exists or points at a missing path: the declaration in docs/PROJECT.md is out of date, not a test failure. Fix §6 (/intake refresh)."; }
} > "$md"

echo "$summary"
echo "report: $md"
[ "$fail" -eq 0 ] && [ "$stale" -eq 0 ]
