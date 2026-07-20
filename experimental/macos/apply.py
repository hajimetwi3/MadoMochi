#!/usr/bin/env python3
"""
One-shot macOS enabler for MadoMochi.

    python3 experimental/macos/apply.py                      # apply on a Mac
    python3 experimental/macos/apply.py --check              # verify only (any OS)
    python3 experimental/macos/apply.py --undo               # reverse everything
    python3 experimental/macos/apply.py --undo --purge-data  # ...and delete runtime data

What it does, in two phases so a mismatch can never leave the repo
half-patched:

  1. PLAN  — every patch anchor is located in the current sources (or
     detected as already applied). Any miss aborts with a report and
     zero writes.
  2. WRITE — originals are backed up to scripts_backup_macos/ once,
     platform files are copied into scripts/ (start/stop .sh get +x),
     and the anchored patches are applied.

The patches (all real code, no hand-editing):
  A  audio backend select      — MacBgmPlayer on darwin
  B  window transparency       — aqua-guarded systemTransparent, with an
                                 explicit degraded mode
  C  transparent sprite paint  — colored runs only; empty pixels stay unset
  D  right-click               — Button-2 / Control-Button-1 on darwin
  E  single instance           — fcntl.flock held for the process lifetime
  F  graceful SIGTERM          — stop_buddy.sh routes through _on_close
  G  hook launcher detach      — start_new_session on POSIX
  H  corner-parking default    — parks when Quartz is unavailable
                                 (an explicit config value still wins)

Re-running is safe: applied patches are recognized and skipped.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import py_compile
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
SCRIPTS = ROOT / "scripts"
BACKUP = ROOT / "scripts_backup_macos"

COPIES = [
    # (source in this folder, destination, make executable)
    (HERE / "window_pos.py", SCRIPTS / "window_pos.py", False),
    (HERE / "mac_audio.py", SCRIPTS / "mac_audio.py", False),
    (HERE / "start_buddy.sh", SCRIPTS / "start_buddy.sh", True),
    (HERE / "stop_buddy.sh", SCRIPTS / "stop_buddy.sh", True),
]

BUDDY = SCRIPTS / "buddy.py"
HOOK = SCRIPTS / "hook_entry.py"
MANIFEST = BACKUP / "manifest.json"

# every file the apply manages, and nothing else
_MANAGED_SOURCES = ("buddy.py", "hook_entry.py", "window_pos.py")
_MANAGED_COPIES = ("mac_audio.py", "start_buddy.sh", "stop_buddy.sh")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_manifest() -> tuple:
    """Load manifest.json, accepting ONLY the program-defined shape.

    A manifest is trusted because it exactly matches the fixed sets this
    program defines (_MANAGED_SOURCES / _MANAGED_COPIES), never because
    of what it happens to contain: every key set must match exactly, so
    absolute paths, separators or dot-segments can never reach a Path.
    Values must be sha256 hex digests. Raises ValueError on any deviation.
    """
    raw = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or set(raw) != {"version", "originals", "applied", "created"}:
        raise ValueError("unsupported manifest shape")
    version = raw.get("version")
    if isinstance(version, bool) or version != 1:  # bool: True == 1 in Python
        raise ValueError("unsupported manifest version")
    hex64 = re.compile(r"[0-9a-f]{64}")

    def table(key, allow):
        t = raw.get(key)
        if not isinstance(t, dict) or set(t) != set(allow):
            raise ValueError(f"{key}: names must exactly match the managed set")
        for k, v in t.items():
            if not isinstance(v, str) or not hex64.fullmatch(v):
                raise ValueError(f"{key}: {k} is not a sha256 digest")
        return dict(t)

    originals = table("originals", _MANAGED_SOURCES)
    applied = table("applied", (*_MANAGED_SOURCES, *_MANAGED_COPIES))
    created = raw.get("created")
    if not isinstance(created, list) or sorted(created) != sorted(_MANAGED_COPIES):
        raise ValueError("created: names must exactly match the managed copies")
    # from here on, only the program's own constant is used as the list
    return originals, applied, list(_MANAGED_COPIES)


def _save_prev(src: Path) -> Path:
    """Preserve a possibly-user-edited file as *.prev in the backup folder.

    Never overwrites an earlier .prev (a counter suffix keeps them all),
    and verifies the copy byte-for-byte — a failed save must abort the
    caller before anything is overwritten.
    """
    BACKUP.mkdir(exist_ok=True)
    prev = BACKUP / (src.name + ".prev")
    n = 1
    while prev.exists():
        n += 1
        prev = BACKUP / f"{src.name}.{n}.prev"
    shutil.copy2(src, prev)
    if _sha(prev) != _sha(src):
        raise OSError(f"verification failed while writing {prev.name}")
    return prev

PATCHES = [
    {
        "name": "A audio backend select",
        "file": BUDDY,
        "marker": "from mac_audio import MacBgmPlayer",
        "anchor": """from retro_bgm import (  # noqa: E402
    TRACKS,
    TRACK_META,
    TRACK_LED,
    LED_MODES,
    RetroBgmPlayer,
    led_frame,
    mood_led_mode,
    mood_led_colors,
)""",
        "replace": """from retro_bgm import (  # noqa: E402
    TRACKS,
    TRACK_META,
    TRACK_LED,
    LED_MODES,
    led_frame,
    mood_led_mode,
    mood_led_colors,
)

