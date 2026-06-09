---
name: diagnostic-research-team
description: Use when a failing test escalates back to the orchestrator via a solution requirement before spawning a Phase 2 fix team. Spawns three diagnostic-researcher agents in parallel — each independently maps the FULL code flow from test input to failing assertion, then theorizes ranked diagnostic hypotheses anchored to file-line evidence. The system-architect agent reviews all three drafts for robustness, identifies coverage gaps, sends researchers back for deeper investigation if needed, and only then produces a consolidated diagnostic plan that becomes mandatory input to the fix team brief. The fix team never starts work without an approved diagnostic plan when this skill applies.
---

# Diagnostic Research Team — Three Researchers + Architect Review for Failed-Test Escalations

When a test fails and the failure escalates to the orchestrator (via a solution requirement with a test-failure origin), the wrong move is to immediately spawn a fix team. The teammate that surfaced the failure already ran the 3-pass `root-cause-test-failures` loop locally, BUT that pass was constrained by what the teammate could see from inside its own slice. The orchestrator has a wider view of the codebase and can dispatch fresh, independent researchers who are not anchored to the teammate's working hypothesis.

This skill operationalizes that wider triage: three independent researchers, an architect review for robustness, and a consolidated plan that becomes the fix team's contract. The discipline guarantees that the fix team starts with a vetted understanding of the failure — not the originating teammate's first guess re-spawned at full team scale.

## When this skill fires

The orchestrator MUST invoke this skill before spawning a Phase 2 fix team for any solution requirement whose `origin.kind` is one of:

- `rca-product-bug` — root-cause-test-failures escalated a product-bug finding.
- `playwright-failure` — a Playwright user-flow test failed against the live dev env.
- `integration-failure` — a dev-API integration test failed.
- `integration-testing-failure` — the test-completeness-verifier found a `both`-layer feature whose happy-path user-flow tests ran against a mocked / fake backend instead of the real one.
- `test-completeness-failure` — the test-completeness-verifier flagged a missing test kind that surfaced a regression.
- `visual-fidelity-cascade` — visual-fidelity-reconciliation surfaced a cascade-blast-radius drift that points to upstream logic, not just CSS.

For SRs whose `origin.kind` does NOT name a test-driven failure (e.g., a `feature-gap` SR derived from a new requirement, an `infra` SR for a missing migration), this skill does NOT fire — the fix team is spawned directly per the normal Phase 2 flow.

## Inputs the skill receives

The orchestrator passes:

1. The SR JSON path (`.architect-team/solution-requirements/SR-*.json`).
2. The originating RCA artifact path (if any) — usually `.architect-team/.../rca/<test-id>-<ts>.json`.
3. The expectation file path for the failing test — `.architect-team/.../expectations/<test-id>.json`.
4. The originating teammate's review-gate evidence file — `.architect-team/reviews/<task-id>.json`.
5. All CODEBASE_MAP.md / ROUTE_MAP.md / INTEGRATION_MAP.md / DESIGN_MAP.md files in scope.
6. The coverage-map slice for the affected requirements.

If ANY of the above is missing or malformed, the skill returns to the originating teammate to fix the missing artifact first. Diagnostic research without the expectation + RCA is just re-running the teammate's analysis.

## Consuming the verified CDLG (lineage roadmap P2 — REQ-CDL-06 / REQ-DIAG-03 / REQ-DIAG-04)

When the lineage foundation (P1) has produced a Code & Data Lineage Graph for the bug's in-scope endpoint subset, the three researchers **CONSUME the pre-built nested call-hierarchy as their call-map input instead of re-tracing the code flow from scratch.** The CDLG is the artifact the `endpoint-trace-mapping` skill builds — `<codebase>/docs/ENDPOINT_TRACE_MAP.md` (the human view: per-endpoint mermaid call-trees with greppable `func://` ids) plus its machine sidecar `lineage-graph.json`. This is the whole point of laying out the call/data structure FIRST and reasoning against a known map rather than discovering the path *while theorizing* — the roadmap's C1.c "recursive call-hierarchy before diagnosing."

