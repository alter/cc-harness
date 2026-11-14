---
status: running
created: 2026-11-14
---
# stop-guard counts tasks, not criteria; skips finished plans; integrity-check skips binaries

## Goal
`stop-guard` and `session-start` count and name only task lines (`- [ ] T…`), so an open or HUMAN acceptance criterion neither keeps a finished plan blocking nor appears as "Next". Both hooks pick the plan through one shared helper that prefers a running plan with open tasks and ignores a running plan with no open task that has not been touched for two hours, so a stale plan no longer steals the stop of a session that has only a draft. `integrity-check` skips binary files and stops at a time budget below the hook timeout, so it never runs for minutes. `/run` finishes a plan when no task line is open. The fix is installed into `~/.claude`.

## Acceptance criteria
- [ ] AC1 A running plan whose tasks are all `[x]` and whose acceptance lines are still `[ ]` lets the stop through; "Next" names task lines only; `session-start` counts task lines only — `./selftest.sh` (plan-count-*)
- [ ] AC2 A stale running plan with no open task (mtime older than `CC_STOP_GUARD_FRESH` minutes, default 120) is ignored by `stop-guard` and `session-start`; a running plan with open tasks is chosen over a finished one earlier in the glob; a freshly finished plan is still checked — `./selftest.sh` (plan-pick-*)
- [ ] AC3 `integrity-check` reports nothing for a binary file that carries a marker, still reports a marker added to a text file, and with `CC_INTEGRITY_SECONDS=0` stops at once without a finding — `./selftest.sh` (integrity-binary-*, integrity-deadline)
- [ ] AC4 Each case of AC1–AC3 that changes behaviour was seen red on the unfixed code; red output under `.claude/scratch/plan-pick/` — `ls .claude/scratch/plan-pick/*-red.log`
- [ ] AC5 On `project E` (base `dac5e8b`, 867 changed files, 562 binary) `integrity-check` finishes in under 15 s with the same finding; the installed `stop-guard` on a scratch clone of `project E` where `plan-1.md` is `draft` and the real freeze of `plan-2.md` is copied in is silent within the hook timeout — `.claude/scratch/plan-pick/T06-*.log`
- [ ] AC6 `/run` finishes when no task line is open; HUMAN acceptance lines are listed for the owner — `grep -n 'task line' skills/run/SKILL.md`
- [ ] AC7 No regression: selftest green at T00 stays green; trial install and live install pass selftest — `./selftest.sh`, `./selftest.sh <trial>`, `./selftest.sh ~/.claude`

## Stack
- bash 5.3.9, ugrep 7.8.4, jq, python 3 (stdlib), git. Claude Code 2.1.323 per the user.
- Gate: `./selftest.sh`. T00 baseline: 488 passed, 0 failed at `ec703c4` (plan `pipefail-grep-q`, T07 log); no file outside `docs/plans/` changed since.

## Evidence (2026-11-14)
- E1 a task-tree `PLAN.md` of another project: the stop-guard reason said "14 unchecked task(s). Next: AC1 …; AC2 …; AC3 …". The file has 8 open `AC` lines and 6 open task lines; `stop-guard.sh:27` and `:118` match `^- \[ \] ` and so count and name criteria. AC8 is HUMAN and never closed by `/run`, so `open` never reaches 0.
- E2 `project E`: after `/plan` left `plan-1.md` `draft`, the Stop hook ran 5m30s. `docs/plans/plan-2.md` and `plan-3.md` are `status: running` since 2026-11-07/08 with 0 open task lines (only HUMAN AC `[!]`); `stop-guard.sh:21-24` takes the first running plan in glob order, `plan-2.md`. Its freeze base is `dac5e8b` (285 commits back). `integrity-check.py --base dac5e8b` there: 2m14s, exit 1, `android/gradlew: a suppression was added (shellcheck\s+disable)` — a generated file of another plan. The hook timeout is 20 s.
- E3 867 paths changed since `dac5e8b`, 562 binary (`git diff --numstat`). A scratch copy of `integrity-check.py` that skips files with a NUL in their first 8000 bytes: 4.6 s, the same single finding.
- E4 `skills/run/SKILL.md` "Finish" starts "When no `- [ ]` remains", which a HUMAN criterion line never satisfies.

