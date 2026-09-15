---
name: run-task
description: Procedure for one plan task in a fresh context — what to read, do, verify, mark and log, then stop. Preloaded into the worker agent; usable directly as /run-task <PLAN.md> <T##> for a single task.
argument-hint: <PLAN.md path> <T##>
---

# run-task

This context exists for one task: `<plan path> <T##>`. Everything else in the plan belongs to other contexts.

## Read (and only this)

1. The plan: `## Goal`, `## Decisions`, `## Assumptions`, `## Out of scope`, the last 10 lines of `## Log`, and the line of `<T##>`.
2. If the plan sits in `tasks/<phase>/<NN>-<slug>/`: that task's `task.txt` (CONTEXT paths are the files to open first) and `tasks/PROTOCOL.md` if present.
3. `docs/PROJECT.md` §5 (unattended policy) and §6 (gate checks).
Do not read other tasks' details unless `<T##>` names them as a dependency.

## Do

- `(needs confirmation)` on the line, or an action from PROJECT.md's "must become BLOCKED" column → mark `- [!] BLOCKED: needs confirmation`, Log line, stop.
- Otherwise do the task by the `/run` rules: `scout`/`test-runner`/`researcher` for noise, no questions, no scope creep, `/diagnose` after the first non-trivial failure — never an unchanged retry.
- Run the task's verify command and the gate checks.
  - Pass → `- [x]`, append `- <time> <T##> done: <one line>` to `## Log`, commit when the repo is git: stage by path (`git add <files you changed> <plan file>`), never `git add -A`/`-u` — a repository with submodules would otherwise commit a moved submodule pointer, and an untracked marker file (like `E2E.RED`) would be swept in. Message in the repository's convention (`tasks/PROTOCOL.md` if present, else `<T##>: <summary>`). If a pre-commit hook rejects the commit, that is a rule of the repository: read its message, fix the cause (branch, message language, staged path), do not bypass with `--no-verify`.
  - Fail → `/diagnose`. Still failing → leave `- [ ]`, append `- <time> <T##> open: <root cause or best hypothesis, with evidence>` so the next context starts from evidence, not zero.
- A decision made alone → one line under `## Assumptions`.

## Stop

Stop as soon as `<T##>` is `[x]` or `[!]`, or an `open:` line with evidence is recorded. Do not take another task.
