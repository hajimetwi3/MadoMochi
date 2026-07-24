# MadoMochi on macOS — experimental port

> ⚠️ **Status: automated apply/undo tests pass on GitHub-hosted macOS 15
> (arm64).** The interactive GUI, Claude window tracking, audio output,
> and multi-display behavior still need real-user testing. Treat this as
> an experiment, not a finished product. The topmost recovery after a
> hide/restore has been confirmed on real hardware. Tk 9 intentionally uses an
> opaque dark card to avoid retained transparent pixels; a genuinely
> transparent Tk 9 backend remains separate experimental work.
> ⚠️ **Runtime data lives in ~/.claude/madomochi (moved from
> ~/.claude/buddy in v0.9.2; old data does not carry over).**
> If upgrading from v0.9.1 or earlier, see
> [Updating](#updating-from-v091-to-v092-or-later) first.
>
> 日本語メモ：apply/undoの自動テストはmacOS上で合格していますが、GUI・
> ウィンドウ追従・音声等は実利用環境で確認が必要です。Tk 9では残像防止を
> 優先し、透明表示ではなく暗い不透明カードを使用します。
> 遊び方は下の *Just want to play?*、全部元に戻す手順は
> *Undo everything* にあります。結果はissueへどうぞ（部分報告歓迎）。

Requires Python 3.10+ and Claude Code 2.1.145+.

## Just want to play? (five minutes)

```bash
cd "your MadoMochi folder"                          # everything below runs from the repo root
python3 experimental/macos/apply.py                 # turn this checkout into the Mac build
python3 -m pip install pyobjc-framework-Quartz      # optional: window following + Tk 8 native redraw repair
python3 scripts/install_hooks.py                    # let Claude Code drive the buddy
./scripts/start_buddy.sh
```

A little pixel cat should appear near your Claude Code window — or, if
you skipped pyobjc, in the **bottom-right corner of the desktop**:
without Quartz the cat cannot follow windows, so it parks there
automatically (no configuration needed).

The PyObjC line is optional for basic corner-parking mode. It is strongly
recommended for this experiment: besides window following, it enables the
native full-window redraw used by the Tk 8 transparent path. Tk 9 uses the
opaque safe card regardless, because that path reliably repaints cleared
pixels.

Now chat with Claude Code and watch the badge over its head:
LISTEN → THINK → WORKING → DONE with confetti. Then right-click the
cat: 15 skins, walk/gym/soccer demos, retro chiptune BGM, sound
effects, a settings dialog with a full showcase demo. Poke it, too.

Multiple Claude sessions are tracked separately and combined into this one
companion. A completion from any session briefly shows DONE with its
celebration (and a sound cue when enabled), then returns to the latest
aggregate state. WAITING and ERROR interrupt that brief DONE immediately.
When `Stop` reports that background tasks remain, DONE is deferred until the
final `Stop`; task descriptions and command strings are not stored or logged.

If something looks broken, that's a finding, not a failure. **Undo
everything** below reverses the whole experiment with one command, and
the checklist further down shows which observations help most.

### Updating the experimental macOS build

Use a newly downloaded or freshly extracted folder for each experimental
version; do not copy a new release over a checkout that has already been
patched. Stop the old buddy first and, when possible, run `--undo` from the
old folder before installing from the new one. The installer replaces the
old MadoMochi hook wiring, so a separate old-folder uninstall is not needed.
Do not delete or move a checkout while its hook wiring still points there:
a missing entrypoint can produce a hook error and may affect a permission
prompt.

If `apply.py` refuses because an existing backup cannot be matched safely to
the current sources, it leaves the managed files unchanged. Keep that folder
for inspection and continue from a fresh download instead of deleting or
editing `scripts_backup_macos/` to force the operation.

### Updating from v0.9.1 to v0.9.2 or later

Before deleting or replacing the v0.9.1 checkout:

```bash
cd "your v0.9.1 MadoMochi folder"
./scripts/stop_buddy.sh
python3 experimental/macos/apply.py --undo
```

Then use a newly downloaded v0.9.2-or-later folder and follow the quick-start
steps above. Old settings are not migrated; re-select
your skin and other preferences after updating. The old runtime-data
folder `~/.claude/buddy` may remain; v0.9.2 and later do not use it.
After confirming that the new version works, you may delete it manually,
or leave it in place — it is normally small and does not affect MadoMochi.
You may also delete the old MadoMochi checkout after confirming the update.

## Undo everything

```bash
cd "your MadoMochi folder"
python3 experimental/macos/apply.py --undo --purge-data
```

That is the everything-off switch — the one to use when you are done
playing. (`--undo` on its own stops the buddy, removes the hooks and
restores the sources but keeps the buddy's saved position, settings
and audio cache in `~/.claude/madomochi`; add `--purge-data`, as above,
unless you plan to try again later.)

One command reverses the whole experiment: it dismisses the buddy,
removes **only this checkout's entries** from `~/.claude/settings.json`
(matched by this repo's exact path, so another copy of MadoMochi keeps
its wiring; a timestamped backup is written first and the changed JSON
is replaced atomically — the Windows
`uninstall.ps1` doesn't run on macOS, so this is the Mac equivalent),
restores the original sources from the automatic backup (the
`scripts_backup_macos/` folder the apply created at the top of your
MadoMochi folder), deletes the files the apply copied in, and checks
every restored file against a manifest of checksums recorded at apply
time. Only after everything
verifies does it clean up its own backup folder and `__pycache__`
litter. Every path is built inside Python: **there are no shell
commands to mistype.** Re-running `--undo` is safe; when something
cannot be verified it says exactly what, keeps the backup folder, and
exits nonzero instead of claiming success.

- Edited the patched files yourself before undoing? Your edited
  version is saved as `*.prev` inside the backup folder before the
  original comes back — nothing you wrote is silently discarded. This
  holds even when the backup was made by an older experimental version
  without a manifest: everything current is preserved first, the
  restore is explicitly reported as unverified, and the exit code stays
  nonzero.
- On Windows/Linux (a test copy of the repo, say), `--undo` restores
  the repository files only; the stop/unhook/purge steps are for the
  machine's real installation, so off macOS they need an explicit
  `--force`. Without that flag, undoing a test copy does not touch the
  buddy you actually use.
- `--purge-data` additionally deletes `~/.claude/madomochi` (the buddy's
  saved position, settings and audio cache). Nothing else on your
  machine is included in that purge target. Before v0.9.2 the folder was
  `~/.claude/buddy`; it is not migrated or removed automatically.
- Wired a single project instead of globally? Also run
  `python3 scripts/install_hooks.py --uninstall --project <dir>`.
- The installer keeps up to five private settings backups per target under
  `~/.claude/madomochi_backups/`. The experimental `--undo` path also keeps
  its own timestamped safety copy next to the global `settings.json`.
- pyobjc, if you installed it, is yours to keep or remove:
  `python3 -m pip uninstall pyobjc-framework-Quartz`.
- A MadoMochi entrypoint that starts normally returns no permission decision.
  Remove or replace stale hook wiring before deleting its checkout; a missing
  entrypoint can produce a hook error and may affect a permission prompt.

## How the apply works

The script is two-phase: it verifies every patch anchor before writing,
so an anchor mismatch stops before any patch is changed. Once the pristine
source backup has been created successfully, the managed write phase is
transactional — if anything then fails, even the final syntax check, the
patched sources, copied files and backup side-files are restored — contents,
timestamps and file modes — and newly created files are removed. The syntax
check compiles into a
scratch directory so no `.pyc` is left behind, and a rollback that
itself hits an error says so instead of claiming success. It is
idempotent, backs the originals up to `scripts_backup_macos/`
(gitignored), records a checksum manifest there (the reference
`--undo` later verifies against), and prints next steps. It refuses to
start when a managed source file is missing, when an existing manifest or
clean-tree backup does not match the sources, or when an already-patched
tree has lost its manifest — in these cases nothing is written and a fresh
download is the recovery path. Re-runs with a valid manifest
re-copy the macOS support files; anything you edited since the last apply —
copied support files or patched sources — is preserved as `*.prev` in the
backup folder before the baseline moves on.

`--check` verifies without writing — it runs on any OS. `--undo`
reverses the apply completely (see **Undo everything** above).

## What apply.py changes

| Patch | What it does |
|-------|--------------|
| A | picks the afplay audio backend (`mac_audio.py`) on darwin |
| B | aqua-guarded window transparency (`systemTransparent`), with an explicit degraded mode when the Tk build can't do it |
| C | sprite painting leaves empty pixels unset, so the window shape is the sprite itself |
| D | right-click works the mac way (`Button-2`, plus Control-click) |
| E | single instance via `fcntl.flock`, held for the process lifetime (required — hooks auto-revive the buddy on prompts) |
| F | `stop_buddy.sh`'s SIGTERM routes through the normal close path, so audio stops and the quit marker is stamped |
| G | the hook launcher detaches with `start_new_session` on POSIX |
| H | without Quartz, corner parking becomes the default (an explicit config value still wins) |
| I | imports the AppKit bridge when PyObjC is present; absence remains a supported degraded path |
| J | adds Aqua recovery helpers: a real topmost OFF→ON transition and full native-view invalidation |
| K | reasserts topmost immediately and again after an Aqua window remap settles |
| L | makes Reset position repair the topmost window level too |
| M | makes the menu's Always on top: ON action force a real state transition instead of a cached no-op |
| N | requests a full transparent-window redraw after each changed sprite frame on the transparent path |
| O | withdraws and remaps the first Aqua window through the same recovery path used after a hide/restore, so undecorated chrome and topmost state are established from startup |
| P | detects Tk 9 and selects an opaque dark-card safe mode so every cleared sprite pixel is deterministically repainted |

Plus file drops: the Quartz `window_pos.py` (tracks the window number,
refreshes its bounds every ~250ms call, full sweep every 2s), the
`mac_audio.py` player (locked process lifecycle: terminate → bounded
wait → kill), and `start/stop_buddy.sh`.

## Known limitations

- **BGM restarts with a small gap** — the system player used here
  (`afplay`) can't loop seamlessly, so each track has a brief pause
  when it repeats. Sound effects are unaffected. There is no setting
  for this: fixing it means writing a CoreAudio-based player, which is
  a welcome future code contribution.
- **CLI-only Claude Code isn't followed** — the buddy finds the Claude
  *app's* window. Claude Code running inside Terminal/iTerm has no such
  window, so use corner parking (`park_when_hidden`) there.
- **Screen Recording permission is not normally expected** — macOS asks for it
  when software reads window *titles*. MadoMochi
  reads only application names, never titles, so that prompt should not
  appear. If macOS asks for it anyway, please report it.
- **Tk 9 uses an opaque safe card on purpose** — Tk 9.0.3 was observed to
  retain old colors in transparent PhotoImage areas. The safe mode removes
  that unreliable transparency path so complete repainting does not depend
  on the Aqua backing store. True transparent Tk 9 rendering will be tested
  separately before it can replace this conservative default.
- **The new startup remap still needs real-device confirmation** — recovery
  after hiding/restoring the Claude window has been confirmed to remove the
  native titlebar and restore the window level. Startup now follows that path,
  and a no-GUI regression test covers the sequence, but only a real Aqua/Tk
  window can confirm the first visible frame. The Tk 8 transparent redraw
  path likewise still needs real-window confirmation.

## Verification checklist 🍡

If you have a real Mac, work through this checklist after following the
quick-start steps above.

1. **Do the tests pass?** Order matters here. On the fresh checkout,
   first run `python3 -B tests/test_macos_apply.py` — the apply/undo
   suite needs the stock tree, and it says so and stops if the tree is
   already patched. Next run `python3 -B tests/test_session_state.py`
   (the GUI-free multi-session suite), then
   `python3 experimental/macos/apply.py`, and finally
   `python3 -B tests/test_units.py` (`-B` keeps Python from scattering
   `__pycache__` folders in the repo). All tests run
   entirely inside a throwaway temp folder and clean up after
   themselves — your Claude Code settings and the buddy's own config
   are untouched. Everything should pass as-is.
2. **Does the buddy actually find the Claude window?** The buddy locates
   Claude by the window's owning-application name. If the cat never follows
   the window, use the diagnostic command below to see the name reported by
   macOS. In Terminal, run the buddy once
   with diagnostics on (the variable applies to just that one command):

   ```bash
   MADOMOCHI_MAC_DEBUG=1 python3 scripts/buddy.py
   ```

   Watch the terminal output: a `[madomochi]` line should name the
   Claude window. If the owner name differs, adjust
   `_find_claude_rect` in `scripts/window_pos.py` and mention the
   actual name in your report — the app name is enough.
   (`MADOMOCHI_MAC_DEBUG=all` prints every open window instead — local
   use only. Running via `start_buddy.sh` hides this output, hence the
   direct command.)
3. **Does the window look right and recover correctly?** No native macOS
   titlebar or traffic-light buttons should appear, including on the first
   visible frame. With Tk 9, an opaque dark rectangular card is expected in
   this safe build; with Tk 8, the sprite should stand free on a transparent
   background. It should stay on top, and drag/settings/focus should all work
   at once. Switch between skins and trigger DONE/confetti several times;
   pixels from the old skin or effect should not remain. Hide and restore the
   Claude window and confirm the buddy is still above it and undecorated. If
   it ever falls behind, choose **Always on top:
   OFF**, then **Always on top: ON**, and report whether that restores it
   without restarting. Also include the single version number printed by:

   ```bash
   python3 -c "import tkinter as tk; r=tk.Tk(); print(r.tk.call('info', 'patchlevel')); r.destroy()"
   ```

   This command only reads the Tk window-system version; it changes no files
   or settings.
4. **Does the menu open?** Right-click and Control-click should both
   bring it up.
5. **Still exactly one buddy?** Chat for a few minutes, then
   `pgrep -fl scripts/buddy.py` should list exactly one process.
   (Don't judge by the lock file — it stays on disk after exit by
   design, so its presence proves nothing.)
6. **Two sessions, if practical:** keep one session working and make the
   other request permission. WAITING should win; resolving it should reveal
   the still-active session rather than putting the buddy to sleep.
7. **Does sound behave?** Effects fire, BGM plays, and after
   `./scripts/stop_buddy.sh` no `afplay` process remains
   (`pgrep afplay` prints nothing).
8. **Multi-display, if you have one:** does following still work on a
   display left of or above the main one (those have negative global
   coordinates)? Single-display setups can skip this.

**Reporting note:** conclusions belong in the issue, logs don't. Debug
dumps are local investigation tools, and full `hook.log` /
`buddy_err.log` contents can carry your username inside file paths —
keep them off public posts entirely.

## Implementation safety requirements

These are not test items. Any code change must preserve these requirements:

1. **A running hook entrypoint makes no permission decision** (it exits 0
   and prints nothing). Install/update instructions must not leave settings
   pointing at an entrypoint that has been moved or deleted.
2. **No subprocess calls inside the render loop**: window tracking uses
   in-process APIs so an external command cannot stall animation.
3. **Never kill processes by generic name — only by this repo's full
   path**: this prevents an unrelated process with a similar script name
   from being selected.

Good luck. The cat is counting on you. 🐱
