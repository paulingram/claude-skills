# Design: turn-boundary-completion-lock

## The decisive design property

Every previous attempt to stop this failure has put the stopping condition somewhere the agent controls — an instruction it reads, a promise string it types, a summary it decides is complete enough. **This design puts the stopping condition in a file the harness writes and the agent does not.** That single property is what separates it from the instruction tier the user has already exhausted, and from ralph-loop.

## Reuse Decisions

Per `reuse-first-design`, the extend > compose > reuse > build-new ladder. Every entry below cites a real, verified location.

| # | Need | Decision | Cites | Rationale |
|---|---|---|---|---|
| RD-1 | A Stop-hook that fires in every session | **REUSE, no change** | `hooks/hooks.json` (`Stop` at `matcher: "*"`); `~/.claude/settings.json` `enabledPlugins` | The vehicle already reaches every session. Nothing to build; the change is to what it observes. A user-level settings.json Stop hook would be a redundant second registration. |
| RD-2 | Read the harness task list | **BUILD NEW (small)** — `read_harness_tasks` in `hooks/open_work.py` | `~/.claude/tasks/session-<8>/<id>.json` (verified, 176 files) | Nothing in `hooks/` reads it today. ~40 lines: resolve the dir from `session_id`, load each `*.json`, partition into open / terminal / unreadable. |
| RD-3 | The session id at Stop time | **REUSE, no change** | `hooks/pipeline-completion-audit.py:1742` | Already parsed from the payload. Zero new plumbing. |
| RD-4 | Read the transcript for ledger derivation + turn output | **REUSE** — `run_continuity.load_transcript_slices` / `read_transcript` | `hooks/run_continuity.py:588`, `:537` | Already handles the tail cap, the head slice, and the `truncated` flag. Building a second reader would drift from the one the engagement detector uses. Its tail cap is precisely why RD-6 must accumulate. |
| RD-5 | Identify a teammate session | **REUSE** — `run_continuity.is_teammate_transcript` + `TEAMMATE_TOKEN` | `hooks/run_continuity.py:724`, `:88-94` | The `CT6-TEAMMATE` token is already mandated on every spawn brief and already fail-open-to-teammate. Extending it beats a parallel detector. |
| RD-6 | The ask-ledger store | **BUILD NEW (small)** — `.architect-team/ask-ledger.json` + accumulate/read in `hooks/open_work.py` | — | No existing store has the right shape. Deliberately a plain JSON file, not a new service module, so `check_separation` is unaffected. |
| RD-7 | Atomic ledger writes | **REUSE** — the `_atomic_write_json` pattern | `hooks/run_continuity.py:282` | Same tmp-then-replace discipline; do not invent a second write path. |
| RD-8 | Classify a turn as narrative | **BUILD NEW (small)** — `classify_turn_output` in `hooks/open_work.py` | — | No existing classifier. Pure function over a string: trivially testable, no I/O. |
| RD-9 | Kill-switch convention | **REUSE the convention** | `CT6_RUN_CONTINUITY_DISABLED` (`run_continuity.py:96`), `CT6_TASK_GATE_DISABLED`, `CT6_FRONTEND_E2E_GATE_DISABLED` | Same `CT6_*_DISABLED` truthy-env shape. Four new names, no new mechanism. |
| RD-10 | Block emission | **EXTEND** — a sibling to `_emit_continuation_block` | `hooks/pipeline-completion-audit.py:1601` | Same `decision: block` + `reason` shape the harness already feeds back. The lock's message differs (it names open items + the rule + the kill-switch), so a sibling emitter rather than an overload. |

**No new hook script. No new Layer-3 tool. No new skill, agent, or command. No new `services/` module** — `check_separation` stays at 26.

## Placement — why it is load-bearing

`main()`'s existing order (`hooks/pipeline-completion-audit.py:1679-1793`):

```
parse payload
:1706  escalation marker exists          -> return 0
:1708  _in_progress_is_fresh             -> return 0
:1750  audit()  (gated by _is_real_run)
:1752  not incomplete                    -> return 0
:1757  not engaged + stop_hook_active    -> return 0      <-- an arm below here never fires for a plain session
:1774  count >= budget -> _auto_escalate -> return 0      <-- an arm below here never fires once the budget burns
:1788  _emit_continuation_block
```

The completion lock is evaluated **immediately after the payload parse and `_in_progress_is_fresh`, and BEFORE the escalation-marker return**. Three consequences, each deliberate:

1. It fires for a plain non-engaged session (above `:1757`), which is the reported bug.
2. It survives budget exhaustion (above `:1774`), which is acceptance criterion 3.
3. **It is above the escalation-marker return, so `escalation-pending.md` does not release it.** This is the sharpest call in the design and it follows directly from the user's "unbounded" decision: the escalation marker is an artifact the *agent* writes, so honouring it as a bypass would restore exactly the self-asserted exit this change exists to remove. The genuine required-input pause is still available — the human sets a kill-switch, or resolves the items.

