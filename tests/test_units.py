"""In-process unit tests for the buddy.

Run with the live buddy STOPPED (this creates its own window):
    powershell -File scripts/stop_buddy.ps1
    python tests/test_units.py
    powershell -File scripts/start_buddy.ps1

Structure: each test_* function receives a freshly reset FloatBuddy, so
tests cannot leak state into each other.
"""

import json
import os
import shutil
import sys
import tempfile
import time
import traceback
from pathlib import Path

# hermetic suite: point every buddy path at a throwaway home BEFORE the
# modules resolve them — tests must never touch the real user's state
_TEST_HOME = tempfile.mkdtemp(prefix="buddy_test_")
os.environ["CLAUDE_BUDDY_DIR"] = _TEST_HOME
os.environ["CLAUDE_BUDDY_STATUS"] = str(Path(_TEST_HOME) / "status.json")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import i18n  # noqa: E402
from buddy import FloatBuddy, discover_skins  # noqa: E402

MOODS = ["idle", "listen", "think", "work", "happy", "error", "alert",
         "sleep", "walk_l", "walk_r", "poke", "gym", "soccer"]

# skins that must always ship; extra local-only skins may also be present
# and their absence must not fail the suite
CORE_SKINS = {
    "neko", "neko_sakura", "penguin", "usagi", "obake", "slime", "slime_big",
    "kaeru", "shiba", "fukurou", "tako", "kinoko", "onigiri",
}


def reset(b: FloatBuddy) -> None:
    for k in ("CLAUDE_BUDDY_FAKE_HOUR", "CLAUDE_BUDDY_FAKE_WDAY"):
        os.environ.pop(k, None)
    b.mood = "idle"
    b.mood_since = time.time()
    b.demo_until = 0.0
    b.overlay = None
    b.walk = None
    b.roam = None
    b.frame = 0
    b.walk_after = 180.0
    b.premium_min = 90.0
    b.premium_max = 240.0
    b.roam_after = 120.0
    b._morning_gym_day = ""
    b._status_tool = ""
    b._status_event_at = time.time()
    # BGM stays silent for the whole suite: the player is never enabled here
    b.bgm_enabled = False
    b.bgm.enabled = False
    b.bgm_follow_mood = True
    b.bgm.follow_mood = True
    b.bgm_volume = 0.35
    b.bgm.volume = 0.35
    b.bgm_track = "pixel_plaza"
    b.bgm.track_id = "pixel_plaza"
    b.bgm._user_pick = False
    b.led_mode = "auto"
    if not b.led_enabled:
        b.led_enabled = True
        b._apply_led_visibility()
    b.lang_pref = None
    b.lang = i18n.detect_lang()
    b.se_enabled = False
    b.bgm.se_enabled = False
    b.park_when_hidden = False
    b.show = None
    b.__dict__.pop("_follow_xy", None)  # drop any per-test method shadow
    b._set_hidden(False)
    b._set_scale(2.4)
    b._sched_reset()


def test_all_skins_render(b):
    sk = discover_skins()
    missing = CORE_SKINS - set(sk)
    assert not missing, f"missing skins: {missing}"
    for name, mod in sk.items():
        for m in MOODS:
            for t in range(24):
                buf = mod.build_frame(m, t)
                mx = max(max(r) for r in buf)
                assert mx < len(mod.PALETTE), (name, m, t, mx)
                mod.frame_hold(m, t)


def test_night_doze(b):
    os.environ["CLAUDE_BUDDY_FAKE_HOUR"] = "3"
    b.mood_since = time.time() - 999
    m, _ = b._advance_render()
    assert m == "sleep", m


def test_morning_gym_once(b):
    os.environ["CLAUDE_BUDDY_FAKE_HOUR"] = "7"
    b.mood_since = time.time() - 999
    m, _ = b._advance_render()
    assert m == "gym" and b.overlay and b.overlay["name"] == "gym", m
    assert b._morning_gym_day != ""


def test_premium_rotation(b):
    os.environ["CLAUDE_BUDDY_FAKE_HOUR"] = "14"
    picks = set()
    for _ in range(40):
        b.overlay = None
        b.next_premium = time.time() - 1
        b.next_walk = time.time() + 999
        m, _ = b._advance_render()
        picks.add(m)
    assert picks == {"gym", "soccer"}, picks


