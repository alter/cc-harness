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

echo "== secrets"
sec="$TMP/sec"; mkdir -p "$sec"; echo "K=1" > "$sec/.env"; echo "K=" > "$sec/.env.example"
for c in "cat $sec/.env" "grep K $sec/.env" "cat ~/.ssh/id_ed25519" "head -n 3 ~/.aws/credentials" "source $sec/.env" "base64 $sec/.env.local"; do
  check "deny-secrets-bash: $c" "$(brg "$c")" '"permissionDecision": *"deny"'
done
check_empty "deny-secrets-template-allowed: cat .env.example" "$(brg "cat $sec/.env.example")"
check_empty "deny-secrets-cp-template-allowed: cp .env.example .env" "$(brg "cp $sec/.env.example $sec/.env")"
check_empty "deny-secrets-cp-template-allowed: cp backend/.env.example backend/.env" "$(brg "cp backend/.env.example backend/.env")"
check "deny-secrets-cp-out: copying .env elsewhere is a read" "$(brg "cp $sec/.env /tmp/leak")" '"permissionDecision": *"deny"'
if [ -f "$TARGET/settings.json" ]; then
  for rule in 'Read(**/.env)' 'Read(~/.ssh/**)' 'Bash(curl * | sh*)' 'Bash(curl * | bash*)'; do
    jq -e --arg r "$rule" '.permissions.deny | index($r)' "$TARGET/settings.json" >/dev/null && ok "deny-secrets-settings: $rule" || bad "deny-secrets-settings: $rule" "missing from permissions.deny"
  done
fi

echo "== integrity"
IC="$H/integrity-check.py"
ir="$TMP/integ"; mkdir -p "$ir/src" "$ir/tests" "$ir/docs/plans"
( cd "$ir" && git init -q
  printf 'def f(x):\n    return x  # noqa: E501\n' > src/a.py
  printf 'def test_f():\n    assert True\n' > tests/test_a.py
  printf 'linters:\n  enable: [errcheck]\n' > .golangci.yml
  printf '{"floor": 80.0, "tolerance": 0.2}\n' > .coverage-gate.json
  printf '[project]\nname = "x"\ndependencies = ["requests"]\n\n[tool.ruff]\nline-length = 100\n' > pyproject.toml
  printf -- '---\nstatus: running\n---\n# P\n## Decisions\n## Assumptions\n## Tasks\n- [ ] T01 x — verify: `true`\n## Log\n' > docs/plans/p.md
  git add -A && git -c user.name=t -c user.email=t@t commit -qm base )
