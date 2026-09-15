# check.py
from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else pathlib.Path(__file__).resolve().parent
REPO = ROOT.parent
SECTIONS = ["TASK:", "GOAL", "CONTEXT", "SCOPE", "OUTCOME", "VERIFY", "ROLE", "DEPENDS"]
LABELS = {"phase", "role", "type", "priority", "status", "verify", "depends", "milestone", "gate"}
PHASES: set[str] = set()
ROLES: set[str] = {"HUMAN"}
TYPES = {"feature", "fix", "research", "decision", "chore"}
PRIORITIES = {"P0", "P1", "P2", "P3"}
MILESTONES: dict[str, int] = {}
STATUSES = {"todo", "in_progress", "review", "done", "blocked"}
VERIFIES = {"pending", "passed", "failed"}
GATES_EXPECTED: int | None = None
VERIFY_REQUIRED = (("Проверил:", "Verifier:"), ("## Как воспроизвести", "## How to reproduce"), ("## Что не проверено", "## What was not checked"))
BLOCKED_REQUIRED = (("Заблокировано:", "Blocked:"), ("Чего не хватает:", "Missing:"), ("Что сделано до остановки:", "Done before stopping:"))
LINE_REF = re.compile(r"(?<![\w/.-])([A-Za-z0-9_./-]+\.[A-Za-z0-9]{1,6}):(\d+)(?:-(\d+))?")


