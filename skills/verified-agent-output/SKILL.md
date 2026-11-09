---
name: verified-agent-output
description: The Verified Agent Output (VAO) framework -- six layers of machine-mediated verification of agent claims, closing the 'agent silently does the wrong thing' class of failures. Schema v7, deterministic tool verdicts, adversarial reviewer pairings, run-history shape detection, the Skill-invocation audit.
user-invocable: false
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

> **STOP.** Before acting under this section, Read `skills/verified-agent-output/references/the-six-layers.md` and execute it in full. Do not work from memory.

Position: a new phase inserted between Phase 0 (Detection & Normalization) and Phase 1 (Planning Validation) in every pipeline-driving skill.

## Composition with existing patterns — v2.0.0 ADDS layers, removes none

> **STOP.** Before acting under this section, Read `skills/verified-agent-output/references/composition-with-existing-patterns-v2-0-0-adds-layers-remove.md` and execute it in full. Do not work from memory.

The picture: v2.0.0 EARLIER nets catch failures the LATER nets had to catch post-facto. The later nets stay as the regression safety; the earlier nets reduce wasted Phase-3-through-Phase-5 cycles.

## Schema v7 — the breaking change

> **STOP.** Before acting under this section, Read `skills/verified-agent-output/references/schema-v7-the-breaking-change.md` and execute it in full. Do not work from memory.

Schema v7 adds five required fields to `REQUIRED_EVIDENCE_FIELDS`:

## No escape hatch

There is no `--no-vao` flag on any command: the six layers are part of every lane's contract, and the only way to run without a layer is the human's kill-switch for the hook that enforces it (named at each hook). Layer 3 tools remain available for ad-hoc CLI invocation.

## Failure-mode mapping (the audit trail)

> **STOP.** Before acting under this section, Read `skills/verified-agent-output/references/failure-mode-mapping-the-audit-trail.md` and execute it in full. Do not work from memory.

## Where this skill plugs in

- `hooks/vao_tools.py` — the Layer-3 facade + CLI: **26 tools** (v4.0.0) — the five originals verify-oracle-match, verify-baseline-clean, verify-no-fake-data, verify-every-element, verify-rendered-parity; the discipline tools (verify-check-can-fail was the 21st, v3.47.0; verify-diagnosis-falsified the 24th, v3.66.0); and the two v4.0.0 additions `verify-principles-respected` (`hooks/vao/principles.py`, the project-principles gate) and `verify-required-reads` (`hooks/vao/required_reads.py`, the INDEX-declared required reads, a measured gap).
- `hooks/vao/check_integrity.py` — the 21st Layer-3 tool's module (v3.47.0).
- `hooks/skill_invocation_audit.py` — the Layer 6 ENGINE: `find_skill_requests` (reused in real time by `hooks/pretool_skill_gate.py` Arm 1, which blocks build/dispatch tools until the mandated Skill is invoked) and the `audit_session` CLI (`--transcript --ledger --run-id --out`) that writes the verdict the `skill_invocation_audit` evidence field cites. It is NOT wired as a Stop hook.
- `hooks/review_evidence_schema.py` — schema v7: 17 required fields (the five required VAO fields among them) + 6 optional tool-mediated fields (`interactions_honored_review`, `live_verification_review`, `appearance_scope_review`, `check_integrity_review`, `claim_instrument_binding_review`, `principles_review`).
- `hooks/pipeline-completion-audit.py` — reads the `verify-check-can-fail` verdicts (`_audit_check_integrity`); the other VAO verdicts reach the gate through the evidence file `hooks/review-gate-task.py` validates, not through the Stop hook.
- `agents/oracle-deriver.md` — the Phase 0.5 agent.
- `agents/adversarial-reviewer.md` — the Phase 3 paired adversarial agent.
- `skills/architect-team-pipeline/SKILL.md` — Phase 0.5 + Layer 2 spawn brief + Layer 4 Phase −2 step.
- `skills/bug-fix-pipeline/SKILL.md` — analogous insertions at B0.5 / B3 / B−1.
- `skills/mini-architect-team-pipeline/SKILL.md` — analogous insertions at M0.5 / M5 / M0.
- `skills/verified-agent-output/references/the-six-layers.md` — the Layer 2 task-shape pairing table the review gate enforces.
- `skills/verified-agent-output/references/the-six-layers-part-2.md` (Layer 4, run-history shape detection) + `skills/common-pipeline-conventions/SKILL.md` `## Skill-invocation discipline (v2.0.0)`.
- `tests/test_vao_tools.py` — pins the Layer 3 tools' contracts.
- `tests/test_vao_skill_invocation_audit.py` — pins the Layer 6 engine.
- `tests/test_vao_fixtures.py` — pins each canonical fixture's round-trip.
- `tests/fixtures/vao/*.json` — the canonical synthetic fixtures.

## Operating rules (non-negotiable)

- A change to any of the six layers edits this skill ONCE. The pipeline skills' references stay one-line; the rule update propagates by reference.
- A pipeline skill MUST NOT re-explain any of the six layers inline — replace with a reference to this skill. Inline re-explanation is the drift-risk this skill exists to remove.
- An agent's `*_review` field in the evidence file MUST be either the legacy string-shape (`pass`/`n/a`/`fail`) OR the canonical dict-shape (`{verdict, verdict_path}`). A field that's a dict but lacks `verdict_path` is rejected at the hook layer.
- The cited verdict file IS the source of truth. The agent's inline summary is NOT — a passing inline summary that cites a failing verdict file is a hook-level violation, not just bad communication.
- Layer 6 is ALWAYS-ON, enforced BEFORE the fact: `pretool_skill_gate.py` Arm 1 refuses build/dispatch tools until the mandated Skill is invoked, and the review gate requires the `skill_invocation_audit` evidence field. A missing or failing field is a hard block at the gate.

## Reference index

Each heavy section's full text lives in this skill's `references/` folder behind the STOP pointer in its section; `references/INDEX.md` lists what to Read before each phase.

| Section | Reference file | Loaded |
| --- | --- | --- |
| `The six layers (part 2)` | `skills/verified-agent-output/references/the-six-layers-part-2.md` | on demand |
| `The six layers` | `skills/verified-agent-output/references/the-six-layers.md` | on demand |
| `Composition with existing patterns — v2.0.0 ADDS layers, removes none` | `skills/verified-agent-output/references/composition-with-existing-patterns-v2-0-0-adds-layers-remove.md` | on demand |
| `Schema v7 — the breaking change` | `skills/verified-agent-output/references/schema-v7-the-breaking-change.md` | on demand |
| `Failure-mode mapping (the audit trail)` | `skills/verified-agent-output/references/failure-mode-mapping-the-audit-trail.md` | on demand |
