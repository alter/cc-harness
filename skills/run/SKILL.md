---
name: run
description: Execute a plan file to completion without asking questions. Use to start or resume unattended work on docs/plans/<slug>.md or a task directory's PLAN.md. Marks tasks done only after their verify command passes.
argument-hint: <path to plan, or empty for the single running plan; add "delegate" to hand tasks to worker subagents>
---

# /run

Input: `$ARGUMENTS` — a plan path or a task directory (then its `PLAN.md`). If empty, find the one file under `docs/plans/` or `tasks/**/PLAN.md` with `status: running`; if there is exactly one `status: draft` and none running, use it and set it to running.

## One session, the whole plan (default)

You do the tasks yourself, one at a time, in this session, by the `run-task` procedure (read the task line, `## Decisions`, `## Assumptions`, `## Out of scope`, the last Log lines; do; run the verify command; mark; log; commit). A subagent's "done" (worker, test-runner, scout) never closes a task: the task's own `verify:` command, run by you and exiting 0, does. The session lives as long as the plan; the plan file is the state, the conversation is the memory of *why*. Do not `/clear`, do not `/compact` by hand, do not spawn a fresh session per task.

Keep noise out of this context, because this context is what the whole night runs on:

- Searching the repo → `scout` (paths with line ranges come back; Read them yourself before use).
- Running tests, builds, linters, long commands → `test-runner` (`COMMAND:` + exit code + PASS/FAIL come back; a result without them is rerun).
- Reading docs, changelogs, unfamiliar subsystems → `researcher` (EVIDENCE with path:line or URL comes back).
- Reviewing a diff before a risky commit → `reviewer`.
- You Read only what you will edit, and only the window you need (Grep first; the read-guard refuses whole files over 500 lines).

Between tasks: nothing to do. The next task starts from the plan line, not from a recap of the previous one. If you notice you are re-reading the plan header or restating earlier tasks, stop — that is the context bloating, not progress.

## Delegate (only when the user says "delegate")

You are the coordinator; you implement nothing. For each unchecked task, spawn the `worker` subagent (fresh context, not a fork) with exactly `<plan path> <T##>`. It does the task by the `run-task` procedure and returns two lines. You then Grep only that task's line in the plan to confirm the mark, and take the next one. Run workers one at a time; several only when the tasks live in different task directories (different `task.txt`) — the ownership boundary from `tasks/ROLES.md`.

Loop until no `- [ ]` remains:

1. `Grep -n '^- \[ \] ' <plan>` → first unchecked task id. No other reading.
2. Spawn `worker` with `<plan path> <T##>`.
3. On return, run the task's `verify:` command yourself (Bash, or `test-runner` when the output is long). A worker's "done" — and its `[x]` in the plan — is a claim, not evidence. Exit 0 → keep `[x]`, next. Non-zero → set the line back to `- [ ]`, append `- <time> <T##> open: worker reported done, verify exits <code>: <first failing line>` and treat it as an open task below. `[!]` → next. Still `- [ ]` with an `open:` Log line → spawn `worker` once more with the same task and the words "second attempt: start from the open: evidence in Log". Still open after that → mark `- [!] BLOCKED: two attempts failed, see Log`, append a Log line, next.
4. A worker's report is a claim: what decides is the verify command you ran, then the plan file — never the two lines.
5. Never Read source files, tool outputs or transcripts in delegate mode.

### Parallel parts of a split task

A task directory whose children carry `split:contract`, `split:part` and `split:assembly` (format 2) runs as one unit: `/run tasks/<phase>/<NN>-<slug> delegate`. `tasks/check.py` has already proved that sibling write sets do not overlap and that parts sharing a file depend on the contract; run it first and stop with `[!]` if it reports a problem.

