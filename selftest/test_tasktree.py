# test_tasktree.py
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = pathlib.Path(__file__).resolve().parent
TEMPLATE = pathlib.Path(os.environ.get("TASKTREE_TEMPLATE", HERE.parent / "project-template" / "tasks"))
LEGACY = HERE / "fixtures" / "tasks-legacy"

README = "# Task tree\n\n```\nphase: build\n```\n"
ROLES = "| Role | Owns |\n|---|---|\n| **DEV** | code |\n"

LABELS_V1 = "phase:build\nrole:DEV\ntype:feature\npriority:P1\nstatus:todo\nverify:pending\nmilestone:M1\n"

TASK_V2 = """TASK: parser

GOAL
  Parse the input file.

CONTEXT
  src/parser.py

SCOPE
  + S1 parse headers
  + S2 parse body
  − writing output — 20-build/02-writer
  indivisible: headers and body share one tokenizer state

WRITE-SET
  src/parser.py
  tests/test_parser.py

DATA
  (none)

SECURITY
  (no sinks)

OUTCOME
  src/parser.py exists.

VERIFY (DEV)
  1. [fast] headers parse; reverse control: drop the header loop → tests/test_parser.py::test_headers
  2. [fast] body parses

ROLE
  DEV

DEPENDS
  (none)
"""

VERIFY_MD_HEAD = """Verifier: separate context; wrote neither the code nor the tests.

## How to reproduce
`python3 -m pytest` from a clean checkout.

## Requirement evidence
"""

VERIFY_MD_TAIL = """
## Reverse control
dropped the header loop, test red.

## What was not checked
performance.
"""


def run_check(root: pathlib.Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(root / "check.py"), str(root)],
        capture_output=True,
        text=True,
    )


class TreeCase(unittest.TestCase):
    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp())
        self.root = self.tmp / "tasks"
        self.root.mkdir()
        for f in TEMPLATE.glob("*.py"):
            shutil.copy(f, self.root / f.name)
        (self.root / "README.md").write_text(README, encoding="utf-8")
        (self.root / "ROLES.md").write_text(ROLES, encoding="utf-8")

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def task(self, rel, body, labels, verify_md=None):
        d = self.root / rel
        d.mkdir(parents=True)
        (d / "task.txt").write_text(body, encoding="utf-8")
        (d / "labels.txt").write_text(labels, encoding="utf-8")
        if verify_md is not None:
            (d / "VERIFY.md").write_text(verify_md, encoding="utf-8")
        return d


class RequirementIds(TreeCase):
    def test_verify_maps_every_id_passes(self):
        evidence = "- S1: src/parser.py:12 header loop\n- S2: `pytest tests/test_body.py` exit 0\n- V1: tests/test_parser.py:5\n- V2: `pytest -k body` exit 0\n"
        self.task("10-build/01-parser", TASK_V2, LABELS_V1 + "format:2\n", VERIFY_MD_HEAD + evidence + VERIFY_MD_TAIL)
        r = run_check(self.root)
        self.assertEqual(r.returncode, 0, r.stdout)

    def test_verify_maps_every_id_missing_scope_id(self):
        evidence = "- S1: src/parser.py:12\n- V1: tests/test_parser.py:5\n- V2: `pytest -k body` exit 0\n"
        self.task("10-build/01-parser", TASK_V2, LABELS_V1 + "format:2\n", VERIFY_MD_HEAD + evidence + VERIFY_MD_TAIL)
        r = run_check(self.root)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("S2", r.stdout)

    def test_verify_maps_every_id_missing_verify_item(self):
        evidence = "- S1: src/parser.py:12\n- S2: src/parser.py:30\n- V1: tests/test_parser.py:5\n"
        self.task("10-build/01-parser", TASK_V2, LABELS_V1 + "format:2\n", VERIFY_MD_HEAD + evidence + VERIFY_MD_TAIL)
        r = run_check(self.root)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("V2", r.stdout)

    def test_verify_maps_every_id_evidence_without_proof(self):
        evidence = "- S1: done, looks fine\n- S2: src/parser.py:30\n- V1: tests/test_parser.py:5\n- V2: `pytest -k body` exit 0\n"
        self.task("10-build/01-parser", TASK_V2, LABELS_V1 + "format:2\n", VERIFY_MD_HEAD + evidence + VERIFY_MD_TAIL)
        r = run_check(self.root)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("S1", r.stdout)

    def test_format2_scope_line_without_id(self):
        body = TASK_V2.replace("+ S2 parse body", "+ parse body")
        self.task("10-build/01-parser", body, LABELS_V1 + "format:2\n")
        r = run_check(self.root)
        self.assertNotEqual(r.returncode, 0)

    def test_format2_duplicate_scope_id(self):
        body = TASK_V2.replace("+ S2 parse body", "+ S1 parse body")
        self.task("10-build/01-parser", body, LABELS_V1 + "format:2\n")
        r = run_check(self.root)
        self.assertNotEqual(r.returncode, 0)

    def test_unknown_format_value(self):
        self.task("10-build/01-parser", TASK_V2, LABELS_V1 + "format:7\n")
        r = run_check(self.root)
        self.assertNotEqual(r.returncode, 0)

    def test_legacy_task_without_ids_passes(self):
        body = TASK_V2.replace("+ S1 ", "+ ").replace("+ S2 ", "+ ")
        self.task("10-build/01-parser", body, LABELS_V1, "Verifier: x\n## How to reproduce\nx\n## What was not checked\nx\n")
        r = run_check(self.root)
        self.assertEqual(r.returncode, 0, r.stdout)


