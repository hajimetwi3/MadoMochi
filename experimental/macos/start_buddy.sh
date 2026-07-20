#!/bin/sh
# Launch MadoMochi in the background (single instance is enforced in-app).
# UNTESTED (written on Windows) — copy into scripts/ next to buddy.py before use.
here="$(cd "$(dirname "$0")/.." && pwd)"
# a manual start is explicit consent: lift any quit-snooze on auto-revival
rm -f "$HOME/.claude/buddy/quit.ts"
nohup python3 "$here/scripts/buddy.py" >/dev/null 2>&1 &
echo "MadoMochi launched (duplicate instances exit by themselves)."
