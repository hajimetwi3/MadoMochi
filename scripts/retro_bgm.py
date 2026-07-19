"""
Retro-game BGM for the buddy — deliberately cheap, lovable chiptune.

Pure stdlib: wave + math + winsound/winmm (Windows). No pip packages and
no audio files shipped — every track is synthesized on demand and cached
as a tiny WAV under the buddy dir.
Gapless looping via winmm waveOut (WHDR_BEGINLOOP|WHDR_ENDLOOP).
"""

from __future__ import annotations

import ctypes
import math
import struct
import threading
import wave
from ctypes import wintypes
from pathlib import Path

SAMPLE_RATE = 22050

# (id, menu label, approx period sec, bpm for LED)
TRACKS: list[tuple[str, str, float, int]] = [
    ("victory_march", "01 Victory March", 4.0, 128),
    ("modem_memories", "02 Modem Memories", 4.8, 100),
    ("chill_elevator", "03 Chill Elevator", 5.45, 88),
    ("coffee_rush", "04 Coffee Rush", 3.43, 140),
    ("starlight", "05 Starlight", 6.67, 72),
    ("pixel_plaza", "06 Pixel Plaza", 4.36, 110),
    ("bug_chase", "07 Bug Chase", 3.2, 150),
    ("deep_think", "08 Deep Think", 6.0, 66),
    ("terminal_tap", "09 Terminal Tap", 4.0, 118),
    ("morning_build", "10 Morning Build", 4.8, 104),
    ("pixel_waltz", "11 Pixel Waltz", 5.14, 105),
    ("carousel_spin", "12 Carousel Spin", 3.79, 126),
]

TRACK_IDS = [t[0] for t in TRACKS]
TRACK_META = {t[0]: t for t in TRACKS}

# Default LED pattern per track (aesthetic pairing)
TRACK_LED: dict[str, str] = {
    "victory_march": "pulse",
    "modem_memories": "scanner",
    "chill_elevator": "vu",
    "coffee_rush": "equalizer",
    "starlight": "firefly",
    "pixel_plaza": "orbit",
    "bug_chase": "glitch",
    "deep_think": "rain",
    "terminal_tap": "binary",
    "morning_build": "stack",
    "pixel_waltz": "heartbeat",
    "carousel_spin": "strobe",
}

LED_MODES = (
    "scanner",
    "equalizer",
    "pulse",
    "rain",
    "glitch",
    "vu",
    "orbit",
    "binary",
    "firefly",
    "heartbeat",
    "strobe",
    "stack",
)

# mood -> preferred track (used while follow_mood is on)
MOOD_TRACK: dict[str, str] = {
    "work": "coffee_rush",
    "listen": "modem_memories",
    "think": "deep_think",
    "happy": "victory_march",
    "error": "bug_chase",
    "alert": "terminal_tap",
    "sleep": "starlight",
    "idle": "pixel_plaza",
}

# ambient beds the auto-switcher may always replace; urgent moods take over
# regardless, calm moods never yank a user-picked energetic track
AMBIENT_TRACKS = {"pixel_plaza", "starlight", "modem_memories", "deep_think", "morning_build"}
URGENT_MOODS = {"work", "error", "happy", "alert"}

# one-shot sound effects (keyed by the mood/action that triggers them)
SE_IDS = ("happy", "error", "alert", "poke")

# Cache version — bump when render changes
_CACHE_VER = "r1"


def _clamp(x: float, lo: float = -1.0, hi: float = 1.0) -> float:
    return lo if x < lo else hi if x > hi else x


def _square(phase: float) -> float:
    return 1.0 if (phase % 1.0) < 0.5 else -1.0


def _tri(phase: float) -> float:
    p = phase % 1.0
    return 4.0 * p - 1.0 if p < 0.5 else 3.0 - 4.0 * p


def _noise(i: int) -> float:
    x = (i * 1103515245 + 12345) & 0x7FFFFFFF
    return (x / 0x40000000) - 1.0


