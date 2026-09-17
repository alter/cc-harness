---
name: graphify
description: Build a local code graph for this repository and expose it to the session as an MCP tool, after checking the graph is worth trusting. Run once per repository; re-run only after a language or layout change.
argument-hint: <project directory, or empty for the current one>
---

# /graphify

A code graph answers two questions cheaply: *which definition is this symbol* and *who calls it*.
`grep` answers them by returning every prose mention of the same word. On a real repository the
graph costs tens of tokens where grep costs thousands.

It answers nothing else. "How does this flow work" is not a graph question — keyword seeding
picks the wrong entry points — and a graph is stale the moment code changes.

## 1. Build and judge, in one command

```bash
~/.claude/graph-setup.sh [project]
```

It refuses rather than guesses. Read its output, do not summarise it away:

- **submodules present** → refused. An umbrella repository resolves nearly every cross-repository
  edge wrongly. Say so and stop; suggest running it inside one component.
- **extraction failed / empty** → refused. The parser does not read these languages.
- **`UNFIT`** → built but not wired, with the numbers that decided it: node count, INFERRED share,
  share of code files that reached the graph. Report the numbers, not the verdict alone.
- **`FIT`** → `.mcp.json` gained a `graphify` server, `.gitignore` gained `graphify-out/`, and a
  git post-commit hook now rebuilds the graph after every commit.

Thresholds are `CC_GRAPH_MIN_NODES` (20), `CC_GRAPH_MAX_INFERRED` (25%), `CC_GRAPH_MIN_COVERAGE`
(30%). Loosen one only when the user asks and you can say what it would let through.

If `graphify` is not on `PATH`: `pip install graphifyy`. Do not install it without saying so.

## 2. The tools are not in this session

MCP servers start when the session starts. Nothing you just wired exists for you now. End the
turn by telling the user to restart `claude` — do not pretend to verify what you cannot call.

## 3. Verify on the next session, before trusting anything

One check, on a symbol whose location is already known:

```
mcp__graphify__get_node  label: "<symbol>"
```

Compare its `source_file` and `source_location` against `grep -n`. If they disagree, the graph is
stale or wrong: rebuild with `graphify update .` and say the graph is not to be trusted until it
agrees.

## 4. What the graph is allowed to claim

- An `EXTRACTED` edge came from the AST. An `INFERRED` edge is a guess, and the interesting-looking
  ones are usually the wrong ones. Pass one on only as a lead, labelled as a guess.
- The post-commit rebuild runs detached. For a few seconds after a commit the graph describes the
  previous commit. A graph answer that contradicts the file you just wrote is the graph being late.
- `graphify hook install` also wrote `.gitattributes` and registered a merge driver for a tracked
  `graph.json`. Here `graphify-out/` is ignored, so both are inert.

## 5. What this skill does not do

It does not run `graphify install`, `claude install` or `cursor install`. Those append to
`CLAUDE.md` and register `PreToolUse` hooks that inject "MANDATORY: run graphify query" into every
Read, Glob, Grep and Bash call — a tax on every call of a long session, and an instruction `scout`
cannot obey, having no Bash. As a tool the model reaches for the graph when it helps and ignores it
when it does not. If the user asks for that mode, say what it costs before doing it.

## 6. Removing it

```bash
graphify hook uninstall
jq 'del(.mcpServers.graphify)' .mcp.json > .mcp.json.new && mv .mcp.json.new .mcp.json
rm -rf graphify-out .gitattributes
```

Then restart `claude`. Leave the `.gitignore` line; it costs nothing.
