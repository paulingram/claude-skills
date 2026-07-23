# -*- coding: utf-8 -*-
"""Agent-model lever — rewrite the agents/*.md frontmatter ``model:`` field.

The v3.32.0 default ships all agents as ``model: fable`` (Fable 5, wherever it is
available). This stdlib-only CLI is the sanctioned, deterministic lever for that
field AND the IMPLEMENTED Opus-4.8 fallback for a harness that predates the fable
alias: ``python scripts/setup/set_default_model.py --model opus``.

v3.35.0 added the availability-gated secondary role split: architecture/control/
design agents stay on ``fable`` while development, code-checking, and testing
agents move to a gateway-served alias. v3.40.0 makes that alias provider-neutral
(``ct6-secondary``) and adds the OpenAI/Z.ai provider registry. v3.41.0 makes
the split's FRONTMATTER target the spawn-compatible impersonation alias
``SPAWN_ALIAS_MODEL_ID`` (the harness rejects custom ids at teammate spawn;
the gateway rewrites the real Claude id to the chosen secondary — disclosed),
and each registry entry carries a required ``route_dialect``. The historical
``CODEX_MODEL = "codex-5.6-sol"`` constant remains importable only for mixed-version
backward compatibility and migration detection. Availability is an INPUT (a flag
or the ``CT6_CODEX_56_AVAILABLE`` env var), never probed here — the same injected-
availability convention as ``services/common/service_config.py``'s
``resolve_model``. Without the availability signal the policy resolves to the
current operating model: uniform ``fable`` (with the existing ``--model opus``
uniform lever remaining the Opus fallback where fable is unavailable).

Behaviour
---------
* ``--model fable|opus|sonnet|haiku`` rewrites ONLY the ``model:`` line in each
  agent's YAML frontmatter (bodies stay byte-identical; the change is idempotent).
  An unknown model is refused (exit 1) and touches nothing. The current and legacy
  secondary aliases are deliberately NOT accepted here — the split never applies
  uniformly (architecture/control/design agents must stay on fable).
* ``--split secondary`` applies the role split unconditionally. ``--split codex``
  remains a deprecated synonym. ``--secondary-model`` overrides the written alias;
  ``--codex-model`` remains a backward-compatible option synonym.
* ``--split delivery`` applies the v3.43.0 delivery-adversarial Opus split: the
  12 delivery + adversarial agents (``DELIVERY_ADVERSARIAL_AGENTS``) take
  ``model: opus``, every planning / validation / review agent stays on ``fable``.
  This is the shipped default state; ``opus`` is a real Claude id (no gateway
  impersonation). It is a DIFFERENT axis than the secondary split above.
* ``--auto`` resolves the policy from ``CT6_CODEX_56_AVAILABLE``: truthy => the
  secondary split; SET-but-falsy => uniform fable (the current operating default);
  ABSENT => no signal — the model state is left untouched (a manually applied
  lever state, e.g. the Opus fallback, is never silently clobbered).
* ``--check`` prints the model distribution, uniformity, and the recognized policy
  state (``uniform-fable`` / ``secondary-split`` / ``uniform-<m>`` / ``mixed``).
  Readers may still encounter ``codex-split`` in legacy state files, but this lever
  emits the single canonical ``secondary-split`` policy string.
* ``--agents-dir`` overrides the target directory (default: the repo's agents/).

Exit codes: 0 on a successful flip/split or a ``--check`` report; 1 on a
validation error (unknown model); 2 when the agents directory does not exist.

Mirrors the house style of scripts/setup/sync_agent_boilerplate.py (line-ending
preservation, write-only-if-changed, argparse main). Stdlib-only.
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import sys
from typing import Dict, List, Mapping, Optional, Tuple

# Shared agent-file I/O (the newline-preserving rewrite trio lives canonically
# in agent_boilerplate_blocks — v3.35.1 consolidation). Dual-form import so the
# module works as a package import, a direct script, or an importlib file load.
try:
    from scripts.setup import agent_boilerplate_blocks as _blocks
    from scripts.setup.teams_mode import _TRUTHY_VALUES as _TRUTHY
except ImportError:  # direct script / importlib-by-path execution
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
    from scripts.setup import agent_boilerplate_blocks as _blocks
    from scripts.setup.teams_mode import _TRUTHY_VALUES as _TRUTHY

VALID_MODELS = ("fable", "opus", "sonnet", "haiku")

# --- Secondary-provider role split (v3.35.0; provider registry v3.40.0) ------- #
SECONDARY_ALIAS = "ct6-secondary"
LEGACY_SECONDARY_ALIASES = ("codex-5.6-sol",)

# v3.41.0 (glm-secondary-route-fix, BUG-B): Claude Code's Agent-Teams spawn
# path validates teammate model ids CLIENT-SIDE — a frontmatter alias that is
# not a known Claude model id dies before any HTTP reaches the gateway
# (gateway-log verified 2026-07-17). The split therefore writes a REAL,
# harness-accepted Claude id into dev-class frontmatter; the gateway rewrites
# that id to the chosen secondary provider via the DISCLOSED impersonation
# route install_gateway.py emits (`SPAWN_ALIAS_MODEL_ID → <dialect>/<model>`).
# `ct6-secondary` remains the served backend alias for direct/scripted callers
# and the state lineage. Test-pinned: changing this id is a deliberate act.
SPAWN_ALIAS_MODEL_ID = "claude-haiku-4-5"

# Frontmatter aliases superseded as SPLIT TARGETS (the gateway still serves
# `ct6-secondary`; it is only superseded as a frontmatter value, because the
# harness spawn gate rejects it — BUG-B above). migrate_legacy_split moves any
# of these to the spawn alias on every config-regenerating install.
SUPERSEDED_FRONTMATTER_ALIASES = (*LEGACY_SECONDARY_ALIASES, SECONDARY_ALIAS)

# Each entry's `route_dialect` names the LiteLLM provider prefix the gateway
# route uses; the route is DERIVED as `<route_dialect>/<model>` — no entry
# carries a redundant route string that could drift from its dialect
# (v3.41.0, BUG-A). The dialect must match what the provider's API actually
# implements: LiteLLM's proxy drives Anthropic-format traffic for `openai/*`
# models through the OpenAI Responses API (codex-gen models REQUIRE it), while
# api.z.ai implements only /chat/completions (live 404 at /v4/responses), so
# zai rides the strict chat-completions `hosted_vllm` dialect.
SECONDARY_PROVIDERS: Dict[str, Dict[str, Optional[str]]] = {
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

# Deprecated back-compat constant. New writers use SECONDARY_ALIAS; this remains
# importable for mixed-version gateway readers and legacy-alias migration only.
CODEX_MODEL = "codex-5.6-sol"

# Canonical model-policy strings (v3.40.0). The lever is the single source —
# the gateway/setup readers import these instead of spelling the literals
# (the SessionStart hook keeps a guarded local copy because it loads the lever
# dynamically, and only after its cheap state check). ``codex-split`` is the
# legacy policy string prior versions recorded: readers accept it, writers
# emit only the canonical values.
POLICY_SECONDARY_SPLIT = "secondary-split"
POLICY_UNIFORM_FABLE = "uniform-fable"
LEGACY_POLICY_CODEX_SPLIT = "codex-split"

# Availability signal for --auto (and for setup.py). Truthy => Codex 5.6 is
# available in this harness. Absent/falsy => stay on the current operating
# model (uniform fable; opus fallback via --model opus where fable is absent).
CODEX_ENV_VAR = "CT6_CODEX_56_AVAILABLE"

ROLE_ARCHITECTURE = "architecture-control-design"   # stays on fable under the split
ROLE_DEVELOPMENT = "development-checking-testing"   # moves to secondary under the split

# Role classification of all 39 agents (v3.35.0). The buckets follow the owner
# directive verbatim: architecture + control + design agents keep Fable;
# development + code-checking + testing agents take Codex 5.6 when available.
# The split was adversarially re-derived by 3 independent classifiers; the
# hard calls landed as: reconciler / reference-tracer / structure-adversary
# (hands-on code merging / reference closure / code-search refutation) and
# flow-explorer (test-flow design inside the testing pipeline) => secondary;
# diagnostic-researcher (root-cause RESEARCH feeding the architect, the
# researcher family) and the doc-currency writers (doc-updater /
# closeout-agent — documentation, not product code) => fable.
ARCHITECTURE_CONTROL_DESIGN_AGENTS = frozenset({
    # architecture: mapping / exploration / structural analysis / synthesis
    "system-architect", "structure-analyst", "route-mapper", "endpoint-tracer",
    "integration-explorer", "master-synthesizer", "codebase-map-reviewer",
    # control: triage / refinement / documentation / meta-authoring
    "bug-classifier", "prompt-refiner", "scaffold-agent",
    "doc-updater", "closeout-agent",
    # design + research: oracle / UX-design discovery / research / contracts
    "oracle-deriver", "interaction-intuiter", "interaction-observer",
    "domain-researcher", "diagnostic-researcher", "mcp-design-agent",
})

DEVELOPMENT_CHECKING_TESTING_AGENTS = frozenset({
    # development: the implementer teammates + hands-on code integration
    "backend", "frontend", "integration", "reconciler",
    # code checking: reviewers + verifiers over written code, incl. the
    # mechanical reference closure + code-search refutation stages
    "adversarial-reviewer", "task-reviewer", "test-completeness-verifier",
    "editability-reviewer", "interaction-reviewer", "fix-sensibility-checker",
    "reference-tracer", "structure-adversary",
    # testing: QA / flow design + execution / test-run + visual verification
    "qa-replayer", "mini-qa", "flow-explorer", "flow-executor",
    "bug-replicator", "test-run-watcher", "monitor-synthesizer",
    "visual-capture", "visual-analyzer",
})

AGENT_ROLES: Dict[str, str] = {
    **{stem: ROLE_ARCHITECTURE for stem in ARCHITECTURE_CONTROL_DESIGN_AGENTS},
    **{stem: ROLE_DEVELOPMENT for stem in DEVELOPMENT_CHECKING_TESTING_AGENTS},
}


def role_for(stem: str) -> str:
    """Return the split role for an agent stem.

    An UNCLASSIFIED stem (e.g. a newly scaffolded agent) defaults to the
    architecture/control/design bucket — the fail-safe is fable, never codex."""
    return AGENT_ROLES.get(stem, ROLE_ARCHITECTURE)


# --- Delivery/adversarial Opus split (v3.43.0) ------------------------------- #
# A SECOND role partition, ORTHOGONAL to the gateway secondary split above and
# independent of it (different axis, different targets). Owner directive
# (2026-07-23): run the DELIVERY + ADVERSARIAL agents on Opus 4.8 — the
# strongest code-gen for the agents that write/merge product code and the
# sharpest attacker for the agents whose job is to break, refute, reproduce, or
# execute-to-surface-failures — and keep the PLANNING / VALIDATION / REVIEW
# agents on Fable (architects, deep planners, researchers, and the reviewers who
# adjudicate the adversarial output). Unlike the secondary split, this writes a
# REAL Claude id (``opus``) into frontmatter — the Agent-Teams spawn gate accepts
# it directly, so no gateway impersonation route is involved.
OPUS_MODEL = "opus"
POLICY_DELIVER_OPUS_SPLIT = "deliver-opus-split"

DELIVERY_ADVERSARIAL_AGENTS = frozenset({
    # delivery — the implementer teammates + hands-on code integration / merge
    "backend", "frontend", "integration", "reconciler",
    # adversarial — attack / refute / reproduce / execute-to-surface-failures
    "adversarial-reviewer", "structure-adversary", "fix-sensibility-checker",
    "bug-replicator", "qa-replayer", "flow-executor", "visual-analyzer",
    "mini-qa",
})


def deliver_role_model(stem: str) -> str:
    """Return the delivery-split target model for an agent stem: ``opus`` for a
    delivery/adversarial agent, else ``fable``. An unclassified (e.g. newly
    scaffolded) stem fails safe to ``fable`` — Opus is never the silent default,
    the same fail-safe direction as the architecture bucket in ``role_for``."""
    return OPUS_MODEL if stem in DELIVERY_ADVERSARIAL_AGENTS else "fable"


def codex_available(env: Optional[Mapping[str, str]] = None) -> bool:
    """True when the ``CT6_CODEX_56_AVAILABLE`` signal is truthy in ``env``
    (defaults to ``os.environ``). Absent or falsy => False."""
    env = os.environ if env is None else env
    return str(env.get(CODEX_ENV_VAR, "")).strip().lower() in _TRUTHY


def codex_signal_from_env(env: Optional[Mapping[str, str]] = None) -> Optional[bool]:
    """Tri-state ``CT6_CODEX_56_AVAILABLE`` read: ``True`` (set truthy — Codex 5.6
    available), ``False`` (SET but falsy — an explicit unavailability assertion),
    ``None`` (absent — NO signal; the caller must leave the model state untouched,
    never silently clobbering a manually applied lever state such as the Opus
    fallback)."""
    env = os.environ if env is None else env
    if CODEX_ENV_VAR not in env:
        return None
    return str(env.get(CODEX_ENV_VAR, "")).strip().lower() in _TRUTHY


def _default_agents_dir() -> pathlib.Path:
    """Locate the repo's ``agents/`` directory relative to this file."""
    return pathlib.Path(__file__).resolve().parents[2] / "agents"


