# architect-team
<!-- architect-team:readme-theme=midnight -->

```
      █████  ██████   ██████ ██   ██ ██ ████████ ███████  ██████ ████████
     ██   ██ ██   ██ ██      ██   ██ ██    ██    ██      ██         ██
     ███████ ██████  ██      ███████ ██    ██    █████   ██         ██
     ██   ██ ██   ██ ██      ██   ██ ██    ██    ██      ██         ██
     ██   ██ ██   ██  ██████ ██   ██ ██    ██    ███████  ██████    ██

                            ─── T E A M ───   v 1 . 8 . 0
```

> Spec-to-production multi-agent coding pipeline for Claude Code. Takes a
> requirements folder (OpenSpec / Superpowers / plain markdown), drives it
> through a 100%-coverage planning loop with reuse-first design, spawns
> **long-lived named teammates** (Claude Code Agent Teams primitive — Lead +
> N teammates, each with its own 1M context, shared task list, `SendMessage`
> for direct messaging) for backend / frontend, enforces review gates via
> hooks, **fixes design drift to spec autonomously**, **verifies the editable
> surface is complete**, **tests full-stack work against the real backend**,
> **auto-spawns fix teams from every surfaced issue**, **remembers what it
> learns in a local searchable memory**, and **auto-commits and pushes on a
> clean pass** — the dev loop closes itself end-to-end.

