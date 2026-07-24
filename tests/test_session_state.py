"""Cross-platform, GUI-free tests for the multi-session state store.

This suite uses one TemporaryDirectory and never reads or writes the user's
HOME.  It is safe to run before or after the experimental macOS apply.
"""

from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
import tempfile
import threading
import time
import traceback
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from session_state import (  # noqa: E402
    SessionStore,
    chmod_private,
    ensure_private_dir,
    hashed_session_id,
)


def test_private_state_permissions(root: Path) -> None:
    private = root / "private-state"
    private.mkdir(mode=0o755)
    ensure_private_dir(private)
    state = private / "status.json"
    state.write_text("{}", encoding="utf-8")
    chmod_private(state)
    if os.name != "nt":
        assert stat.S_IMODE(private.stat().st_mode) == 0o700
        assert stat.S_IMODE(state.stat().st_mode) == 0o600


def test_priority_and_isolation(root: Path) -> None:
    store = SessionStore(root / "priority.sqlite3")
    base = time.time()
    assert store.record_event(
        session_id="main", mood="work", message="working",
        tool="Bash", event="PreToolUse", now=base,
    ).aggregate["mood"] == "work"
    assert store.record_event(
        session_id="helper", mood="sleep", message="session end",
        tool="", event="SessionEnd", now=base + 0.1,
    ).aggregate["mood"] == "work"
    assert store.record_event(
        session_id="waiting", mood="alert", message="waiting",
        tool="", event="PermissionRequest", now=base + 0.2,
    ).aggregate["mood"] == "alert"
    assert store.record_event(
        session_id="main", mood="happy", message="done",
        tool="", event="Stop", now=base + 0.3,
    ).aggregate["mood"] == "alert"

    stale = store.record_event(
        session_id="waiting", mood="work", message="working",
        tool="Bash", event="PostToolUse", now=base + 1.0,
    )
    assert not stale.accepted
    fresh = store.record_event(
        session_id="other", mood="work", message="working",
        tool="Bash", event="PreToolUse", now=base + 1.1,
    )
    assert fresh.accepted and fresh.aggregate["mood"] == "alert"
    assert store.snapshot(now=base + 901.0)["mood"] == "work"


def test_same_session_out_of_order_is_rejected(root: Path) -> None:
    """A delayed old hook must not erase a newer state from the same session."""
    store = SessionStore(root / "same-session-order.sqlite3")
    base = time.time()
    published: list[tuple[int, str]] = []

    newer = store.record_event(
        session_id="same", mood="alert", message="waiting",
        tool="Bash", event="PermissionRequest", now=base + 2.0,
        status_writer=lambda data: published.append(
            (int(data["stateVersion"]), str(data["mood"]))
        ),
    )
    delayed_old = store.record_event(
        session_id="same", mood="work", message="working",
        tool="Bash", event="PreToolUse", now=base + 1.0,
        status_writer=lambda data: published.append(
            (int(data["stateVersion"]), str(data["mood"]))
        ),
    )

    assert newer.accepted and newer.revision == 1
    assert not delayed_old.accepted and delayed_old.revision == 1
    assert delayed_old.aggregate["mood"] == "alert"
    assert published == [(1, "alert")], "rejected hooks must not republish status"
    assert store.snapshot(now=base + 2.0)["mood"] == "alert"

    # The guard is not a permanent latch: a genuinely later completion can
    # still advance the same session after the short terminal safety window.
    resolved = store.record_event(
        session_id="same", mood="work", message="working",
        tool="Bash", event="PostToolUse", now=base + 6.0,
    )
    assert resolved.accepted and resolved.aggregate["mood"] == "work"
    delayed_done = store.record_event(
        session_id="same", mood="happy", message="done",
        tool="", event="Stop", now=base + 5.0,
    )
    assert not delayed_done.accepted
    assert store.snapshot(now=base + 6.0)["mood"] == "work"
    assert [row["kind"] for row in store.signals_after(0)] == ["alert"], (
        "a rejected stale completion must not emit a false DONE signal"
    )


def test_same_session_concurrent_commit_reordering(root: Path) -> None:
    """Mirror an async old hook paused before SQLite while a newer one commits."""
    path = root / "same-session-concurrent-order.sqlite3"
    old_reached_connect = threading.Event()
    release_old = threading.Event()
    old_result = []

    class DelayedConnectStore(SessionStore):
        def _connect(self):
            old_reached_connect.set()
            assert release_old.wait(timeout=10)
            return super()._connect()

    def record_old_work() -> None:
        old_result.append(DelayedConnectStore(path).record_event(
            session_id="same", mood="work", message="working",
            tool="Bash", event="PreToolUse",
        ))

    thread = threading.Thread(target=record_old_work)
    thread.start()
    assert old_reached_connect.wait(timeout=10)
    try:
        newer = SessionStore(path).record_event(
            session_id="same", mood="alert", message="waiting",
            tool="Bash", event="PermissionRequest",
        )
    finally:
        release_old.set()
        thread.join(timeout=10)

    assert not thread.is_alive() and len(old_result) == 1
    assert newer.accepted and not old_result[0].accepted
    assert SessionStore(path).snapshot()["mood"] == "alert"


