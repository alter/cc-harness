# Claude Code session transcripts @ 2.1.330

Retrieved 2026-11-22. Scope: the JSONL files Claude Code writes under `~/.claude/projects/`, as read by `cc-sessiontime`.

The format is almost entirely undocumented. An item cites the official page where one exists; every other item cites local evidence: the field as observed, the Claude Code versions it was seen in, and the count it was checked on. "Local sample" below means the 60 most recently modified session files on this machine (versions 2.1.299–2.1.330, 274 126 entries carrying `sessionId`), probed on 2026-11-22 by scripts that print field names and counts only (`.claude/scratch/test-run-budget/probe*.py`). Nothing here is a contract: a field may change in any release, and the reader must skip what it does not recognise.

## What is documented

- A hook receives `transcript_path`, "Path to conversation JSON"; the file "is written asynchronously and may lag the in-memory conversation" — https://code.claude.com/docs/en/hooks
- `SubagentStop` receives `agent_id`, `agent_type` and `agent_transcript_path`, "the subagent's own transcript stored in a nested `subagents/` folder" — https://code.claude.com/docs/en/hooks
- `PostToolUse` of a foreground `Agent` call carries `tool_response` with `agentId`, `totalTokens`, `usage` — https://code.claude.com/docs/en/hooks
- No official page describes an entry type, a field of an entry or the directory layout beyond the two sentences above — evidence: the hooks page read in three chunks on 2026-11-22; the Agent SDK message-type pages were not read.

## Files and directories

- One session is one file `~/.claude/projects/<project dir>/<sessionId>.jsonl`; the file name equals the `sessionId` of every entry in it — evidence: 274 126 of 274 126 entries in the local sample.
- `<project dir>` is the absolute working directory with every character outside `A-Za-z0-9` replaced by `-`: `/`, `_`, `.` and spaces all become `-`, so `my_app.v2` is stored as `my-app-v2` and `repo/.claude/scratch/x` as `repo--claude-scratch-x` — evidence: directory listing of `~/.claude/projects/` against the `cwd` recorded inside the files. The mapping loses information, so the directory name selects candidates and the `cwd` field decides.
- A session started in a subdirectory or a worktree of a repository gets its own project directory; its name starts with the repository's directory name — evidence: twelve `…-cc-harness--claude-scratch-*` directories beside `…-cc-harness`.
- Subagent transcripts live in `<project dir>/<sessionId>/subagents/agent-<agentId>.jsonl`, each with `agent-<agentId>.meta.json` — https://code.claude.com/docs/en/hooks for the folder; evidence: the `.meta.json` file, 2.1.308–2.1.330.
- `/clear` starts a new file with a new `sessionId`; background task output keeps living under the first id of the process, which entries record as `session_id` (snake case). `session_id` differs from `sessionId` in 23 220 entries of the sample — evidence: local sample. Use `sessionId`.

## Entries

- Every line is one JSON object with a `type`. Types seen: `user`, `assistant`, `attachment`, `system`, `queue-operation`, `api-request`, `api-request-shape`, `api-request-blob`, `file-history-snapshot`, `file-history-delta`, `frame-link`, `mode`, `permission-mode`, `session-owner`, `atis-latch`, `last-prompt`, `ai-title`, `custom-title`, `agent-name`, `tools-used`, `cost-state`, `relocated`, `bridge-session` — evidence: all 169 session files on this machine, 2.1.299–2.1.330.
- A top-level `timestamp` is present on every `user`, `assistant`, `attachment`, `system`, `queue-operation`, `api-request`, `api-request-shape`, `file-history-delta` and `frame-link` entry and on no entry of the other types — evidence: counts per type over the 169 files (for example `user` 67 715 of 67 715, `mode` 0 of 25 116).
- A timestamp is UTC with milliseconds, `YYYY-MM-DDTHH:MM:SS.mmmZ` — evidence: 184 147 of 184 147 timestamps in the local sample. Git records local time with an offset; compare instants, not strings.
- Entries are not strictly ordered by timestamp: a `user` or `assistant` entry is older than its predecessor 594 times in the local sample — evidence: local sample. Sort before computing intervals.
- `cwd`, `version`, `gitBranch`, `sessionId`, `entrypoint`, `userType` sit on `user`, `assistant`, `attachment` and `system` entries; `queue-operation` carries only `sessionId`, `timestamp`, `operation`, `content` — evidence: local sample.
- A `uuid` never repeats across the 169 files — evidence: 0 duplicates. The per-project scripts de-duplicated by `uuid` across files; it is harmless and costs nothing, so the reader keeps it.
- `system` entries carry a `subtype`: `stop_hook_summary`, `turn_duration`, `away_summary`, `compact_boundary`, `informational`, `api_error`, `local_command`, `permission_retry`, `agents_killed`, `scheduled_task_fire`, `bridge_status` — evidence: 11 506 `system` entries, all with a timestamp.
- Compaction writes a `system` entry with `subtype: compact_boundary` and `compactMetadata`, followed by a `user` entry with `isCompactSummary: true` — evidence: 254 boundaries and 53 summaries in the local sample.

