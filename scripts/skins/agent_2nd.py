"""Agent 2nd — an original pearl-and-mint monitor sprite."""

from __future__ import annotations

import importlib.util as _ilu
from pathlib import Path as _Path

_spec = _ilu.spec_from_file_location(
    "buddy_skin__base", _Path(__file__).resolve().parent / "_base.py"
)
_b = _ilu.module_from_spec(_spec)
_spec.loader.exec_module(_b)

NAME = "エージェント2号"
NAME_EN = "Agent 2nd"
PALETTE = _b.std_palette(
    "#dce8e8",  # 1 pearl shell
    "#f6fbfa",  # 2 shell highlight
    "#344454",  # 3 dark rim
    "#afc2c4",  # 4 shell shade
    "#7a8d96",  # 16 anti-aliasing fallback
    [
        "#142235",  # 17 navy face screen
        "#79dfd0",  # 18 mint accents
        "#edfffb",  # 19 luminous face
        "#f2a9ba",  # 20 blush
        "#829298",  # 21 antenna stem
        "#223650",  # 22 screen reflection
    ],
)

SCREEN = 17
MINT = 18
FACE = 19
BLUSH = 20
STEM = 21
REFLECT = 22


def _cable(buf, points):
    """Join logical-grid waypoints with a thin fine-grid cable."""
    for (ax, ay), (bx, by) in zip(points, points[1:]):
        x0, y0 = ax * 2 + 1, ay * 2 + 1
        x1, y1 = bx * 2 + 1, by * 2 + 1
        steps = max(abs(x1 - x0), abs(y1 - y0), 1)
        for step in range(steps + 1):
            x = round(x0 + (x1 - x0) * step / steps)
            y = round(y0 + (y1 - y0) * step / steps)
            _b.plot(buf, x, y, STEM)


def _mitten(buf, x, y, left):
    """A tiny rounded mint hand with one pearl highlight pixel."""
    fx, fy = x * 2, y * 2
    _b.rect(buf, fx + 1, fy, fx + 2, fy + 3, MINT)
    _b.rect(buf, fx, fy + 1, fx + 3, fy + 2, MINT)
    _b.plot(buf, fx + (1 if left else 2), fy + 1, 2)


def _draw_eye(buf, cx, cy, mode, look_x, look_y, oy, mood):
    """Draw one compact light-up eye on the dark monitor face."""
    R, P2 = _b.rect, _b.plot2

    # Work on the fine grid here: an odd-width eye can stay round while a
    # permanent four-pixel navy gap keeps the pair visually independent.
    left = cx < 16
    fcx = cx * 2 - (1 if left else 0)
    fcy = (cy + oy) * 2
    glance = max(-1, min(1, look_x))

    if mode == "blink":
        R(buf, fcx - 3 + glance, fcy, fcx + 3 + glance, fcy + 1, FACE)
        return
    if mode == "squeeze":
        if mood == "error":
            P2(buf, cx - 1, cy + oy, FACE)
            P2(buf, cx, cy + 1 + oy, FACE)
            P2(buf, cx + 1, cy + oy, FACE)
        else:
            P2(buf, cx - 1, cy + 1 + oy, FACE)
            P2(buf, cx, cy + oy, FACE)
            P2(buf, cx + 1, cy + 1 + oy, FACE)
        return

    # Both eyes glance by the same fine-grid pixel so their gap stays even.
    x = fcx if mode == "wide" else fcx + glance
    y = fcy + look_y * 2
    if mode == "wide":
        R(buf, x - 3, y - 3, x + 3, y + 3, FACE)
        R(buf, x - 4, y - 2, x + 4, y + 2, FACE)
    else:
        R(buf, x - 3, y - 2, x + 3, y + 2, FACE)
        R(buf, x - 4, y - 1, x + 4, y + 1, FACE)


