# architect-team
<!-- architect-team:readme-theme=midnight -->

```
      █████  ██████   ██████ ██   ██ ██ ████████ ███████  ██████ ████████
     ██   ██ ██   ██ ██      ██   ██ ██    ██    ██      ██         ██
     ███████ ██████  ██      ███████ ██    ██    █████   ██         ██
     ██   ██ ██   ██ ██      ██   ██ ██    ██    ██      ██         ██
     ██   ██ ██   ██  ██████ ██   ██ ██    ██    ███████  ██████    ██

                            ─── T E A M ───   v 0 . 9 . 17
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

![version](https://img.shields.io/badge/version-0.9.17-2563EB?style=flat-square)
![license](https://img.shields.io/badge/license-MIT-3FB950?style=flat-square)
![tests](https://img.shields.io/badge/tests-431%20passing-3FB950?style=flat-square)
![claude code](https://img.shields.io/badge/Claude%20Code-plugin-7C3AED?style=flat-square)

```
░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
█▓▒░  ◆  NEW IN v0.9.17  ◆  ░▒▓█
░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
```

| Capability | What changed |
|---|---|
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
┌─ SKILLS (18) ───────────────────────┬─ AGENTS (16) ─────────────────────────┐
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
│ ◇ visual-verification-team          │                                       │
│ ◇ documentation-currency            │                                       │
├─ COMMANDS (6) ──────────────────────┴───────────────────────────────────────┤
│ ▸ /architect-team <path-to-requirements-folder>                             │
│ ▸ /architect-team-setup                                                     │
│ ▸ /architect-team:visual-qa [<codebase-path>]                               │
│ ▸ /architect-team:mempalace-install                                         │
│ ▸ /architect-team:memory <search|mine|status|wake-up|sweep>                 │
│ ▸ /architect-team:editability-audit [<codebase-path>]                       │
├─ HOOKS (3) ─────────────────────────────────────────────────────────────────┤
│ ▸ PostToolUse(TaskUpdate)   review-gate evidence — v5 + independent review  │
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
       │   PHASE 5       │    │   PHASE 4       │    │  · 11 fields    │
       │  Integration    │◀───│  Reconciliation │◀───│  · visual-fid   │
       │  · real backend │    │  · shared bounds│    │    review       │
       │  · playwright   │    │  · contract sync│    │  · RCA on fail  │
       │  · visual-fid   │    │  · no feature   │    │  · auto-spawn   │
       │  · editability  │    │    code         │    │    SR on issue  │
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
        ◆ evidence present · valid JSON · all 11 self-review fields valid?
            · spec_review = quality_review = "pass"
            · real_not_stubbed = true · tests added ≥ 1 and == passing
            · reuse_compliance = "ok" · demo_artifact + files_changed non-empty
            · visual_fidelity / test_completeness / integration_testing
              reviews ≠ "fail"
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

Every surfaced issue becomes an SR; test-failure origins route through diagnostic research first, editability gaps go straight to a fix team; the loop closes when the originating check passes.

```
   an issue surfaces   (failed test · visual drift · editability gap)
            │
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
        └─ editability-gap ──────────────────┐                │
           the converged editable-surface    │                │
           map is already the full           │                │
           diagnosis — research is skipped    │                │
                                              ▼                ▼
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
- **Mechanism:** teammate writes its self-review into `<cwd>/.architect-team/reviews/<task-id>.json` (evidence schema v5) BEFORE any `TaskUpdate(status=completed)`; an independent `task-reviewer` agent then reads the diff and writes the `independent_review` block. Exit 0 = allow, exit 2 = block.
- **Acceptance criteria — 11 self-review fields + the `independent_review` block:**

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
- **Mechanism:** `test-completeness-verifier` confirms unit + integration + Playwright tests all ran for the applicable layers; grep-audits Playwright source for forbidden `page.evaluate(() => fetch(...))` / `page.request.*` / `axios.*` direct-API patterns; runs the backend-integration audit (real backend vs mock-backed); confirms each acceptance criterion is covered.
- **Verdict JSON:** per-kind `status` + `backend_integration_audit` + `integration_testing_review`.
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

### ▌ Loop 5 — Cross-layer integration (Phase 5)

- **Wrapper:** Orchestrator-internal. Begins after both layer-teams pass Loop 4 + Phase 4 merges cleanly.
- **Mechanism:** integration agent runs the full suite locally then against the **live dev API with real dev data** (never mocks). For frontend: Playwright user-flow tests against the **real running dev environment** — and for `both`-layer features the run exercises the **real backend** (no `page.route` happy-path stubs, no MSW, no fake API server). Visual-fidelity regression sweep (Loop 4c), its independent verification by the visual-verification-team (Loop 4f), and the editability-completeness review (Loop 4e) all run here.
- **Exit criteria:** every Phase 1 acceptance criterion passes; every documented error response exercised; every interactive element covered by a user-flow test; the editability team reaches `satisfied`.
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
| `<workspace>/.architect-team/reviews/<task-id>.json` | Per-task review-gate evidence (v5 schema — 11 self-review fields + the independent `task-reviewer` verdict) | — |
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
█▓▒░  ◆  DEVELOPMENT  ◆  ░▒▓█
░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
```

```bash
# Run the plugin's self-tests
python -m pytest -v
```

Tests validate: plugin/marketplace JSON; all 18 skill frontmatters; all 16 agent frontmatters (tool + model names); all 6 commands; hooks.json wiring for all three events; hook script logic (review-gate + teammate-idle share one `review_evidence_schema` module — evidence schema v5: 11 self-review fields + the independent `task-reviewer` verdict; the `pipeline-completion-audit` Stop hook incl. the master-review audit check; path-traversal sanitization); cross-component consistency (the two evidence hooks cannot drift; the Stop hook's origin set matches the pipeline; no unregistered skills/agents/commands); the setup + MemPalace install scripts; and the no-arbitrary-timers, diagnostic-research, MemPalace-integration, integration-testing, expensive-verification, editability-completeness, readme-styling, design-baseline-migration, visual-verification-team, producer-checker-enforcement, mempalace-mine-syntax, and documentation-currency disciplines. **418 tests pass.**

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
   ◆       v0.9.17 ─ plain-language requirements are a first-class input (current)

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
