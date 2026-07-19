#!/usr/bin/env python3
"""
Claude Code hook entrypoint for MadoMochi.

Reads the hook JSON from stdin, maps the event to a buddy mood, and writes
~/.claude/buddy/status.json. On SessionStart it also launches the floating
buddy window if it is not running yet.

MUST always exit 0 and print nothing (fail-open: never block Claude Code).
"""

from __future__ import annotations

import ctypes
import json
import os
import subprocess
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

BUDDY_DIR = Path(os.environ.get("CLAUDE_BUDDY_DIR", Path.home() / ".claude" / "buddy"))
STATUS_PATH = Path(os.environ.get("CLAUDE_BUDDY_STATUS", BUDDY_DIR / "status.json"))
LOG_PATH = BUDDY_DIR / "hook.log"
SPAWN_GUARD = BUDDY_DIR / "spawn.ts"
QUIT_TS = BUDDY_DIR / "quit.ts"  # written by the buddy on a deliberate quit
QUIT_SNOOZE = 1800.0             # how long a deliberate quit blocks prompt-revival
BUDDY_TITLE = "MadoMochi"
FLOAT_SCRIPT = Path(__file__).resolve().parent / "buddy.py"

# notification kinds that deserve the WAITING pounce; everything else
# (auth_success, elicitation bookkeeping, ...) is noise for a mascot
ATTENTION_NOTIFICATIONS = {
    "permission_prompt",
    "idle_prompt",
    "agent_needs_input",
    "elicitation_dialog",
}


def notification_is_noise(event: str, data: dict) -> bool:
    """True for Notification payloads that shouldn't alert the buddy.

    An absent/unknown notification_type falls back to alerting — older
    Claude Code versions may not send the field at all.
    """
    if event not in ("Notification", "notification"):
        return False
    ntype = str(data.get("notification_type") or "")
    return bool(ntype) and ntype not in ATTENTION_NOTIFICATIONS


# the label is informational data (status.json / hook.log), not UI —
# kept English so logs read the same on every machine
EVENT_TO_MOOD = {
    "SessionStart": ("idle", "session start"),
    "UserPromptSubmit": ("listen", "prompt received"),
    "PreToolUse": ("work", "working"),
    "PostToolUse": ("work", "working"),
    "PostToolUseFailure": ("error", "tool failed"),
    "Stop": ("happy", "done"),
    "StopFailure": ("error", "turn failed"),
    "TaskCompleted": ("happy", "task completed"),
    "Notification": ("alert", "waiting for you"),
    "PreCompact": ("think", "compacting context"),
    "SessionEnd": ("sleep", "session end"),
}
# accept snake_case event spellings too
EVENT_TO_MOOD.update(
    {
        "session_start": EVENT_TO_MOOD["SessionStart"],
        "user_prompt_submit": EVENT_TO_MOOD["UserPromptSubmit"],
        "pre_tool_use": EVENT_TO_MOOD["PreToolUse"],
        "post_tool_use": EVENT_TO_MOOD["PostToolUse"],
        "post_tool_use_failure": EVENT_TO_MOOD["PostToolUseFailure"],
        "stop": EVENT_TO_MOOD["Stop"],
        "stop_failure": EVENT_TO_MOOD["StopFailure"],
        "task_completed": EVENT_TO_MOOD["TaskCompleted"],
        "notification": EVENT_TO_MOOD["Notification"],
        "pre_compact": EVENT_TO_MOOD["PreCompact"],
        "session_end": EVENT_TO_MOOD["SessionEnd"],
    }
)


def log(line: str) -> None:
    try:
        BUDDY_DIR.mkdir(parents=True, exist_ok=True)
        if LOG_PATH.is_file() and LOG_PATH.stat().st_size > 1_000_000:
            LOG_PATH.replace(LOG_PATH.with_suffix(".log.old"))
        with LOG_PATH.open("a", encoding="utf-8") as f:
            f.write(f"{datetime.now(timezone.utc).isoformat()} {line}\n")
    except Exception:
        pass


# Hooks run async, so a slow PostToolUse/SubagentStop can land AFTER Stop and
# flip DONE back to WORKING. Real new work always passes through
# UserPromptSubmit (listen) first, so a work-write arriving while a terminal
# mood is this fresh can only be a straggler from the finished turn.
GRACE_AFTER_TERMINAL = 3.0
TERMINAL_MOODS = ("happy", "alert", "sleep")


def is_stale_work_write(mood: str) -> bool:
    if mood != "work":
        return False
    try:
        cur = json.loads(STATUS_PATH.read_text(encoding="utf-8"))
        if cur.get("mood") not in TERMINAL_MOODS:
            return False
        ts = datetime.fromisoformat(cur["updatedAt"])
        age = (datetime.now(timezone.utc) - ts).total_seconds()
        return 0 <= age < GRACE_AFTER_TERMINAL
    except Exception:
        return False