def test_friday_flavor(b):
    os.environ["CLAUDE_BUDDY_FAKE_WDAY"] = "4"
    assert b._now_flavor()["friday"]
    os.environ["CLAUDE_BUDDY_FAKE_WDAY"] = "2"
    assert not b._now_flavor()["friday"]


def test_roam_out_and_back(b):
    b.mood = "alert"
    b.mood_since = time.time() - 999
    b.roam_after = 1
    b._maybe_roam()
    assert b.roam is not None and b.roam["phase"] == "out"
    x0, y0 = b.roam["x"], b.roam["y"]
    for _ in range(40):
        b._roam_step()
    moved = abs(b.roam["x"] - x0) + abs(b.roam["y"] - y0)
    assert moved > 50, moved
    b.mood = "idle"
    b._maybe_roam()
    assert b.roam["phase"] == "back"
    for _ in range(2000):
        b._roam_step()
        if b.roam is None:
            break
    assert b.roam is None


def test_roam_demo(b):
    b._demo_roam()
    r = b.roam
    assert r is not None and r["phase"] == "out" and b.mood == "alert"
    b._demo_roam()  # re-click while touring: no restart
    assert b.roam is r
    r["demo_until"] = time.time() - 1  # tour time is up
    b._maybe_roam()
    assert b.mood == "idle" and r["phase"] == "back"
    for _ in range(2000):
        b._roam_step()
        if b.roam is None:
            break
    assert b.roam is None


def test_settings_dialog_and_reset(b):
    import tkinter as tk
    b._open_settings()
    win = b._settings_win
    assert win is not None and win.winfo_exists()
    try:
        scales = [w for w in win.winfo_children() if isinstance(w, tk.Scale)]
        assert len(scales) == 4, len(scales)
        scales[0].set(3.6)
        scales[1].set(60)
        scales[2].set(500)
        scales[3].set(40)
        win.update()
        assert b.scale_value == 3.6 and b.walk_after == 60 and b.roam_after == 40
        btns = [
            w2
            for w in win.winfo_children()
            if isinstance(w, tk.Frame)
            for w2 in w.winfo_children()
            if isinstance(w2, tk.Button)
        ]
        reset_btn = [x for x in btns if x.cget("text") == i18n.STRINGS[b.lang]["btn_reset"]][0]
        reset_btn.invoke()
        win.update()
        assert b.scale_value == 2.4, b.scale_value
        assert b.walk_after == 180.0, b.walk_after
        assert (b.premium_min, b.premium_max) == (90.0, 240.0)
        assert b.roam_after == 120.0, b.roam_after
    finally:
        win.destroy()


def test_work_staleness_tool_aware(b):
    b.mood = "work"
    b._status_tool = "Edit"
    b._status_event_at = time.time() - 301
    b._apply_decay()
    assert b.mood == "idle", b.mood
    b.mood = "work"
    b._status_tool = "Bash"
    b._status_event_at = time.time() - 301
    b._apply_decay()
    assert b.mood == "work", b.mood
    b._status_event_at = time.time() - 1801
    b._apply_decay()
    assert b.mood == "idle", b.mood


def test_mood_decay_chain(b):
    b.mood = "listen"
    b.mood_since = time.time() - 4
    b._apply_decay()
    assert b.mood == "think", b.mood
    b.mood_since = time.time() - 601
    b._apply_decay()
    assert b.mood == "idle", b.mood
    b.mood = "happy"
    b.mood_since = time.time() - 11
    b._apply_decay()
    assert b.mood == "idle", b.mood


def test_scale_change_resizes(b):
    w_before = b.w
    b._set_scale(3.2)
    assert b.w != w_before and b.zoom_n / b.zoom_d == 1.6
    b._set_scale(2.4)


def test_bgm_track_tables(b):
    import retro_bgm as rb
    ids = [t[0] for t in rb.TRACKS]
    assert len(ids) == 12 and len(set(ids)) == 12
    assert set(rb.TRACK_LED) == set(ids)
    assert all(m in rb.LED_MODES for m in rb.TRACK_LED.values())
    assert all(t in rb.TRACK_META for t in rb.MOOD_TRACK.values())
    assert rb.AMBIENT_TRACKS <= set(ids)
    for tid in ids:
        assert rb._period_seconds(tid) > 1.0, tid


