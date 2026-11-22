# journal.py
from __future__ import annotations

import dataclasses
import datetime
import json
import os
import pathlib
import re

CONVERSATION = re.compile(r'"type"\s*:\s*"(?:user|assistant|attachment|queue-operation)"')
NOTICE_FIELD = {name: re.compile(rf"<{name}>([^<]*)</{name}>") for name in ("task-id", "tool-use-id", "status")}
RESUMING = ("SendMessage",)


@dataclasses.dataclass
class Call:
    id: str
    name: str
    input: dict
    start: float
    end: float
    resolved: bool = True
    task_id: str = ""
    agent_id: str = ""
    detached: bool = False


@dataclasses.dataclass
class Message:
    id: str
    first: float
    last: float
    calls: list[Call] = dataclasses.field(default_factory=list)


@dataclasses.dataclass
class Background:
    call: Call
    start: float
    end: float


@dataclasses.dataclass
class Journal:
    path: pathlib.Path
    agent_id: str = ""
    first: float = 0.0
    last: float = 0.0
    cwds: set[str] = dataclasses.field(default_factory=set)
    messages: list[Message] = dataclasses.field(default_factory=list)
    arrivals: list[float] = dataclasses.field(default_factory=list)
    backgrounds: list[Background] = dataclasses.field(default_factory=list)
    unresolved: int = 0


def moment(text: str) -> float:
    return datetime.datetime.fromisoformat(text.replace("Z", "+00:00")).timestamp()


def entries(path: pathlib.Path, seen: set[str]) -> list[dict]:
    rows = []
    with open(path, encoding="utf-8", errors="replace") as handle:
        for line in handle:
            if not CONVERSATION.search(line):
                continue
            try:
                row = json.loads(line)
            except ValueError:
                continue
            if not isinstance(row, dict) or not row.get("timestamp"):
                continue
            if row.get("type") not in ("user", "assistant", "attachment", "queue-operation"):
                continue
            uuid = row.get("uuid")
            if uuid:
                if uuid in seen:
                    continue
                seen.add(uuid)
            try:
                row["at"] = moment(row["timestamp"])
            except ValueError:
                continue
            rows.append(row)
    rows.sort(key=lambda row: row["at"])
    return rows


def blocks(row: dict) -> list[dict]:
    content = (row.get("message") or {}).get("content")
    return [block for block in content if isinstance(block, dict)] if isinstance(content, list) else []


def notice_text(row: dict) -> str:
    kind = row.get("type")
    if kind == "queue-operation" and row.get("operation") == "enqueue":
        text = row.get("content")
    elif kind == "attachment" and (row.get("attachment") or {}).get("type") == "queued_command":
        text = (row.get("attachment") or {}).get("prompt")
    elif kind == "user":
        text = (row.get("message") or {}).get("content")
    else:
        text = None
    return text if isinstance(text, str) and "<task-notification>" in text else ""


def notices(rows: list[dict]) -> list[tuple[float, str, str]]:
    found: dict[tuple[str, str], float] = {}
    for row in rows:
        text = notice_text(row)
        if not text:
            continue
        fields = {name: (pattern.search(text) or [None, ""])[1].strip() for name, pattern in NOTICE_FIELD.items()}
        if not fields["status"]:
            continue
        key = (fields["task-id"], fields["tool-use-id"])
        found[key] = min(row["at"], found.get(key, row["at"]))
    return sorted((at, task, call) for (task, call), at in found.items())


def is_arrival(row: dict) -> bool:
    kind = row.get("type")
    if kind == "user":
        return True
    if kind == "attachment":
        return (row.get("attachment") or {}).get("type") == "queued_command"
    return kind == "queue-operation" and row.get("operation") == "enqueue"


