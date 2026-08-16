# agent-directive-block-menu (v3.61.2)

## Why

A live field report (2026-08-16, a run on another machine at v3.60.0): a
session with a lingering active-run marker re-printed the continuation
guard's full menu at the USER on every conversational turn, indefinitely,
and the agent never acted on it. The user's question — "it shouldn't need me
to do this; why is my claude printing it out" — is the defect statement: the
gate was correct, and the MESSAGE induced the agent's non-compliance. The
lock composes the same text with no budget by design, so the repetition had
no ceiling.

## What

- **M1 — agent-directive decision procedure** in
  `hooks/pipeline-completion-audit.py::_continuation_block_text`: a no-relay
  rule up front; CHECK-then-ACT options with the finished case FIRST and a
  fully-qualified exit command (absolute script path + `--root`, both
  injected by the hook, which always knew them) plus "do this YOURSELF, now";
  the human fork LAST, named the only user-facing case.
- **M2 — terse-on-repeat**: full directive once per wedge episode; at a
  consecutive count >= 2 the block collapses to a few lines that keep exactly
  the two properties that matter (the no-relay rule and the actionable exit).
  No new state — the guard reuses its no-progress count; the lock path reads
  the N5b notify state (already fingerprint-excluded) via the new
  `_lock_consecutive` reader, threading `session_id` into
  `_completion_lock_guard_text`.

## Honest ledger

- The ordering pin's first draft matched `--mark-complete` in the WORKLIST
  (the lifecycle line), not in the decision procedure — a pin passing for
  the wrong reason, exposed only when mutation W5 ESCAPED.
- W5's own first placement inserted the demotion OUTSIDE the slice the fixed
  pin measures — mutation and pin talking past each other. Corrected; the
  in-procedure demotion is CAUGHT.
- Two heredoc escape manglings during witness authoring (the recurring
  environment trap), both caught by anchor-count assertions before any
  mutation ran.
