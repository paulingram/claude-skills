## Why

The v0.9.15 documentation-currency gate at Phase 8 of `architect-team-pipeline` (and the reused gate at Phase B8 of `bug-fix-pipeline`, v0.9.22) does the right discipline — sweep the inventory of affected docs before commit, audit independently via `system-architect`'s Documentation Currency Audit mode, block the auto-commit on a `fail` verdict. But the *update* step is "the orchestrator updates" — a single sentence in the skill body that defers to whichever model is currently driving Phase 8.

That works when the orchestrator is patient and the diff is small. It cracks when:

- **The diff is big.** A v0.9.22-shaped ship touches 30 files and adds 5 new agents / a new skill / 5 new test files; remembering to update every doc the change crosses (the inventory grid in README, the `EXPECTED_*` parametrizations, the CODEBASE_MAP §3/§4 sections, the CLAUDE.md frontmatter counts, the INTEGRATION_MAP frontmatter note, the CHANGELOG entry) is a 22-step checklist the orchestrator at end-of-context routinely forgets parts of.
- **The bug-fix pipeline runs fast.** A 30-line bug fix at Phase B8 has a much smaller diff but still touches CHANGELOG and bumps a version — and the bug-fix loop is supposed to be *fast*, so the orchestrator gets less attention for doc updates per run than for the build itself. Today's bug-fix flow inherits the "the orchestrator updates" sentence verbatim, but that orchestrator is now in symptom-gone-end-to-end mode, not docs-sweep mode.
- **The user has to ask.** The user just typed *"review and update all documentation - note that we should be doing this automatically with an agent as part of the architect team for both bug and regular feature fixes"* — which is the second-worst class of feature request (after one for a fix that should already exist). The discipline is documented; the dispatch is missing.

The fix is to promote the update step from a sentence in the skill to a **dedicated agent** with bounded Write scope and a clear process — the same shape as `task-reviewer` and the visual-fidelity-verifier family. The `system-architect` Documentation Currency Audit mode (independent checker) stays as it is. The orchestrator's role shrinks to dispatch + audit-verdict-gating.

## What Changes

- **Add** the `doc-updater` agent (REQ-001) — opus, bounded `Write` access ONLY to the documentation-currency inventory paths (`README.md`, `CHANGELOG.md`, `docs/CODEBASE_MAP.md`, `docs/INTEGRATION_MAP.md`, `CLAUDE.md`, `AGENTS.md` when present, and per-codebase `<codebase>/docs/ROUTE_MAP.md` / `<codebase>/docs/DESIGN_MAP.md` / `<codebase>/docs/INTERACTION_INTUITION_MAP.md`). NO `Edit` on source code, NO `Write` outside the inventory paths. The agent reads:
  - The run's full `git diff` against the merge base.
  - The coverage map (`openspec/changes/<change-name>/coverage-map.json`).
  - The run ledger (the list of implementing commits, tests added, teammates spawned).
  - The current state of every inventory doc.
  And identifies — per the `documentation-currency` skill's inventory and rules — every section across those docs that is stale relative to what the run actually shipped, then edits each stale section in place. Outputs a structured report at `<cwd>/.architect-team/documentation-currency/updates-<ts>.json` enumerating every file touched and every section edited.
