# Appearance-change policy discipline (v3.14.0)

Agents MUST NOT make unsolicited changes to frontend APPEARANCE. When the user asks for an update, an improvement, or a fix, the mandate covers the named work — it does not authorize restyling, layout tweaks, new visible elements, or "polish" the user never asked for. Backend changes needed to deliver the mandate are unrestricted by this policy ("do what you need to on the backend"); what a user SEES changes only when the user asked for it, approved it, or explicitly granted free rein.

**Failure shape** (verbatim user prose driving the rule): *"sometimes when asking for updates, the agent will arbitrarily change our front end, adding things we didnt explicitly ask for as part of an ask to improve."* The standing default, also verbatim: *"by default we are strict on appearance changes with a no unless explicity asked or given direction to do so."* This is the inverse axis of the scope-fidelity family (`## Scope-fidelity discipline family (v3.10.0)`): the family catches the agent doing LESS than asked (narrowing / deferring); this policy catches visual over-delivery — doing MORE than asked on the visual surface. Same root principle: the user's prose is the contract, in both directions.

### The three modes

| Mode | Meaning |
|---|---|
| **`strict`** | NO appearance-affecting change beyond the explicit mandate (the three sanctioned mandate sources below). Improvement ideas are RECORDED as proposals — never implemented. `strict` is the DEFAULT. |
| **`propose`** | Same boundary as `strict`, but captured proposals are surfaced to the user at a batch approval gate (ONE `AskUserQuestion`, multi-select — a DOMAIN gate per the v0.9.21 carve-out: the user chose this mode, so the approval step IS the deliverable). ONLY user-approved proposals are implemented; approval converts the proposal into an explicit mandate, recorded with the user's verbatim citation. |
| **`innovate`** | The agent is authorized to make the appearance improvements it judges better. Every delta is still LOGGED to the proposals artifact with status `implemented-innovate`, the final report enumerates every visual delta, and `DESIGN_MAP.md` / the documentation-currency inventory are reconciled in the same change so the maps stay truthful. Freedom is granted; silence is not. |

The mode is bound ONCE at pipeline entry (alongside the dispatch-mode selection), persisted as `appearance_mode` in `<workspace>/.architect-team/intake-state.json`, and carried in every teammate's spawn brief (extending the v0.9.13 manifest schema the same way `deploy_mandate` and `baseline_sha` already are).

### What counts as appearance-affecting

Any diff hunk that changes what a user SEES: visual styling (color, typography, spacing, sizing, borders, shadows, animation, theming), UI-surface deltas (adding / removing / relocating visible elements — buttons, panels, banners, nav entries, pages, icons), displayed copy the requirement does not name, and asset swaps (logos, imagery, fonts). NOT appearance-affecting: behavior/data wiring with no visible rendering delta (binding an existing control to a live endpoint), backend-only changes, pure accessibility attributes (`aria-*`, `alt`) that do not alter rendering, and test files.

### The three sanctioned mandate sources (what "explicitly asked or given direction" means under `strict`)

1. **Requirement text.** The prompt / requirements folder names the visual change (*"add an export button"*, *"make the header sticky"*, *"restyle the cards"*). The NAMED surfaces are in scope — and only those.
2. **Spec restoration.** The change restores the documented design source — `DESIGN_MAP.md`, design mockups, brand docs, or the intended rendering a bug broke. `visual-fidelity-reconciliation` / `visual-qa` drift-to-spec fixes and bug fixes that restore intended appearance are ALWAYS in scope, in every mode: restoring documented appearance is not an appearance change in this policy's sense.
3. **Mandated-capability minimum.** An explicitly-required capability with no existing UI entry point may add the MINIMAL surface required to expose it (you cannot ship "export to CSV" without an Export control): match the codebase's existing design system and component patterns, smallest footprint, zero decorative extras. The carve-out covers necessity, never improvement.

Everything else is out of mandate. The agent's confidence that a change "makes it better" is exactly the failure mode this policy closes — better is the user's call.

### Mode selection

