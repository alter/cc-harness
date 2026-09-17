# A personal Claude Code harness: ask once, finish the plan, diagnose instead of guessing

Not tied to any project. Everything lives in `~/.claude/`; a project only gets `docs/plans/`.
Every mechanism here was verified against the Claude Code 2.1.272 binary.

## Install

```bash
./selftest.sh                       # 120 checks on the checkout, installs nothing
./install.sh ~/.claude-harness-test # trial copy; CLAUDE_CONFIG_DIR=~/.claude-harness-test claude
./install.sh                        # into ~/.claude: backup → files → settings.json merge → checks
./selftest.sh ~/.claude             # the same checks against what is now installed
./uninstall.sh ~/.claude-backup/<stamp>   # rollback
```

`INSTALL.md` has the full procedure: backup, offline checks, a live run in a sandbox, and what can go wrong. Needs `jq`. Notifications go through `osascript` (macOS) or `notify-send`.

## Four requirements → four mechanisms

### 1. Every question before the work, none in the middle

`/plan <task>` is a skill with a fixed order:

1. Reconnaissance through the `scout` subagent; stack versions read off the machine.
2. **All** questions through `AskUserQuestion`, up to 4 per call, several calls back to back — but all of them now. Nothing that the repository can answer is ever asked.
3. Writes `docs/plans/<slug>.md`: goal, acceptance criteria with the commands that prove them, decisions from the interview, assumptions, boundaries, and hour-sized tasks each with its verify command.
4. One final question: "start now" / "I will edit the file first".

After that there are no questions, by the contract in `~/.claude/CLAUDE.md`: at a fork the model picks the option consistent with the plan's decisions, records it under `## Assumptions`, and moves on.

### 2. Do not stop until the plan is closed

Three layers, cheapest first:

- **The contract** (`CLAUDE.md` + the `/run` skill): never end a turn while a `- [ ]` remains; mark `[x]` only after the verify command passes; `[!] BLOCKED` is allowed in exactly three cases.
- **`hooks/stop-guard.sh`** (`Stop` event): while a plan with `status: running` still has `- [ ]`, it answers `{"decision":"block","reason":"…next task…"}` and Claude Code sends the model back to work. That is the documented Stop-hook contract. Exits: the literal `NEED_HUMAN` in the last message, the file `.claude/plan-pause`, the `CC_STOP_GUARD_CAP` ceiling (300 continuations per session), and — the one that matters in practice — **a plan that stops advancing**: if the open-task count is unchanged across `CC_STOP_GUARD_STALL` blocks (3), the turn is released and a notification says the plan is not moving. Every exit notifies.
  Claude Code has its own ceiling on *consecutive* blocks, `CLAUDE_CODE_STOP_HOOK_BLOCK_CAP`, and its default is **8** — since every finished task is one more block, a plan longer than eight tasks would be cut off with "a hook blocked the turn from ending 9 consecutive times". This harness sets it to 400, above its own 300, so the harness's own limits are the ones that fire.
- **`/goal`** (built-in; you type it yourself before leaving): `/goal all tasks in docs/plans/x.md are [x] or [!]`. Internally it is also a Stop hook, but with retries on API failures (1, 5, 15 minutes) and it waits out a usage-limit reset. Belt over braces.

`autoContinueAtUsageLimit: true` — on hitting the limit the session waits for the reset and continues by itself. If that gets in the way during the day, start with `--settings '{"autoContinueAtUsageLimit":false}'`.

Overnight run: `cc-night docs/plans/<slug>.md` sets the plan to `running`, clears the pause file and starts `claude --dangerously-skip-permissions --effort high "/run …"`. That flag belongs in a sandbox only — **never** on a machine holding production credentials.

Stopping an overnight run: `touch .claude/plan-pause`, or `status: paused` in the plan file.

