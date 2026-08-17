"""Trait-keyed CLAUDE.md guidance blocks + the Bauplan safety context (SRC-005 / D5).

Two layers, mirroring `tests/test_installer_guidance_blocks.py`:

  1. `scripts/setup/guidance_blocks.py` — `sync_block()`, which drives the
     EXISTING `upsert_block` / `remove_block` from a capability check supplied as
     a PREDICATE over the target project. The three existing entry points keep
     their signatures and behavior; only the gate is new.

  2. `scripts/setup/setup.py` — the Bauplan consumer: the safety-context body,
     the injected marker detector, and the wiring behind the opt-in `--claude-md`
     flag.

The load-bearing case (D5) is the DEGRADED path: marker present, `bauplan`
plugin ABSENT, block still written — because "never write directly to `main`"
matters most exactly when the tooling that would enforce it is missing.

The marker detector itself lives in `hooks/discipline_registry.py` and is owned
elsewhere; here it is always injected, so these tests are independent of it.

Hermetic: tmp target projects, injected detectors, `_write_last_run` patched, no
writes outside tmp_path.
"""
from __future__ import annotations

import inspect
import json
from pathlib import Path
from types import ModuleType
from unittest.mock import patch

import pytest
from tests.helpers.module_loader import load_module

BAUPLAN_ID = "bauplan@bauplan-skills"
HARD_PLUGINS = {
    "superpowers@claude-plugins-official",
    "cartographer@cartographer-marketplace",
    "ralph-loop@claude-plugins-official",
}


@pytest.fixture(scope="module")
def gb(plugin_root: Path) -> ModuleType:
    return load_module(
        plugin_root / "scripts" / "setup" / "guidance_blocks.py",
        "guidance_blocks_bauplan",
    )


@pytest.fixture(scope="module")
def setup_module(plugin_root: Path) -> ModuleType:
    return load_module(
        plugin_root / "scripts" / "setup" / "setup.py", "setup_module_bauplan_guidance"
    )


def _always(value: bool):
    """A trait predicate with a fixed verdict, recording the roots it saw."""

    def predicate(project_root: Path) -> bool:
        predicate.seen.append(Path(project_root))
        return value

    predicate.seen = []  # type: ignore[attr-defined]
    return predicate


def _marker_style(value: bool, example: str = "bauplan_project.yml"):
    """A predicate in the `_has_frontend_markers` house shape: (bool, evidence)."""

    def predicate(project_root: Path) -> tuple[bool, dict]:
        if value:
            return True, {"marker": "bauplan-project-file", "example": example}
        return False, {"marker": "none", "reason": "no bauplan_project.yml"}

    return predicate


def _project(tmp_path: Path, *, existing: str | None = None) -> Path:
    """A target project dir; returns the CLAUDE.md path (written iff `existing`)."""
    root = tmp_path / "target"
    root.mkdir(exist_ok=True)
    claude_md = root / "CLAUDE.md"
    if existing is not None:
        claude_md.write_bytes(existing.encode("utf-8"))
    return claude_md


# =========================================================================== #
# 4.1 — the predicate gate, on top of the UNCHANGED primitives
# =========================================================================== #


def test_existing_entry_point_signatures_are_unchanged(gb: ModuleType) -> None:
    """The reuse contract: only the gate is new. These three keep their exact
    signatures, so every existing caller is untouched."""
    assert str(inspect.signature(gb.block_fences)) == (
        "(capability: 'str') -> 'tuple[str, str]'"
    )
    assert str(inspect.signature(gb.upsert_block)) == (
        "(claude_md_path: 'PathLike', capability: 'str', body: 'str', *, "
        "create: 'bool' = False) -> 'bool'"
    )
    assert str(inspect.signature(gb.remove_block)) == (
        "(claude_md_path: 'PathLike', capability: 'str') -> 'bool'"
    )


def test_sync_block_adds_the_block_when_the_predicate_is_true(
    gb: ModuleType, tmp_path: Path
) -> None:
    claude_md = _project(tmp_path, existing="# Target\n\nExisting content.\n")
    result = gb.sync_block(
        claude_md, "bauplan", "## Bauplan\nrules", capability_check=_always(True)
    )
    text = claude_md.read_text(encoding="utf-8")
    begin, end = gb.block_fences("bauplan")
    assert result == "written"
    assert begin in text and end in text
    assert "# Target\n\nExisting content.\n" in text


