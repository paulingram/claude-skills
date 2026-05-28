# Design: verified-agent-output (v2.0.0)

## Reference

Full WHY + WHAT + ACs in `proposal.md`. This file is the architectural deep-dive: the root-cause taxonomy, the design alternatives considered, the chosen framework's per-layer mechanics, the costs accepted, the Reuse Decisions.

## Root-cause taxonomy: ONE shape, four faces

Before designing the fix, name the failure precisely. All four known failures are structurally identical:

```
agent receives task → agent does work → agent writes self-report → orchestrator accepts self-report
                                                                    └─ NO MACHINE PROOF anywhere in the path
```

The differences across the four cases are surface, not structural:

| Failure shape | What the agent had license to fudge | What machine proof would have caught it |
|---|---|---|
| Scope-narrowing (v1.4.0) | The interpretation of the user's prompt | Oracle-derived structural spec, surfaced and accepted BEFORE work starts |
| Git-stash clobber (v1.6.0) | The state-of-the-tree the work was diffed against | Bash-history audit at task-completion time |
| Frontend faking API (v1.7.0) | The contents of the response the UI consumed | Diff-greppable detector for design-literals, MSW handlers, hardcoded payloads |
| Oracle structure mismatch (new) | The shape of what was built relative to the reference | Deterministic structural-diff tool against a frozen reference |

The pattern: **the agent had a SUBJECTIVE judgment call at a critical moment and was trusted to make it correctly.** Documentation-only discipline tells the agent to make the call correctly. It does not make the call objective.

The structural fix is to **convert each subjective judgment call into a machine-verified objective check**.

## Design alternatives considered

Four candidate frameworks were evaluated against the user's bar (all 4 enforcement layers + perfect adherence). The chosen design is Alternative D — the layered hybrid. Each rejected alternative's rationale is named so the choice is auditable.

### Alternative A: One mega-hook with a universal verifier

**Shape:** A new `verify-everything-hook.py` runs after every teammate task and tries to detect every failure shape in one pass.

**Why rejected.** Conflates orthogonal failure modes into one bottleneck. The hook becomes a god-object that nobody can reason about; adding the 5th failure shape requires understanding the 4 prior ones; debugging a false-positive becomes a forensic exercise. The existing `pipeline-completion-audit.py` Stop hook already shows the limits of this pattern — it grew from 3 checks to 11 in the span of v0.9.x and is harder to extend each release.

### Alternative B: Worktree-per-teammate dispatch

**Shape:** Every teammate is spawned into its OWN git worktree, so destructive ops can't clobber others; merged at Phase 4 via the orchestrator.

**Why rejected.** Solves only the v1.6.0 failure. Does not address scope-narrowing, fake data, or oracle mismatch — those have nothing to do with shared filesystem state. v1.6.0 already deferred this as a candidate for v1.7+; v2.0.0's tool-mediated `verify-baseline-clean` is a much lower-complexity solution to the same problem (and works without per-teammate worktrees at all). Worktree-per-teammate is the right answer to a different, narrower question — and is preempted by Layer 3's bash-history audit.

### Alternative C: Replace the agent dispatch model with a constrained-tool-only execution model

**Shape:** Agents can ONLY emit tool calls; every tool call has a verifier that runs before the next call is allowed.

**Why rejected.** Architecturally cleanest but practically incompatible with Claude Code's harness. The harness's `Agent` and `SendMessage` primitives are the team-dispatch contract; replacing them is out of scope for a plugin. v2.0.0 has to live within the harness's primitives, layer on top of them, and verify what agents produce — not replace how agents are dispatched.

### Alternative D (CHOSEN): The five-layer Verified Agent Output framework

**Shape:** Each failure shape gets its OWN layer at the RIGHT phase, with machine-mediated verification specific to its shape. The layers compose; an agent's work passes ONLY when every applicable layer verifies it.

**Why chosen.**

