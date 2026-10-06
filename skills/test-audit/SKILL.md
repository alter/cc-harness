---
name: test-audit
description: Periodic review of an existing test suite — why it is slow, which tests are redundant or pointless, how to speed up the ones that must stay, and which tests can safely run in parallel. Measured, not guessed — timing from JUnit, flakiness from run history, order and parallel probes. Writes TEST-AUDIT.md; findings become tasks, nothing is deleted. Runs at every milestone, every 7 nights, and when the fast tier doubled or the full tier went over budget.
argument-hint: [report dir, default: next to the running plan]
---

# /test-audit

This is a review of the tests, not of the code. It does not delete, skip or rewrite a test. It produces evidence and findings; the review loop of `/run` turns the CONFIRMED ones into tasks.

Delegate the whole job to the `test-auditor` subagent (Opus, fresh context) with the report directory: the place where `FULLRUN-*` reports live (next to the plan or the milestone task).

## Data, measured first

Measure in a throwaway copy, never in the working tree: `git worktree add <tmp dir> HEAD`, run the full tier and the probes there with `--out <report dir as an absolute path>`, then `git worktree remove --force <tmp dir>`. Test runs write files (reports, state, caches); in the copy they disappear with it. The copy holds the last commit: uncommitted changes are not measured — say so in the report when `git status` is not clean.


- **No full run yet?** Run the full tier once (`cc-fullrun --out <report dir>`, or `python3 <harness>/fullrun/engine.py`) before anything else; an audit without a measured run is opinion.
- **Full run history**: `FULLRUN-*.tsv` (status and seconds per command), `FULLRUN-*.md` (census, time), `FULLRUN-*.tests.json` (outcome per test).
- **Time per test**: `python3 ~/.claude/fullrun/timing.py slowest --report '<report glob from §6>' --top 30`.
- **Flaky tests**: `python3 ~/.claude/fullrun/timing.py flaky --dir <report dir> --runs 10`.
- **Census**: the `## Census` lines of the latest full run — duplicates, overlap, missing tests.
- **Probes**, only when `docs/PROJECT.md` §6 declares them: "Audit: run in another order" and "Audit: run in parallel". Their per-test outcomes are compared with the normal run: a test that passes in order and fails reversed or in parallel depends on another test or on shared state.

## The four questions, each answered with evidence

1. **Why is it slow?** The slowest tests and the share of total time they take; for each, the cause read in its code: a real `sleep` or timeout, real network, a database or container started per test instead of per module, a fixture rebuilt every time, a large input generated on every run, a whole suite repeated (`-count`, `--reruns`, loops, shards that each run everything — the census says so).
2. **What is not needed?** A test that checks what another already checks (same code path, same assertion — cite both `path:line`); a test that cannot fail for any real defect (asserts a constant, a mock's own return value, wording); a test whose job a cheaper check does better (a type check, a schema validation, a linter rule, a property test replacing twenty examples). With a mutation report that names the killing tests, a test that kills no mutant another test does not is CONFIRMED redundant; without one it is PLAUSIBLE.
3. **How to make the needed ones faster?** Concrete changes with the expected gain: a fake clock instead of `sleep`, a shared fixture at module scope, a transaction rollback instead of re-creating the database, a smaller generated input, moving a heavy test to the full tier.
4. **What can run in parallel, and with what?** Groups of tests that share no mutable resource — database, files, ports, environment variables, global state, time — proven by the static scan and by the parallel/order probes. A pair that failed a probe is named with the resource it shares. "Run everything with -n 16" is not an answer; groups are.

## Output

`TEST-AUDIT.md` next to the full run reports:

```
Auditor: <context>, <date>; data: <report files>; probes run: <list or none>.

## 1. Why it is slow
## 2. What is not needed
## 3. How to speed up what stays
## 4. What can run in parallel
## What was not checked
```

Every finding: `path:line`, the measurement or probe that proves it, CONFIRMED or PLAUSIBLE, and the direction. Findings go into the review loop; the audit itself changes nothing in the repository but `TEST-AUDIT.md` and the run reports in the report directory.

## When it runs

- `cc-night`, when the latest `TEST-AUDIT.md` is 7 or more days old, or the latest full run reports `fast_doubled=1` or `full_over_budget=1`.
- `/run`, when it closes a milestone (a `gate:yes` task).
- On request.
