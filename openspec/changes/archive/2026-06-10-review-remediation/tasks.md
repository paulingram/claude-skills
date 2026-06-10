# Tasks

Two task groups with **strictly non-overlapping file scopes**. No file appears in both lists. Every requirement item A1–E3 is assigned to exactly one group (the E-items' suite-wide green is a cross-cutting orchestrator step, but each E-item's actual file work is owned per-dev with no shared file). Test files are partitioned so each is owned by exactly one dev (the dev who owns the production file the test asserts on).

Before starting, read **`## Pinned implementation decisions (zero judgment calls)`** and **`## Count-reconciliation ruling (cycle-2 binding)`** at the bottom — they resolve the detect-once JSON form, the A5/A6 command-invocation conversion decision, the exact new-test filenames, AND the exact post-run count values + the operative-vs-historical token rule, so neither dev has to make a judgment call and the doc-reconciliation (AC-4) is scored at THIS cycle gate (not deferred).

## Group BACKEND-DEV (Python behavior + Python-behavior tests)

**Owns these production files (no other group touches them):**
- `hooks/hooks.json`
- `hooks/vao_tools.py`
- `hooks/inflight_inbox.py`
- `hooks/skill_invocation_audit.py`
- `hooks/pipeline-completion-audit.py`
- `hooks/review-gate-task.py`
- `hooks/teammate-idle-check.py`
- `hooks/pretool_unilateral_override_guard.py`
- `scripts/setup/teams_mode.py`
- `scripts/setup/worktree_lifecycle.py`
- `scripts/setup/worktree_paths.py`
- `scripts/setup/setup.py`

**Owns these test files (Python-behavior + the hooks-structural tests that flip to detect-once):**
- `tests/test_hooks_structure.py` — **MUST be edited**: `test_hooks_use_python3` (L48) and `test_hooks_use_polyglot_python_fallback` (L65) currently assert the OLD `python3 X || python X` form; after A1 they must assert the detect-once contract instead (see Decision 1 in design.md + the pinned form below). This is a deliberate rewrite.
- `tests/test_vao_glue_execution.py` — **NEW** (E1 glue family + A2 bare-module-CLI execution for the vao_tools subcommands and the two new CLIs).
- `tests/test_vao_windows_path.py` — **NEW** (A3 backslash-path regression).
- `tests/test_inflight_inbox_atomic.py` — **NEW** (A4 atomic rewrite + `safe_id` rejection). The pre-existing `tests/test_vao_inflight_clarifications.py` is NOT touched (pin c).
- `tests/test_hooks_stdin_encoding.py` — **NEW** (A8 UTF-8 stdin for the 4 hooks).
- `tests/test_hooks_oserror_handling.py` — **NEW** (A9 OSError-fails-closed for the 2 hooks).
- `tests/test_skill_invocation_audit_canonical.py` — **NEW** (A10 `CANONICAL_COMMANDS == commands/*.md` basenames + the two matcher false-positive/false-negative tests). The pre-existing `tests/test_vao_skill_invocation_audit.py` is NOT touched (pin c).
- `tests/test_subprocess_encoding.py` — **NEW** (A7 source-structural assertion: every text-mode subprocess call in the 4 files carries `encoding=`; network ops carry `timeout=`).
- `tests/test_teams_mode_cli.py` — **NEW** (A5 CLI execution).
- `tests/test_worktree_lifecycle_cli.py` — **NEW** (A6 CLI execution).

**Assigned requirement items: A1, A2, A3, A4, A5, A6, A7, A8, A9, A10 (all of section A), plus the Python halves of E1, E2, E3.**

