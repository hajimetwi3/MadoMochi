"""Big Slime — the same glossy droplet, squished 1.5x wider.

A "filter skin": it loads slime.py and horizontally stretches the body
around the sprite's center axis. Face pixels (eyes, mouth, > < glyphs)
are NOT scaled — each one keeps its true size and only its position
spreads with the stretch, the way a properly drawn big guy works. Props
and effects (soccer ball, confetti, barbell, terminal...) also keep
their true size. Doubles as the worked example of the post-processing
authoring pattern.
"""

from __future__ import annotations

import importlib.util as _ilu
from pathlib import Path as _Path

_spec = _ilu.spec_from_file_location(
    "buddy_skin_slime_src", _Path(__file__).resolve().parent / "slime.py"
)
_slime = _ilu.module_from_spec(_spec)
_spec.loader.exec_module(_slime)

NAME = "ビッグスライム"
NAME_EN = "Big Slime"
PALETTE = list(_slime.PALETTE)
GRID = _slime.GRID

_FACTOR = 1.5
_BODY = {1, 2, 3, 4}   # species colors: stretched
_FACE = {5, 16}        # eyes / mouth / AA glyphs: repositioned, never scaled


def build_frame(mood: str, t: int):
    src = _slime.build_frame(mood, t)
    g = GRID
    cx = (g - 1) / 2
    out = [[0] * g for _ in range(g)]

    # 1. stretched body — face pixels sampled here become body fill so the
    #    relocated eyes don't leave eye-shaped holes behind
    for y in range(g):
        srow = src[y]
        orow = out[y]
        for x in range(g):
            sx = round(cx + (x - cx) / _FACTOR)
            if not 0 <= sx < g:
                continue
            c = srow[sx]
            if c in _BODY:
                orow[x] = c
            elif c in _FACE:
                orow[x] = 1
    # 2. face runs — true size, position spread by the same factor
    for y in range(g):
        srow = src[y]
        orow = out[y]
        x = 0
        while x < g:
            if srow[x] in _FACE:
                x0 = x
                while x < g and srow[x] in _FACE:
                    x += 1
                seq = srow[x0:x]
                rc = (x0 + x - 1) / 2
                nx0 = round(cx + (rc - cx) * _FACTOR - (len(seq) - 1) / 2)
                for i, c in enumerate(seq):
                    if 0 <= nx0 + i < g:
                        orow[nx0 + i] = c
            else:
                x += 1
    # 3. props and effects composite on top, unstretched and unmoved
    for y in range(g):
        srow = src[y]
        orow = out[y]
        for x in range(g):
            c = srow[x]
            if c and c not in _BODY and c not in _FACE:
                orow[x] = c
    return out


frame_hold = _slime.frame_hold
POKE_SEQ = _slime.POKE_SEQ
GYM_SEQ = _slime.GYM_SEQ
SOCCER_SEQ = _slime.SOCCER_SEQ
