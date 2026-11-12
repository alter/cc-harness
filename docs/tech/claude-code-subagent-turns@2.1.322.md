# Claude Code 2.1.322: subagent turns, the turn limit and the hand-back

Checked 2026-11-12 on Claude Code 2.1.322 (`claude --version`). Every line names the file that shows it. Paths are relative to the repository root; `scratch/` is `.claude/scratch/`, which is not committed.

Sources:
- P = `.claude/scratch/probe-turnwarn/` — probes made before the plan (hook `probe-hook.sh`, logs `payloads*.jsonl`, runs `run*.json`).
- T = `.claude/scratch/turn-guard-live/t01/` — probes of task T01 (hook `probe-hook.sh`, hook logs `logs/<run>.jsonl`, parent output `run-<run>.json` and `out-<run>.txt`). Runs whose name starts with `u-` and the two `chan-*` runs loaded the user settings; the others ran with `--setting-sources project`.
- A = `docs/upgrade-2.1.322.md` — audit of the 2.1.322 binary, no live run.
- Docs: https://code.claude.com/docs/en/sub-agents and https://code.claude.com/docs/en/hooks.

## What a turn is

- E1 `maxTurns` is per leg of one subagent: 12 model responses on the first run, 12 more after a `SendMessage` resume; the context survives the cut. One turn is one model response (one `message.id`), whatever the number of tool calls in it. Evidence: session `max-game2/1d7713f3`, agent `a493b25f82eaddc4e`; `scratch/probe-turnwarn/run2.json`.
- N4 Two tool calls of one response are two `tool_use_id` under one `message.id`, and both transcript lines appear together: four calls took two turns. Evidence: `scratch/turn-guard-live/t01/logs/fg-parallel.jsonl` (`total=1` for both calls of the first response, `total=2` for both of the second).
- N5 A response with text only is a turn. An agent that made two tool calls and then answered three times with text (a `SubagentStop` hook sent it back twice) was cut at "its 5-turn limit". Evidence: `scratch/turn-guard-live/t01/logs/textonly-bg.jsonl`, `scratch/turn-guard-live/t01/out-textonly-bg.txt`.
- N8 The count of `api-request` lines in the subagent transcript is not the turn count: a run of five responses had six. Distinct `message.id` is. Evidence: transcript of run `u-fg-last` (session id in `scratch/turn-guard-live/t01/run-u-fg-last.json`).

## What the hooks see

- E4 `PreToolUse` and `PostToolUse` inside a subagent carry `agent_id`, `agent_type`, `tool_use_id` and the parent's `transcript_path`; the subagent's transcript is `<transcript_path without .jsonl>/subagents/agent-<agent_id>.jsonl`. Evidence: `scratch/probe-turnwarn/payloads.jsonl`.
- N3 A background subagent's tool hooks carry the same keys as a foreground one: `agent_id`, `agent_type`, `cwd`, `effort`, `hook_event_name`, `permission_mode`, `prompt_id`, `session_id`, `tool_input`, `tool_name`, `tool_use_id`, `transcript_path`. Evidence: `scratch/turn-guard-live/t01/logs/u-bg-normal.jsonl` against `scratch/turn-guard-live/t01/logs/u-fg-last.jsonl`. Since 2.1.322 the Agent tool starts a subagent in the background unless `run_in_background: false` is passed (`scratch/turn-guard-live/t01/run-normal.json`).
- E5 The transcript lags: at hook time the response that made the current call may not be written yet. Distinct assistant `message.id` plus one when the current `tool_use_id` is absent gave exact turn numbers. Evidence: `scratch/probe-turnwarn/payloads3.jsonl`; `scratch/turn-guard-live/t01/logs/fg-last.jsonl` (turn 3: `total=2`, `present=0`).
- N9 The count and the presence test must come from one read of the transcript. The probe hook read the file twice; when the write landed between the two reads it numbered a second turn as turn 1. Evidence: `scratch/turn-guard-live/t01/logs/u-bg-deny.jsonl` (two `PreToolUse` lines with `turn=1`).
- E6 `SubagentStart` fires on the first run and again on a resume, so it marks the start of a leg. Its payload has `agent_id` and `agent_type`. Evidence: `scratch/probe-turnwarn/payloads2.jsonl`.
- E3 `SubagentStop` does not fire at the cut-off. Evidence: `scratch/probe-turnwarn/payloads.jsonl`; `scratch/turn-guard-live/t01/logs/bg-cut.jsonl` (no such event).
- N1 `SubagentStop` after a normal finish carries `agent_id`, `agent_type`, `agent_transcript_path`, `stop_hook_active`, `background_tasks`, `effort`, `permission_mode`, `session_crons`. `last_assistant_message` is present only when the agent finished with text; after a `SubagentHandback` call — early or on the last turn — the event still fires and the key is absent. Evidence: `scratch/turn-guard-live/t01/logs/fg-normal.jsonl` (text finish), `scratch/turn-guard-live/t01/logs/u-fg-last.jsonl` (hand-back on turn 5 of 5).

