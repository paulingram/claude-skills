# design — quality-upgrades-v3-42

## Team decomposition (5 parallel teams, non-overlapping file scopes)

| Team | Items | Files owned |
|---|---|---|
| **A — instruction-surface** | principles doc + injection; skill boilerplate compile; reference-section extraction | `docs/ETHOS.md`, `scripts/setup/compile_skills.py` (new), `scripts/setup/sync_agent_boilerplate.py` (extend), `agents/*.md` (principles block), the 5 pipeline-driving skills' `SKILL.md` + new `skills/*/references/`, `tests/test_ethos_injection.py`, `tests/test_compile_skills.py`, `tests/test_skill_references.py` |
| **B — memory hygiene** | recall envelope; salience allowlist; digest cache | `scripts/memory/recall_hygiene.py` (new engine), `skills/mempalace-integration/SKILL.md`, `hooks/sessionstart-run-continuity.py` (envelope on injected recall), `tests/test_recall_hygiene.py`, `tests/test_sessionstart_recall_envelope.py` |
| **C — doc tooling** | capability index; non-goals section; changelog rubric | `scripts/docs_tooling/capability_index.py` (new), `docs/CAPABILITY_INDEX.md` (generated), `docs/CODEBASE_MAP.md` (non-goals section ONLY), `docs/CHANGELOG_RUBRIC.md`, `scripts/docs_tooling/changelog_check.py` (new), `CLAUDE.md` (one pointer line), `tests/test_capability_index.py`, `tests/test_changelog_rubric.py` |
| **D — installers** | capability-gated guidance blocks | `scripts/setup/install_mempalace.py`, `scripts/setup/install_librarian.py`, `scripts/setup/install_gateway.py`, `scripts/setup/guidance_blocks.py` (new shared helper), `tests/test_installer_guidance_blocks.py` |
| **E — evals** | behavioral eval tier + budget-regression gate | `scripts/evals/` (new: `runner.py`, `collector.py`, `judge.py`, `budget.py`), `tests/evals/` (new: routing + outcome evals + fixtures), `tests/test_evals_offline.py` (deterministic engine tests, in default suite), `pytest.ini`/`tests/conftest.py` (eval-tier exclusion — coordinate at reconciliation) |

Sequencing inside teams: A does compile mechanism → ETHOS injection → references split (compile provides the injection). B does engine → envelope wiring → allowlist → cache. E does runner/collector → evals → budget gate (warn-first).

## Key design decisions

