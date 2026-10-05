# git-guard.py
from __future__ import annotations

import json
import os
import pathlib
import re
import shlex
import sys

GIT_OPTS_WITH_VALUE = {"-C", "-c", "--git-dir", "--work-tree", "--namespace", "--exec-path", "--super-prefix", "--config-env"}
WRAPPERS = {"sudo", "command", "exec", "env", "nice", "nohup", "time"}
SEPARATORS = re.compile(r"&&|\|\||[;&|\n]")


SHELLS = {"bash", "sh", "zsh", "dash", "ksh"}


def segments(command: str, depth: int = 0) -> list[list[str]]:
    out = []
    try:
        lexer = shlex.shlex(command, posix=True, punctuation_chars=";&|")
        lexer.whitespace_split = True
        tokens = list(lexer)
    except ValueError:
        tokens = command.split()
    parts: list[list[str]] = [[]]
    for tok in tokens:
        if tok and set(tok) <= set(";&|"):
            parts.append([])
        else:
            parts[-1].append(tok)
    for words in parts:
        while words and (re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", words[0]) or words[0] in WRAPPERS):
            words = words[1:]
        if not words:
            continue
        name = os.path.basename(words[0])
        if depth < 3 and name in SHELLS and "-c" in words[1:-1]:
            out.extend(segments(words[words.index("-c") + 1], depth + 1))
            continue
        if depth < 3 and name == "eval" and len(words) > 1:
            out.extend(segments(" ".join(words[1:]), depth + 1))
            continue
        out.append(words)
    return out


def git_call(words: list[str]) -> tuple[list[str], list[str]] | None:
    if os.path.basename(words[0]) != "git":
        return None
    i, options = 1, []
    while i < len(words) and words[i].startswith("-"):
        options.append(words[i])
        if words[i] in GIT_OPTS_WITH_VALUE and i + 1 < len(words):
            options.append(words[i + 1])
            i += 1
        i += 1
    return options, words[i:]


def git_reason(options: list[str], rest: list[str]) -> str | None:
    if any("core.hookspath" in o.lower() for o in options):
        return "it disables the repository's hooks (core.hooksPath)"
    if not rest:
        return None
    sub, args = rest[0], rest[1:]
    if sub == "stash":
        return "git stash hides uncommitted work, possibly someone else's"
    if sub == "reset" and "--hard" in args:
        return "git reset --hard discards uncommitted work"
    if sub == "clean" and not ({"-n", "--dry-run"} & set(args)):
        return "git clean deletes untracked files, possibly someone else's"
    if sub in ("checkout", "restore") and "--staged" not in args:
        paths = args[args.index("--") + 1:] if "--" in args else [a for a in args if not a.startswith("-")]
        if any(p in (".", ":/", "*") for p in paths) or (sub == "checkout" and "--" in args):
            return f"git {sub} over the working tree discards uncommitted changes"
    if sub == "push" and (
        {"-f", "--force", "--force-with-lease", "--force-if-includes"} & set(args)
        or any(a.startswith("--force") for a in args)
        or any(a.startswith("+") for a in args)
    ):
        return "a force push rewrites shared history"
    if "--no-verify" in args or (sub == "commit" and "-n" in args):
        return "--no-verify skips the repository's hooks"
    if sub == "config" and any("hookspath" in a.lower() for a in args):
        return "it redirects the repository's hooks (core.hooksPath)"
    return None


def project_denies(cwd: str) -> list[list[str]]:
    path = pathlib.Path(cwd or ".") / "docs" / "PROJECT.md"
    if not path.is_file():
        return []
    text = path.read_text(encoding="utf-8", errors="ignore")
    section = text.split("## 5.", 1)[1].split("\n## ", 1)[0] if "## 5." in text else ""
    m = re.search(r"```deny\n(.*?)```", section, re.S)
    if not m:
        return []
    return [line.split() for line in m.group(1).splitlines() if line.strip() and not line.strip().startswith("#")]


def deny(reason: str, command: str) -> None:
    text = (
        f"Refused: {reason}. Command: {command!r}. This is never done to make progress. "
        "If uncommitted changes block the task, mark it [!] BLOCKED and continue with others; "
        "if the owner wants this command, they run it themselves."
    )
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny", "permissionDecisionReason": text}}))


def main() -> int:
    if "git-guard" in os.environ.get("CC_DISABLED_HOOKS", "").split(","):
        return 0
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0
    if payload.get("tool_name") != "Bash":
        return 0
    command = (payload.get("tool_input") or {}).get("command") or ""
    extra = project_denies(payload.get("cwd") or "")
    for words in segments(command):
        call = git_call(words)
        if call:
            reason = git_reason(*call)
            if reason:
                deny(reason, command)
                return 0
        for prefix in extra:
            if words[: len(prefix)] == prefix:
                deny(f"docs/PROJECT.md §5 lists '{' '.join(prefix)}' as an action that needs the owner", command)
                return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
