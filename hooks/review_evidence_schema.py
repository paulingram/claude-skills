#!/usr/bin/env python3
"""Shared review-gate evidence schema for the architect-team hooks.

SINGLE SOURCE OF TRUTH for the evidence-file contract enforced by BOTH
`review-gate-task.py` (PostToolUse / TaskUpdate) and `teammate-idle-check.py`
(SubagentStop). Before v0.9.9 the two hooks each carried their own copy of the
schema and drifted: the idle hook validated 8 fields while the task hook
validated 11. Centralising the schema here makes that drift structurally
impossible — both hooks import this module.

This module is NOT a hook itself; it is never wired in hooks.json. The hook
scripts import it because, when a script is run as `python3 <hooks-dir>/x.py`,
the script's own directory is `sys.path[0]`, so a sibling module resolves.
"""
from __future__ import annotations

from typing import Any

# Evidence schema v7 (v2.0.0 added the six required Verified Agent Output
# fields — `oracle_match_review`, `baseline_clean_review`, `no_fake_data_review`,
# `adversarial_review`, plus the existing `visual_fidelity_review` is now
# MANDATORILY backed by a `verify-rendered-parity` tool verdict path, and a new
# `skill_invocation_audit` field cites the Layer-6 `skill_invocation_audit.py`
# verdict path. v6 (v0.9.19) added the required `ui_interaction_review` field —
# a hook-enforced gate confirming every interactive element is genuinely
# UI-tested, every page is the real live page rather than a placeholder, and
# every displayed value is correctly static or dynamically bound — or a
# user-confirmed stub; the same path `visual_fidelity_review` (v0.5.0),
# `test_completeness_review` (v0.9.0) and `integration_testing_review` (v0.9.5)
# each took via a SCHEMA_VERSION bump. v5 (v0.9.13) added the required
# `independent_review` block — the verdict of an independent `task-reviewer`
# agent, so the Phase 3 gate structurally cannot pass on the teammate's
# self-attestation. The v7 fields below are the teammate's OWN self-review and
# remain REQUIRED in every .architect-team/reviews/<task-id>.json evidence file.
#
# v7 BREAKING CHANGE: review-evidence files conforming to v6 are REJECTED
# because the six VAO fields are missing. The migration path is documented in
# CHANGELOG and skills/verified-agent-output/SKILL.md — runs in flight at the
# v2.0.0 upgrade must re-spawn their teammates against v7.
SCHEMA_VERSION = 7

REQUIRED_EVIDENCE_FIELDS = {
    "task_id",
    "spec_review",
    "quality_review",
    "real_not_stubbed",
    "tests",
    "demo_artifact",
    "files_changed",
    "reuse_compliance",
    "visual_fidelity_review",
    "test_completeness_review",
    "integration_testing_review",
    "ui_interaction_review",
    # v7 — Verified Agent Output (VAO) framework fields. Each MUST be one of
    # 'pass' / 'n/a' / 'fail' for the legacy *_review fields, OR a dict citing
    # a verdict path for the new tool-mediated fields. See
    # `skills/verified-agent-output/SKILL.md` for the full citation contract.
    "oracle_match_review",
    "baseline_clean_review",
    "no_fake_data_review",
    "adversarial_review",
    "skill_invocation_audit",
}

VALID_VISUAL_FIDELITY_VALUES = {"pass", "n/a", "fail"}
VALID_TEST_COMPLETENESS_VALUES = {"pass", "n/a", "fail"}
VALID_INTEGRATION_TESTING_VALUES = {"pass", "n/a", "fail"}
VALID_UI_INTERACTION_VALUES = {"pass", "n/a", "fail"}
# v7 VAO valid-value sets — same `pass | n/a | fail` shape; failures BLOCK at
# the hook layer the same way `visual_fidelity_review='fail'` does.
VALID_ORACLE_MATCH_VALUES = {"pass", "n/a", "fail"}
VALID_BASELINE_CLEAN_VALUES = {"pass", "n/a", "fail"}
VALID_NO_FAKE_DATA_VALUES = {"pass", "n/a", "fail"}
VALID_ADVERSARIAL_REVIEW_VALUES = {"pass", "n/a", "fail"}
VALID_SKILL_INVOCATION_AUDIT_VALUES = {"pass", "n/a", "fail"}

