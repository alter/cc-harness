# The harness: how it is built

51 files, three floors. `BEHAVIOR.md` walks through the behaviour step by step; this file is about the construction. Every setting below was verified in the Claude Code 2.1.272 binary or in the official documentation — nothing from memory.

## 1. Three floors

```
~/.claude/                          THE "ME" FLOOR — how I work, the same in every project
├── CLAUDE.md                       behavioural contract (60 lines)
├── settings.json                   model, effort, cache, ceilings, hooks
├── statusline.sh                   status line: limits and cache
├── hooks/ (10)                     deterministic guards outside the model's context
├── skills/ (8)                     /intake /task /plan /run /run-task /test /verify /diagnose
├── agents/ (7)                     Explore scout test-runner researcher reviewer verifier worker
├── night.sh                        the overnight run, one long session
├── install.sh selftest.sh uninstall.sh   backup → install → checks → rollback (INSTALL.md)
└── advisor-stats.sh                 how often the Opus advisor fired, and on how much context

<project>/                          THE "PROJECT" FLOOR — facts about the repository
├── AGENTS.md  +  CLAUDE.md=@AGENTS.md    one contract for every agent
├── docs/PROJECT.md                 capability ledger, "decided by the agent", gate checks, night policy
├── .claude/rules/<area>.md         rules with paths: — loaded when matching files are touched
└── tasks/                          THE "WORK" FLOOR — the ledger of work
    ├── README PROTOCOL GOAL ROLES DECISIONS check.py
    └── NN-phase/NN-task/{task.txt, labels.txt, PLAN.md, NOTES.md, VERIFY.md, BLOCKED.md}
```

The separation: **behaviour** lives with the user and never enters a repository; **facts** live in the repository and are visible to every agent; **work** lives in the task tree, which the model, the hooks and the human all read. Claude Code already separates the first two floors through user and project settings — this just keeps apart what the platform put apart.

## 2. The path of one task

```
/intake  (once per repository)       →  docs/PROJECT.md
   ↓
/task <phase> <what it produces>     →  tasks/…/task.txt + labels.txt      (all questions happen here)
   ↓
/plan tasks/…/NN-slug                →  PLAN.md: T00 baseline, T01…Tn each with its verify command
   ↓  /clear                           (free; the plan is on disk, the SessionStart hook brings it back)
/run  or  cc-night tasks/…/NN-slug   →  one task at a time, [x] only after the check, a commit per task
   ↓                                    the Stop hook refuses to stop while a "- [ ] " remains
   ↓                                    retry-guard catches the second identical failure → /diagnose
   ↓                                    does the OUTCOME artefact exist? → status:done, else in_progress + NOTES
/verify tasks/…/NN-slug              →  another context: VERIFY.md, verify:passed|failed
```

Questions are asked at two points — `/intake` and `/task`/`/plan` — and nowhere else. Everything after that runs on the contract "a fork → pick what agrees with the plan → record it under Assumptions → continue".

## 3. File by file

### `CLAUDE.md` — the contract (loaded into every session, ~700 tokens)

Seven sections: questions only before the work starts; scope decided by the capability ledger; the task tree as the ledger of work; finish the plan; git and workspace; diagnosis instead of retries; code; cost hygiene. This is the only place where behaviour is set in prose. Everything that could be made deterministic was moved into a hook — prose can be forgotten after compaction, a hook cannot.

### `settings.json` — what and why