def read_labels(path: pathlib.Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        if ":" not in line:
            raise ValueError(f"строка без двоеточия: {line!r}")
        key, value = line.split(":", 1)
        out[key.strip()] = value.strip()
    return out


def load_vocab() -> None:
    global GATES_EXPECTED
    readme = ROOT / "README.md"
    if readme.exists():
        text = readme.read_text(encoding="utf-8")
        block = re.search(r"^phase:\s+(.+?)(?=^\w+:|^```)", text, re.M | re.S)
        if block:
            PHASES.update(w for w in re.split(r"[|\s]+", block.group(1)) if re.fullmatch(r"[a-z][a-z0-9-]*", w))
    roles = ROOT / "ROLES.md"
    if roles.exists():
        for m in re.finditer(r"^\| \*\*([A-Z]+)\*\*", roles.read_text(encoding="utf-8"), re.M):
            ROLES.add(m.group(1))
    goal = ROOT / "GOAL.md"
    if goal.exists():
        text = goal.read_text(encoding="utf-8")
        for m in re.finditer(r"\*\*(M\d+)\b", text):
            MILESTONES.setdefault(m.group(1), int(m.group(1)[1:]))
        gates = len(re.findall(r"^\*\*Ворота \d+|^\*\*Gate \d+", text, re.M))
        GATES_EXPECTED = gates or None
    if not PHASES:
        for d in ROOT.iterdir():
            if d.is_dir() and re.match(r"^\d{2}-", d.name):
                PHASES.add(d.name.split("-", 1)[1])


def check_line_refs(rel: str, body: str, problems: list[str]) -> None:
    for m in LINE_REF.finditer(body):
        path, start = m.group(1), int(m.group(2))
        candidates = [REPO / path] + list(REPO.glob(f"**/{path}")) if "/" not in path else [REPO / path]
        target = next((c for c in candidates if c.is_file()), None)
        if target is None:
            continue
        try:
            total = sum(1 for _ in target.open(encoding="utf-8", errors="ignore"))
        except OSError:
            continue
        if start > total:
            problems.append(f"{rel}: ссылка {path}:{start} за пределами файла ({total} строк)")


def main() -> int:
    load_vocab()
    problems: list[str] = []
    tasks: dict[str, dict[str, str]] = {}
    gates: list[str] = []

    for task_txt in sorted(ROOT.rglob("task.txt")):
        d = task_txt.parent
        rel = str(d.relative_to(ROOT))
        body = task_txt.read_text(encoding="utf-8")

        positions = []
        for s in SECTIONS:
            m = re.search(rf"^{re.escape(s)}", body, re.M)
            if not m:
                problems.append(f"{rel}: нет раздела {s}")
            else:
                positions.append(m.start())
        if positions != sorted(positions):
            problems.append(f"{rel}: разделы не в порядке README")
        if "−" not in body:
            problems.append(f"{rel}: в SCOPE нет строк «−» (граница не записана)")
        check_line_refs(rel, body, problems)

        labels_path = d / "labels.txt"
        if not labels_path.exists():
            problems.append(f"{rel}: нет labels.txt")
            continue
        try:
            kv = read_labels(labels_path)
        except ValueError as exc:
            problems.append(f"{rel}: labels.txt — {exc}")
            continue
        tasks[rel] = kv

        for k in kv:
            if k not in LABELS:
                problems.append(f"{rel}: неизвестная метка {k}")
        for k in ("phase", "role", "type", "priority", "status", "verify", "milestone"):
            if k not in kv:
                problems.append(f"{rel}: нет метки {k}")
        if PHASES and kv.get("phase") not in PHASES:
            problems.append(f"{rel}: phase={kv.get('phase')}")
        for role in re.split(r"[,\s]+", kv.get("role", "")):
            if role and role not in ROLES:
                problems.append(f"{rel}: role={role}")
        if kv.get("type") not in TYPES:
            problems.append(f"{rel}: type={kv.get('type')}")
        if kv.get("priority") not in PRIORITIES:
            problems.append(f"{rel}: priority={kv.get('priority')}")
        if MILESTONES and kv.get("milestone") not in MILESTONES:
            problems.append(f"{rel}: milestone={kv.get('milestone')}")
        if kv.get("status") not in STATUSES:
            problems.append(f"{rel}: status={kv.get('status')}")
        if kv.get("verify") not in VERIFIES:
            problems.append(f"{rel}: verify={kv.get('verify')}")
        if kv.get("gate") == "yes":
            gates.append(rel)

        dep = kv.get("depends")
        if dep and not (ROOT / dep).is_dir():
            problems.append(f"{rel}: depends указывает в никуда: {dep}")
        m = re.search(r"(?ms)^DEPENDS\n\s+(.+?)\s*$", body)
        txt = m.group(1).strip() if m else ""
        if dep and dep not in txt:
            problems.append(f"{rel}: DEPENDS в тексте «{txt}» не содержит метку «{dep}»")

        if kv.get("status") == "blocked":
            bp = d / "BLOCKED.md"
            if not bp.exists():
                problems.append(f"{rel}: status:blocked без BLOCKED.md")
            else:
                b = bp.read_text(encoding="utf-8")
                for need in BLOCKED_REQUIRED:
                    if not any(n in b for n in need):
                        problems.append(f"{rel}: BLOCKED.md без «{need[0]}»")
        if kv.get("verify") == "passed":
            vp = d / "VERIFY.md"
            if not vp.exists():
                problems.append(f"{rel}: verify:passed без VERIFY.md")
            else:
                v = vp.read_text(encoding="utf-8")
                for need in VERIFY_REQUIRED:
                    if not any(n in v for n in need):
                        problems.append(f"{rel}: VERIFY.md без «{need[0]}»")
        if kv.get("status") == "done" and kv.get("gate") == "yes" and kv.get("verify") != "passed":
            problems.append(f"{rel}: ворота закрыты без verify:passed")
        plan = d / "PLAN.md"
        if plan.exists() and kv.get("status") in {"done", "blocked"}:
            head = plan.read_text(encoding="utf-8")[:400]
            if "status: running" in head:
                problems.append(f"{rel}: PLAN.md всё ещё running при status:{kv.get('status')}")

    for rel, kv in tasks.items():
        dep = kv.get("depends")
        if dep and dep in tasks and MILESTONES:
            mine = MILESTONES.get(kv.get("milestone", ""), 0)
            theirs = MILESTONES.get(tasks[dep].get("milestone", ""), 0)
            if theirs > mine:
                problems.append(
                    f"{rel} ({kv.get('milestone')}) зависит от {dep} "
                    f"({tasks[dep].get('milestone')}) — более поздняя веха"
                )

    if tasks and GATES_EXPECTED is not None and len(gates) != GATES_EXPECTED:
        problems.append(f"ворот {len(gates)}, ожидается {GATES_EXPECTED}: {gates}")

    print(f"каталогов задач: {len(tasks)}; ворота: {gates}")
    if problems:
        print(f"проблем: {len(problems)}")
        for p in problems:
            print("  •", p)
        return 1
    print("проблем: 0")
    return 0


if __name__ == "__main__":
    sys.exit(main())
