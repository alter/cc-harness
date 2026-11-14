---
status: running
created: 2026-11-14
---
# stop-guard lets a session wait for its background commands and monitors

## Goal
`stop-guard` stays silent while the session that is stopping has a live background command (`Bash` with `run_in_background`, or a command moved to the background on timeout) or a live `Monitor`: the session is woken by that task's notification, and blocking it only makes the model poll. `stable-2026-11-14-2` covered background agents only. Installed into `~/.claude`, CHANGELOG entry, tagged `stable-2026-11-14-3` and pushed.

## Acceptance criteria
- [ ] AC1 A background command started in the transcript, with no terminal `<task-notification>` for its id and its output file held open, lets the turn through; one with a terminal notification, or whose output file nobody holds, does not — `./selftest.sh` (stop-release-bash-*)
- [ ] AC2 A `Monitor` started in the transcript, with no terminal notification and inside its `expires in Nm` window, lets the turn through; one past its window or with a terminal notification does not; an event notification without `<status>` does not end it — `./selftest.sh` (stop-release-monitor-*)
- [ ] AC3 The cases that change behaviour were seen red on the unfixed hook — `ls .claude/scratch/stop-bg/T01-red.log`
- [ ] AC4 Live: the installed hook on this session's real transcript, with a background command running, is silent; the hook from `cb4b2fb` blocks on the same payload — `.claude/scratch/stop-bg/T03-live.log`
- [ ] AC5 No regression: T00 green stays green; trial and live installs pass — `./selftest.sh`, `./selftest.sh <trial>`, `./selftest.sh ~/.claude`
- [ ] AC6 CHANGELOG entry `stable-2026-11-14-3`; tag on the final commit, pushed with `main` — `git ls-remote --tags origin stable-2026-11-14-3`

## Stack
- bash 5.3.9, jq, `/usr/sbin/lsof` 4.91, git; Claude Code 2.1.325.
- Gate `./selftest.sh`; T00 = 506 passed, 0 failed at `f1fcc36` (`.claude/scratch/stop-release/T02-selftest.log`); `cb4b2fb` changed only the plan file.

## Evidence (2026-11-14)
- E1 `project E` session `e94375fa`, plan `plan-1.md`: `Bash` run_in_background `b6qrv0tgq` ("Run T34 full probe chain", 14:48:54) and `Monitor` `bcu3t24w8` (14:49:12, "expires in 30m"); `stop-guard` blocked the turn ends that followed, and at 14:49:34 the model polled the output file in a `for … sleep 5` loop. Both tasks ended with `<task-notification>` `<status>completed</status>` (14:49:46, 14:49:49).
- E2 Start lines in tool results: `Command running in background with ID: <id>. Output is being written to: <path>`, `moved to the background (ID: <id>). Output is being written to: <path>`, `Monitor started (task <id>, expires in <N>m`. Last 7 days on this machine: statuses `completed` 8400, `failed` 670, `killed` 57, `stopped` 35; 129 notifications carry no `<status>` — `Monitor` events (`<event>`), which do not end the task.
- E3 This session, 18:55: a running `sleep 90` background command's `.output` is held open by its `zsh` wrapper and by `sleep` (`lsof -t` → 2 pids, 0.26 s) although the command writes to `/dev/null`; so output-file mtime is no liveness signal. A running `Monitor` has no `.output` file at all.

## Decisions
- D1 Reported by the user right after `stable-2026-11-14-2` ("это что?") as the same symptom; the user's standing instruction: after finished work update CHANGELOG, commit, push and tag.
- D2 Branch `main`.

## Assumptions
- A task is ended by any line of the transcript that holds `<task-id><id></task-id>` together with `<status>`.
- Background command live: not ended, and `lsof -t -- <output path>` names a process. No `lsof` → not live (the old block).
- Monitor live: not ended, and now < tool-result timestamp + N minutes (Claude Code kills it at expiry and notifies).
- Scan: only transcript lines that contain one of the start phrases or `<task-id>`, prefiltered with `grep -F`, then `jq`.
- Background agents stay on their `subagents/*.meta.json` rule.

## Out of scope
- `TaskStop`-ed tasks without a notification, other task kinds (remote, cron).

## Tasks
- [x] T00 Baseline cited: 506 passed, 0 failed at `f1fcc36`
- [x] T01 Cases `stop-release-bash-{live,ended,released}`, `stop-release-monitor-{live,expired,ended,event}`; seen red first (`.claude/scratch/stop-bg/T01-red.log`); then the check in `stop-guard.sh` — verify: `./selftest.sh`
- [ ] T02 Docs: README stop-guard paragraph and row, HARNESS row, INSTALL bullet, CHANGELOG `stable-2026-11-14-3`; gate `./selftest.sh`, trial install (absolute path) and its selftest — verify: `./selftest.sh && ./selftest.sh $PWD/.claude/scratch/stop-bg/trial && grep -n 'stable-2026-11-14-3' CHANGELOG.md`
- [ ] T03 Live install, `./selftest.sh ~/.claude`; live check on this session (`T03-live.log`); tag `stable-2026-11-14-3`, push `main` and the tag — verify: `test -s .claude/scratch/stop-bg/T03-live.log && git ls-remote --tags origin stable-2026-11-14-3 | grep -q .`

## Log
- 2026-11-14 T00 (cited): `./selftest.sh` 506 passed, 0 failed at `f1fcc36` (`.claude/scratch/stop-release/T02-selftest.log`); no code changed since
- 2026-11-14 T01 done: `stop-guard.sh` `bg_task_live`: silent while a background command (started or moved to the background) has no terminal `<task-notification>` and `lsof` finds its output file held, or a `Monitor` has none and is inside its `expires in` window. `bash-live`, `bash-moved`, `monitor-live`, `monitor-event` red on the unfixed hook (`.claude/scratch/stop-bg/T01-red.log`); `bash-ended`, `bash-released`, `monitor-ended`, `monitor-expired` each red on a copy with its rule removed (`T01-breaks.log`). On the real `project E` transcript (19 MB) 0.97 s and silent: its background command `bv4pjq7b7` ("Wait for T34 chain") was running; project C (4.6 MB) 0.20 s. `./selftest.sh` passed 514, failed 0
