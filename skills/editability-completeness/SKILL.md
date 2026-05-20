---
name: editability-completeness
description: Use when a feature that creates or edits entities has been implemented and you must verify that every attribute those entities expose which a user should be able to control actually has a working end-to-end editing path — UI control through state through the API into the database and back. Triggers — a "create a thing" or "edit a thing" flow exists; an entity has attributes (title, name, description, status, tags, owner, ...) and you are not certain every one a user should set is actually settable and persists; a value shows in the UI or the data model but you cannot find where the user sets it; Phase 5 cross-layer verification; an on-demand editability audit via /architect-team:editability-audit. Spawns three editability-reviewer agents that independently reason through what must be editable, argue to a converged list, route gaps as solution requirements, and re-review after fixes until all three agree the editable surface is complete.
---

# Editability Completeness — Is Every Attribute That Should Be Editable Actually Editable, End to End

A feature is not done when its screens render. It is done when **every attribute its entities expose that a user should be able to control actually has a working path from a UI control, through component state, through the API request, through the request schema, through the backend handler, into the database, and back on read.** A `title` that displays but cannot be set when the user creates the thing is a broken feature — not a cosmetic gap, not a polish item. It is a hole in what the product can do.

The existing gates do not catch this. `playwright-user-flows` verifies interactive elements *work*; a button can pass every Playwright test while the `title` field simply does not exist. `visual-fidelity-reconciliation` verifies the UI *looks* right; a screen can be pixel-perfect and still be missing a control. `coverage-mapping` works at requirement granularity, not attribute granularity. This skill closes the gap at the level it actually occurs: **the individual attribute.**

Three disciplines:

1. **Enumerate every attribute, not the obvious ones.** For every entity the feature creates or edits, list every attribute — from the database schema / migrations / ORM models, the API request/response schemas, the design screens, and the component code. The in-scope set is the UNION of all four sources. A field present in any one source is in scope; a field present in some sources but not others is itself a signal of a gap.
2. **Classify by who controls it — reason from the context of the ask.** For each attribute, decide who sets it: the user (at create, at edit, or both), the system, a derivation, or an action/transition. This is a judgment call. Make it from THIS feature's requirements and design — not from the attribute's name. The same name (`status`, `slug`, `priority`) is a user choice in one product and system-managed in another. When the requirements genuinely do not determine it, escalate to the human; never guess.
3. **Trace every user-controllable attribute end-to-end.** UI control → component/form state → API request payload → API request schema → backend handler → database write → read-back. A break at ANY stage, for an attribute that should be editable, is a gap. A control that exists but whose value never reaches the database is exactly as broken as a missing control.

This is a judgment-heavy task — "intuit what a real user would expect to control" — so it runs as a **three-agent team that argues to convergence**, and it is **multi-pass**: after the gaps are fixed, the team re-reviews until all three agree the editable surface is complete.

## The team: three reviewers, argue to convergence, act, repeat

The orchestrator (or the `/architect-team:editability-audit` command) runs this skill as a bounded outer loop. One **pass** is: independent analysis → argue to convergence → gaps become solution requirements → the normal fix loop acts → re-spawn for the next pass.

### Pass P, Round 1 — independent analysis (parallel)

The orchestrator spawns **three `editability-reviewer` agents in parallel**. Each receives the same brief (the feature, the requirements / `$REQ_DIR`, the relevant CODEBASE_MAP / ROUTE_MAP / DESIGN_MAP / INTEGRATION_MAP, the coverage-map slice) and its reviewer index (1, 2, 3).

Each reviewer INDEPENDENTLY — no consulting the others — does the full job: enumerate entities + attributes, classify each attribute, trace each user-controllable attribute end-to-end, and write its draft editable-surface map to:

```
<cwd>/.architect-team/editability/<feature-slug>/reviewer-<N>-pass<P>-<ts>.json
```

Independence is the rigor: three independent judgments about what must be editable catch the classification errors a single reviewer rationalizes past.

### Pass P, Round 2 — argue to convergence (round-robin)

After all three drafts exist, the reviewers converge. Each reviewer reads the other two drafts and, for every attribute where the **classification** or the **gap verdict** differs across drafts, debates it:

- The reviewer who disagrees must either cite evidence — a line from the requirements, the design, the data model, the domain — that changes the others' position, OR be persuaded by their evidence and revise its own draft.
- "It feels like it should be editable" is not evidence. "The proposal says 'users name their projects'" is evidence. "`created_at` is in the migrations with a `DEFAULT now()` and no UI anywhere references it" is evidence.