base=$(git -C "$ir" rev-parse HEAD)
ic() { (cd "$ir" && python3 "$IC" --base "$base" --plan docs/plans/p.md 2>&1); }
reset_ir() { (cd "$ir" && git checkout -q -- . 2>/dev/null; git clean -qfd -e docs 2>/dev/null; git checkout -q -- docs); }
out=$(ic); check "integrity-clean: no change, no finding" "$out" 'integrity: 0 finding'
printf 'def g(y):\n    return y\n' >> "$ir/src/a.py"; out=$(ic); check "integrity-existing-marker-ignored: an old noqa does not count" "$out" 'integrity: 0 finding'; reset_ir
printf 'def g(y):  # noqa\n    return y\n' >> "$ir/src/a.py"; out=$(ic); check "integrity-added-suppression: a new noqa is a finding" "$out" 'integrity: [1-9]'; reset_ir
printf 'def h():\n    run() || true\n' > "$ir/src/b.sh"; (cd "$ir" && git add src/b.sh); out=$(ic); check "integrity-added-suppression: '|| true' in a new file is a finding" "$out" 'integrity: [1-9]'; (cd "$ir" && git rm -q --cached src/b.sh); rm -f "$ir/src/b.sh"
printf 'linters:\n  disable: [errcheck]\n' > "$ir/.golangci.yml"; out=$(ic); check "integrity-lint-config: a changed linter config is a finding" "$out" 'integrity: [1-9]'; reset_ir
rm "$ir/tests/test_a.py"; out=$(ic); check "integrity-deleted-test: a deleted test file is a finding" "$out" 'integrity: [1-9]'; reset_ir
printf '{"floor": 70.0, "tolerance": 0.2}\n' > "$ir/.coverage-gate.json"; out=$(ic); check "integrity-floor-lowered: a lowered coverage floor is a finding" "$out" 'integrity: [1-9]'; reset_ir
sed -i.bak 's/line-length = 100/line-length = 200/' "$ir/pyproject.toml"; out=$(ic); check "integrity-pyproject-tool-section: [tool.ruff] changed is a finding" "$out" 'integrity: [1-9]'; reset_ir
sed -i.bak 's/dependencies = \["requests"\]/dependencies = ["requests", "httpx"]/' "$ir/pyproject.toml"; out=$(ic); check "integrity-pyproject-dependency: a dependency change is not a finding" "$out" 'integrity: 0 finding'; reset_ir
printf 'linters:\n  disable: [errcheck]\n' > "$ir/.golangci.yml"; sed -i.bak 's/^## Assumptions$/## Assumptions\n- .golangci.yml: errcheck disabled, generated code — owner decision D3/' "$ir/docs/plans/p.md"
out=$(ic); check "integrity-declared: a change named in the plan's Assumptions is accepted" "$out" 'integrity: 0 finding'; reset_ir
mkdir -p "$ir/docs"; printf '## 6. Gate checks\n' > "$ir/docs/PROJECT.md"; (cd "$ir" && git add docs/PROJECT.md && git -c user.name=t -c user.email=t@t commit -qm project); base=$(git -C "$ir" rev-parse HEAD)
printf 'linters: {}\n' > "$ir/.yamllint.yml"; out=$(ic); check "integrity-new-check-without-project: a new check config without a PROJECT.md change is a finding" "$out" 'integrity: [1-9]'
printf '## 6. Gate checks\n\nyamllint .\n' > "$ir/docs/PROJECT.md"; out=$(ic); check "integrity-new-check-with-project: declared in PROJECT.md the same change passes" "$out" 'integrity: 0 finding'; reset_ir; rm -f "$ir/.yamllint.yml"

sg="$TMP/sgint"; mkdir -p "$sg/docs/plans" "$sg/src"
( cd "$sg" && git init -q && printf 'x = 1\n' > src/a.py \
  && printf -- '---\nstatus: running\n---\n# P\n## Assumptions\n## Tasks\n- [x] T01 x — verify: `true`\n- [ ] T02 y — verify: `true`\n## Log\n' > docs/plans/p.md \
  && git add -A && git -c user.name=t -c user.email=t@t commit -qm base )
sgp() { jq -n --arg c "$sg" '{cwd:$c,session_id:"integ-case",last_assistant_message:"x"}' | HOME="$TMP" "$H/stop-guard.sh"; }
sgp >/dev/null
printf 'y = 2  # noqa\n' >> "$sg/src/a.py"
out=$(sgp); check "integrity-stop: stop-guard names the added suppression" "$out" 'noqa'
sed -i.bak 's/^- \[ \] T02/- [x] T02/' "$sg/docs/plans/p.md"
out=$(sgp); check "integrity-stop: a finished plan with an undeclared suppression is not released" "$out" '"decision": *"block"'
sed -i.bak 's/^## Assumptions$/## Assumptions\n- src\/a.py: noqa on generated line, see D2/' "$sg/docs/plans/p.md"
out=$(sgp); check_empty "integrity-stop: a declared change releases" "$out"
sed -i.bak -e 's/^- \[x\] T02/- [ ] T02/' -e '/^- src\/a.py: noqa/d' "$sg/docs/plans/p.md"
sgs() { jq -n --arg c "$sg" '{cwd:$c,session_id:"integ-stall",last_assistant_message:"x"}' | CC_STOP_GUARD_STALL=3 HOME="$TMP" "$H/stop-guard.sh"; }
blocks=0; for _ in 1 2 3; do sgs | grep -q '"block"' && blocks=$((blocks+1)); done
out=$(sgs); [ "$blocks" -eq 3 ] && [ -z "$out" ] && ok "integrity-stop-stall-releases: an unresolved finding is released after STALL blocks" || bad "integrity-stop-stall-releases: an unresolved finding is released after STALL blocks" "blocks=$blocks, 4th: $out"
fz="$TMP/freeze-rerun"; mkdir -p "$fz/docs/plans"
printf -- '---\nstatus: running\ncreated: 2026-01-01\n---\n# R\n## Acceptance criteria\n- [x] AC1 old — `true`\n## Tasks\n- [x] T01 a — verify: `true`\n## Log\n' > "$fz/docs/plans/r.md"
fzp() { jq -n --arg c "$fz" '{cwd:$c,session_id:"freeze-rerun",last_assistant_message:"x"}' | HOME="$TMP" "$H/stop-guard.sh"; }
fzp >/dev/null
printf -- '---\nstatus: running\ncreated: 2026-02-01\n---\n# R\n## Acceptance criteria\n- [x] AC1 new — `make check`\n## Tasks\n- [x] T01 b — verify: `make check`\n## Log\n' > "$fz/docs/plans/r.md"
out=$(fzp); check_empty "ac-freeze-stale-run-ignored: a new plan at the same path starts a new freeze" "$out"

