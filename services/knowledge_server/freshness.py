# -*- coding: utf-8 -*-
"""Freshness contract for the knowledge server (KS-4) — stdlib-only.

Every tool response carries a `{verdict: current|stale|unknowable, basis: [...]}`
envelope. Map freshness composes `hooks/lineage_graph.py::transitive_stale_nodes`
over the paths changed since the map's stamp (plus the `map_invalidated`
override); dictionary freshness is reference-file git-drift since `built_at`, with
DB-side currency honestly `unknowable` absent a live connection. Never a
fabricated `current`; never a bare wall clock (deng-toolkit's anti-pattern).

`lineage_graph` lives in `hooks/` — NOT a `services/` sibling — so it is imported
LAZILY inside the one function that needs it. A module-load import of a
non-services module would trip `services/separation.py::check_separation`; an
in-function import is the blessed lazy form that check ignores. The
`sys.path.insert` below is a statement (not an import), so it is invisible to that
AST check and only makes the lazy `import lineage_graph` resolve by bare name.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any, Callable, Optional

_HERE = Path(__file__).resolve().parent
_HOOKS = str(_HERE.parents[1] / "hooks")   # services/knowledge_server -> <repo>/hooks
if _HOOKS not in sys.path:
    sys.path.insert(0, _HOOKS)

CURRENT = "current"
STALE = "stale"
UNKNOWABLE = "unknowable"
VALID_VERDICTS = {CURRENT, STALE, UNKNOWABLE}


def _lineage_graph():
    """Lazy import of `hooks/lineage_graph.py` (keeps check_separation green)."""
    import lineage_graph  # noqa: E402  (in-function on purpose: not a services/ sibling)
    return lineage_graph


def envelope(verdict: str, basis: Any) -> dict[str, Any]:
    """The freshness envelope every tool response carries: `{verdict, basis}`."""
    if verdict not in VALID_VERDICTS:
        raise ValueError(
            f"invalid freshness verdict {verdict!r} (one of {sorted(VALID_VERDICTS)})")
    return {"verdict": verdict, "basis": list(basis or [])}


def _stamp_note(stamp: Any) -> str:
    return f"stamp: {stamp}" if stamp else "no stamp recorded"


def map_freshness(
    graph: dict,
    *,
    changed_paths: Optional[list],
    stamp: Any = None,
    map_invalidated: Optional[list] = None,
    subtree_node_ids: Optional[Any] = None,
) -> dict[str, Any]:
    """Freshness of a map / lineage graph.

    Precedence: (1) an explicit `map_invalidated` override is `stale` even when
    drift is uncomputable; (2) `changed_paths is None` (git unavailable) is
    honestly `unknowable`, never fabricated `current`; (3) otherwise the verdict
    is change-driven — `stale` iff any node in the queried subtree (or the whole
    graph when `subtree_node_ids is None`) is transitively stale under the changed
    paths, else `current`.
    """
    basis: list[str] = []
    if map_invalidated:
        basis.append(f"map_invalidated override active: {list(map_invalidated)}")
        basis.append(_stamp_note(stamp))
        return envelope(STALE, basis)
    if changed_paths is None:
        basis.append("changed paths since the stamp could not be determined (git unavailable)")
        basis.append(_stamp_note(stamp))
        return envelope(UNKNOWABLE, basis)

    stale = _lineage_graph().transitive_stale_nodes(graph or {}, changed_paths)
    if subtree_node_ids is not None:
        subtree = set(subtree_node_ids)
        stale = {n for n in stale if n in subtree}
    if stale:
        basis.append(f"stale nodes (transitive over changed paths): {sorted(stale)}")
        basis.append(_stamp_note(stamp))
        return envelope(STALE, basis)
    basis.append(
        f"no reachable node changed since the stamp ({len(list(changed_paths))} path(s) checked)")
    basis.append(_stamp_note(stamp))
    return envelope(CURRENT, basis)


def dictionary_freshness(
    *,
    changed_paths: Optional[list],
    built_at: Any = None,
    reference_files: Optional[list] = None,
) -> dict[str, Any]:
    """Repo-side freshness of a data dictionary — reference-file drift since
    `built_at`. The DB-side currency is UNKNOWABLE without a live connection and
    is disclosed in the basis of every verdict (so even a `current` repo-side
    answer never implies the live DB is fresh — deng's warm-catalog trap).
    """
    ref = list(reference_files or [])
    db_note = f"DB-side currency unknowable without a live connection (built_at={built_at})"
    if changed_paths is None:
        return envelope(UNKNOWABLE, [
            "reference-file drift could not be determined (git unavailable)", db_note])
    changed_set = set(changed_paths)
    hits = sorted(f for f in ref if f in changed_set)
    if hits:
        return envelope(STALE, [
            f"reference files changed since built_at: {hits}", db_note])
    return envelope(CURRENT, [
        f"no reference file changed since built_at ({len(ref)} tracked)", db_note])


def _default_git_runner(args: list[str]) -> str:
    """Run `git ...` and return stdout. Raises on non-zero exit / missing git."""
    completed = subprocess.run(args, capture_output=True, text=True, check=True)
    return completed.stdout


def git_changed_paths(
    stamp: Any,
    repo_root: Any,
    *,
    runner: Optional[Callable[[list], str]] = None,
) -> Optional[list]:
    """Repo-relative paths changed since `stamp` via `git log --since`.

    Returns a sorted, de-duplicated list, or `None` when the window cannot be
    determined (no stamp, or git unavailable / errored) — the `None` that the
    freshness functions map to an honest `unknowable` rather than a fabricated
    `current`. `runner` is injectable so tests stay hermetic (no real git / repo).
    """
    if not stamp:
        return None
    runner = runner or _default_git_runner
    args = ["git", "-C", str(repo_root), "log", f"--since={stamp}",
            "--name-only", "--pretty=format:"]
    try:
        out = runner(args)
    except Exception:  # git absent, not a repo, non-zero exit — all => unknowable
        return None
    return sorted({line.strip() for line in (out or "").splitlines() if line.strip()})