After each round-robin round each reviewer emits: `agreement: [<attributes where I now match both others>]` and `open_disputes: [<attribute: my classification vs theirs, with my evidence>]`. Loop until every reviewer's `open_disputes` is empty — the three now hold an identical canonical list. A dispute that survives **4 round-robin rounds** is genuinely undetermined by the available evidence: it moves to `escalations` (the human decides) and is removed from the blocking set so convergence does not stall.

This is the "argue until they have a clear list of asks" the team exists to produce.

### Pass P, Round 3 — system-architect robustness review (independent falsifier)

Three reviewers converging is not the same as three reviewers being right. They can converge on the same wrong classification — the classic failure is all three defaulting an ambiguous `status` to `system-managed` because none of them seriously considered it could be `dynamic-via-action`. Convergence-without-an-independent-check is itself a hole. So, after Round 2, the orchestrator dispatches the `system-architect` agent to review the converged editable-surface map for **robustness** — exactly as `diagnostic-research-team` does after its three researchers.

The architect does NOT re-do the enumeration. It asks: is the converged result robust?

- **Shared blind spot.** Did all three reviewers classify some attribute the same way without any of them citing real evidence — a converged guess wearing the costume of consensus? Each `system-managed` / `derived` classification must be justified, not just agreed.
- **Coverage.** Is there an attribute in the data model or the design that the converged map never classified at all?
- **Diversity of the editable set.** If the converged map says almost nothing is `user-editable`, is that the product, or three reviewers being conservative in lockstep?
- **Trace depth.** For every `user-editable` attribute marked `complete`, does the trace actually carry `file:line` evidence at all seven stages, or did the reviewers wave a stage through?
- **Escalation honesty.** Did a genuinely ambiguous attribute get force-classified to avoid an escalation?

The architect writes a verdict to `<cwd>/.architect-team/editability/<feature-slug>/architect-review-pass<P>-<ts>.md`: `pass`, or `gaps_found` with specific items routed back to named reviewers. On `gaps_found`, the orchestrator re-dispatches those reviewers to address the architect's findings, then convergence (Round 2) and this review (Round 3) repeat. Bounded at 3 architect-review cycles per pass; an unresolved item after that escalates to the human. Only an architect `pass` unlocks the converged map.

### Pass P — converged map + gaps become solution requirements

Once the architect's Round 3 verdict is `pass`, reviewer-1 (designated scribe) writes the converged map to:

```
<cwd>/.architect-team/editability/<feature-slug>/converged-map-pass<P>-<ts>.json
```

Every entry in the converged map's `gaps[]` becomes a **solution requirement** per `team-spawning-and-review-gates` with `origin.kind: "editability-gap"`. Unlike test-failure SRs, an editability-gap SR does NOT route through `diagnostic-research-team` — the diagnosis is already complete (the converged map names the exact attribute, the exact stage that breaks, and the exact file). The orchestrator's Phase 3b spawns a fix team directly. The SR's `acceptance_criteria` are precise and end-to-end:

- the create flow (and/or edit flow) for `<entity>` has a working control for `<attribute>`;
- setting it sends the field in the API request and the request schema accepts it;
- the backend handler persists it to `<table>.<column>`;
- reading the entity back returns the set value, and editing it persists across a reload;
- a real-backend integration test (per `dev-api-integration-testing` + the v0.9.5 real-backend discipline) covers the full round-trip.

### Act, then re-review (the multi-pass outer loop)

The fix teams act on the SRs through the normal Phase 2 → Phase 5 dev loop with full review gates. When the fixes land, the orchestrator **re-spawns the three reviewers for Pass P+1** — a fresh independent analysis, not a diff. They re-enumerate, re-classify, re-trace.

- If Pass P+1's converged map has an **empty `gaps[]` AND all three reviewers agree** → **satisfied**. Exit the loop.
- Else → another act + re-review cycle.

The outer loop is bounded at **3 passes**. If Pass 3 still shows gaps, the orchestrator surfaces the residual converged map to the human rather than looping forever — persistent gaps after three passes usually mean an unresolved ambiguity (an attribute whose editability the requirements never settled) that needs a human decision.

## The editability classification rubric (the "intuit what must be editable" core)

For each attribute, ask the framing question: **"In the user's mental model of this thing, would they expect to control this — and if so, when?"** Then classify:

- **`user-editable`** — settable when the user creates the thing AND changeable afterward. The attribute is part of what the thing fundamentally *is* from the user's point of view: names, titles, descriptions, labels, body content, the user's own choices and settings, relationships the user picks (assignee, category, parent, tags), quantities, user-set prices, visibility / privacy choices. **Tell:** imagine a user creating this thing — if they would be surprised they *could not* set this, it is `user-editable`.
- **`user-settable-at-create-only`** — the user picks it once at creation, immutable afterward because changing it would break identity or references. Sometimes a `type` / `kind`, a `slug` when URLs depend on it, an immutable external key. **Tell:** the user chooses it, but the design or domain implies it locks after creation.
- **`system-managed`** — the system always sets it; a user-facing control would be wrong. `id`, `created_at`, `updated_at`, `created_by` / `owner` derived from the session, sequence numbers, internal counters, audit fields. **Tell:** the value is a fact about the record's lifecycle or provenance, not a user choice.
- **`derived`** — not stored as an independently editable value; computed from other attributes. A `full_name` from first + last; an order `total` from line items; a `display_url` from a slug. **Tell:** editing it directly would be ambiguous or would desynchronize it from its inputs. The *inputs* are editable; the derived value is not — verify the inputs instead.
- **`dynamic-via-action`** — the user DOES change it, but through a verb / action / transition, not a form field. An order `status` moved by "Ship" / "Cancel" buttons; a `published` flag flipped by a "Publish" action. **Tell:** the user controls it, but the editing path to verify is "is there an action/control that triggers each valid transition" — not "is there a text input."
- **`ambiguous`** — the requirements and design genuinely do not determine whether or how the user controls this. Do NOT default to a guess. Escalate to the human with a structured question (see below). This is a valid, expected outcome — not a failure of the reviewer.

The classification is **contextual**. Reason from this feature's requirements and design every time. An `editability-reviewer` that classifies `status` as `system-managed` because "status is usually internal" without checking whether THIS design shows a status picker has not done the job.

### Escalating an ambiguous attribute

When a reviewer (or the converged team) cannot determine an attribute's classification from the sources, write a structured question — never a vague one — and surface it to the human via the orchestrator:

```
For <entity>.<attribute>, I cannot determine from the requirements/design whether the user
should control it:
  - If the user sets it: at create only, or also editable later?
  - If the system sets it: from what (session, a default, a computation)?
  - I see <evidence for> and <evidence against>. Which is intended?
```

Asking costs minutes; shipping the wrong classification ships either a missing control or a control that should not exist.

## The end-to-end trace (per user-controllable attribute)

For every attribute classified `user-editable`, `user-settable-at-create-only`, or `dynamic-via-action`, trace the editing path and record a verdict per stage. This is a pathway audit in the sense of `expensive-verification-debugging` — every stage is an independent potential break.

| Stage | What to verify | Applies to |
|---|---|---|
| `create_control` | The "add/create a thing" flow has a working control (input / select / picker / toggle) to set this attribute. | `user-editable`, `user-settable-at-create-only` |
| `edit_control` | The "edit the thing" flow has a working control to change it; for `dynamic-via-action`, an action/control exists for each valid transition. | `user-editable`, `dynamic-via-action` |
| `control_to_state` | The control is bound to component / form state — it is not a dead element. | all controllable |
| `state_to_request` | The attribute is included in the create/update API request payload. | all controllable |
| `request_schema` | The backend endpoint's request schema / validation accepts the field — it is not silently stripped or ignored. | all controllable |
| `handler_to_db` | The backend handler writes the field to the database; the column exists in the schema / migration. | all controllable |
| `read_back` | Reading the entity returns the value; an edit persists across a reload. | all controllable |

Read the actual sources at every stage: the component code, the form state, the HTTP client call, the API route handler, the request schema (OpenAPI / pydantic / zod / TypeScript types), the ORM model, the migrations. Cite `file:line` for every verdict.

### Gap kinds

A `gap` is any must-be-editable attribute whose trace breaks. Record the kind:

- **`missing-control`** — the attribute should be editable but no UI control sets/edits it. (The user's canonical example: an entity has a `title`, but the create flow has no title field.)
- **`dead-control`** — a UI control exists but the value never reaches the database; the trace breaks at `state_to_request`, `request_schema`, or `handler_to_db`. A control that does nothing.
- **`orphan-field`** — a data-model field that should be editable is reachable from neither the create nor the edit flow.
- **`no-readback`** — the value can be set but reloading the entity does not show it; it did not persist or is not returned.
- **`schema-mismatch`** — the UI sends a field the API request schema rejects, or the API accepts a field with no backing column.

## The converged editable-surface map artifact

```json
{
  "schema_version": 1,
  "feature": "<feature slug>",
  "pass": 1,
  "converged_at": "<ISO 8601 UTC>",
  "reviewers_agreed": ["editability-reviewer-1", "editability-reviewer-2", "editability-reviewer-3"],
  "entities": [
    {
      "entity": "Project",
      "attribute_sources": ["migrations/0007_projects.sql", "api: ProjectCreate / ProjectUpdate", "design: screens/new-project.png", "components: NewProjectForm.tsx"],
      "attributes": [
        {
          "attribute": "title",
          "classification": "user-editable",
          "reasoning": "proposal.md line 14: 'users name their projects'; the new-project design screen shows a title field",
          "trace": {
            "create_control": { "status": "missing", "evidence": "NewProjectForm.tsx has name, description — no title input" },
            "edit_control":   { "status": "missing", "evidence": "EditProjectForm.tsx — no title input" },
            "control_to_state": { "status": "n/a", "evidence": "no control to bind" },
            "state_to_request": { "status": "n/a", "evidence": "" },
            "request_schema": { "status": "ok", "evidence": "ProjectCreate schema includes title: str" },
            "handler_to_db": { "status": "ok", "evidence": "create_project() writes row.title; projects.title column exists" },
            "read_back": { "status": "ok", "evidence": "GET /projects/:id returns title" }
          },
          "verdict": "gap",
          "gap_kind": "missing-control"
        }
      ]
    }
  ],
  "gaps": [
    { "entity": "Project", "attribute": "title", "gap_kind": "missing-control", "sr_written": "SR-editability-project-title-<ts>.json" }
  ],
  "escalations": [
    { "entity": "Project", "attribute": "archived_at", "question": "<structured question for the human>" }
  ],
  "satisfied": false
}
```

`satisfied` is `true` only when `gaps` is empty and all three reviewers confirmed the converged map.

Per `mempalace-integration`, the orchestrator auto-mines each converged map to MemPalace: `mempalace --palace <palace> mine "<converged-map path>" --wing <wing> --room editability-maps`. Future runs against the same project can then search prior editable-surface maps before re-reviewing.

## How this differs from neighboring skills

- `playwright-user-flows` — tests that interactive elements *work*. This skill checks whether the *right controls exist at all* and reach the database. A flow can be fully Playwright-tested and still be missing the `title` field.
- `visual-fidelity-reconciliation` — checks the UI *looks* like the design. This skill checks the UI *exposes the controls the data model needs*.
- `design-fidelity-mapping` / DESIGN_MAP — enumerates visual specs, interactive elements, link targets. This skill consumes those AND the data model, and adds the per-attribute classification + the database trace.
- `coverage-mapping` — requirement granularity. This skill — attribute granularity.

They are complementary. A feature can pass all of the above and still fail this skill, which is exactly why this skill exists.

## Where this skill plugs into the pipeline

- **Phase 1 (planning).** Informs the coverage map: for each entity a requirement introduces, the spec should already enumerate the user-editable attributes. The planning validation can consult this skill's rubric to avoid under-specifying.
- **Phase 5 (cross-layer integration).** The mandatory home. Editability is inherently cross-layer (UI + API + DB); Phase 5 is where both layers are integrated. For any feature with a create or edit flow, the orchestrator runs the full editability-completeness team (three reviewers, converge, gaps → SRs, multi-pass) alongside the visual-fidelity regression sweep.
- **Phase 7 (master review).** Confirms the editability team reached `satisfied` for every entity-bearing feature. An unsatisfied editability loop is a coverage gap; re-spawn.
- **`/architect-team:editability-audit`.** On-demand invocation against an existing codebase.

## Hard rules (non-negotiable)

- Three reviewers, always — independent in Round 1, arguing in Round 2. Two cannot triangulate a judgment call; the third is the tie-break and the falsifier.
- The Round 3 `system-architect` robustness review is a non-negotiable gate. Three reviewers converging is not proof they are right — they can converge on a shared blind spot. The converged map is not final, and no `editability-gap` SR is written, until the architect's verdict is `pass`.
- Reviewers are **analysis-only**. They classify, trace, and write the map and the SRs. They do NOT write feature code — adding a field end-to-end is real dev work that must go through Phase 2 → Phase 5 review gates, the reuse-first ladder, and the test requirements. A reviewer that edits a component bypasses every one of those.
- Every classification carries `reasoning` citing a source (requirements / design / data model). A classification with no citation is a guess.
- Every trace stage carries `file:line` evidence. "Looks fine" is not a verdict.
- Enumerate from all four sources (DB schema, API schemas, design, components) — the union. A field in the data model but in no design screen is still in scope (it may be an `orphan-field` gap or correctly `system-managed`).
- Ambiguous attributes escalate to the human. Never default-guess a classification under time pressure.
- The loop is multi-pass and bounded (3 passes). After a fix, re-review from scratch — do not assume the fix was complete.
- An editability-gap SR spawns a fix team directly; it does not route through `diagnostic-research-team` (the gap is already fully diagnosed).
