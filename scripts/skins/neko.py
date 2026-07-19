"""
Neko — a chibi sitting pixel cat in teal. The mascot-agnostic default skin.

Original silhouette: a two-mass build — round head on a smaller body,
sitting upright — with triangle ears, close-set solid round eyes (house
style: no glint), fine-grid whiskers, a pink nose, front paws and a
wagging tail. Raised paws do maneki-neko duty for the waving / typing /
lifting poses.

Fully standalone (no other skin imported) so it can ship on its own.
"""

from __future__ import annotations

from typing import List

# 0 transparent
PALETTE = [
    None,
    "#3fb8a6",  # 1 body teal
    "#6ecfc0",  # 2 light teal
    "#1f7a6d",  # 3 dark teal
    "#2f9686",  # 4 shade teal (whiskers, paws)
    "#1c2528",  # 5 eyes dark
    "#ffffff",  # 6 white (soccer ball / effects)
    "#fbbf24",  # 7 gold spark
    "#38bdf8",  # 8 cyan (sweat / zzz)
    "#1e293b",  # 9 terminal dark
    "#94a3b8",  # 10 terminal frame gray
    "#4ade80",  # 11 terminal green text
    "#f87171",  # 12 alert / error red
    "#c4b5fd",  # 13 think purple
    "#fda4af",  # 14 pink (inner ears, nose, confetti)
    "#93c5fd",  # 15 pale blue shine
    "#2e6f68",  # 16 eye-dark blended on teal (pixel-art AA)
]

Buf = List[List[int]]

NAME = "ネコ"
NAME_EN = "Neko"

GRID = 64

# geometry in chunky (2-unit) coordinates — tall chibi build:
# ears 7-9, round head 10-19, smaller body 20-26, feet below when walking
HEAD_X0, HEAD_X1 = 9, 22
HEAD_Y0, HEAD_Y1 = 10, 19
BODY_X0, BODY_X1 = 11, 20
BODY_Y0, BODY_Y1 = 20, 26
EYE_XS = (12, 18)           # left col of each 2-wide round eye
EYE_Y0 = 14


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


# ---- baked "> <" squeeze eyes (generic kaomoji glyph, anti-aliased) ----

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


