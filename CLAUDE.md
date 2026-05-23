# architect-team plugin

## Codebase Overview

This repo IS the source of the `architect-team` Claude Code plugin — a spec-to-production multi-agent coding pipeline. As of v0.9.26 it ships 22 skills, 22 named agents, 7 slash commands, 3 enforcement hooks, cross-platform setup scripts, and an opt-in per-project email notifier. The plugin orchestrates **MemPalace wake-up → Phase −2 (Triage) → Phase −1 → 8** against a requirements folder. v0.9.26 fixed cohesion-review issue #3: the `system-architect` agent's 7 audit modes (Diagnostic Plan Review, Editability Map Review, Interaction Map Review, Visual Gap Synthesis, Master Review Audit, Documentation Currency Audit, Bug-Fix Generalization Audit) documented writing verdict files but the agent had no `Write` tool — internally contradicting. v0.9.26 adds bounded `Write` (`.architect-team/` paths only); new `## Bounded Write scope` section enumerates the 7 allowed paths. v0.9.25 gave bug-fix-pipeline its own Phase B3 validation gate; v0.9.24 fixed wake-up ordering; v0.9.23 added the **`doc-updater` agent**; v0.9.22 added the **`bug-fix-pipeline` + Phase −2 triage routing**.

**Stack:** Markdown (skills/agents/commands), JSON (plugin/marketplace/hooks metadata), Python 3.10+ (hooks + setup scripts + the stdlib-only `scripts/notify/` email notifier + 890 pytest self-tests).

**Structure:** `.claude-plugin/` (identity), `skills/` (22 dirs), `agents/` (22 files), `commands/` (7 files), `hooks/` (JSON wiring + 3 enforcement scripts + a shared `review_evidence_schema.py` module — review-gate evidence schema v6), `scripts/setup/` (`setup.py` + `install_mempalace.py`), `scripts/notify/` (`notify.py` — the best-effort, stdlib-only per-project email notifier the orchestrator invokes for the five pipeline events when a project supplies `.architect-team-notify.json`; v0.9.18), `tests/` (890 pytest tests across 42 test files with structural + cross-consistency coverage), `docs/` (CODEBASE_MAP.md, INTEGRATION_MAP.md, `superpowers/` historical design + plan).

For full architecture, file purposes, conventions, gotchas, and a navigation guide, see [`docs/CODEBASE_MAP.md`](docs/CODEBASE_MAP.md).

## Conventions at a glance

- Author commits with explicit override (repo's local git config has a "Paul Ingrram" typo):
  `git -c user.name="Paul Ingram" -c user.email="paulingram@users.noreply.github.com" commit ...`
- Run the test suite via `python -m pytest -v` from repo root (647 PASS expected as of v0.9.19).
- Bump version: update `.claude-plugin/plugin.json` + `.claude-plugin/marketplace.json` + `CHANGELOG.md`.
- Runtime state lives under `.architect-team/` (gitignored): reviews, teammates, handoffs, etc.