### The witness gate is a hard precondition (REQ-DIAG-03)

Consumption is **gated on runtime-witness verification** — the researchers MUST NOT consume a subgraph that has not passed the trust gate. The deterministic gate lives in **`hooks/lineage_graph.py`**:

- `reconcile_with_witness(graph, witness_executed_edges)` compares the graph's claimed-executed edges against the `(src, dst)` edges the `code-path-witness.json` observed firing during replication, returning `edge_recall` + `hallucination_rate`.
- `witness_gate(reconciliation, recall_threshold=0.9, hallucination_ceiling=0.05)` decides admissibility. **A subgraph below the recall threshold or above the hallucination ceiling is REJECTED** — the researchers do NOT trust it. Instead the orchestrator routes the gap back to `endpoint-trace-mapping` for a targeted re-trace of the missed/hallucinated edges, and diagnosis resumes only once the subset passes. This is the CT6 anti-hallucination discipline applied to the call-map itself: the map is consumed because it is *grounded against executed reality*, not because it was produced.

Concretely, what each researcher does with a witness-gated CDLG instead of re-tracing:

- **Section 1 (Full code flow examination)** anchors on the CDLG's call-tree: the forward/backward trace cites the graph's `func://` nodes and `calls` / `serves` edges directly (the pre-built nested call-hierarchy), rather than re-walking the source to rediscover the hops. The researcher still annotates `file:line` and data shapes, but the *structure* is given, not rederived. Boundary crossings are the graph's `serves_route` edges (the FE→BE seam, carrying their `match_basis` + confidence).
- **Section 2 (Ranked hypotheses)** attaches each hypothesis to a graph node/edge — every hop in the call-tree with a plausible failure mode is a hypothesis candidate, and the architect's Phase B coverage check (does every hop have a hypothesis?) is checked against the graph's node set.

### The data-source existence check cites the `asset://` node (REQ-DIAG-04)

The data-source existence check (the backtrack of the function + its parameters into the table/store to verify whether the data lives at source) cites the specific data-layer node by its **`asset://<store>/<schema>/<table>` id** from the CDLG, together with the present/absent verdict and the query/evidence that produced it. The asset node and the `reads` / `writes` / `modifies` / `originates` edges connecting it to the implicated `func://` nodes come from `lineage-graph.json` (populated by the `data-lineage-mapping` skill); the researcher does not re-derive which functions touch the asset — the graph already records it.

When **no** CDLG exists for the bug subset (the foundation has not run, or the witness gate cannot be cleared), the researchers fall back to the inline forward/backward trace described below — the CDLG is an accelerant and a trust-anchored input, not a hard dependency for the skill to function.

## Phase A — Spawn three diagnostic researchers in parallel

The orchestrator dispatches three `diagnostic-researcher` subagents simultaneously. Each receives an identical brief containing all six inputs above plus its researcher index (1, 2, or 3).

Each researcher is INDEPENDENT during this phase — no consulting the other two. They produce drafts in parallel.

Each researcher's output goes to:

```
<cwd>/.architect-team/diagnostic-research/<test-id>/researcher-<N>-<ts>.md
```

The draft has TWO required sections:

### Section 1 — Full code flow examination

The researcher traces the failing test's complete code flow end-to-end:

- **Entry point:** the test's first action (`page.goto`, the API call under test, the function-under-test invocation).
- **Forward trace:** every component / function / handler / service / DB call / queue / cache that the input traverses on its way to the assertion point. Every hop annotated with `file:line` and the data shape at that hop.
- **Backward trace:** from the failing assertion, walk backward up the call stack and the code paths actually traversed. Every frame named with `file:line`; for each frame, identify the precondition (what had to be true for this line to execute) and where that precondition was computed.
- **Boundary crossings:** every place the data crosses a process / service / module boundary. These are the highest-leverage hypothesis candidates.
- **Recent change surface:** `git log -p --since=<the-test's-last-green-run> -- <every-file-touched>` for every file the trace touches. Lists every commit that landed in the relevant window with its message and the line-range of the change.

