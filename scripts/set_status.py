#!/usr/bin/env python3
"""Manually set MadoMochi's mood (demo / testing)."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from session_state import chmod_private, ensure_private_dir

BUDDY_DIR = Path(os.environ.get("CLAUDE_BUDDY_DIR", Path.home() / ".claude" / "madomochi"))
DEFAULT_STATUS = Path(os.environ.get("CLAUDE_BUDDY_STATUS", BUDDY_DIR / "status.json"))

MOODS = ("idle", "listen", "think", "work", "happy", "error", "alert", "sleep")


def main() -> int:
    parser = argparse.ArgumentParser(description="Update MadoMochi status")
    parser.add_argument("--mood", choices=MOODS, default="idle")
    parser.add_argument("--message", default="")
    parser.add_argument("--tool", default="")
    parser.add_argument("--path", default=str(DEFAULT_STATUS))
    args = parser.parse_args()

    path = Path(args.path)
    if path.parent == BUDDY_DIR:
        ensure_private_dir(BUDDY_DIR)
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "mood": args.mood,
        "message": args.message,
        "tool": args.tool,
        "event": "manual",
        "updatedAt": datetime.now(timezone.utc).isoformat(),
    }
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    chmod_private(tmp)
    last_error = None
    for _ in range(4):
        try:
            tmp.replace(path)
            chmod_private(path)
            break
        except OSError as exc:
            last_error = exc
            time.sleep(0.03)
    else:
        try:
            tmp.unlink()
        except OSError:
            pass
        print(f"could not update {path}: {last_error}", file=sys.stderr)
        return 1
    print(f"{args.mood} -> {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
