# Tasks: turn-boundary-completion-lock

TDD throughout (red-first, captured under `.architect-team/red-runs/completion-lock/`); stdlib-only; both encodings green; instruction-compliance zero findings; no `": "` in any new frontmatter.

**Test seam requirement, applies to every group below.** The harness task dir lives under the real `~/.claude/tasks/`. Every reader MUST accept an injected root (an explicit argument, honoured ahead of an env override, honoured ahead of the real home) so the suite can point at a `tmp_path` fixture. A test that writes to the user's real task store is forbidden.

## 1. The open-work substrate — `hooks/open_work.py` (owner: lock-core teammate)

- [ ] 1.1 Red-first: `read_harness_tasks` returns open / terminal / unreadable partitions from an injected task root — `pending` and `in_progress` are open, `completed` is terminal, a non-JSON file lands in `unreadable[]` (NOT silently dropped), a missing dir is a clean empty result. Capture the reds (the module does not exist yet).
- [ ] 1.2 Implement `read_harness_tasks(session_id, tasks_root=None)` + `open_task_items(items, owner=None)`. Resolve `session-<first-8-of-session-id>`; skip the `.lock` / `.highwatermark` sidecars by name, never by silent parse failure. Source-read failures are DATA (`unreadable[]`), never exceptions — this is what makes REQ-6's split possible.
- [ ] 1.3 Red-first + implement `classify_turn_output(text)` — pure function, no I/O. Trips at `>= 3` non-empty lines OR any structural marker (markdown heading, bullet/numbered item, `**Label:**` opening a line, table row). Never trips at `<= 2` lines with no marker. Pin BOTH directions; a rule that never fires is decoration and a rule that fires on a terse status update gets disabled.
- [ ] 1.4 Red-first + implement the four kill-switch constants and their truthy-env readers, following the `CT6_*_DISABLED` convention: `CT6_COMPLETION_LOCK_DISABLED` (master), `CT6_TASK_LIST_GATE_DISABLED`, `CT6_ASK_LEDGER_GATE_DISABLED`, `CT6_TURN_OUTPUT_GATE_DISABLED`. Pin that disabling one source leaves the others enforcing.

## 2. The ask-ledger — durable accumulation (owner: lock-core teammate)

- [ ] 2.1 Red-first: a stored entry survives a derivation pass whose transcript slice does NOT contain the originating turn (the tail-cap case). This is the test that matters most — without accumulation the ledger silently under-reports on exactly the long sessions that need it.
- [ ] 2.2 Red-first: re-derivation is purely additive — a pass over a shorter slice never removes or reopens a stored entry; only genuinely new directives are added; an ambiguous entry stays open.
- [ ] 2.3 Implement `derive_ledger_entries(records)` (from harness-written transcript prompts, reusing `run_continuity` genuine-prompt handling — NOT a model-initiated registration call), `accumulate_ledger(root, entries)` (read-union-write via the `_atomic_write_json` pattern at `run_continuity.py:282`), `open_ledger_entries(root)`, and the conservative resolution transition. Store at `.architect-team/ask-ledger.json`.

## 3. Teammate owner-scoping (owner: lock-core teammate)

- [ ] 3.1 Red-first: a teammate session with open tasks NONE of which it owns → no block. A teammate with `>= 1` owned open task → blocked, and the message names that task. An unidentifiable teammate → falls back to the existing standdown (never wedged).
- [ ] 3.2 Implement teammate identification reusing `run_continuity.is_teammate_transcript` (`:724`) + `TEAMMATE_TOKEN` (`:88-94`), and the teammate-name → task `owner` match. Fail toward standdown when identity cannot be resolved — bricking a pipeline worker is the one failure worse than a missed block.

## 4. Wiring into the Stop hook (owner: lock-wiring teammate)

- [ ] 4.1 Red-first placement tests, all against the real `main()` via the subprocess-with-stdin-payload idiom in `tests/test_pipeline_completion_audit_continuation.py`:
  - a plain session, open tasks, NO `.architect-team/` run state → BLOCKED (the reported bug; must be red before the fix)
  - zero open tasks + empty ledger → exit 0 (no false positives)
  - **an ENGAGED session, 10 consecutive no-progress stops** → blocked every time (proves the lock sits above the budget's `return 0` at `:1774-1783`; a non-engaged-only test would pass while the engaged case stayed broken)
  - an escalation marker present + open work → still blocked (the marker is an agent-written artifact and must not be a self-asserted exit)
- [ ] 4.2 Implement the `_completion_lock` evaluation in `main()`, placed after the payload parse and `_in_progress_is_fresh` and BEFORE the escalation-marker return at `:1706` — therefore above both `:1757-1763` and `:1774-1783`. Add the sibling block emitter (the `_emit_continuation_block` shape at `:1601`) whose message names the open items, the one-line-of-state rule when it fired, and the applicable kill-switch.
- [ ] 4.3 Red-first + confirm: the pre-existing arms are untouched — `CT6_MAX_NO_PROGRESS_STOPS` still governs them, `_is_real_run` still gates `audit()`, and a run with no open work behaves byte-identically to before. Run the existing `tests/test_pipeline_completion_audit*.py` as the regression net.

## 5. Split failure semantics (owner: lock-wiring teammate)

- [ ] 5.1 Red-first: a malformed task JSON in the task dir → BLOCKS and the message names that file. A crash injected into the lock's own code → exit 0 with a stderr note (fail open).
- [ ] 5.2 Implement: `unreadable[]` entries become blocking violations naming their source; only genuinely unexpected control-flow errors reach `main()`'s fail-open wrapper at `:1791-1793`.

## 6. Review, docs, release (owner: lock-wiring teammate + orchestrator)

- [ ] 6.1 Paired review (independent `task-reviewer` + `adversarial-reviewer`). Attack list: the lock no-ops in a plain session; the budget or the escalation marker still releases it; the ledger loses an entry to tail-cap truncation; a teammate is wedged on another lane; the narrative rule never fires OR fires on a two-line update; a malformed source silently passes; a kill-switch disables more than its own source. Producer != checker, evidence-schema-v7, `validate_evidence` 0 gaps.
- [ ] 6.2 Full suite zero-NEW-failures vs the captured baseline, both encodings (`PYTHONUTF8=1` and default cp1252); `check_separation` green and unchanged at 26; a `verify-check-can-fail` verdict for every new test file; a captured demo (a session with open tasks → blocked; tasks closed → allowed; each kill-switch → no-op).
- [ ] 6.3 **Write down why ralph-loop is NOT wrapped at the top level** — its exit is a self-asserted `<promise>` string, so adopting it would relocate the reported bug. Lands in `docs/ETHOS.md` (or the conventions body) so a later run does not re-adopt it. Cite ONLY the verified twelve ralph-loop-using skills; there is no `exploration-pipeline` skill and citing one fails `tests/test_instruction_compliance.py`.
- [ ] 6.4 Version 3.55.4 → **3.56.0** (both plugin JSONs); dispatch-banner pin lockstep; CHANGELOG entry per `docs/CHANGELOG_RUBRIC.md` (suite-total line); README spotlight-swap + `docs/RELEASE_HISTORY.md` append + timeline; `CLAUDE.md` header + recent-releases digest; `docs/CODEBASE_MAP.md` + `docs/INTEGRATION_MAP.md` + `docs/CAPABILITY_INDEX.md` current. **Document the four kill-switches in the README** — a gate this broad must be releasable by a user who has never read the source.
- [ ] 6.5 Completion audit exit 0; commit (author override `Paul Ingram`); merge `--no-ff` to `main`.
