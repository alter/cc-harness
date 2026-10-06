#!/usr/bin/env bash
# agenttest.sh
set -uo pipefail

SRC=$(cd "$(dirname "$0")" && pwd)
CASES="$SRC/selftest/agentcases"
CLAUDE_BIN=${CLAUDE_BIN:-claude}
OUT=${AGENTTEST_OUT:-$(mktemp -d)}; mkdir -p "$OUT"
pass=0; fail=0

usage() {
  echo "usage: agenttest.sh [--self-check] [case ...]" >&2
  echo "  runs each agent on a fixture repository with a planted defect and checks that its report names it." >&2
  echo "  cases: $(ls "$CASES" 2>/dev/null | tr '\n' ' ')" >&2
}

build_repo() {
  local case_dir=$1 work=$2
  mkdir -p "$work/.claude/agents"
  cp -R "$case_dir/base/." "$work/"
  [ -d "$work/tasks" ] && cp "$SRC"/project-template/tasks/*.py "$work/tasks/"
  ( cd "$work" && git init -q && git add -A && git -c user.name=t -c user.email=t@t commit -qm base ) || return 1
  if [ -d "$case_dir/change" ]; then
    cp -R "$case_dir/change/." "$work/"
    ( cd "$work" && git add -A && git -c user.name=t -c user.email=t@t commit -qm change ) || return 1
  fi
  for a in $(cat "$case_dir/agent"); do
    [ "$a" = main ] && continue
    cp "$SRC/agents/$a.md" "$work/.claude/agents/$a.md" || return 1
  done
  [ -f "$case_dir/with-fullrun" ] && cp -R "$SRC/fullrun" "$work/.claude/fullrun"
  if [ -f "$case_dir/skill" ]; then
    cp "$SRC/skills/$(head -n 1 "$case_dir/skill")/SKILL.md" "$work/.claude/skill.md" || return 1
    while IFS= read -r sk; do
      [ -z "$sk" ] && continue
      mkdir -p "$work/.claude/skills/$sk" && cp -R "$SRC/skills/$sk/." "$work/.claude/skills/$sk/" || return 1
    done < "$case_dir/skill"
  fi
}

judge() {
  local name=$1 case_dir=$2 out=$3 work=${4:-} missing="" forbidden=""
  if [ -f "$case_dir/expect" ]; then
    while IFS= read -r re; do
      [ -z "$re" ] && continue
      grep -qE -- "$re" "$out" || missing="$missing [$re]"
    done < "$case_dir/expect"
  fi
  if [ -f "$case_dir/expect-not" ]; then
    while IFS= read -r re; do
      [ -z "$re" ] && continue
      grep -qE -- "$re" "$out" && forbidden="$forbidden [$re]"
    done < "$case_dir/expect-not"
  fi
  if [ -f "$case_dir/check.sh" ] && [ -n "$work" ]; then
    ( cd "$work" && AGENT_OUT="$out" bash "$case_dir/check.sh" ) >> "$out" 2>&1 || forbidden="$forbidden [check.sh: repository state after the run is wrong]"
  fi
  if [ -z "$missing$forbidden" ]; then
    pass=$((pass+1)); printf '  PASS  %s\n' "$name"
  else
    fail=$((fail+1)); printf '  FAIL  %s\n' "$name"
    [ -n "$missing" ] && printf '        not found:%s\n' "$missing"
    [ -n "$forbidden" ] && printf '        must not appear:%s\n' "$forbidden"
    printf '        report: %s\n' "$out"
  fi
}

run_case() {
  local name=$1 case_dir="$CASES/$1" work out agent tools
  [ -d "$case_dir" ] || { echo "no such case: $name" >&2; fail=$((fail+1)); return; }
  work=$(mktemp -d); out="$OUT/$name.out"
  build_repo "$case_dir" "$work" || { fail=$((fail+1)); printf '  FAIL  %s\n        fixture did not build\n' "$name"; return; }
  agent=$(head -n 1 "$case_dir/agent")
  tools=$(cat "$case_dir/allowed-tools" 2>/dev/null || echo "Read Grep Glob Bash(git diff:*) Bash(git log:*) Bash(git show:*)")
  local args=(-p --allowedTools "$tools" --output-format text --settings '{"disableAllHooks":true}')
  [ "$agent" != main ] && args+=(--agent "$agent")
  [ -f "$work/.claude/skill.md" ] && args+=(--append-system-prompt-file "$work/.claude/skill.md")
  ( cd "$work" && "$CLAUDE_BIN" "${args[@]}" "$(cat "$case_dir/prompt.txt")" < /dev/null ) > "$out" 2>&1
  judge "$name" "$case_dir" "$out" "$work"
  rm -rf "$work"
}

self_check() {
  local fake="$OUT/fake-claude" sc="$OUT/selfcase"
  mkdir -p "$sc/base"; echo reviewer > "$sc/agent"; echo "review" > "$sc/prompt.txt"
  echo 'x = 1' > "$sc/base/app.py"
  printf 'app\\.py:1\n' > "$sc/expect"; printf 'CONFIRMED.*decoy\\.py\n' > "$sc/expect-not"
  printf '#!/usr/bin/env bash\nprintf "%%s\\n" "$FAKE_REPORT"\n' > "$fake"; chmod +x "$fake"
  local saved_cases=$CASES saved_bin=$CLAUDE_BIN
  CASES=$OUT; CLAUDE_BIN=$fake
  mv "$sc" "$OUT/self-found"
  cp -R "$OUT/self-found" "$OUT/self-missed"
  cp -R "$OUT/self-found" "$OUT/self-decoy"
  export FAKE_REPORT
  FAKE_REPORT="CONFIRMED app.py:1 broken"; run_case self-found
  FAKE_REPORT="no findings"; run_case self-missed
  FAKE_REPORT="CONFIRMED app.py:1 and CONFIRMED decoy.py:3"; run_case self-decoy
  CASES=$saved_cases; CLAUDE_BIN=$saved_bin
}

case "${1:-}" in
  -h|--help) usage; exit 0 ;;
  --self-check)
    log="$OUT/self-check.log"
    self_check > "$log" 2>&1 || { cat "$log"; exit 1; }
    cat "$log"
    if grep -q 'PASS  self-found' "$log" && grep -q 'FAIL  self-missed' "$log" && grep -q 'FAIL  self-decoy' "$log"; then
      echo "agenttest self-check: ok"; exit 0
    fi
    echo "agenttest self-check: the judge does not separate found from missed" >&2; exit 1 ;;
esac

command -v "$CLAUDE_BIN" >/dev/null || { echo "claude CLI not found; agenttest runs real agents and costs tokens" >&2; exit 1; }
names=("$@")
if [ ${#names[@]} -eq 0 ]; then while IFS= read -r n; do names+=("$n"); done < <(ls "$CASES"); fi
echo "== agenttest (reports in $OUT)"
for n in "${names[@]}"; do run_case "$n"; done
echo
echo "passed $pass, failed $fail"
[ "$fail" -eq 0 ]
