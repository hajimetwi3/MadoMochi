English | [日本語](README.ja.md)

# MadoMochi

A tiny pixel buddy **for Claude Code** that lives at the edge of your
window — *mado* (窓) is Japanese for "window", and *mochi* is exactly the
squishy little thing you are picturing. It docks to the Claude Code
window and reacts to what your Claude sessions are actually doing — via Claude
Code hooks.
*(Unofficial community project — not affiliated with Anthropic.)*

> Claude Code's UI has no slot for a live character, so the buddy is a
> frameless, chroma-key-transparent, always-on-top window that tracks the
> Claude Code window and reads a status file written by hooks.

[▶ Watch the MadoMochi demo video](https://x.com/hajimetwi3/status/2078704325292179829)

## Requirements

- **Windows 11** (window tracking & transparency use Win32 APIs; Windows 10
  still works, but support ended on October 14, 2025 — use it
  only on an ESU-covered or otherwise updated system)
- **Python 3.10+** — the standard installer is enough (tkinter and pythonw
  included; **no pip packages needed**, standard library only). Enable
  "Add python.exe to PATH" during install — `install.ps1` looks for `python`
- **Claude Code 2.1.145+** (desktop app, or the CLI in a terminal window) — the thing
  the buddy docks to and reacts to; it hides while no Claude window exists
- macOS: not supported yet, but an **experimental port** lives in
  [experimental/macos/](experimental/macos/) — its automated apply/undo
  tests pass on GitHub-hosted macOS, while the interactive GUI, window
  tracking, and audio still need real-user testing. Read
  [experimental/macos/README.md](experimental/macos/README.md) before trying it
- ⚠️ **MadoMochi keeps its data in the ~/.claude/madomochi folder**
  (v0.9.2 moved it from the old `~/.claude/buddy`; old data does not
  carry over — settings reset, so re-pick your skin and preferences).
  Before installing a newer version, see [Updating](#updating).

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

### Multiple Claude sessions

Hook events are tracked separately by Claude Code `session_id`, then combined
into **one Claude companion**. The visible state follows this priority:
`WAITING` → `ERROR` → `WORKING` → `LISTEN`/`THINK` → `DONE` → `IDLE`/`SLEEP`.
This keeps a helper session's start/end from putting an active session to
sleep, and keeps an unresolved permission prompt visible while other sessions
continue. When any session completes, the companion briefly shows DONE with
its celebration (and a sound cue when enabled), then returns to the newest
aggregate state—usually WORKING if another session is still active. WAITING
and ERROR interrupt this brief DONE immediately. Simultaneous cues are
coalesced so they do not pile up.

If a modern Claude Code `Stop` payload says background tasks are still in
flight, MadoMochi keeps the preceding WORKING state and defers DONE until the
final `Stop` with no pending task. It checks only whether that task array is
empty; descriptions and command strings are neither logged nor stored. If the
field is absent, MadoMochi retains the normal `Stop` behavior.

This version has one provider boundary (`claude`) and one companion for it.
Subagent events are intentionally folded into their parent session: this first
version separates Claude Code sessions, not every subagent.
If Claude Code invokes a hook without `session_id`, MadoMochi places that event
in a shared anonymous fallback bucket because it cannot be attributed safely.

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
  standard library only (WAV cache in `~/.claude/madomochi/bgm_cache`; nothing
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
> Moving or renaming the folder afterwards breaks the wiring and can
> produce hook errors. Re-wire from the new location before continuing
> to use Claude Code there (`install.ps1` does this).
>
> After installing, three main places are in use (plus the separate safety
> backups described below):
> - **this folder** — the app itself (scripts/ and skins, run in place)
> - **hook wiring** — `~/.claude/settings.json` (global) or a project's
>   `.claude/settings.local.json` (project-scoped, machine-local)
> - **state & config** — `~/.claude/madomochi/` (status, config, caches, logs)

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
- Global wiring is stored in `~/.claude/settings.json`; project wiring is
  stored in the machine-local `.claude/settings.local.json`, which should
  remain outside version control.
  Installing to a project also removes older MadoMochi entries from that
  project's shared `.claude/settings.json` while preserving unrelated settings
- Before changing a settings file, the installer keeps a local, bounded
  backup under `~/.claude/madomochi_backups/` (up to five versions per target).
  These safety backups are separate from runtime data and may be deleted
  manually when you no longer need them. Each backup contains the complete
  pre-change settings file, so keep it private and do not publish it
- Hook wiring changes normally apply to **running sessions automatically**
  (Claude Code watches its settings files); open a new session if they
  don't seem to land (older versions)
- A new session **auto-launches the buddy** (SessionStart hook); sending a
  prompt revives a crashed one, while a deliberate quit is respected for
  30 minutes
- **Updating?** See [Updating](#updating) before installing the new version

### Uninstall

```powershell
powershell -ExecutionPolicy Bypass -File uninstall.ps1
```

Same interactive choices as the installer (global / this project / another
folder). It dismisses the buddy and removes **only the buddy's wiring**
from the relevant settings files — including historical project wiring in
`.claude/settings.json` and current wiring in `.claude/settings.local.json`.
Other settings and hooks are left intact, with an automatic backup. Scripted:
`uninstall.ps1 -Global` / `-Project <dir>`;
add `-PurgeData` to clear the saved settings, cache, and logs in
`~/.claude/madomochi`.
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
chunky 2-px body blocks with crisp 1-px details (whiskers, > < eyes).

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
(`lang` in config.json, `null` = auto). Common interface text lives in
[scripts/i18n.py](scripts/i18n.py); skin and track display names are defined
alongside their respective modules.

Settings dialog sliders: scale, idle-walk delay, premium interval, roam
threshold — plus a factory-reset button. The dialog also hosts a
**showcase demo** (60 / 120 / 180 s, with a stop button) that performs the
whole repertoire with music and sound effects on a fixed script — in
performance mode every mood switches the track, and a too-quiet volume is
temporarily floored at 35% — then restores your audio settings afterwards.
Roaming is left out by default so the buddy stays in the showcase area;
enable "Include roaming" when you want to see the full-screen walk. Values
persist in
`~/.claude/madomochi/config.json`
(`walk_after_sec` / `premium_min_sec` / `premium_max_sec` / `roam_after_sec` /
`scale` / `skin` / `bgm_enabled` / `bgm_volume` / `bgm_track` /
`bgm_follow_mood` / `led_enabled` / `led_mode` / `se_enabled` /
`park_when_hidden` / `lang`).

## Skins

Fifteen original characters ship with the buddy: **Neko** (the default
teal cat), Neko-sakura, Penguin, Usagi (bunny), Obake (ghost), Slime,
Big Slime (1.5x wider), Kaeru (frog), Shiba, Fukurou (owl), Tako
(octopus), Kinoko (mushroom), Onigiri and Agent One (a midnight terminal
spirit), plus Agent 2nd (a pearl-and-mint monitor sprite). House style: chunky flat
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

A skin that fails to import or lacks the required interface is skipped. Errors
raised while rendering a custom skin are contained by the render loop and
written to `buddy_err.log`, with repeats from the same failure site
rate-limited. Switch back to a bundled skin if a custom skin misbehaves.

> ⚠️ **Skins are Python code** executed with your privileges when the buddy
> starts. Only install skins you trust (or have read).

## Testing

```powershell
powershell -ExecutionPolicy Bypass -File scripts\stop_buddy.ps1
python -B tests\test_session_state.py # GUI-free multi-session tests
python -B tests\test_units.py       # main regression suite
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
  .claude/settings.local.json # project hook wiring (keep outside version control)
  install.ps1               # interactive installer
  uninstall.ps1             # interactive uninstaller (-PurgeData wipes data too)
  install.settings/
    settings.template.json  # canonical hook wiring (with placeholders)
  scripts/
    buddy.py                # the floating window itself (tkinter, transparent, topmost)
    retro_bgm.py            # 12 built-in chiptune tracks + LED patterns (stdlib synth)
    i18n.py                 # UI strings (EN/JA) and display-language detection
    skins/                  # 15 skins + the shared base _base.py (drop a .py to add)
    window_pos.py           # Claude-window detection & anchoring (pure ctypes)
    hook_entry.py           # hook entrypoint (stdin JSON -> per-session state; handled calls exit 0)
    session_state.py        # SQLite session store, aggregation, decay, sound signals
    set_status.py           # set the mood manually
    install_hooks.py        # wires the template into Claude Code settings
    start_buddy.ps1 / stop_buddy.ps1
  tests/
    test_units.py           # regression suite (run with the buddy stopped, using python -B)
    test_session_state.py   # GUI-free, cross-platform multi-session tests
    test_macos_apply.py     # isolated macOS apply/undo safety tests
    soccer_strip.py         # render sprite phases to PNG
    capture.ps1             # DPI-aware screen capture (-CropX/-CropY/-CropW/-CropH/-Zoom)
```

Runtime files live in `~/.claude/madomochi/`: `status.json` (current aggregate
mood), `sessions.sqlite3` (per-session state; SQLite may also create `-wal` and
`-shm` sidecars while active), `config.json` (position & settings), `hook.log`
(every hook event), `buddy_err.log` (render-loop errors, repeats from the same
failure site rate-limited and rotated at 1MB), and
`bgm_cache/` (synthesized WAV loops). The session database stores a SHA-256-
derived session key, state/event labels, and tool names; it does **not** store
raw session IDs, prompts, tool input/output, or transcript paths.
Hook input is processed only up to 4 MiB. An oversized payload is ignored
without being parsed or persisted; only a size-limit diagnostic is logged.
Diagnostic tracebacks can contain local file paths; review logs before sharing
an excerpt and do not publish complete log files.

Settings-file safety backups are stored separately in
`~/.claude/madomochi_backups/`, with at most five versions retained per target.
`-PurgeData` removes runtime data but intentionally leaves these recovery
copies. They contain complete pre-change settings files and may include other
local configuration, so do not share them; delete the backup directory
manually after you no longer need it.

## Troubleshooting

- **Not reacting to the session** →
  `Get-Content $HOME\.claude\madomochi\hook.log -Tail 20` growing means hooks
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

## Updating

1. Right-click the running MadoMochi, select **Quit**, and wait until it
   disappears.
2. From the new version's folder, run:

```powershell
cd "new MadoMochi folder"
powershell -ExecutionPolicy Bypass -File install.ps1
```

Choose the same hook scope you used before (repeat this for each scope if
you wired more than one). A separate uninstall of the old version is not
needed: the installer replaces existing MadoMochi hook wiring. For a
project-scoped installation, it also removes older MadoMochi entries from
the shared `.claude/settings.json` and installs the new wiring in the
machine-local `.claude/settings.local.json`.

When updating from v0.9.1 or earlier, the old runtime-data folder
`~/.claude/buddy` may remain. MadoMochi v0.9.2 and later do not use it.
After confirming that the new version works, you may delete it manually;
it is normally small and leaving it in place does not affect MadoMochi.
Old settings are not migrated, so re-select your skin and other preferences.

After confirming that the update works, you may delete the old version's
MadoMochi application folder.

## Notes

- **Unofficial**: this is a community project — not affiliated with,
  endorsed by, or sponsored by Anthropic. "Claude" and "Claude Code" are
  trademarks of Anthropic, PBC, used here only to describe compatibility.
- Everything is local: runtime state never leaves your machine
- When the MadoMochi entrypoint starts normally, it returns no permission
  decision. Re-wire or uninstall it before moving or deleting its installed
  folder so a stale missing-script hook cannot affect a permission prompt
- **Mascot IP note**: this repository ships only original characters. The
  engine is mascot-agnostic — if you skin it as someone else's mascot for
  fun, keep that skin local and don't redistribute it.
- Not a productivity tool — a **cute companion** 🐱
- License: [MIT](LICENSE)

## Disclaimer

This app is provided AS IS, with no warranty of correctness or availability.
Use at your own risk. Backing up your files is your responsibility.

---  

## Announcements  

- Announced on X as well (in Japanese).  
  [https://x.com/hajimetwi3/status/2078773256275083572](https://x.com/hajimetwi3/status/2078773256275083572)
  
## Author

[Hajime Tsui](https://hajimetwi3.github.io/hajimetwi3/)  