- **Hits all four enforcement layers** the user named: hook-enforced (schema v7 + Stop-hook VAO assertion), tooling-enforced (`hooks/vao_tools.py`), test-suite-enforced (the synthetic-fixture suite for each known failure case), run-history-enforced (Layer 4 shape-detection).
- **Each layer is independently reasoning-tractable** — a developer extending the framework with a 5th failure shape adds a 5th layer or a 5th tool, doesn't touch the others.
- **Each layer's failure cost is bounded** — a Layer-1 false positive blocks the run with a clear actionable user surface; a Layer-3 false positive surfaces the tool's deterministic JSON output the user can inspect.
- **Composes with existing v0.9.13 / v0.9.19 / v0.9.34 patterns** rather than replacing them — the producer-cannot-be-checker insight is the philosophical anchor; the 3-reviewer convergence at Phase 5 is the existing late net; v2.0.0 adds the early nets.
- **Cost is honest** — ~30-40% more agent-dispatches per run, ~15-25% more wall-clock, ~2× tokens. Named in the proposal, not buried.

## The five layers — per-layer mechanics

### Layer 1: Oracle-derivation gate (Phase 0.5)

**Position in pipeline.** Inserted between Phase 0 (Detection & Normalization) and Phase 1 (Planning Validation). Runs after `openspec` artifacts exist; before the 100%-coverage validation loop.

**Trigger condition.** Active when the requirement contains any of:
- A parity verb (`match`, `rebuild`, `mirror`, `parity`, `make like`, `replicate`) — the v1.4.0 verb list.
- A reference codebase path (one or more `oracle_path` keys in the OpenSpec design metadata).
- A design mockup directory.
- A reference URL.

