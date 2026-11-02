---
status: done
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
- [x] AC1 `git-guard.py` and `bash-read-guard.py` deny a forbidden command whose payload has `tool_name: "Monitor"` — `./selftest.sh` (monitor-*)
- [x] AC2 The four PreToolUse guards carry `onFailure: "block"`, and no Stop, SubagentStop or SessionStart hook does — `./selftest.sh` (onfailure-*). A hook that exits 1 under `onFailure: "block"` blocks the call on 2.1.316 (live check recorded in `## Log`).
- [x] AC3 `guard-subagent.sh` drops an `effort` above the agent's own (frontmatter `effort:`, else `CLAUDE_CODE_SUBAGENT_EFFORT`). Forks are left alone. The model cap still works — `./selftest.sh` (subagent-effort-*, existing model checks)
- [x] AC4 `settings.json` sets `CLAUDE_CODE_SUBAGENT_EFFORT=medium` and `CLAUDE_CODE_WORKFLOW_SUBAGENT_MODEL=sonnet`. `modelSettings."claude-opus-5"` is gone — `jq` on settings.json
- [x] AC5 The harness skill is `verify-task`. No `skills/verify` remains in the source or in an install target, and every reference is renamed — `./selftest.sh` (skill-verify-task-*), `grep -rn '/verify\b'` finds only the built-in mention
- [x] AC6 The behaviour of the built-in `verify` on commit is observed live and recorded in HARNESS.md. If it writes `.claude/skills/verify/` into a repository, a deny rule stops that — log line plus `jq` on settings.json
- [x] AC7 `permissions.blockWritesOutsideWorkingDirectories` is either on, with evidence that no harness agent writes outside the working directories, or off, with the reason recorded under `## Assumptions` and in HARNESS.md
- [x] AC8 `idleCompaction` is either left on, with evidence that SessionStart `source=compact` (or an equivalent) brings the plan back after it, or set to `false` — log line plus `jq`
- [x] AC9 The docs name 2.1.316 as verified, and the stale claims from section 5 of the audit are corrected — grep per claim
- [x] AC10 No regression: every selftest check green at T00 is green at the end. A trial install passes `./selftest.sh <target>`. The live install passes `./selftest.sh ~/.claude` — `./selftest.sh`

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
- T07 needs a logged-in session and a trial CLAUDE_CONFIG_DIR is not logged in (keychain is per config dir), so T07 ran on the live config with the old `verify` still installed (phase A). Phase B — the same commit probe with `verify-task` installed, watching whether the now-visible built-in `verify` writes `.claude/skills/verify/` — runs right after the live install in T13; a deny rule is added then if it writes.
- T08 (D3): blockWritesOutsideWorkingDirectories stays off. Transcript scan of 10,707 Write/Edit calls found harness subagents writing outside their cwd on purpose: reverse-control mutations in /private/tmp/vv (41) and ~/.cache/vs-scratch (6), worktree agents writing VERIFY.md and .claude/scratch into the main checkout (64), session scratchpads (1,144), memory files (115). Turning it on would break verifier/worker runs; moving their scratch inside the repo is a separate change, not taken here.
- Untracked scratch artefacts, not part of the change (selftest logs, the T12 trial install, probe transcripts); flagged only by the installed integrity-check, which T15 fixes and T13 installs: .claude/scratch/bash-1793604371-stdout.log .claude/scratch/t00-selftest.log .claude/scratch/t01.log .claude/scratch/t01b.log .claude/scratch/t03.log .claude/scratch/t04.log .claude/scratch/t06.log .claude/scratch/t07/cfg/projects/<project dir>--claude-scratch-t07/ac83cbb8-48ab-4d59-b267-27ba46b68f59.jsonl .claude/scratch/t12/trial/bin/cc-night .claude/scratch/t12/trial/CLAUDE.md .claude/scratch/t12/trial/graph-setup.sh .claude/scratch/t12/trial/hooks/guard-subagent.sh .claude/scratch/t12/trial/hooks/integrity-check.py .claude/scratch/t12/trial/hooks/notify.sh .claude/scratch/t12/trial/hooks/retry-guard.sh .claude/scratch/t12/trial/hooks/session-start.sh .claude/scratch/t12/trial/hooks/stop-guard.sh .claude/scratch/t12/trial/project-template/docs/PROJECT.md .claude/scratch/t12/trial/skills/intake/SKILL.md .claude/scratch/t12/trial/skills/run-task/SKILL.md .claude/scratch/t12/trial/skills/run/SKILL.md .claude/scratch/t12/trial/skills/test-audit/SKILL.md .claude/scratch/t12b.log .claude/scratch/t14.log .claude/scratch/t14a.log .claude/scratch/t15.log

