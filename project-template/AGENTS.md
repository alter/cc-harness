# AGENTS.md

Shared instructions for every coding agent in this repository. `CLAUDE.md` imports this file (`@AGENTS.md`); do not duplicate rules there. The personal working contract in `~/.claude/CLAUDE.md` still applies on top.

## Source of truth

- `docs/PROJECT.md` owns scope, the capability ledger, decisions the agent makes alone, the unattended policy and the gate checks. Read it first. A capability with no ledger row is `absent`; dormant code or an old doc is not a requirement.
- `docs/plans/<slug>.md` owns the current task list. Work from it; update it; never delete tasks.
- Runbooks in `docs/` own setup and operations. Verify against code, scripts and runtime output rather than trusting a stale doc; update the doc when behavior, contracts, setup or operations change.

## Engineering

- Fix the owning cause, not a symptom in a caller. A cross-layer bug may have a one-file fix; verify affected callers.
- Smallest coherent change with clear ownership. Small duplication beats the wrong shared abstraction. Remove workarounds when their cause is fixed.
- Match investigation to the change: contracts need producer, consumer, serializer and read/write checks; auth and routing need enforcement, guards and state; async work needs retries, idempotency, ordering, cancellation and failure visibility.
- Architecture rules live in checks, not prose: put layering and import boundaries into a script that exits non-zero (`import-linter` for Python) and list it under gate checks.
- Reproducible bug → failing regression test first, then the fix, then the original reproduction again.

## Validation

- A check passes only when the behavior is correct and the command exits 0. Report failed or unavailable checks plainly; a task with broken primary behavior is not done.
- Run the baseline once before the first edit to separate pre-existing failures from new ones; record it in the plan's `## Log`.
- Narrowest stable check per change; the full gate list before a task is marked `[x]`; broad regression only for cross-cutting changes or release.
- End-to-end tests only for the minimal product-critical path; assert outcomes (persisted data, navigation), never wording or layout.

## Git and workspace

- Inspect `git status --short --branch` and `git remote -v` before any git operation. Work on the branch the plan names; never switch mid-run. Stage by path, never `git add -A` (submodule pointers, marker files).
- Never `git stash`, `reset --hard`, `clean`, or `checkout -- .` to make progress. If uncommitted user changes block you, stop that task with `[!] BLOCKED` and continue with others.
- Commit per finished task when `docs/PROJECT.md` says so; message `T##: <what changed>`. Never push unless asked.
- Scratch goes to `.claude/scratch/`, never the repo root. Remove your own scratch when done.
- Never stop or kill processes to free a port; use another port.
- Secrets, tokens, cookies, customer data and raw `.env` values never appear in logs, tests, fixtures or replies. Never weaken auth, validation, rate limits or auditability to pass a check.
- Generated files change through their generator (schema → migration), never by hand.

## Reporting

- What changed, why, which checks ran with their results, remaining risk or blocked items, suggested commit message. No headings for their own sake, no restating the task.
