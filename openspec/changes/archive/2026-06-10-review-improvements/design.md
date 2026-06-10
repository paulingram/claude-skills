# Design — review-improvements

Seven streams (R1–R7). The binding global constraint is **external contracts frozen** — every Layer 3 CLI subcommand, verdict JSON shape, severity name, and fixture round-trip keeps passing; schema v7 unchanged; 19 slash-command surfaces unchanged. The pins below leave zero dev judgment calls.

## Decision 1 — R2 `hooks/vao/` partition + exact facade re-export list

### 1a. The partition (11 modules, each ≤900 lines)

`vao_tools.py` is 5,209 lines / 20 `verify_*` tools. Split by discipline family so each module is cohesive and ≤900 lines. The facade stays at `hooks/vao_tools.py`.

| Module | Tools (verify_* moved here) | Notes |
|---|---|---|
| `hooks/vao/__init__.py` | — | empty (or version marker); package marker only |
| `hooks/vao/core.py` | — | verdict-write helpers, the common output helpers (the `{tool, valid, gaps, verdict_at}` shape), the shared severity-emit scaffolding, `_is_test_path`/`_looks_like_test_path` (test-path heuristics used across tools). Everything the other modules import. |
| `hooks/vao/oracle.py` | `verify_oracle_match`, `verify_rendered_parity`, `verify_every_element`, `verify_interactions_honored` | oracle/parity/element/interaction family |
| `hooks/vao/fake_data.py` | `verify_no_fake_data`, `verify_live_data_wiring` | fake-data + live-data-wiring; owns `_MOCK_STATE_SIGNATURES` |
| `hooks/vao/live_verification.py` | `verify_live_verification_claim`, `verify_target_element_measured` | verified-live + proxy-element; owns `_EXTERNAL_SYSTEM_FEATURE_KINDS`, `_FORBIDDEN_PROXY_ASSERTION_FIELDS`, the localhost union (see R1b) |
| `hooks/vao/persona.py` | `verify_per_persona_path_coverage`, `verify_affordance_coverage` | persona-path + affordance; owns `_LOADING_STATE_UI_HINTS`, `_LOADING_STATE_MAX_DELAY_MS`, `_DOUBLE_SUBMIT_TIMING_THRESHOLD_MS`, `_FILE_UPLOAD_AFFORDANCE_SIGNATURES`, `_AFFORDANCE_SIGNATURES` |
| `hooks/vao/scope.py` | `verify_no_implementation_scope_cut`, `verify_no_unilateral_override` | implementation-scope-cut + unilateral-override; owns `_FULL_BUILD_MANDATE_PHRASES`, `_HONEST_SCOPE_STATEMENT_MARKERS`, `_FOUNDATION_ONLY_FRAMING_MARKERS` |
| `hooks/vao/deferral.py` | `verify_no_end_of_run_deferral`, `verify_no_standing_red` | end-of-run-deferral + standing-red; owns `_DEFERRAL_CATALOG_MARKERS`, `_FOLLOWUP_QUESTION_MARKERS`, `_ITEM_DISPOSITION_CITATIONS`, `_STANDING_RED_MARKERS`, `_CROSS_LAYER_SR_ORIGIN_KINDS` |
| `hooks/vao/prod_safety.py` | `verify_test_prod_safety_classification` | prod-safe-test classification |
| `hooks/vao/registry_inflight.py` | `verify_discipline_registry_current`, `verify_inflight_clarifications_processed` | the two that lazy-import `discipline_registry` / `inflight_inbox` (keep those lazy + dual-form) |
| `hooks/vao/deploy_pipeline.py` | `verify_deploy_mandate_satisfied`, `verify_baseline_clean`, `verify_no_pipeline_bypass` | deploy-mandate + baseline-clean + no-pipeline-bypass; owns `_FORBIDDEN_GIT_PATTERNS` (imported from shared_rule_constants per existing), `_LOCAL_ENV_HOST_PATTERNS` reference |