def test_bgm_render_seamless(b):
    import retro_bgm as rb
    period = rb._render_period("victory_march", 0.35)
    assert len(period) == int(round(rb._period_seconds("victory_march") * rb.SAMPLE_RATE))
    assert all(-1.0 <= s <= 1.0 for s in period)
    pcm = rb._floats_to_pcm(period)
    assert len(pcm) == 2 * len(period)


def test_led_frames_bounded(b):
    import retro_bgm as rb
    for mode in rb.LED_MODES + ("nope",):
        for tick in range(0, 40, 7):
            for mood in ("idle", "work", "sleep"):
                out = rb.led_frame(mode, b.led_n, tick, mood)
                assert len(out) == b.led_n, mode
                assert all(0.0 <= v <= 1.0001 for v in out), (mode, out)
    for m in ["idle", "listen", "think", "work", "happy", "error", "alert", "sleep"]:
        assert rb.mood_led_mode(m) in rb.LED_MODES
        c = rb.mood_led_colors(m)
        assert len(c) == 2 and all(s.startswith("#") for s in c)


def test_led_toggle_and_pick(b):
    import retro_bgm as rb
    h_on = b.h
    assert b.led_enabled
    b._toggle_led()
    assert not b.led_enabled and b.h == h_on - b.led_h, (b.h, h_on)
    b._set_led_mode("glitch")  # picking a pattern re-enables the bar
    assert b.led_enabled and b.h == h_on and b.led_mode == "glitch"
    for mode in ("auto",) + rb.LED_MODES:
        b._set_led_mode(mode)
        assert b.led_mode == mode
    b._set_led_mode("nope")  # unknown pattern is ignored
    assert b.led_mode == rb.LED_MODES[-1]


def test_bgm_controls_stay_silent(b):
    import retro_bgm as rb
    assert not b.bgm.enabled  # guard: tests must never emit audio
    b.bgm_enabled = True      # pretend the feature is on (player itself stays off)
    b._set_bgm_track("carousel_spin")
    assert b.bgm_track == "carousel_spin" and b.bgm.track_id == "carousel_spin"
    assert b.led_mode == rb.TRACK_LED["carousel_spin"]
    assert not b.bgm.enabled
    b.bgm.set_volume(9.9)
    assert b.bgm.volume == 0.85
    b.bgm.set_volume(-1)
    assert b.bgm.volume == 0.05
    b._set_bgm_volume(0.5)
    assert b.bgm_volume == 0.5 and b.bgm.volume == 0.5
    assert b.bgm.next_track() in rb.TRACK_IDS


def test_bgm_pause_resume(b):
    import retro_bgm as rb
    p = rb.RetroBgmPlayer(Path(_TEST_HOME) / "buddy_test_bgm")
    calls = []

    def fake_restart():
        calls.append(1)
        p._playing = True

    p._restart = fake_restart
    p.pause()
    p.resume()  # disabled -> both no-ops
    assert not calls
    p.enabled = True
    p.resume()
    assert len(calls) == 1
    p.resume()  # already playing -> no double start
    assert len(calls) == 1
    p.pause()
    assert not p._playing
    p.resume()
    assert len(calls) == 2


def test_se_render_and_gate(b):
    import retro_bgm as rb
    for name in rb.SE_IDS:
        buf = rb._render_se(name, 0.35)
        assert buf and all(-1.0 <= s <= 1.0 for s in buf), name
        assert len(buf) < rb.SAMPLE_RATE, name  # one-shots stay under 1s
    # gate behavior on a dedicated winmm-backend instance — the live
    # buddy's backend may differ (MacBgmPlayer after the macOS apply)
    p = rb.RetroBgmPlayer(Path(_TEST_HOME) / "buddy_test_bgm")
    calls = []
    p._se_player._winmm = True  # pretend a device exists; emit is stubbed
    p._se_player.play_pcm = lambda pcm, loop=True: calls.append(loop)
    p.se_enabled = False
    p.play_se("happy")
    assert not calls  # disabled -> silent
    p.se_enabled = True
    p.play_se("happy")
    assert calls == [False]  # fired once, as a one-shot
    p.play_se("nope")
    assert calls == [False]  # unknown id ignored