if sys.platform == "darwin":
    from mac_audio import MacBgmPlayer as RetroBgmPlayer  # noqa: E402
else:
    from retro_bgm import RetroBgmPlayer  # noqa: E402""",
    },
    {
        "name": "B window transparency",
        "file": BUDDY,
        "marker": "systemTransparent",
        "anchor": """        self.root = tk.Tk()
        self.root.title(BUDDY_TITLE)
        self.root.configure(bg=CHROMA)
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        try:
            self.root.wm_attributes("-transparentcolor", CHROMA)
        except tk.TclError:
            self.root.attributes("-alpha", 0.92)""",
        "replace": """        self.root = tk.Tk()
        self.root.title(BUDDY_TITLE)
        self._mac_transparent = False
        if sys.platform == "darwin":
            # aqua Tk: per-pixel transparency via a transparent window bg.
            # Guarded end to end — a non-aqua Tk build must still boot.
            try:
                if self.root.tk.call("tk", "windowingsystem") == "aqua":
                    self.root.configure(bg="systemTransparent")
                    self.root.attributes("-transparent", True)
                    self._mac_transparent = True
            except tk.TclError:
                self._mac_transparent = False
            self.root.overrideredirect(True)
            self.root.attributes("-topmost", True)
            if not self._mac_transparent:
                # explicit degraded mode: an opaque dark card, still alive
                self.root.configure(bg="#1e2528")
                try:
                    self.root.attributes("-alpha", 0.92)
                except tk.TclError:
                    pass
        else:
            self.root.configure(bg=CHROMA)
            self.root.overrideredirect(True)
            self.root.attributes("-topmost", True)
            try:
                self.root.wm_attributes("-transparentcolor", CHROMA)
            except tk.TclError:
                self.root.attributes("-alpha", 0.92)""",
    },
    {
        "name": "B2 canvas background",
        "file": BUDDY,
        "marker": "canvas_bg = CHROMA",
        "anchor": """        self.canvas = tk.Canvas(
            self.root,
            width=self.w,
            height=self.h,
            highlightthickness=0,
            bd=0,
            bg=CHROMA,
        )""",
        "replace": """        canvas_bg = CHROMA
        if sys.platform == "darwin":
            canvas_bg = "systemTransparent" if self._mac_transparent else "#1e2528"
        self.canvas = tk.Canvas(
            self.root,
            width=self.w,
            height=self.h,
            highlightthickness=0,
            bd=0,
            bg=canvas_bg,
        )""",
    },
    {
        "name": "C transparent sprite paint",
        "file": BUDDY,
        "marker": "put only the colored runs",
        "anchor": """            base = tk.PhotoImage(width=grid, height=grid)
            rows = []
            for y in range(grid):
                rows.append(
                    "{"
                    + " ".join(
                        (pal[c] if c and pal[c] else CHROMA) for c in buf[y]
                    )
                    + "}"
                )
            base.put(" ".join(rows), to=(0, 0))""",
        "replace": """            base = tk.PhotoImage(width=grid, height=grid)
            if sys.platform == "darwin":
                # put only the colored runs; empty pixels stay unset so the
                # window shape is the sprite itself
                for y in range(grid):
                    row = buf[y]
                    x = 0
                    while x < grid:
                        c = row[x]
                        if c and pal[c]:
                            x0 = x
                            while x < grid and row[x] == c:
                                x += 1
                            base.put(
                                "{" + " ".join([pal[c]] * (x - x0)) + "}",
                                to=(x0, y),
                            )
                        else:
                            x += 1
            else:
                rows = []
                for y in range(grid):
                    rows.append(
                        "{"
                        + " ".join(
                            (pal[c] if c and pal[c] else CHROMA) for c in buf[y]
                        )
                        + "}"
                    )
                base.put(" ".join(rows), to=(0, 0))""",
    },
    {
        "name": "D right-click bindings",
        "file": BUDDY,
        "marker": "<Button-2>",
        "anchor": """        self.canvas.bind("<Double-Button-1>", self._on_double)
        self.canvas.bind("<Button-3>", self._on_menu)
        self.root.bind("<Escape>", lambda e: self._on_close())""",
        "replace": """        self.canvas.bind("<Double-Button-1>", self._on_double)
        self.canvas.bind("<Button-3>", self._on_menu)
        if sys.platform == "darwin":
            # aqua Tk reports the right button as Button-2, and trackpad
            # users expect Control-click to open the menu too
            self.canvas.bind("<Button-2>", self._on_menu)
            self.canvas.bind("<Control-Button-1>", self._on_menu)
        self.root.bind("<Escape>", lambda e: self._on_close())""",
    },
    {
        "name": "E POSIX single-instance lock",
        "file": BUDDY,
        "marker": "singleton.lock",
        "anchor": """    global _singleton_mutex
    try:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)""",
        "replace": """    global _singleton_mutex
    if sys.platform == "darwin":
        # POSIX: an flock held for the process lifetime; the OS releases
        # it on any exit, so a crash never wedges the lock
        try:
            import fcntl

            BUDDY_DIR.mkdir(parents=True, exist_ok=True)
            handle = open(BUDDY_DIR / "singleton.lock", "w")
            try:
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError:
                handle.close()
                return False
            _singleton_mutex = handle  # keep the fd (and the lock) alive
            return True
        except Exception:
            return True
    try:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)""",
    },
    {
        "name": "F graceful SIGTERM",
        "file": BUDDY,
        "marker": "signal.SIGTERM",
        "anchor": """    def run(self) -> None:
        self.root.mainloop()""",
        "replace": """    def run(self) -> None:
        if sys.platform == "darwin":
            # stop_buddy.sh sends SIGTERM: route it through the same close
            # path as the window X so audio stops and quit.ts is stamped
            import signal

            def _term(_sig, _frm):
                try:
                    self.root.after(0, self._on_close)
                except Exception:
                    pass

            try:
                signal.signal(signal.SIGTERM, _term)
            except Exception:
                pass
        self.root.mainloop()""",
    },
    {
        "name": "H corner-parking default",
        "file": BUDDY,
        "marker": "HAVE_QUARTZ",
        "anchor": """        self.se_enabled = False
        # keep squatting in the desktop corner while Claude's window is gone
        self.park_when_hidden = False""",
        "replace": """        self.se_enabled = False
        # keep squatting in the desktop corner while Claude's window is gone
        self.park_when_hidden = False
        if sys.platform == "darwin":
            # without Quartz the window can never be followed, so parking
            # is the only useful default (an explicit config value wins)
            try:
                import window_pos as _wp

                self.park_when_hidden = not getattr(_wp, "HAVE_QUARTZ", False)
            except Exception:
                pass""",
    },
    {
        "name": "G hook launcher detach",
        "file": HOOK,
        "marker": "start_new_session",
        "anchor": """        subprocess.Popen(
            [py, str(FLOAT_SCRIPT)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            creationflags=flags,
            close_fds=True,
        )""",
        "replace": """        kwargs = (
            {"creationflags": flags} if os.name == "nt" else {"start_new_session": True}
        )
        subprocess.Popen(
            [py, str(FLOAT_SCRIPT)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            close_fds=True,
            **kwargs,
        )""",
    },
]


