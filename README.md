# architect-team
<!-- architect-team:readme-theme=midnight -->

```
      █████  ██████   ██████ ██   ██ ██ ████████ ███████  ██████ ████████
     ██   ██ ██   ██ ██      ██   ██ ██    ██    ██      ██         ██
     ███████ ██████  ██      ███████ ██    ██    █████   ██         ██
     ██   ██ ██   ██ ██      ██   ██ ██    ██    ██      ██         ██
     ██   ██ ██   ██  ██████ ██   ██ ██    ██    ███████  ██████    ██

                            ─── T E A M ───   v 0 . 9 . 30
```

> Spec-to-production multi-agent coding pipeline for Claude Code. Takes a
> requirements folder (OpenSpec / Superpowers / plain markdown), drives it
> through a 100%-coverage planning loop with reuse-first design, spawns
> parallel agent teams for backend / frontend, enforces review gates via
> hooks, **fixes design drift to spec autonomously**, **verifies the editable
> surface is complete**, **tests full-stack work against the real backend**,
> **auto-spawns fix teams from every surfaced issue**, **remembers what it
> learns in a local searchable memory**, and **auto-commits and pushes on a
> clean pass** — the dev loop closes itself end-to-end.

![version](https://img.shields.io/badge/version-0.9.30-2563EB?style=flat-square)
![license](https://img.shields.io/badge/license-MIT-3FB950?style=flat-square)
![tests](https://img.shields.io/badge/tests-1016%20passing-3FB950?style=flat-square)
![claude code](https://img.shields.io/badge/Claude%20Code-plugin-7C3AED?style=flat-square)

```
░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
█▓▒░  ◆  NEW IN v0.9.30  ◆  ░▒▓█
░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
```

| Capability | What changed |
|---|---|
| ▸ **Cross-platform Python hook invocation — Windows Store-shim fix (v0.9.30)** | A real user error after the v0.9.29 ship: *"● Ran 2 stop hooks ⎿ Stop hook error: Failed with non-blocking status code: Python was not found; run without arguments to install from the Microsoft Store…"* — the user had Python 3.12.10 installed and working as `python`, but the plugin's hooks and skill bodies invoked the script as `python3`. On default Windows python.org installs only `python` is on PATH; `python3` triggers the Microsoft Store shim, which prints that error and exits non-zero. The v0.9.16 portability work added a *detection* hint to `setup.py` but didn't make the hooks robust. v0.9.30 changes every plugin-script invocation in `hooks/hooks.json` (3 hooks), `skills/architect-team-pipeline/SKILL.md` (6 calls), `skills/bug-fix-pipeline/SKILL.md` (5 calls), and 4 commands (`architect-team`, `bug-fix`, `ux-test`, `architect-team-setup`, `mempalace-install`) to the polyglot pattern `python3 X.py args \|\| python X.py args`. On Unix the first form succeeds and the shell short-circuits (fallback never fires); on Windows-without-`python3` the shim's non-zero exit triggers the `\|\| python ...` fallback, which runs the script with the installed `python` and succeeds. The `\|\|` operator is supported by cmd.exe, POSIX sh, bash, zsh, fish, and PowerShell 7+ — covering every shell Claude Code dispatches hooks through. New `tests/test_hooks_structure.py::test_hooks_use_polyglot_python_fallback` (1 case) asserts every hook command carries the fallback AND that both sides target the same `.py` script. `tests/test_commands.py::test_setup_command_uses_python3` updated to require the fallback (the old *"must NOT contain bare ' python '"* assertion inverted because the polyglot fallback IS a bare-`python` invocation by design). 1016 tests / 0 failures (was 1015 in v0.9.29). |
| ▸ **UX test builder — persona-driven flow discovery → execution → bug-routing, plus a Phase B6b post-deploy sensibility check in the bug-fix pipeline (v0.9.29)** | The plugin's Playwright disciplines (`playwright-user-flows`, `interaction-intuition`, `interaction-completeness`) all operated on *the system being built*. None answered: *"given a persona + objective + a target site, does the site let the person do what they need AND the adjacent things they'd realistically need without breaking?"* v0.9.29 ships that — the new **`ux-test-builder`** skill (10 phases U0-U9, reached via `/architect-team:ux-test`) takes a persona description + objectives + target site (URL or `--dev`) + credentials (env-var reference, never the secret), maps the site (reuses `intake-and-mapping`), drafts a literal Playwright flow matching the user's exact ask at U2, dispatches 3 new **`flow-explorer`** agents at U3 to propose 10-15 adjacent flows each (the *"user said 'upload files' but the site has 3 upload paths and parsed data on 10 pages"* case — explorers find what the literal description missed), distills semantically at U4, authors one `.spec.ts` per flow at U5, dispatches 3 new **`flow-executor`** agents at U6 to run every flow once in parallel against the live target (3 × N executions; the redundancy IS the consensus mechanism), pools verdicts at U7 with 3-cycle bounded convergence on disagreements, and at U8 documents every `fail` flow as a bug + auto-routes through the existing `bug-fix-pipeline` with `origin.kind: "ux-flow-failure"`. **Also closes a real-world bug-fix-pipeline gap (cohesion-issue from a user report):** *"The fix correctly routes Sign Back In to /login, but the deployed bundle is hermetic (no VITE_* baked), so the LoginScreen shows 'auth-unavailable.' There needs to be a post deployment check for sensibility on all elements touched."* v0.9.29 adds **`## Phase B6b — Logical Sensibility Check`** in the bug-fix-pipeline (between B6 QA-replay and B7 archive) + the new **`fix-sensibility-checker`** agent that computes the impact set from the fix's git diff (changed files + their importers + nav destinations + endpoints), authors minimal Playwright sensibility flows per impact-set item, runs them against the deployed dev environment, and routes any `nonsensical` item as a fresh SR with `origin.kind: "fix-regression"` for recursive bug-fix-pipeline processing. The full chain: persona → flows discovered → flows executed → bugs found → bug-fix applied → QA-replay verifies symptom-gone → **B6b sensibility-checks the impact set → any new regression auto-loops** → finally archive. Bounded — 3 consecutive fix-regression SRs escalates. |
| ▸ **Cohesion-review close-out: confirmed-stubs cross-reference + polish (v0.9.28)** | Closes the remaining 6 issues from the v0.9.23 cohesion review in one release. **Issue #5 (UX)** — Phase −1D's `user_verdict: confirmed-stub` entries now flow downstream to Phase 5's `interaction-completeness` team: before enumerating, each reviewer reads `<codebase>/docs/INTERACTION_INTUITION_MAP.md`, pre-populates the converged map's `confirmed_stubs[]` for every pre-confirmed element (keyed on `element_id`), and does NOT re-ask the user. Stale-intuition handling (the element exists in the map but no longer in the enumeration) is documented as an `escalations[]` entry. The cross-reference is bidirectional with v0.9.21's binding-input rule. **Issue #6** — the v0.9.23 doc-updater dogfood asymmetry (the agent didn't exist when its own release ran) is now explicitly marked historical in CODEBASE_MAP. **Issue #7** — the Phase −1D structural-level choice (sub-section D in the main pipeline; its own H2 in intake-and-mapping) is intentionally aesthetic; a clarifying note documents this in both files. **Issue #8** — the `## Default mode of operation` section in the pipeline skill gains three H3 sub-headings (`### Gates are opt-in (process gates)`, `### Process gates vs. domain gates`, `### Proposal-first mode`) for navigability. **Issue #9** — `system-architect.md` gains an `## Audit modes` index table near the top listing all 7 audit modes + their verdict file locations + their default-mode counterpart, so the agent body is navigable at first glance. **Issue #10** — CODEBASE_MAP documents the plugin-cache vs. source-on-disk lag (cached plugin loads pinned-version skill bodies; consumer must `/plugin marketplace update` + `/plugin update architect-team` + `/reload-plugins` after a release commit lands). New `tests/test_confirmed_stubs_cross_reference.py` (12 cases) covers #5 + asserts the polish items #7-#10 landed. |
| ▸ **bug-fix-pipeline gets full notification wiring (v0.9.27)** | A v0.9.23 cohesion-review finding (issue #4): the main `architect-team-pipeline` mandates `phase_start` / `phase_complete` notifier calls at every phase boundary (Phase −1, 0, 1, ..., 8), plus `issue_discovered` / `git_commit` / `deploy` at specific phase steps. The v0.9.22 `bug-fix-pipeline` skill carried only ONE notification line — the `deploy` event at Phase B5. Phase B−1, B0, B1, B2, B3, B4, B6, B7, B8 had no documented `phase_start`/`phase_complete` wiring; the `issue_discovered` event was never wired (despite Phase B6's `bug-still-present` branch writing a fresh SR — exactly what `issue_discovered` exists to surface); the `git_commit` event was never wired (despite Phase B8 producing a commit). Subscribers to a target project's `.architect-team-notify.json` got verbose coverage of feature runs but silent bug-fix runs. v0.9.27 adds a full `## Notifications` section to `skills/bug-fix-pipeline/SKILL.md` paralleling the main pipeline's coverage, plus inline `issue_discovered` wiring at Phase B6's `bug-still-present` branch and inline `git_commit` wiring at Phase B8 immediately after the commit succeeds. All five event types (`phase_start`, `phase_complete`, `issue_discovered`, `git_commit`, `deploy`) now fire on bug-fix runs with the same opt-in / best-effort / never-blocking discipline as the main pipeline. New `tests/test_bug_fix_pipeline_notifications.py` (22 cases) asserts the section structure + the inline wiring + that every B-phase appears in the phase-boundary wiring list + parity with the main pipeline's CLI invocation form. |
| ▸ **system-architect agent gets bounded `Write` for its 7 audit verdicts (v0.9.26)** | A v0.9.23 cohesion-review finding (issue #3): the `system-architect` agent's body documented seven audit modes (Diagnostic Plan Review, Editability Map Review, Interaction Map Review, Visual Gap Synthesis, Master Review Audit, Documentation Currency Audit, Bug-Fix Generalization Audit) each ending with *"Write a verdict to `<cwd>/.architect-team/.../audit-<ts>.json`"* — but the agent's tools allowlist had no `Write`, and the Tools posture section explicitly said *"You have NO Edit or Write access."* The audit modes were internally contradicting the tools posture. Workaround was `Bash` heredoc — but every other verdict-producing agent in the plugin (`doc-updater`, `route-mapper`, `interaction-intuiter`, `bug-replicator`) uses `Write` with a bounded scope. v0.9.26 adds `Write` to the system-architect's allowlist with a bounded scope (verdict paths under `<cwd>/.architect-team/` only — NEVER source code, tests, openspec/* artifacts, the documentation-currency inventory (that's `doc-updater`'s scope per v0.9.23), `.claude-plugin/plugin.json` / `marketplace.json` (version source-of-truth), or any path outside `.architect-team/`). A new `## Bounded Write scope` section enumerates the 7 allowed paths in a table (one per audit mode). `Edit` remains excluded — whole-file verdict writes enforce consistency across the verdict's related fields (same discipline as `doc-updater`'s v0.9.23 design). New `tests/test_system_architect_write_scope.py` (14 cases) asserts `Write` is present, `Edit` is absent, the Tools posture documents the bounded scope (citing `doc-updater` for inventory ownership), the `## Bounded Write scope` section exists with each of the 7 audit modes + path prefixes documented, source-code / tests / openspec / inventory / plugin.json writes are explicitly forbidden, whole-file-writes rationale is documented. The pre-v0.9.26 *"NO Edit or Write access"* language is gone. |
| ▸ **bug-fix-pipeline gets its OWN planning-validation gate at Phase B3 (v0.9.25)** | The v0.9.22 bug-fix pipeline's Phase B3 originally said *"Run `openspec validate --strict` and the Phase 1 planning-validation gate (the same gate as `architect-team-pipeline` Phase 1, applied to this change)"* — but Phase 1's loop conditions are shaped for FEATURE work (authoring NEW Playwright user-flow specifications, NEW dev-API integration criteria, NEW Reuse Decisions for new files), and they trip on bug-fix-shaped work where the replication artifact from B2 IS the Playwright flow (already authored, already failing). A literal reading of Phase 1's conditions would fail-and-spin a backend-only bug fix on "missing Playwright criteria"; a liberal reading would hand-wave it. v0.9.25 gives the bug-fix pipeline its OWN slim **Bug-fix planning-validation gate** — seven conditions fit-for-purpose: (1) openspec validates; (2) every artifact is `done`; (3) coverage map has a source requirement; (4) coverage map records the replication artifact paths from B2 (BOTH Playwright + backend diagnostic for frontend/both-layer bugs; backend script alone for backend-only bugs); (5) reuse-first compliance (every new file has a Reuse Decision; extended existing files get the one-line *"extends `<function>` at `<path>:<line>`"* acknowledgment); (6) proposal's `## Why` cites the replication evidence verbatim; (7) proposed fix is class-scoped in `design.md`'s `## Proposed fix` section. The gate loops until all seven pass; the Phase B4 Generalization Audit (which catches symptom-patches rigorously) runs next. Phase B3 no longer delegates to Phase 1; a dedicated test file (`tests/test_bug_fix_validation_gate.py`, 15 cases) asserts each condition's presence + the absence of the prior Phase 1 delegation language + the "Why not reuse Phase 1?" rationale block. |
| ▸ **MemPalace wake-up runs at the earliest phase, before any subagent dispatch (v0.9.24)** | A v0.9.23 cohesion-review finding: the main pipeline's prior "Phase −1 Prelude — MemPalace wake-up" section said *"REQUIRED, before any subagent dispatch,"* but v0.9.22's Phase −2 (Triage & Routing) had been placed ABOVE it and dispatched the `bug-classifier` subagent first. The invariant + the section ordering directly contradicted. v0.9.24 promotes the MemPalace wake-up to a precondition section (un-numbered, NOT labeled as a phase) that precedes BOTH pipelines' earliest phase — `architect-team-pipeline` Phase −2 AND `bug-fix-pipeline` Phase B−1. The wake-up runs first regardless of entry path (`/architect-team`, `/architect-team:bug-fix`, or any future sibling pipeline); the `bug-classifier`'s past-triage-verdict calibration via `--room triage-verdicts` works correctly because the unscoped wake-up has populated context first. A second wing-scoped wake-up still runs from inside Phase −1A once the wing name is discovered, unchanged. Four new structural tests assert the ordering invariant — `test_mempalace_wakeup_precedes_phase_2`, `test_mempalace_wakeup_section_states_invariant`, `test_bug_fix_pipeline_has_mempalace_wakeup_section`, plus the updated `test_phase_2_precedes_phase_1` that confirms the old `## Phase −1 Prelude` header is gone. |
| ▸ **Automatic documentation currency via a dedicated `doc-updater` agent (v0.9.23)** | The v0.9.15 Phase 8 documentation-currency gate did the right discipline — sweep, audit, block-the-commit-on-fail — but the *update* step was a sentence in the skill that said "the orchestrator performs the updates." That cracked at end-of-context on big diffs (a 30-file v0.9.22-shaped ship has a 22-step doc checklist the orchestrator routinely lost items in) and at end-of-attention on small ones (bug-fix loops inherit the language by reference). v0.9.23 promotes the update step to a dedicated **`doc-updater`** agent (opus, bounded `Write` ONLY to the documentation-currency inventory — README / CHANGELOG / CLAUDE.md / AGENTS.md / CODEBASE_MAP / INTEGRATION_MAP / ROUTE_MAP / DESIGN_MAP / INTERACTION_INTUITION_MAP — and explicitly **NO `Edit`**, **NO source-code writes**, **NO `plugin.json`/`marketplace.json` writes**). The agent reads the run's `git diff` against the merge base + the coverage map + the run ledger + the current state of every inventory doc, identifies every stale section with a triggering `justification` citing a specific diff entry, and edits each in place via **whole-file rewrites** (Edit is excluded by design — partial-update inconsistency where one count gets bumped but a related count doesn't is the failure mode this prevents). Output: a structured report at `.architect-team/documentation-currency/updates-<ts>.json` enumerating every file touched + every section updated with its justification. The existing `system-architect` **Documentation Currency Audit** mode (unchanged from v0.9.15) independently re-verifies; the **audit's verdict** — not the agent's self-report — is what gates the commit (producer/checker discipline, per v0.9.13). **Wired into BOTH pipelines**: the main `architect-team-pipeline` Phase 8 step 1 dispatches `doc-updater` (replacing "orchestrator performs the updates"); the `bug-fix-pipeline` Phase B8 dispatches the same agent with the same audit and the same enforcement. Bug fixes are not exempt from doc currency; small diffs walk the inventory cheaply, produce an empty `updates: []` report, and exit. The user never has to ask for a doc sweep again. |
| ▸ **Bug-fix pipeline — replicate, propose, fix, QA-replay against live dev (v0.9.22)** | The main `architect-team-pipeline` is optimized for greenfield features; for a known-bug-with-a-clear-symptom — *"the row-action menu's Delete button doesn't actually delete; clicking it just closes the menu"* — its 100%-coverage planning gate, parallel team spawn, six Phase 5 review teams, and master-review audit are weight a 30-line fix doesn't need. v0.9.22 ships a sibling **`bug-fix-pipeline`** skill + **`/architect-team:bug-fix`** command with five non-negotiable disciplines: **replicate first** (Playwright user-flow for frontend bugs, backend script for backend bugs, ambiguity-escalation question for unclear bugs — *"How did you experience the bug? What did you click? What did you expect vs. what actually happened?"*); **reproduction IS the regression test** (frontend bugs ALSO author a backend diagnostic so the regression is covered on both layers); **generalize, never symptom-patch** (the new `system-architect` **Bug-Fix Generalization Audit** mode rejects fixes that special-case the failing input — a literal user-id in a conditional, a hard-coded category — unless the user explicitly authorized a hotfix with words like *"hard-code it for now"*); **QA replay against live dev** (the new **`qa-replayer`** agent re-runs the reproduction artifacts verbatim against the deployed dev fix and the pass criterion is "the originating symptom is gone end-to-end," not "the test passes"); **live-dev-environment-by-default** (Phase B5 ALWAYS deploys to the dev environment first; production is an opt-in exception that escalates). Phases B−1 → B8 mirror the main pipeline's structural points (intake-and-mapping reuse, OpenSpec proposal, doc-currency gate, default-branch guard) and replace Phase 2-5 with a tight replicate → reproduce-test → propose → fix → QA-replay loop bounded at 10 local iterations. **Auto-routing at the main `/architect-team`** — a new Phase −2 triage step dispatches the new **`bug-classifier`** agent (sonnet, analysis-only) to classify the incoming requirement as `bug` / `feature` / `mixed` / `unclear`; pure-bug routes to the bug-fix pipeline, pure-feature continues to the existing flow, `mixed` spawns BOTH in parallel (a `triage_done` flag bounds the recursion at depth 1), `unclear` emits a structured question to the user. New `--bug-fix` and `--feature-only` flags on `/architect-team` force the classifier verdict. Both the bug-fix command and the bug-fix-pipeline skill accept the SAME two input forms as the main `/architect-team` — folder OR plain-language prose — with the v0.9.17 anti-pattern forbidance (never refuse prose, never path-treat the first word) applied verbatim. |
| ▸ **Interaction intuition at Phase −1 — every control mapped before code is written (v0.9.21)** | The Phase 5 `interaction-completeness` team catches drift against a *built, running* app — by then the proposal is months old and a wiring gap costs a full cycle. v0.9.21 lifts that same rigor into discovery: for every frontend codebase in scope, a new **`interaction-intuiter`** agent (per-codebase, opus, analysis-only) cross-walks `ROUTE_MAP.md` × `DESIGN_MAP.md` × `INTEGRATION_MAP.md` and produces a per-codebase **`INTERACTION_INTUITION_MAP.md`** carrying, for every interactive element on every designed screen, an intuited action in user-effect terms, candidate endpoints with `match_kind` (exact-by-label / exact-by-action-noun / plausible-by-design-intent / inferred-from-similar-route), explicit confidence (`high` / `medium` / `low` / `unknown`), citation evidence, and — for everything below `high` — a precise ambiguity question that names the concrete candidates and the user-visible behavioral difference between them. Then a new **Phase −1D bulk-verify gate** fires before Phase 0: every `low`/`unknown` (and any flagged `medium`) is presented to the user as a **single numbered list**, the user replies in one of three formats (`all correct` / a list of incorrect indices / `all incorrect`), and a targeted drill-down resolves only the flagged items — `AskUserQuestion` batched 4-per-message when the candidate set fits, free-form otherwise. Items the user did NOT flag are auto-`confirmed`. The `confirmed: true` map is then a **binding input** to Phase 0 spec authoring (the proposal must reflect every confirmed action→endpoint triple verbatim; `superseded_by: REQ-XXX` is the only override) and Phase 1 (every confirmed wiring becomes an acceptance criterion). The gate is a **domain gate** (the user-confirmation step IS the deliverable), so it fires regardless of `--proposal-first` — the pipeline skill's `## Default mode of operation` carve-out makes this distinction explicit alongside the v0.9.20 gates-opt-in rule for process gates. |
| ▸ **Gates are opt-in — orchestrator drives end-to-end (v0.9.20)** | A user-reported defect: the pipeline kept asking obvious clarifying questions ("How should I fix this bug?") when the answer was obviously "fix it properly". v0.9.20 embeds the rule as a non-negotiable in the pipeline skill — drive Phases −1 → 8 to completion, pick sensible defaults, state the pick in one line, proceed. **Process gates** (proposal-first pause, "do you want me to proceed?", clarifying `AskUserQuestion` calls whose answer is obvious) engage ONLY when the user explicitly requests one ("propose first" / "review before implementing" / `--proposal-first`) or a genuinely material fork exists where the answer is not obvious. A new opt-in `--proposal-first` flag formalizes the explicit request channel (with natural-language phrasings). An obvious clarifying question is itself a defect; catch it before sending. Bugs and clear-fix scenarios get fixed at the right scale (small edit / focused commit / full pipeline) — sized by the work, not by asking. |
| ▸ **UI interaction fidelity — every control genuinely tested, every page live (v0.9.19)** | The pipeline kept shipping frontend work that was not what it claimed to be — a Playwright "user-flow" test passing without ever driving the UI (a direct `page.request.*` call, or a vacuous navigate-and-assert), a route wired to a **placeholder** / "coming soon" / mock page in place of the real live page, a hardcoded `"John Smith"` rendered for every user where a dynamic value belongs. v0.9.19 makes "every interactive element is genuinely user-flow-tested, every page is the real live page, and every displayed value is correctly static or dynamically bound — or an explicit user-confirmed stub" a **structural, hook-enforced gate**. A new judgment-heavy verification team — the **`interaction-completeness`** skill + the **`interaction-reviewer`** agent (×3, opus, analysis-only, modeled on `editability-completeness`) — independently re-enumerates every interactive element AND every page, classifies element wiring and page genuineness, audits each Playwright test for genuine user-driven interaction, and traces every element to its endpoint. A first-class **confirmed-stub mechanism** gives an intentionally-inert control or placeholder page a durable, user-confirmed status (escalate-don't-guess); an unconfirmed one is a gap. A new hook-enforced **`ui_interaction_review`** evidence field (schema v5 → **v6**) gates the axis — `pass` / `n/a` / `fail`. A new **`dynamic-value-discovery`** skill — a cross-role discipline wired into the developer, architect, and evaluator — distinguishes a genuine static literal from sample data standing in for a dynamic, data-bound value, classifying every displayed value FROM CONTEXT and binding every dynamic one. The `test-completeness-verifier` is strengthened to flag a vacuous "flow" test and cross-check the interactivity inventory. |
| ▸ **Project email notifications (v0.9.18)** | A pipeline run is a long, mostly-unattended sequence of phases — until now nobody could follow along without watching the terminal. v0.9.18 adds an **opt-in, per-project email-notification system**. A project drops a committed `.architect-team-notify.json` at its repo root naming the email provider (**Gmail** SMTP or **SendGrid** API), the sender identity, the env-var that holds the provider secret, and a recipient list — each recipient subscribing to whichever of the **five event types** they want: `phase_start`, `phase_complete`, `issue_discovered` (a new solution requirement), `git_commit`, and `deploy` (a live dev instance brought up). The notifier (`scripts/notify/notify.py`, **standard library only** — `smtplib` / `urllib`, zero new dependencies) is a CLI the orchestrator invokes at those five moments. It is strictly **best-effort**: every failure path — missing config, missing secret, provider / network error — exits 0, so a notification failure can never block, fail, or alter a run. Provider secrets are read only from the named environment variable, never committed, never logged. With no `.architect-team-notify.json` present the notifier is a silent no-op. |
| ▸ **Plain-language requirements are first-class (v0.9.17)** | `/architect-team` takes a requirement in **two forms** — a requirements folder OR a **plain-language requirement typed directly** (a sentence or paragraph describing what to build, fix, change, review, or improve). Phase 0 has always normalized plain-language input, but the command's argument parser was worded *"the first token is the requirements folder path"* — so a sentence's first word (`no`, `review`, `fix`) got mistaken for a path and models refused with *"I won't run against a non-existent folder."* v0.9.17 rewrites the command's argument parser and the skill's `Inputs` section: two clearly-labelled input forms, both first-class; refusing prose — or treating its first word as a path — is now explicitly forbidden; the pipeline asks for input only when the argument is genuinely empty. |
| ▸ **README visual designer — centering, color, themes (v0.9.16)** | The `readme-styling` skill gains a **canvas-width + centering model** (one width; every element built to it or centered within it — no more crooked, left-listing pages), **pipe-table and ASCII-graph alignment rules**, a **two-world color model** (GitHub-safe — themed badges + colored Mermaid diagrams — plus a separate ANSI-colored variant for terminals), and a **theming engine**: six preset themes (`midnight` / `phosphor` / `amber` / `synthwave` / `crimson` / `mono`), each a badge palette + accent + ANSI palette + Mermaid colors, chosen once via an interactive picker at first setup and recorded in a `<!-- architect-team:readme-theme=... -->` marker so a project's look stays consistent. This README is re-styled as the reference implementation. |
| ▸ **Documentation-currency gate (v0.9.15)** | The pipeline shipped code but left documentation behind — `README.md` + `CHANGELOG.md` got updated, while the maps, `CLAUDE.md`, and `INTEGRATION_MAP.md` drifted. v0.9.15 adds a **Phase 8 documentation-currency gate** — the last step before the GitHub push. The orchestrator updates every doc the change affects (the maps `CODEBASE_MAP` / `ROUTE_MAP` / `DESIGN_MAP` / `INTEGRATION_MAP`, plus `README.md`, `CHANGELOG.md`, `CLAUDE.md`); then the `system-architect` **independently audits** them in a new *Documentation Currency Audit* mode — verifying, against the actual diff, that every doc that should have been updated *was*, and accurately, and that every map's freshness frontmatter is current. The audit verdict gates the commit; `pipeline-completion-audit.py` blocks a push on a stale-docs verdict. Producer/checker, per v0.9.13 — the orchestrator updates, an independent agent confirms. New `documentation-currency` skill. |
| ▸ **MemPalace `mine` syntax fix (v0.9.14)** | The pipeline auto-mines artifacts to MemPalace at many points, and every `mempalace ... mine` command the plugin documented carried a `--room <room>` argument. But `mempalace mine` (verified against mempalace 3.3.5) has **no `--room` flag** — rooms are auto-detected by `mempalace init` from the mined corpus's directory structure; `--room` is valid only on `mempalace search`. Every `mine ... --room` call errored with `unrecognized arguments` on its first attempt and succeeded only on a no-`--room` retry — a guaranteed-failed call per mine. v0.9.14 removes `--room` from every `mine` command across all skills and agents, reframes the `mempalace-integration` room taxonomy as documentation of how the `.architect-team/` + `openspec/` directory layout maps onto MemPalace's auto-detected rooms (not as `mine` flags), and adds a structural regression test so a `mine ... --room` form cannot silently return. |
| ▸ **Independent review — close the producer-is-own-checker gaps (v0.9.13)** | Most phases already have an independent checker (3 reviewers check the cartographer's map; the test-completeness-verifier checks a teammate's tests; the system-architect reviews diagnostic plans). Two phases were the exception — the producer checked its own work. **Phase 3:** the teammate wrote the code AND wrote its own `spec_review` / `quality_review` / `real_not_stubbed` / `reuse_compliance` — and the hook can only check the evidence file's *shape*, not whether its `"pass"` values are *true*. v0.9.13 adds a read-only **`task-reviewer`** agent (opus, no `Edit`) that independently reads the teammate's diff, re-runs the linters / tests, greps for stubs, checks the Reuse Decisions, and writes an `independent_review` block — and the hook now requires that block with `reviewer != teammate` and `verdict == "pass"`, so the gate **structurally cannot open on self-attestation**. **Phase 7:** the `system-architect` gains a *Master Review Audit* mode — after the orchestrator's own coverage-map walk, an independent system-architect re-verifies every coverage-map entry + every SR and writes a verdict that gates the Phase 8 commit (the `Stop` hook checks it). Evidence schema → v5. |
| ▸ **Visual verification team — capture / analyze / synthesize (v0.9.12)** | The v0.9.11 single verifier did capture + analysis + verdict in one agent — which means it can still cut a corner *inside itself*. v0.9.12 decomposes it into three roles with a hard artifact boundary between them: **`visual-capture`** agents (×N) start the live app and produce countable artifacts — screenshots + computed-style **data** for every screen; **`visual-analyzer`** agents do the **objective structural analysis** — a deterministic data diff (not an agent eyeballing two images), a pixel diff vs the design reference, a code cross-check; the **`system-architect`** synthesizes the per-screen gaps **holistically**, clustering twelve isolated drifts into one root cause. Analysis cannot start before the capture artifacts exist on disk; synthesis confirms `screens_captured == screens_analyzed == design_map_screen_count`. The boundaries between the roles are the anti-cheat — no one role can cut a step invisibly. |
| ▸ **Live-app visual verification — the `visual-fidelity-verifier` (v0.9.11)** | The UX agents were not actually comparing designs against the **live running app** — they reasoned about styles from the code, wrote "perfect", cut steps, then apologized. A skill an agent can rationalize past is not enough. v0.9.11 adds an **independent `visual-fidelity-verifier` agent** (opus, read-only) whose entire job is to start the real app and render EVERY `DESIGN_MAP.md` screen itself, measure the real DOM, and compare against the Oracle AND the reconciliation report — catching a `report-fabricated` "perfect" the live app contradicts and a `report-incomplete` skipped screen. It cannot cut the step because rendering-the-live-app IS the job. `visual-fidelity-reconciliation` gains a hard **Phase 0 live-app precondition** (no live app → escalate `blocked`, never substitute static analysis) and a no-cutting-steps / no-apologies discipline. The verifier's verdict — not the self-report — gates Phase 5, and the `Stop` hook blocks a run whose reconciliation was never verified against the live app. |
| ▸ **Design-baseline-migration awareness (v0.9.10)** | A reported failure: during a Full→V2 design migration, agents skipped reconciling screens that a prior Phase −1B design-recon had classified `UNCHANGED` — so several role-landing-page `h1`s shipped at the old sizes/weights. Root cause: a **classification** ("what changed") was trusted as a **verdict** ("design-compliant"). v0.9.10 adds a 4th visual-fidelity discipline — *verify against the Oracle, never against a classification* — plus a Phase A.0 design-baseline check. The key reasoning fix: during a baseline migration, "unchanged" **inverts** — an implementation that has not been migrated is drifted *by definition*, so "unchanged" is a guaranteed-drift signal, never a skip. `DESIGN_MAP.md` gains a `design_baseline` field; a baseline change forces a full re-derive of every screen, and a Phase 5 / on-demand sweep must reconcile every screen (`screens_reconciled_count == design_map_screen_count`). |
| ▸ **Logic-implementation review fixes (v0.9.9)** | A critical review of the pipeline's logic surfaced real holes; v0.9.9 closes all three tiers. The two evidence hooks had **drifted** (`teammate-idle-check` validated 8 fields, `review-gate-task` validated 11) — they now import one shared `review_evidence_schema` module, so drift is structurally impossible. A new **`Stop` hook** (`pipeline-completion-audit`) blocks the orchestrator from ending a run that is still incomplete — open SRs, a test-failure SR with no diagnostic plan, an unsatisfied editability loop, a test-completeness debt, a blown iteration ceiling — and gates the Phase 8 auto-commit. The editability team gained an independent `system-architect` **robustness review** (Round 3). Plus: a global iteration ceiling + oscillation detection, a documented shared-state concurrency model, map re-validation when a map is found wrong, and a default-branch push guard (`--allow-push-to-default`). See Logic Map C. |
| ▸ **README styling skill (v0.9.8)** | New `readme-styling` reference skill codifies the bitmap house style — block-letter banner, gradient dividers, box-drawing panels, ASCII flowcharts, **logic maps that show routing + gates**, status timeline, colored badges — so every README an agent authors carries the same flair. This README is its reference implementation. |
| ▸ **Editability completeness (v0.9.7)** | New `editability-completeness` skill + `editability-reviewer` agent (×3, opus). Confirms every attribute an entity exposes that a user should control is actually editable end-to-end — UI control → state → API → request schema → handler → database → read-back. Catches the case where a `title` displays but has no field to set it. Three reviewers argue to a converged gap list; gaps → SRs; multi-pass until satisfied. `/architect-team:editability-audit` for on-demand audits. |
| ▸ **Expensive-verification debugging (v0.9.6)** | New `expensive-verification-debugging` skill. When a fix is verified by a slow loop (deploy / rebuild / slow CI), audit the whole failure pathway statically, batch every fix, spend the expensive cycle once — instead of one-fix-per-deploy whack-a-mole. |
| ▸ **Real backend by default (v0.9.5)** | Full-stack (`both`-layer) features MUST integration-test against the real running backend — no `page.route` happy-path stubs, no MSW, no fake API server. Hook-enforced `integration_testing_review` evidence field. |
| ▸ **MemPalace integration (v0.9.4)** | Every artifact the pipeline produces (maps, RCAs, diagnostic plans, SRs, coverage maps, final reports) is auto-mined into a local-first searchable memory at `<workspace>/.mempalace/palace`. Named agents query prior context before producing output. `/architect-team:mempalace-install` + `/architect-team:memory`. |
| ▸ **Diagnostic research team (v0.9.3)** | Every test-failure SR routes through three parallel `diagnostic-researcher` agents that map the full code flow + theorize ranked hypotheses; the system-architect reviews robustness; only an approved consolidated plan unlocks the fix team. |
| ▸ **No arbitrary timers (v0.9.2)** | The pipeline never schedules wall-clock wakeups / cron / background timers — it runs synchronously; subagent dispatch is the only wait. |
| ▸ **Auto-compact prompt (v0.9.1)** | At the end of a clean pipeline / visual-qa run, a clearly-marked `/compact` prompt frees context for the next run. Opt out with `--no-compact`. |

```
░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
█▓▒░  ◆  WHAT YOU GET  ◆  ░▒▓█
░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
```

```
┌─ SKILLS (23) ───────────────────────┬─ AGENTS (25) ─────────────────────────┐
│ ◇ architect-team-pipeline           │ ◆ system-architect (opus)             │
│ ◇ intake-and-mapping                │ ◆ frontend (opus)                     │
│ ◇ reuse-first-design                │ ◆ backend (opus)                      │
│ ◇ frontend-route-mapping            │ ◆ reconciler (opus)                   │
│ ◇ design-fidelity-mapping          *│ ◆ integration (sonnet)                │
│ ◇ visual-fidelity-reconciliation   *│ ◆ scaffold-agent (sonnet)             │
│ ◇ playwright-user-flows             │ ◆ codebase-map-reviewer (sonnet)      │
│ ◇ dev-api-integration-testing       │ ◆ integration-explorer (opus)         │
│ ◇ coverage-mapping                  │ ◆ master-synthesizer (opus)           │
│ ◇ team-spawning-and-review-gates    │ ◆ route-mapper (opus)                 │
│ ◇ root-cause-test-failures          │ ◆ test-completeness-verifier (sonnet) │
│ ◇ diagnostic-research-team          │ ◆ diagnostic-researcher (opus)        │
│ ◇ mempalace-integration             │ ◆ editability-reviewer (opus)         │
│ ◇ expensive-verification-debugging  │ ◆ visual-capture (sonnet)             │
│ ◇ editability-completeness          │ ◆ visual-analyzer (opus)              │
│ ◇ readme-styling                    │ ◆ task-reviewer (opus)                │
│ ◇ visual-verification-team          │ ◆ interaction-reviewer (opus)         │
│ ◇ documentation-currency            │ ◆ bug-replicator (opus)               │
│ ◇ interaction-completeness          │ ◆ qa-replayer (opus)                  │
│ ◇ dynamic-value-discovery           │ ◆ bug-classifier (sonnet)             │
│ ◇ interaction-intuition             │ ◆ interaction-intuiter (opus)         │
│ ◇ bug-fix-pipeline                  │ ◆ doc-updater (opus)                  │
│ ◇ ux-test-builder                   │ ◆ flow-explorer (opus)                │
│                                     │ ◆ flow-executor (opus)                │
│                                     │ ◆ fix-sensibility-checker (opus)      │
├─ COMMANDS (8) ──────────────────────┴───────────────────────────────────────┤
│ ▸ /architect-team <path-to-requirements-folder>                             │
│ ▸ /architect-team-setup                                                     │
│ ▸ /architect-team:visual-qa [<codebase-path>]                               │
│ ▸ /architect-team:mempalace-install                                         │
│ ▸ /architect-team:memory <search|mine|status|wake-up|sweep>                 │
│ ▸ /architect-team:editability-audit [<codebase-path>]                       │
│ ▸ /architect-team:bug-fix <bug-description | requirements-folder>           │
│ ▸ /architect-team:ux-test <persona + objectives + --site or --dev>          │
├─ HOOKS (3) ─────────────────────────────────────────────────────────────────┤
│ ▸ PostToolUse(TaskUpdate)   review-gate evidence — v6 + independent review  │
│ ▸ SubagentStop              teammate-idle review-gate re-check              │
│ ▸ Stop                      pipeline-completion audit (terminal gate)       │
├─ SETUP ─────────────────────────────────────────────────────────────────────┤
│ ▸ scripts/setup/setup.py             openspec CLI, pytest+httpx, Playwright │
│ ▸ scripts/setup/install_mempalace.py MemPalace CLI + MCP server (uv-first)  │
└─────────────────────────────────────────────────────────────────────────────┘

      * = activates only when design inputs exist (screenshots / Figma /
          tokens / Storybook / brand docs / assets directory)
```

```
░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
█▓▒░  ◆  INSTALL  ◆  ░▒▓█
░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
```

### ▸ Prerequisites (must be on your machine)

| Requirement | Where to get it |
|---|---|
| **Python 3.10+** as `python3` on `$PATH` | Ubuntu/Debian: `sudo apt install python-is-python3` · macOS: `brew install python` · Windows: re-run the [python.org installer](https://www.python.org/downloads/) with "Add to PATH" checked, or use `py -3` |
| **Node ≥ 20.19** (npm) | [nodejs.org](https://nodejs.org/) or your package manager |
| **Claude Code** | [docs.anthropic.com/claude-code](https://docs.anthropic.com/claude-code) |

### ▸ Install the plugin

```bash
# 1. Register this repo as a marketplace
/plugin marketplace add <git-url-of-this-repo>

# 2. Install the plugin
/plugin install architect-team@architect-team-marketplace
```

### ▸ Install prerequisite Claude plugins (one-time)

```bash
/plugin install superpowers@claude-plugins-official
/plugin install cartographer@cartographer-marketplace
/plugin install ralph-loop@claude-plugins-official
```

### ▸ Install CLI / Python / browser deps

```bash
/architect-team-setup
```

Idempotent. Flags: `--check-only` (report only), `--force-reinstall` (reinstall everything managed).

### ▸ Install MemPalace (optional — enables searchable cross-run memory)

```bash
/architect-team:mempalace-install
```

Installs the MemPalace CLI (uv-first, pip fallback) and prints the `claude mcp add` + per-workspace `mempalace init` commands for you to run. The pipeline degrades gracefully without it — every wake-up / mine / search is skipped with a one-line note.

### ▸ Updating other instances

```bash
/plugin marketplace update architect-team-marketplace
/plugin update architect-team@architect-team-marketplace
/reload-plugins
```

```
░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
█▓▒░  ◆  USAGE  ◆  ░▒▓█
░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
```

```bash
/architect-team <path-to-requirements-folder> [--no-commit] [--no-push] [--no-compact]
```

The requirements folder may contain OpenSpec artifacts (`proposal.md`, `specs/`, `design.md`, `tasks.md`), a Superpowers-formatted brief, or plain markdown. The orchestrator detects and normalizes.

**Default: auto-commit + push on clean pass.** At the end of a successful Phase 8, the pipeline stages its working set, commits with a structured message including the requirements implemented + tests added + archive path, and pushes to the current branch's upstream. To opt out per invocation: pass `--no-commit` (skip both), `--no-push` (commit locally only), or `--no-compact` (suppress the end-of-run `/compact` prompt). Natural-language opt-outs ("don't commit", "no push") are honored.

### The pipeline at a glance

```
       ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
       │   PHASE −1      │    │   PHASE 0–1     │    │    PHASE 2      │
       │  Intake & Map   │───▶│  Detect & Plan  │───▶│  Team Spawn     │
       │  · CODEBASE_MAP │    │  · openspec     │    │  · parallel     │
       │  · ROUTE_MAP    │    │  · coverage-map │    │  · non-overlap  │
       │  · DESIGN_MAP * │    │  · reuse-first  │    │  · plan-approval│
       │  · INTEGR_MAP   │    │  100% gate      │    │    triggers     │
       └─────────────────┘    └─────────────────┘    └────────┬────────┘
            3-reviewer            12 conditions               │
            ralph loop            hard gate                   ▼
                                                     ┌─────────────────┐
                                                     │    PHASE 3      │
                                                     │  Review Gate    │
       ┌─────────────────┐    ┌─────────────────┐    │  · hook-enforced│
       │   PHASE 5       │    │   PHASE 4       │    │  · 12 fields    │
       │  Integration    │◀───│  Reconciliation │◀───│  · visual-fid   │
       │  · real backend │    │  · shared bounds│    │  · ui-interactn │
       │  · playwright   │    │  · contract sync│    │  · RCA on fail  │
       │  · visual-fid   │    │  · no feature   │    │  · auto-spawn   │
       │  · ui-interactn │    │    code         │    │    SR on issue  │
       └────────┬────────┘    └─────────────────┘    └─────────────────┘
                │
                ▼
       ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
       │   PHASE 6       │    │   PHASE 7       │    │   PHASE 8       │
       │  Outer Loop     │───▶│  Master Review  │───▶│  Final Report   │
       │  · per-task-grp │    │  · coverage map │    │  · per req →    │
       │  · dep graph    │    │    fully green  │    │    commit →     │
       │  · ledger       │    │  · re-spawn on  │    │    test → demo  │
       │                 │    │    gap          │    │  · openspec     │
       │                 │    │                 │    │    archive      │
       └─────────────────┘    └─────────────────┘    └─────────────────┘

       * DESIGN_MAP only when design inputs exist
```

```
░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
█▓▒░  ◆  LOGIC MAPS — ROUTING & GATES  ◆  ░▒▓█
░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
```

The flowchart above shows *what happens next*. These two logic maps show *how flow is decided* — the decision points (`◆`), the gates (`▣`), the verdicts (`✓` allow / `✗` block), and the route-back edges (`◀┄┄`).

### ▌ Logic Map A — the Phase 3 review gate

Every `TaskUpdate(completed)` on a teammate-owned task is gated; the hook exits 2 (block) until the evidence is complete.

```
   teammate calls  TaskUpdate(status = completed)
            │
            ▼
   ◆ is task_id owned by a teammate?          (listed in some manifest's
        │                    │                 expected_review_evidence)
      no│                    │ yes
        ▼                    ▼
   ✓ exit 0             ▣ REVIEW GATE  —  hooks/review-gate-task.py
   not an architect-    reads  .architect-team/reviews/<task_id>.json
   team task; ignored             │
                                  ▼
        ◆ evidence present · valid JSON · all 12 self-review fields valid?
            · spec_review = quality_review = "pass"
            · real_not_stubbed = true · tests added ≥ 1 and == passing
            · reuse_compliance = "ok" · demo_artifact + files_changed non-empty
            · visual_fidelity / test_completeness / integration_testing /
              ui_interaction reviews ≠ "fail"
            · independent_review present · reviewer ≠ teammate ·
              verdict = "pass"   (written by the task-reviewer agent)
            │                                       │
         no │                                       │ yes
            ▼                                       ▼
   ✗ exit 2  —  BLOCK                       ✓ exit 0  —  ALLOW
   stderr names the exact gap               task is marked completed
            ┊
            └┄┄▶ teammate fixes the gap and retries;
                 3 consecutive rejections ⇒ escalation handoff
```

### ▌ Logic Map B — issue → fix routing (Solution Requirements)

Every surfaced issue becomes an SR; test-failure origins route through diagnostic research first, editability + interaction gaps go straight to a fix team; the loop closes when the originating check passes.

```
   an issue surfaces  (failed test · visual drift · editability /
            │           interaction gap — unwired control, placeholder
            │           page, hardcoded dynamic value)
            ▼   the discovering agent writes a Solution Requirement (SR)
   ◆ route by  SR.origin.kind
        │
        ├─ test-failure origin ───────────────────▶ ▣ DIAGNOSTIC RESEARCH
        │  rca-product-bug · playwright-failure ·    3 diagnostic-researcher
        │  integration-failure · integration-        agents argue in parallel
        │  testing-failure · test-completeness-      → system-architect reviews
        │  failure · visual-fidelity-cascade         robustness → consolidated
        │                                            diagnostic plan
        │                                                     │
        └─ editability-gap / unwired-control / ───┐            │
           placeholder-page / hardcoded-          │            │
           dynamic-value — the converged map      │            │
           is already the full diagnosis,         │            │
           research is skipped                    │            │
                                                  ▼            ▼
                                       ▣ FIX TEAM  —  spawned in Phase 2,
                                       runs the Phase 2 → 3 → 4 → 5 loop
                                                     │
                                                     ▼
                            ◆ does the originating test / check pass?
                                 │                              │
                              no │                              │ yes
                                 ▼                              ▼
                  ◀┄┄ re-enter the dev loop            ✓ SR → "resolved";
                      (Phase 3 for the slice)             the originating
                                                          teammate unblocks
```

### ▌ Logic Map C — the completion audit (Stop hook)

The orchestrator runs as the main session — no hook can gate its mid-run behaviour, but the `Stop` hook gates its **terminal** state: it blocks the orchestrator from ending a run, or auto-committing, while the run is still incomplete.

```
   orchestrator session ends ──▶ ▣ Stop HOOK · pipeline-completion-audit.py
            │
            ▼
   ◆ does .architect-team/ hold an INCOMPLETE run?
     · an open / in-progress solution requirement
     · a test-failure SR with no diagnostic plan
     · an unsatisfied editability loop   · a test-completeness debt
     · a master-review audit verdict that is not overall: pass
     · the dev-loop iteration ceiling (20) exceeded
        │                                              │
      no│  (clean — or not an architect-team run)      │ yes
        ▼                                              ▼
   ✓ exit 0 — ALLOW the stop          ◆ is .architect-team/escalation-pending.md present?
                                          │                              │
                                      yes │  (legitimately                │ no
                                          ▼   paused for a human)         ▼
                                 ✓ exit 0 — ALLOW             ✗ exit 2 — BLOCK
                                                              resolve the gaps, OR write the
                                                              escalation marker, then stop again
```

The same audit runs as `pipeline-completion-audit.py --check` before the Phase 8 auto-commit — so "clean pass" is a checked fact, not the orchestrator's self-assessment.

```
░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
█▓▒░  ◆  THE LOOPS & ACCEPTANCE CRITERIA  ◆  ░▒▓█
░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
```

The pipeline is a stack of nested loops, each with explicit exit criteria. Listed in execution order; the README enumerates only the contract — skill files are the source of truth.

### ▌ Loop 1 — Per-codebase mapping (Phase −1B)

- **Wrapper:** `/ralph-loop "<review prompt>" --completion-promise "CODEBASE MAP COMPLETE" --max-iterations 10`. One ralph loop per discovered codebase.
- **Mechanism:** Cartographer (and `route-mapper` for frontends) produces `<codebase>/docs/CODEBASE_MAP.md` (and `ROUTE_MAP.md` + `DESIGN_MAP.md` if design inputs exist). Then 3 `codebase-map-reviewer` agents are spawned **in parallel**. Each returns `{ "status": "ok" | "deficient", "deficiencies": [...] }`.
- **Iteration body** (if any reviewer returns `deficient`): aggregate + dedupe deficiencies; re-trigger cartographer / route-mapper in update mode; loop.
- **Exit criteria — all of:** all 3 reviewers return `status: "ok"` in the same iteration; the orchestrator emits `CODEBASE MAP COMPLETE`.
- **Freshness short-circuit:** `last_mapped` frontmatter ≥ `git log -1 --format=%cI` ⇒ codebase marked `CURRENT`, loop skipped.
- **Iteration cap:** 10.
- **References:** [`skills/intake-and-mapping/SKILL.md`](skills/intake-and-mapping/SKILL.md), [`agents/codebase-map-reviewer.md`](agents/codebase-map-reviewer.md), [`agents/route-mapper.md`](agents/route-mapper.md).

### ▌ Loop 2 — Integration mapping (Phase −1C)

- **Wrapper:** `/ralph-loop "<synthesis prompt>" --completion-promise "INTEGRATION MAP COMPLETE" --max-iterations 8`. One ralph loop for all codebases.
- **Mechanism — sequential sub-loops:** (2a) 3 `integration-explorer` agents in parallel, round-robin convergence; (2b) `master-synthesizer` writes `<workspace>/docs/INTEGRATION_MAP.md`; (2c) confirmation pass — each explorer confirms the master doc.
- **Exit criteria — all of:** all 3 explorers confirm; INTEGRATION_MAP.md exists with frontmatter + 6 sections; master-synthesizer emits `INTEGRATION MAP COMPLETE`.
- **Iteration cap:** 8.
- **References:** [`skills/intake-and-mapping/SKILL.md`](skills/intake-and-mapping/SKILL.md), [`agents/integration-explorer.md`](agents/integration-explorer.md), [`agents/master-synthesizer.md`](agents/master-synthesizer.md).

### ▌ Loop 3 — Planning validation (Phase 1, hard gate)

- **Wrapper:** Orchestrator-internal. 100% coverage required; no iteration cap — Phase 2 cannot start until exit.
- **Mechanism per iteration:** `openspec validate --all --strict --json` + `openspec status --json` + refresh `coverage-map.json`, then evaluate the 12-condition exit checklist.
- **Exit criteria — every one must hold:**
  1. `openspec validate` returns `valid: true` with no errors.
  2. Every artifact (`proposal`, `specs`, `design`, `tasks`) has `status: done`.
  3. Every source requirement has ≥ 1 scenario.
  4. Every requirement's acceptance criteria are measurable.
  5. Every front-end requirement has an explicit Playwright user-flow spec.
  6. Every back-end requirement has explicit dev-API integration test criteria.
  7. **Every `both`-layer requirement has an explicit front-to-back integration criterion** (real-backend testing) — or a recorded `mock_testing_authorized` opt-out.
  8. Every new module / file / dependency in `design.md` has a Reuse Decision citing CODEBASE_MAP.md.
  9. Every Reuse Decision cites a file/symbol that **actually exists** in CODEBASE_MAP.md.
  10. No duplicate capabilities (cross-checked via CODEBASE_MAP / INTEGRATION_MAP).
  11. Every new third-party dep has a documented comparison against the existing stack.
  12. `tasks.md` creates a new file only where existing files cannot be extended.
- **References:** [`skills/architect-team-pipeline/SKILL.md`](skills/architect-team-pipeline/SKILL.md), [`skills/coverage-mapping/SKILL.md`](skills/coverage-mapping/SKILL.md), [`skills/reuse-first-design/SKILL.md`](skills/reuse-first-design/SKILL.md).

### ▌ Loop 3b — Solution-Requirement intake (continuous; runs after every subagent idle)

- **Mechanism:** orchestrator walks `<cwd>/.architect-team/solution-requirements/*.json`. For each `open` SR: validates schema; auto-mines it to MemPalace; updates the coverage-map. **Test-failure-origin SRs** (`rca-product-bug`, `playwright-failure`, `integration-failure`, `integration-testing-failure`, `test-completeness-failure`, `visual-fidelity-cascade`) route through `diagnostic-research-team` (Logic Map B) **before** the fix team spawns. `editability-gap` SRs spawn a fix team directly. The fix team's brief carries `acceptance_criteria` verbatim + (for test-failure SRs) the consolidated diagnostic plan.
- **Exit criteria** (per SR): originating failing test passes; acceptance criteria reflected in passing tests; SR → `resolved`; originating teammate unblocks.
- **References:** [`skills/team-spawning-and-review-gates/SKILL.md`](skills/team-spawning-and-review-gates/SKILL.md) §`Solution Requirements`, [`skills/diagnostic-research-team/SKILL.md`](skills/diagnostic-research-team/SKILL.md).

### ▌ Loop 4 — Per-task review gate (Phase 3, hook-enforced)

- **Enforcement layer:** `PostToolUse(TaskUpdate)` → [`hooks/review-gate-task.py`](hooks/review-gate-task.py) + `SubagentStop` → [`hooks/teammate-idle-check.py`](hooks/teammate-idle-check.py). See Logic Map A.
- **Mechanism:** teammate writes its self-review into `<cwd>/.architect-team/reviews/<task-id>.json` (evidence schema v6) BEFORE any `TaskUpdate(status=completed)`; an independent `task-reviewer` agent then reads the diff and writes the `independent_review` block. Exit 0 = allow, exit 2 = block.
- **Acceptance criteria — 12 self-review fields + the `independent_review` block:**

  | Field | Required value |
  |---|---|
  | `task_id` | non-empty, `_safe_id()`-validated |
  | `spec_review` | `"pass"` |
  | `quality_review` | `"pass"` |
  | `real_not_stubbed` | `true` |
  | `tests` | `{ added: int ≥ 1, passing: int == added }` |
  | `demo_artifact` | non-empty string |
  | `files_changed` | non-empty array |
  | `reuse_compliance` | `"ok"` |
  | `visual_fidelity_review` | `"pass"` / `"n/a"` (+ non-empty `_note`) — `"fail"` blocks |
  | `test_completeness_review` | `"pass"` / `"n/a"` (+ non-empty `_note`) — `"fail"` blocks |
  | `integration_testing_review` | `"pass"` / `"n/a"` (+ non-empty `_note`) — `"fail"` blocks |
  | `ui_interaction_review` | `"pass"` / `"n/a"` (+ non-empty `_note`) — `"fail"` blocks (v6 — every interactive element genuinely user-flow-tested, every page live, every value correctly static/dynamic, or a confirmed stub) |
  | `independent_review` | object — `reviewer` (≠ `teammate`), `verdict` = `"pass"`, `spec_review` / `quality_review` = `"pass"`, `real_not_stubbed` = `true`, `reuse_compliance` = `"ok"`, `reviewed_at` non-empty. Written by the `task-reviewer` agent — the gate cannot open on the teammate's self-review alone. |

- **Escalation policy:** after 3 consecutive hook rejections on the same `task_id` → teammate stops retrying and writes a `<teammate>-to-orchestrator-stuck-<task_id>` handoff.
- **References:** [`skills/team-spawning-and-review-gates/SKILL.md`](skills/team-spawning-and-review-gates/SKILL.md), [`hooks/review-gate-task.py`](hooks/review-gate-task.py).

### ▌ Loop 4b — Per-test-failure root-cause analysis (Phase 3 & 5)

- **Trigger:** any Playwright or live dev-API test failure. Mandatory; no retry / patch / rationalize.
- **Pre-condition:** `<test-output-dir>/expectations/<test-id>.json` written BEFORE the test runs.
- **3-pass loop:** (1) forward data-flow trace; (2) backward call-flow trace; (3) alternative-hypotheses sweep — including the **multiple-simultaneous-causes** category (a symptom can have several independent root causes; finding one does not mean you found them all).
- **RCA artifact:** `<test-output-dir>/rca/<test-id>-<ts>.json`. `product-bug` → SR + handoff; **others** → fix in-loop.
- **Expensive verify loops:** when verifying a fix needs a deploy / rebuild / slow CI run, apply [`skills/expensive-verification-debugging/SKILL.md`](skills/expensive-verification-debugging/SKILL.md) — audit the whole failure pathway statically, batch every fix, spend the expensive cycle once; STOP and escalate after 2 cycles.
- **References:** [`skills/root-cause-test-failures/SKILL.md`](skills/root-cause-test-failures/SKILL.md).

### ▌ Loop 4c — Visual-fidelity reconciliation (Phase 3 when frontend touched + Phase 5 regression)

- **Trigger:** any frontend file change + DESIGN_MAP.md exists, OR `/architect-team:visual-qa` on-demand audit.
- **Phase 0 — the live app is a hard precondition:** the real running app (real backend) must be started and serving before any analysis. No live app → escalate `blocked`; never substitute static analysis.
- **Phase A.0 — design-baseline check:** if the design Oracle itself moved (a `design_baseline` change — a redesign / Full→V2 migration), every screen is in scope and an unmigrated implementation is drifted *by definition*.
- **Phase B code-first + Phase C live-app render:** resolve every styling layer to its concrete value; render the live app at every viewport; induce every state; capture computed styles + bounding box + per-state + per-viewport screenshots. A verdict with no live screenshot did not happen.
- **Tolerance defaults:** 0px / exact color / exact font / exact spacing / exact shadow. **Phase E remediation — fix to spec by default;** escalation reserved for 4 narrow cases, each writing an SR.
- **Independently verified** by the visual-verification-team — see Loop 4f.
- **References:** [`skills/visual-fidelity-reconciliation/SKILL.md`](skills/visual-fidelity-reconciliation/SKILL.md), [`skills/design-fidelity-mapping/SKILL.md`](skills/design-fidelity-mapping/SKILL.md).

### ▌ Loop 4d — Test-completeness verification (Phase 3 + Phase 5)

- **Trigger:** end of Phase 3 / Phase 5; on-demand when the orchestrator suspects a coverage gap.
- **Mechanism:** `test-completeness-verifier` confirms unit + integration + Playwright tests all ran for the applicable layers; grep-audits Playwright source for forbidden `page.evaluate(() => fetch(...))` / `page.request.*` / `axios.*` direct-API patterns; flags a "user-flow test" that navigates and asserts with no genuine user-interaction call (a vacuous flow); cross-checks the evidence-listed Playwright tests against the interactivity inventory so an uncovered element is flagged; runs the backend-integration audit (real backend vs mock-backed); confirms each acceptance criterion is covered.
- **Verdict JSON:** per-kind `status` + `backend_integration_audit` + `integration_testing_review` + the vacuous-flow + uncovered-element findings.
- **On `overall: fail`:** writes an SR (`test-completeness-failure` or `integration-testing-failure`); orchestrator re-spawns the originating team.
- **References:** [`agents/test-completeness-verifier.md`](agents/test-completeness-verifier.md).

### ▌ Loop 4e — Editability completeness (Phase 5 + on-demand)

- **Trigger:** any feature with a create or edit flow, at Phase 5; or `/architect-team:editability-audit`.
- **Mechanism:** three `editability-reviewer` agents (opus) spawn in parallel. Each independently enumerates every attribute of every entity (union of DB schema + API schemas + design + components), classifies each (`user-editable` / `user-settable-at-create-only` / `system-managed` / `derived` / `dynamic-via-action` / `ambiguous`), and traces every user-controllable attribute end-to-end through 7 stages: create control → edit control → state → request → request schema → handler → database → read-back.
- **Convergence:** the three argue round-robin (evidence-cited) until they hold one identical canonical list of must-be-editable attributes + gaps. Ambiguous attributes escalate to the human.
- **Gaps → SRs:** every gap (`missing-control`, `dead-control`, `orphan-field`, `no-readback`, `schema-mismatch`) becomes an `editability-gap` SR — spawns a fix team directly.
- **Multi-pass:** after the fixes land, the three re-spawn and re-review; bounded at 3 passes; exits `satisfied` when zero gaps remain.
- **References:** [`skills/editability-completeness/SKILL.md`](skills/editability-completeness/SKILL.md), [`agents/editability-reviewer.md`](agents/editability-reviewer.md).

### ▌ Loop 4f — Visual verification team (Phase 5 + on-demand)

- **Trigger:** after the Phase 5 visual-fidelity reconciliation sweep, OR `/architect-team:visual-qa`. Independently verifies that the reconciliation actually rendered the live app — a self-report does not gate the run.
- **Mechanism — three roles:** `visual-capture` agents (×N, by screen-group) start the LIVE app and capture screenshots + computed-style DATA for every DESIGN_MAP screen (countable artifacts); `visual-analyzer` agents run the objective structural analysis — a deterministic data diff vs the spec + a pixel diff vs the design reference image + a code cross-check; the `system-architect` (Visual Gap Synthesis mode) synthesizes the per-screen gap lists holistically, clustering them into root causes.
- **The verdict is DATA, not eyeballed images.** `38px ≠ 26px` is arithmetic; screenshots are the secondary pixel-diff + gross-break channel.
- **Anti-cheat — the artifact boundary:** capture sets are countable (`screens_captured == screens_analyzed == design_map_screen_count` for a `pass`); analysis cannot precede capture; the verdict is reproducible data; synthesis is independent of both.
- **Exit criteria:** the team's consolidated verdict — not the reconciliation self-report — is `overall: pass`. Each gap cluster → an SR; `blocked` (live app won't run) / `incomplete` escalates. The `Stop` hook blocks a run whose reconciliation was never verified by the team.
- **References:** [`skills/visual-verification-team/SKILL.md`](skills/visual-verification-team/SKILL.md), [`agents/visual-capture.md`](agents/visual-capture.md), [`agents/visual-analyzer.md`](agents/visual-analyzer.md).

### ▌ Loop 4g — Interaction completeness (Phase 3 + Phase 5)

- **Trigger:** any slice with UI/UX interactive surface, at the Phase 3 review gate and the Phase 5 cross-layer pass. The independent VERIFICATION gate that the `playwright-user-flows` authoring discipline was followed — the sibling of Loop 4e (editability), at the granularity of controls and pages instead of attributes.
- **Mechanism:** three `interaction-reviewer` agents (opus, analysis-only) spawn in parallel. Each independently re-enumerates every interactive element (the union of the design / `DESIGN_MAP`, the `ROUTE_MAP.md`, the route table, and the component code) AND every page / screen / route; classifies each element `endpoint-backed` / `client-only` / `confirmed-stub` / `ambiguous` and each page `live` / `placeholder` / `confirmed-stub`; verifies every non-stub element has a genuine user-driven Playwright test (real `page.click` / `page.fill` — not a `page.request.*` direct call, not a vacuous navigate-and-assert); traces each element to its endpoint or client behavior; and applies `dynamic-value-discovery` to flag a hardcoded value the context shows should be dynamic.
- **Convergence:** the three argue round-robin (evidence-cited) to one identical converged interaction map; a `system-architect` Round-3 robustness review checks for a shared blind spot; bounded multi-pass until all three agree the interactive surface is genuine.
- **Confirmed-stub mechanism:** an intentionally-inert control or a placeholder page is `confirmed-stub` ONLY with explicit user confirmation — the reviewer escalates a structured question, never guesses. A confirmed stub is recorded in the converged map and in `coverage-map.json` `confirmed_stubs[]`; it needs no user-flow test but is tracked.
- **Gaps → SRs:** every gap (`unwired-control`, `placeholder-page`, `hardcoded-dynamic-value`) becomes an SR — spawns a fix team directly; surfaces through the `ui_interaction_review` evidence field.
- **References:** [`skills/interaction-completeness/SKILL.md`](skills/interaction-completeness/SKILL.md), [`agents/interaction-reviewer.md`](agents/interaction-reviewer.md), [`skills/dynamic-value-discovery/SKILL.md`](skills/dynamic-value-discovery/SKILL.md).

### ▌ Loop 5 — Cross-layer integration (Phase 5)

- **Wrapper:** Orchestrator-internal. Begins after both layer-teams pass Loop 4 + Phase 4 merges cleanly.
- **Mechanism:** integration agent runs the full suite locally then against the **live dev API with real dev data** (never mocks). For frontend: Playwright user-flow tests against the **real running dev environment** — and for `both`-layer features the run exercises the **real backend** (no `page.route` happy-path stubs, no MSW, no fake API server). Visual-fidelity regression sweep (Loop 4c), its independent verification by the visual-verification-team (Loop 4f), the editability-completeness review (Loop 4e), and the interaction-completeness review (Loop 4g) all run here.
- **Exit criteria:** every Phase 1 acceptance criterion passes; every documented error response exercised; every interactive element covered by a genuine user-flow test and every page verified live (the interaction-completeness team agrees the interactive surface is genuine); the editability team reaches `satisfied`.
- **On failure:** SR auto-spawn → Logic Map B.
- **References:** [`skills/dev-api-integration-testing/SKILL.md`](skills/dev-api-integration-testing/SKILL.md), [`skills/playwright-user-flows/SKILL.md`](skills/playwright-user-flows/SKILL.md), [`agents/integration.md`](agents/integration.md).

### ▌ Loop 6 — Outer task-group loop (Phase 6)

- **Mechanism:** repeat Phase 2 → Phase 5 for each parallel task group, respecting the dependency graph. Maintain a running ledger.
- **Exit criteria:** every task group complete + ledger fully populated.

### ▌ Loop 7 — Master review meta-loop (Phase 7)

- **Mechanism per iteration:** walk every commit; attribute to ≥ 1 requirement via the coverage map; re-run `openspec validate`; walk every coverage-map entry. Then dispatch the `system-architect` in **Master Review Audit mode** — an independent re-verification of every entry + every SR (the orchestrator's own walk is a producer-is-own-checker step; the audit is the independent checker).
- **Exit criteria — every entry must have:** ≥ 1 commit SHA; passing unit/integration tests; passing Playwright flow(s) where applicable; non-empty `demo_artifact`; the editability team `satisfied` for entity-bearing features. Plus `openspec validate` reports `valid: true`, AND the independent master-review audit verdict is `overall: pass` (it gates the Phase 8 commit; the `Stop` hook checks it).
- **On any gap:** re-spawn the appropriate team(s); meta-loop continues until the coverage map is fully green.
- **Terminal action:** `openspec archive <change-name>`. Phase 8 then runs the **documentation-currency gate** — every doc the change touched (the maps, `README.md`, `CHANGELOG.md`, `CLAUDE.md`) is updated and then independently audited by the `system-architect` (Documentation Currency Audit mode) — emits the final report (persisted + mined to MemPalace), and auto-commits + pushes.

```
░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
█▓▒░  ◆  ON-DEMAND COMMANDS  ◆  ░▒▓█
░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
```

### `/architect-team <path>`

Run the full Phase −1 → 8 pipeline against a requirements folder. See "Usage" above.

### `/architect-team-setup [--check-only] [--force-reinstall]`

Cross-platform installer for prerequisites: openspec CLI, pytest+httpx, Playwright + chromium. Idempotent.

### `/architect-team:visual-qa [<codebase-path>]`

On-demand pixel-perfect audit against `DESIGN_MAP.md`. Refreshes the design map if stale, runs code-first + Playwright reconciliation with zero-tolerance defaults, fixes drift to spec. Emits structured `PASS` / `DRIFT_DETECTED` / `GAPS_DETECTED`.

### `/architect-team:mempalace-install [--check-only] [--workspace <path>]`

One-time installer for the MemPalace CLI + MCP server. uv-first, pip fallback. Prints (does not auto-run) the `claude mcp add` + per-workspace `mempalace init` commands.

### `/architect-team:memory <search|mine|status|wake-up|sweep> [args]`

Ad-hoc interaction with the per-workspace MemPalace store at `<workspace>/.mempalace/palace` — semantic search, manual mining, status, wake-up context, transcript sweep.

### `/architect-team:editability-audit [<codebase-path>] [--feature <name>]`

On-demand editability-completeness audit. Spawns the three-reviewer team (Loop 4e), reports the converged editable-surface map + gaps + escalations, and writes the `editability-gap` SRs.

```
░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
█▓▒░  ◆  DOCUMENT CONVENTIONS  ◆  ░▒▓█
░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
```

| Path | Purpose | Frontmatter |
|---|---|---|
| `<codebase>/docs/CODEBASE_MAP.md` | Cartographer's output | `last_mapped` |
| `<codebase>/docs/ROUTE_MAP.md` | Route-mapper's output for frontends | `last_routed` |
| `<codebase>/docs/DESIGN_MAP.md` | Design-fidelity output (conditional) — tokens, asset registry, per-screen specs, link inference | `last_designed` |
| `<workspace>/docs/INTEGRATION_MAP.md` | Master-synthesizer's cross-codebase synthesis | `last_synthesized` |
| `<workspace>/.architect-team/intake-state.json` | Re-entry short-circuit state | — |
| `<workspace>/.architect-team/reviews/<task-id>.json` | Per-task review-gate evidence (v6 schema — 12 self-review fields + the independent `task-reviewer` verdict) | — |
| `<workspace>/.architect-team/teammates/<name>.json` | Teammate manifests | — |
| `<workspace>/.architect-team/handoffs/<from>-to-<to>-<ts>.md` | Inter-agent coordination | — |
| `<workspace>/.architect-team/solution-requirements/SR-<id>-<ts>.json` | Auto-spawn fix-team requirements | — |
| `<workspace>/.architect-team/diagnostic-research/<test-id>/` | Researcher drafts + consolidated diagnostic plan | — |
| `<workspace>/.architect-team/editability/<feature>/converged-map-*.json` | Converged editable-surface maps | — |
| `<workspace>/.architect-team/failure-pathway/<symptom>-<ts>.json` | Pathway-audit artifacts (expensive-verification debugging) | — |
| `<workspace>/.architect-team/test-completeness/<task-id>-<ts>.json` | Test-completeness verdicts | — |
| `<workspace>/.architect-team/master-review/audit-<ts>.json` | Phase 7 independent master-review audit verdict (system-architect Master Review Audit mode) | — |
| `<workspace>/.architect-team/visual-fidelity/` | visual-verification-team artifacts — `capture/` (screenshots + computed-style data), `analysis/` (per-screen gap lists), `verification-verdict-*.json` (consolidated verdict) | — |
| `<workspace>/.architect-team/escalation-pending.md` | Escalation marker — present while the run is paused for a human (the Stop hook stands down) | — |
| `<workspace>/.architect-team/runs/<change>-<ts>.md` | Phase 8 final reports | — |
| `<workspace>/.mempalace/palace` | MemPalace local-first searchable memory store | — |
| `<test-output-dir>/expectations/<test-id>.json` | Per-test predictions (RCA pre-condition) | — |
| `<test-output-dir>/rca/<test-id>-<ts>.json` | 3-pass RCA artifact for failed tests | — |
| `openspec/changes/<change>/coverage-map.json` | Coverage map (Phase 1 → 8 spine) | — |

```
░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
█▓▒░  ◆  PROJECT EMAIL NOTIFICATIONS  ◆  ░▒▓█
░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
```

A pipeline run is long and mostly unattended. The **project email-notification
system** (v0.9.18) keeps a configured list of stakeholders informed as a run
progresses — opt-in, per-project, and strictly best-effort.

### ▸ How it works

The feature is **entirely opt-in**: a project enables it by committing a
`.architect-team-notify.json` file at its repository root. If that file is
absent the notifier is a **silent no-op** and the pipeline behaves exactly as
before. When the file is present, the orchestrator invokes the notifier CLI
(`scripts/notify/notify.py`) at five points in the pipeline; each invocation is
**best-effort** — the notifier always exits 0, and a notification failure never
blocks, fails, or alters a run.

### ▸ The five event types

| Event | Emitted when | Context in the email |
|---|---|---|
| `phase_start` | at the start of each pipeline phase | the phase name |
| `phase_complete` | at the end of each pipeline phase | the phase name |
| `issue_discovered` | a new solution requirement is picked up (Phase 3b) | the issue summary |
| `git_commit` | immediately after the Phase 8 git commit | the commit SHA |
| `deploy` | when Phase 5 brings up a live dev instance | the deploy layer |

Each recipient subscribes to whichever events they want — or to the `"all"`
shorthand for every event.

### ▸ The `.architect-team-notify.json` schema

A committed JSON file at the **target project's** repository root. Copy
[`.architect-team-notify.example.json`](.architect-team-notify.example.json)
and edit it:

```jsonc
{
  "provider": "gmail",                       // "gmail" or "sendgrid"
  "from_address": "ci-bot@your-domain.example",
  "from_name": "Architect Team CI",          // optional display name

  "gmail": {                                  // settings for the gmail provider
    "username": "ci-bot@your-domain.example", // SMTP login (defaults to from_address)
    "app_password_env": "ARCHITECT_GMAIL_APP_PASSWORD"   // env-var NAME, not the secret
  },
  "sendgrid": {                               // settings for the sendgrid provider
    "api_key_env": "ARCHITECT_SENDGRID_API_KEY"          // env-var NAME, not the secret
  },

  "recipients": [
    { "email": "tech-lead@your-domain.example", "events": ["all"] },
    { "email": "qa@your-domain.example",
      "events": ["phase_complete", "issue_discovered", "deploy"] }
  ]
}
```

| Field | Required | Meaning |
|---|---|---|
| `provider` | yes | `"gmail"` or `"sendgrid"` — selects the send transport |
| `from_address` | yes | the sender email address |
| `from_name` | no | optional sender display name |
| `gmail.username` | no | SMTP login; defaults to `from_address` |
| `gmail.app_password_env` | for gmail | **name** of the env var holding the Gmail app password |
| `sendgrid.api_key_env` | for sendgrid | **name** of the env var holding the SendGrid API key |
| `recipients[]` | yes (non-empty) | one entry per recipient |
| `recipients[].email` | yes | the recipient address |
| `recipients[].events[]` | yes (non-empty) | the event types this recipient receives, or `["all"]` |

The config file is `.json` (parsed with the standard-library `json` module) and
holds **only** the *name* of an environment variable for each provider secret —
never the secret value itself.

### ▸ Secret handling — environment variables only

Provider secrets are **never committed and never logged**. The config names an
environment variable (`gmail.app_password_env` / `sendgrid.api_key_env`); the
notifier reads `os.environ[<that name>]` at send time. If the variable is unset,
the send is skipped with a one-line stderr warning that names the variable but
never echoes a secret — and the process still exits 0. The recipient email
addresses themselves do live in the committed config (the project's explicit
choice — ordinary practice, as with `CODEOWNERS`).

### ▸ Provider setup

**Gmail** — transmits via `smtp.gmail.com:587` over STARTTLS (standard-library
`smtplib`). Gmail requires an **app password**, not your account password:
enable 2-Step Verification on the sending Google account, then create an app
password at <https://myaccount.google.com/apppasswords>. Export it under the
name your config gives in `gmail.app_password_env`:

```bash
export ARCHITECT_GMAIL_APP_PASSWORD="<the 16-character app password>"
```

**SendGrid** — POSTs to the SendGrid v3 mail-send API
(`https://api.sendgrid.com/v3/mail/send`) with the API key as a Bearer header
(standard-library `urllib.request`). Create an API key in the SendGrid console
(Settings → API Keys, Mail Send permission) and export it under the name your
config gives in `sendgrid.api_key_env`:

```bash
export ARCHITECT_SENDGRID_API_KEY="<the SendGrid API key>"
```

The notifier uses **only the Python standard library** for both providers —
zero new third-party dependencies.

```
░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
█▓▒░  ◆  UI INTERACTION FIDELITY  ◆  ░▒▓█
░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
```

The pipeline kept shipping frontend work that was not what it claimed to be —
and the verification did not catch it. v0.9.19 makes the genuineness of a
shipped UI a **structural, hook-enforced gate** rather than trust-based
Markdown. Three failure modes, one enforcement layer.

### ▸ The three failure modes it closes

| Failure mode | What shipped | How v0.9.19 catches it |
|---|---|---|
| **Fake user-flow test** | A Playwright "user-flow" test passes without driving the UI — a direct `page.request.post('/api/...')` call, or a navigate-and-assert with zero `page.click`. `integration_testing_review` gates real-backend-vs-mock, a different axis; a grep finds *present* bad patterns, not an *absent* genuine interaction. | The interaction-completeness team audits every Playwright test for genuine user-driven interaction; the strengthened `test-completeness-verifier` flags a vacuous flow mechanically. |
| **Placeholder page** | A route is wired to a `ComingSoon` / skeleton / mock page where the design specifies a real live page — and a Playwright test clicks happily through it. | Every page / screen / route is enumerated and classified `live` / `placeholder` / `confirmed-stub`, cross-checked against the design / requirements / `ROUTE_MAP.md`. |
| **Hardcoded dynamic value** | The design mockup's sample data — `"John Smith"`, `"$1,234.00"`, `"Welcome back, Sarah"` — is copied literally into the code, so one person's sample data ships to everyone. | `dynamic-value-discovery` classifies every displayed value `static` vs. `dynamic` FROM CONTEXT; a hardcoded value the context shows should be bound is a `hardcoded-dynamic-value` gap. |

### ▸ The `interaction-completeness` verification gate

A new judgment-heavy verification discipline — the `interaction-completeness`
skill — modeled on the proven `editability-completeness` pattern. For any slice
with UI/UX surface it runs at the **Phase 3** review gate and the **Phase 5**
cross-layer pass: three `interaction-reviewer` agents (opus, analysis-only)
spawn **in parallel** and each independently re-enumerates **every interactive
element** (buttons, links, inputs, selects, toggles, menus, drag handles,
file-uploads) AND **every page / screen / route** — the union of the design /
`DESIGN_MAP`, the `ROUTE_MAP.md`, the route table, and the component code.
Each reviewer classifies how each element is wired, classifies each page, and
audits whether each non-stub element has a genuine user-driven Playwright test.
The three then **argue round-robin to a converged interaction map**; the
`system-architect` performs a Round-3 robustness review; a bounded multi-pass
outer loop re-reviews after fixes land — the exact relationship
`editability-completeness` has to `playwright-user-flows`, applied to controls
and pages instead of attributes.

### ▸ The classification rubrics

Each **interactive element** is classified — from THIS feature's requirements
and design, never from a name alone:

- `endpoint-backed` — drives an API call (control → handler → HTTP client → endpoint).
- `client-only` — pure client behavior (navigation / state change / overlay).
- `confirmed-stub` — intentionally inert, **user-confirmed** (see below).
- `ambiguous` — the requirements do not determine it → **escalate to the human**.

Each **page / screen / route** is classified `live`, `placeholder`, or
`confirmed-stub`. The skill carries a **placeholder-signal rubric** — component
/ file naming (`Placeholder`, `ComingSoon`, `Stub`, `Mock`, `Demo`, `WIP`),
"coming soon" / "under construction" / lorem-ipsum content, a data-driven page
that makes no API calls, a near-empty route shell, a route-table entry pointing
at a placeholder while the real component is specified-but-unwired.

### ▸ The confirmed-stub mechanism

An interactive element OR a page that is **intentionally inert** is classified
`confirmed-stub` **ONLY with explicit user confirmation**. A reviewer that finds
an inert control or a placeholder page does **not guess** — it escalates a
structured question to the human via the orchestrator. Once confirmed, the stub
is recorded durably in the converged interaction map AND in the change's
`coverage-map.json` `confirmed_stubs[]` list; it does not require a user-flow
test (testing an intentionally-inert control is meaningless) but it **is
tracked**, never silently ignored. An **unconfirmed** inert control is an
`unwired-control` gap; an **unconfirmed** placeholder page is a
`placeholder-page` gap — each routed as a solution requirement.

### ▸ The `ui_interaction_review` review-gate field (evidence schema v6)

The shared review-gate evidence schema is bumped **v5 → v6** with a new
hook-enforced field — `ui_interaction_review`, taking `pass` / `n/a` / `fail`:

- `pass` — every interactive element in the slice is genuinely UI-tested, every page is live, every displayed value is correctly static or dynamically bound, or a confirmed stub.
- `n/a` — the slice has no UI/frontend interactive surface; **requires** a non-empty `ui_interaction_review_note`.
- `fail` — **blocked by the hook**; an `unwired-control` / `placeholder-page` / `hardcoded-dynamic-value` gap must be escalated via a solution requirement, not marked complete.

It is a **separate** field from `integration_testing_review` because it gates a
genuinely orthogonal axis — a test can be real-backend + fake-interaction, or
mock-backend + real-interaction. The field is defined once in
`hooks/review_evidence_schema.py`; both evidence hooks import that module, so
the bump flows through with no per-hook drift — exactly as
`visual_fidelity_review` (v0.5.0), `test_completeness_review` (v0.9.0), and
`integration_testing_review` (v0.9.5) were each added.

### ▸ Dynamic-value discovery — a cross-role discipline

A hardcoded value that should be dynamic cannot be caught by a single gate — it
has to be *prevented* at planning, *avoided* at implementation, and *caught* at
review. So v0.9.19 adds the `dynamic-value-discovery` skill — a cross-role
discipline, modeled on `reuse-first-design`, wired into all three roles:

- **Architect** — `system-architect` and `design-fidelity-mapping` consult it: the `DESIGN_MAP`'s per-screen specs classify each value `static` / `dynamic` and name the data source for each dynamic value.
- **Developer** — `frontend` and `backend` consult it: bind every dynamic value to its data source; never hardcode design sample data.
- **Evaluator** — the `interaction-reviewer`, guided by it, flags a hardcoded value the context shows should be dynamic.

The core rule: **classify FROM CONTEXT, never from the literal** — the same
string is `dynamic` beside an avatar and `static` in a nav bar; the value alone
never decides. Person names, dates, currency amounts, counts, statuses, a value
in a record-detail view or a repeating list row, a greeting with a name are
`dynamic` signals; nav labels, button text, section headings, fixed helper
text, brand strings are `static` signals. Every value classified `dynamic` is
bound to a **named data source**; a genuinely ambiguous classification
escalates to the human.

```
░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
█▓▒░  ◆  DEVELOPMENT  ◆  ░▒▓█
░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
```

```bash
# Run the plugin's self-tests
python -m pytest -v
```

Tests validate: plugin/marketplace JSON; all 20 skill frontmatters; all 17 agent frontmatters (tool + model names); all 6 commands; hooks.json wiring for all three events; hook script logic (review-gate + teammate-idle share one `review_evidence_schema` module — evidence schema v6: 12 self-review fields + the independent `task-reviewer` verdict; the `pipeline-completion-audit` Stop hook incl. the master-review audit check; path-traversal sanitization); cross-component consistency (the two evidence hooks cannot drift; the Stop hook's origin set matches the pipeline; no unregistered skills/agents/commands); the setup + MemPalace install scripts; the `scripts/notify/notify.py` notifier (config load/validate, Gmail + SendGrid message construction with mocked transport, event dispatch, secret resolution, CLI + failure isolation) and its pipeline wiring; and the no-arbitrary-timers, diagnostic-research, MemPalace-integration, integration-testing, expensive-verification, editability-completeness, readme-styling, design-baseline-migration, visual-verification-team, producer-checker-enforcement, mempalace-mine-syntax, documentation-currency, project-email-notifications, and ui-interaction-fidelity disciplines. **647 tests pass.**

### Bumping versions

1. Update `.claude-plugin/plugin.json` + `.claude-plugin/marketplace.json` version.
2. Add a `## [x.y.z] — YYYY-MM-DD` entry to `CHANGELOG.md`.
3. Commit with explicit author override:
   ```bash
   git -c user.name="Paul Ingram" -c user.email="paulingram@users.noreply.github.com" commit -m "..."
   ```
4. Refresh this README per [`skills/readme-styling/SKILL.md`](skills/readme-styling/SKILL.md) — banner version, badges, inventory counts, NEW IN, the timeline.

```
░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
█▓▒░  ◆  STATUS  ◆  ░▒▓█
░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
```

```
   ▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰

           v0.1.0 ─ initial release
           v0.2.0 ─ orchestrator skill rename (command/skill collision)
           v0.2.3 ─ path-traversal hardening + escalation policy
           v0.2.4 ─ python3 portability
           v0.3.0 ─ root-cause-test-failures + playwright hardening
           v0.4.0 ─ design-fidelity-mapping + visual-fidelity tests
           v0.5.0 ─ visual-fidelity-reconciliation + /visual-qa command
           v0.6.0 ─ link inference for un-annotated UI
           v0.7.0 ─ solution-requirement auto-spawn
           v0.8.0 ─ auto-commit + push on clean pass
           v0.8.1 ─ frontend + backend implementers on opus
           v0.9.0 ─ test-completeness verification
           v0.9.1 ─ auto-compact prompt at end of pipeline
           v0.9.2 ─ forbid arbitrary wall-clock wakeups / timers
           v0.9.3 ─ diagnostic-research-team (3 researchers + architect)
           v0.9.4 ─ MemPalace integration — searchable pipeline memory
           v0.9.5 ─ real backend by default for full-stack tests
           v0.9.6 ─ expensive-verification-debugging
           v0.9.7 ─ editability-completeness review
           v0.9.8 ─ readme-styling skill + README refresh
           v0.9.9 ─ logic-implementation review — Tier 1/2/3 hole fixes
           v0.9.10 ─ design-baseline-migration awareness
           v0.9.11 ─ live-app visual verification (single verifier)
           v0.9.12 ─ visual verification team — capture / analyze / synthesize
           v0.9.13 ─ independent review — task-reviewer + master-review audit
           v0.9.14 ─ MemPalace `mine` syntax fix — drop the invalid `--room` flag
           v0.9.15 ─ documentation-currency gate
           v0.9.16 ─ readme-styling: centering + color + themes
           v0.9.17 ─ plain-language requirements are a first-class input
           v0.9.18 ─ project email notifications — Gmail / SendGrid, five events
           v0.9.19 ─ UI interaction fidelity — genuine controls, live pages, dynamic values
           v0.9.20 ─ gates are opt-in — orchestrator drives end-to-end without asking obvious questions
           v0.9.21 ─ interaction intuition at Phase −1 — every control mapped before code is written
           v0.9.22 ─ bug-fix pipeline — replicate, propose, fix, QA-replay against live dev
           v0.9.23 ─ automatic documentation currency via a dedicated doc-updater agent
           v0.9.24 ─ MemPalace wake-up runs at the earliest phase, before any subagent dispatch
           v0.9.25 ─ bug-fix-pipeline gets its own planning-validation gate at Phase B3
           v0.9.26 ─ system-architect agent gets bounded Write for its 7 audit verdicts
           v0.9.27 ─ bug-fix-pipeline gets full notification wiring
           v0.9.28 ─ cohesion-review close-out: confirmed-stubs cross-reference + polish
           v0.9.29 ─ UX test builder + bug-fix Phase B6b post-deploy sensibility check
   ◆       v0.9.30 ─ cross-platform Python hook invocation — Windows Store-shim fix (current)

   ▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰
```

Full design history: [`docs/superpowers/specs/2026-05-16-architect-team-plugin-design.md`](docs/superpowers/specs/2026-05-16-architect-team-plugin-design.md). Full changelog: [`CHANGELOG.md`](CHANGELOG.md).

```
░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
█▓▒░  ◆  LICENSE  ◆  ░▒▓█
░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
```

MIT — see [`LICENSE`](LICENSE).

```
                  ▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄
                  █  Built with Claude Code · Opus 4.7  █
                  ▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀
```