1. The `split:contract` child first, one `worker`, as above.
2. Then every `split:part` child whose `depends:` are all `status:done`, **in parallel**: one `worker` per part, each spawned with `isolation: "worktree"` and the prompt `<child task dir>` — the worker does that task by its `task.txt`, runs its `[fast]` checks, commits in its worktree and returns two lines plus its branch. At most `CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS` at once.
3. Merge each returned branch into the current branch with `git merge --no-ff <branch>`, one at a time. A conflict means the write sets were wrong: `git merge --abort`, mark that part `status:blocked` with `BLOCKED.md` naming the conflicting paths, continue with the other parts. Never resolve a conflict by picking a side. A merged branch is done with: `git worktree remove <path>` and `git branch -d <branch>` (both refuse to drop unmerged work).
4. After every merge, run that part's `[fast]` VERIFY items yourself on the merged tree. Red → the part goes back to `in_progress` with an `open:` line in its `NOTES.md`.
5. The `split:assembly` child last, one `worker`, on the merged tree: it runs the whole fast tier.
6. `reviewer` and `/verify` run once, on the parent, after the assembly — never per part.

Trade: every worker is a cold start (system prompt + tools + CLAUDE.md + AGENTS.md + PROJECT.md + plan + task ≈ 10–20k tokens of cache write) and knows nothing of *why* the previous task was done the way it was. Measured on a three-task plan of small coupled tasks (one run each, Sonnet 5.5): one session $0.22 and 39 s, delegate $0.59 and 104 s. Delegate pays off where parts run in parallel or the plan is too long for one context; the default mode for everything else.

## Review loop

`reviewer` runs once per parent task — a plan's task that changed behaviour, or a split task after its assembly — never per part. It returns findings; what happens to each is fixed:

- **CONFIRMED with a FIX line** is a directive, not a question. Add a fix task right after the reviewed one: `- [ ] T<NN>a fix: <FIX line> — verify: <the REPRODUCTION command>` (in a task tree: a child task with that VERIFY item). The reproduction is the regression test: seen red now, it closes the fix task only when it is green. Nobody argues with a reproduced finding; the implementer fixes it.
- **A directive that contradicts a `D<n>` decision, the task's SCOPE or `docs/PROJECT.md`** is not executed. Record it under `## Assumptions` as `reviewer: <FIX> — not applied, contradicts D<n>`; when it points at a real defect the decision causes, the task becomes `[!] BLOCKED: reviewer finding conflicts with D<n>` for the owner.
- **PLAUSIBLE** (no reproduction) is an observation: one line in `NOTES.md` or `## Log`, no task, no fix.
- After the fix tasks close, `reviewer` runs again **only on the fixed findings** (their WHERE lines and the fix diff), not on the whole change. At most two rounds; a finding still CONFIRMED after the second fix → `[!] BLOCKED: reviewer finding survives two fixes`, with both reproductions in the Log.
- `/verify` follows the review, in another context, on the same parent task.
- A task whose SECURITY block adds a sink, or whose DATA adds an `interpretable=yes` field, also gets `/attack <task dir>` after the review; its CONFIRMED findings enter this same loop. At night `cc-night` runs `/attack milestone` after the full run (`CC_NIGHT_ATTACK=0` turns it off).
- When the reviewed diff touches code that talks to PostgreSQL (a driver import, SQL, a migration, an ORM model), `/pgsql-slow-queries diff` runs beside the reviewer; its CONFIRMED findings become fix tasks the same way, a transaction held across an outside wait blocks the task. At night `cc-night` runs it on the whole project when the repository uses PostgreSQL (`CC_NIGHT_PGSQL=0` turns it off).

## What is not allowed

- Asking the user anything. The interview is over.
- `git stash`, `reset --hard`, `clean`, branch switching. Blocked by user changes → `[!] BLOCKED`, next task.
- Building anything the ledger in `docs/PROJECT.md` marks `absent` or `removed`, however tempting the dormant code looks.
- Ending the turn while unchecked tasks remain. The Stop hook will send you back; save the round trip.
- Retrying a failed command unchanged. After the first failure, `/diagnose`.
- Running tests again for confidence, or writing code that does (loops, `-count=N`, `--reruns`, shards that each run the whole suite). `integrity-check` flags it; the full run's census catches it at runtime.
- Waiting out a run that is known to fail for a cause already fixed. Stop it (`cc-fullrun --stop`), restart it canary-first, and say so in the Log.
- Rewriting an acceptance criterion or a task's `verify:` command. They are frozen when the plan starts running; `stop-guard` refuses the stop while any frozen line differs. Splitting a task adds lines and keeps the original.
- Expanding scope. Anything outside `## Goal` becomes a line under `## Out of scope` or a new task at the end, not work done now.
- Touching anything under `## Out of scope`.

