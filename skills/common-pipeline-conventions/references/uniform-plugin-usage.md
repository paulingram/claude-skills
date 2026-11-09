# Uniform plugin usage (v3.9.0)

> **v4.0.0 status.** `superpowers` and `cartographer` are CONDITIONAL plugins: preferred when installed, reported and remediated when absent, never gating (a lane records `methodology: native` and follows `references/native-methodology.md`). `ralph-loop` is retired; every "loop until all reviewers return ok" gate runs as declare → the `ct6-converge` workflow → record (`references/converge-workflows.md`). The sections below are the live instructions: where they describe a plugin they describe the plugin-present form, and the native fallback applies whenever the plugin is absent.

This is the single source of truth for HOW every CT6 pipeline invokes its orchestration and methodology dependencies — the native `ct6-converge` workflow, the conditional superpowers plugin, and the OpenSpec CLI/skills. The point is **predictable behavior regardless of which pipeline runs**: the full (`architect-team-pipeline`), bug-fix (`bug-fix-pipeline`), mini (`mini-architect-team-pipeline`), and ux-test (`ux-test-builder`) bodies all reference THIS section rather than re-describing the invocation form locally, so a single edit propagates. A pipeline body MUST NOT re-spell these invocations inline.

### 1. Converge workflow (formerly ralph-loop) — canonical invocation form

Every mapping / exploration / review-convergence loop uses EXACTLY this three-step form (`references/converge-workflows.md` carries the argument list and the presets):

```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/converge/record.py" declare --workspace <ws> --kind <kind> --promise "<PROMISE>" --reviewers <N>
#   then, in the session:
#   Workflow({ name: "ct6-converge", args: { kind: "<kind>", promise: "<PROMISE>", reviewers: <N>, reviewerAgent: "<agent>", fixerAgent: "<agent>", artifacts: [...] } })
python "${CLAUDE_PLUGIN_ROOT}/scripts/converge/record.py" record --workspace <ws> --kind <kind> --result '<the workflow JSON>'
```

In prose a site names the gate as *the `ct6-converge` workflow with completion promise "<PROMISE>"* and says which preset (`kind`) and which review tier it runs at. The promise is the gate's LABEL — it names the declared gate `converge:<kind>` and the record under `.architect-team/converge/` — and the verdicts recorded on disk are the exit condition; no agent exits a loop by typing the promise string.

Loop-**until-converged**: there is no iteration cap — no AGENT-chosen cap exists anywhere in the pipeline; the only ceiling is a human-set one (`maxRounds` on the workflow, or the `--max-iterations` lever the USER passes to `proposal-refiner`) — consistent with `## Unbounded solving discipline (v3.8.0)`. A human ceiling that is reached PAUSES the gate (`converged: false` in the record); it never satisfies it, and the gate stays declared until a later run converges. The reviewer count follows the review-tier table (`skills/team-spawning-and-review-gates/references/review-tiers.md`): three independent reviewers for a tier-3 gate (architecture approval, master review, map convergence), one paired reviewer for a tier-2 gate with a second independent verdict only on disagreement.

When the Workflow tool is unavailable (`CLAUDE_CODE_DISABLE_WORKFLOWS=1`), the Lead runs the rounds with the Agent tool and records the same JSON shape; the declaration and the record do not change.

### 2. Superpowers — CONDITIONAL (native fallback), concretely invoked when present

Superpowers was a hard-blocking prerequisite through v3.67.0; since v4.0.0 it is a CONDITIONAL plugin — listed in `scripts/setup/setup.py`'s `CONDITIONAL_PLUGINS`, provably disjoint from `REQUIRED_PLUGINS` (which is empty). Every pipeline still runs a **pre-flight check before its first phase** that resolves availability two ways: the plugin appears in `~/.claude/plugins/installed_plugins.json` carrying `superpowers@claude-plugins-official`, OR the Skill tool resolves `superpowers:using-superpowers`. The pre-flight never aborts the run. When neither resolves it reports the gap with the install path (`/plugin install superpowers@claude-plugins-official`), records `methodology: native` in `intake-state.json`, and the lane follows `references/native-methodology.md` for brainstorming, TDD, systematic debugging and verification before completion. An absent optional plugin is reported and remediated; it is never a reason to abort or to skip the discipline.

