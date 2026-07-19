#!/usr/bin/env python3
"""
Install (or uninstall) MadoMochi hooks in a Claude Code settings.json.

The canonical hook wiring lives in install.settings/settings.template.json
with {{PYTHON}} / {{HOOK_ENTRY}} placeholders; this script resolves them for
the current machine and merges the result into the target settings file.

Default target is the user-global ~/.claude/settings.json so the buddy reacts
in every project. Use --project <dir> to target <dir>/.claude/settings.json
instead, and --uninstall to remove every buddy hook while leaving the rest of
the file untouched. Existing settings are preserved; a timestamped .bak is
written first. Changes take effect from the next Claude Code session.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HOOK_SCRIPT = Path(__file__).resolve().parent / "hook_entry.py"
TEMPLATE = ROOT / "install.settings" / "settings.template.json"


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


def scrub_buddy_hooks(settings: dict) -> None:
    """Strip every buddy hook from a settings dict, in place.

    Cleans ALL events (the template may have dropped some since the last
    install), drops emptied groups/events, and removes an emptied top-level
    "hooks" key entirely. Everything else in the file is left untouched.
    """
    hooks = settings.get("hooks")
    if not isinstance(hooks, dict):
        return
    for event in list(hooks):
        groups = hooks[event]
        for g in groups:
            g["hooks"] = [h for h in g.get("hooks", []) if not _is_buddy_hook(h)]
        groups[:] = [g for g in groups if g.get("hooks")]
        if not groups:
            del hooks[event]
    if not hooks:
        settings.pop("hooks", None)


def _load_with_backup(settings_path: Path) -> dict:
    settings = json.loads(settings_path.read_text(encoding="utf-8"))
    backup = settings_path.with_name(
        settings_path.name + ".bak-" + datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    )
    backup.write_text(settings_path.read_text(encoding="utf-8"), encoding="utf-8")
    print(f"backup: {backup}")
    return settings


def _save(settings_path: Path, settings: dict) -> None:
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings_path.write_text(
        json.dumps(settings, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def install(settings_path: Path) -> None:
    if not HOOK_SCRIPT.is_file():
        raise SystemExit(f"hook_entry.py not found: {HOOK_SCRIPT}")
    tmpl_hooks = render_template()["hooks"]

    settings: dict = {}
    if settings_path.is_file():
        settings = _load_with_backup(settings_path)

    scrub_buddy_hooks(settings)
    hooks = settings.setdefault("hooks", {})
    for event, tmpl_groups in tmpl_hooks.items():
        hooks.setdefault(event, []).extend(tmpl_groups)

    _save(settings_path, settings)
    print(f"installed buddy hooks -> {settings_path}")
    print("hooks take effect from the NEXT Claude Code session")


def uninstall(settings_path: Path) -> None:
    if not settings_path.is_file():
        print(f"nothing to uninstall: {settings_path} not found")
        return
    settings = _load_with_backup(settings_path)
    scrub_buddy_hooks(settings)
    _save(settings_path, settings)
    print(f"removed buddy hooks <- {settings_path}")
    print("sessions that are already open keep their loaded hooks until they end")


def main() -> int:
    parser = argparse.ArgumentParser(description="Install/uninstall MadoMochi hooks")
    parser.add_argument(
        "--project",
        metavar="DIR",
        help="target DIR/.claude/settings.json instead of ~/.claude/settings.json",
    )
    parser.add_argument(
        "--uninstall",
        action="store_true",
        help="remove the buddy hooks instead of installing them",
    )
    args = parser.parse_args()
    if args.project:
        target = Path(args.project).resolve() / ".claude" / "settings.json"
    else:
        target = Path.home() / ".claude" / "settings.json"
    if args.uninstall:
        uninstall(target)
    else:
        install(target)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