This is not a summary — it is a structured trace document. A reviewer must be able to read it and reconstruct the data flow without re-running the trace themselves.

### Section 2 — Ranked diagnostic hypotheses

The researcher produces an ordered list of candidate root causes. Each hypothesis MUST be:

- **Anchored to file:line evidence** from the code flow examination (no "probably" / "might be" without a pointer).
- **Falsifiable** — describes the specific observation that would refute it.
- **Ranked by likelihood** — using the evidence weight, not gut feel. The hypothesis with the most evidence and the most-recent-change correlation goes first.
- **Distinct from the originating teammate's working hypothesis** — at minimum, the researcher must consider one alternative that the teammate did not pursue. If the originating teammate's hypothesis is the strongest candidate, the researcher says so explicitly with its own evidence rather than rubber-stamping.

Hypothesis schema (one entry per candidate):

```yaml
- rank: 1
  candidate: "<one-line summary>"
  category: product-bug | test-author-error | environment | fixture-drift | race | cache | concurrency | timezone | browser-runtime | upstream-contract-change
  evidence:
    - "<file:line> — <what it shows>"
    - "<file:line> — <what it shows>"
  falsification_test: "<what observation would refute this>"
  matches_originating_teammate_hypothesis: true | false
  fix_scope_estimate: single-team | cross-team | architecture-level
```

Three hypotheses minimum per researcher. More is fine; fewer is not allowed — the point of three is to force consideration of alternatives.

### Researcher posture (hard rules)

- Read-only on source code. Cannot Edit / Write source files; can only Write its own draft.
- Cannot consult the other two researchers during Phase A. Parallel independence is the entire point of the three-researcher pattern.
- Cannot lift the originating teammate's hypothesis without verification. Even if the originating teammate is correct, the researcher's draft must show its own evidence trail, not "agree with the teammate."
- Cannot defer hypothesis ranking with phrases like "could be either X or Y." Pick the order based on evidence weight, then mark close calls explicitly in the falsification_test field.

## Phase B — System-architect review for robustness

After all three researchers report their drafts, the orchestrator dispatches the `system-architect` agent with all three drafts + the full input set. The architect's job is NOT to pick the right hypothesis — it is to ensure the three drafts COLLECTIVELY produce a robust diagnostic plan.

The architect evaluates each draft and the set as a whole against this rubric:

1. **Coverage** — does every code-flow hop with a plausible failure mode have at least one hypothesis attached to it? Hops mentioned in zero hypotheses are gaps.
2. **Diversity** — do the three drafts collectively span product-bug, environment, contract-change, race, and test-author-error categories? Or did all three converge on the same category, leaving alternatives unexamined?
3. **Evidence quality** — every hypothesis carries file:line citations? No "probably" / "might be" / "must be" without a pointer? No prose-only hypotheses?
4. **Falsifiability** — every hypothesis names the observation that would refute it? A hypothesis without a falsification test is a guess.
5. **Recent-change correlation** — has each draft consulted the `git log` window between the last-green run and the failure? An unconsulted recent-change window is a coverage gap.
6. **Cross-team awareness** — for any hypothesis tagged `fix_scope_estimate: cross-team` or `architecture-level`, are the affected modules / contracts identified by `file:symbol`?
7. **Test-author-error consideration** — has at least one researcher seriously considered that the expectation itself is wrong (the spec changed, the journey map drifted, the inventory selector renamed)? This category is the most-skipped and most-recurring miss.

### Verdict and loop

The architect writes a verdict file:

```
<cwd>/.architect-team/diagnostic-research/<test-id>/architect-review-<ts>.md
```

Containing per-criterion `pass` / `gap` annotations and, if any criterion is `gap`, a directive back to specific researchers naming the gap and what they must extend their draft to cover. The orchestrator loops:

1. If ALL seven criteria pass → proceed to Phase C.
2. If ANY criterion is `gap` → re-dispatch the named researchers with the gap directive. Each re-dispatch is a fresh, focused pass on the gap — not a full re-research. The re-dispatched researcher updates its draft (`-v2`, `-v3` ...). Loop until ALL criteria pass.

This loop runs until the architect converges — there is NO fixed cycle cap (per `common-pipeline-conventions` `## Unbounded solving discipline`). Each cycle that still shows gaps sends the named researchers back for a deeper pass; the loop continues until all seven criteria pass and the architect produces an approved diagnostic plan. If progress genuinely stalls because a critical input is missing that only the owner can supply (a stale CODEBASE_MAP that needs refreshing, an absent expectation file, a redacted log), the architect surfaces that specific required input to the owner via the orchestrator — loudly, while the rest of the run continues — and resumes the loop once it is provided. The loop never halts on cycle count; only a genuine missing-required-input pause (not exhaustion) interrupts it.

## Phase C — Consolidated diagnostic plan

Once the architect approves, the architect itself produces the consolidated diagnostic plan:

```
<cwd>/.architect-team/diagnostic-research/<test-id>/diagnostic-plan-<ts>.md
```

The plan has these required sections:

1. **Failure summary** — one paragraph in product terms (what users experience), not implementation terms.
2. **Code flow under suspicion** — the merged trace from the three researchers, deduplicated. Annotated with which hops are highest-leverage hypothesis candidates.
3. **Ranked hypotheses (consolidated)** — merged + re-ranked from the three drafts. Each hypothesis carries: rank, candidate, category, evidence (citations from any of the three drafts), falsification_test, fix_scope_estimate, and which researcher(s) raised it. The architect's re-ranking can promote a hypothesis that any single researcher under-weighted but the cross-draft evidence supports.
4. **Recommended investigation order for the fix team** — which hypothesis to verify first, second, third. Each step names the verification action (run X test with Y data, capture Z log, query DB for W).
5. **Fix-scope guidance** — which team(s) own the likely fix per the leading hypothesis. If `cross-team`, the named teams. If `architecture-level`, the architect flags this for a Phase 4 reconciliation-style design step before any code is touched.
6. **Coverage-map impact** — every requirement in the coverage map that the leading hypothesis (and the runner-up) would invalidate if confirmed. The fix team's brief MUST list these as acceptance criteria.
7. **Pre-fix verification checklist** — observations the fix team must capture BEFORE proposing a fix, so the proposed fix can be evaluated against actual evidence rather than the hypothesis. (e.g., "capture POST /api/auth/login response body when the matched account row has deleted_at set" / "log the value of feature_flag_v2 in the failing run".)

The plan becomes a required input to the Phase 2 fix-team brief. The fix-team brief explicitly cites the plan's path; the fix team's first action is to read the plan in full.

## Phase D — Hand-off to Phase 2 fix-team spawn

After the diagnostic plan is written, the orchestrator hands off back to its normal Phase 3b solution-requirement-intake flow with one addition: the SR record is updated with `diagnostic_plan_path: "<path>"` and the spawned fix team's brief (per `team-spawning-and-review-gates`) includes the plan path verbatim with the directive:

> READ THIS PLAN FIRST. Your first work item is the pre-fix verification checklist. Do NOT propose a fix until you have captured every observation in that checklist and your evidence either confirms the leading hypothesis or surfaces a stronger one. If your evidence contradicts the plan, write a counter-evidence note to `.architect-team/diagnostic-research/<test-id>/counter-evidence-<ts>.md`, signal idle, and let the orchestrator re-run diagnostic-research-team with your evidence as a new input.

The fix team can never silently override the plan. If the leading hypothesis is wrong, the fix team surfaces counter-evidence and re-triggers research — it does not patch its way past the plan.

## When this skill does NOT fire

To prevent over-triggering and wasted parallel work:

