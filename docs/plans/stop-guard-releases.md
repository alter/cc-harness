---
status: running
created: 2026-11-14
---
# stop-guard lets a coordinator wait for its background agent and lets a catnap compaction run

## Goal
`stop-guard` stays silent when the session that is stopping has a live background subagent, because the plan is moving in that agent and the session is woken by its notification; it no longer drives a coordinator into minutes-long polling loops. It also stays silent when the turn ends right after `mcp__catnap__compact_now`, whether or not catnap has flushed its pending flag yet, so the compaction is not raced. Installed into `~/.claude`, tagged `stable-2026-11-14-2` and pushed (the user asked to do it "like the previous two").

## Acceptance criteria
- [ ] AC1 A session with an unfinished background subagent whose transcript changed within `CC_STOP_GUARD_AGENT_IDLE` minutes (default 15) is let through; a finished one, a foreground one and one silent for longer are not — `./selftest.sh` (stop-release-agent-*)
- [ ] AC2 A turn whose last tool call is `mcp__catnap__compact_now` is let through with no pending flag on disk; a turn with a later tool call is not — `./selftest.sh` (stop-release-catnap-*)
- [ ] AC3 The two cases that change behaviour were seen red on the unfixed hook — `ls .claude/scratch/stop-release/T01-red.log`
- [ ] AC4 On the live `georgia_house_match` session `548b3dac` (agent `a4ad0a…` running) the installed hook, given that session's real `transcript_path` and scratch state, is silent; the hook from `a44c14b` blocks on the same payload — `.claude/scratch/stop-release/T03-live.log`
- [ ] AC5 No regression: selftest green at T00 stays green; trial and live installs pass — `./selftest.sh`, `./selftest.sh <trial>`, `./selftest.sh ~/.claude`
- [ ] AC6 Tag `stable-2026-11-14-2` on the final commit, pushed with `main` — `git ls-remote --tags origin stable-2026-11-14-2`

## Stack
- bash 5.3.9, jq, git; Claude Code 2.1.323; catnap 0.3.12 (`~/.claude/plugins/cache/lippinc/catnap/0.3.12`).
- Gate `./selftest.sh`; T00 = 499 passed, 0 failed at `a44c14b` (plan `plan-pick-and-integrity`, T05), no code changed since.

## Evidence (2026-11-14)
- E1 `georgia_house_match` session `548b3dac`: the plan `prices-collect.md` is executed by an async agent ("Async agent launched … agentId a4ad0a4558b9429ff", 13:27). The main session coordinates; `stop-guard` blocked its turn ends at 13:57, 13:58, 14:00, 14:06, and after each block the session ran `until …; sleep` loops of up to 600 s waiting for the agent's commits. The stall release never fired: the open count moved 2→3→4 as tasks were added.
- E2 `~/.claude/projects/<proj>/<session>/subagents/agent-<id>.meta.json` carries `requestShape` (`background`/`foreground`) and `finished: true` once done. On this machine: 368 background finished, 27 foreground finished, 5 background without `finished` — one live (`a4ad0a…`, jsonl written 18:21), four dead since 11-05..11-14 13:39.
- E3 `max-game2` session `e94375fa`: `[catnap] Compacting now` at 14:20:40.875, `Stop hook feedback … 7 unchecked task(s)` at 14:20:41.902; catnap log `queued` 14:20:40.761, its flag file `{"pending":true}` written 14:20:41.377. catnap writes the flag in its `tick()` (`hooks/register.ts:619-624`), not when `compact_now` returns, so the Stop hook can run before it. The first nap of the same session (13:26:48) was blocked the same way.

## Decisions
- D1 The user asked for this fix "as a plan and installed, like the previous two" ("сделай"); the catnap race was reported in the same exchange and shares the release path, so it goes into the same plan.
- D2 Branch `main`; tag and push at the end, as the user did for `stable-2026-11-14`.

## Assumptions
- Live background agent: `${transcript_path%.jsonl}/subagents/agent-*.meta.json` with `requestShape == "background"`, no `finished: true`, and its `.jsonl` modified within `CC_STOP_GUARD_AGENT_IDLE` minutes (15: a Bash call may run 10 minutes without a write). A dead agent releases the stop for at most that long.
- catnap: among `tool_use` names and `compact_boundary` entries in the tail (400 lines) of `transcript_path`, the latest is `mcp__catnap__compact_now` → silent; a boundary after it means the compaction already ran (E3: each `compact_now` in `e94375fa` is followed by a `compact_boundary`). The existing flag check stays.
- Both checks run before the plan is picked, like the existing catnap check.

## Out of scope
- Holding a background plan-runner itself to its plan (it has no `Stop` hook; `SubagentStop` is `subagent-evidence`).
- Changes to catnap.

## Tasks
- [x] T01 Cases `stop-release-agent-live` (silent), `-agent-finished`, `-agent-foreground`, `-agent-stale` (all block), `stop-release-catnap-race` (silent), `-catnap-later-call` (blocks); seen red first (`.claude/scratch/stop-release/T01-red.log`); then the two checks in `stop-guard.sh` — verify: `./selftest.sh`
- [ ] T02 Docs: README stop-guard paragraph and table row, HARNESS stop-guard row, INSTALL bullet, CHANGELOG `stable-2026-11-14-2`; gate: `./selftest.sh` against T00, trial install (absolute path) and its selftest — verify: `./selftest.sh && ./selftest.sh /Users/rdolgov/workflow/git/cc-harness/.claude/scratch/stop-release/trial && grep -n 'CC_STOP_GUARD_AGENT_IDLE' README.md HARNESS.md CHANGELOG.md`
- [ ] T03 Live install, `./selftest.sh ~/.claude`; the installed hook and the `a44c14b` hook on the payload of session `548b3dac` with its real `transcript_path`, scratch `HOME`/`XDG_STATE_HOME` (`T03-live.log`); tag `stable-2026-11-14-2`, push `main` and the tag — verify: `./selftest.sh ~/.claude && test -s .claude/scratch/stop-release/T03-live.log && git ls-remote --tags origin stable-2026-11-14-2 | grep -q .`

## Log
- 2026-11-14 T00 (cited): `./selftest.sh` 499 passed, 0 failed at `a44c14b` (`.claude/scratch/plan-pick/T05-selftest.log`); no code changed since
- 2026-11-14 T01 done: `stop-guard.sh` reads `transcript_path`; silent when the latest of tool calls and compaction boundaries is `mcp__catnap__compact_now`, or when an unfinished background agent's transcript changed within `CC_STOP_GUARD_AGENT_IDLE` (15) minutes. `stop-release-agent-live` and `-catnap-race` red on the unfixed hook, `-agent-finished/-foreground/-stale` and `-catnap-later-call` green before and after (`.claude/scratch/stop-release/T01-red.log`); added `-catnap-after-compaction`, red on a copy without the boundary rule (same log); `./selftest.sh` passed 506, failed 0