- T09/D4: "proven" taken as the 2.1.316 code path (idle -> SessionStart source=compact) plus a live source=compact re-injection; a live idle compaction needs a 100K+ session and was not run.

## Out of scope
- `autoCompactWindow` for long agents (audit item 12): no measurement says it is needed.
- Replacing the attribution block with `"attribution": false`.
- Any change to catnap.
- Push, PR.

## Tasks
- [x] T00 Baseline: run `./selftest.sh` once before any edit and record pass/fail counts and any already-red check in `## Log` — verify: `./selftest.sh`
- [x] T01 Monitor bypass: selftest cases `monitor-git-guard` (`git stash` with `tool_name=Monitor` → deny) and `monitor-bash-read-guard` (`cat` of a secret/600-line file with `tool_name=Monitor` → deny). Seen red first, then `git-guard.py:141` and `bash-read-guard.py:146` accept `{"Bash","Monitor"}` — verify: `./selftest.sh`
- [x] T02 Live probe in a trial `CLAUDE_CONFIG_DIR`: a PreToolUse hook with matcher `Bash` that logs its payload, plus a Monitor run of a harmless command. Record the real `tool_name`, and whether a `Bash(git stash:*)` deny rule also stops `git stash list` through Monitor. If it does not, add the matching `Monitor(...)` deny rules (or record why not) and document the result in HARNESS.md — verify: log line plus `jq '.permissions.deny' settings.json`
- [x] T03 `onFailure: "block"` on `guard-subagent.sh`, `read-guard.sh`, `bash-read-guard.py`, `git-guard.py`. Add selftest check `onfailure-guards`, which needs exactly those four and none on Stop/SubagentStop/SessionStart; seen red first. Live check in a trial config: a PreToolUse Bash hook that exits 1 with `onFailure: "block"` stops the Bash call; record it in `## Log` — verify: `./selftest.sh`
- [x] T03a fix: bash-read-guard crashed (RuntimeError from Path.expanduser) on `cat ~+/x`, now blocking under onFailure — use os.path.expanduser — verify: `./selftest.sh` (bash-read-guard-exit0)
- [x] T04 Effort cap in `guard-subagent.sh`. Cases `subagent-effort-over` (test-runner + effort max → updatedInput without effort), `subagent-effort-within`, `subagent-effort-env-cap` (undefined agent, `CLAUDE_CODE_SUBAGENT_EFFORT=medium`, effort high → dropped), `subagent-effort-fork` (untouched), and model+effort both dropped in one updatedInput. All seen red first — verify: `./selftest.sh`
- [x] T05 settings.json: add `CLAUDE_CODE_SUBAGENT_EFFORT=medium` and `CLAUDE_CODE_WORKFLOW_SUBAGENT_MODEL=sonnet`, remove `modelSettings`. Update the HARNESS.md env table rows — verify: `jq -e '.env.CLAUDE_CODE_SUBAGENT_EFFORT=="medium" and .env.CLAUDE_CODE_WORKFLOW_SUBAGENT_MODEL=="sonnet" and (has("modelSettings")|not)' settings.json`
- [x] T05a fix: install.sh kept the retired `modelSettings.claude-opus-5` in an existing target (`$old * $new` merge) — drop it when it still holds the harness value, drop an emptied modelSettings — verify: `./selftest.sh` (install-retire)
- [x] T05b fix: install.sh retires only an exact `{"maxEffortLevel":"high"}` for claude-opus-5, but the live entry is `{"effortLevel":"high","maxEffortLevel":"high"}` (harness cap merged with an effortLevel Claude Code wrote) — drop the harness key `maxEffortLevel:"high"` from that entry, then an emptied entry, then an emptied modelSettings — verify: `./selftest.sh` (install-retire)
- [x] T06 Rename skill `verify` → `verify-task`: directory, `name:`, `/verify` in both CLAUDE.md copies (the repo one is installed), BEHAVIOR.md, HARNESS.md, README.md, `agents/verifier.md`, `skills/run|task|test`, `project-template/tasks/*`, selftest. `install.sh` removes a stale `skills/verify` of the harness from the target (only when its SKILL.md is the harness one). Selftest check `skill-verify-task-installed` / `no-stale-verify` seen red first — verify: `./selftest.sh` and `grep -rn --exclude-dir=.git --exclude-dir=tmp -E '/verify\b|skills/verify\b' . | grep -v upgrade-2.1.316`
- [x] T07 Live observation of the built-in `verify` in a trial config with the renamed harness. Scratch git repo, a product source change, `claude -p "commit this change"`. Record whether `Skill` with `verify` was called and whether `.claude/skills/verify/` appeared. If it appeared, add Write/Edit deny rules for `**/.claude/skills/verify/**`. Record the result in HARNESS.md — verify: log line plus `jq '.permissions.deny' settings.json`
- [x] T08 `blockWritesOutsideWorkingDirectories`. Scan existing transcripts (`~/.claude/projects/*/**/*.jsonl`) for Write/Edit/NotebookEdit `file_path` outside the session cwd by verifier/attacker/test-auditor/worker/main sessions, and read the agents' scratch instructions. Enable per D3 or record why not. If enabled, live-check in a trial config with `--dangerously-skip-permissions` that a Write to `/tmp/x` is refused and a Write inside the repo works — verify: log line plus `jq '.permissions' settings.json`
- [x] T09 Idle compaction. In the 2.1.316 binary, find which hook/source an idle compaction raises (SessionStart `compact`? PreCompact/PostCompact `trigger`?) and whether `session-start.sh` covers it. If needed and cheap, run a live check with `CLAUDE_CODE_IDLE_COMPACT_MIN_TOKENS` lowered. Decide per D4 — verify: log line plus `jq '.idleCompaction' settings.json`
- [x] T10 Version floor. INSTALL.md:5 and :188, README.md:4, HARNESS.md:3/:244 change to "verified on 2.1.316". The required minimum rises to what the new keys need (`onFailure` 2.1.295, Agent `effort` 2.1.292, Monitor hooks 2.1.314, so 2.1.314). If `install.sh` enforces a minimum, raise it there with a selftest case seen red first — verify: `./selftest.sh` if install.sh changed, else `grep -n '2\.1\.3' README.md HARNESS.md INSTALL.md`
- [x] T11 Stale docs (audit section 5) — verify: `grep -n` per claim:
  - README.md:188 and HARNESS.md:110: prompt hooks on Stop exist;
  - HARNESS.md:80: WebSearch refill of 100/h since 2.1.290;
  - HARNESS.md:244: add `/doctor prompt-audit`;
  - HARNESS.md:133/:221: Explore 2.1.284;
  - README.md:46: model versions 5.5;
  - BEHAVIOR.md / night.sh docs: forks on by default in `-p` since 2.1.302, counted by the budget, not capped;
  - BEHAVIOR.md and HARNESS.md hook tables: Monitor, `onFailure`, the effort cap;
  - `docs/upgrade-2.1.316.md`: status "implemented by docs/plans/cc-2.1.316-upgrade.md".
