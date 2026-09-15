#!/usr/bin/env bash
# compress-output.sh
set -uo pipefail

MIN_LINES=${CC_COMPRESS_MIN_LINES:-40}
HEAD=${CC_COMPRESS_HEAD:-120}
TAIL=${CC_COMPRESS_TAIL:-120}

payload=$(cat)
tool=$(printf '%s' "$payload" | jq -r '.tool_name // ""')
[ "$tool" = "Bash" ] || exit 0
kind=$(printf '%s' "$payload" | jq -r '.tool_response.stdout | type')
[ "$kind" = "string" ] || exit 0

cwd=$(printf '%s' "$payload" | jq -r '.cwd // "."')
stdout=$(printf '%s' "$payload" | jq -r '.tool_response.stdout')
stderr=$(printf '%s' "$payload" | jq -r '.tool_response.stderr // ""')

total=$(( $(printf '%s\n' "$stdout" | wc -l) + $(printf '%s\n' "$stderr" | wc -l) ))
[ "$total" -lt "$MIN_LINES" ] && exit 0

squeeze() {
  sed -E 's/\x1B\[[0-9;?]*[A-Za-z]//g; s/[[:space:]]+$//' \
  | awk '
    BEGIN { prev = ""; n = 0 }
    {
      if ($0 == prev) { n++; next }
      if (n > 0) { printf "%s   (x%d)\n", prev, n + 1 } else if (NR > 1) { print prev }
      prev = $0; n = 0
    }
    END { if (n > 0) printf "%s   (x%d)\n", prev, n + 1; else if (NR > 0) print prev }
  ' \
  | cat -s
}

trim() {
  local text=$1 label=$2
  local n; n=$(printf '%s\n' "$text" | wc -l)
  if [ "$n" -le $(( HEAD + TAIL + 20 )) ]; then printf '%s' "$text"; return; fi
  local dir="$cwd/.claude/scratch"; mkdir -p "$dir"
  local f="$dir/bash-$(date +%s)-$label.log"
  printf '%s\n' "$text" > "$f"
  printf '%s\n' "$text" | head -n "$HEAD"
  printf '\n[... %d lines omitted; full %s saved to %s ...]\n\n' $(( n - HEAD - TAIL )) "$label" "${f#"$cwd"/}"
  printf '%s\n' "$text" | tail -n "$TAIL"
}

out=$(printf '%s' "$stdout" | squeeze); out=$(trim "$out" stdout)
err=$(printf '%s' "$stderr" | squeeze); err=$(trim "$err" stderr)

printf '%s' "$payload" | jq --arg o "$out" --arg e "$err" \
  '{hookSpecificOutput:{hookEventName:"PostToolUse",updatedToolOutput:(.tool_response + {stdout:$o, stderr:$e})}}'
