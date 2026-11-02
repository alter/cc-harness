# Обвязка против Claude Code 2.1.316 (было: 2.1.272 / 2.1.289)

Дата: 2026-11-01. Статус: аудит, ничего не изменено.

Источники:
- `CHANGELOG.md` из `anthropics/claude-code`, версии 2.1.273–2.1.316, прочитан полностью;
- строки бинарника `~/.local/share/claude/versions/2.1.316` и сравнение их с 2.1.312;
- один отладочный прогон `claude --debug -p` на 2.1.316;
- код обвязки.

Метки доказательности:
- **[binary]** — строка или код найдены в бинарнике 2.1.316;
- **[code f:l]** — место в обвязке;
- **[changelog X]** — только запись в CHANGELOG;
- **[debug]** — отладочный прогон;
- **[не проверено → тест]** — нужен живой тест.

Не покрыто: версий 2.1.297 и 2.1.298 нет ни в CHANGELOG, ни на диске. Версии 2.1.313 и 2.1.315 покрыты только сравнением имён `CLAUDE_CODE_*` между бинарниками 2.1.312 и 2.1.316: ни одна не удалена, добавлено 21.

---

## 1. Изменить: важное

| # | Что | Почему | Доказательство | Серьёзность |
|---|-----|--------|----------------|-------------|
| 1 | Скилл `verify` обвязки конфликтует со встроенным `verify` | В 2.1.316 есть встроенный скилл: «Run before committing nontrivial changes; bootstraps this repo's project verify skill if none exists yet». Запись 2.1.286: «a project/user skill named `verify` is now run right before committing». Риски: (а) модель запустит `/verify` обвязки на собственной работе перед коммитом, что нарушает контракт «verify:passed — только независимый контекст, запускает пользователь»; (б) встроенный скилл может создать `.claude/skills/verify/` в проектах пользователя, что вне ledger и может попасть в коммит. Подавляет ли это `disable-model-invocation: true`, неизвестно | [binary] текст встроенного скилла; [changelog 2.1.286]; [code skills/verify/SKILL.md:1-6]; [не проверено → тест T01 ниже] | высокая |
| 2 | `git-guard` и `bash-read-guard` пропускают команды Monitor | С 2.1.314 хуки с матчером Bash срабатывают и на shell-команды инструмента Monitor (могут deny/ask, но не rewrite). Оба guard-а выходят молча при `tool_name != "Bash"`, поэтому `git stash`, `git reset --hard` и `cat .env` через Monitor проходят мимо. Исправление: принимать `{"Bash","Monitor"}` и добавить в selftest кейс с `tool_name=Monitor`. `compress-output` трогать не нужно: rewrite для Monitor запрещён | [code hooks/git-guard.py:141, hooks/bash-read-guard.py:146]; [changelog 2.1.314]; точное значение `tool_name` в payload [не проверено], но исправление верно при любом значении | высокая |
| 3 | `onFailure: "block"` для PreToolUse-guard-ов | С 2.1.295 упавший, зависший или не стартовавший хук может блокировать действие, а не пропускать его. Сейчас guard-ы fail-open: если нет `python3`, хук упал или вышел таймаут 10 с, команда проходит. Пример такого падения — коммит `a00d18c`. Ставить только на `git-guard.py`, `bash-read-guard.py`, `read-guard.sh`, `guard-subagent.sh`. **Не** ставить на Stop, SubagentStop и SessionStart: упавший хук там не даст сессии остановиться или стартовать | [changelog 2.1.295]; [code settings.json:67-98] | средняя |
| 4 | `guard-subagent` не ограничивает `effort` | С 2.1.292 у Agent есть параметр `effort`. Хук срезает только `model`, выше заданного у агента, поэтому `effort: max` для `test-runner` (effort low) пройдёт. Нужно добавить такой же кап по рангу `low<medium<high<xhigh<max` против `effort:` из frontmatter или `CLAUDE_CODE_SUBAGENT_EFFORT`. С 2.1.300 `updatedInput` валидируется (неизвестные ключи отбрасываются, невалидный ввод означает deny). Удаление ключа валидно, текущая логика с `model` под это попадает | [changelog 2.1.292, 2.1.300]; [code hooks/guard-subagent.sh:29-52] | средняя |
| 5 | Агенты Workflow обходят `guard-subagent` | Workflow запускает агентов не через Agent/Task, поэтому матчер `Agent\|Task` их не видит: ни бюджета, ни капа модели. Нужно добавить `CLAUDE_CODE_WORKFLOW_SUBAGENT_MODEL=sonnet` (2.1.296). От размера защищает `workflowSizeGuideline: small`, но это лишь подсказка, а не лимит | [changelog 2.1.296]; [binary] переменная есть; [code settings.json:67] | средняя |