- [x] T12 Final gate. Full `./selftest.sh` compared against the T00 baseline. Trial install into a separate directory, then `./selftest.sh <trial>` — verify: `./selftest.sh && ./selftest.sh <trial dir>`
- [x] T13 Live install per D5: `./install.sh` (backup into `~/.claude-backup`), then `./selftest.sh ~/.claude`. Confirm `~/.claude/skills/verify` of the harness is gone and `verify-task` is present — verify: `./selftest.sh ~/.claude`
- [x] T14 bash-read-guard false positive: a jq filter such as `.env.FOO=="x"` (an argument that is not a path to a file) is refused as a secret read. Selftest case red first, then require the argument to name an existing file or a path-like token — verify: `./selftest.sh`
- [x] T14a fix: reviewer — `.env.*`, `.env.{a,b}`, `.env.$VAR`, `.env.local~`, `.env.prod copy` and `jq -rf/-nf .env` were no longer refused — secret = `.env` or `.env.` + no `=`; any short-option cluster with `f` is jq --from-file — verify: `./selftest.sh` (deny-secrets-review)
- [x] T14b fix: reviewer round 2 — an existing secret file with `=` in its name (`.env.bak=1`) was readable — the `=` exemption applies only when no such file exists — verify: `./selftest.sh` (deny-secrets-review: … with = in its name)
- [x] T15 integrity-check scanned untracked `.claude/scratch/` and `.claude/worktrees/` (where the contract puts scratch), so every selftest log and trial install counted as an added suppression (94 findings at stop) — skip those prefixes for untracked files — verify: `./selftest.sh` (integrity-scratch-ignored)

