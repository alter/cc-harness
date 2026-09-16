# bash-read-guard.py
from __future__ import annotations

import json
import os
import pathlib
import shlex
import subprocess
import sys

LIMIT = int(os.environ.get("CC_READ_GUARD_LINES", "500"))
WHOLE_FILE = {"cat", "bat", "nl", "less", "more", "view", "batcat"}
WINDOWED = {"head", "tail"}
EXEMPT_SUFFIX = {".md", ".json", ".toml", ".yaml", ".yml", ".lock", ".txt"}
EXEMPT_PART = ("/docs/plans/", "/.claude/")
PROCESSED = ("|", ">", "<", "$(", "`")


def segments(command: str) -> list[list[str]]:
    out: list[list[str]] = []
    for part in command.replace("&&", ";").replace("||", ";").replace("&", ";").split(";"):
        part = part.strip()
        if not part:
            continue
        try:
            words = shlex.split(part)
        except ValueError:
            continue
        if words:
            out.append(words)
    return out


def window_size(words: list[str]) -> int | None:
    """Explicit line window for head/tail, None when the default (10 lines) applies."""
    expect_value = False
    for word in words[1:]:
        if expect_value:
            expect_value = False
            if word.startswith("+"):
                return 1 << 30
            if word.isdigit():
                return int(word)
            continue
        if word in ("-n", "-c"):
            expect_value = True
        elif word.startswith("--lines=") and word[8:].isdigit():
            return int(word[8:])
        elif word.startswith("-n") and word[2:].isdigit():
            return int(word[2:])
        elif len(word) > 1 and word[0] == "-" and word[1:].isdigit():
            return int(word[1:])
    return None


def is_text(path: pathlib.Path) -> bool:
    try:
        mime = subprocess.run(["file", "--mime", str(path)], capture_output=True, text=True, timeout=3).stdout
    except (OSError, subprocess.SubprocessError):
        return True
    return any(token in mime for token in ("text", "json", "xml", "empty"))


def too_long(path: pathlib.Path) -> int | None:
    if not path.is_file():
        return None
    if path.suffix.lower() in EXEMPT_SUFFIX or any(part in str(path) for part in EXEMPT_PART):
        return None
    if not is_text(path):
        return None
    try:
        with path.open("rb") as fh:
            lines = sum(1 for _ in fh)
    except OSError:
        return None
    return lines if lines > LIMIT else None


def deny(name: str, lines: int) -> None:
    reason = (
        f"{name} has {lines} lines (limit {LIMIT}). Reading a whole file through the shell fills the "
        "window exactly as a full Read would. Grep -n for the place and Read with offset and limit, or "
        "pipe this through grep/sed to the lines you need. For a whole large file, give it to the scout "
        "or researcher subagent and ask for a summary."
    )
    json.dump(
        {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny", "permissionDecisionReason": reason}},
        sys.stdout,
    )
    sys.stdout.write("\n")


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0
    if payload.get("tool_name") != "Bash":
        return 0
    command = (payload.get("tool_input") or {}).get("command") or ""
    if not command or any(token in command for token in PROCESSED):
        return 0

    for words in segments(command):
        name = os.path.basename(words[0])
        if name in WINDOWED:
            window = window_size(words)
            if window is None or window <= LIMIT:
                continue
        elif name not in WHOLE_FILE:
            continue
        for word in words[1:]:
            if word.startswith("-") or word.isdigit():
                continue
            lines = too_long(pathlib.Path(word).expanduser())
            if lines is not None:
                deny(os.path.basename(word), lines)
                return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
