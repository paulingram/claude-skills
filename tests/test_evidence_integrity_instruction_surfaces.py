"""Instruction-surface pins for the v3.47.0 evidence-integrity hardening.

The deterministic halves of this change live in hooks/ and scripts/ and carry
their own behavior tests. This file pins the INSTRUCTION halves — the skill and
agent text that tells an agent what evidence is acceptable — the same way
`tests/test_integration_testing_discipline.py` pins the real-backend discipline
across its three surfaces.

Coverage-map entries covered here (structural criteria only):

  R1a — red-first named three sources (team-spawning + verified-agent-output)
  R2  — the persisted-artifacts enforcement boundary (delivery-manifest)
  R5  — the reading-teammate-state protocol (team-spawning)
  R6  — the mid-run spec-currency discipline (conventions + team-spawning)
  R7  — API read-back (dev-api-integration-testing + test-completeness-verifier)
  R8  — flow fixture hygiene (playwright-user-flows + test-completeness-verifier)
  R9  — the declared-gates discipline (conventions)
  MANDATE-vao-inventory — the 21st tool row + the check_integrity_review contract

Assertions are phrase-level, not byte-level: they pin the load-bearing content
(what an agent must do) and leave the surrounding prose free to be rewritten.
"""
from __future__ import annotations

from pathlib import Path

import pytest


DEV_API_SKILL = ("skills", "dev-api-integration-testing", "SKILL.md")
PLAYWRIGHT_SKILL = ("skills", "playwright-user-flows", "SKILL.md")
TEAM_SPAWNING_SKILL = ("skills", "team-spawning-and-review-gates", "SKILL.md")
VAO_SKILL = ("skills", "verified-agent-output", "SKILL.md")
CONVENTIONS_SKILL = ("skills", "common-pipeline-conventions", "SKILL.md")
DELIVERY_SKILL = ("skills", "delivery-manifest", "SKILL.md")
VERIFIER_AGENT = ("agents", "test-completeness-verifier.md")
TASK_REVIEWER_AGENT = ("agents", "task-reviewer.md")


def _read(plugin_root: Path, parts) -> str:
    return (plugin_root.joinpath(*parts)).read_text(encoding="utf-8")


def _section(text: str, heading: str) -> str:
    """The '## '/'### ' section body for `heading`, up to the next same-or-higher heading."""
    lines = text.split("\n")
    start = next((i for i, ln in enumerate(lines) if ln.rstrip() == heading), None)
    assert start is not None, f"missing section heading: {heading!r}"
    depth = len(heading) - len(heading.lstrip("#"))
    end = len(lines)
    for i in range(start + 1, len(lines)):
        stripped = lines[i].lstrip("#")
        this_depth = len(lines[i]) - len(stripped)
        if lines[i].startswith("#") and stripped.startswith(" ") and this_depth <= depth:
            end = i
            break
    return "\n".join(lines[start:end])


# --- R7: API read-back discipline ---------------------------------------------


def test_dev_api_assertion_layers_require_api_readback(plugin_root: Path) -> None:
    """The assertion phase orders write-echo -> API read-back -> DB -> audit."""
    body = _read(plugin_root, DEV_API_SKILL)
    section = _section(body, "### Assertion phase")
    low = section.lower()
    assert "read-back" in low, "assertion layers do not name an API read-back layer"
    assert "get-after-put" in low or "get after put" in low, (
        "update endpoints must require the GET-after-PUT leg of the read-back chain"
    )
    for leg in ("POST-echo", "PUT-echo"):
        assert leg.lower() in low, f"read-back chain missing the {leg} leg"
    # ordering: read-back precedes the DB/side-effect layer
    readback_at = low.index("read-back")
    sidefx_at = low.index("side-effect verification")
    assert readback_at < sidefx_at, (
        "API read-back must be ordered BEFORE side-effect verification "
        "(the reordered layers are the point of the change)"
    )


def test_dev_api_demotes_db_layer_to_necessary_not_sufficient(plugin_root: Path) -> None:
    body = _read(plugin_root, DEV_API_SKILL)
    section = _section(body, "### Assertion phase").lower()
    assert "necessary" in section and "not sufficient" in section, (
        "the DB/side-effect layer is not marked necessary-and-not-sufficient"
    )
    assert "blank field" in section, (
        "the DB layer demotion must carry the user-facing consequence "
        "('a row the API never returns is a blank field to the user')"
    )