def draw_neko(
    buf: Buf,
    *,
    bob: int = 0,
    eyes: str = "open",         # open | blink | happy | squeeze | wide
    look_x: int = 0,
    look_y: int = 0,
    paw_l: str = "rest",        # rest | raise | up | type_hi | type_lo | droop | hold_lo
    paw_r: str = "rest",
    legs: str = "stand",        # stand | jump | tuck | stomp_l | stomp_r
    tail: str = "wag_a",        # wag_a | wag_b | curl | none
    ear_twitch: bool = False,
    terminal: bool = False,
) -> None:
    oy = bob

    # --- terminal prop first (the typing paw overlaps it) ---
    if terminal:
        rect2(buf, 25, 21 + oy, 30, 28 + oy, 9)
        hline2(buf, 25, 30, 20 + oy, 10)
        hline2(buf, 25, 30, 29 + oy, 10)
        for y in range(21, 29):
            plot2(buf, 25, y + oy, 10)
            plot2(buf, 30, y + oy, 10)
        hline2(buf, 26, 29, 22 + oy, 11)
        hline2(buf, 26, 28, 24 + oy, 11)
        plot2(buf, 29, 26 + oy, 11)

    # --- tail (auto-tucked while the right paw works) ---
    if tail != "none" and paw_r == "rest" and not terminal:
        if tail == "wag_a":
            plot2(buf, 21, 25 + oy, 1)
            plot2(buf, 22, 24 + oy, 1)
            plot2(buf, 22, 23 + oy, 3)
        elif tail == "wag_b":
            plot2(buf, 21, 25 + oy, 1)
            plot2(buf, 22, 25 + oy, 1)
            plot2(buf, 23, 24 + oy, 3)
        elif tail == "curl":
            plot2(buf, 21, 26 + oy, 1)
            plot2(buf, 22, 26 + oy, 3)

    # --- ears (triangles above the head, pink inners) ---
    tw = -1 if ear_twitch else 0
    hline2(buf, 10, 12, 9 + oy, 1)
    plot2(buf, 10 + tw, 8 + oy, 1)
    plot2(buf, 10 + tw, 7 + oy, 1)
    hline2(buf, 19, 21, 9 + oy, 1)
    plot2(buf, 21, 8 + oy, 1)
    plot2(buf, 21, 7 + oy, 1)
    plot2(buf, 11, 9 + oy, 14)
    plot2(buf, 20, 9 + oy, 14)

    # --- round head ---
    hline2(buf, 11, 20, 10 + oy, 1)
    hline2(buf, 10, 21, 11 + oy, 1)
    for y in range(12, 18):
        hline2(buf, 9, 22, y + oy, 1)
    hline2(buf, 10, 21, 18 + oy, 1)
    hline2(buf, 11, 20, 19 + oy, 1)

    # --- body (narrower, sitting) ---
    for y in range(BODY_Y0, BODY_Y1):
        hline2(buf, BODY_X0, BODY_X1, y + oy, 1)
    hline2(buf, BODY_X0 + 1, BODY_X1 - 1, BODY_Y1 + oy, 1)  # rounded bottom

    # --- feet (only while moving; sitting hides them) ---
    if legs == "stomp_l":
        rect2(buf, 12, 27 + oy, 13, 27 + oy, 1)
        rect2(buf, 17, 27 + oy, 18, 28 + oy, 1)
    elif legs == "stomp_r":
        rect2(buf, 12, 27 + oy, 13, 28 + oy, 1)
        rect2(buf, 17, 27 + oy, 18, 27 + oy, 1)
    elif legs == "jump":
        rect2(buf, 12, 27 + oy, 13, 27 + oy, 1)
        rect2(buf, 17, 27 + oy, 18, 27 + oy, 1)

    # --- front paws on the body ---
    plot2(buf, 13, 25 + oy, 4)
    plot2(buf, 14, 25 + oy, 4)
    plot2(buf, 17, 25 + oy, 4)
    plot2(buf, 18, 25 + oy, 4)

    # --- side paws (only when doing something) ---
    def paw(side: str, mode: str) -> None:
        s = -1 if side == "l" else 1
        x0 = 9 if s < 0 else 21   # beside the body/head edge
        x1 = x0 + 1
        if mode == "rest":
            return
        if mode == "raise":
            rect2(buf, x0 + s, 17 + oy, x1 + s, 18 + oy, 1)
        elif mode == "up":
            rect2(buf, x0 + s, 14 + oy, x1 + s, 17 + oy, 1)
        elif mode == "hold_lo":
            rect2(buf, x0 + s, 21 + oy, x1 + s, 22 + oy, 1)
        elif mode == "type_hi":
            rect2(buf, x0 + s * 2, 19 + oy, x1 + s * 2, 20 + oy, 1)
        elif mode == "type_lo":
            rect2(buf, x0 + s * 2, 21 + oy, x1 + s * 2, 22 + oy, 1)
        elif mode == "droop":
            rect2(buf, x0, 23 + oy, x1, 24 + oy, 1)

    paw("l", paw_l)
    paw("r", paw_r)

    # --- eyes (close-set, solid — house style: no glint) ---
    for ex in EYE_XS:
        x = ex + look_x
        y = EYE_Y0 + oy + look_y
        if eyes == "open":
            rect2(buf, x, y, x + 1, y + 1, 5)
        elif eyes == "blink":
            rect2(buf, ex, EYE_Y0 + 1 + oy, ex + 1, EYE_Y0 + 1 + oy, 5)
        elif eyes == "wide":
            rect2(buf, x, EYE_Y0 - 1 + oy, x + 1, EYE_Y0 + 1 + oy, 5)
        elif eyes == "happy":
            if ex == EYE_XS[0]:
                plot2(buf, ex, EYE_Y0 + 1 + oy, 5)
                plot2(buf, ex + 1, EYE_Y0 + oy, 5)
            else:
                plot2(buf, ex, EYE_Y0 + oy, 5)
                plot2(buf, ex + 1, EYE_Y0 + 1 + oy, 5)
        elif eyes == "squeeze":
            fy = EYE_Y0 * 2 - 2 + oy * 2
            if ex == EYE_XS[0]:
                fx = ex * 2 - 2
                pts = _SQ_GT
            else:
                fx = ex * 2 - 3
                pts = _SQ_LT
            for dx, dy, c in pts:
                plot(buf, fx + dx, fy + dy, c)

    # --- nose + whiskers (fine-grid detail) ---
    rect(buf, 31, 34 + oy * 2, 32, 35 + oy * 2, 14)
    for wy in (33, 37):
        rect(buf, 12, wy + oy * 2, 17, wy + oy * 2, 4)
        rect(buf, 46, wy + oy * 2, 51, wy + oy * 2, 4)