**Execution model: one long session for the whole plan.** The model is set to `sonnet[1m]` for exactly this reason — the `[1m]` suffix asks for the 1M-context variant; without it the window is 200k and a long plan compacts early. Drop the suffix if 1M is not enabled for your account. A deliberate choice — the model's context (up to 1M) holds the *why* of earlier tasks, so the next task does not start from a cold start. The price is a larger context resent on every turn; that is paid down by the hooks (`compress-output`, `read-guard`), by the rule "noise goes to a subagent" (`scout`, `test-runner`, `researcher`), and by a 1-hour prompt cache. Compaction is not forced before the model's own limit (`autoCompactWindow` is unset); if it happens anyway, `session-start` puts the plan back into context.

Fallback: `/run <plan> delegate` — the main session only hands tasks to the `worker` subagent one at a time and reads a single line back. Every worker is a cold start (10–20k tokens of cache write) with no memory of earlier tasks; useful for long plans of independent tasks.

### 3. Tests: the only thing that notices a fix breaking something else

An agent edits all night; nobody is watching which of yesterday's behaviours it traded away for today's
fix. Prose cannot catch that. Three mechanisms do:

- **A test per behaviour change, seen red first.** The contract and `/plan` make it part of the task, not a
  follow-up: the task line names the test, and a test that was green the first time it ran has proved
  nothing yet. A fixed bug gets the test that would have caught it, in the same task.
- **`scripts/coverage_gate.py` — a floor that rises and never falls by itself.** It reads the project's
  coverage report (`coverage-py`, `json-summary`, `cobertura`, `lcov`, `go`), compares it with the floor in
  `.coverage-gate.json`, raises the floor when coverage grows, and exits non-zero when it drops by more
  than the tolerance. Put it in the gate checks and `/run` cannot mark a task `[x]` while coverage is
  falling. Lowering the floor is a decision recorded in `docs/PROJECT.md`, with a date and a reason.
- **`T00` and the finish, compared.** `T00` records which tests were already red and what coverage was,
  before any edit. At the plan's finish the full suite runs again: a test that was green at `T00` and is red
  now is a regression this run caused, and the plan does not close over it.

`/test` is the procedure for getting there: measure first, choose by risk (money and data, then branchy
code, then every past defect, then contracts, then nothing), write red first, then prove each guard can go
red by breaking the code in a scratch copy — the reverse control the task tree already demands. It never
asserts wording, layout or log text: those tests fail on honest changes and teach the agent to edit tests
instead of code.

The one thing coverage cannot see is a test that executes a line without noticing it is wrong —
`assert fee(100) is not None` covers the line and survives `0.1` becoming `0.2`. A model raising coverage
writes exactly those, because they are the cheapest tests the ratchet accepts. `/test` therefore carries a
**one-off mutation audit** (`mutmut`, `stryker`): run by hand on one module where a silently wrong value is
worse than a crash, it reports which broken versions of the code the suite failed to catch, and each
survivor becomes a task naming the mutation. It is deliberately not a gate check — a full run costs hours —
and the mutation score is never a target: the survivors are the output.

### 4. Diagnosis instead of "let me try again"

- **`hooks/retry-guard.sh`** (`PostToolUse` + `PostToolUseFailure`, matcher `Bash`): counts identical commands that exit non-zero, per session. On the second failure in a row it injects an instruction to switch to `/diagnose`; on the third it forbids the next tool call until `ROOT CAUSE:` and `EVIDENCE:` are written. A success resets the counter.
- **`/diagnose`** — the protocol: reproduce once and save the output to a file → pin versions off the machine → walk the levels (helicopter view, environment, dependencies, logs at a raised level, stack trace bottom-up, state, measurements, a debugger in scratch) → three hypotheses with a refuting experiment → official documentation **for the pinned version**, through `researcher` → unofficial workarounds only after reproducing them in scratch → one advisor call (`/advisor`, Opus) when the evidence is split → one fix, the original reproduction again, a regression test.
- **The advisor**: `advisorModel: "opus"` plus `CLAUDE_CODE_ENABLE_EXPERIMENTAL_ADVISOR_TOOL=1`. The key alone is **not** enough: the binary gates the tool behind the first-party API (a subscription counts), experimental betas, and a server-side flag delivered by GrowthBook — which does not run when telemetry is opted out, so `DISABLE_TELEMETRY` alone is enough to leave the advisor silently off. Without the variable the tool never appears and the model truthfully says it has none. `claude --debug` settles it in one line: `[AdvisorTool] Server-side tool enabled …` or `[AdvisorTool] Skipping advisor - …`. The advisor must also be at least as capable as the main model. It is a server-side tool the main model calls itself, and Claude Code's own prompt tells it to call before substantive work, when stuck, when changing approach, and before declaring the task done. Every call forwards **the whole conversation** to Opus and bills to the separate weekly Opus window, so in one long session the price of a call grows with the session. `advisor-stats.sh` counts the calls and the context they forwarded, from the transcripts; `/usage` shows the Opus window. `CLAUDE_CODE_DISABLE_ADVISOR_TOOL=1` turns it off for a run.

