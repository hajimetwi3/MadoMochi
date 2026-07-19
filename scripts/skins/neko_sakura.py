"""Neko (sakura) — the teal cat in cherry-blossom pink.

The smallest possible skin: reuse Neko's drawing and timing, swap the wardrobe.
"""

from __future__ import annotations

import importlib.util as _ilu
from pathlib import Path as _Path

_spec = _ilu.spec_from_file_location(
    "buddy_skin_neko_base_for_sakura", _Path(__file__).resolve().parent / "neko.py"
)
_neko = _ilu.module_from_spec(_spec)
_spec.loader.exec_module(_neko)

NAME = "ネコ（さくら）"
NAME_EN = "Neko (Sakura)"
GRID = _neko.GRID
build_frame = _neko.build_frame
frame_hold = _neko.frame_hold
POKE_SEQ = _neko.POKE_SEQ
GYM_SEQ = _neko.GYM_SEQ
SOCCER_SEQ = _neko.SOCCER_SEQ

PALETTE = list(_neko.PALETTE)
PALETTE[1] = "#f2a6b8"   # body sakura pink
PALETTE[2] = "#f9c9d4"   # light
PALETTE[3] = "#b85f78"   # dark
PALETTE[4] = "#d97f95"   # shade
PALETTE[16] = "#8a5464"  # eye-dark AA blend on pink
