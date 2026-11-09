# Tasks: compact-readme-status-timeline

Docs-only PATCH; both encodings green; instruction-compliance zero findings; producer≠checker on the currency audit.

## 1. README compaction (owner: Lead)

- [ ] 1.1 Move the `STATUS` section's `v0.1.0 → v3.55.0` one-line timeline out of `README.md`. Replace the `STATUS` section body with the current-release line (v3.55.1) inside the existing `▰▰▰` frame + a house-style pointer to `docs/RELEASE_HISTORY.md` for the full timeline.
- [ ] 1.2 Preserve the README house aesthetic + the pins: block-letter banner (`█`), gradient dividers (`█▓▒░`/`░▒▓█`), inventory grid (`┌─ SKILLS (53)`), LOGIC MAPS + gate glyph (`▣`), theme marker, exactly ONE `NEW IN` spotlight, the `RELEASE HISTORY` pointer block.

## 2. The full timeline in its own docs file (owner: Lead)

- [ ] 2.1 Add the one-line timeline to `docs/RELEASE_HISTORY.md` as a compact "Release timeline at a glance" index near the top (above the per-release narrative), extended with the v3.55.1 line. Nothing lost.
- [ ] 2.2 Append the `### v3.55.1` narrative section to `docs/RELEASE_HISTORY.md` (complete-history convention: the current release appears here too); keep the ≥55-identity completeness floor + the `CARRIED FROM v2.3.0` earliest anchor.

## 3. Version bump 3.55.0 → 3.55.1 (owner: Lead)

- [ ] 3.1 `.claude-plugin/plugin.json` + `.claude-plugin/marketplace.json` → 3.55.1; `tests/test_dispatch_banner.py` pin → 3.55.1.
- [ ] 3.2 `CHANGELOG.md` new v3.55.1 entry per rubric (top entry == plugin.json; a suite-total line present); README version surfaces (badge `version-3.55.1`, ASCII `v 3 . 55 . 1`, spotlight `NEW IN v3.55.1`); `CLAUDE.md` Current shape v3.55.1 + recent-releases digest (prepend v3.55.1, drop the oldest of three).

## 4. MemPalace + general currency (owner: Lead + doc-sweep)

- [ ] 4.1 Update the MemPalace with the latest changes (Runs A–F + v3.55.0 + this v3.55.1).
- [ ] 4.2 doc-sweep: currency sweep of CODEBASE_MAP / INTEGRATION_MAP / CAPABILITY_INDEX / ETHOS / other docs to v3.55.1; fix the CODEBASE_MAP "Currency note" (v3.49.0 → v3.55.1 live inventory). The 3 doc-tooling checks pass.

## 5. Review + ship (owner: Lead + system-architect)

- [ ] 5.1 Independent system-architect Documentation Currency Audit (producer≠checker): README compact + no lost content + version literals current + RELEASE_HISTORY complete + cross-refs resolve.
- [ ] 5.2 Full suite both encodings (7019/0/6, no NEW failures); `check_separation` unaffected; `openspec validate --all --strict` clean; completion audit exit 0.
- [ ] 5.3 Commit (author override Paul Ingram; Co-Authored-By Claude Opus 4.8), merge --no-ff to main, push.