def _draw(buf, p):
    oy = p.bob
    R, H, P2 = _b.rect2, _b.hline2, _b.plot2

    # Mint feet sit behind the all-in-one monitor body.
    if p.legs == "tuck":
        H(buf, 13, 14, 28 + oy, 4)
        H(buf, 18, 19, 28 + oy, 4)
    elif p.legs == "jump":
        R(buf, 12, 27 + oy, 14, 28 + oy, MINT)
        R(buf, 18, 27 + oy, 20, 28 + oy, MINT)
    elif p.legs == "stomp_l":
        R(buf, 10, 27 + oy, 14, 29 + oy, MINT)
        R(buf, 18, 27 + oy, 20, 28 + oy, MINT)
    elif p.legs == "stomp_r":
        R(buf, 12, 27 + oy, 14, 28 + oy, MINT)
        R(buf, 18, 27 + oy, 22, 29 + oy, MINT)
    else:
        R(buf, 11, 27 + oy, 14, 29 + oy, MINT)
        R(buf, 18, 27 + oy, 21, 29 + oy, MINT)
        H(buf, 12, 14, 27 + oy, 2)
        H(buf, 18, 20, 27 + oy, 2)

    # Small side pads hide flexible cable arms; mint mittens appear only when
    # a pose needs them, avoiding the stiff raised-bar look of long paddles.
    def arm(side, mode):
        left = side == "l"
        s = -1 if left else 1
        x0 = 6 if left else 24
        if mode == "rest":
            R(buf, x0, 17 + oy, x0 + 1, 20 + oy, MINT)
            P2(buf, x0 + s, 19 + oy, 2)
        elif mode == "raise":
            if p.mood == "gym":
                R(buf, x0, 15 + oy, x0 + 1, 18 + oy, MINT)
                _cable(buf, [
                    (x0, 16 + oy), (x0 + s, 14 + oy),
                    (x0 + 2 * s, 12 + oy), (5 if left else 26, 11 + oy),
                ])
                _mitten(buf, 4 if left else 26, 10 + oy, left)
            else:
                R(buf, x0, 14 + oy, x0 + 1, 17 + oy, MINT)
                _cable(buf, [
                    (x0, 15 + oy), (x0 + s, 13 + oy),
                    (5 if left else 26, 12 + oy),
                ])
                _mitten(buf, 4 if left else 26, 11 + oy, left)
        elif mode == "up":
            R(buf, x0, 12 + oy, x0 + 1, 16 + oy, MINT)
            _cable(buf, [
                (x0, 13 + oy), (x0 + s, 11 + oy),
                (5 if left else 26, 10 + oy),
            ])
            _mitten(buf, 4 if left else 26, 9 + oy, left)
        elif mode == "hold_lo":
            R(buf, x0, 19 + oy, x0 + 1, 21 + oy, MINT)
            _cable(buf, [
                (x0, 20 + oy), (x0 + s, 22 + oy),
                (5 if left else 26, 23 + oy),
            ])
            _mitten(buf, 4 if left else 26, 22 + oy, left)
        elif mode in ("type_hi", "type_lo"):
            ty = 19 if mode == "type_hi" else 21
            _cable(buf, [
                (7 if left else 24, ty + oy),
                (5 if left else 26, ty + oy),
            ])
            _mitten(buf, 4 if left else 26, ty + oy, left)
        elif mode == "droop":
            R(buf, x0, 20 + oy, x0 + 1, 22 + oy, 4)
            _cable(buf, [
                (x0, 21 + oy), (x0 + s, 22 + oy),
                (5 if left else 26, 23 + oy),
            ])
            _mitten(buf, 4 if left else 26, 22 + oy, left)

    arm("l", p.paw_l)
    arm("r", p.paw_r)

    # A slightly off-center antenna keeps it curious and toy-like.
    antenna_x = 21 if p.twitch else 20
    R(buf, 20, 5 + oy, 20, 9 + oy, STEM)
    P2(buf, antenna_x, 4 + oy, STEM)
    H(buf, antenna_x - 1, antenna_x + 1, 2 + oy, MINT)
    R(buf, antenna_x - 2, 3 + oy, antenna_x + 2, 4 + oy, MINT)
    H(buf, antenna_x - 1, antenna_x + 1, 5 + oy, MINT)
    P2(buf, antenna_x - 1, 3 + oy, 2)

    # Rounded pearl shell.
    H(buf, 11, 20, 9 + oy, 2)
    H(buf, 9, 22, 10 + oy, 2)
    for y in range(11, 25):
        H(buf, 8, 23, y + oy, 1)
    H(buf, 9, 22, 25 + oy, 4)
    H(buf, 11, 20, 26 + oy, 4)
    for y in range(13, 23):
        P2(buf, 8, y + oy, 4)
        P2(buf, 23, y + oy, 2)

    # Deep navy face with a small diagonal glass reflection.
    H(buf, 11, 20, 12 + oy, 3)
    H(buf, 10, 21, 13 + oy, 3)
    for y in range(14, 22):
        H(buf, 9, 22, y + oy, 3)
    H(buf, 10, 21, 22 + oy, 3)
    H(buf, 11, 20, 23 + oy, 3)

    H(buf, 12, 19, 13 + oy, SCREEN)
    H(buf, 11, 20, 14 + oy, SCREEN)
    for y in range(15, 21):
        H(buf, 10, 21, y + oy, SCREEN)
    H(buf, 11, 20, 21 + oy, SCREEN)
    H(buf, 12, 19, 22 + oy, SCREEN)
    P2(buf, 12, 14 + oy, REFLECT)
    P2(buf, 11, 15 + oy, REFLECT)
    P2(buf, 11, 16 + oy, REFLECT)

    _draw_eye(buf, 13, 17, p.eyes, p.look_x, p.look_y, oy, p.mood)
    _draw_eye(buf, 19, 17, p.eyes, p.look_x, p.look_y, oy, p.mood)

    if p.mood in ("idle", "listen", "happy"):
        P2(buf, 10, 20 + oy, BLUSH)
        P2(buf, 22, 20 + oy, BLUSH)


CFG = {
    "bar_hi": 10,
    "bar_lo": 23,
    "sweat": (26, 8),
    "dots": (26, 9),
    "zzz": (24, 0),
    "ball_x": 2,
}
GRID = _b.GRID
build_frame = _b.make_build_frame(_draw, CFG)
frame_hold = _b.frame_hold
POKE_SEQ = _b.POKE_SEQ
GYM_SEQ = _b.GYM_SEQ
SOCCER_SEQ = _b.SOCCER_SEQ
