---
name: test
description: Raise test coverage on purpose — measure, read the code and the existing tests, propose what to cover by risk, and write only after agreement; every test red first and proved by breaking the code. Wires the coverage ratchet at levels standard and release. Use before a release, when coverage is missing, before a risky change, or after a regression got through.
argument-hint: <module, path or behaviour to cover; empty to start from the whole project>
---

# /test

Two jobs, and they are not the same: prove the code does what it should, and make sure the next change cannot break it unnoticed. An agent that edits code all night needs the second one more than you do.

Coverage is raised on purpose, not by default. A project works at the level its `docs/PROJECT.md` §6 names in the row `Test coverage level`; with no row or no file that is `critical` — tests for critical code and for fixed bugs, nothing else, no ratchet. This skill is how the rest gets covered: before a release, or whenever the owner calls it.

Who called decides how it runs:

- **By hand** (the owner typed `/test` or asked for coverage): sections 1–3 end in a proposal. Nothing is written before the owner agrees — not a test, not `.coverage-gate.json`, not the level row.
- **From a task of a plan with `status: running`**: ask nothing. The task line names what to cover; cover exactly that by section 4 and report. A running plan never widens its own list, and a proposal that occurs to you goes under `## Assumptions` as a note for the owner.

## 1. Measure before writing anything

- Find the project's test command and the level row in `docs/PROJECT.md` §6, and the coverage setup (`.coverage-gate.json`) if there is one.
- No coverage setup: do not create one here. Measure with what the runner already offers, or count the tests per module by hand; the gate file is created in section 5 and only for an agreed `standard` or `release`.
- Run the suite once before touching anything and note the number and the already-failing tests — into the plan's `## Log`, or into the proposal when there is no plan. A test that was red before you started is not yours to count as a regression.

## 2. Read the code and the existing tests

Go through the project area by area (a `scout` for a large one): what the code does, which class below it belongs to, which tests exist for it and what they actually assert. A test that asserts a getter returns what it was given, or that a result `is not None`, runs a line and proves nothing: list it as weak, not as coverage.

Classes, highest first — choose by risk, not by percentage:

1. Behaviour the product promises and money or data depends on: payment, migration, deletion, authorisation, money arithmetic.
2. Code with branches an agent will touch again: parsers, state machines, retry and idempotency, boundary conversions.
3. Anything a past defect went through. Every fixed bug gets the test that would have caught it, even if coverage was already green there.
4. Public contracts: API shape, serialization, schema. One test per contract, not per field.
5. Everything else, calls into a ready SDK or library, and glue with no logic — last, or never. Such a test guards code that many applications already exercise and costs a maintenance line forever.

Never test wording, layout, log text, or the order of an unordered collection. Those tests fail on every honest change and teach the agent to edit tests instead of code.

## 3. Propose, then wait

Show the owner one list and ask through AskUserQuestion:

- **What to cover**, ranked by the classes above. For each item: the behaviour, why it matters, the test that will prove it.
- **What stays uncovered on purpose**, and why (ready SDK calls, glue, layout).
- **Weak tests found**, if any, and what would replace them.
- **The level**: keep the row as it is, or raise it to `standard` or `release` and wire the ratchet.

Ask the scope as one choice — classes 1–2 only, classes 1–4, or everything — with the smallest scope that closes the real risk first and marked recommended, and the level as a second question in the same call. Then write what was agreed and nothing more. A declined item goes into the report as declined, not into a later attempt.

## 4. Write it red first, then prove it can go red

For each case: write the test, run it, **show it failing for the reason you intend** (assertion, not import error), then make it pass. A test that was green the first time it ran has proved nothing yet — it may be asserting something that was already true.

If the code is untestable without touching the world (network, clock, filesystem, cloud), the smallest change that makes it testable comes first, as its own step: a seam (an argument, an injected client) rather than a mock of what you wish existed.

Reverse control: for every test that guards critical code, break the code on purpose in a scratch copy, run the test, keep the red output, restore the code. Record what you broke and what the failure said. A check that has never been red is not a check. In a task tree this is the `VERIFY` reverse-control item: the validator requires it at `standard` and `release`, and at `critical` it is written for tasks with critical code.

Mutations worth trying, in order: invert a condition, drop a guard clause, swap an operator (`<` for `<=`), skip an await, return early, off-by-one on a boundary. If a mutation leaves the suite green, that is a finding — write the missing case.

## 5. Wire the ratchet — only at an agreed `standard` or `release`

At `critical` skip this section: no gate file, no ratchet command, no floor.

