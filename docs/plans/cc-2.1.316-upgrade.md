---
status: running
created: 2026-11-02
---
# Harness upgrade to Claude Code 2.1.316

## Goal
The harness matches Claude Code 2.1.316, as found by the audit `docs/upgrade-2.1.316.md`:
- No guard can be bypassed through the Monitor tool.
- The security guards fail closed.
- `guard-subagent` caps the effort a call asks for, not only the model.
- Workflow agents run on the same model as subagents.
- The harness skill no longer collides with the built-in `verify`.
- Stale settings are gone, and documentation names the version it was checked on.
- The result is installed into `~/.claude` and passes `./selftest.sh ~/.claude`.

## Acceptance criteria
- [ ] AC1 `git-guard.py` and `bash-read-guard.py` deny a forbidden command whose payload has `tool_name: "Monitor"` — `./selftest.sh` (monitor-*)
- [ ] AC2 The four PreToolUse guards carry `onFailure: "block"`, and no Stop, SubagentStop or SessionStart hook does — `./selftest.sh` (onfailure-*). A hook that exits 1 under `onFailure: "block"` blocks the call on 2.1.316 (live check recorded in `## Log`).
- [ ] AC3 `guard-subagent.sh` drops an `effort` above the agent's own (frontmatter `effort:`, else `CLAUDE_CODE_SUBAGENT_EFFORT`). Forks are left alone. The model cap still works — `./selftest.sh` (subagent-effort-*, existing model checks)
- [ ] AC4 `settings.json` sets `CLAUDE_CODE_SUBAGENT_EFFORT=medium` and `CLAUDE_CODE_WORKFLOW_SUBAGENT_MODEL=sonnet`. `modelSettings."claude-opus-5"` is gone — `jq` on settings.json
- [ ] AC5 The harness skill is `verify-task`. No `skills/verify` remains in the source or in an install target, and every reference is renamed — `./selftest.sh` (skill-verify-task-*), `grep -rn '/verify\b'` finds only the built-in mention
- [ ] AC6 The behaviour of the built-in `verify` on commit is observed live and recorded in HARNESS.md. If it writes `.claude/skills/verify/` into a repository, a deny rule stops that — log line plus `jq` on settings.json
- [ ] AC7 `permissions.blockWritesOutsideWorkingDirectories` is either on, with evidence that no harness agent writes outside the working directories, or off, with the reason recorded under `## Assumptions` and in HARNESS.md
- [ ] AC8 `idleCompaction` is either left on, with evidence that SessionStart `source=compact` (or an equivalent) brings the plan back after it, or set to `false` — log line plus `jq`
- [ ] AC9 The docs name 2.1.316 as verified, and the stale claims from section 5 of the audit are corrected — grep per claim
- [ ] AC10 No regression: every selftest check green at T00 is green at the end. A trial install passes `./selftest.sh <target>`. The live install passes `./selftest.sh ~/.claude` — `./selftest.sh`

## Stack
- bash 5.3, python 3 (stdlib), jq 1.6, git.
- Claude Code 2.1.316 (`~/.local/share/claude/versions/2.1.316`); the 2.1.312 binary is also on disk.
- Gate check: `./selftest.sh` (124+ checks, includes `selftest/test_*.py` and `agenttest.sh --self-check`).
- Evidence base: `docs/upgrade-2.1.316.md`.

## Decisions
- D1 Harness `verify` skill -> rename to `verify-task` unconditionally; the name `verify` goes to the built-in.
- D2 `CLAUDE_CODE_SUBAGENT_EFFORT` -> `medium`.
- D3 `blockWritesOutsideWorkingDirectories` -> check where verifier/attacker/test-auditor/worker write; enable only if nothing writes outside the working directories, otherwise leave off and record why.
- D4 `idleCompaction` -> keep on only if the plan is proven to come back after an idle compaction; otherwise `false`.
- D5 Install into the live `~/.claude` at the end (install.sh backs up to `~/.claude-backup`).
- D6 Branch: `main`, one commit per task, no push.
- D7 Priority if time runs out: security first (Monitor, onFailure, verify, effort/workflow cap), then settings, then documentation.