This is the FINAL partition — the dev does not re-derive it. If any single module would exceed 900 lines after extraction, split it by tool into `<family>_a.py`/`<family>_b.py` and have the facade import from both (the 900-line ceiling is the hard rule; cohesion is the soft preference). Constant ownership: a constant lives in the module of its primary consumer; if two modules consume it, it moves to `hooks/vao/core.py` and both import it from there. The localhost union constant (R1b) and `_FORBIDDEN_GIT_PATTERNS` (already in `shared_rule_constants.py`) are the cross-module cases — both resolve via import, not duplication.

### 1b. The EXACT facade re-export list (grep-derived from tests/ — the contract)

`hooks/vao_tools.py` post-split is a ≤400-line facade. It MUST re-export every name the test suite references. Derived by grepping `tests/` for `vao_tools.<attr>`, `from (hooks.)?vao_tools import <names>`, and `from hooks import vao_tools` (module-style). The complete set:

**20 public functions** (every `verify_*`):
```
verify_affordance_coverage, verify_baseline_clean, verify_deploy_mandate_satisfied,
verify_discipline_registry_current, verify_every_element, verify_inflight_clarifications_processed,
verify_interactions_honored, verify_live_data_wiring, verify_live_verification_claim,
verify_no_end_of_run_deferral, verify_no_fake_data, verify_no_implementation_scope_cut,
verify_no_pipeline_bypass, verify_no_standing_red, verify_no_unilateral_override,
verify_oracle_match, verify_per_persona_path_coverage, verify_rendered_parity,
verify_target_element_measured, verify_test_prod_safety_classification
```

**18 module-level constants** (all underscore-prefixed; tests reference them as `vao_tools._X`):
```
_AFFORDANCE_SIGNATURES, _CROSS_LAYER_SR_ORIGIN_KINDS, _DEFERRAL_CATALOG_MARKERS,
_DOUBLE_SUBMIT_TIMING_THRESHOLD_MS, _EXTERNAL_SYSTEM_FEATURE_KINDS, _FILE_UPLOAD_AFFORDANCE_SIGNATURES,
_FOLLOWUP_QUESTION_MARKERS, _FORBIDDEN_GIT_PATTERNS, _FORBIDDEN_PROXY_ASSERTION_FIELDS,
_FOUNDATION_ONLY_FRAMING_MARKERS, _FULL_BUILD_MANDATE_PHRASES, _HONEST_SCOPE_STATEMENT_MARKERS,
_ITEM_DISPOSITION_CITATIONS, _LOADING_STATE_MAX_DELAY_MS, _LOADING_STATE_UI_HINTS,
_LOCAL_ENV_HOST_PATTERNS, _MOCK_STATE_SIGNATURES, _STANDING_RED_MARKERS
```

**3 helper functions** (underscore; tests reference as `vao_tools._X`):
```
_is_local_env_url, _is_test_path, _looks_like_test_path
```

The facade re-exports via `from hooks.vao.<module> import <name>` (dual-form: `try: from hooks.vao.X import ... / except ImportError: from vao.X import ...`). The facade also re-exports any name `__all__`-style for cleanliness, but the 41 names above are the MUST list — a missing one breaks a test, and per R2's acceptance that is a facade bug, not a test bug. The facade additionally preserves the `if __name__ == "__main__":` argparse dispatch byte-for-byte (same subparser names = the 22 `verify-*` subcommand strings the glue-execution test resolves; same exit codes; same verdict-file writes). A simple safe pattern: the facade keeps the argparse block and dispatches to the re-exported functions, OR re-exports a `main()` that `hooks/vao/cli.py` owns — pin: keep the argparse IN the facade (smallest diff, guarantees byte-identical CLI), importing the 20 functions it dispatches to.

**Verification the facade is complete (mechanical, no judgment):** a new test `tests/test_vao_facade_reexports.py` (py-core owns) asserts `set(EXPECTED_REEXPORTS) <= set(dir(vao_tools))` for all 41 names AND that each `vao_tools.<name> is hooks.vao.<module>.<name>` (identity, proving re-export not re-definition). This test is the R2 safety net.

## Decision 2 — R1 ↔ R2 sequencing inside py-core: **R2 split FIRST, then R1 consolidation in the new layout**

