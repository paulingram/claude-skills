# architect-team plugin

## Codebase Overview

This repo IS the source of the `architect-team` Claude Code plugin — a spec-to-production multi-agent coding pipeline. It ships 8 skills, 10 named agents, 2 slash commands, 2 enforcement hooks, and a cross-platform setup script. The plugin orchestrates Phase −1 → 8 (intake/mapping → spec validation → parallel teams → review gates → reconciliation → integration → master review → final report) against a requirements folder.

**Stack:** Markdown (skills/agents/commands), JSON (plugin/marketplace/hooks metadata), Python 3.10+ (hooks + setup script + 52 pytest self-tests).

**Structure:** `.claude-plugin/` (identity), `skills/` (8 dirs), `agents/` (10 files), `commands/` (2 files), `hooks/` (JSON wiring + 2 Python scripts), `scripts/setup/setup.py` (cross-platform installer), `tests/` (52 pytest tests with structural-validity coverage), `docs/superpowers/` (historical design + plan).

For full architecture, file purposes, conventions, gotchas, and a navigation guide, see [`docs/CODEBASE_MAP.md`](docs/CODEBASE_MAP.md).

## Conventions at a glance

- Author commits with explicit override (repo's local git config has a "Paul Ingrram" typo):
  `git -c user.name="Paul Ingram" -c user.email="paulingram@users.noreply.github.com" commit ...`
- Run the test suite via `python -m pytest -v` from repo root (52 PASS expected).
- Bump version: update `.claude-plugin/plugin.json` + `.claude-plugin/marketplace.json` + `CHANGELOG.md`.
- Runtime state lives under `.architect-team/` (gitignored): reviews, teammates, handoffs, etc.