When the pre-flight finds the plugin, each pipeline MUST invoke the named superpowers skills via the Skill tool at the defined points. This is the **SUPERPOWERS INVOCATION MAP** (the native column is what runs when the plugin is absent):

| Phase / moment | Superpowers skill | Native fallback (`references/native-methodology.md`) | Why |
|---|---|---|---|
| design / intake refinement (before committing to an approach) | `superpowers:brainstorming` | the brainstorming form: goal in one sentence, ≥3 approaches with trade-offs, constraints (principles first), one choice argued | explore intent + design before implementation |
| implementation (tests first) | `superpowers:test-driven-development` | the TDD form: failing test first, smallest passing change, selected tests run, refactor under green | write the failing test before the implementation code |
| RCA / diagnosis (test-failure SRs, bug isolation) | `superpowers:systematic-debugging` | the systematic-debugging form: reproduce, ≥2 hypotheses, EXECUTE the falsification, rank by executed evidence | root-cause before proposing a fix |
| review / completion gates (before declaring a slice or run done) | `superpowers:verification-before-completion` | the verification form: nothing reported done without the check run and its output read | evidence before any success claim |

**PRECEDENCE rule.** User `CLAUDE.md` / `AGENTS.md` instructions ALWAYS take precedence over a superpowers skill's default behavior. The conditional posture governs the plugin's **PRESENCE** — whether the plugin or its native fallback carries the discipline — NOT a license to override the user's explicit instructions. When a user instruction and a superpowers skill default conflict, the user instruction wins; the superpowers skill is the default, not the ceiling.

### 3. OpenSpec — uniform gates across every implementing pipeline

The full (`architect-team`), bug-fix, AND mini pipelines run **IDENTICAL** openspec gates. No implementing pipeline skips validate or archive:

- **planning + master-review gate:** `openspec validate --all --strict --json`
- **completion gate:** `openspec archive <change-name>`

The **authoring path** of the `openspec/changes/<name>/` set is allowed to differ — and the split is intentional, not accidental:

- **`plain` Phase 0 path** — the raw-CLI loop `openspec instructions proposal/specs/design/tasks --change <name> --json`, used when the pipeline drafts the change directly.
- **SKILL path** — the `openspec-propose` / `opsx:propose` skill (invoked via the Skill tool), used by the exploration / `visual-to-api` / `data-engineering` Stage-4/7 authoring paths.

Both authoring paths produce a valid `openspec/changes/<name>/` set. The **validate + archive GATES are the same regardless of which authoring path produced the change** — `openspec validate --all --strict --json` at planning + master-review, `openspec archive <change-name>` at completion. The authoring path is a choice; the gates are uniform.

### 4. Uniform-usage table (the four pipelines side by side)

Every implementing pipeline shows the SAME uniform values. `ux-test` has no openspec change of its own, so its validate/archive cells are `n/a` — but it still runs the superpowers pre-flight + the invocation map (or the native fallback).

| Pipeline | Converge form | Superpowers pre-flight | Superpowers invocations | `openspec validate` | `openspec archive` |
|---|---|---|---|---|---|
| `architect-team` (full) | declare → the `ct6-converge` workflow with completion promise "…" → record | conditional (reports + native fallback, never blocks) | brainstorming / TDD / systematic-debugging / verification-before-completion | `--all --strict --json` | `archive <change-name>` |
| `bug-fix` | declare → the `ct6-converge` workflow with completion promise "…" → record | conditional (reports + native fallback, never blocks) | brainstorming / TDD / systematic-debugging / verification-before-completion | `--all --strict --json` | `archive <change-name>` |
| `mini` | declare → the `ct6-converge` workflow with completion promise "…" → record | conditional (reports + native fallback, never blocks) | brainstorming / TDD / systematic-debugging / verification-before-completion | `--all --strict --json` | `archive <change-name>` |
| `ux-test` | declare → the `ct6-converge` workflow with completion promise "…" → record | conditional (reports + native fallback, never blocks) | brainstorming / TDD / systematic-debugging / verification-before-completion | `n/a` (no change) | `n/a` (no change) |
