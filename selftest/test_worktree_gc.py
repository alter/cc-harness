# test_worktree_gc.py
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

HERE = pathlib.Path(__file__).resolve().parent
GC = pathlib.Path(os.environ.get("WORKTREE_GC", HERE.parent / "hooks" / "worktree-gc.py"))
ENV = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t", "CC_GC_MIN_IDLE_HOURS": "0"}


def git(cwd, *args):
    return subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, text=True, env=ENV, check=True).stdout.strip()


class WorktreeGc(unittest.TestCase):
    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp()).resolve()
        self.repo = self.tmp / "repo"
        self.repo.mkdir()
        git(self.repo, "init", "-b", "main")
        (self.repo / "a.txt").write_text("a")
        git(self.repo, "add", "a.txt")
        git(self.repo, "commit", "-m", "init")

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def add(self, name, commit=False):
        path = self.tmp / name
        git(self.repo, "worktree", "add", "-b", name, str(path))
        if commit:
            (path / f"{name}.txt").write_text(name)
            git(path, "add", f"{name}.txt")
            git(path, "commit", "-m", name)
        return path

    def gc(self, *args, env=None):
        return subprocess.run([sys.executable, str(GC), "--repo", str(self.repo), *args], capture_output=True, text=True, env={**ENV, **(env or {})})

    def test_clean_merged_worktree_is_removed_with_its_branch(self):
        path = self.add("done")
        self.gc()
        self.assertFalse(path.exists())
        self.assertNotIn("done", git(self.repo, "branch", "--list", "done"))

    def test_merged_after_commit_is_removed(self):
        path = self.add("merged", commit=True)
        git(self.repo, "merge", "--no-ff", "-m", "m", "merged")
        self.gc()
        self.assertFalse(path.exists())

    def test_unmerged_commits_are_kept(self):
        path = self.add("wip", commit=True)
        self.gc()
        self.assertTrue(path.exists())

    def test_modified_file_is_kept(self):
        path = self.add("dirty")
        (path / "a.txt").write_text("changed")
        self.gc()
        self.assertTrue(path.exists())

    def test_untracked_file_is_kept(self):
        path = self.add("untracked")
        (path / "new.txt").write_text("x")
        self.gc()
        self.assertTrue(path.exists())

    def test_recently_active_is_kept(self):
        path = self.add("fresh")
        self.gc(env={"CC_GC_MIN_IDLE_HOURS": "24"})
        self.assertTrue(path.exists())

    def test_locked_is_kept(self):
        path = self.add("locked")
        git(self.repo, "worktree", "lock", str(path))
        self.gc()
        self.assertTrue(path.exists())

    def test_dry_run_changes_nothing(self):
        path = self.add("dry")
        r = self.gc("--dry-run")
        self.assertTrue(path.exists())
        self.assertIn("would remove 1", r.stdout)

    def test_stale_scratch_is_removed_and_fresh_kept(self):
        scratch = self.repo / ".claude" / "scratch"
        old, fresh = scratch / "old", scratch / "fresh"
        old.mkdir(parents=True)
        fresh.mkdir()
        (old / "f.log").write_text("x")
        (fresh / "f.log").write_text("x")
        stale = time.time() - 30 * 86400
        for p in (old / "f.log", old):
            os.utime(p, (stale, stale))
        self.add("anything")
        self.gc()
        self.assertFalse(old.exists())
        self.assertTrue(fresh.exists())

    def test_hook_mode_honours_kill_switch_and_ignores_compact(self):
        path = self.add("hooked")
        payload = f'{{"cwd": "{self.repo}", "source": "startup"}}'
        subprocess.run([sys.executable, str(GC)], input=payload, text=True, env={**ENV, "CC_DISABLED_HOOKS": "worktree-gc"})
        time.sleep(1.5)
        self.assertTrue(path.exists())
        subprocess.run([sys.executable, str(GC)], input=payload.replace("startup", "compact"), text=True, env=ENV)
        time.sleep(1.5)
        self.assertTrue(path.exists())
        subprocess.run([sys.executable, str(GC)], input=payload, text=True, env=ENV)
        for _ in range(30):
            if not path.exists():
                break
            time.sleep(0.3)
        self.assertFalse(path.exists())


if __name__ == "__main__":
    unittest.main()
