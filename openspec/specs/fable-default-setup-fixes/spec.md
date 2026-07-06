# fable-default-setup-fixes Specification

## Purpose
TBD - created by archiving change fable-default-setup-fixes. Update Purpose after archive.
## Requirements
### Requirement: Cartographer marketplace provenance

The plugin SHALL document where the `cartographer-marketplace` lives (`kingbootoshi/cartographer`) everywhere a user meets the dependency: the `architect-team-setup` check output SHALL print the exact two-step remediation (`/plugin marketplace add kingbootoshi/cartographer` then `/plugin install cartographer@cartographer-marketplace`) when cartographer is missing, and the README setup section SHALL state the source.

#### Scenario: missing cartographer prints the marketplace source

- **WHEN** the setup check runs on a machine without the cartographer plugin
- **THEN** its output names `kingbootoshi/cartographer` as the marketplace source and prints both remediation commands in order

#### Scenario: README documents the source

- **WHEN** the README setup section is read
- **THEN** it names the `kingbootoshi/cartographer` marketplace source next to the cartographer install step

### Requirement: npm EACCES fallback

The openspec npm install step SHALL detect a permission failure (EACCES / unwritable global prefix), retry non-persistently with `--prefix ~/.local`, and print the persistent remediation (`npm config set prefix ~/.local` + the PATH note) — never silently mutating the user's npm configuration.

#### Scenario: EACCES triggers the prefix retry

- **WHEN** the global npm install fails with an EACCES/permission error (simulated via an injected runner)
- **THEN** the step retries with `--prefix ~/.local`
- **AND** the result message includes the persistent-remediation text

### Requirement: PEP-668 Python-deps install ladder

The Python-deps step SHALL walk the ladder `uv pip install --system` → `pip install --user` → `pip install --user --break-system-packages` (the last only on the externally-managed-environment error), SHALL emit an actionable hint (e.g. `apt install python3-pip`) when no pip is importable instead of crashing, and the dep list SHALL include `tiktoken`.

#### Scenario: externally-managed environment falls through the ladder

- **WHEN** the user-level pip install fails with the externally-managed-environment marker (simulated)
- **THEN** the step retries with `--break-system-packages`

#### Scenario: pip absent yields a hint, not a crash

- **WHEN** neither uv nor pip is available
- **THEN** the step reports the missing-pip condition with the platform hint and exits the check as failed-with-remediation (no traceback)

#### Scenario: tiktoken is in the dependency list

- **WHEN** the Python dep list is inspected
- **THEN** it includes `tiktoken` alongside the existing pytest/httpx/playwright deps

### Requirement: Non-interactive consent

`setup.py` SHALL accept a `--yes` flag AND honor a `CT6_SETUP_ASSUME_YES` env var (truthy set {"1","true","yes"}) that answer every consent prompt affirmatively without reading stdin, making the full setup runnable non-interactively.

#### Scenario: --yes short-circuits the teams-mode prompt

- **WHEN** setup runs with `--yes` (or the env var truthy) on a machine without the teams flag configured
- **THEN** the teams-mode settings write proceeds without any `input()` call

### Requirement: Fully-qualified command forms in docs

Every CT6 doc SHALL print plugin commands in the namespaced form (`/architect-team:<cmd>`); the five README bare `/architect-team-setup` sites SHALL be corrected, and no in-scope doc may instruct a bare form.

#### Scenario: README carries no bare command instructions

- **WHEN** the README is grepped for bare `/architect-team-setup` (not preceded by `architect-team:`)
- **THEN** zero instructional sites remain

### Requirement: Fable 5 agent-model default

All 39 `agents/*.md` SHALL declare `model: fable`; `tests/test_agents.py` SHALL include `fable` in `VALID_MODELS` and SHALL pin the uniform-fable state; and a NEW stdlib lever `scripts/setup/set_default_model.py` SHALL rewrite (`--model fable|opus|sonnet|haiku`) or report (`--check`) the frontmatter model field across all agents, idempotently — the implemented fallback path to Opus for harnesses without the fable alias, surfaced (never auto-applied) by the setup check.

#### Scenario: every agent is fable

- **WHEN** `grep '^model:' agents/*.md` runs
- **THEN** all 39 rows read `model: fable`

