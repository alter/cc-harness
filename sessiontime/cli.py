# cli.py
from __future__ import annotations

import argparse
import importlib
import os
import pathlib
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
journal = importlib.import_module("journal")
intervals = importlib.import_module("intervals")
rules = importlib.import_module("rules")
tasks = importlib.import_module("tasks")
report = importlib.import_module("report")


def parse(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="cc-sessiontime", description="Where the time of a plan went: development, test writing, runs.")
    parser.add_argument("--plan", required=True)
    parser.add_argument("--from", dest="start", default="", help="ISO 8601; default: the first commit of the plan file")
    parser.add_argument("--to", dest="stop", default="", help="ISO 8601 or now; default: the last commit of the plan file")
    parser.add_argument("--product", default="", help="product code paths, comma separated; default: the row of docs/PROJECT.md")
    parser.add_argument("--tests", default="", help="test paths, comma separated; default: the row of docs/PROJECT.md")
    parser.add_argument("--runs", default="", help="extra runner tokens, comma separated")
    parser.add_argument("--projects", default="", help="transcript directory; default: ~/.claude/projects")
    return parser.parse_args(argv)


def when(text: str) -> float:
    if text == "now":
        return time.time()
    try:
        return journal.moment(text)
    except ValueError:
        raise tasks.Unmeasurable(f"cannot read the time {text!r}: ISO 8601 or now") from None


def window(root: str, plan: str, start: str, stop: str) -> tuple[float, float, list[tuple[str, float]]]:
    try:
        commits = tasks.plan_commits(root, plan)
    except tasks.Unmeasurable:
        if not (start and stop):
            raise
        commits = []
    begin = when(start) if start else commits[0][0]
    end = when(stop) if stop else commits[-1][0]
    if end <= begin:
        raise tasks.Unmeasurable("the window is empty: the plan file has one commit, or --to is not after --from")
    return begin, end, tasks.flips(root, plan, commits)


def sheets(root: str, projects: str, begin: float, end: float) -> list[report.Sheet]:
    seen: set[str] = set()
    found = []
    for session in journal.session_files(projects, root, begin):
        book = journal.read(session, seen)
        if not journal.belongs(book, root):
            continue
        books = [("main", session, book)] + [("agents", path, journal.read(path, seen)) for path in journal.agent_files(session)]
        for role, path, entry in books:
            measure = intervals.measure(entry, begin, end)
            if measure.span > 0:
                found.append(report.Sheet(name=path.stem, role=role, measure=measure))
    return found


def gather(arguments: argparse.Namespace) -> tuple[report.Summary, float, float]:
    plan = os.path.abspath(arguments.plan)
    if not os.path.isfile(plan):
        raise tasks.Unmeasurable("the plan file does not exist")
    root = tasks.repository(os.path.dirname(plan))
    begin, end, marks = window(root, plan, arguments.start, arguments.stop)
    home = os.environ.get("CLAUDE_CONFIG_DIR") or os.path.expanduser("~/.claude")
    found = sheets(root, arguments.projects or os.path.join(home, "projects"), begin, end)
    if not found:
        raise tasks.Unmeasurable("no transcript of this repository overlaps the window")
    book = rules.load(root, arguments.product, arguments.tests, arguments.runs)
    return report.summarise(found, book, tasks.windows(marks, begin, end)), begin, end


def main(argv: list[str]) -> int:
    arguments = parse(argv)
    try:
        summary, begin, end = gather(arguments)
    except (tasks.Unmeasurable, OSError) as problem:
        print(report.unmeasured(str(problem)))
        return 0
    print(report.render(arguments.plan, begin, end, summary))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
