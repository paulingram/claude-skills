# The six layers (part 2)

### Layer 4 — Run-history shape detection (Phase −2)

Position: at the end of Phase −2 (after the bug-classifier emits its verdict, before routing is finalized). `.architect-team/run-history/` accumulates one file per completed (or escalated) run. Schema:

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
  "vao_layers_engaged": [1, 2, 3, 4, 5, 6]
}
```

The new `vao detect-shape` tool reads all history files, computes the shape-fingerprint of the current requirement, and returns the top-3 matching prior runs (cosine similarity over the shape vector). If a matching prior run had `verdict: red-escalation` AND its `failure_modes_caught` contains any blocking-mode, the orchestrator surfaces:

> *"This run's requirement shape matches 2 prior runs that hit blocking failures (run-id X on date Y caught scope-narrowing; run-id Z on date W caught oracle-mismatch). The v2.0.0 layers paired with each prior failure will be engaged for this run by default. Confirm this is the intended interpretation, or describe a different shape."*

The user's response either confirms or reshapes the run. The orchestrator records the reshape.

### Layer 5 — Structural test enforcement (pytest suite)

The plugin's own pytest suite asserts each VAO layer is wired. Mirrors v1.4 / 1.6 / 1.7's pattern.

- Layer 1: `oracle-deriver` agent exists with the right frontmatter; the 3 pipeline bodies invoke it at Phase 0.5 (or analogous).
- Layer 2: every teammate spawn brief in the pipeline-body documentation includes `vao_task_shape`; the spawn-brief schema in `team-spawning-and-review-gates` includes adversarial-pairing rules.
- Layer 3: each `vao_tools.py` tool has positive + negative synthetic-fixture round-trips.
- Layer 4: `common-pipeline-conventions` has the `## Run-history shape detection` section; the four shape-vector fields are documented.
- Layer 5: schema v7's five required VAO fields are present and the hook blocks `fail` on each.
- Layer 6: `skill_invocation_audit.py` catches the heirship "applied methodology by hand" fixture.

The seven synthetic fixtures under `tests/fixtures/vao/` are the canonical positive cases for each failure shape; the pipeline MUST block each.

### Layer 6 — Skill-invocation verification (Stop hook)

Position: a new Stop-hook auditor (`hooks/skill_invocation_audit.py`) that fires at the END of every Claude Code session, AFTER all other Stop-hook handlers.

Why Layer 6 is the FOUNDATION layer: Layers 1-5 all fire WHEN the architect-team-pipeline Skill is INVOKED. If the orchestrator decides to "apply the methodology by hand" rather than invoke the Skill tool — the heirship-app-v2 session where a "do not re-execute" system note about an already-invoked skill was interpreted as a session-wide ban on re-invocation — none of Layers 1-5 fire. Layer 6 detects that case and blocks the run.

Mechanism:

1. **Parses the session transcript** for explicit user Skill-invocation requests in two surface forms:
   - **Slash-command form**: any of the 13 user-invocable command names preceded by `/` (case-insensitive).
   - **Prose form**: a verb (`use`, `using`, `invoke`, `run`, `fire`, `with`) + optional `the` + optional `/` + command name.
2. **Reads the session tool-call ledger** at `<workspace>/.architect-team/run-history/<run-id>-toolcalls.jsonl`. Each line is one tool invocation as `{ts, tool, args}`.
3. **Cross-checks.** For each explicit request, asserts a matching `Skill` invocation appears in the ledger AFTER the request's timestamp.
4. **Writes verdict JSON** to `<workspace>/.architect-team/vao-verdicts/<run-id>-skill-invocation-audit.json`.
5. **Exits 2** when any user request has no matching invocation.

Schema v7's `skill_invocation_audit` field MUST cite the verdict path.

The user-precedence rule (canonical home in `common-pipeline-conventions/SKILL.md` `## Skill-invocation discipline (v2.0.0)`): **user explicit instructions override "skill already invoked, do not re-execute" system notes**. Applying methodology by hand is forbidden — it bypasses every VAO framework layer.