# v2.1.0 — interactions_honored_review is OPTIONAL (NOT in REQUIRED_EVIDENCE_FIELDS).
# Required only when the run's oracle spec carries a non-empty `interactions[]`
# array (i.e., the v2.1.0 interactive-mockup-discovery framework was engaged).
# n/a in all other cases. v2.0.0 evidence files (which lack the field entirely)
# remain valid — the field's optional-ness is the v2.1.0 backwards-compat guarantee.
VALID_INTERACTIONS_HONORED_VALUES = {"pass", "n/a", "fail"}

# v2.2.0 — live_verification_review is OPTIONAL (NOT in REQUIRED_EVIDENCE_FIELDS).
# Required only when the evidence claims "verified live" (the agent's report
# names a deployed-URL verification); n/a in all other cases. The field cites
# the Layer-3 verify-live-verification-claim verdict path. v2.0.0 and v2.1.0
# evidence files (which lack the field entirely) remain valid — the optional-ness
# is the v2.2.0 backwards-compat guarantee.
VALID_LIVE_VERIFICATION_VALUES = {"pass", "n/a", "fail"}

# v3.14.0 — appearance_scope_review is OPTIONAL (NOT in REQUIRED_EVIDENCE_FIELDS).
# Required only when the slice's diff touches frontend presentation surface
# (styling files, components, templates, routes, assets); n/a otherwise. 'pass'
# means every appearance-affecting delta in the diff traces to one of the three
# sanctioned mandate sources (requirement text / spec restoration /
# mandated-capability minimum), an approved appearance proposal, or — in
# innovate mode — a logged `implemented-innovate` proposals entry, per
# `common-pipeline-conventions` `## Appearance-change policy discipline
# (v3.14.0)`. Pre-v3.14.0 evidence files (which lack the field entirely)
# remain valid — the same optional-ness backwards-compat guarantee as v2.1.0
# and v2.2.0.
VALID_APPEARANCE_SCOPE_VALUES = {"pass", "n/a", "fail"}
OPTIONAL_VAO_FIELDS = (
    "interactions_honored_review",
    "live_verification_review",
    "appearance_scope_review",
)

# v5 (v0.9.13). The `independent_review` block is written by an independent
# `task-reviewer` agent — NOT the teammate. Its sub-fields below are all
# REQUIRED, and `reviewer` MUST NOT equal the top-level `teammate` field: the
# producer cannot be its own checker.
REQUIRED_INDEPENDENT_REVIEW_FIELDS = {
    "reviewer",
    "verdict",
    "spec_review",
    "quality_review",
    "real_not_stubbed",
    "reuse_compliance",
    "reviewed_at",
}


def _detect_trigger_mode(payload: dict[str, Any]) -> str:
    """Return `"teams"` or `"subagents"` based on the hook payload's shape.

    The architect-team hooks attach to TWO trigger shapes:

    - Subagents mode (the v0.9.x dispatch shape): the orchestrator is the main
      session, dispatches each role via the `Agent` tool, and the hook receives
      `PostToolUse(TaskUpdate)` or `SubagentStop` payloads.
    - Teams mode (the v1.0.0 agent-teams shape): the Lead session runs a
      long-lived team of named teammates; the hook receives `TaskCompleted` or
      `TeammateIdle` payloads.

    The two shapes carry different field names (`tool_name` + `tool_input.taskId`
    vs. `task.id`; `subagent.name` vs. `teammate.name`), but the enforcement
    contract — same evidence file at `.architect-team/reviews/<task-id>.json`,
    same v6 validation, same exit-2 block-with-feedback semantics — is identical.

    Heuristic (see `openspec/changes/agent-teams-refactor/specs/agent-teams-mode/spec.md`
    REQ-4 + https://code.claude.com/docs/en/hooks for payload references):

    1. If `hook_event_name` is `TaskCompleted` or `TeammateIdle` → `teams`.
    2. If `tool_name` is `TaskUpdate` AND `hook_event_name` is `PostToolUse` (or
       absent — older harness emissions) → `subagents`.
    3. Unknown payload shapes → fall back to `subagents` (the existing v0.9.x
       behavior is preserved; teams mode is opt-in, so any ambiguous payload
       should NOT silently switch contracts).
    """
    event = payload.get("hook_event_name")
    if event in ("TaskCompleted", "TeammateIdle"):
        return "teams"
    # Subagents mode is the default fallback — every other payload shape (the
    # PostToolUse(TaskUpdate) / SubagentStop pair, OR an unknown harness shape)
    # routes through the existing enforcement path.
    return "subagents"


