#!/bin/sh
# Launch MadoMochi in the background (single instance is enforced in-app).
# Installed into scripts/ by experimental/macos/apply.py.
here="$(cd "$(dirname "$0")/.." && pwd)"
# a manual start is explicit consent: lift any quit-snooze on auto-revival
rm -f "$HOME/.claude/madomochi/quit.ts"
nohup python3 "$here/scripts/buddy.py" >/dev/null 2>&1 &
echo "MadoMochi launched (duplicate instances exit by themselves)."
