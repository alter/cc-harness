#!/usr/bin/env bash
# install.sh
set -euo pipefail

SRC=$(cd "$(dirname "$0")" && pwd)
TARGET=${1:-$HOME/.claude}
TARGET=${TARGET/#\~/$HOME}
BIN_DIR=${CC_BIN_DIR:-$HOME/bin}
STAMP=$(date +%Y%m%d-%H%M%S)
BACKUP=${CC_BACKUP_DIR:-$HOME/.claude-backup/$STAMP}
ITEMS=(settings.json settings.local.json CLAUDE.md statusline.sh hooks agents skills commands project-template keybindings.json)

command -v jq >/dev/null 2>&1 || { echo "jq is required (brew install jq / apt install jq)" >&2; exit 1; }
command -v claude >/dev/null 2>&1 || echo "warning: claude not in PATH; installing anyway" >&2

echo "== backup -> $BACKUP"
mkdir -p "$BACKUP"
if [ -d "$TARGET" ]; then
  for item in "${ITEMS[@]}"; do
    [ -e "$TARGET/$item" ] && cp -R "$TARGET/$item" "$BACKUP/$item"
  done
  ( cd "$TARGET" && find . -maxdepth 3 -type f \
      -not -path './projects/*' -not -path './todos/*' -not -path './shell-snapshots/*' \
      -not -path './statsig/*' -not -path './debug/*' -not -path './cache/*' \
      | sort ) > "$BACKUP/MANIFEST.txt"
else
  : > "$BACKUP/MANIFEST.txt"
fi
[ -f "$HOME/.claude.json" ] && cp "$HOME/.claude.json" "$BACKUP/dot-claude.json"
[ -f "$BIN_DIR/cc-night" ] && cp "$BIN_DIR/cc-night" "$BACKUP/cc-night"
printf 'source=%s\ntarget=%s\nbin=%s\ndate=%s\n' "$SRC" "$TARGET" "$BIN_DIR" "$STAMP" > "$BACKUP/INFO.txt"
echo "   $(wc -l < "$BACKUP/MANIFEST.txt" | tr -d ' ') files listed, config copied"

echo "== install -> $TARGET"
mkdir -p "$TARGET"/{hooks,agents,skills} "$BIN_DIR"
cp "$SRC/CLAUDE.md" "$TARGET/CLAUDE.md"
cp "$SRC/statusline.sh" "$TARGET/statusline.sh"
cp "$SRC"/hooks/* "$TARGET/hooks/"
cp "$SRC"/agents/*.md "$TARGET/agents/"
for s in "$SRC"/skills/*/; do
  name=$(basename "$s"); mkdir -p "$TARGET/skills/$name"; cp "$s"/* "$TARGET/skills/$name/"
done
rm -rf "$TARGET/project-template"; cp -R "$SRC/project-template" "$TARGET/project-template"
cp "$SRC/night.sh" "$BIN_DIR/cc-night"
chmod +x "$TARGET/statusline.sh" "$TARGET"/hooks/* "$BIN_DIR/cc-night"

if [ "$TARGET" != "$HOME/.claude" ]; then
  echo "== rewrite ~/.claude -> $TARGET in installed copies"
  grep -rlE '~/\.claude|\$HOME/\.claude' "$TARGET/hooks" "$TARGET/agents" "$TARGET/skills" "$TARGET/statusline.sh" 2>/dev/null \
    | xargs -r sed -i.bak -e "s#~/\.claude#$TARGET#g" -e "s#\$HOME/\.claude#$TARGET#g"
  find "$TARGET" -name '*.bak' -delete
fi

echo "== settings.json: merge"
NEW=$(mktemp)
if [ "$TARGET" = "$HOME/.claude" ]; then cp "$SRC/settings.json" "$NEW"; else sed -e "s#~/\.claude#$TARGET#g" "$SRC/settings.json" > "$NEW"; fi
if [ -f "$TARGET/settings.json" ] && jq -e . "$TARGET/settings.json" >/dev/null 2>&1; then
  MERGED=$(mktemp)
  OURS=$(cd "$SRC/hooks" && ls | sed 's/\./\\./g' | tr '\n' '|' | sed 's/|$//')
  jq -s --arg t "$TARGET/hooks/" --arg ours "$OURS" '
    .[0] as $old | .[1] as $new
    # An entry is ours if its command names one of this harness'"'"'s hook scripts, whether the
    # path was stored absolute ("/home/x/.claude/hooks/stop-guard.sh") or with a tilde
    # ("~/.claude/hooks/stop-guard.sh"). Matching only the absolute form let a second install
    # append a duplicate set, so every Bash call ran retry-guard twice.
    | ("hooks/(" + $ours + ")$") as $re
    | (($old.hooks // {}) | with_entries(.value |= map(select(((.hooks // []) | any((.command | tostring) | test($re) or contains($t))) | not)))
                          | with_entries(select(.value | length > 0))) as $kept
    | ($old * $new)
    | .env = (($old.env // {}) + ($new.env // {}))
    | .hooks = (reduce (($new.hooks // {}) | keys[]) as $k ($kept; .[$k] = ((.[$k] // []) + $new.hooks[$k])))
  ' "$TARGET/settings.json" "$NEW" > "$MERGED"
  echo "   diff (old -> merged):"
  diff <(jq -S . "$TARGET/settings.json") <(jq -S . "$MERGED") | sed 's/^/   /' || true
  mv "$MERGED" "$TARGET/settings.json"
else
  cp "$NEW" "$TARGET/settings.json"
  echo "   no previous settings.json; installed as is"
fi
rm -f "$NEW"
jq -e . "$TARGET/settings.json" >/dev/null || { echo "settings.json is not valid JSON" >&2; exit 1; }

echo "== check"
for f in "$TARGET"/hooks/*.sh "$TARGET/statusline.sh"; do bash -n "$f"; done
for f in "$TARGET"/hooks/*.py; do [ -e "$f" ] || continue; python3 -c "import ast,sys,pathlib; ast.parse(pathlib.Path(sys.argv[1]).read_text())" "$f"; done
for f in "$TARGET"/agents/*.md "$TARGET"/skills/*/SKILL.md; do
  head -n 1 "$f" | grep -q '^---$' || { echo "bad frontmatter: $f" >&2; exit 1; }
  grep -qE '^name: ' "$f" || { echo "no name: $f" >&2; exit 1; }
done
echo "   hooks: $(ls "$TARGET"/hooks/ | wc -l | tr -d ' '), agents: $(ls "$TARGET"/agents/*.md | wc -l | tr -d ' '), skills: $(ls -d "$TARGET"/skills/*/ | wc -l | tr -d ' ')"
command -v claude >/dev/null 2>&1 && echo "   claude $(claude --version 2>/dev/null | head -n 1)"

cat <<EOF

Done.
  backup:   $BACKUP
  rollback: $SRC/uninstall.sh $BACKUP $TARGET
  selftest: $SRC/selftest.sh $TARGET
  advisor:  $SRC/advisor-check.sh        (one 'ping' request; says ENABLED or why not)
EOF
if [ "$TARGET" != "$HOME/.claude" ]; then
  cat <<EOF
  try it:   CLAUDE_CONFIG_DIR=$TARGET claude
            (fresh config dir: theme/login prompts once; on Linux copy $HOME/.claude/.credentials.json into it to skip login)
EOF
fi
