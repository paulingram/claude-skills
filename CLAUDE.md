# architect-team plugin

## Codebase Overview

This repo IS the source of the `architect-team` Claude Code plugin — a spec-to-production multi-agent coding pipeline. As of v0.10.0 it ships **26 skills, 27 named agents, 11 slash commands**, 3 enforcement hooks, cross-platform setup scripts, and an opt-in per-project email notifier. The plugin orchestrates **MemPalace wake-up → Phase −2 (Triage) → Phase −1 → 8** against a requirements folder, with sibling pipelines for **bug-fix** (`/architect-team:bug-fix`), **UX testing** (`/architect-team:ux-test`, v0.9.29), and **mini** (`/architect-team:mini`, v0.10.0). **v0.10.0 introduces the mini-architect-team-pipeline** — a faster sibling to `/architect-team` for rapid small-to-medium feature changes. Single architect (drafts the full 5-artifact OpenSpec bundle with a mandatory `## QA Guidance` section, self-confirms to a fixed point), parallel backend + frontend devs cross-reviewing each other (no separate `task-reviewer`), single `mini-qa` agent (unit + integration + ≤3 narrow Playwright flows against the live dev URL). Auto-merges to `main` on green QA; cycle cap = 3 on re-eval; cycle 4 escalates to full `/architect-team`. Every commit carries `Mini-Run: <slug>`; companion `/architect-team:mini-review-sweep` replays the full heavyweight review gates in batch. **v0.9.36 closes two structural defects in the bug-fix pipeline**: (1) testing enforcement — B1 and B6 now mandate verdict files with execution-proof fields, checked by the `pipeline-completion-audit` hook; the pipeline cannot complete without proof tests were actually run against the live dev environment; (2) anti-deferral — both pipelines now explicitly forbid clustering identified issues and deferring some to "separate runs"; every bug identified in a run gets fixed in that run. (v0.9.35 audited and refined the v0.9.34 email-testing discipline — Mailpit search API, pre-test cleanup, Docker container collision fix, redirect chain documentation, expanded language indicators, Windows PowerShell binary fallback, 38 new tests.)

**Stack:** Markdown (skills/agents/commands), JSON (plugin/marketplace/hooks metadata), Python 3.10+ (hooks + setup scripts + the stdlib-only `scripts/notify/` email notifier + 1343 pytest self-tests).

**Structure:** `.claude-plugin/` (identity), `skills/` (26 dirs), `agents/` (27 files), `commands/` (11 files), `hooks/` (JSON wiring + 3 enforcement scripts + a shared `review_evidence_schema.py` module — review-gate evidence schema v6), `scripts/setup/` (`setup.py` + `install_mempalace.py`), `scripts/notify/` (`notify.py` — the best-effort, stdlib-only per-project email notifier the orchestrator invokes for the five pipeline events when a project supplies `.architect-team-notify.json`; v0.9.18, wired in BOTH pipelines after v0.9.27), `tests/` (~1417 pytest tests across 65 test files with structural + cross-consistency coverage), `docs/` (CODEBASE_MAP.md, INTEGRATION_MAP.md, `superpowers/` historical design + plan).

For full architecture, file purposes, conventions, gotchas, and a navigation guide, see [`docs/CODEBASE_MAP.md`](docs/CODEBASE_MAP.md).

## Conventions at a glance

- Author commits with explicit override (repo's local git config has a "Paul Ingrram" typo):
  `git -c user.name="Paul Ingram" -c user.email="paulingram@users.noreply.github.com" commit ...`
- Run the test suite via `python -m pytest -v` from repo root (~1417 PASS expected as of v0.10.0).
- Bump version: update `.claude-plugin/plugin.json` + `.claude-plugin/marketplace.json` + `CHANGELOG.md`.
- Runtime state lives under `.architect-team/` (gitignored): reviews, teammates, handoffs, etc.