echo "== git-guard"
GG="$H/git-guard.py"
gg() { jq -n --arg c "$1" --arg d "${2:-$TMP}" '{tool_name:"Bash",tool_input:{command:$c},cwd:$d}' | python3 "$GG" 2>&1; }
for c in "git stash" "git stash pop" "git -C /tmp/x stash list" "git reset --hard HEAD~1" "git clean -fd" "git checkout -- ." "git restore ." \
         "git push --force origin main" "git push origin main --force" "git push -f" "git push origin +main" "git push --force-with-lease" \
         "git commit --no-verify -m x" "git commit -n -m x" "git -c core.hooksPath=/dev/null commit -m x" "git config core.hooksPath /tmp" \
         "cd repo && git stash" "FOO=1 git stash" "true; git -C . reset --hard" "bash -c 'git stash'" "sh -c \"git reset --hard\"" "eval 'git push --force'"; do
  check "git-guard-deny: $c" "$(gg "$c")" '"permissionDecision": *"deny"'
done
for c in "git status" "git stash-like-alias-is-not-stash" "git reset --soft HEAD~1" "git restore --staged a.py" "git checkout main" \
         "git push origin main" "git commit -m 'no --no-verify here'" "git clean -n" "echo git stash" "git log --grep stash"; do
  check_empty "git-guard-allow: $c" "$(gg "$c")"
done
gp="$TMP/gguard"; mkdir -p "$gp/docs"
printf '## 5. Unattended policy\n\n```deny\nterraform apply\nkubectl delete\n```\n\n## 6. Gate checks\n' > "$gp/docs/PROJECT.md"
check "git-guard-project-deny: a command listed in PROJECT.md §5 is refused" "$(gg "terraform apply -auto-approve" "$gp")" '"permissionDecision": *"deny"'
check_empty "git-guard-project-deny: an unlisted command passes" "$(gg "terraform plan" "$gp")"

echo "== compress-output"
big=$(for _ in $(seq 1 300); do echo "same line"; done; seq 1 400 | sed 's/^/unique /')
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
for _ in 1 2 3; do out=$(stp | HOME="$TMP" "$H/stop-guard.sh"); printf '%s' "$out" | grep -q '"block"' && blocks=$((blocks+1)); done
[ "$blocks" -eq 3 ] && ok "stop-guard blocks while the plan may still move (3)" || bad "stop-guard blocks while the plan may still move (3)" "blocked $blocks times"
out=$(stp | HOME="$TMP" "$H/stop-guard.sh"); check_empty "stalled plan releases after CC_STOP_GUARD_STALL blocks" "$out"
out=$(stp | HOME="$TMP" "$H/stop-guard.sh"); check_empty "stalled plan stays released while nothing changes" "$out"
sed -i.bak 's/- \[ \] T01/- [x] T01/' "$stallproj/docs/plans/s.md"
out=$(stp | HOME="$TMP" "$H/stop-guard.sh"); check "a closed task resumes blocking" "$out" '"decision": *"block"'

