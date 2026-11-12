---
status: running
created: 2026-11-12
---
# Subagents hand back a report even at the turn limit

## Goal
A subagent that runs into its `maxTurns` no longer ends with "produced no report". A new hook, `turn-guard`, counts the subagent's turns in the current leg and, on the last two turns, refuses every tool call except `SubagentHandback`, so the agent's only move is to deliver what it has. The coordinator has a written rule for the case the hook cannot cover. The limits of the short agents are raised so that the two reserved turns do not eat their working budget. The result is installed into `~/.claude`.

## Acceptance criteria
- [ ] AC1 A subagent on turn `maxTurns-1` or later gets every tool call except `SubagentHandback` refused with a `TURN LIMIT` reason; `SubagentHandback` passes without any decision — `./selftest.sh` (turn-guard-*)
- [ ] AC2 Turn counting is exact: several tool calls of one model response are one turn; a call whose response is not yet in the transcript is counted; a resumed leg starts from zero — `./selftest.sh` (turn-guard-*)
- [ ] AC3 The hook is silent everywhere else: the main session, an agent with no definition or no `maxTurns`, early turns. It never emits `permissionDecision: "allow"`, honours `CC_DISABLED_HOOKS=turn-guard`, and carries no `onFailure` — `./selftest.sh` (turn-guard-*)
- [ ] AC4 `subagent-evidence` does not send a report forced by `turn-guard` back to work — `./selftest.sh` (subagent-evidence-forced)
- [ ] AC5 Live on Claude Code 2.1.322: a 5-turn agent given a 7-step task delivers a report to its parent on the first run and on a resumed run, started in the foreground and in the background — `! grep -l 'produced no report' .claude/scratch/turn-guard-live/run-*.json`, outputs quoted in `## Log`
- [ ] AC6 Limits: `reviewer` 40, `scout` 10, `Explore` 10, `test-runner` 12, `researcher` 20 — `grep -n '^maxTurns:' agents/{reviewer,scout,Explore,test-runner,researcher}.md`
- [ ] AC7 `CLAUDE.md` tells the coordinator what to do with a subagent that stopped at its turn limit without a report — `grep -n 'turn limit' CLAUDE.md`
- [ ] AC8 README.md, HARNESS.md and BEHAVIOR.md describe the hook, the new limits and the evidence behind the design — `grep -n 'turn-guard' README.md HARNESS.md BEHAVIOR.md`
- [ ] AC9 No regression: every selftest check green at T00 is green at the end; a trial install passes `./selftest.sh <trial>`; the live install passes `./selftest.sh ~/.claude`; one live run through the installed hook delivers a report

## Stack
- bash 5.3, jq 1.6, python 3.14 (stdlib), git.
- Claude Code 2.1.322 (`claude --version`); the harness docs name 2.1.316 as last verified.
- Gate check: `./selftest.sh` (last recorded: 440 passed, 0 failed, plan `cc-2.1.316-upgrade`).
- No `docs/PROJECT.md`, no `tasks/`, no CI, no coverage gate in this repository.

## Evidence gathered before the plan (2026-11-12, CLI 2.1.322)
Probe project: `.claude/scratch/probe-turnwarn/` (hook `probe-hook.sh`, logs `payloads*.jsonl`, runs `run*.json`). Real case: session `project E/1d7713f3`, agent `a493b25f82eaddc4e`.
- E1 `maxTurns` is per leg of one subagent: 12 model responses on the first run, 12 more after a `SendMessage` resume; the context survives the cut. One turn = one model response (distinct `message.id`), whatever the number of tool calls in it.
- E2 At the limit the agent is cut with no wrap-up turn. The parent gets "It was still calling tools and had produced no report … Its unsent text is not shown". The report travels only through the `SubagentHandback` tool.
- E3 `SubagentStop` does not fire at the cut-off (`payloads.jsonl`: no such event), so nothing can rescue the report at that moment.
- E4 `PreToolUse` and `PostToolUse` inside a subagent carry `agent_id`, `agent_type`, `tool_use_id` and the parent's `transcript_path`; the subagent's transcript is `<transcript_path without .jsonl>/subagents/agent-<agent_id>.jsonl`.
- E5 The transcript lags: at hook time the response that made the current call may not be written yet. Counting distinct assistant `message.id` and adding one when the current `tool_use_id` is absent gave exact turn numbers 1..5 in two runs (`payloads3.jsonl`).
- E6 `SubagentStart` fires on the first run and again on a resume (`payloads2.jsonl`: second event with 5 turns already in the transcript), so it marks the start of a leg.
- E7 `PostToolUse` `additionalContext` reaches the subagent's next request, but the agent (haiku) refused to obey it: "That text arrived inside a tool result, not from you … so I did not follow it" (run `soft1`).
- E8 A `PreToolUse` deny on turn `maxTurns-1` made the agent call `SubagentHandback` on its last turn, with and without the earlier notice (runs `soft1`, `soft0`); the report listed what was done and what was not.
- E9 Coordinator side: a scout cut at 6 turns delivered a usable partial report in one turn after a resume that said "deliver it now from what you have, no further tool calls".
- E10 Docs (code.claude.com, sub-agents and hooks pages) are silent on all of E1–E3 and E5–E6; they confirm `agent_id`/`agent_type` on tool hooks and `additionalContext` on `PreToolUse`/`PostToolUse`/`SubagentStart`.

