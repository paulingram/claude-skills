# Tasks

## 1. Ralph-loop uniformity (REQ-001)
- [ ] 1.1 Scrub stale `--max-iterations` from `README.md`, `docs/INTEGRATION_MAP.md`, `openspec/changes/exploration-pipeline/design.md` (actual invocations only; leave removal-description prose).
- [ ] 1.2 Convert prose-promise ralph loops in `data-engineering-exploration` + `domain-research-team` to the explicit `--completion-promise` flag form.

## 2. Superpowers HARD dependency + concrete invocation (REQ-002)
- [ ] 2.1 `setup.py`: required-plugin absence is a hard block; docstring + report wording state superpowers is a hard dependency.
- [ ] 2.2 Each pipeline body gains a `## Plugin prerequisites (v3.9.0)` superpowers pre-flight abort gate.
- [ ] 2.3 Wire concrete `superpowers:brainstorming` / `:test-driven-development` / `:systematic-debugging` / `:verification-before-completion` invocations at named phases.

## 3. OpenSpec gate parity (REQ-003)
- [ ] 3.1 `mini`: add `openspec validate --all --strict --json` + `openspec archive <change>` (keep `git merge --ff-only`).
- [ ] 3.2 `bug-fix`: align `openspec validate --strict` → `openspec validate --all --strict`.

## 4. Plugin enforcement at setup (REQ-004)
- [ ] 4.1 Add `openspec-propose` to the verified prerequisite set; all required plugins block on absence.

## 5. Canonical contract + VAO fix (REQ-005)
- [ ] 5.1 Add `## Uniform plugin usage (v3.9.0)` to `common-pipeline-conventions`; reference it from every pipeline body.
- [ ] 5.2 Fix `verify-no-pipeline-bypass` to recognize the `openspec-propose` skill path + the mini flow.

## 6. Tests + release
- [ ] 6.1 Structural + behavioral tests for all of the above; full `python -m pytest` green.
- [ ] 6.2 Version bump (v3.9.0) across `plugin.json` + `marketplace.json` + `CHANGELOG.md`; docs current.