frz="$TMP/freeze"; mkdir -p "$frz/docs/plans"
cat > "$frz/docs/plans/f.md" <<'EOF'
---
status: running
---
# F
## Acceptance criteria
- [ ] AC1 parser handles empty input — `pytest -k empty`
## Tasks
- [ ] T01 parser — verify: `pytest -k parser`
## Log
EOF
fp() { jq -n --arg c "$frz" '{cwd:$c,session_id:"freeze-case",last_assistant_message:"x"}'; }
fp | HOME="$TMP" "$H/stop-guard.sh" >/dev/null
sed -i.bak -e 's/^- \[ \] AC1/- [x] AC1/' -e 's/^- \[ \] T01/- [x] T01/' "$frz/docs/plans/f.md"
out=$(fp | HOME="$TMP" "$H/stop-guard.sh"); check_empty "ac-freeze-checkbox-ok: ticking AC and tasks is not a change" "$out"
printf -- '- [x] T02 extra split — verify: `true`\n' >> "$frz/docs/plans/f.md"
out=$(fp | HOME="$TMP" "$H/stop-guard.sh"); check_empty "ac-freeze-appended-ok: an added task line is allowed" "$out"
sed -i.bak 's/pytest -k empty/true/' "$frz/docs/plans/f.md"
out=$(fp | HOME="$TMP" "$H/stop-guard.sh"); check "ac-freeze-changed-blocks: a weakened AC blocks the stop" "$out" '"decision": *"block"'
sed -i.bak 's/^- \[x\] AC1 parser handles empty input — `true`/- [x] AC1 parser handles empty input — `pytest -k empty`/' "$frz/docs/plans/f.md"
out=$(fp | HOME="$TMP" "$H/stop-guard.sh"); check_empty "ac-freeze-restored: restoring the AC releases" "$out"
sed -i.bak 's/verify: `pytest -k parser`/verify: `true`/' "$frz/docs/plans/f.md"
out=$(fp | HOME="$TMP" "$H/stop-guard.sh"); check "ac-freeze-verify-changed-blocks: a weakened verify blocks the stop" "$out" '"decision": *"block"'

out=$(jq -n --arg c "$proj" '{cwd:$c,source:"compact"}' | "$H/session-start.sh")
check "session-start after compact re-injects plan" "$out" 'Context was just compacted.*2 open, 1 blocked'
check "session-start carries last log" "$out" 'T00 done: baseline green'
sed -i.bak -E 's/^- \[ \] (T0[12])/- [x] \1/' "$proj/docs/plans/smoke.md"
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
fb="$TMP/fakebin"; mkdir -p "$fb"; printf '#!/usr/bin/env bash\nprintf "%%s\\n" "$*" >> "%s/claude-calls.log"\nexit 0\n' "$TMP" > "$fb/claude"; chmod +x "$fb/claude"
nr="$TMP/nightrun"; mkdir -p "$nr/docs/plans"
printf -- '---\nstatus: draft\ncreated: 2026-10-05\n---\n# P\n## Tasks\n- [ ] T01 x — verify: `true`\n## Log\n' > "$nr/docs/plans/p.md"
printf '## 6. Gate checks\n\n### Fast tier\n\n```\ntrue\n```\n\n### Full tier\n\n```\ntrue\n```\n\n## 7. Delivery\n' > "$nr/docs/PROJECT.md"
printf 'import psycopg\n' > "$nr/db.py"
out=$(PATH="$fb:$PATH" bash "$N" docs/plans/p.md "$nr" 2>&1)
check "night-runs-pgsql: a repository that talks to PostgreSQL gets /pgsql-slow-queries project" "$(cat "$TMP/claude-calls.log" 2>/dev/null)" '/pgsql-slow-queries project'
check "night-runs-attack: /attack milestone follows the full run" "$(cat "$TMP/claude-calls.log" 2>/dev/null)" '/attack milestone'
ls "$nr"/docs/plans/FULLRUN-*.md >/dev/null 2>&1 && ok "night-runs-full-tier: the full run follows /run, report next to the plan" || bad "night-runs-full-tier: the full run follows /run, report next to the plan" "$out"

