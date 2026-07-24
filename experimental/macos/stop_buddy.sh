#!/bin/sh
# Dismiss MadoMochi. Installed into scripts/ by experimental/macos/apply.py.
# The macOS patch routes SIGTERM through the normal close handler. Pre-stamp
# the deliberate-quit marker as insurance if that handler cannot finish.
umask 077
here="$(cd "$(dirname "$0")/.." && pwd)"
target="$here/scripts/buddy.py"
# pgrep interprets its pattern as a regular expression. Escape the checkout
# path first so punctuation in a folder name cannot broaden the match.
pattern="$(python3 -c 'import re, sys; print(r"(^|[[:space:]])" + re.escape(sys.argv[1]) + r"([[:space:]]|$)")' "$target")" ||
    exit 1

# First select processes whose arguments contain this exact buddy.py path,
# then retain only CPython executables. Merely viewing the file in vim, less,
# or another editor must never make that process eligible for termination.
buddy_pids() {
    candidates="$(pgrep -f "$pattern" 2>/dev/null)"
    status=$?
    if [ "$status" -gt 1 ]; then
        return "$status"
    fi
    for pid in $candidates; do
        case "$pid" in
            *[!0-9]*|"") continue ;;
        esac
        if ! process_name="$(ps -p "$pid" -o ucomm= 2>/dev/null)"; then
            # A candidate may disappear naturally between pgrep and ps.
            # If it still exists but cannot be inspected, fail closed.
            if kill -0 "$pid" 2>/dev/null; then
                return 1
            fi
            continue
        fi
        exe="${process_name##*/}"
        exe="${exe#"${exe%%[![:space:]]*}"}"
        exe="${exe%"${exe##*[![:space:]]}"}"
        if printf '%s\n' "$exe" |
            grep -Eiq '^python(w)?([0-9]+([.][0-9]+)*t?)?$'; then
            printf '%s\n' "$pid"
        fi
    done
}

if ! pids="$(buddy_pids)"; then
    echo "MadoMochi process inspection failed; nothing was stopped." >&2
    exit 1
fi

if [ -n "$pids" ]; then
    mkdir -p "$HOME/.claude/madomochi"
    date +%s > "$HOME/.claude/madomochi/quit.ts"
    failed=0
    for pid in $pids; do
        if ! kill "$pid" 2>/dev/null && kill -0 "$pid" 2>/dev/null; then
            failed=1
        fi
    done
    if [ "$failed" -ne 0 ]; then
        echo "MadoMochi could not be stopped." >&2
        exit 1
    fi
    tries=0
    while [ "$tries" -lt 10 ]; do
        if ! pids="$(buddy_pids)"; then
            echo "MadoMochi process inspection failed." >&2
            exit 1
        fi
        [ -z "$pids" ] && break
        sleep 0.2
        tries=$((tries + 1))
    done
    if ! pids="$(buddy_pids)"; then
        echo "MadoMochi process inspection failed." >&2
        exit 1
    fi
    if [ -n "$pids" ]; then
        echo "MadoMochi is still running." >&2
        exit 1
    fi
    echo "MadoMochi dismissed."
else
    echo "MadoMochi is not running."
fi
