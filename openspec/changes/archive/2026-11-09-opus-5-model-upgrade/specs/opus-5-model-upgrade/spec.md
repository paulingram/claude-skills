# opus-5-model-upgrade — delta spec

## ADDED Requirements

### Requirement: Claude Opus 5 is the plugin's named Opus generation

Every version-bearing Opus reference on a non-frozen surface SHALL name **Claude Opus 5** / `claude-opus-5` — the real Claude API id AND alias under the 4.6-generation-and-later dateless scheme `claude-{name}-{major}[-{minor}]`. The plugin SHALL NOT emit `claude-opus-5-0`, a dated `claude-opus-5-YYYYMMDD`, or a `-v1`-suffixed form, none of which exist. `scripts/setup/set_default_model.py`'s two version-bearing narrative lines (the module docstring's fallback sentence and the delivery-split header comment) SHALL name Opus 5, while its versionless Opus mentions — including the `--split` argparse help's reference to "the v3.43.0 delivery-adversarial Opus split" — SHALL remain untouched, since they correctly name a past release's policy rather than a model generation.

#### Scenario: the lever's version-bearing prose names Opus 5

- **WHEN** `scripts/setup/set_default_model.py` is read after the change
- **THEN** its module docstring and its delivery-split header comment name Opus 5, and no `Opus 4.8` / `Opus-4.8` string remains in the file

#### Scenario: versionless policy references are not gratuitously rewritten

- **WHEN** the `--split` argparse help text is compared against its pre-change bytes
- **THEN** it is unchanged — it names the v3.43.0 policy, not a model generation, so there was no version to refresh

#### Scenario: no invented id form is emitted

- **WHEN** the repository is swept for `claude-opus-5-0`, `claude-opus-5-2` followed by six digits, or `anthropic.claude-opus-5-v1`
- **THEN** zero matches are found

### Requirement: Agent frontmatter keeps the floating Opus alias

The 12 delivery + adversarial agents SHALL continue to carry the bare harness alias `model: opus`, and the 27 planning / validation / review agents SHALL continue to carry `model: fable`. No `agents/*.md` file SHALL be modified by this change, and `tests/test_agents.py` — including its `VALID_MODELS` allow-list, which admits no `claude-opus-*` id — SHALL pass unmodified. Rationale: the harness resolves `opus` to the current Opus generation, so the delivery agents inherit Opus 5 with zero edits, whereas a dateless id such as `claude-opus-5` is a **pinned snapshot** rather than an evergreen pointer and would convert a self-maintaining alias into a recurring per-release edit.

#### Scenario: agent frontmatter is byte-identical

- **WHEN** `git diff` for this change is inspected
- **THEN** no file under `agents/` appears in the diff

#### Scenario: the delivery split still holds exactly

- **WHEN** the on-disk set of agents carrying `model: opus` is compared against `DELIVERY_ADVERSARIAL_AGENTS`
- **THEN** the two sets are equal and the count is 12, with the remaining 27 agents on `model: fable`

### Requirement: Gateway explicit-route coverage for Opus 5

`scripts/setup/install_gateway.py`'s `ANTHROPIC_EXPLICIT_MODELS` SHALL include `claude-opus-5`, and SHALL retain every previously-listed id including `claude-opus-4-8`, `claude-opus-4-7`, and `claude-opus-4-6`. The tuple is an allow-list of ids given explicit per-model gateway routes — necessary because the `*` catch-all was observed non-functional on a real LiteLLM install (SR-gateway-wildcard-route) — and is therefore NOT a statement of which generation is current; removing a legacy id would strand callers still using it. The ordering comment SHALL be refreshed so it no longer describes `claude-opus-4-8` as "the implemented fallback".

#### Scenario: Opus 5 is routable

- **WHEN** `ANTHROPIC_EXPLICIT_MODELS` is inspected after the change
- **THEN** it contains `claude-opus-5`

#### Scenario: legacy routes are retained

- **WHEN** the post-change tuple is compared against the pre-change tuple
- **THEN** every pre-change id is still present and the tuple's length has grown by exactly one

### Requirement: Commit trailers attribute the current model

Every pipeline body that emits a `Co-Authored-By` commit trailer naming an Opus generation SHALL name `Claude Opus 5 (1M context)`. This covers exactly 7 live surfaces: `commands/architect-team.md`, `commands/classify-test-prod-safety.md`, `commands/visual-qa.md`, `commands/visual-to-api.md`, `skills/architect-team-pipeline/SKILL.md`, `skills/bug-fix-pipeline/SKILL.md`, and `skills/mini-architect-team-pipeline/SKILL.md`. The literal prefix `Co-Authored-By: Claude Opus ` SHALL be preserved, because `tests/test_dispatch_banner.py` locates the trailer block by that exact substring. `commands/optimize-structure.md`'s `Co-Authored-By: Claude Fable 5` trailer is not an Opus surface and SHALL remain byte-identical.

#### Scenario: no stale trailer survives

- **WHEN** `commands/` and `skills/` are swept for `Co-Authored-By: Claude Opus 4.7`
- **THEN** zero matches are found, and all 7 surfaces read `Claude Opus 5 (1M context)`

#### Scenario: the dispatch-banner trailer anchor still resolves

- **WHEN** `tests/test_dispatch_banner.py` searches the three pipeline SKILL.md bodies for `Co-Authored-By: Claude Opus`
- **THEN** the substring is found in each and the `Dispatch-Mode:` proximity assertions still pass

#### Scenario: the Fable trailer is not collaterally rewritten

