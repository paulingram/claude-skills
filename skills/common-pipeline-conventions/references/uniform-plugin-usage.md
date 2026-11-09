# Uniform plugin usage (v3.9.0)

> **v4.0.0 status.** `superpowers` and `cartographer` are CONDITIONAL plugins: preferred when installed, reported and remediated when absent, never gating (a lane records `methodology: native` and follows `references/native-methodology.md`). `ralph-loop` is retired; every "loop until all reviewers return ok" gate runs the `ct6-converge` workflow (`references/converge-workflows.md`). The sections below describe the preferred, plugin-present form.

This is the single source of truth for HOW every CT6 pipeline invokes its plugin dependencies — the ct6-converge workflow, the superpowers plugin, and the OpenSpec CLI/skills. The point is **predictable behavior regardless of which pipeline runs**: the full (`architect-team-pipeline`), bug-fix (`bug-fix-pipeline`), mini (`mini-architect-team-pipeline`), and ux-test (`ux-test-builder`) bodies all reference THIS section rather than re-describing the invocation form locally, so a single edit propagates. A pipeline body MUST NOT re-spell these invocations inline.

### 1. Converge workflow (formerly ralph-loop) — canonical invocation form

Every mapping / exploration / review-convergence loop uses EXACTLY this form:

```
the `ct6-converge` workflow with completion promise "<EXIT STRING>"
```

Loop-**until-promise**: there is no iteration cap — no AGENT-chosen cap exists anywhere in the pipeline; the only cap is a `--max-iterations` the USER passes explicitly (the `proposal-refiner` lever) — consistent with `## Unbounded solving discipline (v3.8.0)`. The loop ends ONLY when an agent emits the literal `<EXIT STRING>` completion-promise (e.g., `CODEBASE MAP COMPLETE` / a 3-reviewer total-agreement string). The agent emitting the exact promise string is the sole exit condition; a numeric cap would re-introduce the give-up ceiling that v3.8.0 removed.

Also acceptable, naming the SAME mechanism, is the skill form `ct6-converge` workflow (invoked via the Skill tool) — the slash command the `ct6-converge` workflow and the `ct6-converge` workflow skill are two surfaces of one loop primitive. Either is uniform; both carry the completion-promise and neither carries an iteration cap.

### 2. Superpowers — HARD dependency (blocking) + concretely invoked

Superpowers is a **hard-blocking prerequisite**. Every pipeline runs a **pre-flight check before its first phase** that ABORTS the run with an actionable message if the superpowers plugin is unavailable. The pre-flight resolves availability two ways: the plugin appears in `~/.claude/plugins/installed_plugins.json` carrying `superpowers@claude-plugins-official`, OR the Skill tool resolves `superpowers:using-superpowers`. If neither resolves, the run aborts before Phase 0 with a message naming the missing plugin and the install path (`/plugin install superpowers@claude-plugins-official`) — it does NOT silently degrade to a superpowers-free run.

Once the pre-flight passes, each pipeline MUST invoke the named superpowers skills via the Skill tool at the defined points. This is the **SUPERPOWERS INVOCATION MAP**:

| Phase / moment | Superpowers skill | Why |
|---|---|---|
| design / intake refinement (before committing to an approach) | `superpowers:brainstorming` | explore intent + design before implementation |
| implementation (tests first) | `superpowers:test-driven-development` | write the failing test before the implementation code |
| RCA / diagnosis (test-failure SRs, bug isolation) | `superpowers:systematic-debugging` | root-cause before proposing a fix |
| review / completion gates (before declaring a slice or run done) | `superpowers:verification-before-completion` | evidence before any success claim |

**PRECEDENCE rule.** User `CLAUDE.md` / `AGENTS.md` instructions ALWAYS take precedence over a superpowers skill's default behavior. "Hard-blocking" governs the plugin's **PRESENCE** — it is a prerequisite gate that the plugin be installed and resolvable — NOT a license to override the user's explicit instructions. When a user instruction and a superpowers skill default conflict, the user instruction wins; the superpowers skill is the default, not the ceiling.

### 3. OpenSpec — uniform gates across every implementing pipeline

The full (`architect-team`), bug-fix, AND mini pipelines run **IDENTICAL** openspec gates. No implementing pipeline skips validate or archive:

- **planning + master-review gate:** `openspec validate --all --strict --json`
- **completion gate:** `openspec archive <change-name>`

The **authoring path** of the `openspec/changes/<name>/` set is allowed to differ — and the split is intentional, not accidental:

- **`plain` Phase 0 path** — the raw-CLI loop `openspec instructions proposal/specs/design/tasks --change <name> --json`, used when the pipeline drafts the change directly.
- **SKILL path** — the `openspec-propose` / `opsx:propose` skill (invoked via the Skill tool), used by the exploration / `visual-to-api` / `data-engineering` Stage-4/7 authoring paths.

Both authoring paths produce a valid `openspec/changes/<name>/` set. The **validate + archive GATES are the same regardless of which authoring path produced the change** — `openspec validate --all --strict --json` at planning + master-review, `openspec archive <change-name>` at completion. The authoring path is a choice; the gates are uniform.

### 4. Uniform-usage table (the four pipelines side by side)

Every implementing pipeline shows the SAME uniform values. `ux-test` has no openspec change of its own, so its validate/archive cells are `n/a` — but it still runs the superpowers pre-flight + the invocation map.

| Pipeline | Converge form | Superpowers pre-flight | Superpowers invocations | `openspec validate` | `openspec archive` |
|---|---|---|---|---|---|
| `architect-team` (full) | the `ct6-converge` workflow with completion promise "…" | required (blocking) | brainstorming / TDD / systematic-debugging / verification-before-completion | `--all --strict --json` | `archive <change-name>` |
| `bug-fix` | the `ct6-converge` workflow with completion promise "…" | required (blocking) | brainstorming / TDD / systematic-debugging / verification-before-completion | `--all --strict --json` | `archive <change-name>` |
| `mini` | the `ct6-converge` workflow with completion promise "…" | required (blocking) | brainstorming / TDD / systematic-debugging / verification-before-completion | `--all --strict --json` | `archive <change-name>` |
| `ux-test` | the `ct6-converge` workflow with completion promise "…" | required (blocking) | brainstorming / TDD / systematic-debugging / verification-before-completion | `n/a` (no change) | `n/a` (no change) |
