# Relationship to other skills

- `architect-team-pipeline` (sibling) — same orchestration discipline; the lane reuses Phases 1, 2–6, and 8 by reference. Reached via `/architect-team:data-eng` (explicit), `--data-eng`, or the main pipeline's Phase −2 triage when the classifier returns `kind: data-eng`. See `architect-team-pipeline` `## Data-eng lane precedence` for how the front-door lane and Phase 0c mid-flow dispatch interact.
- `bug-fix-pipeline` (sibling) — the template this lane is built on; same "reuse the main pipeline's structural points rather than duplicating them" shape.
- `data-engineering-exploration` (Phase D0) — dispatched verbatim; the lane is its third documented caller.
- `intake-and-mapping` (Phase D−1A) — reused verbatim. Same maps, same freshness rules.
- `data-dictionary` (Phase D−1B, D7) — the deterministic dictionary engine's contract; consulted at D−1 (via the knowledge server) and rebuilt at D7.
- `data-lineage-mapping` (Phase D2–D6) — every transformation's lineage emission traces to this discipline.
- `documentation-currency` (Phase D8) — the doc-currency gate before the auto-commit, same as the main pipeline. The D8 commit is authored as the checkout's RECORDED person per `common-pipeline-conventions` `## Git commit identity discipline (v3.67.0)` (the `git_identity.py git --` wrapper or the explicit `-c user.name= -c user.email=` pair) — never a default author.