def test_dev_api_rationalization_table_rebuts_db_row_as_proof(plugin_root: Path) -> None:
    body = _read(plugin_root, DEV_API_SKILL)
    assert "The DB row proves it persisted" in body, (
        "missing the 'The DB row proves it persisted' rationalization row"
    )
    assert "Persisted is not retrievable" in body, (
        "missing the rebuttal 'Persisted is not retrievable. The user reads through the API; assert there.'"
    )


def test_dev_api_existing_side_effect_row_points_at_the_api_too(plugin_root: Path) -> None:
    """The pre-existing 'the 200 is enough' row must not still name the DB row as
    the destination — the two rows would then contradict each other."""
    body = _read(plugin_root, DEV_API_SKILL)
    row = next(
        (ln for ln in body.split("\n") if "the 200 is enough" in ln),
        None,
    )
    assert row is not None, "the 'skip side-effect verification' rationalization row disappeared"
    assert "read" in row.lower() and "api" in row.lower(), (
        "the side-effect row still points only at the DB row; it must also send the "
        f"author to the API read-back: {row!r}"
    )


def test_verifier_has_readback_audit_step(plugin_root: Path) -> None:
    body = _read(plugin_root, VERIFIER_AGENT)
    assert "readback_audit" in body, "verifier has no readback_audit finding"
    assert '"db_only"' in body or "`db_only`" in body or "db_only" in body, (
        "verifier does not define the db_only readback verdict"
    )
    low = body.lower()
    assert "post/put/patch" in low or "post / put / patch" in low, (
        "the readback audit must name the state-changing verbs it keys on"
    )
    assert "session.get" in low or "orm query" in low, (
        "the readback audit must name the direct-DB assertion shapes it detects"
    )


def test_verifier_verdict_schema_version_bumped_for_new_fields(plugin_root: Path) -> None:
    body = _read(plugin_root, VERIFIER_AGENT)
    assert '"schema_version": 4' in body, (
        "the verdict JSON schema_version must bump additively for readback_audit + "
        "fixture_hygiene_findings"
    )


# --- R8: flow fixture hygiene --------------------------------------------------


def test_playwright_skill_has_shared_state_hygiene_section(plugin_root: Path) -> None:
    body = _read(plugin_root, PLAYWRIGHT_SKILL)
    heading = "### Shared-state hygiene (flows against the shared dev environment)"
    assert heading in body, f"playwright-user-flows is missing {heading!r}"
    section = _section(body, heading).lower()
    assert "unique" in section, "shared-state hygiene must require per-test unique values"
    assert "teardown" in section or "restore" in section, (
        "shared-state hygiene must offer teardown/restore as the alternative to unique values"
    )
    assert "twice in a row" in section, "shared-state hygiene must require runnable-twice"
    assert "never assert" in section and "wrote" in section, (
        "shared-state hygiene must forbid asserting a hardcoded literal the test itself wrote"
    )


def test_playwright_rationalization_table_rebuts_the_field_held_the_value(plugin_root: Path) -> None:
    body = _read(plugin_root, PLAYWRIGHT_SKILL)
    assert "the field held the value, so Edit works" in body, (
        "missing the 'the field held the value, so Edit works' rationalization row"
    )
    assert "previous run" in body and "nothing was dirty" in body, (
        "missing the rebuttal naming the previous run's residue and the request that never fired"
    )


def test_verifier_has_fixture_hygiene_step(plugin_root: Path) -> None:
    body = _read(plugin_root, VERIFIER_AGENT)
    assert "Step 3g" in body, "verifier is missing the Step 3g fixture-hygiene audit"
    assert "fixture_hygiene_findings" in body, (
        "verifier does not record fixture_hygiene_findings[] in the verdict"
    )
    section = _section(body, next(
        ln for ln in body.split("\n") if ln.startswith("### Step 3g")
    ))
    low = section.lower()
    assert "fill(" in low, "the fixture-hygiene audit must key on fill(<literal>)"
    assert "same literal" in low, (
        "the fixture-hygiene audit must flag a fill paired with an assertion of the SAME literal"
    )
    assert "afterEach".lower() in low or "teardown" in low, (
        "the fixture-hygiene audit must accept a teardown/cleanup signal"
    )
    assert "playwright" in low and "fail" in low, (
        "a fixture-hygiene finding must set the playwright kind to fail"
    )


# --- R1a: red-first, three named sources --------------------------------------