- [x] BD-1 (A1) Convert all **8** hook command strings in `hooks/hooks.json` (the 3 PreToolUse entries for `pretool_unilateral_override_guard.py` under matchers Edit/Write/NotebookEdit + PostToolUse(TaskUpdate) `review-gate-task.py` + TaskCompleted `review-gate-task.py` + SubagentStop `teammate-idle-check.py` + TeammateIdle `teammate-idle-check.py` + Stop `pipeline-completion-audit.py`) to the detect-once form, mirroring `commands/architect-team.md:175`. Use the EXACT JSON-string value pinned in `## Pinned implementation decisions` item (a). The 3 PreToolUse entries each carry the same script and so each get the identical command string. Then rewrite `tests/test_hooks_structure.py::test_hooks_use_python3` and `::test_hooks_use_polyglot_python_fallback` to assert the detect-once contract (each command starts with `$(command -v python3 || command -v python) `, contains exactly one `.py` invocation, names the same script throughout, and contains no ` || python ` double-invocation).
- [x] BD-2 (A2) Wrap the three lazy imports in `hooks/vao_tools.py` (~3596 discipline_registry, ~3676 inflight_inbox, ~4846 override_markers) in the dual-form `try: from hooks.X / except ImportError: from X` pattern (mirror lines 61–68). Add bare-module-execution regression coverage for `verify-discipline-registry-current` / `verify-inflight-clarifications-processed` / `verify-no-unilateral-override` in `tests/test_vao_glue_execution.py`.
- [x] BD-3 (A3) In `hooks/vao_tools.py:~4598` (`verify_no_pipeline_bypass`), normalize backslashes→`/` and lowercase BEFORE the `/reviews/` membership check, matching the openspec check ~4 lines below. Add the Windows-path regression test (`tests/test_vao_windows_path.py`).
- [x] BD-4 (A4) Rewrite `hooks/inflight_inbox.py::mark_processed` (~160–182) to temp-file + `os.replace` (mirror `run_metrics.py:184–186`). Add `safe_id` validation of `run_id` at the `_inbox_path` boundary (and any sibling path builders sharing it). Add atomic-survival + traversal-rejection tests in NEW `tests/test_inflight_inbox_atomic.py` (do NOT edit the existing `tests/test_vao_inflight_clarifications.py`).
- [x] BD-5 (A5) Add a minimal argparse `__main__` to `scripts/setup/teams_mode.py` supporting `--banner --command <name>` that prints `format_dispatch_banner()` best-effort (always exit 0 for banner). Add the CLI-execution test (`tests/test_teams_mode_cli.py`).
- [x] BD-6 (A6) Add a minimal argparse `__main__` to `scripts/setup/worktree_lifecycle.py` with a `cleanup-merged` subcommand (`--against`, `--dry-run`) delegating to `cleanup_merged_worktrees()`, printing a one-line summary, exit 0 on cleanup error. Add the `--dry-run` execution test (`tests/test_worktree_lifecycle_cli.py`).
- [x] BD-7 (A7) Add `encoding="utf-8", errors="replace"` to every text-mode subprocess call in `scripts/setup/worktree_lifecycle.py` (23 calls), `scripts/setup/worktree_paths.py` (~161), `scripts/setup/setup.py` (~161–273), `hooks/pipeline-completion-audit.py` (~326–329). Add bounded `timeout=` (60s local, 300s network push ~810 / push --delete ~852) with `TimeoutExpired` routed to the existing best-effort failure paths. Add the source-structural assertion test (`tests/test_subprocess_encoding.py`).
- [x] BD-8 (A8) Switch stdin decoding to `sys.stdin.buffer.read().decode("utf-8", "replace")` in `hooks/pipeline-completion-audit.py:~525`, `hooks/review-gate-task.py:~107`, `hooks/teammate-idle-check.py:~43`, `hooks/pretool_unilateral_override_guard.py:~209–214`. Add the UTF-8-payload test (`tests/test_hooks_stdin_encoding.py`).
- [x] BD-9 (A9) Add `OSError` to the evidence-`read_text` except in `hooks/review-gate-task.py:~151` and `hooks/teammate-idle-check.py:~98`; treat as a blocking gap (parity with missing-file). Add the OSError-fails-closed test (`tests/test_hooks_oserror_handling.py`).
- [x] BD-10 (A10) Regenerate `hooks/skill_invocation_audit.py:CANONICAL_COMMANDS` (44–58) to exactly the 19 `commands/*.md` basenames; drop the 3 phantoms (`mempalace-search`, `mempalace-status`, `code-review`). Fix matcher (a) slash-form no-match in URLs/paths + require `/architect-team:` prefix for generic single words, and (b) prose-form match for "architect team" space form (optional `my`/`your`/`the`). Add the directory-equality test + the false-positive (URL `/status`) and false-negative ("use my architect team") tests in NEW `tests/test_skill_invocation_audit_canonical.py` (do NOT edit the existing `tests/test_vao_skill_invocation_audit.py`). Keep exit semantics unchanged.
- [x] BD-11 (E1 — Python glue test) Author `tests/test_vao_glue_execution.py`: resolve every fenced `python`/`python3` invocation in `commands/*.md` and every `hooks/hooks.json` command string; assert target exists; execute flag/subcommand-bearing scripts with safe args; assert no traceback + not a silent unknown-arg no-op.
- [x] BD-12 (E2/E3 — Python item-specific) Ensure all BACKEND-DEV item-specific tests pass; confirm the BACKEND-DEV-owned tests are green under cp1252 AND `PYTHONUTF8=1` (new tests use explicit `encoding=` in any `read_text`).

