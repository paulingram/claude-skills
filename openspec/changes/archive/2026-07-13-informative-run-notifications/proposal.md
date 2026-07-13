# informative-run-notifications

## Why

The owner directive (v3.34.0), verbatim intent: *"when emails are created and sent, 1) they are always sent as the agent engages in any architect team task. 2) they should contain meaningful updates — both what is about to start, where it is at in the process and what it completed. when it kicks off, it should also send the architecture and solution plan as part of one email. the goal is for this to be informative, not only status updating. when waiting on agents, it should alert that its waiting, and then when it completes, alert it completes."*

Before this change the notifier (`scripts/notify/notify.py`, v0.9.18 + the v3.10.0 `heartbeat`) had six events with bare one-line bodies ("The architect-team pipeline for X has started Phase 2."), no run-level bookends, no plan delivery, no dispatch-wait visibility — and the `ux-test-builder` pipeline had ZERO notification wiring, so "any architect team task" was untrue for one of the four pipelines.

## What Changes

- **Extend** `scripts/notify/notify.py`: `EVENT_TYPES` 6 → 10 — `run_start` (the kickoff email; the repeatable `--plan-file` option embeds the plan artifacts themselves, bounded by `PLAN_FILE_MAX_CHARS = 20_000` / `MAX_PLAN_FILES = 8`, missing files degrading to a note via the never-raising `_read_plan_file`), `waiting_on_agents` / `agents_complete` (the dispatch-wait pair; the `--agents` roster), `run_complete` (the final email; `--elapsed` + `--commit`, optional lines omitted when absent). Universal informative options `--details` / `--progress` / `--next-step` render as their own body blocks on EVERY event (`_context_trailer`). Every existing render substring, the opt-in / best-effort / always-exit-0 contract, stdlib-only, and secrets-via-env-indirection are preserved verbatim. (REQ-001, REQ-002)
- **Rewrite** the canonical `common-pipeline-conventions` `## Notifications wiring convention`: the ten-event vocabulary table + the **"Informative, not just status"** content contract (a bare status-only invocation is non-compliant wiring; the FIRST `phase_start` of a run is the engagement email carrying the requirement summary) + the run-level bookend rule (`run_start` at Phase 1 / B3 / M3 / U4; `run_complete` at Phase 8 / B8 / M7-green / U9) + the dispatch-wait rule (at EVERY dispatch-and-wait point). (REQ-003)
- **Wire** all FOUR pipelines: `architect-team-pipeline` (run_start at the Phase 1 gate exit embedding proposal + design + tasks; the dispatch-wait bash pair at Phase 2 spawn / Phase 3 gate; run_complete at Phase 8), `bug-fix-pipeline` (run_start at the B3 gate exit embedding the fix proposal; the pair at B1/B5/B6/B6b; run_complete at B8), `mini-architect-team-pipeline` (run_start at the M3 self-confirm convergence embedding the bundle; the pair at M4/M5; run_complete at M7 after the auto-merge), and `ux-test-builder` (previously ZERO wiring — full `## Notifications` section, per-U-phase boundaries, run_start at U4 embedding the distilled flow catalog, the pair at U3/U6, issue_discovered at U8, git_commit + run_complete at U9; `deploy` deliberately excluded and documented). `commands/architect-team.md` note updated; `commands/ux-test.md` gains one. (REQ-004…007)
- **Tests**: `tests/test_notify.py` +16 engine cases; `tests/test_notify_wiring.py` rewritten to the ten-event vocabulary + FOUR-pipeline parametrization with a per-pipeline required-event map; `tests/test_bug_fix_pipeline_notifications.py` + `tests/test_heartbeat.py` extended; the `tests/test_dispatch_banner.py` version pin advanced to 3.34.0. (REQ-008)
- **Document & release**: README (the notifications section rewritten around the ten events + the informative contract; NEW IN + badges + timeline), CHANGELOG `## [3.34.0]`, CLAUDE.md, both maps' notify entries + note ledgers, this spec delta, `.architect-team-notify.example.json` showcasing a new-event subscription; version bump `3.33.0 → 3.34.0`. (REQ-009)

No breaking changes. Opt-in semantics unchanged: with no `.architect-team-notify.json` present the notifier remains a silent no-op.

## Capabilities

### Modified Capabilities

- `project-email-notifications`: the event vocabulary grows five → ten (the v3.10.0 heartbeat included); three NEW requirements — run-start-carries-the-plan, dispatch-wait visibility, the informative content contract — and the pipeline-wiring requirement widens from the main pipeline to all four pipeline-driving skills.

## Impact

**Affected files:** `scripts/notify/notify.py`; `skills/common-pipeline-conventions/SKILL.md`; the four pipeline skills; `commands/architect-team.md` + `commands/ux-test.md`; `tests/test_notify.py` / `test_notify_wiring.py` / `test_bug_fix_pipeline_notifications.py` / `test_heartbeat.py` / `test_dispatch_banner.py`; `.architect-team-notify.example.json`; README / CHANGELOG / CLAUDE.md / both maps / this spec; `.claude-plugin/plugin.json` + `marketplace.json`.

**Counts:** skills 48 / agents 39 / commands 23 UNCHANGED; NO new skill / agent / command / hook / Layer-3 tool. Suite 5263 → 5334 passing + 5 skipped (199 test files; 5339 collected), both encodings.