- **Test-author-error fixes inside a teammate's own slice.** If the teammate's local `root-cause-test-failures` 3-pass loop ended with `category: test-author-error` and the teammate is fixing its own expectation file, no SR is written and no research is needed.
- **Environment / fixture / race fixes inside a teammate's own slice** when the RCA documents the trigger AND the prevention strategy AND the fix is local to the teammate's `files_owned`. No SR is written; no research.
- **Visual-fidelity drift inside a single screen with a local CSS fix** (verdict `drift` resolved via fix-to-spec in `visual-fidelity-reconciliation` Phase E). Local, contained, no SR.

The skill fires ONLY when the failure has escalated past the teammate's slice via an SR. Test failures that the teammate self-resolves never reach the orchestrator and never trigger this skill.

## Hard rules (non-negotiable)

- Three researchers, always. Two researchers is not enough — the three-way disagreement is the falsification mechanism. Four is unnecessary cost.
- Researchers are read-only on source code and INDEPENDENT during Phase A. No consulting between drafts.
- Every hypothesis carries file:line citations and a falsification test. Prose-only hypotheses are not hypotheses.
- The architect review is a gate, not a formality. If a gap exists, the loop continues — the fix team is NOT spawned with an unvetted plan.
- The fix team starts every test-failure SR by reading the diagnostic plan in full and executing the pre-fix verification checklist BEFORE proposing any fix.
- The fix team can re-trigger research if its evidence contradicts the plan; it cannot patch past the plan.
- All artifacts persist under `.architect-team/diagnostic-research/<test-id>/` — the audit trail must survive past the SR's resolution so master review (Phase 7) can walk the chain.

## Anti-patterns to reject

| Rationalization | Rebuttal |
|---|---|
| "The originating teammate already ran 3-pass RCA; spawning three more researchers is duplicate work." | The teammate's RCA was inside its slice with its working hypothesis. Three fresh researchers with full-codebase read access and no anchor to the teammate's hypothesis is the falsification step. Skipping it ships the teammate's first guess at full team scale. |
| "The hypothesis is obvious — just spawn the fix team." | Bug-obvious-to-teammate ≠ root-cause-vetted. This is the same anti-pattern `root-cause-test-failures` rejects, escalated to orchestrator scale. Spawn the researchers; let them confirm or refute the obvious. |
| "Two researchers is enough to triangulate." | Two can converge on the same wrong answer. Three forces the architect to weigh divergence as a feature, not a bug — divergence is where the gap is. |
| "We can let the fix team verify the plan during its own work." | The fix team is incentivized to confirm, not falsify. The researchers are incentivized to disagree. Reversing that order is how wrong fixes ship. |
| "Architect review is slow; just consolidate the three drafts mechanically." | Mechanical consolidation produces a union of three drafts. The architect's value is rejecting drafts with gaps and forcing deeper passes. Skip the review and the plan is a least-common-denominator average rather than a robustness-vetted contract. |
| "If all three researchers converge on the same hypothesis, skip the architect — convergence is the answer." | Convergence without divergence-considered is the failure mode the architect catches. Three researchers all picking product-bug because none considered test-author-error is a real risk; the architect's coverage check is what catches it. |

## Where this skill plugs into the pipeline

- **Phase 3b — Solution-Requirement Intake (in `architect-team-pipeline`).** The orchestrator routes every SR with one of the test-failure `origin.kind` values through this skill before spawning the Phase 2 fix team. SRs with non-test-failure origins skip this skill and spawn directly.
- **`root-cause-test-failures` Phase C escalation.** When a teammate writes an SR with `origin.kind: rca-product-bug`, the orchestrator's next pickup invokes this skill against the SR. The teammate does not run this skill itself — it is orchestrator-level discipline.
- **`team-spawning-and-review-gates` ## Solution Requirements.** SR records gain a `diagnostic_plan_path` field for test-failure SRs (optional for other origins; required when this skill fires).
- **Master review (Phase 7).** Walks every test-failure SR and confirms each has a corresponding diagnostic plan + consolidated counter-evidence trail (if any). Test-failure SRs without a plan are an audit gap.
