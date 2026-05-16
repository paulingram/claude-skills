# Changelog

All notable changes to this project will be documented in this file.

## [0.2.4] — 2026-05-16

### Fixed (python3-portability REQ-001: Setup command uses python3)
- `commands/architect-team-setup.md`: replaced bare `python` invocation with `python3` in both the body shell block and the `allowed-tools` frontmatter (`Bash(python:*)` → `Bash(python3:*)`). Fresh installs on stock Linux (Ubuntu, Debian, Fedora) and macOS 12.3+ — where only `python3` is on `$PATH` by default — now succeed instead of failing with `python: command not found`.

### Fixed (python3-portability REQ-002: Hooks use python3)
- `hooks/hooks.json`: both `command` strings (PostToolUse→`review-gate-task.py`, SubagentStop→`teammate-idle-check.py`) now invoke `python3` instead of bare `python`. Same Linux/macOS portability root cause as REQ-001.

### Added (python3-portability REQ-003: Setup script reports python3 PATH resolution)
- `scripts/setup/setup.py`: new `_python3_on_path() -> tuple[bool, str | None]` helper using `shutil.which("python3")`. Returns `(True, path)` on success, `(False, remediation_str)` on failure with per-`sys.platform` remediation: Linux → `python-is-python3`, macOS → `brew install python`, Windows → `py launcher` / `python.org installer`. Wired into `main()` as a non-fatal `python3-on-path` warning row in the status table.

### Added (python3-portability REQ-004: Test coverage)
- `tests/test_setup_script.py`: 3 new tests covering the helper (`test_python3_on_path_returns_true_when_present`, `_when_missing_linux`, `_when_missing_windows`).
- `tests/test_commands.py`: `test_setup_command_uses_python3` + `test_readme_documents_python3_prerequisite`.
- `tests/test_hooks_structure.py`: `test_hooks_use_python3` asserting both hook commands start with `python3 `.
- Total test count: 75 (up from 69).

### Documented (python3-portability REQ-005)
- `README.md`: new Prerequisites subsection listing `python3` as an explicit prerequisite with per-OS one-line remediation (Ubuntu/Debian apt, macOS brew, Windows python.org / py launcher).

### Released (python3-portability REQ-006: v0.2.4)
- `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`: version bumped `0.2.3` → `0.2.4`.
- Git annotated tag `v0.2.4` created with author override (`Paul Ingram`).
- Implemented end-to-end via the architect-team pipeline (Phase −1 mapping refresh + 3-reviewer ralph loop, OpenSpec validation gate, single backend teammate slice, review-gate evidence for REQ-001..REQ-005, full-suite verification).

## [0.2.3] — 2026-05-16

### Fixed (REQ-001: Command pre-binds $REQ_DIR for invoked skill)
- `commands/architect-team.md`: added explicit "IMPORTANT — path binding" instruction block telling the model to treat `$ARGUMENTS` as `$REQ_DIR` when invoking the `architect-team-pipeline` skill. The Claude Code harness does not propagate command `$ARGUMENTS` into skill bodies automatically; without this fix the orchestrator skill re-prompted the user for the requirements folder path even when it was already provided. The empty-`$ARGUMENTS` escape clause (ask the user, do nothing else) is preserved above the new instruction.

