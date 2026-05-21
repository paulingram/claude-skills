# architect-team plugin

## Codebase Overview

This repo IS the source of the `architect-team` Claude Code plugin — a spec-to-production multi-agent coding pipeline. As of v0.9.16 it ships 18 skills, 16 named agents, 6 slash commands, 3 enforcement hooks, and cross-platform setup scripts. The plugin orchestrates Phase −1 → 8 (intake/mapping → spec validation → parallel teams → review gates → reconciliation → integration → master review → final report) against a requirements folder.

**Stack:** Markdown (skills/agents/commands), JSON (plugin/marketplace/hooks metadata), Python 3.10+ (hooks + setup scripts + 423 pytest self-tests).

**Structure:** `.claude-plugin/` (identity), `skills/` (18 dirs), `agents/` (16 files), `commands/` (6 files), `hooks/` (JSON wiring + 3 enforcement scripts + a shared `review_evidence_schema.py` module), `scripts/setup/` (`setup.py` + `install_mempalace.py`), `tests/` (423 pytest tests with structural + cross-consistency coverage), `docs/` (CODEBASE_MAP.md, INTEGRATION_MAP.md, `superpowers/` historical design + plan).

For full architecture, file purposes, conventions, gotchas, and a navigation guide, see [`docs/CODEBASE_MAP.md`](docs/CODEBASE_MAP.md).

## Conventions at a glance

- Author commits with explicit override (repo's local git config has a "Paul Ingrram" typo):
  `git -c user.name="Paul Ingram" -c user.email="paulingram@users.noreply.github.com" commit ...`
- Run the test suite via `python -m pytest -v` from repo root (423 PASS expected as of v0.9.16).
- Bump version: update `.claude-plugin/plugin.json` + `.claude-plugin/marketplace.json` + `CHANGELOG.md`.
- Runtime state lives under `.architect-team/` (gitignored): reviews, teammates, handoffs, etc.