If none of those signal, Layer 1 is a no-op (the proposal-refiner's free-text grade is sufficient for greenfield work).

**Mechanism.** A new `oracle-deriver` agent (opus, read-only Bash + Read tools, no Edit) is dispatched. It:

1. **Reads the named oracle** — the reference codebase / design / URL.
2. **Walks its structure** — component tree (for code), screen list + element list + dynamic values (for design), endpoint surface (for backend reference), data model (for schema).
3. **Produces a structured canonical spec** at `<workspace>/.architect-team/oracle-spec/<change-name>.json`:

   ```json
   {
     "schema_version": 1,
     "change_name": "<name>",
     "oracle_path": "<absolute path>",
     "derived_at": "<ISO 8601 UTC>",
     "spec_shape": "component-tree" | "design-map" | "api-contract" | "data-model" | "hybrid",
     "tree": [ /* deterministically-ordered structural enumeration */ ],
     "elements": [ /* every interactive element with required wiring */ ],
     "dynamic_values": [ /* every value with its required data binding */ ],
     "schemas": [ /* every contract surface */ ],
     "_human_review_required": true
   }
   ```

4. **The orchestrator surfaces the spec to the user** with ONE confirmation gate: *"Here is the structural spec derived from the oracle. Confirm this is what we are building, or say what's wrong."*

5. **On confirm** → `_human_review_required: false`, the spec is frozen, and every Layer 2 / 3 / 4 downstream check measures against it.
6. **On reject** → the user's correction text re-feeds the oracle-deriver; re-derived; re-surfaced. Bounded at 3 cycles per `common-pipeline-conventions`'s domain-gate convention.

**Why this fixes the four known failures.**
- **Scope-narrowing:** the agent's interpretation IS the derived spec; the user reviews IT, not the agent's prose summary. Reframing is impossible because the agent doesn't get to reframe — it must show its structural enumeration.
- **Oracle structure mismatch:** the structural diff is the FIRST artifact; subsequent work measures against it deterministically.

### Layer 2: Adversarial-reviewer pairing (extends Phase 3)

**Position in pipeline.** Concurrent with every Phase 3 teammate dispatch. Replaces the producer-checker pattern's "one independent task-reviewer" model with a "one independent task-reviewer + one shape-matched adversarial-reviewer" pattern.

**Task-shape taxonomy.** The Phase 2 spawn brief includes a `vao_task_shape` field, computed from the task's surface:

| Task shape | Triggered by | Adversarial role assigned |
|---|---|---|
| `parity-verb` | The frozen oracle spec is referenced by the task | `oracle-divergence-hunter` |
| `backend-dep` | The task is `frontend` and references a `pending-backend` or `missing-api-for-frontend-element` SR | `fake-data-hunter` |
| `shared-tree` | ANY teammate dispatch (always-on) | `git-discipline-hunter` |
| `dynamic-value` | The task touches a designed screen with non-trivial `dynamic_values[]` in the oracle spec | `hardcoded-literal-hunter` |
| `default` | None of the above | `general-anti-pattern-hunter` (a lighter sweep across the four shapes) |

**Mechanism.** The orchestrator spawns the teammate + the adversarial-reviewer in the same Phase 2 batch. The adversarial-reviewer:

- Receives the teammate's `task_id`, the frozen oracle spec, and the task brief.
- Polls the teammate's tool-call log (the `<cwd>/.architect-team/teammates/<teammate>-toolcalls.jsonl` stream — a new artifact the harness writes for every teammate task in v2.0.0).
- Independently re-runs the relevant verification: for `oracle-divergence-hunter`, runs `vao verify-oracle-match` against the teammate's diff; for `fake-data-hunter`, runs `vao verify-no-fake-data`; for `git-discipline-hunter`, runs `vao verify-baseline-clean`; for `hardcoded-literal-hunter`, walks the diff for design literals.
- Writes an `adversarial_review` block to the SAME `<cwd>/.architect-team/reviews/<task-id>.json` evidence file:

  ```json
  "adversarial_review": {
    "reviewer": "adversarial-reviewer-oracle-divergence-hunter",
    "shape": "parity-verb",
    "verdict": "pass" | "fail",
    "tool_invoked": "vao verify-oracle-match",
    "tool_verdict_path": "<.architect-team/vao-verdicts/<task-id>-oracle-match.json>",
    "findings": [ /* per-finding citation if fail */ ],
    "reviewed_at": "<ISO 8601 UTC>"
  }
  ```

- The hook's v7 schema requires BOTH `independent_review.verdict == "pass"` AND `adversarial_review.verdict == "pass"`. The Phase 3 gate opens ONLY when both pass.

**Why this fixes the four known failures.**
- **Fake data, git stash, oracle mismatch:** the shape-matched adversarial-reviewer is purpose-built to find that specific failure; it's not a generalist scan that might miss it.
- **Scope-narrowing:** even when Layer 1's gate passes, the `parity-verb` adversarial-reviewer re-checks the teammate's executed work against the frozen spec; if the teammate's interpretation narrowed mid-execution, this catches it.

### Layer 3: Tool-mediated execution proof (`hooks/vao_tools.py`)

**The four tools** (each is a Python module callable from `hooks/vao_tools.py`, also exposed as a CLI for the adversarial-reviewer):

1. **`verify-oracle-match`**
   - Input: a built path (component tree, route table, schema file) + the frozen oracle spec JSON.
   - Output: `{matched: bool, divergences: [{path, expected, actual, severity}], match_pct: float}`.
   - Mechanism: deterministic structural walk; sorted by path. Component-tree comparisons strip whitespace and ordering noise. Schema comparisons normalize field ordering. The tool's output is bit-stable for given inputs.

2. **`verify-baseline-clean`**
   - Input: the teammate's tool-call log path + an optional baseline SHA.
   - Output: `{clean: bool, violations: [{op, args, line, ts}]}`.
   - Mechanism: greps the JSONL stream for Bash invocations matching any of the v1.6.0 forbidden ops; produces structured violation records with line citations.

3. **`verify-no-fake-data`**
   - Input: a list of changed files + the frozen oracle spec's `dynamic_values[]`.
   - Output: `{clean: bool, hits: [{file, line, match, category}]}`.
   - Mechanism: regex sweep for design-literal strings from the spec, common faked-data patterns (`John Smith`, `jane.doe@example.com`, `$1,234.00`, lorem ipsum fragments), MSW handler signatures, `page.route(... fulfill ...)`, hardcoded JSON response objects outside test fixtures.

4. **`verify-every-element`**
   - Input: a list of component paths + the frozen oracle spec's `elements[]`.
   - Output: `{coverage: float, missing: [...], stub: [...], untested: [...]}`.
   - Mechanism: for each oracle-named element, locate it in the built components (selector / role / testid match), confirm it has a non-stub handler (not `() => {}` / empty onClick / commented-out), confirm a Playwright test drives it via `page.click` / `page.fill` / etc.

5. **`verify-rendered-parity`** (the rendered-output gate — added in response to the heirship-app-v2 chrome-level breadcrumb evidence)
   - Input: a candidate URL (the deployed-or-dev render of the work) + an oracle URL (or a screenshot path) + the frozen oracle spec's `chrome_topology[]` and `layout_anchors[]`.
   - Output: `{matched: bool, divergences: [{anchor, expected_level, actual_level, severity}], pixel_diff_pct: float, screenshot_paths: {oracle, candidate, diff}}`.
   - Mechanism: launch a headless Playwright browser; navigate to each URL; dump the **rendered DOM tree** (not the source component tree) and a screenshot of the visible viewport; compare **architectural mount level** of each `chrome_topology[]` entry (e.g., breadcrumb expected in `AppShellHeader` but found inside `[data-testid="page-body"]` → divergence with severity `architectural-mismatch`); compare screenshots with a pixel-diff library (`pixelmatch` or equivalent stdlib alternative).
   - **Crucial discipline this tool enforces:** an agent's "pixel parity: pass" self-attestation derived from reading source code is FORBIDDEN. The schema v7's `visual_fidelity_review` field MUST cite this tool's verdict path; a verdict generated from any other source (including the agent's own prose) is a hook-blocking violation.
   - **Why this tool is distinct from `verify-oracle-match`:** the latter walks the component TREE (source), which is sufficient for schema / API / structural-data parity but blind to chrome-level architectural divergences where the element exists in source but at the wrong mount point. The canonical failure: the heirship-app-v2 `TAMatterDetail.tsx` contained a `<TaCrumbs />` in its page body; the oracle has the same `<TaCrumbs />` mounted in `AppShellLayout`. A source-tree walk says "TaCrumbs present in both ✓"; the rendered DOM shows them at different parent nodes; only the rendered comparison surfaces the divergence.