## The cut-off and the hand-back

- E2 At the limit the agent is cut with no wrap-up turn. With the hand-back channel on, the parent gets "It was still calling tools and had produced no report … Its unsent text is not shown". Evidence: `scratch/probe-turnwarn/run1.json`.
- E11 No native mechanism exists: the same 33 hook events as in 2.1.316, no turn counter in any hook input. `CLAUDE_CODE_ENABLE_WRAP_UP` is about the usage limit. Source: A.
- E12 The hand-back channel is switchable: `CLAUDE_CODE_DISABLE_SUBAGENT_HANDBACK` turns it off, else `CLAUDE_CODE_SENDMESSAGE_HANDBACK`, else the server flag `tengu_lively_waffle`. Source: A.
- N6 What the parent receives from a cut agent. Channel on (default with user settings, or `CLAUDE_CODE_SENDMESSAGE_HANDBACK=1`): the note "stopped at its 5-turn limit … had produced no report" and "ended without delivering a report through SubagentHandback". `CLAUDE_CODE_DISABLE_SUBAGENT_HANDBACK=1`: the same note, then a `[Subagent hand-back]` frame whose body is `(no text output)`. Evidence: `scratch/turn-guard-live/t01/out-u-fg-cut-sendmsg.txt`, `scratch/turn-guard-live/t01/out-u-fg-cut-disable.txt`.
- N10 With `--setting-sources project` the subagent has no `SubagentHandback` tool at all, foreground or background: it ends with text and the parent gets that text in a `[Subagent hand-back]` frame. With the user settings loaded both foreground and background agents have the tool. The cause of the difference was not identified. Evidence: `scratch/turn-guard-live/t01/out-chan-sonnet-proj.txt` against `scratch/turn-guard-live/t01/out-chan-haiku-all.txt`; `scratch/turn-guard-live/t01/logs/u-bg-normal.jsonl`.
- N11 With the text channel a cut agent's last text reaches the parent as "PARTIAL output" when its last response had text beside the tool call. Evidence: `scratch/turn-guard-live/t01/out-fg-last-block.txt`.
- E13 Since 2.1.319 a second `SubagentHandback` by the same agent is refused. Source: A.
- N2 A `decision: block` from `SubagentStop` after a hand-back does not lose the report: the parent received it both after a hand-back on the last turn and after an early one. The block is written to the subagent transcript as `hook_blocking_error`, but no further model request follows: a `SubagentHandback` call ends the run. Evidence: `scratch/turn-guard-live/t01/out-u-fg-last-block.txt`, `scratch/turn-guard-live/t01/logs/u-fg-last-block.jsonl`, `scratch/turn-guard-live/t01/logs/u-textonly-fg.jsonl`.
- N7 The "called SubagentHandback again" refusal did not appear when `SubagentStop` blocked after a hand-back, because the agent never ran again (N2). Evidence: `scratch/turn-guard-live/t01/logs/u-fg-early-block.jsonl`, `scratch/turn-guard-live/t01/logs/u-textonly-fg.jsonl`.
- N12 With the text channel a `SubagentStop` block does send the agent back, and the responses it makes then count against the limit (N5). Evidence: `scratch/turn-guard-live/t01/logs/fg-early-block.jsonl`, `scratch/turn-guard-live/t01/logs/textonly-bg.jsonl`.
- E14 The parent's built-in hint at a cut-off says "SendMessage to let it continue"; for the built-in names `Explore` and `Plan` it is not added. Source: A.