- **Modify** the `documentation-currency` skill (REQ-002) — name the `doc-updater` agent as the update mechanism; document the producer/checker discipline (the agent updates; `system-architect` Documentation Currency Audit independently verifies; the audit's verdict — not the agent's self-report — is what gates the commit). The orchestrator's role is dispatcher + verdict-gate-enforcer, not the typist.
- **Modify** the main `architect-team-pipeline` skill's Phase 8 documentation-currency block (REQ-003) — replace "the orchestrator performs the updates" with "the orchestrator dispatches the `doc-updater` agent." The audit block (`system-architect` in Documentation Currency Audit mode) is unchanged.
- **Modify** the `bug-fix-pipeline` skill's Phase B8 documentation-currency reference (REQ-004) — same dispatch, same audit. The bug-fix pipeline's Phase B8 must reach the same green doc-currency verdict before its auto-commit; today it inherits the main pipeline's discipline by reference, but the reference is to a sentence that says "orchestrator updates" — change to "dispatch the `doc-updater` agent."
- **Add** pytest structural coverage (REQ-005) — the agent registers correctly, the tools allowlist is exactly what it should be (Write present but scoped via prompt to the inventory; Edit absent; Bash present for diff inspection), the body documents the inputs / process / output report schema, the documentation-currency skill cites the agent, both pipeline skills dispatch the agent at the right phase, the system-architect agent's Documentation Currency Audit section is unchanged structurally (still the checker).
- **Document & release** as v0.9.23 (REQ-006) — README banner / NEW IN panel / inventory grid (22 → 22 agents → 22 agents — wait, the new agent is the 22nd, so AGENTS goes 21 → 22) / timeline; CHANGELOG; CODEBASE_MAP §3/§4; CLAUDE.md frontmatter counts; INTEGRATION_MAP frontmatter note; plugin.json + marketplace.json. This release ALSO surfaces and fixes any v0.9.22 doc-staleness the doc-updater agent catches when it runs its first dogfood pass (which IS this release's Phase 8 — eating its own dog food immediately).

No breaking change. The promotion is purely a dispatch refactor. Existing Documentation Currency Audit mode in `system-architect` is unchanged; the gate's pass/fail semantics are unchanged; the commit-blocking enforcement in `pipeline-completion-audit.py` is unchanged.

## Capabilities

### New Capabilities

- `doc-updater-agent`: a dedicated agent that performs the Phase 8 (and Phase B8) documentation-currency update step. Reads the run's diff + coverage map + ledger + the current state of every inventory doc, identifies every stale section, and edits each in place. Bounded `Write` scope to the inventory paths only; never edits source code, never writes outside the inventory. The existing `system-architect` Documentation Currency Audit mode (independent checker, per v0.9.13's producer/checker discipline) is unchanged — the audit verdict still gates the commit. The new agent is wired into BOTH the main `architect-team-pipeline` (Phase 8) AND the `bug-fix-pipeline` (Phase B8), so doc currency is structurally automatic for both feature work and bug fixes.

### Modified Capabilities

None. No existing spec's requirements change. The `documentation-currency` skill, the main pipeline, and the bug-fix pipeline get language updates pointing at the new agent, but their semantics (when the gate fires, what the audit checks, what `pass`/`fail` mean) are unchanged.

## Impact

**Affected files:**

- `agents/doc-updater.md` — NEW. The dedicated documentation-update agent.
- `skills/documentation-currency/SKILL.md` — MODIFIED. References the new agent as the update mechanism; documents the producer/checker pairing.
- `skills/architect-team-pipeline/SKILL.md` — MODIFIED. Phase 8 documentation-currency block dispatches `doc-updater` (replaces "orchestrator performs the updates").
- `skills/bug-fix-pipeline/SKILL.md` — MODIFIED. Phase B8 references the same dispatch (replacing the inherited "orchestrator updates" language).
- `tests/test_doc_updater_agent.py` — NEW. Frontmatter; `model: opus`; tools allowlist (Edit NOT, Write IS, Bash IS); body sections; output report schema.
- `tests/test_doc_updater_wiring.py` — NEW. Cross-cutting wiring assertions across documentation-currency skill, both pipeline skills.
- `tests/test_agents.py` — MODIFIED. `EXPECTED_AGENTS` += `doc-updater`.
- `README.md`, `CHANGELOG.md`, `docs/CODEBASE_MAP.md`, `docs/INTEGRATION_MAP.md`, `CLAUDE.md` — MODIFIED. Documentation (which is exactly the doc-currency sweep this change is designed to automate — meta-poetic).
- `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json` — MODIFIED. Version `0.9.23`.

**Affected APIs / dependencies:** none. No new third-party dependency. Pure Markdown agent + Python pytest self-tests + JSON manifests.

**Affected systems:** future pipeline runs (after the plugin updates to v0.9.23) dispatch the `doc-updater` agent automatically at Phase 8 (main pipeline) and Phase B8 (bug-fix pipeline). The agent updates the inventory docs; the `system-architect` Documentation Currency Audit independently verifies; the audit verdict gates the commit. The user never has to ask for a doc sweep.

**Reuse-first decision summary:** The `system-architect` Documentation Currency Audit mode (v0.9.15) is the right independent-checker pattern and is REUSED unchanged. The `documentation-currency` skill is the right inventory + rules definition and is EXTENDED (one section: "Update mechanism — the doc-updater agent"). The agent-with-bounded-Write pattern is REUSED from `route-mapper` (writes ROUTE_MAP.md / DESIGN_MAP.md only) and `interaction-intuiter` (writes INTERACTION_INTUITION_MAP.md only) — both established patterns where an agent's Write scope is documented in its body and bounded by which files it actually writes. The producer/checker discipline (v0.9.13's anti-self-attestation rule) is REUSED — the agent updates, the system-architect audits, the orchestrator gates on the audit verdict. The agent itself is a justified build-new — discrete role: dispatch-able, bounded-Write, single-responsibility — that does not fit into any existing agent's scope. Full Reuse Decision Log in `design.md`.
