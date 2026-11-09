---
name: intuition-map-lifecycle
description: Lane-callable lifecycle discipline for a frontend codebase's INTERACTION_INTUITION_MAP.md, with three verbs — ensure (guarantee the map exists before any Playwright test is authored, dispatching interaction-intuiter in pipeline context or running the same rubric inline with an inline bulk-verify ad hoc), grow (upsert the elements and routes a user-specified flow exercises as confirmed entries carrying source user-flow, with no bulk-verify round-trip because the user specifying the flow IS the confirmation), bug-path-upsert (record a resolved bug path with source bug-path plus regression_refs naming the covering debug-flow test and the SR or bug slug). Triggers — any lane about to author or review Playwright tests, a user handing over a concrete UX flow, a debugging lane closing out a bug. The deterministic engine lives under scripts/intuition_lifecycle/ and this skill is its contract.
user-invocable: false
---

# intuition-map-lifecycle

`interaction-intuition` produces the map. Nothing, until now, kept it alive.

The map is created during Phase −1 by a dispatch-only agent and confirmed at the
Phase −1D bulk-verify gate — which means it exists only when a full pipeline run
happened to produce it, and it never learns anything after that gate closes. A
user hands over a concrete UX flow and the map does not hear about it. Debugging
discovers a real path through the UI that nobody intuited and the map does not
hear about that either. Meanwhile `playwright-user-flows` authors tests against
`ROUTE_MAP.md` alone, so even an existing map goes unread.

This skill is the sister discipline that closes those three holes. It is cheap,
callable from ANY lane, and deliberately small — three verbs over one artifact.
It does not orchestrate a suite (that is `playwright-suite-builder`) and it does
not re-define the rubric (that is `interaction-intuition`). It keeps the map
present, current, and honest about where each of its entries came from.

## When this fires

- **Before any Playwright test is authored, anywhere.** `playwright-user-flows`
  Step 1 calls `ensure`; the suite-builder calls it at P2. Authoring against a
  missing map is the R1 gap this verb exists to close.
- **When a user specifies a concrete flow.** `ux-test-builder` calls `grow` for
  the U2 literal flow and each U5 distilled flow; an ad-hoc *"write me a
  Playwright test that does X"* is the same case.
- **When a debugging lane resolves a bug.** `bug-fix-pipeline` calls
  `bug-path-upsert` at B2 (repro authored) so the path the bug travelled is in
  the map with a pointer back to the test that now covers it.

## The three verbs at a glance

| Verb | Input | Effect on the map | User round-trip |
|---|---|---|---|
| `ensure` | a frontend codebase | the map exists and conforms to the `interaction-intuition` schema | bulk-verify, when `low`/`unknown` items surface |
| `grow` | a user-specified flow (`.spec.ts` or prose steps) | the exercised elements land as confirmed entries | none, except on contradiction |
| `bug-path-upsert` | a bug artifact (repro spec + diagnosis reference) | the bug path's elements gain provenance + a regression pointer | none |

## Verb — `ensure`

**Contract.** Given a frontend codebase, guarantee that
`<codebase>/docs/INTERACTION_INTUITION_MAP.md` exists and conforms to the
`interaction-intuition` artifact schema BEFORE any test is authored against that
codebase. The verb NEVER treats authoring as map-consulted while the map is
missing — a missing map is a blocking precondition, not a warning.

**Map already present, with elements.** `ensure` is a cheap no-op. It does NOT
re-derive, and it does NOT judge freshness — staleness is the suite-builder's P2
concern, and paying for a re-intuit on every authoring call would make the cheap
verb expensive enough that lanes would skip it.

**A scaffolded map with zero elements does not satisfy the precondition, and the
engine says so.** The `scaffold` operation writes a conforming but EMPTY map —
a supporting operation under `ensure`, not a fourth verb, and not a way to clear
the precondition. `ensure` reports one of four values in `action_required`:

| `action_required` | What the map is | What you do |
|---|---|---|
| `produce-map` | none exists | derive it (dispatch or inline) |
| `repair-map` | exists but does not parse, or carries blocking schema findings | fix the artifact |
| `populate` | exists and is schema-valid but carries ZERO elements | derive the elements |
| `none` | exists, validates, and describes at least one element | proceed |

`populate` sits between `repair-map` and `none` on purpose: the artifact is fine,
the content is absent. A freshly scaffolded map returns `populate`, never `none`.

