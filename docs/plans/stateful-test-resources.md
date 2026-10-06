---
status: running
created: 2026-10-06
---
# Stateful test resources: memory budget, leftovers, audit lens, template rules

## Goal
A test command that shares a machine without swap can no longer take the runner down unnoticed: `cc-fullrun` measures the peak memory of every command's process group, stops it when it passes its budget (declared `mem=`, or 75% of physical RAM) and reports `mem`, which holds a milestone. A command can declare a `leftover=` count (databases, temp dirs, containers) and the run reports what it left behind. `/test-audit` looks at tests that use an external stateful resource: isolation between parallel workers, calls to the resource per test, the time spent building the shared world, and a distribution mode that clones a database per worker for every module. The project template tells tests that only read a shared world to use a read-only connection, requires an equivalence test when a fast world builder bypasses the service layer, and a sweeper for resources named after a process. Everything stays language-neutral, with PostgreSQL as the worked example.

## Acceptance criteria
- [x] AC1 Every command's peak memory (sum over its process group) is in the report and the tsv — `./selftest.sh` (fullrun-peak-mem)
- [x] AC2 A command over its `mem=` budget is stopped with its group and reported `mem`; `mem` holds a milestone — `./selftest.sh` (fullrun-mem-budget), unit `milestone-mem-holds`
- [x] AC3 Without `mem=`, the budget is 75% of physical RAM — `./selftest.sh` (fullrun-mem-default, with the RAM size overridden)
- [x] AC4 `leftover=` counted before and after a command; growth is a finding, not a red status — `./selftest.sh` (fullrun-leftover)
- [x] AC5 `/test-audit` names the test with the most calls to the resource and reports the isolation probe when §6 declares them — `./agenttest.sh test-audit`
- [x] AC6 No regression against T00; a trial install passes `./selftest.sh <target>` — `./selftest.sh`

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
- [x] T00 Baseline: `./selftest.sh`, counts in Log — verify: `./selftest.sh`
- [x] T01 Peak memory per command: sample the process group's RSS each second, record MiB in the tsv and the report — verify: selftest `fullrun-peak-mem`
- [x] T02 `mem=` budget (`512M`, `2G`) and the 75%-of-RAM default; over it → stop the group, status `mem`; `check.py` holds a milestone on `mem` — verify: selftest `fullrun-mem-budget`, `fullrun-mem-default`, unit `milestone-mem-holds`
- [x] T03 `leftover=`: count before and after each command; growth → finding naming the command and the delta — verify: selftest `fullrun-leftover`, `fullrun-leftover-not-a-number`
- [x] T04 Template: `AGENTS.md` and `PROJECT.md` rules for stateful test resources (read-only connection for read-only tests, equivalence test for a fast world builder, a sweeper for process-named resources, distribution mode with per-module databases), PostgreSQL examples; §6 rows for the audit probes — verify: unit `test_project_template_full_tier_attrs` still passes + HUMAN
- [x] T05 `/test-audit` lens for external stateful resources: isolation probe, calls per test from a declared command, world-building share, distribution mode; memory per worker from the run report to recommend a worker count — verify: `./agenttest.sh test-audit` (AC5)
- [x] T06 Finish: README/BEHAVIOR/HARNESS; `./selftest.sh` against T00; `./agenttest.sh test-audit`; trial install — verify: `./selftest.sh`

### After the final review
- [x] T07 `leftover=` on a sharded command: counted around the canary and around the whole fan-out, reported against the command, never per parallel shard — verify: selftest `fullrun-leftover-parallel-no-false-finding`, `fullrun-leftover-parallel-leak`
- [ ] T08 Shared memory: a forked process group that shares a big buffer must not be over-counted into a `mem` stop; on Linux sum `Pss` from `/proc/<pid>/smaps_rollup`, on macOS keep RSS labelled "may overcount shared memory" and, without an explicit `mem=`, a group over the default budget is a finding, not a stop — verify: selftest `fullrun-mem-shared-fork`
- [ ] T09 Machine memory during a command: the lowest available memory (`MemAvailable`, `vm_stat` free+inactive) in the report, a finding under 10% of RAM — memory outside the group (a Postgres service) becomes visible; the Linux code paths run once in a container if Docker is available, otherwise the report says "checked on macOS only" — verify: selftest `fullrun-machine-low-memory` (threshold overridden)

