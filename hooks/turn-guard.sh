#!/usr/bin/env bash
# turn-guard.sh
set -uo pipefail
case ",${CC_DISABLED_HOOKS:-}," in *",turn-guard,"*) exit 0 ;; esac

IFS= read -r -d '' payload || true
case "$payload" in *'"agent_id"'*) ;; *) exit 0 ;; esac

RESERVED=2

IFS=$'\037' read -r event aid atype session tpath tool tuid cwd < <(
  printf '%s' "$payload" | jq -r '[.hook_event_name, .agent_id, .agent_type, .session_id, .transcript_path, .tool_name, .tool_use_id, .cwd] | map(. // "") | join("\u001f")' 2>/dev/null
) || true
[ -n "${aid:-}" ] && [ -n "${atype:-}" ] || exit 0
[ -n "$session" ] || session=unknown
case "$aid$session" in *[!A-Za-z0-9_-]*) exit 0 ;; esac

max=$("${BASH_SOURCE[0]%/*}/agent-def.sh" "$cwd" "$atype" maxTurns 2>/dev/null) || exit 0
case "$max" in ''|*[!0-9]*) exit 0 ;; esac
[ "$max" -gt "$RESERVED" ] || exit 0

transcript="${tpath%.jsonl}/subagents/agent-$aid.jsonl"
state_dir="${XDG_STATE_HOME:-$HOME/.local/state}/cc-turn-guard/$session"
seen_file="$state_dir/$aid.seen"

seen_off=0
seen_n=0
seen_last=-
seen_ids=-

scan() {
  local off=0 n=0 last=- ids=- line
  if [ -f "$seen_file" ]; then
    read -r off n last ids < "$seen_file" || true
    case "$off$n" in ''|*[!0-9]*) off=0; n=0; last=-; ids=- ;; esac
  fi
  [ -f "$transcript" ] || return 0
  line=$(tail -c "+$(( off + 1 ))" "$transcript" 2>/dev/null \
    | LC_ALL=C awk '{pos += length($0) + 1} index($0, "\"type\":\"assistant\"") {print pos "\t" $0}' \
    | jq -nRr --argjson off "$off" --argjson n "$n" --arg last "$last" --arg ids "$ids" '
        reduce (inputs
                | index("\t") as $i
                | (.[0:$i] | tonumber) as $pos
                | (.[$i + 1:] | fromjson? // empty)
                | select(type == "object" and .type == "assistant" and (.message.id | type) == "string")
                | {pos: $pos, id: .message.id, tools: [.message.content[]? | objects | select(.type == "tool_use") | .id]}) as $m
          ({off: $off, n: $n, last: $last, ids: (if $ids == "-" then [] else ($ids | split(",")) end)};
           (if $m.id != .last then .n += 1 | .last = $m.id | .ids = [] else . end)
           | .ids += $m.tools
           | .off = ($off + $m.pos))
        | [.off, .n, .last, (if (.ids | length) == 0 then "-" else (.ids | join(",")) end)] | join(" ")' 2>/dev/null) || return 0
  read -r seen_off seen_n seen_last seen_ids <<< "$line"
  case "$seen_off$seen_n" in ''|*[!0-9]*) seen_off=0; seen_n=0; seen_last=-; seen_ids=-; return 0 ;; esac
  mkdir -p "$state_dir" 2>/dev/null || return 0
  printf '%s %s %s %s\n' "$seen_off" "$seen_n" "$seen_last" "$seen_ids" > "$seen_file.$$" 2>/dev/null && mv -f "$seen_file.$$" "$seen_file" 2>/dev/null
  return 0
}

current_turn() {
  local present=0
  scan
  case ",$seen_ids," in *",$tuid,"*) [ -n "$tuid" ] && present=1 ;; esac
  turn=$(( seen_n + 1 - present ))
}

refuse() {
  jq -n --arg r "TURN LIMIT: this is turn $turn of your $max and the call is refused by the harness, not by the tool. After turn $max the run is cut and everything you have not reported is lost. Deliver your report now, once: through SubagentHandback if you have that tool, otherwise as your plain answer. Say what you finished and write NOT CHECKED: <what> for the rest. Make no other tool call." \
    '{hookSpecificOutput:{hookEventName:"PreToolUse",permissionDecision:"deny",permissionDecisionReason:$r}}'
}

turn=0
case "$event" in
  PreToolUse)
    [ "$tool" = "SubagentHandback" ] && exit 0
    current_turn
    [ $(( max - turn )) -lt "$RESERVED" ] || exit 0
    refuse
    ;;
esac
exit 0
