# Completion-lock follow-ups (post-v3.56.0)

Findings from the adversarial passes, each marked with what actually shipped —
FIXED, NARROWED, or a named boundary. Recorded so the next run inherits the
reasoning rather than rediscovering it, including the remedies that were
measured and **declined**, which are the most expensive thing to re-derive.

Shipped state: v3.56.0 at `9750728`. **Every open item in this document was closed in
v3.57.0** (`completion-lock-followups`); each section below now records its final
disposition. The two DECLINED remedies are kept verbatim — a measured rejection is the
most expensive thing to re-derive, and the next run must not re-adopt them.

## Named lessons this run earned

These generalise past the completion lock and are the durable output of the run.

1. **A gate and its instructions are one contract.** The turn-output rule and the
   block message that tells an agent how to comply were written in the same file
   by the same author, and never checked against each other — so the gate refused
   the exact format its own message demanded. Test the pair, not the half.
2. **Pinning both directions of a rule is not the same as pinning that the rule is
   fed the right thing.** Every classifier test handed `classify_turn_output` a
   string directly, so no test could observe that the *wrong string* was being
   selected. Three revisions of thresholds could not reach T1, because T1 was in
   the input.
3. **A witness has to reproduce the real defect, not merely disturb code near it.**
   A T1 mutation that reversed block order still concatenated every block, so the
   narrative survived in the measured text and the mutant escaped — a green
   mutation log with no real witness behind it.
4. **A fix in one arm can silently retire another arm's witness.** The F6
   short-line rule excluded the fixture that the `NARRATIVE_LINE_THRESHOLD`
   mutation depended on. Nothing went red; the log would have read 31/31 with a
   constant unpinned.
5. **Measure before relaying, including your own reviewers.** T4 reached the
   orchestrator framed as pre-existing and independent of T2. It was neither — T2
   created it — and it shipped live for two commits on that framing. The same
   reflex produced a mutation count written from memory. Both were caught by
   counting, not by thinking harder.
6. **An unverifiable number is indistinguishable from an invented one.** Six
   full-suite numbers were taken on trees that were still being edited before the
   freeze-and-hash discipline was adopted. The shipped number is bracketed by a
   diff hash proving byte-identity across the run.

## Findings and their disposition

### G2 — cumulative turn-output reason (ANSWERED v3.57.0 — the precondition is FALSE)

`_turn_assistant_text` concatenates every assistant text block since the last
genuine user prompt — that is what closes T1's sign-off evasion. The side effect
was that once a turn produced a narrative, every later Stop re-measured it: the
agent replied with exactly the one line of state the block demanded and the arm
still fired, `lines` climbing 6, 7, 8, with no reply able to clear it.

**Fixed** by advancing the measurement boundary in-transcript, detected from the
non-genuine `role: user` record the harness feeds a blocked Stop back as, keyed
on this module's own kill-switch names rather than the emitter's prose. Verified
by sequence: narrative -> TRIP, complies -> CLEARS, complies again -> CLEARS.

**The precondition is not verified, and it may make the fix inert.** The boundary
only advances if the harness actually writes the blocked-Stop feedback into the
transcript as a `role: user` record that `load_transcript_slices` can see. A scan
of 38 transcripts across every project on this machine — including long CT6
pipeline runs in which the v3.30.0 continuation guard has certainly blocked —
found **zero** such records. Every apparent hit was a `tool_result`, a skill
body, or a peer `teammate-message`.

That is suggestive, not conclusive: the completion lock itself had never blocked
on this machine before today, and the Stop-hook contract does deliver `reason`
to the model (ralph-loop depends on exactly that), so the open question is
narrowly whether it is *persisted* in the JSONL rather than whether it is
delivered.

**If it is not persisted, G2 is unfixed** — the boundary never advances and the
behaviour is exactly as described above. It degrades to the prior behaviour and
never to something worse. Severity remains bounded either way: `turn_output` is
only evaluated when work is already open, so G2 can never *cause* a block that
would not happen anyway; it produces a misleading message citing a rule the
agent already satisfied.

**Next step: a live check post-install.** Trigger one real block, then grep the
session transcript for the block text as a `role: user` record. If absent, move
the boundary to durable per-session state — but note the constraint that killed
the first attempt: `note_continuation_block` is written only for engaged CT6
runs, so it is empty in the plain sessions this lock exists for, and writing it
from here would reintroduce the F-F pollution in every repo the user types in.

### G1 — a fenced summary evades the line arms (NARROWED, residual pinned)

