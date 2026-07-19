"""Kaeru — a wide green frog with eye bumps on top."""

from __future__ import annotations

import importlib.util as _ilu
from pathlib import Path as _Path

_spec = _ilu.spec_from_file_location("buddy_skin__base", _Path(__file__).resolve().parent / "_base.py")
_b = _ilu.module_from_spec(_spec)
_spec.loader.exec_module(_b)

NAME = "カエル"
NAME_EN = "Frog"
PALETTE = _b.std_palette("#6abf4b", "#d8eec4", "#3d8a2c", "#4fa538", "#437536")


def _draw(buf, p):
    oy = p.bob
    R, H = _b.rect2, _b.hline2

    # eye bumps
    R(buf, 10, 10 + oy, 12, 12 + oy, 1)
    R(buf, 19, 10 + oy, 21, 12 + oy, 1)

    # wide body
    H(buf, 9, 22, 13 + oy, 1)
    for y in range(14, 24):
        H(buf, 8, 23, y + oy, 1)
    H(buf, 9, 22, 24 + oy, 1)
    for y in range(19, 24):
        H(buf, 12, 19, y + oy, 2)   # belly

    _b.plot2(buf, 10, 18 + oy, 14)
    _b.plot2(buf, 21, 18 + oy, 14)

    # front feet / arms
    def arm(side, mode):
        s = -1 if side == "l" else 1
        x0 = 9 if s < 0 else 21
        if mode == "rest":
            return
        if mode == "raise":
            R(buf, x0 + s * 2, 16 + oy, x0 + 1 + s * 2, 17 + oy, 1)
        elif mode == "up":
            R(buf, x0 + s * 2, 12 + oy, x0 + 1 + s * 2, 16 + oy, 1)
        elif mode == "hold_lo":
            R(buf, x0 + s * 2, 19 + oy, x0 + 1 + s * 2, 20 + oy, 1)
        elif mode == "type_hi":
            R(buf, x0 + s * 3, 19 + oy, x0 + 1 + s * 3, 20 + oy, 1)
        elif mode == "type_lo":
            R(buf, x0 + s * 3, 21 + oy, x0 + 1 + s * 3, 22 + oy, 1)
        elif mode == "droop":
            R(buf, x0 + s * 2, 21 + oy, x0 + 1 + s * 2, 22 + oy, 1)

    arm("l", p.paw_l)
    arm("r", p.paw_r)

    # hind feet
    if p.legs == "stomp_l":
        R(buf, 8, 25 + oy, 10, 26 + oy, 1)
        R(buf, 20, 26 + oy, 22, 26 + oy, 1)
    elif p.legs == "stomp_r":
        R(buf, 9, 26 + oy, 11, 26 + oy, 1)
        R(buf, 21, 25 + oy, 23, 26 + oy, 1)
    elif p.legs in ("stand", "jump"):
        R(buf, 9, 25 + oy, 11, 26 + oy, 1)
        R(buf, 20, 25 + oy, 22, 26 + oy, 1)

    _b.std_eyes(buf, (10, 19), 11, p.eyes, p.look_x, p.look_y, oy)


CFG = {"bar_hi": 15, "bar_lo": 20, "sweat": (24, 8), "dots": (24, 9)}
GRID = _b.GRID
build_frame = _b.make_build_frame(_draw, CFG)
frame_hold = _b.frame_hold
POKE_SEQ = _b.POKE_SEQ
GYM_SEQ = _b.GYM_SEQ
SOCCER_SEQ = _b.SOCCER_SEQ
