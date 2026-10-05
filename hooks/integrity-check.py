# integrity-check.py
from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import subprocess
import sys

try:
    import tomllib
except ModuleNotFoundError:
    tomllib = None

MARKERS = [
    r"#\s*noqa", r"#\s*type:\s*ignore", r"#\s*pragma:\s*no cover", r"pylint:\s*disable", r"pytest\.mark\.(skip|xfail)",
    r"@unittest\.skip", r"eslint-disable", r"@ts-(ignore|expect-error|nocheck)", r"\b(it|describe|test)\.(skip|only)\(",
    r"\bx(it|describe)\(", r"//\s*nolint", r"\bt\.Skip(Now)?\(", r"#\[allow\(", r"#\[ignore\]", r"shellcheck\s+disable",
    r"\|\|\s*true\b", r"^\s*set\s+\+e\b", r"ignore_errors:\s*(yes|true)", r"failed_when:\s*(false|no)\b", r"tflint-ignore",
    r"checkov:skip", r"tfsec:ignore", r"@SuppressWarnings", r"@Disabled\b", r"@Ignore\b", r"#pragma\s+warning\s+disable",
    r"rubocop:disable", r"\bnosec\b", r"NOLINT",
]
CONFIG_NAMES = re.compile(
    r"^(\.eslintrc.*|eslint\.config\..*|\.prettierrc.*|prettier\.config\..*|biome\.jsonc?|\.?ruff\.toml|setup\.cfg|tox\.ini|"
    r"\.?mypy\.ini|pytest\.ini|\.flake8|\.?pylintrc|\.golangci\.ya?ml|\.?clippy\.toml|\.?rustfmt\.toml|\.shellcheckrc|"
    r"\.yamllint.*|\.markdownlint.*|tsconfig.*\.json|jest\.config\..*|vitest\.config\..*|phpunit\.xml.*|\.rubocop\.yml|"
    r"\.coveragerc|\.tflint\.hcl|\.ansible-lint|\.pre-commit-config\.ya?ml|codecov\.ya?ml|\.stylelintrc.*|\.editorconfig)$"
)
PYPROJECT_TOOLS = ("ruff", "mypy", "pytest", "coverage", "pylint", "flake8", "black", "isort", "pyright")
PACKAGE_KEYS = ("eslintConfig", "jest", "prettier", "stylelint")
TEST_PATH = re.compile(r"(^|/)(tests?|__tests__|spec)/|(^|/)test_[^/]+$|_test\.[a-z]+$|\.(test|spec)\.[a-z]+$")


def git(*args: str) -> str:
    return subprocess.run(["git", *args], capture_output=True, text=True).stdout


def old_text(base: str, path: str) -> str:
    return git("show", f"{base}:{path}")


def new_text(path: str) -> str:
    p = pathlib.Path(path)
    return p.read_text(encoding="utf-8", errors="ignore") if p.is_file() else ""


def project_markers() -> list[str]:
    p = pathlib.Path("docs/PROJECT.md")
    if not p.is_file():
        return []
    m = re.search(r"```suppress\n(.*?)```", p.read_text(encoding="utf-8", errors="ignore"), re.S)
    return [re.escape(x.strip()) for x in m.group(1).splitlines() if x.strip()] if m else []


def toml_tools(text: str) -> dict:
    if not tomllib or not text:
        return {}
    try:
        tool = tomllib.loads(text).get("tool", {})
    except Exception:
        return {"unparsed": text}
    return {k: tool.get(k) for k in PYPROJECT_TOOLS}


def package_keys(text: str) -> dict:
    try:
        data = json.loads(text) if text else {}
    except Exception:
        return {"unparsed": text}
    return {k: data.get(k) for k in PACKAGE_KEYS}


def floor(text: str) -> float | None:
    try:
        return float(json.loads(text)["floor"])
    except Exception:
        return None


def findings(base: str) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    markers = [re.compile(m, re.M) for m in MARKERS + project_markers()]
    status = git("diff", "--name-status", base).splitlines() + [
        f"A\t{p}" for p in git("ls-files", "--others", "--exclude-standard").splitlines()
    ]
    changed_paths = {line.split("\t")[-1] for line in status if "\t" in line}
    for line in status:
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        code, path = parts[0][0], parts[-1]
        name = pathlib.PurePosixPath(path).name
        if code == "D":
            if TEST_PATH.search(path):
                out.append((path, "a test file was deleted"))
            continue
        before, after = (old_text(base, path) if code != "A" else ""), new_text(path)
        if name == ".coverage-gate.json":
            fb, fa = floor(before), floor(after)
            if fb is not None and fa is not None and fa < fb:
                out.append((path, f"the coverage floor was lowered {fb} -> {fa}"))
            continue
        if code == "A" and (CONFIG_NAMES.match(name) or path.startswith(".github/workflows/")) and "docs/PROJECT.md" not in changed_paths:
            out.append((path, "a new check or CI configuration appeared without a change to docs/PROJECT.md §6 — declare how it runs"))
            continue
        if CONFIG_NAMES.match(name) and code != "A":
            out.append((path, "a linter, type or test configuration was changed"))
            continue
        if name == "pyproject.toml" and toml_tools(before) != toml_tools(after):
            out.append((path, "a [tool.*] lint/test/type section of pyproject.toml was changed"))
        if name == "package.json" and package_keys(before) != package_keys(after):
            out.append((path, "lint/test configuration inside package.json was changed"))
        for rx in markers:
            if len(list(rx.finditer(after))) > len(list(rx.finditer(before))):
                out.append((path, f"a suppression was added ({rx.pattern})"))
    return out


def declared(plan: str | None) -> str:
    if not plan or not pathlib.Path(plan).is_file():
        return ""
    text = pathlib.Path(plan).read_text(encoding="utf-8", errors="ignore")
    keep = []
    for head in ("## Decisions", "## Assumptions"):
        if head in text:
            keep.append(text.split(head, 1)[1].split("\n## ", 1)[0])
    return "\n".join(keep)


def main() -> int:
    if "integrity-check" in os.environ.get("CC_DISABLED_HOOKS", "").split(","):
        return 0
    ap = argparse.ArgumentParser(description="Changes that make checks pass without fixing code: suppressions, weakened configs, deleted tests, a lowered coverage floor.")
    ap.add_argument("--base", required=True, help="commit the run started from")
    ap.add_argument("--plan", help="plan file; a path named under its Decisions or Assumptions is a declared change")
    args = ap.parse_args()
    open_items = []
    accepted = declared(args.plan)
    for path, why in findings(args.base):
        if path in accepted:
            continue
        open_items.append(f"{path}: {why}")
    print(f"integrity: {len(open_items)} finding(s) since {args.base[:12]}")
    for item in open_items:
        print(f"  • {item}")
    if open_items:
        print("Each is either undone, or declared under the plan's ## Assumptions with the path and the reason, where the owner and the verifier will read it.")
    return 1 if open_items else 0


if __name__ == "__main__":
    sys.exit(main())