def safe_id(value: str) -> str | None:
    """Return value if safe for use in a filesystem path component, else None.

    Rejects empty strings, values containing '/' or '\\', values starting with
    '.', and the exact string '..'. These cover every path-traversal vector for
    the controlled identifier sets (task IDs like 'T-1', subagent names like
    'backend-auth') that the hooks handle.
    """
    if not value:
        return None
    if "/" in value or "\\" in value:
        return None
    if value.startswith("."):
        return None
    if value == "..":
        return None
    return value


def validate_evidence(evidence: dict[str, Any]) -> list[str]:
    """Return a list of human-readable gap descriptions for a review-evidence
    dict. An empty list means the evidence is structurally valid.

    This is a STRUCTURAL validator — it confirms the fields are present and
    carry allowed values. It cannot, at hook time, verify the teammate's own
    self-review CLAIMS are true; that is exactly why the v5 schema requires an
    `independent_review` block written by a separate `task-reviewer` agent that
    read the same task's diff — and why this validator enforces
    `independent_review.reviewer != teammate`: the producer cannot be its own
    checker. The deeper end-of-run cross-checks live in
    `pipeline-completion-audit.py`.
    """
    gaps: list[str] = []
    missing = REQUIRED_EVIDENCE_FIELDS - evidence.keys()
    if missing:
        gaps.append(f"missing fields: {sorted(missing)}")
        return gaps

    if evidence.get("spec_review") != "pass":
        gaps.append(f"spec_review={evidence.get('spec_review')!r} (need 'pass')")
    if evidence.get("quality_review") != "pass":
        gaps.append(f"quality_review={evidence.get('quality_review')!r} (need 'pass')")
    if evidence.get("real_not_stubbed") is not True:
        gaps.append("real_not_stubbed must be true")
    if evidence.get("reuse_compliance") != "ok":
        gaps.append(f"reuse_compliance={evidence.get('reuse_compliance')!r} (need 'ok')")

    tests = evidence.get("tests")
    if not isinstance(tests, dict):
        gaps.append("tests must be an object")
    else:
        added = tests.get("added")
        passing = tests.get("passing")
        if not isinstance(added, int) or not isinstance(passing, int):
            gaps.append("tests.added and tests.passing must be integers")
        else:
            if added < 1:
                gaps.append("tests.added must be >= 1")
            if added != passing:
                gaps.append(f"tests.added ({added}) != tests.passing ({passing})")

    demo = evidence.get("demo_artifact")
    if not isinstance(demo, str) or not demo.strip():
        gaps.append("demo_artifact must be a non-empty string")

    files = evidence.get("files_changed")
    if not isinstance(files, list) or not files:
        gaps.append("files_changed must be a non-empty array")

    vfr = evidence.get("visual_fidelity_review")
    # v7 dict-shape: {verdict, verdict_path} citing the verify-rendered-parity
    # verdict file. The cited file is the source of truth for the actual gate
    # decision (pipeline-completion-audit reads it); here we structurally
    # require the verdict_path citation be present.
    if isinstance(vfr, dict):
        v_verdict = vfr.get("verdict")
        if v_verdict not in VALID_VISUAL_FIDELITY_VALUES:
            gaps.append(
                f"visual_fidelity_review.verdict={v_verdict!r} must be one of "
                f"{sorted(VALID_VISUAL_FIDELITY_VALUES)}"
            )
        v_path = vfr.get("verdict_path")
        if not isinstance(v_path, str) or not v_path.strip():
            gaps.append(
                "visual_fidelity_review (dict-shape) requires a non-empty "
                "'verdict_path' citing the verify-rendered-parity verdict JSON"
            )
        if v_verdict == "fail":
            gaps.append(
                "visual_fidelity_review.verdict='fail' — the cited "
                "verify-rendered-parity verdict shows the rendered DOM diverges "
                "from the frozen oracle. Re-engage on the divergences; do not "
                "mark complete."
            )
        vfr = None  # short-circuit the legacy string-shape branch below
    if vfr is None:
        pass
    elif vfr not in VALID_VISUAL_FIDELITY_VALUES:
        gaps.append(
            f"visual_fidelity_review={vfr!r} must be one of "
            f"{sorted(VALID_VISUAL_FIDELITY_VALUES)}"
        )
    elif vfr == "fail":
        gaps.append(
            "visual_fidelity_review='fail' — drift or gaps detected by "
            "visual-fidelity-reconciliation MUST be escalated via handoff to the "
            "architect-team, not marked complete. Re-run reconciliation after the "
            "architect-routed fix lands and only mark complete when verdict is 'pass'."
        )
    elif vfr == "n/a":
        note = evidence.get("visual_fidelity_review_note")
        if not isinstance(note, str) or not note.strip():
            gaps.append(
                "visual_fidelity_review='n/a' requires a non-empty "
                "visual_fidelity_review_note explaining why (no frontend files "
                "touched, OR no DESIGN_MAP.md exists for the codebase)"
            )

    tcr = evidence.get("test_completeness_review")
    if tcr not in VALID_TEST_COMPLETENESS_VALUES:
        gaps.append(
            f"test_completeness_review={tcr!r} must be one of "
            f"{sorted(VALID_TEST_COMPLETENESS_VALUES)}"
        )
    elif tcr == "fail":
        gaps.append(
            "test_completeness_review='fail' — test-kind completeness gaps detected by "
            "the test-completeness-verifier MUST be escalated via the SR auto-spawn "
            "(origin.kind: 'test-completeness-failure'), not marked complete. "
            "The verifier writes the SR automatically; wait for the orchestrator to "
            "re-spawn the fix loop, then re-run the verifier to reach 'pass'."
        )
    elif tcr == "n/a":
        note = evidence.get("test_completeness_review_note")
        if not isinstance(note, str) or not note.strip():
            gaps.append(
                "test_completeness_review='n/a' requires a non-empty "
                "test_completeness_review_note explaining which kind(s) are "
                "inapplicable and why (e.g., backend-only slice with no testable "
                "pure-logic surface for unit tests, OR no frontend touched so "
                "Playwright is n/a)"
            )

    itr = evidence.get("integration_testing_review")
    if itr not in VALID_INTEGRATION_TESTING_VALUES:
        gaps.append(
            f"integration_testing_review={itr!r} must be one of "
            f"{sorted(VALID_INTEGRATION_TESTING_VALUES)}"
        )
    elif itr == "fail":
        gaps.append(
            "integration_testing_review='fail' — this slice's user-flow / "
            "integration tests ran against a MOCKED or FAKE backend (page.route "
            "happy-path stubs, MSW handlers, an in-memory fake API server, or "
            "hardcoded response fixtures) instead of the real running backend. "
            "For any feature spanning both frontend and backend, the tests MUST "
            "exercise the real backend with real data flow front-to-back unless "
            "the requirements explicitly authorize isolated testing. Re-author the "
            "tests against the real backend (or escalate via SR origin.kind "
            "'integration-testing-failure'); do not mark complete."
        )
    elif itr == "n/a":
        note = evidence.get("integration_testing_review_note")
        if not isinstance(note, str) or not note.strip():
            gaps.append(
                "integration_testing_review='n/a' requires a non-empty "
                "integration_testing_review_note giving ONE of the three "
                "legitimate reasons: (1) this slice has no cross-layer surface "
                "(pure static frontend with no backend, OR backend-only slice "
                "with no frontend); (2) Phase 3 per-team gate where the "
                "counterpart layer is not yet integrated and front-to-back "
                "testing is explicitly DEFERRED TO PHASE 5 integration; (3) the "
                "requirements folder explicitly authorizes isolated / mock-backed "
                "testing for this requirement — quote the authorization."
            )

    uir = evidence.get("ui_interaction_review")
    if uir not in VALID_UI_INTERACTION_VALUES:
        gaps.append(
            f"ui_interaction_review={uir!r} must be one of "
            f"{sorted(VALID_UI_INTERACTION_VALUES)}"
        )
    elif uir == "fail":
        gaps.append(
            "ui_interaction_review='fail' — the interaction-completeness review "
            "found an unwired control, an unconfirmed placeholder page, or a "
            "hardcoded value that context shows should be dynamically bound. An "
            "interactive element must be genuinely user-flow-tested or a "
            "user-confirmed stub; a route must reach the real live page, not a "
            "placeholder; a dynamic value must be bound to its data source. Such "
            "a gap MUST be escalated via a solution requirement (origin.kind "
            "'unwired-control' / 'placeholder-page' / 'hardcoded-dynamic-value'), "
            "not marked complete. Re-run the interaction-completeness team after "
            "the routed fix lands and only mark complete when the verdict is 'pass'."
        )
    elif uir == "n/a":
        note = evidence.get("ui_interaction_review_note")
        if not isinstance(note, str) or not note.strip():
            gaps.append(
                "ui_interaction_review='n/a' requires a non-empty "
                "ui_interaction_review_note explaining why (this slice has no "
                "UI/frontend interactive surface — no interactive elements, no "
                "pages / screens / routes — e.g., a backend-only or pure-infra "
                "slice)"
            )

    gaps += _validate_independent_review(evidence)
    gaps += _validate_vao_fields(evidence)

    return gaps