![version](https://img.shields.io/badge/version-1.8.0-2563EB?style=flat-square)
![license](https://img.shields.io/badge/license-MIT-3FB950?style=flat-square)
![tests](https://img.shields.io/badge/tests-2098%20passing-3FB950?style=flat-square)
![claude code](https://img.shields.io/badge/Claude%20Code-plugin-7C3AED?style=flat-square)

```
░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
█▓▒░  ◆  REQUIREMENTS  ◆  ░▒▓█
░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
```

v1.0.0 makes Claude Code's experimental **Agent Teams** primitive the default
dispatch mode — long-lived named teammates with their own 1M context windows
and a shared task list, instead of the v0.10.0 ephemeral one-shot subagents.
Teams mode requires **two** things to be true; the pipeline auto-detects both
and falls back to subagents mode (the v0.10.0 behavior, unchanged) when either
is missing.

| Requirement | Detail |
|---|---|
| **`CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`** | Set as a shell env var, or as `{"env": {"CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1"}}` in `~/.claude/settings.json`. `/architect-team-setup` checks for it and (with your consent) offers to add it to your settings file. |
| **Claude Code ≥ 2.1.32** | Older versions don't ship the Agent Teams primitive. `/architect-team-setup` checks `claude --version`. |
| **`--no-teams` fallback** | Forces subagents mode even when the flag + version qualify — escape hatch for users hitting experimental-flag instability. Pass it on `/architect-team`, `/architect-team:bug-fix`, or `/architect-team:mini`. |

Without the flag set or with Claude Code < 2.1.32, the pipeline runs in
subagents mode silently — same dispatch behavior as v0.10.0, no surprise. With
the flag set + version OK, the pipeline runs in teams mode automatically and
emits a one-line note at startup recording the choice in `intake-state.json`.

```
░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
█▓▒░  ◆  NEW IN v1.8.0  ◆  ░▒▓█
░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
```

| Capability | What changed |
|---|---|
| ▸ **Agent-Resume Discipline — auto-recover from harness stream timeouts that lose a background agent's final report (v1.8.0)** | A reliability gap distinct from v2.0.0's verified-agent-output framework. A real-world background `dv-attorney` agent ran 68 tool-calls of real work; the final report message was lost to a harness-level stream timeout (rate-limit cutoff); the orchestrator saw an empty result and treated the agent as failed; the work was on disk the whole time; the user had to manually `redispatch and continue` so the agent could re-emit its verdict from already-loaded context. v1.8.0 automates that recovery and adds a checkpoint discipline so the resumed agent doesn't re-do the 68 tool calls. Four enforcement points (same layered shape as v1.6.0 teammate-git + v1.7.0 frontend-missing-API). **(1) The new `scripts/setup/agent_resume.py` helper** is stdlib-only and exposes three functions. **`is_truncated(result)`** returns True on ANY of: missing / non-dict / sub-50-char `output`; output containing a harness rate-limit / stream-timeout marker (case-insensitive — "Server is temporarily limiting requests", "rate limit", "stream timeout", and close variants); output present but containing NONE of the standard report-format markers `Status:` / `DONE` / `BLOCKED` / `NEEDS_CONTEXT`. **`wrap_agent_result(result, agent_id, send_message=None, max_attempts=2, resume_prompt=DEFAULT_RESUME_PROMPT)`** is dependency-injected — the orchestrator passes the harness's `SendMessage`-equivalent at call time; tests pass a mock. On truncation the helper invokes `send_message(to=agent_id, prompt=resume_prompt)` to ask the SAME agent for its final verdict from already-loaded context; merges the resumed output with the original (with a `[resumed via wrap_agent_result]` marker for downstream readers to split the seam); caps retries at `max_attempts`; surfaces `resumed_failed=True` + `resume_error` on cap-exhaustion WITHOUT raising so the orchestrator can route on-disk artifacts to the user. **`read_checkpoint(agent_id, checkpoints_dir=None)`** reads `.architect-team/agent-checkpoints/<agent_id>.json`; defaults the directory via the v1.1.0 `shared_state_dir()` lazy-import pattern (so the checkpoint dir lives in the main worktree, visible across worktrees during the same run); returns None for absent / unreadable / malformed files; never raises. **(2) Two new canonical sections in `skills/common-pipeline-conventions/SKILL.md`** — `## Background-agent resume discipline` (orchestrator MUST wrap every dispatch result; documents the wrap-call rule with a concrete code example, the 3 truncation heuristics, the 2-attempt cap, the user-surfacing on `resumed_failed=True` with on-disk artifact citation) and `## Agent checkpoint discipline` (long-running agents (>20 tool calls expected) write checkpoints every ~10 calls or at logical-step boundaries; documents the path, the schema (`agent_id`, `task_id`, `schema_version`, `last_completed_step`, `files_touched`, `in_progress`, `ts`), the cadence, and the resume-reads-checkpoint pattern — skip already-completed steps, treat `files_touched` as already-touched, resume from `in_progress`). **(3) One-paragraph reference in each of the 3 pipeline SKILL.md bodies** — `architect-team-pipeline` (after Phase 2's dispatch summary), `bug-fix-pipeline` (after MemPalace wake-up), `mini-architect-team-pipeline` (same placement) — each enumerates the phase boundaries where a background Agent dispatch occurs and directs the Lead to route the result through `wrap_agent_result()` BEFORE treating the work as complete. **(4) Uniform `## Checkpoint discipline` section in all 27 `agents/*.md` files** — 3-line block inserted AFTER the existing `## Forbidden git operations` section (v1.6.0) for a stable cross-agent location; the block names when (>20 tool-call work), where (`.architect-team/agent-checkpoints/<your-agent-id>.json`), the cadence, the resume-reads-checkpoint behavior, and the schema. Cross-references the canonical section. Duplicated across 27 files for the safety win, matching the v1.6.0 precedent. **42 new tests in `tests/test_agent_resume_discipline.py`** covering: 10 `is_truncated` tests (positive + negative + parametrized rate-limit markers + case-insensitive); 10 `wrap_agent_result` tests (passthrough on well-formed, no-send-message detection, resume-invocation, merge-with-marker, max-attempts cap, max-attempts=1, early-stop on success, send-message-exception tolerance, extra-keys preservation, None-input tolerance); 5 `read_checkpoint` tests (absent / parsed / malformed / non-dict-payload / default-dir-resolution); 4 canonical-section structural tests; 3 per-agent fan-out tests; 3 parametrized pipeline-reference tests; 2 helper-surface tests (exports + stdlib-only audit). **No runtime detector in v1.8.0** — the discipline lives in the helper (called by the orchestrator at each dispatch point), the canonical sections, and the 27-agent fan-out (read at every dispatch). A future v1.x may add a harness-level Stop-hook that fires on Agent completion with empty output — that requires Claude Code harness extensions the plugin can't make today. **Orthogonal to v2.0.0** — the VAO framework on the separate branch is unaffected; the v1.8.0 helper layers cleanly underneath if v2.0.0 is later approved. **Backwards-compatible:** purely additive; well-behaved runs that don't hit harness stream timeouts see no behavior change. 2056 → **2098 passing** (+ 1 skipped). |
| ▸ **Frontend Missing-API Discipline — surface missing endpoints as SRs; never fake, mock, hardcode, or silently stub (v1.7.0)** | A discipline gap orthogonal to v1.6.0's. When a frontend agent encounters a UI element that needs a backend API which does NOT yet exist, the previous version of the plugin did not tell the agent what to do — and the predictable failure modes were the four downstream defects each existing gate catches AFTER the round trip is wasted: **fake the data** (caught by `dynamic-value-discovery` at Phase 3 / Phase 5), **mock the endpoint** (caught by `playwright-user-flows`'s Real-backend-by-default audit at Phase 5; the mock becomes technical debt the next teammate rips out), **hardcode the response shape** (caught by `dynamic-value-discovery`, one layer deeper), and **silently stub the UI** (caught by `interaction-completeness` `unwired-control` / `placeholder-page`). All four are alerts that the slice already shipped wrong; the clean move is at the moment-of-discovery, when the frontend agent surfaces the missing endpoint as a structured backend requirement and pauses that element's work. v1.7.0 ships the explicit alternative at four enforcement points (same layered shape as v1.4.0 scope-discipline + v1.6.0 teammate-git-discipline). **(1) The new `## Frontend missing-API discipline` section in `skills/common-pipeline-conventions/SKILL.md`** is the canonical home — names the 4 anti-patterns with per-row rationale citing the existing gate that catches each; documents the right pattern (write an SR at `.architect-team/solution-requirements/SR-missing-api-<element>-<ts>.json` with `origin.kind: "missing-api-for-frontend-element"`, pause that element's work, continue on the rest of the slice, return to wire when the orchestrator re-dispatches with the SR resolved); enumerates the SR payload shape; cross-references the three neighbor surfaces. **(2) Per-agent `## Missing-API discipline` section in `agents/frontend.md`** — the authoring side. Documents the 4 forbidden patterns with explicit MUST NOT framing, the 4-step right pattern, the SR payload shape with a complete JSON example, and a worked example for a `<UserAvatar>` component needing `GET /api/users/me` (all four wrong paths shown explicitly; the correct path shown end-to-end). **(3) Per-agent `## Missing-API SR intake` section in `agents/backend.md`** — the resolver side. Documents the 4-step intake: read SR end-to-end (the frontend has named the contract); implement per the SR; **surface the actual endpoint shape in the dispatch report** with an explicit schema diff if the contract had to change so the frontend can confirm before wiring; the frontend will confirm before wiring. **(4) Phase 2 architect brief — backend-vs-frontend ordering check in `agents/system-architect.md`** — new Core Process step + new Output field + new Hard rules entry. For each `both`-layer requirement, the architect explicitly decides between **(a) sequencing backend-first** (cite the specific reason — small feature, well-defined upfront contract, frontend would idle waiting otherwise) or **(b) authorizing the frontend to surface missing-API SRs** (the default — gets parallel work moving immediately, the SR auto-spawn closes the loop without an architectural pre-decision). **(5) The new `pending-backend` element classification in `skills/interaction-completeness/SKILL.md`** — the 5th element classification (the v0.9.x 4-class system gains a 5th). Distinct from `confirmed-stub`: `confirmed-stub` is intentional + user-authorized + NOT planned for wire-up; `pending-backend` is temporary + SR-authorized + WILL be wired once the backend ships. SR-linkage rule: the `interaction-reviewer` accepts `pending-backend` ONLY when a matching open SR with `origin.kind: "missing-api-for-frontend-element"` exists; without the SR, the element is an `unwired-control` gap (the existing rule). **(6) The new `missing-api-for-frontend-element` SR origin-kind in `skills/team-spawning-and-review-gates/SKILL.md`** + documented routing: the orchestrator dispatches the BACKEND agent FIRST with the SR as input (NOT through `diagnostic-research-team` — this is not a test failure; it is a known-shape backend requirement); on backend completion the orchestrator re-dispatches the FRONTEND agent with the SR marked `resolved`. The element's `interaction-completeness` classification flips from `pending-backend` to `endpoint-backed` once the wire-up lands. **26 new tests in `tests/test_frontend_missing_api_discipline.py`** parametrized across (4 anti-patterns × frontend agent body + canonical section) + singletons for each layer's section-exists-once + SR origin-kind verbatim + routing + cross-layer consistency. **No runtime detector in v1.7.0** — the discipline lives in the agent bodies (read at every dispatch) + the structural tests + the orchestrator-provided SR auto-spawn (the right alternative). A future v1.x may add a hook that scans frontend diffs for `page.route` mocks / hardcoded sample literals / `// TODO: wire when API ready` comments and flags missing-API automatically. **Backwards-compatible:** purely additive discipline; well-behaved frontend runs (those that didn't fake / mock / hardcode / silently stub when an API was missing) see no change. 2030 → **2056 passing** (+ 1 skipped). |
| ▸ **Teammate Git Discipline — teammates MUST NOT run destructive git operations on the shared working tree (v1.6.0)** | A real-world failure surfaced by the user in a separate session exposed a plugin-level discipline gap. Four teammates dispatched in parallel against the same working tree each ran `git stash` to verify their work against baseline; the concurrent stash + pop operations interleaved catastrophically; the reflog at end-of-run showed 10+ consecutive `reset: moving to HEAD` entries — the smoking-gun pattern for the race. Three of four teammates' work was lost; only the last writer (`TAReview`) survived. The plugin had no rule forbidding teammates from running destructive git operations, so the teammates did. v1.6.0 ships the discipline at the same four enforcement points v1.4.0 scope-discipline used. **(1) The new `## Teammate git discipline` section in `skills/common-pipeline-conventions/SKILL.md`** is the canonical home — names the 6 forbidden destructive operations (`git stash` / `git stash pop`, `git reset --hard`, `git rebase`, `git commit --amend`, `git checkout <other-branch>` / `git checkout .`, `git clean -f`) with per-row rationale; documents the heirship-app-v2 worked example with the smoking-gun reflog signature `reset: moving to HEAD` repeated 10 times; describes the right pattern (orchestrator captures `BASELINE_SHA=$(git rev-parse HEAD)` once at run start; teammates run `git diff $BASELINE_SHA -- <my-files>` for verification). **(2) Three pipeline body anti-pattern entries** — `architect-team-pipeline`, `bug-fix-pipeline`, and `mini-architect-team-pipeline` each gain a one-line entry in `## Operating rules (non-negotiable)` stamped with the v1.6.0 marker, naming the 6 forbidden ops, and pointing at the canonical section. **(3) All 27 `agents/*.md` files gain a `## Forbidden git operations` section** as a uniform 5-line block, inserted between `## Operating context (v1.0.0)` and the next H2. The block names the 6 forbidden ops, references the v1.6.0 worked example, and tells the teammate to use the orchestrator-provided `$BASELINE_SHA` from its spawn brief instead of stashing. The block is duplicated across 27 files (rather than cross-referenced via a single shared section, the way v1.4.0's scope-discipline does for `## Operating context`) for the safety win — the rule is right in front of every agent, not behind a cross-reference. ~135 lines of duplication accepted for visibility. **(4) The new `## Baseline SHA capture` sub-section in `skills/team-spawning-and-review-gates/SKILL.md`** documents the orchestrator-side mechanics. The capture runs at pipeline entry (Phase −2 prelude for main pipeline; Phase B−1 entry for bug-fix; Phase M0 entry for mini) BEFORE the first teammate is dispatched. The SHA is persisted to `<workspace>/.architect-team/intake-state.json` as `baseline_sha` AND carried in every teammate's spawn brief at `<workspace>/.architect-team/teammates/<teammate>.json` (extending the v0.9.13 manifest schema with a `baseline_sha` field). Teammates substitute `git diff $BASELINE_SHA -- <my-files>` for `git stash` everywhere they would have stashed — the operation is read-only on shared state, safe under concurrent invocation by multiple teammates. **265 new tests in `tests/test_teammate_git_discipline.py`** parametrized across (6 forbidden ops × canonical section) + (3 pipelines × 2 assertions) + (27 agents × 4 assertions) + (27 agents × 5 outside-section ops) + singleton tests for the canonical section's existence + reflog signature + worked example + cross-references. **No runtime detector in v1.6.0** — the discipline lives in the agent bodies (read at every dispatch) + the structural tests + the orchestrator-provided `$BASELINE_SHA` (the right alternative to stashing). A future v1.x may add a hook trapping destructive `git` invocations by teammate processes; another candidate is worktree-per-teammate dispatch (each teammate spawned into its own sub-worktree) as the structural fix. v1.6.0 ships the discipline first; structural fixes can ship later. **Backwards-compatible:** purely additive discipline change; well-behaved teammates already comply. 1765 → **2030 passing** (+ 1 skipped). |
| ▸ **Dispatch-Mode Observability — every `/architect-team` family invocation now prints a banner naming AGENT TEAMS vs SUBAGENTS (fallback) as its FIRST user-visible action, with WHY surfaced in the fallback case (v1.5.0)** | The user's direct question — *"how do I know if a team is deployed via agent teams vs subagents, can we show an indicator"* — exposed a real observability gap. v1.0.0 made the dispatch-mode decision SILENT: it landed in `.architect-team/intake-state.json` but no user-visible signal surfaced. Users had to grep JSON or trust that the mode they expected was the mode they got. v1.5.0 ships three observability pieces. **(1) Startup banner via the new `format_dispatch_banner()` helper in `scripts/setup/teams_mode.py`** — stdlib-only, mirrors `is_teams_mode_available()`'s parameter shape, returns a multi-line box-drawn banner naming **AGENT TEAMS** (when env + version + flag qualify) or **SUBAGENTS (fallback)** (with a `Reason:` line). The reason diagnosis probes in priority order: `--no-teams` flag → version < 2.1.32 → env-and-settings-unset → defensive fallback. Each of the 3 pipeline-driving slash commands (`/architect-team`, `/architect-team:bug-fix`, `/architect-team:mini`) gains a new `## Dispatch mode banner (v1.5.0) — runs first` section at the very TOP of the body, BEFORE the v1.3.0 auto-cleanup section and BEFORE argument parsing — so the banner is genuinely the FIRST line the user sees. Polyglot Python invocation pattern + best-effort discipline: a subprocess failure surfaces a one-line note and the run continues. **(2) New `/architect-team:status` command** (13th in the plugin) — pure read-only observability utility that reports 4 sections: (a) dispatch mode banner; (b) active `architect-team/*` worktrees via `git worktree list`; (c) open SR count + paths under `.architect-team/solution-requirements/`; (d) last completed run (most recent file under `.architect-team/runs/`). Mirrors the v1.3.0 `/architect-team:cleanup-worktrees` shape — explicit user-facing utility for asking *"what's happening with the plugin right now?"* without starting a new pipeline run. **(3) `Dispatch-Mode: <teams\|subagents>` commit-trailer** added to all 3 pipeline SKILL.md bodies' Phase 8 / B8 / M7 commit-message templates, ABOVE the existing `Co-Authored-By` trailer. Value derived from `intake-state.json`'s `dispatch_mode` field (recorded at startup per v1.0.0). Makes `git log --format=%(trailers)` queryable for archeological "which mode produced this commit?" questions without grepping JSON. In mini's M7 the trailer sits alongside the existing `Mini-Run: <slug>` trailer. **20 new tests in `tests/test_dispatch_banner.py`** covering both banner shapes, each of the 4 fallback reasons (env-unset, version-too-low, --no-teams, settings-and-env-unset), banner visual-signal (box-drawing chars), 3 pipeline slash command structural assertions (parametrized × 2 — section exists + precedes auto-cleanup + body documents banner as informational), 3 pipeline body commit-trailer assertions, the status command frontmatter + body sections, and the version-bump consistency check. `tests/test_commands.py::EXPECTED_COMMANDS` gains `"status"`. **Backwards-compatible:** purely additive observability. The banner is informational, never gating — subprocess failure NEVER blocks the run. The dispatch-mode decision itself is unchanged from v1.0.0. 1744 → **1765 passing** (+ 1 skipped). |
| ▸ **Scope Discipline — agents using this package must NOT silently narrow the user's prompt at intake (v1.4.0)** | A user-reported plugin-level discipline gap. In a separate session working on a Title Agency flow, the user said *"match the oracle"* — the agent interpreted the verb `match` as *"enrichment + hardcoded data purge"* and documented the visual rebuild as queued for subsequent runs. The agent had correctly identified the gap (visual parity wasn't done) but had silently reframed the work into a narrower interpretation rather than executing what the user literally asked for. The user surfaced this with: *"its a problem with agents based on this package. we need to correct these."* The v0.9.36 anti-deferral discipline forbade the MID-RUN version of this pattern (agent finds a bug → defers to next run without authorization); v1.4.0 extends the forbiddance to INTAKE. **The canonical home is the new `## Scope discipline` section in `skills/common-pipeline-conventions/SKILL.md`** — names the anti-pattern (*silently narrowing the prompt's scope*), contrasts with v0.9.36 (same shape, different timeline), enumerates the **6 parity-implying verbs** (`match`, `rebuild`, `mirror`, `parity`, `make like`, `replicate`) each implying visual + structural + behavioral parity (NOT data-only or partial), classifies scope-narrowing as a DOMAIN gate (per the v0.9.21 carve-out — fires regardless of `--proposal-first`), instructs the agent to surface the scope decision via `AskUserQuestion` BEFORE starting work with example wording (*"You said 'match the oracle.' I read this as visual + structural + behavioral parity. Is this run scoped to: (a) full parity rebuild, or (b) data-binding only with visual rebuild deferred?"*), and enumerates the four explicit forbidden patterns (queued-for-next-runs / phase-1-of-N / unilateral-split / narrow-then-document). **`agents/prompt-refiner.md` gains a 6th grading axis `scope-fidelity`** measuring whether the refined prompt scopes narrower than the original prose reasonably implies; a flagged value (score ≤ 6) is a DOMAIN gate — the orchestrator MUST surface the scope-clarification question before the refinement loop proceeds, and it is always the highest-priority question of the iteration. Weight redistribution: v1.3.0 (Clarity 0.25 + Scope 0.20 + Acceptance 0.25 + Grounding 0.20 + Conflict 0.10) → v1.4.0 (Clarity 0.20 + Scope 0.18 + Acceptance 0.20 + Grounding 0.17 + Conflict 0.08 + ScopeFidelity 0.17), summing to 1.0. **`skills/proposal-refiner/SKILL.md` Phase R2 updated** to document the 6-axis grade table + the new weights + the new schema. **`agents/bug-classifier.md` gains an `## Action-verb interpretation (v1.4.0)` section** — when the prompt contains a parity-verb AND the classifier's reading is narrower than visual + structural + behavioral parity, the classifier MUST return `kind: unclear` with a scope-clarifying question. A `bug` or `feature` verdict on a parity-verb prompt with silently narrowed interpretation is a scope-narrowing failure, not a routing decision. **`agents/system-architect.md` Master Review Audit mode gains a scope-narrowing check at step 4** — the verdict JSON gains a `scope_fidelity_finding` block (`original_prompt_verb`, `delivered_scope`, `literal_scope`, `narrowing_detected`, `narrowing_authorized`, `authorization_quote`, `authorization_source`, `finding`); a populated `finding` is a verdict-failure condition. **`agents/system-architect.md` Phase 2 architect brief Output section gains a `Scope check` field** documenting the verification BEFORE the architect finalizes the recommendation. **3 pipeline body anti-pattern entries** added — `architect-team-pipeline`, `bug-fix-pipeline`, `mini-architect-team-pipeline` each reference the canonical section; the bug-fix pipeline also gains a new row in its `## Anti-patterns to reject` table covering the parity-verb scope-narrowing case explicitly. **35 new tests in `tests/test_scope_discipline.py`** covering all the structural assertions (parametrized across the 6 verbs and the 3 pipeline bodies). **No runtime hook in v1.4.0** — the discipline lives in agent bodies (read at every dispatch) + structural tests (asserting the discipline is documented). A future v1.x may add a hook that diffs the refined prompt against the original to flag narrowings automatically. **Backwards-compatible:** purely additive discipline change; existing flows continue to work; future runs benefit from explicit scope-surfacing. 1709 → **1744 passing** (+ 1 skipped). |
| ▸ **Auto-cleanup of merged worktrees — every `/architect-team` family invocation sweeps prior runs' merged worktrees first (v1.3.0)** | The direct follow-up to v1.2.0. v1.2.0 made worktree CREATION automatic but explicitly left CLEANUP as a manual user step — the Phase 8 / B8 / M7 success report ended with a recommendation (*"To clean up: `git worktree remove <path> && git branch -d architect-team/<slug>`"*) and the user decided when to act. Predictably the user didn't, and after 10 runs the filesystem held 10 worktrees, 9 of which had merged-and-forgotten branches. The user's follow-up ask was direct: *"we need auto cleanup so we resolve trees when branches are merged in."* v1.3.0 ships it via two auto-cleanup trigger points. **Trigger 1 — start of every `/architect-team` family invocation:** `/architect-team`, `/architect-team:bug-fix`, and `/architect-team:mini` each fire `cleanup_merged_worktrees()` as their FIRST action, BEFORE argument parsing, BEFORE refinement, BEFORE the v1.2.0 auto-worktree creation. A `git fetch origin main` runs first (best-effort) so `origin/main` is current, then the helper walks `git worktree list --porcelain`, identifies pairs whose branch starts with `architect-team/`, runs `git merge-base --is-ancestor <branch> origin/main` against each, and removes the merged ones via `git worktree remove` + `git branch -d`. The user sees a brief one-line note listing the paths cleaned (or *"(no merged worktrees to clean)"*). **Trigger 2 — end of mini Phase M7 after green merge:** the mini pipeline just merged its own branch to main, so it immediately cleans up its own worktree via `cleanup_run_worktree(Path.cwd(), remove_branch=False)`. Combined: mini runs always auto-clean themselves; `/architect-team` + `/architect-team:bug-fix` runs auto-clean any LEFTOVER merged worktrees from prior runs at the start of the next run. **The `exclude_current=True` safeguard:** the cwd's worktree is NEVER auto-removed by trigger 1, even on a re-entry case where its branch is already merged. The two new helpers in **`scripts/setup/worktree_lifecycle.py`** (extending the v1.2.0 module to 6 public functions total): `list_merged_architect_team_worktrees(against="origin/main", exclude_current=True) -> list[Path]` and `cleanup_merged_worktrees(against="origin/main", dry_run=False) -> list[Path]` — both stdlib only (`subprocess` + `pathlib` + `typing`). Non-architect-team branches are NEVER touched regardless of merge state. **Squash-merged branches are NOT auto-detected** — `git merge-base --is-ancestor` doesn't catch them (different SHA); the safer side of the trade-off (false-negative > false-positive auto-delete). Use the new explicit command to clean them manually. **The new `/architect-team:cleanup-worktrees` command (12th in the plugin)** exposes the same helper for on-demand invocation. Flags: `--dry-run` previews paths that WOULD be cleaned without filesystem changes; `--against <ref>` overrides the default `origin/main` comparison reference. Use this when you want to clean now without starting a new pipeline run. **Best-effort discipline:** every auto-cleanup invocation is best-effort — failures surface a one-line note but NEVER block the new run; per-worktree failures don't stop cleanup of the others. **The new `### Auto-cleanup (v1.3.0)` sub-section** in **`common-pipeline-conventions/SKILL.md`**'s `## Auto-worktree lifecycle` section is the canonical home of the rule: the two trigger points, the `exclude_current` safeguard, the merged-branch detection mechanism, the squash-merge limitation, the `--dry-run` capability, the best-effort discipline. The 3 pipeline-driving slash commands cite this section as the canonical rule source. **Mini Phase M7** gains a new `### Cleanup the run worktree (v1.3.0)` step between the existing branch-delete and `/compact` prompt — calls `cleanup_run_worktree` with `remove_branch=False` (the branch is already gone). **6 new tests** in `tests/test_worktree_auto_cleanup.py` (merged-branch identification, exclude_current safeguard true/false, non-architect-team branches ignored, cleanup removes filesystem, dry_run preview leaves filesystem untouched, end-to-end cleanup-only-removes-merged) exercise the helpers against real `git init` + `git worktree add` fixtures with `origin/main` configured via a self-remote — no git mocks. **Backwards-compatible:** no opt-out flag in v1.3.0 — the cleanup is desirable by design. 1702 → **1709 passing** (+ 1 skipped). |
| ▸ **Auto-worktree lifecycle — every `/architect-team` family invocation creates a fresh worktree by default (v1.2.0)** | The natural follow-up to v1.1.0. v1.1.0 made the cross-session state-coordination layer worktree-aware (the lock dir + MemPalace now resolve to the MAIN worktree when called from a sibling worktree) but left worktree CREATION as a manual user step. The user's follow-up ask was direct: *"always on when using architect team."* v1.2.0 ships it — `/architect-team`, `/architect-team:bug-fix`, and `/architect-team:mini` now auto-create a fresh worktree at `<parent-of-repo>/<repo-name>-<slug>/` on branch `architect-team/<slug>` before invoking the pipeline skill. The user's main checkout stays on whatever branch they were on; the run is self-contained on its own branch in its own working tree; concurrent runs are filesystem-isolated by default with zero setup. The existing Phase 8 default-branch-guard (`architect-team/<change-name>`) is now a worktree from the start of the run rather than only a branch at commit time. The new **`scripts/setup/worktree_lifecycle.py`** helper (v1.2.0) exposes 4 stdlib-only functions (extended to 6 in v1.3.0 with the auto-cleanup pair): `create_run_worktree(slug, base_branch="main", parent_dir=None) -> Path` (creates the worktree; on collision appends `-2`, `-3`, ... to find an unused slug; raises `RuntimeError` with an actionable message on parent-dir-not-writable / base-branch-missing / `git worktree add` failure); `cleanup_run_worktree(worktree_path, remove_branch=False) -> None` (`git worktree remove <path>` with optional `git branch -d architect-team/<slug>`; idempotent on already-gone worktree; falls back to `--force` removal once before raising); `current_worktree_is_run() -> bool` (`git rev-parse --abbrev-ref HEAD` starts with `architect-team/` — used by the slash commands to detect re-entry and skip creating a nested worktree); `current_run_slug() -> str | None` (extracts the slug from the branch name). The split from v1.1.0's `worktree_paths.py` is intentional — `worktree_paths.py` is pure read-only resolution (`shared_state_dir()` / `run_state_dir()` / `is_worktree()`); `worktree_lifecycle.py` is side-effecting subprocess work (creation / cleanup / detection). Keeping them in separate modules preserves the v1.1.0 module's pure-resolution contract. The 3 slash command bodies each gain a new `## Auto-worktree creation (v1.2.0)` section between argument parsing / refinement and skill invocation: detect re-entry via `current_worktree_is_run()` → skip; detect `--no-worktree` (or its natural-language equivalents — *"no worktree"*, *"don't create a worktree"*, *"single tree"*, *"in place"*, *"in current tree"*) → skip; otherwise derive a slug, invoke `create_run_worktree()` via the polyglot `python3 -c '...' || python -c '...'` pattern, chdir into the new worktree, emit a one-line note to the user, and proceed to skill invocation. On creation failure the error surfaces verbatim and the run STOPS — no silent fallback to current checkout. **The 7 utility commands** (`/architect-team:visual-qa`, `/architect-team:editability-audit`, `/architect-team:refine-prompt`, `/architect-team:memory`, `/architect-team:mempalace-install`, `/architect-team-setup`, `/architect-team:mini-review-sweep`) do NOT get the auto-worktree step — those are read-mostly inspection / configuration / replay commands, not feature-delivery pipelines. **Cleanup is now AUTOMATIC as of v1.3.0** (see row above) — the v1.2.0 manual recommendation at Phase 8 / B8 / M7 success still appears, but the next run's auto-cleanup sweeps merged worktrees from prior runs without user action. The new `## Auto-worktree lifecycle` section in **`common-pipeline-conventions/SKILL.md`** documents the trigger, the re-entry detection, the opt-out, the path + branch convention, the collision handling, and the cleanup semantics with a full default-run + re-entry + opt-out shell-example trio; the 3 slash command bodies cite this section as the canonical rule source. 8 new tests in `tests/test_worktree_lifecycle.py` (`create_run_worktree` happy path + collision handling; `current_worktree_is_run` True / False; `current_run_slug` extracts / None; `cleanup_run_worktree` removes worktree + optionally branch) exercise the helper against real `git init` + `git worktree add` fixtures, no git mocks. **Backwards-compatible:** v1.1.0 users who liked single-tree mode pass `--no-worktree` and get exactly v1.1.0 behavior. 1694 → **1702 passing** (+ 1 skipped). |
| ▸ **Worktree-aware state resolution — true filesystem isolation + shared lock + shared MemPalace for concurrent sessions (v1.1.0)** | A surgical follow-up to the v1.0.0 ship that closes a structural gap in the cross-session coordination layers. v1.0.0 introduced `.architect-team/locks/` JSON locks + MemPalace cross-session memory, both intended to coordinate two concurrent `/architect-team` invocations on the same project. But both resolved via `git rev-parse --show-toplevel`, which **in a git worktree returns the WORKTREE's own path** — so each worktree got its own locks dir + its own MemPalace, **defeating the cross-session coordination intent**. The right primitive for filesystem isolation between concurrent sessions IS git worktrees (one working tree per session, one branch per session, no clobbering); v1.1.0 fixes the state-resolution layer so worktree-based sessions get true filesystem isolation AND retain shared lock arbitration + shared MemPalace context. **The 3-layer model now documented:** (1) **filesystem isolation = git worktrees** — each session opens its own worktree via the upstream `superpowers:using-git-worktrees` skill, edits + tests + commits in its own working tree, on its own branch, with zero collision risk at the FS layer; (2) **architectural coordination = `.architect-team/locks/` resolved to the MAIN worktree** — each pipeline Lead acquires a JSON file-scope lock before dispatching teammates, two Leads in two worktrees see the same lock dir (overlapping scope → `blocked`, disjoint scope → parallel); (3) **context sharing = MemPalace resolved to the MAIN worktree** — both sessions' wake-up sees the same prior-run context, both sessions' mines write to the same palace. **The state split:** `locks/` + `.mempalace/` + `run-history/` live in the MAIN worktree (`shared_state_dir()`); `reviews/` + `teammates/` + `handoffs/` + this-run's `openspec/changes/<slug>/` live in the CURRENT worktree (`run_state_dir()`). Each worktree owns its own per-run state — nothing pollutes across worktrees — while the coordination + context layers are properly shared. The resolution primitive is the new **`scripts/setup/worktree_paths.py`** — three stdlib-only functions: `shared_state_dir() -> Path` (main worktree's `.architect-team/`, via `git rev-parse --git-common-dir`), `run_state_dir() -> Path` (current worktree's `.architect-team/`, via cwd), `is_worktree() -> bool` (compares `--git-dir` vs `--git-common-dir`). Best-effort: any git probe failure falls back to cwd, never raises. **`hooks/locks.py`** now resolves its default `locks_dir` through `shared_state_dir() / 'locks'` — single-session users (no worktrees) see ZERO behavior change because the resolution is degenerate in a non-worktree clone; worktree users automatically get shared coordination. The explicit `locks_dir=` parameter is preserved verbatim — all 17 v1.0.0 lock tests pass unchanged. **`mempalace-integration/SKILL.md`** wake-up section gains a sentence noting the palace path resolves through `shared_state_dir() / '.mempalace' / 'palace'`; flow unchanged. **`common-pipeline-conventions/SKILL.md`** gains a `## Running in parallel sessions` section documenting the 3-layer model + the shared-vs-run split + a concrete two-session shell-sequence example + a pointer to `superpowers:using-git-worktrees` for worktree lifecycle. 6 new tests in `tests/test_worktree_state_resolution.py` (`is_worktree` true/false, `shared_state_dir` resolution from main + from a real `git worktree add`-created worktree, `run_state_dir` per-worktree differentiation, cross-worktree lock integration test proving the shared-resolution wiring); 1688 → **1694 passing** (+ 1 skipped). Backwards-compatible — no env var, no flag, no opt-in. Out of scope: cross-clone coordination (two separate clones on disk don't coordinate via this layer; intentional). |
| ▸ **Agent Teams as the default dispatch mode — long-lived 1M-context teammates with a shared task list (v1.0.0)** | The architecture the plugin should have shipped with. Converts the entire pipeline from ephemeral `Agent`-tool dispatches (one-shot subagents that drop context after every return — every phase re-onboarded every role, and the user's repeated original ask of *"can the architect listen for new requests mid-flow and marshal them in parallel?"* was structurally impossible because there was no listening point) to Claude Code's experimental **Agent Teams** primitive. A team is a Lead session plus N long-lived teammates, each with its own **1M context window**, a **shared task list** with dependencies, and **`SendMessage`** for direct teammate-to-teammate messaging. The Lead = the architect = the session running `/architect-team` — it owns ALL dispatch decisions, ALL architectural decisions, and the shared task list. Teammates execute assigned tasks within their 1M context; they do NOT spawn sub-teams (per the Agent Teams docs' "no nested teams" constraint), do NOT make architectural decisions, do NOT route work to other teammates. **Every nested-team pattern in the pipeline flattens** — the previous `task-reviewer ×3`, `editability-reviewer ×3`, `interaction-reviewer ×3`, `integration-explorer ×3 + master-synthesizer`, `visual-capture + visual-analyzer`, `diagnostic-researcher ×3`, `codebase-map-reviewer ×3`, `flow-explorer ×3`, `flow-executor ×3` convergences all become Lead-owned task creations in the shared list (or Lead-direct dispatches in subagents mode). The Lead is the listening point the user has been asking for; the shared task list IS the parallel-marshalling primitive. **Cross-session parallelism via the new `.architect-team/locks/` layer** — each Lead claims its file scope via a JSON lock file before dispatching teammates; two concurrent `/architect-team` invocations in separate Claude Code sessions queue (overlapping scope) or proceed truly parallel (disjoint scope) based on a path-glob intersection check. Stale-lock detection (TTL-based, 4h default) auto-releases abandoned locks; malformed lock files are treated as stale. The four lock primitives live in **`hooks/locks.py`** (`acquire_lock` / `release_lock` / `detect_stale` / `globs_intersect`) — stdlib-only, reuses the non-overlapping-file-scope discipline from `team-spawning-and-review-gates`. **Hooks gain teams-mode triggers** — `hooks/review-gate-task.py` and `hooks/teammate-idle-check.py` now handle both `PostToolUse(TaskUpdate)` / `SubagentStop` (subagents mode) AND `TaskCompleted` / `TeammateIdle` (teams mode) by detecting the payload's event type and branching internally to the SAME enforcement code (review evidence schema v6, exit code 2 = block + feedback). The Stop hook (`pipeline-completion-audit.py`) is unchanged — same trigger in both modes. The mode-detection helper **`scripts/setup/teams_mode.py`** centralizes the `is_teams_mode_available(env, settings_path, claude_cmd, flag_no_teams) -> bool` decision: checks the env var OR `~/.claude/settings.json`, checks `claude --version` ≥ 2.1.32, honors the `--no-teams` flag. Falsy / malformed / missing inputs all degrade gracefully to subagents mode. **All 27 agent bodies** get a uniform small rewrite from *"You are invoked for one task"* to *"You are a long-lived teammate in an architect-team run. The Lead assigns tasks via the shared task list (teams mode) or dispatches you per-task (subagents mode). Stay in your role across multiple tasks within this run."* Frontmatter (`name`, `description`, `tools`, `model`, `color`) is untouched — `tools` and `model` carry over to teammates per the Agent Teams docs; `skills` and `mcpServers` do NOT carry over but teammates load them from project + user settings anyway, so existing skill access is preserved. **Each pipeline SKILL.md gains a `## Dispatch mode` section** naming the env var, the `2.1.32` requirement, the `--no-teams` flag, and the teams-mode primitives (`Spawn teammate using <role> agent type`, `SendMessage`, `~/.claude/tasks/<slug>/` for the shared task list). **`/architect-team-setup`** + `scripts/setup/setup.py` extend to check `claude --version` ≥ 2.1.32 and to check / offer-to-add the experimental flag to `~/.claude/settings.json` with explicit user consent (never written without it). New `--check-only` reports status without modifying any user files; `--no-prompt` skips the settings.json write even when the flag is missing. **Migration: none required.** Users without the flag continue running exactly as on v0.10.0 (subagents mode). Users with the flag get teams mode automatically; `--no-teams` on any of the three pipeline commands forces subagents mode if you hit experimental-flag instability. ~210 net-new tests across 7 new files (`test_teams_mode.py`, `test_locks.py`, `test_setup_teams_checks.py`, `test_hooks_trigger_split.py`, `test_dispatch_mode_section.py`, `test_no_nested_teams_in_skills.py`, `test_agent_teammate_framing.py`); 1417 → **1631 passing** (+ 1 skipped). |
| ▸ **Mini pipeline — rapid feature changes with single-architect drive + auto-merge to main on green QA (v0.10.0)** | A faster sibling to the full `architect-team-pipeline` for the everyday case: a `≤5`-acceptance-criteria change against a familiar codebase where the maps are fresh and the heavyweight reconciliation / master-review / six-team Phase 5 gates are overkill. v0.10.0 ships the new **`mini-architect-team-pipeline`** skill — 9 phases **M0 → M8** — plus a new **`/architect-team:mini`** command and a follow-up **`/architect-team:mini-review-sweep`** command that replays the heavyweight gates against a batch of recent mini-runs when the user wants them. Phase flow: **M0 Intake** (the same two input forms as the main pipeline — folder or plain-language prose); **M1 Maps freshness check** (cached maps with single-pass refresh only when stale; no ×3 reviewer convergence); **M2 Architect draft** (one `system-architect` produces the full 5-artifact OpenSpec bundle — proposal/design/spec/tasks/coverage-map — in a single pass, with a **mandatory `## QA Guidance` section** in proposal.md enumerating ≤5 ACs, unit + integration targets, ≤3 Playwright flows each binding to an AC by ID); **M3 Self-confirm loop** (the same architect re-reads its own bundle against the prompt + maps; edits in place; iterates to a fixed point, capped at 3 passes); **M4 Parallel dev with dev↔dev cross-review** (the existing `frontend` + `backend` agents work non-overlapping slices and cross-review each other's v6 evidence files — no separate task-reviewer team; reviewer ≠ teammate invariant already holds because the reviewer is the OTHER dev); **M5 mini-qa** (the new **`mini-qa`** agent — opus — reads `## QA Guidance` as authoritative scope, runs unit tests, runs integration tests against the live dev API per `dev-api-integration-testing`, authors **≤ 3 Playwright user-flow tests bound to ACs**, deploys to the dev environment, runs Playwright against the **live dev URL**, writes a per-cycle verdict at `.architect-team/mini/<slug>/qa-verdict-cycle-<N>.json`); **M6 Verdict gate** (one of `green` / `red-with-evidence` / `env-failure` — `green` proceeds to M7, `red-with-evidence` proceeds to M8 with cycle++, `env-failure` halts without consuming a cycle); **M7 Auto-merge to main** (only on `green`; single-pass doc-currency, commit with the structured **`Mini-Run: <slug>`** trailer, fast-forward or rebase main, push, delete branch; conflict halts with `merge-conflict.json`; safety rails forbid `--no-verify` and `--force`; `--no-merge` falls back to current-branch semantics); **M8 Re-eval loop and escalation** (on `red-with-evidence`, the architect reads `responsible_role_on_red` from the verdict, edits the OpenSpec bundle in place, and re-dispatches; cycle cap = 3; on cycle 4 the pipeline writes a `.architect-team/mini/<slug>/escalation/` folder and re-spawns the full **`/architect-team`** with that folder as REQ_DIR, continuing on the same working branch). Every mini commit carries a `Mini-Run: <slug>` trailer (extracted via `tests/helpers/mini_run_trailer.py` with Git interpret-trailers semantics, last-wins on duplicates) so the new **`/architect-team:mini-review-sweep`** command can replay the heavyweight gates (`interaction-completeness`, `editability-completeness`, `visual-fidelity-reconciliation`, `test-completeness-verifier`, `dev-api-integration-testing` audit) against the last `--limit N` mini-runs since `--since <ref>`, converting drift to solution requirements that the existing dev loop picks up. The cross-review discipline at M4 is structurally backed by **`tests/test_mini_review_gate_dev_cross_check.py`** — confirms the existing v6 review-evidence schema accepts dev-agent cross-review (frontend reviews backend, backend reviews frontend) without modification. Use mini when: ≤5 ACs, familiar codebase, maps fresh, comfort with auto-merge to main. Use full `/architect-team` when: scope larger, maps stale, design contract changes, or you want PR-style review up front. Both pipelines run from the same intake-and-mapping foundation and write to the same MemPalace wing — switching is free. |
| ▸ **Bug-fix testing enforcement + anti-deferral discipline (v0.9.36)** | Two user-reported structural defects. **(1) Testing enforcement:** the bug-fix pipeline's B1 replication and B6 QA replay were trust-based markdown — no proof tests were executed. v0.9.36 mandates **verdict files** at `.architect-team/bug-fix/<slug>/b1-replication-verdict.json` and `b6-qa-replay-verdict.json` with execution-proof fields (`artifact_executed`, `artifacts_executed_against_live_dev`, `symptom_gone_end_to_end`, `code_path_witness_passed`). The `pipeline-completion-audit` hook gains `_audit_bug_fix_testing()` and blocks the run without valid verdicts. "The test would pass" is no longer accepted — the test must actually run. **(2) Anti-deferral:** the pipeline was clustering identified bugs and deferring some to "separate focused runs" because "depth would suffer." Both pipelines now carry an explicit operating rule: **fix every issue identified in the run** — the only legitimate deferral is an explicit user instruction. Four new anti-patterns in the bug-fix table reject "merits a focused run", "describe instead of run", "needs investigation later", and "skip this cluster." 43 new tests; 1300→**1343** passing (58 test files). |
| ▸ **Email Testing Audit — best-in-class refinements to the v0.9.34 email-testing discipline (v0.9.35)** | A comprehensive architecture + wiring + test-coverage + documentation-currency audit against both internal plugin conventions and external industry best practices (Mailpit, Mailtrap, MailSlurp, Ethereal). **Skill refinements:** Mailpit search API (`/api/v1/search`) replaces client-side filtering (eliminates the 10-message ceiling); pre-test `DELETE /api/v1/messages` cleanup prevents stale-email matches; `docker rm -f mailpit-test` before `docker run` handles container collisions from interrupted teardowns; new redirect-chain-handling section for click-tracking services (SendGrid, Mailgun, Postmark); language-specific indicator expansion (Python/Go/Java/Ruby/PHP alongside Node.js); Windows PowerShell `Start-Process` binary fallback. **Test coverage:** 38 new tests (55→66 structural, 37→64 template/flow); 1262→**1300** passing. **Doc currency:** CODEBASE_MAP.md refreshed from v0.9.29→v0.9.35 (all counts, architecture diagram, module guide); INTEGRATION_MAP.md gains Mailpit integration entry. |
| ▸ **Email Testing Discipline — automatic Mailpit-based email flow verification across all QA agents (v0.9.34)** | A cross-cutting skill that closes a testing blind spot: email-dependent user flows (invite → sign-up, password reset → new password, notification click-throughs) were previously untestable in dev environments without a real inbox. v0.9.34 provides a four-phase discipline (E1-E4) that existing QA agents (`bug-replicator`, `flow-executor`, `integration`) consume **automatically** when their work slice touches email templates or email-sending code. **E1** detects email surface via file-path indicators (templates in email-related paths), import indicators (`nodemailer`, `@sendgrid/mail`, `ses`, `postmark`, `mailgun`, `resend`), and function-call indicators (`sendMail`, `sendEmail`, `sendInvite`, etc.). **E2** provisions **Mailpit** (local SMTP trap, zero external dependencies, zero config) via Docker or binary fallback, routes the dev environment SMTP through `localhost:1025`, and wires mandatory teardown. **E3** reads the email template source BEFORE triggering the send to understand the email's purpose, polls Mailpit's REST API to capture the rendered email, extracts every `<a href>` link, and classifies each by purpose (invite-accept / password-reset / email-verification / unsubscribe / calendar-event / destructive-action / general-link) — then cross-checks against the template to flag missing or unexpected links. **E4** navigates Playwright to every testable link and completes the full user flow each link initiates (invite → fill sign-up form → submit → account active; reset → enter new password → submit → success; calendar → download `.ics` → validate SUMMARY/DTSTART/DTEND/ORGANIZER; delete → confirm → resource removed). Every link gets tested — not just the primary CTA. Per-link verdicts (pass/fail/env-failure) aggregate to an overall verdict. **No new agent, no new command** — the skill is cross-cutting, like `playwright-user-flows` or `dynamic-value-discovery`. Projects may override Mailpit via a `## Email Testing` section in `design.md` naming a different provider (Mailtrap, MailSlurp). Wired into `bug-fix-pipeline` Phase B2, `architect-team-pipeline` Phase 5, and `ux-test-builder` Phase U5/U6. ~123 new tests across 3 new test files; 1139 → 1262 passing (57 test files). |
| ▸ **Proposal Refiner — conversational pre-pipeline prompt refinement with codebase-grounded clarity grading (v0.9.33)** | A new upstream capability the user explicitly asked for: *"a proposal refiner that takes in a text prompt and helps the user clarify and enhance the prompt in a way that is optimized for our architect-team pipelines (all types)... reviews it, clarifies it, asks the user to read and converse until satisfied. The agent can leverage knowledge of all codebases through the codemaps etc.. to help refine and make prompt strategy more effective and will grade it for the user to help them understand if it is clear enough."* v0.9.33 ships exactly that: a new **`proposal-refiner`** skill (6 phases R1-R6) + a new **`prompt-refiner`** agent (opus, read-only on source, bounded Write to `.architect-team/refined-prompts/`) + a new standalone command **`/architect-team:refine-prompt`** + automatic upstream invocation in all three existing pipeline commands (`/architect-team`, `/architect-team:bug-fix`, `/architect-team:ux-test`) when their input is free-text prose. The skill conversationally refines a prompt by (1) loading the codebase maps (CODEBASE_MAP, ROUTE_MAP, DESIGN_MAP, INTERACTION_INTUITION_MAP, INTEGRATION_MAP) + a read-only MemPalace wake-up for prior-run context; (2) grading the prompt on five axes — **Clarity / Scope / Acceptance / Codebase grounding / Conflict** — each 1-10 with verbatim-prompt-quoting rationales; (3) computing a 0-100 weighted score mapped to letter grade A-F; (4) generating 2-5 codebase-anchored clarifying questions per iteration (every cited route / endpoint / file must exist in the loaded maps — fabrication is forbidden); (5) iterating with the user (5-iteration ceiling) until they confirm `ship it` / `proceed` / `good` OR the grade reaches A; (6) writing a structured refined-prompt markdown with `## Goal` / `## Scope (in)` / `## Scope (out)` / `## Acceptance criteria` / `## Codebase touchpoints` / `## Open questions` / `## Refinement log`. Two output modes: **pipeline-integrated** (the downstream pipeline rebinds `$REQ_DIR` to the refined markdown and proceeds to Phase −2) and **standalone** (`/architect-team:refine-prompt` — writes the markdown and exits, no downstream phases). Classified as a **DOMAIN gate** (v0.9.21 carve-out) — the user-confirmation step IS the deliverable; `--no-refine` is the explicit opt-out. **97 new tests** (across 4 new test files + inventory updates in `test_skills.py` / `test_agents.py` / `test_commands.py`); 1042 → **1139** passing. |
| ▸ **Full generalization of the wrong-code-path-witness discipline across all 3 Playwright-running sites (v0.9.32)** | A user-flagged generalization gap on v0.9.31. *"the fixes you made were entirely generalizable right?"* — honest audit answer was **no**: v0.9.31 added the witness only at Phase B6's `qa-replayer`; the underlying failure mode (*"a Playwright test passes via an unintended code path"*) lived unfixed at three other sites. v0.9.32 closes all of them: (1) **Phase B2 `bug-replicator`** gets a **selector witness** — `.toBeVisible()` + `.toBeEnabled()` + a disambiguating role/attribute check before every action call — catching the failure at AUTHORING time before any cycle is wasted; (2) **Phase 5 `integration` agent** gets the **code-path execution witness** adapted to feature tests (reads `implementing_commits[]` from the coverage map instead of the fix's git diff) with the new verdict **`feature-tests-did-not-exercise-implementation`** routing teams back to test re-authoring; (3) **Phase U6 `flow-executor`** gets a **flow-effect witness** — a UX-domain variant that verifies the U5-authored `expected_user_effect` block (DOM state change, network request, URL change, or console sentinel) actually occurred; a flow that passes Playwright's assertion but didn't achieve the persona's intent now fails with `failure_reason: "flow-effect-not-witnessed"` and routes through bug-fix as `origin.kind: "flow-effect-gap"`. The B2 selector witness is the EARLIEST gate (catches at authoring time); B6 / Phase 5 / U6 witnesses are LATER gates (catch at verification time). Both layers needed. 14 new structural tests (4 + 4 + 6 across the three agents' test files); 1028 → **1042** passing (was 1016 in v0.9.30, 924 in v0.9.29). Same honest caveat as v0.9.31 applies: tests are structural — they verify the discipline is documented and demanded at every site, but runtime correctness depends on the LLM agents applying the discipline when invoked. The failure mode is now structurally closed at every Phase-with-Playwright in the plugin. |
| ▸ **Phase B6 code-path execution witness — qa-replayer catches tests that pass via the wrong path (v0.9.31)** | A real-world QA gap surfaced by a v0.9.30 production run. Direct quote from the orchestrator's honest post-mortem on a `bug-resolved` verdict that turned out to be wrong: *"My Playwright never actually completed a Schedule click. The test's tech-selector grabbed 'Alabama' (a state filter) instead of a real tech, so the Schedule button stayed disabled — and I declared REQ-001 PASS based only on the Unschedule path's panel-stayed-open assertion. The Unschedule path goes through `handleUnschedule`; the Schedule path goes through `handleSchedule` where the fix lives. The test never invoked `handleSchedule` at all."* The qa-replayer's Step 4 (`symptom-gone-end-to-end`) verifies the user's reported symptom appears resolved, but it never asks *"did the test actually INVOKE the handler the fix touched?"* A Playwright flow with a misidentified selector can satisfy a panel-stayed-open assertion via an irrelevant code path while the fix's actual buggy handler is never called. v0.9.31 adds **Step 4.5 — code-path execution witness** to the `qa-replayer`: it identifies buggy handlers from the fix's git diff (new input #6), derives an invocation fingerprint per handler (`network_request` / `api_access_log` / `dom_state_change` / `console_sentinel`), captures observed fingerprints from the Playwright trace (`trace: 'on'` mandated) + the dev API access log, and cross-checks. The trace's network log + the access log are the witness data. New 4th verdict **`test-did-not-exercise-fix`** routes to **Phase B2** (re-author the test) with `origin.kind: "test-coverage-gap"` — distinct from `bug-still-present` (route to B3, fix is wrong) and `env-failure` (route to env diagnosis, env is wrong). Three on-trial axes now structurally distinct: FIX / TEST / ENV. Oscillation-bounded — 3 consecutive `test-did-not-exercise-fix` verdicts on the same bug escalates to the user. 12 new structural tests (8 in `test_qa_replayer_agent.py`, 4 in `test_bug_fix_pipeline_skill.py`) — total 1028 passing (was 1016 in v0.9.30). **Honest caveat:** the tests are structural; they verify the discipline is documented and demanded, not that an LLM agent runs it correctly at runtime. The mitigation is the verdict-schema mandatory `code_path_witness` field + the Hard rules forbidding skip/fabrication of the witness. |
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
┌─ SKILLS (28) ───────────────────────┬─ AGENTS (29) ─────────────────────────┐
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
│ ◇ proposal-refiner                  │ ◆ flow-executor (opus)                │
│ ◇ email-testing                     │ ◆ fix-sensibility-checker (opus)      │
│ ◇ mini-architect-team-pipeline      │ ◆ prompt-refiner (opus)               │
│ ◇ common-pipeline-conventions       │ ◆ mini-qa (opus)                      │
│ ◇ verified-agent-output (v2.0.0)   *│ ◆ oracle-deriver (opus) ★             │
│                                     │ ◆ adversarial-reviewer (opus) ★       │
├─ COMMANDS (13) ─────────────────────┴───────────────────────────────────────┤
│ ▸ /architect-team <path-to-requirements-folder | free-text prompt>          │
│ ▸ /architect-team-setup                                                     │
│ ▸ /architect-team:visual-qa [<codebase-path>]                               │
│ ▸ /architect-team:mempalace-install                                         │
│ ▸ /architect-team:memory <search|mine|status|wake-up|sweep>                 │
│ ▸ /architect-team:editability-audit [<codebase-path>]                       │
│ ▸ /architect-team:bug-fix <bug-description | requirements-folder>           │
│ ▸ /architect-team:ux-test <persona + objectives + --site or --dev>          │
│ ▸ /architect-team:refine-prompt <free-text prompt>      (standalone refine) │
│ ▸ /architect-team:mini <requirements-folder | free-text prompt>             │
│ ▸ /architect-team:mini-review-sweep [--since <ref>] [--limit <N>]           │
│ ▸ /architect-team:cleanup-worktrees [--dry-run] [--against <ref>]           │
│ ▸ /architect-team:status                          (dispatch / state report) │
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

### `/architect-team:mini <requirements-folder | free-text prompt>`

Faster sibling pipeline (`mini-architect-team-pipeline` skill — phases **M0 → M8**) for ≤5-AC changes against a familiar codebase. Single architect drafts proposal + spec + tasks + coverage in one pass (M2) and self-confirms against the prompt (M3, cap 3); frontend + backend work parallel non-overlapping slices and cross-review each other's evidence (M4); the `mini-qa` agent runs unit + integration + ≤ 3 Playwright user-flows against the live dev environment (M5); a `green` verdict (M6) auto-merges to `main` with a structured **`Mini-Run: <slug>`** commit trailer (M7); the architect re-evaluates against the merged state (M8, cap 3) and escalates if gaps remain. Use when the change is small and the maps are fresh — falls back to the full `/architect-team` flow for larger scope. Accepts the same two input forms as `/architect-team` — folder OR plain-language prose.

### `/architect-team:mini-review-sweep [--since <ref>] [--limit <N>]`

On-demand replay of the heavyweight gates against a batch of recent mini-runs — finds commits with the **`Mini-Run: <slug>`** trailer since `<ref>` (default: last release tag) up to `<N>` (default: 10), and runs the visual-fidelity reconciliation, editability completeness, master-review audit, and doc-currency audit against the merged set. Use when you have shipped several mini changes and want the deeper gates applied as a batch.

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

Tests validate: plugin/marketplace JSON; all 26 skill frontmatters; all 27 agent frontmatters (tool + model names); all 12 commands; hooks.json wiring for all five trigger events (PostToolUse + SubagentStop + Stop + the v1.0.0 TaskCompleted + TeammateIdle); hook script logic (review-gate + teammate-idle share one `review_evidence_schema` module — evidence schema v6: 12 self-review fields + the independent `task-reviewer` verdict; the `pipeline-completion-audit` Stop hook incl. the master-review audit check; path-traversal sanitization); cross-component consistency (the two evidence hooks cannot drift; the Stop hook's origin set matches the pipeline; no unregistered skills/agents/commands); the setup + MemPalace install scripts; the `scripts/notify/notify.py` notifier (config load/validate, Gmail + SendGrid message construction with mocked transport, event dispatch, secret resolution, CLI + failure isolation) and its pipeline wiring; the v1.0.0 teams-mode detection helper (`scripts/setup/teams_mode.py`) + the cross-session lock layer (`hooks/locks.py`); the v1.1.0 worktree-aware state-resolution helper (`scripts/setup/worktree_paths.py`) including the cross-worktree lock-coordination integration test (acquire from a real `git worktree add`-created worktree blocks an intersecting acquire from main with the default `locks_dir`); the v1.2.0+v1.3.0 worktree-lifecycle helper (`scripts/setup/worktree_lifecycle.py`) including `create_run_worktree` happy path + collision handling, `current_worktree_is_run` True / False detection, `current_run_slug` extraction, `cleanup_run_worktree` with + without branch removal, and the v1.3.0 auto-cleanup helpers (`list_merged_architect_team_worktrees` with `exclude_current` safeguard; `cleanup_merged_worktrees` with `dry_run` preview; end-to-end cleanup-only-removes-merged) — all exercising real `git init` + `git worktree add` fixtures with no git mocks; and the no-arbitrary-timers, diagnostic-research, MemPalace-integration, integration-testing, expensive-verification, editability-completeness, readme-styling, design-baseline-migration, visual-verification-team, producer-checker-enforcement, mempalace-mine-syntax, documentation-currency, project-email-notifications, ui-interaction-fidelity, email-testing, proposal-refiner, ux-test-builder, bug-fix-pipeline, code-path-witness, mini-architect-team-pipeline, agent-teams-mode, and scope-discipline (v1.4.0 — `tests/test_scope_discipline.py` audits the canonical `## Scope discipline` section in `common-pipeline-conventions/SKILL.md`, the 6 parity-implying verbs documented in the section + the bug-classifier action-verb section, the 3 pipeline body references, the prompt-refiner 6th `scope-fidelity` axis + grade-schema, the proposal-refiner Phase R2 documentation of the axis + new weights, and the system-architect Master Review Audit + Phase 2 architect brief scope-narrowing checks) disciplines. **1744 tests pass (+ 1 skipped).**

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
           v0.9.30 ─ cross-platform Python hook invocation — Windows Store-shim fix
           v0.9.31 ─ Phase B6 code-path execution witness — qa-replayer catches tests that pass via wrong path
           v0.9.32 ─ wrong-code-path witness generalized across all 3 Playwright sites: B2 selector / Phase 5 feature / U6 flow-effect
           v0.9.33 ─ proposal-refiner — conversational pre-pipeline prompt refinement with codebase-grounded clarity grading
           v0.9.34 ─ email-testing — automatic Mailpit-based email flow verification across all QA agents
           v0.9.35 ─ email-testing audit — Mailpit search API, pre-test cleanup, container collision fix, redirect chain docs, language indicators, 38 new tests, doc-currency refresh
           v0.9.36 ─ bug-fix testing enforcement (verdict file mandates + completion-audit hook) + anti-deferral discipline (both pipelines)
           v0.10.0 ─ mini pipeline — rapid feature changes (≤5 ACs, familiar codebase) with single-architect drive + auto-merge to main on green QA
           v1.0.0  ─ Agent Teams as default dispatch mode — long-lived 1M-context teammates + shared task list; `.architect-team/locks/` cross-session lock layer; hook triggers split TaskCompleted/TeammateIdle; agent bodies framed as teammates; subagents-mode fallback via `--no-teams`
           v1.1.0  ─ worktree-aware state resolution — 3-layer model (filesystem isolation = worktrees / architectural coordination = locks resolved to main worktree / context sharing = MemPalace resolved to main worktree); shared vs per-run state split via `scripts/setup/worktree_paths.py`; cross-worktree lock coordination via `hooks/locks.py` shared default; backwards-compatible for single-session users
           v1.2.0  ─ auto-worktree lifecycle — every `/architect-team` family invocation creates a fresh worktree by default (`<parent-of-repo>/<repo-name>-<slug>/` on branch `architect-team/<slug>`); re-entry detection via `current_worktree_is_run()` skips nested creation; `--no-worktree` reverts to v1.1.0 single-tree behavior; collision handling appends `-2`, `-3`, ...; cleanup recommended at Phase 8 / B8 / M7 success (made automatic in v1.3.0)
           v1.3.0  ─ auto-cleanup of merged worktrees — every `/architect-team` family invocation sweeps merged `architect-team/*` worktrees first (best-effort, excludes current); mini Phase M7 cleans its own worktree after green merge; new `/architect-team:cleanup-worktrees [--dry-run] [--against <ref>]` for on-demand cleanup; merged-branch detection via `git merge-base --is-ancestor` (squash-merges not detected — false-negative is safer than false-positive auto-delete); 2 new helpers (`list_merged_architect_team_worktrees`, `cleanup_merged_worktrees`) in `scripts/setup/worktree_lifecycle.py`; 6 new tests; cleanup failures NEVER block the new run
           v1.4.0  ─ scope discipline — agents using this package must NOT silently narrow the user's prompt at intake; the v0.9.36 anti-deferral discipline forbade the MID-RUN version, v1.4.0 extends it to INTAKE; new `## Scope discipline` section in `common-pipeline-conventions/SKILL.md` (the canonical home) naming the anti-pattern, listing the 6 parity-implying verbs (`match`, `rebuild`, `mirror`, `parity`, `make like`, `replicate`) each implying visual + structural + behavioral parity, classifying scope-narrowing as a DOMAIN gate, requiring `AskUserQuestion` surfacing BEFORE starting work; `prompt-refiner` gains a 6th `scope-fidelity` grading axis (weight 0.17); `bug-classifier` gains an action-verb interpretation section; `system-architect` Master Review Audit + Phase 2 architect brief gain scope-narrowing detection (verdict JSON gains `scope_fidelity_finding` block); 3 pipeline body anti-pattern entries; 35 new tests; backwards-compatible discipline change
           v1.5.0  ─ dispatch-mode observability — the user's direct question *"how do I know if a team is deployed via agent teams vs subagents, can we show an indicator"* exposed a real gap (v1.0.0 made the decision silent). New `format_dispatch_banner()` helper in `scripts/setup/teams_mode.py` renders a one-block banner naming **AGENT TEAMS** or **SUBAGENTS (fallback)** + (in the fallback case) the diagnosed `Reason:`. Each of the 3 pipeline-driving slash commands prints the banner as its FIRST user-visible action (before v1.3.0 auto-cleanup, before argument parsing). New `/architect-team:status` command (13th) reports dispatch mode + active worktrees + open SRs + last completed run. Phase 8 / B8 / M7 commit-message templates gain a `Dispatch-Mode: <teams|subagents>` trailer above the existing `Co-Authored-By` trailer, derived from `intake-state.json`. Banner is informational, never gating — subprocess failure surfaces a one-line note and the run continues. 20 new tests in `tests/test_dispatch_banner.py`; backwards-compatible observability addition
           v1.6.0  ─ teammate git discipline — a real-world failure surfaced in a separate user session exposed a discipline gap: four teammates dispatched in parallel against the same working tree each ran `git stash` to verify their work against baseline; concurrent stash + pop interleaved catastrophically; the reflog showed 10+ consecutive `reset: moving to HEAD` entries; three of four teammates' work was lost (only the last writer survived). The plugin had no rule forbidding teammates from running destructive git operations, so the teammates did. v1.6.0 ships the discipline at 4 enforcement points (same shape as v1.4.0 scope-discipline): (1) new `## Teammate git discipline` section in `common-pipeline-conventions/SKILL.md` is the canonical home — names the 6 forbidden destructive operations (`git stash` / `git stash pop`, `git reset --hard`, `git rebase`, `git commit --amend`, `git checkout <other-branch>` / `git checkout .`, `git clean -f`), documents the heirship-app-v2 worked example with the smoking-gun reflog signature, names the right pattern (orchestrator captures `BASELINE_SHA=$(git rev-parse HEAD)` at run start; teammates run `git diff $BASELINE_SHA -- <my-files>`); (2) 3 pipeline body anti-pattern entries; (3) all 27 `agents/*.md` files gain a `## Forbidden git operations` section as a uniform 5-line block; (4) new `## Baseline SHA capture` sub-section in `team-spawning-and-review-gates/SKILL.md` documents the orchestrator-side mechanics — SHA persisted to `intake-state.json` as `baseline_sha`, carried in every teammate's spawn brief (extending the v0.9.13 manifest schema). 265 new tests in `tests/test_teammate_git_discipline.py`; backwards-compatible discipline addition; no runtime detector, no enforcement hook (discipline lives in agent bodies + structural tests + the orchestrator-provided alternative)
           v1.7.0  ─ frontend missing-API discipline — orthogonal to v1.6.0. When a frontend agent encounters a UI element that needs a backend API which does NOT yet exist, the previous discipline didn't tell the agent what to do — the predictable failure modes were the four downstream defects each existing gate catches AFTER the round trip is wasted (fake the data → caught by `dynamic-value-discovery`; mock the endpoint → caught by `playwright-user-flows`; hardcode the response → caught by `dynamic-value-discovery`; silently stub the UI → caught by `interaction-completeness`). v1.7.0 ships the explicit alternative at 4 enforcement points: (1) new `## Frontend missing-API discipline` section in `common-pipeline-conventions/SKILL.md` is the canonical home — names the 4 anti-patterns + the right pattern (write SR with `origin.kind: "missing-api-for-frontend-element"`, pause that element's work, continue on the rest of the slice, return to wire when the orchestrator re-dispatches with the SR resolved); (2) `## Missing-API discipline` section in `agents/frontend.md` (authoring side; worked example: `<UserAvatar>` component needing `GET /api/users/me`) + `## Missing-API SR intake` section in `agents/backend.md` (resolver side; surfaces actual endpoint shape in dispatch report so frontend can confirm before wiring); (3) `agents/system-architect.md` Phase 2 architect brief — new ordering-dependency check for every `both`-layer requirement (decide between sequencing backend-first or authorizing the frontend to surface missing-API SRs — the default); (4) new `pending-backend` element classification in `skills/interaction-completeness/SKILL.md` (the 5th classification; SR-linkage rule: reviewer accepts only with matching open SR; without the SR it's an `unwired-control` gap) + new `missing-api-for-frontend-element` SR origin-kind in `skills/team-spawning-and-review-gates/SKILL.md` with documented routing (orchestrator dispatches BACKEND agent FIRST, NOT through `diagnostic-research-team` — this is not a test failure; on backend completion the orchestrator re-dispatches the FRONTEND to wire up). 26 new tests in `tests/test_frontend_missing_api_discipline.py`; backwards-compatible discipline addition; no runtime detector, no enforcement hook (discipline lives in agent bodies + structural tests + the SR auto-spawn)
   ◆       v1.8.0  ─ agent-resume discipline — a reliability gap distinct from v2.0.0's verified-agent-output framework. A real-world background `dv-attorney` agent ran 68 tool-calls of real work; the final report message was lost to a harness-level stream timeout (rate-limit cutoff); the orchestrator saw an empty result and treated the agent as failed; the work was on disk the whole time; the user had to manually `redispatch and continue` so the agent could re-emit its verdict from already-loaded context. v1.8.0 automates the recovery and adds a checkpoint discipline so the resumed agent doesn't re-do the 68 tool calls. 4 enforcement points (same shape as v1.6.0 + v1.7.0): (1) new `scripts/setup/agent_resume.py` helper exposes `is_truncated(result)` (3 heuristics — empty / sub-50-char output, rate-limit / stream-timeout markers, missing `Status:` / `DONE` / `BLOCKED` / `NEEDS_CONTEXT` report markers), `wrap_agent_result(result, agent_id, send_message, max_attempts=2)` (dependency-injected `SendMessage`; merges resumed output with original via `[resumed via wrap_agent_result]` marker; caps at 2 attempts; surfaces `resumed_failed=True` + `resume_error` on cap-exhaustion without raising), `read_checkpoint(agent_id, checkpoints_dir=None)` (defaults to `shared_state_dir() / 'agent-checkpoints'` via the v1.1.0 lazy-import pattern; returns None for absent / malformed); (2) two new canonical sections in `skills/common-pipeline-conventions/SKILL.md` — `## Background-agent resume discipline` (wrap-call rule + 3 truncation heuristics + 2-attempt cap + user-surfacing) and `## Agent checkpoint discipline` (path + schema + cadence + resume-reads-checkpoint pattern); (3) one-paragraph reference in each of the 3 pipeline SKILL.md bodies enumerating the dispatch phases; (4) uniform `## Checkpoint discipline` section in all 27 `agents/*.md` files inserted AFTER `## Forbidden git operations`. 42 new tests in `tests/test_agent_resume_discipline.py`; backwards-compatible (purely additive); orthogonal to v2.0.0 (the VAO branch is unaffected; the helper layers cleanly underneath if v2.0.0 is later approved); no runtime detector, no enforcement hook (discipline lives in the helper + canonical sections + 27-agent fan-out) (current)

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