| Key | Value | Why |
|---|---|---|
| `model` | `sonnet[1m]` | Sonnet covers the bulk of development; Opus burns its own weekly window (`seven_day_opus`). The `[1m]` suffix asks for the 1M-context variant, which is what makes one session per plan possible; drop it to `sonnet` if 1M is not enabled for your account (`CLAUDE_CODE_DISABLE_1M_CONTEXT` also turns it off) |
| `advisorModel` | `opus` | Sonnet calls Opus itself at decision points: split evidence, an architectural fork. Cheaper than a whole day on Opus — but every call forwards the entire conversation to Opus and bills to the weekly Opus window, so a call late in a long session costs the whole session. `advisor-stats.sh` measures it; `CLAUDE_CODE_DISABLE_ADVISOR_TOOL=1` switches it off |
| `CLAUDE_CODE_ENABLE_EXPERIMENTAL_ADVISOR_TOOL` (env) | `1` | **`advisorModel` alone does not enable anything.** The binary gates the tool: first-party API, then either this variable or a server-side flag (`tengu_sage_compass2`) that is off for most accounts. Without it the tool is simply absent from the session and the model — correctly — reports it has no advisor. `claude --debug` prints `[AdvisorTool] Server-side tool enabled …` or `[AdvisorTool] Skipping advisor - …` |
| `effortLevel` | `medium` | a persistent default for routine work |
| `maxEffortLevel` | `high` | a ceiling: `xhigh`/`max` cannot be selected even by accident; `max` is officially "prone to overthinking" |
| `autoCompactWindow` | unset | compaction happens at the model's own limit (~1M for Sonnet 5 / Opus 5). The owner's decision: one session per plan, continuity of context is worth more than the price of a turn. If `/usage` shows `long_context` above 10 %, use `/autocompact 500k` in that one session, not in the settings |
| `autoContinueAtUsageLimit` | `true` | an overnight run that hits the limit waits for the reset and continues by itself. Switch it off for the day through `--settings` |
| `promptCacheTtl` / `subagentPromptCacheTtl` | `1h` | on a subscription the main conversation already gets an hour, but subagents, forks and compaction get **5 minutes**; raising them to an hour hits `cache_miss` directly |
| `workflowKeywordTriggerEnabled` | `false` | the word "ultracode" in a prompt no longer fans out a swarm of agents by itself |
| `workflowSizeGuideline` | `small` | if a workflow does start, up to 5 agents |
| `ultracode` | `false` | no xhigh plus permanent orchestration |

`env`:

| Variable | Value | Claude Code default | Why |
|---|---|---|---|
| `CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS` | 3 | **20** | the concurrency ceiling — the main protection for the rate-limit pool |
| `CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH` | 2 | 3 | a subagent may spawn one child, not a tree |
| `CLAUDE_CODE_MAX_WEB_SEARCHES_PER_SESSION` | 60 | 200 | researcher cannot wander off into endless search |
| `CLAUDE_CODE_SUBAGENT_MODEL` | sonnet | = main model | a subagent without an explicit model does not inherit Opus |
| `MAX_MCP_OUTPUT_TOKENS` | 8000 | — | an MCP server's answer cannot flood the window |
| `CC_*` | — | — | thresholds for the hooks below |
| `CLAUDE_CODE_STOP_HOOK_BLOCK_CAP` | 400 | **8** | one finished task is one more consecutive block; the default would override the Stop hook at task nine |

What is deliberately **not** set: `bashOutputMaxChars` — the default (30k characters, then a file plus a preview) already saves; raising it only drives logs into the conversation.

### `hooks/` — ten guards

Hooks run as processes outside the model's window: they cost no tokens, they are not forgotten after compaction, and they are not up for discussion.