def test_sync_block_removes_exactly_the_fenced_block_byte_preserving(
    gb: ModuleType, tmp_path: Path
) -> None:
    """4.5 — exactly the fenced block goes; every other byte survives verbatim,
    including the CRLF / tab / double-space bytes around it."""
    begin, end = gb.block_fences("bauplan")
    seeded = f"# Target\r\n\r\n{begin}\nrules\n{end}\nKeep\tthese  bytes.\r\n"
    claude_md = _project(tmp_path, existing=seeded)
    result = gb.sync_block(claude_md, "bauplan", "rules",
                           capability_check=_always(False))
    assert result == "removed"
    assert claude_md.read_bytes() == b"# Target\r\n\r\nKeep\tthese  bytes.\r\n"


def test_sync_block_add_then_remove_is_byte_identical(
    gb: ModuleType, tmp_path: Path
) -> None:
    """An add/remove round trip restores the file EXACTLY — no residue at all.

    This previously asserted `original + b"\\n"`, encoding a real defect as
    expected behavior: `upsert_block` inserted a separator newline that
    `remove_block` never reclaimed, so the file grew by one byte on every
    install/uninstall cycle, without bound, in a file CT6 does not own. The
    spec scenario "exactly the fenced block is removed and all other CLAUDE.md
    content is byte-preserved" forbids exactly that."""
    claude_md = _project(tmp_path, existing="# Target\r\n\r\nKeep\tthese  bytes.\r\n")
    original = claude_md.read_bytes()
    gb.sync_block(claude_md, "bauplan", "## Bauplan\nrules",
                  capability_check=_always(True))
    result = gb.sync_block(claude_md, "bauplan", "## Bauplan\nrules",
                           capability_check=_always(False))
    begin, end = gb.block_fences("bauplan")
    assert result == "removed"
    assert claude_md.read_bytes() == original
    assert begin not in claude_md.read_text(encoding="utf-8")
    assert end not in claude_md.read_text(encoding="utf-8")


def test_sync_block_repeated_cycles_do_not_accumulate_bytes(
    gb: ModuleType, tmp_path: Path
) -> None:
    """Five on/off cycles leave the file byte-identical.

    Accumulation is the part that actually harms a user, and a single-cycle
    assertion cannot see it: the original defect added one newline per cycle,
    so the file drifted further from its true contents on every run. This is
    the assertion whose absence let a green suite ship a live defect."""
    claude_md = _project(tmp_path, existing="# Target\n\nReal user content.\n")
    original = claude_md.read_bytes()
    for _ in range(5):
        gb.sync_block(claude_md, "bauplan", "## Bauplan\nrules",
                      capability_check=_always(True))
        gb.sync_block(claude_md, "bauplan", "## Bauplan\nrules",
                      capability_check=_always(False))
    assert claude_md.read_bytes() == original


def test_a_bare_cr_file_stays_well_formed_and_stable(
    gb: ModuleType, tmp_path: Path
) -> None:
    """A classic-Mac bare-CR file keeps a WELL-FORMED tail and stops changing.

    Two independent reviews shaped this. The first reclaim stripped the "\\r\\n"
    pair, DESTROYING the user's bare CR. The correction stripped any trailing
    "\\n" — which then TORE a genuine CRLF into a dangling "\\r" on a
    hand-seeded block (see the sibling test). The reclaim now fires only when
    the trailing "\\n" is not part of a "\\r\\n".

    The residue on this degenerate shape is one "\\n", and what matters is that
    it is STABLE — the next cycle sees a "\\r\\n" tail and reclaims nothing —
    so nothing accumulates and the file never becomes malformed."""
    claude_md = _project(tmp_path, existing="# Target\rnotes.\r")
    sizes = []
    for _ in range(5):
        gb.upsert_block(claude_md, "bauplan", "rules")
        gb.remove_block(claude_md, "bauplan")
        sizes.append(len(claude_md.read_bytes()))
    assert len(set(sizes)) == 1, f"bare-CR round trip is not stable: {sizes}"
    assert not claude_md.read_bytes().endswith(b"\r"), "left a torn CR"


def test_removal_never_tears_a_crlf_into_a_dangling_cr(
    gb: ModuleType, tmp_path: Path
) -> None:
    """A hand-seeded block at EOF behind a CRLF blank line keeps that blank line.

    Found by independent review as a PREDICTION about the fix, then confirmed
    live: stripping the trailing "\\n" of a genuine "\\r\\n" leaves a bare
    "\\r" — malformed line endings, which is worse in kind than the byte leak
    the reclaim exists to prevent. `upsert_block` never writes this shape, so
    the reclaim must not assume it did."""
    begin, end = gb.block_fences("bauplan")
    seeded = f"# Target\r\n\r\n{begin}\nrules\n{end}\n"
    claude_md = _project(tmp_path, existing=seeded)
    gb.remove_block(claude_md, "bauplan")
    got = claude_md.read_bytes()
    assert not got.endswith(b"\r"), f"torn CRLF: {got!r}"
    assert got == b"# Target\r\n\r\n"


