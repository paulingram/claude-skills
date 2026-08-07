# Proposal: compact-readme-status-timeline

## Why

The README still embeds a full one-line release changelog — the `STATUS` section carries a `▰▰▰`-bordered timeline naming every release from `v0.1.0` through the current one (~135 lines that grows by one line every release). v3.47.1 already moved the accumulated per-release NARRATIVE to `docs/RELEASE_HISTORY.md` and kept only a swapped-per-release spotlight, but it deliberately left this one-line timeline in place. The user's mandate: **a more compact README — the README should contain only the most recent release's changes plus a direction to see the full history in the docs folder; the updates/changes belong in their own file in docs.** The embedded timeline is exactly that accumulated update history and belongs with the rest of the release history in `docs/`.

## What Changes

- **REQ-1 — the README carries no accumulated release timeline.** The `STATUS` section's full `v0.1.0 → vX.Y.Z` one-line timeline moves out of `README.md`. The README's `STATUS` section keeps the house `▰▰▰` aesthetic but names only the CURRENT release plus a house-style pointer to `docs/RELEASE_HISTORY.md` for the full timeline. The README keeps exactly one `NEW IN` spotlight (the current release) and its existing `RELEASE HISTORY` pointer block — unchanged conventions from v3.47.1.
- **REQ-2 — the full timeline lives in its own docs file.** The one-line timeline moves byte-faithful into `docs/RELEASE_HISTORY.md` as a compact "Release timeline at a glance" index near the top, above the detailed per-release narrative. Nothing is lost: `docs/RELEASE_HISTORY.md` is the complete history the README's pointer already promises.
- **REQ-3 — ship as a versioned docs PATCH + refresh the MemPalace + sweep docs current.** Bump `3.55.0 → 3.55.1` across the version source-of-truth (plugin + marketplace JSONs, CHANGELOG, the README version surfaces, the dispatch-banner pin, the CLAUDE.md digest, the RELEASE_HISTORY append) following the v3.47.1 "compact-readme" precedent; update the MemPalace with the latest changes; and run a comprehensive documentation-currency sweep to fix any stale current-state references the per-release sweeps missed (the known one: the CODEBASE_MAP "Currency note" pinned to the v3.49.0 inventory).

## Impact

- Docs-only. No source / test-behavior change; no new skill / agent / command / hook / Layer-3 tool. Inventory unchanged (53 skills / 39 agents / 25 commands / 7 hook scripts / 22 Layer-3 tools). Suite unchanged: 7019 passing + 6 skipped, 0 failed (both encodings) — the existing `test_release_history.py` / `test_readme_styling.py` / `test_dispatch_banner.py` pins re-derive from `plugin.json` and stay green after the bump. `check_separation` unaffected (docs tier, no `services/` change). HONEST BOUNDARY: this relocates content and refreshes currency; it changes no runtime behavior.
