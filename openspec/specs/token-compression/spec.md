# token-compression Specification

## Purpose
TBD - created by archiving change token-compression. Update Purpose after archive.
## Requirements
### Requirement: REQ-001 — The caveman compression engine (TC-2)

`scripts/token_compression/caveman.py` SHALL be a stdlib-only engine providing `compress(text)` — which reduces verbosity meaning-preservingly by dropping pure filler (articles, politeness, intensifiers/hedges) and wordy phrases while PRESERVING content words, identifiers, numbers, line structure, and fenced / inline code verbatim, and preserving prepositions/conjunctions/copulas — plus `estimate_tokens(text)` and `compression_stats(text)` (original-vs-compressed estimate + savings).

#### Scenario: compress drops filler, preserves content + code, and measures savings

- **WHEN** internal prose with filler and a code span is compressed
- **THEN** the filler words are gone, the content words / numbers / code span survive verbatim, line structure is preserved, and `compression_stats` reports a compressed token estimate ≤ the original

### Requirement: REQ-002 — The hard internal-only boundary (TC-1)

`skills/token-compression/SKILL.md` SHALL state, as a non-negotiable rule, that the transform applies ONLY to agents' INTERNAL communication (inter-agent messages, an agent's own scratch / internal notes) and is NEVER run on external output (the final answer to the user, API payloads, commits, file contents, PRs, emails, test output).

#### Scenario: the internal-only boundary is stated

- **WHEN** the skill body is read
- **THEN** it states "NEVER compress external output," distinguishes internal vs external, and enumerates the external surfaces

### Requirement: REQ-003 — Caveman style + heavier-package option (TC-2/TC-3)

The skill SHALL describe the "caveman" style and frame a heavier ML token-compression package (e.g. LLMLingua-style) as a third-party, app-layer option evaluated against the stdlib floor — NOT bundled into this stdlib-only plugin.

#### Scenario: TC-3 is honestly framed

- **WHEN** the skill's package-evaluation section is read
- **THEN** the stdlib caveman compressor is the floor and the ML package is a documented third-party app-layer option measured against `compression_stats`

### Requirement: REQ-004 — Honest boundary + reuse-first + currency

The skill SHALL disclaim that the transform is a lossy-of-filler heuristic (not a semantic ML compressor) and that token counts are estimates; Python SHALL stay stdlib-only; the release SHALL bump the version to 3.22.0 and bring the skill count current (47 skills).

#### Scenario: honest boundary + counts current

- **WHEN** the skill + version files + README + CLAUDE.md + CODEBASE_MAP are read
- **THEN** the heuristic + estimate disclaimers are present, the version is 3.22.0, and the inventories say 47 skills with a `token-compression` entry

### Requirement: REQ-005 — Tests green both encodings

A new test file SHALL cover filler drop + content/preposition retention, code + line-structure preservation, phrase subs, the boundary-space / unbalanced-backtick / compress-to-nothing edges, and the CLI; the full suite SHALL pass under both Windows cp1252 and `PYTHONUTF8=1`.

#### Scenario: suite green

- **WHEN** the suite runs under both encodings with `tests/test_token_compression.py` present
- **THEN** there are zero failures

