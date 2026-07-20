"""End-to-end tests for experimental/macos/apply.py (apply and --undo).

Everything runs inside ONE outer temporary directory: each test copies
scripts/ and experimental/ into a fresh sandbox, points HOME/USERPROFILE
at a fake home inside it, and loads apply.py from the sandbox by path.
Process stops are stubbed and the platform is pinned, so the suite is
deterministic on any OS and never touches the real user's settings,
buddy state or processes.

Run:
    python3 -B tests/test_macos_apply.py
"""

import contextlib
import hashlib
import importlib.util
import io
import json
import os
import shutil
import stat
import sys
import tempfile
import time
import traceback
import types
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
OUTER = Path(tempfile.mkdtemp(prefix="madomochi_apply_test_"))
_SAVED_ENV = {k: os.environ.get(k) for k in ("USERPROFILE", "HOME")}

SOURCES = ("buddy.py", "hook_entry.py", "window_pos.py")
COPIES = ("mac_audio.py", "start_buddy.sh", "stop_buddy.sh")
FOREIGN_HOOK = r"C:\other\repo\scripts\hook_entry.py"

RW = stat.S_IREAD | stat.S_IWRITE
RO = stat.S_IREAD


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


STOCK = {n: sha(REPO / "scripts" / n) for n in SOURCES}


