---
name: claude-md-efficiency
description: Use when MemPalace is installed and you are authoring or auditing a project's CLAUDE.md (or AGENTS.md). When MemPalace is present, CLAUDE.md becomes a thin POINTER document — it tells the agent WHERE to find things so context is loaded on demand, rather than CONTAINING the full context — and it stays very small. Carries two parts — standards that point to a reference DB / reference MemPalace, and customizations the user can toggle on/off. The deterministic assessor + generator live in scripts/claude_md/claude_md_efficiency.py; this skill is the contract. CONDITIONAL on MemPalace being installed — with no MemPalace, a self-contained CLAUDE.md is correct and this discipline does not apply.
---

# Claude.md Efficiency (CMD-1 … CMD-4)

A large `CLAUDE.md` that an agent must internalize in full burns context on every
turn. When the project has a memory store to point INTO, `CLAUDE.md` should stop
being a container and become a **pointer**: it tells the agent where to find
things and the agent loads that context on demand.

The deterministic pieces — the size budget, the pointer-shape assessor, and the
minimal-pointer generator — live in **`scripts/claude_md/claude_md_efficiency.py`**
(stdlib-only, unit-tested). This skill is the contract + the LLM-judgment
workflow. Do not re-implement the deterministic pieces in prose — call the module.

## The precondition (CMD-1) — MemPalace must be installed

This discipline applies **when (and only when) MemPalace is installed.** With a
reachable MemPalace there is somewhere to point INTO, so `CLAUDE.md` becomes a
pointer. With NO MemPalace there is nowhere to point — a self-contained
`CLAUDE.md` is correct and this discipline does NOT apply. Detect MemPalace per
`mempalace-integration` (its availability check); if absent, leave `CLAUDE.md`
as-is and stop.

## What a pointer-style CLAUDE.md is (CMD-2, CMD-3, CMD-4)

- **A pointer, not a container (CMD-2).** On reading it, the agent must NOT
  internalize its entire contents. Instead it tells the agent where to find
  things — e.g. *"first read your wake-up script, located at XYZ"* — so context is
  loaded on demand. The canonical first pointer is the MemPalace wake-up
  (`mempalace --palace <palace> wake-up`).
- **Very small (CMD-3).** It points; it does not contain. The engine enforces a
  byte budget (`CLAUDE_MD_POINTER_BUDGET_BYTES`); over budget is the strongest
  signal that context that belongs in MemPalace has been inlined.
- **Two parts (CMD-4).** (a) **Standards** that point to a reference DB / reference
  MemPalace (query on demand, never inline); (b) **Customizations** the user can
  toggle on/off at their discretion (and the agent's best guess for defaults).

## Workflow

### Step 1 — Confirm MemPalace is installed (CMD-1)

Per `mempalace-integration`. If absent → this discipline does not apply; stop.

### Step 2 — Assess the current CLAUDE.md

```bash
$(command -v python3 || command -v python) scripts/claude_md/claude_md_efficiency.py assess CLAUDE.md --json
```

Read `is_pointer_style` + the `signals` (`over-budget`, `no-pointers`,
`missing-standards-pointer`, `missing-customizations`). A clean result means the
file already points + fits the budget. The signals are heuristics — judge them.

### Step 3 — Convert to / author a pointer (CMD-2/CMD-4)

If the file is a container (over budget / no pointers), MOVE the inlined context
INTO MemPalace (mine it per `mempalace-integration`) and replace it with pointers.
Use the generator for a correctly-shaped starting point:

```bash
$(command -v python3 || command -v python) scripts/claude_md/claude_md_efficiency.py \
  generate --project "<name>" --palace "<palace>" --out CLAUDE.md
```

Then fill the standards section with the project's actual reference pointers and
the customizations section with the real toggles. Every fact you remove from
`CLAUDE.md` must be reachable from MemPalace via a pointer — never delete context
that is not stored somewhere the agent can load on demand.

### Step 4 — Verify

Re-run the assessor; confirm `is_pointer_style` is true and no `high`-severity
signal remains.

## Honest boundary

The assessor's signals are **heuristics** — a pointer-marker count + a byte
budget, not a proof that every fact is reachable from MemPalace. `over-budget`
can fire on a legitimately information-dense pointer file, and a clean result does
not prove the pointers actually resolve. The engine narrows where to look; the
judgment (is the context truly in MemPalace and reachable?) is yours. And NEVER
shrink `CLAUDE.md` by deleting context that was not first stored in MemPalace —
that is data loss dressed as efficiency.

## Cross-references

- `scripts/claude_md/claude_md_efficiency.py` — the deterministic assessor + generator (the machine).
- `skills/mempalace-integration` — the MemPalace availability check + the mine/wake-up flow this discipline points INTO (CMD-1, CMD-4a).
- `skills/documentation-currency` — the sibling doc-currency discipline; a pointer CLAUDE.md is still an inventory doc kept current.