def test_park_mode(b):
    b.park_when_hidden = True
    b._follow_xy = lambda: None  # simulate: Claude window gone
    b._apply_follow()
    b.root.update()
    assert not b._hidden
    px, py = b._park_xy()
    assert abs(b.root.winfo_x() - px) <= 2 and abs(b.root.winfo_y() - py) <= 2
    b.park_when_hidden = False
    b._apply_follow()
    assert b._hidden  # parking off -> back to hiding


def test_skin_icons(b):
    ic = b._skin_icon("neko")
    assert ic is not None and 8 <= ic.width() <= 24 and ic.height() == ic.width()
    assert b._skin_icon("neko") is ic  # cached
    for name in CORE_SKINS:
        assert b._skin_icon(name) is not None, name


def test_show_mode(b):
    # audio fully stubbed (backend-agnostic): the show must run silent
    b.bgm.play_se = lambda name: None
    b.bgm._restart = lambda: None
    flips = []
    b.bgm.set_enabled = lambda on: (setattr(b.bgm, "enabled", bool(on)), flips.append(bool(on)))
    b.bgm_volume = 0.2       # whisper-quiet user setting...
    b.bgm.volume = 0.2
    b.bgm._user_pick = True  # ...and a sticky hand-picked track
    b._start_show(60)
    assert b.show is not None
    assert b.se_enabled and b.bgm.se_enabled and b.bgm_follow_mood
    assert b.bgm_enabled and b.bgm.enabled and flips == [True]
    assert b.bgm_volume == 0.35 and b.bgm.volume == 0.35  # stage floor
    assert not b.bgm._user_pick  # performance mode: every mood switches
    assert b.demo_until > time.time() + 50  # real events stay locked out
    assert b.mood == "idle"  # act 1 (establishing idle) ran on start
    b.show["next_at"] = 0.0
    b._tick_show()  # act 2: listen
    assert b.mood == "listen"
    assert b.bgm.track_id == "modem_memories"  # calm moods switch too now
    b.show["next_at"] = 0.0
    b._tick_show()  # act 3: think
    assert b.mood == "think"
    assert b.bgm.track_id == "deep_think"
    b._stop_show()
    assert b.show is None and b.demo_until == 0.0
    assert not b.se_enabled and not b.bgm.se_enabled
    assert not b.bgm_enabled and flips == [True, False]
    assert b.bgm.track_id == "pixel_plaza"  # stage props returned
    assert b.bgm_volume == 0.2 and b.bgm.volume == 0.2
    assert b.bgm._user_pick
    assert b.mood == "idle"
    b._stop_show()  # idempotent
    assert b.show is None


def test_show_roam_lap(b):
    b.bgm.play_se = lambda name: None  # backend-agnostic silence
    b.bgm._restart = lambda: None
    b.bgm.set_enabled = lambda on: setattr(b.bgm, "enabled", bool(on))
    b._start_show(60, roam=True)
    assert any(act == "roam" for act, _p, _d in b.show["lap"])
    for _ in range(len(b.show["lap"]) + 2):
        b.show["next_at"] = 0.0
        b._tick_show()
        if b.roam:
            break
    assert b.roam is not None and b.mood == "alert"
    assert b.demo_until > time.time() + 40  # pin restored after the roam act
    b._stop_show()
    assert b.show is None
    b.roam = None


def test_big_slime_wider(b):
    sk = discover_skins()
    body = (1, 2, 3, 4, 5, 16)

    def width(mod):
        w = 0
        for row in mod.build_frame("idle", 0):
            xs = [x for x, c in enumerate(row) if c in body]
            if xs:
                w = max(w, xs[-1] - xs[0] + 1)
        return w

    ws, wb = width(sk["slime"]), width(sk["slime_big"])
    assert ws * 1.3 < wb <= 64, (ws, wb)  # stretched, but inside the grid

    def eye_px(mod):
        return sum(row.count(5) for row in mod.build_frame("idle", 0))

    # the face is repositioned, never scaled: same pixel count as the original
    assert eye_px(sk["slime"]) == eye_px(sk["slime_big"])


