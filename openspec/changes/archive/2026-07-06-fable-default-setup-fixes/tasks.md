# Tasks

## 1. Team A — setup hardening (REQ-001…REQ-005)
- [x] 1.1 setup.py: cartographer-missing output names kingbootoshi/cartographer + prints the two-step remediation; commands/architect-team-setup.md + README setup section document the source (REQ-001)
- [x] 1.2 setup.py: npm EACCES detection → non-persistent `--prefix ~/.local` retry + persistent-remediation message; failing test first via injected runner (REQ-002)
- [x] 1.3 setup.py: Python-deps ladder (uv --system → pip --user → --break-system-packages on the externally-managed marker), pip-absent hint, tiktoken added; failing tests first (REQ-003)
- [x] 1.4 setup.py: `--yes` flag + `CT6_SETUP_ASSUME_YES` env short-circuit for every consent prompt; failing test first; document both in commands/architect-team-setup.md (REQ-004)
- [x] 1.5 README: fix the five bare `/architect-team-setup` sites to `/architect-team:architect-team-setup`; sweep for any other bare instructional forms (REQ-005)

## 2. Team B — fable default (REQ-006…REQ-007)
- [x] 2.1 agents/*.md: all 39 frontmatter `model:` → `fable` (field-only edits) (REQ-006)
- [x] 2.2 NEW scripts/setup/set_default_model.py: `--model fable|opus|sonnet|haiku` rewrite + `--check` report, stdlib, idempotent; failing tests first (new tests/test_set_default_model.py) (REQ-006)
- [x] 2.3 tests/test_agents.py: add `fable` to VALID_MODELS + pin the uniform-fable state (REQ-006)
- [x] 2.4 setup.py handoff: Team A exposes the fable-availability heuristic printing the set_default_model remediation string (Team A owns the setup.py edit; Team B supplies the exact remediation string via SendMessage) (REQ-006)
- [x] 2.6 REQ-006 ripple: flip the 24 per-agent model-pin assertions across the 19 out-of-scope-at-authoring test files to fable (one-line each, comment naming set_default_model.py as the lever); full agent-test slice green (REQ-006)
- [x] 2.5 service_config.py: DEFAULT_MODEL=claude-fable-5, FALLBACK_MODEL=claude-opus-4-8, resolve_model(preferred, fallback, availability_checker=None), build_llm_client routes through it; failing tests first in tests/test_services_common.py; check_separation stays clean (REQ-007)

## 3. Gates + ship (REQ-008)
- [x] 3.1 Phase 3: schema-v7 evidence per team + independent task-reviewer + adversarial reviewer, both `pass` (all REQs)
- [x] 3.2 Phase 5: full pytest suite green (environment-explained split + this change's new tests) (REQ-008)
- [ ] 3.3 Phase 7: master review + independent audit `overall: pass`; openspec archive (REQ-008)
- [ ] 3.4 Phase 8: version bump 3.32.0 (plugin.json + marketplace.json), doc-updater + doc-currency audit pass, commit/push/merge (REQ-008)

## 4. Team C — gate fix (REQ-009, SR-gate-teammate-false-block)
- [x] 4.1 tests/test_pretool_skill_gate.py: failing regression tests FIRST for both captured manifestations (teammate-transcript shape M1; Lead-transcript-with-peer-messages shape M2) (REQ-009)
- [x] 4.2 hooks/pretool_skill_gate.py: arm-1 teammate/sidechain standdown (mirror arm 2) + exclude teammate-message user-role records from the genuine-prompt anchor (REQ-009)
- [x] 4.3 Full gate test file green including all pre-existing false-block-safety + genuine-catch pins (REQ-009)

## 5. Team D — locks flake (REQ-010, SR-locks-flake)
- [x] 5.1 Diagnostic research: 3 researchers -> architect-consolidated plan at .architect-team/diagnostic-research/locks-flake/ (REQ-010)
- [x] 5.2 Fix team implements per plan (pre-fix verification checklist first); TDD (REQ-010)
- [x] 5.3 Determinism proof: 50x test-file green + 3x full-suite green; gates pass (REQ-010)
