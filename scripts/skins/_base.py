"""
Shared skin foundation. Files starting with "_" are not skins themselves.

A concrete skin supplies NAME, PALETTE and a draw(buf, p) that renders the
character for a pose; everything else (mood choreography, effects, timing,
sequences, eye renderers, the > < glyph) lives here.

House style: solid dark eyes, no glint.

Standard palette layout (indices):
  0 None | 1 main 2 light 3 dark 4 shade | 5 eye-dark 6 white
  7 gold 8 cyan 9 term-dark 10 term-gray 11 term-green 12 red
  13 purple 14 pink 15 pale-blue 16 eye-AA-on-face | 17+ species extras
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Callable, List

Buf = List[List[int]]

GRID = 64

EFFECT_COLORS = [
    "#1c2528",  # 5 eyes dark
    "#ffffff",  # 6 white
    "#fbbf24",  # 7 gold
    "#38bdf8",  # 8 cyan
    "#1e293b",  # 9 terminal dark
    "#94a3b8",  # 10 terminal gray
    "#4ade80",  # 11 terminal green
    "#f87171",  # 12 red
    "#c4b5fd",  # 13 purple
    "#fda4af",  # 14 pink
    "#93c5fd",  # 15 pale blue
]


def std_palette(main: str, light: str, dark: str, shade: str, aa: str, extras: list[str] = ()) -> list:
    return [None, main, light, dark, shade] + EFFECT_COLORS[:2] + EFFECT_COLORS[2:] + [aa] + list(extras)


def empty() -> Buf:
    return [[0] * GRID for _ in range(GRID)]


def plot(buf: Buf, x: int, y: int, c: int) -> None:
    if 0 <= x < GRID and 0 <= y < GRID:
        buf[y][x] = c


def rect(buf: Buf, x0: int, y0: int, x1: int, y1: int, c: int) -> None:
    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            plot(buf, x, y, c)


def plot2(buf: Buf, x: int, y: int, c: int) -> None:
    rect(buf, x * 2, y * 2, x * 2 + 1, y * 2 + 1, c)


def rect2(buf: Buf, x0: int, y0: int, x1: int, y1: int, c: int) -> None:
    rect(buf, x0 * 2, y0 * 2, x1 * 2 + 1, y1 * 2 + 1, c)


def hline2(buf: Buf, x0: int, x1: int, y: int, c: int) -> None:
    rect2(buf, x0, y, x1, y, c)


# ---- eyes (house style: solid, no glint) ----

_SQ_GT: list[tuple[int, int, int]] = []
_SQ_LT: list[tuple[int, int, int]] = []
for _dy in range(9):
    _d = _dy if _dy <= 4 else 8 - _dy
    _lead = 0.75 + 1.5 * _d
    _trail = _lead - 2.3
    for _x in range(7):
        _cov = min(_x + 1, _lead) - max(_x, _trail)
        if _cov >= 0.65:
            _c = 5
        elif _cov >= 0.2:
            _c = 16
        else:
            continue
        _SQ_GT.append((_x, _dy, _c))
        _SQ_LT.append((6 - _x, _dy, _c))


def squeeze_eyes(buf: Buf, exs: tuple[int, int], ey: int, oy: int) -> None:
    fy = ey * 2 - 2 + oy * 2
    for ex, pts, off in ((exs[0], _SQ_GT, -2), (exs[1], _SQ_LT, -3)):
        fx = ex * 2 + off
        for dx, dy, c in pts:
            plot(buf, fx + dx, fy + dy, c)


def std_eyes(buf: Buf, exs: tuple[int, int], ey: int, mode: str,
             look_x: int, look_y: int, oy: int) -> None:
    if mode == "squeeze":
        squeeze_eyes(buf, exs, ey, oy)
        return
    for ex in exs:
        x = ex + look_x
        y = ey + oy + look_y
        if mode == "open":
            rect2(buf, x, y, x + 1, y + 1, 5)
        elif mode == "blink":
            rect2(buf, ex, ey + 1 + oy, ex + 1, ey + 1 + oy, 5)
        elif mode == "wide":
            rect2(buf, x, ey - 1 + oy, x + 1, ey + 1 + oy, 5)
        elif mode == "happy":
            if ex == exs[0]:
                plot2(buf, ex, ey + 1 + oy, 5)
                plot2(buf, ex + 1, ey + oy, 5)
            else:
                plot2(buf, ex, ey + oy, 5)
                plot2(buf, ex + 1, ey + 1 + oy, 5)


# ---- effects ----

def confetti(buf: Buf, t: int) -> None:
    pts = [
        (2, 0, 7), (5, 5, 14), (27, 2, 8), (30, 7, 13),
        (7, 10, 12), (25, 8, 7), (3, 12, 13), (29, 13, 14),
    ]
    for i, (x, phase, c) in enumerate(pts):
        y = (phase + t) % 15
        xx = x + (1 if (t + i) % 4 < 2 else 0)
        plot2(buf, xx, y, c)


def zzz(buf: Buf, t: int, ox: int = 24, oy: int = 0) -> None:
    p = t % 9
    if p >= 2:
        plot2(buf, ox, oy + 8, 15)
    if p >= 5:
        plot2(buf, ox + 2, oy + 6, 15)
        plot2(buf, ox + 3, oy + 6, 8)
    if p >= 7:
        plot2(buf, ox + 4, oy + 3, 8)
        plot2(buf, ox + 5, oy + 3, 15)


def think_dots(buf: Buf, t: int, anchor: tuple[int, int] = (24, 9)) -> None:
    ax, ay = anchor
    d = t % 18
    if d > 4:
        plot2(buf, ax, ay, 13)
    if d > 9:
        plot2(buf, ax + 2, ay - 3, 13)
    if d > 14:
        plot2(buf, ax + 4, ay - 6, 13)
        plot2(buf, ax + 5, ay - 6, 15)


def sweat(buf: Buf, xy: tuple[int, int]) -> None:
    plot2(buf, xy[0], xy[1], 8)
    plot2(buf, xy[0], xy[1] + 1, 15)


def terminal(buf: Buf, oy: int) -> None:
    rect2(buf, 25, 21 + oy, 30, 28 + oy, 9)
    hline2(buf, 25, 30, 20 + oy, 10)
    hline2(buf, 25, 30, 29 + oy, 10)
    for y in range(21, 29):
        plot2(buf, 25, y + oy, 10)
        plot2(buf, 30, y + oy, 10)
    hline2(buf, 26, 29, 22 + oy, 11)
    hline2(buf, 26, 28, 24 + oy, 11)
    plot2(buf, 29, 26 + oy, 11)


def barbell(buf: Buf, y: int) -> None:
    hline2(buf, 4, 27, y, 10)
    rect2(buf, 2, y - 1, 4, y + 1, 9)
    rect2(buf, 27, y - 1, 29, y + 1, 9)


def ball(buf: Buf, bx: int, by: int) -> None:
    fx, fy = bx * 2, by * 2
    rect(buf, fx + 1, fy, fx + 2, fy, 9)
    rect(buf, fx, fy + 1, fx, fy + 2, 9)
    rect(buf, fx + 3, fy + 1, fx + 3, fy + 2, 9)
    rect(buf, fx + 1, fy + 3, fx + 2, fy + 3, 9)
    rect(buf, fx + 1, fy + 1, fx + 2, fy + 2, 6)
    plot(buf, fx + 2, fy + 2, 5)


# ---- sequences: (fields..., hold_ms) ----

HAPPY_SEQ = [
    (1, "tuck", "raise", 130),
    (1, "tuck", "raise", 130),
    (-2, "jump", "up", 70),
    (-3, "jump", "up", 85),
    (-3, "jump", "up", 100),
    (-2, "jump", "up", 70),
    (0, "stand", "raise", 150),
    (0, "stomp_l", "up", 110),
    (0, "stomp_r", "raise", 110),
    (0, "stomp_l", "up", 110),
    (0, "stomp_r", "raise", 110),
]

POKE_SEQ = [
    (0, "stand", "squeeze", 90),
    (-1, "jump", "squeeze", 80),
    (-3, "jump", "wide", 90),
    (-1, "jump", "wide", 70),
    (0, "stand", "blink", 130),
    (0, "stand", "open", 170),
]

GYM_SEQ = [
    ("hold_lo", 260, 0),
    ("raise", 340, 0),
    ("hold_lo", 180, 0),
    ("raise", 360, 0),
    ("hold_lo", 180, 0),
    ("raise", 430, 1),
    ("hold_lo", 220, 1),
    ("raise", 500, 1),
    ("hold_lo", 320, 1),
]

SOCCER_SEQ = [
    (25, 1, "stomp_l", 1, 90),
    (21, 0, "stand", 1, 75),
    (17, 0, "stand", 0, 85),
    (14, 0, "stand", -1, 110),
    (13, 0, "stand", -1, 150),
    (14, 0, "stand", -1, 90),
    (17, 0, "stand", 0, 80),
    (21, 0, "stand", 1, 75),
    (25, 1, "stomp_l", 1, 90),
    (21, 0, "stand", 1, 75),
    (17, 0, "stand", 0, 85),
    (14, 0, "stand", -1, 110),
    (13, 0, "stand", -1, 150),
    (15, 0, "stand", -1, 90),
    (18, 0, "stand", 0, 85),
    (22, 0, "stand", 1, 80),
    (25, 0, "tuck", 1, 140),
    (25, 0, "tuck", 1, 300),
]


def frame_hold(mood: str, t: int) -> int:
    if mood == "happy":
        return HAPPY_SEQ[t % len(HAPPY_SEQ)][3]
    if mood == "poke":
        return POKE_SEQ[min(t, len(POKE_SEQ) - 1)][3]
    if mood == "gym":
        return GYM_SEQ[min(t, len(GYM_SEQ) - 1)][1]
    if mood == "soccer":
        return SOCCER_SEQ[min(t, len(SOCCER_SEQ) - 1)][4]
    if mood in ("walk_l", "walk_r"):
        return 90
    if mood == "idle":
        if t % 56 < 3:
            return 70
        if t % 24 in (10, 11):
            return 320
        return 95
    if mood == "think":
        return 240 if t % 18 in (5, 10, 15) else 150
    if mood == "listen":
        return 105
    if mood == "alert":
        return 70
    if mood == "sleep":
        return 260
    return 85


# ---- choreography factory ----

def make_build_frame(draw: Callable, cfg: dict | None = None) -> Callable:
    """draw(buf, p): render the character for pose p (a SimpleNamespace)."""
    cfg = cfg or {}
    bar_hi = cfg.get("bar_hi", 16)
    bar_lo = cfg.get("bar_lo", 21)
    sweat_xy = cfg.get("sweat", (24, 8))
    dots_at = cfg.get("dots", (24, 9))
    zzz_at = cfg.get("zzz", (24, 0))
    ball_x = cfg.get("ball_x", 2)

    def P(**kw) -> SimpleNamespace:
        base = dict(bob=0, eyes="open", look_x=0, look_y=0, paw_l="rest",
                    paw_r="rest", legs="stand", twitch=False, terminal=False,
                    mood="idle", t=0)
        base.update(kw)
        return SimpleNamespace(**base)

    def build_frame(mood: str, t: int) -> Buf:
        buf = empty()

        if mood == "idle":
            draw(buf, P(mood=mood, t=t,
                        bob=0 if t % 24 < 12 else 1,
                        eyes="blink" if t % 56 < 3 else "open",
                        look_x=-1 if t % 64 < 20 else (0 if t % 64 < 42 else 1),
                        twitch=t % 72 < 2))

        elif mood == "listen":
            draw(buf, P(mood=mood, t=t, bob=-1,
                        eyes="blink" if t % 40 < 2 else "wide",
                        look_x=-1 if t % 24 < 12 else 1,
                        paw_l="raise", paw_r="raise"))

        elif mood == "think":
            draw(buf, P(mood=mood, t=t, bob=0 if t % 20 < 10 else 1,
                        look_x=-1 if t % 30 < 15 else 1, look_y=-1,
                        paw_l="raise"))
            think_dots(buf, t, dots_at)

        elif mood == "work":
            bob = 0 if t % 6 < 3 else 1
            terminal(buf, bob)
            draw(buf, P(mood=mood, t=t, bob=bob, look_x=1, look_y=1,
                        paw_r="type_hi" if t % 4 < 2 else "type_lo",
                        terminal=True))
            if t % 4 < 2:
                plot2(buf, 24, 18 + bob, 7)
            if t % 24 < 6:
                sweat(buf, sweat_xy)

        elif mood == "happy":
            p = t % len(HAPPY_SEQ)
            bob, legs_m, paws, _hold = HAPPY_SEQ[p]
            draw(buf, P(mood=mood, t=t, bob=bob,
                        eyes="squeeze" if p >= 7 else "open",
                        look_y=-1 if bob < 0 else 0,
                        paw_l=paws, paw_r=paws, legs=legs_m))
            confetti(buf, t)

        elif mood == "error":
            draw(buf, P(mood=mood, t=t, eyes="squeeze",
                        look_x=-1 if t % 4 < 2 else 1,
                        paw_l="droop", paw_r="droop"))
            plot2(buf, 3, 8, 12 if t % 2 == 0 else 7)
            plot2(buf, 27, 6, 7 if t % 2 else 12)
            if t % 8 < 4:
                sweat(buf, sweat_xy)

        elif mood == "alert":
            hop = t % 4 < 2
            wave = t % 6 < 3
            draw(buf, P(mood=mood, t=t, bob=-1 if hop else 0, eyes="wide",
                        look_x=-1 if t % 8 < 4 else 1,
                        paw_l="up" if wave else "raise",
                        paw_r="raise" if wave else "up",
                        legs="jump" if hop else "stand"))

        elif mood == "sleep":
            draw(buf, P(mood=mood, t=t, bob=1, eyes="blink", legs="tuck"))
            zzz(buf, t, *zzz_at)

        elif mood in ("walk_l", "walk_r"):
            step = t % 4
            draw(buf, P(mood=mood, t=t, bob=1 if step % 2 else 0,
                        look_x=-1 if mood == "walk_l" else 1,
                        legs="stomp_l" if step < 2 else "stomp_r"))

        elif mood == "poke":
            bob, legs_m, eyes_m, _hold = POKE_SEQ[min(t, len(POKE_SEQ) - 1)]
            draw(buf, P(mood=mood, t=t, bob=bob, eyes=eyes_m, legs=legs_m))

        elif mood == "gym":
            mode, _hold, sw = GYM_SEQ[min(t, len(GYM_SEQ) - 1)]
            draw(buf, P(mood=mood, t=t,
                        eyes="squeeze" if mode == "raise" else "open",
                        paw_l=mode, paw_r=mode))
            barbell(buf, bar_hi if mode == "raise" else bar_lo)
            if sw:
                sweat(buf, sweat_xy)

        elif mood == "soccer":
            ball_by, bob, legs_m, look_y, _hold = SOCCER_SEQ[min(t, len(SOCCER_SEQ) - 1)]
            draw(buf, P(mood=mood, t=t, bob=bob, look_x=-1, look_y=look_y,
                        legs=legs_m))
            ball(buf, ball_x, ball_by)

        else:
            draw(buf, P(mood=mood, t=t))

        return buf

    return build_frame