def test_round_trip_preserves_a_file_with_no_trailing_newline(
    gb: ModuleType, tmp_path: Path
) -> None:
    """A CLAUDE.md that does not end in a newline still does not, afterwards.

    `upsert_block` used to append two newlines here but only one when the file
    already ended with a newline. That asymmetry made an exact reverse
    impossible — after the fact the two cases are indistinguishable from the
    file alone — so both branches now append exactly one separator."""
    claude_md = _project(tmp_path, existing="# Target")
    original = claude_md.read_bytes()
    assert not original.endswith(b"\n")
    gb.upsert_block(claude_md, "bauplan", "rules")
    gb.remove_block(claude_md, "bauplan")
    assert claude_md.read_bytes() == original


@pytest.mark.parametrize(
    "label,seed",
    [
        ("lf", b"# Project\n\nReal user content.\n"),
        ("crlf", b"# Project\r\n\r\nReal user content.\r\n"),
    ],
)
def test_primitive_round_trip_is_byte_identical(
    gb: ModuleType, tmp_path: Path, label: str, seed: bytes
) -> None:
    """The PRIMITIVE pair, pinned directly — LF and CRLF alike.

    The three shipped installers call `upsert_block` / `remove_block` straight,
    not through `sync_block`, so the round-trip guarantee has to hold at this
    layer or their `--claude-md` paths are unprotected. Line endings are the
    file's own: a CRLF checkout must not come back LF."""
    claude_md = _project(tmp_path)
    claude_md.write_bytes(seed)
    gb.upsert_block(claude_md, "cap", "guide", create=True)
    assert claude_md.read_bytes() != seed, "upsert wrote nothing; the round trip is vacuous"
    gb.remove_block(claude_md, "cap")
    assert claude_md.read_bytes() == seed


@pytest.mark.parametrize(
    "label,seed",
    [
        ("lf", b"# Project\n\nReal user content.\n"),
        ("crlf", b"# Project\r\n\r\nReal user content.\r\n"),
        ("no-trailing-newline", b"# Project"),
    ],
)
def test_primitive_repeated_cycles_do_not_accumulate_bytes(
    gb: ModuleType, tmp_path: Path, label: str, seed: bytes
) -> None:
    """Five raw install/uninstall cycles leave the file byte-identical.

    Accumulation is the part that actually harms a user — the pre-existing
    defect added one newline per cycle, forever, in a file CT6 does not own —
    and a single-cycle assertion cannot see it. This is the shape of the
    assertion whose absence let the leak ship."""
    claude_md = _project(tmp_path)
    claude_md.write_bytes(seed)
    for _ in range(5):
        gb.upsert_block(claude_md, "cap", "guide", create=True)
        gb.remove_block(claude_md, "cap")
    assert claude_md.read_bytes() == seed


def test_sync_block_creates_nothing_when_the_trait_is_absent(
    gb: ModuleType, tmp_path: Path
) -> None:
    claude_md = _project(tmp_path)
    result = gb.sync_block(claude_md, "bauplan", "body",
                           capability_check=_always(False))
    assert result == "absent"
    assert not claude_md.exists()


def test_sync_block_without_a_target_never_touches_the_filesystem(
    gb: ModuleType, tmp_path: Path
) -> None:
    """4.6 at the helper layer — the opt-in target governs, in EITHER trait state."""
    for trait in (True, False):
        assert gb.sync_block(None, "bauplan", "body",
                             capability_check=_always(trait)) == "skipped"
    assert list(tmp_path.iterdir()) == []


def test_sync_block_twice_leaves_the_block_exactly_once(
    gb: ModuleType, tmp_path: Path
) -> None:
    """4.7 — idempotent: the second run reports no write and adds no duplicate."""
    claude_md = _project(tmp_path, existing="# Target\n")
    body = "## Bauplan\nrules"
    first = gb.sync_block(claude_md, "bauplan", body, capability_check=_always(True))
    second = gb.sync_block(claude_md, "bauplan", body, capability_check=_always(True))
    begin, _ = gb.block_fences("bauplan")
    assert (first, second) == ("written", "unchanged")
    assert claude_md.read_text(encoding="utf-8").count(begin) == 1


