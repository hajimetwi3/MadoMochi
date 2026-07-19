"""Penguin — navy, white belly, orange beak. Flippers do the paw work."""

from __future__ import annotations

import importlib.util as _ilu
from pathlib import Path as _Path

_spec = _ilu.spec_from_file_location("buddy_skin__base", _Path(__file__).resolve().parent / "_base.py")
_b = _ilu.module_from_spec(_spec)
_spec.loader.exec_module(_b)

NAME = "ペンギン"
NAME_EN = "Penguin"
PALETTE = _b.std_palette("#2b3a55", "#46567a", "#1a2436", "#223050", "#888a87",
                         ["#f5f0e6", "#f59b3d"])  # 17 belly, 18 orange
BELLY, ORANGE = 17, 18


def _draw(buf, p):
    oy = p.bob
    R, H, P2 = _b.rect2, _b.hline2, _b.plot2

    # body
    H(buf, 12, 19, 12 + oy, 1)
    H(buf, 11, 20, 13 + oy, 1)
    for y in range(14, 26):
        H(buf, 10, 21, y + oy, 1)
    H(buf, 11, 20, 26 + oy, 1)
    H(buf, 12, 19, 27 + oy, 1)
    # face patch (so the eyes read on the navy head)
    R(buf, 12, 13 + oy, 19, 15 + oy, BELLY)
    # belly
    H(buf, 14, 17, 16 + oy, BELLY)
    for y in range(17, 26):
        H(buf, 13, 18, y + oy, BELLY)
    H(buf, 14, 17, 26 + oy, BELLY)

    # flippers
    def flip(side, mode):
        s = -1 if side == "l" else 1
        x0 = 8 if s < 0 else 22
        if mode == "rest":
            R(buf, x0, 17 + oy, x0 + 1, 20 + oy, 1)
        elif mode == "raise":
            R(buf, x0, 14 + oy, x0 + 1, 17 + oy, 1)
        elif mode == "up":
            R(buf, x0, 11 + oy, x0 + 1, 16 + oy, 1)
        elif mode == "hold_lo":
            R(buf, x0, 19 + oy, x0 + 1, 21 + oy, 1)
        elif mode == "type_hi":
            R(buf, x0 + s, 19 + oy, x0 + 1 + s, 20 + oy, 1)
        elif mode == "type_lo":
            R(buf, x0 + s, 21 + oy, x0 + 1 + s, 22 + oy, 1)
        elif mode == "droop":
            R(buf, x0, 20 + oy, x0 + 1, 23 + oy, 1)

    flip("l", p.paw_l)
    flip("r", p.paw_r)

    # feet
    if p.legs == "stand":
        R(buf, 12, 28 + oy, 13, 28 + oy, ORANGE)
        R(buf, 18, 28 + oy, 19, 28 + oy, ORANGE)
    elif p.legs == "jump":
        R(buf, 13, 28 + oy, 14, 28 + oy, ORANGE)
        R(buf, 17, 28 + oy, 18, 28 + oy, ORANGE)
    elif p.legs == "stomp_l":
        R(buf, 11, 28 + oy, 12, 28 + oy, ORANGE)
        R(buf, 18, 28 + oy, 19, 28 + oy, ORANGE)
    elif p.legs == "stomp_r":
        R(buf, 12, 28 + oy, 13, 28 + oy, ORANGE)
        R(buf, 19, 28 + oy, 20, 28 + oy, ORANGE)

    _b.std_eyes(buf, (12, 18), 14, p.eyes, p.look_x, p.look_y, oy)
    R(buf, 15, 16 + oy, 16, 16 + oy, ORANGE)  # beak


CFG = {"bar_hi": 15, "bar_lo": 20, "sweat": (24, 9), "dots": (24, 9)}
GRID = _b.GRID
build_frame = _b.make_build_frame(_draw, CFG)
frame_hold = _b.frame_hold
POKE_SEQ = _b.POKE_SEQ
GYM_SEQ = _b.GYM_SEQ
SOCCER_SEQ = _b.SOCCER_SEQ
