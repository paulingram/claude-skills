# Scope-fidelity discipline family (v3.10.0)

Five disciplines enforce ONE root principle — **the agent does the mandated work; it never unilaterally narrows the scope or defers the work, and never frames the narrowing/deferral as acceptable** — at five distinct moments in a run's timeline. They share marker lists, severities, the Layer 3 verification surface, and (above all) the **3-disposition model**. This section is the canonical family home; the five member sections below carry each discipline's RULE (markers, severities, paths) and reference this table for the firing-moment distinctions and the disposition model.

### The 3-disposition model (shared by all five)

Every in-scope item the run surfaces — a bug found mid-implementation, a gap a reviewer flagged, a milestone of a full-build mandate, a cross-layer defect — MUST reach exactly ONE of these dispositions before the run is "done". Anything else is a discipline failure on whichever member's axis the defect fires.

1. **Fixed in this change** — the run's commit(s) fix the item; the test that covers it goes green. The report cites the commit-SHA range or the test name.
2. **SR routed** — a solution requirement at `<workspace>/.architect-team/solution-requirements/<sr-id>.json` carries the item with an `origin.kind` from the canonical catalog (`missing-api-for-frontend-element`, `cross-layer-backend-required`, `cross-layer-frontend-required`, `interaction-gap`, `live-data-wiring-gap`, `incomplete-implementation-scope-required`, `security-finding`, `a11y-gap`, …). The report cites the SR ID.
3. **Confirmed-stub** — a `coverage-map.json` `confirmed_stubs[]` entry with a `user_confirmed_at` ISO timestamp + the user's verbatim citation records that the item is intentionally out of scope. The report cites the entry.

### When each member fires

| Discipline | Version | Firing moment | Surface form the member catches |
|---|---|---|---|
| **anti-deferral** | v0.9.36 | DURING execution, between phases | Agent finds a bug mid-run → silently defers to "next run" without authorization |
| **scope discipline** | v1.4.0 | AT intake, before Phase 0 | Agent narrows the user's prompt before any work starts (e.g. a parity-implying verb read as data-only) |
| **no standing-red** | v2.8.0 | At commit time, as a code artifact | Agent commits a failing regression test as documentation of a known (often cross-layer) bug |
| **no end-of-run deferral** | v2.10.0 | At end-of-run, as the final-report shape | Agent ends with "⏳ Deferred" + a "Want me to continue?" follow-up offer, bouncing the decision back |
| **no implementation-time scope cut** | v2.14.0 | At implementation completion, as a VIRTUE statement | Agent (under a full-build mandate) cuts to a foundation subset and PROUDLY ANNOUNCES it ("Honest scope statement" / "I stopped at the boundary deliberately") |

The firing-moment distinctions are load-bearing: v2.10.0 (bounce-the-decision-back) and v2.14.0 (proudly-announce-the-cut) are different surface forms of the same root failure, and v2.14.0 additionally requires a `full_build_required` mandate from the user prompt where v2.10.0 fires on any run. The v3.0.0 unilateral-override discipline is the META layer over this family — it catches the agent OVERRIDING any of these five when the user has not authorized the override (see the Unilateral-override discipline section, v3.0.0).

### Cross-references

- The five member sections (each carries its own RULE + markers): the Scope discipline section (v1.4.0), the No standing-red discipline section (v2.8.0), the No end-of-run deferral discipline section (v2.10.0), the No implementation-time scope cut discipline section (v2.14.0), and the mid-run anti-deferral rule carried in each pipeline body's Default mode of operation (v0.9.36).
- The five Layer 3 tools (code contracts UNCHANGED): `verify_no_standing_red`, `verify_no_end_of_run_deferral`, `verify_no_implementation_scope_cut`, plus the scope/override tools `verify_no_unilateral_override`; each keeps its CLI subcommand, severities, and verdict shape.
- The Unilateral-override discipline section (v3.0.0, META) — the override layer over this family.
