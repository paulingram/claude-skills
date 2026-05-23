# architect-team plugin

## Codebase Overview

This repo IS the source of the `architect-team` Claude Code plugin — a spec-to-production multi-agent coding pipeline. As of v0.9.22 it ships 22 skills, 21 named agents, 7 slash commands, 3 enforcement hooks, cross-platform setup scripts, and an opt-in per-project email notifier. The plugin orchestrates Phase −2 → 8 (triage → intake/mapping → spec validation → parallel teams → review gates → reconciliation → integration → master review → final report) against a requirements folder. v0.9.22 added the **`bug-fix-pipeline` skill + `/architect-team:bug-fix` command + `bug-replicator` / `qa-replayer` / `bug-classifier` agents + Phase −2 triage dispatch** — a sibling orchestrator (phases B−1 → B8) with five non-negotiable disciplines (replicate-first, reproduction-is-the-regression-test, generalize-never-patch, QA-replay-against-live-dev, live-dev-environment-by-default). The main `/architect-team` auto-triages incoming requirements: pure-bug routes to bug-fix-pipeline, pure-feature continues to the existing flow, `mixed` spawns BOTH in parallel, `unclear` asks the user. The `system-architect` gained a new Bug-Fix Generalization Audit mode that rejects symptom patches unless the user explicitly authorized a hotfix.

**Stack:** Markdown (skills/agents/commands), JSON (plugin/marketplace/hooks metadata), Python 3.10+ (hooks + setup scripts + the stdlib-only `scripts/notify/` email notifier + 824 pytest self-tests).

**Structure:** `.claude-plugin/` (identity), `skills/` (22 dirs), `agents/` (21 files), `commands/` (7 files), `hooks/` (JSON wiring + 3 enforcement scripts + a shared `review_evidence_schema.py` module — review-gate evidence schema v6), `scripts/setup/` (`setup.py` + `install_mempalace.py`), `scripts/notify/` (`notify.py` — the best-effort, stdlib-only per-project email notifier the orchestrator invokes for the five pipeline events when a project supplies `.architect-team-notify.json`; v0.9.18), `tests/` (824 pytest tests across 38 test files with structural + cross-consistency coverage), `docs/` (CODEBASE_MAP.md, INTEGRATION_MAP.md, `superpowers/` historical design + plan).

For full architecture, file purposes, conventions, gotchas, and a navigation guide, see [`docs/CODEBASE_MAP.md`](docs/CODEBASE_MAP.md).

## Conventions at a glance

- Author commits with explicit override (repo's local git config has a "Paul Ingrram" typo):
  `git -c user.name="Paul Ingram" -c user.email="paulingram@users.noreply.github.com" commit ...`
- Run the test suite via `python -m pytest -v` from repo root (647 PASS expected as of v0.9.19).
- Bump version: update `.claude-plugin/plugin.json` + `.claude-plugin/marketplace.json` + `CHANGELOG.md`.
- Runtime state lives under `.architect-team/` (gitignored): reviews, teammates, handoffs, etc.
