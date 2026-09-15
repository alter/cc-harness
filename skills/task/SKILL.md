---
name: task
description: Create or extend the project's task tree in the owner's format — tasks/<phase>/<NN>-<slug>/ with task.txt (TASK/GOAL/CONTEXT/SCOPE/OUTCOME/VERIFY/ROLE/DEPENDS) and labels.txt, validated by tasks/check.py. Use whenever new work is added to a project, before any /plan or code.
argument-hint: <phase or new-phase> <what the task produces> | init
---

# /task

The task tree is the project's ledger of work. One directory per task, two required files, a validator. The format is fixed; the vocabulary (phases, roles, milestones) belongs to each project and lives in `tasks/README.md`.

## 0. Read the project's own rules first

- `tasks/README.md` — format, label vocabulary, language of the tree. Follow it over this skill wherever they differ.
- `tasks/PROTOCOL.md` if present — how work is taken and closed.
- `tasks/GOAL.md` — which gates exist; a new task must say which gate it serves or that it serves none.
- `tasks/DECISIONS.md` — a task must not re-open a recorded decision; cite `D<n>` when it relies on one.
- `tasks/check.py` — the validator. If any of these is missing, run `/task init` (section 4).

Language: the tree's language is whatever `tasks/README.md` is written in. Russian trees forbid transliterated jargon (деплой, бэкенд, лог, скрипт, флаг, нода): use Russian words, keep established terms in Latin script (`commit`, `repository`, `Dockerfile`).

## 1. Placement and numbering

- Phase directory: `NN-<slug>` with two-digit prefix in steps of 10 (`05-devenv`, `10-verification`). New phase: pick the number that puts it in dependency order, not at the end.
- Task directory: `NN-<slug>` inside the phase, two-digit, sequential; next free number, never renumber existing ones.
- Each phase has its own `task.txt` + `labels.txt` describing the phase as a whole: its SCOPE lists the child tasks with one line each.
- Slug: 2–4 words, lowercase, hyphens, names the artefact (`vm-lifecycle`, `run-ledger`), not the activity (`do-testing`).

## 2. Interview (all at once, before writing)

Everything derivable from the repo, `GOAL.md`, `DECISIONS.md` is derived, not asked. Ask through AskUserQuestion, one batch, only what remains:
- what artefact exists when this is done (OUTCOME) and where it lives — file path, number, recorded run, signed build;
- what is explicitly out (the `−` lines) and which task owns each excluded piece;
- which role does it; whether any part needs a human (then that part is its own `role:HUMAN` task, or a numbered VERIFY item marked HUMAN);
- priority and milestone if not obvious from the phase;
- hard dependencies.

## 3. Write the files

### `task.txt` — sections in exactly this order, two-space indented bodies

```
TASK: <short name, names the artefact>

GOAL
  What this produces and why it exists. Two or three lines. If it serves a
  gate, say which. Where a number appears, it carries its source
  (path:line, command, log line).

CONTEXT
  3–7 paths to read FOR THIS TASK — knowledge/, code, plan/, DECISIONS D<n>.
  Line numbers where they help. Never "read everything".

SCOPE
  + what is included, one line per item
  − what is deliberately excluded, and which task or document owns it instead

OUTCOME
  The artefact that exists when this is done, by path or by measurable value.
  Not "code written". Not "tests green".

VERIFY (<ROLE>)
  1. Numbered checks a different context can run or observe.
  2. At least one reverse-control item: the change that must turn the check
     red ("обратный контроль" / "reverse control"). A check that was never
     red proves nothing.
  N. Items only a person can judge are marked HUMAN in the item text.

ROLE
  Roles from tasks/README.md, comma-separated. HUMAN when a person must act.

DEPENDS
  Paths of tasks that must finish first, or (нет) / (none).
```

Rules the validator enforces and you must satisfy before running it:
- all eight sections present, in order; SCOPE has at least one `−` line (the character U+2212, not a hyphen);
- DEPENDS text and `depends:` label agree; a dependency points at an existing directory and never at a later milestone;
- `gate:yes` only on the gate tasks named in `GOAL.md`.

### `labels.txt` — one `key:value` per line, values from `tasks/README.md`

```
phase:<phase>
role:<ROLE>
type:feature|fix|research|decision|chore
priority:P0|P1|P2|P3
status:todo
verify:pending
depends:<path>          (only if there is one)
milestone:<M?>
gate:yes                (only on gate tasks)
```

New tasks start `status:todo`, `verify:pending`. Never set `verify:passed` here — that is `/verify`, in another context.

### Optional neighbours, created only when they have content

- `NOTES.md` — rationale, measurements, rejected alternatives, dated headings (`# NOTES — <what> (<YYYY-MM-DD>)`). Every number carries a source.
- `VERIFY.md` — written only by `/verify`.
- `BLOCKED.md` — written only by `/run` when stopping (format in PROTOCOL §6 / README).
- Artefacts: logs, screenshots, measurement output, `qa/`, `shots/`.

## 4. `/task init` — a new tree

When `tasks/` does not exist: copy `~/.claude/project-template/tasks/` into the project, then interview for `GOAL.md` (the goal in one promise; the gates — usually three — that measure it; signs of progress; signs of self-deception; the stop condition), `ROLES.md` (roles, what each owns and writes to, the HUMAN role and where a person must judge), and the label vocabulary in `README.md` + the constants at the top of `check.py`. `DECISIONS.md` starts empty with the entry format. Do not invent phases before the first real task.

## 5. Finish

Run `python3 tasks/check.py` from the repository root; zero problems or the task is not created. Print the new path(s) and the next step: `/plan <task dir>` when the work is to be executed now.
