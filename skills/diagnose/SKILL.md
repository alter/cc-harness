---
name: diagnose
description: Engineering diagnosis instead of retry loops. Use after the first failure of a build, test, command, deploy or integration that is not a trivial typo. Produces a stated root cause with evidence before any fix is attempted.
argument-hint: <what failed, or empty to use the last failure>
---

# /diagnose

Rule zero: no code change until `ROOT CAUSE:` is written as one sentence with evidence attached. "Let me try X" is not evidence.

## 1. Freeze and capture

- Reproduce once, deterministically. Save exact command, exit code, full stdout+stderr to `.claude/scratch/diag-<ts>.log` (send the run through `test-runner` if the output is large; you need the file, not the noise).
- Extract the primary error: first exception, first non-zero exit, first failed assertion. Not the last line.
- `git status`, `git diff`, `git log --oneline -15`. What changed since the last known-good state?

## 2. Pin versions

Record, from the machine, not from memory:
- language: `python -V` / `node -v` / equivalent
- the failing library: `pip show <pkg>` / `npm ls <pkg>` / lockfile line
- framework and any SDK involved
- OS and arch if the failure smells native (`uname -a`)

All docs and searches below are for these versions.

## 3. Look from every level

Answer each in one line; "n/a" is an answer, "didn't check" is not.
- Helicopter: what is the system trying to do, which component actually fails, is the failure in our code or below it?
- Environment: env vars, config files, paths, permissions, ports, DNS, time, locale.
- Dependencies: version drift, transitive conflicts, a lockfile that does not match installed.
- Logs: raise the log level (`--log-level DEBUG`, framework debug flag, `PYTHONVERBOSE`, `-X dev`, `NODE_DEBUG`), read the 50 lines before the error.
- Trace: stack trace read bottom-up to the first frame in our code; if async, get the full chain.
- State: what data or fixture is present; does it fail on empty state too?
- Metrics or timing: if it is flaky or slow, measure (three runs, timings), do not guess.
- Debugger: for logic errors, a scratch script with `pdb`/breakpoints or targeted prints — in scratch, never committed.

## 4. Hypotheses

- List at least three. Rank by evidence. For the top one, write the single experiment that would refute it.
- Run that experiment. If refuted, next hypothesis. Do not "fix" while experimenting.

## 5. Official documentation for the pinned version

Delegate to `researcher` with the exact versions:
- the library's docs for that version (not "latest"), changelog and migration notes between the version you have and the one the docs assume
- the framework's or SDK's reference for the exact call that fails
- GitHub issues for the exact error string, filtered to this version range
Bring back: quotes with URLs, and whether the behavior is documented, deprecated, or a known bug.

## 6. Unofficial workarounds

Search the exact error string plus the library name. Any workaround found:
- must be reproduced in an isolated scratch file first (`.claude/scratch/`)
- must be explained: why it works given the root cause
- is rejected if it only masks the symptom

## 7. Conflict escalation

If two hypotheses remain with split evidence, or the docs contradict observed behavior, get one outside opinion with the evidence table. Use the `advisor` tool when this session has it — it is a server-side tool in your own tool list, not something `ToolSearch` or the agent list can find. It is not always there: `advisorModel` only takes effect when the account's gate allows it (`CLAUDE_CODE_ENABLE_EXPERIMENTAL_ADVISOR_TOOL=1` forces it on, and `claude --debug` prints either `[AdvisorTool] Server-side tool enabled …` or `[AdvisorTool] Skipping advisor - …`). When it is absent, say so in one line and send the evidence table to the `reviewer` subagent on Opus instead. Do not commit to a branch on a coin flip, and do not report advice from a tool that never ran.

## 8. Fix once

- Write `ROOT CAUSE: <sentence>` and `EVIDENCE: <log line / doc quote / experiment>` into the plan's `## Log` (or into the answer if there is no plan).
- Apply one fix. Re-run the original reproduction from step 1. Add a regression test where a test suite exists.
- If the fix fails, you are back at step 4 with new evidence, not at "try again".
