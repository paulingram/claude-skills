# Tasks

Four teams with **strictly disjoint file scopes** — every production AND test file appears under exactly one team. Read `design.md` first: Decision 1 (R2 partition + the EXACT 41-name facade re-export list), Decision 2 (R2-before-R1 sequencing in py-core), Decision 3 (the cross-team resolutions), Decision 4 (the R3b diet protocol). Those pins remove all dev judgment calls.

Global constraint: **external contracts frozen.** A structural test may be edited ONLY where it pins text this run deliberately changes; every edit is enumerated with its reason in the dev report. R2 must produce ZERO test edits (a break there is a missed facade re-export → fix the facade).

## Team file partition (no file in two scopes)

### Team PY-CORE (R1, R2, R7) — Python hooks + their behavior tests
**Production files owned:**
- `hooks/vao_tools.py` (→ facade) · NEW `hooks/vao/__init__.py` · NEW `hooks/vao/core.py` · NEW `hooks/vao/oracle.py` · NEW `hooks/vao/fake_data.py` · NEW `hooks/vao/live_verification.py` · NEW `hooks/vao/persona.py` · NEW `hooks/vao/scope.py` · NEW `hooks/vao/deferral.py` · NEW `hooks/vao/prod_safety.py` · NEW `hooks/vao/registry_inflight.py` · NEW `hooks/vao/deploy_pipeline.py`
- NEW `hooks/shared_util.py` · `hooks/shared_rule_constants.py`
- `hooks/inflight_inbox.py` · `hooks/discipline_registry.py` · `hooks/skill_invocation_audit.py` · `hooks/pipeline-completion-audit.py` · `hooks/pretool_unilateral_override_guard.py` · `hooks/override_markers.py` · `hooks/review-gate-task.py` · `hooks/teammate-idle-check.py`

**Test files owned:**
- NEW `tests/test_vao_facade_reexports.py` (R2 safety net) · NEW `tests/test_shared_util.py` (R1a) · NEW `tests/test_override_markers_proximity.py` (R1d/R1e) · NEW `tests/test_discipline_applicability.py` (R7)
- `tests/test_shared_rule_constants.py` (EDIT only if R1/R2 shift its imports — enumerate) · `tests/test_no_pipeline_bypass_discipline.py` + `tests/test_unilateral_override_discipline.py` (module-style `from hooks import vao_tools` — must stay green post-split; EDIT only if a moved constant breaks them, which the facade prevents) · the existing per-tool VAO behavior tests + fixtures (`tests/test_vao_*.py`, `tests/fixtures/vao/*` — must stay GREEN UNCHANGED under R2; any edit is an R2 bug) · `tests/test_vao_glue_execution.py` (real-subprocess CLI — must stay green; NOT edited)