| Hook | Event | What it does | Which failure it removes |
|---|---|---|---|
| `stop-guard.sh` | `Stop` | while a `PLAN.md` with `status: running` still has `- [ ]`, answers `{"decision":"block","reason":"next task…"}` — Claude Code sends the model back to work; releases the turn once the open-task count stops changing (3 blocks) | "did two tasks out of a hundred and stopped". Exits: `NEED_HUMAN`, `.claude/plan-pause`, 300 continuations, or a plan that is not advancing. Claude Code caps *consecutive* blocks at 8 by default, which would end a plan at task nine: `CLAUDE_CODE_STOP_HOOK_BLOCK_CAP=400` moves that ceiling above ours |
| `retry-guard.sh` | `PostToolUse(Bash)`, `PostToolUseFailure` | counts identical failed commands; on the second it injects a demand to run `/diagnose`, on the third it forbids the next call until `ROOT CAUSE:` + `EVIDENCE:` are written | the "tried, failed, try again" loop |
| `session-start.sh` | `SessionStart` (startup/resume/clear/compact/fork) | injects the active plan, the open tasks and the last Log entries | losing the thread after auto-compaction or a `/clear` at night |
| `compress-output.sh` | `PostToolUse(Bash)` | strips ANSI, collapses repeats into `(x30)`, saves long output to `.claude/scratch/`, gives the model head and tail through `updatedToolOutput` | 4000 lines of log living in the window on every later turn |
| `read-guard.sh` | `PreToolUse(Read)` | a file over 500 lines without `offset/limit` is refused: "Grep first, then Read a window" | reading a whole file for one function — the most common window leak |
| `bash-read-guard.py` | `PreToolUse(Bash)` | the same limit for the shell, parsed with `shlex`: `cat`/`less`/`nl` and an explicit `head -n 900` on a large file are refused; a pipe, a redirect, a substitution and a real window (`tail -5`, `head -n 20`) pass; each `;`/`&&` segment is judged on its own | the obvious way around `read-guard` — `cat` in Bash |
| `guard-subagent.sh` | `PreToolUse(Agent\|Task)` | a per-session ceiling on subagent spawns (40) | unattended fan-out |
| `subagent-evidence.sh` | `SubagentStop` | reads the subagent's transcript and counts real tool calls by name; "found it in src/x.py:12" with no Grep/Read, "12 passed" with no Bash and no `COMMAND:`, "NOT FOUND" with no search → `decision: block` and the agent goes back to work; one retry, then it steps aside | "I did it" with zero tool calls — a subagent's lie is caught by its transcript, not by its wording |
| `guard-model-switch.sh` | `PreModelSwitch` | asks for confirmation when the context is over 40k tokens | `/model` mid-session means rebuilding the whole prompt cache |
| `notify.sh` | `Notification`, and from stop-guard | desktop notification | you learn when the model is genuinely stuck or genuinely finished |

Why `PreToolUse` and not `SubagentStart` for the spawn ceiling: `SubagentStart` output only supports `additionalContext`, it cannot deny a spawn. Why stop-guard is a command and not a prompt hook: prompt and agent hooks exist only for tool events; a command costs zero tokens and zero latency.

### `skills/` — eight procedures

Only their descriptions live in context (under 1536 characters all together); the body loads on call.

| Skill | Called by | What it guarantees |
|---|---|---|
| `/intake` | you, once per repository | `docs/PROJECT.md`: the capability ledger (`included/available/absent/removed`; no row means `absent`, dormant code is not a requirement), the "decided by the agent" list, gate checks, what may run unattended |
| `/task` | you / the model | a task directory in the tree's format, vocabulary and language taken from `tasks/README.md`, questions asked once, `check.py` at zero problems |
| `/plan` | you / the model | `task.txt` → `PLAN.md`: VERIFY → acceptance criteria, `+` → tasks, `−` → boundaries, DEPENDS → a dependency check; `T00` is the baseline; every task carries its verify command; it ends with `/clear` + `/run` |
| `/run` | you / a hook | one task at a time, `[x]` only after the check, a commit per task, `done` only when the artefact exists in the repository, `BLOCKED.md` instead of a stub, `verify:` never touched |
| `/run-task` | `worker`, or you for a single task | what one task reads, does, verifies, marks and logs — then stops |
| `/test` | you, or `/plan` when a task needs cover | coverage chosen by risk, every test seen red before it passes, a mutation proving each guard can fail, `scripts/coverage_gate.py` in the gate checks so the floor can only rise, and a one-off `mutmut`/`stryker` audit (by hand, never a gate) whose surviving mutants become tasks |
| `/verify` | you / `/run` when it finishes | a fresh context (`verifier`): `VERIFY.md` stating what this context did *not* do, reproduction from a clean state, reverse control by mutation, "what was not checked" |
| `/diagnose` | the model after a failure / you | freeze → versions off the machine → the levels (environment, dependencies, logs, trace, state, measurements, debugger) → three hypotheses → documentation for the pinned version → third-party workarounds only in scratch → the advisor on split evidence → one fix plus a regression test |

