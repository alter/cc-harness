# test_fullrun.py
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = pathlib.Path(__file__).resolve().parent
ENGINE_DIR = pathlib.Path(os.environ.get("FULLRUN_DIR", HERE.parent / "fullrun"))
CENSUS = ENGINE_DIR / "census.py"


def junit(cases):
    body = "".join(f'<testcase classname="{c}" name="{n}" time="0.1"/>' for c, n in cases)
    return f'<?xml version="1.0"?><testsuites><testsuite name="s" tests="{len(cases)}">{body}</testsuite></testsuites>'


class Census(unittest.TestCase):
    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def write(self, name, text):
        p = self.tmp / name
        p.write_text(text, encoding="utf-8")
        return p

    def census(self, *args):
        r = subprocess.run([sys.executable, str(CENSUS), *args, "--json", str(self.tmp / "out.json")], cwd=self.tmp, capture_output=True, text=True)
        data = json.loads((self.tmp / "out.json").read_text()) if (self.tmp / "out.json").exists() else {}
        return r, data

    def test_census_clean(self):
        self.write("r.xml", junit([("tests.test_a", "test_x"), ("tests.test_a", "test_y")]))
        self.write("list.txt", "tests/test_a.py::test_x\ntests/test_a.py::test_y\n")
        r, data = self.census("--report", "r.xml", "--list-file", "list.txt")
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertEqual(data["executions"], 2)

    def test_census_duplicates(self):
        cases = [("tests.test_a", "test_x"), ("tests.test_a", "test_y")]
        self.write("r.xml", junit(cases * 3))
        r, data = self.census("--report", "r.xml")
        self.assertNotEqual(r.returncode, 0)
        self.assertEqual(data["executions"], 6)
        self.assertEqual(data["unique"], 2)

    def test_census_repeat_declared(self):
        cases = [("tests.test_a", "test_x")]
        self.write("r.xml", junit(cases * 3))
        r, data = self.census("--report", "r.xml", "--repeat", "3")
        self.assertEqual(r.returncode, 0, r.stdout)

    def test_census_overlap(self):
        self.write("s1.xml", junit([("t", "a"), ("t", "b")]))
        self.write("s2.xml", junit([("t", "a"), ("t", "b")]))
        r, data = self.census("--report", "s1.xml", "--report", "s2.xml")
        self.assertNotEqual(r.returncode, 0)
        self.assertTrue(data["overlap"])

    def test_census_shards_partition_ok(self):
        self.write("s1.xml", junit([("t", "a")]))
        self.write("s2.xml", junit([("t", "b")]))
        self.write("list.txt", "t::a\nt::b\n")
        r, data = self.census("--report", "s1.xml", "--report", "s2.xml", "--list-file", "list.txt")
        self.assertEqual(r.returncode, 0, r.stdout)

    def test_census_missing(self):
        self.write("r.xml", junit([("t", "a")]))
        self.write("list.txt", "t::a\nt::b\nt::c\n")
        r, data = self.census("--report", "r.xml", "--list-file", "list.txt")
        self.assertNotEqual(r.returncode, 0)
        self.assertEqual(len(data["missing"]), 2)

    def test_census_empty(self):
        self.write("r.xml", junit([]))
        r, data = self.census("--report", "r.xml")
        self.assertNotEqual(r.returncode, 0)
        self.assertTrue(data["empty"])

    def test_census_no_report_file_is_empty(self):
        r, data = self.census("--report", "nothing-*.xml")
        self.assertNotEqual(r.returncode, 0)
        self.assertTrue(data["empty"])

    def test_census_list_command_go_style_names(self):
        self.write("r.xml", junit([("example.com/pkg", "TestA"), ("example.com/pkg", "TestB")]))
        r, data = self.census("--report", "r.xml", "--list-cmd", "printf 'TestA\\nTestB\\nok example.com/pkg 0.01s\\n'")
        self.assertEqual(r.returncode, 0, r.stdout)


TIMING = ENGINE_DIR / "timing.py"


