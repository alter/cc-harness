#!/usr/bin/env bash
# notify.sh
set -uo pipefail

title=${1:-}
body=${2:-}

if [ -z "$title" ]; then
  payload=$(cat)
  kind=$(printf '%s' "$payload" | jq -r '.notification_type // "notification"')
  text=$(printf '%s' "$payload" | jq -r '.message // .title // ""' | cut -c1-200)
  dir=$(printf '%s' "$payload" | jq -r '.cwd // ""' | xargs -I{} basename {} 2>/dev/null)
  case "$kind" in
    permission_prompt) title="Claude waits for permission" ;;
    idle_prompt)       title="Claude is idle" ;;
    usage_limit)       title="Claude hit the usage limit" ;;
    elicitation_dialog) title="Claude asks a question" ;;
    *)                 title="Claude: $kind" ;;
  esac
  body="${dir:+[$dir] }$text"
fi

esc() { printf '%s' "$1" | sed 's/\\/\\\\/g; s/"/\\"/g'; }

if command -v osascript >/dev/null 2>&1; then
  osascript -e "display notification \"$(esc "$body")\" with title \"$(esc "$title")\" sound name \"Glass\"" >/dev/null 2>&1 || true
elif command -v notify-send >/dev/null 2>&1; then
  notify-send "$title" "$body" >/dev/null 2>&1 || true
fi

exit 0
