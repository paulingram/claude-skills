# Schema v7 — the breaking change

Schema v7 adds five required fields to `REQUIRED_EVIDENCE_FIELDS`:

```python
REQUIRED_EVIDENCE_FIELDS = {
    # v6 fields (unchanged)
    "task_id", "spec_review", "quality_review", "real_not_stubbed",
    "tests", "demo_artifact", "files_changed", "reuse_compliance",
    "visual_fidelity_review", "test_completeness_review",
    "integration_testing_review", "ui_interaction_review",
    # v7 VAO fields
    "oracle_match_review",      # cites verify-oracle-match verdict
    "baseline_clean_review",    # cites verify-baseline-clean verdict
    "no_fake_data_review",      # cites verify-no-fake-data verdict
    "adversarial_review",       # Layer 2 — adversarial-reviewer's verdict
    "skill_invocation_audit",   # cites Layer 6 audit verdict
}
```

Each field accepts EITHER:
- A string in `{'pass', 'n/a', 'fail'}` — legacy review-shape.
- A dict `{verdict: ..., verdict_path: "<path to cited JSON>"}` — canonical v7 shape that cites the on-disk tool verdict.

The hook blocks any evidence file missing any field OR carrying a `fail` verdict on any field.

### The OPTIONAL tool-mediated fields (validated when present)

Four fields are present-only-when-applicable. Each follows the identical contract: **absent ⇒ the evidence file is still valid v7** (no gap is attributable to the field), **present ⇒ the value MUST be `pass` / `n/a` / `fail` in either the string or the `{verdict, verdict_path}` dict shape, and a `fail` BLOCKS completion at the review gate**.

| Optional field | Present when | Cites |
|---|---|---|
| `interactions_honored_review` | the run's oracle spec carries a non-empty `interactions[]` | the `verify-interactions-honored` verdict |
| `live_verification_review` | the evidence claims "verified live" | the `verify-live-verification-claim` verdict |
| `appearance_scope_review` | the slice's diff touches frontend presentation surface | the appearance-scope verdict / trace |
| `check_integrity_review` (v3.47.0) | the slice's diff adds test files, or any verification command is cited as evidence | the `verify-check-can-fail` verdict path |

`check_integrity_review` carries the same blocking semantics as the rest: absent is fine, `pass` / `n/a` are fine, and a `fail` value BLOCKS the review gate exactly as a `fail` on a required field does — the check-integrity finding is escalated and fixed, never marked complete around.

It is OPTIONAL in the schema by design, not by weakness: "the diff adds a test file" is not computable from the evidence file's own content (`tests.added >= 1` is always true, and `files_changed` cannot distinguish an added file from a modified one), so the schema validates it when present and the diff-keyed REQUIREMENT lives one layer out, in the Stop-audit arm `_audit_check_integrity` (`hooks/pipeline-completion-audit.py`) which can run `git diff --diff-filter=A` against the merge base. A `pass` must cite the verdict path per the citation contract above; the cited verdict file — not the inline summary — is the source of truth.

Red-first is the discipline this field enforces: every NEW test proves it can go red, from one of exactly three named sources, before its green is trusted. The canonical statement lives in `team-spawning-and-review-gates` `## Red-first — a new guard is not evidence until it has been shown to fail`; this skill owns the tool and the field that carry it.

**Migration.** v6 evidence files DO NOT validate against v7. Runs not in flight at the v2.0.0 upgrade: no action needed; new runs use v7 from Phase 0.5. Runs in flight at upgrade: re-spawn the active teammates against v7.
