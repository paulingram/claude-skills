# Phase B6 — QA replay against live dev

The QA replay is this pipeline's `superpowers:verification-before-completion` gate — evidence (the originating symptom is gone end-to-end against the live dev environment) before any claim that the bug is resolved, per `## Plugin prerequisites (v3.9.0)`.

The Lead creates a `qa-replayer` task in the shared list (teams mode) OR dispatches the `qa-replayer` subagent (subagents mode). Inputs:

- The path(s) to the reproduction artifact(s) from B2.
- The dev environment URL(s).
- The bug description (for the symptom-gone-end-to-end verification).
- **The fix's git diff** (v0.9.31) — the unified diff of the fix's commit vs. its parent, used in the code-path execution witness (Step 4.5) to identify the buggy handler(s) and their invocation fingerprints.

The replayer's process:

1. Re-run the Playwright flow against the live dev environment, verbatim (no edits to the flow). **Capture the Playwright trace with network log (`trace: 'on'`)** — the network log is the witness data the code-path gate consumes at step 5.
2. Re-run the backend diagnostic script against the live dev API, verbatim (no edits). **Capture the dev API access log for the test window** — same purpose.
3. Compare the output against the original failing output captured in B1.
4. Verify the originating symptom — what the USER experienced — is gone end-to-end. NOT just "the test passes" — the failure mode is no longer reproducible.
5. **Code-path execution witness (v0.9.31)** — cross-check the fix's git diff against the captured network log + access log. For each handler the fix touched, determine an invocation fingerprint (the endpoint the handler calls, a DOM state-change unique to the path, a console sentinel) and assert at least one fingerprint was observed during the test. A test that passes but never invoked the fix's handler (selector misidentification, precondition skip, sibling-handler entry) is a `test-did-not-exercise-fix` verdict — distinct from `bug-still-present`. Origin case (v0.9.30 production):

   > *"My Playwright never actually completed a Schedule click. The test's tech-selector grabbed 'Alabama' (a state filter) instead of a real tech, so the Schedule button stayed disabled — and I declared REQ-001 PASS based only on the Unschedule path's panel-stayed-open assertion. The Unschedule path goes through `handleUnschedule`; the Schedule path goes through `handleSchedule` where the fix lives. The test never invoked `handleSchedule` at all."*

   The full witness procedure (handler identification, fingerprint selection, trace/log capture, cross-check) lives in the `qa-replayer` agent body (`agents/qa-replayer.md` Step 4.5). The orchestrator does NOT replicate it here — the agent is the source of truth.

The replayer's verdict is one of:

- **`bug-resolved`** — the artifacts pass, the originating symptom is gone, AND the code-path witness verdict is `pass` (at least one fix-touched handler was observably invoked) or `n/a` (the fix's diff has no observable handlers — comments / imports / types only). Proceed to B6b (sensibility check) → B7 (archive).
- **`bug-still-present`** — the artifacts fail (or pass technically but the symptom is still observable) AND the code-path witness is `pass` or `n/a` (the test DID exercise the fix's handler — the fix just isn't doing what it should). The replayer writes a solution requirement back to the orchestrator with the new evidence (the current failing output, the differences from the pre-fix failing output). The loop returns to **B3** — a FRESH OpenSpec proposal authored on the new evidence (not an amendment to the previous proposal; the previous proposal is closed and a new one opened to keep the audit trail clean). **The FIX is on trial here**, not the test. **Notification (best-effort, per `## Notifications`):** the orchestrator emits an `issue_discovered` event with the SR's failure-mode description as `--summary` immediately before re-entering B3. It invokes the notifier from the target project's root and proceeds immediately regardless of the notifier's outcome:

  ```bash
  python3 "${CLAUDE_PLUGIN_ROOT}/scripts/notify/notify.py" issue_discovered --project <name> --summary "<the SR's failure-mode description>" || python "${CLAUDE_PLUGIN_ROOT}/scripts/notify/notify.py" issue_discovered --project <name> --summary "<the SR's failure-mode description>"
  ```

  This `issue_discovered` invocation is best-effort and NEVER blocks or alters the bug-fix loop — a notifier failure does not stop the next iteration. The loop continues.
- **`test-did-not-exercise-fix`** (v0.9.31) — the deploy applied, the artifacts technically passed, the symptom-check looked ok, BUT the code-path witness verdict is `fail` — at least one fix-touched handler with a derivable fingerprint was `not_invoked`. The fix may be correct or wrong; we don't know yet because the test didn't actually exercise it. The replayer writes a solution requirement with `origin.kind: "test-coverage-gap"` and a `gap` field listing every `not_invoked` handler + the likely cause (selector misidentification / precondition skip / sibling-handler entry — directly from the agent's `gap_if_failed` field). The orchestrator routes back to **Phase B2** (re-author the reproduction artifact with corrected selectors + explicit witness assertions; the architect's proposal at B3 is NOT necessarily wrong — the test is). After re-authoring, B3 (re-validate the proposal against the new artifacts) → B4 → B5 → B6 again. **The TEST is on trial here**, not the fix. Emits the same `issue_discovered` notification as `bug-still-present` (with `--summary` carrying the witness gap description) so subscribers see iteration churn regardless of which axis fails. Recurrence detection still applies — when `test-did-not-exercise-fix` recurs on the same bug (e.g. 3 consecutive verdicts), the loop does NOT stop: it continues from a DIFFERENT angle (re-route the re-authoring through `diagnostic-research-team` for a deeper selector/witness analysis, broaden the artifact, try an alternate gesture strategy) and surfaces the recurrence loudly. If the artifact genuinely needs user-provided element IDs that only the owner can supply, that specific required input is surfaced via the required-input marker while the run keeps working everything else — never a give-up. Per `common-pipeline-conventions` `## Unbounded solving discipline`.
- **`env-failure`** — the artifacts couldn't run (the dev environment is down, the deploy didn't apply, the browser is mis-configured). Routes to the implementing team for env diagnosis, NOT to the architect. The env issue must be resolved before re-running the replay — but the fix isn't on trial; the env is.

**Routing goes to the decisions ledger (v4.0.0, best-effort, never blocking).** Whichever branch a non-`bug-resolved` verdict takes, append ONE `sr-routing` line naming the route chosen and the route rejected: `python3 "${CLAUDE_PLUGIN_ROOT}/hooks/decisions_ledger.py" add --workspace "<workspace>" --kind sr-routing --summary "<SR-id>: <verdict>" --chosen "<re-enter B3 (fix on trial) | re-author at B2 (test on trial) | env diagnosis>" --rejected "<other route>=<why the witness / symptom check ruled it out>" --ref <SR-path> || python "${CLAUDE_PLUGIN_ROOT}/hooks/decisions_ledger.py" add --workspace "<workspace>" --kind sr-routing --summary "<SR-id>: <verdict>" --chosen "<re-enter B3 (fix on trial) | re-author at B2 (test on trial) | env diagnosis>" --rejected "<other route>=<why the witness / symptom check ruled it out>" --ref <SR-path>`.

**Loop bounds (v3.8.0 — none):** the bug-fix loop is UNBOUNDED — it runs until the symptom is gone end-to-end, with no iteration ceiling (most bug fixes converge in 1-3 iterations, but the loop never aborts on count). The `dev_loop_iterations` counter in `intake-state.json` increments every B3 → B6 cycle purely as an observability signal, never as a stop condition. Recurrence detection still applies: a fix that keeps re-breaking the same symptom (or the same proposal landing 3 times) does NOT stop — the loop continues from a DIFFERENT angle (re-route through diagnostic-research, broaden scope, alternate strategy) and surfaces the recurrence loudly. Per `architect-team-pipeline`'s `## Run-state: unbounded solving, concurrency, required-input gates`.

**Verdict file mandate (v0.9.36).** The orchestrator writes a structured verdict file at `<cwd>/.architect-team/bug-fix/<bug-slug>/b6-qa-replay-verdict.json` immediately after the `qa-replayer` returns (overwritten on each B6 iteration — only the final verdict matters for the completion audit). The `pipeline-completion-audit` hook checks for this file's existence and verdict. Schema:

```json
{
  "phase": "B6",
  "bug_slug": "<bug-slug>",
  "verdict": "bug-resolved" | "bug-still-present" | "test-did-not-exercise-fix" | "env-failure",
  "artifacts_rerun": ["<path-to-playwright-flow>", "<path-to-backend-diagnostic>"],
  "artifacts_executed_against_live_dev": true,
  "symptom_gone_end_to_end": true,
  "code_path_witness_passed": true,
  "dev_environment_url": "<the URL the artifacts ran against>",
  "iteration": <integer, 1-based>,
  "timestamp": "<ISO 8601>"
}
```