- **Flag.** `--appearance <strict|propose|innovate>` on `/architect-team`, `/architect-team:bug-fix`, and `/architect-team:mini` → `APPEARANCE_MODE`. Default `strict`. Natural-language equivalents recognized at parse time — propose: *"propose appearance changes"* / *"suggest UI improvements first"* / *"ask before changing the look"*; innovate: *"innovate on the UI"* / *"free rein on the design"* / *"do whatever you want with the front end"* / *"make it look better however you want"*.
- **Requirement prose.** An explicit visual ask puts the NAMED surfaces in scope under `strict` — no mode change needed. Broad free-rein prose scoped to a surface (*"redesign the dashboard however you think best"*) is `innovate` for that named surface only. When the prompt asks to "improve" / "update" / "upgrade" a UI surface and it is genuinely ambiguous whether the LOOK may change, surface ONE `AskUserQuestion` at intake (the same domain-gate shape as the Scope discipline section's surfacing pattern, v1.4.0) — or let the upstream `proposal-refiner` conversation settle it — and record the answer.
- **Bug fixes.** The bug-fix pipeline is `strict` by nature: the mandate is the named symptom; restoring intended behavior/appearance (mandate source 2) is in scope; restyling beyond it is not. The flag can still widen a bug-fix run explicitly.

### The proposals artifact

Path: `<workspace>/.architect-team/appearance-proposals/<run-id>.json` (gitignored — runtime state). Every appearance-improvement idea any agent surfaces during the run is appended here REGARDLESS of mode:

```json
{
  "run_id": "...",
  "appearance_mode": "strict",
  "proposals": [
    {
      "proposal_id": "AP-1",
      "surface": "dashboard header",
      "current": "static header",
      "proposed": "sticky header, condensed on scroll",
      "rationale": "keeps nav reachable on long pages",
      "originating_agent": "frontend-dashboard",
      "phase": "Phase 2",
      "status": "recorded",
      "decided_at": null,
      "user_citation": null
    }
  ]
}
```

`status` is one of `recorded` (captured, not acted on — the terminal state under `strict`) / `approved` / `rejected` (the user's gate decision under `propose`, with `decided_at` + `user_citation`) / `implemented-approved` (an approved proposal whose implementation landed) / `implemented-innovate` (the innovate-mode log entry).

Per-mode handling:

- **`strict`** — proposals stay `recorded`. The final report lists them READ-ONLY under an "Appearance proposals (not implemented — strict mode)" heading, citing the artifact path and stating how to act on them in a future invocation (re-run with `--appearance propose` / `--appearance innovate`, or name the change explicitly). The statement is imperative, never interrogative — phrasings like *"Want me to apply them?"* trip the v2.10.0 `_FOLLOWUP_QUESTION_MARKERS` and are forbidden.
- **`propose`** — the orchestrator batches `recorded` proposals at the END of Phase 1 (plan-time ideas) and again at the Phase 5 → 7 boundary (emergent ones) into ONE `AskUserQuestion` per batch (multi-select). Approved → folded into the coverage map as explicit mandates and implemented (`implemented-approved` once landed); declined → `rejected` with the citation.
- **`innovate`** — implement freely; EVERY appearance delta gets a proposals entry with `status: "implemented-innovate"`; `DESIGN_MAP.md` is reconciled in the same change; the final report enumerates the deltas.

### Interplay with the 3-disposition model (v2.10.0)

Unimplemented appearance proposals under `strict` / `propose` are NOT in-scope items in the v2.10.0 sense — they are out-of-mandate improvement IDEAS, and `recorded` / `rejected` is their sanctioned terminal disposition. The v2.10.0 / v2.14.0 deferral disciplines govern MANDATED work; this policy governs UNREQUESTED work. The two never conflict: mandated work is never routed to the proposals artifact, and proposal ideas are never counted as deferred in-scope items.

### Interplay with completeness-discipline SRs

Completeness audits (`interaction-completeness`, `editability-completeness`, affordance coverage) keep DETECTING gaps in every mode — detection is unchanged. Routing honors the mode: an SR whose remediation requires NEW visible UI surface (a control / panel / page that does not exist today) is marked `appearance_gated: true`; under `strict` / `propose` the orchestrator does NOT auto-dispatch implementation for it — it surfaces the SR at the propose-style gate (or read-only in the final report under `strict`) with a matching proposals entry, and the user decides. Under `innovate` it auto-dispatches as before. Pure-wiring SRs (an EXISTING element that is dead / mock-backed / unbound — `unwired-control`, `live-data-wiring-gap`, `missing-api-for-frontend-element` for an element the design already shows) are NOT appearance-affecting and route unchanged in every mode. This generalizes the v2.18.0 catalog's existing "SR-route-only — UX decision, not mechanical" rule.

### Forbidden anti-patterns (`strict` / `propose`)

- **While-I'm-here restyling.** Tightening spacing, swapping colors, "modernizing" a component as part of an unrelated diff. Canonical reviewer markers: *"while I was at it"*, *"also improved the"*, *"took the liberty"*, *"modernized the look"*, *"polished the"*, *"cleaned up the styling"*, *"refreshed the design"*, *"made it look better"*.
- **Unsolicited UI surface.** New buttons / panels / pages / nav items / banners nobody asked for — including "helpful" additions bundled into an ask to improve something else. This is the verbatim failure shape.
- **Redesign-while-wiring.** Rebuilding a component's look as a side effect of binding it to live data. Wire the existing rendering; propose the redesign.
- **Implement-then-confess.** Shipping an unsolicited visual change and announcing it as a favor (*"I also tidied the header — revert if you don't like it"*). Post-hoc disclosure is not authorization — the same rule as `## Unilateral-override discipline (v3.0.0) — META`; the change should have been a proposal.
- **Improvement framing as cover.** Describing an unsolicited appearance change as an "improvement" / "enhancement" in the report. The framing IS the surface symptom — out-of-mandate is out-of-mandate regardless of merit.

### Review-gate enforcement — the `appearance_scope_review` evidence field

Schema v7 gains a THIRD OPTIONAL field, `appearance_scope_review` (joining `interactions_honored_review` / `live_verification_review` in `OPTIONAL_VAO_FIELDS` — same string-or-dict contract, same backwards-compat guarantee: older evidence files that lack the field remain valid). Required whenever the slice's diff touches frontend presentation surface (styling files, components, templates, routes, assets); `n/a` (with a non-empty `appearance_scope_review_note`) otherwise. `VALID_APPEARANCE_SCOPE_VALUES = {"pass", "n/a", "fail"}`.

- The TEAMMATE sets it in its self-review: `pass` = every appearance-affecting delta in the diff traces to one of the three mandate sources, an `approved` proposal, or (innovate mode) a logged `implemented-innovate` entry; `fail` = any delta lacks a trace. The hook BLOCKS `fail`.
- The independent `task-reviewer` verifies the trace per delta as part of its diff review (`agents/task-reviewer.md` `## Appearance-change policy discipline (v3.14.0)`) — an untraceable delta is a `spec_review` gap AND flips `appearance_scope_review` to `fail`.
- The `system-architect` Master Review Audit (Phase 7) walks the RUN-level diff the same way and checks the proposals artifact's integrity (no `approved` without `user_citation`; no `implemented-innovate` entries outside innovate mode).

### What v3.14.0 does NOT ship

NO new Layer 3 tool — enforcement is the schema v7 optional field (hook-blocked on `fail`), the task-reviewer per-delta trace, and the system-architect master-review walk (the same not-runtime-enforcement shape as `## Phenotype convergence rules (v3.5.0)`). A deterministic `verify-no-unsolicited-appearance-change` tool (pure-style-file diff scan + declared-delta / mandate-ref cross-check against the proposals artifact) is the natural v3.14.x follow-up once the declaration artifact beds in.

### Cross-references

- `commands/architect-team.md` / `commands/bug-fix.md` / `commands/mini.md` — the `--appearance` flag + parse-time natural-language equivalents.
- `skills/architect-team-pipeline/references/phase--2.md` `### Phase −2 appearance-mode binding (v3.14.0)` — orchestrator-side binding; Phase 8 carries the final-report proposals rule.
- `skills/bug-fix-pipeline/SKILL.md` + `skills/mini-architect-team-pipeline/SKILL.md` `## Appearance-change policy (v3.14.0)` — per-pipeline statements.
- `agents/frontend.md` + `agents/task-reviewer.md` + `agents/system-architect.md` `## Appearance-change policy discipline (v3.14.0)` — implementer / reviewer / auditor statements.
- `hooks/review_evidence_schema.py` — `appearance_scope_review` in `OPTIONAL_VAO_FIELDS`; `VALID_APPEARANCE_SCOPE_VALUES`.
- `skills/team-spawning-and-review-gates/SKILL.md` — the evidence-file contract documents the third optional field.
- `tests/test_appearance_change_policy.py` — structural tests for this section + the schema field + the cross-wiring.
- Companions: the scope-fidelity family (catches under-delivery; this catches visual over-delivery) and v3.0.0 unilateral-override (implement-then-confess is its appearance-surface form).
