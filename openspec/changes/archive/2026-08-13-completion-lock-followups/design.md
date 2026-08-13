# Design: completion-lock-followups

## Context

Every item here comes from `docs/proposals/COMPLETION_LOCK_FOLLOWUPS.md`, which was written
precisely so this run would inherit the reasoning instead of rediscovering it. Two decisions in
that document are **measurements, not opinions**, and re-deriving them would cost more than the
items themselves are worth. They are restated here so they survive.

## Reuse Decisions

| New thing proposed | Decision | What it reuses instead |
|---|---|---|
| A notification path for a wedged lock | **REUSE** | `scripts/notify/notify.py` `issue_discovered` — an existing event type, already opt-in and best-effort |
| A way to know when to notify | **EXTEND** | the lock's existing per-session heartbeat state under `.architect-team/`; no new store |
| Hardlink detection | **EXTEND** | the existing `_targets_completion_lock_ground_truth` arm; identity comparison is added beside resolution, not in place of it |
| Independent protected-set resolution | **EXTEND** | `_harness_tasks_root`; the union is computed there rather than at each call site |
| Block-message neutralization | **EXTEND** | `_lock_clip`, which already collapses whitespace; the strip lands in the same function |
| Classifier characterization corpus | **NEW TEST ONLY** | no production code; the corpus is the deliverable that makes the next rename safe |

No new module, file, dependency, skill, agent, command, hook script, or Layer-3 tool.

## Decision: N5b notifies but never releases

The user chose "unbounded — never allow stop" explicitly when the lock was designed. N5b must not
erode that. The split is: **the lock's decision to block is unchanged; only its observability
changes.**

Three constraints follow, and each has a named failure it prevents:

1. **Do not advance the continuation guard's no-progress counter.** This was the obvious
   implementation and it is wrong. `escalation-pending.md` is agent-written, and the lock
   deliberately does not honour it (ADV-1) — so raising the marker would produce the *appearance*
   of an escalation without releasing anything, and the burned counter would then mis-fire the guard
   the moment work finally closed. The notification is emitted beside the block, not through the
   escalation path.
2. **Never gate.** The notifier is best-effort by contract: it always exits 0, and it is a silent
   no-op with no `.architect-team-notify.json`. The emission is wrapped so that any exception,
   timeout, or missing interpreter leaves the exit code and block message byte-identical. A gate
   that can be broken by a mail failure is worse than no notification.
3. **Not on every stop.** A lock that emails on every Stop trains the user to filter it, which is
   the same outcome as not notifying at all. It fires once at a persistence threshold, with the
   notified state persisted so a later Stop does not re-fire.

## Decision: the guard protects a UNION, not a redirection

N3's shape is the interesting one. `CT6_TASKS_ROOT` is a legitimate and necessary test seam — no
test may write to the user's real `~/.claude/tasks/`. But the guard resolved its protected set
*through* that same variable, so setting it moved both the store and the protection together, and
the guard would faithfully protect a decoy.

The fix is not to stop honouring the variable. It is to make the variable **additive**: protect the
real default root unconditionally, and additionally protect whatever the override names. An
environment variable may enlarge the protected set; it may never shrink it. That asymmetry is the
whole fix, and it is the same shape as the `open_task_items` asymmetry already in the substrate
(an unknown status counts as OPEN — unknown state is never "done").

## Decision: G1 stays a named boundary — do not re-open it

Both candidate remedies were measured and declined. The measurements:

- Counting fenced lines toward a ceiling of about 6 was correct when proposed. G3 then raised the
  ceiling to 12 for a good and independent reason, and the remedy no longer reached.
- Treating "a fence containing markdown markers" as prose was tested against ten realistic fenced
  shapes and **misclassified 7 of 9 code samples**: a unified diff and a git diff (`- old` is both a
  removed line and a bullet), YAML (`- name: build`), a shell session with `#` comments, a
  documentation sample, a markdown table, and an `ls` listing.

Adopting the second would reintroduce the T4 false-positive class wholesale — and quoting a diff in
a status update is genuinely common, whereas fencing a summary to evade a gate is deliberate. A run
that "closes G1" by adopting a remedy already measured as worse has made the tool worse while
reporting progress.

## Decision: the naming fix must prove equivalence, not assert it

Item 5 is a clarity change with zero intended behaviour change — which is exactly the shape of
change that silently alters behaviour. The corpus is captured **before** the edit and asserts the
full returned dict, not just the boolean. The mutation witness is the real test of the corpus: if
deliberately swapping the two counters does NOT turn the corpus red, the corpus is too weak (or the
counters are genuinely identical, which decides the design question by measurement rather than by
reading).

Note the trap for anyone tempted to "simplify": `NARRATIVE_ABSOLUTE_LINES` and
`NARRATIVE_LINE_THRESHOLD` count differently **on purpose** — that difference is what fixed G3
without un-fixing T2. They are not redundant.

## Decision: G2 is answered, not assumed

G2's fix may be inert, and the honest states are three, not two: PERSISTED, NOT PERSISTED, or
INDETERMINATE. A null result is only a finding if the search scope is quantified — grep proves
presence, never absence. The larger and older sample is the v3.30.0 continuation guard's own block
text, which has fired for months; the lock's own blocks are few and recent.

If the answer is NOT PERSISTED, the consequence is bounded and must be recorded rather than
patched over: the boundary never advances, behaviour degrades to the prior state and never to
something worse, and `turn_output` is only evaluated when work is already open — so G2 can never
*cause* a block that would not happen anyway. It produces a misleading message citing a rule the
agent has already satisfied. The durable-state alternative must address the objection that killed
the first attempt: `note_continuation_block` is written only for engaged CT6 runs, so it is empty in
exactly the plain sessions this lock exists for, and writing it from the lock would reintroduce the
F-F state pollution in every repo the user types in.

## Risks

| Risk | Mitigation |
|---|---|
| The notification fires too eagerly and becomes noise | Threshold plus persisted notified-state; pinned by a both-directions test |
| Identity comparison breaks ordinary new-file writes | Compare only where both paths exist; fall back to resolved-path comparison; never raise |
| The union widens the guard enough to block legitimate edits | An explicit passing negative test that an unrelated write still proceeds |
| The naming change alters a verdict | A pre-captured characterization corpus asserting the full dict, with a mutation witness proving the corpus can detect a change |
| A suite number is taken mid-edit | Quiescence check plus a before/after diff hash bracketing the run — the discipline this project has broken most often |
