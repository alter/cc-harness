#!/usr/bin/env bash
# selftest.sh
set -uo pipefail

SRC=$(cd "$(dirname "$0")" && pwd)
TARGET=${1:-$SRC}
TARGET=${TARGET/#\~/$HOME}
H="$TARGET/hooks"
[ -d "$H" ] || { echo "no hooks dir at $H" >&2; exit 1; }

TMP=$(mktemp -d)
export XDG_STATE_HOME="$TMP/state"
trap 'rm -rf "$TMP"' EXIT
pass=0; fail=0

ok()   { pass=$((pass+1)); printf '  PASS  %s\n' "$1"; }
bad()  { fail=$((fail+1)); printf '  FAIL  %s\n        got: %s\n' "$1" "$(printf '%s' "$2" | head -c 300)"; }
check(){ local name=$1 out=$2 pattern=$3; if printf '%s' "$out" | grep -qE "$pattern"; then ok "$name"; else bad "$name" "$out"; fi; }
check_empty(){ local name=$1 out=$2; if [ -z "$out" ]; then ok "$name"; else bad "$name" "$out"; fi; }

echo "== syntax"
for f in "$H"/*.sh "$TARGET/statusline.sh"; do
  if bash -n "$f" 2>/dev/null; then ok "bash -n $(basename "$f")"; else bad "bash -n $(basename "$f")" "syntax error"; fi
done
if [ -f "$TARGET/settings.json" ]; then
  if jq -e . "$TARGET/settings.json" >/dev/null 2>&1; then ok "settings.json is JSON"; else bad "settings.json is JSON" "invalid"; fi
  for cmd in $(jq -r '.. | .command? // empty' "$TARGET/settings.json" | grep -E '\.sh$'); do
    p=${cmd/#\~/$HOME}
    case "$p" in "$TARGET"/*) [ -x "$p" ] && ok "hook exists+x: $cmd" || bad "hook exists+x: $cmd" "missing or not executable" ;;
      *) printf '  SKIP  %s (not installed here)\n' "$cmd" ;; esac
  done
fi

echo "== read-guard"
seq 1 600 | sed 's/^/x = /' > "$TMP/big.py"
out=$(jq -n --arg f "$TMP/big.py" '{tool_name:"Read",tool_input:{file_path:$f}}' | "$H/read-guard.sh")
check "deny whole read of 600-line file" "$out" '"permissionDecision": *"deny"'
out=$(jq -n --arg f "$TMP/big.py" '{tool_name:"Read",tool_input:{file_path:$f,offset:100,limit:50}}' | "$H/read-guard.sh")
check_empty "allow windowed read" "$out"
cp "$TMP/big.py" "$TMP/big.md"
out=$(jq -n --arg f "$TMP/big.md" '{tool_name:"Read",tool_input:{file_path:$f}}' | "$H/read-guard.sh")
check_empty "allow .md regardless of size" "$out"

echo "== compress-output"
big=$(for i in $(seq 1 300); do echo "same line"; done; seq 1 400 | sed 's/^/unique /')
out=$(jq -n --arg s "$big" --arg c "$TMP" '{tool_name:"Bash",cwd:$c,tool_response:{stdout:$s,stderr:""}}' | "$H/compress-output.sh")
check "collapses repeats (x300)" "$out" 'same line +\(x300\)'
check "saves omitted middle to scratch" "$out" 'lines omitted; full stdout saved to'
ls "$TMP/.claude/scratch"/bash-*-stdout.log >/dev/null 2>&1 && ok "scratch file written" || bad "scratch file written" "none"
out=$(jq -n '{tool_name:"Bash",cwd:"/tmp",tool_response:{stdout:"short\n",stderr:""}}' | "$H/compress-output.sh")
check_empty "short output untouched" "$out"

echo "== retry-guard"
p() { jq -n --arg c "$1" --arg e "$2" --argjson code "$3" '{tool_name:"Bash",session_id:"t1",hook_event_name:$e,tool_input:{command:$c},tool_response:{code:$code,interrupted:false}}'; }
out=$(p "pytest -q" PostToolUse 1 | "$H/retry-guard.sh"); check_empty "1st failure: silent" "$out"
out=$(p "pytest  -q" PostToolUse 1 | "$H/retry-guard.sh"); check "2nd identical failure (spacing differs): /diagnose" "$out" 'RETRY GUARD: this command has now failed twice'
out=$(p "pytest -q" PostToolUseFailure 1 | "$H/retry-guard.sh"); check "3rd: stop and write ROOT CAUSE" "$out" 'failed 3 times unchanged'
out=$(p "pytest -q" PostToolUse 0 | "$H/retry-guard.sh"); check_empty "success resets" "$out"
out=$(p "pytest -q" PostToolUse 1 | "$H/retry-guard.sh"); check_empty "after reset: 1st failure silent again" "$out"

echo "== stop-guard / session-start"
proj="$TMP/proj"; mkdir -p "$proj/docs/plans"
cat > "$proj/docs/plans/smoke.md" <<'EOF'
---
status: running
created: 2026-09-15
---
# Smoke
## Tasks
- [x] T00 baseline — verify: `true`
- [ ] T01 create a.txt — verify: `test -f a.txt`
- [ ] T02 create b.txt — verify: `test -f b.txt`
- [!] T03 needs secret BLOCKED: no API key
## Log
- 00:00 T00 done: baseline green
EOF
sp() { jq -n --arg c "$proj" --arg l "$1" '{cwd:$c,session_id:"s1",last_assistant_message:$l}'; }
out=$(sp "I did T01, stopping here." | HOME="$TMP" "$H/stop-guard.sh")
check "blocks stop with 2 open" "$out" '"decision": *"block"'
check "names next task" "$out" 'T01 create a.txt'
out=$(sp "Everything left is blocked. NEED_HUMAN" | HOME="$TMP" "$H/stop-guard.sh")
check_empty "NEED_HUMAN releases" "$out"
touch "$proj/.claude-pause-probe"; mkdir -p "$proj/.claude"; touch "$proj/.claude/plan-pause"
out=$(sp "stopping" | HOME="$TMP" "$H/stop-guard.sh"); check_empty "plan-pause releases" "$out"
rm -f "$proj/.claude/plan-pause"
out=$(sp "x" | CC_STOP_GUARD_CAP=1 HOME="$TMP" "$H/stop-guard.sh"); check_empty "cap reached releases (counter already at 1)" "$out"
out=$(jq -n --arg c "$proj" '{cwd:$c,source:"compact"}' | "$H/session-start.sh")
check "session-start after compact re-injects plan" "$out" 'Context was just compacted.*2 open, 1 blocked'
check "session-start carries last log" "$out" 'T00 done: baseline green'
sed -i.bak 's/^- \[ \] T0[12].*$//' "$proj/docs/plans/smoke.md"
out=$(sp "done" | HOME="$TMP" "$H/stop-guard.sh"); check_empty "0 open: stop allowed" "$out"

echo "== subagent-evidence"
tr_none="$TMP/tr-none.jsonl"; tr_grep="$TMP/tr-grep.jsonl"
jq -nc '{message:{content:[{type:"text",text:"Found it in src/app.py:12"}]}}' > "$tr_none"
{ jq -nc '{message:{content:[{type:"tool_use",name:"Grep",input:{}}]}}'; jq -nc '{message:{content:[{type:"tool_use",name:"Read",input:{}}]}}'; } > "$tr_grep"
se() { jq -n --arg a "$1" --arg t "$2" --arg l "$3" '{agent_type:$a,agent_transcript_path:$t,last_assistant_message:$l,stop_hook_active:false}'; }
out=$(se scout "$tr_none" "Found it in src/app.py:12. TOOLS USED: Grep:1" | "$H/subagent-evidence.sh")
check "scout with 0 tool calls -> block" "$out" 'EVIDENCE GUARD.*no Grep/Glob/Read'
out=$(se scout "$tr_grep" "src/app.py:12-40 handles auth. TOOLS USED: Grep:1 Read:1" | "$H/subagent-evidence.sh")
check_empty "scout with Grep+Read and a path -> allow" "$out"
out=$(se scout "$tr_grep" "It is handled somewhere in the auth module." | "$H/subagent-evidence.sh")
check "scout answer without a path -> block" "$out" 'names no file path'
out=$(se scout "$tr_none" "NOT FOUND: no matches for foo" | "$H/subagent-evidence.sh")
check "NOT FOUND with 0 tool calls -> block" "$out" 'search that never happened'
out=$(se test-runner "$tr_grep" "PASS 12 tests" | "$H/subagent-evidence.sh")
check "test-runner without Bash -> block" "$out" 'no Bash call'
jq -nc '{message:{content:[{type:"tool_use",name:"Bash",input:{}}]}}' > "$TMP/tr-bash.jsonl"
out=$(se test-runner "$TMP/tr-bash.jsonl" $'COMMAND: pytest -q\nPASS: 12 passed. TOOLS USED: Bash:1' | "$H/subagent-evidence.sh")
check_empty "test-runner with Bash+COMMAND+PASS -> allow" "$out"
out=$(se test-runner "$TMP/tr-bash.jsonl" "12 passed" | "$H/subagent-evidence.sh")
check "test-runner without COMMAND: line -> block" "$out" 'must contain the exact COMMAND'
out=$(se worker "$tr_none" "T05 done: added parser. TOOLS USED: none" | "$H/subagent-evidence.sh")
check "worker with no Edit/Write/Bash -> block" "$out" 'did no work'
out=$(se researcher "$tr_none" "NOT DONE: no network" | "$H/subagent-evidence.sh")
check_empty "NOT DONE always allowed" "$out"
out=$(se scout "$tr_none" "anything" | jq '.stop_hook_active=true' | "$H/subagent-evidence.sh")
check_empty "stop_hook_active -> allow (no loop)" "$out"

echo "== guard-subagent / guard-model-switch"
gs() { jq -n '{session_id:"g1",tool_input:{subagent_type:"scout"}}'; }
out=$(gs | CC_SUBAGENT_BUDGET=2 "$H/guard-subagent.sh"); check "1/2 allow" "$out" '"permissionDecision": *"allow"'
out=$(gs | CC_SUBAGENT_BUDGET=2 "$H/guard-subagent.sh"); check "2/2 allow" "$out" '"permissionDecision": *"allow"'
out=$(gs | CC_SUBAGENT_BUDGET=2 "$H/guard-subagent.sh"); check "3/2 deny" "$out" '"permissionDecision": *"deny"'
out=$(jq -n '{context_tokens:50000,from_model:"sonnet",to_model:"opus",source:"user"}' | "$H/guard-model-switch.sh")
check "switch at 50k ctx -> ask" "$out" '"permissionDecision": *"ask"'
out=$(jq -n '{context_tokens:1000,from_model:"sonnet",to_model:"opus",source:"user"}' | "$H/guard-model-switch.sh")
check "switch at 1k ctx -> allow" "$out" '"permissionDecision": *"allow"'

echo "== statusline"
out=$(jq -n '{model:{display_name:"Sonnet 5"},effort:{level:"medium"},context_window:{used_percentage:42.7},rate_limits:{five_hour:{used_percentage:61,resets_at:(now+5400)},seven_day:{used_percentage:23}},prompt_cache:{warm:false,ttl:"1h",hit_ratio:0.83,last_miss_cause:{causes:["model_changed"]},recache_tokens_if_cold:123456},workspace:{current_dir:"/x/myproj"}}' | "$TARGET/statusline.sh" | sed -E 's/\x1B\[[0-9;]*m//g')
check "statusline renders dir/model/ctx/5h/7d" "$out" 'myproj  Sonnet 5/medium  ctx 42%  5h 61%/(89|90)m  7d 23%'
check "statusline shows cold cache cause and recache size" "$out" 'cache cold:model_changed 123k  hit 83%'

echo
echo "passed $pass, failed $fail"
[ "$fail" -eq 0 ]
