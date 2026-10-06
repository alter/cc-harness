# engine.py
from __future__ import annotations

import argparse
import datetime
import importlib
import os
import pathlib
import re
import shlex
import signal
import subprocess
import sys
import time

sys.dont_write_bytecode = True
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
census = importlib.import_module("census")

KEYS = {"budget", "expect", "report", "list", "shards", "parallel", "repeat", "reason"}
RED = ("fail", "stale", "timeout", "empty", "dup")
PROJECT = pathlib.Path("docs/PROJECT.md")


class Command:
    def __init__(self, text: str, attrs: dict[str, str], unknown: list[str]):
        self.text = text
        self.attrs = attrs
        self.unknown = unknown


def tier(text: str, name: str) -> list[Command]:
    section = text.split("## 6.", 1)[1].split("\n## ", 1)[0] if "## 6." in text else ""
    head = f"### {name} tier"
    if head not in section:
        return []
    body = section.split(head, 1)[1]
    m = re.search(r"```[^\n]*\n(.*?)```", body, re.S)
    if not m:
        return []
    out, attrs, unknown = [], {}, []
    for line in m.group(1).splitlines():
        s = line.strip()
        if not s or s == "_unanswered_":
            continue
        if s.startswith("#:"):
            for tok in shlex.split(s[2:]):
                key, eq, value = tok.partition("=")
                if not eq:
                    continue
                if key in KEYS:
                    attrs[key] = value
                else:
                    unknown.append(key)
            continue
        if s.startswith("#"):
            continue
        out.append(Command(s, attrs, unknown))
        attrs, unknown = {}, []
    return out


def seconds(value: str | None) -> int | None:
    if not value:
        return None
    m = re.fullmatch(r"(\d+)\s*([smh]?)", value.strip())
    if not m:
        return None
    return int(m.group(1)) * {"": 1, "s": 1, "m": 60, "h": 3600}[m.group(2)]


def run(cmd: str, log: pathlib.Path, budget: int | None) -> tuple[int, int, bool]:
    t0 = time.monotonic()
    with log.open("w") as fh:
        proc = subprocess.Popen(["bash", "-c", cmd], stdout=fh, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, start_new_session=True)
        pidfile = pathlib.Path(os.environ.get("FULLRUN_STATE", ".")) / "child.pid"
        try:
            pidfile.write_text(str(proc.pid))
        except OSError:
            pass
        try:
            rc = proc.wait(timeout=budget)
            timed_out = False
        except subprocess.TimeoutExpired:
            timed_out = True
            try:
                os.killpg(proc.pid, signal.SIGTERM)
                proc.wait(timeout=5)
            except (ProcessLookupError, subprocess.TimeoutExpired):
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                proc.wait()
            rc = -1
    return rc, int(round(time.monotonic() - t0)), timed_out


def classify(rc: int, log: pathlib.Path, timed_out: bool) -> str:
    if timed_out:
        return "timeout"
    if rc == 0:
        return "pass"
    text = log.read_text(errors="ignore")
    if rc in (126, 127) or (re.search(r"No such file or directory|command not found", text) and text.count("\n") <= 3):
        return "stale"
    return "fail"


def signature(log: pathlib.Path) -> str:
    for line in log.read_text(errors="ignore").splitlines():
        if re.search(r"error|fail|exception|traceback|panic|fatal", line, re.I):
            return re.sub(r"\d+", "N", line.strip())[:160]
    return ""


def previous(out: pathlib.Path, current: pathlib.Path) -> dict[str, tuple[str, int | None]]:
    runs = sorted(p for p in out.glob("FULLRUN-*.tsv") if p != current)
    if not runs:
        return {}
    data = {}
    for line in runs[-1].read_text().splitlines():
        parts = line.split("\t")
        if len(parts) >= 2:
            data[parts[1]] = (parts[0], int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else None)
    return data