def readme_example() -> str:
    text = (TEMPLATE / "README.md").read_text(encoding="utf-8")
    start = text.index("```task.txt format:2\n") + len("```task.txt format:2\n")
    return text[start:text.index("\n```", start) + 1]


class Template(TreeCase):
    def test_format2_template_valid(self):
        (self.tmp / "docs" / "tech").mkdir(parents=True)
        (self.tmp / "docs" / "tech" / "fastapi@0.115.md").write_text(
            "# fastapi@0.115\n\n- request bodies validate through pydantic v2: https://fastapi.tiangolo.com/tutorial/body/\n",
            encoding="utf-8",
        )
        self.task("10-build/01-reminders", readme_example(), LABELS_V1 + "format:2\n")
        r = run_check(self.root)
        self.assertEqual(r.returncode, 0, r.stdout)


def with_write_set(body, units):
    return re.sub(r"WRITE-SET\n(  .*\n)+", "WRITE-SET\n" + "".join(f"  {u}\n" for u in units), body)


class Splitting(TreeCase):
    def sibling(self, rel, units, labels_extra="", depends=None):
        body = with_write_set(TASK_V2, units)
        labels = LABELS_V1 + "format:2\n" + labels_extra
        if depends:
            body = body.replace("DEPENDS\n  (none)", "DEPENDS\n  " + ", ".join(depends))
            labels += "depends:" + ",".join(depends) + "\n"
        self.task(rel, body, labels)

    def test_writeset_overlap_same_method(self):
        self.sibling("10-build/01-a", ["src/parser.py::Parser.headers"])
        self.sibling("10-build/02-b", ["src/parser.py::Parser.headers"])
        r = run_check(self.root)
        self.assertNotEqual(r.returncode, 0)

    def test_writeset_overlap_whole_file_and_method(self):
        self.sibling("10-build/01-a", ["src/parser.py"])
        self.sibling("10-build/02-b", ["src/parser.py::Parser.body"])
        r = run_check(self.root)
        self.assertNotEqual(r.returncode, 0)

    def test_writeset_disjoint_files_pass(self):
        self.sibling("10-build/01-a", ["src/a.py"])
        self.sibling("10-build/02-b", ["src/b.py"])
        r = run_check(self.root)
        self.assertEqual(r.returncode, 0, r.stdout)

    def test_missing_indivisible(self):
        body = TASK_V2.replace("  indivisible: headers and body share one tokenizer state\n", "")
        self.task("10-build/01-parser", body, LABELS_V1 + "format:2\n")
        r = run_check(self.root)
        self.assertNotEqual(r.returncode, 0)

    def test_missing_write_set(self):
        body = re.sub(r"WRITE-SET\n(  .*\n)+\n", "", TASK_V2)
        self.task("10-build/01-parser", body, LABELS_V1 + "format:2\n")
        r = run_check(self.root)
        self.assertNotEqual(r.returncode, 0)

    def test_contract_order_missing(self):
        self.sibling("10-build/01-a", ["src/parser.py::Parser.headers"], "split:part\n")
        self.sibling("10-build/02-b", ["src/parser.py::Parser.body"], "split:part\n")
        r = run_check(self.root)
        self.assertNotEqual(r.returncode, 0)

    def test_contract_order_present(self):
        self.sibling("10-build/01-contract", ["src/parser_api.py"], "split:contract\n")
        self.sibling("10-build/02-a", ["src/parser.py::Parser.headers"], "split:part\n", ["10-build/01-contract"])
        self.sibling("10-build/03-b", ["src/parser.py::Parser.body"], "split:part\n", ["10-build/01-contract"])
        r = run_check(self.root)
        self.assertEqual(r.returncode, 0, r.stdout)

    def test_contract_and_dependent_part_share_a_file(self):
        self.sibling("10-build/01-contract", ["src/parser.py::Parser.__init__"], "split:contract\n")
        self.sibling("10-build/02-a", ["src/parser.py::Parser.headers"], "split:part\n", ["10-build/01-contract"])
        self.sibling("10-build/03-b", ["src/parser.py::Parser.body"], "split:part\n", ["10-build/01-contract"])
        r = run_check(self.root)
        self.assertEqual(r.returncode, 0, r.stdout)

    def test_phase_task_is_not_a_sibling_of_its_children(self):
        self.task("10-build", with_write_set(TASK_V2, ["src/parser.py"]).replace("  indivisible: headers and body share one tokenizer state\n", ""), LABELS_V1 + "format:2\n")
        self.sibling("10-build/01-a", ["src/parser.py::Parser.headers"])
        r = run_check(self.root)
        self.assertEqual(r.returncode, 0, r.stdout)

    def test_assembly_may_touch_parts_files(self):
        self.sibling("10-build/01-contract", ["src/parser_api.py"], "split:contract\n")
        self.sibling("10-build/02-a", ["src/parser.py::Parser.headers"], "split:part\n", ["10-build/01-contract"])
        self.sibling("10-build/03-b", ["src/parser.py::Parser.body"], "split:part\n", ["10-build/01-contract"])
        self.sibling("10-build/04-asm", ["src/parser.py"], "split:assembly\n", ["10-build/02-a", "10-build/03-b"])
        r = run_check(self.root)
        self.assertEqual(r.returncode, 0, r.stdout)


