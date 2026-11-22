# intervals.py
from __future__ import annotations

import bisect
import dataclasses
import importlib
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
journal = importlib.import_module("journal")

HUMAN_WAIT = ("AskUserQuestion", "ExitPlanMode")
FOREGROUND = ("model", "tool")


@dataclasses.dataclass
class Item:
    start: float
    end: float
    kind: str
    call: journal.Call | None = None
    seconds: float = 0.0


@dataclasses.dataclass
class Measure:
    items: list[Item]
    idle: float
    span: float


def model_start(arrivals: list[float], first: float, previous_end: float | None) -> float:
    at = bisect.bisect_left(arrivals, first)
    start = arrivals[at - 1] if at else first
    if previous_end is not None and start < previous_end:
        start = min(previous_end, first)
    return start


def lay_out(book: journal.Journal) -> list[Item]:
    items: list[Item] = []
    previous_end = None
    for message in book.messages:
        start = model_start(book.arrivals, message.first, previous_end)
        items.append(Item(start, message.last, "model", message.calls[0] if message.calls else None))
        for call in message.calls:
            if call.name not in HUMAN_WAIT:
                items.append(Item(call.start, call.end, "tool", call))
        previous_end = message.last
    for wait in book.backgrounds:
        items.append(Item(wait.start, wait.end, "background", wait.call))
    return items


def clip(items: list[Item], begin: float, end: float) -> list[Item]:
    kept = []
    for item in items:
        start, stop = max(item.start, begin), min(item.end, end)
        if stop > start:
            kept.append(dataclasses.replace(item, start=start, end=stop, seconds=0.0))
    return kept


def share(items: list[Item]) -> float:
    edges = sorted({edge for item in items for edge in (item.start, item.end)})
    opening: dict[float, list[Item]] = {}
    closing: dict[float, list[Item]] = {}
    for item in items:
        opening.setdefault(item.start, []).append(item)
        closing.setdefault(item.end, []).append(item)
    active: list[Item] = []
    idle = 0.0
    for left, right in zip(edges, edges[1:]):
        ended = closing.get(left, [])
        active = [item for item in active if not any(item is done for done in ended)]
        active.extend(opening.get(left, []))
        front = [item for item in active if item.kind in FOREGROUND]
        holders = front or active
        if not holders:
            idle += right - left
        for item in holders:
            item.seconds += (right - left) / len(holders)
    return idle


def measure(book: journal.Journal, begin: float | None = None, end: float | None = None) -> Measure:
    begin = book.first if begin is None else max(begin, book.first)
    end = book.last if end is None else min(end, book.last)
    if end <= begin:
        return Measure(items=[], idle=0.0, span=0.0)
    items = clip(lay_out(book), begin, end)
    gaps = share(items)
    covered = sorted((item.start, item.end) for item in items)
    lead = (covered[0][0] - begin) if covered else end - begin
    tail = (end - max(stop for _, stop in covered)) if covered else 0.0
    return Measure(items=items, idle=gaps + lead + tail, span=end - begin)
