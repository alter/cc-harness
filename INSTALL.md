# Установка, проверка, откат

Порядок: резервная копия → проверка без установки → пробная установка в отдельный каталог → живая проверка на песочнице → установка в `~/.claude` → откат, если что-то не так. Каждый шаг — одна команда, каждый обратим.

Нужны: `jq`, `bash` ≥ 4, `claude` ≥ 2.1.267 (`maxEffortLevel`), на macOS — ничего больше (уведомления через `osascript`).

## 0. Что где лежит у Claude Code — чтобы знать, что копируем

| Путь | Что | Трогает ли харнес |
|---|---|---|
| `~/.claude/settings.json` | настройки, hook, statusLine | **да** — слияние, не замена |
| `~/.claude/CLAUDE.md` | глобальный контракт | **да** — замена |
| `~/.claude/hooks/`, `agents/`, `skills/`, `statusline.sh`, `project-template/` | наши файлы | **да** — добавление; чужие файлы в этих каталогах не удаляются |
| `~/.claude/settings.local.json`, `commands/`, `keybindings.json` | твоё | нет, но копируется в резерв |
| `~/.claude.json` | MCP-серверы, состояние входа, onboarding | **нет**; копируется в резерв |
| `~/.claude/projects/` | стенограммы сессий | нет; в резерв не входит (гигабайты) — см. §1 |
| `~/bin/cc-night` | ночной запуск | **да** |

## 1. Резервная копия

`install.sh` делает её сам перед любой записью (в `~/.claude-backup/<дата-время>/`: все файлы из таблицы плюс `MANIFEST.txt` со списком того, что было). Если хочешь полную копию вместе со стенограммами — до установки:

```bash
tar czf ~/claude-full-$(date +%Y%m%d).tgz -C ~ .claude .claude.json
du -sh ~/claude-full-*.tgz
```

Проверить, что копия читается: `tar tzf ~/claude-full-*.tgz | head`.

## 2. Проверка без установки — 48 проверок hook на синтетических данных

```bash
tar xzf harness.tar.gz && cd harness
chmod +x *.sh hooks/*.sh
./selftest.sh
```

Что проверяется (ничего не пишется вне временного каталога, состояние счётчиков изолировано через `XDG_STATE_HOME`):

- синтаксис всех скриптов, валидность `settings.json`;
- `read-guard`: отказ на файл в 600 строк, пропуск при `offset/limit`, пропуск `.md`;
- `compress-output`: 300 одинаковых строк → `(x300)`, длинный вывод → голова/хвост + файл в `.claude/scratch/`, короткий — нетронут;
- `retry-guard`: первый провал молча, второй (с другими пробелами — та же команда) → указание на `/diagnose`, третий → «ROOT CAUSE до следующего вызова», успех сбрасывает;
- `stop-guard`: план с 2 открытыми → `decision: block` с именем следующей задачи; `NEED_HUMAN`, `.claude/plan-pause`, достигнутый предел, ноль открытых → отпускает;
- `session-start` после сжатия → строка с «2 open, 1 blocked» и хвостом Log;
- `subagent-evidence`: scout без вызовов → блок; с Grep+Read и путём → пропуск; без пути → блок; `NOT FOUND` без вызовов → блок; test-runner без Bash или без `COMMAND:` → блок; worker без Edit/Write/Bash → блок; `NOT DONE` и `stop_hook_active` → пропуск;
- `guard-subagent` 1/2, 2/2 → allow, 3/2 → deny; `guard-model-switch` 50 тыс. → ask, 1 тыс. → allow;
- `statusline` на образце JSON → строка с каталогом, моделью, ctx, 5h, 7d, причиной холодного кэша и долей попаданий.

Последняя строка — `passed N, failed 0`. Иначе — не ставить, прислать вывод.

## 3. Пробная установка в отдельный каталог — не трогая `~/.claude`

Claude Code читает переменную `CLAUDE_CONFIG_DIR` (проверено в двоичном файле): вся конфигурация берётся из неё вместо `~/.claude`.

```bash
./install.sh ~/.claude-harness-test
./selftest.sh ~/.claude-harness-test        # те же проверки + «hook на месте и исполняемы»
CLAUDE_CONFIG_DIR=~/.claude-harness-test claude
```

`install.sh` с нестандартным каталогом переписывает все ссылки `~/.claude/...` в hook, agents, skills и `settings.json` на этот каталог. Первый запуск спросит тему и вход (на macOS ключ входа в Keychain общий, повторный вход обычно не нужен; на Linux скопируй `~/.claude/.credentials.json` в тестовый каталог). MCP-серверы из `~/.claude.json` в тестовой конфигурации не появятся — это ожидаемо.

Убрать тестовый каталог потом: `rm -rf ~/.claude-harness-test`.

## 4. Живая проверка на песочнице (20 минут, ~ниже одного часа лимита)

Отдельный пустой репозиторий, не рабочий проект:

```bash
mkdir -p /tmp/harness-sandbox && cd /tmp/harness-sandbox && git init -q
seq 1 800 | sed 's/^/line = /' > big.py
mkdir -p docs/plans && cat > docs/plans/smoke.md <<'EOF'
---
status: running
created: 2026-09-15
---
# Smoke
## Goal
Three files exist and the suite is green.
## Acceptance criteria
- [ ] AC1 `test -f a.txt && test -f b.txt && test -f c.txt`
## Decisions
- files contain their own name
## Assumptions
## Out of scope
- anything else
## Tasks
- [ ] T00 baseline: run `python3 -c "import big"` and record the result — verify: `true`
- [ ] T01 create a.txt with content "a" — verify: `grep -qx a a.txt`
- [ ] T02 create b.txt with content "b" — verify: `grep -qx b b.txt`
- [ ] T03 create c.txt with content "c" — verify: `grep -qx c c.txt`
- [ ] T04 run `false` and handle the failure by the /diagnose rules — verify: `true`
## Log
EOF
git add -A && git commit -qm init
CLAUDE_CONFIG_DIR=~/.claude-harness-test claude "/run docs/plans/smoke.md"
```

