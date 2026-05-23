# architect-team plugin

## Codebase Overview

This repo IS the source of the `architect-team` Claude Code plugin — a spec-to-production multi-agent coding pipeline. As of v0.9.23 it ships 22 skills, 22 named agents, 7 slash commands, 3 enforcement hooks, cross-platform setup scripts, and an opt-in per-project email notifier. The plugin orchestrates Phase −2 → 8 (triage → intake/mapping → spec validation → parallel teams → review gates → reconciliation → integration → master review → final report + automatic doc-currency) against a requirements folder. v0.9.23 added the **`doc-updater` agent + Phase 8 / Phase B8 dispatch wiring** — promoted the documentation-currency update step from "the orchestrator performs the updates" to a dedicated opus agent with bounded `Write` (inventory paths only; NO `Edit`; NO source-code / test / openspec / version-JSON writes). Wired into BOTH the main `architect-team-pipeline` Phase 8 AND the `bug-fix-pipeline` Phase B8 — doc currency is now structurally automatic for both feature work and bug fixes; the `system-architect` Documentation Currency Audit mode (unchanged from v0.9.15) independently verifies; the audit verdict — not the agent's self-report — is what gates the commit (producer/checker discipline per v0.9.13). v0.9.22 still active: bug-fix-pipeline + Phase −2 triage routing in the main pipeline.

**Stack:** Markdown (skills/agents/commands), JSON (plugin/marketplace/hooks metadata), Python 3.10+ (hooks + setup scripts + the stdlib-only `scripts/notify/` email notifier + 858 pytest self-tests).

**Structure:** `.claude-plugin/` (identity), `skills/` (22 dirs), `agents/` (22 files), `commands/` (7 files), `hooks/` (JSON wiring + 3 enforcement scripts + a shared `review_evidence_schema.py` module — review-gate evidence schema v6), `scripts/setup/` (`setup.py` + `install_mempalace.py`), `scripts/notify/` (`notify.py` — the best-effort, stdlib-only per-project email notifier the orchestrator invokes for the five pipeline events when a project supplies `.architect-team-notify.json`; v0.9.18), `tests/` (857 pytest tests across 40 test files with structural + cross-consistency coverage), `docs/` (CODEBASE_MAP.md, INTEGRATION_MAP.md, `superpowers/` historical design + plan).

For full architecture, file purposes, conventions, gotchas, and a navigation guide, see [`docs/CODEBASE_MAP.md`](docs/CODEBASE_MAP.md).

## Conventions at a glance

- Author commits with explicit override (repo's local git config has a "Paul Ingrram" typo):
  `git -c user.name="Paul Ingram" -c user.email="paulingram@users.noreply.github.com" commit ...`
- Run the test suite via `python -m pytest -v` from repo root (647 PASS expected as of v0.9.19).
- Bump version: update `.claude-plugin/plugin.json` + `.claude-plugin/marketplace.json` + `CHANGELOG.md`.
- Runtime state lives under `.architect-team/` (gitignored): reviews, teammates, handoffs, etc.