def test_team_spawning_names_the_three_red_sources(plugin_root: Path) -> None:
    body = _read(plugin_root, TEAM_SPAWNING_SKILL)
    low = body.lower()
    assert "red-first" in low, "team-spawning has no red-first section"
    assert "tdd" in low and "before the implementation" in low, (
        "red source (a) — the TDD red run captured before the implementation exists — is missing"
    )
    assert "baseline_sha" in body and "pre-change" in low, (
        "red source (b) — a run against the pre-change checkout (baseline SHA) — is missing"
    )
    assert "inversion" in low or "mutation" in low, (
        "red source (c) — a deliberate assertion-inversion or mutation run — is missing"
    )
    assert "captured" in low and "evidence" in low, (
        "the captured failure output must be cited into the review evidence"
    )


def test_vao_skill_cross_references_red_first(plugin_root: Path) -> None:
    body = _read(plugin_root, VAO_SKILL).lower()
    assert "red-first" in body, "verified-agent-output does not carry the red-first rule"
    assert "team-spawning-and-review-gates" in body, (
        "the VAO red-first text must cross-reference the team-spawning red-first section"
    )


def test_task_reviewer_must_capture_and_read_check_output(plugin_root: Path) -> None:
    body = _read(plugin_root, TASK_REVIEWER_AGENT)
    assert "did not capture and read" in body, (
        "task-reviewer is missing the capture-and-scan rule "
        "('no quality_review: pass on a suite run whose output you did not capture and read')"
    )
    low = body.lower()
    assert "zero-work" in low, (
        "task-reviewer must scan captured output for the zero-work signatures "
        "(collected 0 items / no tests found / No test files found)"
    )
    assert "collected 0 items" in body, (
        "task-reviewer must name at least the pytest zero-work signature verbatim"
    )


def test_verifier_must_capture_and_read_check_output(plugin_root: Path) -> None:
    body = _read(plugin_root, VERIFIER_AGENT)
    low = body.lower()
    assert "exit code" in low and "capture" in low, (
        "test-completeness-verifier must instruct capturing output rather than trusting exit codes"
    )
    assert "collected 0 items" in body, (
        "test-completeness-verifier must name the pytest zero-work signature verbatim"
    )


# --- MANDATE-vao-inventory: the 21st tool + the optional field ----------------


def test_vao_skill_lists_verify_check_can_fail(plugin_root: Path) -> None:
    body = _read(plugin_root, VAO_SKILL)
    assert "verify-check-can-fail" in body, "the VAO skill does not list the 21st Layer-3 tool"
    assert "hooks/vao/check_integrity.py" in body, (
        "the 21st tool row must name its module"
    )
    for severity in ("vacuous-check", "new-guard-never-shown-red", "red-run-not-red"):
        assert severity in body, f"the 21st tool row is missing the {severity!r} severity"


def test_vao_skill_documents_check_integrity_review_field(plugin_root: Path) -> None:
    body = _read(plugin_root, VAO_SKILL)
    assert "check_integrity_review" in body, (
        "the VAO citation contract does not document check_integrity_review"
    )
    low = body.lower()
    assert "optional" in low, "check_integrity_review must be documented as OPTIONAL"
    assert "validated when present" in low or "validated-when-present" in low, (
        "check_integrity_review must carry the validated-when-present semantics"
    )
    # the blocking-on-fail semantics + the citation target
    idx = body.index("check_integrity_review")
    window = body[idx: idx + 1400].lower()
    assert "fail" in window and "block" in window, (
        "check_integrity_review's blocking-on-fail semantics are not documented beside it"
    )
    assert "verdict" in window, (
        "check_integrity_review must cite the verify-check-can-fail verdict path"
    )


# --- R5: reading teammate state ------------------------------------------------


def test_team_spawning_documents_reading_teammate_state(plugin_root: Path) -> None:
    body = _read(plugin_root, TEAM_SPAWNING_SKILL)
    assert "## Reading teammate state" in body, (
        "team-spawning is missing the '## Reading teammate state' protocol"
    )
    section = _section(body, next(
        ln for ln in body.split("\n") if ln.startswith("## Reading teammate state")
    ))
    low = section.lower()
    assert "reported" in low and "idle" in low and "in-flight" in low, (
        "the protocol must name all three knowable states (reported / idle-event / in-flight)"
    )
    assert "stalled" in low, "the protocol must govern 'stalled' characterizations"
    assert "supports no conclusion" in low, (
        "state (c) in-flight must be documented as supporting no conclusion"
    )
    assert "mid-edit" in low, (
        "the mid-edit-read corollary (a shared-tree suite run during an in-flight teammate) is missing"
    )
    assert "unattributable" in low, (
        "the corollary must state that red is unattributable until the owner reports"
    )


# --- R6: mid-run spec currency -------------------------------------------------