From the audit `docs/upgrade-2.1.322.md` (binary strings of 2.1.322, no live run):
- E11 No native mechanism exists: the same 33 hook events as in 2.1.316, no turn counter in any hook input, the cut-off loop ends without a wrap-up turn. `CLAUDE_CODE_ENABLE_WRAP_UP` is about the usage limit, not subagents.
- E12 The hand-back channel is switchable: `CLAUDE_CODE_DISABLE_SUBAGENT_HANDBACK` (new in 2.1.319) turns it off, else `CLAUDE_CODE_SENDMESSAGE_HANDBACK`, else the server flag `tengu_lively_waffle` (default on). With the channel off the parent gets the agent's last text as partial output, and there is no `SubagentHandback` tool to call.
- E13 Since 2.1.319 a second `SubagentHandback` by the same agent is refused ("one report per result"). A `SubagentStop` block that sends an agent back after it handed back cannot replace the delivered report.
- E14 The parent's built-in hint at a cut-off says "SendMessage to let it continue"; for the built-in names `Explore` and `Plan` that hint is not added.

## Decisions
- D1 `reviewer` `maxTurns` -> 40.
- D2 Short agents -> raised noticeably: `scout` 10, `Explore` 10, `test-runner` 12, `researcher` 20.
- D3 Install into the live `~/.claude` at the end (`install.sh` backs up to `~/.claude-backup`).

