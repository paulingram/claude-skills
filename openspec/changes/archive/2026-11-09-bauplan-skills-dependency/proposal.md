## Why

CT6 has no way to depend on a third-party plugin *conditionally*. Its only dependency mechanism — `REQUIRED_PLUGINS` in `scripts/setup/setup.py` — is a hard block: a missing member exits setup with code 1 (`setup.py:1141`). That is correct for superpowers, cartographer, and ralph-loop, which every run needs. It is wrong for a domain plugin that most users will never touch.

Bauplan Labs ships a Claude Code plugin (`bauplan` v1.0.0, MIT) with six data-lakehouse skills — explore, assess, build pipelines, ingest from S3 under write-audit-publish, generate quality checks, debug failed jobs. When CT6 runs against a project built on Bauplan, its agents should reach for those skills instead of producing generic data-engineering work that ignores the platform's hard safety rules (never write or import directly to `main`; branch and merge to publish). When CT6 runs against anything else, the plugin should be invisible and cost nothing.

Both halves need machinery CT6 does not have: a dependency tier that recommends without blocking, and a per-project trait check that arms the capability only where it applies.

## What Changes

- **A new conditional-dependency tier** in `scripts/setup/setup.py`, alongside `REQUIRED_PLUGINS` and explicitly outside its block-on-absence rule. Detected, reported, and recommended; never a non-zero exit. Reuses the existing `_PLUGIN_MARKETPLACE_SOURCES` third-party-marketplace registration and `plugin_remediation_lines()` (`setup.py:132`) to emit the `/plugin marketplace add BauplanLabs/bauplan-skills` → `/plugin install bauplan@bauplan-skills` remediation pair.
- **Two-signal arming, handled asymmetrically.** A `bauplan_project.yml` anywhere in the target repo arms the Bauplan path silently — a deterministic trait, discovered recursively so a monorepo subdirectory marker counts, mirroring the `**/`-glob detector pattern at `hooks/discipline_registry.py:204`. Stated Bauplan intent in the ask — including the greenfield case where no marker can yet exist — surfaces exactly one confirmation, then arms. Certain signals act; inferred signals ask.
- **Warn-and-degrade when the plugin is absent** but the project is Bauplan-shaped: the run proceeds with generic behavior and records the missed capability plus its remediation in the run report. Never blocks a run.
- **Bauplan safety context propagated via the existing guidance-block mechanism**, keyed on the project marker rather than on plugin presence — so the lakehouse safety rules survive the degraded path instead of vanishing exactly when the plugin is missing.
- **A reviewed injection-surface binding** mapping each of the six `bauplan-*` skills to the CT6 phase where it is the right tool, with an explicit precedence rule: bauplan skills AUGMENT CT6's invariants and never replace them. Phase D0 still dispatches `data-engineering-exploration` verbatim; a bauplan skill enriches that dispatch rather than standing in for it.
- **Behavioral evals** covering arming, non-arming, and greenfield reachability, in the existing opt-in `CT6_EVALS=1` tier so the default suite stays key-free.

No breaking changes. A run against a non-Bauplan project behaves exactly as it does today.

## Capabilities

### New Capabilities

- `conditional-plugin-dependency`: A non-blocking dependency tier — how a third-party plugin is registered, detected, reported at setup, and remediated when absent, without ever gating setup or a run. Domain-agnostic machinery; Bauplan is its first consumer.
- `project-trait-arming`: How a per-project trait (a marker file) or stated intent arms a capability for a run, with asymmetric handling — deterministic signals arm silently, inferred signals require one confirmation — and what a declined or unarmed run records.
- `bauplan-integration`: The Bauplan-specific binding — which `bauplan-*` skill belongs at which CT6 phase, the augment-never-replace precedence rule, and the propagation of Bauplan's lakehouse safety context into a target project.

### Modified Capabilities

- `uniform-plugin-usage`: The "all four plugins are verified at setup ... and block on any absence" requirement gains an explicit boundary — the four hard prerequisites keep blocking; conditionally-depended plugins are verified and reported but never contribute to a non-zero exit.
- `installer-guidance-blocks`: The capability gate for a guidance block may key on a detected project trait, not only on installed-capability presence, so safety context can persist when the capability it describes is unavailable.
- `behavioral-evals`: The opt-in tier gains routing/arming evals exercising a marker-shaped fixture.

## Impact

- **Code**: `scripts/setup/setup.py` (new tier + reporting), `hooks/discipline_registry.py` (marker detector), `scripts/setup/guidance_blocks.py` (trait-keyed capability check), the injection points chosen by the surface review — candidates are `skills/data-eng-pipeline/SKILL.md`, `skills/data-engineering-exploration/SKILL.md`, `skills/bug-fix-pipeline/SKILL.md`, and the 39 `agents/*.md` via `scripts/setup/sync_agent_boilerplate.py`.
- **Tests**: new unit tests for the tier, the detector, and the trait-keyed gate; new `tests/evals/` fixtures behind `CT6_EVALS=1`.
- **Dependencies**: a new OPTIONAL external plugin (`bauplan@bauplan-skills`, MIT). No new Python dependency — CT6 stays stdlib-only. CT6 never handles Bauplan credentials; the plugin's own auth chain is used as-is.
- **Docs**: `docs/CODEBASE_MAP.md` (new modules + a stale `last_mapped` stamp to correct), `docs/CAPABILITY_INDEX.md` (regenerated), `CHANGELOG.md`, `CLAUDE.md`.
- **Not affected**: the three existing hard dependencies keep their hardness; `hooks/skill_invocation_audit.py` and every other Layer-6 enforcement hook are explicitly out of scope.
