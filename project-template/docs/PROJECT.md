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
| Accounts / sign-in | absent | |
| Persistent storage | absent | |
| File uploads | absent | |
| Payments | absent | |
| Admin / roles | absent | |
| External integrations | absent | |
| Background jobs / scheduling | absent | |
| Notifications (email, push, messaging) | absent | |
| Real-time | absent | |

## 4. Decided by the agent — never asked

Defaults; extend per project. The agent makes these calls, records them under a plan's `## Assumptions`, and explains them in one line.

- File layout, naming, formatting, splitting files above 1400 lines.
- Library choice when the repo already uses one for the purpose; standard library over a new dependency.
- Test shape: unit for pure rules, integration through real boundaries for shared behavior, end-to-end only for the minimal happy path. Never test wording or layout.
- Local services via Docker Compose, never native installs.
- One service unless a measured limit says otherwise; no speculative layers, base classes, CQRS, event buses.
- Scope of validation for a change: the narrowest stable check that proves it, plus directly coupled risks.
- Which docs to update when behavior, contracts, setup or operations change.

## 5. Unattended policy

| May run alone | Must become `[!] BLOCKED` |
|---|---|
| tests, lint, type check, local builds | production deploy |
| migrations against local/dev databases | payments, money movement |
| commits on the current branch | deleting user data, dropping tables |
| reading docs and public web | sending email/messages to real users |
| _unanswered_ | new paid dependency or service account |

## 6. Gate checks

Commands that must exit 0 before any task is marked `[x]`. `/plan` copies them into every verify line.

```
_unanswered_
```

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

## 8. Owning docs

Read before working in the area. Prefer `.claude/rules/<area>.md` with `paths:` so this loads automatically.

| Area | Document |
|---|---|
| _unanswered_ | _unanswered_ |
