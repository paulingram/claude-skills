"""Wiring pins for the thin hooks that bind the existing lanes to the new
`intuition-map-lifecycle` verbs and the target codebase's suite manifest
(tasks 3.1-3.7 of the `playwright-suite-intuition-lifecycle` change).

Each hook is a short named paragraph at ONE named location in an EXISTING
surface. The pins here assert the text at that location — sliced to the named
phase / step section, so a pin cannot pass because the phrase happens to appear
somewhere else in a 900-line orchestrator (the v3.61.2 lesson: an ordering pin
that matched the WORKLIST's copy of the string passed for the wrong reason).

The pinned migration boundary is the one from design.md D7: absent a suite
manifest, every wired surface behaves exactly as it does today. Each
manifest-registering hook states it in its own section, so a future edit that
drops the boundary reads red here rather than silently making the wiring
mandatory in projects that never ran the suite builder.

Two pins are deliberately NEGATIVE and therefore green from the first run:
`mini-architect-team-pipeline` stays narrow (only the SWEEP gained the full-suite
run, per the suite-pipeline-wiring spec's "mini stays narrow while the sweep runs
the suite" scenario), and the sibling registries in other hook files are NOT
asserted here (they are out of this task's file scope). Both are regression
guards, not red-first behavior pins.

`intuition-map-lifecycle` is referenced by NAME only — this file never reads its
body. `playwright-suite-builder` is referenced by name in the wiring pins, and
its body IS read by exactly one pin, `test_registered_lane_carries_its_lifecycle
_step`, which is deliberate: registering that lane as run-driving is only safe
while its playbook marks the run complete, so the two must be asserted together.
That pin is conditional on the registry, so it goes quiet rather than red if the
lane is ever de-registered.

A note on writing pins in this file, learned repeatedly the hard way here: an
assertion must carry the claim its message makes. Four failure shapes recur.

(a) INTER-hook — a token that already exists in the sliced section, so the pin
    reads red at baseline for a DIFFERENT reason than its message names
    (adversarial F1; witnesses W2/W8/W9/W10). Guard: check the token against the
    fe30a182 baseline slice.

(b) INTRA-hook — a token that IS absent at baseline (so the baseline check above
    calls it discriminating) but comes from the hook's own TITLE or boilerplate
    rather than its instruction text, so renaming the instruction ships green
    (adversarial F6: a bare `grow` matched "**Grow the intuition map...**").
    Guard: check the token against the hook's title as well as the baseline —
    the baseline-only method is structurally blind to this, which is why the
    two checks are named separately here.

(c) RELATIONSHIP — a message describing a link ("the registry entry never
    outlives the lifecycle step") while the assertion tests only one side, so
    the other side can be deleted with the pin still green (first cut of the
    lifecycle pin). Guard: every noun in the message appears in the assertion.

(d) OPEN-ENDED NEGATIVE — a blocklist of forbidden phrasings, which is unbounded
    by construction and escapes on the first unlisted wording (adversarial F3;
    witness W16). Guard: prefer a CLOSED form — count the allowed occurrences —
    over enumerating the disallowed ones.

Related: prose about a step is not the step. Assert the INVOCATION form
(`run_continuity.py" --mark-complete`) rather than a bare substring a comment
could satisfy (adversarial F4; witness W14b).

THE PREVENTER — prefer this to all four guards above. The shapes (a)-(d) are
DETECTORS: each tells you to go check something, and each depends on somebody
remembering to check. Sentence-scoping is structural instead. An assertion that
requires TWO tokens to co-occur in ONE sentence cannot be satisfied by a heading
or a bold title, because a title is one short phrase and carries only one of
them — so shape (b) becomes unreachable rather than merely detectable.

Demonstrated in the sibling lane (skills-author, task-2): a pin asserting
`bug-path` under the heading ``## Verb — `bug-path-upsert` `` is textbook (b)
exposure and a token-level audit condemns it — yet its witness came back RED,
because the real assertion was `_has_sentence_with(section, "source",
"bug-path")` and the heading carries no `source`. The scoping had already closed
the hole the audit was about to flag.

So when a pin needs a token that also appears in a title, do not hunt for a
narrower token: require it to co-occur with a second token the title cannot
carry. Reach for a detector only where co-occurrence genuinely does not apply.
"""
from __future__ import annotations
from tests.helpers.surfaces import surface_read

import json
import re
from pathlib import Path

import pytest

from hooks import pretool_skill_gate as gate
from hooks import skill_invocation_audit as audit
from hooks.pretool_skill_gate import check_payload


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #

PLAYWRIGHT_FLOWS = "skills/playwright-user-flows/SKILL.md"
UX_TEST_BUILDER = "skills/ux-test-builder/SKILL.md"
BUG_FIX = "skills/bug-fix-pipeline/SKILL.md"
MAIN_PIPELINE = "skills/architect-team-pipeline/SKILL.md"
DEV_API = "skills/dev-api-integration-testing/SKILL.md"
INTEGRATION_AGENT = "agents/integration.md"
SWEEP_COMMAND = "commands/mini-review-sweep.md"
MINI_PIPELINE = "skills/mini-architect-team-pipeline/SKILL.md"
RUN_MONITOR = "skills/test-run-monitor/SKILL.md"
PROD_CLASSIFIER = "skills/test-prod-safety-classifier/SKILL.md"


