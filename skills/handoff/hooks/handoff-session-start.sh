#!/usr/bin/env bash
# handoff skill — SessionStart detector.
# If the current project has an OPEN handoff, surface a one-line notice
# suggesting `/handoff resume`. Read-only, fast, silent when nothing is open.
# Runs globally for every project; must no-op cleanly when irrelevant.

DIR="${CLAUDE_PROJECT_DIR:-$PWD}"
HANDOFF="$DIR/.handoff/HANDOFF.md"

# No handoff file → nothing to do.
[ -f "$HANDOFF" ] || exit 0

# Only surface handoffs still awaiting resume.
grep -qiE '^status:[[:space:]]*OPEN' "$HANDOFF" 2>/dev/null || exit 0

written=$(grep -iE '^written:' "$HANDOFF" 2>/dev/null | head -1 | sed -E 's/^[Ww]ritten:[[:space:]]*//')
goal=$(grep -iE '^session_goal:' "$HANDOFF" 2>/dev/null | head -1 | sed -E 's/^[^:]*:[[:space:]]*//; s/^"//; s/"$//')

notice="[handoff] יש handoff פתוח בפרויקט הזה"
[ -n "$written" ] && notice="$notice (נכתב $written)"
[ -n "$goal" ] && notice="$notice — \"$goal\""
notice="$notice. הרץ /handoff resume כדי להמשיך, או התעלם והתחל חדש."

# Emit as SessionStart additionalContext. Build the JSON in pure bash: raw UTF-8
# (Hebrew) is valid inside a JSON string, so only \ and " need escaping. This
# avoids any locale/encoding dependency on python at hook runtime.
esc=$(printf '%s' "$notice" | sed -e 's/\\/\\\\/g' -e 's/"/\\"/g')
printf '{"hookSpecificOutput":{"hookEventName":"SessionStart","additionalContext":"%s"}}\n' "$esc"

exit 0