## 2. Изменить: мелкое

| # | Что | Почему | Доказательство |
|---|-----|--------|----------------|
| 6 | `modelSettings."claude-opus-5".maxEffortLevel` | `claude-opus-5` (Opus 5) и `claude-opus-5-5` (Opus 5.5) — разные id, а с 2.1.280 `opus` означает Opus 5.5. Ключ, скорее всего, не действует на текущую модель. Ограничение всё равно держит верхнеуровневый `maxEffortLevel: "high"`. Либо убрать, либо переименовать в `claude-opus-5-5`. Каноникализацию ключа (`mU()`) до конца не разобрал | [binary] оба id встречаются; [changelog 2.1.280] |
| 7 | Добавить `CLAUDE_CODE_SUBAGENT_EFFORT` | Новая переменная 2.1.316: effort субагентов, если он нигде не задан. Покроет агентов без `effort:` (`Explore`, `scout`) и встроенных. Значение решить: `medium` или `low` | [changelog 2.1.316]; [binary] |

## 3. Убрать

Список короткий: ни один ключ и ни одна переменная, которые использует обвязка, из 2.1.316 не удалены. TaskOutput удалён в 2.1.277, но обвязка его не использует.

| # | Что | Почему |
|---|-----|--------|
| 8 | `modelSettings."claude-opus-5"`, если не переименовывать (см. п. 6) | дублирует верхнеуровневый `maxEffortLevel` |
| 9 | `includeCoAuthoredBy: false` (опционально) | при заданном `attribution.commit` бинарник смотрит на него, а не на `includeCoAuthoredBy` (`bp()`: `commit===""` значит `disabled`). Ключ безвреден, удалять необязательно. **Не** заменять весь блок на `"attribution": false` (2.1.281): `sessionUrl` обрабатывается отдельной веткой, текущая форма проверена [binary] |

## 4. Добавить: нужно решение владельца

| # | Что | За | Против / проверить |
|---|-----|----|--------------------|
| 10 | `permissions.blockWritesOutsideWorkingDirectories: true` (2.1.314) | действует «in every permission mode», включая ночные прогоны с `--dangerously-skip-permissions` | verifier и attacker пишут scratch-копии, `install.sh` пишет в `~/.claude` и `~/bin`. Проверить, где лежат scratch-копии, иначе ночной прогон сломается |
| 11 | `idleCompaction` (2.1.299: при простое около 54 мин и контексте 200K+ компактит до истечения кэша) | дешевле, чем холодный кэш через час | компакция без хэндоффа catnap. Проверить, что после неё срабатывает `SessionStart` с `source=compact` и `session-start.sh` возвращает план. Если нет, ставить `"idleCompaction": false` |
| 12 | `autoCompactWindow` во frontmatter `worker` и `verifier` (2.1.296) | длинные агенты (`maxTurns` 240–250) могут упереться в окно | без замеров не нужно; низкий приоритет |

## 5. Документация: устарело или неверно

