---
name: claude-design-import
description: Use when a requirement carries a Claude Design offer — a claude.ai/design/p link and/or a claude_design MCP mention — and you need to import that design project into the pipeline as a front-end oracle. Detects the offer, fetches the WHOLE project natively through the claude_design MCP, materializes it locally path-safely, and hands it to the existing interactive-mockup oracle path. Degrades gracefully with an instruct-then-fallback to the zip/local design-input path when the MCP is unavailable, so a run never dead-ends. The deterministic detector, URL parser, materializer, and fallback planner live in scripts/claude_design/claude_design_import.py; this skill is the contract.
---

# Claude Design Import

A Claude Design project is a whole set of design files (screens + assets) that
lives behind the `claude_design` MCP and is addressed by a
`claude.ai/design/p/<id>` link. This skill imports that project into the pipeline
as a front-end oracle: it detects the offer, fetches the whole project natively
through the MCP, materializes it to a local directory, and hands that directory to
the EXISTING interactive-mockup oracle path with no change to the downstream
derivation agents.

The deterministic engine lives in **`scripts/claude_design/claude_design_import.py`**
(stdlib-only, unit-tested, offline); this skill is the contract + the LLM-judgment
workflow. Do not re-implement the deterministic pieces in prose — call the module.

## When this skill runs

Invoke this skill when a requirement carries a Claude Design offer on EITHER
trigger form (an inclusive OR — either alone is sufficient):

- **A design URL** — a `claude.ai/design/p/<id>` link is present, optionally with a
  `?file=<selector>` query naming a focus screen.
- **An MCP mention** — the `claude_design` MCP is named (naming its endpoint
  `https://api.anthropic.com/v1/design/mcp` counts as a mention too).

Run `detect_claude_design_offer(text)` from the engine over the requirement prose
(`$REQ_DIR`) to get the structured verdict — `detected`, `trigger_forms`,
`project_id`, `file_selector` (URL-decoded), `implement_target` (a trailing
`Implement: <path>` line), and `mcp_endpoint`. When `detected` is false, this skill
is a no-op and the existing local design-input discovery proceeds unchanged.

## Two first-class input sources

MCP-native and zip/local are BOTH first-class design-input sources, selectable per
run. This skill adds the MCP-native source; it never removes or supersedes the
existing local/zip discovery.

- **MCP-native** — the `claude_design` MCP fetches the whole project. Preferred when
  the requirement carries a Claude Design offer and the MCP is connected.
- **zip/local** — a design directory or zip supplied in `$REQ_DIR`, discovered and
  processed exactly as before. This is also the automatic fallback when the MCP is
  unavailable (see the Workflow's fallback branch).

## Workflow

### Step 1 — Detect the offer

Call `detect_claude_design_offer($REQ_DIR-prose)`. If `detected` is false, stop —
the local design-input path handles the run. Otherwise carry the verdict's
`project_id`, `file_selector`, and `implement_target` forward as the focus.

### Step 2 — Load the claude_design MCP tools (runtime)

Load the `claude_design` MCP tools via ToolSearch at runtime. The MCP endpoint is
`https://api.anthropic.com/v1/design/mcp`; authentication is via `/design-login`.
The engine NEVER calls the MCP itself — the fetch is a runtime MCP call injected
into the engine as a `ClaudeDesignSource`.

### Step 3 — Fetch the WHOLE project (focused, not truncated)

Fetch the WHOLE design project through the MCP — every screen and asset, NOT only
the `?file=`-selected file. The `file_selector` and `implement_target` are the
FOCUS (which screen(s) drive implementation), not a filter that drops the rest of
the project — a design's other screens are context the build needs.

### Step 4 — Materialize locally, path-safely

Call `materialize_project(files, dest_dir, focus=...)` to write the fetched files
to `<workspace>/.architect-team/claude-design/<project-id>/`, passing the focus
(`file_selector` + `implement_target`). The engine writes every file path-safely —
it REJECTS absolute paths and `..` traversal and never writes outside the
destination directory — and records the focus alongside the whole-project file
list. `import_claude_design(offer, source, dest_root)` orchestrates the
fetch-plus-materialize in one call.

### Step 5 — Hand the directory to the interactive-mockup oracle path

Hand the materialized directory to `agents/oracle-deriver.md` as an
`interactive-mockup` oracle (its existing v2.1.0 spec_shape). The oracle-deriver
walks the directory, and `skills/design-fidelity-mapping/SKILL.md` treats it as a
design-input source. No downstream derivation logic is rewritten — the materialized
directory flows through the EXISTING front-end analysis path unchanged.

### Fallback — the MCP is unavailable

When the `claude_design` MCP is not connected or `/design-login` has not been run,
call `plan_when_unavailable(offer)`. It returns an `instruct-then-fallback` plan:
instruct the user to connect the `claude_design` MCP and run `/design-login`, and
on the user declining, auto-fall-back to the existing zip/local design-input path.
A run NEVER dead-ends on an unavailable MCP — it proceeds down the zip/local path.
Only when no local fallback exists does the plan become `instruct-then-halt`.

## Honest boundary

The engine does detection, URL / `?file=` / `Implement:` parsing, materialization,
path-safety, and fallback-planning DETERMINISTICALLY and OFFLINE. It NEVER calls
the network or the MCP — the real `claude_design` MCP fetch is invoked by the
orchestrator at runtime via ToolSearch and injected as a `ClaudeDesignSource`;
offline tests use `FakeClaudeDesignSource`. The plugin cannot guarantee the MCP is
connected or `/design-login` has run — hence the instruct-then-fallback boundary.
No MCP tokens or credentials are persisted. This is design + a runnable stdlib core
+ tests, matching every prior CT6 external-adapter capability; it is not a
live-deployed integration.

## Cross-references

- `scripts/claude_design/claude_design_import.py` — the deterministic detector, URL parser, materializer, and fallback planner (the machine; this skill is the contract).
- `agents/oracle-deriver.md` — Layer 1 of VAO; walks the materialized directory as an `interactive-mockup` oracle (the downstream consumer, unchanged).
- `skills/interactive-mockup-discovery/SKILL.md` — the interactive-mockup two-pass mechanism the materialized directory feeds.
- `skills/design-fidelity-mapping/SKILL.md` — treats the materialized Claude Design directory as a design-input source.
- `skills/intake-and-mapping/SKILL.md` — the Phase −1 input discovery this capability extends with the MCP-native source.
