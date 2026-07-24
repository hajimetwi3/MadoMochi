#!/usr/bin/env python3
"""
Install (or uninstall) MadoMochi hooks in Claude Code settings.

The canonical hook wiring lives in install.settings/settings.template.json
with {{PYTHON}} / {{HOOK_ENTRY}} placeholders; this script resolves them for
the current machine and merges the result into the target settings file.

Default target is the user-global ~/.claude/settings.json so the buddy reacts
in every project. Use --project <dir> to target the machine-local
<dir>/.claude/settings.local.json instead. A project install also removes old
MadoMochi wiring from the shared .claude/settings.json, so upgrades need no
old checkout. Everything else is preserved. Before a changed settings file is
saved atomically, a timestamped backup is kept outside the repository.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HOOK_SCRIPT = Path(__file__).resolve().parent / "hook_entry.py"
TEMPLATE = ROOT / "install.settings" / "settings.template.json"
BACKUP_ROOT = Path(
    os.environ.get(
        "MADOMOCHI_SETTINGS_BACKUP_DIR",
        Path.home() / ".claude" / "madomochi_backups",
    )
)
BACKUP_KEEP = 5
_NO_EXPECTATION = object()


def _python_exe() -> str:
    """Prefer pythonw.exe (windowless) next to the running interpreter."""
    py = Path(sys.executable)
    if py.name.lower() == "pythonw.exe":
        return str(py)
    pyw = py.with_name("pythonw.exe")
    return str(pyw if pyw.is_file() else py)


# the one marker every install of this software carries; deliberately
# author-prefixed so no other product would plausibly use the same flag
_MARKER = "--hajimetwi3-buddy-hook"


def _is_buddy_hook(h: dict) -> bool:
    """Identify OUR wiring only — another product's hooks must survive.

    Every check is an exact-element comparison (never substring), and only
    unambiguous identifiers count: the author-prefixed marker, the raw
    template placeholder, or this repo's exact hook_entry.py path.
    """
    command = str(h.get("command", ""))
    args = [str(a) for a in h.get("args", [])]
    if _MARKER in args:
        return True
    if "{{HOOK_ENTRY}}" in args or "{{HOOK_ENTRY}}" == command:
        return True
    hook_path = str(HOOK_SCRIPT)
    return command == hook_path or hook_path in args


def render_template() -> dict:
    raw = TEMPLATE.read_text(encoding="utf-8")
    # json.dumps()[1:-1] gives properly JSON-escaped path text (backslashes!)
    raw = raw.replace("{{PYTHON}}", json.dumps(_python_exe())[1:-1])
    raw = raw.replace("{{HOOK_ENTRY}}", json.dumps(str(HOOK_SCRIPT))[1:-1])
    return json.loads(raw)


def scrub_buddy_hooks(settings: dict) -> int:
    """Strip every buddy hook from a settings dict, in place.

    Cleans ALL events (the template may have dropped some since the last
    install), drops emptied groups/events, and removes an emptied top-level
    "hooks" key entirely. Everything else in the file is left untouched.
    """
    removed = 0
    hooks = settings.get("hooks")
    if not isinstance(hooks, dict):
        return 0
    for event in list(hooks):
        groups = hooks[event]
        for g in groups:
            old = g.get("hooks", [])
            kept = [h for h in old if not _is_buddy_hook(h)]
            removed += len(old) - len(kept)
            g["hooks"] = kept
        groups[:] = [g for g in groups if g.get("hooks")]
        if not groups:
            del hooks[event]
    if not hooks:
        settings.pop("hooks", None)
    return removed


def _chmod_private(path: Path, mode: int) -> None:
    """Best-effort POSIX privacy; Windows ACLs remain authoritative there."""
    if os.name != "nt":
        os.chmod(path, mode)


def _backup_bytes(settings_path: Path, raw: bytes) -> Path:
    """Keep a bounded private backup outside a project working tree."""
    key = hashlib.sha256(
        str(settings_path.resolve()).encode("utf-8", "surrogatepass")
    ).hexdigest()[:16]
    bucket = BACKUP_ROOT / key
    BACKUP_ROOT.mkdir(parents=True, exist_ok=True, mode=0o700)
    bucket.mkdir(exist_ok=True, mode=0o700)
    _chmod_private(BACKUP_ROOT, 0o700)
    _chmod_private(bucket, 0o700)

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    backup = bucket / f"{settings_path.name}.{stamp}.bak"
    fd = os.open(backup, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as f:
        f.write(raw)
        f.flush()
        os.fsync(f.fileno())
    _chmod_private(backup, 0o600)

    # The bucket name is intentionally opaque; this private note makes a
    # manual recovery understandable without putting machine paths in Git.
    note = bucket / "target.txt"
    fd = os.open(note, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
        f.write(str(settings_path.resolve()) + "\n")
    _chmod_private(note, 0o600)

    backups = sorted(bucket.glob(f"{settings_path.name}.*.bak"), reverse=True)
    for old in backups[BACKUP_KEEP:]:
        old.unlink()
    print(f"backup: {backup}")
    return backup


def _load_with_backup(settings_path: Path) -> tuple[dict, bytes]:
    raw = settings_path.read_bytes()
    settings = json.loads(raw.decode("utf-8"))
    _backup_bytes(settings_path, raw)
    return settings, raw


def _save(
    settings_path: Path,
    settings: dict,
    *,
    private: bool = True,
    expected_raw=_NO_EXPECTATION,
) -> None:
    """Atomically save unless another process changed the file meanwhile."""
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    old_mode = None
    if settings_path.is_file():
        old_mode = stat.S_IMODE(settings_path.stat().st_mode)
    tmp = settings_path.with_name(
        f".{settings_path.name}.madomochi-{os.getpid()}-{time.time_ns()}.tmp"
    )
    try:
        mode = 0o600 if private else (old_mode or 0o644)
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(settings, ensure_ascii=False, indent=2) + "\n")
            f.flush()
            os.fsync(f.fileno())
        if os.name != "nt":
            os.chmod(tmp, mode)
        if expected_raw is not _NO_EXPECTATION:
            try:
                current_raw = settings_path.read_bytes()
            except FileNotFoundError:
                current_raw = None
            if current_raw != expected_raw:
                raise RuntimeError(
                    "settings changed during this operation; no update was written: "
                    f"{settings_path}"
                )
        os.replace(tmp, settings_path)
        if private:
            _chmod_private(settings_path, 0o600)
    finally:
        try:
            if tmp.is_file():
                tmp.unlink()
        except OSError:
            pass


def _remove_from_file(settings_path: Path, *, private: bool, label: str) -> int:
    """Remove only MadoMochi entries, saving only when something changed."""
    if not settings_path.is_file():
        return 0
    raw = settings_path.read_bytes()
    settings = json.loads(raw.decode("utf-8"))
    removed = scrub_buddy_hooks(settings)
    if not removed:
        return 0
    _backup_bytes(settings_path, raw)
    _save(settings_path, settings, private=private, expected_raw=raw)
    print(f"{label}: removed {removed} MadoMochi hook(s) <- {settings_path}")
    return removed


def install(settings_path: Path) -> None:
    if not HOOK_SCRIPT.is_file():
        raise SystemExit(f"hook_entry.py not found: {HOOK_SCRIPT}")
    tmpl_hooks = render_template()["hooks"]

    settings: dict = {}
    expected_raw = None
    if settings_path.is_file():
        settings, expected_raw = _load_with_backup(settings_path)

    scrub_buddy_hooks(settings)
    hooks = settings.setdefault("hooks", {})
    for event, tmpl_groups in tmpl_hooks.items():
        hooks.setdefault(event, []).extend(tmpl_groups)

    _save(settings_path, settings, expected_raw=expected_raw)
    print(f"installed buddy hooks -> {settings_path}")
    print("hook changes usually apply to running sessions right away (new session if not)")


def uninstall(settings_path: Path) -> None:
    if not settings_path.is_file():
        print(f"nothing to uninstall: {settings_path} not found")
        return
    removed = _remove_from_file(
        settings_path,
        private=True,
        label="uninstall",
    )
    if not removed:
        print(f"nothing to uninstall: no MadoMochi hooks in {settings_path}")
        return
    print("removal usually applies to running sessions right away (restart them if hooks linger)")


def install_project(project: Path) -> None:
    """Migrate old shared wiring, then install machine-local wiring."""
    claude_dir = project.resolve() / ".claude"
    shared = claude_dir / "settings.json"
    local = claude_dir / "settings.local.json"
    _remove_from_file(
        shared,
        private=False,
        label="migrated shared project settings",
    )
    install(local)


def uninstall_project(project: Path) -> None:
    """Remove both current local wiring and historical shared wiring."""
    claude_dir = project.resolve() / ".claude"
    shared = claude_dir / "settings.json"
    local = claude_dir / "settings.local.json"
    removed_shared = _remove_from_file(
        shared,
        private=False,
        label="cleaned legacy shared project settings",
    )
    if local.is_file():
        uninstall(local)
    elif not removed_shared:
        print(f"nothing to uninstall: {local} not found")


def main() -> int:
    parser = argparse.ArgumentParser(description="Install/uninstall MadoMochi hooks")
    parser.add_argument(
        "--project",
        metavar="DIR",
        help="target DIR/.claude/settings.local.json instead of ~/.claude/settings.json",
    )
    parser.add_argument(
        "--uninstall",
        action="store_true",
        help="remove the buddy hooks instead of installing them",
    )
    args = parser.parse_args()
    if args.project:
        project = Path(args.project).resolve()
        if args.uninstall:
            uninstall_project(project)
        else:
            install_project(project)
    else:
        target = Path.home() / ".claude" / "settings.json"
        if args.uninstall:
            uninstall(target)
        else:
            install(target)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
