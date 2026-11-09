# Declared-gates discipline (v3.47.0)

**A gate you name is a gate you record.** The moment the orchestrator states a condition that gates ship, deploy, merge, or completion — in a plan, in a phase decision, in a progress report, in user-facing prose ("we don't ship until the full Playwright suite passes against the live URL", "this merges after the type-check is clean") — it has made a promise the user is now relying on. An unrecorded gate is a claim, and an unverified claim about a gate is exactly what the rest of this stack forbids. Recording it costs one JSON append; forgetting it is how a run ships past its own stated bar and reports success.

**The registry.** `<workspace>/.architect-team/declared-gates.json` — a JSON array, appended (never rewritten) as gates are declared:

```json
[
  {
    "gate_id": "full-playwright-live-url",
    "declaration_text": "The release gates on the full Playwright suite passing against the live dev URL.",
    "check_command_or_artifact": "npx playwright test --reporter=line  (or the verdict artifact path the check produces)",
    "declared_at": "<ISO 8601 UTC>",
    "satisfied_at": "<ISO 8601 UTC — appended when the check has actually run>",
    "evidence_path": ".architect-team/checks/<run-id>-playwright.txt"
  }
]
```

- `gate_id` — a stable slug; `declaration_text` — the gate as STATED, verbatim, so the audit can quote the run's own words back; `check_command_or_artifact` — what will satisfy it, decided at declaration time rather than negotiated later; `declared_at` — when the promise was made.
- **Satisfying a gate appends `satisfied_at` + `evidence_path`** to its own entry. `evidence_path` cites the executed check's captured output or its verdict file — a path that exists and is non-empty. Satisfaction is a recorded fact, not a recollection.

**The audit.** `_audit_declared_gates` in `hooks/pipeline-completion-audit.py` (worklist family) walks the registry at Stop / pre-commit: every entry must carry `satisfied_at` and an `evidence_path` that exists and is >0 bytes, or the run is **blocked** with a violation quoting that gate's own `declaration_text`. **Fail-open when the registry file is absent** — a run that declared nothing has nothing to satisfy, and no foreign workflow is affected.

**Cite the `gate_id` when you write ship-gating prose.** A sentence that gates ship should name the registry entry it is gating on — "gated on `full-playwright-live-url`" — rather than restating the condition in fresh words. The audit correlates prose to entries by token overlap against `declaration_text`, and that is a STATED BOUNDARY, not a guarantee: a re-worded restatement can miss its entry, and a gate the audit cannot correlate is a gate that does not block. An explicit `gate_id` removes the guess.

**Before any ship step, check the registry.** Phase 8 / B8 / M7 auto-commit, auto-merge, and deploy steps read `declared-gates.json` first; an unsatisfied entry stops the ship step the same way the completion audit does, and the remediation is always the same — run the check, capture its output, append `satisfied_at` + `evidence_path`. Deleting or rewriting an entry to make the audit pass is the *unilateral override* failure mode (`## Unilateral-override discipline (v3.0.0) — META`), not a fix.
