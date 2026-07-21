#!/usr/bin/env python3
"""
MadoMochi — always-on-top floating pixel companion for Claude Code.

- Frameless, chroma-key transparent (Windows)
- Docks to the Claude Code window: bottom-right, above the prompt box
- Follows the window as it moves / hides when Claude is closed or minimized
- Polls ~/.claude/madomochi/status.json (written by Claude Code hooks)
- Poses: idle / listen / think / work / happy(done) / error / alert / sleep
- Extras: variable frame holds, idle walks, premium barbell curls & soccer
  keep-ups (random pick), poke reaction on click (squeeze > < then hop)
- Alert rescue: a permission-wait neglected past roam_after_sec sends the
  buddy wandering across the whole screen until the state resolves
- Skins: any scripts/skins/*.py matching the contract, right-click to switch
- Settings dialog (right-click > Settings…): size / walk / premium / roam sliders
  with a factory-reset button, plus a 60/120/180s showcase demo that runs
  the whole repertoire with music (for recording GIFs)
- Time-of-day: late-night dozing, one morning workout, longer Friday parties
- Retro BGM: 12 built-in chiptune loops (right-click music menu),
  synthesized with the stdlib and looped gaplessly via winmm waveOut;
  optionally re-picks the track to match the mood, pauses while hidden
- LED bar under the sprite: pattern follows the mood ("auto") or a manual
  pick; pairs with the selected track
- UI in English / Japanese: defaults to the Windows display language,
  switchable from the right-click menu (persisted once picked)
- Fractional render scale via PhotoImage zoom/subsample (e.g. 2.4 = 12/5)

Usage:
  python scripts/buddy.py
  python scripts/buddy.py --scale 3
"""

from __future__ import annotations

import argparse
import ctypes
import importlib.util
import json
import os
import random
import sys
import time
import tkinter as tk
import traceback
from datetime import datetime
from fractions import Fraction
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from window_pos import BUDDY_TITLE, place_bottom_right_of_claude  # noqa: E402
from i18n import LANG_LABEL, detect_lang, tr  # noqa: E402
from retro_bgm import (  # noqa: E402
    TRACKS,
    TRACK_META,
    TRACK_LED,
    LED_MODES,
    RetroBgmPlayer,
    led_frame,
    mood_led_mode,
    mood_led_colors,
)

# ---- skins: any scripts/skins/*.py exposing the contract below is selectable ----
SKINS_DIR = Path(__file__).resolve().parent / "skins"
SKIN_CONTRACT = ("PALETTE", "GRID", "build_frame", "frame_hold", "POKE_SEQ", "GYM_SEQ")


def discover_skins() -> dict:
    skins = {}
    for f in sorted(SKINS_DIR.glob("*.py")):
        if f.name.startswith("_"):
            continue
        try:
            spec = importlib.util.spec_from_file_location(f"buddy_skin_{f.stem}", f)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            if all(hasattr(mod, a) for a in SKIN_CONTRACT):
                skins[f.stem] = mod
        except Exception:
            continue  # a broken skin file must never take the buddy down
    return skins

BUDDY_DIR = Path(os.environ.get("CLAUDE_BUDDY_DIR", Path.home() / ".claude" / "madomochi"))
STATUS_PATH = Path(os.environ.get("CLAUDE_BUDDY_STATUS", BUDDY_DIR / "status.json"))
CONFIG_PATH = BUDDY_DIR / "config.json"
CHROMA = "#ff00ff"
ANCHOR_MARGIN_X = 24
ANCHOR_MARGIN_ABOVE_PROMPT = 96
FOLLOW_MS = 250

# idle walk
WALK_DIST = 160          # px to wander left
WALK_SPEED = 3           # px per walk frame
WALK_FAST_SPEED = 9      # hurrying back when work arrives
WALK_PAUSE_FRAMES = 12   # look-around at the far point

# alert roaming / time-of-day
ROAM_SPEED = 4           # px per frame while wandering the screen
ROAM_RETURN_SPEED = 10   # hurrying home once the alert resolves
NIGHT_DOZE_AFTER = 180   # idle seconds before dozing off late at night
MORNING_GYM_AFTER = 20   # settle-in seconds before the once-a-day morning workout

STATUS_LABEL = {
    "idle": "IDLE",
    "listen": "LISTEN",
    "think": "THINK",
    "work": "WORKING",
    "happy": "DONE",
    "error": "ERROR",
    "alert": "WAITING",  # ja override lives in i18n (badge_alert)
    "sleep": "SLEEP",
}
STATUS_COLOR = {
    "idle": "#94a3b8",
    "listen": "#67e8f9",
    "think": "#c4b5fd",
    "work": "#fbbf24",
    "happy": "#2dd4bf",
    "error": "#fb7185",
    "alert": "#f87171",
    "sleep": "#64748b",
}
MOODS = list(STATUS_LABEL)

# mood -> (seconds, next mood): listen settles into think (the model is
# already reasoning by then); everything else eventually falls back to idle
MOOD_DECAY = {
    "listen": (3.0, "think"),
    "happy": (10.0, "idle"),
    "error": (6.0, "idle"),
    "think": (600.0, "idle"),
    "alert": (900.0, "idle"),
}

# work staleness (crash safety net): measured from the LAST hook event, and
# tool-aware — a silent 20-minute Bash build is normal, a silent Edit is not
WORK_DECAY_FAST = 300.0     # 5 min after quick tools
WORK_DECAY_LONG = 1800.0    # 30 min after long-runnable tools
LONG_TOOLS = {"Bash", "PowerShell", "Agent", "Workflow"}

# showcase demo: one ~64s lap of (action, param, seconds), looped to fill
# the chosen duration. Roaming is left out on purpose — it walks the
# window out of a fixed recording frame.
SHOW_LAP = (
    ("mood", "idle", 3),
    ("mood", "listen", 3),
    ("mood", "think", 4),
    ("mood", "work", 8),
    ("mood", "happy", 6),
    ("poke", None, 3),
    ("gym", None, 6),
    ("track", None, 0),
    ("soccer", None, 6),
    ("mood", "error", 5),
    ("walk", None, 12),
    ("mood", "alert", 4),
    ("mood", "sleep", 4),
)

# stage/event variant with the screen-roaming rescue included — opt-in,
# because the window leaves a fixed recording frame (roam brings its own
# alert mood, so it replaces the plain alert act)
SHOW_LAP_FULL = SHOW_LAP[:-2] + (
    ("roam", None, 15),
    ("mood", "sleep", 4),
)


def _clampf(v, lo: float, hi: float, default: float) -> float:
    """Parse a config number defensively: garbage -> default, range enforced."""
    try:
        v = float(v)
    except (TypeError, ValueError):
        return default
    return max(lo, min(v, hi))


