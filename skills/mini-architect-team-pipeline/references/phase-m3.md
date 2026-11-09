# Phase M3 — Architect self-confirm loop

After M2, the **same architect** re-reads its own bundle + the source requirements + the cached maps, and asks one question of itself: *does the bundle still make sense?*

Iterate to a **fixed point**: edit in place, re-read, repeat. Exit when a pass produces zero edits. **Cap = 3 self-confirm passes.** On cap, the architect freezes its current draft and proceeds, noting the unresolved divergence in a `## M3 unresolved` section at the bottom of `proposal.md` so M5's QA agent scrutinizes that area especially carefully.

Each pass must answer at minimum:

1. Does the `## QA Guidance` contract validate? (Run the parser; fix violations.)
1b. Does the OpenSpec bundle validate? Run `openspec validate --all --strict --json` and require `valid: true` with no errors — uniform parity with the architect-team + bug-fix planning gates (per `common-pipeline-conventions/SKILL.md` `## Uniform plugin usage (v3.9.0)`). Fix any validation error before exiting the self-confirm loop. The architect's M2 draft applied `superpowers:brainstorming`; this gate is its `superpowers:verification-before-completion` checkpoint for the spec bundle.
2. Does every AC have a covering Playwright flow? (And every flow bind to an AC?)
3. Does the file scope in `tasks.md` not overlap between backend and frontend?
4. Does the proposal's WHY still match the user's prose / folder?
5. Are the maps the architect cited at M2 still in working context?
6. Does every design option the bundle presents carry a principles verdict (v4.0.0)? Before the bundle is handed to M4 — the mini variant's "presented" moment — the architect writes the `principles-verdicts/v1` sidecar beside `design.md` (one verdict per confirmed principle; every option tagged `fits` / `violates P-xx`) and runs `python "${CLAUDE_PLUGIN_ROOT}/scripts/principles/cli.py" check --verdicts <sidecar> --workspace <ws> --json`; a fitting option is chosen and the run continues, and only when every option violates does it stop with `escalation-pending.md` (`project-principles` `## The autonomous-run rule`).

The self-confirm pass is **structural + semantic**, not free-form refinement. If the architect finds itself rewriting the proposal's voice or scope on a second pass, that's a sign M2 was wrong — note this in the unresolved section rather than spinning.

**Run-start notification — the kickoff email carrying the plan (v3.34.0, best-effort, per `## Notifications`).** The moment the self-confirm loop converges — the 5-artifact bundle is confirmed, so the architecture + solution plan exists — the orchestrator emits `run_start` ONCE, embedding the bundle itself so stakeholders receive the plan (including the QA Guidance) in ONE email:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/notify/notify.py" run_start --project <name> --run-id <slug> --details "<requirement + solution-approach summary>" --next-step "Phase M4 — Parallel dev dispatch" --plan-file "openspec/changes/<slug>/proposal.md" --plan-file "openspec/changes/<slug>/design.md" --plan-file "openspec/changes/<slug>/tasks.md" || python "${CLAUDE_PLUGIN_ROOT}/scripts/notify/notify.py" run_start --project <name> --run-id <slug> --details "<requirement + solution-approach summary>" --next-step "Phase M4 — Parallel dev dispatch" --plan-file "openspec/changes/<slug>/proposal.md" --plan-file "openspec/changes/<slug>/design.md" --plan-file "openspec/changes/<slug>/tasks.md"
```
