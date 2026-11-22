# rules.py
from __future__ import annotations

import dataclasses
import fnmatch
import os
import pathlib
import re
import shlex

CATEGORIES = ("product code", "test code", "runs", "records", "docs", "read-search", "agents", "reply", "other")
PRODUCT_LABEL = "Product code paths"
TESTS_LABEL = "Test paths"
DEFAULT_TESTS = ("tests/", "test/", "__tests__/", "e2e/", "spec/", "selftest/", "test_*", "*_test.*", "*.test.*", "*.spec.*", "conftest.py")
RECORDS = ("docs/plans/", "tasks/", "CHANGELOG*", ".claude/")
DOCS = ("*.md", "*.rst", "*.txt", "*.adoc", "docs/")
THROWAWAY = ("/tmp/", "/private/tmp/", "/var/folders/", "/dev/", ".claude/scratch/")
THROWAWAY_ENDINGS = (".log", ".out", ".tsv")
RUNNERS = (
    "pytest", "py.test", "unittest", "tox", "nox", "vitest", "jest", "mocha", "playwright", "cypress", "rspec", "phpunit", "ctest",
    "ruff", "mypy", "pyright", "flake8", "pylint", "eslint", "tsc", "shellcheck", "golangci-lint", "cc-fullrun", "cc-pertask",
    "go test", "go vet", "cargo test", "cargo clippy", "cargo check", "npm test", "npm run test", "pnpm test", "pnpm run test",
    "yarn test", "bun test", "deno test", "make test", "make check", "gradle test", "gradlew test", "mvn test", "swift test",
    "dotnet test", "flutter test", "xcodebuild test",
)
WRAPPERS = {"timeout": 1, "time": 0, "env": 0, "sudo": 0, "nice": 0, "nohup": 0, "exec": 0, "command": 0, "npx": 0, "bunx": 0}
WRAPPER_PAIRS = {("uv", "run"), ("poetry", "run"), ("pnpm", "exec"), ("pipenv", "run"), ("hatch", "run")}
INTERPRETERS = {"python", "python3", "node", "ruby", "perl", "bash", "sh", "zsh"}
READERS = {
    "cat", "ls", "grep", "rg", "find", "head", "tail", "wc", "awk", "jq", "tree", "stat", "file", "diff", "which", "pwd", "du", "sort",
    "uniq", "cut", "tr", "nl", "less", "sed", "fd", "bat", "column", "basename", "dirname", "realpath", "readlink", "cmp", "xxd", "date",
}
NEUTRAL = {"cd", "echo", "true", "printf", "test", "[", "export", "set", ":", "pushd", "popd"}
GIT_READS = {"log", "status", "diff", "show", "blame", "ls-files", "rev-parse", "describe", "grep", "cat-file", "ls-remote", "branch", "remote", "config", "shortlog", "reflog"}
SEARCH_TOOLS = {"Read", "Grep", "Glob", "ToolSearch", "WebFetch", "WebSearch", "LSP", "ListMcpResourcesTool", "ReadMcpResourceTool"}
AGENT_TOOLS = {"Agent", "Task", "SendMessage", "ListAgents", "TaskStop", "TaskOutput", "Workflow"}
EDIT_TOOLS = {"Edit", "Write", "NotebookEdit", "MultiEdit"}
HEREDOC = re.compile(r"<<-?\s*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\1")
REDIRECT = re.compile(r"(?<![0-9&>])>>?\s*([^\s;&|<>()]+)")
PATH_LITERAL = re.compile(r"""["']([A-Za-z0-9_./@+-]+\.[A-Za-z0-9]{1,6})["']""")
ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
GATE_HEADING = re.compile(r"^(#+)\s.*gate checks", re.IGNORECASE)


@dataclasses.dataclass
class Rules:
    root: str = ""
    product: tuple[str, ...] = ()
    tests: tuple[str, ...] = DEFAULT_TESTS
    runners: tuple[tuple[str, ...], ...] = tuple(tuple(token.split()) for token in RUNNERS)


def listed(text: str) -> tuple[str, ...]:
    return tuple(part.strip().strip("`") for part in text.split(",") if part.strip().strip("`"))


def row(text: str, label: str) -> tuple[str, ...]:
    found = re.search(r"^\s*\|\s*" + re.escape(label) + r"\s*\|([^|\n]*)\|", text, re.MULTILINE)
    values = listed(found.group(1)) if found else ()
    return tuple(value for value in values if not value.startswith("_"))


def head(words: list[str]) -> list[str]:
    words = list(words)
    while words:
        word = os.path.basename(words[0].lstrip("("))
        if ASSIGNMENT.match(words[0]):
            words = words[1:]
        elif word in WRAPPERS:
            words = words[1 + WRAPPERS[word]:]
        elif len(words) > 1 and (word, words[1]) in WRAPPER_PAIRS:
            words = words[2:]
            while words and words[0].startswith("-"):
                words = words[1:]
        elif word in INTERPRETERS and len(words) > 2 and words[1] == "-m":
            words = words[2:]
        elif word in INTERPRETERS and len(words) > 1 and not words[1].startswith("-"):
            words = words[1:]
        else:
            return [word] + words[1:]
    return []