- Write the agreed level into the row `Test coverage level` of `docs/PROJECT.md` §6 and fill the coverage rows next to it.
- Create `.coverage-gate.json` at the repository root — `command` (the test run that produces a report), `format` (`coverage-py` | `json-summary` | `cobertura` | `lcov` | `go`), `report` (the file it writes), `floor: 0`, `tolerance: 0.2` — then `python3 scripts/coverage_gate.py --run --set-floor` to record where the project stands today. The floor is a fact, not a target.
- `standard`: the ratchet is not a gate command. `/plan` runs `python3 scripts/coverage_gate.py --run` at `T00` and `/run` runs it again when the plan closes.
- `release`: add `python3 scripts/coverage_gate.py --run` to the gate checks in `docs/PROJECT.md` §6. From then on it rides in the gate set of every task that changes logic, through `cc-pertask run` and under the same per-task limit as the other gate commands. Where its measured run fits the limit, `/run` cannot mark `[x]` while coverage has fallen below the floor by more than the tolerance; where it does not, it is deferred with the other long checks and holds the plan's close instead.
- The floor rises by itself when coverage grows and never falls on its own. **Lowering it by hand is a decision, not a fix**: it goes into `docs/PROJECT.md` with a reason and a date, or it does not happen.

## 5a. A one-off mutation audit — when coverage is green and you still do not trust it

Coverage says execution passed through a line. It does not say the test would notice the line being
wrong. `assert fee(100) is not None` covers the line and proves nothing: change `amount * 0.1` to
`amount * 0.2` and the suite stays green. A model asked to raise coverage writes exactly these tests,
because they are the cheapest ones that satisfy the ratchet.

A mutation run finds them mechanically: it breaks the code by patterns and reports which broken
versions the suite failed to catch. A surviving mutant is a named blind spot with a line number.

**Not a gate check, and never in the fast tier.** A full run re-executes the suite once per mutant —
hours on a real project. Mutation runs and fuzzing belong to the **full tier** in `docs/PROJECT.md` §6:
the night run (`cc-night` → `fullrun.sh`) and the end of a milestone execute them, and the report lands
next to the plan. By hand, it is a deliberate audit on one module at a time. A task may declare as many
`[full, heavy]` checks as it needs; the fast tier carries unit tests and at most three heavy ones, or the
day goes to waiting for tests instead of writing code.

Pick the module by consequence, not by size: where a silently wrong value is worse than a crash —
money and fees, sizes and limits, boundaries and rounding, retry and idempotency, permissions. One
module per audit.

```bash
pip install mutmut && mutmut run --paths-to-mutate src/billing/ && mutmut results   # Python
npx stryker run --mutate 'src/billing/**/*.ts'                                       # TypeScript
```

Both write a report of survivors. Read it as a list of findings, not as a score:

- A **survivor** in the ranked areas above is a missing test case. It becomes a task through `/task`
  (or a line in the current plan) that names the mutation verbatim: "a test that fails when
  `src/billing/fee.py:41` `<=` becomes `<`". That task is written red first, like any other.
- A survivor in glue, logging, or a defensive branch that cannot be reached is **not** a finding.
  Record it once in `NOTES.md` as accepted, with the reason, so the next audit does not re-litigate it.
- A **timeout** or an **error** mutant is usually an infinite loop the mutation triggered; it counts as
  killed, not as a finding.
- The mutation score itself goes nowhere near the gate checks and nowhere near `.coverage-gate.json`.
  Nobody optimises it; the survivors are the output. Survivors do not hold a milestone; a red full run
  (a test that fails) does.
- Fuzzing follows the same rules: a crash or a hang it finds is a red full run and a task with the
  reproducing input attached; the corpus and the time budget live in the full-tier command, not here.

What comes out of an audit is a short list of tests worth writing, already justified. What must not
come out of it is a rewrite of the suite to please the tool, or a new number to chase.

Run it when: a regression got through despite green tests; before trusting an unattended run with a
module that moves money or data; once after a large stretch of agent-written tests, to see what those
tests actually assert. Not on a schedule.

## 6. Report

- What is now covered that was not, by behaviour and not by file.
- The number before and after, from the tool and not from memory; at `critical` without a coverage tool, the tests added per area.
- Every mutation you tried, and which ones the suite caught. Name the ones it did not.
- What is still uncovered on purpose, and why, and what the owner declined from the proposal — the honest boundary, the same list `/verify-task` writes under "what was not checked".
- The level row as it stands now.
- After a mutation audit: the survivors, split into tests to write and survivors accepted with a reason. Never the score.
