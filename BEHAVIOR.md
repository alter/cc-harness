# Behaviour — from session start to the end of the night

In one sentence: this harness turns Claude Code into an executor that asks once before the work, runs to the end of the plan in a single session, and cures breakage with a diagnosis instead of a retry. Everything that can be checked mechanically is checked by a hook outside the model's context; everything that cannot is set by the contract in `CLAUDE.md` and by the procedures in the skills.

The layers, bottom to top: **settings** (what the model may do), **hooks** (what it will not be allowed to do, or will be forced to do), **the `CLAUDE.md` contract** (how it behaves), **skills** (the procedure for a specific situation), **subagents** (where the noise goes).

---

## 1. Session start

Every `claude` launch, and also `/resume`, `/clear`, `/fork` and the moment after context compaction:

1. `~/.claude/CLAUDE.md` (the contract, 60 lines) and `<project>/CLAUDE.md` = `@AGENTS.md` (the project's facts) are loaded. Rules in `.claude/rules/<area>.md` with `paths:` load only when the model touches a matching file.
2. The `session-start` hook looks for a plan with `status: running` in `docs/plans/*.md`, `tasks/*/PLAN.md`, `tasks/*/*/PLAN.md`. If it finds one with open tasks, it injects a single line into the context: where the session came from (`Context was just compacted` / `Session resumed` / `Fresh context` / …), the plan's path, how many tasks are open and blocked, the next three tasks, the last two `## Log` lines, and an instruction not to ask questions but to continue under `/run` semantics. If there is no such plan, or `.claude/plan-pause` exists, it stays silent.
3. The status line (`statusline.sh`) shows: the directory, model and effort, context used in %, the 5-hour window in % with minutes to reset, the 7-day window in %, cache state (`warm` / `cold:<cause>`, plus the re-caching cost), and the hit ratio.

The effect: after any interruption — compaction, a usage limit, a restart — the model knows where it is in the plan without asking anything.

## 2. Every turn — what the settings decide

| Setting | Value | Behaviour |
|---|---|---|
| `model` / `advisorModel` | `sonnet[1m]` / `opus` | the work runs on Sonnet; Opus joins by itself as an advisor at decision points (`/advisor`, split evidence in `/diagnose`) |
| `effortLevel` / `maxEffortLevel` | `medium` / `high` | medium reasoning depth by default; the ceiling is `high`, so `xhigh` is unavailable even if the model asks for it |
| `modelSettings.claude-opus-5.maxEffortLevel` | `high` | the advisor does not go to `xhigh` either |
| `autoCompactEnabled`, no `autoCompactWindow` | `true`, unset | compaction only at the model's limit (~1M), not earlier. The owner's decision: one session per plan, the memory of *why* is worth more than the price of a turn |
| `autoContinueAtUsageLimit` | `true` | on hitting the limit the session waits for the reset and continues by itself (switch off for daytime with `--settings '{"autoContinueAtUsageLimit":false}'`) |
| `promptCacheTtl`, `subagentPromptCacheTtl` | `1h` | a pause of up to an hour between turns (subagents included) does not drop the prompt prefix from cache |
| `workflowKeywordTriggerEnabled`, `ultracode`, `workflowSizeGuideline` | `false`, `false`, `small` | multi-agent workflows are not triggered by a keyword in a prompt; agent teams (~7× tokens) are off |
| `includeCoAuthoredBy` | `false` | commits without a co-author line |
| `CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS` | `3` | no more than three subagents at once |
| `CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH` | `2` | a subagent may spawn a subagent, but no deeper |
| `CLAUDE_CODE_SUBAGENT_MODEL` | `sonnet` | a subagent without an explicit model runs on Sonnet, it does not inherit Opus |
| `CLAUDE_CODE_MAX_WEB_SEARCHES_PER_SESSION` | `60` | a ceiling on searches per session |
| `MAX_MCP_OUTPUT_TOKENS` | `8000` | an MCP tool's answer is cut at 8k tokens |
| `CC_*` | see §6 | thresholds for the hooks |

## 3. A new project — `/intake` (once)

1. Look first, ask second: language and framework versions, package manager, lockfile, tests, linter, CI, Docker, an existing `AGENTS.md`/`README.md`/`docs/`. If `docs/PROJECT.md` already exists, read it and ask only about the `_unanswered_` cells.
2. The interview goes through AskUserQuestion, up to 4 questions per call, calls back to back, and never again afterwards: the name and who else touches this code; the goal and the first end-to-end journey (and what the first version must NOT do); which capabilities are needed (accounts, storage, payments, background work, scheduling…); which irreversible actions may run unattended and which never may; environments and network; the exact "done" commands (tests, linter, types, architecture check) and whether a red baseline is accepted; the delivery order.
3. It does not ask about file layout, naming, library choice when the repo already has one, formatting, or anything listed under "decided by the agent".
4. It writes `docs/PROJECT.md`: the **capability ledger** (`included` / `available` / `absent` / `removed`; no row means `absent`; dead code and an old migration are not a request), **"decided by the agent"** (classes of decision that are never asked about), **gate checks** (the commands verbatim; `/plan` copies them into every task), **the unattended policy** and what must become `[!] BLOCKED`.
5. If there is no `AGENTS.md`, it creates one from the template and makes `CLAUDE.md` contain only `@AGENTS.md`. It suggests `.claude/rules/*.md` with `paths:`. It runs `scripts/project_check.py`.

The result is a five-line summary and a path. After that there are no more questions about the project.

## 4. New work — `/task`, then `/plan`

### `/task`

- Reads the tree's own rules first: `tasks/README.md` (which outranks the skill), `PROTOCOL.md`, `GOAL.md` (a task names the gate it serves, or says it serves none), `DECISIONS.md` (never re-open a recorded `D<n>`), `check.py`. If there is no tree: `/task init` copies the template and interviews for `GOAL.md` (the promise, the gates, signs of progress and signs of self-deception, the stop condition), `ROLES.md` and the label vocabulary.
- Placement: a phase is `NN-<slug>` in steps of 10, numbered in dependency order; a task takes the next free number, never renumbering; the slug names the artefact, not the activity.
- One batch of questions, only what cannot be derived from the repository and `GOAL.md`: which artefact will exist and where (OUTCOME); what is explicitly out (the `−` lines) and who owns the excluded part; the role, and whether a person is required (then a separate `role:HUMAN` task or a VERIFY item marked HUMAN); priority and milestone; hard dependencies.
- Writes `task.txt` (TASK, GOAL, CONTEXT — 3–7 paths, SCOPE with `+`/`−`, OUTCOME as a path or a measurable value, VERIFY with numbered checks and at least one reverse control, ROLE, DEPENDS) and `labels.txt` (`status:todo`, `verify:pending`, …). In a Russian-language tree, without transliterated jargon.
- `python3 tasks/check.py` — zero problems, or the task is not created. Prints the path and the next step, `/plan <directory>`.

### `/plan`

**Phase 1, reconnaissance, no questions.** Read the task, the tree's rules, `docs/PROJECT.md` (gates, the night policy, the ledger, "decided by the agent" — already settled, never re-asked; if there is no `PROJECT.md` and the task spans modules, suggest `/intake`). Repository discovery is delegated to `scout`; the session does not read the repository itself. Stack versions are pinned. Every fork is first attacked with the repository, the docs and known preferences; only what survives becomes a question.

**Phase 2, the interview — all questions, once.** AskUserQuestion, up to 4 per call, calls back to back, and never again. A question is asked only if the answer changes the code; options are concrete, the recommended one first. Mandatory coverage: boundaries (what is out), acceptance criteria, irreversible actions, external systems, what to do when tests are already red, and priority if time runs out.

**Phase 3, the plan file.** `PLAN.md` in the task directory (built from `task.txt`: GOAL → Goal, VERIFY → acceptance criteria with commands, HUMAN items marked and not closable by `/run`; `+` → Tasks; `−` → Out of scope verbatim; DEPENDS → every dependency must be `status:done`, otherwise the first task is `[!] BLOCKED: depends on …`), otherwise `docs/plans/<slug>.md`. Sections: `status`, Goal, Acceptance criteria, Stack, Decisions, Assumptions, Out of scope, Tasks, Log. Task rules: `T00` is the baseline (gate checks before any edit, the pre-existing red recorded in the Log); every task is ≤ ~1 hour and ends in a verifiable state with a command that includes the gate checks; an architectural decision becomes a check (`import-linter`), not a paragraph; anything in the "must become BLOCKED" column of `PROJECT.md` is a separate task at the end marked `(needs confirmation)`; a task that adds a capability also updates its ledger row; 20 small tasks beat 5 vague ones.

**Phase 4, hand-off.** One final question: "clean window" (recommended) → `status: running`, print the two lines `/clear` and `/run <plan>` and stop (the interview noise stays out of the execution context; `session-start` will bring the plan back after `/clear`); "start here, now" → `running` and straight into execution (sensible up to ~10 tasks); "I will edit it first" → stop.

## 5. Execution — `/run`

### The default mode: one session for the whole plan

Input: a plan path or a task directory; empty means the single `running` plan, or the single `draft` when none is running (it is set to `running`). The word `delegate` in the arguments switches on the fallback mode below.

The session does the tasks itself, one at a time, following the `run-task` procedure:

1. **Reads only**: the `T##` line, `## Goal`, `## Decisions`, `## Assumptions`, `## Out of scope`, the last 10 lines of `## Log`; in a tree, that task's `task.txt` (CONTEXT lists what to open first) and `PROTOCOL.md`; `docs/PROJECT.md` §5–6. Other tasks' details only if named as a dependency.
2. **Checks its authority**: `(needs confirmation)` on the line, or an action from the "must become BLOCKED" column → `- [!] BLOCKED: needs confirmation`, a Log line, next task.
3. **Does the work**, keeping noise out of the context: repository search → `scout`; tests, builds, linters, long commands → `test-runner`; documentation, changelogs, an unfamiliar subsystem → `researcher`; a review before a risky commit → `reviewer`. It reads only what it will edit, and only the window it needs (Grep first).
4. **Verifies**: the task's `verify:` command, the tests covering the files it touched, plus the gate checks (the coverage ratchet among them when `docs/PROJECT.md` §6 lists it — a fallen floor fails the task). Pass → `- [x]`, a `- <time> T## done: …` line in the Log, `git add <the files it changed>` and a commit (never `git add -A`: submodule pointers and marker files). Fail → `/diagnose` (§7). Still red → the line stays `- [ ]` and the Log gets `- <time> T## open: <root cause or best hypothesis, with evidence>`, so the next attempt starts from evidence rather than zero.
5. **A decision made alone** → one line under `## Assumptions`. A question to the user: never.
6. Between tasks: nothing. No `/clear`, no manual `/compact`, no recap of what was done. The next task starts from the plan line. If the model catches itself re-reading the plan header, that is context bloat, not progress.

**Forbidden** during `/run`: asking; `git stash`, `reset --hard`, `clean`, switching branches (user changes in the way → `[!] BLOCKED`, move on); building anything the ledger marks `absent`/`removed`; ending a turn while tasks are open; repeating a failed command unchanged; expanding scope (extras go to `## Out of scope` or a new task at the end); touching anything under `## Out of scope`; switching model or effort mid-run (it drops the cache).

**Task-tree rules** (when the plan lives in `tasks/<phase>/<NN>-<slug>/`; the tree's `README.md` and `PROTOCOL.md` outrank the skill):
- `labels.txt` `status`: `in_progress` while running; `done` only when every OUTCOME artefact exists **in the repository** (`test -f`, `git cat-file -e HEAD:<path>`, the count matches) and the gates pass. An OUTCOME outside the repository (a machine at a provider, a phone, a signed build, a person's eyes) is never closed by this session: it stays `in_progress` and `NOTES.md` says what is missing and who can provide it.
- `verify:` is never touched. That belongs to `/verify`, in another context.
- Blocking: besides `[!] BLOCKED`, write `BLOCKED.md` in the task directory (date; exactly what is missing — a variable name, a task path, a question; what was done before stopping, with paths; what can be done without it) and set `status:blocked`. A stub instead of a secret, "hardcode it for now", "assume the provider is X" — that is a false `done` with delayed discovery, not a workaround.
- `NOTES.md` with a dated heading: rationale, measurements with sources, rejected alternatives, this session's assumptions. A number without a source is not written.
- Reverse control: VERIFY items that demand it are executed and the red output is kept in `NOTES.md`.
- Before closing: `python3 tasks/check.py` — zero problems. Commit messages follow `PROTOCOL.md`; submodules in its order.

**Finish.** No open tasks and all `[x]` → `status: done`, one more run of every acceptance criterion, each one marked; in a tree, the `labels.txt` rules above plus a suggestion to run `/verify <directory>` in a fresh context; then a report: what changed, why, which checks ran with results, remaining risk, a suggested commit message. If any `[!]` remain → `status: paused`, a list of the blocked tasks with reasons, and the last word is `NEED_HUMAN`. Only that word releases the stop-guard.

At the start, `/run` says once: "to make this survive API hiccups, type `/goal all tasks in <plan> are [x] or [!]`" — and does not wait for an answer.

### The fallback: `/run <plan> delegate`

The session becomes a coordinator and edits nothing. The loop: `Grep -n '^- \[ \] '` → the first open task; spawn `worker` (a fresh context, not a fork) with `<plan> <T##>`; on return, Grep that line: `[x]`/`[!]` → next; still `- [ ]` with an `open:` Log line → a second `worker` with "second attempt: start from the open: evidence in Log"; still open → `- [!] BLOCKED: two attempts failed, see Log`. One worker at a time; several only when the tasks live in different task directories (different `task.txt`, the ownership boundary from `ROLES.md`). The coordinator reads no source files, no tool output and no transcripts; a worker's report is a claim, the plan file is the truth. The price: every worker is a cold start of 10–20k tokens of cache write with zero memory of earlier tasks. Use it for long plans of independent tasks.

## 6. The guards — hooks that fire by themselves

All of them are commands outside the model's context; their decisions cannot be argued with. Counters live in `~/.local/state/cc-*` and are cleaned after two days.

| Hook | Event | Condition | Action |
|---|---|---|---|
| `bash-read-guard` | `PreToolUse(Bash)` | a bare whole-file read in the shell: `cat`, `less`, `nl`, `view`, or `head`/`tail` with an explicit window above the limit, on a text file over `CC_READ_GUARD_LINES` lines; a pipe, a redirect or a substitution means the output is processed rather than read, and passes | **refuse**, naming the file and its length: Grep and a windowed Read, or pipe it through grep/sed |
| `read-guard` | `PreToolUse(Read)` | a text file over `CC_READ_GUARD_LINES`=500 lines, without `offset`/`limit`; exempt: `docs/plans/*`, `CLAUDE.md`, `.claude/*`, `*.json/toml/yaml/yml/lock/md`, binaries | **refuse**, with the text "Grep -n first, then Read a window; if you need the whole file, give it to `scout`/`researcher` and ask for a summary" |
| `compress-output` | `PostToolUse(Bash)` | output of at least `CC_COMPRESS_MIN_LINES`=40 lines | strips ANSI and trailing spaces, collapses identical consecutive lines into `(xN)`, squeezes blank lines; above 260 lines the full output goes to `.claude/scratch/bash-<ts>-stdout.log` and the model gets the first 120 and last 120 lines with a note saying how many were omitted and where the file is. It replaces the tool output (`updatedToolOutput`) |
| `retry-guard` | `PostToolUse(Bash)`, `PostToolUseFailure(Bash)` | the same command (after whitespace normalisation) exiting non-zero; a success resets the counter | 2nd failure in a row → into the context: "a third attempt is forbidden, switch to `/diagnose`: save the error to a file, pin the versions, read the trace bottom-up, three hypotheses, ROOT CAUSE with evidence before any edit"; 3rd and later → "you are in a trial-and-error loop; stop; write `ROOT CAUSE:` and `EVIDENCE:` before the next call; split evidence → the advisor; outside your control → `[!] BLOCKED`". This is an instruction into the context, not a mechanical ban: a mechanical ban here would break legitimate repeats, such as waiting for a port |
| `guard-subagent` | `PreToolUse(Agent\|Task)` | subagent spawns this session ≥ `CC_SUBAGENT_BUDGET`=40 | **refuse**: "do it in the main thread, or ask the user to raise the ceiling" |
| `subagent-evidence` | `SubagentStop` | reads the subagent's transcript, counts `tool_use` entries by name, and compares them with the report (§10) | mismatch → **send the subagent back to work** with "EVIDENCE GUARD: … use the tools now and end with a `TOOLS USED:` line, or say `NOT DONE: <why>`". Once only: on `stop_hook_active` it steps aside so nothing loops |
| `guard-model-switch` | `PreModelSwitch` | context over `CC_SWITCH_CTX_LIMIT`=40,000 tokens | **ask the user**: "the switch will re-cache N tokens; use a subagent with an explicit model, or `/clear`" |
| `stop-guard` | `Stop` | a `running` plan with open `- [ ]`; no `.claude/plan-pause`; no `NEED_HUMAN` in the last message; continuations this session below `CC_STOP_GUARD_CAP`=300; and the open-task count has moved within the last `CC_STOP_GUARD_STALL`=3 blocks | **refuses to let the turn end**: "the plan has N open tasks, next are …, continue; `[x]` only after the check passes; `[!] BLOCKED` only for irreversible actions, missing credentials or a missing dependency". Desktop notification on every exit: `NEED_HUMAN` ("Claude needs you"), zero open ("Plan finished"), ceiling reached ("Stop-guard cap reached"), nothing closed across three blocks ("Plan not advancing" — the plan is stale or everything left is waiting on something) |
| `notify` | `Notification` | `permission_prompt`, `idle_prompt`, `usage_limit`, `elicitation_dialog` | a notification through `osascript` (macOS) or `notify-send`, with the project directory and the first 200 characters of the text |
| `session-start` | `SessionStart` | an active plan with open tasks | see §1 |

What the hooks do **not** do: they never edit code, never commit, never touch the network, never call the model. Each runs within 20 seconds and steps aside silently on error (except refusals, which are always explicit).

## 6a. Tests — what stops a fix from breaking something else

The failure this exists for: the model fixes T07 and quietly trades away a behaviour that T03 relied on, and
nobody is awake to notice.

- A behaviour change is not closed until a test covers it, and that test was **seen failing** before the
  change. `/plan` puts it in the task line; the contract repeats it; a test that was green on its first run
  has proved nothing yet.
- Every fixed bug gets the test that would have caught it, in the same task.
- Before `[x]`: the tests covering the touched files, then the gate checks. Before the plan closes: the full
  suite, compared with the `T00` baseline in `## Log` — a test green at `T00` and red now is a regression this
  run caused, and it is fixed or the plan ends `paused` naming it.
- `scripts/coverage_gate.py` holds a floor in `.coverage-gate.json`: it rises when coverage grows, never
  falls by itself, and exits non-zero when coverage drops past the tolerance. Lowering it is a decision
  written into `docs/PROJECT.md` with a date and a reason.
- `/test` is the procedure: measure first, choose by risk (money and data, branchy code, every past defect,
  contracts, then stop), write red first, then break the code in a scratch copy to prove each guard can go
  red — the same reverse control the task tree demands. Wording, layout and log text are never asserted.
- What coverage cannot see: a test that runs a line without noticing it is wrong. `/test` §5a is a one-off
  mutation audit (`mutmut`, `stryker`) on a single module where a wrong value is worse than a crash; every
  surviving mutant becomes a task quoting the mutation. By hand, never a gate check, and the score is not a
  target — the survivors are.

## 7. Breakage — `/diagnose`

Triggered by the contract after the first non-trivial failure (a build, a test, a command, an integration), and by `retry-guard` after the second identical one. Rule zero: no code change until `ROOT CAUSE:` is written as one sentence with evidence attached.

1. **Freeze and capture**: reproduce once, deterministically; the command, exit code and full output go to `.claude/scratch/diag-<ts>.log` (a large run goes through `test-runner`); the primary error is the first exception / first non-zero exit / first failed assertion, not the last line; `git status`, `git diff`, `git log -15` — what changed since the last known-good state.
2. **Pin versions off the machine**, not from memory: the language, the failing library (`pip show`, the lockfile), the framework and any SDK, the OS and architecture if the failure smells native. All documentation and searches below are for those versions.
3. **Walk the levels**, one line each ("n/a" is an answer, "didn't check" is not): helicopter view (what the system is trying to do, which part fails, our code or below it); environment (variables, config files, paths, permissions, ports, DNS, time, locale); dependencies (version drift, conflicts, a lockfile that disagrees with what is installed); logs at a raised level (`--log-level DEBUG`, `-X dev`, `NODE_DEBUG`), the 50 lines before the error; the stack trace bottom-up to the first frame of ours, the full chain if async; state (does it fail on empty input too); measurements when it is flaky (three runs with timings); a debugger in scratch for logic errors.
4. **Hypotheses**: at least three, ranked by evidence; for the leading one, the single experiment that would refute it; run that experiment; refuted → next one. Nothing is "fixed" while experimenting.
5. **Official documentation for the pinned version** — through `researcher`: the docs of that version (not latest), the changelog and migration notes between versions, the reference for the exact failing call, issues for the exact error string in that version range. What comes back: quotes with URLs and a verdict — documented, deprecated, or a known bug.
6. **Unofficial workarounds**: search the exact error string; any workaround is first reproduced in scratch, explained through the root cause, and rejected if it only masks the symptom.
7. **Split evidence**: two hypotheses with equal support, or docs contradicting observation → one advisor call (Opus) with the evidence table. No coin flips.
8. **One fix**: `ROOT CAUSE:` and `EVIDENCE:` into the plan's `## Log`; one fix; the original reproduction again; a regression test where a suite exists. If it did not help, you are back at step 4 with new evidence, not at "try again".

## 8. Checking someone else's work — `/verify`

Independence is the whole point. If this session wrote the code or the tests, it does not verify: the whole job goes to `verifier` (a fresh context) and the result is relayed. `verify:passed` is never set on one's own work.

1. Read, do not trust: the tree's rules, `task.txt` (every VERIFY item, every `−` line, the OUTCOME); `NOTES.md`, an old `VERIFY.md`, commit messages — as claims to be tested.
2. Does the OUTCOME exist: `test -f`, `git cat-file -e HEAD:<path>` (on disk and in a commit are different facts), the count matches, the recorded run opens. An OUTCOME outside the repository is "cannot verify here", item by item, and does not pass.
3. Reproduce from a clean state: for every item, a command a third party can run with a fresh checkout and an empty environment, with nothing exported by hand; run by the verifier in `.claude/scratch/` or `/tmp`, without modifying the repository. A check that depends on the author's shell is a failure by definition.
4. Reverse control: at least one check is made red on purpose (in a copy) and the red output is recorded; a suite that stays green under mutation is a finding.
5. `VERIFY.md` in the tree's language: the verifier line (who, when, what they did NOT do, what they ran); a per-item verdict (pass / fail / cannot verify here — why); reproduction from a clean state with the expected output; reverse control; "what was not checked" — never empty; the verdict `verify:passed|failed` in one sentence.
6. Labels: only `verify:` in `labels.txt`. If `status:done` is set while the OUTCOME is missing, leave `status` alone and record the mismatch in `VERIFY.md`. Findings outside this task's SCOPE go into the owning task's `NOTES.md` or become a proposed new task — never a silent fix. `tasks/check.py` at zero.

## 9. The night, unattended

`cc-night <plan>` (`night.sh`): checks that `status` is `draft|running`, sets it to `running`, clears `.claude/plan-pause`, and starts `claude --dangerously-skip-permissions --effort high --name night:<slug> --settings '{"autoContinueAtUsageLimit":true}' "/run <plan>"`. Sandbox without production credentials only.

Three layers keep it from stalling:
1. the contract and `/run` — do not end a turn while a `- [ ]` remains;
2. `stop-guard` — a deterministic return to work, up to 300 times per session;
3. `/goal all tasks in <plan> are [x] or [!]` — built into Claude Code, typed by you before you leave; it retries on API failures after 1, 5 and 15 minutes and waits out a usage-limit reset.

Plus `autoContinueAtUsageLimit` (hit the limit, wait, continue) and `session-start` (compaction, plan back in context).

To stop: `touch .claude/plan-pause` or `status: paused` in the plan file. In the morning: the plan's `## Log` says what was done and with what evidence; `BLOCKED.md` says what was missing; the notification already told you how it ended.

## 10. Subagents — where the noise goes and what is demanded of them

| Agent | Model / effort | Tools | For what | What `subagent-evidence` checks on return |
|---|---|---|---|---|
| `Explore` (built-in, overridden) | haiku, 6 turns, no CLAUDE.md | Read, Grep, Glob | read-only search | at least one Grep/Glob/Read call and a file path in the answer, or an explicit `NOT FOUND` after at least one call |
| `scout` | haiku, 6 turns, no CLAUDE.md | Read, Grep, Glob | where the code, config or test lives — paths and lines, changes nothing | the same |
| `test-runner` | sonnet low, 8 turns, no CLAUDE.md | Bash, Read, Grep | runs the named command, short failure analysis | Bash was called; the answer contains `COMMAND:` and `PASS`/`FAIL` with counts |
| `researcher` | sonnet medium, 12 turns, no CLAUDE.md | Read, Grep, Glob, WebFetch, WebSearch | a map of an unfamiliar subsystem, docs for the pinned version | at least one call and an `EVIDENCE` section with path:line or a URL |
| `reviewer` | opus high, 12 turns | Read, Grep, Glob, Bash | refute the change: bugs, races, edges, contracts | Read was called |
| `verifier` | sonnet high, 40 turns | Bash, Read, Grep, Glob, Write, Edit | independent verification, writes `VERIFY.md` | Bash and Write/Edit were called |
| `worker` | sonnet high, 80 turns, `run-task` preloaded | all | one plan task in delegate mode | Edit/Write/Bash was called; the report reads `T## done\|blocked\|open: …` |
| anything else | — | — | — | at least one tool call behind a claim of "done" |

`Explore` and `scout` may also answer from a code graph when the session exposes one (`mcp__…graph…__*`, see the README's optional section): the evidence hook counts a graph call as a search, but the answer must still name a `path:line`.

Common to all: the answer ends with `TOOLS USED: <name:count …>`; `NOT DONE: <why>` is always allowed and never checked. The main session's contract adds: a subagent's report is a claim, not a fact; a path from `scout` is Read before use; a test result without `COMMAND:` and an exit code is rerun; a `TOOLS USED` line that does not fit the answer means the answer is discarded.

## 11. The three complaints — exactly where each is closed

**Questions in the middle of the work.** `/intake`, `/task` and `/plan` ask everything in batches of up to 4 before the plan is written; after `status: running` the contract forbids asking: a fork becomes a choice consistent with `## Decisions`, recorded under `## Assumptions`, and the work continues; "decided by the agent" and the unattended policy in `PROJECT.md` answer most future questions in advance; the only exit is `NEED_HUMAN`, and only when everything remaining is blocked.

**It did two tasks and stopped.** The contract → `stop-guard` (a mechanism, `decision: block`) → `/goal` (retries on failures) → `autoContinueAtUsageLimit` (the limit) → `session-start` (compaction). The `T00` baseline separates its own failures from pre-existing ones; otherwise the model spends the night "fixing" red that was red before it arrived.

**Fixing in a loop.** The contract ("a second attempt without new evidence is forbidden") → `retry-guard` (counts identical failures, points at `/diagnose`) → `/diagnose` (versions off the machine, the levels, three hypotheses, docs for the pinned version, workarounds through scratch, the advisor on split evidence) → `ROOT CAUSE:`/`EVIDENCE:` in the Log as a trail for the next context.

## 12. What the harness does not do — honestly

- It does not mechanically forbid a third repeat of a command: `retry-guard` injects an instruction, not a refusal. A refusal would break legitimate repeats (waiting for a port, polling a state). If the model ignores the instruction three times, that is visible in the transcript and in the `## Log`; the fix is to tighten specific commands to `deny` if it ever becomes a real problem.
- It does not guarantee the quality of thought at 900k tokens of context: the attention grey zone in a long context is real. The harness keeps the context small not through a compaction threshold but by sending noise to subagents and trimming output in hooks. If `/usage` shows `long_context` above 10 %, revisit that decision rather than live with it.
- It does not replace `PROJECT.md` and the task tree: without a capability ledger and a `task.txt`, the model will guess the scope at night — and it will guess wider.
- It does not protect you from `--dangerously-skip-permissions` on a machine with production credentials. That is your decision and your perimeter.
- It does not check `verify:passed` twice: `/verify` is independent by context, not by model. A human's eyes remain in the `HUMAN` items.