## One API message is several entries

- An assistant message is written as one entry per content block: 111 732 of 111 735 `assistant` entries hold exactly one block. The entries of one message share `message.id` — evidence: all 169 files. A message spans 1 entry (14 434 messages), 2 (25 153), 3 (7 007) or more (4 156).
- Block types: `thinking`, `text`, `tool_use`, `server_tool_use`, `advisor_tool_result` — evidence: local sample.
- The end of a message is the latest timestamp among the entries sharing its `message.id`. A `tool_use` block is not the last entry of its message in 3 304 of 30 022 paired calls — evidence: local sample.
- A tool starts when the message ends, not at the timestamp of its `tool_use` entry — evidence: the timing report of project D: over three commits the commit time minus the message end was 0.1–0.2 s, minus the `tool_use` entry 12.5–57.3 s.
- The rule has an exception: the result is older than the message end in 927 of 30 022 calls (a tool of a multi-call message that ran while later blocks were still streaming) — evidence: local sample. A tool whose result precedes the end of its message therefore starts at its own `tool_use` entry, every other tool at the message end.

## Tool calls and results

- A call is a `tool_use` block with `id` and `name` in an `assistant` entry. Its result is a `tool_result` block with `tool_use_id` inside `message.content` of a later `user` entry — evidence: 30 022 pairs in the local sample.
- The `user` entry of a result also carries `toolUseResult` (an object for a success, a string for an error: 1 098 strings) and `sourceToolAssistantUUID`, the `uuid` of the entry holding the `tool_use` — evidence: local sample.
- `server_tool_use` (the advisor) has no `tool_result` in a `user` entry; its answer is an `advisor_tool_result` block inside the assistant message — evidence: 291 `server_tool_use`, 269 `advisor_tool_result`, 0 user-side results. Its time belongs to the message, not to a tool interval.
- A client call without a result is rare (1 of 30 023) and marks an interrupted turn; an interruption also writes a `user` entry whose text block starts with `[Request interrupted` — evidence: local sample. The reader ends such a call at the next entry of the session.
- The subagent tool is named `Agent` in every version of the sample; `Task` does not occur — evidence: 691 `Agent` calls, 0 `Task`.

## Background runs

- A `Bash` call with `run_in_background: true` returns at once; `toolUseResult.backgroundTaskId` holds the task id (9 characters) — evidence: 1 873 results over the 169 files.
- A foreground `Bash` call that outlives its timeout is moved to the background: the result carries both `timedOutAfterMs` and `backgroundTaskId` — evidence: 300 results. It is a background run from the result on.
- A background `Agent` call returns `toolUseResult` with `isAsync: true`, `status: "async_launched"` and `agentId` (17 characters) — evidence: 2 142 results.
- Completion is a `queue-operation` entry with `operation: "enqueue"` whose `content` is a `<task-notification>` block with `<task-id>`, `<tool-use-id>`, `<output-file>`, `<status>` (`completed`, `failed`, `killed`, `stopped`) and `<summary>`; an agent's notice adds `<result>` and `<usage>` with `<duration_ms>` — evidence: 5 906 such entries over the 169 files.
- The same notice is repeated when it reaches the model: as an `attachment` entry of type `queued_command` with `commandMode: "task-notification"` (`attachment.prompt` holds the block), or as a `user` entry whose `message.content` is the block as a string. The attachment carries the timestamp of the enqueue (lag median 0.0 s, 90th percentile 0.0 s over 1 435 pairs); the `attachment` form is present in every version from 2.1.299 to 2.1.330 — evidence: local sample; counts per version over all files. Count the `enqueue` and ignore the repeats.
- `<task-id>` equals the `backgroundTaskId` or the `agentId` of the launch (1 842 of 2 223 notices in the sample; the rest are `Monitor` tasks, tasks whose launch is not in the file, and 13 `Bash` calls whose result recorded no `backgroundTaskId`). `<tool-use-id>` equals the launching `tool_use` id (1 615 of 1 842) or, for a resumed agent, the id of the `SendMessage` call that resumed it (189) — evidence: local sample. Link by `<task-id>`, and by `<tool-use-id>` when the task id is unknown and the id names a `Bash` call.
- A `Monitor` sends event notices without `<status>` (99 in the sample); they do not end anything — evidence: local sample.
- An agent's task id notifies once per stop, so a resumed agent notifies again — evidence: the `<note>` of the notice, 2.1.322–2.1.330.