Pin: **do R2 first, then R1.** Reasoning: R1 moves duplicated constants/helpers (the localhost lists, `_utc_now_iso`, `_load_json`, JSONL readers, pipeline-name lists) out of `vao_tools.py` into shared homes. If R1 ran first against the 5,209-line monolith, then R2 would re-cut the file and every R1 edit would have to be re-located into the new modules — double work and a merge-hazard within the same team. Doing R2 first means the file is already partitioned into the `hooks/vao/*` modules; R1 then (a) replaces the two localhost lists with the single union constant in `hooks/vao/live_verification.py` (R1b), and (b) deletes the `vao_tools.py`-local `_utc_now_iso`/`_load_json`/JSONL-reader definitions in favor of `hooks/shared_util.py` imports — operating on the small post-split modules, which is cleaner and the facade re-export test from Decision 1b immediately catches any constant that R1 moves out from under a test reference. The one ordering nuance: R1b's localhost-union must be the constant the facade re-exports as `_LOCAL_ENV_HOST_PATTERNS` (tests reference that name) AND the v2.2.0 ~849 list's consumers must point at the same union — so R1b defines the union once in `live_verification.py`, the persona/other consumer imports it, and the facade re-exports the union under the `_LOCAL_ENV_HOST_PATTERNS` name. (The v2.2.0 list had no exported name; the v2.13.0 `_LOCAL_ENV_HOST_PATTERNS` did — the union keeps that exported name so no test breaks.)

Within py-core the task order is therefore: **R2 (split + facade + facade-reexport test green) → R1a/R1b (consolidate into the new layout) → R1c (CPC family section — but that file is md-docs-owned; see the cross-team note) → R1d/R1e (override_markers, an independent file) → R7 (discipline_registry, an independent file).** R1c's CPC section is authored by md-docs, not py-core (py-core does not touch `skills/`); py-core's R1c obligation is only that the five tools' code contracts stay as-is, which they do.

## Decision 3 — the 4-team disjoint partition

