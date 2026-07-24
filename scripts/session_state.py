#!/usr/bin/env python3
"""Session-aware state storage for MadoMochi.

Claude Code launches one short-lived hook process per event.  This module gives
those processes a small SQLite rendezvous point so events from independent
sessions no longer overwrite one another blindly.  The database stores only a
SHA-256-derived session key, fixed MadoMochi labels, hook event names, and tool
names; prompt text, transcript paths, and raw session ids are never persisted.

The hook still writes the aggregate state to status.json for compatibility with
the existing companion UI.  SQLite serializes commits, and each session rejects
events timestamped before its currently committed state.  The aggregate file is
written while an IMMEDIATE transaction is held so accepted commits are published
in the same order.
"""

from __future__ import annotations

import hashlib
import os
import sqlite3
import stat
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable


SCHEMA_VERSION = 1
DEFAULT_PROVIDER = "claude"
UNKNOWN_SESSION = "<unknown>"
SQLITE_BUSY_MS = 750
SQLITE_INIT_RETRIES = 4


def ensure_private_dir(path: Path) -> None:
    """Create a per-user state directory and tighten it on POSIX."""
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    if os.name != "nt":
        try:
            if stat.S_IMODE(path.stat().st_mode) != 0o700:
                os.chmod(path, 0o700)
        except OSError:
            pass


def chmod_private(path: Path) -> None:
    """Best-effort 0600 permissions; Windows uses its normal ACLs."""
    if os.name != "nt":
        try:
            if stat.S_IMODE(path.stat().st_mode) != 0o600:
                os.chmod(path, 0o600)
        except OSError:
            pass

# Keep these lifetimes aligned with buddy.py's visible decay rules.  They are
# applied when choosing among sessions; the buddy still owns animation timing.
LISTEN_SEC = 3.0
HAPPY_SEC = 10.0
ERROR_SEC = 6.0
THINK_SEC = 600.0
ALERT_SEC = 900.0
WORK_FAST_SEC = 300.0
WORK_LONG_SEC = 1800.0
STRAGGLER_SEC = 3.0
LONG_TOOLS = {"Bash", "PowerShell", "Agent", "Workflow"}
TERMINAL_MOODS = {"happy", "alert", "sleep"}
SIGNAL_MOODS = {"happy", "error", "alert"}

# An unresolved alert must beat everything.  A background completion produces
# a signal (and therefore a sound) but should not hide another active session.
MOOD_PRIORITY = {
    "alert": 800,
    "error": 700,
    "work": 600,
    "listen": 550,
    "think": 500,
    "happy": 400,
    "idle": 100,
    "sleep": 50,
}

DEFAULT_MESSAGE = {
    "idle": "idle",
    "listen": "prompt received",
    "think": "thinking",
    "work": "working",
    "happy": "done",
    "error": "error",
    "alert": "waiting for you",
    "sleep": "session end",
}


@dataclass(frozen=True)
class RecordResult:
    accepted: bool
    aggregate: dict
    session_key: str
    revision: int
    signal_id: int | None = None


def hashed_session_id(session_id: str, provider: str = DEFAULT_PROVIDER) -> str:
    """Return a path/DB-safe identifier without retaining the raw session id."""
    raw = session_id.strip() or UNKNOWN_SESSION
    return hashlib.sha256(f"{provider}\0{raw}".encode("utf-8")).hexdigest()


def _iso_utc(epoch: float) -> str:
    return datetime.fromtimestamp(epoch, timezone.utc).isoformat()


def _effective_mood(
    mood: str,
    tool: str,
    updated_at: float,
    now: float,
    happy_sec: float = HAPPY_SEC,
) -> str:
    """Apply the companion's visible decay rules without mutating the DB row."""
    age = max(0.0, now - updated_at)
    if mood == "listen":
        if age < LISTEN_SEC:
            return "listen"
        return "think" if age < LISTEN_SEC + THINK_SEC else "idle"
    if mood == "think":
        return "think" if age < THINK_SEC else "idle"
    if mood == "work":
        limit = WORK_LONG_SEC if tool in LONG_TOOLS else WORK_FAST_SEC
        return "work" if age < limit else "idle"
    if mood == "happy":
        return "happy" if age < happy_sec else "idle"
    if mood == "error":
        return "error" if age < ERROR_SEC else "idle"
    if mood == "alert":
        return "alert" if age < ALERT_SEC else "idle"
    if mood == "sleep":
        return "sleep"
    return "idle"