Treating a zero-element stub as satisfied would meet the letter of R1 while
leaving every control unintuited, which is the failure this verb exists to
prevent — so `ensure` is not complete until `action_required` is `none`.

**The exit code agrees with the field.** The CLI exits `0` only when
`action_required` is `none`, and non-zero for all three of `produce-map`,
`repair-map` and `populate` — so a clean exit IS a satisfied precondition and you
can gate on it. Read `action_required` when you need to know WHICH work remains;
`covers_elements` in the same report tells you how many elements the map
describes.

**Map absent — pipeline context** (a run is active and agent dispatch is
available): dispatch the `interaction-intuiter` agent exactly as
`intake-and-mapping` does in its per-frontend-codebase intuiter-dispatch step
(filed there under `## Phase −1D — Interaction intuition`), with the same inputs
(`ROUTE_MAP.md`, `DESIGN_MAP.md` when present, `docs/INTEGRATION_MAP.md`, the
source description). Nothing about that path changes; `ensure` is the caller, not
a second implementation of it.

**Map absent — ad-hoc context** (no run, no dispatch — a user asked for a test in
a bare session): run the SAME rubric and the SAME schema inline. Walk the route
map's screens, enumerate the interactive elements, intuit each action, match
candidate endpoints, assign `high` / `medium` / `low` / `unknown` per the
`interaction-intuition` confidence rubric, and author an `ambiguity_question` for
every item below `high`. Then execute the Phase −1D gate logic inline: present
every `low` and `unknown` item (plus any `medium` item carrying a non-null
`ambiguity_question`) to the user as ONE single numbered list with the same
three replies the gate accepts — `all correct`, a list of incorrect indices, or
`all incorrect` — and drill down only on the flagged items. Same gate, same
presentation, executed by the caller instead of the orchestrator.

**How the artifact gets written on the ad-hoc path — scaffold, then populate.**
Do not hand-write the map file; the hard rule below says the verbs are the only
non-intuiter writers, and hand-editing would break it. Call the engine's
`scaffold` operation to write the conforming empty artifact, then populate it
with the entries the inline rubric derived. Scaffold-then-populate is the flow;
**scaffold alone is not a completed `ensure`**, because the empty map it writes
carries zero elements.

The inline path is not a reduced form. An inline map that skips the bulk-verify
is a map full of unconfirmed guesses, and tests authored against it inherit
every one of them.

**Domain gate.** The inline bulk-verify is a domain gate exactly as the −1D gate
is — the user-confirmation step IS the deliverable — so it fires regardless of
`--proposal-first` and regardless of the gates-are-opt-in default. Per
`skills/interaction-intuition` `## Domain-gate carve-out`.

## Verb — `grow`

**Contract.** Given a user-specified flow — a `.spec.ts` file, a handed-over
spec, or prose steps — extract the elements and routes the flow exercises and
upsert them into the map as CONFIRMED entries.

**The upserted entry shape.** Each element the flow exercises lands with
`user_verdict` set to `confirmed`, `source` set to `user-flow`, `confidence` set
to `high`, `confirmed_action` written from what the flow actually does, and
`confirmed_endpoint` populated when the flow's network expectations name one.
`evidence[]` cites the flow file (or the prose) and the step within it.

**No bulk-verify round-trip, and the asymmetry is deliberate.** The Phase −1D
gate exists to resolve the INTUITER's uncertainty — it asks the user to
adjudicate a guess. A user-specified flow carries no guess to adjudicate; the
user specifying the flow IS the confirmation, and asking them to re-confirm what
they just told us is the permission-seeking anti-pattern with extra steps. So
`grow` bypasses the gate by design. This asymmetry with the −1D rule is
intentional, and both this skill and `skills/interaction-intuition` say so
explicitly, so a future reader does not "fix" the inconsistency by routing
`grow` back through a gate it was deliberately kept out of.

**Extraction is heuristic, and the CALLER marks the uncertainty.** Turning a
selector into an `element_id` is inference, and the engine cannot judge how
confident that inference was — it never saw the flow. So the division of labour
is explicit: **the authoring agent marks an extraction ambiguous**, and the
engine enforces what happens next. An element the caller marks ambiguous is
**never upserted**; no entry is written for it at all, and a targeted question
naming the selector and the candidate entries is produced instead.

