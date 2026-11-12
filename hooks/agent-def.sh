#!/usr/bin/env bash
# agent-def.sh
set -uo pipefail

cwd=${1:-}
atype=${2:-}
[ -n "$atype" ] || exit 1
shift 2

file=""
for d in ${cwd:+"$cwd/.claude/agents"} "$HOME/.claude/agents"; do
  f="$d/$atype.md"
  [ -f "$f" ] || f=$(grep -lxE "name: *$atype" "$d"/*.md 2>/dev/null | head -n 1)
  [ -n "$f" ] && [ -f "$f" ] || continue
  file=$f
  break
done
[ -n "$file" ] || exit 1

for key in "$@"; do
  awk -v k="$key" 'NR==1 && $0!="---" {exit} NR>1 && $0=="---" {exit} $0 ~ "^"k":" {sub("^"k": *", ""); print; found=1; exit} END {if (!found) print ""}' "$file"
done
