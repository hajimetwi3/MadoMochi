English | [日本語](README.ja.md)

# MadoMochi

A tiny pixel buddy **for Claude Code** that lives at the edge of your
window — *mado* (窓) is Japanese for "window", and *mochi* is exactly the
squishy little thing you are picturing. It docks to the Claude Code
window and reacts to what your session is actually doing — via Claude
Code hooks.
*(Unofficial community project — not affiliated with Anthropic.)*

> **Why a separate window?**
> Claude Code's UI has no slot for a live character, so the buddy is a
> frameless, chroma-key-transparent, always-on-top window that tracks the
> Claude Code window and reads a status file written by hooks.

[▶ Watch the MadoMochi demo video](https://x.com/hajimetwi3/status/2078704325292179829)

## Requirements

- **Windows 11** (window tracking & transparency use Win32 APIs; Windows 10
  still works, but its mainstream support ended in October 2025 — use it
  only on an ESU-covered or otherwise updated system)
- **Python 3.10+** — the standard installer is enough (tkinter and pythonw
  included; **no pip packages needed**, standard library only). Enable
  "Add python.exe to PATH" during install — `install.ps1` looks for `python`
- **Claude Code** (desktop app, or the CLI in a terminal window) — the thing
  the buddy docks to and reacts to; it hides while no Claude window exists
- macOS: not supported yet, but an **untested experimental port** lives in
  [experimental/macos/](experimental/macos/) — read
  [experimental/macos/README.md](experimental/macos/README.md) before
  trying it; real-Mac reports welcome

## States

| Badge | When (hook) | Animation |
|-------|-------------|-----------|
| (hidden) `IDLE` | idle | breathing, blinking, occasional bubbles |
| `LISTEN` | prompt received (`UserPromptSubmit`) | perks up, looks around (**settles into THINK after 3s**) |
| `THINK` | after LISTEN until the first tool / context compaction (`PreCompact`) | wandering eyes, thought dots |
| `WORKING` | tools running (`Pre/PostToolUse`) | **types on a tiny terminal** |
| `DONE` | turn finished (`Stop`) / background task finished (`TaskCompleted`) | leap, land, **stomp with confetti** (10s) |
| `ERROR` | tool failed (`PostToolUseFailure`) / turn aborted (`StopFailure`) | > < eyes, staggering (6s) |
| `WAITING` | a permission prompt (`PermissionRequest`) or an attention notification (`Notification`: idle prompt, agent-needs-input...) | urgent hops and waving. **Neglect it for a few minutes and the buddy roams your whole screen** until you deal with it, then hurries home |
| `SLEEP` | session ended (`SessionEnd`) | sits down, zzz |

Animation grammar: feelings are shown through **motion only** — leans,
hops, crouches, eye movement — with confetti as the single environmental
effect.

Stuck-state safety net: if no hook event arrives for 5 minutes (30 minutes
after long-running tools like Bash/Agent), WORKING falls back to idle.

## Idle extras

| Move | When | What happens |
|------|------|--------------|
| **Walk** | after 3 min of idle | strolls left, looks around, walks back. Rushes home if work arrives |
| **Gym** | every 90–240s of idle (random pick) | barbell curls, > < effort face, sweat |
| **Soccer** | same pool as Gym | keep-ups, eyes tracking the ball, proud trap finish |
| **Poke** | click (don't drag) | squished > <, startled hop |

Time-of-day: dozes off late at night (23:00–5:00), one morning workout
(6:00–9:00), Friday DONE parties run twice as long.

The right-click menu has one-click demos for walk / gym / soccer / roam —
the roam demo tours the screen for about eight seconds and walks itself
home.

Animations use variable frame holds (fast base frames plus longer holds;
jumps slow at the apex).

## Retro BGM & LED bar

Right-click → **🎵 Retro BGM** turns on a loop of 12 built-in chiptune
tracks, and an **LED bar** under the sprite lights up with the mood and
the music.

- **No audio files** — every track is synthesized on the fly with the
  standard library only (WAV cache in `~/.claude/buddy/bgm_cache`; nothing
  leaves your machine)
- **Gapless looping** via winmm waveOut hardware loops (falls back to
  winsound where unavailable)
- **Mood-driven track picks** (default on) — WORKING plays *Coffee Rush*,
  DONE plays *Victory March*, and so on. A hand-picked track survives calm
  moods but yields to events; turn the option off to pin a track completely
- **Volume** — pick one of five steps (10–70%) straight from the menu
- **Auto-mute** — the music pauses while the buddy is hidden (Claude
  minimized or closed) and picks the tune back up when it reappears
- **Sound effects** (default off) — a fanfare on DONE, a stumble on ERROR,
  a squeak on poke and a chime on WAITING. Toggle in the BGM menu;
  independent of the music, volume follows the BGM volume
- **LED patterns** — default **auto** (follows the mood); 12 manual
  patterns available, and picking a track switches to its matching pattern.
  The LED bar itself can be turned off
- Track list: Victory March / Modem Memories / Chill Elevator / Coffee Rush /
  Starlight / Pixel Plaza / Bug Chase / Deep Think / Terminal Tap /
  Morning Build / Pixel Waltz / Carousel Spin

## Install

> ⚠️ **Pick a stable folder first.** The installer copies no files — it
> writes the **absolute path** of this folder into your hook settings.
> Moving or renaming the folder afterwards silently breaks the wiring
> (run `install.ps1` again from the new location to re-wire).
>
> After installing, three places are in use:
> - **this folder** — the app itself (scripts/ and skins, run in place)
> - **hook wiring** — `~/.claude/settings.json` (or a project's `.claude/settings.json`)
> - **state & config** — `~/.claude/buddy/` (status, config, caches, logs)

```powershell
cd "MadoMochi folder"
powershell -ExecutionPolicy Bypass -File install.ps1
```

The interactive installer asks where to wire the hooks (globally / this
project / another folder) and can launch the buddy right away.
Scripted use: `install.ps1 -Global` or `install.ps1 -Project <dir>` (add
`-Start` to launch). Prompts follow your Windows display language; force
one with `-Lang en` / `-Lang ja`.

- The canonical hook wiring lives in
  [install.settings/settings.template.json](install.settings/settings.template.json)
  (`{{PYTHON}}` / `{{HOOK_ENTRY}}` placeholders resolved per machine)
- The generated `.claude/settings.json` is machine-specific and untracked
- Hook wiring changes normally apply to **running sessions automatically**
  (Claude Code watches its settings files); open a new session if they
  don't seem to land (older versions)
- A new session **auto-launches the buddy** (SessionStart hook); sending a
  prompt revives a crashed one, while a deliberate quit is respected for
  30 minutes
- **Updating from an earlier version?** After replacing the files,
  **re-run `install.ps1`** with the same scope as before (only the
  installer updates the hook wiring)

### Uninstall

```powershell
powershell -ExecutionPolicy Bypass -File uninstall.ps1
```

Same interactive choices as the installer (global / this project / another
folder). It dismisses the buddy and removes **only the buddy's wiring**
from settings.json — other settings and other hooks are untouched, with an
automatic backup. Scripted: `uninstall.ps1 -Global` / `-Project <dir>`;
add `-PurgeData` to also delete `~/.claude/buddy` (settings, cache, logs).
Removal normally applies to running sessions right away too; restart a
session if hooks seem to linger.

## Manual start & stop (usually not needed)

```powershell
powershell -ExecutionPolicy Bypass -File scripts\start_buddy.ps1   # summon
powershell -ExecutionPolicy Bypass -File scripts\stop_buddy.ps1    # dismiss
```

The buddy follows the Claude Code window and hides when it is closed or
minimized — or turn on **corner parking** (right-click) to have it squat
in the bottom-right corner of the desktop instead (`park_when_hidden`).
Size etc. live in the settings dialog (right-click → Settings…), or via
CLI: `python scripts\buddy.py --scale 3` (default 2.4; fractions are fine
— rational-number scaling). Internally the sprite is a 64×64 fine grid:
chunky 2-px body blocks, with 1-px details (whiskers, > < eyes)
anti-aliased on top.

## Controls

| Input | Action |
|-------|--------|
| Click | poke |
| Drag | move (offset is remembered and follows the window) |
| Right-click | mood demos / walk・gym・soccer・roam demos / **skins** / **retro BGM, SE & LED** / reset position / follow & **corner-parking** / badge / **settings** / **language (English・日本語)** / quit |
| Double-click | cycle moods |
| Esc | quit |

**Language**: the UI ships in English and Japanese. It defaults to your
Windows display language; right-click → **English / 日本語** pins a choice
(`lang` in config.json, `null` = auto). All UI strings live in
[scripts/i18n.py](scripts/i18n.py) — adding a language is one more dict.

Settings dialog sliders: scale, idle-walk delay, premium interval, roam
threshold — plus a factory-reset button. The dialog also hosts a
**showcase demo** (60 / 120 / 180 s, with a stop button) that performs the
whole repertoire with music and sound effects on a fixed script — in
performance mode every mood switches the track, and a too-quiet volume is
temporarily floored at 35% — then restores your audio settings afterwards.
Made for recording README GIFs: roaming is left out by default so the
buddy never leaves the frame, with an "Include roaming" checkbox for
stage/event runs. Values persist in
`~/.claude/buddy/config.json`
(`walk_after_sec` / `premium_min_sec` / `premium_max_sec` / `roam_after_sec` /
`scale` / `skin` / `bgm_enabled` / `bgm_volume` / `bgm_track` /
`bgm_follow_mood` / `led_enabled` / `led_mode` / `se_enabled` /
`park_when_hidden` / `lang`).

## Skins

Thirteen original characters ship with the buddy: **Neko** (the default
teal cat), Neko-sakura, Penguin, Usagi (bunny), Obake (ghost), Slime,
Big Slime (1.5x wider), Kaeru (frog), Shiba, Fukurou (owl), Tako
(octopus), Kinoko (mushroom) and Onigiri. House style: chunky flat
bodies, solid dark eyes, one fine-grid detail per character (whiskers,
suckers, nori...).

Drop a `.py` file into `scripts/skins/` and it appears in the right-click
menu with its idle face as a tiny icon (selection persists; switching
costs nothing — the frame cache just rebuilds lazily).

A skin module exports: `NAME`, `PALETTE`, `GRID`, `build_frame(mood, t)`,
`frame_hold(mood, t)`, `POKE_SEQ`, `GYM_SEQ` (and optionally `SOCCER_SEQ`,
plus `NAME_EN` for the English menu).
Four patterns to copy from:

- **palette swap** — [skins/neko_sakura.py](scripts/skins/neko_sakura.py) (a dozen lines)
- **on the shared base** — [skins/penguin.py](scripts/skins/penguin.py):
  [skins/_base.py](scripts/skins/_base.py) owns the choreography, effects and
  timing, so a new character is just a palette plus a draw function
- **fully standalone** — [skins/neko.py](scripts/skins/neko.py)
- **filter / post-processing** — [skins/slime_big.py](scripts/skins/slime_big.py):
  loads Slime and stretches just the body 1.5x wider — eyes and mouth keep
  their size and only spread apart, props stay true to size

A broken skin file is silently skipped; it can never take the buddy down.

> ⚠️ **Skins are Python code** executed with your privileges when the buddy
> starts. Only install skins you trust (or have read).

## Testing

```powershell
powershell -ExecutionPolicy Bypass -File scripts\stop_buddy.ps1
python tests\test_units.py          # regression suite (all features)
python tests\soccer_strip.py out.png [mood] [skin]   # render sprite phases
powershell -ExecutionPolicy Bypass -File scripts\start_buddy.ps1
```

## Manually set a mood (demo / debugging)

```powershell
python scripts\set_status.py --mood happy
python scripts\set_status.py --mood work --tool Bash
```

## Files

```
MadoMochi/                  # repo root
  README.md / README.ja.md  # this document (English / Japanese)
  LICENSE                   # MIT license text
  .gitignore                # ignores caches, PNG renders, generated files
  .claude/settings.json     # hook wiring generated on install (untracked)
  install.ps1               # interactive installer
  uninstall.ps1             # interactive uninstaller (-PurgeData wipes data too)
  install.settings/
    settings.template.json  # canonical hook wiring (with placeholders)
  scripts/
    buddy.py                # the floating window itself (tkinter, transparent, topmost)
    retro_bgm.py            # 12 built-in chiptune tracks + LED patterns (stdlib synth)
    i18n.py                 # UI strings (EN/JA) and display-language detection
    skins/                  # 13 skins + the shared base _base.py (drop a .py to add)
    window_pos.py           # Claude-window detection & anchoring (pure ctypes)
    hook_entry.py           # hook entrypoint (stdin JSON -> status.json, always exit 0)
    set_status.py           # set the mood manually
    install_hooks.py        # wires the template into settings.json
    start_buddy.ps1 / stop_buddy.ps1
  tests/
    test_units.py           # regression suite (run with the buddy stopped)
    soccer_strip.py         # render sprite phases to PNG
    capture.ps1             # DPI-aware screen capture (-CropX/-CropY/-CropW/-CropH/-Zoom)
```

Runtime files live in `~/.claude/buddy/`: `status.json` (current mood),
`config.json` (position & settings), `hook.log` (every hook event),
`buddy_err.log` (render-loop errors, rotated at 1MB), `bgm_cache/`
(synthesized WAV loops).

## Troubleshooting

- **Not reacting to the session** →
  `Get-Content $HOME\.claude\buddy\hook.log -Tail 20` growing means hooks
  fire; if the buddy still doesn't change, restart it. If nothing grows,
  re-run the installer or open a new session.
- **Denied a permission prompt, but WAITING stays** → when a denial ends
  the turn right there, no further hook events arrive, so the badge stays
  put (a known limitation). Your next prompt clears it instantly; to clear
  it on the spot, pick any state (IDLE, say) from the top of the
  right-click menu. Left alone, it auto-releases after 15 minutes. An
  approved long-running command can likewise show WAITING until it
  finishes and reports back.
- **Buddy not visible** → it hides while the Claude window is minimized.
  Right-click → follow OFF pins it on screen permanently, or turn on
  corner parking to have it wait on the desktop instead.
- **Closed the buddy?** → it auto-revives on your next prompt (crash
  self-healing). A deliberate quit (Esc / menu / stop_buddy.ps1) is
  respected for 30 minutes — a new session or start_buddy.ps1 brings it
  back immediately.
- **Edited the sprites** → stop & start the buddy to reload.

## Notes

- **Unofficial**: this is a community project — not affiliated with,
  endorsed by, or sponsored by Anthropic. "Claude" and "Claude Code" are
  trademarks of Anthropic, PBC, used here only to describe compatibility.
- Everything is local: the status files never leave your machine
- Hooks are fail-open by design — a buddy failure can never block Claude Code
- **Mascot IP note**: this repository ships only original characters. The
  engine is mascot-agnostic — if you skin it as someone else's mascot for
  fun, keep that skin local and don't redistribute it.
- Not a productivity tool — a **cute companion** 🐱
- License: [MIT](LICENSE)

## Disclaimer

This app is provided AS IS, with no warranty of correctness or availability.
Use at your own risk. Backing up your files is your responsibility.

## Author

[Hajime Tsui](https://hajimetwi3.github.io/hajimetwi3/)  
X (Twitter): https://x.com/hajimetwi3  