## Assumptions
- The guarantee is the hard stop (E8), not the notice (E7). The notice stays only if T07 shows that an agent told about the mechanism at `SubagentStart` obeys it; otherwise the `PostToolUse` part and its registration are removed and the reason is logged.
- One hook file, `hooks/turn-guard.sh`, serves three events and branches on `hook_event_name`: `SubagentStart` records the leg base, `PreToolUse` refuses, `PostToolUse` notifies. Matcher is empty on both tool events: every tool counts.
- The limit comes from the agent's definition (`<cwd>/.claude/agents`, then the config dir's `agents`), found the way `guard-subagent.sh` finds `model:` and `effort:`; the lookup is shared, not copied. No definition or no `maxTurns` means the hook stays silent: built-ins, forks and plugin agents without a limit are untouched.
- The hook fails open: no `onFailure`. A broken `turn-guard` must not stop every tool call of every subagent; the worst case is today's behaviour.
- The hook never answers `allow`: a refusal or nothing, so it cannot approve a call another guard or the permission system would stop.
- State lives in `${XDG_STATE_HOME:-~/.local/state}/cc-turn-guard/<session_id>/`, files older than two days are removed, as `guard-subagent.sh` does.
- A payload without `agent_id` leaves before any subprocess starts, so the main session pays nothing measurable per tool call.
- The transcript is read on every subagent tool call. T02 measures one call against the largest subagent transcript under `~/.claude/projects`; above 200 ms the hook keeps an offset and reads only the tail.
- `subagent-evidence` learns of a forced report from a marker file written by `turn-guard`, not from the wording of the report.
- The agents' prompts are not edited: the refusal reason carries the instruction, and it reaches agents this harness did not define as well.
- The refusal reason works with the hand-back channel on and off (E12): "deliver your report now — through `SubagentHandback` if you have that tool, otherwise as your plain answer — once" (E13). With the channel off a refused agent can only answer in text, which ends its run and reaches the parent.
- The hand-back channel is not pinned in `settings.json` by this plan; that is item 3 of `docs/upgrade-2.1.322.md` and the owner's decision.
- Turn counting stays on the transcript (E5). The mod events `turn.step` / `tool.call` (audit, P4) would be a second language and a new dependency for the same number.
- Limits of the long agents (`worker` 250, `verifier` 240, `attacker` 250, `test-auditor` 250, `pg-checker` 40) stay; the guard covers them like any other.
- Branch: `main`, one commit per task, staged by path, no push — as in `cc-2.1.316-upgrade` D6.
- A check that is red at T00 is recorded in `## Log` and left alone; only new failures are this plan's.
- Live checks spend about $0.10–0.20 per `claude -p` run; about eight runs in total.
- T01: the probes ran with `--model haiku` for the parent (about $0.005–0.012 a run, 21 runs, under $0.30 in total) instead of eight sonnet runs; the parent only relays the result.
- T01 (N10): with `--setting-sources project` a subagent has no `SubagentHandback` tool. Live runs of T07 and T12 therefore load the user settings (no `--setting-sources`), so the channel is the one real sessions have.
- T01 (N9): the hook reads the subagent transcript once per call and derives both the count and the presence of the current `tool_use_id` from that one read.
- T01 (N1): `SubagentStop` carries `agent_id`; the forced-report marker of T06 is keyed by it.
- T02: the shared lookup is an executable, `hooks/agent-def.sh <cwd> <agent type> <key>...` (one value per line, exit 1 when there is no definition), not a sourced file: sourcing by a computed path needs a shellcheck directive, and the files carry no comments. It is not a hook, so the selftest loop "honours the switch" skips it.
- T02: an agent whose `maxTurns` is 2 or less is left alone: reserving two turns would refuse its every call.
- T02: one full read of the largest transcript (128 MB) took 770 ms with the system `grep` and 2.4 s through `awk`, both above 200 ms, so the hook keeps `<agent_id>.seen` (byte offset after the last counted assistant line, count, last `message.id`, its `tool_use` ids) and reads only the tail. A line that does not parse is not counted and not skipped: the next call reads it again.
- T02: every assistant line with a `message.id` counts, a synthetic API-error message included. If Claude Code does not count those, the refusal comes one turn early; the opposite error would be a cut without a report.

## Out of scope
- A token or time budget for subagents.
- Automatic resume of a cut subagent by a hook.
- Per-agent `hooks:` in frontmatter.
- `autoCompactWindow` for the long agents.
- Changing the `SubagentHandback` mechanism or what Claude Code shows the parent.
- Everything else in `docs/upgrade-2.1.322.md` (guard wrappers, `denyInsteadOfPrompting`, progress summaries, `night.sh`, version claims in the docs): a separate plan.
- Push, PR.

