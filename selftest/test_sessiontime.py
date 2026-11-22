# test_sessiontime.py
import datetime
import importlib.util
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

HERE = pathlib.Path(__file__).resolve().parent
SESSIONTIME_DIR = pathlib.Path(os.environ.get("SESSIONTIME_DIR", HERE.parent / "sessiontime"))
FIXTURES = HERE / "fixtures" / "sessiontime"
sys.dont_write_bytecode = True
sys.path.insert(0, str(SESSIONTIME_DIR))
journal = importlib.import_module("journal")
intervals = importlib.import_module("intervals")
rules = importlib.import_module("rules")


def at(clock):
    moment = datetime.datetime.fromisoformat(f"2026-01-05T{clock}+00:00")
    return moment.timestamp()


def calls(book):
    return {call.id: call for message in book.messages for call in message.calls}


class Reading(unittest.TestCase):
    def test_message_split_over_entries_is_one_message(self):
        book = journal.read(FIXTURES / "split.jsonl")
        first = book.messages[0]
        self.assertEqual([message.id for message in book.messages], ["m1", "m2", "m3", "m4"])
        self.assertEqual((first.first, first.last), (at("10:00:05"), at("10:00:30")))
        self.assertEqual([call.id for call in first.calls], ["toolu_run", "toolu_read"])

    def test_tool_starts_at_the_end_of_its_message(self):
        found = calls(journal.read(FIXTURES / "split.jsonl"))
        self.assertEqual((found["toolu_run"].start, found["toolu_run"].end), (at("10:00:30"), at("10:01:30")))
        self.assertEqual((found["toolu_read"].start, found["toolu_read"].end), (at("10:00:30"), at("10:00:31")))

    def test_result_before_the_message_end_starts_at_its_own_entry(self):
        found = calls(journal.read(FIXTURES / "split.jsonl"))
        self.assertEqual((found["toolu_early"].start, found["toolu_early"].end), (at("10:10:04"), at("10:10:06")))
        self.assertEqual((found["toolu_late"].start, found["toolu_late"].end), (at("10:10:09"), at("10:10:12")))

    def test_span_arrivals_and_working_directory(self):
        book = journal.read(FIXTURES / "split.jsonl")
        self.assertEqual((book.first, book.last), (at("10:00:00"), at("10:10:20")))
        self.assertEqual(book.cwds, {"/work/demo"})
        for clock in ("10:00:00", "10:00:31", "10:01:30", "10:10:00"):
            self.assertIn(at(clock), book.arrivals)
        self.assertEqual(book.arrivals, sorted(book.arrivals))

    def test_entries_that_are_not_conversation_are_skipped(self):
        book = journal.read(FIXTURES / "split.jsonl")
        self.assertEqual(sum(len(message.calls) for message in book.messages), 4)
        self.assertEqual(book.unresolved, 0)

    def test_an_entry_seen_in_another_file_is_not_read_twice(self):
        seen = set()
        self.assertEqual(len(journal.read(FIXTURES / "split.jsonl", seen).messages), 4)
        again = journal.read(FIXTURES / "split.jsonl", seen)
        self.assertEqual(again.messages, [])

    def test_call_without_a_result_ends_at_the_next_entry(self):
        book = journal.read(FIXTURES / "unresolved.jsonl")
        call = calls(book)["toolu_cut"]
        self.assertFalse(call.resolved)
        self.assertEqual((call.start, call.end), (at("10:00:10"), at("10:00:50")))
        self.assertEqual(book.unresolved, 1)

    def test_background_run_lasts_from_its_result_to_its_notice(self):
        book = journal.read(FIXTURES / "background.jsonl")
        runs = {item.call.id: (item.start, item.end) for item in book.backgrounds}
        self.assertEqual(runs["toolu_bg"], (at("10:00:11"), at("10:05:11")))
        self.assertEqual(calls(book)["toolu_bg"].end, at("10:00:11"))

    def test_notice_repeated_in_three_forms_counts_once(self):
        book = journal.read(FIXTURES / "background.jsonl")
        self.assertEqual(sorted(item.call.id for item in book.backgrounds), ["toolu_agent", "toolu_bg", "toolu_moved", "toolu_send"])

    def test_command_moved_to_the_background_keeps_running_until_its_notice(self):
        book = journal.read(FIXTURES / "background.jsonl")
        runs = {item.call.id: (item.start, item.end) for item in book.backgrounds}
        self.assertEqual(calls(book)["toolu_moved"].end, at("10:13:00"))
        self.assertEqual(runs["toolu_moved"], (at("10:13:00"), at("10:15:00")))

    def test_background_agent_and_its_resume_are_two_waits(self):
        book = journal.read(FIXTURES / "background.jsonl")
        runs = {item.call.id: (item.start, item.end) for item in book.backgrounds}
        self.assertEqual(runs["toolu_agent"], (at("10:06:01"), at("10:08:01")))
        self.assertEqual(runs["toolu_send"], (at("10:09:01"), at("10:10:01")))
        self.assertEqual(calls(book)["toolu_agent"].agent_id, "a0000000000000001")

    def test_background_run_without_a_notice_is_not_invented(self):
        book = journal.read(FIXTURES / "background.jsonl")
        self.assertIn("toolu_lost", calls(book))
        self.assertNotIn("toolu_lost", [item.call.id for item in book.backgrounds])

    def test_monitor_event_without_status_ends_nothing(self):
        book = journal.read(FIXTURES / "background.jsonl")
        self.assertEqual(len(book.backgrounds), 4)
        self.assertNotIn(at("10:03:00"), [item.end for item in book.backgrounds])

    def test_agent_transcripts_of_a_session(self):
        files = journal.agent_files(FIXTURES / "background.jsonl")
        self.assertEqual([path.name for path in files], ["agent-a0000000000000001.jsonl"])
        book = journal.read(files[0])
        self.assertEqual(book.agent_id, "a0000000000000001")
        self.assertEqual((book.first, book.last), (at("10:06:01"), at("10:10:00")))
        self.assertEqual(journal.agent_files(FIXTURES / "split.jsonl"), [])


