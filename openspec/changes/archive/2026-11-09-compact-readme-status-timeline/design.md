# Design: compact-readme-status-timeline

## Context

A docs-only PATCH finishing the README compaction v3.47.1 started. v3.47.1 moved the per-release NARRATIVE to `docs/RELEASE_HISTORY.md`; the one-line release timeline (the `STATUS` section's `▰▰▰` block) was kept and has since grown to ~135 lines. The user wants the README to carry only the most recent release plus a pointer, with the accumulated updates in their own docs file.

## Decisions

- **D1 — relocate, don't delete.** The one-line timeline is useful scannable content; it moves byte-faithful into `docs/RELEASE_HISTORY.md` (the file the README's pointer already promises) as a compact index above the detailed narrative, rather than being dropped. The narrative sections already in that file are untouched.
- **D2 — keep the STATUS section, shrink its body.** The README keeps a `STATUS` section (house aesthetic + `test_readme_styling.py` documents a timeline element in the *skill*, not a required full-timeline in the README) but its body becomes the current-release line + a pointer. This preserves the styled frame while satisfying "only the most recent release changes."
- **D3 — ship as v3.55.1, mirroring v3.47.1.** A README structural change to tracked docs is shipped versioned, exactly as v3.47.1 ("compact-readme-release-history — docs-only PATCH") did. All version-bearing surfaces move in lockstep; the `test_release_history.py` / `test_readme_styling.py` pins derive the expected version from `plugin.json`, so they stay green once every surface is bumped together.
- **D4 — the pins already guard the invariant.** `test_release_history.py` pins: exactly one spotlight == plugin.json version, a structure-anchored pointer block above the spotlight, RELEASE_HISTORY carries the current release, reaches `CARRIED FROM v2.3.0`, and names ≥55 release identities. The one-line timeline lines (`v0.1.0 ─ …`) match none of the release-identity grammars, so moving them changes no identity count in either file. Verified against the test source before editing.

## Risks / Trade-offs

- [A test requires the README to contain the full timeline] → verified NONE does: the only "timeline" test assertion targets `skills/readme-styling/SKILL.md`, not the README body; no test matches the `▰` frame or `v0.1.0 … initial release` in the README. The move is pin-safe.
- [The bump misses a version surface] → `test_readme_styling.py::test_readme_banner_version_matches_plugin_json` pins BOTH the ASCII banner (`v 3 . 55 . 1`) and the shields badge (`badge/version-3.55.1-`); `test_dispatch_banner.py` pins the banner constant; `test_release_history.py` pins the spotlight and the history's current-release line — a missed surface fails the suite loudly.
- [Content lost in the move] → the independent Documentation Currency Audit (producer≠checker) diffs the moved timeline against its new home and confirms every release line survived.

## Migration Plan

Docs-only; rollback = git revert. Version 3.55.0 → 3.55.1.