def with_data(*records):
    return TASK_V2.replace("DATA\n  (none)", "DATA\n" + "".join(f"  {r}\n" for r in records).rstrip("\n"))


GOOD_TEXT = "note.text: dir=in; type=string; size=1..500 chars UTF-8; null=no; interpretable=yes; source=https://docs.python.org/3.12/library/stdtypes.html"
GOOD_ID = "note.id: dir=in; type=int64; range=1..9223372036854775807; null=no; interpretable=no; validated=tests/test_note.py::test_id; source=https://www.postgresql.org/docs/16/datatype-numeric.html"


class DataBlock(TreeCase):
    def check_body(self, body):
        self.task("10-build/01-parser", body, LABELS_V1 + "format:2\n")
        return run_check(self.root)

    def test_data_valid_records_pass(self):
        r = self.check_body(with_data(GOOD_TEXT, GOOD_ID))
        self.assertEqual(r.returncode, 0, r.stdout)

    def test_data_bare_type(self):
        r = self.check_body(with_data("note.count: dir=in; type=int; null=no; interpretable=no; validated=tests/t.py::c; source=https://docs.python.org/3.12/"))
        self.assertNotEqual(r.returncode, 0)

    def test_data_no_source(self):
        r = self.check_body(with_data(GOOD_TEXT.split("; source=")[0]))
        self.assertNotEqual(r.returncode, 0)

    def test_data_source_without_version(self):
        r = self.check_body(with_data(GOOD_TEXT.split("; source=")[0] + "; source=https://docs.python.org/library/"))
        self.assertNotEqual(r.returncode, 0)

    def test_data_not_interpretable_without_input_test(self):
        r = self.check_body(with_data(GOOD_ID.replace("validated=tests/test_note.py::test_id; ", "")))
        self.assertNotEqual(r.returncode, 0)

    def test_data_section_missing(self):
        r = self.check_body(TASK_V2.replace("DATA\n  (none)\n\n", ""))
        self.assertNotEqual(r.returncode, 0)


def with_security(body, *lines):
    return body.replace("SECURITY\n  (no sinks)", "SECURITY\n" + "".join(f"  {x}\n" for x in lines).rstrip("\n"))