## Log
- 2026-11-02 T00: ./selftest.sh exit 0, passed 408, failed 0 (baseline; log .claude/scratch/t00-selftest.log).
- 2026-11-02 T01: git-guard.py:141 and bash-read-guard.py:146 accept Bash|Monitor; 3 monitor-* checks red before, green after. Also fixed a pre-existing race: test_worktree_gc tearDown rmtree raced the detached GC process (worktree-gc.py:235) → bounded retry. selftest 412/0.
- 2026-11-02 T02: live probe (.claude/scratch/t02): Bash-matcher hook got {tool_name:"Bash",cmd:"git stash list"} for a Monitor call; installed git-guard refused it; with disableAllHooks the deny rule refused it ("Permission to use Bash with command git stash list has been denied."). No Monitor deny rules needed; HARNESS.md row added.
- 2026-11-02 T03: onFailure:block on the 4 PreToolUse guards; onfailure-guards red before, green after; selftest 414/0. Live on 2.1.316 (.claude/scratch/t03): a hook exiting 1 and a missing hook script both block Bash ("failed; blocking because onFailure is \"block\""). All four guards exit 0 on malformed/empty input.
- 2026-11-02 T04: guard-subagent caps Agent `effort` by the agent's frontmatter effort, else CLAUDE_CODE_SUBAGENT_EFFORT; model and effort dropped in one updatedInput; forks untouched. 4 subagent-effort-* red before, 7 green after; selftest 421/0.
- 2026-11-02 T05: env CLAUDE_CODE_SUBAGENT_EFFORT=medium, CLAUDE_CODE_WORKFLOW_SUBAGENT_MODEL=sonnet; modelSettings removed; BEHAVIOR/HARNESS env tables updated. Verify jq run from a filter file (.claude/scratch/t05v.jq): the inline form was refused by the installed bash-read-guard as a .env read — false positive, T14 added. jq exit 0.
- 2026-11-02 T06: skills/verify → skills/verify-task, all /verify references renamed (12 files), CLAUDE.md names the built-in verify as a different thing, install.sh drops an old harness skills/verify. skill-verify-task-installed/no-stale-verify red before (source and ~/.claude), green on source after; selftest 423/0. Remaining `skills/verify` hits are the intentional stale checks in selftest.sh/install.sh.
- 2026-11-02 T07 phase A (.claude/scratch/t07/a.jsonl): init lists one `verify` (the user skill shadows the built-in); `claude -p "…commit this change"` on a product-source change made 3 Bash calls (status/diff, branch+commit), no Skill call; no .claude/skills/verify/ created. No deny rule needed yet. HARNESS.md paragraph added. Phase B moved to T13.
- 2026-11-02 T08: scan (.claude/scratch/t08/scan.py) → outside-cwd writes by subagents: /tmp/vv 41, ~/.cache/vs-scratch 6, main checkout from a worktree 64, scratchpad 1114; D3 → leave off, reason under Assumptions and in HARNESS.md.
- 2026-11-02 T10: install.sh enforces no minimum (only prints `claude --version`), so docs only: INSTALL.md:5 floor 2.1.314 with reasons, :188 version notes, README.md:4 / HARNESS.md:3 / :248 re-checked on 2.1.316, /doctor prompt-audit added to the upgrade routine. grep shows 2.1.3xx in all four places.
- 2026-11-02 T11: README.md/HARNESS.md: Stop prompt hooks exist (2.1.274/2.1.294), onFailure rationale; WebSearch bucket+refill (binary: max ?? 200, refill 100/h interactive); Explore 2.1.284; models 5.5; hook tables: Monitor, effort cap; BEHAVIOR.md: forks on in -p since 2.1.302; audit marked implemented and item 2 marked refuted by T02. grep per claim: all 12 found.
- 2026-11-02 T14 (done before T12 so the fix is installed): bash-read-guard skips jq's filter argument and treats only `.env(.name)*` file-name tokens as secrets; 3 secrets-jq/not-a-path checks red before, green after, `jq . .env` still refused; selftest 427/0.
- 2026-11-02 T05a: trial install over a copy of live settings kept modelSettings.claude-opus-5; install-retire checks red (2) before, green after.
- 2026-11-02 review round 1 (reviewer, diff 567e59d..13f2bc0): 3 CONFIRMED → T14a (2 secret-guard holes from T14), T03a (old ~+ crash now blocking); 9 reproduction checks red before, green after; selftest 438/0. PLAUSIBLE, not acted on: P1 matcher stays "Bash" so the Monitor branch in the guards only matters if a release sends tool_name Monitor to a Bash matcher; P2 guard-subagent with jq missing or a non-numeric counter file would exit non-zero (now blocking); P3 git-guard read_text on an unreadable -F file.
- 2026-11-02 review round 2: findings 1–3 fixed (reviewer reran cases2.txt); 1 new CONFIRMED in the fixed line → T14b. Review loop closed (two rounds).
- 2026-11-02 T14b + T15: red before (2), green after; selftest 440/0; source integrity-check since 58a32fc: 0 findings. The installed (old) integrity-check keeps flagging scratch until T13 installs this.
- 2026-11-02 T09: idleCompaction kept on (key absent, default true; `jq .idleCompaction settings.json` = null). Binary 2.1.316: idle path lpr(trigger:"idle") -> x7n -> CGr/tWo -> WTe -> Dse(session,"compact") = SessionStart source=compact on the main thread; settings.json SessionStart has no matcher; session-start.sh case `compact)` re-injects the plan (seen live after this session's compaction). Live idle probe not possible cheaply: AZt()=max(1e5, CLAUDE_CODE_IDLE_COMPACT_MIN_TOKENS??2e5) floors the threshold at 100K; probe with 1000 stayed uncompacted after 30 min. Probe tmux session killed.
- 2026-11-02 T12: `./selftest.sh` 440/0 exit 0 (T00 baseline 408/0, no red); trial install (seeded with live settings.json + old skills/verify) exit 0: old verify gone, verify-task present, 4 PreToolUse onFailure=block; `./selftest.sh <trial>` 456/0 exit 0. Live modelSettings.claude-opus-5 also holds the user's own effortLevel, so install keeps it (retirement drops only the exact harness value).
- 2026-11-02 T13: `./install.sh` exit 0, backup ~/.claude-backup/20261102-115533; `./selftest.sh ~/.claude` 457/0 exit 0; ~/.claude/skills/verify gone, verify-task present. T07 phase B (.claude/scratch/t07/b.jsonl, repo t07/repoB2): init lists `verify-task` and built-in `verify`; `claude -p "…Commit this change."` made 2 Bash git calls, no Skill call, no .claude/skills/verify/ created → no deny rule; HARNESS.md paragraph extended.
- 2026-11-02 Finish: `./selftest.sh` 440/0 exit 0 vs T00 408/0 (no regression; monitor 4, onfailure 2, subagent-effort 7, skill-verify-task 1, install-retire 2 green); jq: SUBAGENT_EFFORT=medium, WORKFLOW_SUBAGENT_MODEL=sonnet, opus-5 override absent, blockWrites/idleCompaction unset (off/on by D3/D4); live ~/.claude 457/0. Plan done.
- 2026-11-02 T09 addendum: both finalize branches raise SessionStart compact — a `replacement` record reaches tWo with coreBoundary undefined (G=false → Dse "compact"); coreBoundary is set only for a `compacted` record, whose result already came through CGr → WTe → Dse "compact".
- 2026-11-02 T05b: correction to T12 — the live opus-5 entry is not the owner's: git history shows the harness shipped `{"maxEffortLevel":"high"}`, the `effortLevel:"high"` beside it is on all five models in every backup since 20261019 (written outside the harness). New install-retire case red before (440/1), green after (441/0). Trial install 457/0; live reinstall (backup ~/.claude-backup/20261102-121341) → opus-5 = {"effortLevel":"high"}, `./selftest.sh ~/.claude` 458/0. Plan done again.
