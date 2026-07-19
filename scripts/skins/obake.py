"""Obake — a pale floating ghost. No legs: the hem just waves."""

from __future__ import annotations

import importlib.util as _ilu
from pathlib import Path as _Path

_spec = _ilu.spec_from_file_location("buddy_skin__base", _Path(__file__).resolve().parent / "_base.py")
_b = _ilu.module_from_spec(_spec)
_spec.loader.exec_module(_b)

NAME = "おばけ"
NAME_EN = "Ghost"
PALETTE = _b.std_palette("#eceaf9", "#f8f7fd", "#a29bcc", "#c9c5e8", "#847f90")


def _draw(buf, p):
    oy = p.bob
    R, H = _b.rect2, _b.hline2

    H(buf, 13, 18, 10 + oy, 1)
    H(buf, 11, 20, 11 + oy, 1)
    for y in range(12, 25):
        H(buf, 10, 21, y + oy, 1)

    # wavy hem: scallop phase follows steps / time (ghosts don't walk, they sway)
    phase = 0 if p.legs == "stomp_l" else (2 if p.legs == "stomp_r" else (p.t // 4) % 2 * 2)
    for i, x0 in enumerate((10, 14, 18)):
        if (i + phase) % 2 == 0:
            R(buf, x0, 25 + oy, x0 + 1, 25 + oy, 1)
        else:
            R(buf, x0 + 1, 25 + oy, x0 + 2, 25 + oy, 1)

    # stub arms
    def arm(side, mode):
        s = -1 if side == "l" else 1
        x0 = 8 if s < 0 else 22
        if mode == "rest":
            R(buf, x0, 16 + oy, x0 + 1, 18 + oy, 1)
        elif mode == "raise":
            R(buf, x0, 13 + oy, x0 + 1, 15 + oy, 1)
        elif mode == "up":
            R(buf, x0, 10 + oy, x0 + 1, 14 + oy, 1)
        elif mode == "hold_lo":
            R(buf, x0, 19 + oy, x0 + 1, 21 + oy, 1)
        elif mode == "type_hi":
            R(buf, x0 + s, 19 + oy, x0 + 1 + s, 20 + oy, 1)
        elif mode == "type_lo":
            R(buf, x0 + s, 21 + oy, x0 + 1 + s, 22 + oy, 1)
        elif mode == "droop":
            R(buf, x0, 19 + oy, x0 + 1, 22 + oy, 1)

    arm("l", p.paw_l)
    arm("r", p.paw_r)

    _b.std_eyes(buf, (12, 18), 15, p.eyes, p.look_x, p.look_y, oy)
    R(buf, 15, 20 + oy, 16, 21 + oy, 5)   # hollow little mouth


CFG = {"bar_hi": 15, "bar_lo": 20, "sweat": (23, 8), "dots": (23, 9)}
GRID = _b.GRID
build_frame = _b.make_build_frame(_draw, CFG)
frame_hold = _b.frame_hold
POKE_SEQ = _b.POKE_SEQ
GYM_SEQ = _b.GYM_SEQ
SOCCER_SEQ = _b.SOCCER_SEQ