### `agents/` — seven roles

| Agent | Model | Context | For what |
|---|---|---|---|
| `Explore` | haiku | without CLAUDE.md | overrides the built-in one: since 2.1.198 the built-in Explore inherits the session's model (Opus ceiling) |
| `scout` | haiku | without CLAUDE.md | "where the code lives" — paths and lines, changes nothing |
| `test-runner` | sonnet, low | without CLAUDE.md | runs tests, returns only the reasons for failures. Not Haiku: an invented "12 passed" does not self-correct, unlike an invented path |
| `researcher` | sonnet, medium | without CLAUDE.md | an unfamiliar subsystem, documentation for the pinned version, links instead of paraphrase |
| `reviewer` | opus, high | with CLAUDE.md | adversarial review of significant changes, `FILE:LINE → what breaks` |
| `verifier` | sonnet, high | with CLAUDE.md | independent acceptance through `VERIFY.md`, the only one that sets `verify:` |
| `worker` | sonnet, high | with CLAUDE.md | one plan task in a fresh context, two lines back; only in delegate mode |

Every agent ends with a line like `TOOLS USED: Grep:3 Read:2`; a hook compares it against the transcript. Haiku is kept only where a lie self-corrects on the next step: a path from scout is read immediately by the main session, so an invented path fails at the first Read.

There is deliberately no `builder` agent: implementation is done by the main session, which has a warm cache and the whole context. A subagent exists to isolate noise, not to write code.

### `statusline.sh`

`alpha  Sonnet 5/medium  ctx 43%  5h 62%/38m  7d 88%  cache cold:ttl_expired_5m 84k  hit 91%`

Reads the status-line JSON: `rate_limits.five_hour/seven_day`, `prompt_cache.warm/ttl/hit_ratio/last_miss_cause/recache_tokens_if_cold`, `context_window.used_percentage`. All of it first-hand, from Claude Code itself. `cache cold:<cause>` comes from the closed set `system_prompt_changed | tools_changed | model_changed | messages_rewritten | ttl_expired_5m | ttl_expired_1h`.

### `night.sh`

`cc-night tasks/10-x/03-y` → the plan goes `running`, the pause file is cleared, then `claude --dangerously-skip-permissions --effort high --settings '{"autoContinueAtUsageLimit":true}' "/run …"`. Sandbox without production credentials only — your choice, your responsibility.

### `project-template/`

Copied into a new repository: `AGENTS.md` (40 lines, for every agent) + `CLAUDE.md` = `@AGENTS.md`; `docs/PROJECT.md`; an example `.claude/rules/*.md` with `paths:`; `scripts/project_check.py`; and `tasks/` with README/PROTOCOL/GOAL/ROLES/DECISIONS plus a generic `check.py` (vocabulary from README/ROLES/GOAL, bilingual markers, `path:line` reference checking).

## 3a. How a plan is executed — one long session

The decision: `/run` works in one session for the whole plan, with no `/clear` and no manual `/compact` between tasks, and no restart per task. The model's context (up to 1M) is the memory of *why*: a decision made in T03 is known in T17 directly, not through a paraphrase in the Log. The second mode, `/run … delegate` (a coordinator plus one `worker` per task), is only switched on by the word "delegate".

