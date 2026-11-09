# Completion-hold release discipline (v4.1.0)

Canonical home of the rule the constitution's `## Completion-hold release (v4.1.0)`
stub points at. Read it whenever a turn is being held and you are deciding
what to do about it.

## The rule

A held turn is held because registered work is open: a harness task that is
not complete, an ask the transcript recorded and nothing resolved, a declared
gate (a `converge:<kind>` gate included) with no satisfying record, an active
run marker. The Stop hook reads those from disk; nothing an agent writes
releases them. **Releasing a hold is the USER's verb.** It exists as the
`/architect-team:unlock` command over `hooks/completion_unlock.py`, and it is
sanctioned only inside the user's own command turn.

As the agent under a hold you have exactly two moves:

1. **Finish the work.** Close the task through the task tools, write the
   verdict or record the gate names, resolve the ask by doing it. This is the
   default and it is what the hold is for.
2. **Tell the user plainly what is open** -- the `inspect` verb is read-only
   and always allowed:

   ```bash
   $(command -v python3 || command -v python) "${CLAUDE_PLUGIN_ROOT}/hooks/completion_unlock.py" inspect --root "$(pwd)"
   ```

   Report it as a list and let them decide. If they ask how to clear the
   hold, you may name the command. You never run its `release` verb, and you
   never suggest it as your way out of the loop.

## What the release does (so you can explain it)

The engine writes `.architect-team/releases/unlock-<ts>.json` first -- the
user's words, the session, what held -- then closes each source through the
substrate that owns it: open tasks are RETIRED through `open_work.py`'s
operator verb with `--force` (the human said the list is done) so the store
stays registered and every task carries the reason; open asks are RESOLVED
with the record as evidence; unsatisfied declared gates are WAIVED
(`waived_at` / `waived_by: user` / `evidence_path` -> the record), never
faked as satisfied; the active run is STOOD DOWN (`pipeline-stand-down.md`
carries the words) and the guard state cleared; one `other`-kind decision is
appended so the project homepage shows the release. The Stop arm honours a
waiver only when its evidence is a real release record inside
`.architect-team/releases/`; a waiver with any other evidence is reported as
a violation that does not hold.

## How the hold reaches you (and why the user no longer sees it)

Since v4.1.0 a refused Stop travels as hook JSON on stdout --
`hookSpecificOutput.additionalContext` -- which Claude Code shows only as
transcript feedback while holding the turn through the same loop protections
as a block. The directive is written for you; the user's main view stays
clean. `CT6_STOP_HOLD_MODE=block` restores the hook-error channel for a
harness that does not honour `additionalContext` on Stop;
`CT6_STOP_USER_NOTICE=1` adds a one-line count for the user. Claude Code also
caps consecutive hook continuations (eight by default, reset on every tool
call); a wedged turn ends there -- which is one more reason the lock reports
counts honestly instead of looping on a message.

## The harness pin (v4.1.1)

The quiet channel is Claude Code's behaviour, not ours. `hooks/hold_channel.py`
names the harness range it was verified on (`HOLD_CHANNEL_VERIFIED_MIN`, the
first build, and `HOLD_CHANNEL_VERIFIED_LINE`, the release line whose later
patches count as verified); the SessionStart hook reads the running version
(`claude --version`, else the `version` stamp on transcript records) and prints
ONE line when the harness is older than that build or on a newer, unverified
line. An unknown version prints nothing. `CT6_STOP_HOLD_MODE=block` is the
remedy when the line appears and agents are stopping with work open;
`CT6_HOLD_CHANNEL_PIN_DISABLED=1` silences the line. To re-verify on a new
harness: on a workspace with one open harness task, end a turn and confirm the
transcript shows `Stop hook feedback` and the turn continues; then bump both
constants and record the harness version in the CHANGELOG entry that ships the
bump.

## Enforcement

- `hooks/pretool_skill_gate.py` Arm 5 refuses a Bash command carrying
  `completion_unlock.py ... release` unless the latest genuine user prompt in
  this session's transcript carries the `/architect-team:unlock` marker and the
  session is not a teammate or subagent. It fails CLOSED on a missing
  transcript. Kill-switch: `CT6_UNLOCK_GATE_DISABLED`.
- `commands/unlock.md` is `disable-model-invocation: true`: the model cannot
  invoke it through the Skill tool.
- `hooks/pretool_unilateral_override_guard.py` refuses `Edit` / `Write` on
  `.architect-team/releases/*`; the records are written by the engine only.
- `tests/test_stop_hold_channel.py` sweeps every Stop hold text for the
  command's name: the held agent is never handed its exit.

## Honest boundary

Bash can reach the module in forms the arm's command-text match does not see,
and a hand-written release record is indistinguishable from a real one on
disk -- the same named residual every filesystem gate in this plugin carries.
The record, the decisions-ledger line and the stand-down artifact make a
misuse a deliberate act on a named surface, visible after the fact; they do
not make it impossible.

## From the constitution stub (moved v4.1.2)

A held turn is held because registered work is open, and nothing an agent writes releases it. Releasing a hold is the USER's verb -- the `/architect-team:unlock` command over `hooks/completion_unlock.py`, sanctioned only inside the user's own command turn (the PreToolUse gate refuses its `release` verb from any other turn, the command is `disable-model-invocation: true`, and no Stop hold text names it). Under a hold you have two moves: finish the work, or run the read-only `inspect` verb and tell the user plainly what is open so THEY decide. The release writes a durable record of the user's words, waives gates visibly (never fakes them satisfied), and is reported on the project homepage.
