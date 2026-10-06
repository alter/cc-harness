# census.py
from __future__ import annotations

import argparse
import collections
import glob
import json
import re
import subprocess
import sys
import xml.etree.ElementTree as ET

EXT = re.compile(r"\.(py|go|rs|ts|tsx|js|jsx|java|kt|rb|php|cs|ex|exs)$")


def norm(test_id: str) -> str:
    parts = re.split(r"::|#", test_id.strip().lstrip("./"))
    parts[0] = EXT.sub("", parts[0])
    return ".".join(p.replace("/", ".").replace(" ", ".") for p in parts if p)


def last(test_id: str) -> str:
    base = re.sub(r"\[.*\]$", "", test_id)
    return base.rsplit(".", 1)[-1]


def executed(report_glob: str) -> list[str]:
    ids = []
    for path in sorted(glob.glob(report_glob, recursive=True)):
        try:
            root = ET.parse(path).getroot()
        except ET.ParseError:
            continue
        for case in root.iter("testcase"):
            if case.find("skipped") is not None:
                continue
            classname = case.get("classname") or case.get("file") or ""
            name = case.get("name") or ""
            ids.append(norm(f"{classname}::{name}" if classname else name))
    return ids


def listed(list_cmd: str | None, list_file: str | None) -> list[str] | None:
    if list_file:
        text = open(list_file, encoding="utf-8").read()
    elif list_cmd:
        text = subprocess.run(["bash", "-c", list_cmd], capture_output=True, text=True, stdin=subprocess.DEVNULL).stdout
    else:
        return None
    return [norm(line) for line in text.splitlines() if line.strip() and not re.search(r"\s", line.strip())]


def matches(listed_id: str, run_ids: set[str], by_last: dict[str, list[str]]) -> bool:
    if listed_id in run_ids:
        return True
    for candidate in by_last.get(last(listed_id), ()):
        if candidate.endswith("." + listed_id) or listed_id.endswith("." + candidate):
            return True
    return False


def summarize(reports: list[str], list_ids: list[str] | None, repeat: int) -> dict:
    per_report = [executed(r) for r in reports]
    all_runs = [t for ids in per_report for t in ids]
    counts = collections.Counter(all_runs)
    owners: dict[str, set[int]] = collections.defaultdict(set)
    for i, ids in enumerate(per_report):
        for t in ids:
            owners[t].add(i)
    duplicates = {t: n for t, n in counts.items() if n > repeat and len(owners[t]) == 1}
    overlap = {t: sorted(i + 1 for i in o) for t, o in owners.items() if len(o) > 1}
    missing: list[str] = []
    if list_ids is not None:
        run_ids = set(counts)
        by_last: dict[str, list[str]] = collections.defaultdict(list)
        for t in run_ids:
            by_last[last(t)].append(t)
        missing = sorted(t for t in set(list_ids) if not matches(t, run_ids, by_last))
    data = {
        "reports": reports,
        "listed": len(set(list_ids)) if list_ids is not None else None,
        "unique": len(counts),
        "executions": len(all_runs),
        "repeat": repeat,
        "duplicates": dict(sorted(duplicates.items(), key=lambda kv: -kv[1])[:50]),
        "duplicate_count": len(duplicates),
        "overlap": dict(list(sorted(overlap.items()))[:50]),
        "overlap_count": len(overlap),
        "missing": missing[:200],
        "missing_count": len(missing),
        "empty": len(all_runs) == 0,
    }
    data["red"] = bool(data["empty"] or duplicates or overlap or missing)
    return data


def main() -> int:
    ap = argparse.ArgumentParser(description="Did every test run exactly once? JUnit XML reports against the list of tests.")
    ap.add_argument("--report", action="append", required=True, help="JUnit XML glob; repeat once per shard")
    ap.add_argument("--list-cmd", help="command that lists the tests without running them")
    ap.add_argument("--list-file")
    ap.add_argument("--repeat", type=int, default=1, help="declared executions per test (default 1)")
    ap.add_argument("--json", help="write the summary here")
    args = ap.parse_args()
    data = summarize(args.report, listed(args.list_cmd, args.list_file), args.repeat)
    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2)
    print(
        f"census: unique={data['unique']} executions={data['executions']} listed={data['listed']} "
        f"duplicates={data['duplicate_count']} overlap={data['overlap_count']} missing={data['missing_count']} empty={int(data['empty'])}"
    )
    return 1 if data["red"] else 0


if __name__ == "__main__":
    sys.exit(main())