## The plan file

```
---
status: draft | running | paused | done
created: 2026-09-15
---
# Title
## Goal
## Acceptance criteria
- [ ] AC1 … — `command`
## Stack
## Decisions
## Assumptions
## Out of scope
## Tasks
- [ ] T01 … — verify: `command`
- [x] T02 …
- [!] T03 … BLOCKED: reason
## Log
```

The three task states are the only thing the hooks read. Tasks are never deleted, only split.

## What is where

| File | Event / call | Purpose |
|---|---|---|
| `CLAUDE.md` | every session | the working contract: questions, autonomy, debugging, code, cost hygiene |
| `BEHAVIOR.md` | reading | the whole behaviour step by step: startup, interview, plan, execution, guards, diagnosis, overnight |
| `INSTALL.md`, `install.sh`, `selftest.sh`, `uninstall.sh` | by hand | backup, install with a settings merge, 120 checks, rollback |
| `skills/intake` | `/intake` | one project-level interview → `docs/PROJECT.md`: capability ledger, "decided by the agent", gate checks, what may run unattended |
| `skills/task` | `/task` | a new task in the `tasks/<phase>/<NN>-<slug>/` tree: `task.txt` (TASK/GOAL/CONTEXT/SCOPE/OUTCOME/VERIFY/ROLE/DEPENDS) + `labels.txt`; `/task init` starts a new tree |
| `skills/plan` | `/plan` | interview → plan; for a task directory, a `PLAN.md` inside it built from `task.txt`; `T00` is the baseline |
| `skills/verify` + `agents/verifier.md` | `/verify` | independent verification by another context: `VERIFY.md` (verifier line / reproduce from a clean state / reverse control / what was not checked), then `verify:passed\|failed` |
| `skills/run` | `/run` | execution to the end without questions, in one session; `/run … delegate` hands tasks to `worker` one at a time |
| `skills/run-task` | `/run-task <plan> <T##>`, preloaded into `worker` | the procedure for one task: what to read, do, verify, mark and log |
| `skills/test` | `/test` | coverage by risk, red first, reverse control by mutation, and the ratchet wired into the gate checks |
| `skills/diagnose` | `/diagnose` | engineering diagnosis |
| `skills/graphify` + `graph-setup.sh` | `/graphify` | builds a local code graph, judges whether it is worth trusting, and only then wires it into `.mcp.json` as a tool for `scout` |
| `hooks/stop-guard.sh` | `Stop` | refuses to stop while tasks are open |
| `hooks/retry-guard.sh` | `PostToolUse(Bash)`, `PostToolUseFailure(Bash)` | catches the same failed command being repeated |
| `hooks/notify.sh` | `Notification`, and from stop-guard | desktop notification |
| `hooks/session-start.sh` | `SessionStart` (startup/resume/clear/compact/fork) | re-injects the active plan after compaction, `/clear`, `/resume` |
| `hooks/compress-output.sh` | `PostToolUse(Bash)` | strips ANSI, collapses repeats into `(xN)`, saves long output to `.claude/scratch/`, gives the model head and tail (`updatedToolOutput`) |
| `hooks/read-guard.sh` | `PreToolUse(Read)` | a file over 500 lines without offset/limit is refused: Grep first, then Read a window |
| `hooks/bash-read-guard.py` | `PreToolUse(Bash)` | the same rule for the shell: `cat`/`less`/`head -n 900` on a large file is refused, while a pipe, a redirect or a real window (`tail -5`) passes |
| `hooks/subagent-evidence.sh` | `SubagentStop` | checks a subagent's report against its transcript: zero tool calls behind "done" sends it back to work |
| `hooks/guard-model-switch.sh` | `PreModelSwitch` | asks before a model switch on a large context |
| `hooks/guard-subagent.sh` | `PreToolUse(Agent\|Task)` | a per-session ceiling on subagent spawns |
| `agents/*` | Agent tool | Explore and scout on Haiku, test-runner (Sonnet), researcher, reviewer, verifier, worker |
| `night.sh` | by hand | the overnight run; refuses a file that is not a plan, a `paused` one, or one with no `- [ ] T##` lines |
| `CLAUDE.md` → "Speaking outside the repository" + `docs/PROJECT.md` §8 | anything leaving the machine | the session drafts, you send; it volunteers nothing about the tooling and denies nothing either — a direct question goes to you |
| `project-template/` | copy into a new repository | `AGENTS.md` (one contract for every agent), `CLAUDE.md` = `@AGENTS.md`, `docs/PROJECT.md`, an example `.claude/rules/*.md` with `paths:`, `scripts/project_check.py`, `scripts/coverage_gate.py` |
| `project-template/tasks/` | `/task init` | the task-tree skeleton: `README.md` (the format), `PROTOCOL.md`, `GOAL.md`, `ROLES.md`, `DECISIONS.md`, and `check.py` — a validator that takes its vocabulary from the tree's own README/ROLES/GOAL and also checks `path:line` references |
| `statusline.sh` | status line | 5h / 7d limits, context, cache (the weekly Opus window is not in the status payload — `/usage` shows it) |
| `advisor-check.sh` | after installing | one `ping` request, then a verdict: `ENABLED — claude-opus-5`, or the exact reason it is off |
| `advisor-stats.sh` | by hand | how often the advisor fired and how much context each call forwarded, read from `~/.claude/projects/*.jsonl` |

