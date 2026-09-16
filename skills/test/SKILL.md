---
name: test
description: Cover code with tests that can actually fail — pick what to cover by risk, write the test red first, prove it catches the defect by breaking the code, then wire the coverage ratchet so the number cannot silently fall. Use when coverage is missing, before a risky change, or after a regression got through.
argument-hint: <module, path or behaviour to cover; empty to start from the coverage report>
---

# /test

Two jobs, and they are not the same: prove the code does what it should, and make sure the next change cannot break it unnoticed. An agent that edits code all night needs the second one more than you do.

## 1. Measure before writing anything

- Find the project's test command in `docs/PROJECT.md` §6 and its coverage setup (`.coverage-gate.json` if it exists).
- No coverage setup yet: create `.coverage-gate.json` at the repository root — `command` (the test run that produces a report), `format` (`coverage-py` | `json-summary` | `cobertura` | `lcov` | `go`), `report` (the file it writes), `floor: 0`, `tolerance: 0.2` — then `python3 scripts/coverage_gate.py --run --set-floor` to record where the project stands today. The floor is a fact, not a target.
- Run the suite once before touching anything and write the number and the already-failing tests into the plan's `## Log`. A test that was red before you started is not yours to count as a regression.

## 2. Choose by risk, not by percentage

Ranked, highest first. Stop when the budget for this task runs out; do not chase the number.

1. Behaviour the product promises and money or data depends on: payment, migration, deletion, authorisation, money arithmetic.
2. Code with branches an agent will touch again: parsers, state machines, retry and idempotency, boundary conversions.
3. Anything a past defect went through. Every fixed bug gets the test that would have caught it, even if coverage was already green there.
4. Public contracts: API shape, serialization, schema. One test per contract, not per field.
5. Everything else, and glue with no logic — last, or never. A test that asserts a getter returns what it was given proves nothing and costs a maintenance line forever.

Never test wording, layout, log text, or the order of an unordered collection. Those tests fail on every honest change and teach the agent to edit tests instead of code.

## 3. Write it red first

For each case: write the test, run it, **show it failing for the reason you intend** (assertion, not import error), then make it pass. A test that was green the first time it ran has proved nothing yet — it may be asserting something that was already true.

If the code is untestable without touching the world (network, clock, filesystem, cloud), the smallest change that makes it testable comes first, as its own step in the plan: a seam (an argument, an injected client) rather than a mock of what you wish existed.

## 4. Prove it can go red — the reverse control

For every test that guards something important, break the code on purpose in a scratch copy, run the test, keep the red output, restore the code. Record what you broke and what the failure said. A check that has never been red is not a check; in a task tree this is the `VERIFY` reverse-control item and it is mandatory.

Mutations worth trying, in order: invert a condition, drop a guard clause, swap an operator (`<` for `<=`), skip an await, return early, off-by-one on a boundary. If a mutation leaves the suite green, that is a finding — write the missing case.

## 5. Wire the ratchet so it holds without you

- Add `python3 scripts/coverage_gate.py --run` to the gate checks in `docs/PROJECT.md` §6. From then on every task's verify line includes it, and `/run` cannot mark `[x]` while coverage has fallen below the floor by more than the tolerance.
- The floor rises by itself when coverage grows and never falls on its own. **Lowering it by hand is a decision, not a fix**: it goes into `docs/PROJECT.md` with a reason and a date, or it does not happen.
- If the suite is slow, the ratchet belongs to the whole plan rather than each task: run it at `T00` and again at the finish, and keep the per-task verify narrow. Say which you chose in `## Decisions`.

## 6. Report

- What is now covered that was not, by behaviour and not by file.
- The number before and after, from the tool and not from memory.
- Every mutation you tried, and which ones the suite caught. Name the ones it did not.
- What is still uncovered on purpose, and why — the honest boundary, the same list `/verify` writes under "what was not checked".