def _read(plugin_root: Path, relpath: str) -> str:
    target = plugin_root / relpath
    assert target.exists(), f"{relpath} missing"
    return surface_read(target)


def _section(text: str, heading: str) -> str:
    """The section body for `heading`, up to the next same-or-higher heading."""
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


def _named_hook(section: str, bold_title: str) -> str:
    """The single paragraph of a named hook, sliced from its bold title to the
    next blank line.

    Necessary because some hooks live inside sections that ALREADY contain the
    vocabulary being pinned — the test-run-monitor hook sits under `## Inputs`,
    whose adapter table already names `LocalAdapter`, so a section-wide
    substring assertion passes whether or not the hook says anything. Slicing to
    the hook paragraph is what makes those pins measure the edit (the v3.61.2
    passed-for-the-wrong-reason lesson, caught live on this very pin)."""
    marker = f"**{bold_title}"
    start = section.find(marker)
    assert start >= 0, f"named hook not found: {bold_title!r}"
    end = section.find("\n\n", start)
    return section[start:end] if end > 0 else section[start:]


def _has_sentence_with(text: str, *tokens: str) -> bool:
    """True when ONE sentence contains every token (case-insensitive).

    This is the PREVENTER from the module note, applied rather than described: a
    heading or bold title is a single short phrase and cannot carry two
    independent tokens, so co-occurrence is structurally immune to the
    title-supplied-token class. Adopted from skills-author's lane (task-2), where
    it saved a pin a token-level audit would have condemned."""
    for sentence in re.split(r"(?<=[.!?])\s+|\n\n", text):
        low = sentence.lower()
        if all(t.lower() in low for t in tokens):
            return True
    return False


def _boundary_stated(section: str) -> bool:
    """The D7 migration boundary — 'absent a manifest, behavior is unchanged'."""
    lowered = section.lower()
    return (
        ("absent a suite manifest" in lowered or "absent a manifest" in lowered)
        and "unchanged" in lowered
    )


# --------------------------------------------------------------------------- #
# 3.1 — playwright-user-flows: Step 1 ensure + consult; Phase C registration
# --------------------------------------------------------------------------- #

STEP_1 = "### Step 1: Consult the route map"
STEP_1_HOOK_TITLE = "Ensure and consult the interaction-intuition map."
PHASE_C = "## Phase C — Coverage verification (before submitting tests)"


def test_playwright_flows_step1_ensures_the_intuition_map(plugin_root: Path) -> None:
    """R1: ad-hoc authoring must ENSURE the map exists, not assume a pipeline
    run produced it.

    Sliced to the added paragraph, not the Step 1 section: the section's own
    HEADING is '### Step 1: Consult the route map', so a section-scoped
    `"consult" in lowered` can never fail (adversarial F1 / witness W2)."""
    hook = _named_hook(
        _section(_read(plugin_root, PLAYWRIGHT_FLOWS), STEP_1), STEP_1_HOOK_TITLE
    )
    assert "intuition-map-lifecycle" in hook, (
        "Step 1 must name the `intuition-map-lifecycle` skill as the ensure path"
    )
    assert "`ensure` verb" in hook, (
        "Step 1 must name the `ensure` verb specifically — the bare word 'ensure' "
        "is too weak to bind the obligation to the lifecycle skill"
    )
    assert "INTERACTION_INTUITION_MAP.md" in hook, (
        "Step 1 must name the map artifact it ensures"
    )


def test_playwright_flows_step1_consults_the_map(plugin_root: Path) -> None:
    """The map is a binding input to authoring, not merely produced."""
    hook = _named_hook(
        _section(_read(plugin_root, PLAYWRIGHT_FLOWS), STEP_1), STEP_1_HOOK_TITLE
    )
    assert "consult it alongside" in hook, (
        "Step 1 must state the CONSULT obligation in the added text — the bare "
        "word 'consult' matches the section heading and can never fail (W2)"
    )
    assert "ROUTE_MAP.md" in hook, (
        "the consult obligation must name ROUTE_MAP.md as the map's companion"
    )
    assert "user_verdict: confirmed" in hook, (
        "Step 1 must distinguish confirmed entries (author to them) from unconfirmed ones"
    )


def test_step1_does_not_treat_a_present_map_as_satisfied(plugin_root: Path) -> None:
    """Phase-4 reconciliation SF-1.

    My Step 1 paraphrase collapsed the engine's FOUR-value `ensure` contract to
    two ("absent -> produces one; present -> no-op"), which told the ad-hoc
    authoring path that any present map is satisfied — defeating the `populate`
    guard the engine added for exactly that failure. Present-and-unsatisfied is
    real: `repair-map` (present, unparseable or blocking findings) and
    `populate` (present, schema-valid, ZERO elements).

    The hook must therefore bind completion to what the verb REPORTS, not to the
    map's existence. Sentence-scoped per the module note's PREVENTER, so a bold
    title cannot supply either token on its own."""
    hook = _named_hook(
        _section(_read(plugin_root, PLAYWRIGHT_FLOWS), STEP_1), STEP_1_HOOK_TITLE
    )
    assert _has_sentence_with(hook, "action_required", "none"), (
        "Step 1 must bind ensure's completion to `action_required` reading "
        "`none` — not to the map merely existing (SF-1)"
    )
    assert _has_sentence_with(hook, "populate", "scaffold"), (
        "Step 1 must name the present-but-empty case: a freshly scaffolded map "
        "reports `populate`, never `none` (SF-1)"
    )
    assert "repair-map" in hook, (
        "Step 1 must name the present-but-broken case (`repair-map`) too — "
        "otherwise 'present' still reads as satisfied for a map that will not parse"
    )


