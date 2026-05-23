# architect-team plugin

## Codebase Overview

This repo IS the source of the `architect-team` Claude Code plugin — a spec-to-production multi-agent coding pipeline. As of v0.9.21 it ships 21 skills, 18 named agents, 6 slash commands, 3 enforcement hooks, cross-platform setup scripts, and an opt-in per-project email notifier. The plugin orchestrates Phase −1 → 8 (intake/mapping → spec validation → parallel teams → review gates → reconciliation → integration → master review → final report) against a requirements folder. v0.9.21 added the **`interaction-intuition` skill + `interaction-intuiter` agent + Phase −1D bulk-verify gate** — per-frontend `INTERACTION_INTUITION_MAP.md` artifacts cross-walking design × routes × API produced at Phase −1D, with a bulk user-verify gate (`all correct` / numbered list of incorrect indices / `all incorrect`) before Phase 0, and the confirmed map as a binding input to spec authoring + coverage criteria. The Phase −1D gate is a *domain gate*, not a process gate — it fires regardless of `--proposal-first` (the gates-opt-in rule, v0.9.20, applies to process gates only).

**Stack:** Markdown (skills/agents/commands), JSON (plugin/marketplace/hooks metadata), Python 3.10+ (hooks + setup scripts + the stdlib-only `scripts/notify/` email notifier + 730 pytest self-tests).

**Structure:** `.claude-plugin/` (identity), `skills/` (21 dirs), `agents/` (18 files), `commands/` (6 files), `hooks/` (JSON wiring + 3 enforcement scripts + a shared `review_evidence_schema.py` module — review-gate evidence schema v6), `scripts/setup/` (`setup.py` + `install_mempalace.py`), `scripts/notify/` (`notify.py` — the best-effort, stdlib-only per-project email notifier the orchestrator invokes for the five pipeline events when a project supplies `.architect-team-notify.json`; v0.9.18), `tests/` (730 pytest tests with structural + cross-consistency coverage), `docs/` (CODEBASE_MAP.md, INTEGRATION_MAP.md, `superpowers/` historical design + plan).

For full architecture, file purposes, conventions, gotchas, and a navigation guide, see [`docs/CODEBASE_MAP.md`](docs/CODEBASE_MAP.md).

## Conventions at a glance

- Author commits with explicit override (repo's local git config has a "Paul Ingrram" typo):
  `git -c user.name="Paul Ingram" -c user.email="paulingram@users.noreply.github.com" commit ...`
- Run the test suite via `python -m pytest -v` from repo root (647 PASS expected as of v0.9.19).
- Bump version: update `.claude-plugin/plugin.json` + `.claude-plugin/marketplace.json` + `CHANGELOG.md`.
- Runtime state lives under `.architect-team/` (gitignored): reviews, teammates, handoffs, etc.
