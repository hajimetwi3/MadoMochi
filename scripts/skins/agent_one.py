"""Agent One — an original midnight-blue terminal spirit."""

from __future__ import annotations

import importlib.util as _ilu
from pathlib import Path as _Path

_spec = _ilu.spec_from_file_location(
    "buddy_skin__base", _Path(__file__).resolve().parent / "_base.py"
)
_b = _ilu.module_from_spec(_spec)
_spec.loader.exec_module(_b)

NAME = "エージェント1号"
NAME_EN = "Agent One"
PALETTE = _b.std_palette(
    "#24324f",  # 1 midnight shell
    "#5b7199",  # 2 lit shell edge
    "#0b1020",  # 3 deep outline
    "#17223b",  # 4 shell shade
    "#507780",  # 16 eye anti-aliasing on the screen
    [
        "#a7f3d0",  # 17 face screen
        "#2dd4bf",  # 18 cursor / antenna glow
        "#8b5cf6",  # 19 thought violet
        "#dbeafe",  # 20 cold highlight
    ],
)

SCREEN = 17
GLOW = 18
VIOLET = 19
ICE = 20


def _draw(buf, p):
    oy = p.bob
    R, H, P2 = _b.rect2, _b.hline2, _b.plot2

    # Feet sit behind the tapered body.
    if p.legs == "tuck":
        H(buf, 12, 19, 27 + oy, 4)
    elif p.legs == "jump":
        R(buf, 12, 26 + oy, 14, 27 + oy, 3)
        R(buf, 17, 26 + oy, 19, 27 + oy, 3)
    elif p.legs == "stomp_l":
        R(buf, 10, 27 + oy, 14, 29 + oy, 3)
        R(buf, 17, 27 + oy, 19, 28 + oy, 3)
        H(buf, 9, 14, 29 + oy, 2)
    elif p.legs == "stomp_r":
        R(buf, 12, 27 + oy, 14, 28 + oy, 3)
        R(buf, 17, 27 + oy, 21, 29 + oy, 3)
        H(buf, 17, 22, 29 + oy, 2)
    else:
        R(buf, 12, 27 + oy, 14, 29 + oy, 3)
        R(buf, 17, 27 + oy, 19, 29 + oy, 3)
        H(buf, 11, 14, 29 + oy, 2)
        H(buf, 17, 20, 29 + oy, 2)

    # Articulated cable arms. The bright end pixel is the hand/cuff.
    def arm(side, mode):
        left = side == "l"
        if mode == "tuck":
            x0, x1 = ((9, 13) if left else (18, 22))
            R(buf, x0, 21 + oy, x1, 22 + oy, 4)
            P2(buf, 13 if left else 18, 22 + oy, GLOW)
            return

        x0, x1 = ((7, 10) if left else (21, 24))
        hand_x = x0 if left else x1
        if mode == "rest":
            R(buf, x0, 19 + oy, x1, 23 + oy, 4)
            P2(buf, hand_x, 23 + oy, GLOW)
        elif mode == "raise":
            R(buf, x0, 15 + oy, x1, 20 + oy, 4)
            P2(buf, hand_x, 15 + oy, GLOW)
        elif mode == "up":
            R(buf, x0, 11 + oy, x1, 19 + oy, 4)
            P2(buf, hand_x, 11 + oy, GLOW)
        elif mode == "hold_lo":
            R(buf, x0, 18 + oy, x1, 21 + oy, 4)
            P2(buf, hand_x, 21 + oy, GLOW)
        elif mode in ("type_hi", "type_lo"):
            ty = 19 if mode == "type_hi" else 21
            if left:
                R(buf, 7, ty + oy, 11, ty + 1 + oy, 4)
                P2(buf, 7, ty + oy, GLOW)
            else:
                R(buf, 21, ty + oy, 25, ty + 1 + oy, 4)
                P2(buf, 25, ty + oy, GLOW)
        elif mode == "droop":
            R(buf, x0, 20 + oy, x1, 25 + oy, 4)
            P2(buf, hand_x, 25 + oy, 12)

    arm("l", p.paw_l)
    arm("r", p.paw_r)

    # Small tapered terminal body.
    H(buf, 13, 18, 19 + oy, 2)
    H(buf, 11, 20, 20 + oy, 1)
    for y in range(21, 26):
        H(buf, 10, 21, y + oy, 1)
    H(buf, 11, 20, 26 + oy, 4)

    # Chest prompt: its cursor color follows the current kind of thought.
    R(buf, 13, 21 + oy, 18, 24 + oy, 9)
    prompt_color = {
        "error": 12,
        "alert": 7,
        "happy": 14,
        "sleep": VIOLET,
        "think": VIOLET,
        "work": 11,
    }.get(p.mood, GLOW)
    P2(buf, 14, 22 + oy, prompt_color)
    P2(buf, 15, 23 + oy, prompt_color)
    H(buf, 16, 17, 23 + oy, prompt_color)

    # Side ports sit underneath the head shell.
    R(buf, 7, 12 + oy, 9, 16 + oy, 4)
    R(buf, 22, 12 + oy, 24, 16 + oy, 4)
    P2(buf, 7, 14 + oy, GLOW)
    P2(buf, 24, 14 + oy, GLOW)

    # Rounded monitor head and mint face screen.
    H(buf, 12, 19, 8 + oy, 3)
    H(buf, 10, 21, 9 + oy, 1)
    for y in range(10, 19):
        H(buf, 9, 22, y + oy, 1)
    H(buf, 10, 21, 19 + oy, 3)
    R(buf, 10, 10 + oy, 21, 18 + oy, 3)
    R(buf, 11, 11 + oy, 20, 17 + oy, SCREEN)
    H(buf, 12, 19, 11 + oy, ICE)

    _b.std_eyes(buf, (12, 18), 13, p.eyes, p.look_x, p.look_y, oy)

    # The tiny underscore is both a mouth and a live command cursor.
    mouth_color = 12 if p.mood == "error" else (VIOLET if p.mood == "sleep" else GLOW)
    H(buf, 15, 16, 16 + oy, mouth_color)

    # One deliberately asymmetrical antenna: curious, not perfectly polished.
    P2(buf, 18, 7 + oy, 2)
    P2(buf, 19, 6 + oy, 2)
    P2(buf, 20, 5 + oy, 2)
    tip_x = 22 if p.twitch else 21
    P2(buf, tip_x, 4 + oy, GLOW if p.t % 6 < 4 else VIOLET)


CFG = {
    "bar_hi": 15,
    "bar_lo": 21,
    "sweat": (25, 8),
    "dots": (24, 9),
    "zzz": (24, 0),
    "ball_x": 2,
}
GRID = _b.GRID
build_frame = _b.make_build_frame(_draw, CFG)
frame_hold = _b.frame_hold
POKE_SEQ = _b.POKE_SEQ
GYM_SEQ = _b.GYM_SEQ
SOCCER_SEQ = _b.SOCCER_SEQ