| Mode | What holds state between tasks | What grows | Price |
|---|---|---|---|
| one session (default) | the session's context + `PLAN.md` | the history: up to the model's limit, then compaction | more cache resent with every task; an attention grey zone in a very long context |
| `delegate` | `PLAN.md`; the coordinator keeps one line per task | the coordinator's context, slowly (~100–300 tokens per task) | every worker is a cold start of 10–20k tokens of cache write with zero memory of earlier tasks |

The honest arithmetic. A hundred tasks in one session grow the context to hundreds of thousands of tokens, and every turn resends all of it as a cache read. A hundred cold starts cost 1–2M tokens of cache write, but not one task remembers the previous one. The first is more expensive in read tokens, the second in lost *why* and in repeated mistakes that memory would have prevented. This harness chooses memory and then makes it as cheap as possible:

- noise never enters the context: search goes to `scout`, tests and builds to `test-runner`, documentation to `researcher`; the main session keeps the summary and the `TOOLS USED` line;
- `compress-output` collapses repeats and cuts long output (the full text goes to `.claude/scratch/`), `read-guard` refuses whole-file reads;
- `promptCacheTtl: 1h` — a pause of up to an hour between turns does not drop the cache; switching model or effort mid-run is forbidden by the contract, because that does drop it;
- `autoCompactWindow` is unset, so compaction does not arrive before the model's limit; when it does, `session-start` (`source: compact`) brings back the plan, the counters and the tail of the Log;
- the plan itself is the single source of truth: `## Decisions`, `## Assumptions`, `## Log`, the task's `NOTES.md`, `docs/PROJECT.md`. Even after compaction the *why* is recovered from files, not from memory.

## 4. How this addresses the three complaints it was built against

**"Questions in the middle of a task."** The mechanism: `/intake` and `/task`/`/plan` collect everything through `AskUserQuestion` in batches of up to 4; the contract forbids asking once a plan is `running`; a fork becomes a choice plus a line under `## Assumptions`; the only exit is `NEED_HUMAN`, and only when every remaining task is blocked. Sections 4 ("decided by the agent") and 5 ("what may run unattended") of `docs/PROJECT.md` answer most future questions in advance.

**"It did two tasks and stopped."** Three layers: the contract; `stop-guard` (deterministic, the documented Stop-hook `decision: block`); and `/goal` — built in, typed by you before you leave, internally also a Stop hook but with retries on API failures (1/5/15 min) and waiting out a usage-limit reset. `autoContinueAtUsageLimit` plus `session-start` cover the limit and compaction. The `T00` baseline separates its own failures from pre-existing ones — otherwise the model spends the night "fixing" what was already red.

**"Tried, failed, try again."** `retry-guard` catches the second identical failed command — exactly the moment of "edited the file, the same command failed again"; `/diagnose` is a protocol with a mandatory `ROOT CAUSE:` + `EVIDENCE:` before any edit, versions read off the machine, documentation for the pinned version, and workarounds reproduced in scratch first; `/advisor` (Opus) when the evidence is split. The task tree adds reverse control: a check that was never red does not count.

**Fewer mistakes in general.** From the task tree: `done` means the artefact exists; an OUTCOME outside the repository is not closed by the executor; `verify:` is set by another context that records what it did not do; a `−` line in SCOPE is a boundary; `BLOCKED.md` instead of a stub; every number carries a source. Plus: a capability ledger (so nothing extra is built out of dormant code), a ban on `stash/reset/clean`, and architecture expressed as a check (`import-linter`) rather than a paragraph.

## 5. Where the tokens are saved

The cost model: **context is rent, paid on every turn.** Whatever entered the window is resent with every later request until `/clear`. So the levers are at the entrance to the window and at session boundaries, not on the model's output.

