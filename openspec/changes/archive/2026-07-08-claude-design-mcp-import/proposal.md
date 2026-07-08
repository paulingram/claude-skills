## Why

Today, when a user has a design built in **Claude Design** (`claude.ai/design/p/<id>`), the only way to get it into a CT6 pipeline run is to download it as a zip, unpack it locally, and point `$REQ_DIR` at the files. Claude Code can talk to the `claude_design` MCP (`https://api.anthropic.com/v1/design/mcp`, auth via `/design-login`) natively — the canonical prompt is *"Use the claude_design MCP to import this project: `https://claude.ai/design/p/<id>?file=…` — Implement: `<file>`"*. CT6 does not detect or act on that offer: grep for `claude_design` / `design-login` / `claude.ai/design` / `mcp__` consumption across the plugin returns zero sites (the only MCP surface is the outward-facing `mcp-output-contract-design`). So a design that Claude Code could fetch in one call still forces a manual zip round-trip.

The reusable machinery to CONSUME the design already exists: `agents/oracle-deriver.md` fires at Phase 0.5 when *"A reference URL is named"* and already carries a `spec_shape: interactive-mockup` (v2.1.0) built precisely for *"a single-file `.html` with `<script>` tags, inline `onclick=`…"* — which is exactly the shape of a Claude Design HTML file (the example is `Finance Dashboard.html`). What is missing is the UPSTREAM step: detect the offer, fetch the project through the MCP, and materialize it to a local oracle path so the existing `oracle-deriver` → `interactive-mockup-discovery` → `visual-to-api-design` path runs unchanged.

## What Changes

- **New deterministic engine `scripts/claude_design/claude_design_import.py`** (stdlib-only, no import-time side effects, mirroring `scripts/claude_md/claude_md_efficiency.py`) — detects a Claude Design offer from prose on either trigger form (a `claude.ai/design/p/<id>` URL and/or a `claude_design` MCP mention), parses the `?file=` selector (URL-decoded) and the `Implement: <path>` line as the focus, materializes fetched files to a local dir path-safely, and plans the instruct-then-fallback behavior when the MCP is unavailable. The actual MCP fetch is an INJECTED adapter (a `ClaudeDesignSource` interface with a `FakeClaudeDesignSource` for offline tests — the real MCP is invoked by the orchestrator at runtime via ToolSearch). (REQ-001, REQ-002, REQ-004)
- **New skill `skills/claude-design-import/SKILL.md`** — the LLM-judgment contract over that engine. Documents the detection triggers, the two first-class input sources (MCP-native and zip/local, user-selectable per run), the fetch-whole-project-focused-by-prompt rule, the runtime `claude_design` MCP invocation via ToolSearch, the materialize-then-hand-to-oracle-deriver flow, and the instruct-then-fallback boundary. (REQ-002, REQ-003, REQ-004, REQ-005)
- **Wiring into the existing front-end path (edits only — no derivation-logic change)** — `skills/intake-and-mapping/SKILL.md` (the shared input-discovery seam invokes `claude-design-import` when a link is offered), `agents/oracle-deriver.md` (a materialized Claude Design project is walked as an `interactive-mockup` oracle), `skills/design-fidelity-mapping/SKILL.md` (the materialized dir is a design-input source), and the three design-consuming commands `commands/architect-team.md`, `commands/visual-to-api.md`, `commands/ux-test.md`. (REQ-003, REQ-007)
- **Tests** — new `tests/test_claude_design_import.py` covering detection (both forms + parse), fetch-orchestration against the fake source, materialization + path-safety, and the fallback plan; the new-skill count-pins updated (`tests/test_skills.py` `EXPECTED_SKILLS`, `tests/test_instruction_compliance.py` in-scope counts). Full suite green under both cp1252 and `PYTHONUTF8=1`. (REQ-006)
- **Version + docs** — plugin.json + marketplace.json → **v3.33.0**; CHANGELOG entry; README / CLAUDE.md / the two maps / the instruction-compliance rubric count table refreshed (47 → 48 skills) at the Phase 8 doc-currency gate. (REQ-008)

## Capabilities

### New Capabilities

- `claude-design-import`: native ingestion of a Claude Design project offered via a link — detect the offer, fetch the whole project through the `claude_design` MCP, materialize it to a local oracle path, and route it into the existing `oracle-deriver` interactive-mockup path; MCP-native and zip/local both first-class, with an instruct-then-fallback boundary when the MCP is unavailable.

### Modified Capabilities

None (no existing living spec governs design-input ingestion; the wiring edits extend the existing intake / oracle-derivation flow without changing any governed contract).

## Impact

- `scripts/claude_design/claude_design_import.py` — NEW deterministic engine (stdlib-only, adapter-injected fetch).
- `skills/claude-design-import/SKILL.md` — NEW skill contract (47 → 48 skills).
- `skills/intake-and-mapping/SKILL.md`, `agents/oracle-deriver.md`, `skills/design-fidelity-mapping/SKILL.md` — wiring edits (bodies only; oracle-deriver frontmatter untouched).
- `commands/architect-team.md`, `commands/visual-to-api.md`, `commands/ux-test.md` — a note that these detect Claude Design links.
- `tests/test_claude_design_import.py` — NEW; `tests/test_skills.py` + `tests/test_instruction_compliance.py` count-pins bumped 47 → 48.
- `.claude-plugin/plugin.json` + `marketplace.json` + `CHANGELOG.md` + `README.md` + `CLAUDE.md` + `docs/CODEBASE_MAP.md` + `docs/INTEGRATION_MAP.md` + `docs/INSTRUCTION_COMPLIANCE_RUBRIC.md` — v3.33.0 currency (Phase 8).
- NOT touched: the downstream derivation agents' logic (`interaction-observer`, `visual-to-api-design`, `interactive-mockup-discovery` internals), hooks/, other services/, phenotypes/, the zip/local design-input path (kept working, unchanged).