1. **Marker-block compile, not template files.** `compile_skills.py` follows the in-place marker-fence pattern `sync_agent_boilerplate.py` already uses (BEGIN/END fenced blocks rewritten from one canonical source), NOT a parallel `.tmpl` file per skill — no two-file drift surface, no new authoring model, byte-stable output, `--check` mode for the suite. Canonical block sources live in the script as data (mirroring the agent-boilerplate pattern).
2. **One memory engine, three features.** Envelope, allowlist, and digest cache are one stdlib module (`scripts/memory/recall_hygiene.py`) because they compose on the same render path: recall → allowlist-filter → budget/cache → envelope-wrap → inject. The SessionStart hook and the skill contract both consume it.
3. **Envelope form**: a fenced `<recalled-data source="mempalace" instructions="false">…</recalled-data>` wrapper + a one-line preface. Applied at every render boundary; tests pin each path.
4. **Digest cache** lives under `<workspace>/.architect-team/memory-digests/`: per-entity JSON (digest text + created_at + ttl + source_hash), TTL per entity kind, byte cap per entity (default 2048) + per-injection budget (default 8192), invalidation hook on `mine`, stale-fallback on palace-unreachable with a visible `degraded: stale-cache` marker. Fail-open always.
5. **Eval tier isolation**: `tests/evals/` is NOT collected by the default suite (directory-level exclusion via `pytest.ini` norecursedirs or collect_ignore in `tests/conftest.py` gated on the env flag `CT6_EVALS`). Offline engine tests (parser, collector math, budget-gate logic, fixture integrity) live in the DEFAULT suite (`tests/test_evals_offline.py`) so the tier is still structurally verified key-free.
6. **Eval runner**: stdlib `subprocess` driving `claude -p --output-format stream-json` with `--max-turns` bounds; transcript parsed for Skill-tool calls (routing eval) and final report text (outcome eval). Judge: a second bounded `claude -p` call scoring the report vs ground truth JSON; deterministic pass logic in Python (thresholds in the fixture, not the judge). Cost read from the CLI's reported usage. Collector writes `.architect-team/eval-runs/<ts>.json` + compares to the previous run file.
7. **Budget gate** (`budget.py`): `find_budget_regressions(current, previous, ratio=2.0, min_tools=5, min_turns=3)` → warn-first (returns findings; the eval test prints them; failing mode behind an env flag until baselines stabilize).
8. **Guidance blocks**: shared `guidance_blocks.py` with `upsert_block(claude_md_path, capability, body)` / `remove_block(...)` using `<!-- ct6:<capability>:begin/end -->` fences; installers call it after their existing verify step; removal on `--check-only` failure or uninstall. Never touches text outside the fences; idempotent by construction.
9. **Changelog rubric enforcement**: deterministic subset only (top entry's version == plugin.json version; the suite-total line present in the top entry) as `scripts/docs_tooling/changelog_check.py` + a pinning test; the qualitative voice guidance lives in the rubric doc, explicitly not machine-checked (mirrors the instruction-compliance rubric's carve-out pattern).
10. **Non-goals section**: seeded with ≥4 entries — single-harness (Claude Code native), no usage telemetry, stdlib-only core (no external service deps), no embedded browser runtime — each with rationale + revisit-trigger. Lives in CODEBASE_MAP.md so the doc-updater maintains it.

## Reuse Decision Log

| Proposed new thing | Ladder verdict | Decision |
|---|---|---|
| `scripts/setup/compile_skills.py` | EXTEND pattern | Extends the `sync_agent_boilerplate.py` marker-block mechanism (CODEBASE_MAP §scripts/setup) to the skills tier; no template-file model introduced. |
| `scripts/memory/recall_hygiene.py` | BUILD-NEW (sanctioned) | No existing engine renders/gates recall; `scripts/helpdesk/logit.py`'s allow-list philosophy (CODEBASE_MAP §scripts/helpdesk) is REUSED as the allowlist pattern; locks/state conventions reused from `hooks/` state layout. |
| `scripts/docs_tooling/capability_index.py` + `changelog_check.py` | BUILD-NEW (sanctioned) | Mirror the deterministic-engine shape of `scripts/claude_md/claude_md_efficiency.py` + `scripts/compliance/instruction_compliance.py` (stdlib-only, no import side effects); no existing generator emits a capability catalog. |
| `scripts/setup/guidance_blocks.py` | COMPOSE | Shared helper composed into the three existing installers; fence pattern consistent with the marker conventions in `hooks/override_markers.py`. |
| `scripts/evals/` + `tests/evals/` | BUILD-NEW (sanctioned) | No behavioral tier exists (the gap being closed); collector/verdict JSON conventions reuse the `.architect-team/` state-artifact patterns; the runner reuses the repo's polyglot-Python + stdlib disciplines. |
| `docs/ETHOS.md`, `docs/CAPABILITY_INDEX.md`, `docs/CHANGELOG_RUBRIC.md` | BUILD-NEW (sanctioned) | New doc surfaces; all three join the documentation-currency inventory. |
| New third-party dependency | NONE | Everything stdlib; the eval runner shells to the already-required `claude` CLI. |

## Verification plan

Per-team TDD + v7 review evidence + independent task-reviewer per team; Phase 4 reconciliation (A×C lint-over-generated-files boundary, E×suite collection boundary); Phase 5 = full suite green under cp1252 + PYTHONUTF8=1, instruction-compliance lint green over the compiled skills, and the ONE live eval smoke (routing + outcome) with verdict + cost recorded; Phase 7 independent master-review audit; Phase 8 doc-currency (doc-updater + independent audit) + version 3.42.0.
