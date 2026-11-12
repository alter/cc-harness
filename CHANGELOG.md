# Changelog

One entry per `stable-*` tag, newest first. The reasons and the evidence behind each entry are in the plan under `docs/plans/` named in it.

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
