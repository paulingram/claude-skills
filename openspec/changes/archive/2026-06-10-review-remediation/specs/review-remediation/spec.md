## ADDED Requirements

### Requirement: Glue-layer code executes correctly across platforms

The plugin SHALL ensure its enforcement glue — hook wiring, VAO CLI tools, the in-flight inbox, and every subprocess / stdin boundary — executes correctly and does not silently fail, double-execute, or no-op on either a `python3`-only host or a `python`-only Windows host, under either cp1252 or UTF-8.

#### Scenario: hook wiring detect-once, no double invocation (A1)

- **WHEN** `hooks/hooks.json` is read
- **THEN** every hook command selects the interpreter once via `$(command -v python3 || command -v python)` and invokes its script exactly once
- **AND** no command contains the `" || python "` double-invocation form that re-runs the script on a meaningful exit-2 BLOCK

#### Scenario: the three VAO CLI tools run as a bare-module script (A2)

- **WHEN** `python hooks/vao_tools.py verify-discipline-registry-current`, `... verify-inflight-clarifications-processed`, and `... verify-no-unilateral-override` are each invoked from the repo root
- **THEN** each runs to a normal verdict and does NOT raise `ModuleNotFoundError`
- **AND** the three lazy imports each use the dual-form `try: from hooks.X import ... / except ImportError: from X import ...` fallback

#### Scenario: Windows backslash review paths are counted (A3)

- **WHEN** `verify_no_pipeline_bypass` evaluates a tool-call ledger whose review-evidence path uses Windows backslashes (e.g. `...\.architect-team\reviews\T-1.json`)
- **THEN** the path is normalized (backslashes to forward slashes, lowercased) before the `/reviews/` membership check
- **AND** the tool does NOT emit a false `independent-review-bypassed` severity for that ledger

#### Scenario: the in-flight inbox is atomic and path-safe (A4)

