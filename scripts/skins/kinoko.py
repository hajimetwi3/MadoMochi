"""Kinoko — a red-capped mushroom kid with a face on the stem."""

from __future__ import annotations

import importlib.util as _ilu
from pathlib import Path as _Path

_spec = _ilu.spec_from_file_location("buddy_skin__base", _Path(__file__).resolve().parent / "_base.py")
_b = _ilu.module_from_spec(_spec)
_spec.loader.exec_module(_b)

NAME = "キノコ"
NAME_EN = "Mushroom"
PALETTE = _b.std_palette("#f2e8d5", "#f9f3e8", "#b8a17a", "#d9c8a8", "#877f6f",
                         ["#e05656", "#b83e3e"])  # 17 cap, 18 cap shade
CAP, CAPD = 17, 18


def _draw(buf, p):
    oy = p.bob
    R, H, P2 = _b.rect2, _b.hline2, _b.plot2

    # cap
    tw = 1 if p.twitch else 0   # the cap wobbles instead of an ear twitch
    H(buf, 12 + tw, 19 + tw, 9 + oy, CAP)
    H(buf, 10, 21, 10 + oy, CAP)
    for y in range(11, 16):
        H(buf, 8, 23, y + oy, CAP)
    H(buf, 9, 22, 16 + oy, CAPD)
    R(buf, 10, 11 + oy, 11, 12 + oy, 6)
    R(buf, 16, 10 + oy, 17, 11 + oy, 6)
    R(buf, 20, 13 + oy, 21, 14 + oy, 6)

    # stem with face
    R(buf, 12, 17 + oy, 19, 25 + oy, 1)
    H(buf, 13, 18, 26 + oy, 1)

    # stub arms
    def arm(side, mode):
        s = -1 if side == "l" else 1
        x0 = 10 if s < 0 else 20
        if mode == "rest":
            return
        if mode == "raise":
            R(buf, x0, 19 + oy, x0 + 1, 20 + oy, 1)
        elif mode == "up":
            R(buf, x0, 17 + oy, x0 + 1, 20 + oy, 1)
        elif mode == "hold_lo":
            R(buf, x0, 21 + oy, x0 + 1, 22 + oy, 1)
        elif mode == "type_hi":
            R(buf, x0 + s * 2, 20 + oy, x0 + 1 + s * 2, 21 + oy, 1)
        elif mode == "type_lo":
            R(buf, x0 + s * 2, 22 + oy, x0 + 1 + s * 2, 23 + oy, 1)
        elif mode == "droop":
            R(buf, x0, 23 + oy, x0 + 1, 24 + oy, 1)

    arm("l", p.paw_l)
    arm("r", p.paw_r)

    # feet
    if p.legs == "stomp_l":
        R(buf, 13, 27 + oy, 14, 27 + oy, 4)
        R(buf, 17, 27 + oy, 18, 28 + oy, 4)
    elif p.legs == "stomp_r":
        R(buf, 13, 27 + oy, 14, 28 + oy, 4)
        R(buf, 17, 27 + oy, 18, 27 + oy, 4)
    elif p.legs in ("stand", "jump"):
        R(buf, 13, 27 + oy, 14, 27 + oy, 4)
        R(buf, 17, 27 + oy, 18, 27 + oy, 4)

    _b.std_eyes(buf, (13, 17), 20, p.eyes, p.look_x, p.look_y, oy)
    P2(buf, 12, 22 + oy, 14)
    P2(buf, 19, 22 + oy, 14)


CFG = {"bar_hi": 19, "bar_lo": 23, "sweat": (24, 10), "dots": (24, 8)}
GRID = _b.GRID
build_frame = _b.make_build_frame(_draw, CFG)
frame_hold = _b.frame_hold
POKE_SEQ = _b.POKE_SEQ
GYM_SEQ = _b.GYM_SEQ
SOCCER_SEQ = _b.SOCCER_SEQ