def test_team_spawning_manifest_carries_spec_fingerprint(plugin_root: Path) -> None:
    body = _read(plugin_root, TEAM_SPAWNING_SKILL)
    assert "spec_fingerprint" in body, (
        "the teammate manifest schema does not document the additive spec_fingerprint field"
    )
    assert "baseline_sha" in body
    low = body.lower()
    assert "additive" in low or "pre-upgrade" in low, (
        "spec_fingerprint must be documented as an additive field (pre-upgrade manifests stay valid)"
    )


def test_team_spawning_sr_catalog_carries_spec_drift(plugin_root: Path) -> None:
    body = _read(plugin_root, TEAM_SPAWNING_SKILL)
    enum_line = next(
        (ln for ln in body.split("\n") if '"kind": "playwright-failure"' in ln), None
    )
    assert enum_line is not None, "the SR origin enum line disappeared"
    assert '"spec-drift"' in enum_line, "spec-drift is not in the canonical SR origin enum"
    assert "spec-drift" in body
    idx = body.index("`spec-drift`") if "`spec-drift`" in body else body.index("spec-drift")
    window = body[idx: idx + 900]
    assert "DIRECTLY" in window or "directly" in window, (
        "spec-drift must be documented as direct-dispatch (no diagnostic-research routing)"
    )
    assert "TEST_FAILURE_ORIGINS" in body, (
        "the catalog must state explicitly that spec-drift is NOT a TEST_FAILURE_ORIGINS member"
    )


def test_conventions_has_spec_currency_discipline(plugin_root: Path) -> None:
    body = _read(plugin_root, CONVENTIONS_SKILL)
    heading = next(
        (ln for ln in body.split("\n")
         if ln.startswith("## Spec currency discipline")), None
    )
    assert heading is not None, (
        "common-pipeline-conventions is missing the '## Spec currency discipline (mid-run)' section"
    )
    section = _section(body, heading)
    low = section.lower()
    assert "orchestrator owns" in low, (
        "the discipline must state that the orchestrator owns spec currency while agents read it"
    )
    assert "re-brief" in low, "the re-brief obligation is missing"
    assert "handoff" in low, "the re-brief record must be a handoff file"
    assert "the code wins" in low, "the code-wins-spec-amended rule is missing"
    assert "misread" in low, (
        "the discipline must forbid the 'the readers misread' resolution"
    )
    assert "phase 2" in low, "the discipline must key the obligation to post-Phase-2 dispatch"


def test_team_spawning_references_the_spec_currency_discipline(plugin_root: Path) -> None:
    body = _read(plugin_root, TEAM_SPAWNING_SKILL)
    assert "Spec currency discipline" in body, (
        "team-spawning must cross-reference the conventions spec-currency discipline"
    )


# --- R9: declared gates --------------------------------------------------------


def test_conventions_has_declared_gates_discipline(plugin_root: Path) -> None:
    body = _read(plugin_root, CONVENTIONS_SKILL)
    heading = next(
        (ln for ln in body.split("\n") if ln.startswith("## Declared-gates discipline")), None
    )
    assert heading is not None, (
        "common-pipeline-conventions is missing the '## Declared-gates discipline' section"
    )
    section = _section(body, heading)
    assert ".architect-team/declared-gates.json" in section, (
        "the discipline must name the registry path"
    )
    for field in ("gate_id", "declaration_text", "check_command_or_artifact",
                  "declared_at", "satisfied_at", "evidence_path"):
        assert field in section, f"the registry shape is missing {field!r}"
    low = section.lower()
    assert "a gate you name is a gate you record" in low, (
        "the discipline's headline rule is missing"
    )
    assert "fail-open" in low and "absent" in low, (
        "the absent-registry fail-open must be documented"
    )
    assert "block" in low, "the audit's blocking behavior on an unsatisfied gate is missing"


SHIP_STEP_PIPELINES = {
    # skill dir -> the ship verb its close-out step uses
    "architect-team-pipeline": ("commit", "push"),
    "bug-fix-pipeline": ("commit", "push"),
    "mini-architect-team-pipeline": ("merge", "commit"),
    "ux-test-builder": ("commit", "push"),
}