def _buddy_present() -> bool:
    """Is there a buddy this undo could stop? (window on nt, process on posix)"""
    if os.name == "nt":
        import ctypes

        return bool(ctypes.windll.user32.FindWindowW(None, "MadoMochi"))
    pattern = re.escape(str(SCRIPTS / "buddy.py"))
    return (
        subprocess.run(
            ["pgrep", "-f", pattern],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        ).returncode
        == 0
    )


def _stop_buddy() -> tuple:
    """Dismiss the buddy and CONFIRM it, stamped as a deliberate quit.

    Returns (ok, message): ok is True only when the buddy is verifiably
    gone (or was never running). quit.ts lives in the SHARED
    ~/.claude/buddy and snoozes prompt-revival for every checkout, so it
    is stamped only when there is actually a buddy here to stop.
    """
    try:
        if not _buddy_present():
            return True, "buddy: not running"
        try:
            buddy_dir = Path.home() / ".claude" / "buddy"
            buddy_dir.mkdir(parents=True, exist_ok=True)
            (buddy_dir / "quit.ts").write_text(str(time.time()), encoding="utf-8")
        except OSError:
            pass
        if os.name == "nt":
            import ctypes

            # window titles cannot tell checkouts apart - one reason the
            # external steps require --force off macOS
            ctypes.windll.user32.PostMessageW(
                ctypes.windll.user32.FindWindowW(None, "MadoMochi"), 0x0010, 0, 0
            )
            for _ in range(10):
                if not ctypes.windll.user32.FindWindowW(None, "MadoMochi"):
                    return True, "buddy: stopped"
                time.sleep(0.2)
            return False, "buddy: close requested but the window is still there"
        # full-path match only, regex-escaped so the path matches literally
        pattern = re.escape(str(SCRIPTS / "buddy.py"))
        subprocess.run(
            ["pkill", "-f", pattern],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        for _ in range(10):  # confirm termination instead of assuming it
            if not _buddy_present():
                return True, "buddy: stopped"
            time.sleep(0.2)
        return False, "buddy: still running after SIGTERM (check by hand)"
    except Exception as e:
        return False, f"buddy: stop skipped ({e})"


def _unhook_this_checkout() -> str:
    """Remove only THIS checkout's hook entries from the global settings.

    Deliberately narrower than install_hooks --uninstall: entries are
    matched by this repo's exact hook_entry.py path, so another
    checkout's wiring (which shares the marker) is left alone.
    """
    settings_path = Path.home() / ".claude" / "settings.json"
    if not settings_path.is_file():
        return "nothing to unhook (no settings file)"
    data = json.loads(settings_path.read_text(encoding="utf-8"))
    hook_path = str(SCRIPTS / "hook_entry.py")
    hooks = data.get("hooks")
    removed = 0
    if isinstance(hooks, dict):
        for event in list(hooks):
            groups = hooks[event]
            for g in groups:
                kept = []
                for h in g.get("hooks", []):
                    args = [str(a) for a in h.get("args", [])]
                    if hook_path in args or h.get("command") == hook_path:
                        removed += 1
                    else:
                        kept.append(h)
                g["hooks"] = kept
            groups[:] = [g for g in groups if g.get("hooks")]
            if not groups:
                del hooks[event]
        if not hooks:
            data.pop("hooks", None)
    if removed:
        backup = settings_path.with_name(
            settings_path.name + ".bak-undo-" + time.strftime("%Y%m%d-%H%M%S")
        )
        shutil.copy2(settings_path, backup)
        settings_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        return f"removed {removed} entries for this checkout (backup: {backup.name})"
    return "no entries for this checkout were wired"


def _purge_runtime() -> list:
    """Delete ~/.claude/buddy, existence-verified. Returns problems."""
    target = Path.home() / ".claude" / "buddy"
    shutil.rmtree(target, ignore_errors=True)
    if target.exists():
        return ["could not fully remove ~/.claude/buddy (files in use?)"]
    print("  removed: ~/.claude/buddy (state, config, caches)")
    return []


def _external_steps() -> tuple:
    """Stop this checkout's buddy and remove its hook wiring - each step
    result-verified, never assumed.

    Shared by every undo path: hooks or a live buddy can outlast the
    repository files, so the teardown must not depend on how the tree
    itself looks. Returns (problems, stop_ok, unhook_ok). Purging is
    deliberately NOT here - each path runs it via _purge_gated at its
    own safe moment (after unhook verifies; after a legacy restore).
    """
    problems: list = []
    stop_ok, stop_msg = _stop_buddy()
    print(f"  {stop_msg}")
    if not stop_ok:
        problems.append(f"buddy stop unconfirmed: {stop_msg}")
    unhook_ok = True
    try:
        print(f"  unhook: {_unhook_this_checkout()}")
    except Exception as e:
        unhook_ok = False
        problems.append(f"unhook failed: {e}")
    return problems, stop_ok, unhook_ok


def _purge_gated(purge_data: bool, stop_ok: bool, unhook_ok: bool) -> list:
    """Purge runtime data only when every prerequisite verified.

    A live buddy would half-survive the purge in memory, and a failed
    unhook would revive the buddy against fresh default state - so both
    must be confirmed first. Returns problems.
    """
    if not purge_data:
        return []
    if not stop_ok:
        return ["purge skipped: the buddy could not be confirmed stopped"]
    if not unhook_ok:
        return ["purge skipped: the hook removal did not verify"]
    return _purge_runtime()


def undo(purge_data: bool, force: bool) -> int:
    """Reverse the apply, verified against the manifest.

    Repository restoration runs on any OS. The external side effects
    (stopping the buddy, unhooking, purging data) are scoped to this
    checkout and, off macOS, require --force — so undoing a test copy
    can never touch the installation you actually use.
    """
    external_ok = sys.platform == "darwin" or force
    problems: list = []
    notes: list = []

    copies_present = [n for n in _MANAGED_COPIES if (SCRIPTS / n).is_file()]
    markers_present = []
    for p in PATCHES:
        try:
            if p["file"].is_file() and p["marker"] in p["file"].read_text(encoding="utf-8"):
                markers_present.append(p["name"])
        except OSError:
            pass

    if not BACKUP.is_dir() and not markers_present and not copies_present:
        # the repo already looks stock, but hooks or a live buddy can
        # outlast the files - the external teardown still runs
        print("nothing to undo in the repository: the tree already looks stock.")
        if external_ok:
            ext, stop_ok, unhook_ok = _external_steps()
            problems += ext
            problems += _purge_gated(purge_data, stop_ok, unhook_ok)
        else:
            print("  stop/unhook/purge were skipped on this non-macOS system")
            print("  (use --force to include them)")
        if problems:
            print("\nundo finished with problems:")
            for why in problems:
                print(f"    {why}")
            return 1
        return 0

    if not MANIFEST.is_file():
        if not markers_present and not copies_present:
            # a leftover backup folder next to a stock-looking tree; the
            # external teardown still runs (see above)
            print("the tree already looks stock; scripts_backup_macos/ is kept")
            print("(it may hold preserved *.prev files) - delete it by hand")
            print("when you no longer need it.")
            if external_ok:
                ext, stop_ok, unhook_ok = _external_steps()
                problems += ext
                problems += _purge_gated(purge_data, stop_ok, unhook_ok)
            else:
                print("  stop/unhook/purge were skipped on this non-macOS system")
                print("  (use --force to include them)")
            if problems:
                print("\nundo finished with problems:")
                for why in problems:
                    print(f"    {why}")
                return 1
            return 0
        # applied by an older scaffold: there is no baseline to compare
        # against, so FIRST preserve everything the tree currently holds,
        # then restore best-effort - and never claim a verified success
        print("no manifest found (applied by an older scaffold version).")
        try:
            for name in (*_MANAGED_SOURCES, *_MANAGED_COPIES):
                p = SCRIPTS / name
                if not p.is_file():
                    continue
                # skip files identical to a known reference: the stored
                # original for sources, this folder's scaffold for copies
                ref = (BACKUP / name) if name in _MANAGED_SOURCES else (HERE / name)
                if ref.is_file() and _sha(ref) == _sha(p):
                    continue
                print(f"  preserved: {_save_prev(p).relative_to(ROOT)}")
        except OSError as e:
            print(f"could not preserve the current files ({e}) - refusing to")
            print("touch anything. Nothing was modified.")
            return 1
        ext_problems: list = []
        stop_ok = unhook_ok = True
        if external_ok:
            ext_problems, stop_ok, unhook_ok = _external_steps()
        else:
            print("  stop/unhook/purge were skipped on this non-macOS system")
            print("  (use --force to include them)")
        try:
            if BACKUP.is_dir():
                for name in _MANAGED_SOURCES:
                    keep = BACKUP / name
                    if keep.is_file():
                        shutil.copy2(keep, SCRIPTS / name)
                        print(f"  restored: scripts/{name}")
            for name in _MANAGED_COPIES:
                p = SCRIPTS / name
                if p.is_file():
                    p.unlink()
                    print(f"  removed: scripts/{name}")
        except OSError as e:
            # note the order: the purge has NOT run yet, so a failed
            # restore never costs the runtime data as well
            print(f"legacy restore hit an error ({e}) - the tree may be partial,")
            print("but every pre-undo file is preserved as *.prev in")
            print("scripts_backup_macos/. Fix the cause and re-run --undo.")
            print("(runtime data was left untouched)")
            return 1
        if external_ok:
            ext_problems += _purge_gated(purge_data, stop_ok, unhook_ok)
        if ext_problems:
            print("problems during the external steps:")
            for why in ext_problems:
                print(f"    {why}")
        print("best-effort restore done; the pre-undo files were preserved as")
        print("*.prev in scripts_backup_macos/ (kept). Completeness cannot be")
        print("verified without a manifest - please check scripts/ by hand.")
        return 1

    try:
        originals, applied, created = _read_manifest()
    except Exception as e:
        print(f"manifest rejected ({e}) - refusing to touch anything.")
        return 1

    # 1. the backup must be complete and intact BEFORE anything is touched
    broken = [
        n for n, h in originals.items()
        if not (BACKUP / n).is_file() or _sha(BACKUP / n) != h
    ]
    if broken:
        print("refusing to undo: the backup is incomplete or altered for:")
        for n in broken:
            print(f"    {n}")
        print("nothing was modified. Restore scripts_backup_macos/ (from git or")
        print("a fresh download) and run --undo again.")
        return 1

    # 2. preserve post-apply edits before they would be overwritten -
    #    and refuse to continue when preserving fails
    try:
        for name in (*originals.keys(), *created):
            p = SCRIPTS / name
            expected = applied.get(name)
            if p.is_file() and expected is not None:
                cur = _sha(p)
                if cur != expected and cur != originals.get(name):
                    print(f"  preserved your edits: {_save_prev(p).relative_to(ROOT)}")
    except OSError as e:
        print(f"could not preserve your edited files ({e}) - refusing to")
        print("continue. Nothing was restored.")
        return 1

    # 3. external side effects - scoped to this checkout, gated off macOS
    #    (purge waits until step 7: only a fully verified restore earns it)
    stop_ok = unhook_ok = True
    if external_ok:
        ext, stop_ok, unhook_ok = _external_steps()
        problems += ext
    else:
        notes.append(
            "stop/unhook/purge were skipped on this non-macOS system "
            "(use --force to include them)"
        )

    # 4. transactional restore of the repository files (contents,
    #    timestamps, modes AND absence all snapshot for a true rollback)
    snapshot = {}
    for name in (*originals.keys(), *created):
        p = SCRIPTS / name
        if p.is_file():
            st = p.stat()
            snapshot[p] = (p.read_bytes(), st.st_atime, st.st_mtime, st.st_mode)
        else:
            snapshot[p] = None  # sentinel: did not exist before the undo
    try:
        for name in originals:
            shutil.copy2(BACKUP / name, SCRIPTS / name)
            print(f"  restored: scripts/{name}")
        for name in created:
            p = SCRIPTS / name
            if p.is_file():
                p.unlink()
                print(f"  removed: scripts/{name}")
    except Exception as e:
        rb_errors = []
        for path, snap in snapshot.items():
            try:
                if snap is None:
                    if path.is_file():
                        path.unlink()  # the restore recreated it; put absence back
                    continue
                data, atime, mtime, mode = snap
                if not (path.is_file() and path.read_bytes() == data):
                    path.write_bytes(data)
                    if _sha(path) != hashlib.sha256(data).hexdigest():
                        rb_errors.append(f"{path.name}: content mismatch after write-back")
                # metadata goes back even when only mtime/mode drifted;
                # a write bit is needed for utime on Windows
                os.chmod(path, mode | 0o200)
                os.utime(path, (atime, mtime))
                os.chmod(path, mode)
            except OSError as err:
                rb_errors.append(f"{path.name}: {err}")
        print(f"\nrestore failed ({e}).")
        if rb_errors:
            print("rollback also hit errors - the tree may be inconsistent:")
            for why in rb_errors:
                print(f"    {why}")
            print("the pristine originals still live in scripts_backup_macos/.")
        else:
            print("repository files rolled back to the applied state (contents,")
            print("timestamps and modes); backup folder kept. Fix the cause and")
            print("re-run --undo.")
        return 1

    # 5. verify against the manifest hashes, not just syntax
    for name, h in originals.items():
        p = SCRIPTS / name
        if not p.is_file() or _sha(p) != h:
            problems.append(f"{name} does not match its original hash")
    for name in created:
        if (SCRIPTS / name).is_file():
            problems.append(f"{name} still present")
    for p in PATCHES:
        try:
            if p["file"].is_file() and p["marker"] in p["file"].read_text(encoding="utf-8"):
                problems.append(f"patch still present: {p['name']}")
        except OSError:
            pass
    for f in (BUDDY, HOOK, SCRIPTS / "window_pos.py"):
        try:
            with tempfile.TemporaryDirectory() as td:
                py_compile.compile(str(f), cfile=str(Path(td) / (f.name + "c")), doraise=True)
        except Exception as e:
            problems.append(f"{f.name}: {e}")

    if problems:
        print("\nundo finished with problems (backup folder kept):")
        for why in problems:
            print(f"    {why}")
        return 1

    # 6. clean up the backup folder - only when it is truly ours alone
    if BACKUP.is_dir():
        known = set(originals) | {MANIFEST.name}
        entries = list(BACKUP.iterdir())
        prevs = [e.name for e in entries if e.name.endswith(".prev")]
        unknown = sorted(
            e.name for e in entries
            if e.name not in known and not e.name.endswith(".prev")
        )
        if prevs:
            print("  keeping scripts_backup_macos/ - it holds preserved edits (*.prev)")
        if unknown:
            print("  keeping scripts_backup_macos/ - unexpected files inside: " + ", ".join(unknown))
        if not prevs and not unknown:
            shutil.rmtree(BACKUP, ignore_errors=True)
            if BACKUP.exists():
                print("  note: could not remove scripts_backup_macos/ - the restore")
                print("        itself is verified; delete the folder by hand")
            else:
                print("  removed: scripts_backup_macos/ (restore verified, no longer needed)")
    for cache in (
        SCRIPTS / "__pycache__",
        SCRIPTS / "skins" / "__pycache__",
        HERE / "__pycache__",
        ROOT / "tests" / "__pycache__",
    ):
        shutil.rmtree(cache, ignore_errors=True)

    # 7. runtime data, last of all: only a confirmed stop, a verified
    #    unhook and a verified restore earn the destructive step
    if external_ok:
        problems += _purge_gated(purge_data, stop_ok, unhook_ok)

    if problems:
        print("\nundo finished with problems:")
        for why in problems:
            print(f"    {why}")
        return 1

    done = ["repository files verified back to stock"]
    if external_ok:
        done.append("this checkout's hook wiring removed")
        if purge_data:
            done.append("runtime data deleted")
    print("\nundo complete: " + "; ".join(done) + ".")
    for n in notes:
        print("note: " + n)
    print("if you wired a single project, also run:")
    print("  python3 scripts/install_hooks.py --uninstall --project <dir>")
    return 0


def plan() -> tuple[list, list, list]:
    """Return (to_apply, already_applied, failed) without writing anything."""
    to_apply, done, failed = [], [], []
    texts = {}
    for p in PATCHES:
        f = p["file"]
        if f not in texts:
            try:
                texts[f] = f.read_text(encoding="utf-8")
            except OSError as e:
                failed.append((p["name"], f"cannot read {f.name}: {e}"))
                continue
        text = texts[f]
        if p["marker"] in text:
            done.append(p["name"])
        elif p["anchor"] in text:
            to_apply.append(p)
        else:
            failed.append((p["name"], f"anchor not found in {f.name}"))
    return to_apply, done, failed


def main() -> int:
    ap = argparse.ArgumentParser(description="Enable the macOS backends in place")
    ap.add_argument("--check", action="store_true", help="verify anchors only, write nothing")
    ap.add_argument(
        "--force", action="store_true",
        help="apply even when not on macOS; with --undo, also run the "
             "stop/unhook/purge steps off macOS",
    )
    ap.add_argument("--undo", action="store_true", help="reverse the apply: stop, unhook, restore")
    ap.add_argument(
        "--purge-data", action="store_true",
        help="with --undo: also delete ~/.claude/buddy (state, config, caches)",
    )
    args = ap.parse_args()

    if args.purge_data and not args.undo:
        print("--purge-data only makes sense together with --undo.")
        return 1
    if args.undo:
        return undo(args.purge_data, args.force)

    to_apply, done, failed = plan()
    for name in done:
        print(f"  already applied: {name}")
    for p in to_apply:
        print(f"  ready:           {p['name']}")
    for name, why in failed:
        # ASCII-only CLI output: a cp932 Windows console must never crash
        print(f"  FAILED:          {name} - {why}")

    if failed:
        print("\nNothing was written. This scaffold no longer matches the")
        print("sources (they may have moved on) - please open an issue.")
        return 1
    if args.check:
        print("\ncheck OK: every patch is either ready or already applied.")
        return 0
    if sys.platform != "darwin" and not args.force:
        print("\nThis machine is not macOS - refusing to modify the sources.")
        print("Use --check to verify, or --force if you really mean it.")
        return 1

    # every managed source must exist BEFORE anything is written: a
    # missing file would yield an incomplete backup/manifest, and a later
    # --undo could then never return the tree to stock
    missing = [n for n in _MANAGED_SOURCES if not (SCRIPTS / n).is_file()]
    if missing:
        print("\nRefusing to apply - missing from scripts/: " + ", ".join(missing))
        print("Nothing was written. Restore the stock sources first (from git")
        print("or a fresh download).")
        return 1

    # baseline guard: user edits must never be silently promoted into the
    # manifest baseline (a later --undo would then drop them)
    if MANIFEST.is_file():
        try:
            m_originals, m_applied, _ = _read_manifest()
        except Exception as e:
            print(f"\nRefusing to apply: the existing manifest is invalid ({e}).")
            print("Nothing was written. If you know scripts_backup_macos/ is")
            print("intact, delete its manifest.json and re-run.")
            return 1
        try:
            for name in _MANAGED_SOURCES:
                cur = _sha(SCRIPTS / name)
                if cur not in (m_applied[name], m_originals[name]):
                    prev = _save_prev(SCRIPTS / name)
                    print(f"  note: scripts/{name} was edited after the last apply -")
                    print(f"        kept as {prev.relative_to(ROOT)}")
        except OSError as e:
            print(f"\nRefusing to apply: could not preserve edited files ({e}).")
            print("Nothing was written.")
            return 1
    elif done or any((SCRIPTS / n).is_file() for n in _MANAGED_COPIES):
        # patched by an older scaffold (no manifest): the sources here have
        # unknown provenance, so preserve any that differ from the stored
        # originals before this run establishes a fresh baseline
        lost = [n for n in _MANAGED_SOURCES if not (BACKUP / n).is_file()]
        if done and lost:
            print("\nRefusing to apply: this tree was patched by an older scaffold")
            print("and its backup folder is missing: " + ", ".join(lost))
            print("Nothing was written. Restore the stock sources from git or a")
            print("fresh download, then apply again.")
            return 1
        try:
            for name in _MANAGED_SOURCES:
                p = SCRIPTS / name
                keep = BACKUP / name
                if keep.is_file() and _sha(keep) == _sha(p):
                    continue
                prev = _save_prev(p)
                print(f"  note: provenance of scripts/{name} is unknown (no")
                print(f"        manifest) - kept as {prev.relative_to(ROOT)}")
        except OSError as e:
            print(f"\nRefusing to apply: could not preserve current files ({e}).")
            print("Nothing was written.")
            return 1

    # ---- write phase (transactional: any failure rolls everything back) --
    BACKUP.mkdir(exist_ok=True)
    for target in {p["file"] for p in PATCHES} | {SCRIPTS / "window_pos.py"}:
        keep = BACKUP / target.name
        if target.is_file() and not keep.is_file():
            shutil.copy2(target, keep)
            print(f"  backup: {keep.relative_to(ROOT)}")

    # snapshot everything about to be touched (contents + timestamps),
    # including backup side-files, so rollback is a true undo
    pre: dict = {}
    created: list = []

    def _snap(path) -> None:
        if path.is_file():
            st = path.stat()
            pre[path] = (path.read_bytes(), st.st_atime, st.st_mtime, st.st_mode)
        elif path not in created:
            created.append(path)

    for _src, dst, _x in COPIES:
        _snap(dst)
    for f in {p["file"] for p in to_apply}:
        _snap(f)
    _snap(MANIFEST)  # a stale manifest must not survive a rollback

    try:
        for src, dst, make_x in COPIES:
            if dst in pre and pre[dst][0] != src.read_bytes():  # noqa: index 0 = bytes
                # keep the overwritten content as *.prev, but only when it
                # is not already preserved (the pristine original lives in
                # the once-backup; only a locally MODIFIED copy needs this)
                keep = BACKUP / dst.name
                already_saved = keep.is_file() and keep.read_bytes() == pre[dst][0]
                if not already_saved:
                    # same numbering scheme as _save_prev: earlier .prev
                    # files from earlier re-applies are never overwritten
                    prev = BACKUP / (dst.name + ".prev")
                    n = 1
                    while prev.exists():
                        n += 1
                        prev = BACKUP / f"{dst.name}.{n}.prev"
                    _snap(prev)  # the side-file is part of the transaction too
                    prev.write_bytes(pre[dst][0])
                    if _sha(prev) != hashlib.sha256(pre[dst][0]).hexdigest():
                        raise OSError(f"verification failed while writing {prev.name}")
                    print(f"  note: {dst.relative_to(ROOT)} differed - kept as {prev.relative_to(ROOT)}")
            shutil.copy2(src, dst)
            if make_x:
                os.chmod(dst, 0o755)
            print(f"  copied: {dst.relative_to(ROOT)}")

        texts = {}
        for p in to_apply:
            f = p["file"]
            texts.setdefault(f, f.read_text(encoding="utf-8"))
            texts[f] = texts[f].replace(p["anchor"], p["replace"], 1)
            print(f"  patched: {p['name']}")
        for f, text in texts.items():
            f.write_text(text, encoding="utf-8")

        # compile into a scratch dir: verification must not litter .pyc files
        with tempfile.TemporaryDirectory() as td:
            for f in (BUDDY, HOOK, SCRIPTS / "window_pos.py", SCRIPTS / "mac_audio.py"):
                py_compile.compile(
                    str(f), cfile=str(Path(td) / (f.name + "c")), doraise=True
                )
        print("  syntax check: OK")

        # manifest: the ground truth --undo verifies against. Complete by
        # construction - a missing file is a hard failure that rolls the
        # whole run back, never a silently smaller manifest
        MANIFEST.write_text(
            json.dumps(
                {
                    "version": 1,
                    "originals": {n: _sha(BACKUP / n) for n in _MANAGED_SOURCES},
                    "applied": {
                        n: _sha(SCRIPTS / n)
                        for n in (*_MANAGED_SOURCES, *_MANAGED_COPIES)
                    },
                    "created": list(_MANAGED_COPIES),
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        print("  manifest: written")
    except Exception as e:
        print(f"\n  FAILED mid-write: {e}")
        problems = []
        for path, (data, atime, mtime, mode) in pre.items():
            try:
                path.write_bytes(data)
                os.chmod(path, mode)
                os.utime(path, (atime, mtime))
            except OSError as err:
                problems.append(f"{path.name}: {err}")
        for path in created:
            try:
                if path.is_file():
                    path.unlink()
            except OSError as err:
                problems.append(f"{path.name}: {err}")
        if problems:
            print("  rollback had errors: " + "; ".join(problems))
            print("  pristine originals also live in scripts_backup_macos/")
        else:
            print(
                "  rolled back: managed files restored to their pre-run state"
                " (contents and timestamps)."
            )
        return 1

    print(
        "\nDone. Next steps:\n"
        "  1. optional window-following:  python3 -m pip install pyobjc-framework-Quartz\n"
        "     (without it the buddy parks in the desktop corner automatically)\n"
        "  2. run the suite:              python3 -B tests/test_units.py\n"
        "  3. wire the hooks:             python3 scripts/install_hooks.py\n"
        "  4. start:                      ./scripts/start_buddy.sh\n"
        "Undo everything later with:      python3 experimental/macos/apply.py --undo"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
