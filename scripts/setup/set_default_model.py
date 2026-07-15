# -*- coding: utf-8 -*-
"""Agent-model lever — rewrite the agents/*.md frontmatter ``model:`` field.

The v3.32.0 default ships all agents as ``model: fable`` (Fable 5, wherever it is
available). This stdlib-only CLI is the sanctioned, deterministic lever for that
field AND the IMPLEMENTED Opus-4.8 fallback for a harness that predates the fable
alias: ``python scripts/setup/set_default_model.py --model opus``.

v3.35.0 adds the CODEX 5.6 ROLE SPLIT: when the harness has Codex 5.6 available,
architecture/control/design agents stay on ``fable`` while development,
code-checking, and testing agents move to ``codex-5.6-sol``. Availability is an
INPUT (a flag or the ``CT6_CODEX_56_AVAILABLE`` env var), never probed here — the
same injected-availability convention as ``services/common/service_config.py``'s
``resolve_model``. Without the availability signal the policy resolves to the
current operating model: uniform ``fable`` (with the existing ``--model opus``
uniform lever remaining the Opus fallback where fable is unavailable).

Behaviour
---------
* ``--model fable|opus|sonnet|haiku`` rewrites ONLY the ``model:`` line in each
  agent's YAML frontmatter (bodies stay byte-identical; the change is idempotent).
  An unknown model is refused (exit 1) and touches nothing. The codex id is
  deliberately NOT accepted here — codex never applies uniformly (architecture/
  control/design agents must stay on fable); it arrives only via the split.
* ``--split codex`` applies the role split unconditionally (the caller asserts
  Codex 5.6 availability). ``--codex-model`` overrides the written codex id.
* ``--auto`` resolves the policy from ``CT6_CODEX_56_AVAILABLE``: truthy => the
  codex split; SET-but-falsy => uniform fable (the current operating default);
  ABSENT => no signal — the model state is left untouched (a manually applied
  lever state, e.g. the Opus fallback, is never silently clobbered).
* ``--check`` prints the model distribution, uniformity, and the recognized
  policy state (``uniform-fable`` / ``codex-split`` / ``uniform-<m>`` / ``mixed``).
* ``--agents-dir`` overrides the target directory (default: the repo's agents/).

Exit codes: 0 on a successful flip/split or a ``--check`` report; 1 on a
validation error (unknown model); 2 when the agents directory does not exist.

Mirrors the house style of scripts/setup/sync_agent_boilerplate.py (line-ending
preservation, write-only-if-changed, argparse main). Stdlib-only.
"""
from __future__ import annotations

import argparse
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

# --- Codex 5.6 role split (v3.35.0) ----------------------------------------- #
#
# The frontmatter model id written for development/checking/testing agents when
# Codex 5.6 is available. If the harness registers Codex 5.6 under a different
# id, override with --codex-model (the id is written verbatim, never validated
# against a live registry — model availability is not probe-able from stdlib).
CODEX_MODEL = "codex-5.6-sol"

# Availability signal for --auto (and for setup.py). Truthy => Codex 5.6 is
# available in this harness. Absent/falsy => stay on the current operating
# model (uniform fable; opus fallback via --model opus where fable is absent).
CODEX_ENV_VAR = "CT6_CODEX_56_AVAILABLE"

ROLE_ARCHITECTURE = "architecture-control-design"   # stays on fable under the split
ROLE_DEVELOPMENT = "development-checking-testing"   # moves to codex under the split

# Role classification of all 39 agents (v3.35.0). The buckets follow the owner
# directive verbatim: architecture + control + design agents keep Fable;
# development + code-checking + testing agents take Codex 5.6 when available.
# The split was adversarially re-derived by 3 independent classifiers; the
# hard calls landed as: reconciler / reference-tracer / structure-adversary
# (hands-on code merging / reference closure / code-search refutation) and
# flow-explorer (test-flow design inside the testing pipeline) => codex;
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


