---
last_updated: 2026-07-04T13:00:00Z
purpose: archive-index
note: >-
  The never-delete registry for documentation dispositioned out of the CLAUDE
  TEAM SIX living doc set. Archive, never hard-delete — every doc removed from
  the living set is git mv'd here (history preserved) and listed below.
---

# Documentation Archive Index

> This is the **archive registry** for CLAUDE TEAM SIX (internal slug
> `architect-team`). When a `documentation-currency` / `closeout` disposition
> determines a **flat, non-historical** doc is stale and not worth updating in
> place, the doc is **`git mv`'d into `docs/archive/`** — never hard-deleted —
> and gets a row in this index (original path + reason). Every file physically
> present under `docs/archive/` **except this `INDEX.md`** MUST have a matching
> entry here, and every entry's git history is traceable via `git log --follow`.
> A `frozen-historical` doc (a dated, point-in-time plan or design record) is
> **kept in place** with at most a one-line historical-marker header — it is
> preserved as-authored, not archived.

## Archived flat docs

_None yet._

No flat documentation file has been dispositioned into `docs/archive/` to date.
When the first one is, it is listed here as:

| Original path | Reason | Archived path |
| --- | --- | --- |
| _(none)_ | _(none)_ | _(none)_ |

---

## Run record — `doc-currency-refresh` (2026-07-04)

The `doc-currency-refresh` change re-verified the full expanded in-scope doc set
(83 tracked docs: 22 flat + 49 living specs + 12 non-archived change docs) and
dispositioned every one. Disposition of record:
[`.architect-team/doc-disposition/ledger.json`](../../.architect-team/doc-disposition/ledger.json).

**Zero flat docs required archival this run.** All **22** flat docs verdicted
`current` (12), `updated` (3 — CHANGELOG / CLAUDE.md / README.md), or
`frozen-historical` (7 — the dated `docs/superpowers/` plans + specs, kept in
place with a one-line historical-marker header, bodies byte-immutable). No flat
doc was stale-and-not-worth-updating, so no `git mv` into `docs/archive/` was
performed — hence the empty archived-flat-docs table above.

The only documentation archived this run was **OpenSpec change docs**, moved by
the `openspec archive` tool into its canonical home under
`openspec/changes/archive/` (NOT `docs/archive/` — the OpenSpec tool owns that
tree and its layout). Recorded here for reachability:

| OpenSpec change | Shipped version | Archived path |
| --- | --- | --- |
| `consolidate-duplicated-rules` | v3.1.0 | [`openspec/changes/archive/2026-07-04-consolidate-duplicated-rules/`](../../openspec/changes/archive/2026-07-04-consolidate-duplicated-rules/) |
| `exploration-pipeline` | v3.2.0 | [`openspec/changes/archive/2026-07-04-exploration-pipeline/`](../../openspec/changes/archive/2026-07-04-exploration-pipeline/) |
| `librarian-installable` | v3.29.0 | [`openspec/changes/archive/2026-07-04-librarian-installable/`](../../openspec/changes/archive/2026-07-04-librarian-installable/) |

Each of the three was archived via `openspec archive <slug> -y` (ADD-only delta
folded cleanly into a living spec), with `openspec validate --all --strict`
green after each. Their change docs (proposal / design / tasks / specs) are
byte-identical to their pre-archive state — history preserved via git rename
detection.
