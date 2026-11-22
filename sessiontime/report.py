# report.py
from __future__ import annotations

import dataclasses
import datetime
import importlib
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
intervals = importlib.import_module("intervals")
rules = importlib.import_module("rules")
tasks = importlib.import_module("tasks")

WAITING = "agents"
ROLES = ("main", "agents")


@dataclasses.dataclass
class Sheet:
    name: str
    role: str
    measure: intervals.Measure


@dataclasses.dataclass
class Summary:
    seconds: dict[str, dict[str, float]]
    active: dict[str, float]
    idle: float
    per_task: list[tuple[str, float, float]]
    longest_other: list[tuple[float, str]]
    sheets: list[Sheet]


def category(item: intervals.Item, book: rules.Rules) -> str:
    if item.call is None:
        return "reply"
    model, wait = rules.categories(item.call.name, item.call.input, book)
    return model if item.kind == "model" else wait


def label(item: intervals.Item) -> str:
    if item.call is None:
        return "(reply)"
    if item.call.name == "Bash":
        text, _ = rules.strip_heredocs(str(item.call.input.get("command") or ""))
        return "Bash: " + " ".join(text.split())[:110]
    target = item.call.input.get("file_path") or item.call.input.get("description") or item.call.input.get("skill") or ""
    return f"{item.call.name}: {target}"[:120]


def inside(item: intervals.Item, window: tasks.TaskWindow) -> float:
    length = item.end - item.start
    overlap = min(item.end, window.end) - max(item.start, window.start)
    return item.seconds * overlap / length if length > 0 and overlap > 0 else 0.0


def summarise(sheets: list[Sheet], book: rules.Rules, windows: list[tasks.TaskWindow], top: int = 10) -> Summary:
    seconds = {role: dict.fromkeys(rules.CATEGORIES, 0.0) for role in ROLES}
    others: dict[str, float] = {}
    per_task = {window.task: [0.0, 0.0] for window in windows}
    for sheet in sheets:
        for item in sheet.measure.items:
            kind = category(item, book)
            seconds[sheet.role][kind] += item.seconds
            if kind == "other":
                others[label(item)] = others.get(label(item), 0.0) + item.seconds
            if kind == WAITING:
                continue
            for window in windows:
                part = inside(item, window)
                per_task[window.task][1] += part
                if kind == "runs":
                    per_task[window.task][0] += part
    active = {role: sum(value for kind, value in seconds[role].items() if kind != WAITING) for role in ROLES}
    longest = sorted(((value, name) for name, value in others.items()), reverse=True)[:top]
    idle = sum(sheet.measure.idle for sheet in sheets if sheet.role == "main")
    rows = [(task, run, whole) for task, (run, whole) in per_task.items()]
    return Summary(seconds=seconds, active=active, idle=idle, per_task=rows, longest_other=longest, sheets=sheets)


def minutes(value: float) -> str:
    return f"{value / 60:.1f}"


def percent(part: float, whole: float) -> str:
    return f"{100 * part / whole:.0f}%" if whole > 0 else "0%"


def total(summary: Summary, kind: str) -> float:
    return sum(summary.seconds[role][kind] for role in ROLES)


def timing_line(summary: Summary) -> str:
    active = sum(summary.active.values())
    runs = total(summary, "runs")
    return (
        f"timing: runs {percent(runs, active)} of {minutes(active)} active min "
        f"({minutes(runs)} min: main {minutes(summary.seconds['main']['runs'])}, agents {minutes(summary.seconds['agents']['runs'])}); "
        f"development {percent(total(summary, 'product code'), active)}, test writing {percent(total(summary, 'test code'), active)}, "
        f"unclassified {percent(total(summary, 'other'), active)}; idle {minutes(summary.idle)} min; {len(summary.sheets)} transcript(s)"
    )


def unmeasured(reason: str) -> str:
    return f"timing: not measured — {reason}"


def clock(at: float) -> str:
    return datetime.datetime.fromtimestamp(at).astimezone().strftime("%Y-%m-%d %H:%M")


def category_rows(summary: Summary, active: float) -> list[str]:
    lines = ["| category | main, min | agents, min | total, min | share of active |", "|---|---|---|---|---|"]
    for kind in rules.CATEGORIES:
        main, agents = summary.seconds["main"][kind], summary.seconds["agents"][kind]
        if kind == WAITING:
            lines.append(f"| waiting for agents | {minutes(main)} | {minutes(agents)} | not counted | their own transcripts carry it |")
        else:
            lines.append(f"| {kind} | {minutes(main)} | {minutes(agents)} | {minutes(main + agents)} | {percent(main + agents, active)} |")
    lines.append(f"| active | {minutes(summary.active['main'])} | {minutes(summary.active['agents'])} | {minutes(active)} | 100% |")
    lines.append(f"| idle (main) | {minutes(summary.idle)} | | | |")
    return lines


def transcript_rows(summary: Summary) -> list[str]:
    lines = ["| transcript | role | span, min | items, min | idle, min | items + idle − span, s |", "|---|---|---|---|---|---|"]
    for sheet in summary.sheets:
        items = sum(item.seconds for item in sheet.measure.items)
        gap = items + sheet.measure.idle - sheet.measure.span
        lines.append(f"| {sheet.name} | {sheet.role} | {minutes(sheet.measure.span)} | {minutes(items)} | {minutes(sheet.measure.idle)} | {gap:.3f} |")
    return lines


def render(plan: str, begin: float, end: float, summary: Summary) -> str:
    active = sum(summary.active.values())
    shares = [percent(total(summary, kind), active) for kind in ("product code", "test code", "runs")]
    lines = [f"# Session timing: {plan}", "", f"Window {clock(begin)} → {clock(end)}, {len(summary.sheets)} transcript(s).", ""]
    lines += category_rows(summary, active)
    lines += ["", f"Development {shares[0]}, test writing {shares[1]}, runs {shares[2]} of active time.", ""]
    lines += ["## Runs per task", "", "| task | runs, min | active, min |", "|---|---|---|"]
    lines += [f"| {task} | {minutes(run)} | {minutes(whole)} |" for task, run, whole in summary.per_task] or ["| (no task mark in the window) | | |"]
    lines += ["", f"## Unclassified: {percent(total(summary, 'other'), active)} of active time", "", "| min | command |", "|---|---|"]
    lines += [f"| {minutes(value)} | `{name.replace('|', '¦').replace('`', chr(39))}` |" for value, name in summary.longest_other] or ["| 0.0 | (none) |"]
    lines += ["", "## Transcripts", ""] + transcript_rows(summary)
    lines += ["", timing_line(summary), ""]
    return "\n".join(lines)
