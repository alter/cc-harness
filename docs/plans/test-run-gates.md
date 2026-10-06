---
status: running
created: 2026-10-06
---
# Test run gates: budgets, a canary shard, a run census, a periodic test audit

## Goal
A full or fast test run can no longer burn hours proving nothing. Every command of a tier may carry a time budget, a postcondition on its result, a shard count and the report and list it produces. `fullrun.sh` runs one shard first and fans out only when that shard passed its budget, its postcondition and its census. The census proves each test ran exactly once and every test ran. The integrity guard flags repetition added to the code. The contract forbids re-running tests for confidence and requires restarting a run whose cause is fixed. `/test-audit` periodically reviews the suite: why it is slow, what is redundant, what to speed up, what may run in parallel. Everything stays language-neutral: JUnit XML and the project's own commands, declared in `docs/PROJECT.md` §6.

## Acceptance criteria
- [ ] AC1 A command over its budget is stopped with its process group and reported `timeout` within budget + 5 s — `./selftest.sh` (fullrun-timeout)
- [ ] AC2 Exit 0 with a failed `expect=` is `empty`, not `pass` — `./selftest.sh` (fullrun-empty)
- [ ] AC3 With `shards=N`, a canary shard that is not `pass` stops the fan-out: the other N−1 shards are reported `skipped: same cause` and never start — `./selftest.sh` (fullrun-canary-stops-fanout)
- [ ] AC4 The census reports duplicate executions, shard overlap, tests listed but never run, and zero tests; a canary shard that ran more than its share stops the fan-out — `./selftest.sh` (census-*, fullrun-census-dup-stops)
- [ ] AC5 A declared `repeat=N` with a reason is not a duplicate; an undeclared one is — `./selftest.sh` (census-repeat-declared)
- [ ] AC6 Added repetition (`-count=N`, `--reruns`, `--count`, `--repeat-each`, a loop around a test command, a CI matrix over the same suite) is an integrity finding; existing repetition is not — `./selftest.sh` (integrity-added-repeat-*)
- [ ] AC7 A milestone does not close while its latest full run has `fail`, `stale`, `timeout`, `empty` or `dup` — `./selftest.sh` (milestone-*-holds)
- [ ] AC8 `fullrun.sh --stop` stops the running full run of this checkout and its children — `./selftest.sh` (fullrun-stop)
- [ ] AC9 `/test-audit` on a fixture with a slow test, a duplicated test and an order-dependent pair names all three in TEST-AUDIT.md — `./agenttest.sh test-audit`
- [ ] AC10 No regression: every selftest check green at T00 is green at the finish; a trial install passes `./selftest.sh <target>` — `./selftest.sh`

## Stack
bash 5.3, python 3.14 (stdlib only: `xml.etree`, `subprocess`, `json`), jq 1.6, git; Claude Code 2.1.289. No new dependency.

## Decisions
- D1 `/test-audit` runs at every milestone and at most every 7 nights from `cc-night`, plus automatically when the latest full run reports `fast_doubled=1` or `full_over_budget=1`.
- D2 A milestone is held by `timeout`, `empty`, duplicate executions and shard overlap, exactly as by a red full run.
- D3 The census needs JUnit XML (`report=`) and a list command (`list=`). `/intake` offers the runner's flag for both; a command without them runs, the census for it is `SKIP` and the report carries a finding "this run is not verifiable".
- D4 Priority if time runs out: census + canary shard + budget/expect first; then the repetition guard and the contract rules; then `/test-audit`.
- D5 Branch: `main`, commits per task, no push.
- D6 Attribute syntax: a line `#: key=value …` directly above a command in the ` ``` ` block of a tier; lines starting with `#` were already ignored by `fullrun.sh`, so existing declarations keep working. Keys: `budget`, `expect`, `report`, `list`, `shards`, `parallel`, `repeat`, `reason`. A sharded command uses `{shard}` and `{shards}` placeholders.
- D7 The harness never touches the owner's production project or runner (hk); this plan changes cc-harness only.