class Timing(unittest.TestCase):
    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_timing_slowest(self):
        body = ('<testsuite><testcase classname="t" name="fast" time="0.01"/>'
                '<testcase classname="t" name="slow" time="42.5"/><testcase classname="t" name="mid" time="3.0"/></testsuite>')
        (self.tmp / "r.xml").write_text(body, encoding="utf-8")
        r = subprocess.run([sys.executable, str(TIMING), "slowest", "--report", "r.xml", "--top", "2", "--json", "o.json"], cwd=self.tmp, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        data = json.loads((self.tmp / "o.json").read_text())
        self.assertEqual([t["test"] for t in data["slowest"]], ["t.slow", "t.mid"])
        self.assertGreater(data["top_share"], 0.9)

    def test_timing_flaky(self):
        runs = [{"t.a": "pass", "t.b": "pass"}, {"t.a": "fail", "t.b": "pass"}, {"t.a": "pass", "t.b": "pass"}]
        for i, outcomes in enumerate(runs):
            (self.tmp / f"FULLRUN-2026-10-0{i + 1}-000000.tests.json").write_text(json.dumps(outcomes), encoding="utf-8")
        r = subprocess.run([sys.executable, str(TIMING), "flaky", "--dir", ".", "--runs", "3", "--json", "o.json"], cwd=self.tmp, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        data = json.loads((self.tmp / "o.json").read_text())
        self.assertEqual(list(data["flaky"]), ["t.a"])

    def test_fullrun_keeps_per_test_outcomes(self):
        (self.tmp / "docs").mkdir()
        (self.tmp / "docs" / "PROJECT.md").write_text(
            "## 6. Gate checks\n\n### Full tier\n\n```\n#: report=r.xml\n"
            "printf '<testsuite><testcase classname=\"t\" name=\"a\"/><testcase classname=\"t\" name=\"b\"><failure/></testcase></testsuite>' > r.xml\n"
            "```\n\n## 7. x\n", encoding="utf-8")
        subprocess.run([sys.executable, str(ENGINE_DIR / "engine.py"), "--out", "r"], cwd=self.tmp, capture_output=True, text=True)
        files = list((self.tmp / "r").glob("FULLRUN-*.tests.json"))
        self.assertTrue(files)
        self.assertEqual(json.loads(files[0].read_text()), {"t.a": "pass", "t.b": "fail"})


class ReportOrder(unittest.TestCase):
    def test_reports_sort_in_run_order_within_one_second(self):
        tmp = pathlib.Path(tempfile.mkdtemp())
        try:
            (tmp / "docs").mkdir()
            (tmp / "docs" / "PROJECT.md").write_text("## 6. Gate checks\n\n### Full tier\n\n```\ntrue\n```\n\n## 7. x\n", encoding="utf-8")
            names = []
            for _ in range(3):
                subprocess.run([sys.executable, str(ENGINE_DIR / "engine.py"), "--out", "r"], cwd=tmp, capture_output=True, text=True)
                newest = max((tmp / "r").glob("FULLRUN-*.md"), key=lambda p: p.stat().st_mtime_ns)
                names.append(newest.name)
            self.assertEqual(names, sorted(names), names)
            self.assertEqual(len(set(names)), 3)
        finally:
            shutil.rmtree(tmp)


class AtomicReport(unittest.TestCase):
    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp())
        (self.tmp / "docs").mkdir()

    def tearDown(self):
        subprocess.run(["pkill", "-f", "sleep 37.25"], capture_output=True)
        shutil.rmtree(self.tmp)

    def project(self, block):
        (self.tmp / "docs" / "PROJECT.md").write_text(f"## 6. Gate checks\n\n### Full tier\n\n```\n{block}\n```\n\n## 7. x\n", encoding="utf-8")

    def engine(self, *args, background=False):
        cmd = [sys.executable, str(ENGINE_DIR / "engine.py"), "--out", "r", *args]
        if background:
            return subprocess.Popen(cmd, cwd=self.tmp, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return subprocess.run(cmd, cwd=self.tmp, capture_output=True, text=True)

    def test_fullrun_stop_keeps_last_red(self):
        self.project("false")
        self.engine()
        self.project('bash -c "sleep 37.25 & wait"')
        proc = self.engine(background=True)
        import time
        time.sleep(1.5)
        self.engine("--stop")
        proc.wait(timeout=20)
        tsvs = sorted((self.tmp / "r").glob("FULLRUN-*.tsv"))
        newest = [p for p in tsvs if p.read_text().strip()][-1]
        self.assertTrue(newest.read_text().startswith("fail\t"), [p.read_text() for p in tsvs])
        self.assertFalse([p for p in tsvs if not p.read_text().strip()], "an empty tsv was left behind")

    def test_fullrun_unanswered_tier_no_tsv(self):
        self.project("_unanswered_")
        r = self.engine()
        self.assertNotEqual(r.returncode, 0)
        self.assertEqual(list((self.tmp / "r").glob("FULLRUN-*.tsv")) if (self.tmp / "r").exists() else [], [])


PROJECT_TEMPLATE = pathlib.Path(os.environ.get("PROJECT_TEMPLATE", HERE.parent / "project-template" / "docs" / "PROJECT.md"))


class TemplateAttrs(unittest.TestCase):
    def test_project_template_full_tier_attrs(self):
        sys.path.insert(0, str(ENGINE_DIR))
        import engine
        text = PROJECT_TEMPLATE.read_text(encoding="utf-8")
        start = text.index("```text example-full-tier")
        example = text[start:text.index("```", start + 5) + 3].replace("```text example-full-tier", "```")
        cmds = engine.tier("## 6. Gate checks\n\n### Full tier\n\n" + example + "\n\n## 7. x\n", "Full")
        self.assertTrue(cmds)
        for c in cmds:
            self.assertEqual(c.unknown, [])
        self.assertTrue(any("{shard}" in c.text and c.attrs.get("shards") for c in cmds))


class ShardExpansion(unittest.TestCase):
    def test_expect_is_expanded_per_shard(self):
        tmp = pathlib.Path(tempfile.mkdtemp())
        try:
            (tmp / "docs").mkdir()
            (tmp / "docs" / "PROJECT.md").write_text(
                "## 6. Gate checks\n\n### Full tier\n\n```\n#: shards=2 expect=\"test -s out-{shard}.txt\"\necho x > out-{shard}.txt\n```\n\n## 7. x\n",
                encoding="utf-8")
            r = subprocess.run([sys.executable, str(ENGINE_DIR / "engine.py"), "--out", str(tmp / "r")], cwd=tmp, capture_output=True, text=True)
            self.assertIn("pass=2", r.stdout, r.stdout + r.stderr)
        finally:
            shutil.rmtree(tmp)


if __name__ == "__main__":
    unittest.main()
