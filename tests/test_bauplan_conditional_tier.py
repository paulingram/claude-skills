"""The conditional plugin tier in scripts/setup/setup.py (SRC-001 / D1).

`REQUIRED_PLUGINS` is the HARD set: a missing member reaches `if missing: return 1`
in `main()`. The conditional tier is a SIBLING registry whose members are checked
and reported but whose absence can never influence the exit code.

The load-bearing invariant these tests pin is negative — *nothing about the
conditional tier reaches the exit-1 branch* — so it is proved three ways:

  1. behaviorally, through `main()`: conditional absent + hard set present => 0;
  2. structurally, by capturing what `main()` actually feeds the exit branch
     (the `missing` set handed to `_write_last_run`) and asserting no conditional
     member is in it, in either conditional state;
  3. by the disjoint-sets invariant, so a future edit cannot smuggle a
     conditional member into the hard set.

Plus the SRC-001 REGRESSION assertion: adding the tier must not weaken the hard
set — openspec-propose stays in the verified set and its absence still exits 1.

Hermetic: tmp installed_plugins.json, every installer seam patched, and
`_write_last_run` patched so no test writes scripts/setup/.last-run.json.
"""
from __future__ import annotations

import json
from pathlib import Path
from types import ModuleType
from unittest.mock import patch

import pytest
from tests.helpers.module_loader import load_module

BAUPLAN_ID = "bauplan@bauplan-skills"
BAUPLAN_SOURCE = "BauplanLabs/bauplan-skills"

HARD_PLUGINS = {
    "superpowers@claude-plugins-official",
    "cartographer@cartographer-marketplace",
    "ralph-loop@claude-plugins-official",
}


@pytest.fixture(scope="module")
def setup_module(plugin_root: Path) -> ModuleType:
    path = plugin_root / "scripts" / "setup" / "setup.py"
    assert path.exists(), f"setup.py missing at {path}"
    return load_module(path, "setup_module_bauplan_tier")


def _installed(tmp_path: Path, plugin_ids: set[str]) -> Path:
    """Write an installed_plugins.json listing exactly plugin_ids."""
    path = tmp_path / "installed_plugins.json"
    path.write_text(
        json.dumps({"version": 2, "plugins": {p: [{}] for p in sorted(plugin_ids)}}),
        encoding="utf-8",
    )
    return path


def _run_main(setup_module: ModuleType, installed_path: Path, **overrides):
    """Run main(['--check-only']) with every install/network seam stubbed.

    Returns (exit_code, last_run_calls) where last_run_calls records the
    positional (rows, present, missing) that main() handed the audit writer —
    the same `missing` the `if missing: return 1` branch reads.
    """
    calls: list[tuple] = []

    def _record(rows, present, missing, **kwargs):
        calls.append((rows, present, missing, kwargs))

    propose_row = overrides.pop(
        "openspec_propose_row", ("openspec-propose", "present", "vendored")
    )
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
                      return_value=propose_row), \
         patch.object(setup_module, "_write_last_run", side_effect=_record):
        rc = setup_module.main(["--check-only"])
    return rc, calls


# =========================================================================== #
# 1.1 / 1.2 / 1.6 — the registries
# =========================================================================== #


def test_conditional_plugins_registry_holds_bauplan(setup_module: ModuleType) -> None:
    """The conditional tier exists as a sibling registry carrying bauplan."""
    assert BAUPLAN_ID in setup_module.CONDITIONAL_PLUGINS


def test_conditional_tier_and_required_set_are_disjoint(setup_module: ModuleType) -> None:
    """The spec-pinned invariant: no plugin id may appear in both tiers."""
    assert not (setup_module.CONDITIONAL_PLUGINS & setup_module.REQUIRED_PLUGINS)


def test_hard_set_is_not_weakened_by_the_new_tier(setup_module: ModuleType) -> None:
    """REGRESSION — the three hard prerequisites are untouched by this change."""
    assert setup_module.REQUIRED_PLUGINS == HARD_PLUGINS


