# Project principles — the two schemas

The field reference for `scripts/principles/principles.py`. The skill body
(`skills/project-principles/SKILL.md`) is the procedure; this file is the
contract the engine validates.

## 1. The register — `project-principles/v1`

Machine twin: `<workspace>/.architect-team/principles.json` (gitignored with
the rest of the runtime state). Human twin: `<workspace>/docs/PROJECT_PRINCIPLES.md`,
rendered from the JSON by every writing verb (and by `render`), one line per
confirmed principle, proposed ones in their own short section, retired ones
listed by id only. The render is deterministic and byte-stable; a file that
already uses CRLF is rewritten with CRLF.

```json
{
  "schema": "project-principles/v1",
  "soft_cap": 15,
  "principles": [
    {
      "id": "P-01",
      "statement": "Every service owns its own tables; no cross-service joins.",
      "scope": "data-model",
      "source": {"kind": "extracted", "file": "docs/ARCHITECTURE.md",
                 "quote": "Services must never join across another service's tables."},
      "status": "confirmed",
      "added_by": "architect",
      "added_at": "2026-11-08T10:00:00Z",
      "confirmed_at": "2026-11-08T10:05:00Z",
      "retired_at": null,
      "retire_reason": null
    }
  ]
}
```

| Field | Values | Notes |
|---|---|---|
| `id` | `P-NN` (numeric, assigned by the engine) or `P-R1`..`P-R4` (the default set) | never reused; a retired id stays in the register |
| `statement` | non-empty | duplicates (casefold + whitespace-collapsed) of a non-retired statement are refused |
| `scope` | `architecture` `data-model` `naming` `reuse` `testing` `ui` `process` `security` | closed enum |
| `source.kind` | `document` `user-stated` `extracted` | `document` / `extracted` REQUIRE `file` + verbatim `quote`; `user-stated` may omit both (a `quote` of the user's words is welcome) |
| `status` | `proposed` `confirmed` `retired` | only `confirmed` binds |
| `added_by` / `added_at` | free text / ISO 8601 UTC | provenance |
| `confirmed_at`, `retired_at`, `retire_reason` | ISO 8601 UTC or null / text or null | `retire` requires a reason |
| `soft_cap` | positive integer, default 15 | exceeding it warns (`principles-cap-exceeded`), never refuses |

### Verbs (CLI `scripts/principles/cli.py`)

| Verb | Writes | Refuses when |
|---|---|---|
| `propose --statement --scope [--source] [--file] [--quote]` | both twins | bad scope; document/extracted source without file + quote; duplicate statement |
| `confirm P-xx` | both twins | unknown id; a retired id ("propose it anew") |
| `add --statement --scope [--quote]` | both twins | as `propose` (user-stated, so no file/quote needed) |
| `retire P-xx --reason` | both twins | unknown id; already retired; blank reason |
| `default-set` | both twins | never — idempotent, skips ids already present |
| `render` | the markdown twin | — |
| `brief` / `show [--json]` | nothing | — |
| `extract-candidates <file> [--json]` | nothing | unreadable file (exit 2) |
| `check --verdicts <sidecar> [--json]` | nothing | unreadable sidecar (exit 2); findings exit 1 |

Exit codes: `0` clean, `1` refused verb / blocking check findings, `2` usage,
payload or register error, `3` internal failure.

### The rendered markdown header

The header states the precedence rule verbatim — *the user's explicit
instruction in this run > confirmed principles > CT6 defaults* — and the soft
cap with the current count. When the cap is exceeded a `**WARNING
principles-cap-exceeded:**` line follows.

## 2. The verdict sidecar — `principles-verdicts/v1`

Written by the producing agent beside the artifact it describes, read by
`check` and by the Layer-3 tool `verify-principles-respected`
(`hooks/vao/principles.py`).

```json
{
  "schema": "principles-verdicts/v1",
  "subject": {"kind": "options", "ref": "openspec/changes/orders/design.md#storage"},
  "verdicts": [
    {"id": "P-01", "verdict": "respected", "why": "orders keeps its own tables", "where": "design.md section 3"},
    {"id": "P-02", "verdict": "violated", "why": "adds prisma", "where": "package.json",
     "user_override": "user, this run: 'use prisma for the orders service, I know it is a new ORM'"},
    {"id": "P-R1", "verdict": "not-applicable"}
  ],
  "options": [
    {"label": "A", "fits": false, "violates": ["P-01"], "why": "shares the billing tables"},
    {"label": "B", "fits": true, "violates": [], "why": "owns its tables, calls billing over its API"}
  ],
  "chosen": "B",
  "auto_mode": true
}
```

| Field | Values | Rule |
|---|---|---|
| `subject.kind` | `design` `contract` `diff` `options` | what is being presented |
| `verdicts[].id` | a register id | one verdict per confirmed principle; unknown ids are a gap |
| `verdicts[].verdict` | `respected` `violated` `not-applicable` | `violated` needs `why` + `where` |
| `verdicts[].user_override` | the user's explicit instruction in THIS run, quoted | downgrades `principle-violated` to the warning `principle-overridden-by-user` |
| `options[]` | `label` (unique), `fits` (bool), `violates[]` (register ids), `why` | present when alternatives were weighed |
| `chosen` | an option label, or null | in `auto_mode` it must be a fitting option unless every option violates |
| `auto_mode` | bool | true = an autonomous run chose; false = the user chose |

### Severities

Hard gaps (the check is `valid: false`; the tool exits `2`):

| Severity | Fires when |
|---|---|
| `principle-without-verdict` | a confirmed principle has no verdict |
| `violated-without-cause` | a `violated` verdict lacks `why` or `where` |
| `principle-violated` | a confirmed principle is violated with cause and no `user_override` |
| `invalid-verdict-value` | a verdict is not one of the three values |
| `duplicate-verdict` | one id carries two verdicts |
| `verdict-for-unknown-principle` | a verdict or an option's `violates[]` names an id not in the register |
| `chosen-option-violates` | `auto_mode` and the chosen option violates while a fitting option exists |
| `chosen-option-missing` | `auto_mode`, a fitting option exists, nothing chosen |
| `chosen-option-unknown` | `chosen` is not an option label |
| `all-options-violate` | every option violates — the hard stop (`escalation-pending.md`) |
| `option-malformed` | an option lacks a unique label or a boolean `fits` |
| `sidecar-schema-unknown` | the sidecar is not a `principles-verdicts/v1` object |

Warnings (reported; never block): `principles-cap-exceeded`,
`no-confirmed-principles` (the register has nothing confirmed, so nothing was
checked — a measured gap, not a pass), `verdict-for-inactive-principle` (a
verdict for a proposed or retired id), `principle-overridden-by-user`, and
`chosen-option-violates` when `auto_mode` is false (the user chose).

### The verdict file

The tool writes `{tool, valid, gaps[], warnings[], confirmed_count,
verdict_count, chosen, auto_mode, checked_at}` to `--out` (default
`<workspace>/.architect-team/vao-verdicts/<sidecar-stem>-verify-principles-respected.json`).
The review-gate evidence cites that path in `principles_review`
(`hooks/review_evidence_schema.py`): `pass` must cite it (dict `verdict_path`
or the sibling `principles_review_verdict_path`); `fail` blocks; `n/a` needs
`principles_review_note`.

## 3. Honest boundary

Both schemas prove that principles were considered and verdicts recorded with
causes. Neither proves a verdict is right; the independent reviewer does that.
The extraction heuristic (`extract-candidates`) is a sentence finder with
deterministic triggers — modal words and rule-shaped headings — and a scope
HINT; it writes nothing and judges nothing.