def spent(measure, call_id, kind):
    return sum(item.seconds for item in measure.items if item.kind == kind and item.call is not None and item.call.id == call_id)


def model_time(measure):
    return [round(item.seconds, 3) for item in measure.items if item.kind == "model"]


class Measuring(unittest.TestCase):
    def books(self):
        files = [FIXTURES / "split.jsonl", FIXTURES / "unresolved.jsonl", FIXTURES / "background.jsonl"]
        return [journal.read(path) for path in files + journal.agent_files(FIXTURES / "background.jsonl")]

    def test_items_plus_idle_equal_span(self):
        windows = [(None, None), (at("10:00:40"), at("10:01:00")), (at("09:00:00"), at("10:07:30")), (at("10:05:00"), at("23:00:00"))]
        for book in self.books():
            for begin, end in windows:
                with self.subTest(book=book.path.name, begin=begin, end=end):
                    measure = intervals.measure(book, begin, end)
                    self.assertGreaterEqual(measure.span, 0)
                    self.assertGreaterEqual(measure.idle, -1e-6)
                    self.assertTrue(all(item.seconds >= 0 for item in measure.items))
                    self.assertAlmostEqual(sum(item.seconds for item in measure.items) + measure.idle, measure.span, places=6)

    def test_whole_span_of_a_transcript(self):
        measure = intervals.measure(journal.read(FIXTURES / "split.jsonl"))
        self.assertAlmostEqual(measure.span, at("10:10:20") - at("10:00:00"))

    def test_model_time_runs_from_the_last_arrival_to_the_message_end(self):
        measure = intervals.measure(journal.read(FIXTURES / "split.jsonl"))
        self.assertEqual(model_time(measure), [30.0, 10.0, 8.0, 8.0])

    def test_overlapping_calls_split_their_common_time(self):
        measure = intervals.measure(journal.read(FIXTURES / "split.jsonl"))
        self.assertAlmostEqual(spent(measure, "toolu_read", "tool"), 0.5)
        self.assertAlmostEqual(spent(measure, "toolu_run", "tool"), 59.5)

    def test_tool_running_while_the_message_streams_shares_with_the_model(self):
        measure = intervals.measure(journal.read(FIXTURES / "split.jsonl"))
        self.assertAlmostEqual(spent(measure, "toolu_early", "tool"), 1.0)
        self.assertAlmostEqual(spent(measure, "toolu_late", "tool"), 3.0)

    def test_time_between_a_reply_and_the_next_prompt_is_idle(self):
        measure = intervals.measure(journal.read(FIXTURES / "split.jsonl"))
        self.assertAlmostEqual(measure.idle, at("10:10:00") - at("10:01:40"))

    def test_background_run_takes_the_wait_and_not_the_work(self):
        measure = intervals.measure(journal.read(FIXTURES / "background.jsonl"))
        self.assertAlmostEqual(spent(measure, "toolu_bg", "background"), 300 - 9)
        self.assertAlmostEqual(spent(measure, "toolu_bg", "tool"), 1.0)
        self.assertAlmostEqual(spent(measure, "toolu_moved", "tool"), 120.0)
        self.assertAlmostEqual(spent(measure, "toolu_moved", "background"), 120 - 5)

    def test_wait_for_a_background_agent_and_for_its_resume(self):
        measure = intervals.measure(journal.read(FIXTURES / "background.jsonl"))
        self.assertAlmostEqual(spent(measure, "toolu_agent", "background"), 120 - 4)
        self.assertAlmostEqual(spent(measure, "toolu_send", "background"), 60 - 2)

    def test_window_clips_an_item(self):
        measure = intervals.measure(journal.read(FIXTURES / "split.jsonl"), at("10:00:40"), at("10:01:00"))
        self.assertAlmostEqual(measure.span, 20.0)
        self.assertAlmostEqual(spent(measure, "toolu_run", "tool"), 20.0)
        self.assertAlmostEqual(measure.idle, 0.0)

    def test_agent_file_outside_the_window_is_zero(self):
        book = journal.read(journal.agent_files(FIXTURES / "background.jsonl")[0])
        for begin, end in ((at("11:00:00"), at("12:00:00")), (at("08:00:00"), at("09:00:00"))):
            with self.subTest(begin=begin):
                measure = intervals.measure(book, begin, end)
                self.assertEqual((measure.items, measure.idle, measure.span), ([], 0.0, 0.0))

    def test_idle_between_two_legs_of_a_resumed_agent_is_not_work(self):
        book = journal.read(journal.agent_files(FIXTURES / "background.jsonl")[0])
        measure = intervals.measure(book)
        self.assertAlmostEqual(measure.idle, at("10:09:01") - at("10:08:00"))
        self.assertAlmostEqual(sum(item.seconds for item in measure.items), (at("10:10:00") - at("10:06:01")) - 61)

    def test_call_without_a_result_is_counted_to_the_next_entry(self):
        measure = intervals.measure(journal.read(FIXTURES / "unresolved.jsonl"))
        self.assertAlmostEqual(spent(measure, "toolu_cut", "tool"), 40.0)

    def test_question_to_the_user_is_idle(self):
        ask = journal.Call(id="toolu_ask", name="AskUserQuestion", input={}, start=110.0, end=400.0)
        book = journal.Journal(path=pathlib.Path("memory"), first=100.0, last=420.0, arrivals=[100.0, 400.0])
        book.messages = [journal.Message(id="m1", first=105.0, last=110.0, calls=[ask]), journal.Message(id="m2", first=410.0, last=420.0)]
        measure = intervals.measure(book)
        self.assertAlmostEqual(measure.idle, 290.0)
        self.assertEqual(model_time(measure), [10.0, 20.0])