def _validate_vao_field(
    evidence: dict[str, Any],
    field: str,
    valid_values: set[str],
    fail_explanation: str,
    note_field: str | None = None,
) -> list[str]:
    """Common shape-check for the v7 VAO `*_review` / `*_audit` fields.

    Each field is either:
      - A simple string in {'pass', 'n/a', 'fail'} — the legacy review-shape.
      - A dict with at minimum a 'verdict' key (the tool-mediated shape) AND
        a 'verdict_path' citing the on-disk verdict JSON the dict's verdict
        derived from. The dict-shape is the canonical v7 form; the string
        shape is the migration-compatible form for review-evidence files
        whose VAO inputs are tool-mediated upstream and surfaced inline.

    Returns gap descriptions if the shape is wrong, the value is invalid, the
    verdict is 'fail', or the `n/a` value lacks a non-empty explanatory note.
    """
    gaps: list[str] = []
    value = evidence.get(field)

    if isinstance(value, dict):
        verdict = value.get("verdict")
        if verdict not in valid_values:
            gaps.append(
                f"{field}.verdict={verdict!r} must be one of {sorted(valid_values)}"
            )
            return gaps
        verdict_path = value.get("verdict_path")
        if not isinstance(verdict_path, str) or not verdict_path.strip():
            gaps.append(
                f"{field} (dict-shape) requires a non-empty 'verdict_path' "
                f"citing the on-disk verdict JSON the dict's verdict derived from"
            )
        if verdict == "fail":
            gaps.append(f"{field}.verdict='fail' — {fail_explanation}")
        return gaps

    if value not in valid_values:
        gaps.append(f"{field}={value!r} must be one of {sorted(valid_values)}")
        return gaps

    if value == "fail":
        gaps.append(f"{field}='fail' — {fail_explanation}")
    elif value == "n/a" and note_field is not None:
        note = evidence.get(note_field)
        if not isinstance(note, str) or not note.strip():
            gaps.append(
                f"{field}='n/a' requires a non-empty '{note_field}' explaining why"
            )

    return gaps