## Tuning (environment variables under `settings.json` → `env`)

```
CC_STOP_GUARD_CAP=300     continuations per session, then a notification and a stop
CC_STOP_GUARD_STALL=3     blocks with an unchanged open-task count before the turn is released
CLAUDE_CODE_STOP_HOOK_BLOCK_CAP=400  Claude Code's own consecutive-block ceiling (its default 8 is too low for a plan)
CC_SUBAGENT_BUDGET=40     subagent spawns per session (more at night than by day)
CC_SWITCH_CTX_LIMIT=40000 context size above which /model asks for confirmation
CC_READ_GUARD_LINES=500   file size above which whole-file reads are refused, through Read and through the shell alike
CC_COMPRESS_MIN_LINES=40  output size above which Bash output is compressed
```

## Deliberately absent

- **No hook that "fixes" an error by itself.** A hook hands the model an instruction, never a solution — otherwise it is the same trial-and-error loop, only automated.
- **No built-in Task tools.** On Sonnet 5 / Opus 5 / Fable they are off by default (`CLAUDE_CODE_ENABLE_TODO_TOOLS=1` turns them on) and they live inside the session's context. A plan file on disk survives `/clear`, compaction and a restart — and hooks can read it.
- **No prompt hook on `Stop`.** Per the documentation inside the binary, prompt and agent hooks exist only for tool events; `/goal` reaches that path internally. So stop-guard is a deterministic command: zero tokens, zero latency.
- **Retry-guard only counts identical commands.** The loop "edited the file, ran the same command, failed again" is caught (same command). The loop "edited, a different command failed" is not; the contract in `CLAUDE.md` catches that one.

## Manual moves that no hook covers

- `/compact <what to keep>` — `/compact` takes an argument that steers the summary: `/compact keep plan path, open tasks, decisions, current ROOT CAUSE`.
- `claude -p "<task>"` — for a dozen identical independent chores (fix lint in N files) a batch of one-shot calls is cheaper than one long session, because context does not accumulate. On a subscription, `-p` gets the same 1-hour cache TTL as the main conversation.
- `/rename` before `/clear`, then `/resume` — to come back to the right session by name.