## Log
- 2026-10-05 T00: baseline: selftest 363, failed 0.
- 2026-10-05 T01: engine.run опрашивает ps -A -o pgid=,rss= каждые 0,5 с и суммирует RSS группы процессов команды; пик в МиБ — 4-я колонка tsv и столбец «peak memory (sampled)» в отчёте. Проверка fullrun-peak-mem (bytearray 160 МиБ → 174 МиБ) красная до правки. По ходу 27 проверок упали из-за разбора tsv на 3 колонки в сравнении с прошлым прогоном — исправлено. selftest 364/0.
- 2026-10-05 T02: mem= (K/M/G) и по умолчанию 75% физической RAM (sysctl hw.memsize / MemTotal, FULLRUN_RAM_BYTES для тестов): пик выше — группа процессов остановлена, статус mem, находка с пиком; check.py: mem держит веху. Ограничение написано в T01 до тестов; красный эталон — движок из коммита T00 (21c40d1): mem=60M при 160 МиБ → pass; test_milestone_mem_holds красный до правки check.py. Проверки: mem-budget (снят за 1 s), mem-default. selftest 368/0.
- 2026-10-05 T03: leftover=: команда-счётчик до и после команды; рост — находка «leaves N resource(s) behind (before → after)» с советом про уборщик ресурсов с pid в имени; не число — находка; статус не красный. 3 проверки leftover красные до правки; проверку «уборка не названа» дважды сужал — она цеплялась за строку команды в таблице и за census SKIP. selftest 372, failed 0.
- 2026-10-05 T04: шаблон AGENTS.md (Validation): тесты с внешним ресурсом — общий мир для читающих тестов через read-only соединение (PostgreSQL default_transaction_read_only / роль с SELECT), тест равенства быстрого построителя мира и сервисного слоя в полном ярусе + по тесту на сущность через сервисы, уборщик ресурсов с pid в имени + leftover=, распределение по воркерам с ресурсом на модуль (xdist loadfile/loadscope), сначала меньше обращений, число воркеров — из замера памяти. PROJECT.md §6: mem= и leftover= в описании атрибутов и в примере (разбирается без неизвестных ключей, кавычки leftover проверены), строки проб «isolation between parallel workers» и «calls … per test». AGENTS.md 960 слов (лимит 1500). HUMAN pending: эти тексты. selftest 372, failed 0.
- 2026-10-05 T05: skills/test-audit: раздел «Tests that use an external stateful resource» — проба изоляции воркеров, обращения на тест из объявленной команды, доля построения мира и тест равенства, число воркеров = (RAM×0,75 − память ресурса) / пик на воркер, режим распределения xdist при ресурсе на модуль, остатки leftover; test-auditor читает новые пробы и пик памяти. Заготовка расширена (131 обращение у test_add, проба изоляции падает на общем state.txt): PASS за 162 s. Различающего красного нет — прежний навык тоже прошёл расширенную заготовку: агент сам запустил объявленные в §6 пробы; кейс оставлен как регрессия. selftest без изменений.
- 2026-10-05 T06: README/HARNESS: mem=, leftover=, линза ресурсов в /test-audit. Финиш: selftest 372/0; против T00 (21c40d1, имена без временных путей) ни одна проверка не потеряна (267 → 372); agenttest test-audit PASS (T05); пробная установка 387/0, установленный cc-fullrun находит движок, ~/bin не тронут.
- 2026-10-05 T07: leftover= у команды с частями: счёт вокруг первой части (идёт одна) и вокруг всего размножения (до первой параллельной части, после последней), находка — на команду с пометкой [shards 2–N], а не на отдельную часть. Проверка fullrun-leftover-parallel-leak красная до правки: «утечку» приписывало части 2 вместо 3; no-false-finding был зелёным по удаче расписания. selftest 374/0.
