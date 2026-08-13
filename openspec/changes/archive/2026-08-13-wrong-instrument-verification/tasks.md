# Tasks: wrong-instrument-verification

## 1. The engine — `verify-claim-instrument-binding`
- [ ] 1.1 Read `hooks/vao/check_integrity.py` in full; establish what the existing tool already answers
- [ ] 1.2 Design the discriminating-witness contract; record what was rejected and why
- [ ] 1.3 Red-first per rule, with the actual red output captured
- [ ] 1.4 Both directions per rule: fires on the defect, silent on the honest counterpart
- [ ] 1.5 Mutation witness per rule, classified by EXIT CODE with a changed-file sha256 assertion
- [ ] 1.6 Facade re-export + CLI subcommand matching the existing 22 tools' verdict shape exactly

## 2. The discipline
- [ ] 2.1 Decide: new eighth principle, or a sharpening of "Evidence before assertion"
- [ ] 2.2 Author the statement + its named anti-pattern in ETHOS voice
- [ ] 2.3 The operational rule — checkable at the moment a claim is written
- [ ] 2.4 The claim-shape / wrong-instrument / discriminating-instrument table, grounded in the five witnesses
- [ ] 2.5 State the honest boundary — what the discipline cannot catch

## 3. Wiring — the check must be reached, not merely available
- [ ] 3.1 Decide the reach point (review-gate evidence field, Phase 8 arm, or both) and justify it
- [ ] 3.2 Wire it; confirm by execution that an unbound claim is actually caught
- [ ] 3.3 Confirm a well-bound claim passes — an over-firing gate gets disabled and helps nobody

## 4. Acceptance against the corpus
- [ ] 4.1 State per witness whether the tool catches it, exactly; name the misses
- [ ] 4.2 Confirm every witness would have passed `verify-check-can-fail` (proving the gap is real)

## 5. Ship
- [ ] 5.1 Version bump across plugin.json + marketplace.json + CHANGELOG.md, dispatch pin in lockstep
- [ ] 5.2 Layer-3 tool count 22 -> 23 everywhere it is asserted
- [ ] 5.3 Frozen-tree, hash-bracketed suite measurement under both encodings
- [ ] 5.4 Publish; verify by execution against the INSTALLED copy