def test_hook_scrub(b):
    import install_hooks as ih
    settings = {
        "hooks": {
            "Stop": [
                {"hooks": [
                    {"command": "pythonw", "args": ["C:/a/hook_entry.py", "--hajimetwi3-buddy-hook"]},
                    {"command": "pythonw", "args": ["C:/other-product/hook_entry.py"]},
                    {"command": "pythonw", "args": ["C:/foreign/hook.py", "--buddy-hook-extra"]},
                    {"command": "python", "args": ["C:/foreign/product.py", "--buddy-hook"]},
                    {"command": "other-tool", "args": []},
                ]},
            ],
            "SessionStart": [
                {"hooks": [{"command": "pythonw", "args": ["{{HOOK_ENTRY}}"]}]},
            ],
            "Notification": [  # a pre-marker install of THIS repo (exact path)
                {"hooks": [{"command": "pythonw", "args": [str(ih.HOOK_SCRIPT)]}]},
            ],
        },
        "model": "keep-me",
    }
    ih.scrub_buddy_hooks(settings)
    assert settings["model"] == "keep-me"           # unrelated keys untouched
    assert "SessionStart" not in settings["hooks"]  # template wiring removed
    assert "Notification" not in settings["hooks"]  # legacy exact-path removed
    remaining = settings["hooks"]["Stop"][0]["hooks"]
    assert len(remaining) == 4  # only the marked entry scrubbed, foreign kept
    assert {"command": "pythonw", "args": ["C:/other-product/hook_entry.py"]} in remaining
    # exact-element matching: a marker-like substring is NOT ours
    assert {"command": "pythonw", "args": ["C:/foreign/hook.py", "--buddy-hook-extra"]} in remaining
    # a foreign product using the generic flag "--buddy-hook" is NOT ours either
    assert {"command": "python", "args": ["C:/foreign/product.py", "--buddy-hook"]} in remaining
    assert {"command": "other-tool", "args": []} in remaining
    ih.scrub_buddy_hooks({})  # no hooks key -> no crash
    s2 = {"hooks": {"Stop": [{"hooks": [{"command": "x", "args": ["--hajimetwi3-buddy-hook"]}]}]}}
    ih.scrub_buddy_hooks(s2)
    assert "hooks" not in s2  # a fully-emptied hooks table is dropped


def test_status_write_atomic(b):
    import hook_entry as he
    he.write_status("happy", "unit-test", tool="", event="Test")
    data = json.loads(he.STATUS_PATH.read_text(encoding="utf-8"))
    assert data["mood"] == "happy" and data["event"] == "Test"
    # the per-process temp file never lingers
    assert list(he.STATUS_PATH.parent.glob("status.*.tmp")) == []


def test_notification_filter(b):
    import hook_entry as he
    noise = he.notification_is_noise
    assert not noise("Notification", {})  # no field -> alert (older versions)
    assert not noise("Notification", {"notification_type": "permission_prompt"})
    assert not noise("Notification", {"notification_type": "idle_prompt"})
    assert not noise("Notification", {"notification_type": "agent_needs_input"})
    assert noise("Notification", {"notification_type": "auth_success"})
    assert noise("notification", {"notification_type": "elicitation_complete"})
    assert not noise("Stop", {"notification_type": "auth_success"})  # wrong event


def test_permission_request_mood(b):
    import hook_entry as he
    assert he.EVENT_TO_MOOD["PermissionRequest"] == ("alert", "waiting for approval")
    assert he.EVENT_TO_MOOD["permission_request"][0] == "alert"
    # PermissionRequest is not a Notification: the noise filter must not eat it
    assert not he.notification_is_noise(
        "PermissionRequest", {"notification_type": "auth_success"})


def test_skip_line_shape_only(b):
    import hook_entry as he
    os.environ.pop("MADOMOCHI_HOOK_DEBUG", None)
    line = he._skip_line("SecretEventName", '{"x": 1}', {
        "session_id": "s", "some_private_thing": 1, "message": "hello"})
    # default: unknown names never echoed - neither the event nor fields
    assert "SecretEventName" not in line and "some_private_thing" not in line
    assert "session_id" in line and "message" in line and "<+1 unknown>" in line
    assert "hello" not in line  # values never, in any mode
    os.environ["MADOMOCHI_HOOK_DEBUG"] = "1"
    try:
        line = he._skip_line("NewEventName", "", {"weird field!": 1})
        assert "NewEventName" in line  # local diagnosis shows identifiers...
        assert "weird field!" not in line and "<odd>" in line  # ...only
    finally:
        os.environ.pop("MADOMOCHI_HOOK_DEBUG", None)