def test_sync_block_replaces_a_changed_body_in_place(
    gb: ModuleType, tmp_path: Path
) -> None:
    claude_md = _project(tmp_path, existing="# Target\n\ntail line\n")
    gb.sync_block(claude_md, "bauplan", "old body", capability_check=_always(True))
    result = gb.sync_block(claude_md, "bauplan", "new body",
                           capability_check=_always(True))
    text = claude_md.read_text(encoding="utf-8")
    assert result == "written"
    assert "new body" in text and "old body" not in text
    assert "# Target\n\ntail line\n" in text


def test_sync_block_evaluates_the_predicate_over_the_project_root(
    gb: ModuleType, tmp_path: Path
) -> None:
    """The predicate is a check over the TARGET PROJECT: it receives the project
    root — the CLAUDE.md's directory by default, or an explicit override."""
    claude_md = _project(tmp_path, existing="# Target\n")
    predicate = _always(True)
    gb.sync_block(claude_md, "bauplan", "body", capability_check=predicate)
    assert predicate.seen == [claude_md.parent]

    other = tmp_path / "elsewhere"
    other.mkdir()
    predicate2 = _always(True)
    gb.sync_block(claude_md, "bauplan", "body", capability_check=predicate2,
                  project_root=other)
    assert predicate2.seen == [other]


def test_sync_block_accepts_a_marker_style_tuple_predicate(
    gb: ModuleType, tmp_path: Path
) -> None:
    """`_has_frontend_markers`-shaped detectors return (bool, evidence). The gate
    accepts that shape verbatim, so `_has_bauplan_markers` needs no wrapper."""
    claude_md = _project(tmp_path, existing="# Target\n")
    assert gb.sync_block(claude_md, "bauplan", "body",
                         capability_check=_marker_style(True)) == "written"
    assert gb.sync_block(claude_md, "bauplan", "body",
                         capability_check=_marker_style(False)) == "removed"


def test_sync_block_can_create_the_file_when_asked(
    gb: ModuleType, tmp_path: Path
) -> None:
    claude_md = _project(tmp_path)
    assert gb.sync_block(claude_md, "bauplan", "body",
                         capability_check=_always(True), create=True) == "written"
    assert claude_md.exists()


def test_sync_block_respects_create_false(gb: ModuleType, tmp_path: Path) -> None:
    """create=False keeps the primitive's own contract: a missing file is a no-op."""
    claude_md = _project(tmp_path)
    assert gb.sync_block(claude_md, "bauplan", "body",
                         capability_check=_always(True), create=False) == "skipped"
    assert not claude_md.exists()


# =========================================================================== #
# 4.2 — the Bauplan safety-context body
# =========================================================================== #


def test_bauplan_body_carries_every_upstream_safety_rule(
    setup_module: ModuleType,
) -> None:
    """The six rules the upstream CLAUDE.md makes load-bearing."""
    body = setup_module.BAUPLAN_GUIDANCE_BODY
    lowered = body.lower()
    assert "main" in body
    assert "merge" in lowered                      # branch-and-merge to publish
    assert "--dry-run" in body                     # iterate on dry runs
    assert "hardcode" in lowered                   # never hardcode keys
    assert "secrets" in lowered or "parameters" in lowered
    assert "cli" in lowered and "sdk" in lowered   # CLI-vs-SDK guidance
    assert "polars" in lowered and "pandas" in lowered


def test_bauplan_body_attributes_the_upstream_source(setup_module: ModuleType) -> None:
    assert "BauplanLabs/bauplan-skills" in setup_module.BAUPLAN_GUIDANCE_BODY


def test_bauplan_body_never_asks_the_user_for_a_credential(
    setup_module: ModuleType,
) -> None:
    """CT6 never handles Bauplan credentials — the block must not instruct
    otherwise, and must not embed one."""
    body = setup_module.BAUPLAN_GUIDANCE_BODY
    assert "never ask" in body.lower()
    assert "sk-" not in body


def test_bauplan_body_stays_small_enough_for_a_users_claude_md(
    setup_module: ModuleType,
) -> None:
    """This lands in someone else's CLAUDE.md; a pointer-shaped block, not a manual."""
    assert len(setup_module.BAUPLAN_GUIDANCE_BODY.encode("utf-8")) <= 2048


