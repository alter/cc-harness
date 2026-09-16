# Install, check, roll back

The order: back up → run the checks without installing → install a trial copy into a separate directory → run it live in a sandbox → install into `~/.claude` → roll back if anything is wrong. Every step is one command, and every step is reversible.

You need `jq`, `bash` ≥ 4, and `claude` ≥ 2.1.267 (for `maxEffortLevel`). On macOS nothing else (notifications go through `osascript`); on Linux, `notify-send` if you want them.

## 0. What Claude Code keeps where — so you know what is being touched

| Path | What it is | Does the harness touch it |
|---|---|---|
| `~/.claude/settings.json` | settings, hooks, statusLine | **yes** — merged, not replaced |
| `~/.claude/CLAUDE.md` | the global contract | **yes** — replaced |
| `~/.claude/hooks/`, `agents/`, `skills/`, `statusline.sh`, `project-template/` | the harness's own files | **yes** — added; other files in those directories are not deleted |
| `~/.claude/settings.local.json`, `commands/`, `keybindings.json` | yours | no, but copied into the backup |
| `~/.claude.json` | MCP servers, login state, onboarding | **no**; copied into the backup |
| `~/.claude/projects/` | session transcripts | no; not in the backup (gigabytes) — see §1 |
| `~/bin/cc-night` | the overnight launcher | **yes** |

## 1. Backup

`install.sh` makes one itself before writing anything, into `~/.claude-backup/<stamp>/`: every file from the table above plus a `MANIFEST.txt` listing what was there. If you want a full copy including transcripts, do it before installing:

```bash
tar czf ~/claude-full-$(date +%Y%m%d).tgz -C ~ .claude .claude.json
du -sh ~/claude-full-*.tgz
```

Check that the archive is readable: `tar tzf ~/claude-full-*.tgz | head`.

## 2. Checks without installing — 50 hook checks on synthetic input

```bash
git clone https://github.com/alter/cc-harness && cd cc-harness
./selftest.sh
```

What gets checked (nothing is written outside a temporary directory; counter state is isolated through `XDG_STATE_HOME`):

- the syntax of every script, and that `settings.json` is valid JSON;
- `read-guard`: refuses a 600-line file, allows it with `offset/limit`, allows `.md` regardless of size;
- `compress-output`: 300 identical lines become `(x300)`, long output becomes head/tail plus a file in `.claude/scratch/`, short output is untouched;
- `retry-guard`: the first failure is silent, the second (with different whitespace — the same command) points at `/diagnose`, the third demands `ROOT CAUSE` before the next call, a success resets the counter;
- `stop-guard`: a plan with 2 open tasks produces `decision: block` naming the next task; `NEED_HUMAN`, `.claude/plan-pause`, the ceiling, and zero open tasks each release it;
- `session-start` after compaction produces a line with "2 open, 1 blocked" and the tail of the Log;
- `subagent-evidence`: a scout with no tool calls is blocked; with Grep+Read and a path it passes; without a path it is blocked; `NOT FOUND` with no calls is blocked; a test-runner with no Bash or no `COMMAND:` is blocked; a worker with no Edit/Write/Bash is blocked; `NOT DONE` and `stop_hook_active` pass;
- `guard-subagent` 1/2 and 2/2 allow, 3/2 denies; `guard-model-switch` asks at 50k, allows at 1k;
- `subagent-evidence` also accepts a code-graph call (`mcp__…graph…__*`) as search evidence for scout;
- `statusline` against a sample JSON renders the directory, model, context, 5h, 7d, the cold-cache cause and the hit ratio.

`./selftest.sh` with no argument tests the checkout, so the hook paths inside its `settings.json`
(`~/.claude/hooks/...`) point somewhere else and are reported as `SKIP` — that is the source tree
being checked, not a problem. After installing, run `./selftest.sh ~/.claude`: the same checks run
against the installed copy and every `SKIP` becomes a `PASS` ("hook exists+x"), so the total grows.

The last line must read `passed N, failed 0`. If it does not, do not install — send the output.

## 3. A trial install into a separate directory, leaving `~/.claude` alone

Claude Code honours `CLAUDE_CONFIG_DIR` (verified in the binary): the whole configuration is read from there instead of `~/.claude`.

```bash
./install.sh ~/.claude-harness-test
./selftest.sh ~/.claude-harness-test        # the same checks, plus "hooks present and executable"
CLAUDE_CONFIG_DIR=~/.claude-harness-test claude
```

With a non-default directory, `install.sh` rewrites every `~/.claude/...` reference inside the hooks, agents, skills and `settings.json` to point at that directory. The first launch will ask about the theme and login (on macOS the login key lives in the Keychain and is usually shared, so a second login is not needed; on Linux, copy `~/.claude/.credentials.json` into the test directory). MCP servers from `~/.claude.json` will not appear in the trial configuration — that is expected.

Remove the trial directory afterwards with `rm -rf ~/.claude-harness-test`.

## 4. A live run in a sandbox (20 minutes, well under one hour of the limit)

Use a separate empty repository, not a working project:

```bash
mkdir -p /tmp/harness-sandbox && cd /tmp/harness-sandbox && git init -q
seq 1 800 | sed 's/^/line = /' > big.py
mkdir -p docs/plans && cat > docs/plans/smoke.md <<'EOF'
---
status: running
created: 2026-09-15
---
# Smoke
## Goal
Three files exist and the suite is green.
## Acceptance criteria
- [ ] AC1 `test -f a.txt && test -f b.txt && test -f c.txt`
## Decisions
- files contain their own name
## Assumptions
## Out of scope
- anything else
## Tasks
- [ ] T00 baseline: run `python3 -c "import big"` and record the result — verify: `true`
- [ ] T01 create a.txt with content "a" — verify: `grep -qx a a.txt`
- [ ] T02 create b.txt with content "b" — verify: `grep -qx b b.txt`
- [ ] T03 create c.txt with content "c" — verify: `grep -qx c c.txt`
- [ ] T04 run `false` and handle the failure by the /diagnose rules — verify: `true`
## Log
EOF
git add -A && git commit -qm init
CLAUDE_CONFIG_DIR=~/.claude-harness-test claude "/run docs/plans/smoke.md"
```

What you should see — and what it means if you do not:

| Observation | Mechanism | If it is missing |
|---|---|---|
| The first message offers `/goal all tasks in docs/plans/smoke.md are [x] or [!]` and does not wait for an answer | the `/run` skill, "belt and braces" | the skill did not load: check `ls $CLAUDE_CONFIG_DIR/skills/run/SKILL.md`, then `/skill-doctor` |
| A status line at the bottom: `harness-sandbox  Sonnet 5/medium  ctx N%  5h N%  7d N%  cache …` | `statusLine` | check the path in `settings.json` → `statusLine.command`; run it by hand with `echo '{}' \| ~/.claude/statusline.sh` |
| Not a single question for the whole run | the contract + `/run` | if it does ask, send the transcript: that is a contract defect, not a hook one |
| Try it yourself mid-session: "read big.py in full" → refused, with text about Grep and a window | `read-guard` | `claude --debug hooks` shows whether the hook was called |
| After every task: `[x]`, a Log line, and a commit `T0N: …` (see `git log --oneline`) | `run-task` | — |
| On T04 the model does not repeat `false` but writes `ROOT CAUSE:`/`EVIDENCE:` or blocks the task | the contract; `retry-guard` only fires on the second identical failure, so this is expected | if it repeats 3+ times, send the transcript |
| Try interrupting: say "stop, we will continue tomorrow" while tasks are open → the model returns to work with text about N open tasks | `stop-guard` | `tail ~/.local/state/cc-stop-guard/*` — is the counter growing? If it is 0, the hook was not called: check `hooks.Stop` in `settings.json` |
| When it finishes: a "Plan finished" notification | `notify`, from `stop-guard` | try `osascript -e 'display notification "x"'` by hand |
| `touch .claude/plan-pause` mid-run → the model is allowed to stop | the stop-guard exit | — |

Also worth a look: `/usage` inside the session should show the share of `subagent_heavy` / `cache_miss` (expected to be low across five tasks), and `/insights` should show nothing alarming.

Check the subagents separately, in the same session: "use scout to find where the variable `line` is defined". The answer must contain `big.py:<line>` and a `TOOLS USED: Grep:… Read:…` line. If scout answers "not found" with no `TOOLS USED`, the `subagent-evidence` hook should have sent it back; `claude --debug hooks` will show the `SubagentStop` call.

## 5. Install into `~/.claude`

Once §2–4 have passed:

```bash
./install.sh
```

The script: backup → copy files → merge `settings.json` → syntax checks → report. The merge keeps your `permissions`, `env`, MCP servers and other people's hooks; the harness's own keys (`model`, `effortLevel`, cache, ceilings) **override** yours, and the diff is printed on screen — read it. The harness's hooks are appended to yours per event, and a repeated install does not duplicate them. `~/.claude.json` is not touched.

Then:

```bash
./selftest.sh ~/.claude
claude          # in any project; the status line appears immediately
```

## 6. Rollback

```bash
./uninstall.sh ~/.claude-backup/<stamp>
```

It removes the harness's files (only those present in this checkout), restores `settings.json`, `CLAUDE.md`, `hooks/`, `agents/`, `skills/`, `commands/`, `keybindings.json` and `cc-night` from the backup, and verifies the result against `MANIFEST.txt`. `~/.claude.json` is left alone (a copy sits next to the backup as `dot-claude.json` if you need it).

To roll back from the full archive in §1: `tar xzf ~/claude-full-<stamp>.tgz -C ~` over the top.

## 7. What can go wrong — honestly

- **The `settings.json` merge overrides your model and effort.** That is by design, but if you had `opus[1m]` as your default, it is now `sonnet[1m]`, and an `effortLevel` of `high` becomes `medium`. The diff shows both — read it. Your own `env` variables survive the merge, including ones this harness deliberately leaves off (`CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` is the one to look for: agent teams cost about 7x the tokens, which is why `ultracode` and the workflow keyword trigger are off here).
- **You already have another `Stop` hook.** Both will be called, and a block from either stops the turn. There is no conflict, but there will be two different texts in the context. Look at `jq .hooks.Stop ~/.claude/settings.json`.
- **`--dangerously-skip-permissions` inside `cc-night`.** The script does not check where you run it. The sandbox is your responsibility.
- **A project `CLAUDE.md` with its own rules** is left exactly as it is; the harness does not touch it. If it contains something contradictory ("ask before every step"), the more specific file wins — that is, the project's. Bring project files in line with `project-template/AGENTS.md` through `/intake`.
- **Version.** The keys `maxEffortLevel`, `subagentPromptCacheTtl` and `omitClaudeMd` in agents need 2.1.267 / 2.1.271 or later. On an older build Claude Code ignores them silently — so check `claude --version` first.