- **WHEN** `inflight_inbox.py::mark_processed` rewrites the inbox
- **THEN** it writes to a temp file and `os.replace`s it into place atomically, so a concurrently-appended message is never destroyed and a crash never truncates the inbox
- **AND** a `run_id` containing `/`, `\`, a leading `.`, or `..` is rejected via `safe_id` before it reaches the inbox filename

#### Scenario: teams_mode and worktree_lifecycle expose the invoked CLIs (A5, A6)

- **WHEN** `scripts/setup/teams_mode.py --banner --command "/architect-team:inject"` runs
- **THEN** it prints the dispatch banner and exits 0 (best-effort: a banner-helper error still exits 0)
- **AND WHEN** `scripts/setup/worktree_lifecycle.py cleanup-merged --against origin/main --dry-run` runs
- **THEN** it prints a one-line summary and exits 0 even on a cleanup error

#### Scenario: subprocess calls are encoding-safe and time-bounded (A7)

- **WHEN** the text-mode subprocess calls in `worktree_lifecycle.py`, `worktree_paths.py`, `setup.py`, and `pipeline-completion-audit.py` are read
- **THEN** every text-mode call carries `encoding="utf-8", errors="replace"`
- **AND** the network git operations (`git push`, `git push --delete`) carry a bounded `timeout=` whose `TimeoutExpired` routes to the existing best-effort failure path

#### Scenario: hook stdin is decoded as UTF-8 (A8)

- **WHEN** `pipeline-completion-audit.py`, `review-gate-task.py`, `teammate-idle-check.py`, and `pretool_unilateral_override_guard.py` read stdin
- **THEN** each decodes via `sys.stdin.buffer.read().decode("utf-8", "replace")`
- **AND** a UTF-8 payload (e.g. an emoji in a task title) does not degrade the gate to a silent no-op under cp1252

#### Scenario: an OSError on evidence read fails the gate closed (A9)

- **WHEN** the evidence `read_text` in `review-gate-task.py` or `teammate-idle-check.py` raises `OSError` (e.g. a Windows sharing violation)
- **THEN** the hook catches `OSError` alongside `json.JSONDecodeError` and treats it as a blocking gap, identical to the missing-file branch
- **AND** the gate does NOT traceback to exit 1 and silently skip

#### Scenario: CANONICAL_COMMANDS matches the real command set and the matcher is precise (A10)

- **WHEN** `hooks/skill_invocation_audit.py` is loaded
- **THEN** `CANONICAL_COMMANDS` equals exactly the set of `commands/*.md` basenames (19 entries; no `mempalace-search` / `mempalace-status` / `code-review` phantoms)
- **AND** a structural test asserts that equality against the live `commands/` directory so it cannot drift
- **AND** the slash matcher does NOT fire on a `/status`-like substring inside a URL or file path
- **AND** the prose matcher DOES fire on the documented space-form trigger "use my architect team"

### Requirement: The command surface honors its own invocation conventions

The plugin SHALL ensure every command file invokes Python via the cross-platform conventions it documents, carries the pipeline-discipline blocks its siblings carry, and passes user input robustly.

#### Scenario: inject snippets resolve the plugin root and pass the message safely (B1)

- **WHEN** `commands/inject.md` is read
- **THEN** every python snippet that imports `hooks.inflight_inbox` first inserts `${CLAUDE_PLUGIN_ROOT}` onto `sys.path`
- **AND** the message is passed to the snippet via environment variable or stdin (not via `'''${MESSAGE}'''` interpolation), so quotes / `$` in the message do not break the command

#### Scenario: ux-test carries the full pipeline-discipline preamble (B2)

- **WHEN** `commands/ux-test.md` is read
- **THEN** it carries, in the same order as `commands/architect-team.md`, the v1.5.0 dispatch banner FIRST, the v1.3.0 worktree auto-cleanup, the v3.7.0 branch reconciliation, the v1.2.0 auto-worktree creation, and the v2.5.0 in-flight clarification section
- **AND** each block is adapted to the ux-test slug

#### Scenario: exit-2-capable command invocations are detect-once (B3)

- **WHEN** `commands/discipline-status.md`, `commands/architect-team.md`, `commands/bug-fix.md`, `commands/mini.md`, `commands/classify-test-prod-safety.md`, and `commands/visual-to-api.md` are read
- **THEN** their mutating or exit-2-capable invocations (`verify-discipline-registry-current`, `create_run_worktree`, the `teams_mode`/`worktree_lifecycle` CLIs) use the detect-once `$(command -v python3 || command -v python)` form
- **AND** the structural polyglot tests for those command files enforce the detect-once form for those invocations

#### Scenario: setup command allowed-tools is correct (B4)

- **WHEN** `commands/architect-team-setup.md` frontmatter is read
- **THEN** its `allowed-tools` includes `Bash(python:*)` (the documented Windows fallback)
- **AND** the dead `Bash(${CLAUDE_PLUGIN_ROOT}/...)` rule (env vars do not expand in permission rules) is removed

#### Scenario: absorb-phenotype invocation is anchored and detect-once (B5)

- **WHEN** `commands/absorb-phenotype.md` is read
- **THEN** the `scripts/phenotypes/phenotypes.py` invocation is anchored with `${CLAUDE_PLUGIN_ROOT}` and uses the detect-once interpreter selection

### Requirement: Skill bodies teach the system as the code actually implements it

The plugin SHALL ensure its skill bodies and READMEs describe the shipped code accurately — the current evidence-schema version, the unbounded-solving model, real invocation paths, and a complete set of referenced notes — and that every skill description complies with the Agent Skills length limit.

#### Scenario: the evidence schema is taught as v7 everywhere (C1)

- **WHEN** the six locations that teach the schema version are read (`team-spawning-and-review-gates` frontmatter + JSON example, `architect-team-pipeline`, `bug-fix-pipeline`, `mini-architect-team-pipeline`, `common-pipeline-conventions`, `README.md`)
- **THEN** each states schema v7 (not v6)
- **AND** the full JSON example carries the 17 required fields including the five required VAO fields in their string-or-dict shapes, consistent with `hooks/review_evidence_schema.py`

#### Scenario: bug-fix-pipeline uses the plugin-root path, not a hardcoded cache path (C2)

- **WHEN** `skills/bug-fix-pipeline/SKILL.md` is read near the former hardcoded `vao_tools.py` invocation
- **THEN** it invokes `${CLAUDE_PLUGIN_ROOT}/hooks/vao_tools.py` via detect-once
- **AND** no hardcoded `/Users/.../0.9.35/...` cache path or literal `"..."` fallback remains

#### Scenario: unbounded-solving residue is reconciled (C3)

- **WHEN** the skill/command locations carrying bounded-loop language are read (`architect-team-pipeline` review loop + 3-pass lines, `editability-completeness`, `interaction-completeness`, `mini-architect-team-pipeline` description + `mini.md`, `ux-test-builder` description + `ux-test.md` + the `flaky` verdict, `verified-agent-output` oracle re-feed)
- **THEN** none claims a fixed "bounded at 3 cycles" / "cycle cap = 3" convergence cap
- **AND** each expresses loop-until-converged with a pause only for required owner input, consistent with the v3.8.0 unbounded-solving model

#### Scenario: the MemPalace not-on-PATH note exists and is reachable (C4)

- **WHEN** `skills/mempalace-integration/SKILL.md` `## Phase A` is read
- **THEN** it contains the canonical note: when the `mempalace` CLI is not on PATH, surface ONE line to the user, suggest `/architect-team:mempalace-install`, and continue the run with MemPalace steps as no-ops (never hard-fail)
- **AND** the four pipeline bodies that defer to this note (`architect-team-pipeline`, `bug-fix-pipeline`, `mini-architect-team-pipeline`, `common-pipeline-conventions`) reference a note that now exists

#### Scenario: the undefined Phase B3b reference is resolved (C5)

- **WHEN** `skills/bug-fix-pipeline/SKILL.md` is read where it referenced "Phase B3b"
- **THEN** the reference is resolved consistently — either reworded to "the SR-intake behavior inherited from the main pipeline's Phase 3b" or defined explicitly as B3b — with no remaining dangling reference

#### Scenario: every skill description is within the 1024-char limit (C6)

- **WHEN** every `skills/*/SKILL.md` frontmatter `description` is measured
- **THEN** each is ≤ 1024 characters, trigger-first ("Use when …" + a capability sentence), with any displaced operative detail moved into the skill body so no information is lost
- **AND** a structural test caps every skill description at 1024 characters

### Requirement: Project documentation is internally consistent and version-stamped

The plugin SHALL ensure its project documentation (`CLAUDE.md`, `docs/CODEBASE_MAP.md`, `README.md`, `docs/INTEGRATION_MAP.md`, `CHANGELOG.md`) is internally consistent with the post-run codebase and that the version is bumped in the source-of-truth manifests.

#### Scenario: CLAUDE.md self-contradictions are reconciled (D1)

- **WHEN** `CLAUDE.md` is read
- **THEN** the test-count claims agree on the post-run actual (one format, e.g. "<N> passing + 5 skipped across <M> test files"), the VAO-tool count is stated once as the true count (20+), the enforcement-script count is 4 (including `pretool_unilateral_override_guard.py`), the commands parenthetical names the actual most-recent joiner, and the historical "all 27 agents" claims are annotated "(then 27, now 34)"

#### Scenario: CODEBASE_MAP reflects the current inventory (D2)

- **WHEN** `docs/CODEBASE_MAP.md` is read
- **THEN** §1 and the mermaid diagram state v-current with 40 skills / 34 agents / 19 commands / the actual test count
- **AND** §4 lists the two previously-missing hook files `hooks/override_markers.py` and `hooks/pretool_unilateral_override_guard.py`

#### Scenario: README schema and HOOKS box are corrected (D3)

- **WHEN** `README.md` is read
- **THEN** it teaches schema v7 (per C1)
- **AND** the HOOKS box states 4 scripts across 6 events, including the PreToolUse row

#### Scenario: the version is bumped and the CHANGELOG enumerates the fixes (D4)

- **WHEN** `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, and `CHANGELOG.md` are read
- **THEN** `plugin.json` and `marketplace.json` carry the bumped version (3.9.3)
- **AND** `CHANGELOG.md` has an entry enumerating this run's A–E fixes
- **AND** `docs/INTEGRATION_MAP.md` is current for any cross-file contract this change touched

