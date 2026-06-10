---
name: verified-agent-output
description: The Verified Agent Output (VAO) framework — six layers of machine-mediated verification of agent claims. Closes the class of "agent silently does the wrong thing" failures the plugin has been patching one at a time. Schema v7 + 5 deterministic tool verdicts + adversarial reviewer pairings + run-history shape detection + Skill-invocation audit.
---

# Verified Agent Output (VAO) — the v2.0.0 structural fix

This skill is the canonical home of the framework that the v1.x discipline patches (v1.4 scope, v1.6 git, v1.7 frontend-fake-data, v1.8 agent-resume) were groping toward. The v1.x fixes all share the same shape — documentation telling the agent NOT to do the wrong thing — and they hit the same ceiling: a hook checks the agent's WORDS are present in the evidence file, not whether the agent's claims are TRUE. v2.0.0 converts each subjective agent judgment call at a critical pipeline moment into a machine-verified objective check.

## Why this exists

| v1.x patch | Failure | Documentation said | Hook checked | What was still missing |
|---|---|---|---|---|
| v1.4.0 | Scope-narrowing | "Don't silently narrow scope" | The skill body contains those words | Whether the agent's actual interpretation matched the oracle |
| v1.6.0 | `git stash` clobbering | "Forbidden ops list" | The agent body contains the rule | Whether the agent actually ran those ops |
| v1.7.0 | Frontend faking missing API | "Don't fake data; surface an SR" | Skill body contains the discipline | Whether the diff actually contains fake data |
| v1.8.0 | Agent stream-timeout | "Wrap dispatch results in resume helper" | Agent body has the section | Whether the orchestrator actually called the wrap helper |
| heirship | "Pixel parity: pass" from source-audit | (no rule existed) | (no check existed) | Whether the rendered DOM actually matches |
| heirship | "Addressed with residual variance" | (no rule existed) | (no check existed) | Whether the user's stated bar was met |
| heirship | "Applied methodology by hand" | (no rule existed) | (no check existed) | Whether the Skill was actually invoked |

In every row the gap is the same shape: machine verification of the specific claim. v2.0.0 ships six layers, each closing one rung of that ladder.

## The six layers

### Layer 1 — Pre-execution oracle derivation (Phase 0.5 gate)

Position: a new phase inserted between Phase 0 (Detection & Normalization) and Phase 1 (Planning Validation) in every pipeline-driving skill.

Trigger: the requirement contains a parity verb (`match`, `rebuild`, `mirror`, `parity`, `make like`, `replicate`) OR names an oracle codebase / design mockup / reference URL.

Mechanism: a dedicated `oracle-deriver` agent (opus, read-only) walks the named oracle and produces a structured canonical spec at `<workspace>/.architect-team/oracle-spec/<change-name>.json` with these top-level fields:

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
  "chrome_topology": [ /* rendered-DOM mount-level expectations */ ],
  "schemas": [ /* every contract surface */ ],
  "_human_review_required": true
}
```

The orchestrator surfaces the spec to the user with ONE confirmation gate. On accept, `_human_review_required` flips false; the spec is frozen and becomes the binding contract every downstream layer measures against. On reject, the user's correction text re-feeds the deriver, which re-derives and re-surfaces; this repeats until the user accepts — there is no fixed cycle cap (per `common-pipeline-conventions` `## Unbounded solving discipline`), and the only pause is waiting on the user's own confirmation, which IS the deliverable.

**Why this catches the failures.** Scope-narrowing: the agent's interpretation IS the structural enumeration; reframing prose is impossible. Oracle structure mismatch: the structural diff is the FIRST artifact; subsequent work measures against it deterministically.

### Layer 2 — Adversarial-reviewer pairing (extends Phase 3)

Position: concurrent with every Phase 3 teammate dispatch. The producer-cannot-be-its-own-checker pattern (v0.9.13) scales from "is the work done" to "does the work exhibit the failure-mode the task-shape is prone to."

Task-shape taxonomy (computed at Phase 2 spawn-brief time):

| Task shape | Triggered by | Adversarial role assigned | Tool invoked |
|---|---|---|---|
| `parity-verb` | Frozen oracle spec referenced by the task | `oracle-divergence-hunter` | `verify-oracle-match` |
| `backend-dep` | Frontend task referencing a `pending-backend` or `missing-api-for-frontend-element` SR | `fake-data-hunter` | `verify-no-fake-data` |
| `shared-tree` | ANY teammate dispatch (always-on) | `git-discipline-hunter` | `verify-baseline-clean` |
| `dynamic-value` | Task touches a designed screen with non-trivial `dynamic_values[]` | `hardcoded-literal-hunter` | `verify-no-fake-data` |
| `default` | None of the above | `general-anti-pattern-hunter` | (light sweep across 4 shapes) |

