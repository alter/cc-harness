---
name: run
description: Execute a plan file to completion without asking questions. Use to start or resume unattended work on docs/plans/<slug>.md or a task directory's PLAN.md. Marks tasks done only after their verify command passes.
argument-hint: <path to plan, or empty for the single running plan; add "delegate" to hand tasks to worker subagents>
---

# /run

Input: `$ARGUMENTS` — a plan path or a task directory (then its `PLAN.md`). If empty, find the one file under `docs/plans/` or `tasks/**/PLAN.md` with `status: running`; if there is exactly one `status: draft` and none running, use it and set it to running.

## One session, the whole plan (default)

You do the tasks yourself, one at a time, in this session, by the `run-task` procedure (read the task line, `## Decisions`, `## Assumptions`, `## Out of scope`, the last Log lines; do; run the verify command; mark; log; commit). The session lives as long as the plan; the plan file is the state, the conversation is the memory of *why*. Do not `/clear`, do not `/compact` by hand, do not spawn a fresh session per task.

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
3. On return, Grep that task's line. `[x]` or `[!]` → next. Still `- [ ]` with an `open:` Log line → spawn `worker` once more with the same task and the words "second attempt: start from the open: evidence in Log". Still open after that → mark `- [!] BLOCKED: two attempts failed, see Log`, append a Log line, next.
4. A worker's report is a claim: if its two lines do not match the plan's state after your Grep, trust the plan file.
5. Never Read source files, tool outputs or transcripts in delegate mode.

Trade: every worker is a cold start (system prompt + tools + CLAUDE.md + AGENTS.md + PROJECT.md + plan + task ≈ 10–20k tokens of cache write) and knows nothing of *why* the previous task was done the way it was. Use it for long plans of independent tasks; the default mode for everything else.

## What is not allowed

- Asking the user anything. The interview is over.
- `git stash`, `reset --hard`, `clean`, branch switching. Blocked by user changes → `[!] BLOCKED`, next task.
- Building anything the ledger in `docs/PROJECT.md` marks `absent` or `removed`, however tempting the dormant code looks.
- Ending the turn while unchecked tasks remain. The Stop hook will send you back; save the round trip.
- Retrying a failed command unchanged. After the first failure, `/diagnose`.
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
- Commit messages: the repository's own convention (`tasks/PROTOCOL.md`); submodules per its order.

## Finish

When no `- [ ]` remains:
- All `[x]`: set `status: done`, run every acceptance criterion command once more, mark each AC. In a task tree: apply the `labels.txt` rules above, then suggest `/verify <task dir>` in a fresh context. Report: what changed, why, which checks ran with results, remaining risk, suggested commit message. Stop.
- Some `[!]`: set `status: paused`, list the blocked tasks with their reasons, and end the message with the literal token `NEED_HUMAN`. Stop.

## Context hygiene during a long run

- The window is the model's full context; compaction is not forced early (no `autoCompactWindow`). If it does happen, the SessionStart hook re-injects the active plan afterwards. Keep the plan file the single source of truth so nothing is lost with the history.
- Large tool output is trimmed by a hook (repeated lines collapsed, long output saved to `.claude/scratch/` with head and tail inline). When you need the middle, Grep the saved file; do not re-run the command.
- Whole-file reads over 500 lines are refused by a hook; Grep first, then Read with offset and limit.
- Do not switch model or effort mid-run: it forfeits the prompt cache on a context this size.

## Belt and braces

Tell the user once at start: "To make this unstoppable across API hiccups, run `/goal all tasks in <plan path> are [x] or [!]`." Then proceed without waiting.