#### Scenario: the lever flips and restores uniformly

- **WHEN** `set_default_model.py --model opus` then `--model fable` run against a copy of the tree
- **THEN** each pass rewrites exactly the 39 model fields (bodies untouched) and `--check` reports the uniform state after each

#### Scenario: setup surfaces the fallback remediation

- **WHEN** the setup check concludes the running harness predates the fable alias (heuristic version gate)
- **THEN** it prints the `set_default_model.py --model opus` remediation instead of silently rewriting anything

### Requirement: Fable 5 service-tier default with injected fallback

`services/common/service_config.py` SHALL set `DEFAULT_MODEL = "claude-fable-5"` and `FALLBACK_MODEL = "claude-opus-4-8"`, and SHALL provide `resolve_model(preferred, fallback, availability_checker=None)` — returning `preferred` when no checker is injected (the live probe is an adapter boundary) and `fallback` when an injected checker rejects `preferred` — with `build_llm_client` routing through it and the module staying import-clean per `check_separation()`.

#### Scenario: no checker prefers fable

- **WHEN** `resolve_model()` runs with defaults and no checker
- **THEN** it returns `claude-fable-5`

#### Scenario: rejecting checker falls back to opus

- **WHEN** an injected checker returns False for `claude-fable-5`
- **THEN** `resolve_model` returns `claude-opus-4-8`

#### Scenario: separation invariant holds

- **WHEN** `check_separation()` runs after the change
- **THEN** `services/common/service_config.py` remains import-clean (stdlib + in-repo only)

### Requirement: Version and documentation currency

The release SHALL ship as v3.32.0 (plugin.json + marketplace.json), with a CHANGELOG entry and the documentation-currency inventory (README, CLAUDE.md, the two maps' model-pattern/conventions lines) refreshed at the Phase 8 gate, and the full pytest suite SHALL be green with the environment-explained split.

#### Scenario: version source-of-truth agrees

- **WHEN** plugin.json and marketplace.json are read after Phase 8
- **THEN** both say 3.32.0 and the CHANGELOG's top entry is [3.32.0]

#### Scenario: suite green after the change

- **WHEN** `python -m pytest` runs from the worktree after all edits
- **THEN** zero failures, with the pass/skip split explained by the 3 known environment-conditional tests plus any tests this change legitimately adds

### Requirement: Skill-gate teammate and peer-message exclusions

`hooks/pretool_skill_gate.py` arm 1 (the most-recent-genuine-prompt check) SHALL stand down in teammate/sidechain sessions exactly as arm 2 does, and SHALL exclude teammate-message user-role records (SendMessage-injected peer messages) from the genuine-user-prompt anchor, so that (a) pipeline teammates are never blocked on Write/Edit/Agent/Task and (b) inbound peer messages cannot re-arm the gate past a Lead's satisfying Skill call — while every existing genuine-bypass catch stays intact.

#### Scenario: teammate session stands down

- **WHEN** the gate evaluates a transcript carrying the CT6-TEAMMATE marker (or sidechain records) with a pipeline command as the latest genuine prompt
- **THEN** arm 1 allows the tool call (stand-down), matching arm 2's existing teammate behavior

#### Scenario: peer messages do not re-arm the gate

- **WHEN** the gate evaluates a Lead transcript where a satisfying Skill call is followed only by teammate-message user-role records
- **THEN** the anchor remains the genuine user prompt that the Skill call satisfied and the tool call is allowed

#### Scenario: genuine bypasses are still caught

- **WHEN** the existing test corpus of genuine build/dispatch-before-Skill transcripts runs post-fix
- **THEN** every previously-caught bypass is still blocked (no recall regression)

### Requirement: Deterministic lock-concurrency test

The intermittent failure of `tests/test_locks_concurrency.py::test_n_threads_same_scope_exactly_one_winner` (a threading race observed across four independent suite runs) SHALL be root-caused via the diagnostic-research loop and fixed generalizedly — the race closed in `hooks/locks.py` or the test's synchronization made sound, never a retry/sleep patch — preserving the exactly-one-winner invariant.

#### Scenario: the test is deterministic post-fix

- **WHEN** the test file runs 50 consecutive times and the full suite runs 3 consecutive times under load
- **THEN** every run passes with the exactly-one-winner assertion intact