**Each tool writes a verdict JSON to `<cwd>/.architect-team/vao-verdicts/<task-id>-<tool>.json`.** The evidence schema v7 requires the `*_review` field to cite the verdict path.

**Why these tools and not others.** Each tool maps DIRECTLY to a known failure shape. The user authorized a structural fix to the four known failures + the rendered-vs-source-audit gap surfaced during proposal review; the five tools instantiate one-per-shape. Future failure shapes get future tools — the pattern is extensible without re-architecting.

### Layer 4: Run-history shape detection (Phase −2)

**Position in pipeline.** Inserted at the END of Phase −2, after the bug-classifier emits its verdict and before the routing decision is finalized.

**Mechanism.**

1. `.architect-team/run-history/` accumulates one file per completed (or escalated) run:

   ```json
   {
     "schema_version": 1,
     "run_id": "<id>",
     "completed_at": "<ISO 8601 UTC>",
     "verdict": "green" | "red-escalation" | "user-aborted",
     "requirement_shape": {
       "parity_verbs": ["match"],
       "oracle_referenced": true,
       "layers_touched": ["frontend", "backend"],
       "failure_modes_caught": ["scope-narrowing-attempt-blocked"],
       "failure_modes_missed": []
     },
     "vao_layers_engaged": [1, 2, 3, 4]
   }
   ```

2. The new `vao detect-shape` tool reads all history files, computes the shape-fingerprint of the current requirement, and returns the top-3 matching prior runs (cosine similarity over the shape vector).