class Sandbox:
    """A disposable repo copy plus a fake home, fully isolated."""

    counter = 0

    def __init__(self):
        Sandbox.counter += 1
        root = OUTER / f"case{Sandbox.counter:02d}"
        self.home = root / "home"
        self.work = root / "work"
        shutil.copytree(REPO / "scripts", self.work / "scripts")
        shutil.copytree(REPO / "experimental", self.work / "experimental")
        for pc in list(self.work.rglob("__pycache__")):
            shutil.rmtree(pc, ignore_errors=True)
        self.scripts = self.work / "scripts"
        self.backup = self.work / "scripts_backup_macos"
        self.manifest = self.backup / "manifest.json"
        (self.home / ".claude").mkdir(parents=True)
        self.settings = self.home / ".claude" / "settings.json"
        self.hook_path = str((self.scripts / "hook_entry.py").resolve())

        def entry(path):
            return {"type": "command", "command": "python",
                    "args": [path, "--hajimetwi3-buddy-hook"],
                    "async": True, "timeout": 10}

        self.settings.write_text(json.dumps({
            "someUserKey": "keep-me",
            "hooks": {
                "SessionStart": [{"hooks": [
                    entry(self.hook_path),
                    entry(FOREIGN_HOOK),
                    {"type": "command", "command": "echo",
                     "args": ["user-own-hook"]},
                ]}],
                "Stop": [{"hooks": [entry(self.hook_path)]}],
            },
        }, indent=2), encoding="utf-8")
        # the module resolves Path.home() at call time, so this is enough
        os.environ["USERPROFILE"] = str(self.home)
        os.environ["HOME"] = str(self.home)
        self.mod = None

    def load(self):
        spec = importlib.util.spec_from_file_location(
            f"apply_under_test_{Sandbox.counter}",
            self.work / "experimental" / "macos" / "apply.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        # never touch real processes, and pin the platform so the
        # external-step gating behaves identically on every dev machine
        mod._real_stop_buddy = mod._stop_buddy  # for tests of the real logic
        mod._stop_buddy = lambda: (True, "buddy: stopped (stubbed)")
        mod.sys = types.SimpleNamespace(platform="linux")
        self.mod = mod
        return mod

    def run(self, *argv):
        """Run main() in-process; returns (exit_code, captured_output)."""
        mod = self.mod or self.load()
        buf = io.StringIO()
        saved_argv = sys.argv
        sys.argv = ["apply.py", *argv]
        try:
            with contextlib.redirect_stdout(buf):
                code = mod.main()
        finally:
            sys.argv = saved_argv
        return code, buf.getvalue()

    def stock(self) -> bool:
        return all(sha(self.scripts / n) == STOCK[n] for n in SOURCES)

    def apply_ok(self):
        code, out = self.run("--force")
        assert code == 0, f"apply failed:\n{out}"
        assert "manifest: written" in out, out
        return out

    def edit_manifest(self, fn):
        data = json.loads(self.manifest.read_text(encoding="utf-8"))
        fn(data)
        self.manifest.write_text(json.dumps(data, indent=2), encoding="utf-8")


class _ShutilPatch:
    """Pass-through shutil with selected operations overridden."""

    def __init__(self, real, **overrides):
        self._real = real
        self._overrides = overrides

    def __getattr__(self, name):
        if name in self._overrides:
            return self._overrides[name]
        return getattr(self._real, name)


# ---------------------------------------------------------------- manifest

def test_manifest_schema_accepts_valid():
    sb = Sandbox()
    sb.apply_ok()
    originals, applied, created = sb.mod._read_manifest()
    assert set(originals) == set(SOURCES)
    assert set(applied) == set(SOURCES) | set(COPIES)
    assert sorted(created) == sorted(COPIES)
    assert all(originals[n] == STOCK[n] for n in SOURCES)


def test_apply_undo_roundtrip_with_externals():
    sb = Sandbox()
    sb.apply_ok()
    code, out = sb.run("--undo", "--force")
    assert code == 0, out
    assert sb.stock(), "sources must be byte-identical to stock"
    assert not any((sb.scripts / n).exists() for n in COPIES)
    assert not sb.backup.exists(), "backup folder should be cleaned up"
    assert "verified back to stock" in out
    s = json.loads(sb.settings.read_text(encoding="utf-8"))
    assert s.get("someUserKey") == "keep-me"
    assert "Stop" not in s.get("hooks", {}), "our-only event must be removed"
    left = s["hooks"]["SessionStart"][0]["hooks"]
    assert len(left) == 2, "foreign checkout + user hook must survive"
    assert any(FOREIGN_HOOK in h.get("args", []) for h in left)
    assert any(h.get("args") == ["user-own-hook"] for h in left)
    assert any(p.name.startswith("settings.json.bak-undo-")
               for p in (sb.home / ".claude").iterdir())


def _rejects(sb, why):
    patched = {n: sha(sb.scripts / n) for n in SOURCES}
    settings_before = sb.settings.read_bytes()
    code, out = sb.run("--undo", "--force")
    assert code == 1, f"{why}: expected exit 1\n{out}"
    assert "manifest rejected" in out, f"{why}:\n{out}"
    assert all(sha(sb.scripts / n) == patched[n] for n in SOURCES), \
        f"{why}: sources must be untouched"
    assert all((sb.scripts / n).is_file() for n in COPIES), \
        f"{why}: copies must be untouched"
    assert sb.settings.read_bytes() == settings_before, \
        f"{why}: no external ops may run on a rejected manifest"


def test_manifest_missing_originals_key_rejected():
    sb = Sandbox()
    sb.apply_ok()
    sb.edit_manifest(lambda d: d["originals"].pop("window_pos.py"))
    _rejects(sb, "missing originals key")


def test_manifest_missing_applied_key_rejected():
    sb = Sandbox()
    sb.apply_ok()
    sb.edit_manifest(lambda d: d["applied"].pop("mac_audio.py"))
    _rejects(sb, "missing applied key")


def test_manifest_created_foreign_path_rejected():
    sb = Sandbox()
    sb.apply_ok()
    decoy = sb.work / "decoy.txt"
    decoy.write_text("must survive\n", encoding="utf-8")
    sb.edit_manifest(lambda d: d["created"].append(str(decoy)))
    _rejects(sb, "foreign absolute path in created")
    assert decoy.is_file(), "a foreign path listed in the manifest must never be touched"


def test_manifest_bad_values_rejected():
    sb = Sandbox()
    sb.apply_ok()
    good = sb.manifest.read_bytes()

    def dot_segment(d):
        d["originals"]["../window_pos.py"] = d["originals"].pop("window_pos.py")

    def separator(d):
        d["created"][0] = "sub/mac_audio.py"

    def bad_digest(d):
        d["applied"]["buddy.py"] = "Z" * 64

    for fn in (dot_segment, separator, bad_digest):
        sb.manifest.write_bytes(good)
        sb.edit_manifest(fn)
        _rejects(sb, fn.__name__)


# ------------------------------------------------------------------- apply

def test_apply_refuses_missing_source():
    sb = Sandbox()
    (sb.scripts / "window_pos.py").unlink()
    code, out = sb.run("--force")
    assert code == 1, out
    assert "Refusing to apply" in out and "window_pos.py" in out
    assert not sb.backup.exists(), "nothing may be written"
    assert sha(sb.scripts / "buddy.py") == STOCK["buddy.py"]


def test_apply_refuses_invalid_manifest():
    sb = Sandbox()
    sb.apply_ok()
    patched = sha(sb.scripts / "buddy.py")
    sb.edit_manifest(lambda d: d.pop("originals"))
    code, out = sb.run("--force")
    assert code == 1, out
    assert "existing manifest is invalid" in out
    assert sha(sb.scripts / "buddy.py") == patched, "nothing may be written"


def _reapply_preserves(source_name):
    sb = Sandbox()
    sb.apply_ok()
    target = sb.scripts / source_name
    target.write_text(target.read_text(encoding="utf-8") + "\n# my tweak\n",
                      encoding="utf-8")
    edited = sha(target)
    code, out = sb.run("--force")
    assert code == 0, out
    assert "edited after the last apply" in out, out
    prev = sb.backup / (source_name + ".prev")
    assert prev.is_file() and sha(prev) == edited, \
        "the edit must be preserved before the baseline is refreshed"
    code, out = sb.run("--undo", "--force")
    assert code == 0, out
    assert sb.stock()
    assert prev.is_file() and sha(prev) == edited, \
        "the preserved edit must survive the undo"
    assert sb.backup.is_dir(), "folder holding .prev files must be kept"


def test_reapply_preserves_edited_buddy():
    _reapply_preserves("buddy.py")


def test_reapply_preserves_edited_hook_entry():
    _reapply_preserves("hook_entry.py")


def test_legacy_apply_refuses_missing_backup():
    sb = Sandbox()
    sb.apply_ok()
    sb.manifest.unlink()
    (sb.backup / "window_pos.py").unlink()
    patched = sha(sb.scripts / "buddy.py")
    code, out = sb.run("--force")
    assert code == 1, out
    assert "older scaffold" in out and "window_pos.py" in out
    assert sha(sb.scripts / "buddy.py") == patched, "nothing may be written"


# -------------------------------------------------------------------- undo

def test_legacy_undo_preserves_edits():
    sb = Sandbox()
    sb.apply_ok()
    sb.manifest.unlink()
    target = sb.scripts / "window_pos.py"
    target.write_text(target.read_text(encoding="utf-8") + "\n# precious\n",
                      encoding="utf-8")
    edited = sha(target)
    code, out = sb.run("--undo", "--force")
    assert code == 1, "legacy undo must not claim a verified success\n" + out
    assert "undo complete" not in out
    assert "best-effort restore done" in out, out
    assert sb.stock(), "best-effort restore should still reach stock here"
    assert not any((sb.scripts / n).exists() for n in COPIES)
    prevs = list(sb.backup.glob("*.prev"))
    assert any(sha(p) == edited for p in prevs), \
        "the pre-undo edit must be preserved as .prev"


def test_undo_refuses_incomplete_backup():
    sb = Sandbox()
    sb.apply_ok()
    patched = {n: sha(sb.scripts / n) for n in SOURCES}
    (sb.backup / "window_pos.py").unlink()
    code, out = sb.run("--undo", "--force")
    assert code == 1, out
    assert "refusing to undo" in out and "window_pos.py" in out
    assert all(sha(sb.scripts / n) == patched[n] for n in SOURCES), \
        "an incomplete backup must abort before anything is touched"
    assert all((sb.scripts / n).is_file() for n in COPIES)


def test_undo_preserves_postapply_edits_and_reruns():
    sb = Sandbox()
    sb.apply_ok()
    target = sb.scripts / "window_pos.py"
    target.write_text(target.read_text(encoding="utf-8") + "\n# tweak\n",
                      encoding="utf-8")
    edited = sha(target)
    code, out = sb.run("--undo", "--force")
    assert code == 0, out
    assert sb.stock()
    prev = sb.backup / "window_pos.py.prev"
    assert prev.is_file() and sha(prev) == edited
    assert "preserved your edits" in out
    code, out = sb.run("--undo", "--force")  # idempotent re-run
    assert code == 0, out
    assert sb.stock() and prev.is_file()


def test_unknown_backup_file_kept():
    sb = Sandbox()
    sb.apply_ok()
    stray = sb.backup / "unrelated.py"
    stray.write_text("x = 1\n", encoding="utf-8")
    code, out = sb.run("--undo", "--force")
    assert code == 0, out
    assert sb.stock()
    assert not (sb.scripts / "unrelated.py").exists(), \
        "unknown files must never be copied into scripts/"
    assert stray.is_file() and "unexpected files inside" in out


def test_corrupt_settings_reported():
    sb = Sandbox()
    sb.apply_ok()
    sb.settings.write_text("{not json", encoding="utf-8")
    code, out = sb.run("--undo", "--force")
    assert code == 1, "a failed unhook must fail the undo\n" + out
    assert "unhook failed" in out
    assert sb.stock(), "the repository restore itself should still happen"
    assert sb.backup.is_dir(), "folder must be kept for the retry"


def test_stop_failure_blocks_purge():
    sb = Sandbox()
    sb.apply_ok()
    state = sb.home / ".claude" / "buddy"
    state.mkdir(parents=True)
    (state / "config.json").write_text("{}", encoding="utf-8")
    sb.mod._stop_buddy = lambda: (False, "buddy: still running (stubbed)")
    code, out = sb.run("--undo", "--force", "--purge-data")
    assert code == 1, "an unconfirmed stop must not be reported as success\n" + out
    assert "buddy stop unconfirmed" in out
    assert (state / "config.json").is_file(), \
        "runtime data must not be purged while the buddy may be alive"


def test_restore_failure_rolls_back_with_meta():
    sb = Sandbox()
    sb.apply_ok()
    buddy = sb.scripts / "buddy.py"
    pre_bytes = buddy.read_bytes()
    pre_stat = buddy.stat()
    blocked = sb.scripts / "window_pos.py"
    os.chmod(blocked, RO)
    try:
        code, out = sb.run("--undo", "--force")
    finally:
        os.chmod(blocked, RW)
    assert code == 1, out
    assert "restore failed" in out and "rolled back" in out
    assert buddy.read_bytes() == pre_bytes, "rollback must restore contents"
    post_stat = buddy.stat()
    assert abs(post_stat.st_mtime - pre_stat.st_mtime) < 0.01, \
        "rollback must restore mtime"
    assert stat.S_IMODE(post_stat.st_mode) == stat.S_IMODE(pre_stat.st_mode), \
        "rollback must restore mode"
    assert sb.backup.is_dir()


def test_rollback_failure_reported():
    sb = Sandbox()
    sb.apply_ok()
    mod = sb.mod
    real = mod.shutil

    def copy2(src, dst, **kw):
        d, s = Path(dst), Path(src)
        if s.parent.name == "scripts_backup_macos":
            if d.name == "buddy.py":
                out = real.copy2(src, dst, **kw)
                os.chmod(d, RO)  # make the later write-back fail
                return out
            if d.name == "window_pos.py":
                raise OSError("injected failure")
        return real.copy2(src, dst, **kw)

    mod.shutil = _ShutilPatch(real, copy2=copy2)
    try:
        code, out = sb.run("--undo", "--force")
    finally:
        mod.shutil = real
        os.chmod(sb.scripts / "buddy.py", RW)
    assert code == 1, out
    assert "rollback also hit errors" in out, out
    assert "buddy.py" in out
    assert "undo complete" not in out and "rolled back to the applied state" not in out, \
        "a failed rollback must never read like a success"


def test_backup_cleanup_failure_reported():
    sb = Sandbox()
    sb.apply_ok()
    mod = sb.mod
    real = mod.shutil

    def rmtree(path, **kw):
        # macOS may expose the same temp path as /var/... and /private/var/...
        if Path(path).resolve() == sb.backup.resolve():
            return  # simulate an undeletable folder
        return real.rmtree(path, **kw)

    mod.shutil = _ShutilPatch(real, rmtree=rmtree)
    try:
        code, out = sb.run("--undo", "--force")
    finally:
        mod.shutil = real
    assert code == 0, out
    assert sb.stock()
    assert "could not remove scripts_backup_macos/" in out, out
    assert "removed: scripts_backup_macos/" not in out, \
        "never print removed when the folder is still there"


def test_default_undo_is_restore_only():
    sb = Sandbox()
    sb.apply_ok()
    before = sb.settings.read_bytes()
    code, out = sb.run("--undo")
    assert code == 0, out
    assert sb.stock()
    assert sb.settings.read_bytes() == before, \
        "no --force off macOS means settings.json stays byte-identical"
    assert "skipped on this non-macOS system" in out
    assert "hook wiring removed" not in out


def test_purge_gated_off_nonmac():
    sb = Sandbox()
    sb.apply_ok()
    state = sb.home / ".claude" / "buddy"
    state.mkdir(parents=True)
    (state / "config.json").write_text("{}", encoding="utf-8")
    code, out = sb.run("--undo", "--purge-data")
    assert code == 0, out
    assert (state / "config.json").is_file(), \
        "--purge-data without --force must not delete data off macOS"


def test_stock_tree_nothing_to_undo():
    sb = Sandbox()
    code, out = sb.run("--undo")
    assert code == 0, out
    assert "nothing to undo" in out
    assert sb.stock()


def test_stock_tree_with_leftover_folder():
    sb = Sandbox()
    sb.apply_ok()
    code, out = sb.run("--undo", "--force")
    assert code == 0, out
    sb.backup.mkdir()
    keepsake = sb.backup / "window_pos.py.prev"
    keepsake.write_text("# preserved earlier\n", encoding="utf-8")
    code, out = sb.run("--undo")
    assert code == 0, out
    assert "already looks stock" in out
    assert keepsake.is_file(), "a leftover .prev must never be deleted"


def test_stock_tree_undo_still_unhooks():
    sb = Sandbox()
    code, out = sb.run("--undo", "--force")  # never applied at all
    assert code == 0, out
    assert "looks stock" in out
    s = json.loads(sb.settings.read_text(encoding="utf-8"))
    assert "Stop" not in s.get("hooks", {}), \
        "a stock tree must still get this checkout's wiring removed"
    left = s["hooks"]["SessionStart"][0]["hooks"]
    assert len(left) == 2, "foreign checkout + user hook must survive"


def test_stock_tree_purge_gated_on_stop():
    sb = Sandbox()
    state = sb.home / ".claude" / "buddy"
    state.mkdir(parents=True)
    (state / "config.json").write_text("{}", encoding="utf-8")
    sb.load()
    sb.mod._stop_buddy = lambda: (False, "buddy: still running (stubbed)")
    code, out = sb.run("--undo", "--force", "--purge-data")
    assert code == 1, "an unconfirmed stop must fail the stock-tree undo too\n" + out
    assert (state / "config.json").is_file(), \
        "the purge gate must hold on the stock-tree path as well"


def test_legacy_undo_runs_external_steps():
    sb = Sandbox()
    sb.apply_ok()
    sb.manifest.unlink()
    code, out = sb.run("--undo", "--force")
    assert code == 1, out
    s = json.loads(sb.settings.read_text(encoding="utf-8"))
    assert "Stop" not in s.get("hooks", {}), \
        "legacy undo must still unhook this checkout"
    left = s["hooks"]["SessionStart"][0]["hooks"]
    assert len(left) == 2


def test_rollback_removes_recreated_file():
    sb = Sandbox()
    sb.apply_ok()
    (sb.scripts / "buddy.py").unlink()  # the applied file went missing
    blocked = sb.scripts / "window_pos.py"
    os.chmod(blocked, RO)
    try:
        code, out = sb.run("--undo", "--force")
    finally:
        os.chmod(blocked, RW)
    assert code == 1, out
    assert not (sb.scripts / "buddy.py").exists(), \
        "rollback must remove a file that did not exist before the undo"


def test_reapply_keeps_every_copy_prev():
    sb = Sandbox()
    sb.apply_ok()
    target = sb.scripts / "mac_audio.py"
    target.write_text(target.read_text(encoding="utf-8") + "\n# edit one\n",
                      encoding="utf-8")
    first = sha(target)
    code, out = sb.run("--force")
    assert code == 0, out
    target.write_text(target.read_text(encoding="utf-8") + "\n# edit two\n",
                      encoding="utf-8")
    second = sha(target)
    code, out = sb.run("--force")
    assert code == 0, out
    prevs = {sha(p) for p in sb.backup.glob("mac_audio.py*.prev")}
    assert first in prevs and second in prevs, \
        "every round of copy edits must keep its own .prev"


def test_manifest_version_and_shape_strict():
    sb = Sandbox()
    sb.apply_ok()
    good = sb.manifest.read_bytes()
    sb.edit_manifest(lambda d: d.update(version=True))
    _rejects(sb, "boolean version (True == 1)")
    sb.manifest.write_bytes(good)
    sb.edit_manifest(lambda d: d.update(extra_key=[]))
    _rejects(sb, "extra top-level key")


def test_stock_purge_blocked_on_unhook_failure():
    sb = Sandbox()
    state = sb.home / ".claude" / "buddy"
    state.mkdir(parents=True)
    (state / "config.json").write_text("{}", encoding="utf-8")
    sb.settings.write_text("{not json", encoding="utf-8")  # unhook will fail
    code, out = sb.run("--undo", "--force", "--purge-data")
    assert code == 1, out
    assert "unhook failed" in out
    assert "purge skipped" in out
    assert (state / "config.json").is_file(), \
        "a failed unhook must block the purge (hooks would revive the buddy)"


def test_legacy_restore_failure_keeps_data():
    sb = Sandbox()
    sb.apply_ok()
    sb.manifest.unlink()
    state = sb.home / ".claude" / "buddy"
    state.mkdir(parents=True)
    (state / "config.json").write_text("{}", encoding="utf-8")
    blocked = sb.scripts / "window_pos.py"
    os.chmod(blocked, RO)
    try:
        code, out = sb.run("--undo", "--force", "--purge-data")
    finally:
        os.chmod(blocked, RW)
    assert code == 1, out
    assert "legacy restore hit an error" in out
    assert (state / "config.json").is_file(), \
        "a failed legacy restore must never cost the runtime data as well"


def test_no_quit_stamp_without_target():
    sb = Sandbox()
    sb.load()
    sb.mod._stop_buddy = sb.mod._real_stop_buddy  # real logic under test
    sb.mod._buddy_present = lambda: False
    code, out = sb.run("--undo", "--force")
    assert code == 0, out
    assert "buddy: not running" in out
    assert not (sb.home / ".claude" / "buddy" / "quit.ts").exists(), \
        "no target buddy means no quit stamp (it would snooze OTHER checkouts)"


TESTS = [
    test_manifest_schema_accepts_valid,
    test_apply_undo_roundtrip_with_externals,
    test_manifest_missing_originals_key_rejected,
    test_manifest_missing_applied_key_rejected,
    test_manifest_created_foreign_path_rejected,
    test_manifest_bad_values_rejected,
    test_apply_refuses_missing_source,
    test_apply_refuses_invalid_manifest,
    test_reapply_preserves_edited_buddy,
    test_reapply_preserves_edited_hook_entry,
    test_legacy_apply_refuses_missing_backup,
    test_legacy_undo_preserves_edits,
    test_undo_refuses_incomplete_backup,
    test_undo_preserves_postapply_edits_and_reruns,
    test_unknown_backup_file_kept,
    test_corrupt_settings_reported,
    test_stop_failure_blocks_purge,
    test_restore_failure_rolls_back_with_meta,
    test_rollback_failure_reported,
    test_backup_cleanup_failure_reported,
    test_default_undo_is_restore_only,
    test_purge_gated_off_nonmac,
    test_stock_tree_nothing_to_undo,
    test_stock_tree_with_leftover_folder,
    test_stock_tree_undo_still_unhooks,
    test_stock_tree_purge_gated_on_stop,
    test_legacy_undo_runs_external_steps,
    test_rollback_removes_recreated_file,
    test_reapply_keeps_every_copy_prev,
    test_manifest_version_and_shape_strict,
    test_stock_purge_blocked_on_unhook_failure,
    test_legacy_restore_failure_keeps_data,
    test_no_quit_stamp_without_target,
]


def main() -> int:
    # this suite copies scripts/ as-is into its sandboxes, so it needs
    # the stock tree: run it BEFORE apply.py, or after --undo
    if "from mac_audio import MacBgmPlayer" in (
        (REPO / "scripts" / "buddy.py").read_text(encoding="utf-8")
    ):
        print("this suite needs a stock tree - run it BEFORE")
        print("experimental/macos/apply.py (or after --undo). An already-")
        print("patched tree would fail every case for the wrong reason.")
        shutil.rmtree(OUTER, ignore_errors=True)  # leave no empty temp dir
        return 1
    failed = []
    try:
        for fn in TESTS:
            try:
                fn()
                print(f"OK   {fn.__name__}")
            except Exception:
                failed.append(fn.__name__)
                print(f"FAIL {fn.__name__}")
                traceback.print_exc()
    finally:
        for k, v in _SAVED_ENV.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        # some tests leave read-only files behind on purpose; directories
        # also need their execute bit on POSIX or the removal below
        # cannot traverse into them
        for p in OUTER.rglob("*"):
            try:
                os.chmod(p, (RW | stat.S_IXUSR) if p.is_dir() else RW)
            except OSError:
                pass
        shutil.rmtree(OUTER, ignore_errors=True)
    if failed:
        print("FAILED:", ", ".join(failed))
        return 1
    print(f"ALL {len(TESTS)} TESTS PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