## Assumptions
- Default budget when `budget=` is absent: twice the duration of the last `pass` of the same command in the previous FULLRUN tsv; no history → no budget.
- Canary share check: the canary shard may execute at most `ceil(listed / shards) × 1.5` tests and at least one.
- Same-signature short-circuit with `parallel>1`: the first two failures of a sharded command with the same first error line stop the remaining shards.
- A timeout is enforced by a Python wrapper that starts the command in its own session and kills the process group; bash has no portable process-group timeout on macOS.
- The engine of `fullrun.sh` moves to Python (`fullrun/engine.py`, with `census.py` and `timing.py` beside it), installed as `~/.claude/fullrun/`; `fullrun.sh` stays the entry point (`cc-fullrun`). The census and timing scripts named under `project-template/scripts/` in T05/T12 live there instead: the runner needs them in every project, a project does not need its own copy.
- The test audit's redundancy finding needs per-test kill data from a mutation report; where the tool does not provide it, the finding is PLAUSIBLE from reading, never CONFIRMED.

## Out of scope
- The owner's production project and its runner: restarting its mutation run, editing its tests.
- Deleting or rewriting tests automatically; the audit produces findings that become tasks.
- Per-tool parsers of mutation reports beyond what JUnit XML and a declared `audit-*` command give.
- CI configuration of any project.

## Tasks
- [x] T00 Baseline: `./selftest.sh` and `./agenttest.sh --self-check`, counts in Log — verify: `./selftest.sh; ./agenttest.sh --self-check`
- [x] T01 `fullrun.sh`: parse `#: key=value` attribute lines; record duration per command in the tsv; unknown keys are a finding — verify: selftest `fullrun-attrs-parsed`, `fullrun-unknown-attr`
- [x] T02 `budget=` (and the default from history) through a process-group timeout wrapper; status `timeout` — verify: selftest `fullrun-timeout`, `fullrun-default-budget-from-history`
- [x] T03 `expect=` postcondition; status `empty` — verify: selftest `fullrun-empty`
- [x] T04 `shards=N` with `{shard}`/`{shards}`: canary first, fan-out only after a `pass`, `parallel=K` for the rest, same-signature short-circuit — verify: selftest `fullrun-canary-stops-fanout`, `fullrun-shards-run`, `fullrun-same-signature-stops`
- [x] T05 `project-template/scripts/test_census.py`: JUnit XML + list → unique/executions/duplicates/overlap/missing/empty, `repeat=N` honoured, JSON summary — verify: unit tests `census-duplicates`, `census-overlap`, `census-missing`, `census-empty`, `census-repeat-declared`
- [x] T06 Census in `fullrun.sh`: after the canary (share check) and at the end; status `dup`; no `report=`/`list=` → census SKIP with a finding — verify: selftest `fullrun-census-dup-stops`, `fullrun-census-skip-finding`
- [x] T07 Full tier budget row in `PROJECT.md` §6; `full_over_budget=1` in the summary — verify: selftest `fullrun-over-budget`
- [ ] T08 `check.py`: a milestone is held by `timeout`, `empty`, `dup` in its latest FULLRUN tsv — verify: unit tests `milestone-timeout-holds`, `milestone-empty-holds`, `milestone-dup-holds`
- [ ] T09 `integrity-check.py`: added repetition markers (go `-count=`, `--count`, `--reruns`, `--repeat-each`, `--runs`, retries in runner configs, a loop or `xargs`/`seq` around a test command, a CI matrix over the same suite) — verify: selftest `integrity-added-repeat-*`, `integrity-existing-repeat-ignored`
- [ ] T10 `fullrun.sh --stop` (pid and commit of the running full run under `.claude/scratch/fullrun/`); contract and `/run`: never re-run tests for confidence; a run whose cause is fixed is stopped and restarted canary-first — verify: selftest `fullrun-stop` + HUMAN (contract text)
- [ ] T11 `/intake` and the PROJECT.md template: attribute syntax, `report=`/`list=` flags per runner offered from the repository, budgets from one measured run — verify: selftest `project-template-full-tier-attrs` (template block parses) + HUMAN
- [ ] T12 `project-template/scripts/test_timing.py`: slowest tests, setup vs call share from JUnit; per-test outcomes of every census kept; flaky = tests whose outcome flips across the last N runs — verify: unit tests `timing-slowest`, `timing-flaky`
- [ ] T13 `/test-audit` skill + `test-auditor` agent (Opus): timing, census, flakiness, redundancy (mutation report where available), parallel safety (static shared-resource scan + declared `audit-shuffle=`/`audit-parallel=` runs), TEST-AUDIT.md with the four sections, findings into the review loop — verify: `./agenttest.sh test-audit` (AC9)
- [ ] T14 Triggers: `cc-night` runs `/test-audit` when the last TEST-AUDIT is 7+ days old or the latest full run has `fast_doubled=1`/`full_over_budget=1`; `/run` runs it when it closes a milestone — verify: selftest `night-runs-test-audit`, `night-skips-fresh-test-audit`
- [ ] T15 Finish: README/BEHAVIOR/HARNESS; `./selftest.sh` against T00; `./agenttest.sh` complete; trial install and `./selftest.sh <target>` — verify: `./selftest.sh && ./agenttest.sh`

