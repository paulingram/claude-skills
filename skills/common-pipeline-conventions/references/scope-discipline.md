# Scope discipline

A pipeline run starts with a user prompt. The first thing the run does — before refinement, before triage, before any teammate dispatches — is *read that prompt*. The user's prose IS the contract. Reframing the prompt's scope to fit what the agent thinks is reasonable, what fits the available time, what the agent already knows how to do, or what the agent has been hoping to defer, is **not** the same as answering an obvious clarifying question. It is a domain decision the user hasn't authorized. The plugin treats it as a domain gate and makes the agent surface it explicitly.

### Anti-pattern (forbidden) — silently narrowing the prompt's scope

The shape: the user asks for X; the agent reads X but executes a narrower X' (sometimes a fragment of X, sometimes a phase 1 of X); the agent documents the gap as queued for a future run; the agent does NOT ask the user whether X' is the right scope. The user gets X' and a paragraph explaining why the rest was deferred. The user wanted X. (Canonical case in CHANGELOG v1.4.0: *"match the oracle"* read as *"enrichment + hardcoded data purge"* with the visual rebuild silently deferred.)

This is the intake member of the scope-fidelity discipline family (see `## Scope-fidelity discipline family (v3.10.0)`) — structurally identical to the v0.9.36 anti-deferral pattern, fired EARLIER in the timeline (at intake instead of mid-run).

### The 6 parity-implying verbs (v1.4.0 list)

When the prompt contains any of these verbs against a designed surface (a screen, a flow, an existing reference implementation), the implied scope is **visual + structural + behavioral parity** — NOT data-only, NOT enrichment-only, NOT "phase 1 of N":

| Verb | Example prompt phrasings | Implied scope |
|---|---|---|
| **match** | *"match the oracle"*, *"make X match Y"* | Visual + structural + behavioral parity with the named reference |
| **rebuild** | *"rebuild the dashboard to look like the design"* | Full rebuild — visual + structural + behavioral parity |
| **mirror** | *"mirror the production behavior"*, *"mirror the V1 flow"* | Visual + structural + behavioral parity with the named source |
| **parity** | *"we need parity with the V1 flow"*, *"feature parity with X"* | Explicit parity — visual + structural + behavioral, no partial |
| **make like** | *"make the new page like the existing one"*, *"make it look like X"* | Visual + structural + behavioral parity with the named target |
| **replicate** | *"replicate the wizard from project X"* | Visual + structural + behavioral parity with the named source |

The list is intentionally short — these are the highest-frequency parity-implying verbs. The user may extend the list in a future v1.x once the discipline beds in. When the prompt contains any of these verbs AND the agent's interpretation is narrower than visual + structural + behavioral parity (data-only, partial, "phase 1 of N", "the obvious gaps" only), the agent MUST surface the scope question before proceeding.

### The domain-gate rule

Scope-narrowing IS a domain gate per the v0.9.21 carve-out. The v0.9.20 "gates are opt-in" rule applies to PROCESS gates (the user did not ask for a proposal-first pause, so don't pause). A scope-narrowing decision is not a process gate — it changes what the run produces. Domain gates fire regardless of `--proposal-first`, regardless of "default to action," regardless of how obvious the agent thinks the narrower interpretation is. The agent's confidence that the narrower interpretation is what the user "really meant" is exactly the failure mode this rule closes.

The `## Default mode of operation` rule (in each pipeline body) says *"don't ask obvious clarifying questions."* A scope-narrowing is NOT an obvious clarifying question — it is a reframing of work. The two rules don't conflict; the scope-discipline rule applies to a narrower case (the agent has decided the prompt's literal meaning is wrong) and OVERRIDES the default-action rule for that case.

### The surfacing pattern — `AskUserQuestion` BEFORE starting

When the agent identifies that its reading of the prompt is materially narrower than the prompt's literal meaning, the agent surfaces a single focused question via `AskUserQuestion` BEFORE doing any other intake work, BEFORE invoking refinement, BEFORE drafting a proposal. The question pins the scope choice to the user, who answers; the answer becomes the contract.

Example wording for a `match`-verb prompt:

> *"You said 'match the oracle.' I read this as visual + structural + behavioral parity with the oracle. Is this run scoped to: (a) full parity rebuild (visual + structural + behavioral), or (b) data-binding only, with the visual rebuild deferred to a separate run?"*

Example wording for a `rebuild`-verb prompt where the agent was about to scope to "enrichment only":

> *"You said 'rebuild the dashboard.' I'm reading this as a full visual + structural rebuild against the design. I was about to scope this run to data-enrichment only and defer the visual work. Should I (a) do the full rebuild as you literally asked, or (b) restrict this run to the data work?"*

The question pattern is: name the prompt's literal meaning, name the agent's narrower reading, ask which the user wants. The user answers (a) or (b); the agent records the answer in the refined prompt's `## Goal` or the proposal's `## Why` so the contract is auditable.

### Explicit forbidden patterns

Each of these is the anti-pattern in a different costume — flag them in code review, in proposal review, and in the master-review audit:

- **Documenting work as queued for next runs without explicit user authorization.** A `## Out of scope` section in the proposal listing items the agent decided to defer, when the prompt's literal meaning included them, is the anti-pattern in its most-common form. The `## Out of scope` section is for items the user explicitly authorized as deferred (quoted verbatim) — NOT items the agent decided to defer because they would have been more work.
- **Interpreting parity-implying verbs as "phase 1 of N" without confirming.** *"Match the oracle"* read as *"data-enrichment in phase 1, visual rebuild in phase 2"* is the agent inventing a phase split the user did not authorize. If the work is genuinely too large for one run, the agent asks; it does not pre-split.
- **Unilaterally splitting the user's ask into "this run" and "future runs."** Same shape as the previous, generalized to any verb. The agent's job at intake is to read the prompt and execute it, not to pre-compute a multi-run roadmap.
- **Scoping to a narrower interpretation and then DOCUMENTING the gap, rather than asking before scoping.** This is the most common failure mode — the agent has noticed the gap (correctly), has the discipline to flag it, but flags it as a documented deferral instead of as a clarifying question. The discipline IS the question, not the documentation.
- **Treating "the agent is confident the narrower scope is what the user really meant" as authorization.** Silence is not authorization. The user's literal prose is the ground truth. The agent's intuition about what the user "really" wanted is the exact failure mode this rule closes.

### Example — the discipline applied correctly

The user types *"rebuild the heir-assets table to match the oracle's table"*; the agent's first instinct is to fix only the visible data-binding defect ("9 heirs · 0% totals") and defer the visual rebuild. The agent recognizes this as a scope-narrowing decision (`rebuild` + `match` imply visual + structural + behavioral parity, materially wider than the data fix) and surfaces the (a)-full-parity / (b)-data-only question via `AskUserQuestion` BEFORE any work. The user's answer is recorded verbatim in the refined prompt's `## Goal` — a (b) answer is the rare correct deferral (explicit user words in `## Out of scope`); anything the agent decides on its own is the anti-pattern.
