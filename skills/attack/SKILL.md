---
name: attack
description: Authorized security review of the project's own code by attack — a task, a diff or a milestone against OWASP Top 10, OWASP LLM Top 10 and ASVS plus a mandatory minimum (XSS including push and deep links, CSRF, SQL injection including blind, attacker-controlled slow queries, prompt injection). Every finding is reproduced; ATTACK.md and attack:passed|failed. Use after a task that adds an input or a sink, at a milestone, or on request.
argument-hint: <task dir | diff | milestone | project> [owasp-top10|owasp-llm|asvs|all]
---

# /attack

`$ARGUMENTS`: a scope and an optional catalog. The catalog defaults to `all`; naming one narrows the review, it never removes the mandatory minimum in `catalogs.md`.

| Scope | What is attacked |
|---|---|
| `tasks/<phase>/<NN>-<slug>` | the task's DATA and SECURITY blocks and the diff of its commits |
| `diff` | `git diff` against the base the plan started from (`T00`), or against `HEAD~1` |
| `milestone` | every task of the current milestone, at night (`cc-night`) or at its end |
| `project` | the whole repository; by request only — it is expensive |

Delegate the whole job to the `attacker` subagent (fresh context, Opus) with the scope and the catalog. This session wrote the code; it does not judge its own security.

## What the attacker does

1. **Map sources to sinks.** Every input in scope and its DATA record; every place the value reaches today. The decision taken at the input (`interpretable=no` and validated, or `interpretable=yes` and stored as is) is the hypothesis to break: an `interpretable=no` field is attacked at its validation, an `interpretable=yes` field at every sink.
2. **Attack the mandatory minimum on every pair**, then the chosen catalogs. `catalogs.md` lists ids, titles and links; the attacker cites the id, never paraphrases a category from memory.
3. **Reproduce in a scratch copy** with inert probes (`<i>probe-7f3</i>`, `javascript:probe7f3()`, a prompt that asks for `PROBE-7F3`): a unit test or a call that shows the probe reaching the sink unescaped. A probe proves the interpretation as well as a working exploit and is never one. CONFIRMED only with the reproduction; the rest is PLAUSIBLE.
4. **Write `ATTACK.md`** next to the task (or next to the plan for `diff`/`milestone`):

```
Attacker: <context>, <date>; catalogs: <list>; did not write the code under review.

## Sources and sinks
| field | interpretable | sinks reached |

## Findings
<each in the attacker's format>

## Mandatory minimum
| attack | pairs tried | result |

## What was not attacked
<never empty: environments not available, sinks outside the repository, catalogs not chosen>

## Verdict
attack:passed or attack:failed for <scope>, one sentence why.
```

5. **Set `attack:`** in the task's `labels.txt` (`pending` → `passed` or `failed`). Nothing else in the repository changes.

## What happens to the findings

The same loop as the reviewer's (`/run`, "Review loop"): a CONFIRMED finding with a FIX line becomes a fix task whose verify is the reproduction; a FIX that contradicts a `D<n>` decision is recorded under `## Assumptions` and, when the weakness is real, blocks the task for the owner. PLAUSIBLE goes to `NOTES.md`. After the fixes, `/attack` runs again on the same scope, at most twice.

## When it runs

- After a task whose SECURITY block adds a sink or whose DATA adds an `interpretable=yes` field.
- At night on `milestone` scope, after the full run.
- On request, any scope.