Enumerated completely in `tasks.md` `## Team file partition`. The disjointness rule: every production AND test file appears under exactly one team. The cross-team resolutions:
- `scripts/phenotypes/phenotypes.py` is a `_load_json` site named by R1 but lives outside all four scopes. **Pin: leave it untouched** — it is not imported by any hook gate, its `_load_json` is independent, and dragging it into py-core's scope would couple an unrelated subsystem. R1a documents "phenotypes.py retains its own `_load_json`; out of scope for the dedup, by design (independent subsystem, not a hook gate)." No team owns it this run.
- `tests/test_cdlg_consumers.py` and `tests/test_worktree_state_resolution.py` reference `locks.py` but assert `cdlg_overlap` / worktree behavior that R5 does NOT change. **Pin: py-locks does NOT edit them** (R5's acceptance says `cdlg_overlap` unchanged); they stay green untouched. py-locks owns only `tests/test_locks.py` (edits if a narrative/line-number assertion shifts) + the NEW `tests/test_locks_concurrency.py`.
- `tests/test_shared_rule_constants.py` references `vao_tools` (module-style import) AND `shared_rule_constants`. **Pin: py-core owns it** (it tests py-core modules); if R1/R2 shift what it imports, py-core updates it and enumerates the edit.
- The md-structural test files (`test_agents.py`, `test_skills.py`, `test_interaction_completeness.py`, `test_doc_updater_agent.py`, the CPC/pipeline-body discipline-structural families) are **md-docs-owned** — they pin Markdown text md-docs changes (R3/R4/R6-doc). py teams must NOT touch them. `scripts/setup/sync_agent_boilerplate.py` is **md-docs-owned** (R4c) — py teams must NOT touch it.

## Decision 4 — R3b narrative-diet protocol (tests define the operative contract)

The exact per-section procedure md-docs follows for CPC (and analogously for the pipeline bodies):

1. **Identify the section's RULE vs NARRATIVE.** RULE = definitions, marker tables, severity names, protocols, file paths, the canonical schema/JSON examples, the firing-moment distinctions. NARRATIVE = verbatim user transcripts, "why version vX added this" rationale, neighbor-comparison prose now superseded by R1c's family table.
2. **Trim the NARRATIVE to ≤2 lines + a CHANGELOG pointer.** Keep every RULE token verbatim.
3. **Run the targeted structural tests for that section** (e.g. `tests/test_no_end_of_run_deferral_discipline.py` for the deferral section). 
4. **Triage each failing assertion:** if it pins NARRATIVE text being removed (a transcript quote, a version anecdote, a "why" sentence), it is a **narrative-pinning assertion** — UPDATE it to the trimmed text and ENUMERATE it (file::test + the removed-narrative reason) in the dev report. If it pins a RULE (a marker string, a severity name, a path, a disposition kind), the text STAYS — restore the rule token, do not edit the test.
5. **Re-run; section is done when green with only narrative-pinning edits enumerated.**
6. **Re-measure** (R3d): before/after line + word counts for `CLAUDE.md`, CPC, and the 4 pipeline bodies; CPC target ≥30% line reduction, `CLAUDE.md` ≤350 lines.

The discriminator is mechanical: a test asserting `"_STANDING_RED_MARKERS"` or `"origin.kind"` or `"confirmed-stub"` pins a rule (stays); a test asserting `"this is not allowed"` or `"Want me to continue"` as a quoted transcript, or `"v2.10.0 added"` as a version anecdote, pins narrative (update + enumerate). R3a's `CLAUDE.md` relocation has the same fact-preservation gate: before deleting any sentence, grep CHANGELOG.md + CODEBASE_MAP.md for the same fact; if found only in CLAUDE.md, append it into the matching CHANGELOG entry FIRST, then delete from CLAUDE.md.

## Decision 5 — Reuse Decisions for every NEW file (reuse-first-design schema)

| NEW file | Ladder rung | Decision + justification | CODEBASE_MAP citation |
|---|---|---|---|
| `hooks/vao/*.py` (11 modules) | extract (compose) | Not "build new" logic — mechanical extraction of existing `vao_tools.py` code into cohesive modules; the facade preserves the public surface. No new behavior. The package is the structural home the 5,209-line monolith should have had. | CODEBASE_MAP `hooks/` — `vao_tools.py` is listed as the 20-tool Layer 3 module; this splits it, facade-compatible |
| `hooks/shared_util.py` | build new (smallest) | No existing util module exists; `shared_rule_constants.py` is constants-only (functions don't belong there per R1a). The single home for `load_json(path,*,missing_ok)` + `_utc_now_iso` + the unified JSONL reader. Reuse-maximal: it ELIMINATES 3–4 duplicate definitions rather than adding a 5th. | CODEBASE_MAP `hooks/` — sits beside `shared_rule_constants.py` as the function-sibling |
| `hooks/heartbeat` event in `notify.py` + `heartbeat_snapshot` in `run_metrics.py` | extend | Extends the existing `EVENT_TYPES` tuple (5→6) and the existing `run_metrics.py` reader funcs; no new module. Same opt-in/best-effort contract. | CODEBASE_MAP `scripts/notify/notify.py` (5 event types) + `hooks/run_metrics.py` (metric instrumentation) |
| `tests/test_locks_concurrency.py` | build new (test) | No existing concurrency test for `locks.py`; mirrors `tests/test_inflight_inbox_atomic.py` style (the established atomic/threaded-test pattern in this repo). | CODEBASE_MAP `tests/` — joins the per-hook behavior test set |
| `tests/test_vao_facade_reexports.py` | build new (test) | The mechanical R2 safety net (Decision 1b); no existing test asserts the facade re-export completeness. | CODEBASE_MAP `tests/` |
| `tests/test_locks_*` / `test_shared_util.py` / `test_override_markers_proximity.py` / `test_discipline_applicability.py` / `test_heartbeat*.py` / `test_security_hunter_shape.py` / `test_a11y_axis.py` (the per-item NEW tests) | build new (test) | Each pins a specific R-item fix; none has an existing home that asserts it. Enumerated per-team in `tasks.md`. | CODEBASE_MAP `tests/` |
| `tests/fixtures/vao/security-finding-routed.json` | build new (fixture) | The canonical round-trip fixture for the new `security-finding` origin kind; mirrors the existing `tests/fixtures/vao/*` fixtures. | CODEBASE_MAP `tests/fixtures/vao/` |

No NEW skill, NEW agent, or NEW slash command is created — R6a/R6b extend existing agents + skills; R6c extends existing scripts. The `hooks/vao/` package and `hooks/shared_util.py` are the only net-new code modules, both justified above.

## Decision 6 — Version 3.10.0 (minor) + CHANGELOG skeleton

**3.10.0 (minor), not a patch.** R6 adds NEW capabilities to the plugin's surface — the `security-hunter` adversarial shape, the interaction-completeness accessibility axis, and the `heartbeat` notify event are net-new user-visible capability (a new SR origin kind `security-finding`, a new severity vocabulary `a11y-gap`, a new event type). Under the repo's de-facto semver (minor = new skill/agent/tool/discipline/capability; patch = behavior-restoring fix), the presence of new capabilities forces a minor. R1/R2/R4 are behavior-preserving refactors and R5/R7 are bug fixes — on their own those would be a patch — but a single release containing any new capability is a minor. The requirement itself specifies 3.10.0; this confirms it. (Contrast v3.9.3, which was pure remediation → patch.)

CHANGELOG skeleton (md-docs authors the full entry at FD/MD-time):
```
## 3.10.0 — Second-tier review improvements (R1–R7)

Implements the six design-level streams the v3.9.3 review-remediation run deferred, plus the
discipline-detector-applicability SR (R7).

- R1: Scope-discipline + marker/helper consolidation — `_utc_now_iso` / `load_json` / the JSONL
  reader unified into `hooks/shared_util.py`; the two localhost lists unified; a canonical
  `## Scope-fidelity discipline family (v3.10.0)` CPC section folds the five scattered tables;
  two named override/scope-cut false positives fixed (proximity + standalone-phrase pruning).
- R2: `hooks/vao_tools.py` (5,209 lines / 20 tools) split into the `hooks/vao/` package
  (11 modules, each ≤900 lines); `vao_tools.py` remains a ≤400-line facade re-exporting all
  41 test-referenced names; CLI byte-identical; ZERO behavior change (every fixture + CLI test green).
- R3: Narrative diet — `CLAUDE.md` restructured operative-first (≤350 lines); CPC narrative
  compressed ≥30% with zero rule loss; pipeline bodies collapsed to canonical references.
- R4: Agent hygiene — `LS`/`NotebookRead` removed from frontmatter; write-without-Write fixed;
  boilerplate re-synced across all 34; colors mapped; `scaffold-agent` documented.
- R5: `locks.py` concurrency — `O_CREAT|O_EXCL` lock creation + intersecting-scope re-scan;
  `globs_intersect` prefix/suffix candidate class (the `src/**` vs `**/auth.py` case).
- R6: New capabilities — `security-hunter` adversarial shape + `security-finding` SR origin kind
  (+ SR-catalog fork reconciliation); interaction-completeness `## Accessibility axis (v3.10.0)`
  with `a11y-gap` findings; unbounded-run `heartbeat` notify event + `heartbeat_snapshot` + CPC
  heartbeat discipline.
- R7: `discipline_registry.py` prod-safe + multi-persona detectors gain applicability guards;
  registry schema records `{applied, not_applicable, reason}`; this no-UI repo now records both
  disciplines `not_applicable` instead of false-flagging 163 files.

Suite: 4097 (+ new tests) passing + 5 skipped, green under cp1252 AND PYTHONUTF8=1.
```

## Decision 7 — Phase 1 layer classification + N/A authorization

Every coverage-map entry is `layer: infra`. This repo has no frontend/backend/`both` surface; the `playwright-user-flows` and `dev-api-integration-testing` criteria that Phase 1 normally requires for `frontend`/`both`/`backend` entries are **recorded N/A** with the authorization note (carried on every entry as `mock_testing_authorized`-style note + a top-level coverage-map note): *"no UI/HTTP surface; verification = pytest both encodings + real-subprocess CLI execution + openspec strict validation."* Phase 1's loop conditions accept a recorded authorization in lieu of those criteria; the `infra` layer plus this note is that authorization. The substantive verification (pytest under both encodings + the real-subprocess CLI execution family + `openspec validate --all --strict`) is stronger than a mocked web flow would be for this codebase.