GATE_PROJECT = """# Project

## 6. Gate checks

### Fast tier

```
./selftest.sh
python3 scripts/coverage_gate.py --run
```

## 7. Other

```
deploy-everything --now
```

| Question | Answer |
|---|---|
| Product code paths | app/, lib/*.py |
| Test paths | checks/ |
"""


class Classifying(unittest.TestCase):
    def setUp(self):
        self.root = pathlib.Path(os.path.realpath(tempfile.mkdtemp()))
        self.plain = rules.load(self.root)

    def tearDown(self):
        shutil.rmtree(self.root)

    def project(self, text):
        (self.root / "docs").mkdir(exist_ok=True)
        (self.root / "docs" / "PROJECT.md").write_text(text, encoding="utf-8")
        return rules.load(self.root)

    def bash(self, command, book=None):
        return rules.categories("Bash", {"command": command}, book or self.plain)

    def test_runner_token_behind_wrappers(self):
        for command in (
            "timeout 300 uv run --frozen pytest tests -q | tail -5",
            "python3 -m unittest selftest/test_x.py 2>&1 | tail -3",
            "cd app && npm test",
            "CI=1 go test ./... -run TestX",
            "cc-pertask run --plan docs/plans/p.md -- make lint",
        ):
            with self.subTest(command=command):
                self.assertEqual(self.bash(command), ("runs", "runs"))

    def test_runner_word_in_an_argument_is_not_a_run(self):
        self.assertEqual(self.bash("git commit -q -m 'fix pytest; rerun go test'"), ("records", "records"))
        self.assertEqual(self.bash("grep -rnE 'pytest|vitest' src | head -5"), ("read-search", "read-search"))

    def test_heredoc_body_is_ignored(self):
        note = "cat > notes.md <<'EOF'\nrun pytest and then go test ./...\nEOF"
        self.assertEqual(self.bash(note), ("docs", "docs"))
        script = "python3 - <<'EOF'\nprint('pytest -q; npm test')\nEOF"
        self.assertEqual(self.bash(script), ("other", "other"))

    def test_edit_and_run_command(self):
        self.assertEqual(self.bash("cat > src/app.py <<'EOF'\nx = 1\nEOF\npytest -q"), ("product code", "runs"))
        self.assertEqual(self.bash("sed -i '' 's/a/b/' tests/test_app.py && pytest -q tests/test_app.py"), ("test code", "runs"))

    def test_inline_script_goes_to_the_file_it_names(self):
        script = "python3 - <<'EOF'\nimport pathlib\np = pathlib.Path('tests/test_x.py')\np.write_text(p.read_text().replace('pytest', 'x'))\nEOF"
        self.assertEqual(self.bash(script), ("test code", "test code"))
        self.assertEqual(self.bash(script + "\npytest -q tests/test_x.py"), ("test code", "runs"))

    def test_output_kept_in_a_log_is_not_an_edit(self):
        self.assertEqual(self.bash("pytest -q > .claude/scratch/run.log 2>&1; echo $?"), ("runs", "runs"))
        self.assertEqual(self.bash("./build.sh > /tmp/build-output.txt 2>&1"), ("other", "other"))

    def test_edit_tools_go_by_path(self):
        cases = {
            "src/app.py": "product code",
            str(self.root / "src" / "deep" / "app.py"): "product code",
            "tests/test_app.py": "test code",
            "pkg/thing_test.go": "test code",
            "docs/plans/demo.md": "records",
            "tasks/10-x/01-y/NOTES.md": "records",
            "README.md": "docs",
            "/etc/hosts": "other",
        }
        for path, expected in cases.items():
            with self.subTest(path=path):
                self.assertEqual(rules.categories("Edit", {"file_path": path}, self.plain), (expected, expected))
        self.assertEqual(rules.categories("Write", {"file_path": "tests/test_new.py"}, self.plain)[0], "test code")

    def test_paths_from_project_rows(self):
        book = self.project(GATE_PROJECT)
        self.assertEqual(rules.categories("Edit", {"file_path": "app/main.py"}, book)[0], "product code")
        self.assertEqual(rules.categories("Edit", {"file_path": "lib/util.py"}, book)[0], "product code")
        self.assertEqual(rules.categories("Edit", {"file_path": "checks/check_main.py"}, book)[0], "test code")
        self.assertEqual(rules.categories("Edit", {"file_path": "tools/gen.py"}, book)[0], "other")
        self.assertEqual(rules.categories("Edit", {"file_path": "tests/test_app.py"}, book)[0], "other")

    def test_flags_replace_project_rows(self):
        self.project(GATE_PROJECT)
        book = rules.load(self.root, product="src/", tests="spec/, *_check.py")
        self.assertEqual(rules.categories("Edit", {"file_path": "src/a.py"}, book)[0], "product code")
        self.assertEqual(rules.categories("Edit", {"file_path": "app/main.py"}, book)[0], "other")
        self.assertEqual(rules.categories("Edit", {"file_path": "lib/a_check.py"}, book)[0], "test code")

    def test_gate_commands_become_runner_tokens(self):
        self.assertEqual(self.bash("./selftest.sh > .claude/scratch/s.log 2>&1"), ("other", "other"))
        for text in (GATE_PROJECT, GATE_PROJECT.replace("### Fast tier\n\n", "").replace("## 6. Gate checks", "## Gate checks (what must pass)")):
            book = self.project(text)
            with self.subTest(text=text[:40]):
                self.assertEqual(self.bash("./selftest.sh > .claude/scratch/s.log 2>&1", book), ("runs", "runs"))
                self.assertEqual(self.bash("python3 scripts/coverage_gate.py --run", book), ("runs", "runs"))
                self.assertEqual(self.bash("python3 scripts/other.py", book), ("other", "other"))
                self.assertEqual(self.bash("deploy-everything --now", book), ("other", "other"))

    def test_runs_flag_adds_tokens(self):
        book = rules.load(self.root, runs="selftest.sh, make smoke")
        self.assertEqual(self.bash("bash selftest.sh ~/.claude", book), ("runs", "runs"))
        self.assertEqual(self.bash("make smoke", book), ("runs", "runs"))
        self.assertEqual(self.bash("make docs", book), ("other", "other"))

    def test_reading_and_searching(self):
        for name in ("Read", "Grep", "Glob", "WebFetch"):
            self.assertEqual(rules.categories(name, {}, self.plain), ("read-search", "read-search"))
        for command in ("ls -la && git status --short", "grep -E 'a|b' src/x.py | head -3", "sed -n 1,40p install.sh; wc -l *.sh", "git log --oneline -5"):
            with self.subTest(command=command):
                self.assertEqual(self.bash(command), ("read-search", "read-search"))

    def test_commits_are_records(self):
        self.assertEqual(self.bash("git add src/a.py && git commit -q -m T01 && git log --oneline -1"), ("records", "records"))

    def test_agents_and_the_rest(self):
        for name in ("Agent", "SendMessage"):
            self.assertEqual(rules.categories(name, {}, self.plain), ("agents", "agents"))
        self.assertEqual(rules.categories("Skill", {"skill": "diagnose"}, self.plain), ("other", "other"))
        self.assertEqual(self.bash("docker compose up -d"), ("other", "other"))

    def test_every_answer_is_a_known_category(self):
        samples = [("Bash", {"command": "echo hi"}), ("Bash", {"command": ""}), ("Bash", {}), ("Edit", {}), ("mcp__x__y", {"a": 1}), ("Bash", {"command": "cat <<EOF\nunterminated 'quote"})]
        for name, arguments in samples:
            with self.subTest(name=name, arguments=arguments):
                for kind in rules.categories(name, arguments, self.plain):
                    self.assertIn(kind, rules.CATEGORIES)


