"""Single-source-of-truth constants for cross-file drift pins (v3.35.1).

These are deliberate TRIPWIRES: each value is pinned here as a literal (never
derived from the source module it guards) so an accidental schema/vocabulary
change turns the suite red. Before this module, the same magic numbers were
duplicated across up to five test files, so an intentional change meant a
multi-file hunt; now it is a one-line edit here.
"""

# Review-evidence schema v7 (hooks/review_evidence_schema.py): the required
# field count. Pinned by test_cross_consistency / test_independent_review /
# test_vao_live_verification_claim / test_appearance_change_policy /
# test_prod_safe_classification_discipline.
EXPECTED_EVIDENCE_FIELD_COUNT = 17

# scripts/notify/notify.py EVENT_TYPES — the v3.34.0 ten-event vocabulary.
# Pinned by test_notify_wiring / test_heartbeat.
EXPECTED_NOTIFY_EVENT_COUNT = 10
