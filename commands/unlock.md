---
description: Release a completion hold on the USER's explicit word. When the Stop hook keeps holding a turn after the work is genuinely done -- or after the user has said "good enough, move on with what you have" -- this command inspects what holds the turn (open harness tasks, unresolved asks, declared and converge gates, the active run marker), then retires, resolves, waives and stands them down under ONE durable record of the user's words (.architect-team/releases/unlock-<ts>.json, a decisions-ledger line, pipeline-stand-down.md). Sanctioned only as the user's own slash command; the PreToolUse gate refuses the release verb from any other turn and no Stop hold text names it.
argument-hint: "<why, in your own words -- e.g. good enough, move on with what you have>"
disable-model-invocation: true
---

# /architect-team:unlock

The completion lock, the continuation guard and the declared-gates arm hold a
turn open until the work they can see on disk is closed. That is the design:
they read harness-written state, not the agent's word. Two things they cannot
see are (1) work that is done but whose state was never closed -- a task
nobody marked complete, an ask the transcript never resolved, a converge gate
whose record was never written -- and (2) **the user's own decision** that
what exists is good enough. This command is how the user's decision becomes
released state, auditable and in their words.

**The user runs this. The agent never does.** The command is
`disable-model-invocation: true`, so the model cannot invoke it; the engine's
`release` verb is refused by the PreToolUse gate (`hooks/pretool_skill_gate.py`
Arm 5) unless the latest genuine user prompt is this command; and no Stop hold
text names this command. An agent that is held finishes the work or tells the
user plainly what is open -- it does not look for the exit.

## Step 1 -- show what holds the turn (read-only, always allowed)

```bash
$(command -v python3 || command -v python) "${CLAUDE_PLUGIN_ROOT}/hooks/completion_unlock.py" inspect --root "$(pwd)"
```

Report the output to the user as a short list: the live open tasks (id +
subject), the unresolved asks, the open declared gates (converge gates
included), the run marker's slug and phase. If `session` reads `(unresolved)`,
say so -- the task list is found through the run marker, the environment or
the only session directory with open work, in that order; pass
`--session-id <id>` when the user can name it (the harness `session_id`).

## Step 2 -- the reason is the user's, verbatim

`$ARGUMENTS` is the user's reason. If it is empty, ask ONE question with
`AskUserQuestion` ("Why release the hold? Your words go into the record.")
and use the answer verbatim. Never supply a reason yourself, never
paraphrase, never run the release with a placeholder.

## Step 3 -- release

```bash
$(command -v python3 || command -v python) "${CLAUDE_PLUGIN_ROOT}/hooks/completion_unlock.py" release --root "$(pwd)" --reason "$ARGUMENTS"
```

Add `--session-id <id>` when Step 1 could not resolve the session, and
`--scope tasks|asks|gates|run` (repeatable) when the user wants only part of
the hold released. `--dry-run` reports what would be released and changes
nothing. The engine writes the record FIRST, then: retires the session's open
harness tasks through the operator verb (`open_work.py retire --force`, every
task carrying the reason), resolves the open asks with the record as
evidence, WAIVES (never fakes as satisfied) every unsatisfied declared gate
with `waived_by: user` and the record as evidence, stands the active run down
(`pipeline-stand-down.md` carries the words) and clears the guard state, and
appends one `other`-kind line to the decisions ledger so the project homepage
shows the release.

## Step 4 -- report

Tell the user: what was released (the engine's `released:` line), the record
path, and anything `still held:` or `problem:` named -- an unreadable task
store or a session that could not be resolved is theirs to settle, not yours
to work around. Exit 0 means the turn will end cleanly at the next Stop; exit
1 means something remains and says what.

## Rules

- Runs only when the user typed this command in this turn. Never propose it
  as a way to end a held run; if the user asks how to clear a hold, you may
  name it.
- The release record under `.architect-team/releases/` is written by the
  engine and never edited (the override guard refuses `Edit`/`Write` on it).
- A waived gate stays visibly waived -- `inspect` and the homepage list it --
  it is not retro-marked satisfied.
- Canonical discipline: `skills/common-pipeline-conventions/references/completion-unlock.md`.
