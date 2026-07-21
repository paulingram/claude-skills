# CHANGELOG entry rubric

The house shape for a `CHANGELOG.md` entry, distilled from the conventions the
existing entries already follow. It is the contract for
`scripts/docs_tooling/changelog_check.py` — the deterministic half of this rubric.

Two invariants are **machine-checked** by that engine (a suite-enforced gate); the
rest are **judgment** — followed by the author, verified in review, not linted.

---

## The shape

Every release adds ONE new entry at the TOP of `CHANGELOG.md`, directly under the
`# Changelog` preamble. The prior entries are never touched.

```
## [<x.y.z>] — <YYYY-MM-DD> — <slug> (<verdict-first one-line summary>)

**<MAJOR | MINOR | PATCH> — <verdict-first sentence: what changed and its outcome>.**
<the release narrative — per-requirement or per-iteration bullets>

Tests: <what moved> Suite **<N> passing + <M> skipped** (<K> test files) ...
Skill / agent / command counts <UNCHANGED (48 / 39 / 23) | the delta>; <NO new ... | the new surface>.
```

---

## The rules

### 1. Verdict-first headline — *judgment*
The `## [x.y.z]` header carries the version, an ISO `YYYY-MM-DD` date, a kebab-case
`slug`, and a parenthetical that states the outcome, not just the topic. The first
bold sentence of the body classifies the change as `MAJOR` / `MINOR` / `PATCH` and
leads with what shipped and why it matters — the reader learns the verdict before
the mechanism.

### 2. Verified counts only — never invented numbers — *judgment*
Every number in an entry (test totals, file counts, inventory counts, byte deltas)
is a **measured** value, not an estimate or a target. A count that was not actually
run is not written. When a count is unchanged, say so explicitly
(`counts UNCHANGED (48 / 39 / 23)`) rather than omitting it.

### 3. Honest-divergence notes — *judgment*
When what shipped differs from what was planned, the entry says so in its own
words (`HONEST DIVERGENCE`, `HONEST BOUNDARY`, `Also repairs a … release miss`).
The changelog records the real outcome, including dropped scope, deferrals, and
follow-ups — never an idealized version of the plan.

### 4. The suite-total line — **machine-checked**
The top entry MUST contain a suite-total line in the house form:

> `Suite <N> passing + <M> skipped (<K> test files)`

with the release's **verified** counts. Accepted variants (all recognized by the
check): a leading progression `Suite **5646 → 5689 passing + 4 skipped**`, a bare
total `Suite **5362 passing + 4 skipped**`, a leading `- Suite:` bullet, and
trailing qualifier text before the `(<K> test files)` parenthetical. The arrow may
be a unicode `→` or an ASCII `->`; counts may carry thousands commas.

The regex the engine applies:

```
Suite\s*:?\s*\*{0,2}\s*(?:[\d,]+\s*(?:->|→)\s*)?[\d,]+\s+passing\s*\+\s*\d+\s+skipped[^\n]*?test files
```

### 5. The version invariant — **machine-checked**
The top entry's `[x.y.z]` version MUST equal `.claude-plugin/plugin.json`'s
`version`. The manifest and the changelog head move together at release time (see
the "Bump version & release" navigation step in `docs/CODEBASE_MAP.md`), so a
mismatch means a bump landed without its entry, or an entry without its bump.

### 6. Per-release narrative — *judgment*
The body explains the release for a reader who was not present: the problem, the
approach, the notable decisions, and — for a bug-class fix — the root cause and the
regression contract. Depth scales with the release; a docs-only PATCH is short, a
MINOR feature is a full narrative.

### 7. Append-only history — *judgment*
No historical entry is ever edited. Corrections to a past release are made in a NEW
entry that names the miss, never by rewriting the old text. (Current-state facts
that live OUTSIDE the changelog — the README, the maps — are refreshed in place;
the changelog's own history is not.)

---

## What the check does *not* enforce

`changelog_check.py` verifies only rules 4 and 5 — the two invariants a machine can
judge without reading intent. Rules 1, 2, 3, 6, and 7 are LLM-judgment: a reviewer
confirms the headline leads with the verdict, the numbers are real, divergences are
named, the narrative is sufficient, and no historical entry was rewritten. A clean
`changelog_check.py` run is necessary, not sufficient — it means the head is
version-aligned and carries a verified suite line, not that the entry is good.