def test_event_argv_fallback(b):
    import hook_entry as he
    argv = ["hook_entry.py", "--hajimetwi3-buddy-hook", "Stop"]
    assert he.resolve_event({}, argv) == "Stop"  # empty stdin -> wiring name
    assert he.resolve_event({"hook_event_name": "PreToolUse"}, argv) == "PreToolUse"
    assert he.resolve_event({}, ["hook_entry.py", "--hajimetwi3-buddy-hook"]) == ""
    assert he.resolve_event({}, ["hook_entry.py", "NotAnEvent"]) == ""
    # a marker-only foreign arg must never look like an event
    assert he.resolve_event({}, ["hook_entry.py", "--hajimetwi3-buddy-hook",
                                 "PermissionRequest"]) == "PermissionRequest"


def test_template_wiring(b):
    tpl = json.loads(
        (Path(__file__).resolve().parent.parent
         / "install.settings" / "settings.template.json").read_text(encoding="utf-8"))
    import hook_entry as he
    assert "PermissionRequest" in tpl["hooks"], "permission prompts need their own event"
    for event, groups in tpl["hooks"].items():
        assert event in he.EVENT_TO_MOOD, f"template wires unknown event {event}"
        for g in groups:
            for h in g["hooks"]:
                assert h["args"][0] == "{{HOOK_ENTRY}}"
                assert "--hajimetwi3-buddy-hook" in h["args"]
                # the wiring names its own event so empty-stdin invocations
                # (claude-code #38162) still identify themselves
                assert h["args"][-1] == event, f"{event}: args must end with the event"
                if event == "PermissionRequest":
                    # synchronous decider path: async would break the
                    # permission flow, and a wedged hook must not hold
                    # the prompt hostage for long
                    assert "async" not in h and h["timeout"] <= 5
                else:
                    assert h.get("async") is True


def test_singleton_mutex(b):
    import buddy as bd
    assert bd.acquire_singleton()  # slot free (live buddy stopped for tests)
    assert not bd.acquire_singleton()  # second claim must fail atomically


def test_quit_snooze(b):
    import hook_entry as he
    he.QUIT_TS.parent.mkdir(parents=True, exist_ok=True)
    he.QUIT_TS.write_text("x", encoding="utf-8")
    assert he.recently_quit()  # fresh deliberate quit -> snoozed
    old = time.time() - he.QUIT_SNOOZE - 5
    os.utime(he.QUIT_TS, (old, old))
    assert not he.recently_quit()  # snooze expired
    he.QUIT_TS.unlink()
    assert not he.recently_quit()  # no marker at all


def test_mac_audio_backend(b):
    mac_dir = Path(__file__).resolve().parent.parent / "experimental" / "macos"
    if not (mac_dir / "mac_audio.py").is_file():
        return  # scaffold not shipped in this tree
    sys.path.insert(0, str(mac_dir))
    import mac_audio as ma

    class _Proc:
        """Fake afplay that exits instantly with a nonzero code."""

        def __init__(self, rc):
            self._rc = rc
            self._done = False

        def poll(self):
            return self._rc if self._done else None

        def wait(self, timeout=None):
            self._done = True
            return self._rc

        def terminate(self):
            self._done = True

        def kill(self):
            self._done = True

    spawned = []
    orig = ma._spawn_afplay
    ma._spawn_afplay = lambda path: (spawned.append(str(path)), _Proc(1))[1]
    try:
        p = ma.MacBgmPlayer(Path(_TEST_HOME) / "buddy_test_bgm")
        # SE gate: same semantics as the winmm backend
        p.se_enabled = False
        p.play_se("happy")
        assert spawned == []
        p.se_enabled = True
        p.play_se("happy")
        assert len(spawned) == 1
        p.play_se("nope")
        assert len(spawned) == 1
        # BGM: an instantly-failing afplay must stop after bounded retries,
        # never turn into a spawn storm
        p.enabled = True
        p.set_track("victory_march")
        deadline = time.time() + 6
        while time.time() < deadline and p._playing:
            time.sleep(0.05)
        assert not p._playing  # gave up on its own
        assert len(spawned) - 1 == 3  # exactly the bounded retry count
        p.stop()
    finally:
        ma._spawn_afplay = orig


