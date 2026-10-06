---
name: run-task
description: Procedure for one plan task in a fresh context — what to read, do, verify, mark and log, then stop. Preloaded into the worker agent; usable directly as /run-task <PLAN.md> <T##> for a single task.
argument-hint: <PLAN.md path> <T##>
---

# run-task

This context exists for one task: `<plan path> <T##>`, or a whole child task given as `<task dir>` (a part of a split task, run in its own worktree). Everything else belongs to other contexts.

For `<task dir>`: the task's `task.txt` is the plan — its `+` lines are the work, its `[fast]` VERIFY items are the verify commands, its WRITE-SET is the only code you may change. Commit in the worktree you were started in, run `python3 tasks/scope_check.py <task dir>`, set `status:done` in its `labels.txt` only when every `[fast]` item passed, and end the two return lines with `branch: <current branch name>`.

## Read (and only this)

1. The plan: `## Goal`, `## Decisions`, `## Assumptions`, `## Out of scope`, the last 10 lines of `## Log`, and the line of `<T##>`.
2. If the plan sits in `tasks/<phase>/<NN>-<slug>/`: that task's `task.txt` (CONTEXT paths are the files to open first) and `tasks/PROTOCOL.md` if present.
3. `docs/PROJECT.md` §5 (unattended policy) and §6 (gate checks).
Do not read other tasks' details unless `<T##>` names them as a dependency.

## Do

- `(needs confirmation)` on the line, or an action from PROJECT.md's "must become BLOCKED" column → mark `- [!] BLOCKED: needs confirmation`, Log line, stop.
- Otherwise do the task by the `/run` rules: `scout`/`test-runner`/`researcher` for noise, no questions, no scope creep, `/diagnose` after the first non-trivial failure — never an unchanged retry.
- Run the task's verify command, the tests that cover the files you touched, and the gate checks (the coverage ratchet is one of them when `docs/PROJECT.md` §6 lists it). When the fast tier in §6 carries `#:` attributes (budget, report, list), run it through `cc-fullrun --tier fast --out <plan dir>`: the same budget, census and duplicate check as the full run, reports `FASTRUN-*` kept apart. A `dup`, `empty` or `timeout` there is a failed gate, not a pass.
  - Pass → `- [x]`, append `- <time> <T##> done: <one line>` to `## Log`, commit when the repo is git: stage by path (`git add <files you changed> <plan file>`), never `git add -A`/`-u` — a repository with submodules would otherwise commit a moved submodule pointer, and an untracked marker file (like `E2E.RED`) would be swept in. Message in the repository's convention (`tasks/PROTOCOL.md` if present, else `<T##>: <summary>`). If a pre-commit hook rejects the commit, that is a rule of the repository: read its message, fix the cause (branch, message language, staged path), do not bypass with `--no-verify`.
  - In a task tree, after the commit: `python3 tasks/scope_check.py <task dir>` (a tree without it: `python3 ~/.claude/project-template/tasks/scope_check.py <task dir>`) compares the commit with the task's WRITE-SET (CONTEXT for legacy tasks). A file outside it is either moved out into a new task, or — when the task cannot be done without it — added to WRITE-SET with one line in `NOTES.md` saying why. A silent edit outside the write set is never closed.
  - Before `[x]`: `python3 ~/.claude/hooks/integrity-check.py --base <T00 commit> --plan <plan>` — an added suppression (`noqa`, `//nolint`, `#[allow]`, `|| true`, `ignore_errors`, a skipped test), a changed linter/test/type config, a deleted test or a lowered coverage floor is either undone or declared under `## Assumptions` with its path and reason. `stop-guard` runs the same check and will not let a running plan stop over an undeclared one.
  - After any commit that touches a dependency manifest: `python3 tasks/tech_check.py` (or `~/.claude/project-template/tasks/tech_check.py` without a task tree). A new direct dependency needs `docs/tech/<name>@<version>.md` before the task closes; a version bump does not.
  - Fail → `/diagnose`. Still failing → leave `- [ ]`, append `- <time> <T##> open: <root cause or best hypothesis, with evidence>` so the next context starts from evidence, not zero.
- A decision made alone → one line under `## Assumptions`.

## Stop

Stop as soon as `<T##>` is `[x]` or `[!]`, or an `open:` line with evidence is recorded. Do not take another task.
