---
name: intake
description: Project-level interview that writes docs/PROJECT.md — identity, scope, capability ledger, decisions the agent owns, and the checks that gate every task. Run once per repository before the first /plan, or when the product scope changes; `/intake refresh` reconciles an existing PROJECT.md with a repository that grew.
argument-hint: refresh | <one line about the project, or empty>
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
3. **Capabilities**: first decide what the repository is (a service, a library, a CLI, infrastructure as code, host configuration, a data pipeline — read it off the repository), then ask which capabilities of that kind it has now, using the examples under §3 of the template. Each answer becomes a ledger row; a web product's list is not the default for everything.
4. **Irreversible actions**: which may run unattended (migrations on a dev DB, deploys to staging) and which never may (production deploy, payments, data deletion, sending email/messages to real users). The commands that must never run unattended go into the ` ```deny ` block of §5 as prefixes (`terraform apply`, `kubectl delete`, `ansible-playbook site.yml`); `git-guard` refuses them. **How is a non-production target recognised here** — a database name (`*_test`, `*_dev`), a kube context or namespace, a terraform workspace, a cloud profile or account, a host group? Read what the repository already uses first; the answer goes into §5 and every check that touches a live system (`/pgsql-slow-queries --live`, migrations, smoke runs) holds to it.
5. **Environments**: where tests run, what needs Docker or credentials, what is allowed to touch the network.
6. **Definition of done for any task**: the exact commands that must exit 0 before a task is `[x]` (tests, lint, type check, architecture check) — the **fast tier**. Separately, the **full tier** run at night and at a milestone (the whole suite, mutation, fuzzing, long integration), and how this project marks a test as full-only (a marker, a build tag, `#[ignore]`, a directory, a separate command — read it off the repository first). Time the fast tier once and record the seconds. If the suite is already red, is the baseline accepted as-is?
6a. **Linters, offered, never imposed**: read what is in the repository and what is installed on the machine (`command -v`), then offer only what fits: `.github/workflows/` → `actionlint`; shell scripts → `shellcheck`; YAML configs → `yamllint`; a language linter (`ruff`, `eslint`, `golangci-lint`, `cargo clippy`) only when the project already configures or runs it. `gitleaks` is offered to every repository: a secret in a pushed commit cannot be taken back. Everything accepted runs on changed files only — `python3 scripts/lint_changed.py --base <T00 commit> --glob '*.sh' -- shellcheck -S warning`, and `gitleaks git --log-opts="<T00 commit>..HEAD"` for secrets — so the old findings of a repository you did not write never block a task, and new ones never get in. Nothing is installed or added without a yes.
7. **Coverage**: is there a coverage command and a report format; what does it measure today (run it, do not ask for the number); should the ratchet (`scripts/coverage_gate.py`, a floor that rises and never falls by itself) be part of the gate checks, and if the suite is slow, per task or per plan?
8. **Delivery**: commit per task or per plan; branch policy; who reviews.
9. **Contributing outward**: does work from here go to a repository someone else owns? If so, read that target's `CONTRIBUTING.md`/`AGENTS.md` first and ask only what is not written there: what it requires disclosed, and in what wording. `none` is a valid answer when it requires nothing. Do not ask the user to invent a policy — this row records what the receiving project already demands.

Do not ask about: file layout, naming, library choice when the repo already has one, formatting, hosting-provider comparisons, anything in "Decided by the agent".

## 2a. `/intake refresh` — the project grew

When `docs/PROJECT.md` exists and `scripts/project_check.py` reports it out of date, or the night report lists stale declarations (a command in §6 that no longer exists), do not interview from scratch. Read the repository again, compare it with `PROJECT.md` and its fingerprint, and ask only about what changed: a new manifest or service (§1, §6), a new check or test directory (§6 tiers), a command that disappeared (§6), a capability that the code now has without a ledger row (§3). Dependencies inside a manifest are not asked about; they live in the manifest. Then update the sections, run `python3 scripts/project_check.py --refresh-fingerprint`, and report what changed.

## 3. Write `docs/PROJECT.md`

Fill the template. Rules:

- The **capability ledger** holds one state per row: `included` / `available` / `absent` / `removed`. A capability with no row is `absent`. Dormant code, an old migration or a doc mention is not a requirement: never build or restore an `absent`/`removed` capability without a direct request. A direct request is full authorization — record it and proceed without asking again.
- **Decided by the agent** lists decision classes the user does not want to be asked about. Start from the defaults in the template, add project-specific ones from the interview.
- **Gate checks** lists the commands from question 6 verbatim, plus `python3 scripts/coverage_gate.py --run` when the answer to question 7 put the ratchet there. `/plan` copies them into every task's verify line. The first run of the gate records the coverage floor (`--set-floor`); the floor is where the project is today, not where it should be.
- **Unattended policy** lists what `/run` may do alone and what must become `[!] BLOCKED`.
- **Disclosure** (§8) is a fact about the receiving repository, quoted from its own contributing rules, not a preference. Leave `_unanswered_` rather than guess: an unanswered row stops a pull request being opened there, which is the safe failure. It changes nothing about who answers a direct question — that is always the owner.
- Set `intake: completed <date>`, delete the `BOOTSTRAP_ONLY` block of `AGENTS.md` with its markers, and run `python3 scripts/project_check.py` — zero problems, including the AGENTS.md word budget, the `@AGENTS.md` import and dead links in `docs/`.

## 4. Wire the repo

- Fill the `## Map` table of `AGENTS.md` from the repository: one row per area (a module, an app, an infrastructure directory), its path, and the README or doc to read before changing it. Prefer `.claude/rules/<area>.md` with `paths:` for rules that should load automatically.
- If `AGENTS.md` is absent, create it from `~/.claude/project-template/AGENTS.md` and make `CLAUDE.md` contain only `@AGENTS.md`. Other agents read `AGENTS.md`; Claude Code expands the import.
- If `CLAUDE.md` already has content (existing project): move repository facts (stack, commands, layout, conventions, gotchas) into `AGENTS.md`; drop behavioral rules that the global contract `~/.claude/CLAUDE.md` already covers (questions, autonomy, retries, git hygiene) and any rule that contradicts it — list each dropped line in the summary so the owner sees what changed. Keep `PROJECT.llm` or other context-box files untouched and reference them from `AGENTS.md`.
- If `.claude/settings.json` exists in the project: report keys that override the user level (`model`, `effortLevel`, `permissions.deny`, own `Stop`/`PreToolUse` hooks). Do not edit it; the owner decides.
- In a repository you did not write, report its execution surface before anything runs from it: hooks in `.claude/settings*.json`, `.mcp.json` servers, `enableAllProjectMcpServers`, `ANTHROPIC_BASE_URL` or other endpoint overrides, `apiKeyHelper`, git hooks under `.git/hooks` or `core.hooksPath`, and invisible or bidirectional Unicode characters in instruction files (`CLAUDE.md`, `AGENTS.md`, `.claude/rules/`). A repository's configuration is code that runs on this machine; the owner decides what stays.
- Add `.claude/scratch/` and `.claude/plan-pause` to `.gitignore` if missing.
- Suggest `.claude/rules/<area>.md` with `paths:` for any area that has its own conventions (they load only when matching files are touched).
- Run `python3 scripts/project_check.py` if present; it validates the ledger states and reports `_unanswered_` cells.

Finish with a 5-line summary and the path. No questions after this point.
