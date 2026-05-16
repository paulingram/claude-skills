# Changelog

All notable changes to this project will be documented in this file.

## [0.2.1] — 2026-05-16

### Fixed
- Removed `disable-model-invocation: true` from `skills/architect-team-pipeline/SKILL.md`. The flag prevented the Skill tool from loading the orchestrator body, which broke the entire delegation chain — `/architect-team:architect-team <path>` would run the command's wrapper text but then fail to load the actual Phase −1 → 8 playbook (the Skill tool refused with "cannot be used due to disable-model-invocation"). The slash command is still the recommended user entry point; the model can now also auto-invoke the orchestrator when a user prompt clearly matches the skill's description.

## [0.2.0] — 2026-05-16

### Fixed (breaking)
- **Renamed orchestrator skill: `architect-team` → `architect-team-pipeline`.** The slash command `/architect-team:architect-team` was colliding with a skill of the same name; the Skill tool resolved to the command body (a thin wrapper) instead of the orchestrator's Phase −1 → 8 playbook, so the pipeline never actually ran. The skill directory is now `skills/architect-team-pipeline/`, the SKILL.md frontmatter `name` is `architect-team-pipeline`, and `commands/architect-team.md` now invokes `skill: architect-team-pipeline`. No user-visible slash-command changes — `/architect-team:architect-team <path>` continues to work and now correctly runs the orchestrator.
- Test `tests/test_skills.py` `EXPECTED_SKILLS` updated to match.

### Migration
Teammates with v0.1.x already installed should `/plugin uninstall architect-team@architect-team-marketplace`, then `git pull` inside `~/.claude/plugins/marketplaces/architect-team-marketplace/`, then re-install. Or fully delete the marketplace cache and re-add.

## [0.1.1] — 2026-05-16

### Fixed
- `scripts/setup/setup.py`: `_install_packages` now passes `--system` to `uv pip install` when no virtual environment is active. Previously, `uv` was preferred over plain pip when present, but `uv pip install` refuses to install outside a venv unless `--system` is given — which caused Playwright (and any other pip-installed dep) to fail on machines with `uv` on PATH but no active venv.
- Venv detection now checks `VIRTUAL_ENV`, `sys.real_prefix`, and `sys.base_prefix != sys.prefix` (the three standard signals).

## [0.1.0] — 2026-05-16

Initial release.

### Added
- Plugin metadata: `plugin.json`, `marketplace.json` (one-plugin marketplace).
- 8 skills: `architect-team`, `intake-and-mapping`, `reuse-first-design`, `frontend-route-mapping`, `playwright-user-flows`, `dev-api-integration-testing`, `coverage-mapping`, `team-spawning-and-review-gates`.
- 10 agents: `system-architect`, `frontend`, `backend`, `reconciler`, `integration`, `scaffold-agent`, `codebase-map-reviewer`, `integration-explorer`, `master-synthesizer`, `route-mapper`.
- 2 commands: `/architect-team`, `/architect-team-setup`.
- 2 hooks: `PostToolUse(TaskUpdate)` review-gate enforcement, `SubagentStop` teammate-idle check.
- Cross-platform setup script: `scripts/setup/setup.py`.
- 52 pytest self-tests covering structural validity of every shipped file plus hook + setup logic.

### Install

```
/plugin marketplace add https://github.com/paulingram/claude-skills.git
/plugin install architect-team@architect-team-marketplace
/architect-team-setup
```

### Requires
- Python ≥ 3.10, Node ≥ 20.19.
- Claude plugins: `superpowers@claude-plugins-official`, `cartographer@cartographer-marketplace`, `ralph-loop@claude-plugins-official`.
- NPM package: `@fission-ai/openspec` (installed by setup).
- Python packages: `pytest`, `pytest-asyncio`, `httpx`, `playwright` (installed by setup).
- Browsers: Playwright chromium (installed by setup).