def confetti(buf: Buf, t: int) -> None:
    pts = [
        (2, 0, 7), (5, 5, 14), (27, 2, 8), (30, 7, 13),
        (7, 10, 12), (25, 8, 7), (3, 12, 13), (29, 13, 14),
    ]
    for i, (x, phase, c) in enumerate(pts):
        y = (phase + t) % 15
        xx = x + (1 if (t + i) % 4 < 2 else 0)
        plot2(buf, xx, y, c)


def zzz(buf: Buf, t: int) -> None:
    p = t % 9
    if p >= 2:
        plot2(buf, 24, 8, 15)
    if p >= 5:
        plot2(buf, 26, 6, 15)
        plot2(buf, 27, 6, 8)
    if p >= 7:
        plot2(buf, 28, 3, 8)
        plot2(buf, 29, 3, 15)


def _ball(buf: Buf, bx: int, by: int) -> None:
    fx, fy = bx * 2, by * 2
    rect(buf, fx + 1, fy, fx + 2, fy, 9)
    rect(buf, fx, fy + 1, fx, fy + 2, 9)
    rect(buf, fx + 3, fy + 1, fx + 3, fy + 2, 9)
    rect(buf, fx + 1, fy + 3, fx + 2, fy + 3, 9)
    rect(buf, fx + 1, fy + 1, fx + 2, fy + 2, 6)
    plot(buf, fx + 2, fy + 2, 5)


# --- sequence tables: (pose fields..., hold_ms) ---

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


