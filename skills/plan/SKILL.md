---
name: plan
description: Interview first, then write an executable plan file. Use before any task that touches more than one file or has any open decision. Collects every question up front so execution never stops to ask.
argument-hint: <what to build or change>
disable-model-invocation: false
---

# /plan

Goal: after this skill finishes, `/run` can execute for hours without a single question.

Two entry points:
- `/plan <free text>` — a task that has no directory yet. If the project has a `tasks/` tree, create the task directory first with `/task` (the tree is the ledger; a plan without a task is work nobody can find later), then continue here.
- `/plan tasks/<phase>/<NN>-<slug>` — a task directory exists. `task.txt` is the source: GOAL → plan Goal; VERIFY items → Acceptance criteria (each with the command that proves it, HUMAN items marked and excluded from what `/run` may close); `+` lines → Tasks; `−` lines → Out of scope verbatim; CONTEXT → the files `scout` reads first; DEPENDS → check each dependency's `labels.txt` has `status:done` before writing the plan, otherwise the plan's first task is `[!] BLOCKED: depends on <path>`. The plan file is `PLAN.md` inside the task directory. Set `labels.txt` `status:in_progress` when the plan goes `running`.

## Phase 1 — Reconnaissance (no questions yet)

1. Read the task: `$ARGUMENTS`. If the project has `tasks/`, read `tasks/README.md`, `tasks/PROTOCOL.md` (if present) and `tasks/GOAL.md` — they outrank this skill where they differ. Read `docs/PROJECT.md` if it exists: gate checks, unattended policy, ledger and "Decided by the agent" are already settled — do not re-ask them. If it does not exist and the task touches more than one module, suggest `/intake` first, then continue.
2. Delegate discovery to the `scout` subagent: relevant files, entry points, tests, build/test commands, config, existing conventions. Do not read the whole repo yourself.
3. Pin the stack: language and framework versions, lockfile, CI config. Write them down; the plan will cite them.
4. List every decision point you can see. For each one, first try to answer it from the repo, the docs, or the user's stated preferences. Only what survives becomes a question.

## Phase 2 — The interview (all questions, once)

Ask through AskUserQuestion. Pack up to 4 questions per call; use several calls back to back if needed. All calls happen now, none later.

Rules for each question:
- It changes what you would build. If both answers lead to the same code, do not ask.
- Offer concrete options, the recommended one first, marked "(Recommended)".
- Cover at minimum: scope boundaries (what is explicitly out), acceptance criteria, irreversible actions you may or may not take unattended, external systems you may touch, what to do when a test suite is already red before you start.
- Ask about priorities if the task list will be long: what must be done first if time runs out.

Do not ask about: naming, formatting, file layout, library choice when the repo already uses one, anything answerable by reading.

## Phase 3 — Write the plan

Path: `PLAN.md` in the task directory when one exists, otherwise `docs/plans/<slug>.md`. Format, exactly:

```
---
status: draft
created: <YYYY-MM-DD>
---
# <title>

## Goal
One paragraph. What is true when this is done.

## Acceptance criteria
- [ ] AC1 <observable check, with the command that proves it>
- [ ] AC2 ...

## Stack
<language x.y, framework x.y, key libs x.y — the versions actually pinned>

## Decisions
- <question> -> <answer the user gave>

## Assumptions
- <anything you decided alone; to be reviewed>

## Out of scope
- ...

## Tasks
- [ ] T01 <one action, ≤ ~1 hour, ends with a verifiable state> — verify: `<command>`
- [ ] T02 ...

## Log
```

Task rules:
- `T00` is always the baseline: run the project's gate checks once before any edit and record the pre-existing state in `## Log` (which tests were already red). New failures are then distinguishable from old ones. When `docs/PROJECT.md` §7 or a pre-commit hook forbids commits on the current branch, `T00` also creates the plan's branch (name per the repository's pattern) and `## Decisions` records `Branch: <name>`.
- Every task ends in a verifiable state and names the command that verifies it. The verify line includes the gate checks from `docs/PROJECT.md`, not only the task-local test.
- Architecture or layering decisions become a check, not a paragraph: a task that introduces a boundary also adds the script that enforces it (`import-linter` contract for Python) to the gate checks.
- Order by dependency, then by the user's priority answer.
- Anything in the "Must become BLOCKED" column of `docs/PROJECT.md` is a separate task, placed last, marked `(needs confirmation)` so `/run` BLOCKs it instead of guessing.
- A task that adds or restores a ledger capability also updates the ledger row in `docs/PROJECT.md`.
- Prefer 20 small tasks over 5 vague ones.

## Phase 4 — Hand-off

Show the plan path and the task count. Ask exactly one final AskUserQuestion:
"Start in a clean window" (Recommended) / "Start here, now" / "I will edit the file first".

- "Clean window": set `status: running`, then print exactly two lines and stop:
  `/clear`
  `/run docs/plans/<slug>.md`
  The interview and reconnaissance noise stays out of the execution context; `/clear` costs nothing and the plan file carries everything. The SessionStart hook re-injects the plan after `/clear`.
- "Start here, now": set `status: running` and continue immediately as `/run` would. Only sensible for plans under ~10 tasks.
- "Edit first": stop. The user will run `/run docs/plans/<slug>.md` later (or `cc-night` for an unattended run).
