#!/usr/bin/env bash
# advisor-check.sh
set -uo pipefail

CONFIG=${CLAUDE_CONFIG_DIR:-$HOME/.claude}
LOG=""
[ "${1:-}" = "--log" ] && LOG=${2:-}

say() { printf '%s\n' "$1"; }

settings="$CONFIG/settings.json"
if [ -f "$settings" ] && command -v jq >/dev/null 2>&1; then
  model=$(jq -r '.advisorModel // ""' "$settings")
  flag=$(jq -r '.env.CLAUDE_CODE_ENABLE_EXPERIMENTAL_ADVISOR_TOOL // ""' "$settings")
  off=$(jq -r '.env.CLAUDE_CODE_DISABLE_ADVISOR_TOOL // ""' "$settings")
  say "settings: advisorModel=${model:-unset}, ENABLE_EXPERIMENTAL=${flag:-unset}, DISABLE=${off:-unset}"
  [ -z "$model" ] && say "  → advisorModel is unset: nothing to enable. Add it (\"opus\") and reinstall."
  [ -n "$model" ] && [ -z "$flag" ] && say "  → the flag is missing. Without it the tool depends on a server-side flag that GrowthBook delivers, and GrowthBook does not run with telemetry opted out."
fi

for var in CLAUDE_CODE_DISABLE_ADVISOR_TOOL CLAUDE_CODE_DISABLE_EXPERIMENTAL_BETAS; do
  [ -n "${!var:-}" ] && say "shell env: $var=${!var} — this alone switches the advisor off"
done

if [ -z "$LOG" ]; then
  command -v claude >/dev/null 2>&1 || { say "claude is not in PATH; rerun with --log <debug log>"; exit 1; }
  LOG=$(mktemp)
  say "probing with one 'ping' request…"
  claude --debug --debug-file "$LOG" -p "ping" >/dev/null 2>&1
fi

[ -f "$LOG" ] || { say "no debug log at $LOG"; exit 1; }

enabled=$(grep -oE '\[AdvisorTool\] Server-side tool enabled with [^ ]+' "$LOG" | tail -n 1)
skipped=$(grep -oE '\[AdvisorTool\] Skipping advisor - .*' "$LOG" | tail -n 1)

if [ -n "$enabled" ]; then
  say "ENABLED — ${enabled#*enabled with }"
  exit 0
fi

if [ -n "$skipped" ]; then
  say "DISABLED — ${skipped#*Skipping advisor - }"
  say "  The line above is the whole reason: an unranked base model, an advisor weaker than it, or a bad name."
  exit 1
fi

say "DISABLED — the gate closed before anything was logged. In order:"
say "  1. CLAUDE_CODE_DISABLE_ADVISOR_TOOL set anywhere (shell, user or project settings)"
say "  2. the provider is not first-party (a gateway, Bedrock, Vertex — a subscription IS first-party)"
say "  3. CLAUDE_CODE_DISABLE_EXPERIMENTAL_BETAS, or an organisation in HIPAA mode"
say "  4. neither CLAUDE_CODE_ENABLE_EXPERIMENTAL_ADVISOR_TOOL=1 nor the server-side flag — and that flag"
say "     needs GrowthBook, which does not run when telemetry is opted out (grep the log for 'GrowthBook is off')"
grep -m1 'GrowthBook is off' "$LOG" && say "  ↑ found in this log: the server-side flag cannot arrive, so the variable is the only way"
exit 1