def already_running() -> bool:
    try:
        return bool(ctypes.windll.user32.FindWindowW(None, BUDDY_TITLE))
    except Exception:
        return False


_singleton_mutex = None


def acquire_singleton() -> bool:
    """Atomically claim the single-instance slot via a named Windows mutex.

    The window-title check alone races when several hook processes spawn
    the buddy at the same instant. The mutex is held for the process
    lifetime and released by the OS on any exit, so a crash never wedges
    the lock. Fail-open: with no mutex API, run anyway — a rare double
    beats no buddy at all.
    """
    global _singleton_mutex
    try:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CreateMutexW.restype = ctypes.c_void_p
        kernel32.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_wchar_p]
        kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
        handle = kernel32.CreateMutexW(None, 0, "MadoMochiSingleton")
        if not handle:
            return True
        if ctypes.get_last_error() == 183:  # ERROR_ALREADY_EXISTS
            kernel32.CloseHandle(handle)
            return False
        _singleton_mutex = handle  # keep the handle alive with the process
        return True
    except Exception:
        return True


class FloatBuddy:
    def __init__(self, scale: float | None = None) -> None:
        self._cli_scale = scale
        self.scale_value = 2.4
        self.zoom_n, self.zoom_d = 6, 5  # recomputed after config load
        self.mood = "idle"
        self.frame = 0
        self.demo_until = 0.0
        self.mood_since = time.time()
        self.drag_x = 0
        self.drag_y = 0
        self._dragging = False
        self._hidden = False
        self._last_status = ""
        self._status_mtime = -1
        self._status_tool = ""
        self._status_event_at = time.time()
        # rendered-frame cache keyed by pixel content (sprite edits stay safe:
        # different pixels -> different key). FIFO-capped.
        self._img_cache: dict[bytes, tk.PhotoImage] = {}
        self._img_order: list[bytes] = []
        self._img_key: bytes | None = None
        # overlays / roaming
        self.overlay = None          # {"name": "poke"|"gym"|"soccer", "t": int}
        self.walk = None             # {"phase": "out"|"pause"|"back"|"fast", "dx": float, "t", "pt"}
        self.roam = None             # alert-rescue screen roaming {"phase", "x", "y", "tx", "ty"}
        self.roam_after = 120.0      # alert neglected this long -> roam the screen
        self._morning_gym_day = ""
        self._settings_win = None
        self._press_time = 0.0
        self._press_root = (0, 0)
        self._press_moved = False
        # Offset from the default Claude-window anchor (persisted across runs)
        self.user_dx = 0
        self.user_dy = 0
        self.follow = True
        self.badge_mode = "auto"  # auto (hide while idle) | on | off
        self.walk_after = 180.0
        self.premium_min = 90.0
        self.premium_max = 240.0
        # retro BGM + LED bar
        self.bgm_enabled = False
        self.bgm_volume = 0.35
        self.bgm_track = "pixel_plaza"
        self.bgm_follow_mood = True
        self.led_enabled = True
        self.led_h = 16
        self.led_n = 12
        self.led_tick = 0
        self.led_mode = "auto"  # auto = pattern follows the mood
        self.led_cells: list[int] = []
        self.se_enabled = False
        # keep squatting in the desktop corner while Claude's window is gone
        self.park_when_hidden = False
        # UI language: None = follow the Windows display language
        self.lang_pref: str | None = None
        self._born = time.time()  # SE stays quiet during startup catch-up
        self._skin_icons: dict = {}  # name -> tiny menu PhotoImage (lazy)
        self.show = None          # showcase-demo state (settings dialog)
        self._show_after = None
        self.skins = discover_skins()
        if not self.skins:
            raise SystemExit("no valid skins found in scripts/skins/")
        self.skin_name = "neko" if "neko" in self.skins else sorted(self.skins)[0]
        self._load_config()
        self.lang = self.lang_pref or detect_lang()
        self.skin = self.skins[self.skin_name]
        if self._cli_scale is not None:
            self.scale_value = self._cli_scale
        self._compute_zoom(self.scale_value)
        self._sched_reset()

        self.bgm = RetroBgmPlayer(BUDDY_DIR / "bgm_cache")
        self.bgm.volume = self.bgm_volume
        self.bgm.track_id = self.bgm_track if self.bgm_track in TRACK_META else "pixel_plaza"
        self.bgm.follow_mood = self.bgm_follow_mood
        self.bgm.se_enabled = self.se_enabled

        self.root = tk.Tk()
        self.root.title(BUDDY_TITLE)
        self.root.configure(bg=CHROMA)
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        try:
            self.root.wm_attributes("-transparentcolor", CHROMA)
        except tk.TclError:
            self.root.attributes("-alpha", 0.92)

        px = (self.skin.GRID * self.zoom_n - 1) // self.zoom_d + 1
        self.px = px
        self.badge_h = 18
        self.w = max(px + 12, 96)  # LED bar needs a minimum width
        self.led_n = max(8, min(16, self.w // 8))
        self.h = self.badge_h + px + (self.led_h if self.led_enabled else 0) + 6

        x, y = self._follow_xy() or self._fallback_xy()
        self.root.geometry(f"{self.w}x{self.h}+{x}+{y}")

        self.canvas = tk.Canvas(
            self.root,
            width=self.w,
            height=self.h,
            highlightthickness=0,
            bd=0,
            bg=CHROMA,
        )
        self.canvas.pack(fill="both", expand=True)

        bw = min(self.w - 4, 76)
        self.badge_bg = self.canvas.create_rectangle(
            self.w // 2 - bw // 2, 1, self.w // 2 + bw // 2, 16,
            fill="#1e293b", outline="#334155", width=1,
        )
        self.badge_text = self.canvas.create_text(
            self.w // 2, 8, text="IDLE", fill="#94a3b8",
            font=("Segoe UI", 7, "bold"),
        )

        self.img = tk.PhotoImage(width=px, height=px)
        self.canvas_img = self.canvas.create_image(
            self.w // 2, self.badge_h + px // 2, image=self.img, anchor="center",
        )

        # LED bar under the character
        self.led_bg = self.canvas.create_rectangle(
            0, 0, 1, 1, fill="#0a0f18", outline="#1e293b", width=1
        )
        self.led_cells = []
        for _ in range(self.led_n):
            self.led_cells.append(
                self.canvas.create_rectangle(0, 0, 1, 1, fill="#134e4a", outline="#0f172a", width=1)
            )
        self._layout_led()

        self._bind()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self._apply_badge_visibility()
        self._apply_led_visibility()
        self._tick_draw()
        self._tick_status()
        self._tick_follow()
        self._tick_led()
        if self.bgm_enabled:
            if self._hidden:
                self.bgm.enabled = True  # armed but silent; resume() on unhide
            else:
                self.bgm.set_enabled(True)

    # ---------- config ----------

    def _load_config(self) -> None:
        try:
            data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            # every numeric goes through a defensive clamp: a hand-edited or
            # corrupted config must never produce insane behavior
            self.user_dx = int(_clampf(data.get("dx", 0), -4000, 4000, 0))
            self.user_dy = int(_clampf(data.get("dy", 0), -4000, 4000, 0))
            self.follow = bool(data.get("follow", True))
            if data.get("badge") in ("auto", "on", "off"):
                self.badge_mode = data["badge"]
            self.walk_after = _clampf(
                data.get("walk_after_sec", self.walk_after), 10, 3600, 180.0)
            self.premium_min = _clampf(
                data.get("premium_min_sec", self.premium_min), 10, 3600, 90.0)
            self.premium_max = _clampf(
                data.get("premium_max_sec", self.premium_max), 10, 7200, 240.0)
            if self.premium_max < self.premium_min:
                self.premium_max = self.premium_min
            self.roam_after = _clampf(
                data.get("roam_after_sec", self.roam_after), 10, 3600, 120.0)
            self.scale_value = _clampf(
                data.get("scale", self.scale_value), 1.0, 12.0, 2.4)
            self.bgm_enabled = bool(data.get("bgm_enabled", self.bgm_enabled))
            self.bgm_volume = _clampf(
                data.get("bgm_volume", self.bgm_volume), 0.05, 0.85, 0.35)
            tr = data.get("bgm_track", self.bgm_track)
            if tr in TRACK_META:
                self.bgm_track = tr
            self.bgm_follow_mood = bool(data.get("bgm_follow_mood", self.bgm_follow_mood))
            self.led_enabled = bool(data.get("led_enabled", self.led_enabled))
            lm = data.get("led_mode", self.led_mode)
            if lm == "auto" or lm in LED_MODES:
                self.led_mode = lm
            lg = data.get("lang")
            if lg in ("ja", "en"):
                self.lang_pref = lg
            self.se_enabled = bool(data.get("se_enabled", self.se_enabled))
            self.park_when_hidden = bool(
                data.get("park_when_hidden", self.park_when_hidden))
            s = data.get("skin")
            if isinstance(s, str) and s in self.skins:
                self.skin_name = s
        except Exception:
            pass

    def _save_config(self) -> None:
        try:
            BUDDY_DIR.mkdir(parents=True, exist_ok=True)
            CONFIG_PATH.write_text(
                json.dumps(
                    {
                        "dx": self.user_dx,
                        "dy": self.user_dy,
                        "follow": self.follow,
                        "badge": self.badge_mode,
                        "walk_after_sec": self.walk_after,
                        "premium_min_sec": self.premium_min,
                        "premium_max_sec": self.premium_max,
                        "roam_after_sec": self.roam_after,
                        "scale": self.scale_value,
                        "skin": self.skin_name,
                        "bgm_enabled": self.bgm_enabled,
                        "bgm_volume": self.bgm_volume,
                        "bgm_track": self.bgm_track,
                        "bgm_follow_mood": self.bgm_follow_mood,
                        "led_enabled": self.led_enabled,
                        "led_mode": self.led_mode,
                        "se_enabled": self.se_enabled,
                        "park_when_hidden": self.park_when_hidden,
                        "lang": self.lang_pref,  # null = auto (system language)
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
        except Exception:
            pass

    # ---------- schedulers ----------

    def _compute_zoom(self, v: float) -> None:
        # scale keeps its historical meaning (screen px per chunky 2x2 block);
        # the internal grid is fine, hence /2 for the per-unit zoom
        v = max(1.0, min(float(v), 12.0))
        frac = Fraction(v / 2).limit_denominator(16)
        self.scale_value = v
        self.zoom_n = frac.numerator
        self.zoom_d = frac.denominator

    def _now_flavor(self) -> dict:
        lt = time.localtime()
        hour = int(os.environ.get("CLAUDE_BUDDY_FAKE_HOUR", lt.tm_hour))
        wday = int(os.environ.get("CLAUDE_BUDDY_FAKE_WDAY", lt.tm_wday))
        return {
            "night": hour >= 23 or hour < 5,
            "morning": 6 <= hour < 9,
            "friday": wday == 4,
        }

    def _sched_reset(self, which: str = "both") -> None:
        # Reset only the timer that fired — resetting both let whichever event
        # has the shorter interval starve the other forever.
        now = time.time()
        if which in ("both", "walk"):
            self.next_walk = now + self.walk_after
        if which in ("both", "premium"):
            self.next_premium = now + random.uniform(self.premium_min, self.premium_max)

    # ---------- placement ----------

    def _fallback_xy(self) -> tuple[int, int]:
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        return max(20, sw - self.w - 60), max(20, sh - self.h - 120)

    def _park_xy(self) -> tuple[int, int]:
        """The corner cushion: bottom-right of the desktop, above the taskbar."""
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        return max(20, sw - self.w - 24), max(20, sh - self.h - 88)

    def _anchor_xy(self) -> tuple[int, int] | None:
        try:
            return place_bottom_right_of_claude(
                self.w,
                self.h,
                margin_x=ANCHOR_MARGIN_X,
                margin_above_prompt=ANCHOR_MARGIN_ABOVE_PROMPT,
            )
        except Exception:
            return None

    def _follow_xy(self) -> tuple[int, int] | None:
        a = self._anchor_xy()
        if a is None:
            return None
        return a[0] + self.user_dx, a[1] + self.user_dy

    def _set_hidden(self, hidden: bool) -> None:
        if hidden == self._hidden:
            return
        self._hidden = hidden
        try:
            if hidden:
                self.root.withdraw()
            else:
                self.root.deiconify()
                self.root.attributes("-topmost", True)
                self._sched_reset()
        except tk.TclError:
            pass
        # an invisible buddy shouldn't keep the concert going
        try:
            if hidden:
                self.bgm.pause()
            else:
                self.bgm.resume()
        except Exception:
            pass

    def _apply_follow(self) -> None:
        if self._dragging or not self.follow:
            return
        if self.roam:
            return  # roaming owns the window position
        pos = self._follow_xy()
        if pos is None:
            # Claude window gone (closed/minimized) -> hide, unless the user
            # wants the buddy squatting in the desktop corner instead
            if not self.park_when_hidden:
                self._set_hidden(True)
                return
            pos = self._park_xy()
        self._set_hidden(False)
        x, y = pos
        if self.walk:
            x += int(self.walk["dx"])
        try:
            if abs(self.root.winfo_x() - x) < 2 and abs(self.root.winfo_y() - y) < 2:
                return
        except tk.TclError:
            pass
        self.root.geometry(f"+{x}+{y}")

    def _tick_follow(self) -> None:
        try:
            self._apply_follow()
        except Exception:
            pass
        self.root.after(FOLLOW_MS, self._tick_follow)

    # ---------- input ----------

    def _bind(self) -> None:
        for w in (self.canvas, self.root):
            w.bind("<ButtonPress-1>", self._on_press)
            w.bind("<B1-Motion>", self._on_drag)
            w.bind("<ButtonRelease-1>", self._on_release)
        self.canvas.bind("<Double-Button-1>", self._on_double)
        self.canvas.bind("<Button-3>", self._on_menu)
        self.root.bind("<Escape>", lambda e: self._on_close())

    def _on_press(self, e: tk.Event) -> None:
        self._dragging = True
        self._press_moved = False
        self._press_time = time.time()
        self._press_root = (e.x_root, e.y_root)
        self.drag_x = e.x_root - self.root.winfo_x()
        self.drag_y = e.y_root - self.root.winfo_y()

    def _on_drag(self, e: tk.Event) -> None:
        if not self._press_moved:
            if abs(e.x_root - self._press_root[0]) + abs(e.y_root - self._press_root[1]) < 4:
                return
            self._press_moved = True
            self.walk = None  # grabbed mid-walk
            self.roam = None  # grabbing it counts as noticing it
        self.root.geometry(f"+{e.x_root - self.drag_x}+{e.y_root - self.drag_y}")

    def _on_release(self, _e: tk.Event) -> None:
        self._dragging = False
        if not self._press_moved and time.time() - self._press_time < 0.5:
            self._trigger_poke()
            return
        try:
            a = self._anchor_xy()
            if a is not None:
                self.user_dx = self.root.winfo_x() - a[0]
                self.user_dy = self.root.winfo_y() - a[1]
                self._save_config()
        except Exception:
            pass

    def _trigger_poke(self) -> None:
        if self.walk:
            self.walk["phase"] = "fast"
        self.overlay = {"name": "poke", "t": 0}
        try:
            self.bgm.play_se("poke")
        except Exception:
            pass

    def _reset_position(self) -> None:
        self.user_dx = 0
        self.user_dy = 0
        self._save_config()
        self._apply_follow()

    def _on_double(self, _e: tk.Event) -> None:
        i = MOODS.index(self.mood) if self.mood in MOODS else 0
        self._set_mood(MOODS[(i + 1) % len(MOODS)], demo=True)

    def _toggle_follow(self) -> None:
        self.follow = not self.follow
        self._save_config()
        if self.follow:
            self._apply_follow()
        else:
            self._set_hidden(False)

    def _cycle_badge(self) -> None:
        order = ("auto", "on", "off")
        self.badge_mode = order[(order.index(self.badge_mode) + 1) % 3]
        self._save_config()
        self._apply_badge_visibility()

    def _badge_label(self, mood: str) -> str:
        if mood == "alert":
            return tr(self.lang, "badge_alert")
        return STATUS_LABEL.get(mood, "IDLE")

    def _set_lang(self, code: str) -> None:
        if code not in LANG_LABEL or code == self.lang:
            return
        self.lang = code
        self.lang_pref = code  # explicit pick wins over the system language
        win = self._settings_win
        if win is not None and win.winfo_exists():
            win.destroy()  # reopens in the new language
        self._set_mood(self.mood)  # refresh the badge label
        self._save_config()

    def _demo_walk(self) -> None:
        if not self.walk:
            self.overlay = None
            self.walk = {"phase": "out", "dx": 0.0, "t": 0, "pt": 0}

    def _demo_gym(self) -> None:
        self.walk = None
        self.overlay = {"name": "gym", "t": 0}

    def _demo_soccer(self) -> None:
        self.walk = None
        self.overlay = {"name": "soccer", "t": 0}

    def _demo_roam(self) -> None:
        if self.roam:
            return
        self.walk = None
        self.overlay = None
        self._set_mood("alert", demo=True)
        self._set_hidden(False)
        x, y = self.root.winfo_x(), self.root.winfo_y()
        # unlike the real thing (which roams until the alert resolves),
        # the demo tours for a few seconds and then heads home by itself
        self.roam = {
            "phase": "out", "x": float(x), "y": float(y), "tx": x, "ty": y,
            "demo_until": time.time() + 8.0,
        }

    # ---------- alert roam (missed-permission rescue) ----------

    def _maybe_roam(self) -> None:
        if self.roam:
            until = self.roam.get("demo_until")
            if until and time.time() > until and self.mood == "alert":
                self._set_mood("idle")  # demo tour over -> triggers the trip home
            if self.mood != "alert":
                self.roam["phase"] = "back"  # resolved -> hurry home
            return
        if (
            self.mood == "alert"
            and not self._dragging
            and time.time() - self.mood_since > self.roam_after
        ):
            # roam even if Claude is minimized — that is exactly the point
            self._set_hidden(False)
            x, y = self.root.winfo_x(), self.root.winfo_y()
            self.roam = {"phase": "out", "x": float(x), "y": float(y), "tx": x, "ty": y}

    def _roam_step(self) -> None:
        r = self.roam
        speed = ROAM_RETURN_SPEED if r["phase"] == "back" else ROAM_SPEED
        if r["phase"] == "back":
            target = self._follow_xy() or self._fallback_xy()
            r["tx"], r["ty"] = target
        dx = r["tx"] - r["x"]
        dy = r["ty"] - r["y"]
        dist = (dx * dx + dy * dy) ** 0.5
        if dist <= speed:
            r["x"], r["y"] = float(r["tx"]), float(r["ty"])
            if r["phase"] == "back":
                self.roam = None
                self._apply_follow()
                return
            sw = self.root.winfo_screenwidth()
            sh = self.root.winfo_screenheight()
            r["tx"] = random.randint(20, max(21, sw - self.w - 20))
            r["ty"] = random.randint(20, max(21, sh - self.h - 60))
        else:
            r["x"] += dx / dist * speed
            r["y"] += dy / dist * speed
        self.root.geometry(f"+{int(r['x'])}+{int(r['y'])}")

    # ---------- settings dialog ----------

    def _set_scale(self, v: float) -> None:
        old = (self.zoom_n, self.zoom_d)
        self._compute_zoom(v)
        if (self.zoom_n, self.zoom_d) == old:
            return
        self._img_cache.clear()
        self._img_order.clear()
        self._img_key = None
        self._resize_for_skin()

    def _set_premium_avg(self, v) -> None:
        v = float(v)
        self.premium_min = v * 0.75
        self.premium_max = v * 1.25

    def _open_settings(self) -> None:
        win = self._settings_win
        if win is not None and win.winfo_exists():
            win.lift()
            return
        win = tk.Toplevel(self.root)
        self._settings_win = win
        win.title(tr(self.lang, "settings_title"))
        win.attributes("-topmost", True)
        win.resizable(False, False)
        win.geometry(f"+{max(0, self.root.winfo_x() - 280)}+{max(0, self.root.winfo_y() - 160)}")

        scales = {}

        def row(key, label, frm, to, res, init, cb):
            tk.Label(win, text=label, anchor="w").pack(fill="x", padx=12, pady=(8, 0))
            s = tk.Scale(
                win, from_=frm, to=to, resolution=res,
                orient="horizontal", length=230, command=cb,
            )
            s.set(init)
            s.pack(padx=12)
            scales[key] = s

        row("scale", tr(self.lang, "set_scale"), 1.6, 4.0, 0.1, self.scale_value,
            lambda v: self._set_scale(float(v)))
        row("walk", tr(self.lang, "set_walk"), 30, 600, 10, self.walk_after,
            lambda v: setattr(self, "walk_after", float(v)))
        row("premium", tr(self.lang, "set_premium"), 60, 600, 10,
            (self.premium_min + self.premium_max) / 2, self._set_premium_avg)
        row("roam", tr(self.lang, "set_roam"), 30, 600, 10, self.roam_after,
            lambda v: setattr(self, "roam_after", float(v)))

        tk.Label(win, text=tr(self.lang, "show_label"), anchor="w").pack(
            fill="x", padx=12, pady=(10, 0))
        srow = tk.Frame(win)
        srow.pack(pady=(2, 0))
        roam_var = tk.BooleanVar(master=win, value=False)
        for sec in (60, 120, 180):
            tk.Button(
                srow, text=tr(self.lang, "show_btn", n=sec),
                command=lambda ss=sec: self._start_show(ss, roam=bool(roam_var.get())),
            ).pack(side="left", padx=4)
        tk.Button(srow, text=tr(self.lang, "show_stop"), command=self._stop_show).pack(
            side="left", padx=4)
        tk.Checkbutton(win, text=tr(self.lang, "show_roam"), variable=roam_var).pack(
            anchor="w", padx=12)

        def reset_defaults():
            scales["scale"].set(2.4)
            scales["walk"].set(180)
            scales["premium"].set(165)
            scales["roam"].set(120)

            def _exact():
                # slider callbacks fire deferred and only approximate the
                # premium range — restore the exact factory pair after them
                self.premium_min = 90.0
                self.premium_max = 240.0
                self._save_config()

            win.after_idle(_exact)

        def on_close():
            self._save_config()
            self._sched_reset()
            win.destroy()

        btns = tk.Frame(win)
        btns.pack(pady=10)
        tk.Button(btns, text=tr(self.lang, "btn_reset"), command=reset_defaults).pack(side="left", padx=6)
        tk.Button(btns, text=tr(self.lang, "btn_close"), command=on_close).pack(side="left", padx=6)
        win.protocol("WM_DELETE_WINDOW", on_close)

    # ---------- showcase demo (settings dialog) ----------

    def _start_show(self, total: int, roam: bool = False) -> None:
        if self.show:
            self._stop_show()
        # borrow the audio stage; everything is restored by _stop_show
        saved = {
            "bgm": self.bgm_enabled,
            "se": self.se_enabled,
            "follow_mood": self.bgm_follow_mood,
            "track": self.bgm_track,
            "volume": self.bgm_volume,
            "user_pick": self.bgm._user_pick,
        }
        self.show = {
            "end": time.time() + total, "queue": [], "next_at": 0.0,
            "saved": saved, "lap": SHOW_LAP_FULL if roam else SHOW_LAP,
        }
        self.se_enabled = True
        self.bgm.se_enabled = True
        self.bgm_follow_mood = True
        self.bgm.follow_mood = True
        # it's a performance: every mood takes the stage (no sticky picks),
        # and a whisper-quiet volume setting would undersell the music
        self.bgm._user_pick = False
        vol = max(self.bgm_volume, 0.35)
        self.bgm_volume = vol
        self.bgm.set_volume(vol)
        if not self.bgm_enabled:
            self.bgm_enabled = True
            self.bgm.set_enabled(True)
        # pin the demo window so real hook events can't crash the stage
        self.demo_until = self.show["end"] + 1.0
        win = self._settings_win
        if win is not None and win.winfo_exists():
            win.destroy()  # keep the recording frame clean
        self._tick_show()

    def _stop_show(self) -> None:
        s = self.show
        self.show = None
        if self._show_after is not None:
            try:
                self.root.after_cancel(self._show_after)
            except Exception:
                pass
            self._show_after = None
        if not s:
            return
        saved = s["saved"]
        self.demo_until = 0.0
        self.overlay = None
        self.walk = None
        self.bgm_follow_mood = saved["follow_mood"]
        self.bgm.follow_mood = saved["follow_mood"]
        self.se_enabled = saved["se"]
        self.bgm.se_enabled = saved["se"]
        self.bgm_track = saved["track"]
        self.bgm_volume = saved["volume"]
        if saved["bgm"]:
            self.bgm.volume = saved["volume"]
            try:
                self.bgm.set_track(saved["track"])  # restarts at the old volume
            except Exception:
                pass
        else:
            self.bgm_enabled = False
            self.bgm.set_enabled(False)
            self.bgm.volume = saved["volume"]
            self.bgm.track_id = saved["track"]
        self.bgm._user_pick = saved["user_pick"]
        self._set_mood("idle")
        self._sched_reset()

    def _tick_show(self) -> None:
        s = self.show
        if not s:
            return
        now = time.time()
        if now >= s["end"]:
            self._stop_show()
            return
        try:
            if now >= s["next_at"]:
                if not s["queue"]:
                    s["queue"] = list(s["lap"])
                act, param, dur = s["queue"].pop(0)
                if act == "mood":
                    self._set_mood(param)
                elif act == "poke":
                    self._trigger_poke()
                elif act == "gym":
                    self._demo_gym()
                elif act == "soccer":
                    self._demo_soccer()
                elif act == "walk":
                    self._demo_walk()
                elif act == "roam":
                    self._demo_roam()
                    self.demo_until = s["end"] + 1.0  # roam demo shrank the pin
                elif act == "track":
                    self.bgm.next_track()
                    self.bgm._user_pick = False  # stay in performance mode
                    self.bgm_track = self.bgm.track_id
                s["next_at"] = now + dur
        except Exception:
            self._log_error()
        self._show_after = self.root.after(400, self._tick_show)

    def _set_skin(self, name: str) -> None:
        if name not in self.skins or name == self.skin_name:
            return
        self.skin = self.skins[name]
        self.skin_name = name
        # cache keys are pixel indices, valid only per-palette -> flush
        self._img_cache.clear()
        self._img_order.clear()
        self._img_key = None
        self.overlay = None  # sequence tables may differ between skins
        self._resize_for_skin()
        self._save_config()

    def _resize_for_skin(self) -> None:
        px = (self.skin.GRID * self.zoom_n - 1) // self.zoom_d + 1
        self.px = px
        self.w = max(px + 12, 96)
        self.led_n = max(8, min(16, self.w // 8))
        self.h = self.badge_h + px + (self.led_h if self.led_enabled else 0) + 6
        self.canvas.config(width=self.w, height=self.h)
        bw = min(self.w - 4, 76)
        self.canvas.coords(self.badge_bg, self.w // 2 - bw // 2, 1, self.w // 2 + bw // 2, 16)
        self.canvas.coords(self.badge_text, self.w // 2, 8)
        self.canvas.coords(self.canvas_img, self.w // 2, self.badge_h + px // 2)
        self._layout_led()
        self.root.geometry(f"{self.w}x{self.h}")
        self._apply_follow()

    # ---------- LED bar / BGM ----------

    def _layout_led(self) -> None:
        """Position the LED bar under the sprite."""
        if not self.led_cells:
            return
        y0 = self.badge_h + self.px + 2
        pad = 4
        gap = 2
        # ensure cell count matches led_n
        while len(self.led_cells) < self.led_n:
            self.led_cells.append(
                self.canvas.create_rectangle(0, 0, 1, 1, fill="#134e4a", outline="#0f172a", width=1)
            )
        for i, cell in enumerate(self.led_cells):
            st = "normal" if self.led_enabled and i < self.led_n else "hidden"
            self.canvas.itemconfigure(cell, state=st)
        if not self.led_enabled:
            self.canvas.itemconfigure(self.led_bg, state="hidden")
            return
        self.canvas.itemconfigure(self.led_bg, state="normal")
        self.canvas.coords(self.led_bg, 2, y0, self.w - 2, y0 + self.led_h - 2)
        inner_w = self.w - pad * 2
        cell_w = max(3, (inner_w - gap * (self.led_n - 1)) // self.led_n)
        total = cell_w * self.led_n + gap * (self.led_n - 1)
        x0 = (self.w - total) // 2
        for i in range(self.led_n):
            x = x0 + i * (cell_w + gap)
            self.canvas.coords(
                self.led_cells[i],
                x,
                y0 + 3,
                x + cell_w,
                y0 + self.led_h - 5,
            )

    def _apply_led_visibility(self) -> None:
        self.h = self.badge_h + self.px + (self.led_h if self.led_enabled else 0) + 6
        self.canvas.config(height=self.h)
        self.root.geometry(f"{self.w}x{self.h}")
        self._layout_led()
        self._apply_follow()

    def _tick_led(self) -> None:
        ms = 80
        try:
            if not self.led_enabled or self._hidden or not self.led_cells:
                ms = 250
            else:
                self.led_tick += 1
                bpm = self.bgm.bpm if self.bgm_enabled else 100
                if self.mood == "work":
                    self.led_tick += 1
                # pattern: "auto" follows the mood, otherwise the user's pick
                mode = mood_led_mode(self.mood) if self.led_mode == "auto" else self.led_mode
                levels = led_frame(mode, self.led_n, self.led_tick, self.mood)
                on_c, dim_c = mood_led_colors(self.mood)
                for i, lv in enumerate(levels):
                    if i >= len(self.led_cells):
                        break
                    if lv > 0.55:
                        color = on_c
                    elif lv > 0.2:
                        color = on_c if (self.led_tick + i) % 3 else dim_c
                    else:
                        color = dim_c
                    self.canvas.itemconfigure(self.led_cells[i], fill=color)
                ms = max(50, min(120, int(60000 / max(bpm, 60) / 4)))
        except Exception:
            pass
        self.root.after(ms, self._tick_led)

    def _toggle_bgm(self) -> None:
        self.bgm_enabled = not self.bgm_enabled
        self.bgm.volume = self.bgm_volume
        self.bgm.track_id = self.bgm_track
        self.bgm.follow_mood = self.bgm_follow_mood
        self.bgm.set_enabled(self.bgm_enabled)
        self._save_config()

    def _set_bgm_track(self, track_id: str) -> None:
        self.bgm_track = track_id
        self.bgm.volume = self.bgm_volume
        self.bgm.follow_mood = self.bgm_follow_mood
        self.bgm.set_track(track_id, user=True)
        # pair the LED pattern with the track for the full retro aesthetic
        self.led_mode = TRACK_LED.get(track_id, self.led_mode)
        if not self.bgm_enabled:
            self.bgm_enabled = True
            self.bgm.set_enabled(True)
        self._save_config()

    BGM_VOLUMES = (0.1, 0.2, 0.35, 0.5, 0.7)

    def _set_bgm_volume(self, vol: float) -> None:
        self.bgm_volume = max(0.05, min(0.85, float(vol)))
        self.bgm.set_volume(self.bgm_volume)
        self._save_config()

    def _toggle_bgm_follow(self) -> None:
        self.bgm_follow_mood = not self.bgm_follow_mood
        self.bgm.follow_mood = self.bgm_follow_mood
        self._save_config()

    def _toggle_se(self) -> None:
        self.se_enabled = not self.se_enabled
        self.bgm.se_enabled = self.se_enabled
        if self.se_enabled:
            try:
                self.bgm.play_se("poke")  # audible confirmation
            except Exception:
                pass
        self._save_config()

    def _toggle_park(self) -> None:
        self.park_when_hidden = not self.park_when_hidden
        self._save_config()
        self._apply_follow()

    def _toggle_led(self) -> None:
        self.led_enabled = not self.led_enabled
        self._apply_led_visibility()
        self._save_config()

    def _set_led_mode(self, mode: str) -> None:
        if mode != "auto" and mode not in LED_MODES:
            return
        self.led_mode = mode
        if not self.led_enabled:
            self.led_enabled = True  # picking a pattern means wanting to see it
            self._apply_led_visibility()
        self._save_config()

    def _skin_label(self, name: str) -> str:
        mod = self.skins[name]
        label = getattr(mod, "NAME", name)
        if self.lang == "en":
            label = getattr(mod, "NAME_EN", label)
        return label

    def _skin_icon(self, name: str):
        """Tiny transparent face for the skins menu (lazy, cached forever)."""
        if name in self._skin_icons:
            return self._skin_icons[name]
        icon = None
        try:
            mod = self.skins[name]
            grid = mod.GRID
            pal = mod.PALETTE
            buf = mod.build_frame("idle", 0)
            stride = max(1, grid // 21)
            size = (grid + stride - 1) // stride
            icon = tk.PhotoImage(width=size, height=size)
            for y in range(size):
                for x in range(size):
                    # majority color of the source block; empty stays transparent
                    counts: dict = {}
                    for yy in range(y * stride, min((y + 1) * stride, grid)):
                        row = buf[yy]
                        for xx in range(x * stride, min((x + 1) * stride, grid)):
                            c = row[xx]
                            if c and pal[c]:
                                counts[c] = counts.get(c, 0) + 1
                    if counts:
                        icon.put(pal[max(counts, key=counts.get)], to=(x, y))
        except Exception:
            icon = None
        self._skin_icons[name] = icon
        return icon

    def _on_menu(self, e: tk.Event) -> None:
        t = lambda key, **fmt: tr(self.lang, key, **fmt)  # noqa: E731
        menu = tk.Menu(self.root, tearoff=0)
        for m in MOODS:
            label = f"{self._badge_label(m)}  —  {t('speech_' + m)}"
            menu.add_command(label=label, command=lambda mm=m: self._set_mood(mm, demo=True))
        menu.add_separator()
        menu.add_command(label=t("demo_walk"), command=self._demo_walk)
        menu.add_command(label=t("demo_gym"), command=self._demo_gym)
        menu.add_command(label=t("demo_soccer"), command=self._demo_soccer)
        menu.add_command(label=t("demo_roam"), command=self._demo_roam)
        menu.add_separator()
        skin_menu = tk.Menu(menu, tearoff=0)
        for name in sorted(self.skins):
            label = self._skin_label(name)
            if name == self.skin_name:
                label = "● " + label
            icon = self._skin_icon(name)
            kw = {"image": icon, "compound": "left"} if icon else {}
            skin_menu.add_command(
                label=label, command=lambda n=name: self._set_skin(n), **kw
            )
        menu.add_cascade(label=t("skins"), menu=skin_menu)
        menu.add_separator()
        bgm_menu = tk.Menu(menu, tearoff=0)
        bgm_menu.add_command(
            label=t("bgm_off" if self.bgm_enabled else "bgm_on"),
            command=self._toggle_bgm,
        )
        for tid, label, _dur, _bpm in TRACKS:
            mark = "● " if tid == self.bgm_track else ""
            bgm_menu.add_command(
                label=f"{mark}{label}",
                command=lambda tid_=tid: self._set_bgm_track(tid_),
            )
        bgm_menu.add_separator()
        vol_menu = tk.Menu(bgm_menu, tearoff=0)
        for v in self.BGM_VOLUMES:
            mark = "● " if abs(v - self.bgm_volume) < 0.01 else ""
            vol_menu.add_command(
                label=f"{mark}{int(v * 100)}%",
                command=lambda vv=v: self._set_bgm_volume(vv),
            )
        bgm_menu.add_cascade(
            label=t("bgm_volume", pct=int(self.bgm_volume * 100)), menu=vol_menu
        )
        bgm_menu.add_command(
            label=t("bgm_follow_off" if self.bgm_follow_mood else "bgm_follow_on"),
            command=self._toggle_bgm_follow,
        )
        bgm_menu.add_command(
            label=t("se_off" if self.se_enabled else "se_on"),
            command=self._toggle_se,
        )
        menu.add_cascade(label=t("bgm_menu"), menu=bgm_menu)
        menu.add_command(
            label=t("led_off" if self.led_enabled else "led_on"),
            command=self._toggle_led,
        )
        led_menu = tk.Menu(menu, tearoff=0)
        for mode in ("auto",) + LED_MODES:
            mark = "● " if mode == self.led_mode else ""
            label = t("led_auto") if mode == "auto" else mode
            led_menu.add_command(
                label=mark + label,
                command=lambda mm=mode: self._set_led_mode(mm),
            )
        menu.add_cascade(label=t("led_pattern", mode=self.led_mode), menu=led_menu)
        menu.add_separator()
        menu.add_command(label=t("reset_pos"), command=self._reset_position)
        menu.add_command(
            label=t("follow_off" if self.follow else "follow_on"),
            command=self._toggle_follow,
        )
        menu.add_command(
            label=t("park_off" if self.park_when_hidden else "park_on"),
            command=self._toggle_park,
        )
        menu.add_command(label=t("badge_mode", mode=self.badge_mode), command=self._cycle_badge)
        menu.add_command(label=t("topmost_on"), command=lambda: self.root.attributes("-topmost", True))
        menu.add_command(label=t("topmost_off"), command=lambda: self.root.attributes("-topmost", False))
        menu.add_command(label=t("settings"), command=self._open_settings)
        menu.add_separator()
        for code in ("en", "ja"):
            mark = "● " if self.lang == code else ""
            menu.add_command(label=mark + LANG_LABEL[code], command=lambda c=code: self._set_lang(c))
        menu.add_separator()
        menu.add_command(label=t("quit"), command=self._on_close)
        try:
            menu.tk_popup(e.x_root, e.y_root)
        finally:
            menu.grab_release()

    def _on_close(self) -> None:
        try:
            self.bgm.stop()
        except Exception:
            pass
        try:
            # deliberate quit: snooze the hooks' prompt-revival for a while
            BUDDY_DIR.mkdir(parents=True, exist_ok=True)
            (BUDDY_DIR / "quit.ts").write_text(str(time.time()), encoding="utf-8")
        except Exception:
            pass
        self.root.destroy()

    # ---------- state ----------

    def _apply_badge_visibility(self) -> None:
        show = self.badge_mode == "on" or (self.badge_mode == "auto" and self.mood != "idle")
        state = "normal" if show else "hidden"
        self.canvas.itemconfigure(self.badge_bg, state=state)
        self.canvas.itemconfigure(self.badge_text, state=state)

    def _set_mood(self, mood: str, demo: bool = False) -> None:
        mood = mood if mood in STATUS_LABEL else "idle"
        if mood != self.mood:
            self.mood = mood
            self.frame = 0
            self.mood_since = time.time()
            if self.overlay and self.overlay["name"] == "gym":
                self.overlay = None
            if self.walk and mood != "idle":
                self.walk["phase"] = "fast"
            if mood == "idle":
                self._sched_reset()
            try:
                self.bgm.on_mood(mood)
                self.bgm_track = self.bgm.track_id
            except Exception:
                pass
            # punctuating moments get a one-shot; startup catch-up stays quiet
            if (
                mood in ("happy", "error", "alert")
                and not self._hidden
                and time.time() - self._born > 2.0
            ):
                try:
                    self.bgm.play_se(mood)
                except Exception:
                    pass
        self.canvas.itemconfigure(
            self.badge_text,
            text=self._badge_label(self.mood),
            fill=STATUS_COLOR.get(self.mood, "#94a3b8"),
        )
        self._apply_badge_visibility()
        if demo:
            self.demo_until = time.time() + 10

    # ---------- render ----------

    def _advance_render(self) -> tuple[str, int]:
        """Pick the sprite (mood, frame) for this tick and advance its counter."""
        if self.overlay:
            name = self.overlay["name"]
            t = self.overlay["t"]
            self.overlay["t"] += 1
            seq = getattr(self.skin, f"{name.upper()}_SEQ", None)
            length = len(seq) if seq else 1
            if self.overlay["t"] >= length:
                self.overlay = None
                if name in ("gym", "soccer"):
                    self._sched_reset("premium")
            return name, t

        if self.walk:
            w = self.walk
            t = w["t"]
            w["t"] += 1
            if w["phase"] == "out":
                w["dx"] -= WALK_SPEED
                if w["dx"] <= -WALK_DIST:
                    w["phase"] = "pause"
                    w["pt"] = 0
                return "walk_l", t
            if w["phase"] == "pause":
                w["pt"] += 1
                if w["pt"] > WALK_PAUSE_FRAMES:
                    w["phase"] = "back"
                return "idle", t
            speed = WALK_FAST_SPEED if w["phase"] == "fast" else WALK_SPEED
            w["dx"] += speed
            if w["dx"] < 0:
                return "walk_r", t
            self.walk = None
            self._sched_reset("walk")

        if self.mood == "idle" and not self._hidden:
            now = time.time()
            fl = self._now_flavor()
            if fl["night"] and now - self.mood_since > NIGHT_DOZE_AFTER:
                # dozing off after hours (render-only; any event wakes it)
                t = self.frame
                self.frame += 1
                return "sleep", t
            if (
                fl["morning"]
                and self._morning_gym_day != time.strftime("%Y-%m-%d")
                and now - self.mood_since > MORNING_GYM_AFTER
            ):
                self._morning_gym_day = time.strftime("%Y-%m-%d")
                self.overlay = {"name": "gym", "t": 1}
                return "gym", 0
            if now >= self.next_walk:
                self.walk = {"phase": "out", "dx": 0.0, "t": 1, "pt": 0}
                return "walk_l", 0
            if now >= self.next_premium:
                name = random.choice(
                    [n for n in ("gym", "soccer") if hasattr(self.skin, f"{n.upper()}_SEQ")]
                    or ["gym"]
                )
                self.overlay = {"name": name, "t": 1}
                return name, 0

        t = self.frame
        self.frame += 1
        return self.mood, t

    def _paint(self, mood: str, t: int) -> None:
        buf = self.skin.build_frame(mood, t)
        key = bytes(c for row in buf for c in row)
        if key == self._img_key:
            return  # identical frame already on screen
        img = self._img_cache.get(key)
        if img is None:
            grid = self.skin.GRID
            pal = self.skin.PALETTE
            base = tk.PhotoImage(width=grid, height=grid)
            rows = []
            for y in range(grid):
                rows.append(
                    "{"
                    + " ".join(
                        (pal[c] if c and pal[c] else CHROMA) for c in buf[y]
                    )
                    + "}"
                )
            base.put(" ".join(rows), to=(0, 0))
            img = base.zoom(self.zoom_n) if self.zoom_n > 1 else base
            if self.zoom_d > 1:
                img = img.subsample(self.zoom_d)
            self._img_cache[key] = img
            self._img_order.append(key)
            while len(self._img_order) > 256:
                old = self._img_order.pop(0)
                if old == key or old == self._img_key:
                    self._img_order.append(old)  # never evict what's on screen
                    continue
                self._img_cache.pop(old, None)
        self.img = img
        self._img_key = key
        self.canvas.itemconfigure(self.canvas_img, image=img)

    def _log_error(self) -> None:
        try:
            BUDDY_DIR.mkdir(parents=True, exist_ok=True)
            log = BUDDY_DIR / "buddy_err.log"
            if log.is_file() and log.stat().st_size > 1_000_000:
                log.replace(log.with_suffix(".log.old"))
            with log.open("a", encoding="utf-8") as f:
                f.write(f"--- {datetime.now().isoformat()}\n{traceback.format_exc()}\n")
        except Exception:
            pass

    def _tick_draw(self) -> None:
        # A mascot must never freeze: log loop errors and keep ticking.
        hold = 95
        try:
            self._maybe_roam()
            if not self._hidden:
                m, t = self._advance_render()
                self._paint(m, t)
                hold = self.skin.frame_hold(m, t)
                if self.walk:
                    self._apply_follow()
                if self.roam:
                    self._roam_step()
            else:
                self.walk = None
                self.overlay = None
                hold = 250
            self._apply_decay()
        except Exception:
            self._log_error()
        self.root.after(int(hold), self._tick_draw)

    def _apply_decay(self) -> None:
        if time.time() < self.demo_until:
            return
        if self.mood == "work":
            limit = WORK_DECAY_LONG if self._status_tool in LONG_TOOLS else WORK_DECAY_FAST
            if time.time() - self._status_event_at > limit:
                self._set_mood("idle")
            return
        decay = MOOD_DECAY.get(self.mood)
        if not decay:
            return
        limit, nxt = decay
        if self.mood == "happy" and self._now_flavor()["friday"]:
            limit *= 2  # Friday parties run long
        if time.time() - self.mood_since > limit:
            self._set_mood(nxt)

    def _tick_status(self) -> None:
        if time.time() < self.demo_until:
            self.root.after(350, self._tick_status)
            return
        try:
            mtime = STATUS_PATH.stat().st_mtime_ns
            if mtime != self._status_mtime:
                self._status_mtime = mtime
                raw = STATUS_PATH.read_text(encoding="utf-8")
                if raw != self._last_status:
                    self._last_status = raw
                    data = json.loads(raw)
                    self._status_tool = data.get("tool") or ""
                    try:
                        self._status_event_at = datetime.fromisoformat(
                            data["updatedAt"]
                        ).timestamp()
                    except Exception:
                        self._status_event_at = time.time()
                    self._set_mood(data.get("mood") or "idle")
        except Exception:
            pass
        self.root.after(350, self._tick_status)

    def run(self) -> None:
        self.root.mainloop()


def main() -> int:
    parser = argparse.ArgumentParser(description="MadoMochi (floating pixel companion)")
    parser.add_argument(
        "--scale",
        type=float,
        default=None,
        help="Pixel scale, fractions allowed (default: saved setting, else 2.4)",
    )
    parser.add_argument("--force", action="store_true", help="Start even if another instance runs")
    args = parser.parse_args()

    if not args.force and (already_running() or not acquire_singleton()):
        print("MadoMochi is already running.")
        return 0

    BUDDY_DIR.mkdir(parents=True, exist_ok=True)
    print(f"MadoMochi floating - status={STATUS_PATH}")
    print("Drag / click to poke / right-click menu / double-click demo / Esc quit")
    FloatBuddy(scale=args.scale).run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
