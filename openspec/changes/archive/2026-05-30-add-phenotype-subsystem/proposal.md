# Add the phenotype subsystem

## Why

The architect-team pipeline rebuilds common, well-understood application architectures from
scratch on every run that needs them — a user-management system, an OpenTofu cloud-deployment
layer, an AI agent/prompt versioning layer. The user maintains best-in-class reference
implementations of exactly these (in the sibling `limetree/` workspace) and wants the pipeline to
deploy them as **default solutions** on request, rather than reinventing them each time.

A **phenotype** is a labeled, generalized, *deployable* application-architecture pattern, captured
once and reused: a **blueprint** document + a parameterized **scaffold** (starter code + OpenTofu
templates) + **metadata**. When a request matches a phenotype, the pipeline proposes it
(reuse-first) or is told to use it explicitly, then customizes the scaffold to the specific request
instead of building blind.

This is the missing top rung of the reuse-first ladder: today `reuse-first-design` reasons over the
*target workspace*; phenotypes add a *cross-project library of proven architectures* to reuse from.

## What changes

**This change — the vertical slice, to a checkpoint:**

- NEW `phenotypes/` top-level directory — the phenotype library; each record =
  `phenotypes/<label>/{blueprint.md, scaffold/, phenotype.json}`.
- NEW `scripts/phenotypes/phenotypes.py` (stdlib) — discover / validate / match / emit-scaffold +
  a CLI. Deterministic matching + scaffold emission; the demonstrable, testable engine.
- NEW `skills/phenotypes/` skill — teaches the pipeline to discover, match (reuse-first, never
  silent), and consume (emit + customize) phenotypes; documents the schemas and the absorb design.
- Trigger wiring — `--phenotype <name>` flag + "use the X phenotype" phrasing in
  `commands/architect-team.md`; phenotype auto-suggest integrated into `skills/reuse-first-design`;
  phenotype consumption referenced from `architect-team-pipeline`; phenotype records mined into
  MemPalace (`skills/mempalace-integration`).
- The first SEED phenotype — **user-management** — authored from a deep analysis of the user's
  `globalUserManagement-Backend` + `globalUserManagementFrontEnd` + their OpenTofu deployment
  (`confgigs`), generalized.
- Tests (helper unit + structural + schema validation) + docs + version bump.

**Deferred to the post-checkpoint follow-up (designed here, not built this run):**

- The **confgigs** (OpenTofu config-management) and **AI-management** seed phenotypes.
- The **absorb** capability — `/architect-team:absorb-phenotype <path> --label <name>` command +
  `skills/phenotype-absorption/` skill — that ingests any arbitrary codebase into a new labeled
  phenotype.
- **Auto-deploy** (running OpenTofu against a live cloud) — explicitly out of scope; a phenotype
  produces a blueprint + scaffold, not a live deployment.

## Impact

- **Additive.** A new top-level dir, a new skill, a new helper, a new opt-in flag. With no phenotype
  requested (and none matched) the pipeline behaves exactly as before — zero behavior change.
- The reuse-first ladder gains a phenotype-match step that is a **proposal, never a silent
  application** (domain-gate discipline: the user confirms).
- **Affected files:** `commands/architect-team.md`, `skills/reuse-first-design/SKILL.md`,
  `skills/architect-team-pipeline/SKILL.md`, `skills/mempalace-integration/SKILL.md`, `README.md`,
  `CHANGELOG.md`, `docs/CODEBASE_MAP.md`, `.claude-plugin/plugin.json` + `marketplace.json`,
  `tests/` (new `EXPECTED_SKILLS` entry + new test files).
