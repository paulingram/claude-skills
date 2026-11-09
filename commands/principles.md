---
description: Show, add, retire or extract the current project's codified principles (the project-principles register at .architect-team/principles.json, rendered to docs/PROJECT_PRINCIPLES.md). Read-only by default — `show` lists the confirmed, proposed and retired principles with their sources; `add` codifies a rule the user states (confirmed immediately); `retire` removes one with a recorded reason; `extract` prints candidate statements from a document for the user to confirm. The same engine every pipeline lane consults at intake and before presenting a design.
argument-hint: "[show | brief | add \"<statement>\" --scope <scope> | retire P-xx --reason \"...\" | extract <file>] [--workspace <path>]"
---

# /architect-team:principles

Reports and maintains the current project's codified principles — the rules
that hold across runs — through the `project-principles` engine
(`scripts/principles/principles.py`, CLI `scripts/principles/cli.py`). Mirrors
the `/architect-team:discipline-status` shape: a user-facing standalone command
over the same mechanism the pipeline lanes fire automatically (extract at
intake, `check` before a design is presented).

**Read-only by default.** With no arguments, or `show`, the command lists the
register and changes nothing. `add`, `retire` and `extract` are the only other
verbs; `extract` writes nothing either — it prints candidates for the user to
confirm. `<workspace>/docs/PROJECT_PRINCIPLES.md` is changed ONLY by the engine CLI: this
command never edits it by hand.

## Dispatch mode banner — runs first

The interpreter is selected ONCE via `$(command -v python3 || command -v python)`
(the v2.16.0 detect-once form). Best-effort — a subprocess failure surfaces a
one-line note and the command continues.

```bash
$(command -v python3 || command -v python) "${CLAUDE_PLUGIN_ROOT}/scripts/setup/teams_mode.py" --banner --command "/architect-team:principles"
```

## Argument parsing

- `show` (default) → list the register. Read-only.
- `brief` → print the confirmed-principles block a spawn brief carries — the text the lanes paste verbatim under `Confirmed project principles` in every architect and teammate brief (`(none confirmed)` is written out, never omitted). Read-only.
- `add "<statement>" --scope <scope>` → codify a rule the USER stated; confirmed
  immediately (the user saying it is the confirmation). `<scope>` is one of
  `architecture` `data-model` `naming` `reuse` `testing` `ui` `process`
  `security`. Pass the user's verbatim words as `--quote` when they differ
  from the statement.
- `retire P-xx --reason "<why>"` → retire a principle. The reason is mandatory.
- `extract <file>` → print candidate statements (verbatim quote + line number)
  from a markdown document. Writes nothing.
- `--workspace <path>` → operate on the given codebase root instead of cwd.
  Default: `git rev-parse --show-toplevel` (cwd fallback).

Anything else prints the argument hint and exits.

## Phase 1 — Resolve workspace

```bash
WORKSPACE="${WORKSPACE:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}"
```

## Phase 2 — Run the verb

Detect-once invocation (`check`-style verbs exit non-zero on a meaningful
result; the old `python3 X || python X` form would re-run the verb on it).

```bash
# show (default)
$(command -v python3 || command -v python) "${CLAUDE_PLUGIN_ROOT}/scripts/principles/cli.py" show --workspace "${WORKSPACE}"

# brief
$(command -v python3 || command -v python) "${CLAUDE_PLUGIN_ROOT}/scripts/principles/cli.py" brief --workspace "${WORKSPACE}"

# add
$(command -v python3 || command -v python) "${CLAUDE_PLUGIN_ROOT}/scripts/principles/cli.py" add --workspace "${WORKSPACE}" --statement "<statement>" --scope <scope> --quote "<the user's words>"

# retire
$(command -v python3 || command -v python) "${CLAUDE_PLUGIN_ROOT}/scripts/principles/cli.py" retire P-xx --workspace "${WORKSPACE}" --reason "<why>"

# extract
$(command -v python3 || command -v python) "${CLAUDE_PLUGIN_ROOT}/scripts/principles/cli.py" extract-candidates "<file>"
```

Exit codes: `0` clean, `1` the engine refused (unknown id, duplicate statement,
missing reason) — relay the refusal verbatim, `2` usage or an unreadable
register, `3` an internal failure.

## Phase 3 — Display

For `show`, render the engine output as a short table:

```
Project principles — workspace: <workspace>   soft cap: 15 (confirmed: 3)
Precedence: the user's explicit instruction in this run > confirmed principles > CT6 defaults

  Id     Status     Scope         Statement                                   Source
  P-01   confirmed  data-model    Every service owns its own tables.          extracted docs/ARCHITECTURE.md
  P-R1   confirmed  reuse         Extend an existing module before ...        document skills/reuse-first-design/SKILL.md
  P-R2   proposed   reuse         Compose with existing modules via ...       document skills/reuse-first-design/SKILL.md
  retired: P-02

  Register: <workspace>/.architect-team/principles.json
  Rendered: <workspace>/docs/PROJECT_PRINCIPLES.md
```

Print any `WARNING principles-cap-exceeded` line the engine emits, unchanged.

For `extract`, print the candidates as the engine lists them (`L<line> [kind]
"quote"`), then ask the user with ONE `AskUserQuestion` which to codify: each
chosen candidate is written with `propose --source extracted --file <file>
--quote "<verbatim>"` followed by `confirm`. A candidate the user did not pick
is NOT written — nothing becomes confirmed silently.

## Safety rules

- Read-only by default; `add` and `retire` are the only mutating verbs, and both
  act on what the user said in this invocation.
- Never edit `<workspace>/docs/PROJECT_PRINCIPLES.md` or
  `<workspace>/.architect-team/principles.json` by hand — the engine CLI is the only writer.
- Best-effort on the banner; the engine's own exit code is the command's.
- An empty register is reported as such and the user is offered
  `default-set` (the reuse-first ladder as PROPOSED `P-R1`..`P-R4`) — this
  standalone command never runs it without asking. (The pipeline lanes DO run it
  at intake when `.architect-team/principles.json` is absent, because it only
  PROPOSES — a proposed principle never binds until the user confirms it.)
- The lanes' `check` verb (`cli.py check --verdicts <sidecar> --workspace <ws>`,
  the same validator as `hooks/vao/principles.py`) is not exposed here; it runs
  before a design, contract, diff or option set is presented.

## Cross-references

- `skills/project-principles/SKILL.md` — the canonical discipline (the four
  verbs, the binding rule, the option-tagging and autonomous-run rules).
- `skills/project-principles/references/principles-schema.md` — the register +
  verdict-sidecar schemas and the severity table.
- `scripts/principles/cli.py` — the engine CLI this command invokes.
- `hooks/vao/principles.py` — `verify-principles-respected`, the Layer-3 check
  the lanes run before presenting a design.
