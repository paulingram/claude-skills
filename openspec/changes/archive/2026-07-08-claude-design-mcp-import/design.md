# Design — claude-design-mcp-import

## Context

CT6 builds each discrete capability as a **deterministic stdlib engine + an LLM-judgment skill contract** pair (data-dictionary, claude-md-efficiency, mcp-output-contract-design, helpdesk, token-compression). This change follows that shape exactly, plus thin wiring edits into the existing design-consuming path. The external `claude_design` MCP is handled the same way CT6 handles every external boundary — an **injected adapter** with a stdlib fake for offline tests (the `services/librarian` `UrlSource` / `FakeLLMClient` precedent).

## Goals / Non-Goals

**Goals.** Detect a Claude Design offer; fetch the whole project natively via the `claude_design` MCP; materialize it locally; route it into the existing `oracle-deriver` interactive-mockup path unchanged; degrade gracefully when the MCP is unavailable; keep the zip/local path first-class.

**Non-Goals.** Implementing the finance-dashboard example; building/hosting the MCP server or `/design-login`; changing the downstream derivation agents' logic; persisting MCP tokens; wiring detection onto `bug-fix` / `mini`.

## The engine API contract (`scripts/claude_design/claude_design_import.py`)

Stdlib-only, `from __future__ import annotations`, no import-time side effects, module docstring naming this design. Public surface:

```python
def detect_claude_design_offer(text: str) -> dict:
    """Detect a Claude Design offer from prose. Fires on EITHER trigger form
    (a claude.ai/design/p/<id> URL OR a claude_design MCP mention — inclusive OR).
    Returns:
      {
        "detected": bool,
        "trigger_forms": list[str],     # subset of {"design-url", "mcp-mention"}, sorted
        "project_url": str | None,       # full claude.ai/design/p/<id>... URL if present
        "project_id": str | None,        # the <id> path segment
        "file_selector": str | None,     # URL-decoded ?file= value
        "implement_target": str | None,  # value of a trailing "Implement: <path>" line
        "mcp_endpoint": str | None,      # the MCP endpoint if named in the prose
      }
    """

def parse_design_url(url: str) -> dict:
    """Extract {base_url, project_id, file_selector} from a claude.ai/design/p/<id>?file=...
    URL. file_selector is URL-decoded (%2F -> '/', '+' -> ' '). Returns project_id=None for a
    non-matching URL (never raises on a plain string)."""

class ClaudeDesignSource:  # interface / Protocol
    def fetch_project(self, project_id: str, *, file_selector: str | None = None) -> list[dict]:
        """Return the whole project's files as [{"path": str, "content": str}, ...].
        The REAL implementation is the runtime claude_design MCP call (done by the orchestrator
        via ToolSearch, injected here); this interface is the seam."""

class FakeClaudeDesignSource(ClaudeDesignSource):
    """Offline test double constructed from a {path: content} mapping (or a file list)."""

def materialize_project(files: list[dict], dest_dir: str | Path, *, focus: dict | None = None) -> dict:
    """Write each fetched file under dest_dir, path-safely. Rejects absolute paths and '..'
    traversal (never writes outside dest_dir). Returns:
      {"materialized_dir": str, "files_written": list[str], "rejected": list[dict], "focus": dict|None}
    """

def import_claude_design(offer: dict, source: ClaudeDesignSource, dest_root: str | Path,
                         *, mcp_available: bool = True, local_fallback_available: bool = True) -> dict:
    """Orchestrate: when mcp_available and offer.detected -> fetch via source + materialize to
    dest_root/<project_id>/ and return {"status": "materialized", ...}. When not mcp_available ->
    return plan_when_unavailable(...) verbatim (no fetch). The engine never calls the MCP itself."""

def plan_when_unavailable(offer: dict, *, local_fallback_available: bool = True) -> dict:
    """Return {"action": "instruct-then-fallback" | "instruct-then-halt",
               "instruction": "<connect the claude_design MCP + run /design-login ...>",
               "fallback": "zip-local" | None}. instruct-then-fallback when a local fallback
    is available; instruct-then-halt only when it is not."""

def _safe_relpath(path: str) -> str:
    """Normalize + validate a fetched file path to a safe relative path; raise ValueError on
    absolute paths or '..' escape. Used by materialize_project."""

def main(argv: list[str] | None = None) -> int:
    """CLI: `detect <text-or-@file> [--json]` and `parse-url <url> [--json]` (offline subcommands;
    fetch/materialize need a live source, so they are library-only)."""
```

Determinism: `detect_claude_design_offer` and `parse_design_url` are pure functions of their input; `materialize_project` sorts its `files_written`. JSON output uses `sort_keys=True, indent=2`.