- **WHEN** `commands/optimize-structure.md` is compared against its pre-change bytes
- **THEN** it is unchanged

### Requirement: Current-state documentation updated, release history frozen

Documentation SHALL be corrected where it asserts what the plugin ships **today** and SHALL be left byte-identical where it records what a **past release did**. The 6 current-state lines to correct are `CLAUDE.md:9`, `CLAUDE.md:33`, `docs/CODEBASE_MAP.md:293`, `docs/CODEBASE_MAP.md:360`, `docs/INTEGRATION_MAP.md:20`, and `README.md:1729`. The 6 historical lines to freeze are `CLAUDE.md:60`, `docs/CODEBASE_MAP.md:36`, `README.md:132`, `README.md:251`, `README.md:256`, and `README.md:1698`. The discriminator SHALL be tense and function, not file or proximity: `docs/CODEBASE_MAP.md:360` is version-tagged yet describes what the lever presently IS and is the direct mirror of `scripts/setup/set_default_model.py:6`, so the two SHALL move together — updating the module while freezing its map entry would leave the map contradicting the module it documents.

#### Scenario: no frozen line is touched

- **WHEN** `git diff -U0` for this change is inspected against the merge base
- **THEN** no hunk overlaps any of the 6 enumerated frozen lines

#### Scenario: the map entry and its module agree

- **WHEN** `docs/CODEBASE_MAP.md:360`'s fallback clause is compared against `scripts/setup/set_default_model.py`'s module docstring
- **THEN** both name Opus 5

#### Scenario: the doubly-stale integration map is corrected

- **WHEN** `docs/INTEGRATION_MAP.md`'s model paragraph is read after the change
- **THEN** it names the v3.43.0 delivery-adversarial split with Opus 5 rather than describing uniform `model: fable` with an Opus 4.8 fallback

### Requirement: Bounded, countable coverage

The change's scope SHALL be verifiable by a mechanically-reproducible sweep rather than by reviewer judgment. The sweep `grep -rniE "opus[- ]?4[.-][78]" --include=*.py --include=*.md --include=*.json .`, excluding `CHANGELOG.md`, `openspec/changes/archive/**`, `docs/superpowers/**`, `__pycache__`, and `.architect-team/`, SHALL return exactly 36 lines before the change and exactly 11 after, in three justified classes: the 6 frozen narrative lines; the 2 retained legacy entries in `ANTHROPIC_EXPLICIT_MODELS` plus the 2 lines of `tests/test_install_gateway.py` that assert and explain that retention; and the 1 line of the `fable-default-setup-fixes` delta spec where the forbidden strings appear as the quoted SUBJECT of a negative assertion. No surviving hit SHALL be on a surface that asserts CURRENT state. The pattern SHALL be case-insensitive AND SHALL admit the hyphenated `Opus-4.8` form; a case-sensitive `opus|OPUS` pattern demonstrably misses `services/common/service_config.py:31` and `tests/test_set_default_model.py:6`.

#### Scenario: post-change sweep count is exact

- **WHEN** the sweep runs after the change
- **THEN** it returns exactly 11 lines, each matching an entry in the coverage map's `surface_contract.post_change_expected_lines` together with that entry's stated justification

#### Scenario: a surviving hit is never a current-state assertion

- **WHEN** each of the 11 surviving lines is read in context
- **THEN** every one is either frozen release history, a deliberately-retained routable legacy id (or its explaining comment / asserting test), or a quoted forbidden-string subject — and none of them tells a reader that the plugin currently ships on Opus 4.8 or 4.7

#### Scenario: a case-sensitive sweep is insufficient

- **WHEN** a case-sensitive `opus|OPUS` sweep is compared against the case-insensitive one on the pre-change tree
- **THEN** the case-sensitive sweep misses at least `services/common/service_config.py:31` and `tests/test_set_default_model.py:6`

### Requirement: Release shape and suite honesty

The change SHALL ship as a MINOR release **3.45.0**, with `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, and `CHANGELOG.md`'s top entry all agreeing, and the CHANGELOG entry SHALL satisfy `docs/CHANGELOG_RUBRIC.md` (version match plus a suite-total line) as mechanized by `scripts/docs_tooling/changelog_check.py`. The suite result SHALL be reported against the measured pre-change baseline on the executing machine — `5948 passed, 2 failed, 5 skipped` on this Windows checkout — with **no new failures and no new skips**. The 2 pre-existing failures (`tests/test_installer_guidance_blocks.py::test_remove_deletes_exactly_and_byte_preserves` and `tests/test_skill_references.py::test_target_skill_byte_count_reduced_vs_baseline[common-pipeline-conventions]`) are line-ending artifacts outside this change's scope; they SHALL be reported by name as pre-existing, SHALL NOT be "fixed" by editing recorded byte counts, and the run SHALL NOT claim a fully green suite.

#### Scenario: version sources agree

- **WHEN** `plugin.json`, `marketplace.json`, and `CHANGELOG.md` are read after Phase 8
- **THEN** all three say 3.45.0 and `scripts/docs_tooling/changelog_check.py` passes

#### Scenario: the two pre-existing failures are reported honestly

- **WHEN** the final report states the suite result
- **THEN** it names both pre-existing failures explicitly, attributes them to the Windows line-ending artifact rather than to this change, and does not describe the suite as fully green

#### Scenario: no new failure is introduced

- **WHEN** the post-change suite is compared against the 5948/2/5 baseline
- **THEN** the passing count has not decreased other than by tests intentionally re-pinned, and no test outside the enumerated pin set has changed status
