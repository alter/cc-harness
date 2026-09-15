#!/usr/bin/env bash
# uninstall.sh
set -euo pipefail

BACKUP=${1:?usage: uninstall.sh <backup-dir> [target-dir]}
TARGET=${2:-$HOME/.claude}
TARGET=${TARGET/#\~/$HOME}
SRC=$(cd "$(dirname "$0")" && pwd)
BIN_DIR=${CC_BIN_DIR:-$HOME/bin}
ITEMS=(settings.json settings.local.json CLAUDE.md statusline.sh hooks agents skills commands project-template keybindings.json)

[ -f "$BACKUP/MANIFEST.txt" ] || { echo "not a harness backup: $BACKUP" >&2; exit 1; }

echo "== remove harness files from $TARGET"
rm -f "$TARGET/CLAUDE.md" "$TARGET/statusline.sh"
for f in "$SRC"/hooks/*.sh; do rm -f "$TARGET/hooks/$(basename "$f")"; done
for f in "$SRC"/agents/*.md; do rm -f "$TARGET/agents/$(basename "$f")"; done
for s in "$SRC"/skills/*/; do rm -rf "$TARGET/skills/$(basename "$s")"; done
rm -rf "$TARGET/project-template"
rm -f "$TARGET/settings.json"
rm -f "$BIN_DIR/cc-night"

echo "== restore from $BACKUP"
for item in "${ITEMS[@]}"; do
  if [ -e "$BACKUP/$item" ]; then
    rm -rf "$TARGET/$item"
    cp -R "$BACKUP/$item" "$TARGET/$item"
    echo "   restored $item"
  fi
done
[ -f "$BACKUP/cc-night" ] && cp "$BACKUP/cc-night" "$BIN_DIR/cc-night" && echo "   restored cc-night"

for d in hooks agents skills; do
  [ -d "$TARGET/$d" ] && [ -z "$(ls -A "$TARGET/$d")" ] && rmdir "$TARGET/$d"
done

echo "== verify against manifest"
missing=0
while IFS= read -r rel; do
  [ -z "$rel" ] && continue
  case "$rel" in
    ./settings.json|./settings.local.json|./CLAUDE.md|./statusline.sh|./hooks/*|./agents/*|./skills/*|./commands/*|./project-template/*|./keybindings.json)
      [ -e "$TARGET/$rel" ] || { echo "   missing after restore: $rel"; missing=1; } ;;
  esac
done < "$BACKUP/MANIFEST.txt"
[ "$missing" -eq 0 ] && echo "   all config files from the manifest are back"

echo "Done. $HOME/.claude.json was not touched (copy kept at $BACKUP/dot-claude.json if you need it)."
