# Design: agent-teams-refactor

## Reference design

The full design discussion lives in `.architect-team/refined-prompts/2026-05-28-agent-teams-refactor.md` (the refined-prompt brief) and the Anthropic docs at https://code.claude.com/docs/en/agent-teams. This file is the OpenSpec entry point — it must not diverge from the refined-prompt brief. Update both in lockstep.

## Architecture

The plugin gains a **dispatch mode** decision made at pipeline-skill startup:

```
┌─────────────────────────────────────────────────┐
│ /architect-team / /architect-team:bug-fix /     │
│ /architect-team:mini  invoked                   │
└────────────────────┬────────────────────────────┘
                     │
            ┌────────▼──────────┐
            │ Read teams_mode   │
            │ availability:     │
            │ env + version +   │
            │ --no-teams flag   │
            └────────┬──────────┘
                     │
        ┌────────────┴──────────────┐
        │                           │
    teams=true                  teams=false
        │                           │
        ▼                           ▼
 Spawn named teammates       Existing Agent-tool
 via Agent(run_in_background  ephemeral dispatch
 +name).  Maintain shared     (current v0.9.36
 task list at                 behavior verbatim).
 ~/.claude/tasks/<slug>/
 SendMessage for resumption.
 Hooks attach to
 TaskCompleted /
 TeammateIdle / Stop.
        │                           │
        └────────────┬──────────────┘
                     ▼
              Phase phases run
              (same body, dispatch
              primitive varies)
```

The agent role definitions, pipeline-skill phase bodies, OpenSpec/coverage-map/Mini-Run conventions, git commit/push/merge logic, doc-currency gate, MemPalace integration, email notifications, and the review-evidence schema v6 are IDENTICAL across modes. Only the dispatch primitive + hook trigger payload-shape varies.

## Reuse Decision Log (per `reuse-first-design`)

Anchored in `docs/CODEBASE_MAP.md` (last_mapped 2026-05-27) + `docs/INTEGRATION_MAP.md`.

### RD-1: Extend `scripts/setup/setup.py` for mode-detection consent

**Decision:** Extend, not replace.
**Map anchor:** `scripts/setup/setup.py` is the canonical installer (per CODEBASE_MAP §4 setup-scripts). The existing module checks `openspec`, Python test tools, Playwright + browsers. Adding `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS` + `claude --version` to the check list is structurally additive — same shape as the existing checks.
**Anti-pattern avoided:** Spawning a new `scripts/setup/setup-teams.py` would split installer responsibility across two scripts and force the architect-team-setup command to call both.

### RD-2: New `scripts/setup/teams_mode.py` helper (the helper is new; not a code-duplication of existing logic)

**Decision:** Build new. No existing module addresses "is teams mode available right now."
**Map anchor:** No existing helper in `scripts/setup/`, `hooks/`, or `tests/helpers/` performs runtime detection of the experimental flag + Claude Code version. CODEBASE_MAP confirms — `scripts/setup/` has `setup.py` + `install_mempalace.py` only.
**Reuse within the new module:** Uses `os.environ.get("CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS")` and a small JSON-read of `~/.claude/settings.json`; uses `subprocess.run(["claude", "--version"])` for the version check; uses `packaging.version` (already imported elsewhere — verify in dep tree) for the `>= 2.1.32` comparison.

### RD-3: New `hooks/locks.py` for the cross-session lock layer

**Decision:** Build new.
**Map anchor:** No existing lock layer; `.architect-team/` is currently used for per-run state (reviews, teammates, handoffs) but has no concurrency primitive. CODEBASE_MAP §4 confirms.
**Module shape:** Pure-Python, stdlib-only (the plugin's discipline per `scripts/notify/notify.py` precedent). Lock files at `.architect-team/locks/<scope-glob-hash>.json` with `{holder, scope_glob, acquired_at, ttl_seconds, run_id}`. Functions: `acquire`, `release`, `detect_stale`, `globs_intersect`. The `globs_intersect` reuses the same logic the existing `team-spawning-and-review-gates` skill prescribes for non-overlapping-file-scope checks at dispatch time (i.e., extend that skill's prose to point at this helper).
**Anti-pattern avoided:** Using `fcntl.flock` would tie the layer to a single host and fail on networked filesystems; using a SQLite "lock table" would add a dependency. File-based locks with TTL stale-detection match the plugin's existing minimal-dependency posture.

