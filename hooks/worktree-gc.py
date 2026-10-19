# worktree-gc.py
import json
import os
import pathlib
import shutil
import subprocess
import sys
import time

HOOK_ID = "worktree-gc"
MIN_IDLE_HOURS = float(os.environ.get("CC_GC_MIN_IDLE_HOURS", "6"))
SCRATCH_DAYS = float(os.environ.get("CC_GC_SCRATCH_DAYS", "7"))


def git(repo, *args):
    r = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True)
    return r.returncode, r.stdout.strip()


def list_worktrees(repo):
    code, out = git(repo, "worktree", "list", "--porcelain")
    if code != 0:
        return []
    trees, cur = [], {}
    for line in out.splitlines() + [""]:
        if not line:
            if cur:
                trees.append(cur)
            cur = {}
            continue
        key, _, value = line.partition(" ")
        cur[key] = value or True
    return trees


def base_ref(main):
    code, out = git(main, "symbolic-ref", "--short", "refs/remotes/origin/HEAD")
    if code == 0 and out:
        return out
    code, out = git(main, "symbolic-ref", "--short", "HEAD")
    return out if code == 0 else ""


def newest_mtime(path, cutoff):
    newest = 0.0
    for root, dirs, files in os.walk(path):
        for name in dirs + files:
            try:
                m = os.lstat(os.path.join(root, name)).st_mtime
            except OSError:
                continue
            if m > newest:
                newest = m
            if newest >= cutoff:
                return newest
    try:
        return max(newest, os.lstat(path).st_mtime)
    except OSError:
        return newest


def idle_since(tree):
    gitdir = pathlib.Path(tree["worktree"]) / ".git"
    stamps = []
    for p in (pathlib.Path(tree["worktree"]), gitdir):
        try:
            stamps.append(p.stat().st_mtime)
        except OSError:
            pass
    code, out = git(tree["worktree"], "rev-parse", "--git-dir")
    if code == 0:
        for name in ("index", "HEAD"):
            try:
                stamps.append((pathlib.Path(tree["worktree"]) / out / name).stat().st_mtime)
            except OSError:
                pass
    return max(stamps) if stamps else 0.0


def verdict(main, tree, base, cwd, now):
    path = pathlib.Path(tree["worktree"]).resolve()
    if tree.get("locked"):
        return "locked"
    if cwd and (cwd == path or path in cwd.parents):
        return "current directory"
    if not path.exists():
        return "missing"
    if now - idle_since(tree) < MIN_IDLE_HOURS * 3600:
        return "recently active"
    code, out = git(path, "status", "--porcelain", "--untracked-files=normal")
    if code != 0 or out:
        return "uncommitted or untracked files"
    head = tree.get("HEAD")
    if not head or not base:
        return "no base to compare"
    if subprocess.run(["git", "-C", str(main), "merge-base", "--is-ancestor", head, base], capture_output=True).returncode != 0:
        return "commits not merged into " + base
    return "removable"


def remove_tree(main, tree, base):
    path = tree["worktree"]
    code, _ = git(main, "worktree", "remove", path)
    if code != 0:
        return False
    branch = str(tree.get("branch", "")).removeprefix("refs/heads/")
    if branch and branch != base:
        git(main, "branch", "-d", branch)
    return True


def clean_scratch(root, now):
    scratch = pathlib.Path(root) / ".claude" / "scratch"
    freed = 0
    if not scratch.is_dir():
        return freed
    cutoff = now - SCRATCH_DAYS * 86400
    for entry in scratch.iterdir():
        if entry.name == "gc.log" or newest_mtime(entry, cutoff) >= cutoff:
            continue
        size = disk_size(entry)
        try:
            shutil.rmtree(entry) if entry.is_dir() and not entry.is_symlink() else entry.unlink()
        except OSError:
            continue
        freed += size
    return freed


def disk_size(path):
    total = 0
    for root, _, files in os.walk(path):
        for name in files:
            try:
                total += os.lstat(os.path.join(root, name)).st_size
            except OSError:
                pass
    return total


def collect(repo, dry_run, now=None):
    now = now if now is not None else time.time()
    trees = list_worktrees(repo)
    if not trees:
        return {"removed": [], "kept": {}, "scratch_freed": 0}
    main = pathlib.Path(trees[0]["worktree"])
    base = base_ref(main)
    cwd = pathlib.Path(repo).resolve()
    removed, kept, freed = [], {}, 0
    for tree in trees[1:]:
        why = verdict(main, tree, base, cwd, now)
        if why == "missing":
            continue
        if why != "removable":
            kept[tree["worktree"]] = why
            continue
        size = disk_size(tree["worktree"])
        if dry_run or remove_tree(main, tree, base):
            removed.append(tree["worktree"])
            freed += size
    if not dry_run:
        git(main, "worktree", "prune")
        freed += clean_scratch(main, now)
        for tree in trees[1:]:
            freed += 0 if tree["worktree"] in removed else clean_scratch(tree["worktree"], now)
    return {"removed": removed, "kept": kept, "scratch_freed": freed}


def acquire_lock(repo):
    code, out = git(repo, "rev-parse", "--git-common-dir")
    if code != 0:
        return None
    lock = (pathlib.Path(repo) / out / "cc-worktree-gc.lock").resolve()
    try:
        if lock.exists() and time.time() - lock.stat().st_mtime < 3600:
            return None
        lock.write_text(str(os.getpid()))
    except OSError:
        return None
    return lock


def run_collect(repo, dry_run):
    lock = None if dry_run else acquire_lock(repo)
    if not dry_run and lock is None:
        return None
    try:
        return collect(repo, dry_run)
    finally:
        if lock is not None:
            lock.unlink(missing_ok=True)


def log_result(repo, result):
    trees = list_worktrees(repo)
    if not trees or result is None:
        return
    scratch = pathlib.Path(trees[0]["worktree"]) / ".claude" / "scratch"
    try:
        scratch.mkdir(parents=True, exist_ok=True)
        with open(scratch / "gc.log", "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"at": int(time.time()), "removed": len(result["removed"]), "kept": len(result["kept"]), "freed_bytes": result["scratch_freed"]}) + "\n")
    except OSError:
        pass


def cli(argv):
    dry_run = "--dry-run" in argv
    repo = os.getcwd()
    if "--repo" in argv:
        repo = argv[argv.index("--repo") + 1]
    result = run_collect(repo, dry_run)
    if result is None:
        print("another collection is running or this is not a git repository")
        return 1
    verb = "would remove" if dry_run else "removed"
    print(f"{verb} {len(result['removed'])} worktrees, kept {len(result['kept'])}, freed {result['scratch_freed'] / 1e6:.1f} MB")
    for path, why in sorted(result["kept"].items()):
        print(f"kept {path}: {why}")
    if not dry_run:
        log_result(repo, result)
    return 0


def hook():
    if HOOK_ID in os.environ.get("CC_DISABLED_HOOKS", "").split(","):
        return 0
    try:
        payload = json.load(sys.stdin)
    except ValueError:
        return 0
    cwd = payload.get("cwd")
    if not cwd or payload.get("source", "startup") not in ("startup", "resume", "clear"):
        return 0
    subprocess.Popen([sys.executable, os.path.abspath(__file__), "--repo", cwd], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    return 0


if __name__ == "__main__":
    sys.exit(cli(sys.argv[1:]) if len(sys.argv) > 1 else hook())