@pytest.mark.parametrize("skill", sorted(SHIP_STEP_PIPELINES))
def test_pipeline_body_checks_declared_gates_before_ship(plugin_root: Path, skill: str) -> None:
    """Each pipeline's ship-adjacent phase text requires the declared-gates registry
    to be satisfied before the commit / merge proceeds, referencing the canonical
    section rather than re-explaining the rule."""
    body = (plugin_root / "skills" / skill / "SKILL.md").read_text(encoding="utf-8")
    assert "declared-gates.json" in body, (
        f"{skill}: ship text does not name the declared-gates registry"
    )
    assert "Declared-gates discipline" in body, (
        f"{skill}: ship text must cross-reference the canonical "
        "`## Declared-gates discipline` section in common-pipeline-conventions "
        "rather than re-explaining the rule"
    )
    # Scan EVERY mention, not just the first. A pipeline may legitimately name the
    # registry more than once — v3.48.0's contract-first parallelism DECLARES a
    # retirement gate at provisioning time, which is the registry's own rule ("a
    # gate you name is a gate you record") and necessarily precedes the ship step.
    # The property under test is that SOME mention is the ship-adjacent one; that
    # the earliest happens to be is a formatting accident, not the requirement.
    verbs = SHIP_STEP_PIPELINES[skill]
    windows = []
    start = 0
    while (idx := body.find("declared-gates.json", start)) != -1:
        windows.append(body[max(0, idx - 1500): idx + 1500].lower())
        start = idx + 1
    assert any(any(v in w for v in verbs) for w in windows), (
        f"{skill}: no declared-gates reference sits in the ship-adjacent text "
        f"(expected one of {verbs} within 1500 chars of a mention)"
    )
    assert any(any(v in w for v in verbs) and "satisf" in w for w in windows), (
        f"{skill}: the ship text must require the registry to be SATISFIED, not merely mention it"
    )


@pytest.mark.parametrize("skill", sorted(SHIP_STEP_PIPELINES))
def test_pipeline_body_declared_gates_text_is_outside_the_compiled_fence(
    plugin_root: Path, skill: str
) -> None:
    """The ship reference is hand-authored body text — it must NOT sit inside a
    ct6:block fence, whose interior belongs to the compilers."""
    lines = (plugin_root / "skills" / skill / "SKILL.md").read_text(encoding="utf-8").split("\n")
    inside = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("<!-- ct6:block:") and stripped.endswith(":begin -->"):
            inside = True
        elif stripped.startswith("<!-- ct6:block:") and stripped.endswith(":end -->"):
            inside = False
        elif inside:
            assert "declared-gates" not in line, (
                f"{skill}: declared-gates text found INSIDE a ct6:block fence — "
                "the fence interior is compiler-owned and would be overwritten"
            )


# --- R2: the delivery-manifest citation bar + honest boundary ------------------


def test_delivery_manifest_documents_the_citation_bar(plugin_root: Path) -> None:
    body = _read(plugin_root, DELIVERY_SKILL)
    low = body.lower()
    assert "cite" in low, "the delivery manifest does not carry a citation bar"
    assert "validation step" in low and "element" in low, (
        "the citation bar must cover validation steps AND delivered elements"
    )
    assert "block" in low, "the citation bar must be documented as blocking (error severity)"


def test_delivery_manifest_states_the_enforcement_boundary(plugin_root: Path) -> None:
    body = _read(plugin_root, DELIVERY_SKILL)
    section = _section(body, "## Honest boundary").lower()
    assert "persisted" in section, (
        "the honest boundary must say enforcement binds persisted artifacts"
    )
    assert "chat" in section or "conversation" in section, (
        "the honest boundary must say mid-run chat is instruction-governed only"
    )
    assert "claims as claims" in section and "verdicts as facts" in section, (
        "the relay rule must be stated at the delivery surface"
    )


# --- claim-accuracy pins (adversarial batch B1/B3/B4/B5 + queue) --------------
# Each of these pins a sentence that ASSERTS SOMETHING ABOUT CODE. They exist
# because the adversarial pass found newly-written prose that overstated what the
# engines enforce; a text-vs-code claim needs a pin the same way a behavior does.


def test_delivery_manifest_claim_row_attributes_enforcement_correctly(plugin_root: Path) -> None:
    """B1 — the citation bar must not attribute deploy/absence enforcement to the
    delivery-manifest engine. `validate` scans validation_steps[].expected and
    elements[]; deploy and absence claims are enforced by the deferral tool over
    the FINAL REPORT. The section must name the right tool for each artifact."""
    body = _read(plugin_root, DELIVERY_SKILL)
    section = _section(body, "## The citation bar (every claim names its evidence)")
    low = section.lower()
    assert "final report" in low, (
        "the claim bar must name the FINAL REPORT as the artifact the deploy/absence "
        "severities are enforced over"
    )
    assert "deferral_b.py" in section, (
        "the claim bar must name the module that ACTUALLY carries the deploy/absence "
        "detectors (hooks/vao/deferral_b.py), not its sibling"
    )
    # the engine's true scope must be stated, not overstated
    assert "validation step" in low and "element" in low, (
        "the claim bar must state what `validate` itself covers (steps + elements)"
    )
    # the false attribution must be gone
    bad = "a completion, deploy, or absence claim with no citation blocks publishing"
    assert bad not in low, (
        "the claim bar still attributes deploy+absence blocking to the manifest engine; "
        "`validate` scans neither deploy_notes nor any absence pattern"
    )


