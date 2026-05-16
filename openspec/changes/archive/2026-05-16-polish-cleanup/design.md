## Context

The `architect-team` plugin v0.2.2 is functionally complete: install, setup, slash command, skill loading, and orchestrator delegation chain all verified end-to-end via this very dogfood run. Six remaining issues span: a UX wart (REQ-001), defensive correctness (REQ-002), test coverage gaps (REQ-003), undocumented operational policy (REQ-004), historical doc drift (REQ-005), and release bookkeeping (REQ-006). All scoped to existing files; no new modules. v0.2.3 is the target release.

## Goals / Non-Goals

**Goals:**
- Eliminate the "orchestrator re-prompts for path" UX wart so a single `/architect-team:architect-team <path>` invocation drives the pipeline end-to-end without user intervention.
- Close the path-traversal correctness gap in both hooks before the plugin is shared more widely.
- Bring the self-test suite to ≥60 tests, covering all hook validation branches.
- Document the previously-implicit hook-rejection escalation policy so stuck teammates have a deterministic procedure.
- Sync the historical design spec with the current implementation (no `%ct`/`task_ids[]` drift).
- Ship v0.2.3 with consumers able to upgrade via `/plugin update`.

**Non-Goals:**
- Refactoring the orchestrator's phase structure or skill set.
- Adding new skills, agents, commands, or external dependencies.
- A full pipeline run against a real customer codebase (the dogfood already exercises the architecture).
- Changing the schemas of evidence/manifest/coverage-map files (they are correct).
- Implementing a "skip Phase −1C for single-codebase work" optimization (logged as future open question).
- README rewrites beyond what REQ-006 requires.

## Decisions

### REQ-001: Inline-explicit path binding in command body (over harness-level fix)

**Decision:** Update `commands/architect-team.md` body to add an explicit instruction telling the model to bind `$REQ_DIR` from the command's `$ARGUMENTS`.

**Alternatives considered:**
- *Harness-level fix:* push for Claude Code itself to propagate command `$ARGUMENTS` into invoked skill bodies. Rejected: outside our control; uncertain timeline; we ship today.
- *Inline the skill body into the command:* eliminates the indirection but duplicates ~200 lines of orchestrator content; loses skill auto-discoverability; structurally brittle.
- *Add a CLI argument to the skill body via Skill-tool extension:* not supported by current API.

**Why this:** smallest possible change (a few sentences in one file), zero risk to other components, immediately effective.

### REQ-002: `_safe_id` helper added to each hook (not extracted to a shared lib)

**Decision:** Define `_safe_id(value: str) -> str | None` independently in both `hooks/review-gate-task.py` and `hooks/teammate-idle-check.py`. Return `None` for unsafe identifiers; caller exits 2 with structured stderr.