## Assumptions
- The Monitor fix accepts `tool_name` in `{"Bash","Monitor"}`. It is correct whatever the real payload carries; T02 records the real value.
- `onFailure: "block"` goes only on PreToolUse guards. On Stop, SubagentStop or SessionStart a crashing hook would block the session from stopping or starting.
- The effort cap mirrors the model cap. The ceiling is the agent's frontmatter `effort:`. With no definition or no `effort:`, the ceiling is `CLAUDE_CODE_SUBAGENT_EFFORT`. With neither, there is no cap. Rank: low < medium < high < xhigh < max.
- `modelSettings."claude-opus-5"` is removed rather than renamed: the top-level `maxEffortLevel: "high"` already caps every model.
- `includeCoAuthoredBy: false` stays. It is harmless, and HARNESS.md explains the attribution block as a whole.
- The built-in `verify` is not denied. If T08 shows it writing a project skill, a Write/Edit deny rule on `**/.claude/skills/verify/**` stops the write. The skill itself may still run.

- T02 finding: on 2.1.316 Monitor's shell commands reach Bash hooks as tool_name "Bash" and Bash deny rules apply to them, so audit item 2 was not a live bypass; the T01 change stays as a guard against relabelling, no Monitor(...) deny rules added.

## Out of scope
- `autoCompactWindow` for long agents (audit item 12): no measurement says it is needed.
- Replacing the attribution block with `"attribution": false`.
- Any change to catnap.
- Push, PR.

