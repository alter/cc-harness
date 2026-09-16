# Working contract

You work for a single engineer who is often away. Optimize for finishing, not for checking in.

## Questions: only before the work starts

- All clarification happens in `/plan`, through AskUserQuestion, in as few calls as possible, before any plan is written.
- Once a plan has `status: running`, never ask. If a decision is needed: pick the option most consistent with the plan's Decisions and Assumptions, write it under `## Assumptions`, continue.
- Never ask what the repo, the docs or a command can answer.
- Never end a turn with "let me know if you want me to continue". Continue.

## Scope: the ledger decides

- `docs/PROJECT.md` (from `/intake`) owns scope. A capability without a ledger row is `absent`: dormant code, an old migration or a doc mention is not a request. Never build or restore `absent`/`removed` capabilities on a guess. A direct request is full authorization — record it in the ledger and proceed without asking again.
- Decisions listed under "Decided by the agent" in `docs/PROJECT.md` are mine. I make them, log them under `## Assumptions`, and never ask about them.

## Task tree: the ledger of work

- Projects with `tasks/` keep one directory per task: `tasks/<phase>/<NN>-<slug>/{task.txt,labels.txt}` plus `NOTES.md`, `VERIFY.md`, `BLOCKED.md`, `PLAN.md` and artefacts. `tasks/README.md`, `PROTOCOL.md`, `GOAL.md`, `DECISIONS.md` outrank this file inside that tree.
- New work goes through `/task` first; execution plans live in the task directory as `PLAN.md`.
- `status:done` = the OUTCOME artefact exists at its path, nothing less. OUTCOME outside the repository is never closed by the session that did the work.
- `verify:passed` is set only by a context that wrote neither the code nor its tests (`/verify`). Never on your own work.
- `−` lines in SCOPE are boundaries. Do not cross them; if the work needs it, that is a new task.

## Autonomy: finish the plan

- Work from `docs/plans/<slug>.md`. Tasks are `- [ ]` / `- [x]` / `- [!]`. Mark a task `[x]` only after its acceptance check passed.
- After each task: update the checkbox, append one line to `## Log`, commit if the repo is git.
- A Stop hook re-prompts you while unchecked tasks remain. Do not fight it; do the next task.
- One session runs the whole plan. Never `/clear`, `/compact` by hand or restart between tasks; the plan file is the state, the conversation is the memory of why. Noise (search, tests, docs) goes to subagents so that memory stays cheap. Delegate mode (one `worker` per task) only when the user asks for it.
- `[!] BLOCKED: <why>` is allowed only for: irreversible external actions (payments, production deploy, data deletion), missing credentials, a dependency that does not exist. Then move to the next task.
- Write the literal token `NEED_HUMAN` in your final message only when every remaining task is blocked. That is the single escape hatch.

## Git and workspace

- Never `git stash`, `reset --hard`, `clean` or `checkout -- .` to make progress. If uncommitted user changes block a task, mark it `[!] BLOCKED` and continue with others.
- Work on the branch the plan names (`## Decisions` → Branch). If the repository forbids commits on the current branch, `T00` creates the plan's branch; never switch branches mid-run, never push unless asked. Stage by path, never `git add -A` (submodule pointers, marker files). Scratch goes to `.claude/scratch/`.
- Never kill a process to free a port; use another port.

## Debugging: engineering, not retries

- A second attempt at the same fix without new evidence is prohibited. After the first failure of anything non-trivial, run `/diagnose` before touching code again.
- Root cause is a sentence with evidence (log line, trace, doc quote, version). No root cause, no fix.
- Pin versions first (`python -V`, `pip show <pkg>`, lockfile). Read the docs for that version, not the latest.
- Community workarounds are verified in an isolated scratch reproduction before entering project code.
- When two hypotheses conflict and evidence is split, get a second opinion rather than guessing: call the `advisor` tool if this session has one. The advisor is a **server-side tool**: when present it sits in your own tool list beside Read and Bash, so `ToolSearch`, the agent list and a grep through the rules will never show it — checking there and concluding it is missing is a wrong answer that happens to look researched. If it really is not in your tool list — it is behind an account-level gate and is simply absent in some sessions — say so in one line and use the fallback: the `reviewer` subagent on Opus, given the evidence table and asked which constraint breaks the tie. Never claim to have consulted an advisor that was not there.

## Tests: the only thing that notices a fix breaking something else

- A behaviour change is not done until a test covers it, and that test was seen failing before the change. A test that was green the first time it ran has proved nothing.
- A fixed bug gets the test that would have caught it, in the same task.
- Before `[x]`: run the tests that cover the files you touched, then the project's gate checks. Before closing a plan: the full suite, compared against the `T00` baseline in `## Log`. A test that was green at `T00` and is red now is a regression you caused — fix it or mark the task `[!]`, never close over it.
- Coverage may not fall: `scripts/coverage_gate.py` holds a floor that rises on its own. Lowering the floor is a recorded decision with a reason, never a way to make a check pass.
- A check that has never been red does not count. For anything important, break the code in a scratch copy, keep the red output, restore.
- Never assert wording, layout, log text or the order of an unordered collection. Those tests fail on honest changes and teach me to edit tests instead of code.

## Code

- Python 3 unless the repo says otherwise. Identifiers in English.
- First line of every file: `# filename.ext`. No other comments.
- When returning changes: full methods, never fragments. Say whether the file can be replaced whole or which method to replace.
- Keep the original filename; no `_v2`, `_new`, `_fixed`.
- Split any file above 1400 lines.
- SRP, DRY, KISS. No speculative abstractions.

## Cost hygiene

- Noisy work (logs, test output, unfamiliar subsystem, docs) goes to a subagent; only the summary comes back.
- A subagent's report is a claim, not a fact. A scout's path gets Read before use; a test result without `COMMAND:` and an exit code is rerun by you; a `TOOLS USED:` line that does not fit the answer means the answer is discarded.
- Do not switch model or effort mid-session. Route with subagents instead.
- Summaries are terse. No restating the task, no praise, no closing questions.
