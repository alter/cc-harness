---
intake: not started
---
# PROJECT

Single source of truth for what this project is, what it contains, and what the agent may decide alone. `/plan` reads it before every task. Cells hold `_unanswered_` until asked, `n/a` when not applicable.

## 1. Identity

| Question | Answer |
|---|---|
| Name / slug | _unanswered_ |
| Repository | _unanswered_ |
| Other agents or people working in this repo | _unanswered_ |
| Stack (from the machine, with versions) | _unanswered_ |

## 2. Goal

| Question | Answer |
|---|---|
| What must work end to end first | _unanswered_ |
| What the first version must NOT do | _unanswered_ |

## 3. Capability ledger

One state per row: `included` (present, expected to work) · `available` (partly there; note says what is missing) · `absent` (not part of this project; build only on request) · `removed` (deleted on purpose; restore only on request). No row means `absent`.

| Capability | State | Note |
|---|---|---|

`/intake` fills this from the repository. What counts as a capability depends on what the repository is; take the rows that apply, add the ones that are missing, and drop the rest:

- **Service / web or mobile backend**: accounts and sign-in, persistent storage, file uploads, payments, admin and roles, background jobs, notifications (email, push), real-time, external integrations, a model or LLM call.
- **Library / SDK**: the public API surface, supported runtimes and versions, optional extras, plugins or hooks, a CLI entry point.
- **Command-line tool**: commands and subcommands, config file, network access, writing outside the working directory, self-update.
- **Infrastructure as code**: environments (dev/stage/prod), the resources each module creates, state backend, secrets handling, destructive operations.
- **Host or fleet configuration** (ansible, shell, dotfiles): the hosts or groups touched, services it installs or restarts, users and keys it manages, firewall rules.
- **Data pipeline / ML**: sources, outputs, schedules, models trained or served, evaluation gates.

## 4. Decided by the agent — never asked

Defaults; extend per project. The agent makes these calls, records them under a plan's `## Assumptions`, and explains them in one line.

- File layout, naming, formatting; modular code — no single giant file, modules split by responsibility.
- Library choice when the repo already uses one for the purpose; standard library over a new dependency.
- Test shape: unit for pure rules, integration through real boundaries for shared behavior, end-to-end only for the minimal happy path. Never test wording or layout.
- No speculative layers, base classes or options; the existing structure of the repository is followed, not replaced by a preferred one.
- Scope of validation for a change: the narrowest stable check that proves it, plus directly coupled risks.
- Isolation of parallel copies: ports, Compose project names, test databases and temporary directories are derived from the checkout path, so two worktrees never collide; test databases end in `_test`.
- Which docs to update when behavior, contracts, setup or operations change.

Further defaults by kind of repository — keep the lines that fit, delete the others:

- *Service*: local services via Docker Compose, never native installs; one service unless a measured limit says otherwise; no CQRS or event bus without a measured need.
- *Library*: no new runtime dependency without a decision here; public API changes follow the project's versioning policy.
- *Infrastructure / host configuration*: every change is shown as a plan or dry run (`terraform plan`, `ansible --check --diff`, `nginx -t`) before it is applied; apply is in the "must become BLOCKED" column below.

## 5. Unattended policy

| May run alone | Must become `[!] BLOCKED` |
|---|---|
| tests, lint, type check, local builds | production deploy |
| migrations against local/dev databases | payments, money movement |
| commits on the current branch | deleting user data, dropping tables |
| reading docs and public web | sending email/messages to real users |
| _unanswered_ | new paid dependency or service account |

| Question | Answer |
|---|---|
| A non-production target is recognised by (database name, kube context, workspace, profile, host group) | _unanswered_ |

Commands that need the owner, as prefixes; `git-guard` refuses them in every session:

```deny
```

## 6. Gate checks

Two tiers. The harness runs what is declared here and nothing else; a tool the project does not list is not run.

### Fast tier

Commands that must exit 0 before any task is marked `[x]`. `/plan` copies them into every verify line. Unit tests, plus at most three heavy tests per task; the rest of the heavy tests belong to the full tier.

```
_unanswered_
```

### Full tier

