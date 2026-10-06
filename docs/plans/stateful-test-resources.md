---
status: running
created: 2026-10-06
---
# Stateful test resources: memory budget, leftovers, audit lens, template rules

## Goal
A test command that shares a machine without swap can no longer take the runner down unnoticed: `cc-fullrun` measures the peak memory of every command's process group, stops it when it passes its budget (declared `mem=`, or 75% of physical RAM) and reports `mem`, which holds a milestone. A command can declare a `leftover=` count (databases, temp dirs, containers) and the run reports what it left behind. `/test-audit` looks at tests that use an external stateful resource: isolation between parallel workers, calls to the resource per test, the time spent building the shared world, and a distribution mode that clones a database per worker for every module. The project template tells tests that only read a shared world to use a read-only connection, requires an equivalence test when a fast world builder bypasses the service layer, and a sweeper for resources named after a process. Everything stays language-neutral, with PostgreSQL as the worked example.

## Acceptance criteria
- [ ] AC1 Every command's peak memory (sum over its process group) is in the report and the tsv — `./selftest.sh` (fullrun-peak-mem)
- [ ] AC2 A command over its `mem=` budget is stopped with its group and reported `mem`; `mem` holds a milestone — `./selftest.sh` (fullrun-mem-budget), unit `milestone-mem-holds`
- [ ] AC3 Without `mem=`, the budget is 75% of physical RAM — `./selftest.sh` (fullrun-mem-default, with the RAM size overridden)
- [ ] AC4 `leftover=` counted before and after a command; growth is a finding, not a red status — `./selftest.sh` (fullrun-leftover)
- [ ] AC5 `/test-audit` names the test with the most calls to the resource and reports the isolation probe when §6 declares them — `./agenttest.sh test-audit`
- [ ] AC6 No regression against T00; a trial install passes `./selftest.sh <target>` — `./selftest.sh`

## Stack
bash 5.3, python 3.14 (stdlib), jq 1.6, git; Claude Code 2.1.289. Memory sampling through `ps` (BSD and procps both support `-o pgid=,rss=`).

## Decisions
- D1 Default memory budget: 75% of physical RAM when `mem=` is absent; an explicit `mem=` overrides.
- D2 Over the memory budget: the command is stopped like a timeout and reported `mem`; `mem` holds a milestone. Leftovers are a finding and a task, never a block.
- D3 The equivalence test (fast world builder against the service-layer builder) is an ordinary test of the project in the full tier, required by the template when a fast builder exists; the isolation probe between workers belongs to `/test-audit`.
- D4 Execution: in this session.
- D5 Branch: `main`, commits per task, no push.

## Assumptions
- Peak memory is sampled once per second from `ps -A -o pgid=,rss=`; a spike shorter than a second can be missed. The report says "sampled".
- Physical RAM: `sysctl -n hw.memsize` on macOS, `MemTotal` in `/proc/meminfo` on Linux; `FULLRUN_RAM_BYTES` overrides it for tests.
- `leftover=` is a command printing one number; anything else is a finding "leftover command did not print a number".

## Out of scope
- The owner's production project and its runner (hk): its `pgtemplate.py`, its CI lock, its xdist settings.
- Choosing a worker count automatically; the audit recommends one from measurements.
- psycopg pipeline mode or any driver-specific optimisation inside the harness.

## Tasks
- [ ] T00 Baseline: `./selftest.sh`, counts in Log — verify: `./selftest.sh`
- [ ] T01 Peak memory per command: sample the process group's RSS each second, record MiB in the tsv and the report — verify: selftest `fullrun-peak-mem`
- [ ] T02 `mem=` budget (`512M`, `2G`) and the 75%-of-RAM default; over it → stop the group, status `mem`; `check.py` holds a milestone on `mem` — verify: selftest `fullrun-mem-budget`, `fullrun-mem-default`, unit `milestone-mem-holds`
- [ ] T03 `leftover=`: count before and after each command; growth → finding naming the command and the delta — verify: selftest `fullrun-leftover`, `fullrun-leftover-not-a-number`
- [ ] T04 Template: `AGENTS.md` and `PROJECT.md` rules for stateful test resources (read-only connection for read-only tests, equivalence test for a fast world builder, a sweeper for process-named resources, distribution mode with per-module databases), PostgreSQL examples; §6 rows for the audit probes — verify: unit `test_project_template_full_tier_attrs` still passes + HUMAN
- [ ] T05 `/test-audit` lens for external stateful resources: isolation probe, calls per test from a declared command, world-building share, distribution mode; memory per worker from the run report to recommend a worker count — verify: `./agenttest.sh test-audit` (AC5)
- [ ] T06 Finish: README/BEHAVIOR/HARNESS; `./selftest.sh` against T00; `./agenttest.sh test-audit`; trial install — verify: `./selftest.sh`

## Log
