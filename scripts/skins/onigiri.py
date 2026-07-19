"""Onigiri — a rice ball with a nori band and little rice hands."""

from __future__ import annotations

import importlib.util as _ilu
from pathlib import Path as _Path

_spec = _ilu.spec_from_file_location("buddy_skin__base", _Path(__file__).resolve().parent / "_base.py")
_b = _ilu.module_from_spec(_spec)
_spec.loader.exec_module(_b)

NAME = "おにぎり"
NAME_EN = "Onigiri"
PALETTE = _b.std_palette("#f8f7f2", "#fdfdfa", "#c9c6b8", "#e3e0d4", "#8a887c",
                         ["#26302b"])  # 17 nori
NORI = 17

_ROWS = [(15, 16), (14, 17), (14, 17), (13, 18), (13, 18), (12, 19), (12, 19),
         (11, 20), (11, 20), (10, 21), (10, 21), (9, 22), (9, 22), (9, 22)]


def _draw(buf, p):
    oy = p.bob
    R, H, P2 = _b.rect2, _b.hline2, _b.plot2

    # rice triangle
    for i, (x0, x1) in enumerate(_ROWS):
        H(buf, x0, x1, 10 + i + oy, 1)
    H(buf, 10, 21, 24 + oy, 1)

    # nori band
    R(buf, 12, 20 + oy, 19, 24 + oy, NORI)

    # rice hands
    def hand(side, mode):
        s = -1 if side == "l" else 1
        x0 = 8 if s < 0 else 22
        if mode == "rest":
            return
        if mode == "raise":
            R(buf, x0, 18 + oy, x0 + 1, 19 + oy, 1)
        elif mode == "up":
            R(buf, x0, 15 + oy, x0 + 1, 18 + oy, 1)
        elif mode == "hold_lo":
            R(buf, x0, 20 + oy, x0 + 1, 21 + oy, 1)
        elif mode == "type_hi":
            R(buf, x0 + s, 19 + oy, x0 + 1 + s, 20 + oy, 1)
        elif mode == "type_lo":
            R(buf, x0 + s, 21 + oy, x0 + 1 + s, 22 + oy, 1)
        elif mode == "droop":
            R(buf, x0, 21 + oy, x0 + 1, 22 + oy, 1)

    hand("l", p.paw_l)
    hand("r", p.paw_r)

    # feet peeking under the nori
    if p.legs == "stomp_l":
        R(buf, 13, 25 + oy, 14, 25 + oy, 4)
        R(buf, 17, 25 + oy, 18, 26 + oy, 4)
    elif p.legs == "stomp_r":
        R(buf, 13, 25 + oy, 14, 26 + oy, 4)
        R(buf, 17, 25 + oy, 18, 25 + oy, 4)
    elif p.legs in ("stand", "jump"):
        R(buf, 13, 25 + oy, 14, 25 + oy, 4)
        R(buf, 17, 25 + oy, 18, 25 + oy, 4)

    _b.std_eyes(buf, (12, 17), 16, p.eyes, p.look_x, p.look_y, oy)
    P2(buf, 10, 18 + oy, 14)
    P2(buf, 20, 18 + oy, 14)


CFG = {"bar_hi": 16, "bar_lo": 21, "sweat": (23, 9), "dots": (23, 9)}
GRID = _b.GRID
build_frame = _b.make_build_frame(_draw, CFG)
frame_hold = _b.frame_hold
POKE_SEQ = _b.POKE_SEQ
GYM_SEQ = _b.GYM_SEQ
SOCCER_SEQ = _b.SOCCER_SEQ
