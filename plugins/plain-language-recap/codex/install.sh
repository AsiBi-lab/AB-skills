#!/usr/bin/env bash
# Wire the recap Stop hook into Codex, pointing at this clone.
# Re-run it after `git pull` only if the repo moved — the hook path is what
# Codex stores, so pulling a new version needs no re-install.
set -euo pipefail

PLUGIN_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HOOK="$PLUGIN_ROOT/hooks/codex_stop_hook.py"
CONFIG="$HOME/.codex/hooks.json"

[ -f "$HOOK" ] || { echo "hook not found at $HOOK" >&2; exit 1; }
command -v python3 >/dev/null 2>&1 || { echo "python3 is required" >&2; exit 1; }

mkdir -p "$HOME/.codex"
[ -f "$CONFIG" ] || echo '{"hooks":{}}' > "$CONFIG"
cp "$CONFIG" "$CONFIG.bak.$(date +%Y%m%d%H%M%S)"

python3 - "$CONFIG" "$HOOK" <<'PY'
import json, sys
config_path, hook_path = sys.argv[1], sys.argv[2]
with open(config_path, encoding="utf-8") as handle:
    config = json.load(handle)

command = f"python3 '{hook_path}'"
hooks = config.setdefault("hooks", {})
stop = hooks.setdefault("Stop", [])

# Drop any previous install of this hook so re-running never duplicates it.
for group in stop:
    group["hooks"] = [h for h in group.get("hooks", [])
                      if "codex_stop_hook.py" not in str(h.get("command", ""))]
stop = [g for g in stop if g.get("hooks")]

stop.append({"matcher": "*", "hooks": [{"type": "command", "command": command}]})
hooks["Stop"] = stop

with open(config_path, "w", encoding="utf-8") as handle:
    json.dump(config, handle, ensure_ascii=False, indent=2)
    handle.write("\n")
print(f"installed Stop hook -> {hook_path}")
PY

echo "Done. A backup of your previous config sits next to it."
echo "To customise the rules without touching this repo, create ~/.codex/recap.config.json"
