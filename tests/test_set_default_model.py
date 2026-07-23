"""Tests for scripts/setup/set_default_model.py — the uniform agent-model lever.

The v3.43.0 ship state is the delivery-adversarial Opus split (12 delivery +
adversarial agents on ``model: opus``, the rest on ``fable``); this stdlib CLI is
the sanctioned, deterministic lever that rewrites the frontmatter ``model:`` field
— uniformly (``--model``, incl. the implemented Opus-4.8 fallback), on the gateway
secondary role split (``--split secondary``), or on the delivery/adversarial Opus
split (``--split delivery``). These tests exercise the lever against a throwaway
copy of the real ``agents/`` directory so they are robust to whatever the committed
model state happens to be.

Module-load style mirrors tests/test_teams_mode.py: loaded via importlib, NOT a
package import.
"""
from __future__ import annotations

import importlib.util
import shutil
from pathlib import Path
from types import ModuleType

import pytest
from tests.helpers.module_loader import load_module

REPO_ROOT = Path(__file__).resolve().parents[1]


def _load() -> ModuleType:
    path = REPO_ROOT / "scripts" / "setup" / "set_default_model.py"
    assert path.exists(), f"set_default_model.py missing at {path}"
    mod = load_module(path, "set_default_model_module")
    return mod


@pytest.fixture(scope="module")
def mod() -> ModuleType:
    return _load()


@pytest.fixture()
def tmp_agents(tmp_path: Path) -> Path:
    """A throwaway copy of the real agents/ directory."""
    dst = tmp_path / "agents"
    shutil.copytree(REPO_ROOT / "agents", dst)
    return dst


# --------------------------------------------------------------------------- #
# flip semantics
# --------------------------------------------------------------------------- #

def test_flip_to_opus_makes_all_uniform(mod: ModuleType, tmp_agents: Path) -> None:
    mod.set_model(tmp_agents, "opus")
    assert mod.distribution(tmp_agents) == {"opus": 39}


def test_flip_back_to_fable(mod: ModuleType, tmp_agents: Path) -> None:
    mod.set_model(tmp_agents, "opus")
    mod.set_model(tmp_agents, "fable")
    assert mod.distribution(tmp_agents) == {"fable": 39}


def test_flip_only_touches_the_model_line(mod: ModuleType, tmp_agents: Path) -> None:
    """Bodies stay byte-identical except the single frontmatter ``model:`` line."""
    # Establish a deterministic uniform baseline so every file genuinely changes
    # on the next flip regardless of the committed state.
    mod.set_model(tmp_agents, "haiku")
    baseline = {p.name: p.read_text(encoding="utf-8") for p in tmp_agents.glob("*.md")}
    mod.set_model(tmp_agents, "opus")
    for p in sorted(tmp_agents.glob("*.md")):
        before = baseline[p.name].splitlines()
        after = p.read_text(encoding="utf-8").splitlines()
        assert len(before) == len(after), f"{p.name}: line count changed"
        diffs = [i for i, (b, a) in enumerate(zip(before, after)) if b != a]
        assert len(diffs) == 1, f"{p.name}: expected exactly one changed line, got {diffs}"
        i = diffs[0]
        assert before[i].lstrip().startswith("model:"), f"{p.name}: changed line is not the model line"
        assert after[i].strip() == "model: opus", f"{p.name}: model line not rewritten"


def test_idempotent(mod: ModuleType, tmp_agents: Path) -> None:
    mod.set_model(tmp_agents, "opus")
    assert mod.set_model(tmp_agents, "opus") == []


def test_trailing_bytes_preserved(mod: ModuleType, tmp_agents: Path) -> None:
    """The whole-file bytes outside the model line survive a flip verbatim."""
    mod.set_model(tmp_agents, "sonnet")
    sample = sorted(tmp_agents.glob("*.md"))[0]
    before = sample.read_bytes()
    mod.set_model(tmp_agents, "opus")
    after = sample.read_bytes()
    assert before.replace(b"model: sonnet", b"model: opus", 1) == after


# --------------------------------------------------------------------------- #
# --check reporting
# --------------------------------------------------------------------------- #