## The task tree

The format is one directory per task, two required files and a validator (`tasks/check.py`). The harness knows it:

- `/task <phase> <what it produces>` — reads `tasks/README.md` (vocabulary, language), asks once for only what the repository cannot answer, writes `task.txt` and `labels.txt`, runs `tasks/check.py`.
- `/plan tasks/<phase>/<NN>-<slug>` — turns `task.txt` into a `PLAN.md` inside the task directory: VERIFY → acceptance criteria, `+` lines → tasks, `−` lines → boundaries, DEPENDS → a check that every dependency is `status:done`.
- `/run` — executes `PLAN.md`; `status:done` only if the OUTCOME artefact exists in the repository, otherwise `in_progress` + `NOTES.md`. Blocking writes `BLOCKED.md` in the tree's format and sets `status:blocked`. It never touches `verify:`.
- `/verify <directory>` — another context (`verifier`) writes `VERIFY.md` and sets `verify:`.
- The `stop-guard` and `session-start` hooks see `tasks/**/PLAN.md` exactly as they see `docs/plans/*.md`.

The bundled `tasks/check.py` is generic: phases come from the `phase:` block in `tasks/README.md`, roles from the table in `ROLES.md`, milestones and gates from `GOAL.md`; `VERIFY.md` and `BLOCKED.md` markers are recognised in two languages. On a real tree it finds real discrepancies: a SCOPE with no `−` lines, a `phase:` outside the vocabulary, `status:blocked` without `BLOCKED.md`, `verify:passed` without `VERIFY.md`, a missing DEPENDS section, DEPENDS prose disagreeing with the label, and `path:line` references that drifted after edits.

## Optional: a code graph as a scout tool — `/graphify`

`scout` and `Explore` resolve a symbol with Grep, which searches text. On a large codebase a
symbol whose name is an ordinary English word costs a fortune in tokens and answers badly:
measured on a 600k-line repository, `grep -w Cluster` returned 2,827 lines (~73k tokens) and
`grep assemble` 114 lines (~3.5k tokens) of mostly prose.

