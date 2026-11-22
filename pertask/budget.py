# budget.py
from __future__ import annotations

import json
import os
import pathlib
import re

DEFAULT_LIMIT = 30.0
LIMIT_LABEL = "Per-task limit for gate checks, seconds"
LIMIT_ROW = re.compile(r"^\s*\|\s*" + re.escape(LIMIT_LABEL) + r"\s*\|([^|\n]*)\|", re.MULTILINE)
STATE_DIR = pathlib.Path(".claude") / "scratch" / "pertask"


def empty() -> dict:
    return {"seq": 0, "commands": {}}


def positive(text: object) -> float | None:
    try:
        value = float(str(text).strip())
    except ValueError:
        return None
    return value if value > 0 else None


def limit(root: pathlib.Path, flag: float | None = None) -> float:
    if flag is not None and positive(flag) is not None:
        return positive(flag)
    try:
        text = (pathlib.Path(root) / "docs" / "PROJECT.md").read_text(encoding="utf-8")
    except OSError:
        return DEFAULT_LIMIT
    for answer in LIMIT_ROW.findall(text):
        value = positive(answer)
        if value is not None:
            return value
    return DEFAULT_LIMIT


def plan_key(root: pathlib.Path, plan: str) -> str:
    base = os.path.realpath(root)
    target = os.path.realpath(os.path.join(base, plan))
    relative = os.path.relpath(target, base)
    return relative.replace(os.sep, "_")


def state_path(root: pathlib.Path, plan: str) -> pathlib.Path:
    return pathlib.Path(root) / STATE_DIR / (plan_key(root, plan) + ".json")


def load(path: pathlib.Path) -> dict:
    try:
        state = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return empty()
    if not isinstance(state, dict) or not isinstance(state.get("commands"), dict) or not isinstance(state.get("seq"), int):
        return empty()
    return state


def save(path: pathlib.Path, state: dict) -> None:
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    draft = path.with_name(path.name + f".{os.getpid()}.tmp")
    draft.write_text(json.dumps(state, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(draft, path)


def entry(state: dict, command: str) -> dict:
    return state["commands"].setdefault(command, {"seconds": None, "exit": None, "ran": 0, "skipped": 0})


def tick(state: dict) -> int:
    state["seq"] += 1
    return state["seq"]


def note_run(state: dict, command: str, seconds: float, code: int) -> None:
    record = entry(state, command)
    known = record["seconds"]
    if code == 0 or known is None or seconds > known:
        record["seconds"] = round(seconds, 2)
    record["exit"] = code
    record["ran"] = tick(state)


def note_skip(state: dict, command: str) -> None:
    entry(state, command)["skipped"] = tick(state)


def fitting(state: dict, seconds: float) -> list[str]:
    known = [(record["seconds"], command) for command, record in state["commands"].items() if record["seconds"] is not None]
    chosen: list[str] = []
    spent = 0.0
    for cost, command in sorted(known):
        if spent + cost > seconds:
            break
        spent += cost
        chosen.append(command)
    return chosen


def runs_now(state: dict, command: str, seconds: float) -> bool:
    record = state["commands"].get(command)
    if record is None or record["seconds"] is None:
        return True
    return command in fitting(state, seconds)


def deferred(state: dict) -> list[str]:
    return sorted(command for command, record in state["commands"].items() if record["skipped"] > record["ran"])