def test_check_reports_uniform_fable(mod: ModuleType, tmp_agents: Path, capsys) -> None:
    mod.set_model(tmp_agents, "fable")
    rc = mod.main(["--check", "--agents-dir", str(tmp_agents)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "fable: 39" in out
    assert "uniform: yes (fable)" in out


def test_check_reports_mixed(mod: ModuleType, tmp_agents: Path, capsys) -> None:
    mod.set_model(tmp_agents, "opus")
    one = sorted(tmp_agents.glob("*.md"))[0]
    one.write_text(
        one.read_text(encoding="utf-8").replace("model: opus", "model: sonnet", 1),
        encoding="utf-8",
    )
    rc = mod.main(["--check", "--agents-dir", str(tmp_agents)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "uniform: no" in out
    assert "opus: 38" in out
    assert "sonnet: 1" in out


# --------------------------------------------------------------------------- #
# validation + CLI
# --------------------------------------------------------------------------- #

def test_unknown_model_rejected_touches_nothing(mod: ModuleType, tmp_agents: Path) -> None:
    before = {p.name: p.read_bytes() for p in tmp_agents.glob("*.md")}
    rc = mod.main(["--model", "gpt-4o", "--agents-dir", str(tmp_agents)])
    assert rc == 1
    after = {p.name: p.read_bytes() for p in tmp_agents.glob("*.md")}
    assert before == after


def test_main_model_flip_returns_zero(mod: ModuleType, tmp_agents: Path) -> None:
    rc = mod.main(["--model", "fable", "--agents-dir", str(tmp_agents)])
    assert rc == 0
    assert mod.distribution(tmp_agents) == {"fable": 39}


def test_valid_models_are_the_four(mod: ModuleType) -> None:
    assert set(mod.VALID_MODELS) == {"fable", "opus", "sonnet", "haiku"}


def test_secondary_provider_registry_shape(mod: ModuleType) -> None:
    assert mod.SECONDARY_ALIAS == "ct6-secondary"
    assert mod.LEGACY_SECONDARY_ALIASES == ("codex-5.6-sol",)
    assert mod.CODEX_MODEL == "codex-5.6-sol"
    # v3.41.0: the spawn-compatible impersonation alias — a REAL Claude id the
    # Agent-Teams spawn gate accepts (it rejects custom ids client-side with
    # zero HTTP; gateway-log verified 2026-07-17). Deliberately pinned:
    # changing this id changes which real model id the gateway impersonates.
    assert mod.SPAWN_ALIAS_MODEL_ID == "claude-haiku-4-5"
    assert mod.SUPERSEDED_FRONTMATTER_ALIASES == ("codex-5.6-sol", "ct6-secondary")
    # route_model is GONE (derive-shape, v3.41.0): the gateway route is
    # derived as `<route_dialect>/<model>`, so an entry cannot carry a route
    # string inconsistent with its dialect. `openai` keeps the Responses-API
    # dialect (codex-gen requires /responses); `zai` rides the strict
    # chat-completions `hosted_vllm` dialect (api.z.ai has no /responses —
    # live 404 at /v4/responses).
    assert mod.SECONDARY_PROVIDERS == {
        "openai": {
            "model": "gpt-5.6-sol",
            "key_env": "OPENAI_API_KEY",
            "route_dialect": "openai",
            "api_base": None,
            "label": "OpenAI — Codex 5.6 (gpt-5.6-sol)",
        },
        "zai": {
            "model": "glm-5.2",
            "key_env": "ZAI_API_KEY",
            "route_dialect": "hosted_vllm",
            "api_base": "https://api.z.ai/api/paas/v4",
            "label": "Z.ai — GLM 5.2 (glm-5.2)",
        },
    }


def test_registry_entries_require_a_consistent_route_dialect(mod: ModuleType) -> None:
    """B4-note extensibility pin (glm-secondary-route-fix): every current AND
    future SECONDARY_PROVIDERS entry MUST declare its route dialect, and the
    derive-shape forbids a coexisting `route_model` field — a future entry can
    therefore never carry a route string inconsistent with its dialect (the
    class of bug that 404'd every zai call at /v4/responses)."""
    required = {"model", "key_env", "route_dialect", "api_base", "label"}
    for name, entry in mod.SECONDARY_PROVIDERS.items():
        assert set(entry) == required, (
            f"SECONDARY_PROVIDERS[{name!r}] keys {sorted(entry)} != "
            f"{sorted(required)} — route_dialect is REQUIRED and route_model "
            f"must NOT be reintroduced (the route derives from the dialect)")
        dialect = entry["route_dialect"]
        assert isinstance(dialect, str) and dialect and "/" not in dialect, (
            f"SECONDARY_PROVIDERS[{name!r}].route_dialect={dialect!r} must be "
            f"a bare LiteLLM provider prefix (no slash)")


def test_default_agents_dir_resolves(mod: ModuleType) -> None:
    d = mod._default_agents_dir()
    assert d.is_dir() and d.name == "agents"


# --------------------------------------------------------------------------- #
# Codex 5.6 role split (v3.35.0)
# --------------------------------------------------------------------------- #

def _model_of(agents_dir: Path, stem: str, mod: ModuleType) -> str:
    text = (agents_dir / f"{stem}.md").read_text(encoding="utf-8")
    return mod.read_model_value(text)


def test_role_map_covers_exactly_the_shipped_agents(mod: ModuleType, tmp_agents: Path) -> None:
    """Every shipped agent stem is classified, no stale stems linger, and the
    two role buckets are disjoint — a newly added agent must be classified (or
    it defaults to the fable bucket and shows up in --check as unclassified)."""
    stems = {p.stem for p in tmp_agents.glob("*.md")}
    assert set(mod.AGENT_ROLES) == stems, "AGENT_ROLES drifted from agents/*.md"
    overlap = mod.ARCHITECTURE_CONTROL_DESIGN_AGENTS & mod.DEVELOPMENT_CHECKING_TESTING_AGENTS
    assert not overlap, f"agents classified in BOTH role buckets: {overlap}"


def test_split_applies_the_role_models(mod: ModuleType, tmp_agents: Path) -> None:
    """v3.41.0: the split's frontmatter target is the SPAWN-COMPATIBLE
    impersonation alias, not the raw ct6-secondary — the harness spawn gate
    rejects custom ids client-side, so a dev-class agent left on a custom
    alias never reaches the gateway (BUG-B)."""
    mod.apply_split(tmp_agents)
    dist = mod.distribution(tmp_agents)
    assert dist == {
        "fable": len(mod.ARCHITECTURE_CONTROL_DESIGN_AGENTS),
        mod.SPAWN_ALIAS_MODEL_ID: len(mod.DEVELOPMENT_CHECKING_TESTING_AGENTS),
    }


def test_split_role_spot_checks(mod: ModuleType, tmp_agents: Path) -> None:
    """The owner directive verbatim: development + code checking + testing on
    the (spawn-compatible) secondary alias; architecture + control + design on
    fable."""
    mod.apply_split(tmp_agents)
    for dev in ("backend", "frontend", "integration", "task-reviewer",
                "adversarial-reviewer", "qa-replayer", "test-completeness-verifier"):
        assert _model_of(tmp_agents, dev, mod) == mod.SPAWN_ALIAS_MODEL_ID, dev
    for arch in ("system-architect", "oracle-deriver", "mcp-design-agent",
                 "master-synthesizer", "prompt-refiner", "route-mapper"):
        assert _model_of(tmp_agents, arch, mod) == "fable", arch


def test_split_is_idempotent(mod: ModuleType, tmp_agents: Path) -> None:
    mod.apply_split(tmp_agents)
    assert mod.apply_split(tmp_agents) == []


def test_split_only_touches_the_model_line(mod: ModuleType, tmp_agents: Path) -> None:
    mod.set_model(tmp_agents, "haiku")
    baseline = {p.name: p.read_text(encoding="utf-8") for p in tmp_agents.glob("*.md")}
    mod.apply_split(tmp_agents)
    for p in sorted(tmp_agents.glob("*.md")):
        before = baseline[p.name].splitlines()
        after = p.read_text(encoding="utf-8").splitlines()
        assert len(before) == len(after), f"{p.name}: line count changed"
        diffs = [i for i, (b, a) in enumerate(zip(before, after)) if b != a]
        assert len(diffs) == 1, f"{p.name}: expected exactly one changed line"
        assert before[diffs[0]].lstrip().startswith("model:"), p.name


def test_apply_policy_available_applies_split(mod: ModuleType, tmp_agents: Path) -> None:
    mod.set_model(tmp_agents, "fable")  # deterministic baseline (the ship state)
    policy, changed = mod.apply_policy(tmp_agents, True)
    assert policy == "secondary-split"
    assert sorted(changed) == sorted(mod.DEVELOPMENT_CHECKING_TESTING_AGENTS)
    assert mod.policy_state(tmp_agents) == "secondary-split"


def test_apply_policy_unavailable_restores_the_operating_model(
    mod: ModuleType, tmp_agents: Path
) -> None:
    """No codex => the current operating model: uniform fable (the Opus
    fallback where fable is unavailable stays the --model opus lever)."""
    mod.apply_split(tmp_agents)
    policy, changed = mod.apply_policy(tmp_agents, False)
    assert policy == "uniform-fable"
    assert sorted(changed) == sorted(mod.DEVELOPMENT_CHECKING_TESTING_AGENTS)
    assert mod.distribution(tmp_agents) == {"fable": 39}


def test_policy_state_transitions(mod: ModuleType, tmp_agents: Path) -> None:
    mod.set_model(tmp_agents, "fable")
    assert mod.policy_state(tmp_agents) == "uniform-fable"
    mod.apply_split(tmp_agents)
    assert mod.policy_state(tmp_agents) == "secondary-split"
    one = tmp_agents / "backend.md"
    one.write_text(
        one.read_text(encoding="utf-8").replace(
            f"model: {mod.SPAWN_ALIAS_MODEL_ID}", "model: sonnet", 1
        ),
        encoding="utf-8",
    )
    assert mod.policy_state(tmp_agents) == "mixed"
    mod.set_model(tmp_agents, "opus")
    assert mod.policy_state(tmp_agents) == "uniform-opus"


def test_policy_state_recognizes_legacy_alias_split(
    mod: ModuleType, tmp_agents: Path
) -> None:
    mod.apply_split(tmp_agents, mod.CODEX_MODEL)
    assert mod.policy_state(tmp_agents) == "secondary-split"


def test_policy_state_recognizes_every_alias_generation(
    mod: ModuleType, tmp_agents: Path
) -> None:
    """All three split generations classify as secondary-split: the v3.41
    spawn alias (the default), the v3.40 neutral ct6-secondary, and the
    legacy provider alias — an installed copy from any era is recognized
    instead of read as 'mixed'."""
    for alias in (mod.SPAWN_ALIAS_MODEL_ID, mod.SECONDARY_ALIAS,
                  *mod.LEGACY_SECONDARY_ALIASES):
        mod.apply_split(tmp_agents, alias)
        assert mod.policy_state(tmp_agents) == "secondary-split", alias


def test_policy_state_override_still_recognizes_current_alias(
    mod: ModuleType, tmp_agents: Path
) -> None:
    mod.apply_split(tmp_agents)
    assert mod.policy_state(tmp_agents, mod.CODEX_MODEL) == "secondary-split"


@pytest.mark.parametrize("superseded_attr", ["CODEX_MODEL", "SECONDARY_ALIAS"])
def test_migrate_legacy_split_rewrites_and_is_idempotent(
    mod: ModuleType, tmp_agents: Path, superseded_attr: str
) -> None:
    """Both superseded frontmatter generations — the legacy provider alias AND
    the v3.40 raw ct6-secondary (spawn-dead under the harness gate, BUG-B) —
    migrate to the spawn-compatible alias, idempotently."""
    mod.apply_split(tmp_agents, getattr(mod, superseded_attr))
    changed = mod.migrate_legacy_split(tmp_agents)
    assert sorted(changed) == sorted(mod.DEVELOPMENT_CHECKING_TESTING_AGENTS)
    assert mod.distribution(tmp_agents) == {
        "fable": len(mod.ARCHITECTURE_CONTROL_DESIGN_AGENTS),
        mod.SPAWN_ALIAS_MODEL_ID: len(mod.DEVELOPMENT_CHECKING_TESTING_AGENTS),
    }
    assert mod.policy_state(tmp_agents) == "secondary-split"
    assert mod.migrate_legacy_split(tmp_agents) == []


def test_codex_available_env_parsing(mod: ModuleType) -> None:
    for truthy in ("1", "true", "YES", " True "):
        assert mod.codex_available({mod.CODEX_ENV_VAR: truthy}) is True, truthy
    for falsy in ("0", "false", "no", ""):
        assert mod.codex_available({mod.CODEX_ENV_VAR: falsy}) is False, falsy
    assert mod.codex_available({}) is False


def test_codex_signal_from_env_is_tri_state(mod: ModuleType) -> None:
    """Truthy => True; SET-but-falsy => False (explicit unavailability); the
    var ABSENT => None (no signal — callers must leave the state untouched)."""
    assert mod.codex_signal_from_env({mod.CODEX_ENV_VAR: "1"}) is True
    assert mod.codex_signal_from_env({mod.CODEX_ENV_VAR: "0"}) is False
    assert mod.codex_signal_from_env({mod.CODEX_ENV_VAR: ""}) is False
    assert mod.codex_signal_from_env({}) is None


def test_role_for_unknown_stem_defaults_to_fable_bucket(mod: ModuleType) -> None:
    """Fail-safe: an unclassified (e.g. newly scaffolded) agent never lands on
    codex — it defaults to the architecture/control/design (fable) bucket."""
    assert mod.role_for("some-brand-new-agent") == mod.ROLE_ARCHITECTURE
    assert mod.role_for("backend") == mod.ROLE_DEVELOPMENT


def test_unclassified_stems_surface_in_check(mod: ModuleType, tmp_agents: Path, capsys) -> None:
    (tmp_agents / "brand-new-agent.md").write_text(
        "---\nname: brand-new-agent\nmodel: fable\n---\nbody\n", encoding="utf-8"
    )
    rc = mod.main(["--check", "--agents-dir", str(tmp_agents)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "unclassified" in out and "brand-new-agent" in out


def test_cli_split_secondary(mod: ModuleType, tmp_agents: Path, capsys) -> None:
    rc = mod.main(["--split", "secondary", "--agents-dir", str(tmp_agents)])
    captured = capsys.readouterr()
    assert rc == 0
    assert "secondary-split" in captured.out
    assert captured.err == ""
    assert mod.policy_state(tmp_agents) == "secondary-split"


def test_cli_split_codex_is_deprecated_synonym(
    mod: ModuleType, tmp_agents: Path, capsys
) -> None:
    rc = mod.main(["--split", "codex", "--agents-dir", str(tmp_agents)])
    captured = capsys.readouterr()
    assert rc == 0
    assert "secondary-split" in captured.out
    assert "deprecated" in captured.err.lower()
    assert "--split secondary" in captured.err
    assert mod.policy_state(tmp_agents) == "secondary-split"


def test_cli_auto_follows_the_env_signal(
    mod: ModuleType, tmp_agents: Path, monkeypatch, capsys
) -> None:
    monkeypatch.setenv(mod.CODEX_ENV_VAR, "1")
    assert mod.main(["--auto", "--agents-dir", str(tmp_agents)]) == 0
    assert mod.policy_state(tmp_agents) == "secondary-split"
    monkeypatch.setenv(mod.CODEX_ENV_VAR, "0")
    assert mod.main(["--auto", "--agents-dir", str(tmp_agents)]) == 0
    out = capsys.readouterr().out
    assert "uniform-fable" in out
    assert mod.distribution(tmp_agents) == {"fable": 39}


def test_cli_auto_without_signal_leaves_state_untouched(
    mod: ModuleType, tmp_agents: Path, monkeypatch, capsys
) -> None:
    """--auto with CT6_CODEX_56_AVAILABLE ABSENT is a no-op: a manually applied
    lever state (e.g. the Opus fallback for a pre-fable harness) is never
    silently clobbered back to fable."""
    monkeypatch.delenv(mod.CODEX_ENV_VAR, raising=False)
    mod.set_model(tmp_agents, "opus")  # the sanctioned manual Opus fallback state
    before = {p.name: p.read_bytes() for p in tmp_agents.glob("*.md")}
    assert mod.main(["--auto", "--agents-dir", str(tmp_agents)]) == 0
    out = capsys.readouterr().out
    assert "no availability signal" in out
    assert "untouched" in out
    assert before == {p.name: p.read_bytes() for p in tmp_agents.glob("*.md")}


def test_cli_check_reports_policy_state(mod: ModuleType, tmp_agents: Path, capsys) -> None:
    mod.set_model(tmp_agents, "fable")
    mod.main(["--check", "--agents-dir", str(tmp_agents)])
    assert "policy: uniform-fable" in capsys.readouterr().out
    mod.apply_split(tmp_agents)
    mod.main(["--check", "--agents-dir", str(tmp_agents)])
    assert "policy: secondary-split" in capsys.readouterr().out


def test_cli_secondary_model_override(mod: ModuleType, tmp_agents: Path) -> None:
    rc = mod.main([
        "--split", "secondary", "--secondary-model", "ct6-secondary-luna",
        "--agents-dir", str(tmp_agents),
    ])
    assert rc == 0
    assert _model_of(tmp_agents, "backend", mod) == "ct6-secondary-luna"
    assert _model_of(tmp_agents, "system-architect", mod) == "fable"
    assert mod.policy_state(tmp_agents, "ct6-secondary-luna") == "secondary-split"


def test_cli_codex_model_override_is_synonym(mod: ModuleType, tmp_agents: Path) -> None:
    rc = mod.main([
        "--split", "secondary", "--codex-model", "ct6-secondary-luna",
        "--agents-dir", str(tmp_agents),
    ])
    assert rc == 0
    assert _model_of(tmp_agents, "backend", mod) == "ct6-secondary-luna"
    assert mod.policy_state(tmp_agents, "ct6-secondary-luna") == "secondary-split"


@pytest.mark.parametrize(
    "split_alias_attr", ["SPAWN_ALIAS_MODEL_ID", "SECONDARY_ALIAS", "CODEX_MODEL"])
def test_uniform_split_aliases_are_rejected(
    mod: ModuleType, tmp_agents: Path, split_alias_attr: str
) -> None:
    """Split aliases never apply uniformly; architecture/control/design agents
    must stay on fable, so the uniform lever refuses current and legacy aliases."""
    before = {p.name: p.read_bytes() for p in tmp_agents.glob("*.md")}
    rc = mod.main([
        "--model", getattr(mod, split_alias_attr), "--agents-dir", str(tmp_agents)
    ])
    assert rc == 1
    assert before == {p.name: p.read_bytes() for p in tmp_agents.glob("*.md")}


# --------------------------------------------------------------------------- #
# Delivery/adversarial Opus split (v3.43.0)
# --------------------------------------------------------------------------- #

def test_delivery_adversarial_set_is_the_twelve_shipped_stems(
    mod: ModuleType, tmp_agents: Path
) -> None:
    """The canonical opus partition is exactly 12 stems, every one is a real
    shipped agent (no typo / stale entry), and it is a SUBSET of the gateway
    development bucket — a delivery/adversarial agent is, by construction, also a
    development/checking/testing agent, so the two splits never disagree on a
    stem's 'is this a doer' classification."""
    stems = {p.stem for p in tmp_agents.glob("*.md")}
    assert len(mod.DELIVERY_ADVERSARIAL_AGENTS) == 12
    assert mod.DELIVERY_ADVERSARIAL_AGENTS <= stems, (
        mod.DELIVERY_ADVERSARIAL_AGENTS - stems)
    assert mod.DELIVERY_ADVERSARIAL_AGENTS <= mod.DEVELOPMENT_CHECKING_TESTING_AGENTS


def test_deliver_split_applies_opus_and_fable(mod: ModuleType, tmp_agents: Path) -> None:
    mod.apply_deliver_split(tmp_agents)
    assert mod.distribution(tmp_agents) == {"opus": 12, "fable": 39 - 12}


def test_deliver_split_spot_checks(mod: ModuleType, tmp_agents: Path) -> None:
    """Owner directive verbatim: delivery + adversarial => opus; plan / validate /
    review => fable."""
    mod.apply_deliver_split(tmp_agents)
    for opus in ("backend", "frontend", "integration", "reconciler",
                 "adversarial-reviewer", "structure-adversary", "qa-replayer",
                 "mini-qa", "visual-analyzer", "flow-executor"):
        assert _model_of(tmp_agents, opus, mod) == "opus", opus
    for fable in ("system-architect", "task-reviewer", "test-completeness-verifier",
                  "flow-explorer", "visual-capture", "reference-tracer",
                  "doc-updater", "prompt-refiner", "monitor-synthesizer"):
        assert _model_of(tmp_agents, fable, mod) == "fable", fable


def test_deliver_role_model_fail_safe(mod: ModuleType) -> None:
    """A delivery/adversarial stem => opus; an unclassified (e.g. newly scaffolded)
    stem fails safe to fable — opus is never the silent default."""
    assert mod.deliver_role_model("backend") == "opus"
    assert mod.deliver_role_model("some-brand-new-agent") == "fable"


def test_deliver_split_is_idempotent(mod: ModuleType, tmp_agents: Path) -> None:
    mod.apply_deliver_split(tmp_agents)
    assert mod.apply_deliver_split(tmp_agents) == []


def test_deliver_split_only_touches_the_model_line(mod: ModuleType, tmp_agents: Path) -> None:
    mod.set_model(tmp_agents, "haiku")
    baseline = {p.name: p.read_text(encoding="utf-8") for p in tmp_agents.glob("*.md")}
    mod.apply_deliver_split(tmp_agents)
    for p in sorted(tmp_agents.glob("*.md")):
        before = baseline[p.name].splitlines()
        after = p.read_text(encoding="utf-8").splitlines()
        assert len(before) == len(after), f"{p.name}: line count changed"
        diffs = [i for i, (b, a) in enumerate(zip(before, after)) if b != a]
        assert len(diffs) == 1, f"{p.name}: expected exactly one changed line"
        assert before[diffs[0]].lstrip().startswith("model:"), p.name


def test_policy_state_recognizes_deliver_opus_split(mod: ModuleType, tmp_agents: Path) -> None:
    mod.apply_deliver_split(tmp_agents)
    assert mod.policy_state(tmp_agents) == "deliver-opus-split"
    assert mod.policy_state(tmp_agents) == mod.POLICY_DELIVER_OPUS_SPLIT


def test_deliver_split_distinct_from_secondary_split(mod: ModuleType, tmp_agents: Path) -> None:
    """The two splits are different axes: the secondary split classifies as
    secondary-split, the delivery split as deliver-opus-split — neither is read
    as the other, and a fresh secondary split is never 'mixed'."""
    mod.apply_split(tmp_agents)
    assert mod.policy_state(tmp_agents) == "secondary-split"
    mod.apply_deliver_split(tmp_agents)
    assert mod.policy_state(tmp_agents) == "deliver-opus-split"


def test_cli_split_delivery(mod: ModuleType, tmp_agents: Path, capsys) -> None:
    rc = mod.main(["--split", "delivery", "--agents-dir", str(tmp_agents)])
    captured = capsys.readouterr()
    assert rc == 0
    assert "deliver-opus-split" in captured.out
    assert captured.err == ""
    assert mod.policy_state(tmp_agents) == "deliver-opus-split"
    assert mod.distribution(tmp_agents) == {"opus": 12, "fable": 27}


def test_cli_check_reports_deliver_opus_split_policy(
    mod: ModuleType, tmp_agents: Path, capsys
) -> None:
    mod.apply_deliver_split(tmp_agents)
    mod.main(["--check", "--agents-dir", str(tmp_agents)])
    out = capsys.readouterr().out
    assert "policy: deliver-opus-split" in out
    assert "opus: 12" in out
    assert "fable: 27" in out


# --------------------------------------------------------------------------- #
# runtime agents-dir resolution (v3.39.0)
# --------------------------------------------------------------------------- #
#
# The agents Claude Code RUNS are the installed plugin cache copy — the
# resolver finds it via Claude Code's installed_plugins.json so install-time
# policy (the codex split) lands where the runtime actually reads it.

def _write_registry(tmp_path: Path, install_path: Path,
                    key: str = "architect-team@architect-team-marketplace") -> Path:
    reg = tmp_path / "installed_plugins.json"
    reg.write_text(
        '{"version": 2, "plugins": {"%s": [{"scope": "user", "installPath": %s}]}}'
        % (key, __import__("json").dumps(str(install_path))),
        encoding="utf-8")
    return reg


def test_installed_plugin_agents_dir_resolves(mod: ModuleType, tmp_path: Path) -> None:
    install = tmp_path / "cache" / "architect-team-marketplace" / "architect-team" / "9.9.9"
    (install / "agents").mkdir(parents=True)
    reg = _write_registry(tmp_path, install)
    assert mod.installed_plugin_agents_dir(reg) == install / "agents"


def test_installed_plugin_agents_dir_missing_registry(mod: ModuleType, tmp_path: Path) -> None:
    assert mod.installed_plugin_agents_dir(tmp_path / "nope.json") is None


def test_installed_plugin_agents_dir_no_agents_dir(mod: ModuleType, tmp_path: Path) -> None:
    """An installPath without an agents/ dir must NOT resolve (a half-installed
    or purged cache entry falls back to the repo agents/)."""
    install = tmp_path / "cache" / "architect-team" / "9.9.9"
    install.mkdir(parents=True)  # no agents/ inside
    reg = _write_registry(tmp_path, install)
    assert mod.installed_plugin_agents_dir(reg) is None


def test_installed_plugin_agents_dir_ignores_other_plugins(
    mod: ModuleType, tmp_path: Path
) -> None:
    install = tmp_path / "cache" / "other" / "1.0.0"
    (install / "agents").mkdir(parents=True)
    reg = _write_registry(tmp_path, install, key="cartographer@cartographer-marketplace")
    assert mod.installed_plugin_agents_dir(reg) is None


def test_installed_plugin_agents_dir_malformed_registry(
    mod: ModuleType, tmp_path: Path
) -> None:
    reg = tmp_path / "installed_plugins.json"
    for body in ("not json", '{"plugins": "not-a-dict"}', '{"plugins": {"architect-team@m": "x"}}'):
        reg.write_text(body, encoding="utf-8")
        assert mod.installed_plugin_agents_dir(reg) is None


def test_installed_plugin_agents_dir_env_var(
    mod: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    install = tmp_path / "cache" / "architect-team" / "9.9.9"
    (install / "agents").mkdir(parents=True)
    reg = _write_registry(tmp_path, install)
    monkeypatch.setenv(mod.PLUGIN_REGISTRY_ENV, str(reg))
    assert mod.installed_plugin_agents_dir() == install / "agents"


def test_runtime_agents_dir_installed_first_repo_fallback(
    mod: ModuleType, tmp_path: Path
) -> None:
    install = tmp_path / "cache" / "architect-team" / "9.9.9"
    (install / "agents").mkdir(parents=True)
    reg = _write_registry(tmp_path, install)
    assert mod.runtime_agents_dir(reg) == install / "agents"
    # no installed copy => the repo agents/ (the pre-v3.39.0 behavior)
    assert mod.runtime_agents_dir(tmp_path / "nope.json") == mod._default_agents_dir()


def test_runtime_agents_dir_hermetic_under_suite(mod: ModuleType) -> None:
    """The conftest autouse scrub points CT6_PLUGIN_REGISTRY at a nonexistent
    file, so a bare runtime_agents_dir() inside the suite ALWAYS falls back to
    the repo agents/ — no test can reach the real installed plugin copy."""
    assert mod.runtime_agents_dir() == mod._default_agents_dir()