class Sinks(TreeCase):
    def setUp(self):
        super().setUp()
        self.task("10-build/01-input", with_write_set(with_data(GOOD_TEXT, GOOD_ID), ["src/input.py"]), LABELS_V1 + "format:2\n")

    def sink_task(self, *lines):
        body = with_security(with_write_set(TASK_V2, ["src/push.py"]), *lines)
        self.task("30-notify/01-push", body, LABELS_V1 + "format:2\n")
        return run_check(self.root)

    def test_sink_unsafe_field_unprotected(self):
        r = self.sink_task("sink push.payload: consumes note.text")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("note.text", r.stdout)

    def test_sink_unsafe_field_protected(self):
        r = self.sink_task("sink push.payload: consumes note.text; protection=escape for the push payload, app:// links only; test=tests/test_push.py::test_escapes")
        self.assertEqual(r.returncode, 0, r.stdout)

    def test_sink_safe_field_needs_nothing(self):
        r = self.sink_task("sink push.payload: consumes note.id")
        self.assertEqual(r.returncode, 0, r.stdout)

    def test_sink_unknown_field(self):
        r = self.sink_task("sink push.payload: consumes note.title; protection=escape; test=tests/t.py::x")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("note.title", r.stdout)

    def test_security_section_missing(self):
        body = with_write_set(TASK_V2, ["src/push.py"]).replace("SECURITY\n  (no sinks)\n\n", "")
        self.task("30-notify/01-push", body, LABELS_V1 + "format:2\n")
        r = run_check(self.root)
        self.assertNotEqual(r.returncode, 0)


def with_verify(*items):
    head = "VERIFY (DEV)\n"
    start = TASK_V2.index(head) + len(head)
    end = TASK_V2.index("\nROLE")
    return TASK_V2[:start] + "".join(f"  {i + 1}. {x}\n" for i, x in enumerate(items)) + TASK_V2[end:]


RC = "[fast] reverse control: drop the header loop → tests/test_parser.py::test_headers"


class Tiers(TreeCase):
    def check_body(self, body):
        self.task("10-build/01-parser", body, LABELS_V1 + "format:2\n")
        return run_check(self.root)

    def test_fast_heavy_over_3(self):
        r = self.check_body(with_verify(RC, *["[fast, heavy] long integration"] * 4))
        self.assertNotEqual(r.returncode, 0)

    def test_fast_heavy_3_pass(self):
        r = self.check_body(with_verify(RC, *["[fast, heavy] long integration"] * 3))
        self.assertEqual(r.returncode, 0, r.stdout)

    def test_full_heavy_unlimited(self):
        r = self.check_body(with_verify(RC, *["[full, heavy] mutation run"] * 6))
        self.assertEqual(r.returncode, 0, r.stdout)

    def test_reverse_control_unnamed(self):
        r = self.check_body(with_verify("[fast] reverse control: yes, done", "[fast] body parses"))
        self.assertNotEqual(r.returncode, 0)

    def test_reverse_control_missing(self):
        r = self.check_body(with_verify("[fast] headers parse", "[fast] body parses"))
        self.assertNotEqual(r.returncode, 0)

    def test_verify_item_without_tier(self):
        r = self.check_body(with_verify(RC, "body parses"))
        self.assertNotEqual(r.returncode, 0)


class MilestoneFullRun(TreeCase):
    def gate_task(self, tsv):
        d = self.task("10-build/01-parser", TASK_V2, LABELS_V1.replace("status:todo", "status:done").replace("verify:pending", "verify:passed") + "format:2\ngate:yes\n",
                      VERIFY_MD_HEAD + "- S1: src/parser.py:1\n- S2: src/parser.py:2\n- V1: `pytest` exit 0\n- V2: `pytest` exit 0\n" + VERIFY_MD_TAIL)
        (d / "FULLRUN-2026-10-05-010000.tsv").write_text(tsv, encoding="utf-8")
        return run_check(self.root)

    def test_milestone_red_full_run_holds(self):
        r = self.gate_task("pass\tpytest -m slow\nfail\tmutmut run\n")
        self.assertNotEqual(r.returncode, 0)

    def test_milestone_timeout_holds(self):
        r = self.gate_task("pass\tpytest -m slow\t30\ntimeout\tmutmut run --shard 1/16\t3000\n")
        self.assertNotEqual(r.returncode, 0)

    def test_milestone_empty_holds(self):
        r = self.gate_task("empty\tmutmut run\t2900\n")
        self.assertNotEqual(r.returncode, 0)

    def test_milestone_dup_holds(self):
        r = self.gate_task("dup\tpytest -n 16 [census of 16 shards]\t0\n")
        self.assertNotEqual(r.returncode, 0)

    def test_milestone_green_full_run_closes(self):
        r = self.gate_task("pass\tpytest -m slow\npass\tmutmut run\n")
        self.assertEqual(r.returncode, 0, r.stdout)