def gate_runners(text: str) -> tuple[tuple[str, ...], ...]:
    found, level, fenced = [], 0, False
    for line in text.splitlines():
        heading = re.match(r"^(#+)\s", line) if not fenced else None
        if heading:
            level = len(heading.group(1)) if GATE_HEADING.match(line) else (level if level and len(heading.group(1)) > level else 0)
            continue
        if not level:
            continue
        if line.strip().startswith("```"):
            fenced = not fenced
            continue
        if fenced and line.strip() and not line.strip().startswith("#"):
            for words in segments(line):
                if words and words[0] not in NEUTRAL:
                    found.append((os.path.basename(words[0]),))
    return tuple(dict.fromkeys(found))


def load(root: str | os.PathLike, product: str = "", tests: str = "", runs: str = "") -> Rules:
    try:
        text = (pathlib.Path(root) / "docs" / "PROJECT.md").read_text(encoding="utf-8")
    except OSError:
        text = ""
    rules = Rules(root=os.path.realpath(root))
    rules.product = listed(product) or row(text, PRODUCT_LABEL)
    rules.tests = listed(tests) or row(text, TESTS_LABEL) or DEFAULT_TESTS
    extra = tuple(tuple(token.split()) for token in listed(runs))
    rules.runners = tuple(dict.fromkeys(rules.runners + gate_runners(text) + extra))
    return rules


def strip_heredocs(command: str) -> tuple[str, str]:
    kept, bodies, terminator = [], [], None
    for line in command.split("\n"):
        if terminator is not None:
            if line.strip() == terminator:
                terminator = None
            else:
                bodies.append(line)
            continue
        kept.append(line)
        opened = HEREDOC.search(line)
        if opened:
            terminator = opened.group(2)
    return "\n".join(kept), "\n".join(bodies)


def split_commands(text: str) -> list[str]:
    parts, current, quote, index = [], [], "", 0
    while index < len(text):
        char, pair = text[index], text[index: index + 2]
        if char == "\\" and quote != "'":
            current.append(pair)
            index += 2
            continue
        if quote:
            quote = "" if char == quote else quote
            current.append(char)
        elif char in "'\"":
            quote = char
            current.append(char)
        elif pair in ("&&", "||"):
            parts.append("".join(current))
            current = []
            index += 1
        elif char in ";|\n":
            parts.append("".join(current))
            current = []
        else:
            current.append(char)
        index += 1
    parts.append("".join(current))
    return parts


def segments(text: str) -> list[list[str]]:
    found = []
    for part in split_commands(text):
        part = part.strip().lstrip("({ ").strip()
        if not part:
            continue
        try:
            words = shlex.split(part, comments=False)
        except ValueError:
            words = part.split()
        words = head(words)
        if words:
            found.append(words)
    return found


def is_run(words: list[str], rules: Rules) -> bool:
    return any(tuple(words[: len(token)]) == token for token in rules.runners)


def relative(path: str, rules: Rules) -> str:
    if rules.root and os.path.isabs(path):
        inside = os.path.relpath(path, rules.root)
        return path if inside.startswith("..") else inside
    return path[2:] if path.startswith("./") else path


def matches(path: str, patterns: tuple[str, ...]) -> bool:
    name = os.path.basename(path)
    for pattern in patterns:
        if pattern.endswith("/"):
            if path.startswith(pattern) or ("/" + pattern) in ("/" + path):
                return True
        elif fnmatch.fnmatch(path, pattern) or fnmatch.fnmatch(name, pattern):
            return True
    return False


def throwaway(path: str) -> bool:
    return any(mark in path or path.startswith(mark.lstrip("/")) for mark in THROWAWAY) or path.endswith(THROWAWAY_ENDINGS)


def path_category(path: str, rules: Rules) -> str:
    path = relative(path, rules)
    if matches(path, RECORDS):
        return "records"
    if matches(path, rules.tests):
        return "test code"
    if rules.product and matches(path, rules.product):
        return "product code"
    if matches(path, DOCS):
        return "docs"
    if os.path.isabs(path) or rules.product:
        return "other"
    return "product code"


def written(text: str, bodies: str, rules: Rules) -> list[str]:
    paths = [target for target in REDIRECT.findall(text)]
    for words in segments(text):
        if words[0] == "sed" and any(word.startswith("-i") for word in words[1:]):
            paths.append(words[-1])
        if words[0] == "tee":
            paths.extend(word for word in words[1:] if not word.startswith("-"))
        if words[0] in INTERPRETERS and bodies:
            paths.extend(PATH_LITERAL.findall(bodies))
    return [path for path in paths if not throwaway(path) and not path.startswith("&")]


def bash_categories(command: str, rules: Rules) -> tuple[str, str]:
    text, bodies = strip_heredocs(command)
    parts = segments(text)
    run = any(is_run(words, rules) for words in parts)
    edits = written(text, bodies, rules)
    if edits:
        edited = path_category(edits[0], rules)
        return edited, ("runs" if run else edited)
    if run:
        return "runs", "runs"
    acting = [words for words in parts if words[0] not in NEUTRAL]
    if any(words[0] == "git" and not (len(words) > 1 and words[1] in GIT_READS) for words in acting):
        return "records", "records"
    if acting and all(words[0] in READERS or words[0] == "git" for words in acting):
        return "read-search", "read-search"
    return "other", "other"


def categories(name: str, arguments: dict, rules: Rules) -> tuple[str, str]:
    if name == "Bash":
        return bash_categories(str(arguments.get("command") or ""), rules)
    if name in EDIT_TOOLS:
        kind = path_category(str(arguments.get("file_path") or arguments.get("notebook_path") or ""), rules)
        return kind, kind
    if name in SEARCH_TOOLS:
        return "read-search", "read-search"
    if name in AGENT_TOOLS:
        return "agents", "agents"
    return "other", "other"