def test_privacy_and_signals(root: Path) -> None:
    path = root / "privacy.sqlite3"
    store = SessionStore(path)
    raw_session = "private-session-id-please-do-not-store"
    base = time.time()
    result = store.record_event(
        session_id=raw_session, mood="happy", message="done",
        tool="", event="Stop", now=base,
    )
    assert result.session_key == hashed_session_id(raw_session)
    duplicate = store.record_event(
        session_id=raw_session, mood="happy", message="done",
        tool="", event="TaskCompleted", now=base + 0.2,
    )
    assert duplicate.signal_id is None
    store.record_event(
        session_id="other", mood="error", message="error",
        tool="", event="StopFailure", now=base + 0.3,
    )
    assert [item["kind"] for item in store.signals_after(0)] == ["happy", "error"]
    needle = raw_session.encode("utf-8")
    for db_part in path.parent.glob(path.name + "*"):
        assert needle not in db_part.read_bytes(), db_part.name
    if os.name != "nt":
        assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_decay_variants(root: Path) -> None:
    base = time.time()
    happy = SessionStore(root / "happy-decay.sqlite3")
    happy.record_event(
        session_id="friday", mood="happy", message="done",
        tool="", event="Stop", now=base,
    )
    assert happy.snapshot(now=base + 15.0)["mood"] == "idle"
    assert happy.snapshot(now=base + 15.0, happy_sec=20.0)["mood"] == "happy"

    sleep = SessionStore(root / "sleep-decay.sqlite3")
    sleep.record_event(
        session_id="ended", mood="sleep", message="session end",
        tool="", event="SessionEnd", now=base,
    )
    assert sleep.snapshot(now=base + 86400.0)["mood"] == "sleep"


def test_concurrent_writers(root: Path) -> None:
    path = root / "concurrent.sqlite3"
    base = time.time()
    ready = threading.Barrier(16)

    def write_one(n: int) -> bool:
        ready.wait(timeout=10)
        return SessionStore(path).record_event(
            session_id=f"session-{n}", mood="work", message="working",
            tool="Bash", event="PreToolUse", now=base + n / 100.0,
        ).accepted

    with ThreadPoolExecutor(max_workers=16) as pool:
        assert all(pool.map(write_one, range(16)))
    state = SessionStore(path).snapshot(now=base + 1.0)
    assert state["mood"] == "work" and state["sessionCount"] == 16


def test_status_writer_order(root: Path) -> None:
    path = root / "ordering.sqlite3"
    published: list[int] = []

    def write_one(n: int) -> bool:
        result = SessionStore(path).record_event(
            session_id=f"session-{n}", mood="work", message="working",
            tool="Bash", event="PreToolUse",
            status_writer=lambda payload: published.append(payload["stateVersion"]),
        )
        return result.accepted

    with ThreadPoolExecutor(max_workers=8) as pool:
        assert all(pool.map(write_one, range(16)))
    assert published == list(range(1, 17)), published


def test_concurrent_hook_processes(root: Path) -> None:
    """Mirror Claude Code: every simultaneous event is a fresh process."""
    runtime = root / "concurrent-hooks"
    status = runtime / "status.json"
    db = runtime / "sessions.sqlite3"
    env = os.environ.copy()
    env.update({
        "CLAUDE_BUDDY_DIR": str(runtime),
        "CLAUDE_BUDDY_STATUS": str(status),
        "MADOMOCHI_STATE_DB": str(db),
        "PYTHONDONTWRITEBYTECODE": "1",
    })
    hook = ROOT / "scripts" / "hook_entry.py"
    ready = threading.Barrier(16)

    def invoke(n: int) -> int:
        ready.wait(timeout=10)
        payload = {
            "hook_event_name": "PreToolUse",
            "session_id": f"process-session-{n}",
            "tool_name": "Bash",
        }
        proc = subprocess.run(
            [sys.executable, str(hook), "--hajimetwi3-buddy-hook", "PreToolUse"],
            input=json.dumps(payload), text=True, capture_output=True,
            timeout=12, env=env,
        )
        assert proc.stdout == "" and proc.stderr == ""
        return proc.returncode

    with ThreadPoolExecutor(max_workers=16) as pool:
        assert list(pool.map(invoke, range(16))) == [0] * 16

    aggregate = SessionStore(db).snapshot(now=time.time())
    assert aggregate["mood"] == "work" and aggregate["sessionCount"] == 16
    published = json.loads(status.read_text(encoding="utf-8"))
    assert published["stateVersion"] == 16 and published["sessionCount"] == 16
    hook_log = (runtime / "hook.log").read_text(encoding="utf-8")
    assert "state_db_fallback" not in hook_log
    assert list(runtime.glob("status.*.tmp")) == []