### Requirement: Regression tests prevent the defect class from re-shipping

The plugin SHALL carry regression coverage that executes the real command/hook glue and remains green under both Windows cp1252 and `PYTHONUTF8=1`, so the silent-failure defect class cannot re-ship undetected.

#### Scenario: the execute-the-glue family resolves and exercises every invocation (E1)

- **WHEN** the test suite runs the glue-execution family
- **THEN** for every fenced `python`/`python3` invocation in `commands/*.md` and every command string in `hooks/hooks.json`, the target script is resolved and asserted to exist
- **AND** for scripts invoked with a subcommand/flag (`--banner`, `cleanup-merged`, vao_tools subcommands), the script is executed with safe args (`--help` / a dry-run / a temp-cwd equivalent) and asserted to neither traceback nor silently no-op on an unknown argument

#### Scenario: the item-specific regression tests pass (E2)

- **WHEN** the suite runs the A1–A10 / B / C item-specific tests
- **THEN** each pins its fix (detect-once hooks, runnable VAO CLIs, atomic inbox, normalized paths, UTF-8 stdin, OSError handling, the regenerated CANONICAL_COMMANDS + matcher fixes, the command-file fixes, the schema-v7 docs)

#### Scenario: the suite is green under both encodings (E3)

- **WHEN** `python -m pytest` runs once under default Windows cp1252 and once under `PYTHONUTF8=1`
- **THEN** the full suite passes in both, with all new tests additive and no pre-existing test regressed
