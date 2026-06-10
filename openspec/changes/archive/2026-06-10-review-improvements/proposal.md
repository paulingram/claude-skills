## Why

The 2026-06-09 comprehensive library review of CLAUDE TEAM SIX produced two tiers of findings. The first tier — 30 verified silent-failure defects — shipped as v3.9.3 (`review-remediation`, merged at `bcfee65`). This change implements the **second tier**: six design-level work streams (R1–R6) the remediation run deliberately deferred as separate work, plus one open solution requirement (R7, `SR-discipline-detector-applicability`) folded in per the fix-everything rule. The repo is at v3.9.3: **4097 passing + 5 skipped across 163 test files**, green under Windows cp1252 AND `PYTHONUTF8=1` — that both-encodings invariant is the hard constraint at the end of this run (counts grow; both-green stays).

The streams share a theme: **the plugin's own internal structure has accreted to the point where it works but is hard to maintain and occasionally mis-fires.** Five disciplines enforce one principle at five timeline moments, each with its own duplicated marker lists and neighbor-comparison tables; `vao_tools.py` is a 5,209-line / 20-tool monolith; the project `CLAUDE.md` overview is a multi-thousand-token version-history narrative loaded every session; `common-pipeline-conventions` is ~2,470 lines at ~50% narrative; the four pipeline bodies re-spell ~250–300 lines of CPC-canonical content in violation of CPC's own "MUST NOT re-spell inline" rule; agent frontmatter carries stale tool vocabulary and four drifted boilerplate variants; `locks.py` has two genuine concurrency bugs; and two `override_markers`/scope-cut detectors fire on benign text. Two of those mis-fires are named false positives with reproducible triggers.

Global constraint (binding): **external contracts are frozen unless an item says otherwise.** Every Layer 3 tool's CLI subcommand name, verdict JSON shape, severity names, and canonical fixture round-trips keep passing; review-evidence schema v7 is unchanged; the 19 slash-command surfaces are unchanged. Structural tests may be edited ONLY where they pin text this run deliberately changes (pure narrative, stale tool vocabulary, boilerplate wording) — every edited test is enumerated with its reason in the implementing dev's report.

## What Changes

- **R1 — Scope-discipline + marker consolidation (REQ-R1, behavior-preserving + 2 named false-positive fixes).** Move the duplicated constants/helpers (`_utc_now_iso` ×4, `_load_json` ×3 with a deliberately-unified `load_json(path, *, missing_ok)`, JSONL readers ×3, two localhost lists, pipeline-name lists ×3) to a single shared home; author a `## Scope-fidelity discipline family (v3.10.0)` CPC section folding the five scattered tables; fix `detect_virtue_framed_override` proximity and prune the standalone admission phrases.
- **R2 — Split the `vao_tools.py` monolith (REQ-R2, zero behavior change).** Split into a `hooks/vao/` package of ≤900-line per-family modules; `vao_tools.py` remains a ≤400-line facade re-exporting EVERY test-referenced public function (20) AND underscore constant (18) AND helper (3); CLI byte-identical.
- **R3 — Narrative diet (REQ-R3, no operative-rule loss).** Restructure `CLAUDE.md` operative-first (≤350 lines); compress CPC narrative ≥30% with zero rule loss; collapse the duplicated pipeline-body blocks to canonical references + minimal inline operative stubs.
- **R4 — Agent hygiene sweep (REQ-R4, mechanical).** Remove `LS`/`NotebookRead` from frontmatter (30/8 files); fix write-without-`Write` contradictions; re-sync the four drifted boilerplate variants to canonical; fix invalid colors; document + fix the `scaffold-agent` orphan.
- **R5 — `locks.py` concurrency fixes (REQ-R5, bug fix).** `O_CREAT|O_EXCL` lock creation + intersecting-scope re-scan; `globs_intersect` prefix-vs-suffix candidate class.
- **R6 — New capabilities (REQ-R6, features).** `security-hunter` adversarial shape + `security-finding` SR origin kind + SR-catalog fork reconciliation; an `## Accessibility axis (v3.10.0)` for interaction-completeness with `a11y-gap` findings; an unbounded-run `heartbeat` notify event + `heartbeat_snapshot` + CPC heartbeat discipline.
- **R7 — Discipline-detector applicability guards (REQ-R7, the folded SR).** `discipline_registry.py` prod-safe + multi-persona detectors gain applicability guards so a pytest-only no-UI repo records `not_applicable` instead of false-flagging 163 files / demanding a persona inventory; registry schema gains an auditable `{applied, not_applicable, reason}` state.