def _validate_vao_fields(evidence: dict[str, Any]) -> list[str]:
    """Validate the five v7 VAO fields (oracle_match_review,
    baseline_clean_review, no_fake_data_review, adversarial_review,
    skill_invocation_audit). Each fires the same shape-check; only the
    fail-explanation strings differ to give a targeted error in the hook
    output that names which VAO layer is in violation.
    """
    gaps: list[str] = []
    gaps += _validate_vao_field(
        evidence,
        "oracle_match_review",
        VALID_ORACLE_MATCH_VALUES,
        "Layer 3 `verify-oracle-match` found structural divergence from the "
        "frozen oracle spec. The teammate's built tree does not match the "
        "Phase 0.5 oracle. Re-engage on the divergences named in the verdict; "
        "do not mark complete on a 'fail' verdict — the variance is the failure.",
        note_field="oracle_match_review_note",
    )
    gaps += _validate_vao_field(
        evidence,
        "baseline_clean_review",
        VALID_BASELINE_CLEAN_VALUES,
        "Layer 3 `verify-baseline-clean` found a forbidden git operation in "
        "the teammate's tool-call log (one of: `git stash`, `git stash pop`, "
        "`git reset --hard`, `git rebase`, `git commit --amend`, "
        "`git checkout <other-branch>`, `git clean -f`). Per v1.6.0 "
        "teammate-git-discipline these clobber concurrent teammates' work; "
        "do not mark complete — the violations named in the verdict must be "
        "remediated.",
        note_field="baseline_clean_review_note",
    )
    gaps += _validate_vao_field(
        evidence,
        "no_fake_data_review",
        VALID_NO_FAKE_DATA_VALUES,
        "Layer 3 `verify-no-fake-data` found design-literal hits in production "
        "code (one of: oracle-listed dynamic values appearing verbatim, MSW "
        "handlers, page.route fulfill stubs, hardcoded JSON payloads outside "
        "test fixtures). Per v1.7.0 frontend-missing-api-discipline, frontend "
        "must surface a missing-API SR rather than fake the data. Re-engage; "
        "do not mark complete.",
        note_field="no_fake_data_review_note",
    )
    gaps += _validate_vao_field(
        evidence,
        "adversarial_review",
        VALID_ADVERSARIAL_REVIEW_VALUES,
        "Layer 2 adversarial-reviewer found the shape-specific anti-pattern "
        "the teammate's task is prone to. The independent_review verdict "
        "covers correctness; the adversarial_review covers the named "
        "failure-mode the task shape forbids. Both MUST pass for the Phase 3 "
        "gate to open.",
        note_field="adversarial_review_note",
    )
    gaps += _validate_vao_field(
        evidence,
        "skill_invocation_audit",
        VALID_SKILL_INVOCATION_AUDIT_VALUES,
        "Layer 6 `skill_invocation_audit.py` detected an explicit user "
        "Skill-invocation request in the session transcript with no matching "
        "`Skill` tool invocation in the tool-call ledger. The orchestrator "
        "applied the methodology by hand rather than invoke the framework. "
        "Re-invoke the requested Skill in this session before marking complete.",
        note_field="skill_invocation_audit_note",
    )

    # v2.1.0 — interactions_honored_review is OPTIONAL. Validate only when the
    # field is present in the evidence dict. An absent field is NOT a gap
    # (v2.0.0 evidence files lack it; they remain valid). When present, it
    # follows the same string/dict-shape contract as the other v7 fields.
    if "interactions_honored_review" in evidence:
        gaps += _validate_vao_field(
            evidence,
            "interactions_honored_review",
            VALID_INTERACTIONS_HONORED_VALUES,
            "v2.1.0 `verify-interactions-honored` found the built work does "
            "NOT honor the resolved-intent of one or more interactions[] "
            "entries in the frozen oracle spec. The mockup's literal behavior "
            "(or the user-confirmed canonical intent for the mockup-lies "
            "case) is not wired in the built code. Re-engage on the gaps "
            "named in the verdict; do not mark complete.",
            note_field="interactions_honored_review_note",
        )

    # v3.14.0 — appearance_scope_review is OPTIONAL. Validate only when the
    # field is present in the evidence dict. An absent field is NOT a gap
    # (pre-v3.14.0 evidence files lack it; they remain valid). When present,
    # it follows the same string/dict-shape contract as the other v7 fields.
    if "appearance_scope_review" in evidence:
        gaps += _validate_vao_field(
            evidence,
            "appearance_scope_review",
            VALID_APPEARANCE_SCOPE_VALUES,
            "v3.14.0 appearance-change policy violated — the diff contains an "
            "appearance-affecting delta (visual styling, a UI-surface "
            "addition/removal/relocation, displayed copy, or an asset swap) "
            "that traces to NO sanctioned mandate: not named in the "
            "requirement text, not a spec restoration (DESIGN_MAP / design "
            "source / intended rendering), not the minimal UI a mandated "
            "capability requires, not an approved appearance proposal, and "
            "not an innovate-mode `implemented-innovate` log entry. Under "
            "`strict` (the default) and `propose`, unsolicited appearance "
            "changes are forbidden — revert the delta or route it as a "
            "proposal per `common-pipeline-conventions` `## Appearance-change "
            "policy discipline (v3.14.0)`; do not mark complete.",
            note_field="appearance_scope_review_note",
        )

    # v2.2.0 — live_verification_review is OPTIONAL. Validate only when the
    # field is present in the evidence dict. An absent field is NOT a gap
    # (v2.0.0 / v2.1.0 evidence files lack it; they remain valid). When present,
    # it follows the same string/dict-shape contract as the other v7 fields.
    if "live_verification_review" in evidence:
        gaps += _validate_vao_field(
            evidence,
            "live_verification_review",
            VALID_LIVE_VERIFICATION_VALUES,
            "v2.2.0 `verify-live-verification-claim` found the agent's 'verified live' "
            "claim is invalid. One of the 6 named severities fired — gesture-substitution "
            "(empty-region click instead of user gesture), self-verification-loop (agent "
            "wrote a test that asserts its own fix), prefill-masking (pre-populated demo "
            "state where the bug can't manifest), missing-screenshot, missing-deployed-url, "
            "or missing-semantic-assertion. Re-run verification against the live deployed "
            "URL with the literal user gesture, an independent test, the bug-exposable "
            "state, a captured screenshot, and a semantic assertion. Do not mark complete.",
            note_field="live_verification_review_note",
        )

    return gaps