## Group FRONTEND-DEV (Markdown / docs + Markdown-structural tests + version bump)

**Owns these production files (no other group touches them):**
- `commands/inject.md`
- `commands/ux-test.md`
- `commands/discipline-status.md`
- `commands/classify-test-prod-safety.md`
- `commands/visual-to-api.md`
- `commands/monitor-tests.md`
- `commands/architect-team.md`
- `commands/bug-fix.md`
- `commands/mini.md`
- `commands/architect-team-setup.md`
- `commands/absorb-phenotype.md`
- `skills/team-spawning-and-review-gates/SKILL.md`
- `skills/architect-team-pipeline/SKILL.md`
- `skills/bug-fix-pipeline/SKILL.md`
- `skills/mini-architect-team-pipeline/SKILL.md`
- `skills/common-pipeline-conventions/SKILL.md`
- `skills/editability-completeness/SKILL.md`
- `skills/interaction-completeness/SKILL.md`
- `skills/ux-test-builder/SKILL.md`
- `skills/verified-agent-output/SKILL.md`
- `skills/mempalace-integration/SKILL.md`
- `skills/visual-to-api-design/SKILL.md`, `skills/visual-fidelity-reconciliation/SKILL.md`, `skills/email-testing/SKILL.md`, `skills/proposal-refiner/SKILL.md` (the remaining C6 over-length descriptions not already listed above)
- `README.md`
- `CLAUDE.md`
- `docs/CODEBASE_MAP.md`
- `docs/INTEGRATION_MAP.md`
- `CHANGELOG.md`
- `.claude-plugin/plugin.json`
- `.claude-plugin/marketplace.json`

**Owns these test files (Markdown-structural tests that assert on command/skill bodies):**
- `tests/test_skills.py` — **MUST be edited**: add the 1024-char description-cap assertion across all `skills/*/SKILL.md` (C6). Currently only checks `len(description) > 20` (L76).
- `tests/test_visual_to_api_command.py` — **MUST be edited**: `test_command_body_uses_polyglot_python_pattern` (L68) asserts every python block in `visual-to-api.md` is `python3 ... || python ...`; after B3 converts the teams_mode/worktree_lifecycle invocations to detect-once it must accept/enforce the detect-once form for those blocks (pin b says they DO convert).
- `tests/test_monitor_tests_command.py` — **MUST be edited**: `test_command_uses_polyglot_python_pattern` (L48) asserts a `|| python` line in `monitor-tests.md`. Per pin (b) the monitor-tests teams_mode banner converts to detect-once, so this test flips to assert the detect-once form for that invocation.
- `tests/test_inject_command.py` — **MUST be edited**: `test_command_uses_polyglot_python_pattern` (L51) checks helper lines use `|| python`. Per pin (b), inject's teams_mode banner converts to detect-once but the inflight_inbox helper snippets (the ones B1 adds the `sys.path` insert to) stay polyglot; re-target the test's assertion so it checks the inflight_inbox helper lines (not the banner) use polyglot, and add a detect-once assertion for the banner line.
- `tests/test_commands.py` — **VERIFY (no edit expected)**: `test_setup_command_uses_python3` (L58) only requires `architect-team-setup.md` to contain `|| python ` somewhere; B4 edits only the frontmatter allowed-tools (L4), so the body's polyglot invocation is untouched and the test stays green. Also confirm `EXPECTED_COMMANDS` (19) still matches (this run adds/removes no command). If — and only if — the verification shows the body has no remaining `|| python ` invocation, edit the test; otherwise leave it.

