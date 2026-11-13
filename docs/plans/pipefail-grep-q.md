---
status: running
created: 2026-11-13
---
# No `| grep -q` under pipefail: the SIGPIPE race in the hooks

## Goal
No shell script of the harness that runs under `set -o pipefail` feeds a pipeline into `grep -q`. Every such test reads its input from a here-string (or another form with no writer process in the pipeline), so an early-exiting `grep` can no longer kill the writer with SIGPIPE and turn a match into exit 141. `stop-guard` no longer reports "acceptance criteria or verify commands changed" on an unchanged plan, no longer misses `NEED_HUMAN`, and `subagent-evidence` no longer refuses a report whose evidence is there. A static selftest check keeps the form out. The fix is installed into `~/.claude` and tagged `stable-2026-11-13`.

## Acceptance criteria
- [ ] AC1 An unchanged running plan whose frozen lines total more than 100 KiB (a short line first, a 100 KiB verify line after it) is not reported as changed; changing one short frozen line still blocks and names that line — `./selftest.sh` (stop-guard-pipe-*)
- [ ] AC2 `NEED_HUMAN` on the first line of a 100 KiB last message releases the turn; a running plan whose line 3 is 100 KiB long is still found by `stop-guard` and by `session-start` — `./selftest.sh` (stop-guard-pipe-*, session-start-pipe-*)
- [ ] AC3 `subagent-evidence` passes a 100 KiB report whose required marker is on its first line (scout path, test-runner `COMMAND:` + `PASS`, `NOT DONE`) — `./selftest.sh` (subagent-evidence-pipe-*)
- [ ] AC4 Each test of AC1–AC3 was seen red on the unfixed hook; the red output is kept under `.claude/scratch/pipefail/` — `ls .claude/scratch/pipefail/*-red.log`
- [ ] AC5 Static check `no-pipe-grep-q`: no `*.sh` under `hooks/` (and, when selftest runs on the repository, no `*.sh` at the repository root) that sets `pipefail` contains a pipe into `grep` with `-q` among its flags; seen red before the last occurrence was removed — `./selftest.sh` (no-pipe-grep-q) and `! grep -nE '\| *grep +-[A-Za-z]*q' hooks/*.sh *.sh`
- [ ] AC6 CHANGELOG.md has a `stable-2026-11-13` entry naming the defect, the evidence and this plan; INSTALL.md lists the new selftest cases — `grep -n 'stable-2026-11-13' CHANGELOG.md && grep -n 'no-pipe-grep-q' INSTALL.md`
- [ ] AC7 No regression: every selftest check green at T00 is green at the end; a trial install passes `./selftest.sh <trial>`; the live install passes `./selftest.sh ~/.claude`; the user's 600-round reproduction against the installed `stop-guard.sh` gives 0 blocks
- [ ] AC8 Local tag `stable-2026-11-13` on the final commit, not pushed — `git tag --points-at HEAD | grep -x stable-2026-11-13`

## Stack
- bash 5.3.9, `grep` = ugrep 7.8.4 (this machine, `grep --version`), jq, python 3 (stdlib), git. The user's reproduction machine: bash 5.3.9, ugrep 7.8.4, Linux 7.0, Claude Code 2.1.323.
- Gate check: `./selftest.sh` (last recorded: 477 passed, 0 failed on the repository; 497/0 on `~/.claude`; plan `subagent-limit-handback`).
- No `docs/PROJECT.md`, no `tasks/`, no CI, no coverage gate in this repository. No new technology, so no `docs/tech/` file.

