#!/usr/bin/env bash
# Pick which language the recap rules are written for.
#
# It copies a bundled ruleset to your own config file, OUTSIDE this repo, so
# your choice (and any edits you make afterwards) survive every update.
set -euo pipefail

PLUGIN_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONFIGS="$PLUGIN_ROOT/configs"

usage() {
  echo "usage: $(basename "$0") <language> [claude|codex]"
  echo
  echo "available languages:"
  for f in "$CONFIGS"/*.json; do echo "  - $(basename "$f" .json)"; done
  echo
  echo "Writes the chosen ruleset to ~/.claude/recap.config.json (default) or"
  echo "~/.codex/recap.config.json. Edit that file afterwards to fine-tune;"
  echo "updates to this repo will never overwrite it."
}

[ $# -ge 1 ] || { usage; exit 1; }
case "$1" in -h|--help|help) usage; exit 0;; esac

LANGUAGE="$1"
TOOL="${2:-claude}"
SOURCE="$CONFIGS/$LANGUAGE.json"
TARGET_DIR="$HOME/.$TOOL"
TARGET="$TARGET_DIR/recap.config.json"

[ -f "$SOURCE" ] || { echo "no bundled ruleset called '$LANGUAGE'" >&2; usage; exit 1; }
case "$TOOL" in claude|codex) ;; *) echo "tool must be 'claude' or 'codex'" >&2; exit 1;; esac

mkdir -p "$TARGET_DIR"
[ -f "$TARGET" ] && cp "$TARGET" "$TARGET.bak.$(date +%Y%m%d%H%M%S)" && echo "backed up your previous config"
cp "$SOURCE" "$TARGET"
echo "$LANGUAGE rules active for $TOOL -> $TARGET"
echo "Edit that file to adjust headings, vocabulary, or thresholds."
