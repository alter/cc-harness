---
name: plan
description: Interview first, then write an executable plan file. Use before any task that touches more than one file or has any open decision. Collects every question up front so execution never stops to ask.
argument-hint: <what to build or change>
disable-model-invocation: false
model: opus
---

# /plan

Goal: after this skill finishes, `/run` can execute for hours without a single question.

Two entry points:
- `/plan <free text>` — a task that has no directory yet. If the project has a `tasks/` tree, create the task directory first with `/task` (the tree is the ledger; a plan without a task is work nobody can find later), then continue here.
- `/plan tasks/<phase>/<NN>-<slug>` — a task directory exists. `task.txt` is the source: GOAL → plan Goal; VERIFY items → Acceptance criteria (each with the command that proves it, HUMAN items marked and excluded from what `/run` may close); `+` lines → Tasks; `−` lines → Out of scope verbatim; CONTEXT → the files `scout` reads first; DEPENDS → check each dependency's `labels.txt` has `status:done` before writing the plan, otherwise the plan's first task is `[!] BLOCKED: depends on <path>`. The plan file is `PLAN.md` inside the task directory. Set `labels.txt` `status:in_progress` when the plan goes `running`.

## Phase 1 — Reconnaissance (no questions yet)

1. Read the task: `$ARGUMENTS`. If the project has `tasks/`, read `tasks/README.md`, `tasks/PROTOCOL.md` (if present) and `tasks/GOAL.md` — they outrank this skill where they differ. Read `docs/PROJECT.md` if it exists: gate checks, unattended policy, ledger, "Decided by the agent" and the row `Test coverage level` of §6 are already settled — do not re-ask them. No row, or no file, means level `critical`. If it does not exist and the task touches more than one module, suggest `/intake` first, then continue.
1a. If `scripts/project_check.py` exists, run it. A report that `docs/PROJECT.md` is out of date (signal files appeared or disappeared since its fingerprint) turns into questions for the interview below: "a `.golangci.yml` appeared — add `golangci-lint run` to the fast tier?", "`requirements.txt` is gone — what replaced it?". After the answers, update the sections they touch and run `--refresh-fingerprint`. While a plan is already `running` nobody is asked: the drift is recorded under `## Assumptions` and in the night report, and work continues on what is declared.
2. Delegate discovery to the `scout` subagent: relevant files, entry points, tests, build/test commands, config, existing conventions. Do not read the whole repo yourself.
3. Pin the stack: language and framework versions, lockfile, CI config. Write them down; the plan will cite them.
3a. Study before designing. For every technology the task uses that has no `docs/tech/<name>@<version>.md` yet — a library the code will call directly, a database, a protocol, an external API — the plan's first tasks after `T00` are research tasks, one per technology, done through `researcher`/`web-researcher`. Each produces `docs/tech/<name>@<version>.md` for the pinned version: the official documentation of that version (the methods used, their **types, limits and defaults** — an `int` that arrives as a `bigint` is a design failure found too late), known issues from the project's issue tracker for that version, Stack Overflow and Reddit threads, tips and pitfalls. Every item carries its URL; an item without one is not written. Design and implementation tasks list the file in CONTEXT, and DATA records take types and ranges from it. A small library gets five lines; a database or a framework gets a real file. Transitive dependencies get none.
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
- D1 <question> -> <answer the user gave>

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
- Every acceptance criterion carries an `AC<n>` id and every decision a `D<n>` id. The verifier maps each id to evidence (`path:line`, a test, or a command with its exit code); a decision is checked for *how* the work was done, not only *that* it was done. An id with no evidence is an unproven claim.
- `T00` is always the baseline: when any task changes logic, run each of the project's gate checks once before any edit through `cc-pertask record --plan <plan> -- <command>` — one run is both the baseline and the measurement the per-task limit works from — and record the pre-existing state in `## Log` (which tests were already red, and at levels `standard` and `release` the coverage percentage from the tool — there the ratchet, `python3 scripts/coverage_gate.py --run`, runs at `T00` and again when the plan closes). New failures are then distinguishable from old ones. When `docs/PROJECT.md` §7 or a pre-commit hook forbids commits on the current branch, `T00` also creates the plan's branch (name per the repository's pattern) and `## Decisions` records `Branch: <name>`.
- Which tasks carry a test is decided here, by the row `Test coverage level`, and fixed in the task line; nothing downstream reopens it. At `standard` and `release` every task that changes behaviour names the test that proves it. At `critical` a task that changes behaviour in critical code — the contract's definition: money, access rights, data that can be lost or corrupted, the project's own non-trivial logic — names its test, and every other logic task says `no test (critical level: <reason>)` with the reason in two or three words (`SDK call`, `wiring`, `layout`). A task that fixes a bug names its regression test at every level. A named test is seen failing before the change, or the task is not done. A task that only adds tests is fine and belongs to `/test`; raising coverage is never added to a plan on your own judgment.
- Every task ends in a verifiable state and names the command that verifies it. The verify line of a task that changes logic is the task's own test, when the line names one, followed by the gate commands from `docs/PROJECT.md`, each written as `cc-pertask run --plan <plan> -- <command>`: the commands whose measured times fit the per-task limit (30 seconds, or the `Per-task limit` row of §6) run before the mark, the others print `SKIPPED (per-plan)` and are owed before a push or a deploy and at the plan's close. The ratchet command is one of those gate commands only at level `release`; at `critical` it is not written into any verify line, even when an older `docs/PROJECT.md` still lists it. A task without logic (copy, labels, styles, templates, docs, config values) verifies with the narrow check for the touched file — a grep, a render, a lint of that file — never the gate checks or the full suite: the verify line freezes when the plan runs and nothing downstream can narrow it.
- A no-logic plan — every task changes only copy, legal text, labels, styles, templates, docs or config values — has no task that runs the gate set, e2e, integration or a local CI run, under any name ("checks before sending", "pre-push", "final verification"), and no such command in `## Decisions` or in an acceptance criterion. It closes on its narrow checks. The only exception is the owner asking for that run in the interview, recorded as their decision with their reason; a heavy run is never added on your own judgment.
- Architecture or layering decisions become a check, not a paragraph: a task that introduces a boundary also adds the check that enforces it — the tool the project already uses for boundaries, or a short script that reports `path:line [rule] message` — to the gate checks.
- Order by dependency, then by the user's priority answer.
- Anything in the "Must become BLOCKED" column of `docs/PROJECT.md` is a separate task, placed last, marked `(needs confirmation)` so `/run` BLOCKs it instead of guessing.
- A task that adds or restores a ledger capability also updates the ledger row in `docs/PROJECT.md`.
- Prefer 20 small tasks over 5 vague ones.

## Phase 4 — Hand-off

Show the plan path and the task count. Ask exactly one final AskUserQuestion:
"Start in a clean window" (Recommended) / "Start here, now" / "I will edit the file first".

- "Clean window": leave `status: draft` (the Stop hook blocks any turn that ends while a plan is `running` with open tasks, so `running` here would trap this window; `/run` sets `running` in the clean one), then print exactly two lines and stop:
  `/clear`
  `/run docs/plans/<slug>.md`
  The interview and reconnaissance noise stays out of the execution context; `/clear` costs nothing and the plan file carries everything. `/run` flips `draft` to `running`.
- "Start here, now": set `status: running` and continue immediately as `/run` would. Only sensible for plans under ~10 tasks.
- "Edit first": stop. The user will run `/run docs/plans/<slug>.md` later (or `cc-night` for an unattended run).
