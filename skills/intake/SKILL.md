---
name: intake
description: Project-level interview that writes docs/PROJECT.md — identity, scope, capability ledger, decisions the agent owns, and the checks that gate every task. Run once per repository before the first /plan, or when the product scope changes.
argument-hint: <one line about the project, or empty>
---

# /intake

`/plan` asks about one task. `/intake` asks about the project, once, so that every later `/plan` can skip the same questions. Output is `docs/PROJECT.md`; template at `~/.claude/project-template/docs/PROJECT.md`.

## 1. Look before asking

- Repo facts from the machine: language and framework versions, package manager, lockfile, test runner, linter, CI config, Docker, existing `AGENTS.md`/`CLAUDE.md`/`README.md`, `docs/`.
- If `docs/PROJECT.md` already exists: read it, list what is `_unanswered_`, and ask only that.
- Everything discoverable is written down, not asked.

## 2. Interview, all at once

AskUserQuestion, up to 4 per call, calls back to back, none later. Cover:

1. **Identity**: name/slug, repository, who else touches this code (other agents, people).
2. **Goal and first journey**: what must work end to end first; what the first version explicitly must NOT do.
3. **Capabilities**: which of these the product needs now — accounts, persistence, uploads, payments, admin, external integrations, real-time, background jobs, scheduled work, notifications. Each answer becomes a ledger row.
4. **Irreversible actions**: which may run unattended (migrations on a dev DB, deploys to staging) and which never may (production deploy, payments, data deletion, sending email/messages to real users).
5. **Environments**: where tests run, what needs Docker or credentials, what is allowed to touch the network.
6. **Definition of done for any task**: the exact commands that must exit 0 before a task is `[x]` (tests, lint, type check, architecture check). If the suite is already red, is the baseline accepted as-is?
7. **Coverage**: is there a coverage command and a report format; what does it measure today (run it, do not ask for the number); should the ratchet (`scripts/coverage_gate.py`, a floor that rises and never falls by itself) be part of the gate checks, and if the suite is slow, per task or per plan?
8. **Delivery**: commit per task or per plan; branch policy; who reviews.

Do not ask about: file layout, naming, library choice when the repo already has one, formatting, hosting-provider comparisons, anything in "Decided by the agent".

## 3. Write `docs/PROJECT.md`

Fill the template. Rules:

- The **capability ledger** holds one state per row: `included` / `available` / `absent` / `removed`. A capability with no row is `absent`. Dormant code, an old migration or a doc mention is not a requirement: never build or restore an `absent`/`removed` capability without a direct request. A direct request is full authorization — record it and proceed without asking again.
- **Decided by the agent** lists decision classes the user does not want to be asked about. Start from the defaults in the template, add project-specific ones from the interview.
- **Gate checks** lists the commands from question 6 verbatim, plus `python3 scripts/coverage_gate.py --run` when the answer to question 7 put the ratchet there. `/plan` copies them into every task's verify line. The first run of the gate records the coverage floor (`--set-floor`); the floor is where the project is today, not where it should be.
- **Unattended policy** lists what `/run` may do alone and what must become `[!] BLOCKED`.
- Set `intake: completed <date>`.

## 4. Wire the repo

- If `AGENTS.md` is absent, create it from `~/.claude/project-template/AGENTS.md` and make `CLAUDE.md` contain only `@AGENTS.md`. Other agents read `AGENTS.md`; Claude Code expands the import.
- If `CLAUDE.md` already has content (existing project): move repository facts (stack, commands, layout, conventions, gotchas) into `AGENTS.md`; drop behavioral rules that the global contract `~/.claude/CLAUDE.md` already covers (questions, autonomy, retries, git hygiene) and any rule that contradicts it — list each dropped line in the summary so the owner sees what changed. Keep `PROJECT.llm` or other context-box files untouched and reference them from `AGENTS.md`.
- If `.claude/settings.json` exists in the project: report keys that override the user level (`model`, `effortLevel`, `permissions.deny`, own `Stop`/`PreToolUse` hooks). Do not edit it; the owner decides.
- Add `.claude/scratch/` and `.claude/plan-pause` to `.gitignore` if missing.
- Suggest `.claude/rules/<area>.md` with `paths:` for any area that has its own conventions (they load only when matching files are touched).
- Run `python3 scripts/project_check.py` if present; it validates the ledger states and reports `_unanswered_` cells.

Finish with a 5-line summary and the path. No questions after this point.