def test_playwright_flows_phase_c_registers_into_the_manifest(plugin_root: Path) -> None:
    section = _section(_read(plugin_root, PLAYWRIGHT_FLOWS), PHASE_C)
    assert "suite-manifest.json" in section, (
        "Phase C must name the suite manifest as the registration target"
    )
    assert "playwright-suite-builder" in section, (
        "Phase C must name the suite-builder skill that owns the manifest contract"
    )


def test_playwright_flows_phase_c_states_the_absent_manifest_boundary(plugin_root: Path) -> None:
    section = _section(_read(plugin_root, PLAYWRIGHT_FLOWS), PHASE_C)
    assert _boundary_stated(section), (
        "Phase C must state the migration boundary: absent a suite manifest, behavior is unchanged"
    )


# --------------------------------------------------------------------------- #
# 3.2 — ux-test-builder: U2 + U5 grow; U9 registration
# --------------------------------------------------------------------------- #

U2 = "## Phase U2 — Literal flow draft"
U5 = "## Phase U5 — Playwright authoring per distilled flow"
U9 = "## Phase U9 — Final report"


@pytest.mark.parametrize("heading", [U2, U5])
def test_ux_test_builder_grows_the_map(plugin_root: Path, heading: str) -> None:
    """R2: a user-specified flow upserts as a CONFIRMED entry sourced
    `user-flow`.

    This pin asserts only that the phase names the verb and the provenance the
    upsert carries. The D2 RATIONALE — that a user-specified flow carries no
    uncertainty for the Phase -1D gate to resolve, so `grow` bypasses it — is a
    separate obligation asserted by test_ux_test_builder_u2_names_the_bulk_verify
    _asymmetry; it is named here as context, not tested here."""
    section = _section(_read(plugin_root, UX_TEST_BUILDER), heading)
    assert "intuition-map-lifecycle" in section, (
        f"{heading}: must name the `intuition-map-lifecycle` skill"
    )
    # Adversarial F6: a bare "grow" is satisfied by the hook's own bold TITLE
    # ("**Grow the intuition map...**"), so renaming the INSTRUCTION verb to
    # `extend` ships green. Demand the backticked verb form, which only the
    # instruction text carries. This is the intra-hook blind spot: the token is
    # absent at baseline (so the baseline audit calls it discriminating) yet
    # still comes from the hook's own boilerplate rather than its instruction.
    assert "`grow` verb" in section, (
        f"{heading}: must name the `grow` verb in backticked form — a bare 'grow' "
        "is satisfied by the hook's own title and survives renaming the "
        "instruction verb (F6)"
    )
    assert "source: user-flow" in section or "`source: user-flow`" in section, (
        f"{heading}: must name the `source: user-flow` provenance the upsert carries"
    )
    assert "confirmed" in section.lower(), (
        f"{heading}: must state the upsert lands as a confirmed entry"
    )


def test_ux_test_builder_u2_names_the_bulk_verify_asymmetry(plugin_root: Path) -> None:
    """D2 is the load-bearing asymmetry — grow bypasses the -1D bulk-verify gate
    deliberately, and a contradiction is the one case that still asks."""
    section = _section(_read(plugin_root, UX_TEST_BUILDER), U2)
    lowered = section.lower()
    assert "bulk-verify" in lowered, "U2 must name the bulk-verify gate it bypasses"
    assert "contradiction" in lowered or "contradicts" in lowered, (
        "U2 must name the contradiction case that still asks"
    )


@pytest.mark.parametrize("heading", [U2, U5])
def test_ux_test_builder_states_the_caller_ambiguity_duty(plugin_root: Path, heading: str) -> None:
    """Phase-4 reconciliation SF-2.

    Both sites said "the ONE case that still asks is a contradiction", which is
    false: `grow` has TWO question kinds. The second — an element the CALLER
    marked `ambiguous: true` routes to an `ambiguous-extraction` question and is
    never upserted — is unreachable from precisely this lane if the text names
    only contradictions, because ux-test-builder IS the heuristic-extraction
    caller the design's risk register named. The engine reads a MISSING marker as
    falsy (silence = certain, by design), so an unstated duty is a silent
    mis-upsert, not an error.

    Both sites are pinned because both call `grow`; fixing one would leave the
    other lane-blind."""
    section = _section(_read(plugin_root, UX_TEST_BUILDER), heading)
    assert "ambiguous" in section, (
        f"{heading}: must name the ambiguity path at all — `grow` has TWO "
        "question kinds and this lane can only reach the second by marking it"
    )
    assert _has_sentence_with(section, "ambiguous", "mark"), (
        f"{heading}: must state the CALLER DUTY — this lane marks an uncertain "
        "extraction; the engine cannot judge a flow it never saw (SF-2)"
    )
    assert _has_sentence_with(section, "never", "upsert") or "never upserted" in section, (
        f"{heading}: must state that a marked-ambiguous element is NEVER "
        "upserted — a question is produced instead"
    )