### RD-4: Extend the existing 3 hook scripts for mode-branch behavior

**Decision:** Extend, not replace.
**Map anchor:** `hooks/review-gate-task.py`, `hooks/teammate-idle-check.py`, `hooks/pipeline-completion-audit.py` all exist; CODEBASE_MAP §4 confirms. Each currently reads the PostToolUse / Stop payload shape. The extension is: detect which trigger fired (PostToolUse(TaskUpdate) vs TaskCompleted; TaskCompleted vs TeammateIdle) by inspecting the payload's tool name / event type, then run the existing enforcement logic.
**Anti-pattern avoided:** Forking each hook into a `-v1` (subagents) and `-v2` (teams) file would double the maintenance surface. Single hook, mode-detected branch, common enforcement.

### RD-5: Reuse `hooks/review_evidence_schema.py` (no change)

**Decision:** Reuse as-is.
**Map anchor:** Schema v6 (per CODEBASE_MAP §4) defines `teammate`, `reviewer`, the 12 self-review fields, the 7 independent_review fields. None of those need to change for teams mode — a teammate's review evidence has the same shape regardless of how the teammate was spawned. Mode-detection happens upstream (at the hook), not in the schema.

### RD-6: Agent role definitions (27 files) — uniform small rewrite, not new files

**Decision:** Edit in place.
**Map anchor:** `agents/*.md` is the canonical role-definition home (CODEBASE_MAP §4 agents-table). Each agent body has a small "you are spawned for one task" framing that needs to become "you are a long-lived teammate." `tools` and `model` frontmatter is unchanged.
**Anti-pattern avoided:** Authoring parallel `agents/teams/*.md` files would mean the dispatch primitive picks which file to reference — but the docs explicitly say the same subagent definition works as both a subagent and a teammate. One file per role, same body, mode-agnostic.

### RD-7: Pipeline skills (3 files) — additive mode-detection section + dispatch-section split

**Decision:** Extend in place.
**Map anchor:** `skills/architect-team-pipeline/SKILL.md`, `skills/bug-fix-pipeline/SKILL.md`, `skills/mini-architect-team-pipeline/SKILL.md`. Each gains a `## Dispatch mode` section near the top (after Inputs) that decides teams vs subagents, and each "spawn X" / "dispatch Y" section gains a mode-conditional dispatch instruction. The phase bodies themselves do not change.
**Anti-pattern avoided:** A separate `skills/architect-team-pipeline-teams/SKILL.md` would mean four pipeline skills instead of three; users would have to pick.

### RD-8: README + CLAUDE.md — additive Requirements section

**Decision:** Extend.
**Map anchor:** Both files have inventory sections + version paragraphs that get refreshed every release. Add a Requirements bullet to the existing "Prerequisites" / overview area citing `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` + Claude Code ≥ 2.1.32.

## Migration / rollback

- **Default = teams when available, subagents otherwise.** No big-bang switch; the runtime decision means every existing user keeps working with no env change.
- **`--no-teams` flag** on each pipeline command forces subagents mode for the run.
- **Tests gate both modes.** A failing teams-mode test does not break subagents-mode users.
- **Rollback path:** if a user hits experimental-flag instability, unset the env or pass `--no-teams`; subagents mode is the fallback that was 100% the v0.9.36 behavior.

## Trade-offs accepted

- **Higher token cost in teams mode** (each teammate has its own 1M context per the docs). Worth it for zero re-onboarding on multi-phase runs; opt out via `--no-teams` if cost-sensitive.
- **Per-run team teardown** adds a few seconds at end-of-run; cleanup is automatic.
- **The experimental-flag dependency** — Anthropic may iterate the contract. Mitigation: subagents fallback stays first-class; both modes are CI-gated.
- **Cross-session parallelism is best-effort** — the lock layer prevents file-scope clobbering, but two leads making architecturally-incompatible decisions on independent codebases is caught only after-the-fact via MemPalace recall. Acceptable: truly orthogonal work is the common case for parallel runs.

## Versioning

v1.0.0 — the structural pivot is significant enough to bump the major version. Backwards-compatible via subagents fallback.