## The skill contract (`skills/claude-design-import/SKILL.md`)

Frontmatter `name: claude-design-import` (== dir), a `description` that carries NO `': '` and NO `' #'` (house YAML rule) and is ≤ 1024 chars. Body: `# Claude Design Import` H1, then `## When this skill runs` (the two trigger forms), `## Two first-class input sources` (MCP-native + zip/local, user picks per run), `## Workflow` (detect via the engine → load the `claude_design` MCP tools via ToolSearch → fetch the WHOLE project focused by `?file=` + `Implement:` → materialize via the engine → hand the dir to `oracle-deriver` as an `interactive-mockup` oracle; the MCP-unavailable instruct-then-fallback branch), `## Honest boundary` (the engine is deterministic; the MCP fetch is an injected adapter; tokens are never persisted), `## Cross-references`. The skill body cites the engine and the downstream path in machine-checkable path forms (`scripts/claude_design/claude_design_import.py`, `agents/oracle-deriver.md`, `skills/interactive-mockup-discovery/SKILL.md`, `skills/design-fidelity-mapping/SKILL.md`).

## The wiring edits (bodies only)

- `skills/intake-and-mapping/SKILL.md` — a short subsection under input/codebase discovery: when `$REQ_DIR` prose carries a Claude Design offer (detected via the engine), invoke `claude-design-import` to materialize it, then treat the materialized dir as a design-input oracle. Additive — the existing local discovery is unchanged.
- `agents/oracle-deriver.md` — in the `interactive-mockup` spec_shape section (and the "A reference URL is named" trigger), note that a Claude Design link materialized by `claude-design-import` is walked as an `interactive-mockup` oracle. Body edit only; frontmatter (description/tools/model/color) untouched.
- `skills/design-fidelity-mapping/SKILL.md` — add the materialized Claude Design dir to the design-input source list.
- `commands/architect-team.md`, `commands/visual-to-api.md`, `commands/ux-test.md` — a one-line note that these design-consuming commands detect a Claude Design link and route it through `claude-design-import`.

## Reuse Decision Log (reuse-first-design)

| Proposed item | Ladder verdict | Rationale (CODEBASE_MAP anchor) |
|---|---|---|
| Detect + fetch + materialize logic | **build-new (engine)** | No existing engine does link-detection or MCP materialization; grep confirms zero `claude_design` / MCP-consumption sites. Built as a new stdlib engine mirroring `scripts/claude_md/claude_md_efficiency.py`. |
| Consume the fetched design (oracle/spec) | **reuse** | `agents/oracle-deriver.md` `spec_shape: interactive-mockup` (v2.1.0) already handles HTML mockups → `skills/interactive-mockup-discovery` → `skills/visual-to-api-design`. We materialize INTO that path; no new consumer. |
| The MCP fetch adapter + fake | **compose** | Mirrors `services/librarian` `UrlSource`/`StaticSource`/`FakeLLMClient` — an injected boundary with a stdlib fake for offline tests. |
| The capability contract | **build-new (skill)** | Each discrete CT6 capability is its own skill; this is a discrete capability. New `skills/claude-design-import/SKILL.md` (47 → 48). |
| Input discovery | **extend** | Extend `skills/intake-and-mapping` input discovery with the new source rather than a parallel intake path. |

## Honest boundary

The engine does detection, URL/`?file=`/`Implement:` parsing, materialization, path-safety, and fallback-planning **deterministically and offline**. It NEVER calls the network or the MCP — the real `claude_design` MCP fetch is invoked by the orchestrator at runtime via ToolSearch and injected as a `ClaudeDesignSource`; offline tests use `FakeClaudeDesignSource`. The plugin cannot guarantee the MCP is connected or `/design-login` has run — hence the instruct-then-fallback boundary. No MCP tokens or credentials are persisted. This is design + a runnable stdlib core + tests, matching every prior CT6 external-adapter capability; it is not a live-deployed integration.

## Risks / Mitigations

- **Instruction-compliance lint failure on the new/edited files** → author the skill frontmatter with no `': '`/`' #'`, ≤ 1024-char description, `## Cross-references`; run the lint before completion.
- **Count-pins break when the 48th skill lands** → update `tests/test_skills.py` `EXPECTED_SKILLS` + `tests/test_instruction_compliance.py` in-scope counts (47 → 48) as part of the implementation, not deferred.
- **`?file=` encoding edge cases** (`%2F`, `+`) → `parse_design_url` URL-decodes; tests pin the decode.
- **Path traversal in fetched files** → `_safe_relpath` rejects absolute + `..`; a scenario pins the rejection.
