# design — docs-currency-v3-39-1

## Root cause

The v3.39.0 release commit updated the primary release surfaces (README NEW-IN block, CHANGELOG, CLAUDE.md header, map frontmatter note-ledgers) but did not sweep the maps' BODY sections or README's secondary current-state text. Those sections carry flat current-state assertions ("current: v3.38.0", "5467 pytest self-tests … 199 test files", the `tests-5467` badge) that no automated gate pinned against the shipped reality — the doc-currency audit checked the release's own diff surfaces, not the whole living set's current-state claims. The class of bug: **living docs asserting a prior release's facts as current**, invisible to diff-scoped doc review.

## Proposed fix (class-scoped)

Fix the CLASS, not just the 11 instances:

1. **Sweep** every stale current-state assertion in the living doc set to the verified v3.39.0 reality (5494 passing + 4 skipped, 200 test files, 48/39/23, current version 3.39.1 after the bump) — the 11 replicated violations plus anything the executable scan surfaces during verification. Historical narrative exempt (user-authorized); frozen docs untouched.
2. **Keep the detector.** The B1/B2 replication artifact `tests/bug-fix-docs-currency-v3-39-1/check_docs_current.py` ships permanently as the deterministic current-state scan (standalone, never pytest-collected — future releases can run it in their doc-currency step; its expected totals are read from the CHANGELOG top entry + plugin.json so it does not hard-pin this release's numbers). This converts the fix from an instance-patch into a re-checkable discipline — the generalization the B4 audit requires.
3. **Version machinery**: manifests → 3.39.1, CHANGELOG v3.39.1 entry (top only), `tests/test_dispatch_banner.py` pin → 3.39.1.

The CODEBASE_MAP Tests-section environment note's cross-encoding figures are stated as the verified totals (5494 + 4, 200 files, green under both encodings) without re-inventing per-OS collected-count variants — the honesty constraint from the refined brief.

## Dev Environment

N/A — this repo is a Claude Code plugin (markdown + stdlib Python); there is no deployed dev instance. The "live environment" for a docs bug is the repo working tree at HEAD: docs ship with the repo, and verification is the executed scan + the full pytest suite under both encodings (`python -m pytest -q` with and without `PYTHONUTF8=1`).

## Reuse Decisions

- **No new modules.** The fix edits existing docs + manifests + one existing test pin in place.
- `tests/bug-fix-docs-currency-v3-39-1/check_docs_current.py` (new file, authored at B1/B2 per the bug-fix pipeline's replication convention `tests/bug-fix-<bug-slug>/`): stdlib-only standalone script; deliberately NOT a pytest module (named `check_*`, module docstring states why) so the suite's collected total stays deterministic. Reuse ladder: no existing engine performs living-doc current-state scanning (the instruction-compliance lint at `scripts/compliance/instruction_compliance.py` targets AI-facing instruction files' structure, not release-fact currency — verified against CODEBASE_MAP's scripts inventory), so a new bounded artifact in the sanctioned bug-fix location is the minimal build-new.
- `tests/test_dispatch_banner.py`: extends the existing version-pin test in place (one-line acknowledgment — extends the REQ-6 pin at ~line 430).

## Error handling / rollback

Docs-only PATCH on branch `architect-team/docs-currency-v3-39-1`; a bad sweep is recoverable by reverting the branch. The merge to main happens only after the full gate chain (B4 generalization audit, B6 QA replay, B8 doc-currency audit + completion audit) passes.

## Testing

- The executed replication scan must flip fail→pass (the regression contract).
- Full pytest suite green under Windows cp1252 AND `PYTHONUTF8=1` (expected 5494 passing + 4 skipped; if the verified totals differ, docs carry the verified number — the refined brief's hedge).
- The v3.31.0 instruction-compliance gate rides the suite (commands/skills/agents untouched → expected clean).
