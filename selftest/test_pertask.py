# test_pertask.py
import importlib
import os
import pathlib
import shutil
import sys
import tempfile
import unittest

HERE = pathlib.Path(__file__).resolve().parent
PERTASK_DIR = pathlib.Path(os.environ.get("PERTASK_DIR", HERE.parent / "pertask"))
sys.dont_write_bytecode = True
sys.path.insert(0, str(PERTASK_DIR))
budget = importlib.import_module("budget")

PLAN = "docs/plans/demo.md"


def measured(**seconds):
    state = budget.empty()
    for command, value in seconds.items():
        budget.note_run(state, command, value, 0)
    return state


class Project(unittest.TestCase):
    def setUp(self):
        self.root = pathlib.Path(os.path.realpath(tempfile.mkdtemp()))

    def tearDown(self):
        shutil.rmtree(self.root)

    def project_file(self, text):
        (self.root / "docs").mkdir(exist_ok=True)
        (self.root / "docs" / "PROJECT.md").write_text(text, encoding="utf-8")


class Limit(Project):
    def test_limit_default(self):
        self.project_file("# Project\n\n## 6. Gate checks\n\n| Question | Answer |\n|---|---|\n| Coverage floor | 80 |\n")
        self.assertEqual(budget.limit(self.root), 30)

    def test_limit_from_project(self):
        layouts = [
            "## 6. Gate checks\n\n| Question | Answer |\n|---|---|\n| Per-task limit for gate checks, seconds | 45 |\n",
            "# Notes\n\n|Per-task limit for gate checks, seconds|45|\n\n## Gate\n\n```\nmake test\n```\n",
            "intro\n\n   |  Per-task limit for gate checks, seconds  |   45   |  measured at T00 |\n",
        ]
        for text in layouts:
            with self.subTest(text=text):
                self.project_file(text)
                self.assertEqual(budget.limit(self.root), 45)

    def test_limit_unanswered_row_is_default(self):
        for answer in ("_unanswered_", "", "0", "-5", "soon"):
            with self.subTest(answer=answer):
                self.project_file(f"| Per-task limit for gate checks, seconds | {answer} |\n")
                self.assertEqual(budget.limit(self.root), 30)

    def test_limit_argument_wins(self):
        self.project_file("| Per-task limit for gate checks, seconds | 45 |\n")
        self.assertEqual(budget.limit(self.root, 12), 12)

    def test_no_project_file(self):
        self.assertEqual(budget.limit(self.root), 30)
        path = budget.state_path(self.root, PLAN)
        budget.save(path, measured(lint=2))
        self.assertEqual(budget.load(path)["commands"]["lint"]["seconds"], 2)


class Decision(unittest.TestCase):
    def test_cheapest_first(self):
        state = measured(suite=193, lint=2, unit=5)
        self.assertEqual(budget.fitting(state, 30), ["lint", "unit"])
        self.assertTrue(budget.runs_now(state, "lint", 30))
        self.assertFalse(budget.runs_now(state, "suite", 30))

    def test_prefix_stops_at_the_limit(self):
        state = measured(a=20, b=15, c=1)
        self.assertEqual(budget.fitting(state, 30), ["c", "b"])
        self.assertEqual(budget.fitting(state, 36), ["c", "b", "a"])
        self.assertEqual(budget.fitting(state, 0.5), [])

    def test_set_at_the_limit_runs_whole(self):
        state = measured(a=10, b=20)
        self.assertEqual(sorted(budget.fitting(state, 30)), ["a", "b"])

    def test_unmeasured_command_runs_now(self):
        state = measured(suite=193)
        self.assertTrue(budget.runs_now(state, "never seen", 30))

    def test_failed_run_keeps_the_longer_measure(self):
        state = measured(suite=193)
        budget.note_run(state, "suite", 4, 1)
        self.assertEqual(state["commands"]["suite"]["seconds"], 193)
        budget.note_run(state, "suite", 250, 1)
        self.assertEqual(state["commands"]["suite"]["seconds"], 250)
        budget.note_run(state, "suite", 60, 0)
        self.assertEqual(state["commands"]["suite"]["seconds"], 60)


class Deferred(unittest.TestCase):
    def test_skip_is_owed_until_the_command_runs(self):
        state = measured(suite=193, lint=2)
        self.assertEqual(budget.deferred(state), [])
        budget.note_skip(state, "suite")
        self.assertEqual(budget.deferred(state), ["suite"])
        budget.note_run(state, "lint", 2, 0)
        self.assertEqual(budget.deferred(state), ["suite"])
        budget.note_run(state, "suite", 190, 0)
        self.assertEqual(budget.deferred(state), [])
        budget.note_skip(state, "suite")
        self.assertEqual(budget.deferred(state), ["suite"])


class State(Project):
    def test_state_roundtrip(self):
        state = measured(suite=193)
        budget.note_skip(state, "suite")
        path = budget.state_path(self.root, PLAN)
        budget.save(path, state)
        self.assertEqual(budget.load(path), state)

    def test_lost_state_is_unmeasured(self):
        path = budget.state_path(self.root, PLAN)
        self.assertEqual(budget.load(path), budget.empty())
        path.parent.mkdir(parents=True)
        path.write_text("{not json", encoding="utf-8")
        self.assertEqual(budget.load(path), budget.empty())

    def test_plan_forms_share_one_state(self):
        forms = [PLAN, "./" + PLAN, str(self.root / PLAN), "docs/../docs/plans/demo.md"]
        paths = {budget.state_path(self.root, form) for form in forms}
        self.assertEqual(len(paths), 1)
        self.assertEqual(paths.pop().parent, self.root / ".claude" / "scratch" / "pertask")

    def test_plans_do_not_share_state(self):
        self.assertNotEqual(budget.state_path(self.root, PLAN), budget.state_path(self.root, "docs/plans/other.md"))


if __name__ == "__main__":
    unittest.main()
