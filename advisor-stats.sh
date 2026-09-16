#!/usr/bin/env bash
# advisor-stats.sh
set -uo pipefail

DIR=${1:-$HOME/.claude/projects}
DAYS=${CC_ADVISOR_DAYS:-7}
DIR=${DIR/#\~/$HOME}

[ -d "$DIR" ] || { echo "no transcript directory at $DIR" >&2; exit 1; }

mapfile -d '' FILES < <(find "$DIR" -name '*.jsonl' -mtime -"$DAYS" -print0 2>/dev/null)
if [ ${#FILES[@]} -eq 0 ]; then
  echo "no transcripts with model turns found (looked in $DIR, last $DAYS days)"
  exit 0
fi

python3 -c '
import json, sys, os, collections

sessions = collections.OrderedDict()
for path in sys.argv[1:]:
    calls, ctx_at_call, turns, last_ctx = 0, [], 0, 0
    try:
        fh = open(path, errors="ignore")
    except OSError:
        continue
    with fh:
        for line in fh:
            line = line.strip()
            if not line.startswith("{"):
                continue
            try:
                o = json.loads(line)
            except Exception:
                continue
            msg = o.get("message") or {}
            usage = msg.get("usage") or {}
            if usage:
                turns += 1
                last_ctx = (usage.get("input_tokens", 0)
                            + usage.get("cache_read_input_tokens", 0)
                            + usage.get("cache_creation_input_tokens", 0))
            content = msg.get("content")
            if isinstance(content, list):
                for block in content:
                    if not isinstance(block, dict):
                        continue
                    name = block.get("name")
                    btype = block.get("type")
                    if (btype == "server_tool_use" and name == "advisor") or btype == "advisor_tool_result":
                        if btype == "server_tool_use":
                            calls += 1
                            ctx_at_call.append(last_ctx)
    if turns:
        sessions[path] = (calls, turns, ctx_at_call)

if not sessions:
    print("no transcripts with model turns found")
    raise SystemExit(0)

total_calls = sum(c for c, _, _ in sessions.values())
total_turns = sum(t for _, t, _ in sessions.values())
all_ctx = [c for _, _, lst in sessions.values() for c in lst]
with_advisor = sum(1 for c, _, _ in sessions.values() if c)

print(f"sessions: {len(sessions)} ({with_advisor} used the advisor) | model turns: {total_turns} | advisor calls: {total_calls}")
if all_ctx:
    all_ctx.sort()
    forwarded = sum(all_ctx)
    print(f"context forwarded to the advisor: {forwarded/1000:.0f}k tokens total, "
          f"median {all_ctx[len(all_ctx)//2]/1000:.0f}k, max {all_ctx[-1]/1000:.0f}k per call")
    print("every call re-reads the whole conversation on the advisor model, and it bills to its own weekly window (/usage)")
else:
    print("no advisor calls recorded: either it never fired, or advisorModel is unset for these sessions")

rows = [(c, t, os.path.basename(p)) for p, (c, t, _) in sessions.items() if c]
for calls, turns, name in sorted(rows, reverse=True)[:10]:
    print(f"  {calls:3d} calls / {turns:4d} turns  {name}")
' "${FILES[@]}"