**The mark is a key on the flow element, and here it is.** Set
**`ambiguous: true`** on the element in the payload you hand `grow`. The engine
also accepts **`extraction_confidence`** of `low` or `unknown` as an equivalent
mark, so a pipeline that already carries a confidence reading does not need a
second field. Either spelling routes the element to an `ambiguous-extraction`
question; you may add `ambiguity_note` to say what was unclear.

**Absence is a silent default, and that is by design.** The engine reads the key
as falsy when it is missing, so an element with no marker — the common case — is
taken as certain and upserted normally. That direction is deliberate and
engine-pinned: the normal path must not require ceremony. The cost is that
forgetting to mark a shaky extraction is indistinguishable from asserting it is
sound, and nothing downstream will tell you. Mark on the way in.

Do not read this as the engine scoring confidence on its own. It does not. An
unmarked extraction is taken as certain, which means failing to mark a shaky one
is how a wrong `confirmed` entry gets written — and a wrong upsert is worse than
an absent one precisely because it lands marked `confirmed`.

**Contradiction never silently overwrites.** When a grown entry would contradict
an existing CONFIRMED entry — a different action, or a different endpoint, for
the same `element_id` — the existing entry is left byte-unmodified and the verb
surfaces exactly ONE targeted question naming BOTH readings and the user-visible
difference between them:

> *"The map records `dashboard__row-actions__archive__1` as archiving the row
> (`POST /api/items/{id}/archive`, the row stays queryable), confirmed on
> 2026-08-02. The flow you handed over clicks that control and expects the row to
> disappear entirely (`DELETE /api/items/{id}`). Which is the intended behaviour
> — has the control changed, or is the flow exercising a different control?"*

Never a silent overwrite, never a merge of the two readings, never a
last-write-wins. This one question is the domain gate on the `grow` path, and it
is the ONLY case where `grow` involves the user at all.

## Verb — `bug-path-upsert`

**Contract.** Given a bug artifact — a reproduction spec plus a diagnosis
reference — upsert the elements along the bug's path with `source` set to
`bug-path` and a `regression_refs[]` entry that points at BOTH the covering
debug-flow test and the originating SR path or bug slug.

**Why both refs.** A map entry that says "this path had a bug" is trivia. An
entry that names the `debug-flow` test now covering it, and the SR it came from,
is the thing a future run needs — it answers *"is this path protected, and by
what?"* without reading the run history. When the suite-builder's P6 registers
the repro as a `kind: debug-flow` manifest entry, the manifest's `origin_ref` and
the map's `regression_refs[]` point at each other; `verify-suite-manifest` checks
the manifest side, and a `regression_refs[]` entry naming a test that no longer
exists is a finding the next `bug-path-upsert` reports rather than silently
carries.

**Confirmation status.** A bug path is observed behaviour, not an intuition — the
path was walked and the failure reproduced. Elements the repro demonstrably
exercises land `confirmed` with `confidence` `high`. Elements the diagnosis only
implicates land at their existing confidence with the provenance recorded; the
verb does not promote an inference to a confirmation because it appeared in a
bug report.

**Existing entries.** `bug-path-upsert` appends to `regression_refs[]` — it does
not replace an entry's confirmed action or endpoint.

**Contradiction carries the same guard as `grow`, stated here rather than
delegated.** When a bug path's action or endpoint contradicts an existing
confirmed entry, the existing entry is left unmodified, the verb **never
silently overwrites** it, and exactly one targeted question naming both readings
goes to the user. There is no last-write-wins here either. A bug fix that
genuinely CHANGED the behaviour is a legitimate correction — and the user is the
one who says so, which is what the question is for.

(The earlier wording pointed at `grow` and called the paths "the same". Pointing
at another section is not a guarantee that the guard exists; it is now written
out, and the engine enforces it on this path too.)

## The additive schema

Two per-element fields join the `interaction-intuition` artifact schema:

- **`source`** — one of `intuiter`, `user-flow`, `bug-path`. Where this entry
  came from.
- **`regression_refs[]`** — list of `{test, ref}` objects, where `test` names the
  covering test and `ref` names the SR path or bug slug that produced it (an
  optional `note` carries one line of context). Empty for entries no regression
  covers. These are the key names the engine validates; any other spelling is
  rejected as `malformed-regression-ref`. Note the suite manifest's own
  `origin_ref` field is a DIFFERENT thing — the two point at each other, they do
  not share a spelling.