A code graph answers the same two questions — *which definition is this* and *who calls it* —
from an AST index. [graphify](https://github.com/Graphify-Labs/graphify) builds one locally with
tree-sitter in seconds and spends no model tokens, and serves it over MCP. On the same repository
the two answers above cost 82 and 39 tokens, with exact `path:line` for every caller and callee.

```bash
pip install graphifyy      # once
/graphify                  # in the project, once
```

`/graphify` runs `graph-setup.sh`, which builds the graph with `graphify extract . --code-only`
and then **judges it before wiring anything**:

| Refusal | Why |
|---|---|
| the repository has submodules | an umbrella repository resolves nearly every cross-repository edge wrongly — measured: 559 of 566 cross-repository edges were false `INFERRED` guesses |
| extraction produced nothing | the parser does not read these languages |
| fewer than 20 nodes | nothing here that a grep cannot answer |
| over 25% `INFERRED` edges | the graph is mostly guessing |
| under 30% of code files reached the graph | the grammar does not really cover this language |

Only on a pass does it add a `graphify` server to `.mcp.json` (merging, never replacing),
add `graphify-out/` to `.gitignore`, and install a git post-commit hook that rebuilds the graph
after every commit — which matters, because `/run-task` commits after each task. Thresholds:
`CC_GRAPH_MIN_NODES`, `CC_GRAPH_MAX_INFERRED`, `CC_GRAPH_MIN_COVERAGE`.

MCP servers start at session start, so the tools do not exist in the session that ran `/graphify`.
Restart `claude`, then check one symbol you already know against `grep -n` before trusting the
rest. `scout` already carries the four graph tools in its `tools:` list; where no graph exists,
those names resolve to nothing and it falls back to Grep. `subagent-evidence` accepts a
`mcp__…graph…__*` call as search evidence, so a scout that answered from the graph is not sent
back for a Grep it did not need.

Do **not** run `graphify install`: it appends to your `CLAUDE.md` and registers its own
`PreToolUse` hooks that inject "MANDATORY: run graphify query" into every Read, Glob, Grep and
Bash call — a per-call tax on a long session, and an instruction `scout` cannot follow, because
`scout` has no Bash. As a tool the model calls it when it helps and ignores it when it does not.

What the graph is not: it answers symbol questions, not "how does this flow work" — keyword
seeding picks the wrong entry points for those. `INFERRED` edges are guesses, and they are the
ones that look most interesting; cross-file guesses like SQLAlchemy's `select()` pointing at an
unrelated local `select()` are normal. Prefer `EXTRACTED`, and treat the rest as a lead. The
post-commit rebuild is detached, so for a few seconds after a commit the graph still describes
the previous one.

## A new repository

```bash
cp -r ~/.claude/project-template/{AGENTS.md,CLAUDE.md,docs,scripts,.claude} .
claude   # -> /intake
```

`/intake` fills in `docs/PROJECT.md`. From then on every `/plan` reads it and stops re-asking about the environment, the checks and the boundaries. The ledger rule: a capability with no row is `absent`; dormant code is not a requirement. A direct request is full authorization — it is recorded in the ledger and never asked about again.

## A repository you are already working in

Nothing has to be migrated. Installing the harness changes how a session behaves; it does not change the
repository until you ask it to.

1. **`/intake`, once.** It reads the repository first and asks only what it could not find out. The result is
   `docs/PROJECT.md`: the capability ledger, what the agent decides on its own, the commands that gate every
   task, and what may run unattended. Every later `/plan` reads it instead of asking you again.
2. **An existing `CLAUDE.md` stays where it is.** The harness never edits a project's own contract. Where the
   two disagree, the more specific file wins — that is, the project's — so a line like "ask before every step"
   will quietly cancel the harness's autonomy. Either fix that line or move the file's content into
   `AGENTS.md` and leave `CLAUDE.md` as `@AGENTS.md`, the way `project-template/` does.
3. **Your existing plans, issues and TODOs are not converted.** Start the next piece of work through `/task`
   and `/plan`; the old ones stay as they are. There is no importer and there should not be one.
4. **Optionally `/graphify`**, if the repository is one component and not an umbrella of submodules.

### What the working day looks like afterwards

The familiar loop — *describe what you want, have a strong model cut it into tasks, let agents run it to the
end while you stay out of it* — is unchanged in shape. What changed is where you spend attention:

| | before | with the harness |
|---|---|---|
| you describe the work | in the chat, once | `/task` — the questions all arrive together, at the start |
| tasks appear | the model invents them mid-run | `/plan` writes them to disk with a verify command each, and `T00` measures the baseline first |
| you review | by reading the run | by reading one file, `PLAN.md`, before anything runs |
| execution | agents, until they decide they are finished | one session to the end; the Stop hook refuses to finish while a `- [ ]` remains |
| a failure | "let me try again" | the second identical failure is caught and turned into `/diagnose` |
| the end | a summary you have to trust | the artefact exists in the repository, or the task is `blocked` with `BLOCKED.md` |

The two places you are still needed are `/intake` and `/task`/`/plan`. After `/run` starts, being asked a
question is a defect, not a feature — send the transcript.

## The first run

0. Once per repository: `/intake`.
1. In the project: `claude` → `/plan <tonight's task>`. Answer the questions. Pick "I will edit the file first" (or "clean window" → `/clear`, `/run`).
2. Read `docs/plans/<slug>.md`. Add, remove, reorder.
3. `cc-night docs/plans/<slug>.md`, then in the session type `/goal all tasks in docs/plans/<slug>.md are [x] or [!]`.
4. In the morning: `## Log`, `## Assumptions`, the `[!]` tasks. Then `/usage` — look at `cron` and `subagent_heavy`.

## License

MIT — see `LICENSE`. Take it, change it to fit, no need to ask. `CLAUDE.md` is one engineer's contract: the rules about Python 3, `# filename.ext` and splitting files over 1400 lines are the first things to rewrite for your own habits.