**Alternatives considered:**
- *Shared helper module under `hooks/_common.py`:* tighter, but requires adding `sys.path` manipulation or making `hooks/` a package. Both hooks are already standalone scripts and `_validate()` is also duplicated for the same standalone-script reason. Defer extraction until a third hook needs it.
- *Use `os.path.commonpath()` to verify the resolved path stays under `.architect-team/`:* technically more thorough but overkill — the four character checks (`/`, `\`, leading `.`, `..`) cover every traversal vector for the controlled identifier sets we expect.

**Why this:** consistent with existing `_validate()` duplication; standalone scripts stay standalone; one-line helper.

### REQ-003: Test additions follow existing patterns

**Decision:** Add tests to `tests/test_review_gate_task.py` and `tests/test_teammate_idle_check.py` using the same subprocess-based pattern as existing tests, with the new `_write_manifest` helper added in v0.2.2.

**Alternatives considered:**
- *Refactor tests to use pytest parametrize over a (field, bad_value, expected_stderr_substring) tuple:* terser, but obscures the intent. Each branch deserves a self-documenting test name.

**Why this:** matches conventions already in those files; readable; one test per branch.

### REQ-004: Escalation policy as a SKILL.md section (not a config file)

**Decision:** Document the 3-rejection escalation policy as a new `## Hook-rejection escalation policy` section inside `skills/team-spawning-and-review-gates/SKILL.md`. The threshold (3) is hard-coded in the prose. No config file or CLI flag.

**Alternatives considered:**
- *Configurable threshold via `.architect-team/config.json`:* introduces a new schema, new validation, new code path. Premature configurability; YAGNI.
- *Implement enforcement in the hook itself (count consecutive rejections):* would require persisted state per task. Out of scope for v0.2.3; can be added later if real-world data shows teammates ignoring the documented policy.

**Why this:** behavior change at the teammate-prose level only; no new code, no new config, no new schema. Frontmatter `description` extension makes the policy auto-trigger-discoverable.

### REQ-005: Inline edits, no spec restructuring

**Decision:** Three targeted line edits to `docs/superpowers/specs/...md`. No restructuring of the spec.

### REQ-006: Single-pass release commit, semantic versioning bump (patch → minor irrelevant)

**Decision:** Bump 0.2.2 → 0.2.3 (patch bump). All REQs are bug-fixes or doc cleanup; no new capabilities visible to users.

**Alternatives considered:**
- *Bump to 0.3.0:* warranted only if there were a breaking change or a meaningful new capability. Neither applies.

## Risks / Trade-offs

- **REQ-001 risk: model interprets the explicit instruction inconsistently** → Mitigation: the new instruction is unambiguous ("treat `$ARGUMENTS` from this command as `$REQ_DIR` in the skill"). Re-validate via dogfood after landing.
- **REQ-002 risk: legitimate identifiers happen to start with `.`** → Mitigation: project convention is `T-N` / `<role>-<slice>` style; no such identifiers in the wild. The policy is documented in the skill; if a legitimate need arises, the rule is one line to relax.
- **REQ-002 risk: the leading-`.` rule blocks `.hidden` style names some downstream user might want** → Mitigation: same as above; we'd hear about it before it bit anyone.
- **REQ-003 risk: new tests are flaky on Windows due to file-handle race conditions** → Mitigation: existing tests use `tmp_path` correctly; following the same pattern eliminates the risk.
- **REQ-004 risk: the policy is documented but not enforced; teammates might ignore it** → Mitigation: this is a known v0.3.0 gap and is acknowledged in the skill section's prose. Real-world data will tell us if enforcement is needed.
- **REQ-005 risk: zero (pure doc edit).**
- **REQ-006 risk: marketplace cache prevents teammates from picking up v0.2.3** → Mitigation: documented `/plugin marketplace update` workflow; verified working in this session.

## Reuse Decisions

Per the `reuse-first-design` skill — every change in this scope extends an existing file or adds a section within one. Zero new modules, zero new dependencies. The Reuse Decision Log entries:

### REQ-001 — modifying `commands/architect-team.md`
- **Existing considered:** the file itself (`commands/architect-team.md` is the canonical command entry).
- **Extension attempted:** add a few explicit sentences telling the model to pre-bind `$REQ_DIR`.
- **Why not sufficient:** N/A — extension is sufficient.
- **Decision:** extend the existing file.
- **Net new files:** none.

### REQ-002 — modifying `hooks/review-gate-task.py` and `hooks/teammate-idle-check.py`
- **Existing considered:** both hook scripts already have helper-function patterns (`_validate`, `_extract_subagent_name`, `_is_teammate_task`).
- **Extension attempted:** add `_safe_id` as another standalone helper following the same pattern.
- **Why not sufficient:** N/A — extension is sufficient.
- **Decision:** extend each file with one helper. Decline shared-module extraction (rationale in Decisions §REQ-002).
- **Net new files:** none.

### REQ-003 — extending `tests/test_review_gate_task.py` and `tests/test_teammate_idle_check.py`
- **Existing considered:** both test files have established subprocess-based patterns and helper functions (`_run`, `_make_payload`, `_valid_evidence`, `_write_manifest`).
- **Extension attempted:** add new test functions following the existing pattern; reuse helpers; no new helpers needed.
- **Why not sufficient:** N/A.
- **Decision:** add tests in-place; do not create new test files.
- **Net new files:** none.

### REQ-004 — extending `skills/team-spawning-and-review-gates/SKILL.md`
- **Existing considered:** the skill body already has section structure (Non-overlapping file scopes, Plan-approval triggers, Direct messaging, Review-gate evidence file, Teammate manifest, Anti-patterns).
- **Extension attempted:** add a new `## Hook-rejection escalation policy` section between the Teammate manifest and Anti-patterns sections; extend frontmatter `description`.
- **Why not sufficient:** N/A.
- **Decision:** in-place section addition.
- **Net new files:** none.

### REQ-005 — modifying `docs/superpowers/specs/2026-05-16-architect-team-plugin-design.md`
- **Existing considered:** the file itself.
- **Extension attempted:** three single-line edits.
- **Why not sufficient:** N/A.
- **Decision:** in-place edits.
- **Net new files:** none.

### REQ-006 — version bump + CHANGELOG entry + tag
- **Existing considered:** `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, `CHANGELOG.md`.
- **Extension attempted:** version field bumps + CHANGELOG section prepend.
- **Why not sufficient:** N/A.
- **Decision:** in-place edits + git tag.
- **Net new files:** none.

## Migration Plan

Consumers on v0.2.2 (or earlier) upgrade to v0.2.3 with:

```
/plugin marketplace update architect-team-marketplace
/plugin update architect-team@architect-team-marketplace
/reload-plugins
```

No data migration. No config migration. No breaking changes. Existing `.architect-team/` runtime directories remain valid.

If `/plugin update` is unavailable in the consumer's Claude Code build, fall back to:

```
/plugin uninstall architect-team@architect-team-marketplace
/plugin install architect-team@architect-team-marketplace
/reload-plugins
```

## Open Questions

- **`$ARGUMENTS` propagation: harness-level fix vs. permanent inline workaround.** Tracked in v0.2.3 brief as a follow-up; the inline workaround is shipped this release.
- **Single-codebase Phase −1C optimization.** Currently the orchestrator runs the 3-explorer + master-synthesizer ceremony even for one codebase. A "skip if single codebase" branch would save tokens. Logged for v0.3.0 consideration.
- **Stuck-teammate enforcement (vs. documentation).** REQ-004 documents the 3-rejection policy in prose. v0.3.0 may add code-level enforcement (count consecutive rejections in the hook, persist per task) if real-world dogfood data shows teammates ignoring the documented policy.
