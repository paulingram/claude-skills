# -*- coding: utf-8 -*-
"""Structural pins for the playwright-suite / intuition-lifecycle SURFACES (tasks 2.1-2.4).

Scope boundary: this file pins the NEW skill + command surfaces and the additive
schema section on `interaction-intuition`. The thin pin-tested EDITS to the eight
EXISTING wired skills (task group 3) live in their own file,
`tests/test_playwright_suite_hooks.py`, so the two task groups never share a file.

Frontmatter discipline (design D9). The house trap is a `": "` inside an
*unquoted* plain-scalar frontmatter value - `yaml.safe_load` raises
"mapping values are not allowed here" on it. Quoted values are immune, which is
why several shipped descriptions legitimately carry a colon. The pins below
therefore hold the strong form on the three NEW surfaces (no colon-space at all
in the raw description, quoted or not) and hold the real invariant - the value
parses - on every surface including the pre-existing `interaction-intuition`
description, whose text this change must not alter.
"""
from __future__ import annotations
from tests.helpers.surfaces import agent_surface, skill_surface, surface_read

from pathlib import Path

import pytest

from tests.helpers import frontmatter


LIFECYCLE_SKILL = "skills/intuition-map-lifecycle/SKILL.md"
SUITE_SKILL = "skills/playwright-suite-builder/SKILL.md"
INTUITION_SKILL = "skills/interaction-intuition/SKILL.md"
SUITE_COMMAND = "commands/playwright-suite.md"

#: Every surface this task group owns.
OWNED_SURFACES = (LIFECYCLE_SKILL, SUITE_SKILL, INTUITION_SKILL, SUITE_COMMAND)

#: The three surfaces this change CREATES - held to the strong no-colon-space form.
NEW_SURFACES = (LIFECYCLE_SKILL, SUITE_SKILL, SUITE_COMMAND)


def _body(plugin_root: Path, rel: str) -> str:
    _, body = frontmatter.parse(plugin_root / rel)
    return body


def _section(body: str, header: str) -> str:
    """The slice of `body` from `header` up to the next same-or-shallower heading.

    The header must start a LINE. An inline prose mention of a heading string
    (`see \\`## Phase P9\\`'s note`) once hijacked this slicer and turned six
    unrelated pins red - a real defect the pins caught, but only after some
    confusion, so the match is anchored now.
    """
    start = -1
    for candidate in (0, *[i + 1 for i, ch in enumerate(body) if ch == "\n"]):
        if body.startswith(header, candidate):
            start = candidate
            break
    assert start >= 0, f"missing section header at line start: {header!r}"
    level = len(header) - len(header.lstrip("#"))
    nxt = len(body)
    for depth in range(1, level + 1):
        probe = body.find("\n" + "#" * depth + " ", start + 1)
        if probe >= 0:
            nxt = min(nxt, probe)
    return body[start:nxt]


def _sentences(text: str) -> list[str]:
    """Rough sentence split, lowercased, with line wraps flattened.

    Multi-substring pins ("`never` appears AND `overwrite` appears") pass on words
    scattered across unrelated sentences - the v3.61.2 passed-for-the-wrong-reason
    failure mode. Pins that hold a CLAIM assert the words co-occur in ONE sentence,
    which is what this feeds. Line wraps are flattened first so an authored phrase
    broken across two source lines still reads as contiguous.
    """
    flat = " ".join(text.split()).lower()
    return [s for s in flat.replace("!", ".").replace("?", ".").split(".") if s.strip()]


def _has_sentence_with(text: str, *needles: str) -> bool:
    """True when ONE sentence carries every needle."""
    return any(all(n in s for n in needles) for s in _sentences(text))


def _flat(text: str) -> str:
    """Lowercased, whitespace-collapsed - so a wrapped phrase matches contiguously."""
    return " ".join(text.split()).lower()


def _raw_description_line(path: Path) -> str:
    """The literal `description:` frontmatter line, as authored (pre-YAML-parse)."""
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---"), f"{path}: no frontmatter"
    fm_text = text.split("---", 2)[1]
    for line in fm_text.splitlines():
        if line.startswith("description:"):
            return line.partition(":")[2].strip()
    raise AssertionError(f"{path}: no single-line `description:` scalar")


# --------------------------------------------------------------------------- #
# existence + frontmatter (2.1 / 2.2 / 2.3 / 2.4)
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("rel", OWNED_SURFACES)
def test_surface_exists(plugin_root: Path, rel: str) -> None:
    assert (plugin_root / rel).exists(), f"missing surface: {rel}"


@pytest.mark.parametrize("rel", OWNED_SURFACES)
def test_frontmatter_parses_with_a_substantive_description(plugin_root: Path, rel: str) -> None:
    fm, body = frontmatter.parse(plugin_root / rel)
    assert isinstance(fm.get("description"), str) and len(fm["description"]) > 20, (
        f"{rel}: description must be a substantive string"
    )
    assert len(fm["description"]) <= 1024, (
        f"{rel}: description is {len(fm['description'])} chars, over the 1024-char cap"
    )
    assert body.strip(), f"{rel}: body is empty"


@pytest.mark.parametrize("rel", (LIFECYCLE_SKILL, SUITE_SKILL, INTUITION_SKILL))
def test_skill_frontmatter_name_matches_directory(plugin_root: Path, rel: str) -> None:
    fm, _ = frontmatter.parse(plugin_root / rel)
    assert fm.get("name") == Path(rel).parent.name, f"{rel}: frontmatter name mismatch"


@pytest.mark.parametrize("rel", NEW_SURFACES)
def test_new_surface_description_has_no_colon_space(plugin_root: Path, rel: str) -> None:
    """D9 - the house frontmatter rule, held on every surface this change creates."""
    raw = _raw_description_line(plugin_root / rel)
    assert ": " not in raw, (
        f"{rel}: frontmatter description contains a colon-space, the yaml.safe_load trap "
        "(memory `skill-frontmatter-no-colon-space`) - use an em-dash or a comma"
    )


@pytest.mark.parametrize("rel", OWNED_SURFACES)
def test_body_opens_with_an_h1(plugin_root: Path, rel: str) -> None:
    body = _body(plugin_root, rel)
    first = next((ln for ln in body.splitlines() if ln.strip()), "")
    assert first.startswith("# "), f"{rel}: body must open with an H1, got {first!r}"


# --------------------------------------------------------------------------- #
# 2.1 - intuition-map-lifecycle: three verbs, the engine, the asymmetry
# --------------------------------------------------------------------------- #

LIFECYCLE_VERBS = ("ensure", "grow", "bug-path-upsert")


@pytest.mark.parametrize("verb", LIFECYCLE_VERBS)
def test_lifecycle_names_each_verb_in_its_own_section(plugin_root: Path, verb: str) -> None:
    body = _body(plugin_root, LIFECYCLE_SKILL)
    assert f"## Verb — `{verb}`" in body or f"## Verb - `{verb}`" in body, (
        f"intuition-map-lifecycle must carry a dedicated section for the `{verb}` verb"
    )


def test_lifecycle_ensure_documents_both_contexts(plugin_root: Path) -> None:
    """Pipeline context dispatches the intuiter; ad-hoc runs the same rubric inline
    and surfaces low/unknown items as the SAME single numbered-list bulk-verify."""
    section = _section(_body(plugin_root, LIFECYCLE_SKILL), "## Verb — `ensure`")
    assert "interaction-intuiter" in section, "ensure must name the dispatched agent"
    assert "intake-and-mapping" in section, "ensure must anchor the pipeline path"
    assert "ad-hoc" in section.lower(), "ensure must document the ad-hoc context"
    assert "inline" in section.lower(), "ensure must state the ad-hoc rubric runs inline"
    low = section.lower()
    assert "bulk-verify" in low, "ensure must name the bulk-verify gate"
    assert "numbered list" in low, "the ad-hoc bulk-verify is the SAME single numbered list"
    assert "low" in low and "unknown" in low, "ensure must name the surfaced confidences"


def test_lifecycle_ensure_never_authors_against_a_missing_map(plugin_root: Path) -> None:
    """Held as ONE claim, not two loose words - `never` in one sentence and
    `missing map` in another says nothing."""
    section = _section(_body(plugin_root, LIFECYCLE_SKILL), "## Verb — `ensure`")
    assert _has_sentence_with(section, "missing map", "blocking") or _has_sentence_with(
        section, "never", "missing map"
    ), "ensure must state, in one sentence, that a missing map BLOCKS authoring"


def test_lifecycle_grow_upserts_confirmed_user_flow_entries(plugin_root: Path) -> None:
    section = _section(_body(plugin_root, LIFECYCLE_SKILL), "## Verb — `grow`")
    for token in ("user_verdict", "confirmed", "source", "user-flow", "high"):
        assert token in section, f"grow must document `{token}` in the upserted entry shape"


def test_lifecycle_grow_bypasses_bulk_verify_and_says_why(plugin_root: Path) -> None:
    """D2 - the asymmetry with the Phase -1D gate is deliberate and must be explicit."""
    section = _section(_body(plugin_root, LIFECYCLE_SKILL), "## Verb — `grow`")
    flat = _flat(section)
    assert "no bulk-verify" in flat or "bypass" in flat or "without a bulk-verify" in flat, (
        "grow must state it does NOT take a bulk-verify round-trip"
    )
    assert "is the confirmation" in flat, (
        "grow must state the user specifying the flow IS the confirmation"
    )
    # The asymmetry must be NAMED as deliberate in one sentence - the word alone
    # floating anywhere in the section is not the claim D2 requires.
    assert _has_sentence_with(section, "asymmetry", "deliberate") or _has_sentence_with(
        section, "asymmetry", "intentional"
    ) or _has_sentence_with(section, "asymmetry", "by design"), (
        "the -1D asymmetry must be named AND called deliberate in the same sentence"
    )