## Task-tree rules (when the plan lives in `tasks/<phase>/<NN>-<slug>/`)

`tasks/README.md` and `tasks/PROTOCOL.md` outrank everything below where they differ.

- `labels.txt` `status`: `in_progress` while running. `done` only when every artefact named in `task.txt` OUTCOME exists **in the repository** (`test -f`, `git cat-file -e HEAD:<path>`, the count matches) and the gate checks pass. An OUTCOME outside the repository (a machine at a provider, a phone, a signed build, a person's eyes) is never closed by this session: leave `in_progress` and write in `NOTES.md` what is missing and who can provide it.
- **Never touch `verify:`.** Verification is another context's job (`/verify`). Setting `verify:passed` on your own work is the one thing this tree forbids absolutely.
- Blocking: instead of `[!] BLOCKED` alone, also create `BLOCKED.md` in the task directory in the tree's format (date; what exactly is missing — variable name, task path, question; what was done before stopping, with paths; what can be done without it) and set `status:blocked`. A stub instead of a secret, "hardcode for now", "assume the provider is X" — is a false `done` with delayed discovery, not a workaround.
- `NOTES.md`: dated heading (`# NOTES — <what> (<YYYY-MM-DD>)`), rationale, measurements with sources, rejected alternatives, and this session's assumptions. Numbers carry a source or are not written.
- Reverse control: VERIFY items that say so are executed, and the red output is kept in `NOTES.md` (the verifier will need it for `VERIFY.md`).
- Before finishing: `python3 tasks/check.py` from the repository root — zero problems or the task is not closed.
- Closing a milestone (a `gate:yes` task): run the full tier (`cc-fullrun --out <task dir>`) and `/test-audit <task dir>`; a red, `timeout`, `empty` or `dup` full run holds the milestone, the audit's CONFIRMED findings enter the review loop.
- Commit messages: the repository's own convention (`tasks/PROTOCOL.md`); submodules per its order.

## Finish

When no `- [ ]` remains:
- All `[x]`: set `status: done`, run the full suite and every acceptance criterion command once more, mark each AC. Compare the suite against the `T00` baseline recorded in `## Log`: a test that was green then and is red now is a regression this run caused — it is fixed before the plan closes, or the plan ends `paused` with that test named. A rising coverage floor is expected; a fallen one is a failure, not a formality. In a task tree: apply the `labels.txt` rules above, then suggest `/verify <task dir>` in a fresh context. Report: what changed, why, which checks ran with results, remaining risk, suggested commit message. Stop.
- Some `[!]`: set `status: paused`, list the blocked tasks with their reasons, and end the message with the literal token `NEED_HUMAN`. Stop.

## Context hygiene during a long run

- The window is the model's full context; compaction is not forced early (no `autoCompactWindow`). If it does happen, the SessionStart hook re-injects the active plan afterwards. Keep the plan file the single source of truth so nothing is lost with the history.
- Large tool output is trimmed by a hook (repeated lines collapsed, long output saved to `.claude/scratch/` with head and tail inline). When you need the middle, Grep the saved file; do not re-run the command.
- Whole-file reads over 500 lines are refused by a hook; Grep first, then Read with offset and limit.
- Do not switch model or effort mid-run: it forfeits the prompt cache on a context this size.

## Belt and braces

Tell the user once at start: "To make this unstoppable across API hiccups, run `/goal all tasks in <plan path> are [x] or [!]`." Then proceed without waiting.
