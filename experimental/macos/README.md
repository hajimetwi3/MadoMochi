# MadoMochi on macOS — untested experimental port

> ⚠️ **Status: UNTESTED on real macOS.** Written and review-hardened on
> Windows; every patch is machine-verified to apply cleanly and the
> patched code still passes the full test suite on Windows (the macOS
> branches stay dormant there) — but no line of it has run on an actual
> Mac yet. Treat it as a well-prepared experiment, not a product.  
> ⚠️ **The folder is assumed to be MadoMochi's own — don't run the
> experiment if some other tool already created ~/.claude/buddy.**
>
> 日本語メモ：これはWindows上で作られた、**実機未検証**の移植です。
> 遊び方は下の *Just want to play?*、全部元に戻す手順は
> *Undo everything* にあります。結果はissueへどうぞ（部分報告歓迎）。

## Just want to play? (five minutes)

```bash
cd "your MadoMochi folder"                          # everything below runs from the repo root
python3 experimental/macos/apply.py                 # turn this checkout into the Mac build
python3 -m pip install pyobjc-framework-Quartz      # optional: lets the cat follow the window
python3 scripts/install_hooks.py                    # let Claude Code drive the buddy
./scripts/start_buddy.sh
```

A little pixel cat should appear near your Claude Code window — or, if
you skipped pyobjc, in the **bottom-right corner of the desktop**:
without Quartz the cat cannot follow windows, so it parks there
automatically (no configuration needed).

Now chat with Claude Code and watch the badge over its head:
LISTEN → THINK → WORKING → DONE with confetti. Then right-click the
cat: 13 skins, walk/gym/soccer demos, retro chiptune BGM, sound
effects, a settings dialog with a full showcase demo. Poke it, too.

If something looks broken, that's a finding, not a failure — this
build has never met a real Mac before you. **Undo everything** below
reverses the whole experiment with one command, and the checklist
further down shows which observations help most.

Updating from an earlier version of this scaffold? After the apply,
re-run `python3 scripts/install_hooks.py` — newer hook wiring (the
permission-prompt event and per-event args) is only added by the
installer, not by restarting the buddy.

## Undo everything

```bash
cd "your MadoMochi folder"
python3 experimental/macos/apply.py --undo --purge-data
```

That is the everything-off switch — the one to use when you are done
playing. (`--undo` on its own stops the buddy, removes the hooks and
restores the sources but keeps the buddy's saved position, settings
and audio cache in `~/.claude/buddy`; add `--purge-data`, as above,
unless you plan to try again later.)

One command reverses the whole experiment: it dismisses the buddy,
removes **only this checkout's entries** from `~/.claude/settings.json`
(matched by this repo's exact path, so another copy of MadoMochi keeps
its wiring; a timestamped backup is written first — the Windows
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
  holds even when the backup was made by an older scaffold version
  without a manifest: everything current is preserved first, the
  restore is explicitly reported as unverified, and the exit code stays
  nonzero.
- On Windows/Linux (a test copy of the repo, say), `--undo` restores
  the repository files only; the stop/unhook/purge steps are for the
  machine's real installation, so off macOS they need an explicit
  `--force`. Undoing a test copy can never touch the buddy you
  actually use.
- `--purge-data` additionally deletes `~/.claude/buddy` (the buddy's
  saved position, settings and audio cache). Nothing else on your
  machine is ever touched.
- Wired a single project instead of globally? Also run
  `python3 scripts/install_hooks.py --uninstall --project <dir>`.
- The `settings.json` backups are deliberately kept as your safety
  net; they live next to `settings.json`.
- pyobjc, if you installed it, is yours to keep or remove:
  `python3 -m pip uninstall pyobjc-framework-Quartz`.
- A half-finished undo is harmless in the meantime: hooks are
  fail-open by design, so a leftover entry exits silently and can
  never block Claude Code.

## How the apply works

The script is two-phase: it verifies every patch anchor before writing
anything, so a mismatch can never leave the repo half-patched. It is
also transactional — if anything fails mid-write, even the final syntax
check, the managed files (patched sources, copied files and backup
side-files) are restored — contents, timestamps and file modes — and
newly created files are removed. The syntax check compiles into a
scratch directory so no `.pyc` is left behind, and a rollback that
itself hits an error says so instead of claiming success. It is
idempotent, backs the originals up to `scripts_backup_macos/`
(gitignored), records a checksum manifest there (the ground truth
`--undo` later verifies against), and prints next steps. It refuses to
start when a managed source file is missing, or when an existing
manifest is invalid — in both cases nothing is written. Re-runs
re-copy the scaffold files; anything you edited since the last apply —
scaffold copies or patched sources — is preserved as `*.prev` in the
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
- **No scary permission prompts expected** — macOS asks for the Screen
  Recording permission when software reads window *titles*. MadoMochi
  reads only application names, never titles, so that prompt should not
  appear. If macOS asks for it anyway, that's a finding — please
  report it.

## Verification checklist — for humans and coding agents 🍡

If you have a real Mac, the fastest route is to point a coding agent
(Claude Code, for example) at this repo and have it work through this
list; every item is equally doable by hand.

1. **Do the tests pass?** Order matters here. On the fresh checkout,
   first run `python3 -B tests/test_macos_apply.py` — the apply/undo
   suite needs the stock tree, and it says so and stops if the tree is
   already patched. Then `python3 experimental/macos/apply.py`, and
   finally `python3 -B tests/test_units.py` (`-B` keeps Python from
   scattering `__pycache__` folders in the repo). All tests run
   entirely inside a throwaway temp folder and clean up after
   themselves — your Claude Code settings and the buddy's own config
   are untouched. Everything should pass as-is.
2. **Does the buddy actually find the Claude window?** Background: the
   buddy locates Claude by the window's owning-app name, and "the name
   contains `claude`" is an unverified guess made without a Mac — this
   item exists to check that guess. If the cat never follows the
   window, this is the first suspect. In Terminal, run the buddy once
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
3. **Does the window look right?** The sprite should stand free (no
   colored rectangle behind it), stay on top, and drag/settings/focus
   should all work at once.
4. **Does the menu open?** Right-click and Control-click should both
   bring it up.
5. **Still exactly one buddy?** Chat for a few minutes, then
   `pgrep -fl scripts/buddy.py` should list exactly one process.
   (Don't judge by the lock file — it stays on disk after exit by
   design, so its presence proves nothing.)
6. **Does sound behave?** Effects fire, BGM plays, and after
   `./scripts/stop_buddy.sh` no `afplay` process remains
   (`pgrep afplay` prints nothing).
7. **Multi-display, if you have one:** does following still work on a
   display left of or above the main one (those have negative global
   coordinates)? Single-display setups can skip this.

**Reporting note:** conclusions belong in the issue, logs don't. Debug
dumps are local investigation tools, and full `hook.log` /
`buddy_err.log` contents can carry your username inside file paths —
keep them off public posts entirely.

## If you end up changing code — three house rules

These are not test items; they are the rules any fix must keep, each
learned the hard way:

1. **Hooks stay fail-open** (always exit 0, print nothing): a broken
   hook must degrade to "the mascot misses a beat", never to "Claude
   Code stops working".
2. **No subprocess calls inside the render loop**: one hung external
   call once froze the entire mascot silently — that is why window
   tracking uses in-process APIs only.
3. **Never kill processes by generic name — only by this repo's full
   path**: a loose `pkill` pattern once took down an unrelated
   program's process that happened to share a script name.

Good luck. The cat is counting on you. 🐱