def test_lifecycle_grow_contradiction_never_silently_overwrites(plugin_root: Path) -> None:
    section = _section(_body(plugin_root, LIFECYCLE_SKILL), "## Verb — `grow`")
    flat = _flat(section)
    assert "contradict" in flat, "grow must handle contradiction with a confirmed entry"
    # The prohibition must read as ONE contiguous claim. `never` in one sentence and
    # `overwrite` in another is vocabulary, not a rule.
    assert "never silently overwrite" in flat or "never a silent overwrite" in flat, (
        "grow must forbid the silent overwrite in so many words"
    )
    assert "both readings" in flat, (
        "the targeted question must name BOTH readings (the existing one and the new one)"
    )
    assert _has_sentence_with(section, "one", "question"), (
        "the contradiction surfaces exactly ONE targeted question"
    )


def test_grow_contradiction_body_states_non_modification(plugin_root: Path) -> None:
    """Escapes M14/M19 - the rule was SOFTENED, then INVERTED, with the heading kept.

    The prohibition pin matched the bolded lead sentence, so a body that said the
    opposite underneath it passed. Hold the operative claim: the EXISTING entry is
    left unmodified.
    """
    section = _section(_body(plugin_root, LIFECYCLE_SKILL), "## Verb — `grow`")
    assert _has_sentence_with(section, "existing entry", "unmodified") or _has_sentence_with(
        section, "existing entry", "left"
    ), "the contradiction body must state the EXISTING entry is left unmodified"
    flat = _flat(section)
    for inversion in ("the newer reading wins", "last-write-wins is", "the new entry replaces",
                      "overwrites the existing entry", "the grown entry wins"):
        assert inversion not in flat, (
            f"grow's contradiction body states an INVERSION of the rule ({inversion!r})"
        )
    assert "last-write-wins" in flat, (
        "the body must explicitly rule out last-write-wins, not merely omit it"
    )


def test_hard_rules_do_not_contradict_the_caller_marks_contract(plugin_root: Path) -> None:
    """adv-R1 / adv-R5 - the Hard-rules bullet still said the ENGINE judges confidence.

    The amended body says in as many words that the engine does NOT score confidence
    and that an unmarked extraction is taken as certain. The hard rule said the
    opposite, and Hard rules is the section an agent treats as normative - so the
    file contradicted itself on its own central safety rule.

    It was also literally false: verified against the engine, an UNMARKED element
    absent from the map gets an id derived (the function is named derive_element_id)
    and lands confirmed/high. This pin holds the FALSE clause out by name, which is
    the adversary's R5 regression-thinness point - restoring the original sentence
    must not stay green.
    """
    body = _body(plugin_root, LIFECYCLE_SKILL)
    rules = _section(body, "## Hard rules (non-negotiable)")

    # adv round-3 T1: this guard was SECTION-scoped, so the identical false claim
    # could be restored in the grow BODY with every pin green - the adversary
    # reproduced exactly that (102 passed while the body asserted the engine scores
    # confidence and the hard rule three sections down said it does not). The claim
    # is false ANYWHERE in the file, so the guard is file-scoped now. All four
    # phrases are verified at 0 occurrences in the shipped text.
    flat = _flat(body)

    for false_clause in (
        "an extraction the engine cannot bind with confidence",
        "the engine cannot bind with confidence",
        "grow never invents an `element_id`",
        "grow never invents an element_id",
        # the grow BODY's original lead-in, which T1's mutation restored
        "records an extraction confidence",
        "the engine records an extraction confidence per element",
    ):
        assert _flat(false_clause) not in flat, (
            f"the file reasserts the FALSE clause {false_clause!r} somewhere - the "
            "engine does not score confidence, and it DOES derive an element_id on "
            "the unmarked path (derive_element_id). The caller supplies the mark; "
            "the engine enforces the routing. This guard is file-scoped precisely "
            "because a section-scoped one let the claim return in the grow body."
        )

    assert _has_sentence_with(rules, "mark", "ambiguous") or _has_sentence_with(
        rules, "marked", "ambiguous"
    ), "the hard rule must state the caller-marks contract it replaced the false clause with"


def test_grow_documents_caller_marked_ambiguity(plugin_root: Path) -> None:
    """F1 alignment - the amended spec's ambiguity routing.

    The AUTHORING AGENT marks an uncertain extraction; a marked element routes to a
    question and is NEVER upserted. The engine enforces the routing; the agent
    supplies the mark. The earlier text implied the engine judged confidence itself.
    """
    section = _section(_body(plugin_root, LIFECYCLE_SKILL), "## Verb — `grow`")
    flat = _flat(section)
    assert "ambigu" in flat, "grow must document the ambiguity path"
    assert _has_sentence_with(section, "mark", "ambiguous") or _has_sentence_with(
        section, "marks", "ambiguous"
    ), "the text must say the CALLER / authoring agent MARKS the extraction ambiguous"
    assert _has_sentence_with(section, "ambiguous", "question") or _has_sentence_with(
        section, "marked", "question"
    ), "a marked-ambiguous element must route to a question"
    assert _has_sentence_with(section, "never", "upsert") or _has_sentence_with(
        section, "no entry", "upserted"
    ), "a marked-ambiguous element is NEVER upserted"