# --- Codex 5.6 role split application (v3.35.0) ------------------------------ #

def split_targets(agents_dir, codex_model: str = CODEX_MODEL) -> Dict[str, str]:
    """Return ``{stem: target_model}`` for every agent file under the codex split."""
    agents_dir = pathlib.Path(agents_dir)
    targets: Dict[str, str] = {}
    for path in sorted(agents_dir.glob("*.md")):
        role = role_for(path.stem)
        targets[path.stem] = codex_model if role == ROLE_DEVELOPMENT else "fable"
    return targets


def apply_split(agents_dir, codex_model: str = CODEX_MODEL) -> List[str]:
    """Apply the codex role split: fable on architecture/control/design agents,
    ``codex_model`` on development/checking/testing agents. Returns sorted
    changed stems. Idempotent; only the frontmatter model line is touched."""
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


def apply_policy(
    agents_dir,
    codex_is_available: bool,
    codex_model: str = CODEX_MODEL,
) -> Tuple[str, List[str]]:
    """Apply the availability-gated model policy. Returns ``(policy, changed)``.

    * Codex 5.6 available  => the role split (``codex-split``).
    * Codex 5.6 unavailable => the current operating model: uniform fable
      (``uniform-fable``; the Opus fallback where fable itself is unavailable
      stays the separate ``--model opus`` uniform lever)."""
    if codex_is_available:
        return "codex-split", apply_split(agents_dir, codex_model)
    return "uniform-fable", set_model(agents_dir, "fable")


def unclassified_stems(agents_dir) -> List[str]:
    """Agent stems present on disk but absent from AGENT_ROLES (they default to
    the fable bucket; surfaced so a newly scaffolded agent is visible)."""
    agents_dir = pathlib.Path(agents_dir)
    return sorted(
        p.stem for p in agents_dir.glob("*.md") if p.stem not in AGENT_ROLES
    )


def policy_state(agents_dir, codex_model: str = CODEX_MODEL) -> str:
    """Classify the on-disk model state: ``uniform-<model>`` (incl. the
    ``uniform-fable`` operating default), ``codex-split`` when every file matches
    its split target, else ``mixed``."""
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
    if actual == split_targets(agents_dir, codex_model):
        return "codex-split"
    return "mixed"


def _print_distribution(agents_dir: pathlib.Path, codex_model: str = CODEX_MODEL) -> None:
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
        "— uniform, or the availability-gated Codex 5.6 role split."
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--model",
        default=None,
        help="Rewrite every agent's model field to this value ("
        + "/".join(VALID_MODELS)
        + "). The codex id is refused here — codex applies only via the split.",
    )
    group.add_argument(
        "--split",
        choices=["codex"],
        default=None,
        help="Apply the Codex 5.6 role split: fable on architecture/control/design "
        "agents, the codex model on development/checking/testing agents.",
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
        "--codex-model",
        default=CODEX_MODEL,
        help=f"Model id written for development/checking/testing agents under the "
        f"split (default: {CODEX_MODEL}).",
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
        _print_distribution(agents_dir, args.codex_model)
        return 0

    if args.split == "codex":
        policy, changed = apply_policy(agents_dir, True, args.codex_model)
        _report_changed(policy, changed)
        return 0

    if args.auto:
        signal = codex_signal_from_env()
        if signal is None:
            # NO signal: leave the model state untouched (never clobber a
            # manually applied lever state, e.g. the Opus fallback).
            print(
                f"{CODEX_ENV_VAR} absent — no availability signal; leaving the "
                f"model state untouched (current policy: {policy_state(agents_dir, args.codex_model)})."
            )
            return 0
        policy, changed = apply_policy(agents_dir, signal, args.codex_model)
        print(
            f"{CODEX_ENV_VAR} {'truthy — Codex 5.6 available' if signal else 'set falsy — Codex 5.6 unavailable'}; "
            f"resolved policy: {policy}"
        )
        _report_changed(policy, changed)
        return 0

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