**Tasks:**
- [x] PC-1 (R2, FIRST) Split `vao_tools.py` into the 11 `hooks/vao/*` modules per `design.md` Decision 1a (each ≤900 lines; if a module exceeds, split by tool with the facade importing both). Constants live with their primary consumer; cross-module constants move to `hooks/vao/core.py`.
- [x] PC-2 (R2) Reduce `hooks/vao_tools.py` to a ≤400-line facade re-exporting ALL 41 names in `design.md` Decision 1b (20 functions + 18 constants + 3 helpers) via dual-form `from hooks.vao.<module> import ...`, and KEEP the argparse `if __name__=="__main__":` block in the facade byte-identical (same 22 `verify-*` subcommands, exit codes, verdict writes).
- [x] PC-3 (R2) Author `tests/test_vao_facade_reexports.py`: assert all 41 names are `dir(vao_tools)` members AND each `vao_tools.<name> is hooks.vao.<module>.<name>` (identity = re-export not re-definition). Run `python -m pytest` + `tests/test_vao_glue_execution.py`: green with ZERO edits to existing VAO tests/fixtures (a break ⇒ missed re-export ⇒ fix facade).
- [x] PC-4 (R1a, after R2) Create `hooks/shared_util.py` with `load_json(path, *, missing_ok)` + `_utc_now_iso` + the unified JSONL reader. Replace the duplicate definitions in `hooks/vao/*` (post-split), `inflight_inbox.py`, `discipline_registry.py`, `skill_invocation_audit.py`, `pipeline-completion-audit.py` with dual-form imports. Unify `_load_json` semantics: `missing_ok=True` returns default (the pipeline-completion-audit None-on-missing behavior), `missing_ok=False` raises (the vao_tools behavior) — preserve each call site's fail-open/fail-closed by passing the right flag; test each. Document `scripts/phenotypes/phenotypes.py` as out of scope (independent subsystem; keeps its own helper).
- [x] PC-5 (R1b, after R2) Define the localhost union constant once in `hooks/vao/live_verification.py`; point both former consumers at it; ensure the facade re-exports it under `_LOCAL_ENV_HOST_PATTERNS` (the test-referenced name). Prove both tools' fixture verdicts unchanged (existing VAO tests stay green).
- [x] PC-6 (R1d) In `hooks/override_markers.py` `detect_virtue_framed_override` (~223–259): require proximity (same paragraph or ≤500-char window) for a single opener+admission pair; keep document-wide pairing only with ≥2 distinct admissions. Add to `tests/test_override_markers_proximity.py`: the benign "You're right, and the roadmap doc is updated — let me know if you want more detail" does NOT fire; the canonical v3.0.0 fixture STILL fires.
- [x] PC-7 (R1e) Prune `_HONEST_SCOPE_STATEMENT_MARKERS`/admission lists so standalone "blueprint"/"roadmap"/"quick win"/"let me know if" count only adjacent to a scope-cut phrase. Canonical fixtures still fire; add benign non-firing tests (`tests/test_override_markers_proximity.py`).
- [x] PC-8 (R7) In `hooks/discipline_registry.py`: the prod-safe detector counts only Playwright/QA-shaped files (`*.spec.ts`/`*.spec.js` under e2e dirs, or py importing playwright); the multi-persona detector records `applicable=false` with no frontend markers. Add the `{applied, not_applicable, reason}` applicability field to the registry schema. `tests/test_discipline_applicability.py`: positive (webapp-shaped fixture still flags) + negative (this repo's shape records n/a); confirm `verify-discipline-registry-current` against this repo → `valid:true`, both disciplines `not_applicable`. Keep existing `tests/test_vao_discipline_registry.py` green (md-docs/py-core boundary: that file is py-core-owned; EDIT only if the schema addition requires it — enumerate).
- [x] PC-9 (R1, R7) Confirm the five scope-discipline tools' code contracts are UNCHANGED (R1c's family doc is md-docs's job; py-core only guarantees no code-contract change). Full suite + both encodings green for py-core-owned files.

### Team PY-LOCKS (R5) — locks.py only
**Production files owned:** `hooks/locks.py`
**Test files owned:** `tests/test_locks.py` (EDIT only for shifted line-number/narrative assertions — enumerate) · NEW `tests/test_locks_concurrency.py`
**NOT owned (do not touch — `cdlg_overlap`/worktree behavior unchanged):** `tests/test_cdlg_consumers.py`, `tests/test_worktree_state_resolution.py`

**Tasks:**
- [x] LK-1 (R5a) `acquire_lock` creates the lock with `os.open(path, O_CREAT|O_EXCL|O_WRONLY)`; existing file ⇒ acquisition fails surfacing the holder. Stale-lock reclaim integrates via atomic `os.replace` of a freshly-EXCL temp.
- [x] LK-2 (R5b) After a successful EXCL write, re-scan the lock dir; if another live lock has an intersecting scope and an earlier (acquired_at, session-id tiebreak), release own + return acquisition-failed naming the winner. Document the advisory-semantics boundary in the module docstring.
- [x] LK-3 (R5c) `globs_intersect`: add the prefix/suffix candidate (other glob's literal prefix + this glob's literal suffix → e.g. `src/`+`auth.py`); `("src/**","**/auth.py")` returns True both orders. Keep heuristic framing; `cdlg_overlap` unchanged.
- [x] LK-4 (R5d) NEW `tests/test_locks_concurrency.py` (mirror `tests/test_inflight_inbox_atomic.py`): N-thread same-scope → exactly one winner; intersecting-scope sequencing; the glob cases; stale-reclaim still works. Green on Windows (no `fcntl`); existing `tests/test_locks.py` green.

### Team PY-NOTIFY (R6c) — notify.py + run_metrics.py
**Production files owned:** `scripts/notify/notify.py` · `hooks/run_metrics.py`
**Test files owned:** `tests/test_notify_wiring.py` (+ any existing notify test — EDIT for the new event) · NEW `tests/test_heartbeat.py`
**NOTE:** the CPC `### Heartbeat discipline (v3.10.0)` SUBSECTION is md-docs-owned (it is Markdown in CPC). py-notify owns only the code (notify.py event + run_metrics snapshot) and its tests. Cross-team dependency: md-docs's heartbeat subsection references py-notify's event name `heartbeat` + the snapshot payload keys — both fixed here so md-docs can cite them.

**Tasks:**
- [x] NT-1 (R6c) `scripts/notify/notify.py`: add `heartbeat` to `EVENT_TYPES` (line ~45, 5→6); thread it through the dispatch + CLI `choices` (~167/380/447/474). Same opt-in/best-effort contract; offline/no-config = silent no-op exit 0.
- [x] NT-2 (R6c) `hooks/run_metrics.py`: add `heartbeat_snapshot(workspace, run_id)` returning {run-id, phase, elapsed-since-start, qa-cycle-count, agents-dispatched} from existing metrics (`read_run_metrics`) + intake-state. Reuse `_metrics_path`/existing readers; do not add a new file.
- [x] NT-3 (R6c) Tests: `tests/test_heartbeat.py` — notify CLI accepts `heartbeat` (offline = silent no-op); `heartbeat_snapshot` unit tests (payload keys, derivation from metrics+intake-state). `tests/test_notify_wiring.py` EDIT for the 6th event (enumerate: it pins the EVENT_TYPES list).

### Team MD-DOCS (R3, R4, R6a-doc, R6b-doc, R1c-doc, R6c-doc, version + docs) — Markdown + structural tests + version
**Production files owned:**
- `CLAUDE.md`
- `skills/common-pipeline-conventions/SKILL.md` (R1c family section + R3b diet + R6c heartbeat subsection + R6a/R6b cross-refs)
- `skills/architect-team-pipeline/SKILL.md` · `skills/bug-fix-pipeline/SKILL.md` · `skills/mini-architect-team-pipeline/SKILL.md` · `skills/ux-test-builder/SKILL.md` (R3c body diet)
- `skills/team-spawning-and-review-gates/SKILL.md` (R6a SR-catalog reconciliation + security-hunter trigger rules) · `skills/interaction-completeness/SKILL.md` (R6b accessibility axis)
- ALL `agents/*.md` (R4 sweep across 34; R6a `agents/adversarial-reviewer.md`; R6b `agents/interaction-reviewer.md`)
- `scripts/setup/sync_agent_boilerplate.py` (R4c — md-docs owns; py teams MUST NOT touch)
- `README.md` · `docs/CODEBASE_MAP.md` · `docs/INTEGRATION_MAP.md` · `CHANGELOG.md`
- `.claude-plugin/plugin.json` · `.claude-plugin/marketplace.json` (3.10.0)
- NEW `tests/fixtures/vao/security-finding-routed.json` (R6a fixture — Markdown/JSON doc artifact, md-docs owns it since it pairs with the team-spawning catalog doc; the round-trip test that loads it is md-docs-owned too)

**Test files owned (Markdown-structural — pin text md-docs changes):**
- `tests/test_agents.py` (R4a VALID_TOOLS ~47–52, R4d VALID_COLORS assertion NEW, R4a VALID_MODELS += `inherit`, R4b/R4c boilerplate + exemption assertions)
- `tests/test_interaction_completeness.py` (R4a allowlist ~65–66 + R6b a11y-axis section/vocab presence)
- `tests/test_doc_updater_agent.py` (R4a EXPECTED_TOOLS_IN_ALLOWLIST line 27 — drop `LS`)
- `tests/test_skills.py` (R3b/R1c CPC structure — EDIT only for narrative-pinning per Decision 4)
- The discipline-structural families whose assertions the R3b/R3c diet touches — EDIT only where they pin removed NARRATIVE (transcript quotes / version anecdotes), enumerate each; where they pin a RULE the text stays. Candidate set to triage (grep-confirmed to assert CPC/pipeline-body text): `tests/test_no_end_of_run_deferral_discipline.py`, `tests/test_in_flight_clarification_discipline.py`, `tests/test_inflight_injection_discipline.py`, `tests/test_deploy_mandate_discipline.py`, `tests/test_discipline_registry_discipline.py`, `tests/test_dispatch_mode_section.py`, `tests/test_frontend_missing_api_discipline.py`, `tests/test_multi_persona_path_coverage_discipline.py`, `tests/test_dynamic_affordance_discovery_discipline.py`, `tests/test_agent_resume_discipline.py`, `tests/test_data_engineering_discipline.py`, `tests/test_bug_isolation_reorder.py`, and the pipeline-body prerequisite/dispatch tests. NEW `tests/test_security_hunter_shape.py` (R6a) + NEW `tests/test_a11y_axis.py` (R6b) + NEW `tests/test_scope_fidelity_family.py` (R1c section presence).

**NOTE (R6a fixture ownership):** `tests/fixtures/vao/security-finding-routed.json` is a doc/catalog artifact, but its round-trip test asserts the SR catalog (a Markdown doc in team-spawning). To keep the disjointness rule clean, md-docs owns BOTH the fixture and its round-trip test (`tests/test_security_hunter_shape.py`). py-core does NOT add `security-finding` handling to any verify_* tool (it is an SR origin kind in the catalog doc + spawn-brief routing, not a Layer 3 verdict severity) — so no py-core/md-docs collision.

**Tasks:**
- [x] MD-1 (R1c) Author `## Scope-fidelity discipline family (v3.10.0)` in CPC: name the five disciplines as one family, the 3-disposition model, the firing-moment comparison table; fold the five scattered neighbor-comparison tables (preserve firing-moment distinctions). NEW `tests/test_scope_fidelity_family.py` asserts the section + table presence.
- [x] MD-2 (R3a) Diet `CLAUDE.md` to ≤350 lines operative-first: codebase-overview facts + `## Recent releases` (≤3 versions, ≤3 sentences each) + CHANGELOG pointer. Before deleting any sentence, verify the fact in CHANGELOG/CODEBASE_MAP; if CLAUDE.md-only, append to the matching CHANGELOG entry FIRST. Keep count/version facts exactly true.
- [x] MD-3 (R3b) Diet CPC ≥30% per Decision 4 (trim narrative → run targeted structural tests → narrative-pinning edits updated+enumerated, rule-pinning text stays). 
- [x] MD-4 (R3c) Collapse the four pipeline bodies' duplicated `## Plugin prerequisites` + dispatch re-spelling + v2.18/v2.19/v2.20/v3.0 bash blocks to one-line CPC references + the minimal inline abort stub (one sentence/body); move the bash invocations to a single parameterized CPC invocation table. Update + enumerate the per-body structural tests.
- [x] MD-5 (R3d) Re-measure: before/after line+word counts for CLAUDE.md, CPC, the 4 pipeline bodies.
- [x] MD-6 (R4a) Remove `LS` (30 files) + `NotebookRead` (8 files) from `agents/*.md` frontmatter (keep NotebookEdit). Update `tests/test_agents.py` VALID_TOOLS, `tests/test_interaction_completeness.py`, `tests/test_doc_updater_agent.py` EXPECTED_TOOLS_IN_ALLOWLIST; add `inherit` to VALID_MODELS.
- [x] MD-7 (R4b) Grant bounded `Write` to `agents/test-completeness-verifier.md` + `agents/qa-replayer.md` (tools + bounded-write note, task-reviewer pattern); add the analysis-only exemption sentence to `agents/bug-classifier.md` + `agents/codebase-map-reviewer.md` checkpoint blocks.
- [x] MD-8 (R4c) Re-sync git-discipline + checkpoint boilerplate across all 34 agents via `scripts/setup/sync_agent_boilerplate.py` (extend it for these blocks); restore oracle-deriver's dropped `$BASELINE_SHA`; move blessed per-agent additions outside the canonical block; fold the R4b exemption as conditional canonical phrasing.
- [x] MD-9 (R4d) Map colors (domain-researcher amber→yellow, integration magenta→pink, test-run-watcher+monitor-synthesizer teal→cyan); add VALID_COLORS assertion to `tests/test_agents.py`.
- [x] MD-10 (R4e) Fix `scaffold-agent` stale LS/NotebookRead/Task vocabulary → R4a vocabulary; document it (README agents inventory + docs/CODEBASE_MAP.md). Keep it.
- [x] MD-11 (R6a) Add `security-hunter` as the 6th adversarial-reviewer shape in `agents/adversarial-reviewer.md`; document the trigger rules in `skills/team-spawning-and-review-gates/SKILL.md`; add `security-finding` to the SR origin-kind catalog; reconcile the closed-enum → open canonical catalog fixing `integration-failure`→`integration-test-failure` + `visual-fidelity-cascade`→`visual-fidelity-drift` across the two routing lists (team-spawning ~361, architect-team-pipeline ~473). NEW `tests/fixtures/vao/security-finding-routed.json` + `tests/test_security_hunter_shape.py` (round-trip + shape + triggers + origin-kind-in-catalog + zero-fork grep).
- [x] MD-12 (R6b) Add `## Accessibility axis (v3.10.0)` to `skills/interaction-completeness/SKILL.md` + `## Accessibility audit (v3.10.0)` to `agents/interaction-reviewer.md`; `a11y-gap` vocabulary (keyboard-unreachable/missing-accessible-name/axe-violation) + origin kind `a11y-gap` + the n/a rule. NEW `tests/test_a11y_axis.py` (section + vocab presence); update `tests/test_interaction_completeness.py` for the new section.
- [x] MD-13 (R6c-doc) Add `### Heartbeat discipline (v3.10.0)` under CPC `## Unbounded solving discipline` referencing py-notify's `heartbeat` event + `heartbeat_snapshot` payload keys (>30-min phase + post-first-hour phase-boundary refresh of `.architect-team/in-progress.md` + emit; never gates/caps).
- [x] MD-14 (version + docs) Bump `.claude-plugin/plugin.json` + `marketplace.json` to 3.10.0; author the CHANGELOG 3.10.0 entry (design.md Decision 6 skeleton); update README + docs/CODEBASE_MAP.md (the `hooks/vao/` package layout, the new agent vocabulary, the new capabilities, scaffold-agent row, new counts) + docs/INTEGRATION_MAP.md (the heartbeat event contract + security-finding/a11y-gap origin kinds + the facade↔package relationship). Backfill final test counts after all teams land (X-3).

## Cross-cutting (orchestrator-run, not a file scope)

- [x] X-1 (run-level) After all teams land, run the FULL suite once under default Windows cp1252 and once under `PYTHONUTF8=1`; both green, all new tests additive. Report final counts (they grow from 4097).
- [x] X-2 (validation gate) `openspec validate --all --strict --json` from the worktree root → `valid:true` for `review-improvements`; the 2 pre-existing active changes (`consolidate-duplicated-rules`, `exploration-pipeline`) stay green.
- [x] X-3 (post-run counts) Final test + test-file counts backfilled by MD-DOCS into CLAUDE.md / README / CODEBASE_MAP / the CHANGELOG entry (FRONTEND/md-docs owns those files; values known only after all teams' tests land). The v3.9.3 lesson: the count reconciliation runs THIS run, pinned post-run — no deferral.

## Enumerated existing structural tests each team MAY update (with reason)

| Test file | Team | May edit? | Reason |
|---|---|---|---|
| `tests/test_shared_rule_constants.py` | py-core | only if imports shift | R1/R2 may move a constant it imports (enumerate) |
| `tests/test_no_pipeline_bypass_discipline.py`, `tests/test_unilateral_override_discipline.py` | py-core | must stay green; edit = R2 bug | module-style `from hooks import vao_tools`; facade keeps them passing |
| `tests/test_vao_*.py` + `tests/fixtures/vao/*` (existing) | py-core | NO (R2 acceptance) | a break ⇒ missed re-export ⇒ fix facade not test |
| `tests/test_vao_glue_execution.py` | py-core | NO | CLI byte-identical by contract |
| `tests/test_vao_discipline_registry.py` | py-core | only if R7 schema add requires | enumerate the applicability-field assertion |
| `tests/test_locks.py` | py-locks | only shifted line/narrative assertions | R5 changes acquire_lock/globs_intersect internals |
| `tests/test_cdlg_consumers.py`, `tests/test_worktree_state_resolution.py` | (none) | NO | `cdlg_overlap`/worktree behavior unchanged |
| `tests/test_notify_wiring.py` | py-notify | YES | pins EVENT_TYPES (5→6); enumerate |
| `tests/test_agents.py` | md-docs | YES | R4a VALID_TOOLS, R4d VALID_COLORS (new), R4a VALID_MODELS += inherit, R4b/R4c assertions |
| `tests/test_interaction_completeness.py` | md-docs | YES | R4a allowlist ~65–66 + R6b a11y section/vocab |
| `tests/test_doc_updater_agent.py` | md-docs | YES | R4a EXPECTED_TOOLS_IN_ALLOWLIST line 27 drops LS |
| `tests/test_skills.py` | md-docs | only narrative-pinning | R3b/R1c CPC structure per Decision 4 |
| the R3b/R3c discipline-structural families (enumerated in MD-DOCS test list) | md-docs | only narrative-pinning | each edit justified: pinned a transcript quote / version anecdote, not a rule (Decision 4) |

NEW test files (no edit conflict, each one owner): py-core — `test_vao_facade_reexports.py`, `test_shared_util.py`, `test_override_markers_proximity.py`, `test_discipline_applicability.py`. py-locks — `test_locks_concurrency.py`. py-notify — `test_heartbeat.py`. md-docs — `test_security_hunter_shape.py`, `test_a11y_axis.py`, `test_scope_fidelity_family.py`, fixture `security-finding-routed.json`.

If a fix forces a change to another team's owned test, the owning team makes the edit and the other team surfaces an SR rather than reaching across the boundary. All known boundary cases are enumerated above; none requires a shared file.