**Both are additive, and there is no migration.** An entry that carries neither
field is read as `source` `intuiter` with empty `regression_refs` — the value a
pre-existing map has always implied. Old maps parse unchanged, the engine treats
absence as the default rather than rewriting entries it was not asked to touch,
and no map anywhere needs a migration pass. Absence is a meaningful, permanent,
supported state, not a transitional one.

The canonical field documentation lives in `skills/interaction-intuition`
`## Provenance fields (additive)`. This skill is the sole writer of any entry
whose `source` is not `intuiter`.

## The engine (the deterministic mechanism)

Every verb's behaviour is implemented by a stdlib-only engine package under
`scripts/intuition_lifecycle/` — map parse (the YAML-blocks-in-markdown body),
upsert, validate, and a CLI. The CLI additionally exposes `scaffold` (writes a
conforming empty map) and `validate` — these are **supporting operations**, not
a fourth and fifth verb: `scaffold` is how `ensure` writes the artifact on the
ad-hoc path, and `validate` is the gate every verb runs before writing.

**The skill is the contract; the engine is the mechanism.** The three verbs above
are the contract's surface; `scaffold` and `validate` sit underneath it as
mechanism, which is why they are documented here rather than promoted into the
verb list. The split is what makes each verb red-first testable: parse
round-trip, upsert-preserves-untouched-entries, the confirmed-entry shape, the
contradiction-produces-a-question-not-an-overwrite behaviour in both directions,
and schema validation are engine tests, not prose promises.

Invoke it via the polyglot Python form per `common-pipeline-conventions`
`## Cross-platform Python invocation`. When the engine reports a validation
error, the verb does NOT write the map — a half-written map is worse than an
unchanged one, and the engine's round-trip guarantee is what lets a caller
upsert one entry without risking the other four hundred.

## Hard rules (non-negotiable)

- **Never author tests against a missing map.** `ensure` runs first, in every
  lane, in both contexts. "The map probably isn't needed for this one test" is
  the rationalization that produced the R1 gap.
- **`ensure` does not re-derive an existing map.** Freshness belongs to the
  suite-builder's P2. A cheap verb that quietly costs a full re-intuit is a verb
  callers learn to avoid.
- **`grow` never silently overwrites a confirmed entry.** Contradiction surfaces
  ONE question naming both readings.
- **`grow` derives an `element_id` only for an extraction the caller did NOT mark
  ambiguous.** A marked extraction becomes a question, not an entry. The caller
  supplies the mark; the engine enforces the routing. The engine does not score
  confidence on its own — it never saw the flow — so an unmarked extraction is
  derived and written as `confirmed`, which is why marking is the caller's
  obligation and not a formality.
- **Provenance is written, never inferred after the fact.** An entry this skill
  writes carries its `source` at write time. Backfilling provenance by guessing
  which entries "look like" bug paths is forbidden.
- **The verbs are the only non-intuiter writers.** No lane hand-edits the map's
  entries; a lane that needs something the three verbs do not do raises it rather
  than writing the file directly.
- **One map per frontend codebase**, per `skills/interaction-intuition`
  `## Hard rules (non-negotiable)`. The verbs never merge codebases' maps.

## Relationship to other skills

- `skills/interaction-intuition` — owns the rubric, the confidence labels, the
  artifact schema, and the Phase −1D gate. This skill calls that rubric; it never
  redefines it. The provenance fields are documented there.
- `skills/intake-and-mapping` — the Phase −1D intuiter dispatch `ensure` reuses verbatim
  in pipeline context, and the freshness discipline P2 builds on.
- `skills/playwright-user-flows` — Step 1 calls `ensure` and consults the map
  alongside `ROUTE_MAP.md` before authoring.
- `skills/playwright-suite-builder` — calls `ensure` at P2 (with freshness) and
  `bug-path-upsert` at P6; the manifest's `origin_ref` and this map's
  `regression_refs[]` are the two ends of one pointer.
- `skills/ux-test-builder` — calls `grow` for the U2 literal flow and the U5
  distilled flows.
- `skills/bug-fix-pipeline` — calls `bug-path-upsert` at B2, once the
  reproduction artifact exists and the path is known.
- `skills/mempalace-integration` — the map is mined after a verb writes it, the
  same way the intuiter's output is mined, so a future run recalls the confirmed
  entries.