def test_hook_entry_integration(root: Path) -> None:
    runtime = root / "hook-runtime"
    status = runtime / "status.json"
    db = runtime / "sessions.sqlite3"
    env = os.environ.copy()
    env.update({
        "CLAUDE_BUDDY_DIR": str(runtime),
        "CLAUDE_BUDDY_STATUS": str(status),
        "MADOMOCHI_STATE_DB": str(db),
        "PYTHONDONTWRITEBYTECODE": "1",
    })
    hook = ROOT / "scripts" / "hook_entry.py"

    events = [
        ("PreToolUse", "session-a", {"tool_name": "Bash"}),
        ("PermissionRequest", "session-b", {}),
        ("Stop", "session-a", {}),
    ]
    for event, session_id, extra in events:
        payload = {
            "hook_event_name": event,
            "session_id": session_id,
            **extra,
        }
        proc = subprocess.run(
            [sys.executable, str(hook), "--hajimetwi3-buddy-hook", event],
            input=json.dumps(payload), text=True, capture_output=True,
            timeout=8, env=env,
        )
        assert proc.returncode == 0 and proc.stdout == "" and proc.stderr == ""

    aggregate = json.loads(status.read_text(encoding="utf-8"))
    assert aggregate["mood"] == "alert"
    assert aggregate["session"] == hashed_session_id("session-b")[:12]
    persisted = b"".join(
        item.read_bytes() for item in runtime.glob("sessions.sqlite3*")
    )
    hook_log = (runtime / "hook.log").read_text(encoding="utf-8")
    assert b"session-a" not in persisted and b"session-b" not in persisted
    assert "session-a" not in hook_log and "session-b" not in hook_log


def test_background_stop_defers_done(root: Path) -> None:
    runtime = root / "background-runtime"
    status = runtime / "status.json"
    db = runtime / "sessions.sqlite3"
    env = os.environ.copy()
    env.update({
        "CLAUDE_BUDDY_DIR": str(runtime),
        "CLAUDE_BUDDY_STATUS": str(status),
        "MADOMOCHI_STATE_DB": str(db),
        "PYTHONDONTWRITEBYTECODE": "1",
    })
    hook = ROOT / "scripts" / "hook_entry.py"

    def invoke(event: str, extra: dict) -> None:
        payload = {
            "hook_event_name": event,
            "session_id": "background-session",
            **extra,
        }
        proc = subprocess.run(
            [sys.executable, str(hook), "--hajimetwi3-buddy-hook", event],
            input=json.dumps(payload), text=True, capture_output=True,
            timeout=8, env=env,
        )
        assert proc.returncode == 0 and proc.stdout == "" and proc.stderr == ""

    invoke("PreToolUse", {"tool_name": "Bash"})
    working = json.loads(status.read_text(encoding="utf-8"))
    assert working["mood"] == "work"

    secret = "private background command text"
    invoke("Stop", {"background_tasks": [{
        "id": "task-1", "type": "shell", "status": "running",
        "description": secret, "command": secret,
    }]})
    deferred = json.loads(status.read_text(encoding="utf-8"))
    assert deferred == working, "a foreground-only Stop must preserve WORKING"
    assert SessionStore(db).signals_after(0) == [], "no early DONE signal"
    hook_log = (runtime / "hook.log").read_text(encoding="utf-8")
    assert "defer done" in hook_log and "background_tasks=1" in hook_log
    assert secret not in hook_log
    assert secret.encode("utf-8") not in b"".join(
        item.read_bytes() for item in runtime.glob("sessions.sqlite3*")
    )

    invoke("Stop", {"background_tasks": []})
    finished = json.loads(status.read_text(encoding="utf-8"))
    assert finished["mood"] == "happy"
    assert [row["kind"] for row in SessionStore(db).signals_after(0)] == ["happy"]
    hook_log = (runtime / "hook.log").read_text(encoding="utf-8")
    assert "background_tasks=0" in hook_log


TESTS = [
    test_private_state_permissions,
    test_priority_and_isolation,
    test_same_session_out_of_order_is_rejected,
    test_same_session_concurrent_commit_reordering,
    test_privacy_and_signals,
    test_decay_variants,
    test_concurrent_writers,
    test_status_writer_order,
    test_concurrent_hook_processes,
    test_hook_entry_integration,
    test_background_stop_defers_done,
]


def main() -> int:
    failed = []
    with tempfile.TemporaryDirectory(prefix="madomochi_session_test_") as tmp:
        root = Path(tmp)
        for fn in TESTS:
            try:
                fn(root)
                print(f"OK   {fn.__name__}")
            except Exception:
                failed.append(fn.__name__)
                print(f"FAIL {fn.__name__}")
                traceback.print_exc()
    if failed:
        print("FAILED:", ", ".join(failed))
        return 1
    print(f"ALL {len(TESTS)} TESTS PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
