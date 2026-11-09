# Operating rules (non-negotiable)

The UX-test-builder inherits every operating rule from `architect-team-pipeline`'s `## Operating rules (non-negotiable)` section — the no-arbitrary-timers rule, the unbounded-solving discipline (no iteration ceiling; loop until success), the shared-state concurrency model, the required-input-marker discipline, the safety rules for auto-commit. **Plus**:

- **Real-site testing.** All execution at U2 + U5 + U6 + the bug-fix pipeline's downstream B6 + B6b runs against the live target. NEVER mocked.
- **Independent expansion at U3.** The explorers (one by default; a panel of three at tier 3) do NOT consult each other during U3.
- **Literal first.** Phase U2 always runs BEFORE Phase U3 — the literal flow is the user's exact ask and gets its own pass.
- **Semantic distillation at U4.** Dedup is by goal + steps + rationale, not just string-match.
- **Tier-2 executor redundancy at U6.** Each flow runs once under the paired executor; a disputed flow runs again under a second executor, and three times only on a tier-3 panel — so flakiness surfaces as disagreement rather than as a silent pass.
- **Loop-until-converged at U7 (v3.8.0).** Disagreement → re-examination cycles until consensus, no fixed cycle cap. Persistent irreconcilable divergence surfaces to the owner as required input while the run continues — it never halts on cycle count.
- **Bug-route at U8.** Every `fail` becomes an SR; SRs auto-route through `bug-fix-pipeline`. Documenting bugs without routing is forbidden.
- **No credential leaks.** Raw secrets are NEVER persisted in any artifact (intake / proposal / verdict / trace / screenshot / report).
