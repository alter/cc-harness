#!/usr/bin/env bash
# subagent-evidence.sh
set -uo pipefail

payload=$(cat)
active=$(printf '%s' "$payload" | jq -r '.stop_hook_active // false')
[ "$active" = "true" ] && exit 0

atype=$(printf '%s' "$payload" | jq -r '.agent_type // ""')
transcript=$(printf '%s' "$payload" | jq -r '.agent_transcript_path // ""')
last=$(printf '%s' "$payload" | jq -r '.last_assistant_message // ""')

[ -f "$transcript" ] || exit 0
printf '%s' "$last" | grep -qE 'NOT DONE|НЕ СДЕЛАНО' && exit 0

counts=$(jq -r 'select(.message.content|type=="array") | .message.content[] | select(.type=="tool_use") | .name' "$transcript" 2>/dev/null | sort | uniq -c | awk '{printf "%s:%s ", $2, $1}')
total=$(jq -r 'select(.message.content|type=="array") | .message.content[] | select(.type=="tool_use") | .name' "$transcript" 2>/dev/null | wc -l | tr -d ' ')

has() { printf '%s' "$counts" | grep -qE "(^| )$1:"; }
has_graph() { printf '%s' "$counts" | grep -qE "(^| )mcp__[a-z0-9_]*graph[a-z0-9_]*__"; }

if printf '%s' "$last" | grep -qE 'NOT FOUND|НЕ НАЙДЕНО'; then
  [ "$total" -ge 1 ] && exit 0
  jq -n '{decision:"block",reason:"EVIDENCE GUARD: NOT FOUND is a claim about a search that never happened: the transcript shows zero tool calls. Search with Grep/Glob first, then report NOT FOUND with the patterns you tried."}'
  exit 0
fi

reason=""
case "$atype" in
  Explore|scout)
    if [ "$total" -eq 0 ] || ! { has Grep || has Glob || has Read || has_graph; }; then
      reason="You reported results for a code search but the transcript shows no Grep/Glob/Read or code-graph call ($total tool calls: ${counts:-none})."
    elif ! printf '%s' "$last" | grep -qE '[A-Za-z0-9_./-]+\.[A-Za-z0-9]{1,6}(:[0-9]+)?'; then
      reason="Your answer names no file path. A scout answer is paths with line ranges, or an explicit NOT FOUND."
    fi ;;
  test-runner)
    if ! has Bash; then
      reason="You reported a test result but the transcript shows no Bash call ($total tool calls: ${counts:-none}). A test result without a run does not exist."
    elif ! printf '%s' "$last" | grep -qE 'COMMAND:' || ! printf '%s' "$last" | grep -qE '\b(PASS|FAIL)\b'; then
      reason="The answer must contain the exact COMMAND: you ran and a PASS or FAIL verdict with counts."
    fi ;;
  researcher)
    if [ "$total" -eq 0 ]; then
      reason="You answered a research question without reading anything ($total tool calls). Read or fetch, then cite: path:line or URL under EVIDENCE."
    elif ! printf '%s' "$last" | grep -qE 'EVIDENCE'; then
      reason="The answer has no EVIDENCE section. Every claim needs a path:line or URL."
    fi ;;
  reviewer)
    if ! has Read; then
      reason="A review without a single Read call is not a review ($total tool calls: ${counts:-none})."
    fi ;;
  worker)
    if ! { has Edit || has Write || has Bash; }; then
      reason="A worker that made no Edit/Write/Bash call did no work ($total tool calls: ${counts:-none})."
    elif ! printf '%s' "$last" | grep -qE 'T[0-9]+ (done|blocked|open):'; then
      reason="The report must be exactly '<T##> done|blocked|open: <summary>' plus a TOOLS USED line."
    fi ;;
  verifier)
    if ! has Bash; then
      reason="Verification requires running the checks yourself; the transcript shows no Bash call."
    elif ! has Write && ! has Edit; then
      reason="VERIFY.md was not written (no Write/Edit call)."
    fi ;;
  *)
    # Agents this harness did not define still get a rule, chosen by what their name says they do:
    # the weakest guard belongs to agents that only think, not to those that read or search.
    lower=$(printf '%s' "$atype" | tr '[:upper:]' '[:lower:]')
    if [ "$total" -eq 0 ]; then
      reason="You reported completion with zero tool calls. Either do the work with tools, or answer plainly 'NOT DONE: <why>'."
    elif printf '%s' "$lower" | grep -qE 'web|search|research'; then
      if ! { has WebFetch || has WebSearch || has_graph; }; then
        reason="You reported a web answer but the transcript shows no WebFetch/WebSearch call ($total tool calls: ${counts:-none})."
      elif ! printf '%s' "$last" | grep -qE 'https?://'; then
        reason="A web answer carries the URL it came from. Give the source for every fact, or say plainly what the search did not find."
      fi
    elif printf '%s' "$lower" | grep -qE 'read|file|code|grep|explore|scout'; then
      if ! { has Read || has Grep || has Glob || has_graph; }; then
        reason="You reported what a file contains but the transcript shows no Read/Grep/Glob call ($total tool calls: ${counts:-none})."
      elif ! printf '%s' "$last" | grep -qE '[A-Za-z0-9_./-]+\.[A-Za-z0-9]{1,6}(:[0-9]+)?'; then
        reason="An answer about files names the path it came from, with line numbers where they matter."
      fi
    fi ;;
esac

[ -z "$reason" ] && exit 0

jq -n --arg r "EVIDENCE GUARD: $reason Do not restate the previous answer. Use the tools now and end with a line 'TOOLS USED: <name:count …>' that matches what you actually called; if the task cannot be done, say 'NOT DONE: <reason>'." \
  '{decision:"block",reason:$r}'
