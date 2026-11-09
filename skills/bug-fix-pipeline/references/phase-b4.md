# Phase B4 — Bug-Fix Generalization Audit

The Lead creates a `system-architect` task in **Bug-Fix Generalization Audit** mode (teams mode) OR dispatches the `system-architect` subagent in that mode (subagents mode). Inputs:

- The source description (the bug report).
- The replication evidence (the artifact paths + their failing output).
- The proposal + `design.md` + the diff of the proposed fix (when the fix is implementation-ready) OR the spec'd approach (when the fix isn't yet implemented).
- The relevant CODEBASE_MAP + INTEGRATION_MAP.

The audit's verdict is one of:

- **`pass`** — the fix addresses the *class* of bug and is correctly scoped. No special-casing of the failing input. The architect cites the class explicitly: *"This fix addresses the class of bugs where a soft-delete is treated as a hard-delete by the row-action handler; the change to the handler correctly affects every row, not just the one the user reported."*
- **`needs-generalization`** — the proposal special-cases the failing input. The architect cites the offending pattern (the literal user-id, the hard-coded category, the targeted conditional) and describes the underlying class of bug. The proposal returns to authoring (back to Phase B3) for revision.
- **`needs-replacement`** — the proposed approach is wrong (treats a symptom while leaving the root cause; uses the wrong layer; introduces a worse defect). The architect cites a better alternative; back to B3.

**The user-authorized override.** If the source description explicitly authorized a targeted fix — phrasings like *"hard-code it for now"*, *"just for this one user"*, *"hotfix before the demo"*, *"patch it just temporarily"* — the architect records the authorization verbatim in the verdict and lets a targeted fix proceed. The architect does NOT extrapolate authorization from silence; a description that doesn't address generalization is NOT authorization. The audit verdict's reasoning field carries the authorization quote.

**Genuinely-narrow classes are NOT generalization gaps.** A bug whose class is exactly one input (a singleton config issue, an enum value that doesn't exist anywhere else, a one-time data fix) is general for its class. The audit's reasoning field cites the class size when relevant.

The audit verdict gates Phase B5: the implementing team does NOT touch code until the verdict is `pass`.
