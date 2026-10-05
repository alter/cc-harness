---
name: pgsql-slow-queries
description: Read-only check of PostgreSQL usage — transactions held open across API calls, file or network waits (red flag), and queries on columns without an index. A check, not a fix. Use from the review loop when a diff touches PostgreSQL code, in the night run, or on request.
argument-hint: [diff | <path> | project] [--live]
---

# /pgsql-slow-queries

A check, not active work. It reports; the developer, or the agent that knows this project, fixes. It never rewrites the project onto a preferred driver, ORM or style.

Scope from `$ARGUMENTS`: `diff` (default: the change since `T00`, or `HEAD~1`), a path, or `project` (the whole repository — the night run uses it). `--live` allows read-only queries against a database, and only against a non-production target as `docs/PROJECT.md` §5 defines it: `EXPLAIN` without `ANALYZE`, `pg_stat_activity`, `pg_stat_user_tables`, `pg_stat_statements` when installed, `SHOW` of the timeout settings. Without `--live` the check reads code, migrations and schema only.

Delegate to the `pg-checker` subagent (Sonnet, high effort, read-only) with the scope. It answers the two questions in its own instructions and cites `reference.md` for every reason.

## What happens to the report

- **CONFIRMED** findings become tasks for the implementer in the current plan (the review loop in `/run`): the DIRECTION line is the starting point, the WHERE line is the evidence, the regression test is the implementer's to write.
- **PLAUSIBLE** findings go to `NOTES.md`.
- A transaction held across an outside wait is BLOCK: the task that introduced it does not close until it is fixed or the owner records why it stays (`## Assumptions`, with the path).

## When it runs

- From the review loop, when the reviewed diff touches code that talks to PostgreSQL (a driver import, SQL, a migration, an ORM model).
- At night with scope `project`, after the full run.
- On request.

This is not a security review. A query that is slow for every input is a developer's mistake and belongs here; a query an outsider can make slow by choosing the input belongs to `/attack`. One spot can be both: two findings, two directions — "add the index" and "bound the input".
