# claude-compliance-compaction (v3.61.1)

## Why

The user asked for a review of the codebase with fixes to "optimize and
maximize claude compliance". The repo ships its own deterministic engines for
exactly that question, so the review ran them first: `instruction_compliance.py`
(120 files, 0 findings), `compile_skills.py --check` (in sync),
`capability_index.py` (fresh), `changelog_check.py --require-measurements`
(backed). The machine tier was clean; the two real findings sat above it.

## What

- **C1 — CLAUDE.md compacted 54,293 → 17,345 bytes (−68%).** The repo's own
  `claude_md_efficiency.py` assessor flagged it high/over-budget, and it is
  the file every session loads. The Stack essays (30.7KB) and the 9,535-byte
  Current-shape sentence duplicated `docs/CODEBASE_MAP.md` /
  `docs/CAPABILITY_INDEX.md` / `CHANGELOG.md` / `docs/RELEASE_HISTORY.md`.
  A ten-phrase orphan-fact sweep verified every distinctive fact lives in 2–4
  canonical docs before anything was cut. The three-release digest convention
  and the Conventions section were carried byte-identical (tail splice, not
  retyped). Honest residual: 17,345 bytes is still above the engine's
  2,048-byte pointer budget — deliberate, because the digests and operative
  conventions live inline by house convention; the assessor is advisory for
  this repo (not suite-gated) and the distance is stated.
- **C2 — the tests badge pinned.** The version badge got its pin at v3.45.0
  after drifting three times in one run; the tests badge beside it got
  nothing — a pin that covered one of two badges. It drifted three releases
  stale (7375 vs 7627), and the new test's FIRST RUN caught it drifted again
  (7655 vs the published 7656 — left over from the v3.61.0 count
  oscillation). Pinned to the CHANGELOG top entry's suite-total count, which
  is measurement-backed at release, so the badge chains to the recorded
  artifact. Mutation-witnessed both directions.

## Explicitly NOT done

- No wholesale 2,048-byte CLAUDE.md: it would evict the digest convention and
  the operative conventions, trading a purist number for worse compliance.
- No new lint dimensions in `instruction_compliance.py`: zero findings across
  the current dimensions gave no evidence a new dimension is where drift
  actually happens; the two live drifts found were both COUNT surfaces, and
  C2 closes that channel at its only unpinned point.