def test_vao_locator_line_does_not_overstate_the_invocation_table(plugin_root: Path) -> None:
    """B3 — the Layer-3 locator must not claim the conventions invocation table
    specifies the other fifteen tools; it names four."""
    body = _read(plugin_root, VAO_SKILL)
    section = _section(body, "### Layer 3 — Tool-mediated execution proof (`hooks/vao_tools.py`)")
    low = section.lower()
    assert "hooks/vao_tools.py" in section, (
        "the locator must point the COMPLETE tool inventory at the facade"
    )
    bad = "the other fifteen are specified at their own discipline's canonical home in `common-pipeline-conventions` and invoked per that skill's `## layer 3 gate invocation table (v3.10.0)`"
    assert bad not in low, (
        "the locator still routes all fifteen remaining tools through the invocation "
        "table, which names only four"
    )
    assert "four" in low, (
        "the corrected locator should say how many tools the invocation table actually names"
    )


@pytest.mark.parametrize("tool", ["verify-affordance-coverage", "verify-per-persona-path-coverage"])
def test_vao_skill_documents_the_otherwise_undocumented_tools(plugin_root: Path, tool: str) -> None:
    """B3 — these two CLI names appeared in no skill at all. The VAO skill is the
    tool inventory's home, so it carries their one-line rows."""
    body = _read(plugin_root, VAO_SKILL)
    assert tool in body, f"{tool} is documented in no skill; the VAO tool table must carry it"


STALE_ORDINAL_SURFACES = [
    "skills/architect-team-pipeline/SKILL.md",
    "skills/bug-fix-pipeline/SKILL.md",
    "skills/mini-architect-team-pipeline/SKILL.md",
    "skills/common-pipeline-conventions/SKILL.md",
]


@pytest.mark.parametrize("rel", STALE_ORDINAL_SURFACES)
def test_unilateral_override_carries_no_stale_ordinal(plugin_root: Path, rel: str) -> None:
    """B4 — two tools cannot both be 'the 21st Layer 3 tool'. verify-check-can-fail
    genuinely is the 21st; the unilateral-override sites must name their tool
    without an ordinal."""
    text = (plugin_root / rel).read_text(encoding="utf-8")
    offenders = []
    for i, line in enumerate(text.split("\n"), 1):
        low = line.lower()
        if "unilateral" not in low:
            continue
        if "21st" in low or "21th" in low:
            offenders.append((i, line.strip()[:120]))
    assert not offenders, (
        f"{rel}: stale '21st' ordinal on the unilateral-override tool "
        f"(verify-check-can-fail is the real 21st): {offenders}"
    )


def test_dev_api_expectation_file_enumeration_includes_readback(plugin_root: Path) -> None:
    """B5 — the expectation-file inventory is written BEFORE the test runs and
    decides what the test asserts. It claims completeness ('all of which are
    mandated above'), so omitting the read-back leg reintroduces the R7 gap."""
    body = _read(plugin_root, DEV_API_SKILL)
    section = _section(body, "## Per-test expectations & failure handling")
    low = section.lower()
    assert "read-back" in low, (
        "the expectation-file enumeration omits the API read-back assertions — an author "
        "working from this line records no read-back expectation"
    )


def test_conventions_declared_gates_requires_explicit_gate_id_citation(plugin_root: Path) -> None:
    """Queue B-8 — ship-gating prose should cite the gate_id, and the matching
    boundary should be stated rather than implied."""
    body = _read(plugin_root, CONVENTIONS_SKILL)
    heading = next(ln for ln in body.split("\n") if ln.startswith("## Declared-gates discipline"))
    section = _section(body, heading).lower()
    assert "gate_id" in section
    assert "cite" in section or "citing" in section, (
        "the discipline must direct ship-gating prose to cite the gate_id explicitly"
    )
    assert "overlap" in section or "boundary" in section, (
        "the token-overlap matching limitation must be stated as a boundary, not implied"
    )


