#!/usr/bin/env python3
"""Manually set MadoMochi's mood (demo / testing)."""

from __future__ import annotations

import argparse
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

BUDDY_DIR = Path(os.environ.get("CLAUDE_BUDDY_DIR", Path.home() / ".claude" / "buddy"))
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
    for _ in range(4):
        try:
            tmp.replace(path)
            break
        except PermissionError:
            time.sleep(0.03)
    print(f"{args.mood} -> {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