T4 excluded fenced content from the line arms and the marker scan, so a summary
wrapped in a fence was invisible to everything but the >600-char prose arm.

**Narrowed:** fenced lines now count toward the absolute ceiling, so a fenced
summary trips at >= 12 total lines. **Residual:** a 4-line fenced summary is 6
lines and still evades. Both the fix and the gap are pinned in the suite by
`test_a_fenced_summary_reaches_the_ceiling_when_long_enough`, so the residual
lives in tests rather than only in prose.

**Two candidate remedies were measured and both declined**, and the reason is
the durable part. Counting fenced lines toward a ceiling of ~6 was correct when
proposed — G3 then raised the ceiling to 12 for a good reason and it no longer
reached. Treating "a fence containing markdown markers" as prose was measured
against ten realistic fenced shapes and **misclassified 7 of 9 code samples**: a
unified diff and a git diff (`- old` is both a removed line and a bullet), YAML
(`- name: build`), a shell session with `#` comments, a documentation sample, a
markdown table, and an `ls` listing. Adopting it would reintroduce the T4
false-positive class wholesale — and quoting a diff in a status update is
genuinely common, unlike fencing a summary, which is deliberate.

G1 therefore stays a **named boundary** alongside `Bash` writes and
`TaskUpdate(status="deleted")`: an agent that wants out has cheaper routes.

### G3 — ordinary narration tripped the ceiling (FIXED FOR ITS WITNESS ONLY — see H1 below)

Six one-line narration blocks in one turn — the ordinary shape of an agent
narrating between tool calls — concatenated to 6 prose lines and tripped, on a
turn containing no report at all. T1's seam with T2: `too_many_lines` counted
every prose line while `long_enough` counted only >= 24-char lines.
`NARRATIVE_ABSOLUTE_LINES` raised 6 -> 12, which still catches T2's 30 x 19 with
margin and clears a normal working turn. Switching the absolute arm to
`counting_lines` was rejected because it would un-fix T2.

### H1 / H4 / N-obs — the sixth revision (FIXED, with a stated residual)

A final adversarial pass at `2c7cc5e` found that **G3 was fixed for its witness,
not for its class**. G3 was reported as "six one-line narration blocks" and fixed
by raising `NARRATIVE_ABSOLUTE_LINES` 6 -> 12 — which only ever reached the
short-line arm. The `long_enough` arm counted lines of `>= 24` chars and fired at
`>= 3`, and ordinary narration sentences run 45-60 chars. Measured: three natural
sentences of 59 / 62 / 56 chars -> `narrative=True`. Narrating between tool calls
is the single most common thing an agent does, so with work open every such turn
was refused with an instruction it had already satisfied.

**Fixed by RAISING `NARRATIVE_LINE_THRESHOLD` 3 -> 6.** The first attempt retired
the arm outright; the independent review pushed back that this let a markerless
plain-prose report through at any length under 600 chars — measured, eight
markerless report lines at 473 chars were allowed — and it was right: a
marker-only rule cannot see a report that simply does not use markdown. Raising
the threshold clears three narration sentences while six report-length lines
still trip. G3's original short lines are unaffected, because `counting_lines`
ignores anything under 24 chars.

**H4 — the marker vocabulary was ASCII-only.** In the 2-line band the marker arm
is the ONLY arm that can fire, so the spec's named catch rested on three exact
characters (`-`, `*`, `+`). A Unicode bullet or an en-dash defeated it, verified.
Widened to the glyphs a model actually emits.

**STATED RESIDUAL (narrowed).** A markerless prose report of 3..5 report-length
lines under 600 chars is allowed; six trips. This is the accepted, deliberate cost of
not blocking ordinary narration. It is not a defect to be fixed by another
threshold — that is precisely the pendulum that produced six revisions. If a
future run wants it closed, the answer is a different signal, not a different
number.

### Pin sequences, not just strings (spec gap)

Four revisions of both-directions pinning never surfaced G2, because **it is
invisible to any single-text test**. Every pin classifies one string; G2 only
appears as a *sequence of Stops*. For any rule whose input accumulates, "both
directions pinned" is insufficient — pin the sequence: narrative, then
compliance, then assert the arm clears.


### N5b — a wedged run is silent, not just unreleased (CLOSED v3.57.0)

The README states that nothing releases a wedged run automatically, which is
correct and is the point of "unbounded". But that sentence does two jobs, and the
second is incidental: *nothing tells you automatically* either. A run wedged
overnight with nobody watching produces no signal.

