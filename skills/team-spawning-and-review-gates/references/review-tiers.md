# Review tiers — how many independent checkers a gate gets (v4.0.0)

> **STOP.** Before dispatching reviewers for any gate, decide the gate's tier
> from the table below and record it in the dispatch brief. Three independent
> reviewers is the right tool for a few high-stakes gates and an expensive
> default everywhere else.

The principle is unchanged: **the producer is never its own checker**. What
changes is how many checkers, and which model does the checking.

## The tiers

| Tier | Shape | Model | Use for |
|---|---|---|---|
| 3 | three independent reviewers in parallel + one synthesis; loop until all three return `ok` (a Workflow script owns the loop) | Fable 5.1 reviewers for architecture approval, the master review and map convergence; the Phase 7 editability / interaction sweep reuses those reviewers' shipped seats (Sonnet 5.5 under `--split role`) | architecture approval (`system-architect` Interface Contract Approval), the Phase 7 master review, codebase-map convergence (Phase −1B), integration-map convergence (Phase −1C) |
| 2 | the producer plus ONE paired adversarial reviewer; a second independent verifier only when the first two disagree | adversarial reviewer on Fable 5.1; mechanical verifiers on Sonnet 5.5 | every Phase 3 task gate (`task-reviewer` + `test-completeness-verifier`), editability and interaction completeness for a slice, bug-fix sensibility |
| 1 | one verifier, often a Layer-3 tool or a `prompt` hook with no agent dispatch | Haiku 5.5 or no model | classification (`bug-classifier`, prod-safety), evidence-file shape checks, manifest reconciliation, freshness checks |

## Rules

1. The tier is chosen **by the gate, not by the agent under review**. The table
   above is the default; a project principle or an explicit user instruction
   may raise a tier, never lower tier 3 gates below 2.
2. A tier-2 disagreement (producer evidence says pass, adversary says fail)
   escalates to a third independent verdict, which is final for that round.
3. Tier-1 verdicts are recorded like any other evidence; "no agent was
   dispatched" is written down, never implied.
4. The tier and the models used are written into the Phase 3 evidence file so
   the Stop audit and the homepage can report them.

5. A **research fan-out** (three `diagnostic-researcher` or `domain-researcher`
   seats exploring in parallel) is not a review tier: nothing is being verified
   yet, so the table is silent on it and the lanes label it a fan-out. The
   CONVERGENCE that follows it -- the map or the ranked cause the panel must
   agree on -- is a tier-3 gate and runs as a declared and recorded
   `ct6-converge` workflow.

## Why

`×3 in parallel` appeared 80 times across the v3.67.0 surfaces. Three
independent reviewers buy real signal when the question is judgment-heavy
(architecture, convergence of a whole map, the final review). For a mechanical
check they buy three copies of the same answer at three times the price.
Models follow the same logic: the sharpest attacker on the adversarial seat,
a fast model on mechanical verification, the cheapest on classification.

## Honest boundary

A tier is a dispatch decision; it does not make a reviewer right. The
evidence rules (verified-live, no proxy element, evidence integrity) apply at
every tier.