def test_bauplan_capability_slug_is_a_valid_fence_token(
    setup_module: ModuleType, gb: ModuleType
) -> None:
    begin, end = gb.block_fences(setup_module.BAUPLAN_GUIDANCE_CAPABILITY)
    assert begin.startswith("<!-- ct6:guidance:") and end.endswith(":end -->")


# =========================================================================== #
# 4.3 / 4.4 — the consumer: marker-keyed, NOT plugin-keyed
# =========================================================================== #


def test_marker_present_and_plugin_absent_still_yields_the_block(
    setup_module: ModuleType, gb: ModuleType, tmp_path: Path
) -> None:
    """4.4 / D5 — the degraded path is exactly when the safety rules matter."""
    claude_md = _project(tmp_path, existing="# Target\n")
    # The plugin is genuinely absent — asserted against the real presence check,
    # not assumed — and the block is written anyway.
    _, absent = setup_module.check_plugin_presence(
        _installed(tmp_path, HARD_PLUGINS), setup_module.CONDITIONAL_PLUGINS
    )
    assert BAUPLAN_ID in absent
    name, status, detail = setup_module.sync_bauplan_guidance(
        claude_md, detector=_always(True)
    )
    begin, _ = gb.block_fences(setup_module.BAUPLAN_GUIDANCE_CAPABILITY)
    assert status == "present"
    assert begin in claude_md.read_text(encoding="utf-8")
    assert "bauplan" in name


def test_marker_absent_removes_the_block_byte_preserving(
    setup_module: ModuleType, gb: ModuleType, tmp_path: Path
) -> None:
    """A project that stops exhibiting the trait loses exactly the block: no
    fence byte remains and every user byte survives, with NO residue.

    The `original + b"\\n"` this once asserted was the round-trip leak, not a
    property of the design — see
    test_sync_block_add_then_remove_is_byte_identical."""
    claude_md = _project(tmp_path, existing="# Target\n\nkeep me\n")
    original = claude_md.read_bytes()
    setup_module.sync_bauplan_guidance(claude_md, detector=_always(True))
    name, status, detail = setup_module.sync_bauplan_guidance(
        claude_md, detector=_always(False)
    )
    begin, _ = gb.block_fences(setup_module.BAUPLAN_GUIDANCE_CAPABILITY)
    assert status == "removed"
    assert claude_md.read_bytes() == original
    assert begin not in claude_md.read_text(encoding="utf-8")


def test_running_twice_on_a_marker_project_leaves_one_block(
    setup_module: ModuleType, gb: ModuleType, tmp_path: Path
) -> None:
    claude_md = _project(tmp_path, existing="# Target\n")
    setup_module.sync_bauplan_guidance(claude_md, detector=_always(True))
    setup_module.sync_bauplan_guidance(claude_md, detector=_always(True))
    begin, _ = gb.block_fences(setup_module.BAUPLAN_GUIDANCE_CAPABILITY)
    assert claude_md.read_text(encoding="utf-8").count(begin) == 1


def test_check_only_never_modifies_the_target(
    setup_module: ModuleType, tmp_path: Path
) -> None:
    """`--check-only` never modifies user files — it reports what it WOULD do."""
    claude_md = _project(tmp_path, existing="# Target\n")
    original = claude_md.read_bytes()
    name, status, detail = setup_module.sync_bauplan_guidance(
        claude_md, check_only=True, detector=_always(True)
    )
    assert status == "note"
    assert "would" in (detail or "").lower()
    assert claude_md.read_bytes() == original


def test_an_unavailable_detector_is_a_skipped_row_that_touches_nothing(
    setup_module: ModuleType, tmp_path: Path
) -> None:
    """Fail-open: with no marker detector resolvable, the guidance step reports
    itself skipped rather than guessing at the project's shape."""
    claude_md = _project(tmp_path, existing="# Target\n")
    original = claude_md.read_bytes()
    with patch.object(setup_module, "_resolve_bauplan_detector", return_value=None):
        name, status, detail = setup_module.sync_bauplan_guidance(claude_md)
    assert status == "skipped"
    assert claude_md.read_bytes() == original


def test_a_guidance_write_failure_is_a_warn_row_never_a_gate(
    setup_module: ModuleType, tmp_path: Path
) -> None:
    """Guidance is best-effort: a failure to write it must never fail setup."""
    claude_md = _project(tmp_path, existing="# Target\n")
    with patch.object(setup_module._guidance, "sync_block",
                      side_effect=OSError("read-only filesystem")):
        name, status, detail = setup_module.sync_bauplan_guidance(
            claude_md, detector=_always(True)
        )
    assert status == "warn"
    assert status != "failed"
    assert "read-only filesystem" in (detail or "")


