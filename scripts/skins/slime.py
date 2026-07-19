"""Slime — a glossy green droplet. Squishes instead of standing."""

from __future__ import annotations

import importlib.util as _ilu
from pathlib import Path as _Path

_spec = _ilu.spec_from_file_location("buddy_skin__base", _Path(__file__).resolve().parent / "_base.py")
_b = _ilu.module_from_spec(_spec)
_spec.loader.exec_module(_b)

NAME = "スライム"
NAME_EN = "Slime"
PALETTE = _b.std_palette("#58c470", "#a9e8b8", "#2e8a48", "#3fa858", "#3a7448")


def _draw(buf, p):
    oy = p.bob
    R, H = _b.rect2, _b.hline2

    # squash & stretch via legs mode
    squash = 1 if p.legs == "tuck" else 0
    stretch = 1 if p.legs == "jump" else 0
    lean = -1 if p.legs == "stomp_l" else (1 if p.legs == "stomp_r" else 0)

    top = 14 + oy + squash - stretch
    H(buf, 13 + lean, 18 + lean, top, 1)
    H(buf, 12 + lean, 19 + lean, top + 1, 1)
    H(buf, 11 + lean, 20 + lean, top + 2, 1)
    for y in range(top + 3, 26 + oy):
        H(buf, 10, 21, y, 1)
    H(buf, 9, 22, 26 + oy, 1)
    H(buf, 10 - squash, 21 + squash, 27 + oy, 1)

    # gloss
    R(buf, 12 + lean, top + 2, 14 + lean, top + 3, 2)
    _b.plot2(buf, 12 + lean, top + 5, 2)

    # pseudopod arms (only when needed)
    def arm(side, mode):
        s = -1 if side == "l" else 1
        x0 = 8 if s < 0 else 22
        if mode == "rest":
            return
        if mode == "raise":
            R(buf, x0, 19 + oy, x0 + 1, 20 + oy, 1)
        elif mode == "up":
            R(buf, x0, 15 + oy, x0 + 1, 19 + oy, 1)
        elif mode == "hold_lo":
            R(buf, x0, 21 + oy, x0 + 1, 22 + oy, 1)
        elif mode == "type_hi":
            R(buf, x0 + s, 20 + oy, x0 + 1 + s, 21 + oy, 1)
        elif mode == "type_lo":
            R(buf, x0 + s, 22 + oy, x0 + 1 + s, 23 + oy, 1)
        elif mode == "droop":
            R(buf, x0, 23 + oy, x0 + 1, 24 + oy, 1)

    arm("l", p.paw_l)
    arm("r", p.paw_r)

    _b.std_eyes(buf, (12, 18), 19, p.eyes, p.look_x, p.look_y, oy)
    R(buf, 15, 23 + oy, 16, 23 + oy, 5)   # tiny mouth


CFG = {"bar_hi": 18, "bar_lo": 22, "sweat": (23, 12), "dots": (23, 12)}
GRID = _b.GRID
build_frame = _b.make_build_frame(_draw, CFG)
frame_hold = _b.frame_hold
POKE_SEQ = _b.POKE_SEQ
GYM_SEQ = _b.GYM_SEQ
SOCCER_SEQ = _b.SOCCER_SEQ
