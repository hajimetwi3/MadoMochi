"""Locate the Claude Code desktop-app window and compute buddy placement.

Uses ctypes directly so window tracking never waits on a subprocess.
"""

from __future__ import annotations

import ctypes
import time
from ctypes import wintypes
from typing import NamedTuple

BUDDY_TITLE = "MadoMochi"

PROCESS_QUERY_LIMITED_INFORMATION = 0x1000

# cache the matched window so the frequent follow tick avoids a full
# EnumWindows sweep; a full rescan still happens on invalidation or every 10s
_cached_hwnd: int | None = None
_last_scan = 0.0
RESCAN_SEC = 10.0


class RECT(ctypes.Structure):
    _fields_ = [
        ("left", ctypes.c_long),
        ("top", ctypes.c_long),
        ("right", ctypes.c_long),
        ("bottom", ctypes.c_long),
    ]


class WinRect(NamedTuple):
    left: int
    top: int
    right: int
    bottom: int

    @property
    def width(self) -> int:
        return self.right - self.left

    @property
    def height(self) -> int:
        return self.bottom - self.top


user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)


def _proc_name(pid: int) -> str:
    """Executable basename (lowercase) for a pid, via ctypes only."""
    h = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not h:
        return ""
    try:
        buf = ctypes.create_unicode_buffer(1024)
        size = wintypes.DWORD(1024)
        if kernel32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size)):
            return buf.value.replace("/", "\\").rsplit("\\", 1)[-1].lower()
        return ""
    finally:
        kernel32.CloseHandle(h)


def _title_of(hwnd: int) -> str:
    length = user32.GetWindowTextLengthW(hwnd)
    if length <= 0:
        return ""
    buf = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buf, length + 1)
    return buf.value


def _valid_rect(hwnd: int) -> WinRect | None:
    r = RECT()
    if not user32.GetWindowRect(hwnd, ctypes.byref(r)):
        return None
    if r.right - r.left < 400 or r.bottom - r.top < 250:
        return None
    return WinRect(r.left, r.top, r.right, r.bottom)


def find_claude_window() -> WinRect | None:
    """
    Find the best window that hosts Claude Code.

    Preference:
    1. The desktop app: process claude.exe, window title "Claude"
    2. A terminal window whose title mentions claude (CLI usage)
    """
    global _cached_hwnd, _last_scan

    now = time.monotonic()
    h = _cached_hwnd
    if h and now - _last_scan < RESCAN_SEC:
        if (
            user32.IsWindow(h)
            and user32.IsWindowVisible(h)
            and not user32.IsIconic(h)
            and "claude" in _title_of(h).lower()
        ):
            rect = _valid_rect(h)
            if rect is not None:
                return rect
        _cached_hwnd = None

    _last_scan = now
    candidates: list[tuple[int, int, WinRect, str, str]] = []

    def cb(hwnd, _lparam):
        if not user32.IsWindowVisible(hwnd) or user32.IsIconic(hwnd):
            return True
        title = _title_of(hwnd)
        if not title or title == BUDDY_TITLE:
            return True
        rect = _valid_rect(hwnd)
        if rect is None:
            return True
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        candidates.append((hwnd, pid.value, rect, title, _proc_name(pid.value)))
        return True

    user32.EnumWindows(EnumWindowsProc(cb), 0)

    scored: list[tuple[int, WinRect, int]] = []
    for hwnd, _pid, rect, title, pname in candidates:
        low = title.lower()
        score = 0
        if "claude" in low:
            score += 100
        if low == "claude":
            score += 50
        if pname in {"claude.exe", "claude"}:
            score += 80
        area = rect.width * rect.height
        score += min(area // 50000, 20)
        if score >= 100:
            scored.append((score, rect, hwnd))

    if not scored:
        for hwnd, _pid, rect, title, pname in candidates:
            if pname in {"claude.exe", "claude"}:
                scored.append((50, rect, hwnd))

    if not scored:
        _cached_hwnd = None
        return None
    scored.sort(key=lambda x: x[0], reverse=True)
    _cached_hwnd = scored[0][2]
    return scored[0][1]


def place_bottom_right_of_claude(
    buddy_w: int,
    buddy_h: int,
    *,
    margin_x: int = 24,
    margin_above_prompt: int = 96,
) -> tuple[int, int] | None:
    """
    Placement: inside the Claude window, bottom-right, just above the prompt box.

    Returns (x, y) for the buddy top-left, or None when no Claude window exists.
    """
    rect = find_claude_window()
    if rect is None:
        return None

    x = rect.right - buddy_w - margin_x
    y = rect.bottom - buddy_h - margin_above_prompt

    # clamp inside the Claude window
    x = max(rect.left + 4, min(x, rect.right - buddy_w - 4))
    y = max(rect.top + 4, min(y, rect.bottom - buddy_h - 4))
    return int(x), int(y)
