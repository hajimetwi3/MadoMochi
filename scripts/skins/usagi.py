"""Usagi — cream bunny with long pink-lined ears."""

from __future__ import annotations

import importlib.util as _ilu
from pathlib import Path as _Path

_spec = _ilu.spec_from_file_location("buddy_skin__base", _Path(__file__).resolve().parent / "_base.py")
_b = _ilu.module_from_spec(_spec)
_spec.loader.exec_module(_b)

NAME = "うさぎ"
NAME_EN = "Bunny"
PALETTE = _b.std_palette("#f2ede4", "#fbf8f3", "#b8a894", "#d9cfc0", "#857f74")


def _draw(buf, p):
    oy = p.bob
    R, H = _b.rect2, _b.hline2
    r = _b.rect

    # ears (left tip bends on twitch)
    tw = -1 if p.twitch else 0
    R(buf, 12 + tw, 5 + oy, 13 + tw, 6 + oy, 1)
    R(buf, 12, 7 + oy, 13, 12 + oy, 1)
    R(buf, 18, 5 + oy, 19, 12 + oy, 1)
    r(buf, 25, 14 + oy * 2, 26, 23 + oy * 2, 14)   # inner pink (fine)
    r(buf, 37, 12 + oy * 2, 38, 23 + oy * 2, 14)

    # head + body
    H(buf, 11, 20, 13 + oy, 1)
    for y in range(14, 20):
        H(buf, 10, 21, y + oy, 1)
    H(buf, 11, 20, 20 + oy, 1)
    R(buf, 12, 21 + oy, 19, 26 + oy, 1)
    H(buf, 13, 18, 27 + oy, 1)

    # arms (stubs)
    def arm(side, mode):
        s = -1 if side == "l" else 1
        x0 = 9 if s < 0 else 21
        if mode == "rest":
            return
        if mode == "raise":
            R(buf, x0, 18 + oy, x0 + 1, 19 + oy, 1)
        elif mode == "up":
            R(buf, x0, 15 + oy, x0 + 1, 18 + oy, 1)
        elif mode == "hold_lo":
            R(buf, x0, 21 + oy, x0 + 1, 22 + oy, 1)
        elif mode == "type_hi":
            R(buf, x0 + s * 2, 19 + oy, x0 + 1 + s * 2, 20 + oy, 1)
        elif mode == "type_lo":
            R(buf, x0 + s * 2, 21 + oy, x0 + 1 + s * 2, 22 + oy, 1)
        elif mode == "droop":
            R(buf, x0, 23 + oy, x0 + 1, 24 + oy, 1)

    arm("l", p.paw_l)
    arm("r", p.paw_r)

    # feet (visible when moving)
    if p.legs == "stomp_l":
        R(buf, 12, 28 + oy, 13, 28 + oy, 4)
        R(buf, 17, 27 + oy, 18, 28 + oy, 4)
    elif p.legs == "stomp_r":
        R(buf, 12, 27 + oy, 13, 28 + oy, 4)
        R(buf, 17, 28 + oy, 18, 28 + oy, 4)
    elif p.legs in ("stand", "jump"):
        R(buf, 13, 27 + oy, 14, 27 + oy, 4)
        R(buf, 17, 27 + oy, 18, 27 + oy, 4)

    _b.std_eyes(buf, (12, 18), 16, p.eyes, p.look_x, p.look_y, oy)
    r(buf, 31, 36 + oy * 2, 32, 37 + oy * 2, 14)   # nose


CFG = {"bar_hi": 17, "bar_lo": 22, "sweat": (23, 10), "dots": (23, 11), "zzz": (23, 1)}
GRID = _b.GRID
build_frame = _b.make_build_frame(_draw, CFG)
frame_hold = _b.frame_hold
POKE_SEQ = _b.POKE_SEQ
GYM_SEQ = _b.GYM_SEQ
SOCCER_SEQ = _b.SOCCER_SEQ