**Assigned requirement items: B1, B2, B3, B4, B5 (all of section B), C1, C2, C3, C4, C5, C6 (all of section C), D1, D2, D3, D4 (all of section D), plus the Markdown/docs halves of E1, E2, E3.**

- [x] FD-1 (B1) Add the `${CLAUDE_PLUGIN_ROOT}` `sys.path` insert to every python snippet in `commands/inject.md` (`:43` RUN_ID detection, `:57–73` append blocks). Pass `${MESSAGE}` via environment variable or stdin instead of `'''${MESSAGE}'''` interpolation. Update `tests/test_inject_command.py` per pin (b).
- [x] FD-2 (B2) Port into `commands/ux-test.md`, in `architect-team.md` order, the v1.5.0 dispatch banner (FIRST), v1.3.0 worktree auto-cleanup, v3.7.0 branch reconciliation, v1.2.0 auto-worktree creation, and the v2.5.0 in-flight clarification section — adapted for the ux-test slug.
- [x] FD-3 (B3) Convert the exit-2-capable / mutating command invocations to detect-once: `discipline-status.md:45` (`verify-discipline-registry-current`), `create_run_worktree` in `architect-team.md:148`, `bug-fix.md:147`, `mini.md:127`, AND (per pin b) the `teams_mode --banner` + `worktree_lifecycle cleanup-merged` invocations from A5/A6 in `classify-test-prod-safety.md`, `visual-to-api.md`, `discipline-status.md`, `inject.md`, `monitor-tests.md`. Update `tests/test_visual_to_api_command.py`, `tests/test_monitor_tests_command.py`, and `tests/test_inject_command.py` to enforce detect-once for the converted invocations.
- [x] FD-4 (B4) In `commands/architect-team-setup.md:4`, add `Bash(python:*)` to `allowed-tools` and remove the dead `Bash(${CLAUDE_PLUGIN_ROOT}/...)` rule; match `mempalace-install.md:4`'s shape. Confirm `tests/test_commands.py::test_setup_command_uses_python3` still passes (body retains a polyglot invocation).
- [x] FD-5 (B5) Anchor `commands/absorb-phenotype.md:35` `phenotypes.py validate` with `${CLAUDE_PLUGIN_ROOT}` + detect-once.
- [x] FD-6 (C1) Update schema v6→v7 in `skills/team-spawning-and-review-gates/SKILL.md` (frontmatter L3 + JSON example ~135–139 → the v7 17-field example with the 5 VAO fields + 2 optional fields per design.md Decision 8), `skills/architect-team-pipeline/SKILL.md:~449`, `skills/bug-fix-pipeline/SKILL.md:~319`, `skills/mini-architect-team-pipeline/SKILL.md:~212`, `skills/common-pipeline-conventions/SKILL.md:~2261`, `README.md:294,623,966–968,1014`. Cross-check the field list against `hooks/review_evidence_schema.py`.
- [x] FD-7 (C2) Replace the hardcoded cache path in `skills/bug-fix-pipeline/SKILL.md:401–405` with `${CLAUDE_PLUGIN_ROOT}/hooks/vao_tools.py` via detect-once; drop the literal `"..."` fallback.
- [x] FD-8 (C3) Sweep the v3.8.0 unbounded-solving residue: `architect-team-pipeline/SKILL.md:473,512–513`, `editability-completeness/SKILL.md:59`, `interaction-completeness/SKILL.md:62`, `mini-architect-team-pipeline/SKILL.md:3` + `mini.md:2`, `ux-test-builder/SKILL.md:3` + `ux-test.md:2` + `ux-test-builder/SKILL.md:~241` (`flaky` = consensus-on-intermittence), `verified-agent-output/SKILL.md:~50`. Align all to loop-until-converged / pause-only-for-required-input (diagnostic-research-team:145 wording).
- [x] FD-9 (C4) Author the MemPalace not-on-PATH note in `skills/mempalace-integration/SKILL.md` `## Phase A`: one user-facing line, suggest `/architect-team:mempalace-install`, continue with MemPalace steps as no-ops (never hard-fail). The four deferring bodies (`architect-team-pipeline:88`, `bug-fix-pipeline:77`, `mini-architect-team-pipeline:63`, `common-pipeline-conventions:86`) now reference a real note.
- [x] FD-10 (C5) Resolve the undefined "Phase B3b" in `skills/bug-fix-pipeline/SKILL.md:~453` — reword to "the SR-intake behavior inherited from the main pipeline's Phase 3b" (or define B3b explicitly); pick one and apply consistently.
- [x] FD-11 (C6) Rewrite the 7 over-length descriptions (visual-to-api-design, interaction-completeness, visual-fidelity-reconciliation, bug-fix-pipeline, mini-architect-team-pipeline, email-testing, proposal-refiner) to trigger-first, ≤1024 chars (target ≤600), moving displaced detail into the body. Add the 1024-char cap to `tests/test_skills.py`.
- [x] FD-12 (D1) Reconcile `CLAUDE.md`: test counts (apply the PINNED values + token rule in `## Count-reconciliation ruling` — do this in THIS cycle, not deferred), VAO-tool count (state the true 20+ once in Stack, fix Structure), enforcement-scripts → 4, commands parenthetical → actual most-recent joiner, "all 27 agents" → "(then 27, now 34)". The operative test-count values are fixed by FD-18; this task and FD-18 land together.
- [x] FD-13 (D2) Refresh `docs/CODEBASE_MAP.md`: §1 + mermaid → v-current / 40 skills / 34 agents / 19 commands / actual test count (the PINNED values from `## Count-reconciliation ruling`); add `hooks/override_markers.py` + `hooks/pretool_unilateral_override_guard.py` to §4.
- [x] FD-14 (D3) `README.md`: schema v7 (per C1), HOOKS box "(3)" → 4 scripts / 6 events including the PreToolUse row; refresh the tests badge + any count this run changes per the PINNED values in `## Count-reconciliation ruling`.
- [x] FD-15 (D4) Bump `.claude-plugin/plugin.json` + `.claude-plugin/marketplace.json` to 3.9.3; add the `CHANGELOG.md` entry enumerating this run's A–E fixes; bring `docs/INTEGRATION_MAP.md` current for any cross-file contract changed; add CLAUDE.md's concise new-version paragraph. (The new 3.9.3 CHANGELOG/CLAUDE.md delta narrative states the new actuals `3928→4097` per the ruling.)
- [x] FD-16 (E1 — Markdown verification) Confirm the BACKEND-DEV glue-execution family covers the command-file invocations FD touched (no separate FD test file; the family is backend-owned, but FD verifies its own edited command bodies pass it after the detect-once conversions).
- [x] FD-17 (E2/E3 — Markdown item-specific) Ensure the FD-owned structural tests pass; confirm `tests/test_skills.py`, `test_visual_to_api_command.py`, `test_monitor_tests_command.py`, `test_inject_command.py`, `test_commands.py` are green under cp1252 AND `PYTHONUTF8=1`.
- [x] FD-18 (D1/D2/D3 count reconciliation — IMMEDIATE, this cycle) Reconcile EVERY documentation test-count claim to the pinned post-run actuals and DELETE the 7 `<!-- COUNT-RECOUNT-AT-M7: ... -->` sentinels. The pinned values (verified at M5: suite ran twice — default cp1252 AND `PYTHONUTF8=1` — both `4097 passed + 5 skipped`; test-file count `163` via `ls tests/test_*.py | wc -l` in the worktree): (a) total-tests OPERATIVE claims → `4097 passed + 5 skipped` (or the file's existing phrasing form, e.g. `4097 PASS + 5 SKIPPED`, `4097 pytest self-tests + 5 skipped`); replace the literal `3928` in `CLAUDE.md` L7/L9/L11/L19 and `docs/CODEBASE_MAP.md` L19/L260 and delete each trailing `<!-- COUNT-RECOUNT-AT-M7: total tests -->`. (b) test-file-count OPERATIVE claims → `163`: `CLAUDE.md` L11 `88 test files <!-- COUNT-RECOUNT-AT-M7: test-file count -->` → `163 test files` (delete sentinel); `docs/CODEBASE_MAP.md` L4 `80 test files (+1 new file)` → `163 test files`, L19 `90+ test files` → `163 test files`, L285 `80 test files under tests/` → `163 test files under tests/`. (c) `README.md` L41 badge `tests-3928%20passing` → `tests-4097%20passing`; if any untagged README "N passing / N pytest" count sentence exists, set it to `4097 passed + 5 skipped` (the L1037 sentence is a category description with no count and is left as-is). (d) Apply the operative-vs-historical token rule in `## Count-reconciliation ruling`: the literal `3871` in `CLAUDE.md` L7 ("suite 3871→3920" v3.9.0 narrative), `docs/CODEBASE_MAP.md` L4, and `CHANGELOG.md` L127 are era-accurate version-history — KEEP them, but ensure each sits unambiguously inside a version-history sentence (a "v3.9.0 … suite 3871→3920" clause); the new 3.9.3 CHANGELOG entry + CLAUDE.md new-version paragraph state the new delta `3928→4097`. After this task, NO operative current-state claim states 3928 and NO `COUNT-RECOUNT-AT-M7` sentinel remains in the tree. (This is FRONTEND-DEV-owned — all touched files are already in the FRONTEND-DEV production list.)

## Cross-cutting (orchestrator-run, not a third file scope)

- [x] X-1 (suite-green, serves E3) After both groups land, the orchestrator (M-phase) runs the FULL suite once under default Windows cp1252 and once under `PYTHONUTF8=1`; both green. New tests are additive; the pre-run baseline was 3933 collected (3928 passed + 5 skipped); the post-run actual is **4097 passed + 5 skipped** (the E1/E2 families added the delta), none removed. This actual is the value FD-18 pins into the docs.
- [x] X-2 (validation gate) Run `openspec validate --all --strict --json` from the worktree root → `valid: true` for `review-remediation`; the two pre-existing active changes stay green.
- [x] X-3 (SUPERSEDED by FD-18) The earlier "recount at M7" deferral is withdrawn — it self-conflicted with the QA Guidance, which scores doc reconciliation (AC-4) at the cycle gate. The recount is now the immediate FRONTEND-DEV task FD-18 above, carrying pinned values, executed in THIS cycle. No count work is deferred to M7.

## Count-reconciliation ruling (cycle-2 binding)

This ruling is the contract QA cycle 2 scores AC-4's count dimension against. It resolves the cycle-1 red.

**Pinned post-run actuals (do not re-measure; these are the M5-verified values):**
- Total tests: **4097 passed + 5 skipped** — verified by running the full suite TWICE, once under default Windows cp1252 and once under `PYTHONUTF8=1`; identical result, zero failures, identical 5-skip set.
- Test-file count: **163** — `ls tests/test_*.py | wc -l` in the worktree (the 9 NEW backend test files this run added are already on disk and counted).

**Operative-vs-historical token rule (the cycle-1 `3871` false-flag fix):**
- An **OPERATIVE** count claim describes the plugin's CURRENT state ("As of v3.9.3 it ships … N pytest self-tests"; the README tests badge; "run … from repo root (N PASS …) expected as of v3.9.3"; a CODEBASE_MAP "### Tests (N PASS …)" header). Every operative claim MUST state the pinned actuals (`4097 passed + 5 skipped`; `163 test files`). No operative claim may state `3928` or `3871` after FD-18.
- A **HISTORICAL-DELTA** narrative records what a PAST version did ("v3.9.0 … suite 3871→3920"; a CHANGELOG entry; a CODEBASE_MAP note-ledger line dated to an earlier era). These are era-accurate history and are KEPT verbatim — but each MUST sit unambiguously inside a version-history sentence so it cannot be misread as a current-state claim. The literal `3871` survives ONLY in such clauses (`CLAUDE.md` L7 v3.9.0 paragraph, `docs/CODEBASE_MAP.md` L4, `CHANGELOG.md` L127). The new 3.9.3 CHANGELOG entry + CLAUDE.md new-version paragraph state the new delta `3928→4097`.
- **Sentinel deletion:** all 7 `<!-- COUNT-RECOUNT-AT-M7: ... -->` comments (CLAUDE.md ×5, docs/CODEBASE_MAP.md ×2) are DELETED by FD-18 — they were the marker of the now-withdrawn M7 deferral.

**The cycle-2 verification matrix scores this as "no stale OPERATIVE count," NOT "no 3871 anywhere":** the check is (1) zero `COUNT-RECOUNT-AT-M7` sentinels in the tree; (2) every operative total-tests claim states `4097 passed + 5 skipped`; (3) every operative test-file-count claim states `163`; (4) the README badge reads `tests-4097 passing`; (5) any remaining `3871`/`3928`/`3920` literal sits inside a version-history clause (historical narrative), never an operative current-state claim. This matches the QA Guidance integration-target wording amended in `proposal.md`.

## Test-file ownership summary (no file in two scopes)

| Test file | Owner | Why |
|---|---|---|
| `tests/test_hooks_structure.py` | BACKEND-DEV | asserts on `hooks/hooks.json` (A1) |
| `tests/test_vao_glue_execution.py` (NEW) | BACKEND-DEV | executes scripts/hooks |
| `tests/test_vao_windows_path.py` (NEW) | BACKEND-DEV | `vao_tools.py` (A3) |
| `tests/test_inflight_inbox_atomic.py` (NEW) | BACKEND-DEV | `inflight_inbox.py` (A4) |
| `tests/test_hooks_stdin_encoding.py` (NEW) | BACKEND-DEV | the 4 hooks (A8) |
| `tests/test_hooks_oserror_handling.py` (NEW) | BACKEND-DEV | 2 hooks (A9) |
| `tests/test_skill_invocation_audit_canonical.py` (NEW) | BACKEND-DEV | `skill_invocation_audit.py` (A10) |
| `tests/test_subprocess_encoding.py` (NEW) | BACKEND-DEV | A7 source assertion |
| `tests/test_teams_mode_cli.py` (NEW) | BACKEND-DEV | `teams_mode.py` (A5) |
| `tests/test_worktree_lifecycle_cli.py` (NEW) | BACKEND-DEV | `worktree_lifecycle.py` (A6) |
| `tests/test_skills.py` | FRONTEND-DEV | asserts on `skills/*/SKILL.md` (C6) |
| `tests/test_visual_to_api_command.py` | FRONTEND-DEV | asserts on `visual-to-api.md` (B3) |
| `tests/test_monitor_tests_command.py` | FRONTEND-DEV | asserts on `monitor-tests.md` (B3) |
| `tests/test_inject_command.py` | FRONTEND-DEV | asserts on `inject.md` (B1/B3) |
| `tests/test_commands.py` | FRONTEND-DEV | asserts on command files (B4) |

The two pre-existing `tests/test_vao_inflight_clarifications.py` and `tests/test_vao_skill_invocation_audit.py` are NOT in either scope — neither dev edits them (pin c). The A4 / A10 tests go into dedicated NEW files, so there is no cross-boundary test edit and no shared file. FD-18 touches only FRONTEND-DEV-owned doc files (`CLAUDE.md`, `docs/CODEBASE_MAP.md`, `README.md`, `CHANGELOG.md`) — no new file, no cross-boundary edit.

## Pinned implementation decisions (zero judgment calls)

### (a) Exact detect-once form for `hooks/hooks.json` (JSON-escaped)

The reference shipped form is `commands/architect-team.md:175`: `$(command -v python3 || command -v python) "${CLAUDE_PLUGIN_ROOT}/hooks/<script>.py" <args>`. Inside `hooks.json` the command is a JSON **string**, so the double-quotes around the path MUST be JSON-escaped as `\"`. The EXACT string value for each of the 8 commands (verified to round-trip through `json.loads`):

```json
"command": "$(command -v python3 || command -v python) \"${CLAUDE_PLUGIN_ROOT}/hooks/pretool_unilateral_override_guard.py\""
"command": "$(command -v python3 || command -v python) \"${CLAUDE_PLUGIN_ROOT}/hooks/review-gate-task.py\""
"command": "$(command -v python3 || command -v python) \"${CLAUDE_PLUGIN_ROOT}/hooks/teammate-idle-check.py\""
"command": "$(command -v python3 || command -v python) \"${CLAUDE_PLUGIN_ROOT}/hooks/pipeline-completion-audit.py\""
```

Apply by script: the 3 PreToolUse entries (Edit / Write / NotebookEdit) all take the `pretool_unilateral_override_guard.py` line; PostToolUse(TaskUpdate) + TaskCompleted both take the `review-gate-task.py` line; SubagentStop + TeammateIdle both take the `teammate-idle-check.py` line; Stop takes the `pipeline-completion-audit.py` line. None of these hooks pass extra args (the current wirings pass none). Keep `"async": false` on every entry unchanged. The rewritten `test_hooks_structure.py` assertions: each command `.startswith("$(command -v python3 || command -v python) ")`, the same `.py` basename appears once, and `" || python "` (with surrounding spaces) is absent.

### (b) The A5/A6 banner/cleanup command invocations DO convert to detect-once

**Decision: YES — convert them.** B3's mandate explicitly includes "the teams_mode/worktree_lifecycle invocations from A5/A6". Even though `teams_mode --banner` and `worktree_lifecycle cleanup-merged` are best-effort (always exit 0), they go through detect-once for uniformity and to satisfy the E1 glue-execution family's "not a silent no-op" check consistently. The five `teams_mode --banner --command "/architect-team:<name>"` invocations (`inject.md:16`, `monitor-tests.md:15`, `visual-to-api.md:15`, `classify-test-prod-safety.md:13`, `discipline-status.md:21`) and the two `worktree_lifecycle cleanup-merged --against origin/main` invocations (`classify-test-prod-safety.md:19`, `visual-to-api.md:23`) all become:

```
$(command -v python3 || command -v python) "${CLAUDE_PLUGIN_ROOT}/scripts/setup/teams_mode.py" --banner --command "/architect-team:<name>"
$(command -v python3 || command -v python) "${CLAUDE_PLUGIN_ROOT}/scripts/setup/worktree_lifecycle.py" cleanup-merged --against origin/main
```

(In a command `.md` fenced bash block these are shell, not JSON, so no `\"` escaping — the quotes are literal.) Consequently `tests/test_visual_to_api_command.py`, `tests/test_monitor_tests_command.py`, and `tests/test_inject_command.py` must be edited (FRONTEND-DEV) to assert the detect-once form for the converted invocation lines. For `inject.md`, the inflight_inbox helper snippets (the RUN_ID detector + the append blocks that B1 touches) MAY remain in the polyglot `python3 -c "..." || python -c "..."` form because they are not exit-2-capable and the existing test targets them; the teams_mode banner line converts. Re-target `test_inject_command.py` to check the helper lines (polyglot) and the banner line (detect-once) separately.

### (c) Exact new-test filenames each dev owns

BACKEND-DEV creates these 9 NEW test files and edits 1 existing:
- NEW: `tests/test_vao_glue_execution.py` (E1, BD-11) · `tests/test_vao_windows_path.py` (A3, BD-3) · `tests/test_inflight_inbox_atomic.py` (A4, BD-4) · `tests/test_hooks_stdin_encoding.py` (A8, BD-8) · `tests/test_hooks_oserror_handling.py` (A9, BD-9) · `tests/test_skill_invocation_audit_canonical.py` (A10, BD-10) · `tests/test_subprocess_encoding.py` (A7, BD-7) · `tests/test_teams_mode_cli.py` (A5, BD-5) · `tests/test_worktree_lifecycle_cli.py` (A6, BD-6).
- EDIT: `tests/test_hooks_structure.py` (A1, BD-1).
- A2's bare-module CLI regression lives inside `tests/test_vao_glue_execution.py` (no separate file).
- DO NOT TOUCH: `tests/test_vao_inflight_clarifications.py`, `tests/test_vao_skill_invocation_audit.py` (both pre-exist; A4/A10 use the NEW dedicated files above).

FRONTEND-DEV creates 0 NEW test files and edits up to 4 existing:
- EDIT: `tests/test_skills.py` (C6, FD-11) · `tests/test_visual_to_api_command.py` (B3, FD-3) · `tests/test_monitor_tests_command.py` (B3, FD-3) · `tests/test_inject_command.py` (B1/B3, FD-1/FD-3).
- VERIFY-ONLY (edit only if the post-B4 check shows the body lost its polyglot invocation, which it will not): `tests/test_commands.py` (B4, FD-4).

If, during implementation, a BACKEND-DEV fix forces a change to a FRONTEND-DEV-owned structural test (or vice-versa), the owning dev makes the edit and the other dev surfaces an SR rather than reaching across the boundary. All known boundary risks (the detect-once test flips) are enumerated above; none requires a shared file.
