# architect-team plugin

## Codebase Overview

This repo IS the source of the `architect-team` Claude Code plugin — a spec-to-production multi-agent coding pipeline. As of v0.9.28 it ships 22 skills, 22 named agents, 7 slash commands, 3 enforcement hooks, cross-platform setup scripts, and an opt-in per-project email notifier. The plugin orchestrates **MemPalace wake-up → Phase −2 (Triage) → Phase −1 → 8** against a requirements folder. **The v0.9.23 cohesion review (10 issues) is now closed across v0.9.24-v0.9.28** — wake-up ordering, bug-fix Phase B3 gate, system-architect bounded Write, bug-fix-pipeline notifications, confirmed-stubs cross-reference between Phase −1D and Phase 5, plus four polish items (historical-marker, nomenclature, sub-headings, audit-modes index, cache-lag documentation). v0.9.28 specifically wires the confirmed-stubs cross-reference: Phase −1D's `user_verdict: confirmed-stub` entries now flow downstream to Phase 5's interaction-completeness team (pre-population on `element_id`); the user is never asked the same question twice across the two phases.

**Stack:** Markdown (skills/agents/commands), JSON (plugin/marketplace/hooks metadata), Python 3.10+ (hooks + setup scripts + the stdlib-only `scripts/notify/` email notifier + 924 pytest self-tests).

**Structure:** `.claude-plugin/` (identity), `skills/` (22 dirs), `agents/` (22 files), `commands/` (7 files), `hooks/` (JSON wiring + 3 enforcement scripts + a shared `review_evidence_schema.py` module — review-gate evidence schema v6), `scripts/setup/` (`setup.py` + `install_mempalace.py`), `scripts/notify/` (`notify.py` — the best-effort, stdlib-only per-project email notifier the orchestrator invokes for the five pipeline events when a project supplies `.architect-team-notify.json`; v0.9.18, wired in BOTH pipelines after v0.9.27), `tests/` (924 pytest tests across 44 test files with structural + cross-consistency coverage), `docs/` (CODEBASE_MAP.md, INTEGRATION_MAP.md, `superpowers/` historical design + plan).

For full architecture, file purposes, conventions, gotchas, and a navigation guide, see [`docs/CODEBASE_MAP.md`](docs/CODEBASE_MAP.md).

## Conventions at a glance

- Author commits with explicit override (repo's local git config has a "Paul Ingrram" typo):
  `git -c user.name="Paul Ingram" -c user.email="paulingram@users.noreply.github.com" commit ...`
- Run the test suite via `python -m pytest -v` from repo root (647 PASS expected as of v0.9.19).
- Bump version: update `.claude-plugin/plugin.json` + `.claude-plugin/marketplace.json` + `CHANGELOG.md`.
- Runtime state lives under `.architect-team/` (gitignored): reviews, teammates, handoffs, etc.