The `adversarial-reviewer` agent is dispatched alongside the teammate, gets access to the teammate's tool-call log + diff, and writes its `adversarial_review` block into the SAME `<cwd>/.architect-team/reviews/<task-id>.json` evidence file. The Phase 3 hook (schema v7) requires BOTH `independent_review.verdict == "pass"` AND `adversarial_review.verdict == "pass"`. The gate opens only when both pass.

### Layer 3 — Tool-mediated execution proof (`hooks/vao_tools.py`)

Five deterministic verification tools. Each produces machine-mediated proof; the agent's prose attestation is no longer accepted.

#### `verify-oracle-match`

Input: built tree dict + frozen oracle-spec dict. Walks both with deterministic normalization (whitespace stripped, dict keys sorted, list ordering preserved). Output:

```json
{
  "tool": "verify-oracle-match",
  "matched": true|false,
  "divergences": [{"path": "App.Header.label", "expected": "...", "actual": "...", "severity": "missing-in-actual"|"extra-in-actual"|"value-mismatch"|"type-mismatch"}],
  "match_pct": 0.0-1.0,
  "verdict_at": "<ISO 8601 UTC>"
}
```

#### `verify-baseline-clean`

Input: teammate's tool-call log path + optional baseline SHA. Greps the log for the six v1.6.0-forbidden git operations (`git stash`, `git reset --hard`, `git rebase`, `git commit --amend`, `git checkout <other-branch>`, `git clean -f`) without firing on legitimate read ops (`git status`, `git log`, `git diff`, `git stash list`). Output:

```json
{
  "tool": "verify-baseline-clean",
  "clean": true|false,
  "violations": [{"op": "git stash", "args": "...", "line": 7, "ts": "..."}],
  "baseline_sha": "<sha or null>",
  "verdict_at": "<ISO 8601 UTC>"
}
```

#### `verify-no-fake-data`

Input: list of changed files (each with added lines) + the frozen oracle spec's `dynamic_values[]`. Pattern-matches every line in production code (test files are skipped) against:

- Placeholder names — `John Smith`, `Jane Doe`
- Placeholder emails — `john.doe@example.com`, etc.
- Lorem ipsum
- Placeholder money — `$1,234.00` / `$1,234.56`
- MSW handler signatures — `rest.get(`, `http.post(`, etc.
- Playwright route fulfill stubs — `page.route(... .fulfill(...)`
- Every oracle-declared dynamic-value literal (e.g., if the oracle binds `Park Family Trust` to `matter.title`, the literal `Park Family Trust` must NOT appear in production code)

Each line is matched against EVERY category — a line carrying both a placeholder name AND an MSW handler is flagged for both. Output:

```json
{
  "tool": "verify-no-fake-data",
  "clean": true|false,
  "hits": [{"file": "src/Users.tsx", "line": 0, "match": "John Smith", "category": "placeholder-name"}],
  "verdict_at": "<ISO 8601 UTC>"
}
```

#### `verify-every-element`

Input: list of built components (each with elements) + the oracle's `elements[]`. For every oracle-named element, asserts presence in the built tree, non-stub handler, Playwright test driving it. Output:

```json
{
  "tool": "verify-every-element",
  "coverage": 0.0-1.0,
  "missing": [{"selector": "#cancel"}],
  "stub": [{"selector": "#submit", "handler": "() => {}"}],
  "untested": [{"selector": "#delete"}],
  "verdict_at": "<ISO 8601 UTC>"
}
```

#### `verify-rendered-parity` (the heirship-amendment tool)

Input: candidate rendered-DOM snapshot + oracle rendered-DOM snapshot + oracle-spec `chrome_topology[]` + optional screenshot paths + optional pre-computed pixel-diff percentage. Operates on the RENDERED DOM — NOT the source component tree. Catches the canonical heirship case where the SAME element exists in both candidate and oracle source but mounts at DIFFERENT rendered parent paths.

Output:

```json
{
  "tool": "verify-rendered-parity",
  "matched": true|false,
  "divergences": [
    {"anchor": "[data-component='TaCrumbs']",
     "expected_level": "body > [AppShellLayout] > [AppShellHeader]",
     "actual_level": "body > [AppShellLayout] > [AppShellBody] > [data-testid='page-body']",
     "severity": "architectural-mismatch"|"missing-in-candidate"|"missing-in-oracle"|"pixel-divergence"}
  ],
  "pixel_diff_pct": 0.0-1.0,
  "screenshot_paths": {"oracle": "...", "candidate": "...", "diff": null},
  "verdict_at": "<ISO 8601 UTC>"
}
```

