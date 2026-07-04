# Design — doc-currency-refresh

## Context

The deliverable is a verifiable currency + disposition state for the CT6 plugin's non-instruction documentation surface, not new machinery. The maps' re-verification is already done (Phase −1, committed, stamps `2026-07-04`); the gated 7-file inventory was audited-PASS 2026-07-03; the three non-archived OpenSpec changes are verified-shipped. So the work is: (1) enumerate the corpus deterministically, (2) assign a per-file verdict with evidence, (3) execute the sanctioned dispositions (in-place fix / freeze / archive-move / tool-archive), and (4) prove it with a widened independent audit + count consistency + a green suite. The disposition ledger is the machine-readable spine that makes "100% covered" checkable.

## Reuse Decision Log

Per `reuse-first-design` (extend > compose > reuse > build-new). This change adds NO new Python engine — the ledger is a run artifact and the verification reuses existing machines.

| Need | Decision | Reuse target (exists in repo) | New code justification |
|---|---|---|---|
| Doc inventory + "current" definition + Phase-8 update-then-audit flow | **REUSE** | `skills/documentation-currency/SKILL.md` (the inventory + producer/checker split) | none — the discipline is the contract; the audit is WIDENED, not re-implemented |
| Independent currency audit (producer ≠ checker) | **REUSE** | `agents/system-architect.md` Documentation Currency Audit mode; `agents/doc-updater.md` whole-file-rewrite pattern | none — same agents, widened walk-list |
| Deterministic file/count consistency + cross-reference validity over the doc corpus | **REUSE** | `scripts/compliance/instruction_compliance.py` + `tests/test_cross_consistency.py` + `tests/test_documentation_currency.py` | none — reused to corroborate count-consistency; no new lint |
| OpenSpec archival of shipped changes | **REUSE** | `openspec archive <change> -y` CLI (v1.3.1) + `openspec validate --all --strict` | none — the tool folds the ADD-only deltas + moves the folder; hand-moving is forbidden |
| Disposition ledger (per-file verdict + evidence) | **BUILD-NEW (run artifact)** | none — no existing per-file doc-disposition ledger | `.architect-team/doc-disposition/ledger.json` — a data artifact under the gitignored run-state root, authored by the run, NOT a Python module or engine |
| Archive index for moved flat docs | **BUILD-NEW (doc)** | none — `docs/archive/` does not exist yet | `docs/archive/INDEX.md` — a markdown index mirroring the OpenSpec-archive reachability guarantee for the flat-doc archive |

## Key decisions

- **Ledger is a data artifact, not an engine.** It lives at `.architect-team/doc-disposition/ledger.json` under the gitignored run-state root. No `scripts/**` or `hooks/**` module is added. Its 100%-coverage claim is checkable by reconciling its in-scope + excluded totals against `git ls-files '*.md'` (395 at authoring: 83 in-scope + 193 archive + 10 dot-dir + 109 instruction).
- **Disposition of the 3 non-archived changes is `openspec archive`, verified not assumed.** git log + CHANGELOG show all three shipped (v3.1.0 / v3.2.0 / v3.29.0); each spec delta is `## ADDED Requirements` ONLY against a capability name absent from the living specs, so `openspec archive <change> -y` folds each cleanly and `validate --all --strict` stays green (baseline: 52 passed / 0 failed). No `--skip-specs` needed. Archive re-run after EACH, not batched, so a mid-sequence failure is localized.
- **Count arithmetic shifts under archival — the ledger records both states.** Archiving folds each change's ADDED capability spec into the living set: living specs 49 → 52; non-archived change docs 12 → 0 (moved to `openspec/changes/archive/`). The three change folders' 12 docs are verdicted `archived`; the three new living specs are verdicted `current` (freshly folded). Post-run count-consistency (acceptance criterion 3) is asserted against the POST-archive state.
- **Frozen-historical is a marker, not a rewrite.** The 7 dated `docs/superpowers/**` files are point-in-time records. Disposition = `frozen-historical`; at most a one-line header ("Historical design record — <date>; superseded by <current home>"). Their dated bodies are never edited to present, never archived-away, never deleted. The immutable OpenSpec archive tree is exempt entirely.
- **Archive-never-delete for flat docs.** Any stale non-historical flat doc moves via `git mv` into `docs/archive/` with a `docs/archive/INDEX.md` entry. `docs/archive/` is net-new; `INDEX.md` is created even if zero flat docs need archiving (present-but-empty-list), so the "reachable via index" guarantee is structurally satisfied.
- **Test-pin safety is confirmed clean.** No test pins the `openspec/changes/<slug>` paths of the three changes — the only two references (`tests/test_agent_boilerplate_sync.py`, `tests/test_install_librarian.py`) are docstring provenance, not path assertions. So the REQ-006 "update the pin in the same change" clause has no trigger from archival; it remains a live guard only for a flat-doc `git mv` that happens to move a pinned path.

## Parallelization (disjoint file sets)

- **Group A — ledger + glob skeleton (REQ-001).** Owns `.architect-team/doc-disposition/ledger.json`. Produces the deterministic in-scope glob + class totals + the empty per-file verdict skeleton; every other group writes its verdicts back into A's skeleton rows (A defines the schema; B/C/D fill their disjoint row-ranges).
- **Group B — inventory + non-inventory currency waves (REQ-002, REQ-003).** Owns the 7 inventory docs + the 15 non-inventory flat docs. Verify/fix in place; freeze the 7 historical docs.
- **Group C — OpenSpec-docs wave (REQ-004).** Owns the 49 living specs' verdicts + the 3 change archivals (tool-driven) + re-validation.
- **Group D — disposition execution (REQ-005).** Depends on A–C verdicts (it acts on what they mark stale-non-historical). Owns `docs/archive/` + `docs/archive/INDEX.md` + any `git mv`.
- **Group E — widened audit + ship (REQ-006).** Phase 7–8 territory: the independent widened audit, corpus-wide count consistency, suite green both encodings.

File scopes are disjoint by construction (A owns the ledger JSON; B owns flat docs; C owns openspec; D owns docs/archive) except the ledger JSON, which A seeds and B/C/D append disjoint row-ranges to — sequenced, not concurrent, on that one file.

## Risks / boundaries

- **`openspec archive` interactivity.** The CLI prompts for confirmation; `-y`/`--yes` skips it. Run non-interactively with `-y`. If a future delta were MODIFIED/REMOVED against a drifted spec the tool could error — not the case here (all ADD-only), but the "validate green after each" gate catches it.
- **Ledger 100%-coverage is a reconciliation claim, not a proof of correctness of each verdict.** The verdict quality is what the widened independent audit (REQ-006, producer ≠ checker) certifies; the ledger guarantees completeness, the audit guarantees correctness.
- **Scope fences.** Instruction corpus (`skills/`/`agents/`/`commands/`), the immutable `openspec/changes/archive/**`, gitignored/dot-dir files, historical CHANGELOG entries, and source/tests/hooks/engines are OUT — touched only where a sanctioned move alters a pinned path.
