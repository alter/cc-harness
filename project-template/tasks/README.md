# Task tree — <project>

One task is one directory with two required files and a validator. The tree is a
ledger of work, not a journal: it holds what must exist, split into executable
pieces.

## Key documents

- `PROTOCOL.md` — read first by every executor: what to check before an edit,
  how to work, reverse control, when a task is closed, when to stop.
- `GOAL.md` — the goal, the gates, signs of progress and signs of self-deception.
- `ROLES.md` — the roles, what each owns and where it writes; the HUMAN role.
- `DECISIONS.md` — cross-cutting decisions `D<n>`: decided / why / rejected.

## Phases

`NN-<slug>` in steps of 10, in dependency order. Every phase carries its own
`task.txt` and `labels.txt`; the phase's SCOPE lists its child tasks, one line
each.

<filled in by /task init>

## Task format

`task.txt`, sections in exactly this order, bodies indented by two spaces:

```
TASK: <short name, names the artefact>

GOAL
  What this produces and why it exists. Two or three lines. If it serves a gate,
  say which. Every number carries its source.

CONTEXT
  3–7 paths to read FOR THIS TASK. Never "read everything".

SCOPE
  + what is included
  − what is deliberately excluded, and where it lives instead

OUTCOME
  The artefact that exists when the task is closed: a path or a measurable number.

VERIFY (<role>)
  Numbered checks somebody else can run. At least one of them is reverse
  control: what must turn the check red.

ROLE
  Who does it.

DEPENDS
  Paths of tasks that must finish first, or (none).
```

`labels.txt` — one `key:value` pair per line.

Optional neighbours: `NOTES.md` (rationale, measurements, rejected alternatives;
dated headings), `VERIFY.md` (proof of verification — written only by the
verifier), `BLOCKED.md` (when `status:blocked`), `PLAN.md` (the current session's
execution plan, created by `/plan`) and any artefact — logs, screenshots,
measurement output.

The `−` lines in SCOPE matter as much as the `+` lines. An unwritten boundary is
a boundary somebody will cross.

## Labels

```
phase:      <from the phase list above>
role:       <from ROLES.md>
type:       feature | fix | research | decision | chore
priority:   P0 | P1 | P2 | P3
status:     todo | in_progress | review | done | blocked (with BLOCKED.md next to it)
verify:     pending | passed | failed
depends:    <path to a task>
milestone:  <from GOAL.md>
gate:       yes — only on tasks that measure the goal
```

## Order of work

1. The executing role works (`status: todo → in_progress → done`).
2. **Another context**, which wrote neither the code nor its tests, sets
   `verify: passed` or `failed` (`/verify`).
3. Tasks with `gate:yes` are confirmed by a human; the next phase does not start
   until they pass.

## The `status:done` rule

`status:done` means **the OUTCOME artefact exists** at the named path, not that
"the work looks finished". An artefact outside the repository (a machine at a
provider, a phone in someone's hand, a signed build, another person's eyes) is
not closed by the context that did the work: it stays `in_progress` with a note
in `NOTES.md` saying what is missing and who can provide it.

## The `verify:passed` rule

Requires a `VERIFY.md` in the task directory. Words in a commit message are not
proof. Required parts:

- a `Verifier:` line naming the context and listing what it did **not** do — it
  authored neither the code nor its tests;
- `## How to reproduce` — at least one command from a clean state: a fresh
  checkout, an empty environment, not a single variable exported by hand;
- `## Reverse control` — what was broken on purpose and what red output it gave;
- `## What was not checked` — non-empty. A verification boundary always exists.

Every number in `VERIFY.md` carries its source — a path, a command, a log line.

## The stopping rule

The executor stops and **does not simulate** when a missing secret is needed; an
owner's decision is needed; a task in DEPENDS is not closed; the artefact
requires a person; or reverse control cannot be made red. A `BLOCKED.md` is
created in the task directory:

```
Blocked: <date>
Missing: <one line, concrete — a variable name, a task path, a question>
Done before stopping: <list, with paths>
What can be done without it: <or "nothing">
```

and `labels.txt` gets `status:blocked`. A stub instead of a secret, "hardcode it
for now", "let us assume that…" — that is not a way around a blocker, it is a
false `done` with delayed discovery.

## Validator

```bash
python3 tasks/check.py     # zero problems is a precondition for closing a task
```

## Language

The tree's language is whatever this file is written in; `check.py` accepts the
`VERIFY.md` and `BLOCKED.md` markers in English or Russian, so a tree kept in
another language keeps its own wording. Code, docstrings and commit messages
follow the existing code.
