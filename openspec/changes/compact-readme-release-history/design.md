# Design: compact-readme-release-history

## Context

README.md (1,785 lines) carries ~636 lines of accumulated release narrative above ~1,000 lines of durable docs. The move-set is line-anchored (not version-anchored): the `### v` heading convention stops at v3.9.0 and the older history continues in a denser digest format to ~line 705. One pin test is RED on the checkout (banner 3.46.0 vs plugin.json 3.47.0) — inherited, fixed here. Both user decisions are ratified: option-A history-only extraction; complete-history convention (current release duplicated in history). The v3.47.0 enforcement stack applies to this run: added tests need captured reds + a check-can-fail verdict; declared gates are registered and audited; the final report's claims need citations.

## Goals / Non-Goals

**Goals**: byte-identical extraction with mechanical verification; a compact README (current spotlight + pointer + durable content); banner currency; structural enforcement of the new convention; cross-refs + palace updated; zero suite failures.

**Non-Goals**: option-B durable-content re-homing; any edit to moved history bytes; CHANGELOG.md changes; README aesthetic redesign (readme-styling elements preserved as-is — appearance_mode strict).

## Decisions

- **D1 — Extraction is script-verified, not eyeballed.** The mover writes a small verification script (scratch, not shipped) that records the move-set regions (start/end line anchors + SHA-256 per region) from the PRE-change README, performs the move, then verifies each region's bytes appear exactly once in RELEASE_HISTORY.md — the artifact (region table + hashes + verdict) lands in `.architect-team/demos/` as the byte-identical proof cited in evidence. Line-ending discipline: regions are compared on the file's stored bytes (the repo checkout is CRLF-normalized by git; comparing extracted-bytes-to-inserted-bytes within the same checkout sidesteps the LF/CRLF class entirely).
- **D2 — RELEASE_HISTORY.md shape**: a short header (title + one-line purpose + the convention statement "each release appends here; the README carries only the current spotlight") followed by the current v3.47.0 section, then the moved regions newest→oldest in their existing order. The header is NEW text (not moved bytes); everything below it is moved-or-duplicated bytes only.
- **D3 — README pointer**: a one-line, visually prominent pointer in the house style placed where the narrative began ("Full release history → docs/RELEASE_HISTORY.md"), inside a small divider block consistent with readme-styling; no other appearance change (strict mode).
- **D4 — The structural pin counts release sections mechanically**: NEW-IN spotlight-divider occurrences (the countable marker of a release block in this README's grammar) == 1, pointer string present, RELEASE_HISTORY.md exists + contains both the current version string and the earliest release marker ("v2.3.0" digest anchor). Red-first: run the new test against the PRE-change tree (naturally red: 7 spotlights, no history file) — the captured red is genuine without mutation.
- **D5 — Version lands as v3.47.1 PATCH** at Phase 8 (docs-only released-artifact change, house convention), with a rubric-conformant CHANGELOG entry and the doc-currency pass covering the new file in the inventory.
- **D6 — One teammate** (the restructure is one coherent file-scope) + the standard paired independent + adversarial reviewers; the adversary's shape: extraction-fidelity attacks (dropped/duplicated/reordered regions, hash mismatches, a pin quietly weakened).

## Reuse Decisions (per reuse-first-design)

| Proposed unit | Decision | Basis |
|---|---|---|
| `docs/RELEASE_HISTORY.md` | build-new doc | No existing docs/ file holds release narrative (CHANGELOG is the rubric-gated formal log, a different surface the user explicitly keeps; CODEBASE_MAP ledger notes are per-map provenance) |
| `tests/test_release_history.py` | build-new test file | House pattern: one structural-pin file per convention (cf. test_readme_styling.py); extending test_readme_styling.py was considered and declined — the convention spans two files (README + docs/RELEASE_HISTORY.md), outside that file's README-only charter |
| Everything else | extend existing | README.md, CLAUDE.md, docs/CODEBASE_MAP.md line edits; the mover's verification script is scratch (not shipped) |

## Risks / Trade-offs

- [A moved region silently altered] → D1's per-region SHA verification + the adversary's extraction-fidelity attacks.
- [A README pin referencing moved content breaks] → the pin surface is enumerated in the spec; each retarget is explicit in evidence; the full suite is the net.
- [The 6 historical NEW-IN blocks vs the pin's ==1 count: a future release adds a second spotlight] → that is exactly what the pin exists to catch (swap, not accumulate).
- [MemPalace mine flake (database locked)] → bounded in-turn retry per house rule; mining is idempotent.

## Migration Plan

Single-commit restructure on `architect-team/compact-readme-release-history`; auto-merge to main per deploy config. Rollback = git revert of the release commit (the byte-identical property makes the reverse move equally mechanical).

## Open Questions

None — both user decisions ratified in the refined brief.
