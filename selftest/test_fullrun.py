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