def test_ux_test_builder_u9_registers_into_the_manifest(plugin_root: Path) -> None:
    section = _section(_read(plugin_root, UX_TEST_BUILDER), U9)
    assert "suite-manifest.json" in section, (
        "U9 must name the suite manifest as the registration target"
    )
    assert "playwright-suite-builder" in section, (
        "U9 must name the suite-builder skill that owns the manifest contract"
    )


def test_ux_test_builder_u9_states_the_absent_manifest_boundary(plugin_root: Path) -> None:
    section = _section(_read(plugin_root, UX_TEST_BUILDER), U9)
    assert _boundary_stated(section), (
        "U9 must state the migration boundary: absent a suite manifest, behavior is unchanged"
    )


# --------------------------------------------------------------------------- #
# 3.3 — bug-fix-pipeline: B2 bug-path-upsert; B7 debug-flow registration
# --------------------------------------------------------------------------- #

B2 = "## Phase B2 — Reproduction-artifact promotion + backend diagnostic"
B7 = "## Phase B7 — Archive + Report"


def test_bug_fix_b2_upserts_the_bug_path(plugin_root: Path) -> None:
    """R3: the repro artifact proved which elements the failing path traverses;
    that evidence reaches the map instead of dying with the run."""
    section = _section(_read(plugin_root, BUG_FIX), B2)
    assert "intuition-map-lifecycle" in section, (
        "B2 must name the `intuition-map-lifecycle` skill"
    )
    assert "bug-path-upsert" in section, "B2 must name the `bug-path-upsert` verb"
    assert "source: bug-path" in section or "`source: bug-path`" in section, (
        "B2 must name the `source: bug-path` provenance the upsert carries"
    )
    assert "regression_refs" in section, (
        "B2 must name `regression_refs[]` — the artifact the upsert points back at"
    )


def test_bug_fix_b7_registers_the_repro_as_a_debug_flow(plugin_root: Path) -> None:
    section = _section(_read(plugin_root, BUG_FIX), B7)
    assert "suite-manifest.json" in section, (
        "B7 must name the suite manifest as the registration target"
    )
    assert "debug-flow" in section, "B7 must name the `debug-flow` entry kind"
    assert "origin_ref" in section, (
        "B7 must name `origin_ref` — the SR path / bug slug the entry is bound to"
    )


def test_bug_fix_b7_states_the_absent_manifest_boundary(plugin_root: Path) -> None:
    section = _section(_read(plugin_root, BUG_FIX), B7)
    assert _boundary_stated(section), (
        "B7 must state the migration boundary: absent a suite manifest, behavior is unchanged"
    )


# --------------------------------------------------------------------------- #
# 3.4 — full integration enumerates the manifest and runs the ENTIRE dev suite
# --------------------------------------------------------------------------- #

PHASE_5 = "## Phase 5 — Cross-Layer Integration (frontend + backend)"
DEV_API_FULL_RUN = "## Full-run enumeration — the whole dev suite"
PLAYWRIGHT_WORKFLOW = "## Two-phase Playwright workflow (when frontend is in scope)"


def test_phase_5_enumerates_the_manifest(plugin_root: Path) -> None:
    """R5: a full integration run runs the WHOLE dev suite, not only the flows
    the current slice authored."""
    section = _section(_read(plugin_root, MAIN_PIPELINE), PHASE_5)
    assert "suite-manifest.json" in section, (
        "Phase 5 must name `suite-manifest.json` as the enumeration source"
    )
    lowered = section.lower()
    # `enumerate` and `solution requirement` BOTH pre-exist in this slice (items
    # 7, 9, 9b), so the bare tokens guard nothing — adversarial F1 / witness W8.
    # Bind to the manifest-scoped clauses the 3c hook actually authored.
    assert "the selector enumerates it" in lowered, (
        "Phase 5 must state the enumeration duty against THAT MANIFEST — the bare "
        "verb 'enumerate' already appears at items 7/9/9b and guards nothing (W8)"
    )
    # F6 class, found by the INTRA-HOOK audit rather than by the adversary:
    # "entire dev suite" lives ONLY in this hook's bold title, so the instruction
    # text could stop saying the whole suite runs and the pin would still pass.
    # Bind to the instruction clause that states the actual duty.
    assert "runs once, at phase 8" in lowered, (
        "Phase 5 must state the duty in its INSTRUCTION text — that the run "
        "executes every entry in the manifest's `dev` project. 'entire dev suite' "
        "alone lives in the hook's title and survives gutting the instruction (F6)"
    )
    assert "not the entire dev suite" in lowered, (
        "Phase 5 must state the selected flows run, not the ENTIRE dev suite (v4.0.0 reversal)"
    )
    assert "solution requirements exactly as before" in lowered, (
        "Phase 5 must state failures route as solution requirements EXACTLY AS "
        "TODAY — the bare phrase 'solution requirement' pre-exists in this slice (W8)"
    )


def test_phase_5_states_the_absent_manifest_boundary(plugin_root: Path) -> None:
    section = _section(_read(plugin_root, MAIN_PIPELINE), PHASE_5)
    assert _boundary_stated(section), (
        "Phase 5 must state the migration boundary: absent a suite manifest, behavior is unchanged"
    )