def test_i18n_tables(b):
    import re
    from buddy import MOODS as ALL_MOODS
    en, ja = i18n.STRINGS["en"], i18n.STRINGS["ja"]
    assert set(en) == set(ja)
    for k in en:
        assert set(re.findall(r"{\w*}", en[k])) == set(re.findall(r"{\w*}", ja[k])), k
    assert {f"speech_{m}" for m in ALL_MOODS} <= set(en)
    assert i18n.detect_lang() in ("en", "ja")
    assert i18n.tr("en", "nope_key") == "nope_key"      # unknown key -> key
    assert i18n.tr("zz", "quit") == en["quit"]          # unknown lang -> en
    assert i18n.tr("ja", "bgm_volume", pct=50) == "音量（今: 50%）"


def test_language_switch(b):
    b._set_lang("en")
    assert b.lang == "en" and b.lang_pref == "en"
    assert b._badge_label("alert") == "WAITING"
    assert b._badge_label("work") == "WORKING"
    sk = discover_skins()
    for name in CORE_SKINS:
        label = getattr(sk[name], "NAME_EN", getattr(sk[name], "NAME", name))
        assert label.isascii(), (name, label)
    b._set_lang("ja")
    assert b.lang == "ja" and b.lang_pref == "ja"
    assert b._badge_label("alert") == "確認待ち"
    b._set_lang("xx")  # unknown code is ignored
    assert b.lang == "ja"


def test_bgm_mood_follow_logic(b):
    import retro_bgm as rb
    p = rb.RetroBgmPlayer(Path(_TEST_HOME) / "buddy_test_bgm")
    p.enabled = True  # exercise the switching logic only...
    p._restart = lambda: None  # ...never the audio device
    p.track_id = "pixel_plaza"
    p.on_mood("work")
    assert p.track_id == "coffee_rush"
    p.on_mood("idle")  # auto-picked track -> calm mood may replace it
    assert p.track_id == "pixel_plaza"
    p.set_track("coffee_rush", user=True)
    p.on_mood("idle")  # hand-picked energetic track survives calm moods
    assert p.track_id == "coffee_rush"
    p.on_mood("happy")  # urgent moods always take the stage
    assert p.track_id == "victory_march"
    p.follow_mood = False
    p.on_mood("error")
    assert p.track_id == "victory_march"


TESTS = [
    test_all_skins_render,
    test_night_doze,
    test_morning_gym_once,
    test_premium_rotation,
    test_friday_flavor,
    test_roam_out_and_back,
    test_roam_demo,
    test_settings_dialog_and_reset,
    test_work_staleness_tool_aware,
    test_mood_decay_chain,
    test_scale_change_resizes,
    test_bgm_track_tables,
    test_bgm_render_seamless,
    test_led_frames_bounded,
    test_led_toggle_and_pick,
    test_bgm_controls_stay_silent,
    test_bgm_pause_resume,
    test_bgm_mood_follow_logic,
    test_mac_audio_backend,
    test_se_render_and_gate,
    test_park_mode,
    test_skin_icons,
    test_show_mode,
    test_show_roam_lap,
    test_big_slime_wider,
    test_hook_scrub,
    test_status_write_atomic,
    test_notification_filter,
    test_permission_request_mood,
    test_skip_line_shape_only,
    test_event_argv_fallback,
    test_template_wiring,
    test_singleton_mutex,
    test_quit_snooze,
    test_i18n_tables,
    test_language_switch,
]


def main() -> int:
    from buddy import CONFIG_PATH
    saved_config = CONFIG_PATH.read_bytes() if CONFIG_PATH.is_file() else None
    failed = []
    b = FloatBuddy()
    try:
        for fn in TESTS:
            reset(b)
            try:
                fn(b)
                print(f"OK   {fn.__name__}")
            except Exception:
                failed.append(fn.__name__)
                print(f"FAIL {fn.__name__}")
                traceback.print_exc()
    finally:
        b.root.destroy()
        # belt and braces: the suite runs against _TEST_HOME, but if the
        # env redirect is ever bypassed, restore whatever config we saw
        try:
            if saved_config is not None:
                CONFIG_PATH.write_bytes(saved_config)
        except Exception:
            pass
        shutil.rmtree(_TEST_HOME, ignore_errors=True)
    if failed:
        print("FAILED:", ", ".join(failed))
        return 1
    print(f"ALL {len(TESTS)} TESTS PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
