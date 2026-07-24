#!/usr/bin/env python3
"""
Claude Code hook entrypoint for MadoMochi.

Reads the hook JSON from stdin, maps the event to a buddy mood, records it per
Claude session, and writes the provider-wide aggregate to
~/.claude/madomochi/status.json. On SessionStart it also launches the floating
buddy window if it is not running yet. Handled paths return 0 without stdout,
so this hook reports no permission decision.
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

from session_state import (
    RecordResult,
    SessionStore,
    chmod_private,
    ensure_private_dir,
)

BUDDY_DIR = Path(os.environ.get("CLAUDE_BUDDY_DIR", Path.home() / ".claude" / "madomochi"))
STATUS_PATH = Path(os.environ.get("CLAUDE_BUDDY_STATUS", BUDDY_DIR / "status.json"))
STATE_DB_PATH = Path(
    os.environ.get("MADOMOCHI_STATE_DB", BUDDY_DIR / "sessions.sqlite3")
)
LOG_PATH = BUDDY_DIR / "hook.log"
SPAWN_GUARD = BUDDY_DIR / "spawn.ts"
QUIT_TS = BUDDY_DIR / "quit.ts"  # written by the buddy on a deliberate quit
QUIT_SNOOZE = 1800.0             # how long a deliberate quit blocks prompt-revival
BUDDY_TITLE = "MadoMochi"
FLOAT_SCRIPT = Path(__file__).resolve().parent / "buddy.py"
SESSION_STORE = SessionStore(STATE_DB_PATH, provider="claude")
PERSISTED_FIELD_LIMIT = 160
LOG_LINE_LIMIT = 2_048
LOG_MAX_BYTES = 1_000_000
HOOK_INPUT_MAX_BYTES = 4 * 1024 * 1024
HOOK_INPUT_DRAIN_BYTES = 64 * 1024


def _bounded_field(value, limit: int = PERSISTED_FIELD_LIMIT) -> str:
    """Return a short printable field suitable for state files and logs."""
    text = str(value or "")
    marker = "<truncated>"
    if len(text) <= limit:
        return text
    return text[: max(0, limit - len(marker))] + marker


def _read_hook_input(
    stream=None, limit: int = HOOK_INPUT_MAX_BYTES
) -> tuple[str, bool]:
    """Read one UTF-8 hook payload without retaining more than *limit* bytes.

    The excess is drained in small chunks so the parent process can finish
    writing its pipe cleanly. Oversized payloads are discarded as a whole:
    partially parsed JSON must never be attributed to the anonymous session.
    """
    source = sys.stdin if stream is None else stream
    source = getattr(source, "buffer", source)
    chunk = source.read(limit + 1)
    is_bytes = isinstance(chunk, bytes)
    measured = len(chunk) if is_bytes else len(chunk.encode("utf-8"))
    oversized = measured > limit
    if oversized:
        empty = b"" if is_bytes else ""
        while source.read(HOOK_INPUT_DRAIN_BYTES) != empty:
            pass
        return "", True
    if is_bytes:
        return chunk.decode("utf-8"), False
    return chunk, False


def _notification_type(data: dict) -> str:
    return _bounded_field(data.get("notification_type"))

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
    ntype = _notification_type(data)
    return bool(ntype) and ntype not in ATTENTION_NOTIFICATIONS


def stop_has_pending_background(event: str, data: dict) -> bool:
    """True when a Stop ends only the foreground reply, not all work.

    Claude Code 2.1.145+ includes the currently in-flight task registry in
    Stop payloads.  We deliberately inspect only whether the JSON array is
    non-empty: task descriptions and command strings can contain private
    user data and must never be persisted or logged.
    """
    tasks = data.get("background_tasks")
    return event in ("Stop", "stop") and isinstance(tasks, list) and bool(tasks)


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
    # permission prompts get their own event: the Notification hook is
    # known not to fire for them (claude-code issue #56936)
    "PermissionRequest": ("alert", "waiting for approval"),
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
        "permission_request": EVENT_TO_MOOD["PermissionRequest"],
        "pre_compact": EVENT_TO_MOOD["PreCompact"],
        "session_end": EVENT_TO_MOOD["SessionEnd"],
    }
)


# payload field names from the official hook schema - the only strings
# the default skip log will ever echo back
_KNOWN_FIELDS = {
    "session_id", "prompt_id", "transcript_path", "cwd", "permission_mode",
    "hook_event_name", "hookEventName", "notification_type", "message",
    "title", "tool_name", "toolName", "tool_input", "tool_response",
    "effort", "matcher", "source", "reason",
}


def _skip_line(event: str, raw: str, data: dict) -> str:
    """Shape-only description of an unrecognized payload.

    Default: nothing from the payload is echoed except field names that
    appear in the official schema; everything else is reduced to
    lengths/counts. MADOMOCHI_HOOK_DEBUG=1 (local diagnosis only) shows
    identifier-shaped names instead.
    """
    if os.environ.get("MADOMOCHI_HOOK_DEBUG", "") == "1":
        shown = event if (event.isidentifier() and len(event) <= 40) \
            else f"<len {len(event)}>"
        keys = [
            k if (isinstance(k, str) and k.isidentifier() and len(k) <= 40)
            else "<odd>"
            for k in sorted(data)[:12]
        ]
    else:
        shown = f"<unknown len={len(event)}>" if event else "<none>"
        keys = sorted(k for k in data if isinstance(k, str) and k in _KNOWN_FIELDS)
        unknown = len(data) - len(keys)
        if unknown > 0:
            keys.append(f"<+{unknown} unknown>")
    return f"skip event={shown!r} len={len(raw)} fields={keys}"


def resolve_event(data: dict, argv: list) -> str:
    """Event name from the payload, else from the wiring's own args.

    Claude Code documents hook_event_name on every payload, but async
    hooks are known to occasionally receive empty stdin (claude-code
    issue #38162). The installer plants each event's name as a literal
    argument in settings.json, so those invocations still identify
    themselves instead of being dropped.
    """
    event = str(data.get("hook_event_name") or data.get("hookEventName") or "")
    if event:
        return event
    for a in argv[1:]:
        if a in EVENT_TO_MOOD:
            return str(a)
    return ""


def log(line: str) -> None:
    try:
        ensure_private_dir(BUDDY_DIR)
        line = _bounded_field(line, LOG_LINE_LIMIT)
        entry = f"{datetime.now(timezone.utc).isoformat()} {line}\n"
        projected = len(entry.encode("utf-8"))
        if (
            LOG_PATH.is_file()
            and LOG_PATH.stat().st_size + projected > LOG_MAX_BYTES
        ):
            old_log = LOG_PATH.with_suffix(".log.old")
            LOG_PATH.replace(old_log)
            chmod_private(old_log)
        with LOG_PATH.open("a", encoding="utf-8") as f:
            f.write(entry)
        chmod_private(LOG_PATH)
    except Exception:
        pass


def _write_status_payload(payload: dict) -> None:
    """Atomically publish a pre-built aggregate for the companion poller."""
    ensure_private_dir(BUDDY_DIR)
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
                chmod_private(tmp)
                tmp.replace(STATUS_PATH)
                chmod_private(STATUS_PATH)
                return
            except (PermissionError, OSError):
                time.sleep(0.03)
    finally:
        try:
            if tmp.is_file():
                tmp.unlink()
        except OSError:
            pass


def write_status(
    mood: str,
    message: str,
    tool: str = "",
    event: str = "",
    session_id: str = "",
) -> RecordResult | None:
    """Record one session event and publish Claude's aggregate state.

    SQLite is disposable runtime state. If it is unavailable or damaged, the
    hook falls back to a single-status write so the companion can still react
    without making a hook decision.
    """
    try:
        return SESSION_STORE.record_event(
            session_id=session_id,
            mood=mood,
            message=message,
            tool=tool or "",
            event=event or "",
            status_writer=_write_status_payload,
        )
    except Exception as exc:
        fallback = {
            "mood": mood,
            "message": message,
            "tool": tool or "",
            "event": event or "",
            "updatedAt": datetime.now(timezone.utc).isoformat(),
            "provider": "claude",
            "session": "",
            "sessionCount": 1,
            "stateVersion": 0,
        }
        _write_status_payload(fallback)
        log(f"state_db_fallback {type(exc).__name__}")
        return None


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
        ensure_private_dir(BUDDY_DIR)
        SPAWN_GUARD.write_text(str(now), encoding="utf-8")
        chmod_private(SPAWN_GUARD)

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
            raw, oversized = _read_hook_input()
            if oversized:
                log(f"stdin_oversize limit_bytes={HOOK_INPUT_MAX_BYTES}")
                return 0
        except Exception as e:
            # UnicodeDecodeError retains the original byte object; repr(e)
            # could therefore copy private hook input into hook.log.
            log(f"stdin_err type={type(e).__name__}")

        data: dict = {}
        if raw and raw.strip():
            try:
                data = json.loads(raw)
            except Exception as e:
                # log the shape only — raw hook input can carry session paths
                log(f"bad_json {e!r} len={len(raw)}")

        event = resolve_event(data, sys.argv)
        tool = _bounded_field(data.get("tool_name") or data.get("toolName"))
        session_id = str(data.get("session_id") or "")

        mapped = EVENT_TO_MOOD.get(event)
        if mapped is None:
            # diagnosis needs the SHAPE, never the content
            log(_skip_line(event, raw, data))
            return 0

        if notification_is_noise(event, data):
            log(f"skip notification type={_notification_type(data)!r}")
            return 0

        if stop_has_pending_background(event, data):
            # The foreground response ended, but Claude will wake again when
            # the background result arrives.  Keep the preceding WORKING row
            # instead of producing a premature DONE; the final Stop (empty
            # task list) will publish the one real completion.
            log(
                f"defer done event={event!r} "
                f"background_tasks={len(data['background_tasks'])}"
            )
            return 0

        mood, msg = mapped
        if tool and mood == "work":
            msg = f"WORKING · {tool}"
        result = write_status(
            mood, msg, tool=tool, event=event, session_id=session_id
        )
        if result is not None and not result.accepted:
            log(
                f"drop straggler event={event!r} "
                f"session={result.session_key[:12]}"
            )
        else:
            session_label = result.session_key[:12] if result is not None else "fallback"
            background_note = ""
            if event in ("Stop", "stop"):
                tasks = data.get("background_tasks")
                background_note = (
                    f" background_tasks={len(tasks)}"
                    if isinstance(tasks, list)
                    else " background_tasks=<unavailable>"
                )
            log(
                f"ok event={event!r} mood={mood} tool={tool!r} "
                f"session={session_label}{background_note}"
            )

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

    return 0  # handled paths emit no stdout and make no hook decision


if __name__ == "__main__":
    raise SystemExit(main())
