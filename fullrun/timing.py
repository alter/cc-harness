# timing.py
from __future__ import annotations

import argparse
import glob
import importlib
import json
import pathlib
import sys
import xml.etree.ElementTree as ET

sys.dont_write_bytecode = True
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
census = importlib.import_module("census")


def durations(report_glob: str) -> dict[str, float]:
    times: dict[str, float] = {}
    for path in sorted(glob.glob(report_glob, recursive=True)):
        try:
            root = ET.parse(path).getroot()
        except ET.ParseError:
            continue
        for case in root.iter("testcase"):
            classname = case.get("classname") or case.get("file") or ""
            test = census.norm(f"{classname}::{case.get('name') or ''}" if classname else case.get("name") or "")
            times[test] = times.get(test, 0.0) + float(case.get("time") or 0)
    return times


def slowest(report_glob: str, top: int) -> dict:
    times = durations(report_glob)
    total = sum(times.values())
    ranked = sorted(times.items(), key=lambda kv: -kv[1])
    head = ranked[:top]
    return {
        "tests": len(times),
        "total_seconds": round(total, 2),
        "slowest": [{"test": t, "seconds": round(sec, 2)} for t, sec in head],
        "top_share": round(sum(sec for _, sec in head) / total, 3) if total else 0.0,
    }


def flaky(directory: str, runs: int) -> dict:
    files = sorted(pathlib.Path(directory).glob("FULLRUN-*.tests.json"))[-runs:]
    seen: dict[str, set[str]] = {}
    for f in files:
        for test, outcome in json.loads(f.read_text(encoding="utf-8")).items():
            seen.setdefault(test, set()).add(outcome)
    flips = {t: sorted(o) for t, o in sorted(seen.items()) if {"pass", "fail"} <= o}
    return {"runs": [f.name for f in files], "flaky": flips}


def main() -> int:
    ap = argparse.ArgumentParser(description="Where test time goes, and which tests flip between runs.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("slowest")
    a.add_argument("--report", required=True)
    a.add_argument("--top", type=int, default=20)
    a.add_argument("--json")
    b = sub.add_parser("flaky")
    b.add_argument("--dir", required=True)
    b.add_argument("--runs", type=int, default=10)
    b.add_argument("--json")
    args = ap.parse_args()
    data = slowest(args.report, args.top) if args.cmd == "slowest" else flaky(args.dir, args.runs)
    if args.json:
        pathlib.Path(args.json).write_text(json.dumps(data, indent=2), encoding="utf-8")
    print(json.dumps(data, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