class CapabilityLabel(TreeCase):
    def project(self, rows):
        (self.tmp / "docs").mkdir(exist_ok=True)
        (self.tmp / "docs" / "PROJECT.md").write_text(
            "## 3. Capability ledger\n\n| Capability | State | Note |\n|---|---|---|\n" + rows + "\n## 4. Decided\n", encoding="utf-8")

    def test_integrity_capability_without_ledger(self):
        self.project("| Accounts | included | |\n")
        self.task("10-build/01-parser", TASK_V2, LABELS_V1 + "format:2\ncapability:Payments\n")
        r = run_check(self.root)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("Payments", r.stdout)

    def test_capability_absent_in_ledger(self):
        self.project("| Payments | absent | |\n")
        self.task("10-build/01-parser", TASK_V2, LABELS_V1 + "format:2\ncapability:Payments\n")
        r = run_check(self.root)
        self.assertNotEqual(r.returncode, 0)

    def test_capability_in_ledger(self):
        self.project("| Payments | included | card only |\n")
        self.task("10-build/01-parser", TASK_V2, LABELS_V1 + "format:2\ncapability:payments\n")
        r = run_check(self.root)
        self.assertEqual(r.returncode, 0, r.stdout)


class AttackLabel(TreeCase):
    def test_attack_label_without_report(self):
        self.task("10-build/01-parser", TASK_V2, LABELS_V1 + "format:2\nattack:passed\n")
        r = run_check(self.root)
        self.assertNotEqual(r.returncode, 0)

    def test_attack_label_with_report(self):
        d = self.task("10-build/01-parser", TASK_V2, LABELS_V1 + "format:2\nattack:failed\n")
        (d / "ATTACK.md").write_text("Attacker: x\n", encoding="utf-8")
        r = run_check(self.root)
        self.assertEqual(r.returncode, 0, r.stdout)


LINT_CHANGED = TEMPLATE.parent / "scripts" / "lint_changed.py"
FAKE_LINT = [sys.executable, "-c", "import sys; bad=[f for f in sys.argv[1:] if 'BAD' in open(f).read()]; print(*bad); sys.exit(1 if bad else 0)"]


class DiffScopedLint(unittest.TestCase):
    def setUp(self):
        self.repo = pathlib.Path(tempfile.mkdtemp())
        git(self.repo, "init", "-q")
        (self.repo / "old.sh").write_text("echo BAD\n", encoding="utf-8")
        (self.repo / "README.md").write_text("x\n", encoding="utf-8")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-qm", "base")
        self.base = subprocess.run(["git", "rev-parse", "HEAD"], cwd=self.repo, capture_output=True, text=True).stdout.strip()

    def tearDown(self):
        shutil.rmtree(self.repo)

    def lint(self):
        return subprocess.run([sys.executable, str(LINT_CHANGED), "--base", self.base, "--glob", "*.sh", "--", *FAKE_LINT],
                              cwd=self.repo, capture_output=True, text=True)

    def test_diff_scoped_lint_old_finding_ignored(self):
        (self.repo / "README.md").write_text("y\n", encoding="utf-8")
        r = self.lint()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_diff_scoped_lint_new_finding_caught(self):
        (self.repo / "new.sh").write_text("echo BAD\n", encoding="utf-8")
        r = self.lint()
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("new.sh", r.stdout)
        self.assertNotIn("old.sh", r.stdout)


class LegacyTreeTools(unittest.TestCase):
    def test_legacy_tree_task_format_scope_check_from_template(self):
        repo = pathlib.Path(tempfile.mkdtemp())
        try:
            shutil.copytree(LEGACY, repo / "tasks")
            git(repo, "init", "-q")
            (repo / "src").mkdir()
            (repo / "src" / "writer.py").write_text("x = 1\n", encoding="utf-8")
            git(repo, "add", "-A")
            git(repo, "commit", "-qm", "base")
            (repo / "src" / "writer.py").write_text("x = 2\n", encoding="utf-8")
            (repo / "src" / "other.py").write_text("y = 1\n", encoding="utf-8")
            git(repo, "add", "-A")
            git(repo, "commit", "-qm", "task")
            self.assertFalse((repo / "tasks" / "scope_check.py").exists())
            r = subprocess.run([sys.executable, str(TEMPLATE / "scope_check.py"), str(repo / "tasks" / "10-build" / "02-writer")],
                               cwd=repo, capture_output=True, text=True)
            self.assertNotEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn("src/other.py", r.stdout)
            self.assertNotIn("src/writer.py", r.stdout)
        finally:
            shutil.rmtree(repo)


