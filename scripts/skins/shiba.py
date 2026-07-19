"""Shiba — tan dog with a cream muzzle and a curled tail."""

from __future__ import annotations

import importlib.util as _ilu
from pathlib import Path as _Path

_spec = _ilu.spec_from_file_location("buddy_skin__base", _Path(__file__).resolve().parent / "_base.py")
_b = _ilu.module_from_spec(_spec)
_spec.loader.exec_module(_b)

NAME = "しば"
NAME_EN = "Shiba"
PALETTE = _b.std_palette("#e8a85c", "#f7efdd", "#a06a2e", "#c9853d", "#8f6b42")


def _draw(buf, p):
    oy = p.bob
    R, H, P2 = _b.rect2, _b.hline2, _b.plot2

    # tail (hides while the right paw works)
    if p.paw_r == "rest" and not p.terminal:
        if p.t % 16 < 8:
            P2(buf, 21, 21 + oy, 1)
            P2(buf, 22, 20 + oy, 1)
            P2(buf, 22, 19 + oy, 4)
        else:
            P2(buf, 21, 20 + oy, 1)
            P2(buf, 22, 19 + oy, 1)
            P2(buf, 21, 18 + oy, 4)

    # ears
    tw = -1 if p.twitch else 0
    R(buf, 10, 9 + oy + tw, 12, 11 + oy, 1)
    R(buf, 19, 9 + oy, 21, 11 + oy, 1)
    P2(buf, 11, 10 + oy + tw, 4)
    P2(buf, 20, 10 + oy, 4)

    # head
    H(buf, 10, 21, 12 + oy, 1)
    for y in range(13, 19):
        H(buf, 9, 22, y + oy, 1)
    H(buf, 10, 21, 19 + oy, 1)
    R(buf, 13, 16 + oy, 18, 19 + oy, 2)   # muzzle
    R(buf, 15, 16 + oy, 16, 17 + oy, 5)   # nose

    # body
    R(buf, 11, 20 + oy, 20, 26 + oy, 1)
    R(buf, 13, 21 + oy, 18, 26 + oy, 2)   # chest

    # paws (side stubs when active)
    def arm(side, mode):
        s = -1 if side == "l" else 1
        x0 = 9 if s < 0 else 21
        if mode == "rest":
            return
        if mode == "raise":
            R(buf, x0 + s, 17 + oy, x0 + 1 + s, 18 + oy, 1)
        elif mode == "up":
            R(buf, x0 + s, 14 + oy, x0 + 1 + s, 17 + oy, 1)
        elif mode == "hold_lo":
            R(buf, x0 + s, 21 + oy, x0 + 1 + s, 22 + oy, 1)
        elif mode == "type_hi":
            R(buf, x0 + s * 2, 19 + oy, x0 + 1 + s * 2, 20 + oy, 1)
        elif mode == "type_lo":
            R(buf, x0 + s * 2, 21 + oy, x0 + 1 + s * 2, 22 + oy, 1)
        elif mode == "droop":
            R(buf, x0, 23 + oy, x0 + 1, 24 + oy, 1)

    arm("l", p.paw_l)
    arm("r", p.paw_r)

    # feet
    if p.legs == "stomp_l":
        R(buf, 12, 27 + oy, 13, 27 + oy, 1)
        R(buf, 18, 27 + oy, 19, 28 + oy, 1)
    elif p.legs == "stomp_r":
        R(buf, 12, 27 + oy, 13, 28 + oy, 1)
        R(buf, 18, 27 + oy, 19, 27 + oy, 1)
    elif p.legs in ("stand", "jump"):
        R(buf, 12, 27 + oy, 13, 27 + oy, 1)
        R(buf, 18, 27 + oy, 19, 27 + oy, 1)

    _b.std_eyes(buf, (11, 19), 14, p.eyes, p.look_x, p.look_y, oy)


CFG = {"bar_hi": 16, "bar_lo": 21, "sweat": (24, 8), "dots": (24, 9)}
GRID = _b.GRID
build_frame = _b.make_build_frame(_draw, CFG)
frame_hold = _b.frame_hold
POKE_SEQ = _b.POKE_SEQ
GYM_SEQ = _b.GYM_SEQ
SOCCER_SEQ = _b.SOCCER_SEQ
