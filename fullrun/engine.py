# engine.py
from __future__ import annotations

import argparse
import concurrent.futures
import datetime
import glob
import threading
import importlib
import math
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
STATE = pathlib.Path(".claude/scratch/fullrun")
CHILDREN: set[int] = set()
CHILDREN_LOCK = threading.Lock()


def kill_group(pgid: int) -> None:
    for sig in (signal.SIGTERM, signal.SIGKILL):
        try:
            os.killpg(pgid, sig)
        except (ProcessLookupError, PermissionError):
            return
        time.sleep(0.5)


def on_term(signum, frame) -> None:
    with CHILDREN_LOCK:
        groups = list(CHILDREN)
    for pgid in groups:
        kill_group(pgid)
    (STATE / "current").unlink(missing_ok=True)
    os._exit(143)


def stop_running() -> int:
    current = STATE / "current"
    if not current.is_file():
        print("no full run is running in this checkout")
        return 0
    pid, commit, stamp = (current.read_text().split() + ["?", "?"])[:3]
    try:
        os.kill(int(pid), signal.SIGTERM)
    except ProcessLookupError:
        current.unlink(missing_ok=True)
        print(f"full run {stamp} (pid {pid}) was already gone")
        return 0
    for _ in range(40):
        if not current.exists():
            break
        time.sleep(0.25)
    print(f"stopped full run {stamp} (pid {pid}, started at commit {commit}); restart it after the fix — the canary shard runs first")
    return 0


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
        with CHILDREN_LOCK:
            CHILDREN.add(proc.pid)
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
    with CHILDREN_LOCK:
        CHILDREN.discard(proc.pid)
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
    ap.add_argument("--stop", action="store_true", help="stop the full run running in this checkout, with its children")
    args = ap.parse_args()
    os.chdir(args.project)
    if args.stop:
        return stop_running()
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
    STATE.mkdir(parents=True, exist_ok=True)
    commit = subprocess.run(["git", "rev-parse", "--short=12", "HEAD"], capture_output=True, text=True).stdout.strip() or "none"
    (STATE / "current").write_text(f"{os.getpid()} {commit} {stamp}\n")
    signal.signal(signal.SIGTERM, on_term)

    commands = tier(text, "Full")
    if not commands:
        print(f"no full tier declared in {PROJECT} §6 (### Full tier)", file=sys.stderr)
        return 2

    started = time.monotonic()
    counts = {k: 0 for k in ("pass", "fail", "stale", "timeout", "empty", "dup", "skipped")}
    rows, findings, tsv_lines, censuses = [], [], [], []
    seq = iter(range(1, 1_000_000))
    lock = threading.Lock()

    def take_census(reports: list[str], attrs: dict[str, str], shards: int = 1, canary: bool = False) -> tuple[str | None, str]:
        list_ids = census.listed(attrs.get("list"), None)
        data = census.summarize(reports, list_ids, int(attrs.get("repeat", "1") or 1))
        line = (f"census {', '.join(reports)}: unique={data['unique']} executions={data['executions']} listed={data['listed']} "
                f"duplicates={data['duplicate_count']} overlap={data['overlap_count']} missing={data['missing_count']}")
        if data["empty"]:
            return "empty", line + " — no test executed"
        if data["duplicate_count"] or data["overlap_count"]:
            return "dup", line + f" — e.g. {list(data['duplicates'].items())[:3] or list(data['overlap'].items())[:3]}"
        if canary and data["listed"] and shards > 1 and data["executions"] > math.ceil(data["listed"] / shards) * 1.5:
            return "dup", line + f" — one shard ran {data['executions']} of {data['listed']} tests, more than its share of {shards}"
        if not canary and data["missing_count"]:
            return "dup", line + f" — {data['missing_count']} listed tests never ran, e.g. {data['missing'][:3]}"
        return None, line

    def execute(text: str, attrs: dict[str, str], report: str | None = None, shards: int = 1, canary: bool = False) -> tuple[str, int, int, pathlib.Path]:
        with lock:
            log = logs / f"{next(seq)}.log"
        if report:
            for old in glob.glob(report):
                pathlib.Path(old).unlink(missing_ok=True)
        budget = seconds(attrs.get("budget"))
        if budget is None and prev.get(text, ("", None))[0] == "pass" and prev[text][1]:
            budget = max(2 * prev[text][1], int(os.environ.get("FULLRUN_MIN_BUDGET", "60")))
        rc, secs, timed_out = run(text, log, budget)
        status = classify(rc, log, timed_out)
        if status == "pass" and attrs.get("expect"):
            check = subprocess.run(["bash", "-c", attrs["expect"]], capture_output=True, text=True, stdin=subprocess.DEVNULL)
            if check.returncode != 0:
                status = "empty"
                with lock:
                    findings.append(f"`{text}` exited 0 but its result is empty: `{attrs['expect']}` failed — the run proved nothing")
        if status == "pass" and report and (shards == 1 or canary):
            verdict, line = take_census([report], attrs, shards, canary)
            with lock:
                censuses.append(line)
            if verdict:
                status = verdict
                with lock:
                    findings.append(f"`{text}`: {line}")
        return status, rc, secs, log

    def record(text: str, status: str, rc: int | str, secs: int, log: pathlib.Path | str) -> None:
        counts[status] += 1
        tsv_lines.append(f"{status}\t{text}\t{secs}")
        rows.append(f"| {len(rows) + 1} | {status} | {rc} | {secs}s | `{text}` | {log} |")

    for c in commands:
        for key in c.unknown:
            findings.append(f"unknown attribute `{key}` on `{c.text}` (known: {', '.join(sorted(KEYS))})")
        shards = int(c.attrs.get("shards", "1") or 1)

        def expand(value: str, k: int) -> str:
            return value.replace("{shard}", str(k)).replace("{shards}", str(shards))

        texts = [expand(c.text, k) for k in range(1, shards + 1)]
        reports = [expand(c.attrs["report"], k) for k in range(1, shards + 1)] if c.attrs.get("report") else [None] * shards
        if not c.attrs.get("report") or not c.attrs.get("list"):
            findings.append(f"census SKIP for `{c.text}`: no report= (JUnit XML) or no list= — this run is not verifiable: nobody can tell whether every test ran once")
        if c.attrs.get("repeat") and not c.attrs.get("reason"):
            findings.append(f"`{c.text}` declares repeat={c.attrs['repeat']} without reason=")
        status, rc, secs, log = execute(texts[0], c.attrs, reports[0], shards, canary=True)
        record(texts[0], status, rc, secs, log)
        if shards == 1:
            continue
        if status != "pass":
            for t in texts[1:]:
                record(t, "skipped", "-", 0, "not started: the canary shard was " + status)
            findings.append(f"`{c.text}`: canary shard 1/{shards} was {status}; {shards - 1} shards not started — same cause")
            continue
        stop = threading.Event()
        signatures: dict[str, int] = {}

        def shard(job: tuple[str, str | None]) -> tuple[str, str, int | str, int, pathlib.Path | str]:
            text, report = job
            if stop.is_set():
                return text, "skipped", "-", 0, "not started: two shards already failed with the same cause"
            st, code, sec, lg = execute(text, c.attrs, report, shards)
            if st != "pass":
                sig = signature(lg) if isinstance(lg, pathlib.Path) else ""
                with lock:
                    signatures[sig] = signatures.get(sig, 0) + 1
                    if sig and signatures[sig] >= 2:
                        stop.set()
            return text, st, code, sec, lg

        workers = max(1, int(c.attrs.get("parallel", "1") or 1))
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
            results = list(pool.map(shard, list(zip(texts[1:], reports[1:]))))
        for text, st, code, sec, lg in results:
            record(text, st, code, sec, lg)
        if c.attrs.get("report") and all(r[1] == "pass" for r in results):
            verdict, line = take_census([r for r in reports if r], c.attrs, shards)
            censuses.append(line)
            if verdict:
                record(f"{c.text} [census of {shards} shards]", verdict, "-", 0, line)
                findings.append(f"`{c.text}`: {line}")
        if stop.is_set():
            sig = max(signatures, key=signatures.get)
            findings.append(f"`{c.text}`: two shards failed with the same cause ({sig!r}); the rest were not started")

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

    full_minutes = (time.monotonic() - started) / 60
    m = re.search(r"^\| Full tier budget[^|]*\|\s*([0-9.]+)", text, re.M)
    full_budget = float(m.group(1)) if m else None
    full_over_budget = int(bool(full_budget and full_minutes > full_budget))
    full_note = (f"full tier: {full_minutes:.1f} min against a budget of {full_budget:g} min" if full_budget
                 else f"full tier: {full_minutes:.1f} min (no budget declared in §6)")
    if full_over_budget:
        full_note += " — **over budget**; /test-audit is due"
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

    total = len(tsv_lines)
    summary = (
        f"fullrun: total={total} pass={counts['pass']} fail={counts['fail']} stale={counts['stale']} "
        f"new_red={new_red} still_red={still_red} fixed={fixed} fast_doubled={fast_doubled} "
        f"timeout={counts['timeout']} empty={counts['empty']} dup={counts['dup']} skipped={counts['skipped']} full_over_budget={full_over_budget}"
    )
    report = [f"# Full run {stamp}", "", summary, "", f"Compared with: {'the previous run' if prev else 'nothing (first run)'}", "",
              "| # | status | exit | time | command | log |", "|---|---|---|---|---|---|", *rows, "",
              "## Changes since the previous run", *(compare or ["- none"]), "", "## Time", full_note, fast_note]
    if counts["stale"]:
        report += ["", "## Stale declarations",
                   "A command in §6 no longer exists or points at a missing path: the declaration in docs/PROJECT.md is out of date, not a test failure. Fix §6 (/intake refresh)."]
    if censuses:
        report += ["", "## Census", *[f"- {line}" for line in censuses]]
    if findings:
        report += ["", "## Findings", *[f"- {f}" for f in findings]]
    md.write_text("\n".join(report) + "\n")
    (STATE / "current").unlink(missing_ok=True)
    print(summary)
    print(f"report: {md}")
    return 0 if all(counts[k] == 0 for k in RED) else 1


if __name__ == "__main__":
    sys.exit(main())