The schema v7's `visual_fidelity_review` field MUST cite this tool's verdict path. An agent's "pixel parity: pass" attestation derived from reading source code is REJECTED at the hook layer — the cited verdict file is the source of truth.

**Why this tool is distinct from `verify-oracle-match`.** The latter walks the SOURCE component tree; that's sufficient for schema / API / structural-data parity but BLIND to chrome-level architectural divergences where the element exists in source but at the wrong mount point. The canonical heirship failure: `heirship-app-v2`'s `TAMatterDetail.tsx` rendered `<TaCrumbs />` inside its page body; the oracle (`heirship-app-v3`) renders the same `<TaCrumbs />` inside `AppShellHeader`. Source audit says matched; rendered audit catches the divergence.

Each tool writes its verdict JSON to `<cwd>/.architect-team/vao-verdicts/<task-id>-<tool>.json`. The schema v7 `*_review` field cites the verdict path; the hook reads the cited file at validation time.

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
- Layer 5: schema v7's six required VAO fields are present and the hook blocks `fail` on each.
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

## Composition with existing patterns — v2.0.0 ADDS layers, removes none

| Existing gate (v1.x) | What it catches | v2.0.0 changes |
|---|---|---|
| `task-reviewer` (Phase 3 independent review) | Self-attestation gap on per-task correctness | Unchanged — still required; schema v7 adds `adversarial_review` ALONGSIDE |
| `test-completeness-verifier` (Phase 3 + 5) | Missing unit / integration / Playwright kinds | Unchanged |
| `interaction-completeness` (Phase 5) | Unwired controls, placeholder pages, hardcoded literals | Unchanged — late net; Layer 1 + 2 catch the same shapes EARLIER |
| `editability-completeness` (Phase 5) | Attributes the UI can't actually edit | Unchanged |
| `visual-verification-team` (Phase 5) | Visual drift vs DESIGN_MAP | Unchanged |
| `system-architect` Master Review Audit (Phase 7) | Coverage-map self-attestation gap | Extended — now also walks VAO verdicts |
| `documentation-currency` audit (Phase 8) | Stale docs after a run | Unchanged |
| `pipeline-completion-audit.py` (Stop hook) | Incomplete-state termination | Extended — now also blocks on missing VAO verdicts + invokes Layer 6 |

The picture: v2.0.0 EARLIER nets catch failures the LATER nets had to catch post-facto. The later nets stay as the regression safety; the earlier nets reduce wasted Phase-3-through-Phase-5 cycles.

## Schema v7 — the breaking change

Schema v7 adds six required fields to `REQUIRED_EVIDENCE_FIELDS`:

```python
REQUIRED_EVIDENCE_FIELDS = {
    # v6 fields (unchanged)
    "task_id", "spec_review", "quality_review", "real_not_stubbed",
    "tests", "demo_artifact", "files_changed", "reuse_compliance",
    "visual_fidelity_review", "test_completeness_review",
    "integration_testing_review", "ui_interaction_review",
    # v7 VAO fields
    "oracle_match_review",      # cites verify-oracle-match verdict
    "baseline_clean_review",    # cites verify-baseline-clean verdict
    "no_fake_data_review",      # cites verify-no-fake-data verdict
    "adversarial_review",       # Layer 2 — adversarial-reviewer's verdict
    "skill_invocation_audit",   # cites Layer 6 audit verdict
}
```

Each field accepts EITHER:
- A string in `{'pass', 'n/a', 'fail'}` — legacy review-shape.
- A dict `{verdict: ..., verdict_path: "<path to cited JSON>"}` — canonical v7 shape that cites the on-disk tool verdict.

The hook blocks any evidence file missing any field OR carrying a `fail` verdict on any field.

**Migration.** v6 evidence files DO NOT validate against v7. Runs not in flight at the v2.0.0 upgrade: no action needed; new runs use v7 from Phase 0.5. Runs in flight at upgrade: re-spawn the active teammates against v7.

## `--no-vao` escape hatch

The three pipeline-driving slash commands (`/architect-team`, `/architect-team:bug-fix`, `/architect-team:mini`) accept a `--no-vao` flag that disables Layers 1, 2, 4, 5. Layer 3 tools remain available for ad-hoc CLI invocation; Layer 6 (Skill-invocation audit) is ALWAYS-ON and cannot be opted out — the audit checks whether the framework was invoked at all, so opting out IS the failure mode it exists to catch.

Trade-off: `--no-vao` re-opens the v1.x failure modes (scope-narrowing, git-stash clobbering, fake data, oracle mismatch, source-vs-rendered audit, execution-time variance). Use only when the user has explicitly accepted that trade.

## Failure-mode mapping (the audit trail)