## Subagent transcripts

- Every `user` and `assistant` entry of an agent file has `isSidechain: true` and `agentId` — evidence: 277 254 of 277 254 entries in every agent file on this machine. The `sessionId` in them is the parent's — evidence: `agent-*.jsonl`, 2.1.322.
- `.meta.json` holds `agentType`, `description`, `toolUseId` (the parent's `Agent` call), `spawnDepth`, `finished` and, in some files, `model`, `launchedWithDefaults` and `parentAgentId` — evidence: key sets of 651 meta files.
- A foreground `Agent` result carries `agentId`, `totalDurationMs`, `totalTokens`, `totalToolUseCount`; a background one reports `<duration_ms>` in its notice — evidence: 28 foreground results (26 of them written by 2.1.322), 2 142 background.
- For an agent that ran once, `duration_ms` and the span of its file agree within 2.4 s (35 of 35 agents) — evidence: local sample.
- A resumed agent keeps writing into the same file. `duration_ms` then covers the last leg only, and first-to-last of the file overstates the work by the wait between legs: 992 s to 5 158 s in five agents of the sample — evidence: local sample; the timing report of project C. The wait is the gap between an assistant message without a call and the next prompt; an interval model that treats it as idle needs no special case.

## Differences across 2.1.309–2.1.330

- `api-request` and `api-request-shape` entries are absent in 2.1.299 and present from 2.1.300 — evidence: types per version over the 169 files.
- `totalDurationMs` on a foreground `Agent` result was seen in 2.1.299 and 2.1.322 only; every other version of the sample ran its agents in the background — evidence: counts per version over all files.
- The fields the timing tool reads are present in every version from 2.1.299 to 2.1.330 that has more than three assistant entries: `message.id` on every `assistant` entry, `tool_use_id`, `toolUseResult.backgroundTaskId`, `toolUseResult.isAsync` with `agentId`, the `queued_command` notice, `cwd` — evidence: counts per version over all files (`probe5.py`). `queue-operation` entries carry no `version`, so the `enqueue` form could not be split by version.

## Pitfalls the seven per-project scripts met

- A background run counted as idle: the main session waits, the script sees no tool call. Measure from the call to the notice — evidence: the timing report of project B.
- An agent file outside the window clipped to a negative duration and doubled the peak agent count — evidence: the timing report of project B.
- Words inside a heredoc body matched classification rules — evidence: the timing report of project E; the timing report of project D.
- A command that edits and then runs went wholly to one category, and the two orders of the rules gave two answers — evidence: the timing report of project B.
- Calls issued in one message overlap; summing them counts the same seconds twice — evidence: the timing report of project F.
- The window taken from commits misses the work before the first one — evidence: the timing report of project F.
- Attribution to a task by commit subject fails where subjects carry no task id — evidence: the timing report of project F.
- A result lags its commit by 0.2–3 s, up to 32 s when the command goes on after `git commit` — evidence: the timing report of project C.
- An agent waiting for its own nested agents is running for the harness and idle in its file — evidence: the timing report of project D.
- Task output files under `tasks/` are deleted later; the transcript is the only durable record of a background run — evidence: the timing report of project F.
- `api-request-blob` lines are large and are not conversation entries; a reader that parses every line pays for them — evidence: 21 112 blob entries in 169 files.