def test_dev_api_integration_testing_full_run_enumerates_the_manifest(plugin_root: Path) -> None:
    section = _section(_read(plugin_root, DEV_API), DEV_API_FULL_RUN)
    assert "suite-manifest.json" in section, (
        "the full-run section must name `suite-manifest.json` as the enumeration source"
    )
    lowered = section.lower()
    # This whole section is new, so a bare `enumerate` IS discriminating here
    # (unlike Phase 5 and integration.md). Bound to the manifest-scoped clause
    # anyway, so all three enumeration pins guard the same shape and none of them
    # can be satisfied by an unrelated use of the verb.
    assert "the selector reads it" in lowered, (
        "the full-run section must state the manifest is enumerated through the selector"
    )
    assert "runs once, at phase 8" in lowered, (
        "the full-run section must state the whole dev project runs once at Phase 8 (v4.0.0)"
    )


def test_dev_api_integration_testing_states_the_absent_manifest_boundary(plugin_root: Path) -> None:
    section = _section(_read(plugin_root, DEV_API), DEV_API_FULL_RUN)
    assert _boundary_stated(section), (
        "the full-run section must state the migration boundary: "
        "absent a suite manifest, behavior is unchanged"
    )


def test_integration_agent_brief_names_the_enumeration_duty(plugin_root: Path) -> None:
    section = _section(_read(plugin_root, INTEGRATION_AGENT), PLAYWRIGHT_WORKFLOW)
    assert "suite-manifest.json" in section, (
        "the integration agent's Playwright workflow must name the manifest"
    )
    lowered = section.lower()
    # `enumerate` pre-exists at agents/integration.md:62 ("enumerate every
    # interactive element...") inside this same slice — adversarial F1 / W9.
    assert "enumerate that manifest through the selector" in lowered, (
        "the integration agent must state the enumeration duty against THAT "
        "MANIFEST — the bare verb pre-exists at workflow step 1 and guards nothing (W9)"
    )
    assert "not the entire dev suite" in lowered, (
        "the integration agent must state the selected flows run, not the ENTIRE dev suite"
    )
    assert _boundary_stated(section), (
        "the integration agent must state the absent-manifest boundary"
    )


# --------------------------------------------------------------------------- #
# 3.5 — the sweep gains the full-suite run; mini stays narrow
# --------------------------------------------------------------------------- #


def test_mini_review_sweep_adds_the_full_suite_run(plugin_root: Path) -> None:
    body = _read(plugin_root, SWEEP_COMMAND)
    assert "suite-manifest.json" in body, (
        "the sweep must name the manifest it enumerates"
    )
    lowered = body.lower()
    # F6 class, found by the INTRA-HOOK audit: "full-suite run" is the bullet's
    # bold TITLE only, so the gate's actual instruction could be gutted with the
    # pin still green. Bind to the instruction clause as well as the title.
    assert "select --phase 8" in lowered, (
        "the sweep must state the duty in its INSTRUCTION text — run the ENTIRE "
        "dev project. The bold title 'Full-suite run' alone survives gutting the "
        "instruction beneath it (F6)"
    )
    assert "full suite at the merge boundary" in lowered, (
        "the sweep must name the full-suite run among its batched gates"
    )
    assert "playwright-suite-builder" in body, (
        "the sweep must name the suite-builder skill that owns the manifest contract"
    )
    assert _boundary_stated(body), (
        "the sweep must state the absent-manifest boundary"
    )


def test_mini_pipeline_stays_narrow(plugin_root: Path) -> None:
    """Regression guard (green from the first run): only the SWEEP gained the
    full-suite run. The mini lane's whole theory is fast at runtime, audited in
    batch — pulling whole-suite enumeration into it would undo that."""
    body = _read(plugin_root, MINI_PIPELINE)
    assert "suite-manifest" not in body, (
        "mini-architect-team-pipeline must NOT name suite-manifest enumeration — "
        "mini stays narrow; the batched sweep runs the suite"
    )


# --------------------------------------------------------------------------- #
# 3.6 — prod smoke suite source + the classifier's manifest binding
# --------------------------------------------------------------------------- #

MONITOR_INPUTS = "## Inputs"
MONITOR_HOOK_TITLE = "The suite-manifest prod project is a named test source."
CLASSIFIER_BINDING = "## Suite-manifest binding"


def test_test_run_monitor_names_the_prod_project_as_a_source(plugin_root: Path) -> None:
    """R6: the prod project is runnable through the EXISTING command-spawn path
    against the production URL — reuse-first, no adapter change."""
    hook = _named_hook(
        _section(_read(plugin_root, RUN_MONITOR), MONITOR_INPUTS), MONITOR_HOOK_TITLE
    )
    assert "suite-manifest.json" in hook, (
        "test-run-monitor must name the suite manifest as a source"
    )
    assert "prod-check" in hook, (
        "test-run-monitor must name the read-only `prod-check` set the prod project holds"
    )
    assert "LocalAdapter" in hook, (
        "the HOOK ITSELF must name the LocalAdapter command-spawn path as the runner "
        "(the `## Inputs` adapter table already names it, so a section-wide match "
        "would pass without the hook saying anything)"
    )
    assert "production URL" in hook, (
        "test-run-monitor must name the production URL the prod project runs against"
    )