class Legacy(unittest.TestCase):
    def test_legacy_tasks_unchanged(self):
        tmp = pathlib.Path(tempfile.mkdtemp())
        try:
            old, new = tmp / "old", tmp / "new"
            shutil.copytree(LEGACY, old)
            shutil.copytree(LEGACY, new)
            shutil.copy(HERE / "fixtures" / "check_legacy_reference.py", old / "check.py")
            for f in TEMPLATE.glob("*.py"):
                shutil.copy(f, new / f.name)
            a = run_check(old)
            b = run_check(new)
            self.assertEqual((a.returncode, a.stdout), (b.returncode, b.stdout))
            self.assertNotEqual(a.returncode, 0, "the fixture must carry known problems, or the comparison proves nothing")
        finally:
            shutil.rmtree(tmp)


TECH_DOC = """# psycopg@3.2

- `cursor.execute` binds parameters server-side by default: https://www.psycopg.org/psycopg3/docs/basic/params.html
- integer columns arrive as Python int of any size: https://www.psycopg.org/psycopg3/docs/basic/adapt.html
"""


class TechDocs(TreeCase):
    def with_context(self, line):
        return TASK_V2.replace("CONTEXT\n  src/parser.py", "CONTEXT\n  src/parser.py\n  " + line)

    def test_tech_without_doc(self):
        self.task("10-build/01-parser", self.with_context("docs/tech/psycopg@3.2.md"), LABELS_V1 + "format:2\n")
        r = run_check(self.root)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("docs/tech/psycopg@3.2.md", r.stdout)

    def test_tech_doc_present_passes(self):
        (self.tmp / "docs" / "tech").mkdir(parents=True)
        (self.tmp / "docs" / "tech" / "psycopg@3.2.md").write_text(TECH_DOC, encoding="utf-8")
        self.task("10-build/01-parser", self.with_context("docs/tech/psycopg@3.2.md"), LABELS_V1 + "format:2\n")
        r = run_check(self.root)
        self.assertEqual(r.returncode, 0, r.stdout)

    def test_tech_doc_no_url(self):
        (self.tmp / "docs" / "tech").mkdir(parents=True)
        (self.tmp / "docs" / "tech" / "psycopg@3.2.md").write_text(TECH_DOC + "- connections are not thread-safe\n", encoding="utf-8")
        self.task("10-build/01-parser", self.with_context("docs/tech/psycopg@3.2.md"), LABELS_V1 + "format:2\n")
        r = run_check(self.root)
        self.assertNotEqual(r.returncode, 0)

    def test_tech_doc_without_version_in_name(self):
        (self.tmp / "docs" / "tech").mkdir(parents=True)
        (self.tmp / "docs" / "tech" / "psycopg.md").write_text(TECH_DOC, encoding="utf-8")
        self.task("10-build/01-parser", self.with_context("docs/tech/psycopg.md"), LABELS_V1 + "format:2\n")
        r = run_check(self.root)
        self.assertNotEqual(r.returncode, 0)


class NewDependency(TreeCase):
    def commit_manifest(self, before, after, name="requirements.txt"):
        repo = self.tmp
        git(repo, "init", "-q")
        (repo / name).write_text(before)
        git(repo, "add", "-A")
        git(repo, "commit", "-qm", "base")
        (repo / name).write_text(after)
        git(repo, "add", "-A")
        git(repo, "commit", "-qm", "dep")
        return subprocess.run([sys.executable, str(self.root / "tech_check.py"), "HEAD~1"], cwd=repo, capture_output=True, text=True)

    def test_new_dependency_without_doc(self):
        r = self.commit_manifest("requests==2.32.3\n", "requests==2.32.3\npsycopg==3.2.1\n")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("psycopg", r.stdout)

    def test_new_dependency_with_doc(self):
        (self.tmp / "docs" / "tech").mkdir(parents=True)
        (self.tmp / "docs" / "tech" / "psycopg@3.2.md").write_text(TECH_DOC, encoding="utf-8")
        r = self.commit_manifest("requests==2.32.3\n", "requests==2.32.3\npsycopg==3.2.1\n")
        self.assertEqual(r.returncode, 0, r.stdout)

    def test_new_dependency_package_json(self):
        before = '{\n  "dependencies": {\n    "react": "18.3.1"\n  }\n}\n'
        after = '{\n  "dependencies": {\n    "react": "18.3.1",\n    "date-fns": "4.1.0"\n  }\n}\n'
        r = self.commit_manifest(before, after, "package.json")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("date-fns", r.stdout)

    def test_version_bump_is_not_new(self):
        r = self.commit_manifest("requests==2.31.0\n", "requests==2.32.3\n")
        self.assertEqual(r.returncode, 0, r.stdout)


