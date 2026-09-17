#!/usr/bin/env bash
# selftest.sh
set -uo pipefail

SRC=$(cd "$(dirname "$0")" && pwd)
TARGET=${1:-$SRC}
TARGET=${TARGET/#\~/$HOME}
TARGET=$(cd "$TARGET" 2>/dev/null && pwd || echo "$TARGET")
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
for f in "$H"/*.sh "$TARGET/statusline.sh" "$TARGET/graph-setup.sh"; do
  if bash -n "$f" 2>/dev/null; then ok "bash -n $(basename "$f")"; else bad "bash -n $(basename "$f")" "syntax error"; fi
done
for f in "$H"/*.py; do
  [ -e "$f" ] || continue
  if python3 -c "import ast,sys,pathlib; ast.parse(pathlib.Path(sys.argv[1]).read_text())" "$f" 2>/dev/null; then ok "python -m ast $(basename "$f")"; else bad "python -m ast $(basename "$f")" "syntax error"; fi
done
if [ "$TARGET" = "$SRC" ]; then
  echo "  NOTE  testing the source tree; hooks wired into another config dir are reported as SKIP."
  echo "        To check what is actually installed: $0 ~/.claude"
fi
if [ -f "$TARGET/settings.json" ]; then
  if jq -e . "$TARGET/settings.json" >/dev/null 2>&1; then ok "settings.json is JSON"; else bad "settings.json is JSON" "invalid"; fi
  dup=$(jq -r '(.hooks // {}) | to_entries | map(.key as $e | [.value[].hooks[].command] | group_by(.) | map(select(length > 1) | "\($e): \(.[0])")) | flatten | join(", ")' "$TARGET/settings.json")
  [ -z "$dup" ] && ok "no duplicated hook commands" || bad "no duplicated hook commands" "registered more than once: $dup"
  adv=$(jq -r '[(.advisorModel // ""), (.env.CLAUDE_CODE_ENABLE_EXPERIMENTAL_ADVISOR_TOOL // "")] | @tsv' "$TARGET/settings.json")
  case "$adv" in
    "	"*) ok "advisor: not configured, nothing to gate" ;;
    *"	1") ok "advisor: model set and the account gate is bypassed" ;;
    *) bad "advisor: advisorModel needs CLAUDE_CODE_ENABLE_EXPERIMENTAL_ADVISOR_TOOL=1" "advisorModel/flag: $adv — without the flag the tool never appears in the session" ;;
  esac
  m=$(jq -r '.model // "unset"' "$TARGET/settings.json")
  case "$m" in *"[1m]"|unset) ok "model keeps its context variant ($m)" ;; *) bad "model keeps its context variant" "$m — the [1m] suffix is gone, the window is 200k" ;; esac
  for cmd in $(jq -r '.. | .command? // empty' "$TARGET/settings.json" | grep -oE '[^ ]+\.(sh|py)$'); do
    p=${cmd/#\~/$HOME}
    case "$p" in
      "$TARGET"/*)
        case "$p" in
          *.py) [ -f "$p" ] && ok "hook present: $cmd" || bad "hook present: $cmd" "missing" ;;
          *)    [ -x "$p" ] && ok "hook exists+x: $cmd" || bad "hook exists+x: $cmd" "missing or not executable" ;;
        esac ;;
      *) printf '  SKIP  %s (not installed here)\n' "$cmd" ;;
    esac
  done
fi

echo "== read-guard"
seq 1 600 | sed 's/^/x = /' > "$TMP/big.py"
out=$(jq -n --arg f "$TMP/big.py" '{tool_name:"Read",tool_input:{file_path:$f}}' | "$H/read-guard.sh")
check "deny whole read of 600-line file" "$out" '"permissionDecision": *"deny"'
out=$(jq -n --arg f "$TMP/big.py" '{tool_name:"Read",tool_input:{file_path:$f,offset:100,limit:50}}' | "$H/read-guard.sh")
check_empty "allow windowed read" "$out"
cp "$TMP/big.py" "$TMP/big.md"
seq 1 40 > "$TMP/small.py"
seq 1 900 > "$TMP/with space.py"
out=$(jq -n --arg f "$TMP/big.md" '{tool_name:"Read",tool_input:{file_path:$f}}' | "$H/read-guard.sh")
check_empty "allow .md regardless of size" "$out"

echo "== bash-read-guard"
brg() { jq -n --arg c "$1" '{tool_name:"Bash",tool_input:{command:$c}}' | python3 "$H/bash-read-guard.py"; }
check "cat of a 600-line file is refused" "$(brg "cat $TMP/big.py")" '"permissionDecision": *"deny"'
check_empty "tail -5 is a targeted read" "$(brg "tail -5 $TMP/big.py")"
check_empty "head -n 20 is a targeted read" "$(brg "head -n 20 $TMP/big.py")"
check "head -n 900 is a whole-file read" "$(brg "head -n 900 $TMP/big.py")" '"permissionDecision": *"deny"'
check "tail -n +1 is a whole-file read" "$(brg "tail -n +1 $TMP/big.py")" '"permissionDecision": *"deny"'
check_empty "a pipe means the output is processed" "$(brg "cat $TMP/big.py | grep 42")"
check_empty "a redirect does not reach the window" "$(brg "cat $TMP/big.py > /tmp/out")"
check_empty "small files pass" "$(brg "cat $TMP/small.py")"
check_empty "markdown is exempt like in read-guard" "$(brg "cat $TMP/big.md")"
check_empty "unrelated commands pass" "$(brg "git log --oneline -5")"
spaced="$TMP/with space.py"
check "a quoted path with spaces is still checked" "$(brg "cat \"$spaced\"")" '"permissionDecision": *"deny"'
check "cd && cat is judged per segment" "$(brg "cd /tmp && cat $TMP/big.py")" '"permissionDecision": *"deny"'

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

stallproj="$TMP/stall"; mkdir -p "$stallproj/docs/plans"
printf -- '---\nstatus: running\n---\n# S\n## Tasks\n- [ ] T01 a\n- [ ] T02 b\n- [ ] T03 c\n## Log\n' > "$stallproj/docs/plans/s.md"
stp() { jq -n --arg c "$stallproj" '{cwd:$c,session_id:"stall-case",last_assistant_message:"stopping"}'; }
blocks=0
for i in 1 2 3; do out=$(stp | HOME="$TMP" "$H/stop-guard.sh"); printf '%s' "$out" | grep -q '"block"' && blocks=$((blocks+1)); done
[ "$blocks" -eq 3 ] && ok "stop-guard blocks while the plan may still move (3)" || bad "stop-guard blocks while the plan may still move (3)" "blocked $blocks times"
out=$(stp | HOME="$TMP" "$H/stop-guard.sh"); check_empty "stalled plan releases after CC_STOP_GUARD_STALL blocks" "$out"
out=$(stp | HOME="$TMP" "$H/stop-guard.sh"); check_empty "stalled plan stays released while nothing changes" "$out"
sed -i.bak 's/- \[ \] T01/- [x] T01/' "$stallproj/docs/plans/s.md"
out=$(stp | HOME="$TMP" "$H/stop-guard.sh"); check "a closed task resumes blocking" "$out" '"decision": *"block"'

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

tr_graph="$TMP/tr-graph.jsonl"
{ jq -nc '{message:{content:[{type:"tool_use",name:"mcp__graphify__get_node",input:{}}]}}'; jq -nc '{message:{content:[{type:"tool_use",name:"mcp__graphify__get_neighbors",input:{}}]}}'; } > "$tr_graph"
out=$(se scout "$tr_graph" "FILES: src/app.py:L93 assemble(). TOOLS USED: mcp__graphify__get_node:1" | "$H/subagent-evidence.sh")
check_empty "scout answering from a code graph -> allow" "$out"
out=$(se scout "$tr_graph" "it lives somewhere in the auth module" | "$H/subagent-evidence.sh")
check "code-graph answer without a path -> block" "$out" 'names no file path'

tr_web="$TMP/tr-web.jsonl"
jq -nc '{message:{content:[{type:"tool_use",name:"WebSearch",input:{}}]}}' > "$tr_web"
out=$(se web-researcher "$tr_grep" "The rate grew 12% in 2026." | "$H/subagent-evidence.sh")
check "an unknown web agent without a web call -> block" "$out" 'no WebFetch/WebSearch call'
out=$(se web-researcher "$tr_web" "The rate grew 12%." | "$H/subagent-evidence.sh")
check "an unknown web agent without a URL -> block" "$out" 'carries the URL it came from'
out=$(se web-researcher "$tr_web" "Grew 12% (https://example.org/report, 2026-04-01)." | "$H/subagent-evidence.sh")
check_empty "an unknown web agent with a URL -> allow" "$out"
out=$(se file-reader "$tr_web" "The file defines fee()." | "$H/subagent-evidence.sh")
check "an unknown file agent without a read -> block" "$out" 'no Read/Grep/Glob call'
out=$(se file-reader "$tr_grep" "It lives somewhere in the billing module." | "$H/subagent-evidence.sh")
check "an unknown file agent without a path -> block" "$out" 'names the path it came from'
out=$(se file-reader "$tr_grep" "src/billing/fee.py:41 def fee(). TOOLS USED: Read:1" | "$H/subagent-evidence.sh")
check_empty "an unknown file agent with a path -> allow" "$out"

echo "== guard-subagent / guard-model-switch"
gs() { jq -n '{session_id:"g1",tool_input:{subagent_type:"scout"}}'; }
out=$(gs | CC_SUBAGENT_BUDGET=2 "$H/guard-subagent.sh"); check "1/2 allow" "$out" '"permissionDecision": *"allow"'
out=$(gs | CC_SUBAGENT_BUDGET=2 "$H/guard-subagent.sh"); check "2/2 allow" "$out" '"permissionDecision": *"allow"'
out=$(gs | CC_SUBAGENT_BUDGET=2 "$H/guard-subagent.sh"); check "3/2 deny" "$out" '"permissionDecision": *"deny"'
out=$(jq -n '{context_tokens:50000,from_model:"sonnet",to_model:"opus",source:"user"}' | "$H/guard-model-switch.sh")
check "switch at 50k ctx -> ask" "$out" '"permissionDecision": *"ask"'
out=$(jq -n '{context_tokens:1000,from_model:"sonnet",to_model:"opus",source:"user"}' | "$H/guard-model-switch.sh")
check "switch at 1k ctx -> allow" "$out" '"permissionDecision": *"allow"'

echo "== advisor-check"
printf '[DEBUG] [AdvisorTool] Server-side tool enabled with claude-opus-5 as the advisor model\n' > "$TMP/adv-ok.log"
printf '[DEBUG] [AdvisorTool] Skipping advisor - sonnet cannot advise opus (advisor must be at least as capable as the base model)\n' > "$TMP/adv-skip.log"
printf '[DEBUG] GrowthBook is off for this session: telemetry opted out\n[DEBUG] [engine] turn 1 start\n' > "$TMP/adv-gate.log"
out=$(CLAUDE_CONFIG_DIR=/nonexistent bash "$SRC/advisor-check.sh" --log "$TMP/adv-ok.log" 2>&1); rc=$?
check "advisor-check reads an enabled log" "$out" 'ENABLED . claude-opus-5'
[ "$rc" -eq 0 ] && ok "advisor-check exits 0 when enabled" || bad "advisor-check exits 0 when enabled" "exit $rc"
out=$(CLAUDE_CONFIG_DIR=/nonexistent bash "$SRC/advisor-check.sh" --log "$TMP/adv-skip.log" 2>&1); rc=$?
check "advisor-check relays the skip reason" "$out" 'cannot advise opus'
[ "$rc" -ne 0 ] && ok "advisor-check exits non-zero when disabled" || bad "advisor-check exits non-zero when disabled" "exit $rc"
out=$(CLAUDE_CONFIG_DIR=/nonexistent bash "$SRC/advisor-check.sh" --log "$TMP/adv-gate.log" 2>&1)
check "advisor-check names telemetry when the gate closed silently" "$out" 'GrowthBook is off'

echo "== coverage gate"
cg="$SRC/project-template/scripts/coverage_gate.py"
cgdir="$TMP/cov"; mkdir -p "$cgdir"
echo '{"totals":{"percent_covered":73.4}}' > "$cgdir/coverage.json"
printf '{"format":"coverage-py","report":"coverage.json","floor":70.0,"tolerance":0.2}\n' > "$cgdir/.coverage-gate.json"
out=$(python3 "$cg" --root "$cgdir" 2>&1)
check "coverage grew: floor raised" "$out" 'floor raised from 70.00'
out=$(python3 "$cg" --root "$cgdir" 2>&1)
check "coverage unchanged: pass" "$out" 'PASS 73.40% \(floor 73.40%\)'
echo '{"totals":{"percent_covered":71.9}}' > "$cgdir/coverage.json"
out=$(python3 "$cg" --root "$cgdir" 2>&1); rc=$?
check "coverage fell: fail" "$out" 'FAIL 71.90% < floor 73.40%'
[ "$rc" -ne 0 ] && ok "coverage gate exits non-zero on a drop" || bad "coverage gate exits non-zero on a drop" "exit $rc"
floor_before=$(python3 -c 'import json,sys;print(json.load(open(sys.argv[1]))["floor"])' "$cgdir/.coverage-gate.json")
[ "$floor_before" = "73.4" ] && ok "a drop does not lower the floor" || bad "a drop does not lower the floor" "floor is $floor_before"
printf 'SF:a.js\nLF:10\nLH:8\nend_of_record\n' > "$cgdir/lcov.info"
printf '{"format":"lcov","report":"lcov.info","floor":0,"tolerance":0.2}\n' > "$cgdir/.coverage-gate.json"
out=$(python3 "$cg" --root "$cgdir" 2>&1)
check "lcov report is understood" "$out" 'PASS 80.00%'
rm -f "$cgdir/.coverage-gate.json"
out=$(python3 "$cg" --root "$cgdir" 2>&1)
check "missing config explains itself" "$out" 'no .coverage-gate.json'

echo "== advisor-stats"
adir="$TMP/projects"; mkdir -p "$adir"
python3 - "$adir/s1.jsonl" <<'PYEOF'
import json, sys
rows = [{"type":"assistant","message":{"usage":{"input_tokens":5,"cache_read_input_tokens":100000,"cache_creation_input_tokens":0},"content":[{"type":"text","text":"x"}]}},
        {"type":"assistant","message":{"usage":{"input_tokens":5,"cache_read_input_tokens":300000,"cache_creation_input_tokens":0},"content":[{"type":"server_tool_use","name":"advisor","input":{}}]}}]
open(sys.argv[1], "w").write("\n".join(json.dumps(r) for r in rows))
PYEOF
out=$(bash "$SRC/advisor-stats.sh" "$adir" 2>&1)
check "advisor-stats counts a call" "$out" 'advisor calls: 1'
check "advisor-stats reports forwarded context" "$out" 'max 300k per call'
rm -f "$adir/s1.jsonl"
out=$(bash "$SRC/advisor-stats.sh" "$adir" 2>&1)
check "advisor-stats on an empty directory" "$out" 'no transcripts with model turns found'

echo "== statusline"
out=$(jq -n '{model:{display_name:"Sonnet 5"},effort:{level:"medium"},context_window:{used_percentage:42.7},rate_limits:{five_hour:{used_percentage:61,resets_at:(now+5400)},seven_day:{used_percentage:23}},prompt_cache:{warm:false,ttl:"1h",hit_ratio:0.83,last_miss_cause:{causes:["model_changed"]},recache_tokens_if_cold:123456},workspace:{current_dir:"/x/myproj"}}' | "$TARGET/statusline.sh" | sed -E 's/\x1B\[[0-9;]*m//g')
check "statusline renders dir/model/ctx/5h/7d" "$out" 'myproj  Sonnet 5/medium  ctx 42%  5h 61%/(89|90)m  7d 23%'
check "statusline shows cold cache cause and recache size" "$out" 'cache cold:model_changed 123k  hit 83%'

echo "== graph-setup"
G="$TARGET/graph-setup.sh"
if [ -x "$G" ]; then ok "graph-setup.sh present and executable"; else bad "graph-setup.sh present and executable" "missing or not +x"; fi
gdir="$TMP/graph"; mkdir -p "$gdir"
python3 - "$gdir" <<'PYG'
import json, pathlib, sys
d = pathlib.Path(sys.argv[1])
def w(name, nodes, links, files=1):
    json.dump({"nodes": [{"id": str(i), "source_file": "f%d.py" % (i % files)} for i in range(nodes)],
               "links": links}, open(d / name, "w"))
w("fit.json", 40, [{"confidence": "EXTRACTED"}] * 50, files=4)
w("thin.json", 5, [{"confidence": "EXTRACTED"}] * 4)
w("guessy.json", 40, [{"confidence": "INFERRED"}] * 30 + [{"confidence": "EXTRACTED"}] * 20, files=4)
w("narrow.json", 40, [{"confidence": "EXTRACTED"}] * 50, files=2)
(d / "broken.json").write_text("not json")
PYG
out=$(bash "$G" --stats "$gdir/fit.json" 4 2>&1); rc=$?
check "graph-setup: a usable graph is FIT" "$out" 'FIT'
[ "$rc" -eq 0 ] && ok "graph-setup: FIT exits 0" || bad "graph-setup: FIT exits 0" "exit $rc"
out=$(bash "$G" --stats "$gdir/thin.json" 2>&1); rc=$?
check "graph-setup: too few nodes is UNFIT" "$out" 'only 5 nodes'
[ "$rc" -eq 2 ] && ok "graph-setup: UNFIT exits 2" || bad "graph-setup: UNFIT exits 2" "exit $rc"
out=$(bash "$G" --stats "$gdir/guessy.json" 4 2>&1)
check "graph-setup: too many INFERRED edges is UNFIT" "$out" '60\.0% of edges are INFERRED'
out=$(bash "$G" --stats "$gdir/narrow.json" 20 2>&1)
check "graph-setup: poor file coverage is UNFIT" "$out" 'covers 10% of code files'
out=$(bash "$G" --stats "$gdir/broken.json" 2>&1); rc=$?
check "graph-setup: an unreadable graph is reported, not crashed" "$out" 'unreadable graph'
[ "$rc" -eq 2 ] && ok "graph-setup: unreadable exits 2" || bad "graph-setup: unreadable exits 2" "exit $rc"
out=$(bash "$G" --stats 2>&1); rc=$?
[ "$rc" -eq 64 ] && ok "graph-setup: --stats without a path exits 64" || bad "graph-setup: --stats without a path exits 64" "exit $rc"
mkdir -p "$gdir/umbrella" && touch "$gdir/umbrella/.gitmodules"
( cd "$gdir/umbrella" && git init -q 2>/dev/null )
out=$(cd "$gdir/umbrella" && bash "$G" 2>&1); rc=$?
check "graph-setup: an umbrella repository is refused" "$out" 'has submodules'
[ "$rc" -eq 2 ] && ok "graph-setup: umbrella refusal exits 2" || bad "graph-setup: umbrella refusal exits 2" "exit $rc"
out=$(cd "$TMP" && bash "$G" 2>&1)
check "graph-setup: a non-repository is refused" "$out" 'not a git repository|is not on PATH'
if grep -q 'mcp__graphify__get_node' "$TARGET/agents/scout.md"; then ok "scout may call the graph tools"; else bad "scout may call the graph tools" "not in tools:"; fi
if [ -f "$TARGET/skills/graphify/SKILL.md" ]; then ok "graphify skill installed"; else bad "graphify skill installed" "missing"; fi

echo "== night.sh"
N="$SRC/night.sh"
nd="$TMP/night"; mkdir -p "$nd/docs/plans" "$nd/tasks/10-x/03-y" "$nd/.claude"
printf '# Analysis\n\n- [ ] look at this\n' > "$nd/docs/plans/notaplan.md"
printf -- '---\nstatus: paused\ncreated: 2026-09-17\n---\n# P\n## Tasks\n- [!] T01 x\n' > "$nd/tasks/10-x/03-y/PLAN.md"
printf -- '---\nstatus: running\ncreated: 2026-09-17\n---\n# P\n## Tasks\n- [x] T01 x\n' > "$nd/docs/plans/finished.md"
printf -- '---\nstatus: running\ncreated: 2026-09-17\n---\n# P\n## Notes\n- [ ] a bullet\n' > "$nd/docs/plans/notasks.md"
out=$(bash "$N" docs/plans/notaplan.md "$nd" 2>&1); rc=$?
check "night.sh: a document without front matter is not a plan" "$out" 'has no front matter'
[ "$rc" -eq 1 ] && ok "night.sh: refusal exits 1" || bad "night.sh: refusal exits 1" "exit $rc"
out=$(bash "$N" tasks/10-x/03-y "$nd" 2>&1)
check "night.sh: a task directory resolves to its PLAN.md" "$out" 'plan is paused'
check "night.sh: paused says why and what to do" "$out" 'NEED_HUMAN'
out=$(bash "$N" docs/plans/finished.md "$nd" 2>&1)
check "night.sh: a finished plan is refused" "$out" 'nothing open'
out=$(bash "$N" docs/plans/notasks.md "$nd" 2>&1)
check "night.sh: bullets without a T-number are not tasks" "$out" 'no tasks in'
out=$(bash "$N" docs/plans/missing.md "$nd" 2>&1)
check "night.sh: a missing plan is named" "$out" 'no such plan'
out=$(bash "$N" tasks/10-x "$nd" 2>&1)
check "night.sh: a directory without PLAN.md says so" "$out" 'no PLAN.md in that task directory'

echo "== speaking outside the repository"
C="$TARGET/CLAUDE.md"; PT="$TARGET/project-template/docs/PROJECT.md"; IN="$TARGET/skills/intake/SKILL.md"
if grep -q '^## Speaking outside the repository' "$C"; then ok "the contract carries the outward-speech rule"; else bad "the contract carries the outward-speech rule" "section missing from CLAUDE.md"; fi
if grep -q 'you draft it, the user sends it' "$C"; then ok "the session never writes in the user's voice outside"; else bad "the session never writes in the user's voice outside" "rule missing"; fi
if grep -q 'never announce what made the change and you never deny it' "$C"; then ok "neither announce nor deny"; else bad "neither announce nor deny" "rule missing"; fi
if grep -q '^## 8\. Disclosure required by the receiving repository' "$PT"; then ok "PROJECT.md template has the disclosure row"; else bad "PROJECT.md template has the disclosure row" "section missing"; fi
if grep -q 'Contributing outward' "$IN"; then ok "/intake asks what the receiving repository requires"; else bad "/intake asks what the receiving repository requires" "question missing"; fi

echo
echo "passed $pass, failed $fail"
[ "$fail" -eq 0 ]
