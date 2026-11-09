# Phase B5 — Implement + deploy to dev

The Lead creates ONE focused fix-team task in the shared list (teams mode) OR dispatches ONE focused fix-team subagent (subagents mode) — a `frontend` or `backend` agent depending on layer; for `both`-layer bugs, the Lead sequences them or runs them in parallel with non-overlapping file scope per the main pipeline's Phase 2 rules — usually a bug fix is single-layer or has a clear primary. Brief includes:

- The OpenSpec change name + the relevant tasks from `tasks.md`.
- The proposed approach from `design.md` (architect-approved at B4).
- The replication artifacts (the failing flow / script) as the verification target.
- The acceptance criterion: the replication artifacts pass when re-run against the deployed fix.

The team writes Phase 3 review-gate evidence per the existing schema (v7) — the 17 required fields including `real_not_stubbed`, `tests`, `integration_testing_review`, `test_completeness_review`, `demo_artifact`, `reuse_compliance`, `visual_fidelity_review` (for frontend touches), `ui_interaction_review`, and the 5 Verified Agent Output fields (`oracle_match_review` / `baseline_clean_review` / `no_fake_data_review` / `adversarial_review` / `skill_invocation_audit`). The `task-reviewer` independently re-reviews and writes the `independent_review` block; only its `verdict: pass` opens the Phase 3 gate. (Same gate as the main pipeline — bug fixes don't skip review-gate evidence.)

**After local tests pass, deploy to the dev environment.** Read the target project's `design.md` `## Dev Environment` section for the deploy command (`npm run deploy:dev`, `make dev-deploy`, `gh workflow run ...`, etc.) and the dev URL. Run the deploy, then poll the dev environment's health endpoint or build-status URL with a tight bounded in-turn loop until builds are green. A failed build is a Phase B5 escalation that routes back to the implementing team for diagnosis (probably a build-config issue, a missing env var, a dependency drift) — it is NOT a QA-replay failure. The bug-fix loop must never confuse a deploy failure with a fix failure.

**The `--environment production` exception.** If the run was invoked with `--environment production` (or the user's prose names the target as production), the orchestrator escalates a structured question:

*"This run is targeting production. A production deploy is your decision, not mine. The fix is implemented and verified locally; please confirm: (a) deploy to production now, (b) deploy to a staging environment first, or (c) hold for manual review."*

Phase B5 does NOT auto-deploy to production. The user's answer is the green light.

**Notification (best-effort, per `## Notifications`):** if the target project supplies `.architect-team-notify.json`, the orchestrator emits a `deploy` event with `--layer <layer>` (e.g., `frontend` / `backend` / `fullstack`) at the start of the dev deploy. Invoke from the target project's root and proceed immediately regardless of the notifier's outcome:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/notify/notify.py" deploy --project <name> --layer <layer> || python "${CLAUDE_PLUGIN_ROOT}/scripts/notify/notify.py" deploy --project <name> --layer <layer>
```

This `deploy` invocation is best-effort and NEVER blocks, fails, or delays the dev deploy — a notifier failure does not affect the deploy or the QA replay.