def test_bauplan_marketplace_source_is_registered(setup_module: ModuleType) -> None:
    """Reuse: provenance goes through the EXISTING _PLUGIN_MARKETPLACE_SOURCES map."""
    assert setup_module._PLUGIN_MARKETPLACE_SOURCES[BAUPLAN_ID] == BAUPLAN_SOURCE


# =========================================================================== #
# 1.7 — remediation ordering, produced by the existing helper
# =========================================================================== #


def test_bauplan_remediation_is_marketplace_add_then_install(
    setup_module: ModuleType,
) -> None:
    """plugin_remediation_lines() emits the marketplace-add line FIRST."""
    assert setup_module.plugin_remediation_lines(BAUPLAN_ID) == [
        f"/plugin marketplace add {BAUPLAN_SOURCE}",
        f"/plugin install {BAUPLAN_ID}",
    ]


def test_conditional_remediation_comes_from_the_shared_helper(
    setup_module: ModuleType, capsys
) -> None:
    """No duplicate remediation machinery: the printed guidance for an absent
    conditional member is exactly plugin_remediation_lines()' output."""
    setup_module._print_report([], [], [], conditional_absent=[BAUPLAN_ID])
    out = capsys.readouterr().out
    for line in setup_module.plugin_remediation_lines(BAUPLAN_ID):
        assert line in out


# =========================================================================== #
# 1.3 — distinct report rows
# =========================================================================== #


def test_absent_conditional_row_is_distinguished_from_a_missing_hard_row(
    setup_module: ModuleType, capsys
) -> None:
    """An absent conditional member never renders under the HARD 'MISSING' block,
    and its section says plainly that it does not block."""
    setup_module._print_report(
        [],
        [],
        ["ralph-loop@claude-plugins-official"],
        conditional_absent=[BAUPLAN_ID],
    )
    out = capsys.readouterr().out
    hard_block, _, conditional_block = out.partition("Optional plugins")
    assert "REQUIRED plugins MISSING" in hard_block
    assert BAUPLAN_ID not in hard_block
    assert BAUPLAN_ID in conditional_block
    assert "never" in conditional_block.lower()


def test_present_conditional_row_is_distinguished_from_a_present_hard_row(
    setup_module: ModuleType, capsys
) -> None:
    """A present conditional member is reported present and visibly marked
    conditional, so it cannot be read as a hard prerequisite."""
    setup_module._print_report(
        [],
        ["superpowers@claude-plugins-official"],
        [],
        conditional_present=[BAUPLAN_ID],
    )
    out = capsys.readouterr().out
    bauplan_line = next(ln for ln in out.splitlines() if BAUPLAN_ID in ln)
    assert "present" in bauplan_line
    assert "conditional" in bauplan_line.lower()
    superpowers_line = next(
        ln for ln in out.splitlines() if "superpowers@" in ln
    )
    assert "conditional" not in superpowers_line.lower()


# =========================================================================== #
# 1.4 / 1.5 — the exit code
# =========================================================================== #


def test_conditional_absent_with_hard_present_exits_zero(
    setup_module: ModuleType, tmp_path: Path, capsys
) -> None:
    """1.4 — the whole point of the tier: absence is reported, never fatal."""
    rc, _ = _run_main(setup_module, _installed(tmp_path, HARD_PLUGINS))
    out = capsys.readouterr().out
    assert rc == 0
    assert BAUPLAN_ID in out


def test_conditional_present_with_hard_present_exits_zero(
    setup_module: ModuleType, tmp_path: Path, capsys
) -> None:
    """The present state is equally non-fatal, and reported."""
    rc, _ = _run_main(setup_module, _installed(tmp_path, HARD_PLUGINS | {BAUPLAN_ID}))
    out = capsys.readouterr().out
    assert rc == 0
    assert BAUPLAN_ID in out