class SessionStore:
    """Short-transaction SQLite store shared by hook processes and the UI."""

    def __init__(self, path: Path, provider: str = DEFAULT_PROVIDER):
        self.path = Path(path)
        self.provider = provider

    @staticmethod
    def _busy_error(exc: sqlite3.OperationalError) -> bool:
        text = str(exc).lower()
        return "locked" in text or "busy" in text

    @staticmethod
    def _schema_ready(con: sqlite3.Connection) -> bool:
        objects = {
            str(row[0])
            for row in con.execute(
                "SELECT name FROM sqlite_master "
                "WHERE name IN ('meta', 'sessions', 'signals', "
                "'signals_provider_id')"
            ).fetchall()
        }
        if objects != {"meta", "sessions", "signals", "signals_provider_id"}:
            return False
        row = con.execute(
            "SELECT value FROM meta WHERE key='schema_version'"
        ).fetchone()
        return bool(row and str(row[0]) == str(SCHEMA_VERSION))

    @staticmethod
    def _initialize_schema(con: sqlite3.Connection) -> None:
        """Create the complete schema under one SQLite write transaction."""
        con.execute("BEGIN IMMEDIATE")
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """
        )
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                provider TEXT NOT NULL,
                session_key TEXT NOT NULL,
                mood TEXT NOT NULL,
                message TEXT NOT NULL,
                tool TEXT NOT NULL,
                event TEXT NOT NULL,
                updated_at REAL NOT NULL,
                ended INTEGER NOT NULL DEFAULT 0,
                revision INTEGER NOT NULL,
                PRIMARY KEY (provider, session_key)
            )
            """
        )
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                provider TEXT NOT NULL,
                session_key TEXT NOT NULL,
                kind TEXT NOT NULL,
                event TEXT NOT NULL,
                created_at REAL NOT NULL
            )
            """
        )
        con.execute(
            """
            CREATE INDEX IF NOT EXISTS signals_provider_id
                ON signals(provider, id)
            """
        )
        con.execute(
            "INSERT OR IGNORE INTO meta(key, value) "
            "VALUES('schema_version', ?)",
            (str(SCHEMA_VERSION),),
        )
        con.execute(
            "INSERT OR IGNORE INTO meta(key, value) VALUES('revision', '0')"
        )
        con.commit()

    def _connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if os.name != "nt" and not self.path.exists():
            try:
                fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_RDWR, 0o600)
                os.close(fd)
            except FileExistsError:
                pass
        if self.path.is_file():
            chmod_private(self.path)

        # Every Claude hook is a fresh process. Reissuing the write-form
        # journal_mode pragma and all CREATE statements on every connection
        # lets simultaneous first events race before BEGIN IMMEDIATE is even
        # reached. Read the persistent mode/schema first, initialize only when
        # needed, and retry the short first-open race within the synchronous
        # PermissionRequest hook's five-second ceiling.
        last_busy: sqlite3.OperationalError | None = None
        for attempt in range(SQLITE_INIT_RETRIES):
            con: sqlite3.Connection | None = None
            try:
                con = sqlite3.connect(
                    str(self.path), timeout=SQLITE_BUSY_MS / 1000.0
                )
                con.row_factory = sqlite3.Row
                con.execute(f"PRAGMA busy_timeout = {SQLITE_BUSY_MS}")
                row = con.execute("PRAGMA journal_mode").fetchone()
                mode = str(row[0]).lower() if row else ""
                if mode != "wal":
                    con.execute("PRAGMA journal_mode = WAL")
                con.execute("PRAGMA synchronous = NORMAL")
                if not self._schema_ready(con):
                    self._initialize_schema(con)
                return con
            except sqlite3.OperationalError as exc:
                if con is not None:
                    try:
                        con.rollback()
                    except sqlite3.Error:
                        pass
                    con.close()
                if not self._busy_error(exc) or attempt + 1 >= SQLITE_INIT_RETRIES:
                    raise
                last_busy = exc
                time.sleep(0.025 * (attempt + 1))
            except Exception:
                if con is not None:
                    try:
                        con.rollback()
                    except sqlite3.Error:
                        pass
                    con.close()
                raise
        assert last_busy is not None
        raise last_busy

    def _read_connect(self) -> sqlite3.Connection:
        """Open an existing store without repeating schema-write statements."""
        if not self.path.is_file():
            return self._connect()
        con = sqlite3.connect(str(self.path), timeout=SQLITE_BUSY_MS / 1000.0)
        con.row_factory = sqlite3.Row
        con.execute(f"PRAGMA busy_timeout = {SQLITE_BUSY_MS}")
        return con

    @staticmethod
    def _next_revision(con: sqlite3.Connection) -> int:
        row = con.execute("SELECT value FROM meta WHERE key='revision'").fetchone()
        revision = int(row[0] if row else 0) + 1
        con.execute(
            "INSERT INTO meta(key, value) VALUES('revision', ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (str(revision),),
        )
        return revision

    def _aggregate(
        self,
        con: sqlite3.Connection,
        now: float,
        revision: int,
        happy_sec: float = HAPPY_SEC,
    ) -> dict:
        rows = con.execute(
            "SELECT session_key, mood, message, tool, event, updated_at, ended "
            "FROM sessions WHERE provider=?",
            (self.provider,),
        ).fetchall()

        candidates: list[tuple[tuple[float, float], sqlite3.Row, str]] = []
        active_count = 0
        for row in rows:
            effective = _effective_mood(
                str(row["mood"]), str(row["tool"]),
                float(row["updated_at"]), now, happy_sec,
            )
            if not int(row["ended"]):
                active_count += 1
            # For alerts, the oldest unresolved request wins ties so roaming
            # reflects the request that has actually waited the longest.
            tie = (
                -float(row["updated_at"])
                if effective == "alert"
                else float(row["updated_at"])
            )
            candidates.append(((float(MOOD_PRIORITY[effective]), tie), row, effective))

        if not candidates:
            return {
                "mood": "idle",
                "message": DEFAULT_MESSAGE["idle"],
                "tool": "",
                "event": "",
                "updatedAt": _iso_utc(now),
                "provider": self.provider,
                "session": "",
                "sessionCount": 0,
                "stateVersion": revision,
            }

        _score, selected, effective = max(candidates, key=lambda item: item[0])
        original_mood = str(selected["mood"])
        message = str(selected["message"])
        tool = str(selected["tool"])
        if effective != original_mood:
            message = DEFAULT_MESSAGE[effective]
            if effective != "work":
                tool = ""
        return {
            "mood": effective,
            "message": message,
            "tool": tool,
            "event": str(selected["event"]),
            "updatedAt": _iso_utc(float(selected["updated_at"])),
            "provider": self.provider,
            "session": str(selected["session_key"])[:12],
            "sessionCount": active_count,
            "stateVersion": revision,
        }

    def record_event(
        self,
        *,
        session_id: str,
        mood: str,
        message: str,
        tool: str,
        event: str,
        now: float | None = None,
        status_writer: Callable[[dict], None] | None = None,
    ) -> RecordResult:
        """Record one hook event and return the provider-wide aggregate.

        status_writer runs before COMMIT while the database write lock is held.
        That small critical section preserves aggregate-file ordering across
        concurrent hook processes.
        """
        stamp = time.time() if now is None else float(now)
        key = hashed_session_id(session_id, self.provider)
        con = self._connect()
        try:
            con.execute("BEGIN IMMEDIATE")
            previous = con.execute(
                "SELECT mood, updated_at FROM sessions "
                "WHERE provider=? AND session_key=?",
                (self.provider, key),
            ).fetchone()
            previous_at = (
                float(previous["updated_at"]) if previous is not None else stamp
            )
            stale_timestamp = previous is not None and stamp < previous_at
            recent_terminal_straggler = (
                mood == "work"
                and previous is not None
                and str(previous["mood"]) in TERMINAL_MOODS
                and 0.0 <= stamp - previous_at < STRAGGLER_SEC
            )
            if stale_timestamp or recent_terminal_straggler:
                row = con.execute("SELECT value FROM meta WHERE key='revision'").fetchone()
                revision = int(row[0] if row else 0)
                # A rejected event must not make the returned view travel
                # backwards in time either.  This matters to callers that use
                # the aggregate for diagnostics even though it is not published.
                aggregate = self._aggregate(con, max(stamp, previous_at), revision)
                con.rollback()
                return RecordResult(False, aggregate, key, revision)

            revision = self._next_revision(con)
            ended = 1 if event in {"SessionEnd", "session_end"} else 0
            con.execute(
                """
                INSERT INTO sessions(
                    provider, session_key, mood, message, tool, event,
                    updated_at, ended, revision
                ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(provider, session_key) DO UPDATE SET
                    mood=excluded.mood,
                    message=excluded.message,
                    tool=excluded.tool,
                    event=excluded.event,
                    updated_at=excluded.updated_at,
                    ended=excluded.ended,
                    revision=excluded.revision
                """,
                (
                    self.provider,
                    key,
                    mood,
                    message,
                    tool,
                    event,
                    stamp,
                    ended,
                    revision,
                ),
            )

            signal_id = None
            if mood in SIGNAL_MOODS:
                # Coalesce exact duplicate arrivals from the same session in a
                # very small window, while preserving genuinely separate turns.
                last = con.execute(
                    "SELECT kind, created_at FROM signals "
                    "WHERE provider=? AND session_key=? ORDER BY id DESC LIMIT 1",
                    (self.provider, key),
                ).fetchone()
                duplicate = bool(
                    last
                    and str(last["kind"]) == mood
                    and stamp - float(last["created_at"]) < 0.5
                )
                if not duplicate:
                    cur = con.execute(
                        "INSERT INTO signals(provider, session_key, kind, event, created_at) "
                        "VALUES(?, ?, ?, ?, ?)",
                        (self.provider, key, mood, event, stamp),
                    )
                    signal_id = int(cur.lastrowid)

            # Runtime state is disposable, but keep it bounded even if a
            # machine runs many sessions for months.
            con.execute(
                "DELETE FROM sessions WHERE provider=? AND updated_at < ?",
                (self.provider, stamp - 7 * 86400.0),
            )
            con.execute(
                "DELETE FROM signals WHERE provider=? AND created_at < ?",
                (self.provider, stamp - 86400.0),
            )
            cutoff = con.execute(
                "SELECT id FROM signals WHERE provider=? "
                "ORDER BY id DESC LIMIT 1 OFFSET 511",
                (self.provider,),
            ).fetchone()
            if cutoff:
                con.execute(
                    "DELETE FROM signals WHERE provider=? AND id < ?",
                    (self.provider, int(cutoff["id"])),
                )

            aggregate = self._aggregate(con, stamp, revision)
            if status_writer is not None:
                status_writer(aggregate)
            con.commit()
            return RecordResult(True, aggregate, key, revision, signal_id)
        except Exception:
            con.rollback()
            raise
        finally:
            con.close()

    def latest_signal_id(self) -> int:
        con = self._connect()
        try:
            row = con.execute(
                "SELECT COALESCE(MAX(id), 0) FROM signals WHERE provider=?",
                (self.provider,),
            ).fetchone()
            return int(row[0] if row else 0)
        finally:
            con.close()

    def signals_after(self, signal_id: int, limit: int = 64) -> list[dict]:
        con = self._read_connect()
        try:
            rows = con.execute(
                "SELECT id, kind, event, created_at, session_key FROM signals "
                "WHERE provider=? AND id>? ORDER BY id LIMIT ?",
                (self.provider, int(signal_id), int(limit)),
            ).fetchall()
            return [dict(row) for row in rows]
        finally:
            con.close()

    def snapshot(
        self, now: float | None = None, happy_sec: float = HAPPY_SEC
    ) -> dict:
        stamp = time.time() if now is None else float(now)
        con = self._read_connect()
        try:
            row = con.execute("SELECT value FROM meta WHERE key='revision'").fetchone()
            return self._aggregate(
                con, stamp, int(row[0] if row else 0), happy_sec
            )
        finally:
            con.close()

    def poll(
        self,
        signal_id: int,
        now: float | None = None,
        limit: int = 64,
        happy_sec: float = HAPPY_SEC,
    ) -> tuple[dict, list[dict]]:
        """Read aggregate state and new momentary signals in one transaction."""
        stamp = time.time() if now is None else float(now)
        con = self._read_connect()
        try:
            con.execute("BEGIN")
            row = con.execute("SELECT value FROM meta WHERE key='revision'").fetchone()
            aggregate = self._aggregate(
                con, stamp, int(row[0] if row else 0), happy_sec
            )
            rows = con.execute(
                "SELECT id, kind, event, created_at, session_key FROM signals "
                "WHERE provider=? AND id>? ORDER BY id LIMIT ?",
                (self.provider, int(signal_id), int(limit)),
            ).fetchall()
            con.commit()
            return aggregate, [dict(item) for item in rows]
        except Exception:
            con.rollback()
            raise
        finally:
            con.close()

    def clear(self) -> None:
        """Clear disposable runtime state. Intended for hermetic tests."""
        con = self._connect()
        try:
            con.execute("DELETE FROM sessions WHERE provider=?", (self.provider,))
            con.execute("DELETE FROM signals WHERE provider=?", (self.provider,))
            con.execute("UPDATE meta SET value='0' WHERE key='revision'")
            con.commit()
        finally:
            con.close()
