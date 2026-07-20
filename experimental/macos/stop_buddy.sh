#!/bin/sh
# Dismiss MadoMochi. UNTESTED (written on Windows) — copy into scripts/ before use.
# SIGTERM skips tk's close handler, so stamp the deliberate-quit marker
# ourselves to keep the 30-minute revival snooze working.
here="$(cd "$(dirname "$0")/.." && pwd)"
mkdir -p "$HOME/.claude/buddy"
date +%s > "$HOME/.claude/buddy/quit.ts"
# IMPORTANT: match on OUR full path only — never a generic script name
if pkill -f "$here/scripts/buddy.py" 2>/dev/null; then
    echo "MadoMochi dismissed."
else
    echo "MadoMochi is not running."
fi
