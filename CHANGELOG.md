# Changelog

One entry per `stable-*` tag, newest first. The reasons and the evidence behind each entry are in the plan under `docs/plans/` named in it.

## stable-2026-11-14-3 — stop-guard waits for background commands and monitors

Plan: `docs/plans/stop-guard-background-tasks.md`.

### Fixed
- `stable-2026-11-14-2` let a session wait for a background agent but not for a background command or a `Monitor`. In one game repository the model started its probe chain with `run_in_background` and a `Monitor` on it, `stop-guard` blocked each following turn end, and the model went back to polling the output file in a `sleep` loop. `stop-guard` now stays quiet while a background command of the session has no completion notice and `lsof` finds its output file held open (the file's age says nothing: a command that writes to its own log leaves it empty), or while a `Monitor` has no completion notice and is inside its `expires in` window. A monitor's event notices carry no `<status>` and do not end it. Without `lsof` the command rule never releases.

## stable-2026-11-14-2 — stop-guard waits for background agents and for catnap

Plan: `docs/plans/stop-guard-releases.md`.

### Fixed
- A coordinator that handed the plan to a background agent was blocked on every turn end, and answered by polling: in one session 4 blocks between 13:57 and 14:06, each followed by a 600 s `until … sleep` loop waiting for the agent. `stop-guard` now reads the session's `transcript_path` and stays quiet while an agent of the session with `requestShape: background` is not `finished` and its transcript changed within `CC_STOP_GUARD_AGENT_IDLE` minutes (15); a finished, foreground or idle agent does not hold it.
- A catnap compaction raced the hook: `[catnap] Compacting now` at 14:20:40.875 was followed by a `stop-guard` block recorded at 14:20:41.902. catnap queued the compaction at 14:20:40.761 but writes its pending flag in its own tick (here 14:20:41.377), not when `compact_now` returns, so the Stop hook can run before the flag exists. It now also stays quiet when the latest of the tool calls and compaction boundaries in the transcript's tail is `mcp__catnap__compact_now`; a later tool call or a compaction boundary ends that.

## stable-2026-11-14 — stop-guard counts tasks and leaves finished plans alone

Plan: `docs/plans/plan-pick-and-integrity.md`.

### Fixed
- `stop-guard` and `session-start` counted every `- [ ]`, acceptance criteria included: a plan with all tasks done but an open HUMAN criterion kept blocking, and "Next" named `AC1 …` instead of the next task. Only task lines (`- [ ] T…`, `- [!] T…`) are counted and named now.
- A plan finished long ago and left `status: running` was taken by both hooks before any other, because it came first in the glob. In a session that had only a draft plan, `stop-guard` ran `integrity-check` against that plan's base: in one game repository 285 commits and 867 changed paths, 2 min 14 s, far past the 20 s hook timeout, ending in a block about a file of another plan. Both hooks now pick through `hooks/plan-pick.sh`: the first running plan with an open task, else a running plan with no open task touched in the last `CC_STOP_GUARD_FRESH` minutes (120).
- `integrity-check` read binary files as text: 562 of the 867 paths there were binary. It skips files with a NUL byte in their first 8000 bytes (3.6 s on the same diff, same finding) and stops after `CC_INTEGRITY_SECONDS` (15) without blocking, naming how many paths it did not check.
- `/run` finished a plan only when no `- [ ]` remained, which an open HUMAN acceptance line never allows. It finishes when no task line is open and lists the HUMAN lines for the owner.

## stable-2026-11-13 — no pipe into `grep -q` under pipefail

Plan: `docs/plans/pipefail-grep-q.md`.

### Fixed
- `stop-guard` reported "acceptance criteria or verify commands changed" on an unchanged plan, now and then. Under `set -o pipefail`, `printf … | grep -q` returns 141 when `grep` finds the match and exits while `printf` is still writing: the writer gets SIGPIPE and the pipeline reports failure although `grep` returned 0. Measured on the installed hook: 3 false blocks in 600 rounds on an unchanged plan, `PIPESTATUS` `141 0` once in 10 800 comparisons; 0 in 2000 with the fix. A false finding also reset the "plan not advancing" count, because the reason is part of its key.
- The same race in the other direction: `NEED_HUMAN` on line 1 of a 2001-line message was missed 283 times in 5000, so the escape hatch kept blocking; a running plan with a long line in its first 8 could be missed by `stop-guard` and `session-start`; `subagent-evidence` could refuse a report whose path, `COMMAND:`, `PASS` or `NOT DONE` was there.
- Every such test now reads a here-string, or process substitution where empty input must stay "no line" (`read-guard` with no `file` binary). With 100 KiB of input after the match the race is deterministic, which is what the new selftest cases use.

### Added
- Selftest `no-pipe-grep-q`: no `*.sh` that sets `pipefail` pipes into `grep -q`; selftest's own checks follow the rule.

## stable-2026-11-12-2 — /plan no longer traps its own window

### Fixed
- `/plan` "clean window" left the plan `running`, so `stop-guard` blocked the planning window before `/clear`. The plan now stays `draft`; `/run` sets `running`, also when given a path.

## stable-2026-11-12 — subagents hand back a report at the turn limit

Plan: `docs/plans/subagent-limit-handback.md`. Checked live on Claude Code 2.1.322; evidence in `docs/tech/claude-code-subagent-turns@2.1.322.md`.

A subagent that ran into its `maxTurns` used to be cut with no wrap-up turn, and its parent got "It was still calling tools and had produced no report". Now the agent's last two turns are kept for the report.

### Added
- `hooks/turn-guard.sh`, registered on `SubagentStart`, `PreToolUse` and `PostToolUse` for every tool. For a subagent whose definition has `maxTurns` it counts the turns of the current run from the subagent's transcript, names the limit at the start, adds a `TURN LIMIT` note after turn `maxTurns-2`, and on turns `maxTurns-1` and `maxTurns` refuses every tool call except `SubagentHandback`. It is silent for the main session, for agents with no definition, no `maxTurns` or a `maxTurns` of 2 or less; it never answers `allow`, has no `onFailure`, and is switched off by `CC_DISABLED_HOOKS=turn-guard`.
- `hooks/agent-def.sh`: the lookup of an agent's frontmatter (`<cwd>/.claude/agents`, then the config directory), shared by `turn-guard.sh` and `guard-subagent.sh`.
- `CLAUDE.md`, "Cost hygiene": what the coordinator does with a subagent that stopped at its turn limit without a report — resume once with a fixed ask, never claim the limit was lifted, split the task after a second cut.
- `docs/tech/claude-code-subagent-turns@2.1.322.md`: how turns, the cut-off, the hand-back channel and the subagent hooks behave on 2.1.322, each line with its evidence.
- `docs/upgrade-2.1.322.md`: the audit of the harness against Claude Code 2.1.322. Only the subagent turn limit is acted on here; the rest is open.
- `selftest.sh`: 36 new checks, among them `turn-guard-*`, `agent-def-shared`, `subagent-evidence-forced` and `install-rerun-no-dup`; 477 on the checkout.
- `CHANGELOG.md`.

### Changed
- Turn limits: `reviewer` 12 → 40, `scout` 6 → 10, `Explore` 6 → 10, `test-runner` 8 → 12, `researcher` 12 → 20. Two turns of every limit are now kept for the report.
- `hooks/subagent-evidence.sh` does not send back a report that `turn-guard` forced.
- `hooks/guard-subagent.sh` reads agent definitions through `hooks/agent-def.sh`; its behaviour is the same.
- `README.md`, `HARNESS.md`, `BEHAVIOR.md`, `INSTALL.md` describe the hook, the limits and why a refusal in `PreToolUse` rather than `SubagentStop` or a warning alone.

### Upgrading
`./install.sh`, then `./selftest.sh ~/.claude`. The previous configuration is backed up to `~/.claude-backup/<timestamp>`; `./uninstall.sh <backup> ~/.claude` rolls back.

### Known limits
- An agent that ignores the refusal and repeats the call is still cut.
- The definition is looked up by the working directory of the call, so a subagent in a worktree without the project's `.claude/agents` gets the definition from the config directory, or no limit.

## Earlier

- `stable-2026-11-02` — harness upgraded to Claude Code 2.1.316: `docs/plans/cc-2.1.316-upgrade.md`, `docs/upgrade-2.1.316.md`.
- `stable-2026-10-05` — stable main before `docs/plans/harness-expansion.md`.
