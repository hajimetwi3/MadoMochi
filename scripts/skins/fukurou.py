"""Fukurou — a brown owl with a cream face disc. Wings do the paw work."""

from __future__ import annotations

import importlib.util as _ilu
from pathlib import Path as _Path

_spec = _ilu.spec_from_file_location("buddy_skin__base", _Path(__file__).resolve().parent / "_base.py")
_b = _ilu.module_from_spec(_spec)
_spec.loader.exec_module(_b)

NAME = "フクロウ"
NAME_EN = "Owl"
PALETTE = _b.std_palette("#a5714f", "#e8d7b8", "#6e4930", "#8a5c3d", "#827e70",
                         ["#f59b3d"])  # 17 orange
ORANGE = 17


def _draw(buf, p):
    oy = p.bob
    R, H, P2 = _b.rect2, _b.hline2, _b.plot2

    # ear tufts
    tw = -1 if p.twitch else 0
    P2(buf, 10, 9 + oy + tw, 1)
    P2(buf, 11, 10 + oy, 1)
    P2(buf, 21, 9 + oy, 1)
    P2(buf, 20, 10 + oy, 1)

    # egg body
    H(buf, 12, 19, 10 + oy, 1)
    H(buf, 10, 21, 11 + oy, 1)
    for y in range(12, 26):
        H(buf, 9, 22, y + oy, 1)
    H(buf, 10, 21, 26 + oy, 1)
    H(buf, 12, 19, 27 + oy, 1)

    # face disc + beak
    R(buf, 11, 13 + oy, 20, 18 + oy, 2)
    R(buf, 15, 17 + oy, 16, 18 + oy, ORANGE)

    # wings
    def wing(side, mode):
        s = -1 if side == "l" else 1
        x0 = 7 if s < 0 else 23
        if mode == "rest":
            R(buf, x0, 17 + oy, x0 + 1, 22 + oy, 4)
        elif mode == "raise":
            R(buf, x0, 14 + oy, x0 + 1, 19 + oy, 4)
        elif mode == "up":
            R(buf, x0, 10 + oy, x0 + 1, 17 + oy, 4)
        elif mode == "hold_lo":
            R(buf, x0, 19 + oy, x0 + 1, 22 + oy, 4)
        elif mode == "type_hi":
            R(buf, x0 + s, 19 + oy, x0 + 1 + s, 20 + oy, 4)
        elif mode == "type_lo":
            R(buf, x0 + s, 21 + oy, x0 + 1 + s, 22 + oy, 4)
        elif mode == "droop":
            R(buf, x0, 20 + oy, x0 + 1, 24 + oy, 4)

    wing("l", p.paw_l)
    wing("r", p.paw_r)

    # feet
    if p.legs == "stomp_l":
        R(buf, 11, 28 + oy, 12, 28 + oy, ORANGE)
        R(buf, 18, 28 + oy, 19, 28 + oy, ORANGE)
    elif p.legs == "stomp_r":
        R(buf, 12, 28 + oy, 13, 28 + oy, ORANGE)
        R(buf, 19, 28 + oy, 20, 28 + oy, ORANGE)
    elif p.legs == "stand":
        R(buf, 12, 28 + oy, 13, 28 + oy, ORANGE)
        R(buf, 18, 28 + oy, 19, 28 + oy, ORANGE)

    _b.std_eyes(buf, (12, 18), 14, p.eyes, p.look_x, p.look_y, oy)


CFG = {"bar_hi": 16, "bar_lo": 21, "sweat": (24, 8), "dots": (24, 9)}
GRID = _b.GRID
build_frame = _b.make_build_frame(_draw, CFG)
frame_hold = _b.frame_hold
POKE_SEQ = _b.POKE_SEQ
GYM_SEQ = _b.GYM_SEQ
SOCCER_SEQ = _b.SOCCER_SEQ