def _load_lifecycle_engine(plugin_root: Path):
    import importlib.util
    path = plugin_root / "scripts" / "intuition_lifecycle" / "engine.py"
    if not path.exists():
        pytest.skip("intuition-lifecycle engine not present yet (task 1.2)")
    spec = importlib.util.spec_from_file_location("_il_engine_keys", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


def test_grow_names_the_ambiguity_payload_key(plugin_root: Path) -> None:
    """adv-R3 - the whole caller-marks contract hinges on a key named NOWHERE.

    The prose said the caller "marks an extraction ambiguous" twice without ever
    naming the payload key that does it, and `cli.py` mentions it zero times - so
    an agent driving the CLI has no way to find it. The engine reads
    `spec.get("ambiguous")`, which is FALSY WHEN ABSENT, so the failure is silent:
    every extraction is taken as certain and the guard never fires.

    The adversary's N13 proved the gap - keeping every word of the prose while
    naming the WRONG key (`ambiguity: true`) passed 94/94.
    """
    section = _section(_body(plugin_root, LIFECYCLE_SKILL), "## Verb — `grow`")
    assert "`ambiguous: true`" in section, (
        "the grow contract must name the ambiguity payload key VERBATIM - prose "
        "telling an agent to 'mark' an extraction without naming the key it sets "
        "is unactionable, and the engine's absent-key default is silent"
    )
    assert "extraction_confidence" in section, (
        "the engine accepts a second spelling (`extraction_confidence` of low/unknown); "
        "a contract that names only one leaves the other undiscoverable"
    )


def test_documented_ambiguity_key_is_the_one_the_engine_reads(plugin_root: Path) -> None:
    """The key the CONTRACT names is fed to the ENGINE, both directions.

    Same engine-as-oracle technique as the regression_refs shape pin: a documented
    key that the engine ignores is worse than no documentation, because it reads as
    supported. Both polarities are held - the documented key MARKS, and its absence
    does NOT (which is the by-design normal-upsert path).
    """
    engine = _load_lifecycle_engine(plugin_root)
    section = _section(_body(plugin_root, LIFECYCLE_SKILL), "## Verb — `grow`")

    import re
    keys = set(re.findall(r"`([a-z_]+): true`", section))
    assert keys, "the grow section names no `<key>: true` ambiguity marker"

    raw = getattr(engine, "_normalize_flow_element", None)
    if raw is None:
        pytest.skip("could not resolve the engine's flow-element normalizer")

    def normalize(spec):
        return raw(spec, "e2e/probe.spec.ts")

    base = {"element_id": "probe", "route": "/x", "element_label": "Probe"}
    # Absent => NOT ambiguous. This is the by-design normal-upsert path.
    assert normalize(dict(base))["ambiguous"] is False, (
        "the engine must treat an ABSENT marker as not-ambiguous - that is the "
        "documented by-design normal path"
    )
    # Every key the contract documents must actually mark.
    for key in sorted(keys):
        probe = dict(base)
        probe[key] = True
        assert normalize(probe)["ambiguous"] is True, (
            f"the contract documents `{key}: true` as the ambiguity marker, but the "
            f"engine does not read it - an agent following the text would mark "
            f"nothing and every extraction would be taken as certain"
        )
    # The second spelling the contract mentions must work too.
    if "extraction_confidence" in section:
        for value in ("low", "unknown"):
            probe = dict(base)
            probe["extraction_confidence"] = value
            assert normalize(probe)["ambiguous"] is True, (
                f"the contract names `extraction_confidence: {value}` as an equivalent "
                f"mark, but the engine does not honour it"
            )


def test_grow_states_the_absent_marker_semantic(plugin_root: Path) -> None:
    """Silent absence is BY DESIGN and engine-pinned, so the contract must say so."""
    section = _section(_body(plugin_root, LIFECYCLE_SKILL), "## Verb — `grow`")
    flat = _flat(section)
    # The claim is specifically about the KEY's absence being a SILENT default -
    # not the softer "an unmarked extraction is taken as certain", which survives
    # deleting the semantic entirely (the R3c escape).
    assert "silent default" in flat or "falsy when it is missing" in flat or (
        "reads the key" in flat and "missing" in flat
    ), (
        "the contract must state that the KEY's ABSENCE is a silent default - an "
        "agent that does not know this cannot know the guard failed to fire, which "
        "is the whole failure mode the caller-marks contract depends on"
    )
    assert _has_sentence_with(section, "by design", "absence") or _has_sentence_with(
        section, "silent default", "design"
    ), "the silent default must be named as DELIBERATE, so it is not read as a bug to route around"


def test_bug_path_upsert_carries_the_same_contradiction_guard(plugin_root: Path) -> None:
    """F6 alignment - the guard must be STATED, not merely claimed to be the same.

    The adversary proved the old text asserted a sameness that was not true of the
    engine. The amended spec makes bug-path carry grow's guard, so the text states
    the guard itself rather than pointing at grow and hoping.
    """
    section = _section(_body(plugin_root, LIFECYCLE_SKILL), "## Verb — `bug-path-upsert`")
    flat = _flat(section)
    assert "contradict" in flat, "bug-path-upsert must handle the contradiction case"
    assert "never silently overwrite" in flat or "never a silent overwrite" in flat, (
        "bug-path-upsert must state the no-silent-overwrite guard IN ITS OWN WORDS"
    )
    assert _has_sentence_with(section, "one", "question") or _has_sentence_with(
        section, "targeted question", "both"
    ), "the contradiction surfaces one targeted question here too"


def test_lifecycle_bug_path_upsert_carries_provenance_and_refs(plugin_root: Path) -> None:
    """Each assertion holds the CLAIM its message makes, not a loose token.

    The first cut asserted four bare substrings while the messages described
    relationships ("must SET source: bug-path", "regression_refs must NAME the
    covering debug-flow test"). A section mentioning `bug-path` anywhere satisfied
    a message about what `source` is set to, and `"sr" in low` matched "users".
    """
    section = _section(_body(plugin_root, LIFECYCLE_SKILL), "## Verb — `bug-path-upsert`")
    assert _has_sentence_with(section, "source", "bug-path"), (
        "bug-path-upsert must say, in one sentence, that it sets `source` to `bug-path`"
    )
    assert _has_sentence_with(section, "regression_refs", "debug-flow"), (
        "the covering debug-flow test must be named as what regression_refs points at, "
        "in the same sentence - not merely mentioned somewhere in the section"
    )
    assert _has_sentence_with(section, "regression_refs", "sr") or _has_sentence_with(
        section, "regression_refs", "bug slug"
    ), "regression_refs must be tied to the SR path / bug slug in one sentence"


def test_lifecycle_names_the_deterministic_engine(plugin_root: Path) -> None:
    """The skill is the contract; the engine is the mechanism (design D8)."""
    body = _body(plugin_root, LIFECYCLE_SKILL)
    assert "scripts/intuition_lifecycle/" in body, (
        "the lifecycle skill must name its deterministic engine package"
    )
    assert _has_sentence_with(body, "contract", "mechanism"), (
        "the skill-is-contract / engine-is-mechanism split must be ONE stated "
        "relationship, not the two words appearing in unrelated sentences"
    )


def test_lifecycle_states_the_additive_schema_rule(plugin_root: Path) -> None:
    body = _body(plugin_root, LIFECYCLE_SKILL)
    assert "source" in body and "regression_refs" in body
    low = _flat(body)
    assert "additive" in low, "the schema addition must be called additive"
    assert "no migration" in low, "the skill must state no migration of existing maps is required"
    assert _has_sentence_with(body, "intuiter", "regression_refs") or _has_sentence_with(
        body, "absent", "intuiter"
    ) or _has_sentence_with(body, "neither", "intuiter"), (
        "an entry lacking the fields must be documented as READING intuiter-produced, "
        "in one sentence - the bare word `intuiter` appearing somewhere is not that claim"
    )


# --------------------------------------------------------------------------- #
# 2.2 - interaction-intuition: the additive section
# --------------------------------------------------------------------------- #

INTUITION_ADDITIVE_HEADER = "## Provenance fields (additive)"


def test_intuition_carries_the_additive_provenance_section(plugin_root: Path) -> None:
    body = _body(plugin_root, INTUITION_SKILL)
    assert INTUITION_ADDITIVE_HEADER in body, (
        "interaction-intuition must document the two new per-element provenance fields"
    )


@pytest.mark.parametrize("value", ("intuiter", "user-flow", "bug-path"))
def test_intuition_names_every_source_enum_value(plugin_root: Path, value: str) -> None:
    section = _section(_body(plugin_root, INTUITION_SKILL), INTUITION_ADDITIVE_HEADER)
    assert value in section, f"the `source` enum must name `{value}`"


def test_intuition_documents_backward_compatibility(plugin_root: Path) -> None:
    section = _section(_body(plugin_root, INTUITION_SKILL), INTUITION_ADDITIVE_HEADER)
    assert "regression_refs" in section
    # Both halves of D3 held as claims: absence READS AS intuiter (one sentence),
    # and no migration is required (a contiguous phrase, not two stray words).
    assert _has_sentence_with(section, "absent", "intuiter") or _has_sentence_with(
        section, "neither field", "intuiter"
    ), "the section must say, in one sentence, that an entry lacking the fields reads as intuiter"
    assert "no migration" in _flat(section), (
        "backward compatibility means no migration of existing maps is required"
    )


def test_intuition_names_the_lifecycle_as_sole_writer(plugin_root: Path) -> None:
    section = _section(_body(plugin_root, INTUITION_SKILL), INTUITION_ADDITIVE_HEADER)
    assert "intuition-map-lifecycle" in section, "the sister skill must be named"
    low = section.lower()
    assert "sole writer" in low or "only writer" in low, (
        "the lifecycle skill must be named the SOLE writer of non-intuiter entries"
    )


def test_intuition_existing_rules_are_untouched(plugin_root: Path) -> None:
    """2.2 is additive - every pre-existing section of the skill must survive."""
    body = _body(plugin_root, INTUITION_SKILL)
    for header in (
        "## Inputs",
        "## Outputs",
        "## Confidence rubric",
        "## Per-element intuition",
        "## Artifact schema",
        "## Escalate-don't-guess",
        "## Domain-gate carve-out",
        "## Hard rules (non-negotiable)",
        "## Anti-patterns to reject",
        "## Relationship to other skills",
    ):
        assert header in body, f"interaction-intuition lost a pre-existing section: {header}"


# --------------------------------------------------------------------------- #
# 2.3 - playwright-suite-builder: P0-P9 + the named reuse anchors
# --------------------------------------------------------------------------- #

P_PHASES = tuple(f"## Phase P{n}" for n in range(10))


@pytest.mark.parametrize("phase", P_PHASES)
def test_suite_builder_carries_every_p_phase(plugin_root: Path, phase: str) -> None:
    body = _body(plugin_root, SUITE_SKILL)
    assert phase in body, f"playwright-suite-builder missing {phase}"


def test_p0_documents_the_e2e_dir_resolution_ladder(plugin_root: Path) -> None:
    """User decision - follow the target repo's convention; create e2e/ only as a last resort."""
    section = _section(_body(plugin_root, SUITE_SKILL), "## Phase P0")
    assert "testDir" in section, "the ladder's first rung is the Playwright config testDir"
    assert "e2e/" in section, "the ladder must name the created-only-when-none-exists e2e/ dir"
    low = section.lower()
    assert "only when none exists" in low, (
        "P0 must state a fresh e2e/ is created ONLY when no conventional dir exists"
    )
    assert "convention" in low, "P0 must state the suite follows the target repo's convention"


def test_p1_reconciles_the_inventory_against_the_manifest(plugin_root: Path) -> None:
    section = _section(_body(plugin_root, SUITE_SKILL), "## Phase P1")
    assert "suite-manifest.json" in section, "P1 must reconcile against the manifest"
    assert "pre-existing" in section, "tests the builder did not author take source: pre-existing"


def test_p2_uses_frontend_impact_detection_for_freshness(plugin_root: Path) -> None:
    section = _section(_body(plugin_root, SUITE_SKILL), "## Phase P2")
    assert "hooks/frontend_impact.py" in section, (
        "P2 must reuse the existing frontend-change detection, not reimplement it"
    )
    assert "last_intuited" in section, "P2 compares the map's last_intuited timestamp"
    assert "intuition-map-lifecycle" in section, "a stale map refreshes via the lifecycle skill"
    low = section.lower()
    assert "bulk-verify" in low, "new low/unknown items gate on bulk-verify before authoring"


def test_p3_dispatches_the_existing_checkers_and_never_duplicates_them(plugin_root: Path) -> None:
    """D5 - the two checkers already exist; P3 dispatches them by name."""
    section = _section(_body(plugin_root, SUITE_SKILL), "## Phase P3")
    assert "test-completeness-verifier" in section
    assert "interaction-completeness" in section
    low = section.lower()
    assert "dispatch" in low, "P3 must DISPATCH the checkers"
    assert "never" in low and ("duplicat" in low or "re-implement" in low or "reimplement" in low), (
        "P3 must state the checkers are never duplicated"
    )


def test_p4_gap_analysis_uses_phase_c_math_and_escalates_unknown_personas(plugin_root: Path) -> None:
    section = _section(_body(plugin_root, SUITE_SKILL), "## Phase P4")
    assert "covers_elements" in section, "coverage is manifest covers_elements vs the confirmed map"
    assert "playwright-user-flows" in section, "the coverage math is Phase C's, applied suite-wide"
    assert "Phase C" in section
    low = section.lower()
    assert "persona" in low
    assert "escalat" in low and "never guess" in low, (
        "an unknown persona escalates per Step 0 - it is NEVER guessed"
    )


def test_p5_gap_fill_uses_the_full_authoring_discipline(plugin_root: Path) -> None:
    section = _section(_body(plugin_root, SUITE_SKILL), "## Phase P5")
    assert "playwright-user-flows" in section
    low = section.lower()
    assert "full" in low, "gap-fill authoring is the FULL discipline, not a reduced form"
    assert "step 0" in low, "Step 0 citations-or-escalation ride along"


def test_p6_registers_debug_flows_with_live_provenance(plugin_root: Path) -> None:
    section = _section(_body(plugin_root, SUITE_SKILL), "## Phase P6")
    assert "debug-flow" in section
    # A text pin cannot check that an origin_ref is LIVE at runtime - that is
    # verify-suite-manifest's job. What it CAN hold is that P6 states the
    # liveness requirement, so the message and the assertion now match.
    assert _has_sentence_with(section, "origin_ref", "live"), (
        "P6 must state that a registered debug-flow carries a LIVE origin_ref "
        "(runtime liveness is verify-suite-manifest's check, not this pin's)"
    )
    assert "bug-path-upsert" in section, "P6 also feeds the map via the lifecycle verb"


def test_p7_groups_by_persona_and_defines_both_projects(plugin_root: Path) -> None:
    section = _section(_body(plugin_root, SUITE_SKILL), "## Phase P7")
    assert "personas/" in section
    assert "debug-flows/" in section
    assert "prod-checks/" in section
    assert "`dev`" in section and "`prod`" in section, (
        "P7 must define BOTH Playwright projects by name"
    )


def test_p8_binds_classifier_verdicts_and_defaults_prod_deny(plugin_root: Path) -> None:
    section = _section(_body(plugin_root, SUITE_SKILL), "## Phase P8")
    assert "test-prod-safety-classifier" in section, "P8 reuses the existing classifier"
    assert _has_sentence_with(section, "mutates_data", "manifest") or _has_sentence_with(
        section, "safety", "manifest"
    ), "P8 must say the classifier verdict is recorded INTO the manifest per entry"
    assert "mutates_data" in section and "safety" in section, (
        "both recorded fields must be named"
    )
    assert "prod_exceptions" in section
    # `"it-" in section` matched any hyphenated word containing "it-" (split-,
    # commit-, ...). Hold the literal convention token instead.
    assert "it-<prefix>" in section, (
        "a prod exception needs the it-<prefix> test-only data tag, named literally"
    )
    low = section.lower()
    assert "default-deny" in low, "the prod project is default-deny"
    assert "teardown" in low, "a prod exception needs mandatory teardown"
    assert "authoriz" in low, "a prod exception needs the user's recorded authorization"


def test_p9_writes_an_engine_validated_manifest(plugin_root: Path) -> None:
    section = _section(_body(plugin_root, SUITE_SKILL), "## Phase P9")
    assert "suite-manifest.json" in section
    assert "scripts/playwright_suite/manifest.py" in section, (
        "P9 must name the deterministic validation engine"
    )
    low = section.lower()
    assert "report" in low, "P9 emits the run report"


def test_p9_documented_cli_matches_the_real_engine(plugin_root: Path) -> None:
    """Every flag P9 tells an agent to run must be a flag the engine accepts.

    Prose naming a real script with invented flags reads as verified and is not.
    The first cut of P9 documented `--manifest` where the engine takes `--json`,
    and no cross-reference lint catches that - the PATH resolved, so the file was
    green while the instruction was wrong. This pin is the check that would have.
    """
    engine = plugin_root / "scripts" / "playwright_suite" / "manifest.py"
    if not engine.exists():
        pytest.skip("manifest engine not present yet (task 1.4)")

    section = _section(_body(plugin_root, SUITE_SKILL), "## Phase P9")
    invocations = [
        ln for ln in section.splitlines()
        if "manifest.py" in ln and ("validate" in ln or "verify" in ln)
    ]
    assert invocations, "P9 must show how to invoke the engine"

    # Negative control: if _engine_flags returned an over-broad set (help parsing
    # broke, say), `unknown` would always be empty and every invocation would pass
    # regardless of what it documented. Prove a bogus flag IS rejected first.
    for sub in ("validate", "verify"):
        assert "--definitely-not-a-real-flag" not in _engine_flags(engine, sub), (
            f"_engine_flags({sub}) reports a flag the engine cannot have - the help "
            "parse is over-broad, so this pin's pass would be vacuous"
        )

    for line in invocations:
        tokens = line.split()
        sub = next((t for t in tokens if t in ("validate", "verify")), None)
        assert sub is not None, f"P9 invocation names no subcommand: {line.strip()}"
        flags = {t.split("=")[0] for t in tokens if t.startswith("--")}
        accepted = _engine_flags(engine, sub)
        unknown = flags - accepted
        assert not unknown, (
            f"P9 documents flag(s) {sorted(unknown)} for `{sub}`, which "
            f"scripts/playwright_suite/manifest.py does not accept "
            f"(it accepts {sorted(accepted)}) - fix the skill text to match the engine"
        )


def _engine_flags(engine: Path, subcommand: str) -> set[str]:
    """Option strings the engine's REAL parser accepts, read from its own --help.

    Asking argparse rather than reading the source keeps this honest when the
    engine changes shape.
    """
    import re
    import subprocess
    import sys

    proc = subprocess.run(
        [sys.executable, str(engine), subcommand, "--help"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    help_text = (proc.stdout or "") + (proc.stderr or "")
    assert proc.returncode == 0 and help_text.strip(), (
        f"could not read `{subcommand} --help` from the manifest engine: {help_text[:200]}"
    )
    return set(re.findall(r"(--[A-Za-z0-9][A-Za-z0-9-]*)", help_text))


REGRESSION_REF_SURFACES = (LIFECYCLE_SKILL, INTUITION_SKILL)


def _documented_ref_keys(plugin_root: Path, rel: str) -> list[str]:
    """The key names the skill's `regression_refs[]` bullet documents."""
    import re
    body = _body(plugin_root, rel)
    m = re.search(r"`regression_refs\[\]`\*{0,2}\s*[—-]\s*list of `\{([^}]*)\}`", _flat(body))
    assert m, f"{rel}: no `regression_refs[]` bullet naming an object shape"
    return [k.strip() for k in m.group(1).split(",") if k.strip()]


@pytest.mark.parametrize("rel", REGRESSION_REF_SURFACES)
def test_documented_regression_ref_shape_matches_the_engine(plugin_root: Path, rel: str) -> None:
    """XL-1 - the documented key names must be the ones the engine ACCEPTS.

    Both skills documented `{test_path, origin_ref}` while the engine writes and
    validates `{test, ref}` - so an agent following the skill text would produce
    entries the validator rejects as `malformed-regression-ref`. Nothing caught it
    because the older pins only asserted the SUBSTRING `regression_refs` appeared.

    This pin runs the ENGINE'S OWN validator over the key names the skill's
    `regression_refs[]` bullet documents. Scope, precisely: it holds THAT bullet's
    key shape against the engine and nothing wider - it does not check the rest of
    the prose, other fields, or that the skill describes the verbs correctly. The
    manifest's separate `origin_ref` field is a DIFFERENT thing and is deliberately
    out of scope here.
    """
    engine_path = plugin_root / "scripts" / "intuition_lifecycle" / "engine.py"
    if not engine_path.exists():
        pytest.skip("intuition-lifecycle engine not present yet (task 1.2)")

    import importlib.util
    spec = importlib.util.spec_from_file_location("_il_engine_pins", engine_path)
    engine = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(engine)  # type: ignore[union-attr]

    # Negative control FIRST: if the validator accepted anything, this pin would
    # pass vacuously and its green would mean nothing. Prove it discriminates
    # before trusting it to judge the documented shape.
    try:
        engine._normalize_refs([{"not_a_real_key": "x"}])
    except ValueError:
        pass
    else:
        raise AssertionError(
            "the engine's _normalize_refs accepted a bogus key shape, so this pin "
            "cannot distinguish a correct skill text from a wrong one - the check "
            "must be able to fail before its pass is evidence of anything"
        )

    keys = _documented_ref_keys(plugin_root, rel)
    probe = {k: "x" for k in keys}
    try:
        engine._normalize_refs([probe])
    except ValueError as exc:
        raise AssertionError(
            f"{rel} documents regression_refs entries as {{{', '.join(keys)}}}, which "
            f"scripts/intuition_lifecycle/engine.py REJECTS: {exc}. The engine's shape "
            f"is pinned by its own suite - fix the skill text, not the engine."
        ) from None


# --------------------------------------------------------------------------- #
# The manifest contract, held against the ENGINE rather than against prose.
#
# The adversarial battery escaped 11 of 33 mutations, and one cluster dominated:
# corrupting the documented `kind`/`source` enums, deleting the origin_ref row,
# moving the manifest path, and dropping the section header all went unnoticed,
# because the pins asserted that TOKENS appeared rather than that the CONTRACT was
# right. Reading the field table and checking it against manifest.py's own
# constants closes the whole cluster at once and cannot drift.
# --------------------------------------------------------------------------- #

def _load_manifest_engine(plugin_root: Path):
    import importlib.util
    path = plugin_root / "scripts" / "playwright_suite" / "manifest.py"
    if not path.exists():
        pytest.skip("manifest engine not present yet (task 1.4)")
    spec = importlib.util.spec_from_file_location("_ps_manifest_pins", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


def _manifest_section(plugin_root: Path) -> str:
    return _section(_body(plugin_root, SUITE_SKILL), "## The suite manifest — the durable registry")


def _documented_backticked(section: str) -> set[str]:
    import re
    return set(re.findall(r"`([A-Za-z_][A-Za-z0-9_]*)(?:\[\])?`", section))


def test_documented_manifest_top_level_fields_match_the_engine(plugin_root: Path) -> None:
    """Every REQUIRED top-level field the engine enforces must be named in the text.

    F2: `tests` was required by the engine and named nowhere in the skill, so a
    manifest built from the contract failed validation with nothing in the text to
    explain why.
    """
    engine = _load_manifest_engine(plugin_root)
    section = _manifest_section(plugin_root)
    named = _documented_backticked(section)
    missing = [f for f in engine.REQUIRED_TOP_LEVEL_FIELDS if f not in named]
    assert not missing, (
        f"the manifest contract omits required top-level field(s) {missing} that "
        f"scripts/playwright_suite/manifest.py enforces - a manifest authored from "
        f"this text is rejected by the engine"
    )


def test_documented_manifest_per_test_fields_match_the_engine(plugin_root: Path) -> None:
    """Read the TABLE, not the whole section.

    Regression I caused myself: adding a prose paragraph that mentions
    `origin_ref` and `mutates_data` in backticks meant deleting the actual table
    ROW no longer failed this pin - the adversary's M23 mutation escaped again on
    a pin that had previously caught it. A field's presence in explanatory prose is
    not the same as its presence in the contract table an author reads off.
    """
    engine = _load_manifest_engine(plugin_root)
    section = _manifest_section(plugin_root)
    rows = [ln for ln in section.splitlines() if ln.strip().startswith("| `")]
    assert rows, "the manifest contract must carry a per-test field table"
    named = set()
    for row in rows:
        first_cell = row.split("|")[1]
        named |= _documented_backticked(first_cell)
    missing = [f for f in engine.REQUIRED_TEST_FIELDS if f not in named]
    assert not missing, (
        f"the per-test entry TABLE omits required field(s) {missing} the engine "
        f"enforces (mentioning them in surrounding prose does not count - the table "
        f"is what an author reads the contract off)"
    )


@pytest.mark.parametrize("attr", ("KINDS", "SOURCES", "SAFETY_LEVELS"))
def test_documented_manifest_enums_match_the_engine(plugin_root: Path, attr: str) -> None:
    """Corrupting a documented enum value must not pass.

    Escapes M27/M28 - the `kind` and `source` enums were corrupted and every pin
    stayed green, because nothing compared them to the engine's own tuples.
    """
    engine = _load_manifest_engine(plugin_root)
    section = _manifest_section(plugin_root)
    values = getattr(engine, attr)
    missing = [v for v in values if f"`{v}`" not in section]
    assert not missing, (
        f"the manifest contract's enum documentation is missing {missing} from "
        f"manifest.py's {attr} = {values} - a corrupted or stale enum in the text "
        f"sends an agent to write entries the engine rejects"
    )


def test_a_manifest_built_from_the_documented_contract_validates_clean(
    plugin_root: Path, tmp_path: Path
) -> None:
    """The end-to-end proof: author a manifest from the TEXT, run the REAL engine.

    A field list can be individually correct and still incomplete. This builds a
    manifest using exactly the documented top-level fields and one entry using
    exactly the documented per-test fields, then validates it through the engine.
    """
    engine = _load_manifest_engine(plugin_root)
    section = _manifest_section(plugin_root)
    named = _documented_backticked(section)

    # Only fields the TEXT documents may be used - that is the point.
    assert set(engine.REQUIRED_TOP_LEVEL_FIELDS) <= named
    assert set(engine.REQUIRED_TEST_FIELDS) <= named

    manifest = {
        "schema_version": 1,
        "e2e_dir": "e2e",
        "personas": ["shopper"],
        "last_built": "2026-08-26T00:00:00Z",
        "prod_exceptions": [],
        "tests": [{
            "file": "e2e/personas/shopper/browse.spec.ts",
            "test_names": ["shopper browses the catalog"],
            "persona": "shopper",
            "kind": "journey",
            "source": "gap-fill",
            "covers_elements": ["catalog__grid__item__1"],
            "covers_routes": ["/catalog"],
            "safety": "dev",
            "mutates_data": False,
            "origin_ref": None,
        }],
    }
    findings = engine.validate_manifest(manifest)
    blocking = [f for f in findings if f.get("severity") == "error"]
    assert not blocking, (
        "a manifest authored from the documented contract does NOT validate clean "
        f"through scripts/playwright_suite/manifest.py: {blocking}"
    )


def test_manifest_contract_states_fields_are_strings_not_merely_present(
    plugin_root: Path,
) -> None:
    """The engine rejects falsy non-strings; the contract must say so.

    Not pedantry, and not hypothetical: a `teardown: false` once passed a
    present-and-not-blank check - `false` is neither None nor "" - and authorized a
    production-mutating test. The JSON looks like it says something; the validator
    read it as saying nothing. An author reading "these fields are present" writes
    `false` and is genuinely surprised.

    Held BOTH ways: the contract states it, and the engine is confirmed to enforce
    it, so the sentence cannot become a promise nothing keeps.
    """
    section = _manifest_section(plugin_root)
    flat = _flat(section)
    assert "string" in flat, "the contract must state the fields are STRINGS"
    assert _has_sentence_with(section, "falsy", "absent") or _has_sentence_with(
        section, "false", "absent"
    ), (
        "the contract must state that a falsy non-string is treated as ABSENT rather "
        "than as a value - that is the distinction an author gets wrong"
    )

    # And the engine really does refuse it, so the contract is not overclaiming.
    engine = _load_manifest_engine(plugin_root)
    bad = {
        "schema_version": 1, "e2e_dir": "e2e", "personas": ["p"],
        "last_built": "2026-08-26T00:00:00Z", "prod_exceptions": [],
        "tests": [{
            "file": False, "test_names": ["t"], "persona": "p", "kind": "journey",
            "source": "gap-fill", "covers_elements": [], "covers_routes": [],
            "safety": "dev", "mutates_data": False, "origin_ref": None,
        }],
    }
    blocking = [f for f in engine.validate_manifest(bad) if f.get("severity") == "error"]
    assert blocking, (
        "the contract says a falsy non-string blocks, but the engine accepted "
        "`file: False` - the claim would be a promise nothing keeps"
    )


def test_manifest_section_names_its_committed_path(plugin_root: Path) -> None:
    """Escape M29 - the manifest path was moved and nothing noticed."""
    section = _manifest_section(plugin_root)
    assert "<e2e-dir>/suite-manifest.json" in section, (
        "the contract must name the manifest's exact committed location"
    )
    assert _has_sentence_with(section, "committed", "target repo"), (
        "the manifest lives COMMITTED in the target repo - that is what makes it "
        "durable and CI-runnable rather than run state"
    )


def test_intuition_source_enum_matches_the_lifecycle_engine(plugin_root: Path) -> None:
    """Escape M32 - interaction-intuition's `source` enum was corrupted unnoticed."""
    engine_path = plugin_root / "scripts" / "intuition_lifecycle" / "engine.py"
    if not engine_path.exists():
        pytest.skip("intuition-lifecycle engine not present yet (task 1.2)")
    import importlib.util
    spec = importlib.util.spec_from_file_location("_il_src_pins", engine_path)
    engine = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(engine)  # type: ignore[union-attr]

    values = None
    for attr in ("SOURCES", "VALID_SOURCES", "SOURCE_VALUES"):
        if hasattr(engine, attr):
            values = tuple(getattr(engine, attr))
            break
    if values is None:
        values = ("intuiter", "user-flow", "bug-path")

    section = _section(_body(plugin_root, INTUITION_SKILL), INTUITION_ADDITIVE_HEADER)

    # Hold the DECLARATION line, not merely "the values appear somewhere". The
    # adversary's M32 corrupted the `source` bullet to `auto`/`manual` while the
    # explanatory sentences below still name the real values, and a
    # values-appear-anywhere pin sailed straight past it.
    import re
    m = re.search(r"^- \*{0,2}`source`\*{0,2}\s*[—-]\s*one of ([^.]+)\.",
                  section, re.MULTILINE)
    assert m, (
        "interaction-intuition must declare the `source` enum as a `- `source` — "
        "one of ...` bullet so the declared set can be checked against the engine"
    )
    declared = set(re.findall(r"`([a-z][a-z-]*)`", m.group(1)))
    assert declared == set(values), (
        f"the declared `source` enum {sorted(declared)} does not match the engine's "
        f"{sorted(values)} - a corrupted declaration sends an agent to write entries "
        f"the engine rejects, even when the old values still appear in nearby prose"
    )


def test_p9_marks_the_run_complete(plugin_root: Path) -> None:
    """P9 carries a correctly-shaped run-continuity mark-complete step.

    Why it matters: playwright-suite-builder is registered in
    hooks/run_continuity.py's RUN_DRIVING_SKILLS, so every
    /architect-team:playwright-suite invocation engages the active-run marker,
    and a run-driving skill with no `--mark-complete` step can never release it
    (the v3.61.2 wedge class).

    What this pin ACTUALLY holds, precisely: the P9 section names the helper,
    carries `--mark-complete`, states the ordering contract, uses the polyglot
    invocation form, and runs from the workspace root. It does NOT read
    RUN_DRIVING_SKILLS and therefore does NOT verify the registration exists or
    that the two are bound - removing the registry entry leaves this pin green.
    The binding is held separately, next to the registry, by
    tests/test_playwright_suite_hooks.py. Saying otherwise here would be a
    message claiming more than the assertion tests.
    """
    section = _section(_body(plugin_root, SUITE_SKILL), "## Phase P9")
    assert "hooks/run_continuity.py" in section, (
        "P9 must invoke the run-continuity helper to release the active-run marker"
    )
    assert "--mark-complete" in section, "P9 must carry the --mark-complete invocation"
    flat = _flat(section)
    assert "last state action" in flat, (
        "mark-complete must be named the LAST state action of P9 - ordering is the "
        "contract (outputs land first, then the marker is released)"
    )
    # Polyglot invocation per the house cross-platform rule, mirroring ux-test U9.
    assert "python3" in section and "|| python " in section, (
        "the invocation must use the polyglot `python3 ... || python ...` form"
    )
    assert "workspace root" in flat, "the helper runs from the workspace root"


def test_p9_notes_routed_srs_are_their_own_runs(plugin_root: Path) -> None:
    """Mirrors ux-test U9's hand-off note - a routed SR must not block THIS run.

    Without it, an orchestrator reading P9 can conclude the suite run stays
    in-flight until every routed authenticity finding and gap escalation is
    resolved, which is the same wedge from the other direction.
    """
    section = _section(_body(plugin_root, SUITE_SKILL), "## Phase P9")
    flat = _flat(section)
    assert "own runs" in flat or "own markers" in flat, (
        "P9 must state that routed SRs are their OWN runs with their own markers"
    )
    assert _has_sentence_with(section, "marks complete", "its"), (
        "P9 must say the suite run marks complete when ITS phases close"
    )


def test_suite_builder_keeps_the_phase_marker_current(plugin_root: Path) -> None:
    """The observability half - `--set phase=... slug=...` at P-phase boundaries."""
    body = _body(plugin_root, SUITE_SKILL)
    assert "--set" in body, "the skill must name the --set phase/slug discipline"
    flat = _flat(body)
    assert "phase=" in flat and "slug=" in flat, (
        "the --set invocation must carry both phase and slug"
    )
    assert "phase boundaries" in flat, (
        "the marker is kept current AT PHASE BOUNDARIES, not once at the start"
    )


def test_p9_states_the_engine_exit_codes_correctly(plugin_root: Path) -> None:
    """Escape M30 - P9 stated the WRONG exit codes and nothing noticed."""
    section = _section(_body(plugin_root, SUITE_SKILL), "## Phase P9")
    flat = _flat(section)
    for code, meaning in (("0", "no blocking"), ("1", "blocking"), ("2", "could not be read")):
        assert f"**`{code}`**" in section or f"`{code}`" in section, (
            f"P9 must state exit code {code}"
        )
    assert _has_sentence_with(section, "0", "no blocking findings"), "exit 0 = no blocking findings"
    assert _has_sentence_with(section, "1", "blocking findings"), "exit 1 = blocking findings"
    assert "could not be read" in flat or "unreadable" in flat, (
        "exit 2 = the manifest could not be read"
    )


def test_p9_states_that_validate_refuses_repo_root(plugin_root: Path) -> None:
    """Escape M31 - prose claimed `validate` ACCEPTS --repo-root; the engine refuses it.

    The flag-level pin only reads the code block, so prose contradicting the code
    block went unnoticed. This holds the sentence.
    """
    section = _section(_body(plugin_root, SUITE_SKILL), "## Phase P9")
    assert _has_sentence_with(section, "refuses", "--repo-root") or _has_sentence_with(
        section, "refuse", "--repo-root"
    ), "P9 must state that `validate` REFUSES --repo-root (argparse exit 2), not accepts it"
    flat = _flat(section)
    for wrong in ("validate also takes `--repo-root`", "validate accepts --repo-root",
                  "`validate` takes `--repo-root`"):
        assert _flat(wrong) not in flat, (
            f"P9 claims validate accepts --repo-root ({wrong!r}) - the engine refuses it"
        )


def test_p9_documents_the_blocking_versus_advisory_split(plugin_root: Path) -> None:
    """F3 - 'Every violation is blocking' is FALSE for the bug-slug form this skill blesses.

    The engine deliberately emits `debug-flow-origin-undereferenceable` at ADVISORY
    severity for a ref that is not path-shaped, and advisories are excluded from the
    exit code. The skill compiles the ETHOS 'Honest boundary' principle into its own
    body, so overclaiming enforcement here is precisely the anti-pattern it carries.
    """
    body = _body(plugin_root, SUITE_SKILL)
    flat = _flat(body)
    assert "every violation is blocking" not in flat, (
        "the blanket 'Every violation is blocking' claim is false - a bare bug slug "
        "produces an ADVISORY, and advisories do not affect the exit code"
    )
    assert "advisory" in flat, "the blocking/advisory split must be named"
    assert _has_sentence_with(body, "path-shaped", "blocks") or _has_sentence_with(
        body, "path-shaped", "dereferenced"
    ), "the text must say a PATH-SHAPED origin_ref is dereferenced and a dead one blocks"
    assert _has_sentence_with(body, "slug", "advisory"), (
        "the text must say a bare SLUG is advisory because it cannot be dereferenced"
    )


def test_suite_builder_keeps_the_adapter_split_warning(plugin_root: Path) -> None:
    """Escape M4 - the corrective 'Mind the adapter split' paragraph was deleted.

    The positive pin (LocalAdapter named) and the negative pin (no
    ProductionQAAdapter-executes claim) both stayed green with the corrective
    paragraph gone, so the warning that stops the next reader repeating the F2
    mistake was unprotected.
    """
    body = _body(plugin_root, SUITE_SKILL)
    assert "Mind the adapter split" in body, (
        "the corrective adapter-split warning must survive - it is what stops the "
        "next reader making the same ProductionQAAdapter mistake"
    )
    assert _has_sentence_with(body, "productionqaadapter", "observes") or _has_sentence_with(
        body, "productionqaadapter", "executes nothing"
    ), "the warning must say the adapter OBSERVES and executes nothing"


def test_suite_builder_covers_both_playwright_suffixes(plugin_root: Path) -> None:
    """F4 alignment - suite discovery covers *.spec.ts AND *.test.ts."""
    body = _body(plugin_root, SUITE_SKILL)
    assert ".spec.ts" in body and ".test.ts" in body, (
        "P0/P1 suite-dir language must cover BOTH *.spec.ts and *.test.ts - a suite "
        "the text blesses but discovery cannot see makes reconciliation vacuous"
    )


def test_suite_builder_states_the_migration_boundary(plugin_root: Path) -> None:
    """D7 - absent manifest => every consuming surface behaves exactly as today."""
    body = _body(plugin_root, SUITE_SKILL)
    low = body.lower()
    assert "migration boundary" in low, "the boundary must be NAMED as such"
    assert "absent" in low and "manifest" in low
    assert "exactly as today" in low, (
        "the boundary's promise is that absent a manifest nothing changes"
    )


def test_suite_builder_names_the_runnable_prod_smoke_suite(plugin_root: Path) -> None:
    """The prod suite runs via the command-spawn path, NOT the ProductionQAAdapter.

    The F2 spec correction: `ProductionQAAdapter` is an APM-poll / log-tail
    adapter - it OBSERVES a signal production already emits and executes nothing,
    so it cannot spawn a Playwright suite. Running the prod project is an ordinary
    test-command spawn, which `test-run-monitor`'s existing source table already
    resolves to `LocalAdapter` with no adapter change.

    This pin held the WRONG claim on its first cut (it asserted ProductionQAAdapter
    ran the suite) and was flipped when the spec landed the correction. Both halves
    are pinned now - the right mechanism named, and the wrong one not claimed.
    """
    body = _body(plugin_root, SUITE_SKILL)
    assert "test-run-monitor" in body
    assert "LocalAdapter" in body, (
        "the prod suite is runnable via test-run-monitor's existing command-spawn "
        "path (LocalAdapter), which the source table already resolves"
    )
    flat = _flat(body)
    # The spec scenario's own vocabulary - the prod project is a runnable TEST
    # SOURCE, run against the PRODUCTION URL.
    assert "test source" in flat, (
        "the amended spec names the prod project a runnable TEST SOURCE"
    )
    assert "production url" in flat, (
        "the prod smoke suite runs against the production URL"
    )
    assert "no adapter change" in flat or "no new input form" in flat, (
        "the wiring must state it needs no adapter change - reusing the monitor "
        "unchanged is the point of routing through the existing source table"
    )
    # The negative half of the spec scenario: the skill must NOT claim the
    # ProductionQAAdapter executes the suite.
    for claim in (
        "runnable through the existing **productionqaadapter**",
        "via the productionqaadapter",
        "through its productionqaadapter",
        "runs the prod project through its productionqaadapter",
    ):
        assert claim not in flat, (
            f"the skill claims the ProductionQAAdapter executes the prod suite "
            f"({claim!r}) - it is an APM-poll / log-tail adapter and spawns nothing"
        )


def test_suite_builder_adds_no_new_agents(plugin_root: Path) -> None:
    """Reuse-first - the suite-builder orchestrates existing agents only.

    Held inside the Operating rules section, so it pins the RULE rather than a
    passing mention elsewhere in the prose.
    """
    body = _body(plugin_root, SUITE_SKILL)
    assert "no new agents" in _flat(body), "the skill must state it introduces no new agents"
    rules = _section(body, "## Operating rules (non-negotiable)")
    assert "no new agents" in _flat(rules), (
        "'no new agents' must be an operating RULE, not only a remark in the prose"
    )
    assert "reuse" in _flat(rules)


def test_suite_builder_is_reachable_from_the_command(plugin_root: Path) -> None:
    body = _body(plugin_root, SUITE_SKILL)
    assert "/architect-team:playwright-suite" in body


def test_suite_builder_carries_the_compiled_principles_block(plugin_root: Path) -> None:
    """playwright-suite-builder is run-driving, so it carries the ETHOS block.

    Recorded decision: this skill DOES carry the compiled principles block (it is
    a run-driving pipeline, mirroring ux-test-builder, and it is registered in
    hooks/pretool_skill_gate.py's _PIPELINE_SKILLS); intuition-map-lifecycle does
    NOT (it is a lane-callable discipline, mirroring interaction-intuition).

    Opt-in is the FENCE, not a list - scripts/setup/compile_skills.py discovers
    consumers by scanning for the fence pair - so deleting the fence silently
    drops the skill out of the compiled set with nothing else going red. That is
    what this pin exists to catch.
    """
    raw = (plugin_root / SUITE_SKILL).read_text(encoding="utf-8")
    assert "<!-- ct6:block:principles:begin -->" in raw, (
        "playwright-suite-builder must carry the ct6:block:principles fence - it is "
        "how scripts/setup/compile_skills.py discovers the skill as a consumer"
    )
    assert "<!-- ct6:block:principles:end -->" in raw

    # And the fenced content must be the CANONICAL text, not a hand-written copy.
    import importlib.util
    compiler = plugin_root / "scripts" / "setup" / "compile_skills.py"
    spec = importlib.util.spec_from_file_location("_ct6_compile_pins", compiler)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    current = mod.fenced_content(raw.replace("\r\n", "\n"), "principles")
    assert current == mod.render_block("principles"), (
        "the fenced principles content has drifted from the canonical source - run "
        "`python scripts/setup/compile_skills.py --write`"
    )


def test_lifecycle_does_not_carry_the_principles_block(plugin_root: Path) -> None:
    """The other half of the same decision, held so it cannot silently flip.

    intuition-map-lifecycle is a lane-callable discipline, not a run-driving
    pipeline; it mirrors interaction-intuition, which carries no block either.
    """
    raw = (plugin_root / LIFECYCLE_SKILL).read_text(encoding="utf-8")
    assert "ct6:block:principles" not in raw, (
        "intuition-map-lifecycle is a lane-callable discipline and deliberately "
        "does NOT carry the compiled principles block (it mirrors interaction-intuition)"
    )
    sibling = (plugin_root / INTUITION_SKILL).read_text(encoding="utf-8")
    assert "ct6:block:principles" not in sibling, (
        "interaction-intuition is the sibling this decision mirrors - if IT gained "
        "the block, revisit the lifecycle skill's exclusion rather than pinning around it"
    )


# --------------------------------------------------------------------------- #
# 2.4 - the command wrapper
# --------------------------------------------------------------------------- #

def test_command_invokes_the_suite_builder_skill(plugin_root: Path) -> None:
    text = (plugin_root / SUITE_COMMAND).read_text(encoding="utf-8")
    assert "skill: playwright-suite-builder" in text, (
        "the command must bind the skill by name for the Skill tool"
    )


def test_command_binds_arguments(plugin_root: Path) -> None:
    text = (plugin_root / SUITE_COMMAND).read_text(encoding="utf-8")
    assert "$ARGUMENTS" in text, "the command must bind $ARGUMENTS"


@pytest.mark.parametrize("flag", ("--no-commit", "--no-push", "--no-compact"))
def test_command_documents_each_standard_flag(plugin_root: Path, flag: str) -> None:
    text = (plugin_root / SUITE_COMMAND).read_text(encoding="utf-8")
    assert flag in text, f"the command must document the standard flag {flag}"


def test_ensure_names_scaffold_honestly(plugin_root: Path) -> None:
    """F7 - `scaffold` is a real CLI subcommand the 'three verbs' contract never named.

    Two consequences the adversary proved: an empty scaffolded map satisfied
    `ensure` (so the R1 gap the verb exists to close was satisfiable by a stub),
    and the ad-hoc path told an agent to derive a map inline while naming no engine
    call to write it - against a hard rule that the verbs are the only writers.
    """
    body = _body(plugin_root, LIFECYCLE_SKILL)
    assert "scaffold" in _flat(body), "the engine's scaffold operation must be named"
    section = _section(body, "## Verb — `ensure`")
    sflat = _flat(section)
    assert "scaffold" in sflat, "the ad-hoc ensure path must name scaffold as how the map is written"
    assert _has_sentence_with(section, "scaffold", "populate") or _has_sentence_with(
        section, "scaffolded", "not"
    ), "ensure must state that scaffold-then-populate is the flow, not scaffold alone"
    assert _has_sentence_with(section, "empty", "not") or _has_sentence_with(
        section, "zero-element", "not"
    ), "an empty / zero-element scaffolded map must be stated NOT to satisfy ensure"
    # And the contract must not silently present scaffold as a fourth peer verb.
    assert _has_sentence_with(body, "scaffold", "supporting") or _has_sentence_with(
        body, "scaffold", "not a"
    ), "scaffold must be named a SUPPORTING operation under ensure, not a fourth verb"


def test_ensure_documents_every_action_required_value(plugin_root: Path) -> None:
    """rev-R4 closed on the ENGINE side - the contract must name what it now returns.

    backend-engines gave ensure_support a fourth value, `populate`, so a freshly
    scaffolded map no longer reports `none`. My held sentence had been written as a
    caller obligation precisely because the engine did not gate; now that it does,
    telling an agent to work around a closed hole would be its own kind of stale.

    Held against the engine's own docstring so the two cannot drift apart.
    """
    engine = _load_lifecycle_engine(plugin_root)
    import inspect
    import re
    doc = " ".join((inspect.getdoc(engine.ensure_support) or "").split())

    # SCOPE the extraction to the sentence that enumerates the values, rather than
    # scraping the whole docstring and subtracting known non-values. backend-engines
    # flagged the fragility: their docstring also double-backticks the FIELD NAME
    # (``action_required``) in the sentence introducing the list, so a looser
    # character class picks it up as a fifth "value" - and the assertion would then
    # pass only because the field name happens to appear in my table. Verified: a
    # `[\w-]+` class extracts action_required; the tight class does not. Scoping is
    # the structural fix; the tight class alone was an accident that held.
    marker = "names what the skill must do:"
    assert marker in doc, (
        "the engine's ensure_support docstring no longer introduces its values with "
        f"{marker!r} - re-scope this extraction against the current docstring rather "
        "than widening it back to the whole text"
    )
    enumeration = doc.split(marker, 1)[1]
    values = set(re.findall(r"``([a-z][a-z-]*)``", enumeration))
    assert values, "could not read the engine's action_required values from its docstring"
    assert "action_required" not in values, (
        "the extraction picked up the FIELD NAME as a value - the scoping broke, and "
        "this pin would otherwise demand the contract document a non-value"
    )

    # adv round-3 T2: bind the docstring to the CODE it describes, the way
    # backend-engines' zero-width pin binds theirs. Reading only the docstring means
    # a fifth value added to ensure_support's body - without a docstring update -
    # keeps every pin green and leaves the skill silent about it (their V1 mutation,
    # 102 passed). Comparing both sources closes that: the docstring must describe
    # exactly the values the code can actually emit.
    src = inspect.getsource(engine.ensure_support)
    emitted = set(re.findall(r'"action_required":\s*"([a-z-]+)"', src))
    emitted |= set(re.findall(r'\["action_required"\]\s*=\s*"([a-z-]+)"', src))
    assert emitted, "could not read any action_required value out of ensure_support's code"
    assert emitted == values, (
        f"ensure_support's CODE emits {sorted(emitted)} but its DOCSTRING describes "
        f"{sorted(values)}. The two have drifted, so this pin can no longer tell the "
        f"skill contract what to document - fix the engine's docstring (backend-engines "
        f"owns it and has a standing agreement to ping before rewording)."
    )
    # ADMITTED LIMIT (adv round-4 U4, accepted rather than chased): `emitted` is read
    # from ensure_support's OWN source only. A fifth action_required value assigned
    # inside a HELPER that ensure_support calls is invisible here, and because no
    # existing literal is removed the equality above still holds - so the contract
    # would stay silent about a value agents can receive. The inline-literal, rename
    # and module-constant forms ARE caught; only helper-emission is not. Walking the
    # whole module would close it but widens to any assignment anywhere in the file,
    # trading a bounded blind spot for an unbounded false-positive surface - a new
    # guard that would need its own guard. The adversary's own judgment was
    # "bounded... recording it so the pin's true scope is on the record, not because
    # I think it should be chased". This comment IS that record, and
    # test_action_required_pin_admits_its_helper_blind_spot asserts both that the
    # admission is here and that the blind spot is real.

    section = _section(_body(plugin_root, LIFECYCLE_SKILL), "## Verb — `ensure`")
    missing = sorted(v for v in values if f"`{v}`" not in section)
    assert not missing, (
        f"ensure's contract does not name action_required value(s) {missing} that "
        f"scripts/intuition_lifecycle/engine.py returns - an agent reading the skill "
        f"would not know what to do when it sees one"
    )
    assert _has_sentence_with(section, "populate", "zero") or _has_sentence_with(
        section, "populate", "scaffold"
    ), "the contract must say WHEN `populate` is returned, not merely list it"


def test_ensure_states_the_exit_code_agrees_with_the_field(plugin_root: Path) -> None:
    """The exit code IS a faithful gate, and the contract must not teach otherwise.

    backend-engines' generalization, which caught a real instance in my text: a
    sentence phrased "do not infer X, check Y yourself" is a workaround wearing a
    rule's clothes, and it turns actively misleading the moment the hole it worked
    around is closed. Mine said "read that field rather than the exit status",
    written when `ensure` did not gate on a zero-element map. It now does, and the
    CLI returns 0 ONLY when action_required is `none` - so the exit code is
    trustworthy and telling an agent to distrust it is wrong.

    Verified against the CLI rather than assumed.
    """
    cli = plugin_root / "scripts" / "intuition_lifecycle" / "cli.py"
    if not cli.exists():
        pytest.skip("intuition-lifecycle CLI not present yet (task 1.2)")
    cli_src = cli.read_text(encoding="utf-8")
    assert 'return 0 if report["action_required"] == "none" else 1' in cli_src, (
        "the CLI's ensure exit rule changed - re-verify what the contract should say "
        "about the exit code before trusting this pin's premise"
    )

    section = _section(_body(plugin_root, LIFECYCLE_SKILL), "## Verb — `ensure`")
    flat = _flat(section)
    assert "exit" in flat, "the contract must say what the exit code means"
    assert _has_sentence_with(section, "exits", "none") or _has_sentence_with(
        section, "exit code", "agrees"
    ), "the contract must state the exit code tracks action_required"
    # adv round-3 T3: the guard was a three-phrase blocklist, and their W7 mutation
    # cleared all three with a near-miss paraphrase ("Do not infer from the exit
    # code. Read the field rather than the status") while passing 102/102. A
    # blocklist enumerates the phrasings someone happened to think of; this matches
    # the SHAPE instead - any "do not rely on / do not infer from / rather than"
    # aimed at the exit code or status, however worded in between.
    # adv round-4 U3: the first alternation missed two denial forms - a different
    # verb ("never trust the exit code") and a denial placed 86 chars from "status".
    # Widened to share the negation prefix, add trust/ignore, and open the window to
    # 120, the value that closes both without firing on the shipped text.
    #
    # ADMITTED LIMIT: a distance-bounded shape is evadable by a long enough
    # sentence. 120 closes every form either the adversary or I could author; a
    # denial 200 characters from its object would still clear it. Widening further
    # grows false-positive risk faster than coverage, so this is a bounded guard
    # and is documented as one rather than presented as complete.
    import re as _re
    distrust = _re.compile(
        r"((do not|don't|never) (rely on|infer from|trust)|ignore|rather than)"
        r"[^.]{0,120}\b(the )?(exit|status)\b"
    )
    hit = distrust.search(flat)
    assert hit is None, (
        f"the contract still teaches distrust of the exit code ({hit.group(0)!r}) - "
        "that was a workaround for a hole the engine has since closed, and a "
        "workaround outlives its hole as actively misleading advice"
    )


def test_action_required_pin_admits_its_helper_blind_spot(plugin_root: Path) -> None:
    """The W13b honesty pattern: an ADMITTED limit, asserted to be both stated and real.

    adv round-4 U4 found that the docstring==code binding reads only
    ensure_support's own source, so a value emitted from a HELPER it calls is
    invisible. Their judgment was that this is bounded and not worth chasing, and I
    agree: walking the whole module closes it but widens to any assignment anywhere,
    trading a bounded blind spot for an unbounded false-positive surface.

    An admitted limit is an acceptable terminal state; an UNadmitted one is not. So
    this test holds both halves - the admission exists in the pin, AND the limit it
    admits is genuinely real. If someone later closes the blind spot without
    removing the admission, the second half fails and the stale claim gets deleted.
    """
    import re
    src = (plugin_root / "tests" / "test_playwright_suite_wiring.py").read_text(encoding="utf-8")

    # (a) The admission is present, on the pin it describes.
    fn_start = src.index("def test_ensure_documents_every_action_required_value")
    fn_end = src.index("\ndef ", fn_start + 1)
    body = src[fn_start:fn_end]
    assert "ADMITTED LIMIT" in body, (
        "the action_required pin must ADMIT its helper-emission blind spot in place - "
        "an unadmitted limit is what this run's W13b pattern exists to prevent"
    )
    assert "helper" in body.lower(), "the admission must name WHICH blind spot it admits"

    # (b) The limit is real: run the pin's own extraction over a synthetic module
    # whose helper emits a fifth value, and confirm it is missed. Built in-memory so
    # nothing outside my owned files is touched.
    synthetic = (
        'def _helper(report):\n'
        '    report["action_required"] = "needs-review"\n'
        '\n'
        'def ensure_support():\n'
        '    """Doc.\n'
        '\n'
        '    ``action_required`` names what the skill must do:\n'
        '    ``produce-map``, ``repair-map``, ``populate``, or ``none``.\n'
        '    """\n'
        '    report = {"action_required": "produce-map"}\n'
        '    report["action_required"] = "repair-map"\n'
        '    report["action_required"] = "populate"\n'
        '    report["action_required"] = "none"\n'
        '    _helper(report)\n'
        '    return report\n'
    )
    fn_src = synthetic[synthetic.index("def ensure_support"):]
    emitted = set(re.findall(r'"action_required":\s*"([a-z-]+)"', fn_src))
    emitted |= set(re.findall(r'\["action_required"\]\s*=\s*"([a-z-]+)"', fn_src))
    module_wide = set(re.findall(r'\["action_required"\]\s*=\s*"([a-z-]+)"', synthetic))

    assert "needs-review" not in emitted, (
        "the helper-emitted value is now VISIBLE to the function-scoped extraction - "
        "the blind spot is closed, so delete the ADMITTED LIMIT comment rather than "
        "leaving a stale admission standing"
    )
    assert "needs-review" in module_wide, (
        "sanity: the value must be findable module-wide, or this test is not "
        "demonstrating the limit it claims to"
    )


def test_lifecycle_cross_reference_resolves_to_a_real_section(plugin_root: Path) -> None:
    """F8 - the intake-and-mapping 'Phase -1B dispatch' anchor does not exist.

    intake-and-mapping files the per-frontend-codebase intuiter dispatch under
    Phase -1D, not -1B. Verified against the real file rather than assumed.
    """
    body = _body(plugin_root, LIFECYCLE_SKILL)
    intake_path = plugin_root / "skills" / "intake-and-mapping" / "SKILL.md"
    intake = surface_read(intake_path)

    # Which phase does intake-and-mapping ACTUALLY file the intuiter dispatch under?
    import re
    real_phases = set()
    for m in re.finditer(r"^## Phase [−-]1([A-Z])\b", intake, re.MULTILINE):
        seg = _section(intake, m.group(0)) if m.group(0) in intake else ""
        if "intuit" in seg.lower():
            real_phases.add(m.group(1))
    if not real_phases:
        pytest.skip("intake-and-mapping files no intuiter dispatch under a Phase −1x heading")

    # Every phase THIS skill cites alongside intake-and-mapping for that dispatch
    # must be one of them. The first cut only raised when the cited section existed
    # AND lacked 'intuit', so citing a phase with no heading at all sailed through -
    # which is exactly the −1B case it was written to catch.
    for line in body.splitlines():
        if "intake-and-mapping" not in line:
            continue
        for cited in re.findall(r"Phase [−-]1([A-Z])", line):
            assert cited in real_phases, (
                f"intuition-map-lifecycle cites the intake-and-mapping intuiter dispatch at "
                f"Phase −1{cited}, but intake-and-mapping files it under "
                f"{sorted('−1' + p for p in real_phases)}. Cite the step that exists.\n"
                f"  line: {line.strip()}"
            )


def test_command_documents_proposal_first(plugin_root: Path) -> None:
    """F10 - the skill's P2 text carves out against a flag the command never defined."""
    text = (plugin_root / SUITE_COMMAND).read_text(encoding="utf-8")
    body = _body(plugin_root, SUITE_SKILL)
    if "--proposal-first" in body:
        assert "--proposal-first" in text, (
            "the skill's domain-gate carve-out names --proposal-first, so the command "
            "must actually accept it - 4 of 5 sibling run-driving commands carry it"
        )


def test_proposal_first_is_not_an_inert_flag(plugin_root: Path) -> None:
    """rev-R3 - the command claimed 'P5 and P7 read PROPOSAL_FIRST'; the skill did not.

    Same defect class as the --no-worktree inert flag: a flag a user can pass that
    changes nothing reads as supported. Fixed on the SKILL side rather than by
    deleting the claim, so the flag actually does something.
    """
    text = (plugin_root / SUITE_COMMAND).read_text(encoding="utf-8")
    body = _body(plugin_root, SUITE_SKILL)
    if "PROPOSAL_FIRST" not in text:
        pytest.skip("the command does not declare PROPOSAL_FIRST")
    assert "PROPOSAL_FIRST" in body, (
        "the command passes PROPOSAL_FIRST to the skill, so the skill must name it - "
        "otherwise the flag is inert and the command's claim is false"
    )
    p5 = _section(body, "## Phase P5")
    assert "PROPOSAL_FIRST" in p5, (
        "the command says the pause happens before P5 authoring, so P5 is where the "
        "skill must honour it"
    )
    assert _has_sentence_with(p5, "proposal_first", "pause"), (
        "P5 must state what PROPOSAL_FIRST actually does"
    )


def test_command_consumes_every_flag_it_declares(plugin_root: Path) -> None:
    """Independent-review item - --no-worktree / AUTO_WORKTREE were declared but inert.

    A flag a user can pass that changes nothing is worse than an absent one: it
    reads as supported. Every state variable the command binds must be consumed by
    a step that acts on it.
    """
    text = (plugin_root / SUITE_COMMAND).read_text(encoding="utf-8")
    if "AUTO_WORKTREE" in text:
        assert text.count("AUTO_WORKTREE") >= 2, (
            "AUTO_WORKTREE is bound but never consumed - either wire the worktree "
            "step (per the ux-test sibling) or drop the flag"
        )
        assert "worktree_lifecycle" in text or "create_run_worktree" in text, (
            "the --no-worktree flag must gate a real auto-worktree step, mirroring "
            "commands/ux-test.md, or not exist at all"
        )


def test_command_argument_hint_lists_every_parsed_flag(plugin_root: Path) -> None:
    """adv round-3 T4 - the argument-hint was revertible with every pin green.

    Dropping `[--proposal-first]` from the hint passed 102/102 and would silently
    re-open round-1 F10. The hint is the only place a user learns a flag exists, so
    every flag the command PARSES must appear in it - held structurally rather than
    by naming one flag, so a future flag cannot be added to parsing alone.
    """
    text = (plugin_root / SUITE_COMMAND).read_text(encoding="utf-8")
    fm, _ = frontmatter.parse(plugin_root / SUITE_COMMAND)
    hint = fm.get("argument-hint", "")

    import re
    # adv round-4 U2: bolding a flag bullet - `- **`--proposal-first`**` - dropped it
    # out of `parsed`, so un-hinting it at the same time passed. Emphasis is an
    # ordinary editorial change, which is exactly why the pin must survive it.
    parsed = set(re.findall(r"^- \*{0,2}`(--[a-z-]+)`", text, re.MULTILINE))
    assert parsed, "could not read the command's parsed flag list"
    missing = sorted(f for f in parsed if f not in hint)
    assert not missing, (
        f"the command PARSES {missing} but the argument-hint does not list them - "
        f"the hint is where a user discovers a flag exists, so a parsed-but-unhinted "
        f"flag is invisible"
    )


def test_command_worktree_step_stays_consumed(plugin_root: Path) -> None:
    """adv round-3 T4 - deleting the AUTO_WORKTREE consumption step passed 102/102.

    That would silently re-open the declared-but-inert flag. The existing inert-flag
    pin is conditional on AUTO_WORKTREE appearing at all, so removing the CONSUMER
    while keeping the declaration slipped between the two. Hold the step itself.
    """
    text = (plugin_root / SUITE_COMMAND).read_text(encoding="utf-8")
    assert "## Auto-worktree creation" in text, (
        "the command must carry the auto-worktree step that consumes --no-worktree, "
        "mirroring commands/ux-test.md - or drop the flag entirely"
    )
    assert "create_run_worktree" in text, (
        "the auto-worktree step must invoke the real helper, not merely mention worktrees"
    )
    assert "current_worktree_is_run" in text, (
        "the step must carry the re-entry guard - nested run worktrees are the failure "
        "this check exists to prevent"
    )

    # adv round-4 U1: all three tokens above survive while the flag goes INERT.
    # Deleting only the skip-condition line kept the header, the helper and the
    # re-entry guard, so 105/105 stayed green while --no-worktree gated nothing.
    # The count guard elsewhere did not catch it either: AUTO_WORKTREE fell 3 -> 2
    # and both survivors are DECLARATION sites, not consumption. Existence is not
    # consumption - hold that the step READS the variable.
    step_lines = []
    for line in text.split("## Auto-worktree creation", 1)[1].splitlines():
        if line.startswith("## "):
            break
        step_lines.append(line)
    assert any("AUTO_WORKTREE" in line for line in step_lines), (
        "the auto-worktree step never reads AUTO_WORKTREE - --no-worktree binds a "
        "variable no step consumes, so the flag is inert again (the exact defect "
        "the inert-flag item was opened for)"
    )


def test_manifest_required_field_count_matches_the_list(plugin_root: Path) -> None:
    """adv round-3 T4 - 'All six are REQUIRED' -> 'All five' passed 102/102.

    Cosmetic on its own (the field-set pin still guarantees all six are named), but
    prose that miscounts its own list is exactly the drift a reader trusts. Derived
    from the engine rather than hardcoded, so it tracks the real requirement set.
    """
    engine = _load_manifest_engine(plugin_root)
    section = _manifest_section(plugin_root)
    n = len(engine.REQUIRED_TOP_LEVEL_FIELDS)
    words = {5: "five", 6: "six", 7: "seven", 8: "eight"}
    word = words.get(n)
    if word is None:
        pytest.skip(f"no spelled-out word for {n} required top-level fields")
    assert f"All {word} are REQUIRED" in section or f"all {word} are required" in _flat(section), (
        f"the manifest contract must say all {word} top-level fields are REQUIRED - "
        f"the engine enforces {n} ({sorted(engine.REQUIRED_TOP_LEVEL_FIELDS)}), and prose "
        f"that miscounts its own list is drift a reader trusts"
    )


def test_command_frontmatter_carries_an_argument_hint(plugin_root: Path) -> None:
    fm, _ = frontmatter.parse(plugin_root / SUITE_COMMAND)
    assert isinstance(fm.get("argument-hint"), str) and fm["argument-hint"].strip(), (
        "house command shape - every command declares an argument-hint"
    )
