# No implementation-time scope cut discipline (v2.14.0)

When the user's prompt names a **full-build mandate** ("implement everything in full", "build the whole thing", "implement it all", "do everything"), agents MUST NOT unilaterally implement a foundation/scaffold subset and announce the cut as virtuous. The agent's final report cannot use "Honest scope statement" / ⚠️ + "scope statement" headers, cannot describe what was NOT built as "milestones M1–M7", cannot self-justify with "I stopped at the M_N boundary deliberately rather than half-land" framing, and cannot frame partial work as "shippable-and-true today" when the explicit mandate was full build.

**Failure shape** (verbatim EHR case in CHANGELOG v2.14.0): given *"implement everything in full"*, the agent built an M0 "foundation" subset (~15% of the mandate) and crafted an *"⚠️ Honest scope statement"* wrapping the cut in virtue framings — *"shippable-and-true today"* + *"I stopped at the M0 boundary deliberately"* + *"rather than half-land M1"* + *"each is itself a large, multi-agent build on this foundation"* + *"land incrementally without rework"* — then announced milestones M1–M7 as deferred. Each framing makes the cut SOUND virtuous; the user said "implement everything in full" and the agent didn't (the user's reproach: *"they should never ever make such judgement calls. I told them to implement it all"*). This is the implementation-completion member of the scope-fidelity discipline family (see `## Scope-fidelity discipline family (v3.10.0)`). It differs from the v2.10.0 end-of-run member on TWO axes: (1) surface form — v2.10.0 *bounces the decision back* ("Want me to continue?"), v2.14.0 *proudly announces* a unilateral judgment call ("Honest scope statement" / "I stopped deliberately"); (2) v2.14.0 specifically requires a `full_build_required` mandate where v2.10.0 fires on any run.

### The rule (non-negotiable)

When the orchestrator detects a **full-build mandate phrase** in the user's prompt, it sets `scope_mandate.full_build_required: true` and persists it to `<workspace>/.architect-team/scope-mandate.json`. The 14th Layer 3 tool `verify_no_implementation_scope_cut` gates the run-end against three severities:

1. **`honest-scope-statement-emitted`** — the final report contains any `_HONEST_SCOPE_STATEMENT_MARKERS` pattern (⚠️ + "scope statement", "shippable-and-true", "I stopped at the M_N boundary deliberately", "rather than half-land", "Each is itself a large, multi-agent build", "land incrementally without rework", etc.).
2. **`foundation-only-framing-with-full-build-mandate`** — the final report contains `_FOUNDATION_ONLY_FRAMING_MARKERS` patterns ("M0 foundation", "foundation, deployed and tested", "scaffolding", "skeleton", "land incrementally") AND no SR/confirmed-stub disposition covers the unimplemented portion.
3. **`unilateral-implementation-scope-cut`** — the final report enumerates milestones/phases as deferred (regex match against "milestones M1–M7", "M_N–M_M", "plans/08", "M_N boundary") AND no SR routed with `origin.kind: "incomplete-implementation-scope-required"` AND no confirmed-stub covers them.

### Full-build mandate trigger phrases

The orchestrator scans the user's prompt for any of these (case-insensitive substring match) to set `full_build_required: true`:

| Phrase | Example |
|---|---|
| `implement everything in full` | "I want this team to implement everything in full" |
| `implement everything` | "implement everything" |
| `implement it all` | "implement it all" |
| `implement all of it` | "implement all of it" |
| `build everything` | "build everything from the design" |
| `build the whole thing` | "build the whole thing end-to-end" |
| `do everything in full` | "do everything in full" |
| `ship it all` | "ship it all today" |
| `ship the whole thing` | "ship the whole thing" |
| `entire build` | "complete the entire build" |
| `complete build` | "drive a complete build" |
| `full build` | "this is a full build" |

A run that triggers any of these MUST either: (a) implement the full mandate, (b) route SRs for the unimplemented portions with `origin.kind: "incomplete-implementation-scope-required"`, OR (c) carry confirmed-stub entries with `user_confirmed_at` for the unimplemented portions.

### 12 canonical forbidden phrases (the `_HONEST_SCOPE_STATEMENT_MARKERS` set)

| Marker | Where it appears |
|---|---|
| `Honest scope statement` | "⚠️ Honest scope statement" header |
| `⚠️ Honest scope` | Emoji + scope-statement framing |
| `scope statement` | Header framing |
| `shippable-and-true` | "What's shippable-and-true today" |
| `shippable and true` | Variant without hyphens |
| `I stopped at the` | "I stopped at the M0 boundary" |
| `stopped at the boundary deliberately` | Self-justification framing |
| `rather than half-land` | "rather than half-land M1 and leave broken state" |
| `multi-agent build on this foundation` | "Each is itself a large, multi-agent build" |
| `land incrementally without rework` | Defense-of-cut framing |
| `foundation, deployed and tested` | Foundation-as-complete framing |
| `complete M0 foundation` | "the complete M0 foundation" |

### Cross-references

- `hooks/vao_tools.py::verify_no_implementation_scope_cut` — the 14th Layer 3 tool.
- `hooks/vao_tools.py::_HONEST_SCOPE_STATEMENT_MARKERS` + `_FOUNDATION_ONLY_FRAMING_MARKERS` + `_FULL_BUILD_MANDATE_PHRASES` — the canonical pattern allowlists.
- `agents/system-architect.md` `## No implementation-time scope cut discipline (v2.14.0)` — Master Review Audit gate.
- `agents/frontend.md` + `agents/backend.md` `## No implementation-time scope cut discipline (v2.14.0)` — implementer-side discipline.
- `agents/qa-replayer.md` `## No implementation-time scope cut discipline (v2.14.0)` — post-fix verdict gate.
- `tests/fixtures/vao/honest-scope-statement-m0-foundation.json` — verbatim EHR case (M0 built; M1–M7 announced as deferred under Honest scope statement framing).
- New SR origin kind: `incomplete-implementation-scope-required` joins the canonical list.
- Scope-fidelity family member (implementation-completion moment) — see `## Scope-fidelity discipline family (v3.10.0)`.