| Failure | Caught at Layer | Caught how |
|---|---|---|
| v1.4.0 — silent scope narrow at intake | Layer 1 | Oracle-deriver shows the structural spec; user accepts BEFORE Phase 2; agent doesn't get to "interpret" |
| v1.4.0 — agent reframes mid-run | Layer 2 (`parity-verb` shape) | `oracle-divergence-hunter` runs `verify-oracle-match` on the teammate's diff |
| v1.6.0 — teammate runs `git stash` | Layer 2 (`shared-tree`, always-on) | `git-discipline-hunter` runs `verify-baseline-clean` on the tool-call log |
| v1.7.0 — frontend mocks the API | Layer 2 (`backend-dep`) | `fake-data-hunter` runs `verify-no-fake-data` on the diff |
| v1.7.0 — frontend hardcodes the response | Layer 2 (`backend-dep` + `dynamic-value`) | Same — overlapping coverage by design |
| v1.7.0 — frontend silently stubs the UI | Layer 2 (`backend-dep`) + Layer 3 (`verify-every-element`) | Coverage check finds the stub element |
| heirship — oracle structure mismatch | Layer 1 + Layer 2 + Layer 3 | Deterministic structural diff; teammate cannot pass without matching |
| heirship — "pixel parity pass" from source audit | Layer 3 (`verify-rendered-parity`) | Rendered DOM + screenshot diff; agent prose attestation forbidden |
| heirship — "addressed with residual variance" | Layer 3 + Schema v7 | The cited verify-rendered-parity verdict's `matched: false` blocks regardless of the agent's inline `verdict: pass` |
| heirship — "applied methodology by hand" | Layer 6 | Stop-hook auditor blocks when explicit user Skill request has no matching `Skill` invocation |
| novel failure shape on future run | Layer 4 | Run-history feed makes the framework learn; future runs with the same shape get a known check |

## Where this skill plugs in

- `hooks/vao_tools.py` — the five Layer-3 tools (verify-oracle-match, verify-baseline-clean, verify-no-fake-data, verify-every-element, verify-rendered-parity).
- `hooks/skill_invocation_audit.py` — the Layer 6 Stop-hook auditor.
- `hooks/review_evidence_schema.py` — schema v7 declaring the six required VAO fields.
- `hooks/pipeline-completion-audit.py` — extended to assert VAO verdicts + delegate to Layer 6.
- `agents/oracle-deriver.md` — the Phase 0.5 agent.
- `agents/adversarial-reviewer.md` — the Phase 3 paired adversarial agent.
- `skills/architect-team-pipeline/SKILL.md` — Phase 0.5 + Layer 2 spawn brief + Layer 4 Phase −2 step.
- `skills/bug-fix-pipeline/SKILL.md` — analogous insertions at B0.5 / B3 / B−1.
- `skills/mini-architect-team-pipeline/SKILL.md` — analogous insertions at M0.5 / M5 / M0.
- `skills/team-spawning-and-review-gates/SKILL.md` — `## VAO task-shape pairing` section + manifest v2.
- `skills/common-pipeline-conventions/SKILL.md` — `## Run-history shape detection (v2.0.0)` + `## Skill-invocation discipline (v2.0.0)` sections.
- `commands/{architect-team,bug-fix,mini}.md` — `--no-vao` flag.
- `tests/test_vao_tools.py` — 32 tests pinning the 5 tools' contracts.
- `tests/test_vao_skill_invocation_audit.py` — 55 tests pinning the Layer 6 audit.
- `tests/test_vao_fixtures.py` — 19 tests pinning each canonical fixture's round-trip.
- `tests/fixtures/vao/*.json` — 7 canonical synthetic fixtures.

## Operating rules (non-negotiable)

- A change to any of the six layers edits this skill ONCE. The pipeline skills' references stay one-line; the rule update propagates by reference.
- A pipeline skill MUST NOT re-explain any of the six layers inline — replace with a reference to this skill. Inline re-explanation is the drift-risk this skill exists to remove.
- An agent's `*_review` field in the evidence file MUST be either the legacy string-shape (`pass`/`n/a`/`fail`) OR the canonical dict-shape (`{verdict, verdict_path}`). A field that's a dict but lacks `verdict_path` is rejected at the hook layer.
- The cited verdict file IS the source of truth. The agent's inline summary is NOT — a passing inline summary that cites a failing verdict file is a hook-level violation, not just bad communication.
- Layer 6 is ALWAYS-ON. `--no-vao` does not disable it. A skill-invocation audit failure is a hard block.
- `--no-vao` MUST come with an explicit user acknowledgment of the re-opened failure modes — the documentation lists them; the orchestrator surfaces them in the run summary.