PROJECT_TEMPLATE = TEMPLATE.parent / "docs" / "PROJECT.md"
PROJECT_CHECK = TEMPLATE.parent / "scripts" / "project_check.py"


class ProjectCheck(unittest.TestCase):
    def run_on(self, text):
        tmp = pathlib.Path(tempfile.mkdtemp())
        try:
            (tmp / "docs").mkdir()
            (tmp / "docs" / "PROJECT.md").write_text(text, encoding="utf-8")
            return subprocess.run([sys.executable, str(PROJECT_CHECK)], cwd=tmp, capture_output=True, text=True)
        finally:
            shutil.rmtree(tmp)

    def test_project_template_passes(self):
        r = self.run_on(PROJECT_TEMPLATE.read_text(encoding="utf-8"))
        self.assertEqual(r.returncode, 0, r.stdout)

    def test_project_empty_ledger_ok(self):
        text = PROJECT_TEMPLATE.read_text(encoding="utf-8")
        self.assertNotIn("| Payments | absent |", text, "the template ledger must not presume a web product")
        r = self.run_on(text)
        self.assertEqual(r.returncode, 0, r.stdout)

    def test_project_ledger_bad_state_still_caught(self):
        text = PROJECT_TEMPLATE.read_text(encoding="utf-8").replace("|---|---|---|\n", "|---|---|---|\n| CLI flags | maybe | |\n", 1)
        r = self.run_on(text)
        self.assertNotEqual(r.returncode, 0)

    def run_repo(self, files):
        tmp = pathlib.Path(tempfile.mkdtemp())
        try:
            for name, text in files.items():
                (tmp / name).parent.mkdir(parents=True, exist_ok=True)
                (tmp / name).write_text(text, encoding="utf-8")
            return subprocess.run([sys.executable, str(PROJECT_CHECK)], cwd=tmp, capture_output=True, text=True)
        finally:
            shutil.rmtree(tmp)

    def base_files(self, **over):
        files = {
            "docs/PROJECT.md": PROJECT_TEMPLATE.read_text(encoding="utf-8"),
            "AGENTS.md": "# AGENTS.md\n\n## Map\n\nSee [testing](docs/TESTING.md).\n",
            "CLAUDE.md": "@AGENTS.md\n",
            "docs/TESTING.md": "# Testing\n",
        }
        files.update(over)
        return files

    def test_repo_files_pass(self):
        r = self.run_repo(self.base_files())
        self.assertEqual(r.returncode, 0, r.stdout)

    def test_agents_word_budget(self):
        r = self.run_repo(self.base_files(**{"AGENTS.md": "# AGENTS.md\n\n" + "word " * 1600}))
        self.assertNotEqual(r.returncode, 0)

    def test_claude_imports_agents(self):
        r = self.run_repo(self.base_files(**{"CLAUDE.md": "# rules\n\nsee AGENTS.md\n"}))
        self.assertNotEqual(r.returncode, 0)

    def test_claude_copies_agents_section(self):
        r = self.run_repo(self.base_files(**{"CLAUDE.md": "@AGENTS.md\n\n## Map\n\ncopied\n"}))
        self.assertNotEqual(r.returncode, 0)

    def test_docs_dead_link(self):
        r = self.run_repo(self.base_files(**{"docs/TESTING.md": "# Testing\n\nSee [setup](SETUP.md) and [x](#nowhere).\n"}))
        self.assertNotEqual(r.returncode, 0)

    def test_bootstrap_left(self):
        text = PROJECT_TEMPLATE.read_text(encoding="utf-8").replace("intake: not started", "intake: completed 2026-10-06").replace("_unanswered_", "n/a")
        agents = "# AGENTS.md\n\n<!-- BOOTSTRAP_ONLY_START -->\nrun /intake\n<!-- BOOTSTRAP_ONLY_END -->\n"
        r = self.run_repo(self.base_files(**{"docs/PROJECT.md": text, "AGENTS.md": agents}))
        self.assertNotEqual(r.returncode, 0)

    def drift_repo(self):
        tmp = pathlib.Path(tempfile.mkdtemp())
        (tmp / "docs").mkdir()
        text = PROJECT_TEMPLATE.read_text(encoding="utf-8")
        (tmp / "docs" / "PROJECT.md").write_text(text, encoding="utf-8")
        (tmp / "requirements.txt").write_text("requests==2.32.3\n", encoding="utf-8")
        (tmp / "tests").mkdir()
        (tmp / "tests" / "test_a.py").write_text("x = 1\n", encoding="utf-8")
        r = subprocess.run([sys.executable, str(PROJECT_CHECK), "--refresh-fingerprint"], cwd=tmp, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return tmp

    def check_in(self, tmp):
        return subprocess.run([sys.executable, str(PROJECT_CHECK)], cwd=tmp, capture_output=True, text=True)

    def test_project_drift_clean_after_refresh(self):
        tmp = self.drift_repo()
        try:
            r = self.check_in(tmp)
            self.assertEqual(r.returncode, 0, r.stdout)
        finally:
            shutil.rmtree(tmp)

    def test_project_drift_new_signal(self):
        tmp = self.drift_repo()
        try:
            (tmp / ".golangci.yml").write_text("linters: {}\n", encoding="utf-8")
            r = self.check_in(tmp)
            self.assertNotEqual(r.returncode, 0)
            self.assertIn(".golangci.yml", r.stdout)
        finally:
            shutil.rmtree(tmp)

    def test_project_drift_removed_signal(self):
        tmp = self.drift_repo()
        try:
            (tmp / "requirements.txt").unlink()
            r = self.check_in(tmp)
            self.assertNotEqual(r.returncode, 0)
            self.assertIn("requirements.txt", r.stdout)
        finally:
            shutil.rmtree(tmp)

    def test_project_drift_manifest_line_ignored(self):
        tmp = self.drift_repo()
        try:
            (tmp / "requirements.txt").write_text("requests==2.32.3\nhttpx==0.27.0\n", encoding="utf-8")
            r = self.check_in(tmp)
            self.assertEqual(r.returncode, 0, r.stdout)
        finally:
            shutil.rmtree(tmp)

    def test_project_missing_full_tier(self):
        text = PROJECT_TEMPLATE.read_text(encoding="utf-8")
        start = text.index("### Full tier")
        end = text.index("### ", start + 4) if "### " in text[start + 4:] else text.index("\n## 7.")
        r = self.run_on(text[:start] + text[end:])
        self.assertNotEqual(r.returncode, 0)

    def test_project_missing_full_only_marker_row(self):
        text = PROJECT_TEMPLATE.read_text(encoding="utf-8")
        lines = [line for line in text.splitlines(keepends=True) if "marked full-only" not in line]
        r = self.run_on("".join(lines))
        self.assertNotEqual(r.returncode, 0)


def git(cwd, *args):
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *args], cwd=cwd, check=True, capture_output=True)