def build_frame(mood: str, t: int) -> Buf:
    buf = empty()
    wag = "wag_a" if t % 16 < 8 else "wag_b"

    if mood == "idle":
        bob = 0 if t % 24 < 12 else 1
        blink = t % 56 < 3
        look = -1 if t % 64 < 20 else (0 if t % 64 < 42 else 1)
        draw_neko(
            buf,
            bob=bob,
            eyes="blink" if blink else "open",
            look_x=look,
            tail=wag,
            ear_twitch=t % 72 < 2,
        )

    elif mood == "listen":
        blink = t % 40 < 2
        look = -1 if t % 24 < 12 else 1
        draw_neko(
            buf,
            bob=-1,
            eyes="blink" if blink else "wide",
            look_x=look,
            paw_l="raise",
            paw_r="raise",
            tail="wag_a",
        )

    elif mood == "think":
        bob = 0 if t % 20 < 10 else 1
        draw_neko(
            buf,
            bob=bob,
            eyes="open",
            look_x=-1 if t % 30 < 15 else 1,
            look_y=-1,
            paw_l="raise",
            tail=wag,
        )
        d = t % 18
        if d > 4:
            plot2(buf, 24, 9, 13)
        if d > 9:
            plot2(buf, 26, 6, 13)
        if d > 14:
            plot2(buf, 28, 3, 13)
            plot2(buf, 29, 3, 15)

    elif mood == "work":
        bob = 0 if t % 6 < 3 else 1
        hi = t % 4 < 2
        draw_neko(
            buf,
            bob=bob,
            eyes="open",
            look_x=1,
            look_y=1,
            paw_r="type_hi" if hi else "type_lo",
            tail="none",
            terminal=True,
        )
        if t % 4 < 2:
            plot2(buf, 24, 18 + bob, 7)
        if t % 24 < 6:
            plot2(buf, 24, 8, 8)
            plot2(buf, 24, 9, 15)

    elif mood == "happy":
        p = t % len(HAPPY_SEQ)
        bob, legs_m, paws, _hold = HAPPY_SEQ[p]
        draw_neko(
            buf,
            bob=bob,
            eyes="squeeze" if p >= 7 else "open",
            look_y=-1 if bob < 0 else 0,
            paw_l=paws,
            paw_r=paws,
            legs=legs_m,
            tail="none",
        )
        confetti(buf, t)

    elif mood == "error":
        shake = -1 if t % 4 < 2 else 1
        draw_neko(
            buf,
            eyes="squeeze",
            look_x=shake,
            paw_l="droop",
            paw_r="droop",
            tail="curl",
        )
        plot2(buf, 3, 8, 12 if t % 2 == 0 else 7)
        plot2(buf, 27, 6, 7 if t % 2 else 12)
        if t % 8 < 4:
            plot2(buf, 24, 8, 8)
            plot2(buf, 24, 9, 15)

    elif mood == "alert":
        # maneki-neko emergency beckoning
        hop = t % 4 < 2
        wave = t % 6 < 3
        draw_neko(
            buf,
            bob=-1 if hop else 0,
            eyes="wide",
            look_x=-1 if t % 8 < 4 else 1,
            paw_l="up" if wave else "raise",
            paw_r="raise" if wave else "up",
            legs="jump" if hop else "stand",
            tail="none",
        )

    elif mood == "sleep":
        draw_neko(
            buf,
            bob=1,
            eyes="blink",
            legs="tuck",
            tail="curl",
        )
        zzz(buf, t)

    elif mood in ("walk_l", "walk_r"):
        step = t % 4
        draw_neko(
            buf,
            bob=1 if step % 2 else 0,
            eyes="open",
            look_x=-1 if mood == "walk_l" else 1,
            legs="stomp_l" if step < 2 else "stomp_r",
            tail=wag,
        )

    elif mood == "poke":
        bob, legs_m, eyes_m, _hold = POKE_SEQ[min(t, len(POKE_SEQ) - 1)]
        draw_neko(buf, bob=bob, eyes=eyes_m, legs=legs_m, tail="wag_b")

    elif mood == "gym":
        mode, _hold, sweat = GYM_SEQ[min(t, len(GYM_SEQ) - 1)]
        draw_neko(
            buf,
            eyes="squeeze" if mode == "raise" else "open",
            paw_l=mode,
            paw_r=mode,
            tail="none",
        )
        bar_y = 16 if mode == "raise" else 21
        hline2(buf, 4, 27, bar_y, 10)
        rect2(buf, 2, bar_y - 1, 4, bar_y + 1, 9)
        rect2(buf, 27, bar_y - 1, 29, bar_y + 1, 9)
        if sweat:
            plot2(buf, 24, 8, 8)
            plot2(buf, 24, 9, 15)

    elif mood == "soccer":
        ball_by, bob, legs_m, look_y, _hold = SOCCER_SEQ[min(t, len(SOCCER_SEQ) - 1)]
        draw_neko(
            buf,
            bob=bob,
            eyes="open",
            look_x=-1,
            look_y=look_y,
            legs=legs_m,
            tail=wag,
        )
        _ball(buf, 2, ball_by)

    else:
        draw_neko(buf)

    return buf


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