## Log
- 2026-10-05 T00: baseline: selftest 302/0, agenttest --self-check ok.
- 2026-10-05 T01: ядро fullrun.sh перенесено в fullrun/engine.py (fullrun.sh — обёртка, ищет движок рядом или в ~/.claude/fullrun; install/uninstall ставят каталог fullrun); строки #: key=value прикрепляются к следующей команде, неизвестный ключ — находка в отчёте; tsv: статус, команда, секунды. Все прежние проверки fullrun-* и night-runs-* зелёные; fullrun-unknown-attr и fullrun-duration-recorded красные до правки (attrs-parsed был зелёным: # строки и раньше пропускались). selftest 305, failed 0.
- 2026-10-05 T02: budget= (s/m/h) через отдельную сессию процесса: по истечении SIGTERM группе, через 5 s SIGKILL, статус timeout; без budget= — 2× длительность последнего pass этой же команды (не меньше FULLRUN_MIN_BUDGET, по умолчанию 60 s). Проверки: timeout при budget=1s за 2 s, процесс-потомок sleep 31.25 убит, бюджет по истории ловит sleep 6 после sleep 1. Таймаут написан в T01 до тестов; красный эталон — прежний bash-раннер (788e76a~1): budget=1s, sleep 3 → pass. selftest 309, failed 0.
- 2026-10-05 T03: expect= — команда-постусловие после кода выхода 0; неуспех → статус empty и находка «прогон ничего не доказал» (твой артефакт в 942 байта). Проверка fullrun-empty красная до правки. selftest 310, failed 0.
- 2026-10-05 T04: shards=N с {shard}/{shards}: часть 1 идёт одна; не pass → остальные N−1 записываются skipped «та же причина» и не стартуют; после pass остальные в parallel=K потоков; две неудачи с одной сигнатурой (первая строка error/fail/exception/…, цифры нормализованы) — не начатые части skipped. Проверки canary-stops-fanout, shards-run, same-signature-stops, skipped считаются — красные до правки (параллельность «прошла» случайно: старый код части не размножал). selftest 315/0.
- 2026-10-05 T05: fullrun/census.py: JUnit XML (по glob на каждую часть) против списка (--list-cmd или --list-file): unique, executions, дубли сверх repeat, пересечение частей, пропущенные из списка, empty; нормализация id (путь/модуль/::), сопоставление по суффиксу (go: TestA против pkg.TestA), строки списка с пробелами — не тесты; JSON и код выхода 1 при красном. 9 тестов census-* (selftest/test_fullrun.py, подключён в selftest), красные до реализации. selftest 324, failed 0.
- 2026-10-05 T06: engine: перед запуском удаляются старые файлы report=; перепись после pass одиночной команды и после части-разведки: empty при 0 тестов, dup при дублях/пересечении, у разведки — больше ceil(listed/shards)×1.5 тестов → dup и размножение не начинается; после всех частей — перепись серии (пропуски из list= → dup, отдельная строка tsv «[census of N shards]»); без report=/list= — находка «census SKIP … not verifiable»; repeat= без reason= — находка; раздел ## Census в отчёте. 4 проверки fullrun-census-* красные до правки. selftest 328/0. (По ходу: моя команда с cat без аргументов зависла на stdin — остановлена TaskStop.)
- 2026-10-05 T07: PROJECT.md §6: строка «Full tier budget, minutes, whole run»; engine меряет весь полный ярус, full_over_budget=1 в сводке и раздел ## Time с пометкой «/test-audit is due». Проверки fullrun-over-budget/within-budget красные до правки. selftest 330/0.