3. If a matching prior run had `verdict: red-escalation` AND its `failure_modes_caught` contains any blocking-mode, the orchestrator surfaces this BEFORE Phase −1:

   *"This run's requirement shape matches 2 prior runs that hit blocking failures (run-id X on date Y caught scope-narrowing; run-id Z on date W caught oracle-mismatch). The v2.0.0 layers paired with each prior failure will be engaged for this run by default. Confirm this is the intended interpretation, or describe a different shape."*

4. The user's response either confirms or reshapes the run. The orchestrator records the reshape.

**Why this is necessary.** Layers 1–3 catch known shapes. Layer 4 makes the plugin LEARN — each new failure becomes a future check. Without Layer 4, v2.1.x is back to whack-a-mole on novel shapes.

### Layer 5: Structural test enforcement

**Position.** The plugin's own pytest suite. Mirrors v1.4 / 1.6 / 1.7's test pattern.

**What the tests assert.**
- Layer 1: `oracle-deriver` agent exists with the right frontmatter; the 3 pipeline bodies invoke it at Phase 0.5 (or the analogous insertion).
- Layer 2: every teammate spawn brief in the pipeline body's documentation includes the `vao_task_shape` field; the spawn brief schema in `team-spawning-and-review-gates` includes adversarial-pairing rules.
- Layer 3: each `hooks/vao_tools.py` tool has a unit test with a positive + negative synthetic-fixture round-trip.
- Layer 4: `common-pipeline-conventions` has the `## Run-history shape detection` section; the four shape-vector fields are documented.
- The four known-failure synthetic fixtures under `tests/fixtures/vao/` MUST be detected (positive case) and the v2.0.0 pipeline MUST block them; this is the *test-suite-enforced* layer the user named.

## Composition with existing patterns

v2.0.0 does NOT remove any existing gate. It LAYERS:

| Existing gate (v1.7.0) | What it catches | v2.0.0 changes |
|---|---|---|
| `task-reviewer` (Phase 3, independent review) | Self-attestation gap on per-task correctness | Unchanged — still required; v2.0.0 schema v7 adds `adversarial_review` ALONGSIDE |
| `test-completeness-verifier` (Phase 3 + 5) | Missing unit / integration / Playwright kinds | Unchanged |
| `interaction-completeness` (Phase 5) | Unwired controls, placeholder pages, hardcoded literals | Unchanged — late net; Layer 1 + 2 catch the same shapes EARLIER |
| `editability-completeness` (Phase 5) | Attributes the UI can't actually edit | Unchanged |
| `visual-verification-team` (Phase 5) | Visual drift vs DESIGN_MAP | Unchanged |
| `system-architect` Master Review Audit (Phase 7) | Coverage-map self-attestation gap | Extended — now also walks VAO verdicts |
| `documentation-currency` audit (Phase 8) | Stale docs after a run | Unchanged |
| `pipeline-completion-audit.py` (Stop hook) | Incomplete-state termination | Extended — now also blocks on missing VAO verdicts |

The picture: v2.0.0 EARLIER nets catch the failures the LATER nets had to catch post-facto. The later nets stay as the regression safety, but the earlier nets reduce wasted Phase-3-through-Phase-5 cycles by blocking at intake / per-task instead of at integration.

## Reuse Decision Log

### RD-1: NEW `skills/verified-agent-output/SKILL.md`

**Decision:** Build new.
**Justification.** The framework is a cross-cutting discipline distinct from any existing skill. Adding it to `common-pipeline-conventions` would bloat that file past tractability (it is already ~1000 lines); embedding it in `team-spawning-and-review-gates` would conflate per-task spawn rules with cross-cutting verification. The new skill is the canonical home; the existing skills cross-reference it.

### RD-2: NEW `agents/oracle-deriver.md`

**Decision:** Build new.
**Justification.** No existing agent has the read-the-oracle-and-produce-canonical-spec role. The closest are `interaction-intuiter` (similar role for interactive elements; could be considered an extension) and `route-mapper` (similar role for routes). The cleanest design extracts the shared structural-walk pattern into its own agent. Decision is a build-new + a future v2.1.x candidate to refactor `interaction-intuiter` to invoke `oracle-deriver` for the design-map case.