@pytest.mark.parametrize("conditional_installed", [False, True])
def test_missing_hard_prerequisite_still_exits_one_in_both_conditional_states(
    setup_module: ModuleType, tmp_path: Path, conditional_installed: bool
) -> None:
    """1.5 — the conditional tier cannot mask a hard failure in either state."""
    installed = HARD_PLUGINS - {"ralph-loop@claude-plugins-official"}
    if conditional_installed:
        installed = installed | {BAUPLAN_ID}
    rc, _ = _run_main(setup_module, _installed(tmp_path, installed))
    assert rc == 1


@pytest.mark.parametrize("conditional_installed", [False, True])
def test_openspec_propose_absence_still_exits_one_in_both_conditional_states(
    setup_module: ModuleType, tmp_path: Path, conditional_installed: bool
) -> None:
    """SRC-001 REGRESSION — openspec-propose stays a verified prerequisite whose
    absence contributes to a non-zero exit. Adding the conditional tier must not
    weaken the hard set, and a PRESENT conditional member must not offset it."""
    installed = HARD_PLUGINS | ({BAUPLAN_ID} if conditional_installed else set())
    rc, _ = _run_main(
        setup_module,
        _installed(tmp_path, installed),
        openspec_propose_row=("openspec-propose", "missing", "not found"),
    )
    assert rc == 1


# =========================================================================== #
# The structural proof: the conditional tier never reaches the exit branch
# =========================================================================== #


@pytest.mark.parametrize("conditional_installed", [False, True])
def test_conditional_state_never_enters_the_exit_branch_input(
    setup_module: ModuleType, tmp_path: Path, conditional_installed: bool
) -> None:
    """`main()` computes `missing` from REQUIRED_PLUGINS alone and that set — the
    one `if missing: return 1` reads — never contains a conditional member."""
    installed = HARD_PLUGINS | ({BAUPLAN_ID} if conditional_installed else set())
    _, calls = _run_main(setup_module, _installed(tmp_path, installed))
    assert calls, "main() did not reach the audit writer"
    rows, present, missing, _kwargs = calls[-1]
    assert not (set(missing) & setup_module.CONDITIONAL_PLUGINS)
    assert not (set(present) & setup_module.CONDITIONAL_PLUGINS)
    assert set(missing) | set(present) <= setup_module.REQUIRED_PLUGINS


def test_conditional_tier_adds_no_row_that_could_trigger_exit_two(
    setup_module: ModuleType, tmp_path: Path
) -> None:
    """The other exit path reads `rows`: `any(r[1] == 'failed') -> 2`. The
    conditional tier contributes no row at all, so it cannot reach that branch
    either."""
    _, calls = _run_main(setup_module, _installed(tmp_path, HARD_PLUGINS))
    rows = calls[-1][0]
    assert not any(BAUPLAN_ID in str(r) for r in rows)
    assert not any(r[1] == "failed" for r in rows)


def test_conditional_state_is_recorded_in_the_audit_file_payload(
    setup_module: ModuleType, tmp_path: Path
) -> None:
    """The tier is reported, not merely swallowed: main() hands its state to the
    audit writer under its own keys, distinct from the hard-tier keys."""
    _, calls = _run_main(setup_module, _installed(tmp_path, HARD_PLUGINS))
    kwargs = calls[-1][3]
    assert BAUPLAN_ID in set(kwargs["conditional_absent"])
    assert not set(kwargs["conditional_present"])


def test_write_last_run_records_the_conditional_tier_separately(
    setup_module: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The audit JSON keeps the two tiers in separate keys — a reader can never
    mistake an absent conditional member for a missing prerequisite."""
    monkeypatch.setattr(setup_module, "__file__", str(tmp_path / "setup.py"))
    setup_module._write_last_run(
        [("python", "present", None)],
        {"superpowers@claude-plugins-official"},
        set(),
        conditional_present=set(),
        conditional_absent={BAUPLAN_ID},
    )
    payload = json.loads((tmp_path / ".last-run.json").read_text(encoding="utf-8"))
    assert payload["plugins_missing"] == []
    assert payload["conditional_plugins_absent"] == [BAUPLAN_ID]
    assert payload["conditional_plugins_present"] == []
