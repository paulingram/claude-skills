# Tasks: compact-readme-release-history

## 1. Restructure (owner: docs-mover teammate)

- [ ] 1.1 Write the NEW structural pin tests (tests/test_release_history.py) and RUN them against the pre-change tree — naturally RED (7 spotlights, no history file); capture the red
- [ ] 1.2 Build the extraction verification script (scratch): record move-set regions + per-region SHA-256 from the pre-change README
- [ ] 1.3 Create docs/RELEASE_HISTORY.md per design D2 (header + current v3.47.0 section + moved regions in order); rewrite README.md (spotlight + pointer + durable content; banner 3.46.0 -> 3.47.0)
- [ ] 1.4 Run the verification: every region byte-identical in RELEASE_HISTORY.md, gone from README; artifact captured to .architect-team/demos/
- [ ] 1.5 Cross-references: CLAUDE.md docs list + docs/CODEBASE_MAP.md doc inventory name the new file
- [ ] 1.6 Slice green both encodings: test_release_history.py + test_readme_styling.py (banner pin flips red->green) + the README pin families; flag any pin retarget explicitly
- [ ] 1.7 Evidence (schema v7) with the check-can-fail artifact for the added test file (red cited); signal ready for review

## 2. Close-out (orchestrator)

- [ ] 2.1 Paired reviews (independent + adversarial: extraction-fidelity attacks) to pass
- [ ] 2.2 Full suite zero failures; run-level check-can-fail verdict for this run's added tests; declared gates satisfied
- [ ] 2.3 Version 3.47.1 (both plugin JSONs); CHANGELOG entry per rubric; doc-updater + doc-currency audit (inventory includes the NEW docs/RELEASE_HISTORY.md)
- [ ] 2.4 Mine README + RELEASE_HISTORY into the palace (output captured); delivery manifest; completion audit exit 0; commit; merge to main per deploy config; mark complete
