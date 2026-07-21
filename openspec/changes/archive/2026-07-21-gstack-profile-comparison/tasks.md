# tasks — gstack-profile-comparison

## 1. Verify staging (REQ-001)

- [x] 1.1 Confirm `~/Downloads/gstack-main/` exists with package contents (unpacked during refinement); confirm no gstack content under the repo tree.

## 2. Four-tier profile (REQ-002) — 4 parallel profiler subagents, static read only

- [x] 2.1 Tier A — skill format: root `SKILL.md` + per-skill `SKILL.md`/`SKILL.md.tmpl` system, frontmatter/structure conventions, skill inventory count, template/generation mechanism. Findings → `findings/tier-a-skill-format.md`.
- [x] 2.2 Tier B — `bin/` tool tier: enumerate tools, classify (brain/memory, artifacts, analytics, browser, dev-env), read key tools' headers/usage. Findings → `findings/tier-b-bin-tools.md`.
- [x] 2.3 Tier C — evals CI: `evals.yml`, `evals-periodic.yml`, `version-gate.yml`, `skill-docs.yml`, `make-pdf-gate.yml`, Windows workflows — what is gated, how skills are evaluated. Findings → `findings/tier-c-evals-ci.md`.
- [x] 2.4 Tier D — architecture/ethos docs: `ARCHITECTURE.md`, `ETHOS.md`, `CLAUDE.md`, `AGENTS.md`, `BROWSER.md`, `README.md`, `USING_GBRAIN_WITH_GSTACK.md`; skim `CHANGELOG.md`/`TODOS.md` for recency/direction. Findings → `findings/tier-d-docs.md`.

## 3. Comparison synthesis (REQ-003)

- [x] 3.1 Build the surface-by-surface matrix (skill format / quality-verification / tooling / docs / memory-context / agent-model config) with two-sided citations.
- [x] 3.2 Author the three narrative sections (gstack-better / CT6-better / ideas-to-adopt).

## 4. Adversarial verification (REQ-003 scenario 2)

- [x] 4.1 Independent reviewer re-resolves every citation on both sides; refutes weak/overreaching claims; report corrected until verdict is pass.

## 5. Adoption backlog (REQ-004)

- [x] 5.1 Write `adoption-backlog.md` — SR-style items, value/effort/ratio scored, ordered by ratio; path recorded in the report.

## 6. Finalize (REQ-005)

- [x] 6.1 Persist report + backlog to the MAIN checkout's `.architect-team/gstack-comparison/`; present findings in full in-chat.
- [x] 6.2 Verify repo hygiene: worktree `git status` shows only this OpenSpec change.
- [x] 6.3 Phase 7 master-review audit (independent) → `overall: pass`; `openspec validate --all --strict` green; archive the change.