def test_test_run_monitor_names_the_command_spawn_path_as_correct(plugin_root: Path) -> None:
    """Replaces the old `no new adapter` pin, which locked in the F2 falsehood.

    The amended scenario requires the hook to say the prod suite reaches the
    monitor through the EXISTING command-spawn selection and that this is the
    right routing — not a shortfall the reader should try to fix by inventing an
    adapter row."""
    hook = _named_hook(
        _section(_read(plugin_root, RUN_MONITOR), MONITOR_INPUTS), MONITOR_HOOK_TITLE
    )
    lowered = hook.lower()
    assert "routing is correct" in lowered, (
        "the hook must state the LocalAdapter routing is CORRECT, so a reader "
        "does not treat it as a gap and add an adapter row"
    )
    assert "no adapter change" in lowered, (
        "the hook must state the prod suite needs NO adapter change (D5 reuse)"
    )
    assert "test-command spawn" in lowered or "command spawn" in lowered, (
        "the hook must name the command-spawn path as the mechanism"
    )


def test_test_run_monitor_does_not_claim_prodqa_adapter_runs_the_suite(plugin_root: Path) -> None:
    """Adversarial finding F2: ProductionQAAdapter is an APM-poll / log-tail
    adapter — it OBSERVES a signal already being emitted and cannot spawn a test
    run. An earlier draft of this hook named it as the runner, which would have
    shipped an instruction no operator could follow. The claim must be absent,
    and the distinction stated so the same error is not reintroduced."""
    section = _section(_read(plugin_root, RUN_MONITOR), MONITOR_INPUTS)
    hook = _named_hook(section, MONITOR_HOOK_TITLE)
    # Adversarial F3: a blocklist of phrasings is unbounded by construction —
    # their W16 inserted "The `ProductionQAAdapter` runs this suite." and sailed
    # through all four patterns. Counting is the closed form: the hook gets
    # EXACTLY ONE mention, the does-not-execute warning asserted below. Any
    # second mention is a new claim about that adapter and must be justified,
    # which is a review conversation rather than a silent pass.
    assert hook.count("ProductionQAAdapter") == 1, (
        "the hook must mention `ProductionQAAdapter` EXACTLY ONCE — the "
        "does-not-execute warning. Found "
        f"{hook.count('ProductionQAAdapter')}. A second mention is a new claim "
        "about an adapter that cannot spawn a test run (F2/F3); if you genuinely "
        "need it, change this pin deliberately rather than widening a blocklist."
    )
    lowered = hook.lower()
    assert "does not execute" in lowered or "cannot spawn" in lowered, (
        "the section must state explicitly that ProductionQAAdapter does not "
        "execute / cannot spawn the test run, so the F2 error is not reintroduced"
    )


def test_prod_safety_classifier_binds_verdicts_into_the_manifest(plugin_root: Path) -> None:
    section = _section(_read(plugin_root, PROD_CLASSIFIER), CLASSIFIER_BINDING)
    assert "playwright-suite-builder" in section, (
        "the binding note must name the suite-builder that records the verdict"
    )
    assert "P8" in section, "the binding note must name the P8 stage that records it"
    assert "suite-manifest.json" in section, "the binding note must name the manifest"
    assert "`safety`" in section, "the binding note must name the `safety` field"
    assert "`mutates_data`" in section, "the binding note must name the `mutates_data` field"


def test_prod_safety_classifier_states_prod_entry_requires_a_verdict(plugin_root: Path) -> None:
    """Default-deny (D6): no verdict => dev-only, never prod."""
    section = _section(_read(plugin_root, PROD_CLASSIFIER), CLASSIFIER_BINDING)
    lowered = section.lower()
    assert "prod_exceptions" in section, (
        "the binding note must name the `prod_exceptions[]` authorization path"
    )
    assert "safety: dev" in lowered, (
        "the binding note must state an unclassified test lands `safety: dev`"
    )
    assert "exclude" in lowered, (
        "the binding note must state an unclassified test is EXCLUDED from the prod project"
    )


# --------------------------------------------------------------------------- #
# 3.7 registry — the suite builder is a command-reachable run-driving pipeline
# --------------------------------------------------------------------------- #


def test_pretool_skill_gate_registers_the_suite_builder() -> None:
    """`playwright-suite-builder` drives a run behind its own slash command, so
    it belongs in the real-time PreToolUse hard-gate's pipeline registry beside
    `data-eng-pipeline` — the same role, the same registry, the same file."""
    assert "playwright-suite-builder" in gate._PIPELINE_SKILLS, (
        "playwright-suite-builder must be registered in pretool_skill_gate._PIPELINE_SKILLS"
    )


def test_pretool_skill_gate_registry_keeps_its_existing_members() -> None:
    """The addition is beside the existing entries, never in place of them."""
    for existing in (
        "architect-team-pipeline",
        "bug-fix-pipeline",
        "ux-test-builder",
        "mini-architect-team-pipeline",
        "data-eng-pipeline",
        "proposal-refiner",
    ):
        assert existing in gate._PIPELINE_SKILLS, (
            f"{existing} must remain registered in _PIPELINE_SKILLS"
        )


# --------------------------------------------------------------------------- #
# E1 — the command->skill mapping, pinned as COMPOSED behavior
# --------------------------------------------------------------------------- #
#
# Gating /architect-team:playwright-suite takes TWO registries in TWO files:
# skill_invocation_audit._PIPELINE_COMMAND_SKILLS routes the command name to the
# lane skill, and pretool_skill_gate._PIPELINE_SKILLS marks that skill as
# pipeline-driving. Either half alone gates nothing. The v3.61.0 one-of-two-
# places lesson is that separate pins on separate halves both pass while the
# composed behavior is dead, so the load-bearing pin below drives the REAL gate
# end to end and the resolution pin asserts both halves in one body.