echo "== task tree (check.py)"
tt=$(TASKTREE_TEMPLATE="$TARGET/project-template/tasks" python3 -m unittest -v "$SRC/selftest/test_tasktree.py" 2>&1)
while IFS= read -r line; do
  case "$line" in
    "test_"*" ... ok") ok "${line%% *}" ;;
    "test_"*" ... FAIL"|"test_"*" ... ERROR") bad "${line%% *}" "$(printf '%s' "$tt" | grep -A12 "^[A-Z]*: ${line%% *}" | tail -n +3)" ;;
  esac
done <<< "$tt"
printf '%s' "$tt" | grep -qE '^Ran [1-9]' || bad "task tree tests ran" "$tt"

echo "== full run"
FR="$SRC/fullrun.sh"
frp="$TMP/fullrun"; mkdir -p "$frp/docs"
cat > "$frp/docs/PROJECT.md" <<'EOF'
## 6. Gate checks

### Fast tier

```
true
```

### Full tier

```
echo first
test -f fixed.flag
echo third
```

| Question | Answer |
|---|---|
| How a test is marked full-only here | separate command |
| Fast tier wall time at `T00`, seconds, from the run | 1 |

## 7. Delivery
EOF
fr() { (cd "$frp" && bash "$FR" --out "$frp/report" 2>&1); }
out=$(fr); check "fullrun-keeps-going: every command runs after a failure" "$out" 'fullrun: total=3 pass=2 fail=1 '
check "fullrun-first-report-has-no-history" "$out" 'new_red=1 still_red=0 fixed=0'
out=$(fr); check "fullrun-diff-vs-previous: a known red stays known" "$out" 'new_red=0 still_red=1 fixed=0'
touch "$frp/fixed.flag"
out=$(fr); check "fullrun-diff-vs-previous: a repaired command is reported fixed" "$out" 'fail=0 .*fixed=1'
sed -i.bak 's/^echo third$/no-such-tool-xyz --run/' "$frp/docs/PROJECT.md"
out=$(fr); check "fullrun-stale-command: a missing command is stale, not a test failure" "$out" 'stale=1'
check "fullrun-fast-tier-within-budget" "$out" 'fast_doubled=0'
sed -i.bak 's/^true$/sleep 3/' "$frp/docs/PROJECT.md"
out=$(fr); check "fullrun-fast-tier-doubled: a fast tier past twice its T00 time is a finding" "$out" 'fast_doubled=1'
ls "$frp/report"/FULLRUN-*.md >/dev/null 2>&1 && ok "fullrun writes its report into --out" || bad "fullrun writes its report into --out" "$(ls "$frp/report" 2>&1)"

echo "== skill references"
for ref in "$TARGET/skills/attack/catalogs.md" "$TARGET/skills/pgsql-slow-queries/reference.md"; do
  name=$(basename "$(dirname "$ref")")
  if [ ! -f "$ref" ]; then bad "$name reference exists" "missing $ref"; continue; fi
  nourl=$(grep -nE '^\s*- ' "$ref" | grep -vE 'https?://' | head -3)
  [ -z "$nourl" ] && ok "$name reference: every item carries a URL" || bad "$name reference: every item carries a URL" "$nourl"
  grep -qE 'retrieved [0-9]{4}-[0-9]{2}-[0-9]{2}' "$ref" && ok "$name reference: dated" || bad "$name reference: dated" "no 'retrieved YYYY-MM-DD'"
done

echo "== agenttest"
if [ -x "$SRC/agenttest.sh" ]; then
  at=$(AGENTTEST_OUT="$TMP/agenttest" "$SRC/agenttest.sh" --self-check 2>&1)
  check "agenttest judge separates found, missed and decoy" "$at" 'agenttest self-check: ok'
else
  bad "agenttest.sh present" "missing or not executable"
fi