def _mix_tone(
    buf: list[float],
    freq: float,
    start: float,
    dur: float,
    amp: float,
    kind: str = "square",
    slide: float | None = None,
) -> None:
    n0 = int(start * SAMPLE_RATE)
    n1 = min(len(buf), int((start + dur) * SAMPLE_RATE))
    if n1 <= n0 or freq <= 0:
        return
    for i in range(n0, n1):
        t = (i - n0) / SAMPLE_RATE
        env = 1.0
        atk = 0.006
        rel = 0.03
        if t < atk:
            env = t / atk
        rem = dur - t
        if rem < rel:
            env *= max(0.0, rem / rel)
        f = freq
        if slide is not None:
            f = freq + (slide - freq) * (t / max(dur, 1e-6))
        phase = f * t
        if kind == "square":
            s = _square(phase)
        elif kind == "tri":
            s = _tri(phase)
        elif kind == "noise":
            s = _noise(i) * 0.7
        else:
            s = math.sin(2 * math.pi * phase)
        buf[i] = _clamp(buf[i] + s * amp * env)


def _note(n: int) -> float:
    return 440.0 * (2.0 ** ((n - 69) / 12.0))


# Forced 8th-note counts for tight loops (2 bars = 16 eighths usually)
_FORCE_STEPS: dict[str, int] = {
    "victory_march": 16,
    "modem_memories": 16,
    "chill_elevator": 16,
    "coffee_rush": 16,
    "starlight": 16,
    "pixel_plaza": 16,
    "bug_chase": 16,
    "deep_think": 16,
    "terminal_tap": 16,
    "morning_build": 16,
    "pixel_waltz": 18,  # 3/4-ish: 6 beats * 3 eighth-feel
    "carousel_spin": 16,
}


def _period_seconds(track_id: str) -> float:
    """Snap period to an exact number of 8th-notes so loops land on the grid."""
    meta = TRACK_META.get(track_id, TRACKS[0])
    bpm = meta[3]
    step = 60.0 / bpm / 2.0  # 8th
    steps = _FORCE_STEPS.get(track_id)
    if steps is None:
        steps = max(8, int(round(meta[2] / step)))
    return steps * step