# =========================================================================== #
# main() wiring — the opt-in flag governs, and nothing here gates setup
# =========================================================================== #


def _installed(tmp_path: Path, plugin_ids: set[str]) -> Path:
    path = tmp_path / "installed_plugins.json"
    path.write_text(
        json.dumps({"version": 2, "plugins": {p: [{}] for p in sorted(plugin_ids)}}),
        encoding="utf-8",
    )
    return path


def _run_main(setup_module: ModuleType, installed_path: Path, argv: list[str],
              detector=None):
    """main() with every install seam stubbed and the marker detector injected."""
    rows: list[list] = []

    def _record(rows_arg, present, missing, **kwargs):
        rows.append(rows_arg)

    with patch.object(setup_module, "INSTALLED_PLUGINS_PATH", installed_path), \
         patch.object(setup_module, "ensure_openspec",
                      return_value=("openspec", "present", None)), \
         patch.object(setup_module, "ensure_python_test_tools",
                      return_value=("pytest+httpx+...", "present", None)), \
         patch.object(setup_module, "ensure_playwright",
                      return_value=("playwright", "present", None)), \
         patch.object(setup_module, "check_teams_mode",
                      return_value=("teams-mode", "present", None)), \
         patch.object(setup_module, "ensure_openspec_propose_skill",
                      return_value=("openspec-propose", "present", "vendored")), \
         patch.object(setup_module, "_resolve_bauplan_detector",
                      return_value=detector), \
         patch.object(setup_module, "_write_last_run", side_effect=_record):
        rc = setup_module.main(argv)
    return rc, (rows[-1] if rows else [])


@pytest.mark.parametrize("trait", [True, False])
def test_no_claude_md_flag_means_no_file_created_or_modified(
    setup_module: ModuleType, tmp_path: Path, trait: bool
) -> None:
    """4.6 — the opt-in flag governs, in EITHER trait state."""
    claude_md = _project(tmp_path, existing="# Target\n")
    original = claude_md.read_bytes()
    other = tmp_path / "target" / "NOTES.md"
    rc, _ = _run_main(setup_module, _installed(tmp_path, HARD_PLUGINS),
                      ["--check-only"], detector=_always(trait))
    assert rc == 0
    assert claude_md.read_bytes() == original
    assert not other.exists()


def test_main_with_the_flag_writes_the_block_on_a_marker_project(
    setup_module: ModuleType, gb: ModuleType, tmp_path: Path
) -> None:
    claude_md = _project(tmp_path, existing="# Target\n")
    rc, rows = _run_main(
        setup_module,
        _installed(tmp_path, HARD_PLUGINS),
        ["--claude-md", str(claude_md)],
        detector=_always(True),
    )
    begin, _ = gb.block_fences(setup_module.BAUPLAN_GUIDANCE_CAPABILITY)
    assert rc == 0
    assert begin in claude_md.read_text(encoding="utf-8")
    assert any("bauplan-guidance" in str(r[0]) for r in rows)


def test_main_with_the_flag_creates_a_claude_md_when_absent(
    setup_module: ModuleType, gb: ModuleType, tmp_path: Path
) -> None:
    """A marker project with no CLAUDE.md yet still gets the safety context."""
    claude_md = _project(tmp_path)
    rc, _ = _run_main(setup_module, _installed(tmp_path, HARD_PLUGINS),
                      ["--claude-md", str(claude_md)], detector=_always(True))
    begin, _ = gb.block_fences(setup_module.BAUPLAN_GUIDANCE_CAPABILITY)
    assert rc == 0
    assert begin in claude_md.read_text(encoding="utf-8")


def test_main_guidance_row_never_carries_a_gating_status(
    setup_module: ModuleType, tmp_path: Path
) -> None:
    """The guidance row rides in `rows`, which the `-> 2` branch reads — so it
    must never carry the 'failed' status, in any trait state."""
    claude_md = _project(tmp_path, existing="# Target\n")
    for trait in (True, False):
        rc, rows = _run_main(setup_module, _installed(tmp_path, HARD_PLUGINS),
                             ["--claude-md", str(claude_md)],
                             detector=_always(trait))
        guidance = [r for r in rows if "bauplan-guidance" in str(r[0])]
        assert guidance, "guidance row missing from the report"
        assert all(r[1] != "failed" for r in guidance)
        assert rc == 0