## Capabilities

### New Capabilities

- `review-improvements`: the second-tier review remediation — an internal-structure refactor (marker/helper consolidation, the `hooks/vao/` package split, the narrative diet, the agent hygiene sweep) that is behavior-preserving on every external contract, PLUS three net-new capabilities (the `security-hunter` adversarial shape, the interaction-completeness accessibility axis, the unbounded-run heartbeat), PLUS two bug-fix surfaces (the `locks.py` concurrency races and the discipline-detector applicability false positives), delivered so the plugin's maintainability and correctness improve without weakening any shipped gate.

### Modified Capabilities

No existing capability's behavioral requirement is weakened. R1/R2/R4 are behavior-preserving refactors verified by unchanged fixture round-trips + CLI subprocess tests. R5/R7 fix genuine bugs (the detectors stop mis-firing; the lock layer stops silently overwriting). R3 relocates narrative without losing an operative rule. R6 adds capability (a new adversarial shape, a new review axis, a new visibility event) without changing any existing gate's pass/fail logic. The `consolidate-duplicated-rules` and `exploration-pipeline` active OpenSpec changes are untouched.

## Impact

This repo is a Claude Code plugin: Markdown skills/agents/commands, JSON metadata, stdlib Python hooks + setup scripts, verified by a pytest self-suite. **No web/API/UI surface exists.** Every coverage-map entry is `layer: infra`; Playwright + dev-API integration criteria are recorded N/A with the authorization note *"no UI/HTTP surface; verification = pytest both encodings + real-subprocess CLI execution + openspec strict validation"* (Phase 1's loop conditions accept this recorded authorization).

**Four disjoint team scopes** (every production + test file enumerated in `tasks.md`; no file in two scopes):
- **py-core** — `hooks/vao_tools.py` + new `hooks/vao/*` + `hooks/shared_rule_constants.py` + new `hooks/shared_util.py` + `inflight_inbox.py` + `discipline_registry.py` + `skill_invocation_audit.py` + `pipeline-completion-audit.py` + `pretool_unilateral_override_guard.py` + `override_markers.py` + `review-gate-task.py` + `teammate-idle-check.py` → R1, R2, R7 + their Python-behavior tests.
- **py-locks** — `hooks/locks.py` only → R5 + a new `tests/test_locks_concurrency.py`.
- **py-notify** — `scripts/notify/notify.py` + `hooks/run_metrics.py` → R6c code + their tests.
- **md-docs** — `CLAUDE.md`, the touched `skills/*/SKILL.md`, `agents/*.md`, `scripts/setup/sync_agent_boilerplate.py`, `README.md`/`docs/CODEBASE_MAP.md`/`docs/INTEGRATION_MAP.md`/`CHANGELOG.md`, `.claude-plugin/plugin.json`+`marketplace.json` (3.10.0) + the Markdown-structural test files → R3, R4, R6a-doc, R6b-doc.

**Affected APIs / dependencies:** no new third-party dependency; Python stays stdlib-only. The only net-new import surface is the internal `hooks/vao/` package + `hooks/shared_util.py`, both consumed via the existing dual-form try/except pattern.

**Reuse-first decision summary:** EXTEND in place wherever possible — the five discipline tools' code contracts stay; `shared_rule_constants.py` is the existing home R1 consolidates into; `notify.py`/`run_metrics.py`/`adversarial-reviewer.md`/`interaction-completeness` are all extended, not replaced. Genuinely NEW: the `hooks/vao/` package modules (mechanical extraction of existing code — the facade preserves the import surface), `hooks/shared_util.py` (the single home for the deduplicated functions — no existing util module exists), the `heartbeat` event + `heartbeat_snapshot` (new visibility surface, no existing equivalent), `tests/test_locks_concurrency.py` + the other new test files, and the `security-finding-routed.json` fixture. Each NEW file carries a Reuse Decision in `design.md` citing CODEBASE_MAP.

## QA Guidance

This codebase has **no web application, no dev URL, no production system, and no API surface.** QA verifies via the pytest self-suite (run under BOTH default cp1252 and `PYTHONUTF8=1`) + real CLI/hook subprocess execution + `openspec validate --all --strict`, NOT via web testing.

### Acceptance Criteria

- [AC-1] **Marker/helper consolidation + false-positive fixes (REQ-R1, REQ-R7).** Covers **R1a** (one definition each of `_utc_now_iso` / `load_json` / the JSONL reader, imported via dual-form everywhere; `_load_json` semantics deliberately unified with per-call-site fail-open/fail-closed preserved + tested), **R1b** (the two localhost lists unified into one union constant; both tools' fixture verdicts unchanged), **R1c** (the `## Scope-fidelity discipline family (v3.10.0)` CPC section names the five disciplines as one family with the 3-disposition model + a firing-moment table), **R1d** (`detect_virtue_framed_override` requires proximity for a single opener+admission pair; the benign sentence does NOT fire, the canonical v3.0.0 fixture STILL fires), **R1e** (standalone admission phrases only count adjacent to a scope-cut phrase; fixtures still fire, benign text does not), **R7** (the prod-safe + multi-persona detectors record `not_applicable` on this no-UI repo; the registry schema gains `{applied, not_applicable, reason}`; `verify-discipline-registry-current` against this repo yields `valid:true` with both disciplines `not_applicable`).
- [AC-2] **The `hooks/vao/` package split is behavior-preserving (REQ-R2).** Covers the partition into ≤900-line per-family modules; `vao_tools.py` ≤400-line facade re-exporting all 20 verify_ functions + 18 underscore constants + 3 helpers (the grep-derived list in `design.md`); `python -m pytest` green with ZERO test edits attributable to R2 (a broken test reveals a missed re-export — fix the facade); `tests/test_vao_glue_execution.py` (real-subprocess CLI) green; every Layer 3 fixture round-trips unchanged; CLI byte-identical.
- [AC-3] **The narrative diet loses no operative rule (REQ-R3).** Covers `CLAUDE.md` ≤350 lines operative-first with every relocated fact verified present in CHANGELOG/CODEBASE_MAP first; CPC ≥30% line reduction with every kept RULE intact; the pipeline bodies collapsed to canonical references + minimal inline operative stubs (the abort condition stays inline per body); every edited structural test justified as narrative-pinning and enumerated; the count/version facts in `CLAUDE.md` still exactly true; before/after line+word counts reported.
- [AC-4] **Agent hygiene + locks fixes + new capabilities land (REQ-R4, REQ-R5, REQ-R6).** Covers **R4** (zero `LS`/`NotebookRead` tokens in `agents/*.md` frontmatter; all 3 allowlists updated; `Write` granted to test-completeness-verifier + qa-replayer with bounded-scope notes; the analysis-only exemption sentence added to bug-classifier + codebase-map-reviewer; boilerplate hash-identical across all 34 or canonical + enumerated blessed additions; colors mapped to the palette + `VALID_COLORS` assertion; `scaffold-agent` vocabulary fixed + documented), **R5** (the `O_CREAT|O_EXCL` lock + intersecting-scope re-scan + `globs_intersect` prefix/suffix candidate; the `("src/**","**/auth.py")` case returns True; threaded stress test → exactly one winner; `cdlg_overlap` unchanged), **R6** (the `security-hunter` shape + trigger rules + `security-finding` origin kind + SR-catalog fork reconciliation; the `## Accessibility axis (v3.10.0)` + `a11y-gap` vocabulary; the `heartbeat` event + `heartbeat_snapshot` + CPC heartbeat discipline; new fixtures round-trip).
- [AC-5] **The full suite is green under both encodings + docs current + version bumped (run-level).** Covers `python -m pytest` fully green under default cp1252 AND `PYTHONUTF8=1` (final counts reported; all new tests additive); `openspec validate --all --strict` green (the 2 pre-existing active changes stay green); `plugin.json` + `marketplace.json` at 3.10.0; the CHANGELOG entry; `CLAUDE.md` (post-R3a) + `README.md` + `docs/CODEBASE_MAP.md` + `docs/INTEGRATION_MAP.md` reflecting the `hooks/vao/` layout, the new agent vocabulary, the new capabilities, and the new counts; every edited existing test enumerated with its reason.

### Unit Test Targets

- `hooks/shared_util.py:load_json` → `missing_ok=True` returns the default for a missing file; `missing_ok=False` raises; existing call-site fail-open/fail-closed semantics preserved (per-site tests).
- `hooks/vao_tools.py` (facade) → every one of the 20 verify_ functions + 18 underscore constants + 3 helpers is importable as `vao_tools.<name>` AND `from hooks.vao_tools import <name>`; identity round-trips against `hooks/vao/*`.
- `hooks/vao/*` modules → each ≤900 lines; each importable in both package and bare-module sys.path shapes.
- `hooks/override_markers.py:detect_virtue_framed_override` → the benign "You're right, and the roadmap doc is updated — let me know if you want more detail" does NOT fire; the canonical v3.0.0 fixture fires; a ≤500-char proximity window for a single opener+admission pair; document-wide pairing only with ≥2 admissions.
- `hooks/discipline_registry.py` → prod-safe detector counts only Playwright/QA-shaped files; multi-persona records `not_applicable` with no frontend markers; the registry schema carries `{applied, not_applicable, reason}`.
- `hooks/locks.py:acquire_lock` → N threads same scope → exactly one winner; identical-scope second acquire fails surfacing the holder; intersecting-scope earlier-acquired wins; stale-reclaim still works.
- `hooks/locks.py:globs_intersect` → `("src/**","**/auth.py")` → True (both directions); documented heuristic cases unchanged; `cdlg_overlap` unchanged.
- `scripts/notify/notify.py` → `heartbeat` accepted in `EVENT_TYPES`; offline/no-config = silent no-op exit 0.
- `hooks/run_metrics.py:heartbeat_snapshot` → returns {run-id, phase, elapsed, qa_cycle_count, agents_dispatched} from existing metrics + intake-state.
- `tests/fixtures/vao/security-finding-routed.json` → round-trips; `security-finding` in the SR catalog.

### Integration Test Targets

This repository has **no web/API integration surface**; its integration surface is real-subprocess CLI/hook execution + the OpenSpec + pytest gates:
- `tests/test_vao_glue_execution.py` (the execute-the-glue family) → every `commands/*.md` + `hooks/hooks.json` invocation resolves, exists, and runs without traceback / silent no-op — green AFTER the R2 package split (proves the facade CLI is byte-identical).
- Every Layer 3 tool's CLI subcommand (`python hooks/vao_tools.py <subcommand>`) → same argparse, exit codes, verdict files as pre-split (the frozen external contract).
- `openspec validate --all --strict --json` → `valid:true` for `review-improvements`; the 2 pre-existing active changes stay green.
- `python -m pytest` → full suite green, run once under default Windows cp1252 and once under `PYTHONUTF8=1`.

### Playwright Flows

**Zero Playwright flows.** This codebase is a Claude Code plugin with no web UI, no rendered pages, and no dev URL — nothing for a browser to drive. The `### Playwright Flows` subsection is present (structural-contract requirement) but enumerates no flows; the browser-flow verification it normally represents is replaced for this plugin by the real-subprocess CLI/hook execution family. Note the irony that this run ADDS an accessibility axis (R6b) and a prod-safe-test discipline guard (R7) — both of which are `n/a` for this repo's own no-UI shape, which is exactly what R7 makes auditable. mini-qa / the QA gate verifies via pytest + CLI execution.

### Out of Scope

QA MUST NOT:
- Do any live web testing, browser automation, or dev-server interaction — there is no web surface.
- Touch any production system, deployed URL, or external service — none exist for this plugin.
- Run destructive git operations (`stash` / `reset --hard` / `rebase` / `commit --amend` / `checkout` of another branch / `clean -f`) — the run is shared-tree-disciplined.
- Edit a structural test EXCEPT where it pins text this run deliberately changes (narrative, stale tool vocabulary, boilerplate wording); every such edit is enumerated with its reason. R2 specifically must produce ZERO test edits — a broken test there is a missed facade re-export.
- Touch the `consolidate-duplicated-rules` or `exploration-pipeline` active OpenSpec changes.
- Add or change runtime third-party dependencies — Python stays stdlib-only.