def _validate_independent_review(evidence: dict[str, Any]) -> list[str]:
    """Return gap descriptions for the `independent_review` block.

    The 12 top-level fields are the TEAMMATE's self-review. They are a cheap
    first pass — a teammate can write a perfectly-conformant self-review that
    lies, and shape validation cannot tell. The `independent_review` block is
    the verdict of an independent `task-reviewer` agent that read the same
    task's diff: it is REQUIRED, and its `reviewer` MUST NOT equal the
    top-level `teammate` field, so the Phase 3 gate cannot open on
    self-attestation — the producer cannot be its own checker.
    """
    gaps: list[str] = []
    review = evidence.get("independent_review")
    if review is None:
        gaps.append(
            "missing the required 'independent_review' block — the Phase 3 gate "
            "cannot open on the teammate's self-review alone; an independent "
            "task-reviewer agent must review the task's diff and write this block"
        )
        return gaps
    if not isinstance(review, dict):
        gaps.append("independent_review must be an object")
        return gaps

    missing = REQUIRED_INDEPENDENT_REVIEW_FIELDS - review.keys()
    if missing:
        gaps.append(f"independent_review is missing fields: {sorted(missing)}")
        return gaps

    # The `reviewer != teammate` check below is the headline anti-self-attestation
    # guarantee — but it can only run if the evidence carries a usable `teammate`.
    # `teammate` is NOT in REQUIRED_EVIDENCE_FIELDS, so an evidence file could omit
    # it and silently no-op the check. Because `independent_review` is always
    # required in v5, requiring `teammate` here makes it mandatory by design: the
    # producer-cannot-be-its-own-checker rule has no meaning without it.
    teammate = evidence.get("teammate")
    teammate_ok = isinstance(teammate, str) and bool(teammate.strip())
    if not teammate_ok:
        gaps.append(
            "evidence must carry a non-empty 'teammate' field — the "
            "independent_review.reviewer != teammate check cannot run without it"
        )

    reviewer = review.get("reviewer")
    if not isinstance(reviewer, str) or not reviewer.strip():
        gaps.append("independent_review.reviewer must be a non-empty string")
    elif teammate_ok and reviewer.strip() == teammate.strip():
        gaps.append(
            f"independent_review.reviewer ({reviewer!r}) equals the teammate "
            f"({teammate!r}) — the producer cannot be its own checker; the "
            f"independent review must be written by a different agent"
        )

    if review.get("verdict") != "pass":
        gaps.append(
            f"independent_review.verdict={review.get('verdict')!r} (need 'pass') — "
            f"a non-pass verdict means the task-reviewer found the task incomplete; "
            f"the teammate must re-engage on the reviewer's per-gap notes"
        )

    if review.get("spec_review") != "pass":
        gaps.append(
            f"independent_review.spec_review={review.get('spec_review')!r} (need 'pass')"
        )
    if review.get("quality_review") != "pass":
        gaps.append(
            f"independent_review.quality_review={review.get('quality_review')!r} "
            f"(need 'pass')"
        )
    if review.get("real_not_stubbed") is not True:
        gaps.append("independent_review.real_not_stubbed must be true")
    if review.get("reuse_compliance") != "ok":
        gaps.append(
            f"independent_review.reuse_compliance={review.get('reuse_compliance')!r} "
            f"(need 'ok')"
        )

    reviewed_at = review.get("reviewed_at")
    if not isinstance(reviewed_at, str) or not reviewed_at.strip():
        gaps.append("independent_review.reviewed_at must be a non-empty string")

    return gaps