def test_vao_verdict_example_matches_the_tools_actual_output(plugin_root: Path) -> None:
    """Queue G4 — the documented verdict example omitted the `notes` key the tool
    ALWAYS emits, and the input contract omitted the optional per-check
    `tsconfig_path`."""
    # Bound by the real section, not a fixed-size window: the window version
    # broke when the section grew, which is a pin that reports on its own
    # arithmetic rather than on the text.
    section = _tool_section(plugin_root)
    assert '"notes"' in section, (
        "the verdict example omits the `notes` key the tool always emits"
    )
    assert "tsconfig_path" in section, (
        "the input contract omits the optional per-check `tsconfig_path`"
    )


def test_spec_currency_cross_references_cite_the_full_heading(plugin_root: Path) -> None:
    """Adversary note N2 — the same slice used two citation conventions for the
    same kind of target. Cite the heading as written."""
    conventions = _read(plugin_root, CONVENTIONS_SKILL)
    heading = next(
        ln.strip() for ln in conventions.split("\n")
        if ln.startswith("## Spec currency discipline")
    )
    cited = heading[3:]  # drop the '## '
    for parts in (TEAM_SPAWNING_SKILL, CONVENTIONS_SKILL):
        text = _read(plugin_root, parts)
        for line in text.split("\n"):
            if "Spec currency discipline" not in line or line.startswith("## "):
                continue
            assert cited in line, (
                f"{parts[-2] if len(parts) > 2 else parts[-1]}: cites the spec-currency "
                f"section without its full heading (expected {cited!r}): {line.strip()[:150]!r}"
            )


# --- text-vs-code currency pins (the 16-item reconciliation delta) ------------
# The tool kept evolving after the review closed. These pin the description
# against identifiers that EXIST in hooks/vao/check_integrity.py, so the next
# behavior change breaks a test rather than silently staling the prose.


def _tool_section(plugin_root: Path) -> str:
    body = _read(plugin_root, VAO_SKILL)
    start = body.index("#### `verify-check-can-fail` (the 21st tool")
    end = body.index("#### Two tools whose only prose home is this table")
    return body[start:end]


@pytest.mark.parametrize("identifier", [
    "reporting_region", "_RUNNER_OUTPUT_SHAPES", "_decode_output_bytes",
    "_assess_red_output", "_terminal_verdict", "signature_registry",
])
def test_documented_identifier_exists_in_the_module(plugin_root: Path, identifier: str) -> None:
    """Every code identifier the skill names must be real — the B3 failure mode
    was prose citing a locator that did not exist."""
    src = (plugin_root / "hooks" / "vao" / "check_integrity.py").read_text(encoding="utf-8")
    assert identifier in src, f"skill names {identifier!r} but the module does not define it"


@pytest.mark.parametrize("reason", [
    "output-missing", "no-failure-signature", "excerpt-not-in-output",
    "output-does-not-reference-test", "excerpt-required-when-indeterminate",
    "shared-anonymous-red",
])
def test_documented_reason_code_is_emitted_by_the_module(plugin_root: Path, reason: str) -> None:
    """Each documented red-run-not-red reason code must be one the code emits."""
    section = _tool_section(plugin_root)
    src = (plugin_root / "hooks" / "vao" / "check_integrity.py").read_text(encoding="utf-8")
    assert reason in section, f"the skill does not document the {reason!r} reason code"
    assert f'"{reason}"' in src, f"{reason!r} is documented but not emitted by the module"


def test_tool_section_documents_the_reporting_partition(plugin_root: Path) -> None:
    """O1 — the region gate is the load-bearing class fix; describing only the
    patterns leaves a reader thinking a printed string can forge a verdict."""
    low = _tool_section(plugin_root).lower()
    assert "reporting" in low, "the REPORTING-vs-relayed partition is undocumented"
    assert "relayed" in low or "echoed" in low, (
        "the text must say WHAT is excluded from the region, not just that a region exists"
    )


def test_tool_section_documents_terminal_verdict_modes(plugin_root: Path) -> None:
    """O2/O3/O4 — the three resolution modes, including the refusal."""
    low = _tool_section(plugin_root).lower()
    assert "ambiguous-multi-run-capture" in low, "the multi-run refusal is undocumented"
    assert "verdict-absent-framed-sections-only" in low, "the degraded-basis abstain is undocumented"
    assert "refused" in low, "a capture holding more than one run is REFUSED, not resolved"


def test_tool_section_corrects_the_shared_red_rule(plugin_root: Path) -> None:
    """M2 — 'one red output cannot vouch for five new guards' is false as
    shipped: it can, when the output NAMES them. Executed both directions."""
    section = _tool_section(plugin_root)
    low = section.lower()
    assert "one red output cannot vouch for five new guards" not in low, (
        "the stale absolute survives; sharing IS accepted when the output names the guards"
    )
    assert "names" in low and "shared-anonymous-red" in low, (
        "the corrected rule must say sharing is accepted when named and refused when anonymous"
    )


