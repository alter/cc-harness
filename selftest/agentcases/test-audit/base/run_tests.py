# run_tests.py
import argparse
import sys
import time
import unittest
import xml.etree.ElementTree as ET

sys.path.insert(0, "src")


def cases(suite):
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from cases(item)
        else:
            yield item


ap = argparse.ArgumentParser()
ap.add_argument("--list", action="store_true")
ap.add_argument("--junit")
ap.add_argument("--reverse", action="store_true")
args = ap.parse_args()
tests = list(cases(unittest.defaultTestLoader.discover("tests", top_level_dir=".")))
if args.list:
    for t in tests:
        print(f"{type(t).__module__}.{type(t).__name__}::{t._testMethodName}")
    sys.exit(0)
if args.reverse:
    tests.reverse()
root = ET.Element("testsuite")
failed = 0
for t in tests:
    result = unittest.TestResult()
    t0 = time.monotonic()
    t.run(result)
    case = ET.SubElement(root, "testcase", classname=f"{type(t).__module__}.{type(t).__name__}", name=t._testMethodName, time=f"{time.monotonic() - t0:.3f}")
    if result.failures or result.errors:
        failed += 1
        ET.SubElement(case, "failure", message=str((result.failures or result.errors)[0][1])[-200:])
if args.junit:
    ET.ElementTree(root).write(args.junit)
print(f"{len(tests)} tests, {failed} failed")
sys.exit(1 if failed else 0)
