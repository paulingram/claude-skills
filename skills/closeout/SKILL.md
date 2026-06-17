---
name: closeout
description: Use at the END of a work session — before compacting context, before declaring work done, or when invoked via /architect-team:closeout. A double-check that reviews the changes made against the requirement and confirms the documentation has been suitably updated; if any doc in the currency inventory is lax or incomplete, it updates it itself rather than just flagging it. Fires automatically before compaction via the PreCompact hook (hooks/precompact-closeout.py), which surfaces the deterministic staleness signals from hooks/closeout_check.py. Reuses the documentation-currency discipline + the doc-updater pattern; operates from the working-tree diff so it works OUTSIDE a full pipeline run.
---

# Closeout (CO-1 … CO-3)

Work is not done when the code is done — it is done when the code AND the
documentation reflect what changed. The **closeout** is the last-mile
double-check that closes that gap: before context is compacted or work is
declared finished, review what changed against the requirement, confirm every
affected document is current, and **update any that are stale — yourself, now,
not as a deferred follow-up.**

This skill is the contract. The deterministic staleness detector is
**`hooks/closeout_check.py`** (stdlib-only); the automatic trigger is the
PreCompact hook **`hooks/precompact-closeout.py`**. The actual review-and-update
work reuses the **`documentation-currency`** discipline (the canonical inventory
+ per-doc rules) and the **`doc-updater`** whole-file-rewrite pattern. Do not
re-implement those — follow them.

## When this fires (CO-1)

- **Automatically, before compaction.** The `PreCompact` hook runs
  `closeout_check.py` against the working tree and, when docs look stale, injects
  a reminder to run this skill BEFORE the compaction proceeds. The hook is a
  non-blocking double-check — it never blocks compaction; performing the update
  is your job, prompted by the reminder.
- **At any end-of-work boundary.** Before you tell the user the work is done,
  run the closeout review.
- **On demand** via `/architect-team:closeout` (read-only with `--check`).

The closeout is distinct from the pipeline's Phase-8 doc-currency gate: that gate
runs inside a full `/architect-team` run with a coverage-map + run ledger; the
closeout runs at ANY session's end (often with no pipeline artifacts at all),
working from the git working-tree diff. That is why it has its own engine + agent
(`closeout-agent`) rather than reusing `doc-updater` directly — `doc-updater`
depends on pipeline artifacts the closeout context may not have.

## Workflow

### Step 1 — Assess (deterministic signals)

Run the engine to get the advisory staleness signals:

```bash
$(command -v python3 || command -v python) hooks/closeout_check.py --repo . --json
```

It classifies the working-tree changes into `code` / `docs` / `version` /
`new_surfaces` and emits `signals` such as `code-changed-no-doc`,
`version-bumped-no-changelog`, `source-changed-no-changelog`, and
`new-surface-undocumented`. `docs_appear_current: true` with no signals means the
deterministic check is clean — but still do Step 2 (the engine catches structural
staleness, not semantic staleness).

### Step 2 — Review against the requirement (CO-2)

Independently review the session's changes against the **requirement / mandate**
(what the user actually asked for), not just against the engine signals:

- Read the working-tree diff (`git diff` + `git status`) — what did this session
  change?
- For each change, ask: which docs in the `documentation-currency` inventory does
  it affect? (README, CHANGELOG, CLAUDE.md, AGENTS.md, `docs/CODEBASE_MAP.md`,
  `docs/INTEGRATION_MAP.md`, per-codebase `*_MAP.md`, and — when present —
  `phenotypes/README.md` / `SCHEMA.md`.)
- Is each affected doc current with what shipped? Counts, version strings, new
  surfaces (skills/agents/commands), new external integrations, the CHANGELOG
  entry, the map note ledgers.

### Step 3 — Update if lax, do not just flag (CO-3)

If any doc is stale or incomplete, **perform the update** — do not merely suggest
it. Apply the `documentation-currency` per-doc rules and the `doc-updater`
discipline: whole-file rewrites that touch ONLY the currency inventory (never
source, tests, `openspec/*`, or the version source-of-truth — the version bump is
the orchestrator's job). Every update must cite the triggering change.

When the closeout is run as an isolated/heavy pass, spawn the **`closeout-agent`**
to do Steps 1-3 (it carries the bounded doc-write scope). For an inline closeout
at the end of a normal session, do the review-and-update directly per this skill.

### Step 4 — Confirm

State plainly what was reviewed and what was updated (or that docs were already
current). Then it is safe to compact / declare done. If you updated docs, the
changes are part of the session's work — commit them with it, do not leave a
stale doc and a fixed code in the same state.

## Honest boundary

The engine's signals are **heuristics** — `code-changed-no-doc` can fire when the
docs genuinely needed no change (e.g. a pure refactor), and a clean engine result
does not prove semantic currency. The engine narrows where to look; the
review (Step 2) is judgment. Never silence a signal by editing a doc you did not
actually need to change, and never claim docs are current without having looked.

## Cross-references

- `hooks/closeout_check.py` — the deterministic staleness engine (the machine).
- `hooks/precompact-closeout.py` — the PreCompact trigger (CO-1).
- `skills/documentation-currency` — the canonical currency inventory + per-doc rules this skill applies.
- `agents/closeout-agent` — the spawnable worker for an isolated closeout pass.
- `agents/doc-updater` — the in-pipeline (Phase 8) counterpart + the whole-file-rewrite pattern this skill reuses.
