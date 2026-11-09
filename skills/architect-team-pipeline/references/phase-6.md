# Phase 6 — Outer Loop

Repeat Phase 2 → Phase 5 for each task group in the OpenSpec plan, respecting the dependency graph from Phase 2. Maintain a running ledger:

- Completed task groups
- Commits produced (with SHA + message + which requirement(s) served)
- Tests added (unit / integration / e2e) and their pass status
- Playwright flows executed, with traces

### Target-element verification gate (v2.21.0)

After the Phase 5 cross-layer Playwright runs complete, invoke the 19th Layer 3 tool against every verification artifact that carries a per-element PASS claim:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/vao_tools.py" verify-target-element-measured --artifact "<workspace>/.architect-team/vao-evidence/<run-id>.json" --out "<workspace>/.architect-team/vao-verdicts/<run-id>-target-element.json" || python "${CLAUDE_PLUGIN_ROOT}/hooks/vao_tools.py" verify-target-element-measured --artifact "<workspace>/.architect-team/vao-evidence/<run-id>.json" --out "<workspace>/.architect-team/vao-verdicts/<run-id>-target-element.json"
```

Any of the 3 severities (`proxy-element-substituted` / `unreachable-state-not-escalated` / `semantic-target-mismatch`) blocks the run. The fix loop routes SRs with `origin.kind: target-state-unreachable-needs-seed-data`. See `common-pipeline-conventions/SKILL.md` `## No proxy-element verification discipline (v2.21.0)` for the canonical home.
