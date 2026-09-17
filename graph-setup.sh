#!/usr/bin/env bash
# graph-setup.sh
set -euo pipefail

MIN_NODES=${CC_GRAPH_MIN_NODES:-20}
MAX_INFERRED=${CC_GRAPH_MAX_INFERRED:-25}
MIN_COVERAGE=${CC_GRAPH_MIN_COVERAGE:-30}
SERVER=${CC_GRAPH_SERVER:-graphify}
OUT=${GRAPHIFY_OUT:-graphify-out}

stats() {
  python3 - "$1" "${2:-0}" "$MIN_NODES" "$MAX_INFERRED" "$MIN_COVERAGE" <<'PY'
import json, sys

path, code_files, min_nodes, max_inferred, min_coverage = sys.argv[1:6]
code_files, min_nodes = int(code_files), int(min_nodes)
max_inferred, min_coverage = float(max_inferred), float(min_coverage)

try:
    with open(path, encoding="utf-8") as fh:
        graph = json.load(fh)
except (OSError, ValueError) as exc:
    print(f"unreadable graph: {exc}")
    sys.exit(2)

nodes = graph.get("nodes") or []
links = graph.get("links") or graph.get("edges") or []
inferred = sum(1 for l in links if str(l.get("confidence", "")).upper() == "INFERRED")
files = {n.get("source_file") for n in nodes if n.get("source_file")}
share = 100.0 * inferred / len(links) if links else 0.0
coverage = 100.0 * len(files) / code_files if code_files else None

print(f"nodes: {len(nodes)}")
print(f"edges: {len(links)} ({inferred} INFERRED, {share:.1f}%)")
print(f"files in graph: {len(files)}" + (f" of {code_files} code files ({coverage:.0f}%)" if coverage is not None else ""))

verdict = []
if len(nodes) < min_nodes:
    verdict.append(f"only {len(nodes)} nodes (< {min_nodes}): nothing here a grep cannot answer")
if share > max_inferred:
    verdict.append(f"{share:.1f}% of edges are INFERRED guesses (> {max_inferred:.0f}%)")
if coverage is not None and coverage < min_coverage:
    verdict.append(f"the graph covers {coverage:.0f}% of code files (< {min_coverage:.0f}%): the parser does not read this language")
if verdict:
    print("UNFIT:")
    for line in verdict:
        print(f"  - {line}")
    sys.exit(2)
print("FIT")
PY
}

if [ "${1:-}" = "--stats" ]; then
  [ -n "${2:-}" ] || { echo "usage: graph-setup.sh --stats <graph.json> [code-file-count]" >&2; exit 64; }
  stats "$2" "${3:-0}"
  exit $?
fi

PROJECT=${1:-$(pwd)}
cd "$PROJECT"

git rev-parse --show-toplevel >/dev/null 2>&1 || { echo "not a git repository: $PROJECT" >&2; exit 1; }

if [ -f .gitmodules ]; then
  echo "refusing: this repository has submodules." >&2
  echo "A graph built over an umbrella repository resolves almost every cross-repository edge wrongly." >&2
  echo "Run this inside one component repository instead." >&2
  exit 2
fi

command -v graphify >/dev/null 2>&1 || { echo "graphify is not on PATH: pip install graphifyy" >&2; exit 1; }
command -v graphify-mcp >/dev/null 2>&1 || { echo "graphify-mcp is not on PATH: pip install graphifyy" >&2; exit 1; }
command -v jq >/dev/null 2>&1 || { echo "jq is required" >&2; exit 1; }

echo "== extract (local AST, no API key, no model tokens)"
log=$(mktemp)
trap 'rm -f "$log"' EXIT
set +e
graphify extract . --code-only 2>&1 | tee "$log"
rc=${PIPESTATUS[0]}
set -e
if [ "$rc" -ne 0 ]; then
  echo >&2
  echo "refusing: extraction failed or produced no nodes (its own message is above)." >&2
  echo "Usually the parser does not read this repository's languages." >&2
  echo "Nothing was wired. Leftovers, if any, are in $OUT/ — delete them yourself." >&2
  exit 2
fi
code_files=$(awk '
  /found [0-9]+ code,/            { match($0, /found [0-9]+ code/); n = substr($0, RSTART + 6, RLENGTH - 11) + 0 }
  /code, .* changed; [0-9]+ unch/ { c = $0; sub(/ code,.*/, "", c); sub(/.*\] /, "", c)
                                    u = $0; sub(/ unchanged.*/, "", u); sub(/.*; /, "", u)
                                    n = c + u }
  END { print n + 0 }' "$log")
code_files=${code_files:-0}

echo "== is this graph worth a tool?"
if ! stats "$OUT/graph.json" "$code_files"; then
  echo
  echo "Not wiring the MCP server. A graph this thin answers confidently and wrongly," >&2
  echo "which is worse than no graph. Remove it with: rm -rf $OUT" >&2
  exit 2
fi

echo "== .mcp.json"
tmp=$(mktemp)
if [ -f .mcp.json ] && jq -e . .mcp.json >/dev/null 2>&1; then
  jq --arg s "$SERVER" --arg g "$OUT/graph.json" \
    '.mcpServers = ((.mcpServers // {}) + {($s): {command: "graphify-mcp", args: [$g]}})' .mcp.json > "$tmp"
else
  [ -e .mcp.json ] && { echo "refusing: .mcp.json exists and is not valid JSON" >&2; exit 1; }
  jq -n --arg s "$SERVER" --arg g "$OUT/graph.json" \
    '{mcpServers: {($s): {command: "graphify-mcp", args: [$g]}}}' > "$tmp"
fi
mv "$tmp" .mcp.json
echo "   server \"$SERVER\" -> graphify-mcp $OUT/graph.json"

echo "== .gitignore"
if [ ! -f .gitignore ] || ! grep -qxF "$OUT/" .gitignore; then
  printf '%s/\n' "$OUT" >> .gitignore
  echo "   added $OUT/"
else
  echo "   $OUT/ already ignored"
fi

echo "== rebuild on commit"
graphify hook install
echo "   note: the rebuild runs detached; the graph trails a commit by a few seconds."
echo "   note: 'hook install' also wrote .gitattributes and a merge driver for a tracked graph.json."
echo "   Since $OUT/ is ignored here, both are inert — delete .gitattributes if you object."

cat <<EOF

Done. The tools do not exist in this session: MCP servers are started at session start.
  1. restart claude
  2. ask scout to resolve a symbol you already know
  3. compare its path:line against grep before you trust the next answer
EOF
