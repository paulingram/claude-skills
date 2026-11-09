# Default mode of operation — drive end-to-end, don't ask obvious things

The pipeline's default is **forward motion**, not deliberation. When `/architect-team` is invoked, drive Phases −1 → 8 to completion. Do NOT ask the user clarifying questions when one path is obviously right — pick the sensible default, state your pick in one line, and proceed. The user corrects in their next turn if they wanted otherwise — that costs them one short message; asking up front costs the same plus an extra round trip and signals the wrong default ("you want approval?"). An obvious clarifying question — *"How should I fix this bug? → Fix it properly"* — is itself a defect; catch it before sending. Bugs and clear-fix scenarios get fixed at the right scale (a small edit, a focused commit, or the full pipeline) — sized by the work, not by asking.

### Gates are opt-in (process gates)

A proposal-first pause (Phase −1 → 1, then stop for user review before Phase 2 implementation), an `AskUserQuestion` call, an approval prompt, a "do you want me to proceed?" — engage these ONLY when:

- The user **explicitly requests a gate** in their input — phrases like *"propose first"* / *"review before implementing"* / *"show me the plan first"* / *"stop after the proposal"*, OR the `--proposal-first` flag on `/architect-team`. OR
- A **genuinely material fork** exists where the user's answer changes what is built AND the answer is not obvious — a real architectural tradeoff with two reasonable answers, a scope choice with non-trivial cost, a security / credential decision, or a destructive irreversible action.

The bar for asking is high; the default is to proceed.

### Process gates vs. domain gates

The opt-in rule above applies to **process gates** — interruptions to the pipeline's forward motion (the `--proposal-first` pause, "do you want me to proceed?" approval prompts, clarifying `AskUserQuestion` calls whose answer is obvious). It does NOT apply to **domain gates** — user-input steps that ARE part of the deliverable. The Phase −1D bulk-verify of low-confidence interaction intuitions, the `editability-completeness` team's `ambiguous` attribute escalation, and the `interaction-completeness` team's `ambiguous` element escalation are domain gates: they fire whenever the user's specific factual input is required to produce the deliverable correctly, regardless of `--proposal-first`. They are the work, not interruptions to it.

### Proposal-first mode (engaged by an explicit opt-in trigger)

Run Phases −1 → 1, present the validated proposal / design / specs / tasks / coverage-map package, write `<workspace>/.architect-team/escalation-pending.md` describing what is being awaited, and PAUSE. Resume Phases 2 → 8 when the user replies *"proceed"* (or revises the proposal and replies). Otherwise the default is the full Phases −1 → 8 build, no pause. (Domain gates inside Phase −1 — the Phase −1D bulk-verify — still fire even when `--proposal-first` is engaged: they precede the pause and the user's verifications inform the proposal the user then reviews.)

### In-flight clarification handling (v2.5.0)

If the user injects a message mid-run (after this skill has begun executing Phase −2 / −1 / 0 / 1 / 2 / 3 / 3b / 4 / 5 / 6 / 7 / 8) AND the message does NOT explicitly cancel the run AND is NOT a fresh `/architect-team:<command>` invocation, the orchestrator MUST treat the message as a **clarification or scope amendment to the IN-FLIGHT run** — append it verbatim to `<workspace>/.architect-team/clarifications/<run-id>-<ts>.md`, re-evaluate the in-flight phase against the amended brief (re-run Phase 0 → 1 if scope materially shifted; otherwise fold into the next phase's inputs), and continue the pipeline. The orchestrator MUST NOT (a) solve the clarification with tools directly bypassing the pipeline, (b) answer conversationally and continue without folding, (c) spawn a sibling `/architect-team` invocation, or (d) silently ignore. Full rules + the 3 detection signals + 4 forbidden anti-patterns + cancellation channel in `common-pipeline-conventions/SKILL.md` `## In-flight clarification discipline (v2.5.0)`.
