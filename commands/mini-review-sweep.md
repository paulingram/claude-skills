---
description: "Batched heavyweight review for commits produced by /architect-team:mini. Greps git log for the Mini-Run: <slug> trailer in the configured range (--since), groups commits by slug, computes the aggregate per-slug diff, and runs the full /architect-team review gates against each — interaction-completeness (×3 reviewers), editability-completeness (×3 reviewers), visual-fidelity-reconciliation (per design map), test-completeness-verifier, dev-api-integration-testing audit. Drift becomes solution requirements; the existing bug-fix-pipeline auto-spawn picks them up (v0.7.0 SR → dev-loop). After sweep, tags main with mini-sweep/<ISO-date> so the next sweep's --since works. Closes the loop on the many rapid mini changes + one massive review pattern."
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
   - `interaction-completeness` — spawn 3 `interaction-reviewer` agents per slice with UI surface.
   - `editability-completeness` — spawn 3 `editability-reviewer` agents per affected entity surface.
   - `visual-fidelity-reconciliation` — per `DESIGN_MAP.md` for each affected frontend codebase.
   - `test-completeness-verifier` — run as a single agent against the per-slug diff.
   - `dev-api-integration-testing` audit — verify integration tests in scope hit the real dev API, no mocks beyond external boundaries.
5. **Convert findings to solution requirements.** Each finding is written as an SR in `.architect-team/solution-requirements/` per the v0.7.0 SR auto-spawn convention. The existing dev loop picks them up and runs them through the appropriate pipeline (`bug-fix-pipeline` for defects, `architect-team-pipeline` for feature gaps).
6. **Tag main.** After all slugs are reviewed, `git tag mini-sweep/<ISO-date> HEAD` so the next sweep's `--since` default works. Push the tag.

## Out of scope for this command (v0.10.0)

The full sweep orchestrator skill — how it parallelizes across slugs, how findings are de-duplicated when the same drift appears in multiple slugs, how it batches Mailpit/email-testing capture across mini commits that all touch the email surface — is a follow-up spec slated for v0.10.1. v0.10.0 ships the command signature, the trailer-extraction wire-up, and the per-slug review dispatch with no de-duplication beyond "one SR per finding per slug." The shape is right; the depth follows in v0.10.1.

The command DOES land in v0.10.0 because the trailer convention only earns its keep if the sweep is runnable end-to-end against real Mini-Run commits.
