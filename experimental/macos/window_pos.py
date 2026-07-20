"""
macOS window tracking for MadoMochi — UNTESTED, written on Windows.

Same public surface as scripts/window_pos.py:

    BUDDY_TITLE
    place_bottom_right_of_claude(w, h, margin_x=..., margin_above_prompt=...)

Design (review-hardened):
- Full window-list sweeps run at most every RESCAN_SEC to find the
  Claude window and remember its kCGWindowNumber.
- Once a window is tracked, its bounds are re-read on EVERY call via
  CGWindowListCreateDescriptionFromArray — cheap, so window-following
  moves at the caller's cadence (~250ms) instead of the sweep interval.
- Owner-name matching only (window titles would need the screen
  recording permission; owner names do not).
- Without pyobjc, always returns None: pair with corner parking
  (`park_when_hidden: true`) for a dependency-free setup.
- Diagnostics (privacy-tiered, printed to stderr — note that
  start_buddy.sh discards stderr, so run `python3 scripts/buddy.py`
  from a terminal to actually see it):
    MADOMOCHI_MAC_DEBUG=1    print only Claude-matching windows plus a
                             scanned-count summary
    MADOMOCHI_MAC_DEBUG=all  print EVERY window's owner/bounds (the
                             sweep completes the whole list even after
                             a match). This is your full list of
                             running apps: local debugging only
    unset / 0 / false / off  disabled
"""

from __future__ import annotations

import os
import sys
import time

BUDDY_TITLE = "MadoMochi"

try:
    from Quartz import (  # type: ignore
        CGWindowListCopyWindowInfo,
        CGWindowListCreateDescriptionFromArray,
        kCGNullWindowID,
        kCGWindowListExcludeDesktopElements,
        kCGWindowListOptionOnScreenOnly,
    )

    HAVE_QUARTZ = True
except Exception:
    HAVE_QUARTZ = False

RESCAN_SEC = 2.0
_DEBUG = os.environ.get("MADOMOCHI_MAC_DEBUG", "").strip().lower()
if _DEBUG in ("0", "false", "off", "no"):
    _DEBUG = ""
_state = {"scan_at": 0.0, "wid": None, "rect": None}


def _rect_of(info) -> tuple | None:
    b = info.get("kCGWindowBounds") or {}
    rect = (
        int(b.get("X", 0)),
        int(b.get("Y", 0)),
        int(b.get("Width", 0)),
        int(b.get("Height", 0)),
    )
    if rect[2] < 200 or rect[3] < 200:
        return None  # tool palettes and other small windows
    return rect


def _full_scan() -> None:
    """Sweep all windows for a normal-layer Claude window."""
    _state["wid"] = None
    _state["rect"] = None
    try:
        wins = CGWindowListCopyWindowInfo(
            kCGWindowListOptionOnScreenOnly | kCGWindowListExcludeDesktopElements,
            kCGNullWindowID,
        ) or []
    except Exception:
        return
    for w in wins:
        owner = str(w.get("kCGWindowOwnerName", "")).lower()
        # privacy tiers: "1" shows Claude-matching windows only;
        # "all" dumps every owner = the user's full app list
        if _DEBUG == "all" or (_DEBUG and "claude" in owner):
            print(
                f"[madomochi] owner={owner!r} layer={w.get('kCGWindowLayer')} "
                f"bounds={dict(w.get('kCGWindowBounds') or {})}",
                file=sys.stderr,
            )
        if _state["wid"] is not None:
            continue  # found already; still iterating so =all stays complete
        if "claude" not in owner or owner == "madomochi":
            continue
        if int(w.get("kCGWindowLayer", 0)) != 0:
            continue  # menus / status items / overlays
        rect = _rect_of(w)
        if rect is None:
            continue
        _state["wid"] = w.get("kCGWindowNumber")
        _state["rect"] = rect
        if _DEBUG != "all":
            return  # =all keeps printing the rest of the list
    if _DEBUG and _DEBUG != "all" and _state["wid"] is None:
        print(
            f"[madomochi] scanned {len(wins)} windows, no Claude match; "
            "other owners omitted (MADOMOCHI_MAC_DEBUG=all shows them - "
            "local debugging only, do not paste that publicly)",
            file=sys.stderr,
        )


def _find_claude_rect():
    """(x, y, w, h) of the tracked Claude window, or None."""
    if not HAVE_QUARTZ:
        return None
    wid = _state["wid"]
    if wid is not None:
        # cheap per-call refresh: only the tracked window is queried, and
        # its identity is revalidated (window numbers can be reused, and a
        # minimized/other-Space window must not keep its stale bounds)
        try:
            infos = CGWindowListCreateDescriptionFromArray([wid]) or []
        except Exception:
            infos = []
        if infos:
            info = infos[0]
            owner = str(info.get("kCGWindowOwnerName", "")).lower()
            onscreen = info.get("kCGWindowIsOnscreen")
            if (
                "claude" in owner
                and int(info.get("kCGWindowLayer", 0)) == 0
                and (onscreen is None or bool(onscreen))
            ):
                rect = _rect_of(info)
                if rect is not None:
                    _state["rect"] = rect
                    return rect
        _state["wid"] = None  # gone / minimized / reused -> force a sweep
    now = time.time()
    if now - _state["scan_at"] >= RESCAN_SEC:
        _state["scan_at"] = now
        _full_scan()
    return _state["rect"] if _state["wid"] is not None else None


def place_bottom_right_of_claude(w, h, margin_x=24, margin_above_prompt=96):
    """Top-left position for a w*h buddy window, or None when Claude is gone.

    Quartz global coordinates may be negative on multi-display setups
    (displays left/above the main one); Tk's "+{x}+{y}" accepts negative
    values with the + prefix, so they pass through unchanged.
    """
    rect = _find_claude_rect()
    if rect is None:
        return None
    cx, cy, cw, ch = rect
    return cx + cw - w - margin_x, cy + ch - h - margin_above_prompt