Run by the night full run and at the end of a milestone, never before a single `[x]`: the whole suite, mutation testing, fuzzing, long integration. The runner does not stop at a failing command; it reports every one. A red full run holds the milestone; surviving mutants become tasks and do not hold it.

```
_unanswered_
```

A command may carry attributes on a `#:` line directly above it. Keys: `budget` (`40m`; over it the command is stopped with its children and reported `timeout`; without it, twice the last passing time), `expect` (a postcondition on the result; exit 0 with a failed `expect` is `empty`), `report` (JUnit XML the command writes), `list` (a command that lists the tests without running them — `pytest --collect-only -q`, `go test -list .`, `cargo nextest list`, `jest --listTests`), `shards` and `parallel` (the command uses `{shard}`/`{shards}`; shard 1 runs alone first and the rest start only after it passed its budget, its `expect` and its census), `repeat` with `reason` (a declared repetition; anything else that runs a test twice is a duplicate). With `report` and `list` the run is censused: each test ran exactly once, every listed test ran, shards are disjoint.

```text example-full-tier
#: budget=40m shards=16 parallel=4 report=reports/mut-{shard}.xml list="pytest --collect-only -q -m mutation" expect="test -s reports/mut-{shard}.xml"
mutmut run --shard {shard}/{shards}
```

| Question | Answer |
|---|---|
| How a test is marked full-only here (marker, build tag, `#[ignore]`, a directory, a separate command) | _unanswered_ |
| Fast tier wall time at `T00`, seconds, from the run | _unanswered_ |
| Full tier budget, minutes, whole run (over it: a finding, and `/test-audit` is due) | _unanswered_ |
| Audit: run in another order (a command, for `/test-audit`; e.g. `pytest -p random_order`, `go test -shuffle=on`) | _unanswered_ |
| Audit: run in parallel (a command, for `/test-audit`; e.g. `pytest -n 4`, `go test -p 4`, `cargo nextest run`) | _unanswered_ |

Baseline accepted as-is (pre-existing failures tolerated): _unanswered_

Coverage: the command, its report format, and where the floor lives (`.coverage-gate.json`). The ratchet
(`python3 scripts/coverage_gate.py --run`) belongs in the list above per task, or runs at `T00` and at the
plan's finish when the suite is slow — say which. The floor rises on its own; lowering it is a decision
recorded here, with a date and a reason, and never a way to make a check pass.

| Question | Answer |
|---|---|
| Coverage command | _unanswered_ |
| Report format (`coverage-py` / `json-summary` / `cobertura` / `lcov` / `go`) | _unanswered_ |
| Floor today (from the tool, not from memory) | _unanswered_ |
| Ratchet per task or per plan | _unanswered_ |
| Areas deliberately left uncovered, and why | _unanswered_ |

## 7. Delivery

| Question | Answer |
|---|---|
| Commit per task or per plan | _unanswered_ |
| Branch policy | _unanswered_ |
| Who reviews before merge | _unanswered_ |

## 8. Disclosure required by the receiving repository

Read the target's `CONTRIBUTING.md` / `AGENTS.md` before filling this in; the answer belongs to them, not to us. `none` means the repository asks for nothing and nothing is volunteered. A wording means it is inserted verbatim into the pull-request body. `_unanswered_` blocks opening a pull request there.

| Target | What it requires | Wording to use |
|---|---|---|
| this repository | _unanswered_ | _unanswered_ |

Whatever this says, a direct question from a person is answered by the owner, not by the session, and the session never writes in his voice outside this machine.

## 9. Owning docs

Read before working in the area. Prefer `.claude/rules/<area>.md` with `paths:` so this loads automatically.

| Area | Document |
|---|---|
| _unanswered_ | _unanswered_ |

## 10. Fingerprint

The signal files of the repository when this file was last reconciled with it: manifests, lint/test/type configs, build and CI files, container files, test and migration directories. `scripts/project_check.py` compares it with the repository and reports what appeared or disappeared since; a new line inside a manifest is not a change of this kind. After reconciling (`/intake refresh`), run `python3 scripts/project_check.py --refresh-fingerprint`.

```fingerprint
```