4. **It is also above `_in_progress_is_fresh`. (Reversed after adversarial review — recorded rather than quietly amended.)** The first draft of this design kept `_in_progress_is_fresh` above the lock, reasoning that a fresh `in-progress.md` means work is actively *running* rather than that the agent decided it was done. The architect endorsed that. It was wrong, and the adversarial pass demonstrated it: `.architect-team/in-progress.md` is written by the **agent**, per the heartbeat discipline in `common-pipeline-conventions` — so an open task plus that file returned exit 0 where the control returned exit 2. That is precisely the self-asserted exit the whole change exists to remove, admitted through a side door because the reasoning attached to the file's *meaning* instead of to its *author*.

   The corrected rule, which generalizes: **on this gate, the question is never what a file means — it is who writes it.** A file the agent can create is never a release path, however sincere its semantics. The harness-written task list and the transcript qualify; `in-progress.md`, `escalation-pending.md`, and the ask-ledger's own contents do not.

## Teammate standdown — reversed for the no-name case (v3.56.0, post-review)

The first draft said: when a session is classified as a teammate but no name resolves, fall back to the existing standdown, on the grounds that bricking a pipeline worker is worse than a missed block. The adversarial pass showed that fallback is reachable by the *user's own prompts*: `run_continuity.is_teammate_transcript`'s heuristic fires on a first prompt of `>= 1500` chars containing `.architect-team`, `teammate_name()` then resolves nothing, and the lock returns an empty verdict — the entire gate stands down. The prompt that commissioned this feature is that shape.

**Corrected rule:** the standdown requires a genuine `CT6-TEAMMATE` token. Heuristic-only classification with no resolvable name is treated as an **orchestrator** and blocked on all open tasks. The wedge risk that motivated the original fallback is real, but it is bounded by the kill-switches and by owner-scoping; a gate that silently disables itself whenever the user writes a long prompt is not.

## The ledger's trust property, and why accumulation is not optional

The harness task list defeats a lying agent because the *harness* writes it. A ledger the *model* writes would inherit the unreliability this change exists to remove — so the ledger is derived from the transcript, which the harness also writes.

But `load_transcript_slices` is tail-capped. Re-deriving the whole ledger from a truncated window on a long session would drop the earliest directives — **precisely the ones most likely still unfinished** — and silently allow the stop. So derivation is strictly additive against the stored file: read stored, derive from the available slice, union, write. A stored entry is never removed by a pass that simply could not see it. Resolution is a separate, explicit transition, and ambiguous stays open.

The asymmetry is deliberately favourable: a too-weak resolution predicate **over-blocks**, which fails safe. A too-strong one under-blocks, which is the bug.

## Failure semantics — the two cases are not the same

| Case | Behaviour | Why |
|---|---|---|
| The lock's own code raises | **Fail OPEN** (exit 0, stderr note) | Matches `main()`'s wrapper at `:1791-1793`. A bug in this code must never wedge a session — that is the one outcome worse than the bug being fixed. |
| A source could not be read | **BLOCK**, naming the source | A blanket fail-open here reproduces the reported bug via a bad file: one malformed task JSON and the gate silently passes. An unreadable source is unknown state, and unknown state is not "empty". |

The distinction is implemented by keeping source-read failures as **data** (an `unreadable[]` list returned alongside the items) rather than as exceptions, so only genuinely unexpected control-flow errors reach the fail-open wrapper.

## The narrative predicate

Pure function, no I/O, so it is exhaustively testable:

- **Trips** when all assistant text in the turn (every block since the last genuine user prompt) carries any structural marker at `>= 2` lines (a markdown heading, a bullet/numbered list item — ASCII or Unicode, a bold-label block, or a table row), OR reaches the absolute line ceiling, OR runs to enough unbroken prose. The `>= 3 report-length lines` arm was retired: it fired on three ordinary narration sentences.
- **Never trips** at `<= 2` lines with no marker.

The two directions are both pinned by tests because both failure modes are real: a rule that never fires is decoration, and a rule that fires on a legitimate two-line status update trains the user to disable it.

## Why not ralph-loop (write this down)

The user asked directly, so the answer ships in the docs rather than living only here. ralph-loop's Stop hook exits on `[[ "$PROMISE_TEXT" = "$COMPLETION_PROMISE" ]]` — a literal string the model types — and its own system message says *"do not lie to exit!"*. Nothing verifies the claim. Wrapping the top-level run in it would move the reported failure one layer out, not remove it.

ralph-loop keeps its place in the convergence sub-loops of the twelve skills that use it — `api-design-from-frontend`, `architect-team-pipeline`, `bug-fix-pipeline`, `cartographer-team`, `common-pipeline-conventions`, `data-engineering-exploration`, `data-eng-pipeline`, `domain-research-team`, `intake-and-mapping`, `structure-optimization`, `ux-test-builder`, `visual-to-api-design` (verified case-insensitively; three write it as "ralph loop" with a space). There is **no** `exploration-pipeline` skill — citing one fails `tests/test_instruction_compliance.py`, which pins zero findings.

## Risks accepted

| Risk | Mitigation |
|---|---|
| A stale open task makes a session hard to exit | Per-source kill-switches; teammate owner-scoping removes the largest wedge surface; the block message names the switch |
| Narrative false positive on a terse formatted turn | Both directions pinned by tests; `CT6_TURN_OUTPUT_GATE_DISABLED` is independent of the task-list gate |
| Harness changes the on-disk task format | Degrades to the unreadable-source path — blocks and names it, rather than silently passing |
| Blast radius: fires in every project | The user's explicit decision, taken with the cost stated. Kill-switches documented in the module header, the block message, and the README |
