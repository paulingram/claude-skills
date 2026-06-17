## Why

CT6-6 §3 (TC-1…TC-3) asks to optimize agents' INTERNAL communication without harming their EXTERNAL communication — a "talk like a caveman" token-compression approach that lowers internal verbosity, plus evaluating available token-compression packages for developer agents. A full ML compressor (LLMLingua-style) is a third-party dependency; the in-repo, always-available deliverable is the discipline + a stdlib-only deterministic "caveman" baseline. The sixth and final in-repo component of the CT6-6 tier.

## What Changes

- **New deterministic engine** — `scripts/token_compression/caveman.py` (stdlib-only): `compress(text)` (meaning-preserving filler-drop + phrase-subs, preserving content/identifiers/numbers/line-structure/code verbatim), `estimate_tokens(text)`, `compression_stats(text)`. (REQ-001)
- **New skill** — `skills/token-compression/SKILL.md`: the caveman style (TC-2), the hard internal-only boundary (TC-1), and evaluating a heavier ML package (TC-3). (REQ-002, REQ-003)
- **Honest boundary + reuse + currency** — a lossy-of-filler heuristic (not semantic ML), token counts are estimates, never compress external output; Python stdlib-only; version bump to 3.22.0; skill 46→47. (REQ-004)
- **Tests** — `tests/test_token_compression.py` (filler drop + preservation + code + edges + CLI); suite green both encodings. (REQ-005)

## Capabilities

### New Capabilities

- `token-compression` — reduce the token cost of agents' internal communication via a deterministic "caveman" compressor, with a hard internal-only boundary and a documented path to a heavier ML package.

### Modified Capabilities

- None removed. The skill inventory grows by one; no new command/agent/Layer-3 tool. This completes the in-repo CT6-6 tier (components 1–6).
