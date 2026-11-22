# cli.py
from __future__ import annotations

import argparse
import importlib
import os
import pathlib
import shlex
import subprocess
import sys
import time

sys.dont_write_bytecode = True
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
budget = importlib.import_module("budget")


def project_root() -> pathlib.Path:
    found = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True)
    if found.returncode == 0 and found.stdout.strip():
        return pathlib.Path(found.stdout.strip())
    return pathlib.Path.cwd()


def split(argv: list[str]) -> tuple[list[str], str]:
    if "--" not in argv:
        return argv, ""
    at = argv.index("--")
    words = argv[at + 1:]
    command = words[0] if len(words) == 1 else shlex.join(words)
    return argv[:at], command.strip()


def seconds(value: float) -> str:
    return f"{value:.0f}s" if value >= 10 else f"{value:.1f}s"


def execute(command: str) -> tuple[int, float]:
    started = time.monotonic()
    code = subprocess.run(["bash", "-c", command]).returncode
    return (128 - code if code < 0 else code), time.monotonic() - started


def run_and_note(path: pathlib.Path, command: str) -> int:
    code, elapsed = execute(command)
    state = budget.load(path)
    budget.note_run(state, command, elapsed, code)
    budget.save(path, state)
    print(f"pertask: ran in {seconds(elapsed)}, exit {code}: {command}", file=sys.stderr)
    return code


def run(path: pathlib.Path, plan: str, command: str, limit: float) -> int:
    state = budget.load(path)
    if budget.runs_now(state, command, limit):
        return run_and_note(path, command)
    measured = state["commands"][command]["seconds"]
    budget.note_skip(state, command)
    budget.save(path, state)
    print(
        f"SKIPPED (per-plan): {command} — measured {seconds(measured)}, the per-task limit is {seconds(limit)}; "
        f"it runs before a push or a deploy and when the plan closes: cc-pertask record --plan {plan} -- {shlex.quote(command)}"
    )
    return 0


def status(path: pathlib.Path, plan: str, limit: float) -> int:
    state = budget.load(path)
    owed = budget.deferred(state)
    fits = set(budget.fitting(state, limit))
    print(f"pertask: {plan}: per-task limit {seconds(limit)}, {len(state['commands'])} command(s), {len(owed)} deferred")
    for command, record in sorted(state["commands"].items(), key=lambda item: (item[1]["seconds"] or 0, item[0])):
        if record["seconds"] is None:
            where, cost = "unmeasured", "-"
        else:
            where, cost = ("per-task" if command in fits else "per-plan"), seconds(record["seconds"])
        last = "never ran" if record["exit"] is None else f"last exit {record['exit']}"
        mark = "DEFERRED" if command in owed else "ok"
        print(f"  {mark:<8}  {where:<10}  {cost:>6}  {last}  {command}")
    return 1 if owed else 0


def main(argv: list[str]) -> int:
    options, command = split(argv)
    parser = argparse.ArgumentParser(prog="cc-pertask", description="Hold the gate checks run before a task mark to a time limit.")
    parser.add_argument("action", choices=("run", "record", "status"))
    parser.add_argument("--plan", required=True)
    parser.add_argument("--limit", type=float)
    args = parser.parse_args(options)
    if args.action != "status" and not command:
        parser.error(f"{args.action} needs a command after --")
    root = project_root()
    path = budget.state_path(root, os.path.abspath(args.plan))
    limit = budget.limit(root, args.limit)
    if args.action == "status":
        return status(path, args.plan, limit)
    if args.action == "record":
        return run_and_note(path, command)
    return run(path, args.plan, command, limit)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