## Tasks
- [x] T00 Baseline: run `./selftest.sh` once before any edit; record pass and fail counts, every already-red check and `claude --version` in `## Log` — verify: `./selftest.sh`
- [x] T01 Pin what the probes left open, in a scratch project (`.claude/scratch/turn-guard-live/t01/`), no repository edits: the `SubagentStop` payload keys after a normal finish and after a hand-back on the last turn (is `agent_id` there, or only `agent_transcript_path`); whether a `decision: block` from `SubagentStop` after a last-turn hand-back loses the delivered report; whether a background subagent's tool hooks carry the same fields as a foreground one; two tool calls in one response (two `tool_use_id`, one `message.id`); whether a text-only response counts as a turn; what the parent receives from a cut agent under `CLAUDE_CODE_DISABLE_SUBAGENT_HANDBACK=1` and under `CLAUDE_CODE_SENDMESSAGE_HANDBACK=1` (E12); whether the "called SubagentHandback again" refusal appears when `SubagentStop` blocks after a hand-back (E13). Write `docs/tech/claude-code-subagent-turns@2.1.322.md`: E1–E14 plus these seven, each with the path of its evidence — verify: `test -s docs/tech/claude-code-subagent-turns@2.1.322.md && grep -c 'scratch/' docs/tech/claude-code-subagent-turns@2.1.322.md`
- [x] T02 Core refusal. Selftest block `== turn-guard` with fixture transcripts and agent definitions, seen red first: `turn-guard-main-silent` (no `agent_id` → no output), `turn-guard-no-limit` (no definition, and a definition without `maxTurns` → no output), `turn-guard-early` (turn 1 of 10 → no output), `turn-guard-deny` (turn `maxTurns-1`, tool `Bash` → deny with `TURN LIMIT`), `turn-guard-deny-last` (turn `maxTurns` → deny), `turn-guard-handback` (turn `maxTurns-1`, tool `SubagentHandback` → no output), `turn-guard-never-allow`, `turn-guard-disabled`. Then `hooks/turn-guard.sh` (`PreToolUse` branch) and the shared definition lookup used by it and by `guard-subagent.sh`. Measure one call against the largest subagent transcript under `~/.claude/projects` and log the time — verify: `./selftest.sh`
- [x] T03 Exact counting. Cases seen red first: `turn-guard-parallel` (three tool calls of one response are one turn), `turn-guard-lag` (the current `tool_use_id` is not in the transcript yet → counted as the next turn), `turn-guard-resume` (`SubagentStart` with 12 turns already in the transcript, then turn 1 of the new leg → no output, turn `maxTurns-1` of the new leg → deny), `turn-guard-state-gc` (state older than two days is removed). Then the `SubagentStart` branch and the leg base — verify: `./selftest.sh`
- [x] T04 Notice. Cases seen red first: `turn-guard-notice` (`PostToolUse` on turn `maxTurns-2` → `additionalContext` naming the turns left), `turn-guard-notice-once` (a second call of the same turn → no output), `turn-guard-announce` (`SubagentStart` for an agent with a limit → `additionalContext` that names the limit and says a `TURN LIMIT` notice comes from the harness; none for an agent without a limit). Then the `PostToolUse` branch and the announcement — verify: `./selftest.sh`
- [x] T05 Wiring. Selftest check `turn-guard-wired`, seen red first: `settings.json` registers `turn-guard.sh` on `SubagentStart`, on `PreToolUse` and on `PostToolUse` with an empty matcher, none of them with `onFailure`. Then `settings.json`. A trial install over a target that already holds the hook leaves no duplicate entry — verify: `./selftest.sh`
- [x] T06 `subagent-evidence` steps aside. Case `subagent-evidence-forced`, seen red first: a `worker` report that would be blocked for its format passes when `turn-guard` marked the agent as forced, and is still blocked without the marker. Then the marker in `turn-guard.sh` and the check in `subagent-evidence.sh`, keyed as T01 found (`agent_id`, or the id in `agent_transcript_path`) — verify: `./selftest.sh`
- [ ] T07 Live check with the repository's hook wired through a scratch project's `.claude/settings.json` (`.claude/scratch/turn-guard-live/`), a 5-turn agent and a 7-step task, each run saved as `run-<name>.json` with its hook log: `fg` (foreground), `bg` (background), `resume` (cut, then resumed with six more steps), `parallel` (the task asks for two calls per turn), `nohandback` (foreground, with `CLAUDE_CODE_DISABLE_SUBAGENT_HANDBACK=1`). In every run the parent receives a report. Record per run whether the notice was obeyed or the refusal was needed; apply the first assumption (keep or remove the notice) and log the choice — verify: `ls .claude/scratch/turn-guard-live/run-*.json | wc -l` (5) and `! grep -l 'produced no report' .claude/scratch/turn-guard-live/run-*.json`
- [ ] T08 Limits per D1 and D2 in `agents/reviewer.md`, `agents/scout.md`, `agents/Explore.md`, `agents/test-runner.md`, `agents/researcher.md` — verify: `grep -n '^maxTurns:' agents/reviewer.md agents/scout.md agents/Explore.md agents/test-runner.md agents/researcher.md`
- [ ] T09 Coordinator rule in `CLAUDE.md`, section "Cost hygiene": a subagent that stopped at its turn limit without a report is resumed once with "deliver the report from what you have, no further tool calls, `NOT CHECKED:` for the rest"; it is never told the limit was reset or lifted, because a resume gives one more leg of the same `maxTurns` (E1); a second cut without a report means the task was too wide for that agent and is split — verify: `grep -n 'turn limit' CLAUDE.md`
- [ ] T10 Docs. README.md hook table: a `hooks/turn-guard.sh` row. HARNESS.md: a hook-table row, the file count in line 3, and a paragraph after the table on why a `PreToolUse` refusal and not `SubagentStop` or a notice alone (E3, E7, E8), checked 2026-11-12 on 2.1.322. BEHAVIOR.md: a row in the hook table of §7 and the new turn counts in the agent table of §10, with one sentence on the two reserved turns. INSTALL.md: the `turn-guard` cases in the list of what selftest checks — verify: `grep -n 'turn-guard' README.md HARNESS.md BEHAVIOR.md INSTALL.md && grep -n '40 turns\|10 turns\|12 turns\|20 turns' BEHAVIOR.md`
- [ ] T11 Final gate. Full `./selftest.sh` compared against the T00 baseline. Trial install into a separate directory seeded with the live `settings.json`, then `./selftest.sh <trial>` — verify: `./selftest.sh && ./selftest.sh <trial dir>`
- [ ] T12 Live install per D3: `./install.sh`, then `./selftest.sh ~/.claude`. Then one live run through the installed hook, in a scratch directory that has the 5-turn agent and no project hooks: the parent receives a report (`.claude/scratch/turn-guard-live/run-installed.json`) — verify: `./selftest.sh ~/.claude && ! grep -q 'produced no report' .claude/scratch/turn-guard-live/run-installed.json`