## Tasks
- [x] T00 Baseline: run `./selftest.sh` once before any edit and record pass/fail counts and any already-red check in `## Log` — verify: `./selftest.sh`
- [x] T01 Monitor bypass: selftest cases `monitor-git-guard` (`git stash` with `tool_name=Monitor` → deny) and `monitor-bash-read-guard` (`cat` of a secret/600-line file with `tool_name=Monitor` → deny). Seen red first, then `git-guard.py:141` and `bash-read-guard.py:146` accept `{"Bash","Monitor"}` — verify: `./selftest.sh`
- [x] T02 Live probe in a trial `CLAUDE_CONFIG_DIR`: a PreToolUse hook with matcher `Bash` that logs its payload, plus a Monitor run of a harmless command. Record the real `tool_name`, and whether a `Bash(git stash:*)` deny rule also stops `git stash list` through Monitor. If it does not, add the matching `Monitor(...)` deny rules (or record why not) and document the result in HARNESS.md — verify: log line plus `jq '.permissions.deny' settings.json`
- [ ] T03 `onFailure: "block"` on `guard-subagent.sh`, `read-guard.sh`, `bash-read-guard.py`, `git-guard.py`. Add selftest check `onfailure-guards`, which needs exactly those four and none on Stop/SubagentStop/SessionStart; seen red first. Live check in a trial config: a PreToolUse Bash hook that exits 1 with `onFailure: "block"` stops the Bash call; record it in `## Log` — verify: `./selftest.sh`
- [ ] T04 Effort cap in `guard-subagent.sh`. Cases `subagent-effort-over` (test-runner + effort max → updatedInput without effort), `subagent-effort-within`, `subagent-effort-env-cap` (undefined agent, `CLAUDE_CODE_SUBAGENT_EFFORT=medium`, effort high → dropped), `subagent-effort-fork` (untouched), and model+effort both dropped in one updatedInput. All seen red first — verify: `./selftest.sh`
- [ ] T05 settings.json: add `CLAUDE_CODE_SUBAGENT_EFFORT=medium` and `CLAUDE_CODE_WORKFLOW_SUBAGENT_MODEL=sonnet`, remove `modelSettings`. Update the HARNESS.md env table rows — verify: `jq -e '.env.CLAUDE_CODE_SUBAGENT_EFFORT=="medium" and .env.CLAUDE_CODE_WORKFLOW_SUBAGENT_MODEL=="sonnet" and (has("modelSettings")|not)' settings.json`
- [ ] T06 Rename skill `verify` → `verify-task`: directory, `name:`, `/verify` in both CLAUDE.md copies (the repo one is installed), BEHAVIOR.md, HARNESS.md, README.md, `agents/verifier.md`, `skills/run|task|test`, `project-template/tasks/*`, selftest. `install.sh` removes a stale `skills/verify` of the harness from the target (only when its SKILL.md is the harness one). Selftest check `skill-verify-task-installed` / `no-stale-verify` seen red first — verify: `./selftest.sh` and `grep -rn --exclude-dir=.git --exclude-dir=tmp -E '/verify\b|skills/verify\b' . | grep -v upgrade-2.1.316`
- [ ] T07 Live observation of the built-in `verify` in a trial config with the renamed harness. Scratch git repo, a product source change, `claude -p "commit this change"`. Record whether `Skill` with `verify` was called and whether `.claude/skills/verify/` appeared. If it appeared, add Write/Edit deny rules for `**/.claude/skills/verify/**`. Record the result in HARNESS.md — verify: log line plus `jq '.permissions.deny' settings.json`
- [ ] T08 `blockWritesOutsideWorkingDirectories`. Scan existing transcripts (`~/.claude/projects/*/**/*.jsonl`) for Write/Edit/NotebookEdit `file_path` outside the session cwd by verifier/attacker/test-auditor/worker/main sessions, and read the agents' scratch instructions. Enable per D3 or record why not. If enabled, live-check in a trial config with `--dangerously-skip-permissions` that a Write to `/tmp/x` is refused and a Write inside the repo works — verify: log line plus `jq '.permissions' settings.json`
- [ ] T09 Idle compaction. In the 2.1.316 binary, find which hook/source an idle compaction raises (SessionStart `compact`? PreCompact/PostCompact `trigger`?) and whether `session-start.sh` covers it. If needed and cheap, run a live check with `CLAUDE_CODE_IDLE_COMPACT_MIN_TOKENS` lowered. Decide per D4 — verify: log line plus `jq '.idleCompaction' settings.json`
- [ ] T10 Version floor. INSTALL.md:5 and :188, README.md:4, HARNESS.md:3/:244 change to "verified on 2.1.316". The required minimum rises to what the new keys need (`onFailure` 2.1.295, Agent `effort` 2.1.292, Monitor hooks 2.1.314, so 2.1.314). If `install.sh` enforces a minimum, raise it there with a selftest case seen red first — verify: `./selftest.sh` if install.sh changed, else `grep -n '2\.1\.3' README.md HARNESS.md INSTALL.md`
- [ ] T11 Stale docs (audit section 5) — verify: `grep -n` per claim:
  - README.md:188 and HARNESS.md:110: prompt hooks on Stop exist;
  - HARNESS.md:80: WebSearch refill of 100/h since 2.1.290;
  - HARNESS.md:244: add `/doctor prompt-audit`;
  - HARNESS.md:133/:221: Explore 2.1.284;
  - README.md:46: model versions 5.5;
  - BEHAVIOR.md / night.sh docs: forks on by default in `-p` since 2.1.302, counted by the budget, not capped;
  - BEHAVIOR.md and HARNESS.md hook tables: Monitor, `onFailure`, the effort cap;
  - `docs/upgrade-2.1.316.md`: status "implemented by docs/plans/cc-2.1.316-upgrade.md".
- [ ] T12 Final gate. Full `./selftest.sh` compared against the T00 baseline. Trial install into a separate directory, then `./selftest.sh <trial>` — verify: `./selftest.sh && ./selftest.sh <trial dir>`
- [ ] T13 Live install per D5: `./install.sh` (backup into `~/.claude-backup`), then `./selftest.sh ~/.claude`. Confirm `~/.claude/skills/verify` of the harness is gone and `verify-task` is present — verify: `./selftest.sh ~/.claude`

## Log
- 2026-11-02 T00: ./selftest.sh exit 0, passed 408, failed 0 (baseline; log .claude/scratch/t00-selftest.log).
- 2026-11-02 T01: git-guard.py:141 and bash-read-guard.py:146 accept Bash|Monitor; 3 monitor-* checks red before, green after. Also fixed a pre-existing race: test_worktree_gc tearDown rmtree raced the detached GC process (worktree-gc.py:235) → bounded retry. selftest 412/0.
- 2026-11-02 T02: live probe (.claude/scratch/t02): Bash-matcher hook got {tool_name:"Bash",cmd:"git stash list"} for a Monitor call; installed git-guard refused it; with disableAllHooks the deny rule refused it ("Permission to use Bash with command git stash list has been denied."). No Monitor deny rules needed; HARNESS.md row added.