# The app spawns short-lived helper sessions (title generation etc.) whose
# SessionStart/SessionEnd would stomp the real session's state ("fell asleep
# mid-turn"). While an active mood is fresh, those events are just noise.
ACTIVE_MOODS = ("listen", "think", "work", "alert")
SESSION_NOISE_WINDOW = 120.0


def is_session_noise(event: str) -> bool:
    if event not in ("SessionStart", "session_start", "SessionEnd", "session_end"):
        return False
    try:
        cur = json.loads(STATUS_PATH.read_text(encoding="utf-8"))
        if cur.get("mood") not in ACTIVE_MOODS:
            return False
        ts = datetime.fromisoformat(cur["updatedAt"])
        age = (datetime.now(timezone.utc) - ts).total_seconds()
        return 0 <= age < SESSION_NOISE_WINDOW
    except Exception:
        return False


def write_status(mood: str, message: str, tool: str = "", event: str = "") -> None:
    BUDDY_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "mood": mood,
        "message": message,
        "tool": tool or "",
        "event": event or "",
        "updatedAt": datetime.now(timezone.utc).isoformat(),
    }
    # async hooks run one process each: the temp file must be per-process,
    # and the whole write+swap retried (poller readers AND sibling hooks
    # can collide on Windows)
    tmp = STATUS_PATH.with_name(f"status.{os.getpid()}.tmp")
    try:
        for _ in range(4):
            try:
                tmp.write_text(
                    json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
                )
                tmp.replace(STATUS_PATH)
                return
            except (PermissionError, OSError):
                time.sleep(0.03)
    finally:
        try:
            if tmp.is_file():
                tmp.unlink()
        except OSError:
            pass


def buddy_running() -> bool:
    try:
        return bool(ctypes.windll.user32.FindWindowW(None, BUDDY_TITLE))
    except Exception:
        return False


def recently_quit() -> bool:
    """True while a deliberate quit should keep prompt-revival snoozed."""
    try:
        return time.time() - QUIT_TS.stat().st_mtime < QUIT_SNOOZE
    except Exception:
        return False


def launch_buddy() -> None:
    """Spawn the floating buddy, detached and windowless. Guarded against storms."""
    try:
        if buddy_running() or not FLOAT_SCRIPT.is_file():
            return
        now = time.time()
        try:
            if now - float(SPAWN_GUARD.read_text(encoding="utf-8").strip()) < 60:
                return
        except Exception:
            pass
        BUDDY_DIR.mkdir(parents=True, exist_ok=True)
        SPAWN_GUARD.write_text(str(now), encoding="utf-8")

        exe = Path(sys.executable)
        pyw = exe.with_name("pythonw.exe")
        py = str(pyw) if pyw.is_file() else str(exe)
        flags = (
            getattr(subprocess, "CREATE_NO_WINDOW", 0)
            | getattr(subprocess, "DETACHED_PROCESS", 0)
            | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        )
        subprocess.Popen(
            [py, str(FLOAT_SCRIPT)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            creationflags=flags,
            close_fds=True,
        )
        log("spawned buddy")
    except Exception:
        log("spawn_fail " + traceback.format_exc().replace("\n", " | "))


def main() -> int:
    try:
        raw = ""
        try:
            raw = sys.stdin.read()
        except Exception as e:
            log(f"stdin_err {e!r}")

        data: dict = {}
        if raw and raw.strip():
            try:
                data = json.loads(raw)
            except Exception as e:
                # log the shape only — raw hook input can carry session paths
                log(f"bad_json {e!r} len={len(raw)}")

        event = str(
            data.get("hook_event_name")
            or data.get("hookEventName")
            or os.environ.get("CLAUDE_HOOK_EVENT")
            or ""
        )
        tool = str(data.get("tool_name") or data.get("toolName") or "")

        mapped = EVENT_TO_MOOD.get(event)
        if mapped is None:
            log(f"skip event={event!r}")
            return 0

        if notification_is_noise(event, data):
            log(f"skip notification type={data.get('notification_type')!r}")
            return 0

        mood, msg = mapped
        if tool and mood == "work":
            msg = f"WORKING · {tool}"
        if is_stale_work_write(mood):
            log(f"drop straggler event={event!r} (terminal mood is fresh)")
        elif is_session_noise(event):
            log(f"drop session noise event={event!r} (active mood is fresh)")
        else:
            write_status(mood, msg, tool=tool, event=event)
            log(f"ok event={event!r} mood={mood} tool={tool!r}")

        if event in ("SessionStart", "session_start"):
            try:
                QUIT_TS.unlink()  # a fresh session un-snoozes revival
            except Exception:
                pass
            launch_buddy()
        elif event in ("UserPromptSubmit", "user_prompt_submit") and not recently_quit():
            # chatting revives a crashed/closed buddy — unless freshly quit
            launch_buddy()
    except Exception:
        log("fatal " + traceback.format_exc().replace("\n", " | "))

    return 0  # ALWAYS 0, print nothing (empty output = do not interfere)


if __name__ == "__main__":
    raise SystemExit(main())