## Evidence gathered before the plan (2026-11-13)
From the user's report (measured on their machine, installed hook, commit 057b4a4, `hooks/stop-guard.sh` byte-identical to a00d18c):
- E1 `stop-guard.sh:62` `printf '%s\n' "$current" | grep -qxF -- "$line" || changed=…` under `set -uo pipefail` (line 3). `grep -q` exits on the first match; bash's builtin `printf` writes a multi-line string in several `write()` calls (strace: 10 writes of 100–170 bytes for 18 lines); a write after grep exited gets SIGPIPE, the pipeline returns 141 with grep's 0, `||` fires and the matching line is recorded as changed. `PIPESTATUS` `141 0` once in 10 800 comparisons.
- E2 Installed hook, unchanged plan copy in a scratch git repo, 18 comparisons per round: 3 blocks in 600 rounds (lines AC2, AC2, T09). Copy with only line 62 changed to a here-string: 0 in 2000; reverse control (T01 verify line replaced by `true`): 2 blocks in 2 rounds naming T01.
- E3 `stop-guard.sh:32` `printf '%s' "$last" | grep -q 'NEED_HUMAN'`: a 2001-line message with the token on line 1 missed 283/5000 (41 lines: 0/5000); here-string 0/5000.
- E4 Side effect: `guard_reason` is part of the stall key (`stop-guard.sh:96`), so a false finding also resets the "plan not advancing" count.
- E5 Same form, not measured by the user: `subagent-evidence.sh:22,27,28,30,41,47,53,63,78,81,84,87`; `stop-guard.sh:23`, `session-start.sh:15` (`head -n 8 … | grep -qE`), `read-guard.sh:25` (`file --mime … | grep -qvE`); `selftest.sh:19` (`check()`) and 17 more lines; `install.sh:113`.
- E6 Measured here (bash 5.3.9, ugrep 7.8.4, `.claude/scratch/` race probe): with a large input after a first-line match the race is deterministic — pipeline missed 200/200 for `grep -q 'NEED_HUMAN'` at 1 MiB, and 200/200 for the line-62 form at 1 MiB, 256 KiB and 100 KiB; here-string 0/200 in every case. This is what makes the red-first tests of T01–T04 possible. The filler stays at 100 KiB, because every frozen line becomes an argument of `grep` (line 62) and, in the unfixed hook, part of `jq --arg r "$guard_reason"`: Linux caps one argument at 128 KiB (E2BIG, exit 126), `getconf ARG_MAX` here is 1048576 in total.
- E6a An empty here-string is one empty line: `grep -qvE text <<<"$(true)"` exits 0, `grep -qvE text < <(true)` exits 1 (the old pipe's result). So `-v` and any pattern that matches an empty line cannot take a here-string of possibly empty input.
- E7 Other early-exit readers in pipefail scripts (`| head`, `grep -m`, `sed -n`): every one is inside `$(…)` whose status is not tested (`agent-def.sh:13`, `compress-output.sh:44`, `session-start.sh:23`, `stop-guard.sh:118`, `install.sh:117`, selftest helpers). They are left alone.
- E8 From the user, about the last update: `stop-guard.sh` is byte-identical to the previous version and still blocks falsely (3/600 on the installed hook); changed hooks: `bash-read-guard.py`, `git-guard.py`, `guard-subagent.sh`, `integrity-check.py`, `subagent-evidence.sh`; new: `agent-def.sh`, `turn-guard.sh`.

## Decisions
- D1 Install the fix into the live `~/.claude` after a trial install? -> Yes: trial install, then `./install.sh`, then `./selftest.sh ~/.claude`.
- D2 Tag a release after the green run? -> Yes, local tag `stable-2026-11-13`, no push.
- D3 Branch: `main` (previous plans committed on `main`; no hook forbids it).

## Assumptions
- The fix form is the user's: `grep … <<<"$x"`. The trailing newline the here-string adds changes nothing for line-wise `-x` or `-E` substring search with a pattern that cannot match an empty line. It does change `-v` and empty-matching patterns on empty input (E6a): those take process substitution `grep … < <(cmd)` instead, which adds nothing and keeps the writer outside any pipeline status. `stop-guard.sh:62` keeps its loop (minimal change) rather than becoming one `grep -vxFf`.
- `head -n 8 "$f" | grep -qE` becomes `grep -qE … <<<"$(head -n 8 "$f")"`; `file --mime … | grep -qvE` becomes `grep -qvE … < <(file --mime "$file" 2>/dev/null)` (with no `file` binary the old pipe ran the guard; a here-string would skip it); `install.sh:113` becomes a here-string with `head -n 1`. In T05 every `check()` call whose pattern can match an empty line (`^$`, `.*`, an empty alternative, `-v`) is listed and kept on process substitution.
- Selftest payloads that carry the filler are built with `jq --rawfile` or `jq -Rs < file`, never `--arg "$big"`; each `*-pipe-*` case that expects silence asserts that stdout and stderr together (`2>&1`) are empty, so an E2BIG in the hook cannot pass as green.
- Until T08 the live `~/.claude/hooks/stop-guard.sh` is the buggy one and guards this plan's own run. A "changed since the plan started running" block during the run is first checked with `diff <(frozen lines of the plan) <freeze file>`; an empty diff means this bug: log it and continue, restore nothing.
- The static check covers `hooks/*.sh` of the target and, on the repository, every root `*.sh`; it forbids any `| grep` whose flags include `q`. Selftest's own lines are fixed in the same task, because selftest also runs under pipefail and can redden for no reason.
- `read-guard.sh:25` and `has()`/`has_graph()` in `subagent-evidence.sh` read inputs too short to give a deterministic red test (one line from `file`, a short tool-count string); they are fixed and covered only by the static check.
- The 100 KiB filler is built once into a file under `$TMP` with `head -c 102400 /dev/zero | tr '\0' x`; in a plan it is the last frozen line, after the short line the race needs.

## Out of scope
- The `| head` / `grep -m` / `sed -n` pipelines of E7.
- Rewriting `stop-guard.sh:62` as a single `grep -vxFf`.
- Any other behaviour of `stop-guard`, `subagent-evidence`, `session-start`, `read-guard`.
- Pushing commits or the tag.

## Tasks
- [x] T00 Baseline: `./selftest.sh > .claude/scratch/pipefail/T00-selftest.log 2>&1`, record pass/fail counts and any red check in `## Log` — verify: `test -s .claude/scratch/pipefail/T00-selftest.log`
- [x] T01 `stop-guard.sh:62`. Selftest cases `stop-guard-pipe-unchanged` (running plan, 0 open tasks, frozen lines: a short AC line, then a task whose verify line is 100 KiB; first run freezes, second run on the unchanged plan prints nothing on stdout and stderr together) and `stop-guard-pipe-changed` (the short AC line edited: block naming `AC`). Seen red first (`.claude/scratch/pipefail/T01-red.log`), then `grep -qxF -- "$line" <<<"$current" || changed=…` — verify: `./selftest.sh`
- [ ] T02 `stop-guard.sh:32` and `:23`. Cases `stop-guard-pipe-need-human` (plan with one open task, last message `NEED_HUMAN` + newline + 100 KiB: no block) and `stop-guard-pipe-long-header` (running plan whose line 3 is 100 KiB, one open task: block for the open task). Seen red first (`T02-red.log`), then here-strings on both lines — verify: `./selftest.sh`
- [ ] T03 `session-start.sh:15` and `read-guard.sh:25`. Case `session-start-pipe-long-header` (running plan with a 100 KiB line 3: the session-start output names the plan as it does for a normal plan). Seen red first (`T03-red.log`), then a here-string in `session-start.sh` and process substitution in `read-guard.sh` (E6a); case `read-guard-pipe-no-file` (`PATH` without `file`: the guard still runs on a text file, as the old pipe did) green before and after the change; the existing read-guard cases stay green — verify: `./selftest.sh`
- [ ] T04 `subagent-evidence.sh` lines 22, 27, 28, 30, 41, 47, 53, 63, 78, 81, 84, 87. Cases `subagent-evidence-pipe-scout` (scout with a Read call, report = path on line 1 + 100 KiB: passes), `subagent-evidence-pipe-test-runner` (Bash call, `COMMAND: x` and `PASS 1` on line 1 + 100 KiB: passes), `subagent-evidence-pipe-not-done` (a worker with no tool calls, `NOT DONE: x` on line 1 + 100 KiB: passes). Seen red first (`T04-red.log`), then here-strings on every listed line — verify: `./selftest.sh`
- [ ] T05 Static check `no-pipe-grep-q` in `selftest.sh` per the assumption above, reporting `path:line` of each offence. Seen red first on the still-unfixed `selftest.sh` and `install.sh:113` (`T05-red.log`); then every line the check reports rewritten to a here-string (at plan time: `check()` at `selftest.sh:19` and 17 more selftest lines, `install.sh:113`) — verify: `./selftest.sh && ! grep -nE '\| *grep +-[A-Za-z]*q' hooks/*.sh *.sh`
- [ ] T06 Docs: INSTALL.md, in the bulleted list of what selftest checks (lines 46–50 at plan time), one bullet for the `*-pipe-*` cases (100 KiB inputs with the match on line 1) and `no-pipe-grep-q`; README.md "~480 checks" (lines 9, 130) updated if the new count rounds differently; CHANGELOG.md entry `stable-2026-11-13` (Fixed: the race, E1–E3 numbers, this plan's path) — verify: `grep -n 'stable-2026-11-13' CHANGELOG.md && grep -n 'no-pipe-grep-q' INSTALL.md`
- [ ] T07 Final gate: full `./selftest.sh` compared against T00 (no check green at T00 is red or missing); trial install into `.claude/scratch/pipefail/trial` seeded with the live `settings.json`, then `./selftest.sh .claude/scratch/pipefail/trial` — verify: `./selftest.sh && ./selftest.sh .claude/scratch/pipefail/trial`
- [ ] T08 Live install per D1: `./install.sh`, then `./selftest.sh ~/.claude`; then the user's 600-round reproduction (E2 loop; sandbox git repo holding a copy of `docs/plans/subagent-limit-handback.md` with `status: running` — 0 open tasks, as in the user's case; `HOME`/`XDG_STATE_HOME` in scratch, `CC_STOP_GUARD_CAP=100000`). Reverse control first: the same loop against `git show 057b4a4:hooks/stop-guard.sh` saved to scratch, output in `T08-rounds-base.log`; a count of 0 there is logged as "the race does not show on this machine at this size; AC7 rests on the deterministic `stop-guard-pipe-*` cases". Then against `~/.claude/hooks/stop-guard.sh`, output in `.claude/scratch/pipefail/T08-rounds.log` — verify: `./selftest.sh ~/.claude && ! grep -q '^round ' .claude/scratch/pipefail/T08-rounds.log`
- [ ] T09 Tag per D2: `git tag stable-2026-11-13` on the final commit, no push — verify: `git tag --points-at HEAD | grep -x stable-2026-11-13`

## Log
- 2026-11-13 T00 done: `./selftest.sh` exit 0, passed 477, failed 0 (`.claude/scratch/pipefail/T00-selftest.log`, 2:30 wall); no red check before the change
- 2026-11-13 T01 done: `stop-guard.sh:62` → here-string; cases `stop-guard-pipe-unchanged`, `-changed`, `-changed-only` red on the unfixed hook (`.claude/scratch/pipefail/T01-red.log`: unchanged plan reported as changed, AC and T100 named), green after; `./selftest.sh` passed 480, failed 0. Found on the way: the first draft of the case put the long line at plan line 8, so `stop-guard.sh:23` (`head -n 8 | grep -q`) lost the plan and the case passed for the wrong reason — that is T02's defect; and ugrep 7.8.4 answers "grep: out of memory" (exit 2) for a 100 KiB `-xF` pattern (65 000 bytes still works), so the case uses 200 task lines of 500 bytes, not one 100 KiB line