Fixable without weakening unboundedness at all: emit a notification at the
no-progress cap **and keep blocking**. `scripts/notify/notify.py` already has a
suitable event type (`issue_discovered`).

**Do NOT** fix this by advancing the continuation guard's counter.
`escalation-pending.md` is agent-written and the lock deliberately does not honour
it (ADV-1), so the marker would appear without releasing anything, and the burned
counter would mis-fire the guard the moment work finally closed.

### T4's neighbour — `prose_lines` vs `line_count` (CLOSED v3.57.0 — and the premise was STALE)

`prose_lines` now drives three arms; `line_count` only populates the reported
`lines` field. A later change that reintroduces a line-count-based arm should use
`prose_lines` unless it genuinely wants code lines counted. The two are one
careless rename apart, and that confusion is precisely what T4 was.

### N2b — hardlink under another name (CLOSED v3.57.0)

The ground-truth guard resolves paths, which closes case-folding, `..` traversal
and junctions. It cannot see a hardlink under a different name; that needs
`st_dev`/`st_ino` identity comparison. Low severity because creating one is a
Bash act, and Bash is already a named boundary.

### N3 — `CT6_TASKS_ROOT` moves the guard's own root (CLOSED v3.57.0)

One environment variable relocates both the gate's ground truth and the guard
protecting it. Documented as a boundary; a fix would need the guard to resolve
its protected set independently of the value under attack.

### F7 — unescaped task text in the block message (CLOSED v3.57.0)

A task subject containing newlines and a forged `How this releases:` section
renders as a single bullet, because `_lock_clip` collapses whitespace first — so
structure cannot be spoofed and the real section still appears once. What does
land is instruction-shaped prose inside a message the agent reads as enforcement
output. The mitigation is incidental rather than deliberate. Cheap hardening:
strip bullet-prefix and colon-terminated-heading shapes inside `_lock_clip`.

### Mutation-harness classification (CLOSED v3.57.0)

`mutation-checks-lock-wiring.txt` derives `caught` by parsing the pytest result
line; lock-core's harness derives it from the exit code and additionally asserts
the file actually changed before running. The exit-code design removes the
class of a no-op mutation logging green; the parsing design only detects it.
Convert the weaker artifact.

### The classifier pendulum

Four revisions, each fix creating the next: markers too aggressive → markers too
weak → ceiling with no fence exemption → snippets blocked. The spec now requires
both directions pinned for every arm, but the observation that matters is the
adversary's: *the shapes that keep moving are the ones between the poles, not at
them*. A fifth revision should start by enumerating the middle, not the extremes.

---

# v3.57.0 — what closed, and how

Every open item above is closed. Twenty-two mutations were run under exit-code
classification: **22 caught, 0 escaped, 0 no-op, 0 broken.**

## N5b — CLOSED

The lock now emits one best-effort `issue_discovered` notification once it has blocked
`CT6_COMPLETION_LOCK_NOTIFY_AFTER` (default 5) consecutive times, and **keeps blocking**.
The counter resets when the lock stops blocking, so a later wedge notifies again rather
than being swallowed by a stale `notified` flag. Kill-switch
`CT6_COMPLETION_LOCK_NOTIFY_DISABLED` silences the channel without weakening the gate.

The prohibition was honoured: the continuation guard's no-progress counter is NOT
advanced, and the escalation marker is not raised — pinned by a test.

**The witness that mattered.** The emission path is wrapped in a bare `except`, so a
defect inside it ships the feature INERT with every test still green. That is not
hypothetical — the first cut called a `_utc_now` helper that does not exist in the
module, and the swallow hid it completely. The test therefore observes a **sentinel
notifier from outside the hook**, and one mutation deliberately raises inside the
swallowed path to prove the test can see it.

## F7 — CLOSED, and the first fix was ineffective

Neutralization is applied **per field** in `_lock_task_text`, not to the assembled line.
The first cut put it only in `_lock_clip` and was useless for the actual threat:
`_lock_task_text` prefixes `[<id>] `, so a subject's forged bullet is never at position 0
and a leading-shape strip never reaches it. **The test asserted on a rendering that could
not occur and passed vacuously; the mutation witness is what exposed it** — disabling the
strip left the test green.

## N3 — CLOSED

The guard protects the **union** of the real default root and any `CT6_TASKS_ROOT`
override. The asymmetry is the whole fix: an environment variable may ADD to the
protected set, never remove the real store from it — the same shape as the substrate's
`open_task_items` treating an unknown status as OPEN.

## N2b — CLOSED