## Steering the agent before the cut

- E7 `PostToolUse` `additionalContext` reaches the subagent's next request, but the agent (haiku) refused to obey it: "That text arrived inside a tool result, not from you". Evidence: `scratch/probe-turnwarn/run3-soft1.json`.
- E8 A `PreToolUse` deny on turn `maxTurns-1` made the agent call `SubagentHandback` on its last turn. Evidence: `scratch/probe-turnwarn/run3-soft1.json`, `scratch/probe-turnwarn/run3-soft0.json`; repeated in `scratch/turn-guard-live/t01/out-u-fg-last.txt` (foreground) and `scratch/turn-guard-live/t01/out-u-bg-deny.txt` (background). The agent sees the reason as a tool result that starts with `PreToolUse:Bash hook error:`.
- N13 The same deny with the hand-back channel off: the agent answered in text on its last turn and the parent received the partial report. Evidence: `scratch/turn-guard-live/t01/out-fg-deny-disable.txt`, `scratch/turn-guard-live/t01/out-fg-last.txt`.
- N14 The deny is not obeyed every time. In one run of six with a deny the agent (haiku) wrote "That message came back inside a tool result … so I'll keep going and retry it", spent its last turn on the same call and was cut. Evidence: `scratch/turn-guard-live/t01/out-fg-last-block.txt`, `scratch/turn-guard-live/t01/logs/fg-last-block.jsonl` (deny on turns 4 and 5).
- N15 An agent told at `SubagentStart` that `TURN LIMIT` messages come from the harness obeyed the `PostToolUse` notice in five runs of five (haiku), foreground, background, with parallel calls and with the hand-back channel off; no refusal was needed. Evidence: `scratch/turn-guard-live/hooklog-fg.jsonl`, `scratch/turn-guard-live/hooklog-bg.jsonl`, `scratch/turn-guard-live/hooklog-parallel.jsonl`, `scratch/turn-guard-live/hooklog-nohandback.jsonl`, `scratch/turn-guard-live/run-fg.json`.
- N16 On a resume the `SubagentStart` hook fires, but its `additionalContext` is not given to the agent: the transcript has `hook_success` for the event and no `hook_additional_context`, while the first start has both. Whatever a resumed agent must know has to be in its context already. Evidence: subagent transcript of `scratch/turn-guard-live/first-resume.json` (session id inside), `scratch/turn-guard-live/first-resume-hooklog.jsonl`.
- N17 A resumed agent that had been told "tool calls are refused" kept to it: the second leg made no tool call and answered "The harness capped this run at 5 turns … I have no way to start new calls". Evidence: `scratch/turn-guard-live/first-resume.json`.
- E9 Coordinator side: a scout cut at 6 turns delivered a usable partial report in one turn after a resume that said "deliver it now from what you have, no further tool calls". Evidence: the session that wrote the plan; no file kept.
- E10 The documentation is silent on E1–E3, E5 and E6; it confirms `agent_id`/`agent_type` on tool hooks and `additionalContext` on `PreToolUse`, `PostToolUse` and `SubagentStart`. Source: Docs.

## Pitfalls for a hook that counts turns

- Read the transcript once per call (N9).
- Count distinct `message.id`, not `api-request` lines and not tool calls (N4, N8).
- Text-only responses count (N5): an agent sent back by a `SubagentStop` hook spends turns without any tool call.
- The refusal reason must work without the `SubagentHandback` tool (N10, N13).
- A refusal on the last turn alone leaves no turn for the report; a refusal on the last two leaves one, and one disobeyed refusal still ends in a cut (N14).
