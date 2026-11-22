# test_project_check.py
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = pathlib.Path(__file__).resolve().parent
TEMPLATE = pathlib.Path(os.environ.get("TASKTREE_TEMPLATE", HERE.parent / "project-template" / "tasks")).parent
PROJECT_TEMPLATE = TEMPLATE / "docs" / "PROJECT.md"
PROJECT_CHECK = TEMPLATE / "scripts" / "project_check.py"
LEVEL_ROW = re.compile(r"^\| Test coverage level[^\n]*\n", re.M)
ANCHOR = "| Coverage command |"


def project_text(level=None):
    text = LEVEL_ROW.sub("", PROJECT_TEMPLATE.read_text(encoding="utf-8"))
    if level is None:
        return text
    row = f"| Test coverage level (critical / standard / release) | {level} |\n"
    return text.replace(ANCHOR, row + ANCHOR, 1)


class CoverageLevelRow(unittest.TestCase):
    def run_on(self, text):
        tmp = pathlib.Path(tempfile.mkdtemp())
        try:
            (tmp / "docs").mkdir()
            (tmp / "docs" / "PROJECT.md").write_text(text, encoding="utf-8")
            return subprocess.run([sys.executable, str(PROJECT_CHECK)], cwd=tmp, capture_output=True, text=True)
        finally:
            shutil.rmtree(tmp)

    def test_level_unknown_value(self):
        self.assertIn(ANCHOR, project_text())
        r = self.run_on(project_text("realease"))
        self.assertNotEqual(r.returncode, 0, r.stdout)

    def test_level_each_value_passes(self):
        for level in ("critical", "standard", "release"):
            with self.subTest(level=level):
                r = self.run_on(project_text(level))
                self.assertEqual(r.returncode, 0, r.stdout)

    def test_level_row_absent_passes(self):
        r = self.run_on(project_text())
        self.assertEqual(r.returncode, 0, r.stdout)


if __name__ == "__main__":
    unittest.main()