echo "== disabled hooks"
out=$(jq -n --arg f "$TMP/big.py" '{tool_name:"Read",tool_input:{file_path:$f}}' | CC_DISABLED_HOOKS=read-guard "$H/read-guard.sh"); check_empty "disabled-hooks: read-guard" "$out"
out=$(jq -n --arg c "cat $TMP/big.py" '{tool_name:"Bash",tool_input:{command:$c}}' | CC_DISABLED_HOOKS=x,bash-read-guard python3 "$H/bash-read-guard.py"); check_empty "disabled-hooks: bash-read-guard" "$out"
out=$(jq -n '{tool_name:"Bash",tool_input:{command:"git stash"},cwd:"/tmp"}' | CC_DISABLED_HOOKS=git-guard python3 "$H/git-guard.py"); check_empty "disabled-hooks: git-guard" "$out"
out=$(jq -n --arg c "$stallproj" '{cwd:$c,session_id:"disabled-case",last_assistant_message:"x"}' | CC_DISABLED_HOOKS=stop-guard HOME="$TMP" "$H/stop-guard.sh"); check_empty "disabled-hooks: stop-guard" "$out"
out=$(jq -n --arg f "$TMP/big.py" '{tool_name:"Read",tool_input:{file_path:$f}}' | CC_DISABLED_HOOKS=retry-guard "$H/read-guard.sh"); check "disabled-hooks: another hook's id does not disable this one" "$out" '"permissionDecision": *"deny"'
for f in "$H"/*.sh "$H"/*.py; do
  id=$(basename "$f"); id=${id%.*}
  grep -q 'CC_DISABLED_HOOKS' "$f" && ok "disabled-hooks: $id honours the switch" || bad "disabled-hooks: $id honours the switch" "no CC_DISABLED_HOOKS check in $f"
done

echo "== lint (the harness itself)"
if command -v shellcheck >/dev/null; then
  sc=$(shellcheck -S warning "$H"/*.sh "$SRC"/*.sh 2>&1); [ -z "$sc" ] && ok "lint-shell: shellcheck, warnings and above" || bad "lint-shell: shellcheck, warnings and above" "$sc"
else echo "  SKIP  lint-shell: shellcheck not installed"; fi
if command -v ruff >/dev/null; then
  rf=$(ruff check --no-cache --extend-exclude "$SRC/selftest/agentcases" "$H" "$SRC/project-template" "$SRC/selftest" 2>&1); printf '%s' "$rf" | grep -q 'All checks passed' && ok "lint-python: ruff" || bad "lint-python: ruff" "$rf"
else echo "  SKIP  lint-python: ruff not installed"; fi
if command -v gitleaks >/dev/null && [ -d "$SRC/.git" ]; then
  gl=$(gitleaks git --no-banner --redact "$SRC" 2>&1); [ $? -eq 0 ] && ok "no-secrets: gitleaks over the history" || bad "no-secrets: gitleaks over the history" "$gl"
else echo "  SKIP  no-secrets: gitleaks not installed or not a git checkout"; fi

echo "== speaking outside the repository"
C="$TARGET/CLAUDE.md"; PT="$TARGET/project-template/docs/PROJECT.md"; IN="$TARGET/skills/intake/SKILL.md"
if grep -q '^## Speaking outside the repository' "$C"; then ok "the contract carries the outward-speech rule"; else bad "the contract carries the outward-speech rule" "section missing from CLAUDE.md"; fi
if grep -q 'you draft it, the user sends it' "$C"; then ok "the session never writes in the user's voice outside"; else bad "the session never writes in the user's voice outside" "rule missing"; fi
if grep -q 'never announce what made the change and you never deny it' "$C"; then ok "neither announce nor deny"; else bad "neither announce nor deny" "rule missing"; fi
if grep -q '^## 8\. Disclosure required by the receiving repository' "$PT"; then ok "PROJECT.md template has the disclosure row"; else bad "PROJECT.md template has the disclosure row" "section missing"; fi
if grep -q 'Contributing outward' "$IN"; then ok "/intake asks what the receiving repository requires"; else bad "/intake asks what the receiving repository requires" "question missing"; fi
if ! grep -q '1400' "$C" && grep -qi 'modul' "$C"; then ok "contract-modularity-rule: modular code instead of a line limit"; else bad "contract-modularity-rule: modular code instead of a line limit" "$(grep -n '1400\|odul' "$C")"; fi

echo
echo "passed $pass, failed $fail"
[ "$fail" -eq 0 ]