Что должен увидеть — и что означает, если не увидел:

| Наблюдение | Механизм | Если нет |
|---|---|---|
| Первым сообщением модель предлагает `/goal all tasks in docs/plans/smoke.md are [x] or [!]` и не ждёт ответа | skill `/run`, раздел Belt and braces | skill не загрузился: `ls $CLAUDE_CONFIG_DIR/skills/run/SKILL.md`, `/skill-doctor` |
| Строка состояния внизу: `harness-sandbox  Sonnet 5/medium  ctx N%  5h N%  7d N%  cache …` | `statusLine` | путь в `settings.json` → `statusLine.command`; запусти его руками с `echo '{}' \| ~/.claude/statusline.sh` |
| Ни одного вопроса за весь прогон | контракт + `/run` | если спросила — прислать стенограмму: это дефект контракта, не hook |
| Попробуй сам в сессии: «прочитай big.py целиком» → отказ с текстом про Grep и окно | `read-guard` | `claude --debug hooks` покажет, вызывался ли hook |
| После каждой задачи — `[x]`, строка в `## Log`, commit `T0N: …` (`git log --oneline`) | `run-task` | — |
| На T04 модель не повторяет `false`, а пишет `ROOT CAUSE:`/`EVIDENCE:` или блокирует | контракт; `retry-guard` включится только при втором одинаковом провале — это ожидаемо | если повторяет 3+ раз — прислать стенограмму |
| Попробуй прервать: скажи «остановись, продолжим завтра» при открытых задачах → модель возвращается к работе с текстом про N открытых задач | `stop-guard` | `tail ~/.local/state/cc-stop-guard/*` — счётчик растёт? если 0 — hook не вызван: проверь `settings.json` → `hooks.Stop` |
| По завершении — уведомление macOS «Plan finished» | `notify` из `stop-guard` | `osascript -e 'display notification "x"'` руками |
| `touch .claude/plan-pause` посреди работы → модель может остановиться | выход из `stop-guard` | — |

Дополнительно: `/usage` в сессии — должен показать долю `subagent_heavy`/`cache_miss` (ожидаемо низкую на пяти задачах), `/insights` — ничего лишнего.

Проверка subagent'ов отдельно, в той же сессии: «найди через scout, где определена переменная line» → ответ обязан содержать `big.py:<строка>` и `TOOLS USED: Grep:… Read:…`. Если scout вернул «не нашёл» без строки `TOOLS USED` — hook `subagent-evidence` должен был его вернуть в работу; `claude --debug hooks` покажет `SubagentStop`.

## 5. Установка в `~/.claude`

Когда §2–4 прошли:

```bash
./install.sh
```

Скрипт: резервная копия → копирование файлов → слияние `settings.json` → проверка синтаксиса → отчёт. Слияние: твои `permissions`, `env`, MCP, чужие hook остаются; наши ключи (`model`, `effortLevel`, кэш, пределы) **перекрывают** твои — diff печатается на экран, прочитай его. Наши hook добавляются к твоим по каждому событию, при повторной установке не дублируются. `~/.claude.json` не трогается.

Потом:

```bash
./selftest.sh ~/.claude
claude          # в любом проекте; строка состояния появится сразу
```

## 6. Откат

```bash
./uninstall.sh ~/.claude-backup/<дата-время>
```

Удаляет наши файлы (только те, что есть в этом архиве харнеса), возвращает `settings.json`, `CLAUDE.md`, `hooks/`, `agents/`, `skills/`, `commands/`, `keybindings.json`, `cc-night` из копии, сверяет с `MANIFEST.txt`. `~/.claude.json` не трогает (копия лежит рядом как `dot-claude.json`, если понадобится).

Откат из полной копии §1: `tar xzf ~/claude-full-<дата>.tgz -C ~` поверх.

## 7. Что может пойти не так — честно

- **Слияние `settings.json` перекроет твою модель/effort.** Так и задумано, но если у тебя стоял `opus` по умолчанию — теперь `sonnet`. Diff покажет.
- **Другой `Stop`-hook у тебя уже есть.** Оба будут вызваны; блок любого из них останавливает выход. Конфликта нет, но два разных текста в контексте. Посмотри `jq .hooks.Stop ~/.claude/settings.json`.
- **`--dangerously-skip-permissions` в `cc-night`.** Скрипт не проверяет, где ты его запускаешь. Песочница — твоя ответственность.
- **Проектный `CLAUDE.md` со своими правилами** останется как есть; харнес его не трогает. Если там противоречащее («спрашивай перед каждым шагом») — победит более конкретное, т. е. проектное. Приведи проектные файлы к `AGENTS.md` из `project-template/` через `/intake`.
- **Версия.** Ключи `maxEffortLevel`, `subagentPromptCacheTtl`, `omitClaudeMd` в agents требуют ≥ 2.1.267/2.1.271. На старой версии Claude Code молча их игнорирует — `claude --version` первым делом.
