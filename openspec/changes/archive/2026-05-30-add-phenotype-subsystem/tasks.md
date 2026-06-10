# Tasks — add the phenotype subsystem

## 1. Subsystem core
- [ ] 1.1 Create `phenotypes/` with `README.md` (index + how-it-works) and `SCHEMA.md` (manifest + scaffold-manifest schema reference).
- [ ] 1.2 Implement `scripts/phenotypes/phenotypes.py` (stdlib): `phenotypes_dir`, `discover_phenotypes`, `validate_phenotype`, `load_phenotype`, `match_phenotype`, `emit_scaffold` + a `list|show|match|validate|emit` CLI.

## 2. Consumption skill + wiring
- [ ] 2.1 Author `skills/phenotypes/SKILL.md` (discovery, matching, trigger, consumption flow, schemas, absorb design); register in `tests/test_skills.py::EXPECTED_SKILLS`.
- [ ] 2.2 Add `--phenotype <label>` flag parsing + "use the X phenotype" phrasing to `commands/architect-team.md`.
- [ ] 2.3 Add the phenotype auto-suggest rung (never-silent) to `skills/reuse-first-design/SKILL.md`.
- [ ] 2.4 Reference phenotype consumption from `skills/architect-team-pipeline/SKILL.md`; document phenotype mining/recall in `skills/mempalace-integration/SKILL.md`.

## 3. Seed phenotype (user-management)
- [ ] 3.1 Author `phenotypes/user-management/blueprint.md` (10-section schema; incl. How-they-interrelate + Deployment).
- [ ] 3.2 Author `phenotypes/user-management/scaffold/` (generalized backend + frontend + OpenTofu templates) + `scaffold.manifest.json`.
- [ ] 3.3 Author `phenotypes/user-management/phenotype.json` (validates; no secrets/account-specifics).

## 4. Tests
- [ ] 4.1 `tests/test_phenotypes_helper.py` — unit tests for discover/validate/match/emit (incl. the user-mgmt-match + dry-run + missing-param scenarios).
- [ ] 4.2 `tests/test_phenotype_subsystem.py` — structural tests (dir layout, skill body, flag parse, seed record validates, blueprint sections present).

## 5. Docs + release
- [ ] 5.1 Update `README.md` (inventory + NEW IN), `CHANGELOG.md`, `docs/CODEBASE_MAP.md`.
- [ ] 5.2 Bump `.claude-plugin/plugin.json` + `marketplace.json`.
- [ ] 5.3 Run `python -m pytest -v` to green.

## 6. Checkpoint
- [ ] 6.1 Commit the vertical slice to `architect-team/phenotypes`; present the checkpoint report; pause for review before confgigs + AI-mgmt phenotypes + the absorb build.

## Deferred (post-checkpoint follow-up change)
- confgigs (OpenTofu config-management) phenotype.
- AI-management phenotype.
- The `absorb` capability build (`/architect-team:absorb-phenotype` + `skills/phenotype-absorption/`).