| Lever | Mechanism | What it buys |
|---|---|---|
| The cache stays warm | one model and one effort per session; `guard-model-switch`; `/output-style` instead of editing CLAUDE.md mid-session; `tools_changed` closed in 2.1.267 by deferred tool descriptions | a cache miss means the whole history uncached. The miss cause is visible in the status line |
| 1-hour TTL for subagents | `subagentPromptCacheTtl` | by default subagents, forks and compaction get 5 minutes, so every relaunch paid for the cache write again |
| Session boundaries | `/clear` between unrelated jobs (0 requests), `/compact` before leaving (while it is still warm), `/rewind` instead of arguing; the plan on disk survives all of it | `long_context` and `cache_miss` are two of the five cost behaviours `/usage` can show |
| Memory instead of a compaction threshold | `autoCompactWindow` unset; one session per plan | in tokens, a turn at 900k costs three times a turn at 300k even from cache — but losing the thread after compaction costs more, in rework. The context is kept small not by a threshold but by noise going to subagents and hooks trimming output |
| What gets into the window at all | `read-guard` (a window, not a whole file), `compress-output` (logs collapsed, long output to a file), `MAX_MCP_OUTPUT_TOKENS`, subagents with `omitClaudeMd` for noise | every line of output lives in the window until `/clear` |
| Cheap models where they suffice | `Explore`/`scout` on Haiku; `test-runner` and `researcher` on Sonnet; `SUBAGENT_MODEL=sonnet` | since 2.1.198 the built-in Explore would otherwise run on the session's model |
| Fan-out under control | `MAX_CONCURRENT_SUBAGENTS=3` (was 20), depth 2, `guard-subagent` at 40/session, workflows `small`, ultracode off, keyword trigger off | `subagent_heavy` and `high_parallel` are two more of the five |
| A reasoning ceiling | `maxEffortLevel: high`, `effortLevel: medium` | "Higher effort … uses your limits faster" — Claude Code's own wording |
| Not Opus by default | Sonnet plus an Opus advisor | the separate weekly Opus window is not burned on routine |
| Observability | the status line, `/usage` (five behaviours with a 10 % threshold, top subagents/skills/MCP, and the weekly Opus window the status line cannot show), `/cost`, `/skill-doctor`, `/insights`, `advisor-stats.sh` | measure first, then tune. Without this, tuning is guessing |

What this harness does **not** do, stated plainly: it does not compress the model's output tokens (caveman styles are a net loss for a profile where the spend is in cache and input); it does not count dollars (meaningless on a subscription); and it promises no percentages — your own `/usage` will show them after a week.

## 6. What you do by hand

- Once per repository: `/intake`, and copy `project-template/`.
- New work: `/task`, answer the questions; `/plan`, answer; `/clear`; then `/run` or `cc-night`.
- Before leaving for the night: `/goal all tasks in <PLAN.md> are [x] or [!]` — belt over braces.
- In the morning: `## Log`, `## Assumptions`, `BLOCKED.md`; `/verify` on what was closed; `python3 tasks/check.py`.
- Once a day: `/usage` — which of the five behaviours is above 10 %; once a week: `/skill-doctor`, `/insights`.
- When your own habits change: edit `~/.claude/CLAUDE.md`, not the project's `CLAUDE.md`.

## 7. Limits

- `retry-guard` only sees an identical command; "edited it and a different one failed" is caught by the contract alone.
- `stop-guard` checks the fact of `[x]`, not its quality: if the model marks `[x]` without the check passing, the hook will not notice — `/verify` and the morning `## Log` will.
- `read-guard` and `bash-read-guard` cover Read and the plain shell read; a file can still arrive through a language runtime (`python -c 'print(open(...).read())'`), and then `compress-output` is what trims it. There is no full impermeability and there will not be — hooks lower the frequency, they do not eliminate.
- The overnight `--dangerously-skip-permissions` is not a harness without a sandbox; it is a risk.
- Everything was measured on 2.1.272. Later releases change hooks and caching every week (2.1.257–2.1.271 carried more than twenty cache changes); after an upgrade, run `/skill-doctor` and check hook status in `/hooks`.
