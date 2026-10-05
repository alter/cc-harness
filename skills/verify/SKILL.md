---
name: verify
description: Independent verification of a task directory by a context that wrote neither the code nor its tests. Produces VERIFY.md in the tree's format (verifier line, reproduce-from-clean-state, what was not checked, reverse control) and sets verify:passed|failed. Use after a task reaches status:done or review.
argument-hint: <task directory path>
---

# /verify

Independence is the whole point. If this session wrote any of the code or tests under review, do not verify here: delegate the entire job to the `verifier` subagent (fresh context) with the task path, and relay its result. Never set `verify:passed` on your own work.

## 1. Read, do not trust

- `tasks/README.md` (the `verify:passed` rule), `tasks/PROTOCOL.md` if present, `tasks/GOAL.md`.
- The task's `task.txt` — every VERIFY item, every `+` and `−` line in SCOPE, the OUTCOME. With `format:2` every `+` line is an id `S<n>` and every VERIFY item `n.` is `V<n>`.
- The decisions the work had to follow: `D<n>` in the task's `PLAN.md`, `tasks/DECISIONS.md` entries the task cites, `## Decisions` of the plan. A decision says *how*; it is checked as strictly as *what*.
- `NOTES.md`, existing `VERIFY.md`, commit messages — as claims to test, not as evidence.

## 2. Does the OUTCOME exist?

For each artefact named in OUTCOME: `test -f`, `git cat-file -e HEAD:<path>` (on disk vs in a commit are different facts), the count matches, the recorded run opens. If the OUTCOME lives outside the repository (a machine at a provider, a phone, a store listing), it cannot be confirmed here: say so, item by item, and do not pass it.

## 3. Reproduce from a clean state

Every VERIFY item gets a command a third party can run with a fresh checkout, empty environment, no variables exported by hand. Run them yourself. Prefer a throwaway location (`.claude/scratch/`, `/tmp`) and never modify the repository. If a check depends on the author's shell state, it fails — that is exactly the incident this rule was written against.

Items marked `[full]` are not run here: they belong to the full run. Take their result from the latest `FULLRUN-*.md` next to the task (or its plan), cite the file and the row. No report, or a report older than the last commit of the task → `cannot verify here`, never `pass`. A milestone (`gate:yes`) is not passed while that report is red.

## 3a. Every requirement, one by one

Tests passing is not the same as the requirement being met. For each id — every `S<n>`, every `V<n>`, every `D<n>` the work had to follow — find the evidence yourself and write it down:

- the `path:line` where the requirement is implemented, read in this session; or
- the command you ran and its exit code; or
- the test that covers it, as `path:line`, and the command that ran it.

A decision is met only when the code does it the way the decision says. "Use a short transaction after the API call" is failed by code that calls the API inside the transaction, even with every test green. A requirement that you cannot point at is `fail` or `cannot verify here` — never `pass` by inference.

## 4. Reverse control

At least one check must be made red on purpose: mutate the input, break the ordering, remove the guard — in a scratch copy — and record the red output. A suite that stays green under mutation does not test what it claims; write that down as a finding, with the mutation.

## 5. Write `VERIFY.md` in the task directory

Language of the tree. Required parts, in the tree's wording (Russian trees: `Проверил:`, `## Как воспроизвести`, `## Что не проверено`; English trees: `Verifier:`, `## How to reproduce`, `## What was not checked`):

```
<Verifier line>: <who>, <date>; what this context did NOT do — did not write
<files>, did not write <tests>; what it did run.

## Per-item verdict
| # | Item | Result |   pass / fail / cannot verify here (why)

## Requirement evidence
- S1: <path:line> — <what is there>
- V2: `<command>` exit <code>
- D1: <path:line> — <how the code follows the decision>, or fail: <where it does not>

## <Reproduce from a clean state>
commands, from an empty environment, with the expected output stated

## <Reverse control>
what was mutated, where (scratch copy), and the red output

## <What was not checked>
non-empty, always. Boundaries, edge values, environments not available, items
outside the repository, anything inferred rather than observed.

## Verdict
verify:passed or verify:failed for <task path>, one sentence why.
```

Every number carries a source: path, command, log line. Plain "clean result" is reported as plainly as a finding.

## 6. Labels and neighbours

- Set `verify:passed` or `verify:failed` in `labels.txt`. Touch nothing else in `labels.txt`.
- If OUTCOME does not exist but `status:done` is set: do not change `status` yourself; record the mismatch in `VERIFY.md` and in the verdict, so the owner or `/run` moves it back.
- Findings outside this task's SCOPE go into `NOTES.md` of the owning task or a one-line proposal for a new task — never silently fixed.
- Run `python3 tasks/check.py`; zero problems.
