# project_check.py
import re
import sys
from pathlib import Path

STATES = {"included", "available", "absent", "removed"}


def main() -> int:
    path = Path("docs/PROJECT.md")
    if not path.exists():
        print("docs/PROJECT.md missing; run /intake")
        return 1
    text = path.read_text(encoding="utf-8")
    problems: list[str] = []

    intake = re.search(r"^intake:\s*(.+)$", text, re.M)
    if not intake:
        problems.append("frontmatter lacks 'intake:'")
    completed = bool(intake and intake.group(1).strip().startswith("completed"))

    ledger = text.split("## 3. Capability ledger", 1)
    if len(ledger) < 2:
        problems.append("section '3. Capability ledger' missing")
    else:
        body = ledger[1].split("\n## ", 1)[0]
        for line in body.splitlines():
            if not line.startswith("|") or "---" in line or line.startswith("| Capability"):
                continue
            cells = [c.strip() for c in line.strip("|").split("|")]
            if len(cells) < 2:
                continue
            if cells[1] not in STATES:
                problems.append(f"ledger row '{cells[0]}' has state '{cells[1]}' (allowed: {sorted(STATES)})")

    if completed:
        open_cells = [m.start() for m in re.finditer(r"_unanswered_", text)]
        if open_cells:
            lines = sorted({text.count("\n", 0, i) + 1 for i in open_cells})
            problems.append(f"intake completed but {len(lines)} '_unanswered_' cell(s) remain at lines {lines[:12]}")

    for heading in ("## 5. Unattended policy", "## 6. Gate checks"):
        if heading not in text:
            problems.append(f"section '{heading[3:]}' missing")

    if problems:
        print("\n".join(problems))
        return 1
    print(f"PROJECT.md ok (intake: {intake.group(1).strip() if intake else '?'})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
