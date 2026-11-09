# Composition with existing patterns — v2.0.0 ADDS layers, removes none

| Existing gate (v1.x) | What it catches | v2.0.0 changes |
|---|---|---|
| `task-reviewer` (Phase 3 independent review) | Self-attestation gap on per-task correctness | Unchanged — still required; schema v7 adds `adversarial_review` ALONGSIDE |
| `test-completeness-verifier` (Phase 3 + 5) | Missing unit / integration / Playwright kinds | Unchanged |
| `interaction-completeness` (Phase 5) | Unwired controls, placeholder pages, hardcoded literals | Unchanged — late net; Layer 1 + 2 catch the same shapes EARLIER |
| `editability-completeness` (Phase 5) | Attributes the UI can't actually edit | Unchanged |
| `visual-verification-team` (Phase 5) | Visual drift vs DESIGN_MAP | Unchanged |
| `system-architect` Master Review Audit (Phase 7) | Coverage-map self-attestation gap | Extended — now also walks VAO verdicts |
| `documentation-currency` audit (Phase 8) | Stale docs after a run | Unchanged |
| `pipeline-completion-audit.py` (Stop hook) | Incomplete-state termination | Extended — reads the `verify-check-can-fail` verdicts (`_audit_check_integrity`); the other VAO verdicts gate through the evidence file at the review gate |

The picture: v2.0.0 EARLIER nets catch failures the LATER nets had to catch post-facto. The later nets stay as the regression safety; the earlier nets reduce wasted Phase-3-through-Phase-5 cycles.