## Decisions
- D1 The user asked directly to fix both reported defects ("баги … пофикси"); the stale plans in `project E` stay as they are (the user will not pause them now), so the hook must cope with them.
- D2 Branch `main`; no push and no tag unless asked.

## Assumptions
- A task line is `- [ ] T<digits>…` (`T11a` included); a blocked task is `- [!] T<digits>…`. Plans whose tasks are not numbered `T` are not counted.
- Plan choice, shared by both hooks through `hooks/plan-pick.sh <cwd>` (prints plan path, open, blocked): the first running plan with an open task; else the first running plan with no open task modified within `CC_STOP_GUARD_FRESH` minutes (default 120) — a plan just finished is still checked for frozen lines and integrity; else none.
- Binary = a NUL byte in the first 8000 bytes of the working-tree file; such a path is skipped after the deleted-test check.
- `integrity-check` budget `CC_INTEGRITY_SECONDS` (default 15, below the 20 s hook timeout): at the deadline it stops, prints what it found so far plus a line naming the unchecked count; exit 1 only when it found something. An unfinished scan does not block.
- `/run` Finish: no open task line → all tasks `[x]` → `done` (open HUMAN acceptance lines listed for the owner); some task `[!]` → `paused` + `NEED_HUMAN`.

## Out of scope
- Changing the plans of `project E` or `project H`.
- The relative-path `install.sh` defect and the `git-guard` false positive noted in plan `pipefail-grep-q`.
- Push, tag.

## Tasks
- [ ] T01 `hooks/plan-pick.sh` (task-line counts, plan choice per Assumptions) used by `stop-guard.sh` and `session-start.sh`; `next=` lists task lines only. Cases `plan-count-ac-open` (all tasks `[x]`, AC `[ ]`: stop allowed), `plan-count-next` (open AC before open task: Next names the task, not the AC), `plan-count-session-start` (session-start counts tasks only), `plan-pick-stale` (stale finished `a.md` running + `draft` `b.md`: silent), `plan-pick-open-first` (stale finished `a.md` + `b.md` with an open task: block names `b.md`), `plan-pick-fresh-finished` (finished plan touched now with a weakened AC: still blocks). Seen red first (`T01-red.log`) — verify: `./selftest.sh`
- [ ] T02 `integrity-check.py`: skip binaries, deadline per Assumptions. Cases `integrity-binary-skip` (a committed text file replaced by bytes with a NUL and `# noqa`: no finding), `integrity-binary-text-still` (`# noqa` added to a text file: finding), `integrity-deadline` (`CC_INTEGRITY_SECONDS=0` with a finding present: exit 0, names the unchecked count). Seen red first (`T02-red.log`) — verify: `./selftest.sh`
- [ ] T03 `skills/run/SKILL.md` Finish per Assumptions — verify: `grep -n 'task line' skills/run/SKILL.md`
- [ ] T04 Docs: README.md and HARNESS.md hook tables name `plan-pick.sh`; INSTALL.md bullets for the new cases; CHANGELOG entry `stable-2026-11-14` (not tagged) — verify: `grep -n 'plan-pick' README.md HARNESS.md INSTALL.md CHANGELOG.md`
- [ ] T05 Final gate: `./selftest.sh` against T00; trial install with an absolute path, `./selftest.sh <trial>` — verify: `./selftest.sh && ./selftest.sh $PWD/.claude/scratch/plan-pick/trial`
- [ ] T06 Live install, `./selftest.sh ~/.claude`; on `project E`: timed `integrity-check` with base `dac5e8b` (`T06-integrity.log`), and the installed `stop-guard` against a `git clone --shared` scratch copy with `plan-1.md` set to `draft` and the real `plan-2` freeze copied under the clone's key, in scratch `XDG_STATE_HOME`/`HOME` (`T06-stop.log`) — verify: `./selftest.sh ~/.claude && test -s .claude/scratch/plan-pick/T06-integrity.log && test -s .claude/scratch/plan-pick/T06-stop.log`

## Log
- 2026-11-14 T00 (cited): `./selftest.sh` 488 passed, 0 failed at `ec703c4` (`.claude/scratch/pipefail/T07-selftest.log`); no code changed since