### RD-3: NEW `agents/adversarial-reviewer.md`

**Decision:** Build new.
**Justification.** No existing reviewer agent has the role-paired adversarial mandate. `task-reviewer` is the closest analog (independent per-task review) but its mandate is "verify the work is correct"; the adversarial-reviewer's mandate is "verify the specific anti-pattern this task-shape is prone to is absent." The two are complementary, not substitutable — both are required by schema v7.

### RD-4: NEW `hooks/vao_tools.py`

**Decision:** Build new.
**Justification.** The four deterministic verification tools have no existing analog. The closest is `hooks/review_evidence_schema.py` (shared validation logic) — `vao_tools.py` follows the same module-not-hook pattern: imported by hooks, also runnable as a CLI by the adversarial-reviewer.

### RD-5: Extend `hooks/review_evidence_schema.py` to schema v7

**Decision:** Extend.
**Justification.** The schema is the single source of truth; bumping in place is the right pattern. The v7 bump mirrors v6 (v0.9.19), v5 (v0.9.13), v4 (v0.9.5), v3 (v0.9.0), v2 (v0.5.0) — each added required fields. The four new v7 fields follow the same precedent.

### RD-6: Extend `hooks/pipeline-completion-audit.py` to assert VAO verdicts

**Decision:** Extend.
**Justification.** The Stop hook is the existing gate for incomplete-run termination. Adding VAO verdict assertions is a natural extension (same exit semantics, same finding-format).

### RD-7: Extend 3 pipeline SKILL.md bodies for Phase 0.5 + the new task-shape field

**Decision:** Extend.
**Justification.** Same pattern as v1.4.0 (`## Default mode of operation`), v1.6.0 (`## Operating rules` entry), v1.7.0 (`## Frontend missing-API discipline` entry). The pipeline bodies remain the canonical phase contract.

### RD-8: Extend `skills/team-spawning-and-review-gates/SKILL.md` for the adversarial-pairing + manifest v2

**Decision:** Extend.
**Justification.** The skill is the canonical home for spawn discipline. The pairing rule belongs alongside the existing `## Plan-approval-mode triggers` section.

### RD-9: Extend `skills/common-pipeline-conventions/SKILL.md` for Layer 4 shape-detection

**Decision:** Extend.
**Justification.** Cross-cutting convention; same pattern as the existing notification / dispatch-mode / MemPalace wake-up sections.

### RD-10: NEW `tests/test_verified_agent_output.py` + `tests/fixtures/vao/`

**Decision:** Build new.
**Justification.** Each new layer needs structural tests; the synthetic-fixture suite is the test-suite-enforced layer the user named.

### RD-11: NO worktree-per-teammate dispatch in v2.0.0

**Decision:** Deferred — Layer 3's `verify-baseline-clean` solves the same problem at lower complexity.
**Justification.** v1.6.0 deferred this as a v1.7+ candidate; v2.0.0's tool-mediated baseline-history audit preempts the need. Worktree-per-teammate becomes a v2.x+ candidate if Layer 3's audit proves insufficient (no evidence it will).

### RD-12: NO replacement of the `Agent` / `SendMessage` harness primitives

**Decision:** Build on top, never replace.
**Justification.** The harness primitives are the team-dispatch contract; replacing them is outside the plugin's scope. v2.0.0 layers verification on top.

## Failure-mode mapping (the audit)

Cross-walk of every named v1.x failure against the v2.0.0 layer that catches it:

| Failure | Caught at v2.0.0 layer | Caught how |
|---|---|---|
| v1.4.0 — silent scope narrow at intake | Layer 1 | Oracle-deriver shows the structural spec; user accepts BEFORE Phase 2; agent doesn't get to "interpret" |
| v1.4.0 — agent reframes mid-run | Layer 2 (`parity-verb` shape) | `oracle-divergence-hunter` runs `verify-oracle-match` against the teammate's diff at task completion |
| v1.6.0 — teammate runs `git stash` | Layer 2 (`shared-tree` shape, always-on) | `git-discipline-hunter` runs `verify-baseline-clean` on the teammate's tool-call log |
| v1.7.0 — frontend mocks the API | Layer 2 (`backend-dep` shape) | `fake-data-hunter` runs `verify-no-fake-data` on the diff |
| v1.7.0 — frontend hardcodes the response | Layer 2 (`backend-dep` shape) + Layer 2 (`dynamic-value` shape) | Same — overlapping coverage by design |
| v1.7.0 — frontend silently stubs the UI | Layer 2 (`backend-dep` shape) + Layer 3 (`verify-every-element`) | Coverage check finds the stub element |
| (NEW) — oracle structure mismatch | Layer 1 + Layer 2 (`parity-verb` shape) + Layer 3 (`verify-oracle-match`) | Deterministic structural diff; the teammate cannot pass without matching |
| (NEW) — source-code-audit "pixel parity: pass" false positive (heirship-app-v2 chrome-level breadcrumb) | Layer 3 (`verify-rendered-parity`) | Rendered DOM + screenshot diff; an agent's prose attestation derived from source-code reading is forbidden by schema v7 (the `visual_fidelity_review` field MUST cite the tool's verdict path) |
| (NEW + unnamed) — novel failure shape on future run | Layer 4 — gets folded into the shape-fingerprint registry; future runs with the same shape get a known check | The run-history feed makes the framework learn |

## Costs accepted

The user explicitly authorized a LARGE architectural appetite, but the costs deserve to be on the record:

1. **Wall-clock per run: +15-25%.** The Phase 0.5 oracle-derivation adds one agent-dispatch; each Phase 3 teammate adds one paired adversarial-reviewer dispatch. The Phase 5 reviews are unchanged, so the late nets don't grow.
2. **Tokens per run: ~2×.** Each adversarial-reviewer is a full opus dispatch. For a 5-teammate Phase 2 batch, that's 5 extra opus dispatches.
3. **Schema bump = breaking change.** Runs in flight at the v2.0.0 release cut over must re-spawn teammates against the v7 evidence schema. This is named in the migration guide.
4. **Cognitive overhead.** A future plugin developer must reason about WHICH shape attaches to a task, WHICH layer catches WHICH failure. The mitigation is the per-layer skill body documenting exactly that, with the failure-mode mapping above as the audit trail.
5. **Coverage gaps remain possible.** A novel failure shape that doesn't match any of the four named tools will pass Layer 2 + 3. Layer 4 makes the framework LEARN, but the first instance of a novel shape will still slip. This is the irreducible cost of any verification framework; the framework can only check for shapes it knows about. The mitigation is making sure unknown shapes get recorded so the NEXT run with the same shape benefits.

These costs are the price of converting subjective agent judgment into objective machine verification at the four points the plugin has been patching one-at-a-time. The trade is on-bar for the user's stated appetite.

## Migration / backwards compatibility

- **v1.7.0 → v2.0.0:** BREAKING. Review-evidence schema v6 → v7. The hook will reject v6 evidence files.
- **Migration path.** Runs not in flight at upgrade: no action needed; new runs use v7 from Phase 0.5 forward. Runs in flight at upgrade: re-spawn the active teammates with the v7 schema; their prior v6 evidence is discarded.
- **Opt-out.** A new `--no-vao` flag on the pipeline-driving slash commands disables Layers 1, 2, 4, 5 (Layer 3 tools remain available for ad-hoc invocation). This is the escape hatch for projects that can't afford the +15-25% wall-clock cost; the trade-off (re-opening the v1.x failure modes) is documented explicitly.
- **Tests.** Existing tests pass. New tests assert the v2.0.0 structure.

## Version

**v2.0.0** — MAJOR bump. Schema break, new mandatory phase, architecturally distinct dispatch model. Per `## Why this is a v2.0.0, not a v1.8.0` in the proposal.
