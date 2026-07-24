"""
Experimental macOS audio layer for MadoMochi (afplay-based).

The synth is reused from scripts/retro_bgm.py (the WAV renderers are
pure stdlib and platform-free); only playback differs:

- SE one-shots: one `afplay` process per effect (tracked and reaped).
- BGM: `afplay` cannot loop, so a daemon thread respawns it per period.
  There IS an audible seam between repeats; a CoreAudio backend with the
  same class surface would fix that later.
- No `-v` flag on purpose: volume is already baked into the rendered
  WAV by ensure_wav/ensure_se_wav.

Process lifecycle: a Lock guards all process handles,
stop() does terminate -> bounded wait -> kill -> wait, and finished SE
processes are pruned on every new effect.

MacBgmPlayer mirrors retro_bgm.RetroBgmPlayer's public surface so
buddy.py can swap the class per platform. This module must sit next to
retro_bgm.py (apply.py copies it into scripts/).
"""

from __future__ import annotations

import subprocess
import threading
import time

from retro_bgm import (
    AMBIENT_TRACKS,
    MOOD_TRACK,
    SE_IDS,
    TRACK_IDS,
    TRACK_META,
    TRACKS,
    URGENT_MOODS,
    ensure_se_wav,
    ensure_wav,
)


def _spawn_afplay(path):
    return subprocess.Popen(
        ["afplay", str(path)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def _end_proc(p, grace: float = 0.5) -> None:
    """terminate -> bounded wait -> kill -> bounded wait; never hangs."""
    if p is None or p.poll() is not None:
        return
    try:
        p.terminate()
        p.wait(timeout=grace)
    except Exception:
        try:
            p.kill()
            p.wait(timeout=0.2)
        except Exception:
            pass


class MacBgmPlayer:
    """afplay-backed drop-in for RetroBgmPlayer (loop has a small seam)."""

    def __init__(self, cache_dir) -> None:
        self.cache_dir = cache_dir
        self.enabled = False
        self.track_id = TRACK_IDS[0]
        self.volume = 0.35
        self.follow_mood = True
        self.se_enabled = False
        self._playing = False
        self._mood = "idle"
        self._user_pick = False
        self._gen = 0
        self._lock = threading.Lock()
        self._proc = None
        self._se_procs: list = []

    @property
    def bpm(self) -> int:
        return TRACK_META.get(self.track_id, TRACKS[0])[3]

    # ---- same control surface as RetroBgmPlayer --------------------------

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
        calm_ok = (not self._user_pick) or self.track_id in AMBIENT_TRACKS
        if mood in URGENT_MOODS or calm_ok:
            self.set_track(prefer)

    def pause(self) -> None:
        if self.enabled:
            self.stop()

    def resume(self) -> None:
        if self.enabled and not self._playing:
            self._restart()

    def play_se(self, name: str) -> None:
        if not self.se_enabled or name not in SE_IDS:
            return
        try:
            path = ensure_se_wav(self.cache_dir, name, self.volume)
        except Exception:
            return
        with self._lock:
            self._se_procs = [p for p in self._se_procs if p.poll() is None]
            try:
                self._se_procs.append(_spawn_afplay(path))
            except Exception:
                pass

    def stop(self) -> None:
        with self._lock:
            self._gen += 1  # ends the loop thread at its next iteration
            _end_proc(self._proc)
            self._proc = None
            for p in self._se_procs:
                _end_proc(p)
            self._se_procs = []
            self._playing = False

    # ---- playback --------------------------------------------------------

    def _loop(self, gen: int, path) -> None:
        failures = 0
        while True:
            with self._lock:
                if gen != self._gen or not self.enabled:
                    return
                try:
                    proc = _spawn_afplay(path)
                except Exception:
                    self._playing = False
                    return
                self._proc = proc
            try:
                rc = proc.wait()
            except Exception:
                return
            if rc != 0:
                # an instantly-failing afplay must never become a spawn
                # storm: bounded retries with backoff, then give up
                failures += 1
                if failures >= 3:
                    with self._lock:
                        if gen == self._gen:
                            self._playing = False
                    return
                time.sleep(0.5 * failures)
            else:
                failures = 0

    def _restart(self) -> None:
        self.stop()
        if not self.enabled:
            return
        try:
            path = ensure_wav(self.cache_dir, self.track_id, self.volume)
        except Exception:
            self._playing = False
            return
        with self._lock:
            self._gen += 1
            gen = self._gen
            self._playing = True
        threading.Thread(target=self._loop, args=(gen, path), daemon=True).start()
