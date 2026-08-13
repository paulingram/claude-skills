# Proposal: completion-lock-followups

## Why

v3.56.0 shipped the turn-boundary completion lock and, with it, an honest record of what the
adversarial passes found but the run did not close. `docs/proposals/COMPLETION_LOCK_FOLLOWUPS.md`
names fifteen escapes across six passes — ten closed, four narrowed, one accepted boundary — plus
seven items left genuinely open. This change closes the open seven.

The headline is **N5b**, and it is an operational gap rather than a hardening nicety. The README
states that nothing releases a wedged run automatically. That is correct and it is the entire point
of "unbounded" — the user chose it explicitly. But the sentence does two jobs and the second is
incidental: *nothing tells you automatically either*. A run wedged overnight with nobody watching
produces no signal at all. That is fixable without weakening unboundedness by even a little: notify
at the persistence threshold and **keep blocking**.

The remaining six are the residue a live gate accumulates. Two are guard holes documented as
boundaries rather than closed — an environment variable that relocates both the protected store and
the protection (**N3**), and a hardlink that path resolution cannot see (**N2b**). One is an
unverified precondition that may make a shipped fix inert (**G2**). One is a naming trap one careless
rename away from reproducing T4, a bug that already shipped live for two commits
(**prose_lines/line_count**). One is attacker-controlled text rendering inside an enforcement message
(**F7**). One is a mutation harness whose classification method cannot distinguish a caught mutation
from a no-op (**mutation-harness**).

## What Changes

- **N5b** — the completion lock emits a best-effort `issue_discovered` notification once it has
  blocked persistently, and continues to block. NOT implemented by advancing the continuation
  guard's no-progress counter: `escalation-pending.md` is agent-written and the lock deliberately
  does not honour it, so that route would raise the marker without releasing anything and burn a
  counter that then mis-fires the moment work finally closed.
- **N3** — the ground-truth guard resolves its protected set independently of the task-root override,
  protecting the union of the real default root and any configured root. An environment variable may
  add to the protected set; it may never remove the real store from it.
- **N2b** — the guard compares filesystem identity, so a hardlink under another name is caught. Fails
  safe: identity is compared only when both paths exist, and an indeterminate comparison falls back
  to the existing resolved-path check rather than raising or allowing.
- **F7** — the block-message clipper strips bullet-prefix and colon-terminated-heading shapes, so task
  text cannot present as enforcement output.
- **prose_lines/line_count** — the load-bearing counter and the cosmetic one are made distinguishable
  at every call site, pinned by a characterization corpus proving the classifier verdicts unchanged.
- **G2** — the unverified precondition is answered against the live installed lock, and the answer
  recorded whichever way it falls.
- **mutation-harness** — the result-line-parsing artifact is converted to exit-code classification
  with a changed-file assertion, removing the class of a no-op mutation logging green.

## Out of scope — deliberately, with reasons already measured

- **The G1 fenced-summary residual.** Both candidate remedies were measured and declined: one stopped
  reaching when the ceiling was correctly raised for G3, and the other misclassified 7 of 9 realistic
  code samples (unified diffs, YAML, shell comments, docs, tables, listings). Adopting a remedy
  already measured as worse is not progress. G1 stays a named boundary.
- **The classifier pendulum.** Six revisions; the accepted residual — markerless prose of 3 to 5
  report-length lines — is deliberate. A seventh threshold is the pendulum, not a fix.

## Impact

- Affected code: the completion-audit hook, the unilateral-override guard, and the open-work substrate.
- Affected specs: `turn-boundary-completion-lock` (MODIFIED — three requirements).
- No new skill, agent, command, hook script, or Layer-3 tool. Counts unchanged (53 / 39 / 25 / 7 / 22).
- Service-tier separability unaffected (26 modules checked).