# --- Runtime agents-dir resolution (v3.39.0) --------------------------------- #
#
# The agents Claude Code actually RUNS are the installed plugin cache copy under
# ~/.claude/plugins/cache/<marketplace>/architect-team/<version>/agents — NOT the
# dev checkout this file may live in. A split applied to a dev checkout never
# affects the runtime and is silently reverted by the next git operation (the
# committed ship state is uniform fable). Install-time policy therefore targets
# the INSTALLED copy when one exists; the repo agents/ stays the fallback for
# repos that ARE the runtime plugin (a --plugin-dir dev install) and for tests.
PLUGIN_REGISTRY_ENV = "CT6_PLUGIN_REGISTRY"
PLUGIN_KEY_PREFIX = "architect-team@"


def default_plugin_registry() -> pathlib.Path:
    """Claude Code's installed-plugin registry (installed_plugins.json)."""
    return pathlib.Path.home() / ".claude" / "plugins" / "installed_plugins.json"


def installed_plugin_agents_dir(
    registry_path=None, env: Optional[Mapping[str, str]] = None
) -> Optional[pathlib.Path]:
    """The installed architect-team plugin's ``agents/`` dir, or ``None``.

    Reads Claude Code's ``installed_plugins.json`` (explicit ``registry_path`` >
    ``$CT6_PLUGIN_REGISTRY`` > the real per-user registry), finds the
    ``architect-team@<marketplace>`` entry, and returns ``<installPath>/agents``
    when that directory exists. Any read/shape failure returns ``None`` — the
    caller falls back to the repo agents/ (fail-open, never raises)."""
    env = os.environ if env is None else env
    reg = pathlib.Path(
        registry_path or env.get(PLUGIN_REGISTRY_ENV) or default_plugin_registry())
    try:
        data = json.loads(reg.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return None
    plugins = data.get("plugins") if isinstance(data, dict) else None
    if not isinstance(plugins, dict):
        return None
    for key, entries in plugins.items():
        if not str(key).startswith(PLUGIN_KEY_PREFIX) or not isinstance(entries, list):
            continue
        for entry in entries:
            install_path = entry.get("installPath") if isinstance(entry, dict) else None
            if install_path:
                agents = pathlib.Path(install_path) / "agents"
                if agents.is_dir():
                    return agents
    return None


def runtime_agents_dir(
    registry_path=None, env: Optional[Mapping[str, str]] = None
) -> pathlib.Path:
    """The agents/ dir the RUNTIME actually loads: the installed plugin copy
    when one exists, else the repo agents/ (the pre-v3.39.0 behavior)."""
    installed = installed_plugin_agents_dir(registry_path, env)
    return installed if installed is not None else _default_agents_dir()


# Thin aliases onto the canonical trio (call sites + test surface unchanged).
_detect_newline = _blocks.detect_newline
_read = _blocks.read_preserving
_write_if_changed = _blocks.write_if_changed


def _frontmatter_bounds(lines: List[str]) -> Optional[Tuple[int, int]]:
    """Return ``(open_idx, close_idx)`` of the YAML frontmatter fence, or ``None``.

    The frontmatter is the block between the first ``---`` line (which must be the
    file's first line) and the next ``---`` line."""
    if not lines or lines[0].strip() != "---":
        return None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            return (0, i)
    return None


def read_model_value(text_lf: str) -> Optional[str]:
    """Return the frontmatter ``model:`` value, or ``None`` if there is no model line."""
    lines = text_lf.split("\n")
    bounds = _frontmatter_bounds(lines)
    if bounds is None:
        return None
    _, close = bounds
    for i in range(1, close):
        stripped = lines[i].lstrip()
        if stripped.startswith("model:"):
            return stripped[len("model:"):].strip().strip("\"'")
    return None


def rewrite_model_line(text_lf: str, new_model: str) -> Optional[str]:
    """Rewrite ONLY the frontmatter ``model:`` value to ``new_model``.

    Returns the new text, or ``None`` if there is no model line or it already reads
    ``new_model`` (idempotent)."""
    lines = text_lf.split("\n")
    bounds = _frontmatter_bounds(lines)
    if bounds is None:
        return None
    _, close = bounds
    for i in range(1, close):
        stripped = lines[i].lstrip()
        if stripped.startswith("model:"):
            indent = lines[i][: len(lines[i]) - len(stripped)]
            new_line = f"{indent}model: {new_model}"
            if lines[i] == new_line:
                return None
            lines[i] = new_line
            return "\n".join(lines)
    return None


def set_model(agents_dir, new_model: str) -> List[str]:
    """Rewrite the model field across ``agents_dir/*.md``. Returns sorted changed stems."""
    agents_dir = pathlib.Path(agents_dir)
    changed: List[str] = []
    for path in sorted(agents_dir.glob("*.md")):
        text_lf, newline, trailing = _read(path)
        new = rewrite_model_line(text_lf, new_model)
        if new is None or new == text_lf:
            continue
        if trailing and not new.endswith("\n"):
            new += "\n"
        if _write_if_changed(path, new, newline):
            changed.append(path.stem)
    return sorted(changed)


def distribution(agents_dir) -> Dict[str, int]:
    """Return ``{model_value: count}`` across ``agents_dir/*.md``."""
    agents_dir = pathlib.Path(agents_dir)
    dist: Dict[str, int] = {}
    for path in sorted(agents_dir.glob("*.md")):
        text_lf, _, _ = _read(path)
        model = read_model_value(text_lf) or "<none>"
        dist[model] = dist.get(model, 0) + 1
    return dist


# --- Secondary-provider role split application (v3.35.0 / v3.40.0) ----------- #

def split_targets(
    agents_dir, codex_model: str = SPAWN_ALIAS_MODEL_ID
) -> Dict[str, str]:
    """Return ``{stem: target_model}`` for every agent under the role split.

    The default target is the spawn-compatible impersonation alias (v3.41.0):
    the harness rejects unknown model ids at teammate spawn, so the value
    written into dev-class frontmatter must be a real Claude id the gateway
    rewrites to the secondary. ``codex_model`` retains its historical parameter
    name so mixed-version callers using the positional or keyword form remain
    compatible."""
    agents_dir = pathlib.Path(agents_dir)
    targets: Dict[str, str] = {}
    for path in sorted(agents_dir.glob("*.md")):
        role = role_for(path.stem)
        targets[path.stem] = codex_model if role == ROLE_DEVELOPMENT else "fable"
    return targets


def apply_split(
    agents_dir, codex_model: str = SPAWN_ALIAS_MODEL_ID
) -> List[str]:
    """Apply the role split: fable on architecture/control/design agents and the
    spawn-compatible impersonation alias on development/checking/testing agents.
    Returns sorted changed stems. Idempotent; only the frontmatter model line is
    touched."""
    agents_dir = pathlib.Path(agents_dir)
    targets = split_targets(agents_dir, codex_model)
    changed: List[str] = []
    for path in sorted(agents_dir.glob("*.md")):
        text_lf, newline, trailing = _read(path)
        new = rewrite_model_line(text_lf, targets[path.stem])
        if new is None or new == text_lf:
            continue
        if trailing and not new.endswith("\n"):
            new += "\n"
        if _write_if_changed(path, new, newline):
            changed.append(path.stem)
    return sorted(changed)


def deliver_split_targets(agents_dir) -> Dict[str, str]:
    """Return ``{stem: target_model}`` for the delivery/adversarial Opus split:
    ``opus`` on every delivery + adversarial agent, ``fable`` on every planning /
    validation / review agent (and any unclassified stem)."""
    agents_dir = pathlib.Path(agents_dir)
    return {
        path.stem: deliver_role_model(path.stem)
        for path in sorted(agents_dir.glob("*.md"))
    }


def apply_deliver_split(agents_dir) -> List[str]:
    """Apply the delivery/adversarial Opus split: ``opus`` on delivery + adversarial
    agents, ``fable`` on planning / validation / review agents. Returns sorted
    changed stems. Idempotent; only the frontmatter model line is ever touched."""
    agents_dir = pathlib.Path(agents_dir)
    targets = deliver_split_targets(agents_dir)
    changed: List[str] = []
    for path in sorted(agents_dir.glob("*.md")):
        text_lf, newline, trailing = _read(path)
        new = rewrite_model_line(text_lf, targets[path.stem])
        if new is None or new == text_lf:
            continue
        if trailing and not new.endswith("\n"):
            new += "\n"
        if _write_if_changed(path, new, newline):
            changed.append(path.stem)
    return sorted(changed)


def migrate_legacy_split(agents_dir) -> List[str]:
    """Rewrite superseded split-target aliases to ``SPAWN_ALIAS_MODEL_ID``.

    Covers the legacy provider-specific aliases AND the raw ``ct6-secondary``
    frontmatter value (v3.41.0: superseded as a SPLIT TARGET by the
    spawn-compatible alias — the harness spawn gate rejects custom ids, so a
    dev-class agent left on it never reaches the gateway; the backend route
    itself stays served). Returns sorted changed stems and is idempotent.
    Every superseded model occurrence is migrated, including an unexpected one
    outside the development role bucket; callers can then re-apply the role
    policy to repair any broader drift."""
    agents_dir = pathlib.Path(agents_dir)
    changed: List[str] = []
    for path in sorted(agents_dir.glob("*.md")):
        text_lf, newline, trailing = _read(path)
        if read_model_value(text_lf) not in SUPERSEDED_FRONTMATTER_ALIASES:
            continue
        new = rewrite_model_line(text_lf, SPAWN_ALIAS_MODEL_ID)
        if new is None:
            continue
        if trailing and not new.endswith("\n"):
            new += "\n"
        if _write_if_changed(path, new, newline):
            changed.append(path.stem)
    return sorted(changed)


def apply_policy(
    agents_dir,
    codex_is_available: bool,
    codex_model: str = SPAWN_ALIAS_MODEL_ID,
) -> Tuple[str, List[str]]:
    """Apply the availability-gated model policy. Returns ``(policy, changed)``.

    * Secondary model available => the role split (``secondary-split``).
    * Secondary model unavailable => the current operating model: uniform fable
      (``uniform-fable``; the Opus fallback where fable itself is unavailable
      stays the separate ``--model opus`` uniform lever).

    ``codex_model`` retains its old name for keyword-call compatibility."""
    if codex_is_available:
        return POLICY_SECONDARY_SPLIT, apply_split(agents_dir, codex_model)
    return POLICY_UNIFORM_FABLE, set_model(agents_dir, "fable")


def unclassified_stems(agents_dir) -> List[str]:
    """Agent stems present on disk but absent from AGENT_ROLES (they default to
    the fable bucket; surfaced so a newly scaffolded agent is visible)."""
    agents_dir = pathlib.Path(agents_dir)
    return sorted(
        p.stem for p in agents_dir.glob("*.md") if p.stem not in AGENT_ROLES
    )


def policy_state(agents_dir, codex_model: str = SPAWN_ALIAS_MODEL_ID) -> str:
    """Classify the on-disk model state.

    Returns ``uniform-<model>`` (including the operating ``uniform-fable``),
    ``secondary-split`` when every file matches either the requested/current
    alias or any complete split on a recognized alias generation (the spawn
    alias, the neutral ``ct6-secondary``, or a legacy provider alias), else
    ``mixed``. ``codex-split`` is the legacy policy string readers elsewhere
    may still hold; this function emits only the canonical ``secondary-split``
    value."""
    agents_dir = pathlib.Path(agents_dir)
    actual: Dict[str, str] = {}
    for path in sorted(agents_dir.glob("*.md")):
        text_lf, _, _ = _read(path)
        actual[path.stem] = read_model_value(text_lf) or "<none>"
    if not actual:
        return "empty"
    values = set(actual.values())
    if len(values) == 1:
        return f"uniform-{next(iter(values))}"
    recognized_aliases = tuple(dict.fromkeys(
        (codex_model, SPAWN_ALIAS_MODEL_ID, SECONDARY_ALIAS,
         *LEGACY_SECONDARY_ALIASES)
    ))
    if any(actual == split_targets(agents_dir, alias) for alias in recognized_aliases):
        return POLICY_SECONDARY_SPLIT
    if actual == deliver_split_targets(agents_dir):
        return POLICY_DELIVER_OPUS_SPLIT
    return "mixed"


def _print_distribution(
    agents_dir: pathlib.Path, codex_model: str = SPAWN_ALIAS_MODEL_ID
) -> None:
    dist = distribution(agents_dir)
    total = sum(dist.values())
    print(f"model distribution across {total} agent file(s) in {agents_dir}:")
    for model in sorted(dist):
        print(f"  {model}: {dist[model]}")
    if len(dist) == 1:
        only = next(iter(dist))
        print(f"uniform: yes ({only})")
    else:
        print("uniform: no")
    print(f"policy: {policy_state(agents_dir, codex_model)}")
    unknown = unclassified_stems(agents_dir)
    if unknown:
        print(
            "unclassified (default to the fable bucket under the split): "
            + ", ".join(unknown)
        )


def _report_changed(policy: str, changed: List[str]) -> None:
    if changed:
        print(f"Applied policy {policy}: {len(changed)} agent file(s) changed:")
        for stem in changed:
            print(f"  - {stem}.md")
    else:
        print(f"0 files changed (agents already match policy: {policy}).")


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Set (or report) the frontmatter model field across agents/*.md "
        "— uniform, or the availability-gated secondary-model role split."
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--model",
        default=None,
        help="Rewrite every agent's model field to this value ("
        + "/".join(VALID_MODELS)
        + "). Secondary split aliases are refused here — they apply only via the split.",
    )
    group.add_argument(
        "--split",
        choices=["secondary", "codex", "delivery"],
        default=None,
        help="Apply a role split. 'secondary' (canonical; 'codex' is a deprecated "
        "synonym): fable on architecture/control/design agents, the gateway "
        "secondary alias on development/checking/testing agents. 'delivery': opus "
        "on delivery + adversarial agents, fable on planning/validation/review "
        "agents (the v3.43.0 delivery-adversarial Opus split).",
    )
    group.add_argument(
        "--auto",
        action="store_true",
        help=f"Resolve the policy from {CODEX_ENV_VAR}: truthy applies the codex "
        "split; set-but-falsy applies the uniform fable operating default; "
        "absent leaves the model state untouched.",
    )
    group.add_argument(
        "--check",
        action="store_true",
        help="Report the model distribution, uniformity, and policy state (writes nothing).",
    )
    parser.add_argument(
        "--secondary-model", "--codex-model",
        dest="secondary_model",
        default=SPAWN_ALIAS_MODEL_ID,
        help=f"Model id written for development/checking/testing agents under the "
        f"split (default: {SPAWN_ALIAS_MODEL_ID}, the spawn-compatible "
        f"impersonation alias the gateway routes to the secondary); "
        f"--codex-model is a compatibility synonym.",
    )
    parser.add_argument(
        "--agents-dir",
        default=None,
        help="Path to the agents/ directory (defaults to the repo's agents/).",
    )
    args = parser.parse_args(argv)

    agents_dir = pathlib.Path(args.agents_dir) if args.agents_dir else _default_agents_dir()
    if not agents_dir.is_dir():
        print(f"ERROR: agents directory not found: {agents_dir}", file=sys.stderr)
        return 2

    if args.check:
        _print_distribution(agents_dir, args.secondary_model)
        return 0

    if args.split == "delivery":
        changed = apply_deliver_split(agents_dir)
        _report_changed(POLICY_DELIVER_OPUS_SPLIT, changed)
        return 0

    if args.split in {"secondary", "codex"}:
        if args.split == "codex":
            print(
                "NOTE: --split codex is deprecated; use --split secondary.",
                file=sys.stderr,
            )
        policy, changed = apply_policy(agents_dir, True, args.secondary_model)
        _report_changed(policy, changed)
        return 0

    if args.auto:
        signal = codex_signal_from_env()
        if signal is None:
            # NO signal: leave the model state untouched (never clobber a
            # manually applied lever state, e.g. the Opus fallback).
            print(
                f"{CODEX_ENV_VAR} absent — no availability signal; leaving the "
                f"model state untouched (current policy: {policy_state(agents_dir, args.secondary_model)})."
            )
            return 0
        policy, changed = apply_policy(agents_dir, signal, args.secondary_model)
        print(
            f"{CODEX_ENV_VAR} {'truthy — Codex 5.6 available' if signal else 'set falsy — Codex 5.6 unavailable'}; "
            f"resolved policy: {policy}"
        )
        _report_changed(policy, changed)
        return 0

    split_aliases = {SPAWN_ALIAS_MODEL_ID, SECONDARY_ALIAS,
                     *LEGACY_SECONDARY_ALIASES}
    if args.model in split_aliases:
        print(
            f"ERROR: split alias {args.model!r} cannot apply uniformly; "
            "use --split secondary",
            file=sys.stderr,
        )
        return 1
    if args.model not in VALID_MODELS:
        print(
            f"ERROR: unknown model {args.model!r} (valid: {', '.join(VALID_MODELS)})",
            file=sys.stderr,
        )
        return 1

    changed = set_model(agents_dir, args.model)
    if changed:
        print(f"Set model: {args.model} on {len(changed)} agent file(s):")
        for stem in changed:
            print(f"  - {stem}.md")
    else:
        print(f"0 files changed (all agents already model: {args.model}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
