# Phase B1 — Bug Replication

The Lead creates a `bug-replicator` task in the shared list (teams mode) OR dispatches the `bug-replicator` subagent (subagents mode), one per affected codebase (usually just one). Bracket the dispatch with the v3.34.0 dispatch-wait pair per `## Notifications` — emit `waiting_on_agents` (`--agents "bug-replicator-<codebase> — reproduce: <symptom one-liner>"`) as the dispatch goes out, and `agents_complete` (`--agents "bug-replicator-<codebase> — <verdict>"`) when every replicator has returned its verdict. Inputs to the agent:

**Data defect => sample-first unless `--full-data` (v4.0.0).** When the classifier's bug is a data defect -- wrong rows, a bad aggregate, a dedup or join that drifted -- AND the run was NOT invoked with `--full-data` (and no project principle forbids sampling), B1 replicates on a **stratified sample**, not the full table: `python "${CLAUDE_PLUGIN_ROOT}/scripts/data_dictionary/sampling.py" plan --dictionary docs/data-dictionary.json --table <T> --predicate <the columns the defect depends on> --change-kind filter|aggregate|window|dedup|join --reported-rows <the exact rows the report named>.json --out <workspace>/.architect-team/bug-fix/<slug>/sample-plan.json`, then `sql --plan ... --dialect <engine>` into a warehouse sandbox; the reported rows are edge rows by construction, so the replication includes them, and aggregate-level defects keep whole groups. B6 replays the fix on the sample first (`diff --before --after --plan` per stratum is the replay evidence) and on the full data second -- the full run stays the gate. Skip the sample only when `should-sample` shows the dictionary positively knows the table is small. When `--full-data` WAS passed (or a project principle opts the project out), the sample plan is neither produced nor referenced: B1 replicates and B6 replays against the full table, and the B7 report records the opt-out and its source. The rule in full: `skills/data-eng-pipeline/references/sample-first.md`.

- The bug description (the source prose OR the bug-report artifacts).
- The relevant CODEBASE_MAP / ROUTE_MAP / DESIGN_MAP / INTEGRATION_MAP / INTERACTION_INTUITION_MAP (when present).
- The dev-environment URL(s) from the target project's `design.md` `## Dev Environment` section.

The agent's process (apply `superpowers:systematic-debugging` throughout — replicate and root-cause before any fix is proposed, per `## Plugin prerequisites (v3.9.0)`):

1. **Identify the failing path** from the description + maps. For frontend bugs: which route, which component, which interactive element. For backend bugs: which endpoint, which payload shape, which side-effect.
2. **Write the replication artifact** at the appropriate location in the target codebase:
   - Frontend bugs → a Playwright user-flow per `playwright-user-flows` at `tests/e2e/bug-fix-<bug-slug>/<flow>.spec.ts` (or the codebase's e2e convention). The flow exercises the real UI path — real `page.click`, real `page.fill`, real `page.waitFor` — against the live dev URL.
   - Backend bugs → a script (Python with `httpx`, or Node, per the target's conventions) at `tests/bug-fix-<bug-slug>/<script>.py` that calls the failing endpoint(s) against the live dev API and asserts the failing condition.
3. **Run the artifact** against the live dev environment. Capture the output verbatim. **The artifact MUST currently fail** — that is the replication. If it passes (the bug isn't actually present), exit with `could-not-reproduce`.
4. **Report a verdict**: one of `reproduced` (bug confirmed; proceed to B2), `could-not-reproduce` (the bug isn't present; escalate to the user with the evidence — the bug may already be fixed, or the description may be incomplete), `needs-clarification` (the description is genuinely ambiguous; emit a structured question and pause).

**The canonical ambiguity-escalation question (Phase B1):**

*"I need a bit more detail to replicate this — can you describe how you experienced the bug? Specifically: (1) what page or screen were you on, (2) what did you click / type / submit, (3) what did you expect to see, and (4) what actually happened? A screenshot or video would help if you have one."*

The replicator does NOT guess at the steps. A guessed replication that doesn't reproduce the bug burns an iteration; an honest `needs-clarification` saves the loop.

**Hard rule:** Phase B1 does NOT proceed to B2 without a `reproduced` verdict. "We'll figure it out at QA" is forbidden.

**Verdict file mandate (v0.9.36).** The orchestrator writes a structured verdict file at `<cwd>/.architect-team/bug-fix/<bug-slug>/b1-replication-verdict.json` immediately after the `bug-replicator` returns. The `pipeline-completion-audit` hook checks for this file's existence and verdict. Schema:

```json
{
  "phase": "B1",
  "bug_slug": "<bug-slug>",
  "verdict": "reproduced" | "could-not-reproduce" | "needs-clarification",
  "artifact_paths": ["<path-to-playwright-flow>", "<path-to-backend-diagnostic>"],
  "artifact_executed": true,
  "failing_output_captured": true,
  "dev_environment_url": "<the URL the artifact ran against>",
  "timestamp": "<ISO 8601>"
}
```

`artifact_executed` and `failing_output_captured` are both **mandatory `true`** for a `reproduced` verdict — the replicator must have actually run the artifact (not just written it) and captured the verbatim failing output (not described it). A verdict file with `artifact_executed: false` is structurally invalid and the completion audit blocks on it. **This is the enforcement mechanism for testing**: the pipeline cannot complete without proof that the replication test was actually executed against the live dev environment.

**Bauplan-armed replication (gated on the B−1 arming verdict; a no-op when unarmed).** On an armed run, dispatch `bauplan-debug-and-fix-pipeline` **alongside** the `bug-replicator`, never instead of it. Its own contract is evidence-first and is already this lane's shape — pin the data state, collect the evidence, make the minimal fix, rerun — so use it for what a generic replication cannot reach: **pin the lakehouse state the failure reproduced against** (the branch and the table snapshot), so B6's QA replay re-runs against that same state rather than a drifted one, and collect the failed-job / query evidence behind the symptom. Everything B1 requires is unchanged: a `reproduced` verdict still gates B2, the artifact must still have been EXECUTED with its failing output captured verbatim, and the verdict file above is still mandatory with `artifact_executed: true`. The skill supplies evidence; it does not supply the verdict. Record each dispatch to `<workspace>/.architect-team/bug-fix/<bug-slug>/bauplan-dispatches.json`, and where a Bauplan write rule collides with a CT6 default on a lakehouse operation, the Bauplan rule governs and the conflict is appended there as a `precedence_conflicts[]` entry — per `common-pipeline-conventions` `## Augment-never-replace discipline (v3.63.0)`.
