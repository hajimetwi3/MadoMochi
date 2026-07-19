"""Tako — a coral octopus. Tentacle fringe scuttles instead of legs."""

from __future__ import annotations

import importlib.util as _ilu
from pathlib import Path as _Path

_spec = _ilu.spec_from_file_location("buddy_skin__base", _Path(__file__).resolve().parent / "_base.py")
_b = _ilu.module_from_spec(_spec)
_spec.loader.exec_module(_b)

NAME = "タコ"
NAME_EN = "Octopus"
PALETTE = _b.std_palette("#e86a5a", "#f29387", "#a03c30", "#c65046", "#824a44")


def _draw(buf, p):
    oy = p.bob
    R, H, P2 = _b.rect2, _b.hline2, _b.plot2
    r = _b.rect

    # dome
    H(buf, 13, 18, 10 + oy, 1)
    H(buf, 11, 20, 11 + oy, 1)
    for y in range(12, 23):
        H(buf, 9, 22, y + oy, 1)

    # tentacle fringe (alternates while scuttling)
    long_first = p.legs == "stomp_r" or (p.legs not in ("stomp_l", "stomp_r") and False)
    for i, x0 in enumerate((9, 13, 17, 21)):
        lengthen = (i % 2 == 0) != long_first and p.legs in ("stomp_l", "stomp_r")
        y1 = 25 if lengthen else 24
        if p.legs == "tuck":
            y1 = 23
        R(buf, x0, 23 + oy, x0 + 1, y1 + oy, 1)

    # side tentacle curls (the paws)
    def curl(side, mode):
        s = -1 if side == "l" else 1
        x0 = 7 if s < 0 else 23
        if mode == "rest":
            R(buf, x0, 19 + oy, x0 + 1, 22 + oy, 1)
            P2(buf, x0 if s > 0 else x0 + 1, 18 + oy, 1)
        elif mode == "raise":
            R(buf, x0, 15 + oy, x0 + 1, 18 + oy, 1)
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

    curl("l", p.paw_l)
    curl("r", p.paw_r)

    _b.std_eyes(buf, (12, 18), 15, p.eyes, p.look_x, p.look_y, oy)
    R(buf, 15, 18 + oy, 16, 18 + oy, 5)   # little mouth line

    # suckers (fine pink dots)
    for fx in (20, 28, 36, 44):
        r(buf, fx, 48 + oy * 2, fx + 1, 49 + oy * 2, 14)


CFG = {"bar_hi": 15, "bar_lo": 20, "sweat": (23, 8), "dots": (23, 8)}
GRID = _b.GRID
build_frame = _b.make_build_frame(_draw, CFG)
frame_hold = _b.frame_hold
POKE_SEQ = _b.POKE_SEQ
GYM_SEQ = _b.GYM_SEQ
SOCCER_SEQ = _b.SOCCER_SEQ