| Где | Было | Стало |
|-----|------|-------|
| README.md:4, HARNESS.md:3, HARNESS.md:244, INSTALL.md:5 | «verified against 2.1.272», «checked on 2.1.289» | 2.1.316, после тестов из раздела 7 |
| README.md:188, HARNESS.md:110 | «prompt/agent hooks only for tool events, no prompt hook on Stop» | неверно: prompt-хуки на Stop/SubagentStop есть, их чинили в 2.1.274 и 2.1.294 [changelog]. Переделывать `stop-guard` не нужно, только текст |
| HARNESS.md:80 | WebSearch: «default 200» | с 2.1.290 интерактивный бюджет пополняется на 100 запросов в час (`CLAUDE_CODE_WEB_SEARCH_REFILLS_PER_HOUR`), а не заканчивается на 200. `CLAUDE_CODE_MAX_WEB_SEARCHES_PER_SESSION` по-прежнему читается [binary]; как значение 300 сочетается с пополнением, описать после проверки |
| HARNESS.md:244 | после обновления: `/skill-doctor`, `/hooks` | добавить `/doctor prompt-audit` (2.1.283): аудит CLAUDE.md, скиллов и агентов на устаревшие паттерны |
| HARNESS.md:133, :221 | Explore наследует модель сессии с 2.1.198 | дополнить: с 2.1.284 при неизвестном id тоже наследует, а не переключается на Opus. Переопределение `agents/Explore.md` на haiku остаётся нужным |
| README.md:46 и описания моделей | `sonnet`, `opus`, `haiku` без версий | теперь это Sonnet 5.5 (2.1.284), Opus 5.5 (2.1.280) и Haiku 5.5 (2.1.293), у всех 1M контекста. Суффикс `[1m]` оставить: в 2.1.311 описаны сессии со стандартным контекстом 200K. Цены и замеры README:54 сделаны на старых моделях |
| BEHAVIOR.md / night.sh | — | с 2.1.302 fork-субагенты по умолчанию включены в `-p`, а ночные `test-audit`, `pgsql` и `attack` идут через `-p`. Форки считаются бюджетом `guard-subagent` и не проходят через кап модели (`atype=fork`). Записать это |

## 6. Проверено, менять не нужно

- Все ключи `settings.json` и все `CLAUDE_CODE_*` из `env` присутствуют в 2.1.316 и подключены к коду. Отладочный прогон не выдал ни одного предупреждения о неизвестных ключах [binary, debug].
- `compress-output.sh`: с 2.1.316 `updatedToolOutput` проверяется на форму вывода. Хук проходит: «Hook PostToolUse (compress-output.sh) replaced tool output», ошибки формы нет [debug].
- `commitTrailers` (новый подключ attribution): при `attribution.commit: ""` трейлеры выключены, утечки нет [binary `bp()`].
- Значения по умолчанию, записанные в HARNESS.md: `STOP_HOOK_BLOCK_CAP ?? 8` верно; флаг `tengu_sage_compass2` для advisor и строки `[AdvisorTool]`, которые грепает `advisor-check.sh`, на месте [binary].
- Ограничение вывода хука в 10 000 символов (2.1.314, про PreCompact): `session-start.sh` отдаёт три строки плана, риска нет.
- Изменения в MCP allow-правилах (2.1.299): у обвязки MCP allow-правил нет, а у `scout` инструменты graphify перечислены полными именами.
- SubagentStop срабатывал примерно дважды в минуту на каждый живой субагент; исправлено в 2.1.311. `subagent-evidence.sh` защищён через `stop_hook_active`, менять ничего не нужно.
- `--append-system-prompt-file` в `agenttest.sh` уже в той форме, которую требует 2.1.281.

## 7. Тесты, которыми должен начаться план

- **T01 (решает п. 1).** Пробный `CLAUDE_CONFIG_DIR` с установленной обвязкой и scratch-репозиторий. Правка продуктового кода, затем `claude -p "commit this"`. Смотреть: (а) был ли в транскрипте вызов `Skill` с `verify` и чей это скилл; (б) появился ли в репозитории `.claude/skills/verify/`.
  - Если вызов был: переименовать скилл обвязки (например, в `verify-task`). Что затронет переименование: `skills/verify/`, `/verify` в обоих CLAUDE.md (`~/.claude` и в репозитории), BEHAVIOR.md, HARNESS.md, `agents/verifier.md`, шаблоны `tasks/`, `project-template/`, selftest. Метка `verify:passed` может остаться.
  - Если встроенный скилл создаёт файлы в репозитории: нужно правило против этого (deny на запись в `.claude/skills/verify/**` или строка в CLAUDE.md).
- **T02 (п. 2).** Payload Monitor-команды: какой `tool_name` приходит в PreToolUse и закрывает ли deny-правило `Bash(git stash:*)` тот же `git stash` через Monitor.
- **T03 (п. 11).** Срабатывает ли после idle compaction `SessionStart` с `source=compact`.

Следующий шаг: `/plan` по пунктам 1–7 и 10–11 с T01–T03 в начале плана.