def collect_messages(rows: list[dict]) -> tuple[list[Message], dict[str, float]]:
    messages: dict[str, Message] = {}
    stamps: dict[str, float] = {}
    for row in rows:
        if row.get("type") != "assistant":
            continue
        key = (row.get("message") or {}).get("id") or row.get("uuid") or str(row["at"])
        message = messages.setdefault(key, Message(id=key, first=row["at"], last=row["at"]))
        message.first, message.last = min(message.first, row["at"]), max(message.last, row["at"])
        for block in blocks(row):
            if block.get("type") == "tool_use" and block.get("id"):
                stamps[block["id"]] = row["at"]
                message.calls.append(Call(id=block["id"], name=str(block.get("name") or ""), input=block.get("input") or {}, start=row["at"], end=row["at"]))
    return sorted(messages.values(), key=lambda message: message.first), stamps


def collect_results(rows: list[dict]) -> dict[str, tuple[float, dict]]:
    results: dict[str, tuple[float, dict]] = {}
    for row in rows:
        if row.get("type") != "user":
            continue
        detail = row.get("toolUseResult") if isinstance(row.get("toolUseResult"), dict) else {}
        for block in blocks(row):
            if block.get("type") == "tool_result" and block.get("tool_use_id"):
                results.setdefault(block["tool_use_id"], (row["at"], detail))
    return results


def settle_calls(book: Journal, rows: list[dict], stamps: dict[str, float], results: dict[str, tuple[float, dict]]) -> None:
    moments = [row["at"] for row in rows]
    for message in book.messages:
        for call in message.calls:
            result = results.get(call.id)
            if result is None:
                later = [at for at in moments if at > message.last]
                call.start, call.end, call.resolved = message.last, (later[0] if later else message.last), False
                book.unresolved += 1
                continue
            at, detail = result
            call.start = message.last if at >= message.last else stamps[call.id]
            call.end = max(at, call.start)
            call.task_id = str(detail.get("backgroundTaskId") or "")
            call.agent_id = str(detail.get("agentId") or "")
            call.detached = bool(call.task_id or detail.get("isAsync"))


def collect_backgrounds(book: Journal, rows: list[dict]) -> list[Background]:
    by_id = {call.id: call for message in book.messages for call in message.calls if call.resolved}
    waiting = {call.id: call for call in by_id.values() if call.detached or call.name in RESUMING}
    found = []
    for at, task, call_id in notices(rows):
        call = waiting.pop(call_id, None)
        if call is None:
            match = [c for c in waiting.values() if task and task in (c.task_id, c.agent_id) and c.end <= at]
            call = waiting.pop(match[0].id) if match else None
        if call is not None and at >= call.end:
            found.append(Background(call=call, start=call.end, end=at))
    return sorted(found, key=lambda item: item.start)


def read(path: pathlib.Path, seen: set[str] | None = None) -> Journal:
    path = pathlib.Path(path)
    book = Journal(path=path)
    rows = entries(path, seen if seen is not None else set())
    if not rows:
        return book
    book.first, book.last = rows[0]["at"], rows[-1]["at"]
    book.cwds = {row["cwd"] for row in rows if row.get("cwd")}
    book.agent_id = next((str(row["agentId"]) for row in rows if row.get("agentId")), "")
    book.messages, stamps = collect_messages(rows)
    results = collect_results(rows)
    settle_calls(book, rows, stamps, results)
    book.arrivals = sorted({row["at"] for row in rows if is_arrival(row)})
    book.backgrounds = collect_backgrounds(book, rows)
    return book


def agent_files(session: pathlib.Path) -> list[pathlib.Path]:
    session = pathlib.Path(session)
    return sorted((session.parent / session.stem / "subagents").glob("agent-*.jsonl"))


def session_files(projects: str | os.PathLike, root: str, since: float) -> list[pathlib.Path]:
    found = []
    for directory in sorted(pathlib.Path(projects).glob(re.sub(r"[^A-Za-z0-9]", "-", root) + "*")):
        if directory.is_dir():
            found += [path for path in sorted(directory.glob("*.jsonl")) if path.stat().st_mtime >= since]
    return found


def belongs(book: Journal, root: str) -> bool:
    root = root.rstrip(os.sep)
    scratch = os.path.join(root, ".claude", "scratch")
    inside = [cwd for cwd in book.cwds if cwd == root or cwd.startswith(root + os.sep)]
    return any(cwd != scratch and not cwd.startswith(scratch + os.sep) for cwd in inside)
