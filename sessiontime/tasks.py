# tasks.py
from __future__ import annotations

import dataclasses
import os
import re
import subprocess

DONE = re.compile(r"^- \[x\] (T\d+\w*)\b", re.MULTILINE)
REST = "after the last mark"


@dataclasses.dataclass
class TaskWindow:
    task: str
    start: float
    end: float


class Unmeasurable(Exception):
    pass


def git(root: str, *arguments: str) -> str:
    done = subprocess.run(["git", "-C", root, *arguments], capture_output=True, text=True)
    if done.returncode != 0:
        raise Unmeasurable(done.stderr.strip().splitlines()[-1] if done.stderr.strip() else "git failed")
    return done.stdout


def repository(start: str) -> str:
    return git(start, "rev-parse", "--show-toplevel").strip()


def relative(root: str, plan: str) -> str:
    return os.path.relpath(os.path.realpath(plan), os.path.realpath(root))


def plan_commits(root: str, plan: str) -> list[tuple[float, str]]:
    lines = git(root, "log", "--reverse", "--format=%ct %H", "--", relative(root, plan)).split("\n")
    commits = [(float(line.split()[0]), line.split()[1]) for line in lines if line.strip()]
    if not commits:
        raise Unmeasurable("no commit touches the plan file")
    return commits


def done_at(root: str, plan: str, commit: str) -> set[str]:
    try:
        return set(DONE.findall(git(root, "show", f"{commit}:{relative(root, plan)}")))
    except Unmeasurable:
        return set()


def flips(root: str, plan: str, commits: list[tuple[float, str]]) -> list[tuple[str, float]]:
    found, known = [], set()
    for at, commit in commits:
        done = done_at(root, plan, commit)
        if done - known:
            found.append((", ".join(sorted(done - known)), at))
        known |= done
    return found


def windows(marks: list[tuple[str, float]], begin: float, end: float) -> list[TaskWindow]:
    found, start = [], begin
    for task, at in marks:
        at = min(max(at, begin), end)
        if at > start:
            found.append(TaskWindow(task=task, start=start, end=at))
            start = at
    if marks and end > start:
        found.append(TaskWindow(task=REST, start=start, end=end))
    return found
