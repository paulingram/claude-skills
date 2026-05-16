# architect-team

Spec-to-production multi-agent coding pipeline for Claude Code. Takes a requirements folder (OpenSpec / Superpowers / plain markdown), drives it through a 100%-coverage planning loop, spawns parallel agent teams for backend/frontend, enforces review gates, reconciles parallel work, and verifies with live dev-API + Playwright user-flow tests.

**Status:** v0.1.0 — initial scaffold.

See `docs/superpowers/specs/2026-05-16-architect-team-plugin-design.md` for the full design.

## Quick start

(Will be filled in by Task G1.)

## Requires

- Claude Code
- Prerequisite plugins (installed separately):
  - `superpowers@claude-plugins-official`
  - `cartographer@cartographer-marketplace`
  - `ralph-loop@claude-plugins-official`
- System: Python ≥ 3.10, Node ≥ 20.19
- The `/architect-team-setup` command installs the remaining CLI / pip / browser deps.

## License

MIT — see `LICENSE`.