def test_tool_section_names_the_real_artifact_keys(plugin_root: Path) -> None:
    """M6/O9 — the top-level key is `red_runs` (a dict), and repo_root decides
    how every relative cited path resolves."""
    section = _tool_section(plugin_root)
    assert "`red_runs`" in section, "the artifact's real top-level key is never named"
    assert "repo_root" in section, "repo_root is undocumented though every cited path resolves against it"


def test_tool_section_states_the_module_boundaries(plugin_root: Path) -> None:
    """O6 — the module records three boundaries deliberately; the skill must not
    present the tool as deciding more than it does."""
    low = _tool_section(plugin_root).lower()
    assert "boundar" in low, "the skill documents no boundary though the code records three"
    for token in ("basename", "encoding"):
        assert token in low, f"boundary set incomplete — {token} boundary missing"


def test_verdict_example_uses_real_note_keys(plugin_root: Path) -> None:
    """M3 — the example used a `detail` key that does not exist."""
    section = _tool_section(plugin_root)
    assert '"detail"' not in section, "the notes example still uses the non-existent `detail` key"
    src = (plugin_root / "hooks" / "vao" / "check_integrity.py").read_text(encoding="utf-8")
    for key in ("kind", "command", "evidence", "remediation"):
        assert f'"{key}"' in src, f"documented note key {key!r} is not emitted"


def test_verdict_example_shows_the_reasons_array(plugin_root: Path) -> None:
    """M4 — reasons[] is the field a consumer keys on; it was absent from the
    documented shape."""
    section = _tool_section(plugin_root)
    assert '"reasons"' in section, (
        "the gaps[] example never shows reasons[], the field distinguishing the six modes"
    )


def test_vao_package_docstring_is_current(plugin_root: Path) -> None:
    """F1 — the package docstring counted 20 tools and listed no modules."""
    doc = (plugin_root / "hooks" / "vao" / "__init__.py").read_text(encoding="utf-8")
    assert "21 ``verify_*`` tools" not in doc, "package docstring still says 21 tools"
    assert "22 ``verify_*`` tools" in doc
    for mod in ("check_integrity", "deferral_b", "mention_context", "frontend_e2e"):
        assert mod in doc, f"package docstring omits the {mod} module"
    for helper in ("_ITEM_DISPOSITION_CITATIONS", "_boundary_pattern"):
        assert helper in doc, f"package docstring omits the relocated helper {helper}"
    # the count must match the package
    import re as _re
    names = set()
    for p in (plugin_root / "hooks" / "vao").glob("*.py"):
        names |= set(_re.findall(r"^def (verify_[a-z_]+)", p.read_text(encoding="utf-8"), _re.M))
    assert len(names) == 22, f"package defines {len(names)} verify_* tools, docstring says 22"


def test_conventions_documents_verdict_hygiene(plugin_root: Path) -> None:
    """Every verdict in the directory must pass — there is no latest-wins, so a
    re-run must overwrite or delete the verdict it supersedes."""
    body = _read(plugin_root, CONVENTIONS_SKILL)
    section = _section(body, "### Verdict hygiene — a superseded verdict still counts (v3.47.0)")
    low = section.lower()
    assert "every" in low and "pass" in low
    assert "--out" in section, "the remediation must name the --out path reuse"
    assert "delete" in low, "deleting the superseded verdict must be offered as the alternative"
    assert "latest-wins" in low or "latest wins" in low, (
        "the absence of latest-wins is the reason the rule exists — say it"
    )


# --- the two agents keep their frontmatter clean ------------------------------


@pytest.mark.parametrize("parts", [VERIFIER_AGENT, TASK_REVIEWER_AGENT])
def test_edited_agents_keep_parseable_frontmatter(plugin_root: Path, parts) -> None:
    """House YAML hazards: an unquoted ': ' or ' #' in a description breaks the
    loader. The edits here touch bodies, not frontmatter — this is the guard."""
    text = _read(plugin_root, parts)
    assert text.startswith("---\n")
    fm = text.split("---", 2)[1]
    for line in fm.split("\n"):
        if not line.strip() or ":" not in line:
            continue
        key, _, value = line.partition(":")
        value = value.strip()
        if value.startswith(('"', "'")):
            continue
        assert ": " not in value, f"{parts[-1]}: unquoted '{key}' value carries a ': ' YAML hazard"
        assert " #" not in value, f"{parts[-1]}: unquoted '{key}' value carries a ' #' YAML hazard"