def _render_period(track_id: str, volume: float) -> list[float]:
    dur = _period_seconds(track_id)
    n = int(round(dur * SAMPLE_RATE))
    dur = n / SAMPLE_RATE
    buf = [0.0] * n
    vol = max(0.05, min(0.85, volume))
    meta = TRACK_META.get(track_id, TRACKS[0])
    bpm = meta[3]
    step = 60.0 / bpm / 2.0
    n_steps = max(1, int(round(dur / step)))

    if track_id == "victory_march":
        root = 45
        for i in range(n_steps):
            t0 = i * step
            if i % 8 in (0, 4):
                _mix_tone(buf, 90, t0, 0.08, 0.45 * vol, "sine", slide=45)
            if i % 8 in (2, 6):
                _mix_tone(buf, 1, t0, 0.05, 0.22 * vol, "noise")
            if i % 2 == 0:
                _mix_tone(buf, 1, t0, 0.02, 0.08 * vol, "noise")
            if i % 4 == 0:
                _mix_tone(buf, _note(root + (0 if i % 16 < 8 else -2)), t0, step * 1.5, 0.28 * vol, "square")
            arp = [0, 3, 7, 12, 7, 3]
            _mix_tone(buf, _note(root + 24 + arp[i % len(arp)]), t0, step * 0.7, 0.12 * vol, "square")

    elif track_id == "modem_memories":
        root = 48
        for i in range(n_steps):
            t0 = i * step
            if i % 4 == 0:
                _mix_tone(buf, _note(root), t0, step * 2.5, 0.22 * vol, "square")
            if i % 3 == 0:
                _mix_tone(buf, 400 + (i * 37) % 600, t0, 0.06, 0.1 * vol, "square", slide=900)
            if i % 8 == 4:
                _mix_tone(buf, 1, t0, 0.12, 0.15 * vol, "noise")
            if i % 16 == 0:
                _mix_tone(buf, _note(root + 7), t0, step * 6, 0.08 * vol, "tri")

    elif track_id == "chill_elevator":
        root = 40
        for i in range(n_steps):
            t0 = i * step
            if i % 8 == 0:
                _mix_tone(buf, _note(root), t0, step * 3, 0.3 * vol, "tri")
            if i % 8 == 4:
                _mix_tone(buf, _note(root + 5), t0, step * 2, 0.18 * vol, "square")
            if i % 4 == 2:
                _mix_tone(buf, 1, t0, 0.03, 0.06 * vol, "noise")
            if i % 16 == 12:
                _mix_tone(buf, 880, t0, 0.05, 0.14 * vol, "square")
                _mix_tone(buf, 660, t0 + 0.07, 0.08, 0.12 * vol, "square")

    elif track_id == "coffee_rush":
        root = 50
        for i in range(n_steps):
            t0 = i * step
            if i % 4 == 0:
                _mix_tone(buf, 100, t0, 0.06, 0.4 * vol, "sine", slide=50)
            if i % 4 == 2:
                _mix_tone(buf, 1, t0, 0.04, 0.2 * vol, "noise")
            _mix_tone(buf, 1, t0, 0.012, 0.06 * vol, "noise")
            bass = [0, 0, 3, 0, 5, 0, 3, 0]
            _mix_tone(buf, _note(root + bass[i % 8]), t0, step * 0.85, 0.2 * vol, "square")
            if i % 2 == 1:
                _mix_tone(buf, _note(root + 12 + (i % 5)), t0, step * 0.35, 0.1 * vol, "square")

    elif track_id == "starlight":
        root = 47
        for i in range(n_steps):
            t0 = i * step
            if i % 16 == 0:
                _mix_tone(buf, _note(root), t0, step * 8, 0.16 * vol, "tri")
            if i % 16 == 8:
                _mix_tone(buf, _note(root + 3), t0, step * 6, 0.12 * vol, "tri")
            if i % 8 == 4:
                _mix_tone(buf, _note(root + 10), t0, step * 0.5, 0.08 * vol, "sine")
            if i % 32 == 20:
                _mix_tone(buf, 1, t0, 0.2, 0.05 * vol, "noise")

    elif track_id == "pixel_plaza":
        root = 43
        for i in range(n_steps):
            t0 = i * step
            if i % 4 == 0:
                _mix_tone(buf, 80, t0, 0.09, 0.38 * vol, "sine", slide=40)
            if i % 8 in (2, 6):
                _mix_tone(buf, 1, t0, 0.05, 0.18 * vol, "noise")
            if i % 2 == 0:
                _mix_tone(buf, 1, t0, 0.02, 0.06 * vol, "noise")
            chord = [0, 3, 7] if (i // 8) % 2 == 0 else [0, 5, 8]
            if i % 4 == 0:
                for off in chord:
                    _mix_tone(buf, _note(root + 12 + off), t0, step * 3, 0.07 * vol, "square")
            if i % 8 == 1:
                _mix_tone(buf, _note(root + 24 + (i % 7)), t0, step * 0.6, 0.11 * vol, "square")

    elif track_id == "bug_chase":
        # dense staccato bursts — chase-the-bug panic energy
        root = 52
        for i in range(n_steps):
            t0 = i * step
            if i % 2 == 0:
                _mix_tone(buf, 110, t0, 0.04, 0.35 * vol, "sine", slide=55)
            _mix_tone(buf, 1, t0, 0.01, 0.1 * vol, "noise")
            burst = [0, 7, 12, 15, 12, 7, 3, 10]
            _mix_tone(buf, _note(root + burst[i % 8]), t0, step * 0.35, 0.14 * vol, "square")
            if i % 4 == 3:
                _mix_tone(buf, _note(root + 19), t0, step * 0.2, 0.09 * vol, "square", slide=_note(root + 7))
            if i % 8 == 0:
                _mix_tone(buf, _note(root - 12), t0, step * 1.2, 0.22 * vol, "square")

    elif track_id == "deep_think":
        # slow pondering pad + rare distant blip
        root = 38
        for i in range(n_steps):
            t0 = i * step
            if i % 8 == 0:
                _mix_tone(buf, _note(root), t0, step * 7, 0.2 * vol, "tri")
            if i % 8 == 4:
                _mix_tone(buf, _note(root + 3), t0, step * 5, 0.12 * vol, "tri")
            if i % 16 == 10:
                _mix_tone(buf, 720, t0, 0.04, 0.08 * vol, "sine")
            if i % 16 == 11:
                _mix_tone(buf, 540, t0, 0.08, 0.07 * vol, "sine")
            if i % 4 == 0:
                _mix_tone(buf, 1, t0, 0.04, 0.04 * vol, "noise")

    elif track_id == "terminal_tap":
        # keyboard clack + deep drone
        root = 41
        for i in range(n_steps):
            t0 = i * step
            if i % 4 == 0:
                _mix_tone(buf, _note(root), t0, step * 2.2, 0.26 * vol, "square")
            # keyclick cluster
            if i % 2 == 0:
                _mix_tone(buf, 1200 + (i * 40) % 400, t0, 0.015, 0.06 * vol, "square")
            if i % 8 in (0, 3, 5):
                _mix_tone(buf, 1, t0, 0.02, 0.08 * vol, "noise")
            prompt = [0, 0, 5, 0, 7, 5, 0, 12]
            if i % 2 == 1:
                _mix_tone(buf, _note(root + 12 + prompt[i % 8]), t0, step * 0.4, 0.1 * vol, "square")

    elif track_id == "morning_build":
        # slightly brighter minor -> major tease
        root = 48
        for i in range(n_steps):
            t0 = i * step
            if i % 4 == 0:
                _mix_tone(buf, 95, t0, 0.07, 0.36 * vol, "sine", slide=48)
            if i % 8 in (2, 6):
                _mix_tone(buf, 1, t0, 0.045, 0.16 * vol, "noise")
            prog = [0, 0, 5, 5, 7, 7, 5, 3] if i < 8 else [0, 2, 4, 5, 7, 9, 7, 5]
            _mix_tone(buf, _note(root + prog[i % 8]), t0, step * 0.9, 0.18 * vol, "tri")
            if i % 4 == 2:
                _mix_tone(buf, _note(root + 12 + prog[i % 8]), t0, step * 0.5, 0.09 * vol, "square")

    elif track_id == "pixel_waltz":
        # lopsided 3-feel waltz elegance
        root = 46
        for i in range(n_steps):
            t0 = i * step
            # oom-pa-pa
            if i % 3 == 0:
                _mix_tone(buf, _note(root), t0, step * 0.9, 0.28 * vol, "tri")
                _mix_tone(buf, 70, t0, 0.05, 0.25 * vol, "sine", slide=40)
            else:
                _mix_tone(buf, _note(root + 7), t0, step * 0.45, 0.12 * vol, "square")
                _mix_tone(buf, 1, t0, 0.02, 0.07 * vol, "noise")
            if i % 6 == 5:
                _mix_tone(buf, _note(root + 16), t0, step * 0.6, 0.1 * vol, "sine")

    elif track_id == "carousel_spin":
        # spinning carousel arps
        root = 44
        spin = [0, 3, 7, 10, 12, 10, 7, 3]
        for i in range(n_steps):
            t0 = i * step
            if i % 4 == 0:
                _mix_tone(buf, _note(root - 12), t0, step * 1.8, 0.24 * vol, "square")
            _mix_tone(buf, _note(root + 12 + spin[(i + (i // 4)) % 8]), t0, step * 0.55, 0.13 * vol, "square")
            if i % 8 == 4:
                _mix_tone(buf, 1, t0, 0.06, 0.12 * vol, "noise")
            if i % 2 == 0:
                _mix_tone(buf, _note(root + spin[i % 8]), t0, step * 0.7, 0.1 * vol, "tri")

    else:
        # fallback: quiet tick
        for i in range(n_steps):
            if i % 4 == 0:
                _mix_tone(buf, 200, i * step, 0.05, 0.1 * vol, "sine")

    return _make_seamless(buf)


def _make_seamless(buf: list[float]) -> list[float]:
    """
    Circular crossfade so last samples blend into first — critical for gapless
    hardware loop and for winsound file restart.
    """
    n = len(buf)
    if n < 64:
        return buf
    fade = min(int(0.04 * SAMPLE_RATE), n // 8)  # ~40ms
    out = list(buf)
    for i in range(fade):
        t = (i + 1) / fade
        # end fades toward beginning
        a = out[n - fade + i]
        b = out[i]
        mixed = a * (1.0 - t) + b * t
        out[n - fade + i] = mixed
    # match start to the new end so restart is continuous
    for i in range(fade):
        t = (i + 1) / fade
        out[i] = out[i] * t + out[n - fade + i] * (1.0 - t)
    # tiny edge mute to kill DC click
    edge = min(32, fade // 4)
    for i in range(edge):
        g = i / edge
        out[i] *= g
        out[n - 1 - i] *= g
    return out


def _floats_to_pcm(buf: list[float]) -> bytes:
    pcm = bytearray()
    for s in buf:
        v = int(_clamp(s) * 30000)
        pcm += struct.pack("<h", v)
    return bytes(pcm)


def _render_se(name: str, volume: float) -> list[float]:
    """A sub-second one-shot: fanfare / stumble / chime / squeak."""
    vol = max(0.05, min(0.85, volume))
    if name == "happy":
        # rising arpeggio into a little chord — DONE fanfare
        buf = [0.0] * int(0.8 * SAMPLE_RATE)
        for i, n in enumerate((72, 76, 79)):
            _mix_tone(buf, _note(n), i * 0.09, 0.1, 0.45 * vol, "square")
        for n, a in ((84, 0.35), (79, 0.2), (76, 0.2)):
            _mix_tone(buf, _note(n), 0.28, 0.45, a * vol, "square")
        _mix_tone(buf, 1, 0.28, 0.05, 0.18 * vol, "noise")
    elif name == "error":
        # sad downward slide with a thud at the bottom
        buf = [0.0] * int(0.5 * SAMPLE_RATE)
        _mix_tone(buf, _note(70), 0.0, 0.38, 0.45 * vol, "square", slide=_note(46))
        _mix_tone(buf, 1, 0.34, 0.12, 0.35 * vol, "noise")
    elif name == "alert":
        # two-note doorbell — tri body, octave underlay, bright strike on top
        # (a bare tri chime was too quiet next to the square-wave effects)
        buf = [0.0] * int(0.75 * SAMPLE_RATE)
        for t0, n in ((0.0, 88), (0.3, 84)):
            _mix_tone(buf, _note(n), t0, 0.32, 0.55 * vol, "tri")
            _mix_tone(buf, _note(n - 12), t0, 0.32, 0.28 * vol, "tri")
            _mix_tone(buf, _note(n), t0, 0.05, 0.3 * vol, "square")
    else:  # poke — soft squeak up then down
        buf = [0.0] * int(0.22 * SAMPLE_RATE)
        _mix_tone(buf, 330, 0.0, 0.1, 0.4 * vol, "sine", slide=560)
        _mix_tone(buf, 560, 0.1, 0.1, 0.35 * vol, "sine", slide=260)
    n = len(buf)
    edge = min(64, n // 8)
    for i in range(edge):  # soft edges against clicks
        g = i / edge
        buf[i] *= g
        buf[n - 1 - i] *= g
    return buf


# SE cache version — bump when an effect's render changes (independent of
# the track cache so retuning a chime doesn't re-render all 12 tracks)
_SE_VER = "s2"


def ensure_se_wav(cache_dir: Path, name: str, volume: float) -> Path:
    cache_dir.mkdir(parents=True, exist_ok=True)
    vkey = int(round(max(0.05, min(0.85, volume)) * 20))
    path = cache_dir / f"se_{name}_{_SE_VER}_v{vkey}.wav"
    if path.is_file() and path.stat().st_size > 100:
        return path
    pcm = _floats_to_pcm(_render_se(name, vkey / 20.0))
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SAMPLE_RATE)
        w.writeframes(pcm)
    return path


def ensure_wav(cache_dir: Path, track_id: str, volume: float) -> Path:
    """Write one seamless period as WAV (also used as waveOut buffer source)."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    vkey = int(round(max(0.05, min(0.85, volume)) * 20))
    path = cache_dir / f"{track_id}_{_CACHE_VER}_v{vkey}.wav"
    if path.is_file() and path.stat().st_size > 1000:
        return path
    period = _render_period(track_id, vkey / 20.0)
    pcm = _floats_to_pcm(period)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SAMPLE_RATE)
        w.writeframes(pcm)
    return path


# ---- Gapless winmm waveOut player -------------------------------------------------

class WAVEFORMATEX(ctypes.Structure):
    _fields_ = [
        ("wFormatTag", wintypes.WORD),
        ("nChannels", wintypes.WORD),
        ("nSamplesPerSec", wintypes.DWORD),
        ("nAvgBytesPerSec", wintypes.DWORD),
        ("nBlockAlign", wintypes.WORD),
        ("wBitsPerSample", wintypes.WORD),
        ("cbSize", wintypes.WORD),
    ]


class WAVEHDR(ctypes.Structure):
    _fields_ = [
        ("lpData", ctypes.c_void_p),
        ("dwBufferLength", wintypes.DWORD),
        ("dwBytesRecorded", wintypes.DWORD),
        ("dwUser", ctypes.POINTER(ctypes.c_ulong)),
        ("dwFlags", wintypes.DWORD),
        ("dwLoops", wintypes.DWORD),
        ("lpNext", ctypes.c_void_p),
        ("reserved", ctypes.POINTER(ctypes.c_ulong)),
    ]


WHDR_BEGINLOOP = 0x00000004
WHDR_ENDLOOP = 0x00000008
WHDR_DONE = 0x00000001
WHDR_PREPARED = 0x00000002
WAVE_MAPPER = 0xFFFFFFFF
WAVE_FORMAT_PCM = 1


class GaplessWavePlayer:
    """
    Infinite hardware loop of one PCM buffer via waveOut.
    Avoids winsound SND_LOOP restart gap.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._hwo = wintypes.HANDLE()
        self._hdr: WAVEHDR | None = None
        self._pcm_buf: ctypes.Array | None = None
        self._playing = False
        self._winmm = None
        try:
            self._winmm = ctypes.windll.winmm
        except Exception:
            self._winmm = None

    @property
    def available(self) -> bool:
        return self._winmm is not None

    def play_pcm(self, pcm: bytes, loop: bool = True) -> bool:
        with self._lock:
            self._stop_unlocked()
            if not self._winmm or not pcm:
                return False
            try:
                fmt = WAVEFORMATEX()
                fmt.wFormatTag = WAVE_FORMAT_PCM
                fmt.nChannels = 1
                fmt.nSamplesPerSec = SAMPLE_RATE
                fmt.wBitsPerSample = 16
                fmt.nBlockAlign = 2
                fmt.nAvgBytesPerSec = SAMPLE_RATE * 2
                fmt.cbSize = 0

                hwo = wintypes.HANDLE()
                r = self._winmm.waveOutOpen(
                    ctypes.byref(hwo),
                    WAVE_MAPPER,
                    ctypes.byref(fmt),
                    0,
                    0,
                    0,
                )
                if r != 0:
                    return False

                buf = (ctypes.c_char * len(pcm)).from_buffer_copy(pcm)
                hdr = WAVEHDR()
                hdr.lpData = ctypes.cast(buf, ctypes.c_void_p)
                hdr.dwBufferLength = len(pcm)
                if loop:
                    hdr.dwFlags = WHDR_BEGINLOOP | WHDR_ENDLOOP
                    hdr.dwLoops = 0xFFFFFFFF  # infinite
                else:
                    hdr.dwFlags = 0
                    hdr.dwLoops = 0  # one-shot (sound effect)

                r = self._winmm.waveOutPrepareHeader(hwo, ctypes.byref(hdr), ctypes.sizeof(hdr))
                if r != 0:
                    self._winmm.waveOutClose(hwo)
                    return False
                r = self._winmm.waveOutWrite(hwo, ctypes.byref(hdr), ctypes.sizeof(hdr))
                if r != 0:
                    self._winmm.waveOutUnprepareHeader(hwo, ctypes.byref(hdr), ctypes.sizeof(hdr))
                    self._winmm.waveOutClose(hwo)
                    return False

                self._hwo = hwo
                self._hdr = hdr
                self._pcm_buf = buf  # keep alive
                self._playing = True
                return True
            except Exception:
                self._stop_unlocked()
                return False

    def stop(self) -> None:
        with self._lock:
            self._stop_unlocked()

    def _stop_unlocked(self) -> None:
        if not self._winmm:
            self._playing = False
            return
        try:
            if self._hwo:
                self._winmm.waveOutReset(self._hwo)
                if self._hdr is not None:
                    # wait briefly for DONE
                    for _ in range(50):
                        if self._hdr.dwFlags & WHDR_DONE or not (self._hdr.dwFlags & WHDR_PREPARED):
                            break
                        threading.Event().wait(0.01)
                    try:
                        self._winmm.waveOutUnprepareHeader(
                            self._hwo, ctypes.byref(self._hdr), ctypes.sizeof(self._hdr)
                        )
                    except Exception:
                        pass
                self._winmm.waveOutClose(self._hwo)
        except Exception:
            pass
        self._hwo = wintypes.HANDLE()
        self._hdr = None
        self._pcm_buf = None
        self._playing = False


class RetroBgmPlayer:
    """Play / stop / switch cheap loops — gapless when winmm works."""

    def __init__(self, cache_dir: Path) -> None:
        self.cache_dir = cache_dir
        self.enabled = False
        self.track_id = TRACK_IDS[0]
        self.volume = 0.35
        self.follow_mood = True
        self.se_enabled = False
        self._playing = False
        self._mood = "idle"
        self._user_pick = False
        self._gapless = GaplessWavePlayer()
        self._use_gapless = self._gapless.available
        self._se_player = GaplessWavePlayer()  # own device: SE mix over BGM

    @property
    def bpm(self) -> int:
        return TRACK_META.get(self.track_id, TRACKS[0])[3]

    def set_enabled(self, on: bool) -> None:
        self.enabled = bool(on)
        if self.enabled:
            self._restart()
        else:
            self.stop()

    def set_track(self, track_id: str, user: bool = False) -> None:
        if track_id not in TRACK_META:
            return
        self.track_id = track_id
        self._user_pick = bool(user)
        if self.enabled:
            self._restart()

    def led_for_track(self, track_id: str | None = None) -> str:
        tid = track_id or self.track_id
        return TRACK_LED.get(tid, "scanner")

    def next_track(self) -> str:
        i = TRACK_IDS.index(self.track_id) if self.track_id in TRACK_IDS else 0
        self.set_track(TRACK_IDS[(i + 1) % len(TRACK_IDS)], user=True)
        return self.track_id

    def set_volume(self, vol: float) -> None:
        self.volume = max(0.05, min(0.85, float(vol)))
        if self.enabled and self._playing:
            self._restart()

    def on_mood(self, mood: str) -> None:
        self._mood = mood or "idle"
        if not self.enabled or not self.follow_mood:
            return
        prefer = MOOD_TRACK.get(mood)
        if not prefer or prefer == self.track_id or prefer not in TRACK_META:
            return
        # urgent moods always take the stage; calm ones only replace an
        # auto-picked track or an ambient bed (a hand-picked banger stays)
        calm_ok = (not self._user_pick) or self.track_id in AMBIENT_TRACKS
        if mood in URGENT_MOODS or calm_ok:
            self.set_track(prefer)

    def pause(self) -> None:
        """Silence without flipping `enabled` — resume() picks it back up."""
        if self.enabled:
            self.stop()

    def resume(self) -> None:
        if self.enabled and not self._playing:
            self._restart()

    def play_se(self, name: str) -> None:
        """Fire a one-shot effect; never touches the looping BGM stream."""
        if not self.se_enabled or name not in SE_IDS:
            return
        if not self._se_player.available:
            return  # no winmm: don't risk killing a winsound-fallback loop
        try:
            path = ensure_se_wav(self.cache_dir, name, self.volume)
            with wave.open(str(path), "rb") as w:
                pcm = w.readframes(w.getnframes())
            if pcm:
                self._se_player.play_pcm(pcm, loop=False)
        except Exception:
            pass

    def stop(self) -> None:
        self._gapless.stop()
        self._se_player.stop()
        try:
            import winsound

            winsound.PlaySound(None, winsound.SND_PURGE)
        except Exception:
            pass
        self._playing = False

    def _restart(self) -> None:
        self.stop()
        if not self.enabled:
            return
        try:
            vol = self.volume
            # the WAV cache doubles as a render cache: first play of a
            # (track, volume) renders once, later restarts just read it
            pcm = None
            try:
                path = ensure_wav(self.cache_dir, self.track_id, vol)
                with wave.open(str(path), "rb") as w:
                    pcm = w.readframes(w.getnframes())
            except Exception:
                pcm = None
            if not pcm:
                pcm = _floats_to_pcm(_render_period(self.track_id, vol))

            ok = False
            if self._use_gapless:
                ok = self._gapless.play_pcm(pcm)
            if not ok:
                # Fallback: winsound loop on seamless WAV (may still micro-gap)
                import winsound

                path = ensure_wav(self.cache_dir, self.track_id, vol)
                winsound.PlaySound(
                    str(path),
                    winsound.SND_FILENAME
                    | winsound.SND_ASYNC
                    | winsound.SND_LOOP
                    | winsound.SND_NODEFAULT,
                )
            self._playing = True
        except Exception:
            self._playing = False


# LED pattern generators -----------------------------------------------------------

def led_frame(mode: str, n: int, tick: int, mood: str) -> list[float]:
    out = [0.0] * n
    t = tick

    if mode == "scanner":
        pos = t % (n * 2 - 2) if n > 1 else 0
        if pos >= n:
            pos = (n * 2 - 2) - pos
        for i in range(n):
            d = abs(i - pos)
            out[i] = max(0.0, 1.0 - d * 0.45)

    elif mode == "pulse":
        phase = (t % 8) / 8.0
        base = 0.35 + 0.65 * (1.0 if phase < 0.15 else max(0.0, 1.0 - phase))
        for i in range(n):
            out[i] = base * (0.6 + 0.4 * ((i + t) % 3 == 0))

    elif mode == "rain":
        for i in range(n):
            drop = (t + i * 3) % (n + 4)
            out[i] = 1.0 if drop < 2 else (0.4 if drop < 3 else 0.05)

    elif mode == "glitch":
        seed = (t * 17 + 13) & 255
        for i in range(n):
            v = (seed * (i + 3) + t * 9) & 15
            out[i] = 1.0 if v > 11 else (0.5 if v > 8 else 0.08)
        if t % 11 == 0:
            out = [1.0 - x for x in out]

    elif mode == "vu":
        level = {
            "work": 0.85,
            "alert": 0.95,
            "happy": 0.75,
            "error": 0.7,
            "listen": 0.45,
            "think": 0.35,
            "sleep": 0.15,
            "idle": 0.3,
        }.get(mood, 0.4)
        level = min(1.0, level + 0.1 * math.sin(t * 0.7))
        fill = int(level * n)
        for i in range(n):
            if i < fill - 1:
                out[i] = 0.85
            elif i == fill - 1:
                out[i] = 1.0
            else:
                out[i] = 0.06

    elif mode == "orbit":
        # two counter-rotating blips
        a = t % n
        b = (n - 1 - (t // 2) % n) % n
        for i in range(n):
            d = min(abs(i - a), abs(i - b))
            out[i] = max(0.08, 1.0 - d * 0.55)

    elif mode == "binary":
        # fake bit stream
        word = (0b10110101 ^ (t * 3)) & 0xFFFF
        for i in range(n):
            bit = (word >> (i % 16)) & 1
            out[i] = 0.95 if bit else 0.08
            if (t + i) % 7 == 0:
                out[i] = 1.0 - out[i] * 0.5

    elif mode == "firefly":
        for i in range(n):
            phase = (t * 0.15 + i * 1.7) % (math.pi * 2)
            out[i] = 0.1 + 0.9 * max(0.0, math.sin(phase)) ** 3

    elif mode == "heartbeat":
        # lub-dub
        cyc = t % 12
        spike = 1.0 if cyc in (0, 1, 3, 4) else (0.35 if cyc in (2, 5) else 0.08)
        for i in range(n):
            mid = abs(i - n / 2) / max(n / 2, 1)
            out[i] = spike * (1.0 - mid * 0.4)

    elif mode == "strobe":
        on = (t % 4) < 2
        for i in range(n):
            out[i] = 1.0 if on and (i + t) % 2 == 0 else (0.15 if on else 0.05)

    elif mode == "stack":
        # rising stack then drop
        h = (t % (n + 3))
        for i in range(n):
            out[i] = 0.9 if i < h else 0.08
        if h >= n:
            out = [0.5] * n

    else:  # equalizer
        for i in range(n):
            h = 0.3 + 0.7 * abs(math.sin((t * 0.4) + i * 0.9))
            if mood == "work":
                h = min(1.0, h + 0.2)
            if mood == "sleep":
                h *= 0.35
            out[i] = h

    return out


def mood_led_mode(mood: str) -> str:
    return {
        "work": "equalizer",
        "listen": "scanner",
        "think": "firefly",
        "happy": "pulse",
        "error": "glitch",
        "alert": "strobe",
        "sleep": "rain",
        "idle": "orbit",
    }.get(mood, "scanner")


def mood_led_colors(mood: str) -> tuple[str, str]:
    return {
        "work": ("#fbbf24", "#3d2e0a"),
        "listen": ("#67e8f9", "#0c3a42"),
        "think": ("#c4b5fd", "#2a2040"),
        "happy": ("#2dd4bf", "#0a3d36"),
        "error": ("#fb7185", "#3f1520"),
        "alert": ("#f87171", "#3f1515"),
        "sleep": ("#64748b", "#1e293b"),
        "idle": ("#5eead4", "#134e4a"),
    }.get(mood, ("#5eead4", "#134e4a"))
