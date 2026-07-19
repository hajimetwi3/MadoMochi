"""Render sprite-animation phases to a PNG strip (visual check without launching).

Usage:
    python tests/soccer_strip.py out.png            # soccer, neko skin
    python tests/soccer_strip.py out.png happy      # any mood
    python tests/soccer_strip.py out.png gym neko_sakura
"""

import struct
import sys
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from buddy import discover_skins  # noqa: E402

out = sys.argv[1] if len(sys.argv) > 1 else "strip.png"
mood = sys.argv[2] if len(sys.argv) > 2 else "soccer"
skin_name = sys.argv[3] if len(sys.argv) > 3 else "neko"
skin = discover_skins()[skin_name]
WHITE = (255, 255, 255)


def hex_rgb(h):
    return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))


def write_png(path, w, h, pix):
    raw = b""
    for y in range(h):
        raw += b"\x00" + b"".join(bytes(pix[y][x]) for x in range(w))

    def chunk(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)

    Path(path).write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw))
        + chunk(b"IEND", b"")
    )


S = 3
G = skin.GRID
frames = [0, 2, 4, 8, 16]
W = (G * S + 8) * len(frames)
H = G * S
canvas = [[WHITE] * W for _ in range(H)]
for i, t in enumerate(frames):
    buf = skin.build_frame(mood, t)
    ox = i * (G * S + 8)
    for y in range(G):
        for x in range(G):
            c = buf[y][x]
            if not c or not skin.PALETTE[c]:
                continue
            rgb = hex_rgb(skin.PALETTE[c])
            for sy in range(S):
                for sx in range(S):
                    canvas[y * S + sy][ox + x * S + sx] = rgb
write_png(out, W, H, canvas)
print(f"strip written: {out} ({mood} / {skin_name})")