def munged(path):
    return re.sub(r"[^A-Za-z0-9]", "-", str(path))


class Reporting(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tasks = importlib.import_module("tasks")
        cls.report = importlib.import_module("report")
        spec = importlib.util.spec_from_file_location("sessiontime_cli", SESSIONTIME_DIR / "cli.py")
        cls.cli = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.cli)
        cls.base = pathlib.Path(os.path.realpath(tempfile.mkdtemp()))
        cls.addClassCleanup(shutil.rmtree, cls.base)
        cls.repo = cls.base / "demo"
        cls.plan = cls.repo / "docs" / "plans" / "demo.md"
        cls.plan.parent.mkdir(parents=True)
        cls.git("init", "-q")
        cls.commit("10:00:00", [])
        cls.commit("10:05:00", ["T01"])
        cls.commit("10:10:30", ["T01", "T02", "T03"])
        agent = "background/subagents/agent-a0000000000000001.jsonl"
        cls.place("one", cls.repo, ["split.jsonl"])
        cls.place("one", pathlib.Path(str(cls.repo) + "2"), ["split.jsonl"], prefix="n")
        cls.place("two", cls.repo, ["background.jsonl", agent])
        cls.place("three", cls.repo / "packages" / "web", ["split.jsonl"])
        (cls.base / "none").mkdir()

    @classmethod
    def git(cls, *arguments, clock=""):
        quiet = {"GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_SYSTEM": os.devnull}
        who = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.invalid", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.invalid"}
        when = {name: f"2026-01-05T{clock}+00:00" for name in ("GIT_AUTHOR_DATE", "GIT_COMMITTER_DATE")} if clock else {}
        subprocess.run(["git", "-C", str(cls.repo), *arguments], check=True, capture_output=True, env={**os.environ, **quiet, **who, **when})

    @classmethod
    def commit(cls, clock, done):
        lines = [f"- [{'x' if task in done else ' '}] {task} step" for task in ("T01", "T02", "T03")]
        cls.plan.write_text("# Plan\n\n## Tasks\n" + "\n".join(lines) + "\n", encoding="utf-8")
        cls.git("add", "docs/plans/demo.md")
        cls.git("commit", "-q", "-m", clock, clock=clock)

    @classmethod
    def place(cls, projects, cwd, files, prefix=""):
        for name in files:
            text = (FIXTURES / name).read_text(encoding="utf-8").replace("/work/demo", str(cwd))
            target = cls.base / projects / munged(cwd) / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text.replace('"uuid":"', f'"uuid":"{prefix}'), encoding="utf-8")

    def gather(self, projects, *extra):
        return self.cli.gather(self.cli.parse(["--plan", str(self.plan), "--projects", str(self.base / projects), *extra]))

    def command(self, *arguments, cwd=None):
        return subprocess.run([sys.executable, str(SESSIONTIME_DIR / "cli.py"), *arguments], capture_output=True, text=True, cwd=cwd or self.repo)

    def timing(self, done):
        return [line for line in done.stdout.splitlines() if line.startswith("timing:")]

    def test_window_is_the_first_to_the_last_commit_of_the_plan(self):
        _, begin, end = self.gather("one")
        self.assertEqual((begin, end), (at("10:00:00"), at("10:10:30")))

    def test_marks_are_the_flips_in_the_history_of_the_plan(self):
        commits = self.tasks.plan_commits(str(self.repo), str(self.plan))
        self.assertEqual([moment for moment, _ in commits], [at("10:00:00"), at("10:05:00"), at("10:10:30")])
        marks = self.tasks.flips(str(self.repo), str(self.plan), commits)
        self.assertEqual(marks, [("T01", at("10:05:00")), ("T02, T03", at("10:10:30"))])

    def test_tasks_marked_in_one_commit_share_a_window(self):
        found = self.tasks.windows([("T01", at("10:05:00")), ("T02, T03", at("10:10:30"))], at("10:00:00"), at("10:10:30"))
        bounds = [(window.task, window.start, window.end) for window in found]
        self.assertEqual(bounds, [("T01", at("10:00:00"), at("10:05:00")), ("T02, T03", at("10:05:00"), at("10:10:30"))])

    def test_time_after_the_last_mark_has_a_window(self):
        found = self.tasks.windows([("T01", at("10:05:00"))], at("10:00:00"), at("10:10:30"))
        self.assertEqual([(window.start, window.end) for window in found], [(at("10:00:00"), at("10:05:00")), (at("10:05:00"), at("10:10:30"))])

    def test_mark_before_the_window_has_no_window(self):
        found = self.tasks.windows([("T01", at("09:00:00")), ("T02", at("10:10:30"))], at("10:00:00"), at("10:10:30"))
        self.assertEqual([(window.task, window.start, window.end) for window in found], [("T02", at("10:00:00"), at("10:10:30"))])

    def test_categories_of_the_main_session(self):
        summary, _, _ = self.gather("one")
        main = summary.seconds["main"]
        self.assertAlmostEqual(main["runs"], 89.5)
        self.assertAlmostEqual(main["read-search"], 12.5)
        self.assertAlmostEqual(main["reply"], 18.0)
        self.assertAlmostEqual(summary.active["main"], 120.0)
        self.assertAlmostEqual(summary.idle, 500.0)
        self.assertEqual(summary.active["agents"], 0.0)

    def test_session_of_a_neighbour_repository_is_left_out(self):
        summary, _, _ = self.gather("one")
        self.assertEqual(len(summary.sheets), 1)

    def test_session_started_in_a_subdirectory_is_counted(self):
        summary, _, _ = self.gather("three")
        self.assertAlmostEqual(summary.seconds["main"]["runs"], 89.5)

    def test_runs_per_task(self):
        summary, _, _ = self.gather("one")
        rows = {task: (round(run, 3), round(whole, 3)) for task, run, whole in summary.per_task}
        self.assertEqual(rows, {"T01": (89.5, 100.0), "T02, T03": (0.0, 20.0)})

    def test_agents_have_their_own_column(self):
        summary, _, _ = self.gather("two")
        self.assertAlmostEqual(summary.seconds["agents"]["runs"], 49.0)
        self.assertAlmostEqual(summary.active["agents"], 178.0)
        self.assertAlmostEqual(summary.seconds["main"]["runs"], 302.0)
        self.assertEqual(sorted(sheet.role for sheet in summary.sheets), ["agents", "main"])

    def test_waiting_for_agents_is_not_active_time(self):
        summary, _, _ = self.gather("two")
        self.assertAlmostEqual(summary.seconds["main"]["agents"], 265.0)
        self.assertAlmostEqual(summary.active["main"], 365.0)

    def test_unclassified_time_names_its_commands(self):
        summary, _, _ = self.gather("two")
        self.assertAlmostEqual(summary.seconds["main"]["other"], 29.0)
        self.assertEqual([round(value, 3) for value, _ in summary.longest_other], [29.0])

    def test_runs_flag_reaches_the_report(self):
        summary, _, _ = self.gather("two", "--runs", "selftest.sh")
        self.assertAlmostEqual(summary.seconds["main"]["runs"], 331.0)
        self.assertEqual(summary.longest_other, [])

    def test_from_and_to_replace_the_window(self):
        summary, begin, end = self.gather("two", "--from", "2026-01-05T10:00:00+00:00", "--to", "2026-01-05T10:20:00+00:00")
        self.assertEqual((begin, end), (at("10:00:00"), at("10:20:00")))
        self.assertAlmostEqual(summary.seconds["main"]["other"], 355.0)
        self.assertAlmostEqual(summary.idle, 0.0)

    def test_window_can_end_now(self):
        _, begin, end = self.gather("one", "--to", "now")
        self.assertEqual(begin, at("10:00:00"))
        self.assertLess(abs(end - time.time()), 60)

    def test_every_transcript_adds_up(self):
        for projects in ("one", "two", "three"):
            summary, _, _ = self.gather(projects)
            for sheet in summary.sheets:
                with self.subTest(projects=projects, sheet=sheet.name):
                    self.assertAlmostEqual(sum(item.seconds for item in sheet.measure.items) + sheet.measure.idle, sheet.measure.span)

    def test_command_prints_one_timing_line(self):
        done = self.command("--plan", "docs/plans/demo.md", "--projects", str(self.base / "one"))
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(len(self.timing(done)), 1)

    def test_no_transcript_is_said_and_is_not_a_failure(self):
        with self.assertRaises(self.tasks.Unmeasurable):
            self.gather("none")
        measured = self.command("--plan", "docs/plans/demo.md", "--projects", str(self.base / "one"))
        done = self.command("--plan", "docs/plans/demo.md", "--projects", str(self.base / "none"))
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(len(self.timing(done)), 1)
        self.assertNotEqual(self.timing(done), self.timing(measured))

    def test_plan_outside_a_repository_is_not_a_failure(self):
        loose = self.base / "loose.md"
        loose.write_text("- [x] T01 step\n", encoding="utf-8")
        with self.assertRaises(self.tasks.Unmeasurable):
            self.cli.gather(self.cli.parse(["--plan", str(loose), "--projects", str(self.base / "one")]))
        done = self.command("--plan", str(loose), "--projects", str(self.base / "one"), cwd=self.base)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(len(self.timing(done)), 1)

    def test_date_that_cannot_be_read_is_not_a_failure(self):
        done = self.command("--plan", "docs/plans/demo.md", "--projects", str(self.base / "one"), "--from", "yesterday")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(len(self.timing(done)), 1)


if __name__ == "__main__":
    unittest.main()
