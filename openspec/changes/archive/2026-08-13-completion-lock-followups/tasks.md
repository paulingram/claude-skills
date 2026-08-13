# Tasks: completion-lock-followups

## 1. N5b — a wedged run is silent, not just unreleased
- [ ] 1.1 Red-first: the lock emits a notification once it has blocked persistently
- [ ] 1.2 Red-first: no notification on an ordinary single block
- [ ] 1.3 Red-first: a notifier failure leaves exit code and block message unchanged
- [ ] 1.4 Red-first: the no-progress counter is NOT advanced by the notification path
- [ ] 1.5 Implement emission + persisted notified-state; mutation witness per property

## 2. F7 — task text cannot present as enforcement output
- [ ] 2.1 Red-first: a subject with bullet prefix and colon-terminated heading renders inert
- [ ] 2.2 Red-first: an ordinary subject stays readable
- [ ] 2.3 Implement the strip inside the clipper; mutation witness

## 3. N3 — the protected set is independent of the value under attack
- [ ] 3.1 Red-first: a redirected task root does not unprotect the real default root
- [ ] 3.2 Red-first: the configured root is still protected, so the test seam keeps working
- [ ] 3.3 Implement union resolution; mutation witness

## 4. N2b — hardlink identity
- [ ] 4.1 Red-first: a hardlink to the ledger under another name is refused
- [ ] 4.2 Red-first: an ordinary unrelated write is still allowed
- [ ] 4.3 Implement filesystem-identity comparison, fail-safe; mutation witness

## 5. The prose_lines vs line_count naming trap
- [ ] 5.1 Capture a characterization corpus of at least 25 turn shapes BEFORE any edit
- [ ] 5.2 Land the corpus as a permanent regression test
- [ ] 5.3 Make the distinction self-evident; prove full verdict equality
- [ ] 5.4 Mutation witness: swapping the counters must go red

## 6. G2 — answer the unverified precondition
- [ ] 6.1 Search the live transcripts for a harness-written user-role block record
- [ ] 6.2 Quantify the search scope so a null result is a finding rather than a shrug
- [ ] 6.3 Record the verdict and its consequence for G2

## 7. Mutation-harness classification
- [ ] 7.1 Convert the lock-wiring artifact to exit-code classification plus a changed-file assertion
- [ ] 7.2 Re-run the mutations for real; report any that flip classification

## 8. Ship
- [ ] 8.1 Update the follow-ups doc — closed versus still-a-boundary
- [ ] 8.2 Version bump 3.56.0 to 3.57.0 across plugin.json, marketplace.json, CHANGELOG.md
- [ ] 8.3 Frozen-tree, hash-bracketed suite measurement
- [ ] 8.4 Publish and verify by execution against the INSTALLED copy