def _user(text: str, ts: str) -> dict:
    return {"type": "user", "userType": "external", "timestamp": ts,
            "message": {"role": "user", "content": text}}


def _skill_call(skill: str, ts: str) -> dict:
    return {"type": "assistant", "timestamp": ts, "message": {
        "role": "assistant",
        "content": [{"type": "tool_use", "name": "Skill", "input": {"skill": skill}}],
    }}


def _command_text(plugin_command: str, args: str = "build the suite") -> str:
    """The harness's recorded shape for a slash-command invocation."""
    return (
        f"<command-message>{plugin_command}</command-message>\n"
        f"<command-name>/{plugin_command}</command-name>\n"
        f"<command-args>{args}</command-args>"
    )


def _write(tmp_path: Path, records: list, name: str) -> Path:
    p = tmp_path / name
    p.write_text("\n".join(json.dumps(r) for r in records), encoding="utf-8")
    return p


def _payload(transcript: Path, tool: str = "Read") -> dict:
    return {"tool_name": tool, "transcript_path": str(transcript),
            "cwd": str(transcript.parent)}


def test_playwright_suite_command_resolves_end_to_end_to_the_lane_skill() -> None:
    """Both halves, asserted in ONE body: the command resolves to the lane
    skill AND that skill is gate-registered. Neither half is meaningful alone."""
    mapping = audit.COMMAND_TO_SKILLS
    assert "playwright-suite" in mapping, (
        "COMMAND_TO_SKILLS must carry the playwright-suite command"
    )
    assert "playwright-suite-builder" in mapping["playwright-suite"], (
        "the playwright-suite command must map to the playwright-suite-builder lane skill"
    )
    assert set(mapping["playwright-suite"]) & gate._PIPELINE_SKILLS, (
        "the command's resolved skills must intersect _PIPELINE_SKILLS — without "
        "that intersection the mapping exists but the gate never fires"
    )


def test_playwright_suite_command_gated_and_satisfied_by_suite_builder_skill(tmp_path: Path) -> None:
    """The COMPOSED behavior: the real PreToolUse gate blocks a build tool on an
    unsatisfied /architect-team:playwright-suite request, and stands down once
    the playwright-suite-builder Skill is engaged. This is the pin that fails if
    EITHER registry half is missing, so neither can silently regress."""
    pend = _write(tmp_path, [
        _user(_command_text("architect-team:playwright-suite"), "2026-08-26T10:00:00Z"),
    ], name="ps_pend.jsonl")
    assert check_payload(_payload(pend, tool="Edit"))[0] == 2, (
        "an unsatisfied /architect-team:playwright-suite request must BLOCK Edit"
    )
    ok = _write(tmp_path, [
        _user(_command_text("architect-team:playwright-suite"), "2026-08-26T10:00:00Z"),
        _skill_call("playwright-suite-builder", "2026-08-26T10:00:03Z"),
    ], name="ps_ok.jsonl")
    assert check_payload(_payload(ok, tool="Read"))[0] == 0, (
        "engaging the playwright-suite-builder Skill must stand the gate down"
    )


# --------------------------------------------------------------------------- #
# E2 — the run-continuity registry, pinned as CONSUMING behavior
# --------------------------------------------------------------------------- #
#
# RUN_DRIVING_SKILLS membership is not a label: hooks/pretool_skill_gate.py:760
# tests it and, on a match, :778 calls _rc.engage_marker() — WRITING the
# active-run marker. So the pin drives that real PostToolUse path and observes
# the marker, rather than asserting set membership (which would pass even if the
# consumer stopped reading the registry).
#
# Landing this entry was deliberately SEQUENCED behind the suite-builder skill
# gaining a `--mark-complete` step at P9: registering a lane whose body never
# releases the marker would end every /architect-team:playwright-suite run in
# run-active state, which is the v3.61.2 wedge.


def _engagement_payload(workspace: Path, transcript: Path, skill: str) -> dict:
    return {
        "tool_name": "Skill",
        "tool_input": {"skill": skill},
        "tool_response": {"ok": True},
        "cwd": str(workspace),
        "transcript_path": str(transcript),
        "session_id": "test-session",
    }


def _engage(tmp_path: Path, skill: str, name: str) -> dict | None:
    """Drive the REAL PostToolUse engagement path; return the marker written."""
    from hooks import run_continuity as rc

    ws = tmp_path / name
    ws.mkdir(parents=True, exist_ok=True)
    transcript = ws / "transcript.jsonl"
    transcript.write_text(
        json.dumps(_user("build the playwright suite", "2026-08-26T10:00:00Z")),
        encoding="utf-8",
    )
    gate.record_engagement(_engagement_payload(ws, transcript, skill))
    return rc.read_marker(ws)