class DiffScope(TreeCase):
    def repo_with_change(self, write_set, changed):
        repo = self.tmp
        body = re.sub(r"WRITE-SET\n(  .*\n)+", "WRITE-SET\n" + "".join(f"  {w}\n" for w in write_set), TASK_V2)
        self.task("10-build/01-parser", body, LABELS_V1 + "format:2\n")
        git(repo, "init", "-q")
        (repo / "src").mkdir()
        (repo / "src" / "parser.py").write_text("x = 1\n")
        (repo / "src" / "other.py").write_text("y = 1\n")
        git(repo, "add", "-A")
        git(repo, "commit", "-qm", "base")
        for f in changed:
            path = repo / f
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("changed\n")
        git(repo, "add", "-A")
        git(repo, "commit", "-qm", "task")
        return subprocess.run(
            [sys.executable, str(self.root / "scope_check.py"), str(self.root / "10-build/01-parser"), "HEAD~1"],
            cwd=repo, capture_output=True, text=True,
        )

    def test_diff_outside_write_set(self):
        r = self.repo_with_change(["src/parser.py::parse_headers"], ["src/parser.py", "src/other.py"])
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("src/other.py", r.stdout)

    def test_diff_inside_write_set(self):
        r = self.repo_with_change(["src/parser.py::parse_headers", "tests/"], ["src/parser.py", "tests/test_parser.py"])
        self.assertEqual(r.returncode, 0, r.stdout)

    def test_diff_own_task_dir_allowed(self):
        r = self.repo_with_change(["src/parser.py"], ["src/parser.py", "tasks/10-build/01-parser/NOTES.md"])
        self.assertEqual(r.returncode, 0, r.stdout)


if __name__ == "__main__":
    unittest.main()