`(st_dev, st_ino)` identity comparison catches a hardlink under any name. Fails safe
throughout: only compared where both paths exist (so an ordinary new-file `Write` is
untouched), `st_ino == 0` yields no identity, an indeterminate result falls back to
resolved-path comparison, and the arm can only ever ADD a block. Skipped only for paths
that could be a second name at all (`st_nlink != 1`), so the common write pays one stat.

## `prose_lines` vs `line_count` — CLOSED, and this document's premise was WRONG

The finding said one counter was load-bearing and the other cosmetic. **That was stale.**
T4 moved the arms onto unfenced lines and left `line_count` reporting-only; **G1 then put
the ceiling arm back on the full count** and the comment was never corrected. By v3.56.0
there were three counters and all three were load-bearing — so a reader trusting the
comment would have concluded one was free to substitute, which is T4 exactly.

Renamed to `all_nonempty_lines` / `unfenced_lines` / `report_length_lines`, each stating
what it counts, with the nesting relation and the pick-by-meaning rule at the call site.

Equivalence was **proved, not asserted**: a 40-input corpus captured from `9750728`
before the edit, full returned-dict comparison, **0 mismatches**. The corpus landed as a
permanent parametrized test — that regression net, not the rename, is the deliverable.
All three counter substitutions turn it red.

## G2 — ANSWERED: the precondition is FALSE, and the fix is INERT

Scanned **679 transcripts across 23 projects, 1120.3 MB**, four patterns, **331 matching
records**. Eight were `type=user` + `role=user` + string content; **all eight dissolved**
— seven `<teammate-message>` peer envelopes, one `isCompactSummary` record. **Zero**
harness-written blocked-Stop feedback records.

The decisive evidence is the OLD sample: the v3.30.0 continuation guard has used the same
mechanism for months and contributes 64 records — 57 `tool_result`, 6 `assistant`, 1
teammate envelope. This is a property of the harness, not a thin sample.

**Consequence, bounded.** The boundary never advances, so a turn that went narrative keeps
reporting even after the agent complies. But `turn_output` is only evaluated when work is
already open, so **G2 can never CAUSE a block** — it produced a misleading message.

**Fixed by making the message honest rather than by adding state.** The objection that
killed the first attempt still stands: `note_continuation_block` is empty in exactly the
plain sessions this lock exists for, and writing it from the lock would pollute every repo
the user types in. Trading a misleading sentence for a stray state file everywhere is a
bad trade. The message no longer claims *"the last turn tripped it"*; it says the output
**since the last user prompt** is a narrative and discloses that this covers the whole
turn. The rule keeps its teeth; only the false claim is gone.

Full evidence: `.architect-team/red-runs/completion-lock/g2-precondition-answer.md`.

## Mutation-harness classification — CLOSED

`mutation-checks-lock-wiring.txt` is regenerated by an exit-code harness. Each entry
asserts the anchor matched, asserts the file changed **by sha256** before running
anything, classifies on pytest's exit code (1 = caught, 0 = ESCAPED, 2..5 = `[ERROR]`, so
a collection error can never read as caught), and verifies the restored sha256 plus a
green re-run before scoring. Every mutation was re-run for real, not transcribed.

## Frontend-E2E loop-exit gate — the in-flight item 8

Reported live: *"25 of the 27 flagged slices are pre-existing debt"* — a commit stopped
over work the run never touched, and the user was asked to choose. Three defects:

1. **Retroactive scope.** `.architect-team/reviews/` is cumulative, so a gate introduced
   in v3.55.0 demanded live-environment evidence from slices written before it existed.
   `_audit_frontend_e2e` now scopes to slices this run owns — claimed by a teammate
   manifest **OR** written after the run marker's `started_at` — and prints how many it
   excluded. With **neither** signal it keeps today's behaviour: unknown provenance must
   not disarm a loop-exit gate, because under-blocking is the defect v3.55.0 removed.
2. **No path to a live environment.** The gate required a deploy the pipeline never
   performed. `common-pipeline-conventions` gains *"Local -> dev -> test-on-dev is the
   pipeline's job, not the user's"*: bring the environment up (or run `deploy_command`),
   seed the records the flow needs **through the application's own create path**, then run
   the flow — in that order, automatically.
3. **It asked.** *"How do you want to proceed?"* with a recommended option attached is not
   an escalation; it is the run asking permission to do its own job. Only a genuine
   external blocker escalates.

**Named boundary:** the inherited debt still exists. Scoping stops it blocking the next
commit; it does not close it. That is a backlog to schedule, deliberately not this run's.