### Fixed (REQ-002: Path-traversal sanitization in hooks)
- `hooks/review-gate-task.py`: added `_safe_id(value)` helper that rejects identifiers containing `/`, `\`, starting with `.`, or equal to `..`; called on `task_id` before constructing the evidence file path. On rejection the hook exits 2 with a structured stderr message naming the unsafe identifier.
- `hooks/teammate-idle-check.py`: identical `_safe_id` helper added; called on the extracted subagent name before constructing the manifest file path. On rejection exits 2 with structured stderr.
- `tests/test_review_gate_task.py`, `tests/test_teammate_idle_check.py`: 8 new parametrized test cases covering `/`, `\`, leading `.`, and `..` traversal vectors in both hooks.

### Added (REQ-003: Test coverage for all validation branches)
- `tests/test_review_gate_task.py`: added `test_exits_two_when_quality_review_failing`, `test_exits_two_when_reuse_compliance_failing`, `test_exits_two_when_demo_artifact_empty` (both `""` and `"   "`), `test_exits_two_when_tests_added_zero`, `test_exits_two_when_evidence_json_malformed` — covering every previously-untested `_validate()` failure branch.
- `tests/test_teammate_idle_check.py`: added `test_subagent_name_flat_payload` — covers the alternate flat `{subagent_name: ...}` payload shape in `_extract_subagent_name()`.
- Total test count: 69 (up from 54).

### Added (REQ-004: Hook-rejection escalation policy)
- `skills/team-spawning-and-review-gates/SKILL.md`: added `## Hook-rejection escalation policy` section between "Teammate manifest" and "Review evidence" sections. Mandates: after 3 consecutive hook rejections on the same `task_id`, the teammate stops retrying, writes an escalation handoff at `.architect-team/handoffs/<teammate>-to-orchestrator-stuck-<task_id>-<timestamp>.md` (containing the task ID, verbatim hook stderr, what was tried, and clarification needed), and waits for orchestrator response.
- Frontmatter `description` extended to mention "and escalation policy on repeated hook rejection."

### Fixed (REQ-005: Spec drift cleanup)
- `docs/superpowers/specs/2026-05-16-architect-team-plugin-design.md`: replaced two occurrences of `--format=%ct` (lines 208 and 405) with `--format=%cI` (ISO 8601, matching every implementation file); replaced "manifest of assigned `task_ids[]`" (line 664) with "manifest's `expected_review_evidence` list (the set of task IDs for which review evidence is required)". No `%ct` or `task_ids[]` references remain.

### Released (REQ-006: v0.2.3)
- `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`: version bumped `0.2.2` → `0.2.3`.
- Git annotated tag `v0.2.3` created with author override (`Paul Ingram`).

## [0.2.2] — 2026-05-16

### Fixed (REQ-007: discovered via dogfood)
- `hooks/review-gate-task.py` no longer blocks ALL `TaskUpdate→completed` calls — only those whose `task_id` appears in some teammate manifest's `expected_review_evidence` list. Previously the hook fired on every TaskUpdate, breaking orchestrator-internal task tracking, user TaskCreate/TaskUpdate workflows, and any other plugin using TaskUpdate without architect-team semantics. New `_is_teammate_task()` helper walks `.architect-team/teammates/*.json`; absence of the teammates dir entirely (no architect-team workflow in progress) is also a hard allow.
- Two new tests: `test_exits_zero_when_task_not_in_any_manifest`, `test_exits_zero_when_no_teammates_dir`. Existing review-gate tests updated to write a teammate manifest claiming the task ID before exercising the gate.
- Also tightened the "missing taskId on completed" branch: now exits 0 instead of 2 (a TaskUpdate without taskId can't be looked up in any manifest, so we can't safely block — same reasoning as the manifest-absence case).

### Coming in v0.2.3+
The dogfood that found REQ-007 also surfaced the following open items from earlier reviews, all targeted for a follow-up pass:
- REQ-001: `$ARGUMENTS` propagation from command into invoked skill body.
- REQ-002: path-traversal sanitization on `task_id` / subagent `name` in both hooks.
- REQ-003: test coverage for `quality_review` / `reuse_compliance` / `demo_artifact` empty / `tests.added=0` validation branches; subagent_name flat-payload shape.
- REQ-004: hook-rejection escalation policy in `team-spawning-and-review-gates` skill.
- REQ-005: spec drift cleanup (`%ct`→`%cI` lines 208/405; "task_ids[]" line 664).
- REQ-006: CHANGELOG accuracy + tag/release polish.

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
