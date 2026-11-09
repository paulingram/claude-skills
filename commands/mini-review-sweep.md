---
description: Batch review of /architect-team:mini commits, grouped by Mini-Run trailer (--since) -- interaction- and editability-completeness at review tier 2 (one paired reviewer, a second only on disagreement), visual-fidelity, test-completeness, dev-API audits per slug. Drift becomes SRs.
argument-hint: "[--since <ref>] [--limit <N>] [--no-compact]"
---

# /architect-team:mini-review-sweep

Runs the heavyweight review gates that `/architect-team:mini` deliberately skips at runtime, in batch, against every commit that carries a `Mini-Run: <slug>` trailer in the configured range. The mini variant's whole theory is "fast at runtime, audited in batch" — this is the batch.

## Flags

- `--since <ref>` → only consider commits reachable from `HEAD` but not from `<ref>`. Default: the most recent `mini-sweep/<date>` tag, or 30 days ago if no sweep tag exists.
- `--limit <N>` → cap the number of slugs reviewed in this run. Default: 25. If the range contains more slugs than `--limit`, the sweep reviews the oldest `N` and reports the remainder for the next sweep.
- `--no-compact` → suppress the trailing `/compact` prompt. Default `true`.

## What the sweep does

1. **Find Mini-Run commits.** `git log --format=%H%x00%B --no-decorate <since>..HEAD` and grep each commit's trailer block for `Mini-Run: <slug>` using `tests/helpers/mini_run_trailer.py`'s `extract()`.
2. **Group by slug.** Multiple commits per slug are normal (the mini pipeline commits doc-currency updates separately from the dev work).
3. **For each slug, compute the aggregate diff** vs. the parent of the oldest commit in the group.
4. **Run the heavyweight review gates** against that aggregate diff:
   - Both completeness reviews run PER SLICE (one slug's aggregate diff), so they are **review tier 2** per `skills/team-spawning-and-review-gates/references/review-tiers.md`: the slug's own evidence (the mini run's dev cross-review + its `mini-qa` verdict) is the producer side, ONE paired reviewer is the independent verdict, and a second independent verdict is dispatched only when the two disagree (recorded in the same `history[]`). Each is a `ct6-converge` workflow the Lead runs, DECLARED before and RECORDED after per `skills/architect-team-pipeline/references/phase--1.md` `### Converge record protocol (v4.0.0)` (the recorded all-`ok` round is the exit condition; the promise is the label); three reviewers are the tier-3 shape of the full pipeline's Phase 7, not the sweep's.
   - `interaction-completeness` — the `interaction` preset (`kind: "interaction"`, `promise: "INTERACTION COMPLETE"`, `reviewerAgent: "architect-team:interaction-reviewer"`, `reviewers: 1`) per slice with UI surface; one `interaction-reviewer` per slice, a second only on disagreement.
   - `editability-completeness` — the `editability` preset (`kind: "editability"`, `promise: "EDITABILITY COMPLETE"`, `reviewerAgent: "architect-team:editability-reviewer"`, `reviewers: 1`) per affected entity surface; one `editability-reviewer` per slice, a second only on disagreement.
   - `visual-fidelity-reconciliation` — per `DESIGN_MAP.md` for each affected frontend codebase.
   - `test-completeness-verifier` — run as a single agent against the per-slug diff.
   - `dev-api-integration-testing` audit — verify integration tests in scope hit the real dev API, no mocks beyond external boundaries.
   - **Selected run, full suite at the merge boundary (v4.0.0)** — the sweep runs the selected set, not the suite: `python "${CLAUDE_PLUGIN_ROOT}/scripts/test_index/cli.py" select --workspace <ws> --phase M<n> --changed-files <the swept slugs' files> --json`, whose record already carries the human `always_run` pins and every unknown mapping and is cited in the sweep's evidence. At M7, the lane's merge boundary, call `select --phase 8` (the selector's full-suite token) so the whole suite -- and the dev Playwright project enumerated from `<e2e-dir>/suite-manifest.json`, if one exists -- runs once before the merge (`skills/common-pipeline-conventions/references/test-selection.md`; `playwright-suite-builder` owns the manifest's contract). Failures become SRs in step 5 like every other finding. Absent a suite manifest, behavior is unchanged.
5. **Convert findings to solution requirements.** Each finding is written as an SR in `.architect-team/solution-requirements/` per the v0.7.0 SR auto-spawn convention. The existing dev loop picks them up and runs them through the appropriate pipeline (`bug-fix-pipeline` for defects, `architect-team-pipeline` for feature gaps).
6. **Tag main.** After all slugs are reviewed, `git tag mini-sweep/<ISO-date> HEAD` so the next sweep's `--since` default works. Push the tag.

## Out of scope for this command (v0.10.0)

The full sweep orchestrator skill — how it parallelizes across slugs, how findings are de-duplicated when the same drift appears in multiple slugs, how it batches Mailpit/email-testing capture across mini commits that all touch the email surface — is a follow-up spec slated for v0.10.1. v0.10.0 ships the command signature, the trailer-extraction wire-up, and the per-slug review dispatch with no de-duplication beyond "one SR per finding per slug." The shape is right; the depth follows in v0.10.1.

The command DOES land in v0.10.0 because the trailer convention only earns its keep if the sweep is runnable end-to-end against real Mini-Run commits.