def test_suite_builder_engages_the_active_run_marker(tmp_path: Path) -> None:
    """The consuming behavior: a suite-builder Skill call must ENGAGE the
    active-run marker, exactly as an already-registered lane does.

    The control half is load-bearing — if run-continuity were disabled in the
    environment, a target-only assertion would pass vacuously (marker None for
    both). Asserting the control engages makes that failure loud instead."""
    control = _engage(tmp_path, "architect-team-pipeline", "control")
    assert control is not None and control.get("status") == "active", (
        "CONTROL FAILED — an already-registered lane did not engage the marker, "
        "so this test cannot say anything about the suite-builder "
        f"(continuity disabled? marker={control!r})"
    )

    target = _engage(tmp_path, "playwright-suite-builder", "target")
    assert target is not None, (
        "playwright-suite-builder did not engage the active-run marker — it is "
        "not in run_continuity.RUN_DRIVING_SKILLS, so pretool_skill_gate's "
        "PostToolUse arm returns before calling engage_marker()"
    )
    assert target.get("status") == "active", f"expected an active marker, got {target!r}"
    assert target.get("skill") == "playwright-suite-builder", (
        f"the marker must record which lane engaged it, got {target!r}"
    )


def test_engagement_skills_stays_the_derived_superset() -> None:
    """ENGAGEMENT_SKILLS must equal RUN_DRIVING_SKILLS | {proposal-refiner}, and
    the suite-builder must be in it.

    WHAT THIS CATCHES: any DIVERGENCE in the resulting sets — a lane added to one
    registry and not the other, or the refiner dropped.

    WHAT IT DOES NOT CATCH (adversarial F5 / witness W13b): re-declaring
    ENGAGEMENT_SKILLS as an independent literal whose members happen to be
    identical today. The assertion compares VALUES, not the derivation, so an
    equivalent literal passes — and the divergence it would eventually cause is
    caught later, when someone adds a lane to one side, not at the moment the
    derivation is dropped. Asserting the source form would need AST inspection;
    that is a deliberate non-goal here, so the limit is stated rather than
    implied. The membership half read RED before the registry edit; the identity
    itself held at baseline and is the regression guard."""
    from hooks import run_continuity as rc

    assert rc.ENGAGEMENT_SKILLS == rc.RUN_DRIVING_SKILLS | {"proposal-refiner"}, (
        "ENGAGEMENT_SKILLS must remain exactly RUN_DRIVING_SKILLS | {proposal-refiner}"
    )
    assert "playwright-suite-builder" in rc.ENGAGEMENT_SKILLS, (
        "the suite-builder must be engaged-session machinery via the derivation"
    )


def test_registered_lane_carries_its_lifecycle_step(plugin_root: Path) -> None:
    """CONDITIONAL contract: IF the suite-builder is registered run-driving,
    THEN its playbook must mark the run complete.

    A lane in RUN_DRIVING_SKILLS opens the active-run marker on invocation, and
    the marker clears only via `--mark-complete`, an explicit user stand-down, or
    the staleness window — so a registered lane whose body never marks complete
    wedges every one of its runs (the v3.61.2 field report).

    The conditional is the point, and the first version of this pin got it wrong:
    it asserted the prose unconditionally, which made it green even with the lane
    de-registered (mutation-proved escape, caught in review by skills-author).
    Reading the registry makes the pin assert the CONTRACT its name claims, and
    it also stays correct through a DELIBERATE de-registration — it stops
    demanding a lifecycle step that no longer has a reason to exist, rather than
    going red and pressuring someone to re-add dead prose.

    Going quiet on de-registration costs no coverage: registry membership is
    independently owned by test_suite_builder_engages_the_active_run_marker and
    test_engagement_skills_stays_the_derived_superset, so the lane cannot be
    removed without those two reading red first."""
    from hooks import run_continuity as rc

    if "playwright-suite-builder" not in rc.RUN_DRIVING_SKILLS:
        pytest.skip(
            "playwright-suite-builder is not registered run-driving, so the "
            "lifecycle obligation does not apply; its membership is pinned by "
            "test_suite_builder_engages_the_active_run_marker"
        )
    body = _read(plugin_root, "skills/playwright-suite-builder/SKILL.md")
    # Adversarial F4: a bare `--mark-complete` substring is satisfied by ANY
    # mention — their W14b shipped green on a body whose only occurrence was
    # "NOTE: a future version may add a `--mark-complete` call here." Demand the
    # INVOCATION FORM, so prose about the step cannot stand in for the step.
    assert 'run_continuity.py" --mark-complete' in body, (
        "playwright-suite-builder IS in run_continuity.RUN_DRIVING_SKILLS, so its "
        "playbook MUST actually INVOKE the lifecycle step — the literal "
        '`run_continuity.py" --mark-complete` form, not merely mention it in prose. '
        "Otherwise every suite run ends wedged in run-active state. Either add the "
        "P9 invocation or de-register the lane; the two must move together."
    )


def test_playwright_suite_frozen_fallback_lists_the_command() -> None:
    """The fallback command list (in force when commands/ is unreadable, e.g. the
    hook running detached from the repo) must name playwright-suite: COMMAND_TO_SKILLS
    is built by iterating CANONICAL_COMMANDS, so a command missing from the fallback
    gets no mapping at all on that path — the same one-of-two-places hole, one level
    down. Mirrors the data-eng precedent in tests/test_data_eng_entry_surfaces.py."""
    src = (Path(audit.__file__)).read_text(encoding="utf-8")
    start = src.find("def _discover_canonical_commands")
    end = src.find("\ndef ", start + 1)
    region = src[start:end]
    assert '"playwright-suite"' in region, (
        "the frozen fallback tuple must include playwright-suite"
    )