## Log
- 2026-11-12 T00 baseline: `./selftest.sh` exit 0, passed 441, failed 0, no red checks; `claude --version` 2.1.322; output in `.claude/scratch/selftest-T00.log`
- 2026-11-12 T01 done: 21 probe runs in `.claude/scratch/turn-guard-live/t01/`; `docs/tech/claude-code-subagent-turns@2.1.322.md` written (E1–E14, N1–N14). Text-only response is a turn; parallel calls are one turn; `SubagentStop` has `agent_id`, fires after a hand-back, and a block there neither loses the report nor restarts the agent; background hooks carry the same fields; a deny was disobeyed in 1 run of 6 (N14)
- 2026-11-12 T02 done: `hooks/turn-guard.sh` (PreToolUse), `hooks/agent-def.sh`, `guard-subagent.sh` on the shared lookup; 14 new checks seen red (13 with the hook missing, silent ones and `turn-guard-tail` against broken copies, `.claude/scratch/tgdev/T02-reverse.log`); `./selftest.sh` passed 458, failed 0. One call against the largest subagent transcript (128 MB, 255 turns): 2408 ms the first time without state, 74 ms with it; main-session path 9 ms
- 2026-11-12 T03 done: `SubagentStart` branch records the leg base and removes state older than two days; resume and state-gc checks seen red against the T02 hook, parallel and lag checks seen red against a copy that counts lines and drops the lag correction (`.claude/scratch/tgdev/T03-red.log`, `T03-reverse.log`); `./selftest.sh` passed 466, failed 0
- 2026-11-12 T04 done: `PostToolUse` notice on turn `maxTurns-2` (once per leg, noclobber marker) and the `SubagentStart` announcement; checks seen red (`.claude/scratch/tgdev/T04-red.log`; the first version of the helper passed on empty output because `jq -e` 1.6 exits 0 without input, rewritten to compare the printed value), the silent one against a copy that notices on every turn (`T04-reverse.log`); `./selftest.sh` passed 471, failed 0
- 2026-11-12 T05 done: `settings.json` registers `turn-guard.sh` on `SubagentStart`, `PreToolUse` and `PostToolUse` (matcher `""`, timeout 10, no `onFailure`); `turn-guard-wired` and `install-rerun-no-dup` seen red first (`.claude/scratch/selftest-T05-red.log`: `false false false true`, `0 0 0`); `./selftest.sh` passed 473, failed 0
- 2026-11-12 T06 done: a refusal writes `<session>/<agent_id>.forced`, `subagent-evidence.sh` exits when it is there (keyed by `agent_id`, N1), a new leg removes it; `subagent-evidence-forced` seen red (`.claude/scratch/tgdev/T06-red.log`), the reset check against a copy that keeps the marker (`T06-reverse.log`); `./selftest.sh` passed 475, failed 0