def main() -> int:
    ap = argparse.ArgumentParser(description="Run the full tier of docs/PROJECT.md §6 to the end and report it.")
    ap.add_argument("--project", default=".")
    ap.add_argument("--out")
    args = ap.parse_args()
    os.chdir(args.project)
    if not PROJECT.is_file():
        print(f"no {PROJECT} in {os.getcwd()}: run /intake first", file=sys.stderr)
        return 2
    text = PROJECT.read_text(encoding="utf-8")
    out = pathlib.Path(args.out) if args.out else pathlib.Path(".claude/reports")
    out.mkdir(parents=True, exist_ok=True)
    stamp = datetime.datetime.now().strftime("%Y-%m-%d-%H%M%S")
    n = 0
    while (out / f"FULLRUN-{stamp}.md").exists() or (out / f"FULLRUN-{stamp}.tsv").exists():
        n += 1
        stamp = datetime.datetime.now().strftime("%Y-%m-%d-%H%M%S") + f"-{n}"
    logs = pathlib.Path(".claude/scratch/fullrun") / stamp
    logs.mkdir(parents=True, exist_ok=True)
    tsv, md = out / f"FULLRUN-{stamp}.tsv", out / f"FULLRUN-{stamp}.md"
    tsv.write_text("")
    prev = previous(out, tsv)

    commands = tier(text, "Full")
    if not commands:
        print(f"no full tier declared in {PROJECT} §6 (### Full tier)", file=sys.stderr)
        return 2

    counts = {k: 0 for k in ("pass", "fail", "stale", "timeout", "empty", "dup", "skipped")}
    rows, findings, tsv_lines = [], [], []
    i = 0
    for c in commands:
        for key in c.unknown:
            findings.append(f"unknown attribute `{key}` on `{c.text}` (known: {', '.join(sorted(KEYS))})")
        i += 1
        log = logs / f"{i}.log"
        budget = seconds(c.attrs.get("budget"))
        if budget is None and prev.get(c.text, ("", None))[0] == "pass" and prev[c.text][1]:
            budget = max(2 * prev[c.text][1], int(os.environ.get("FULLRUN_MIN_BUDGET", "60")))
        rc, secs, timed_out = run(c.text, log, budget)
        status = classify(rc, log, timed_out)
        if status == "pass" and c.attrs.get("expect"):
            check = subprocess.run(["bash", "-c", c.attrs["expect"]], capture_output=True, text=True, stdin=subprocess.DEVNULL)
            if check.returncode != 0:
                status = "empty"
                findings.append(f"`{c.text}` exited 0 but its result is empty: `{c.attrs['expect']}` failed — the run proved nothing")
        counts[status] += 1
        tsv_lines.append(f"{status}\t{c.text}\t{secs}")
        rows.append(f"| {i} | {status} | {rc} | {secs}s | `{c.text}` | {log} |")

    tsv.write_text("".join(line + "\n" for line in tsv_lines))

    new_red = still_red = fixed = 0
    compare = []
    for line in tsv_lines:
        status, cmd, _ = line.split("\t")
        before = prev.get(cmd, ("", None))[0]
        if status in RED and before in RED:
            still_red += 1
            compare.append(f"- still red: `{cmd}`")
        elif status in RED:
            new_red += 1
            compare.append(f"- **new red**: `{cmd}`")
        elif status == "pass" and before in RED:
            fixed += 1
            compare.append(f"- fixed: `{cmd}`")

    fast_note, fast_doubled = "fast tier: not declared", 0
    fast = tier(text, "Fast")
    if fast:
        t0 = time.monotonic()
        for c in fast:
            run(c.text, logs / "fast.log", None)
        fast_secs = int(round(time.monotonic() - t0))
        m = re.search(r"^\| Fast tier wall time[^|]*\|\s*(\d+)", text, re.M)
        base = int(m.group(1)) if m else None
        if base and fast_secs > 2 * base:
            fast_doubled = 1
            fast_note = f"fast tier: {fast_secs}s against {base}s at T00 — **more than doubled**; move slow tests to the full tier (finding, does not block)"
        elif base:
            fast_note = f"fast tier: {fast_secs}s against {base}s at T00"
        else:
            fast_note = f"fast tier: {fast_secs}s (no T00 time recorded in §6)"

    total = len(commands)
    summary = (
        f"fullrun: total={total} pass={counts['pass']} fail={counts['fail']} stale={counts['stale']} "
        f"new_red={new_red} still_red={still_red} fixed={fixed} fast_doubled={fast_doubled} "
        f"timeout={counts['timeout']} empty={counts['empty']} dup={counts['dup']} skipped={counts['skipped']}"
    )
    report = [f"# Full run {stamp}", "", summary, "", f"Compared with: {'the previous run' if prev else 'nothing (first run)'}", "",
              "| # | status | exit | time | command | log |", "|---|---|---|---|---|---|", *rows, "",
              "## Changes since the previous run", *(compare or ["- none"]), "", "## Fast tier", fast_note]
    if counts["stale"]:
        report += ["", "## Stale declarations",
                   "A command in §6 no longer exists or points at a missing path: the declaration in docs/PROJECT.md is out of date, not a test failure. Fix §6 (/intake refresh)."]
    if findings:
        report += ["", "## Findings", *[f"- {f}" for f in findings]]
    md.write_text("\n".join(report) + "\n")
    print(summary)
    print(f"report: {md}")
    return 0 if all(counts[k] == 0 for k in RED) else 1


if __name__ == "__main__":
    sys.exit(main())