`artifacts_executed_against_live_dev` is **mandatory `true`** for a `bug-resolved` verdict — the replayer must have actually re-run the artifacts against the deployed dev environment (not just read them, not just described the expected outcome, not just run them locally). `symptom_gone_end_to_end` and `code_path_witness_passed` must also be `true` for `bug-resolved`. A verdict file where ANY of these three fields is `false` on a `bug-resolved` verdict is structurally invalid and the completion audit blocks on it. **This is the enforcement mechanism for QA testing**: the pipeline cannot complete without proof that the fix was actually verified against the live dev environment.

### Phase B6 Verification-Claim Audit (v2.2.0)

After the qa-replayer returns its verdict and BEFORE Phase B6b runs, the orchestrator invokes the v2.2.0 Layer 3 tool `verify-live-verification-claim` against the qa-replayer's `verification_artifact` + `bug_description` blocks. This is the structural gate that catches the 3 named failure modes the qa-replayer's self-audit (per `agents/qa-replayer.md` `## Verification-Claim Audit (v2.2.0)`) is supposed to surface.

Invocation:

The interpreter is selected ONCE via `$(command -v python3 || command -v python)` (the v2.16.0 detect-once form) and the script is anchored with `${CLAUDE_PLUGIN_ROOT}` so it resolves regardless of the install location — never a hardcoded plugin-cache path:

```bash
$(command -v python3 || command -v python) "${CLAUDE_PLUGIN_ROOT}/hooks/vao_tools.py" verify-live-verification-claim \
  --artifact "<cwd>/.architect-team/qa-replays/<bug-slug>/verification-artifact.json" \
  --bug "<cwd>/.architect-team/qa-replays/<bug-slug>/bug-description.json" \
  --out "<cwd>/.architect-team/vao-verdicts/<bug-slug>-live-verification.json"
```

The tool's verdict — `valid: true|false` with named severity gaps — IS the authoritative gate:

- **`valid: true` AND qa-replayer verdict is `bug-resolved`** → accept; proceed to B6b sensibility check → B7 archive.
- **`valid: false` AND qa-replayer verdict is `bug-resolved-verification-suspect`** → the qa-replayer correctly self-flagged. Route to **Phase B2 re-replication** with the suspect mode as input:
  - `gesture-substitution` → re-author the reproduction artifact with the correct user gesture (NOT a corner-click or backdrop selector).
  - `self-verification-loop` → re-author the test such that its creation predates the fix OR its assertion does NOT mirror any substring from the fix's git diff.
  - `prefill-masking` → re-author the setup to drive the test to the bug-exposing state (blank matter, navigate to a genuinely-blank step).
- **`valid: false` AND qa-replayer verdict is `bug-resolved`** → CONFLICT. The qa-replayer's self-audit missed what the tool caught. Re-route to deeper diagnosis and re-replication; if the gap genuinely needs an owner decision the orchestrator can't make, surface it via the required-input marker per `## Run-state: unbounded solving, concurrency, required-input gates` (write `.architect-team/escalation-pending.md` with the conflict report) while continuing all other work; the owner reviews the gap between the qa-replayer's self-audit and the tool's deterministic check before any further routing.
- **`valid: true` AND qa-replayer verdict is `bug-resolved-verification-suspect`** → CONFLICT in the other direction (the qa-replayer was more conservative than the tool). Surface the conflict but DEFAULT to the qa-replayer's more conservative verdict — route to Phase B2 re-replication with the suspect mode. The tool's `valid: true` may be a false negative on the tool's heuristics; the agent's self-audit may have caught something the tool's static rules don't see (a novel gesture-substitution shape, e.g.).

The schema v7 evidence file's optional `live_verification_review` field MUST cite this verdict path (`live_verification_review: {verdict: "pass" | "fail", verdict_path: "<vao-verdicts/<bug-slug>-live-verification.json>"}`). If the qa-replayer's `verified_live: true` is claimed in evidence, the schema v7 hook requires the field to be present and non-`fail`.
