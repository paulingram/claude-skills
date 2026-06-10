#!/usr/bin/env python3
"""Cross-session file-scope lock layer for the architect-team plugin (v1.0.0).

Two concurrent `/architect-team` invocations in separate Claude Code sessions
must not clobber overlapping file scopes. This module ships the primitive: each
Lead acquires a lock over its declared file scope before dispatching teammates;
disjoint scopes proceed in true parallel; overlapping scopes are surfaced as a
conflict that the orchestrator surfaces back to the user.

Lock files live at `.architect-team/locks/<sha256-of-scope-glob>.json` and
carry:

  {
    "holder":       "<run_id>",
    "scope_glob":   "src/auth/**",
    "acquired_at":  "<ISO 8601 UTC>",
    "ttl_seconds":  14400,
    "lock_id":      "<sha256-hex>"
  }

A lock is stale when (acquired_at + ttl_seconds) is in the past, OR the file is
malformed (corrupt JSON, missing required fields, unparseable timestamp).
`acquire_lock` auto-cleans every stale lock it encounters before deciding.

Concurrency model (advisory, best-effort — REQ-R5):
  - The IDENTICAL-scope race (two acquirers, same scope-hash filename) is closed
    hard: the lock file is created with ``os.open(path, O_CREAT|O_EXCL|O_WRONLY)``
    so the OS guarantees exactly one creator wins; a second concurrent creator
    gets ``FileExistsError`` and is reported ``blocked``. A *stale* lock at that
    path is reclaimed by staging a fresh lock in an EXCL-created temp and
    swapping it in with an atomic ``os.replace`` (no destructive unlink→write
    window).
  - The INTERSECTING-scope race (two acquirers, DIFFERENT scopes whose path
    spaces overlap — different filenames, so EXCL cannot see the collision) is
    closed advisorily: after its EXCL write succeeds, an acquirer RE-SCANS the
    lock dir; if a live lock with an intersecting scope holds an earlier
    ``(acquired_at, session-id)`` position, the later acquirer releases its own
    lock and reports ``blocked`` naming the winner.
  - Residual boundary (honest): the intersecting-scope resolution is advisory,
    not kernel-atomic — it relies on every participant running the same re-scan
    + tiebreak. A writer that bypasses ``acquire_lock`` is not constrained, and
    the ``acquired_at`` second-resolution timestamp makes the order deterministic
    only down to the lexicographic ``(acquired_at, session-id)`` pair (two
    acquirers inside the same clock-second tie-break on session id). This layer
    is a coordination aid for cooperating ``/architect-team`` Leads, not a
    mutex.

Reuse Decision: RD-3 (build-new — no existing equivalent). Stdlib only per
NF-2.

References:
  - openspec/changes/agent-teams-refactor/specs/agent-teams-mode/spec.md REQ-3
  - skills/team-spawning-and-review-gates/SKILL.md (the
    non-overlapping-file-scope discipline this layer enforces across sessions)
"""
from __future__ import annotations

import fnmatch
import hashlib
import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# ---- Constants ---------------------------------------------------------------

# Legacy default locks directory (relative to cwd). Kept exported for any
# downstream consumer that still references `locks.DEFAULT_LOCKS_DIR` directly
# — the public API never reads this constant. As of v1.1.0 the resolved default
# is computed by `_default_locks_dir()` below, which routes through
# `scripts/setup/worktree_paths.shared_state_dir()` so two `/architect-team`
# sessions in two git worktrees of the same repo coordinate on the same lock
# directory (the MAIN worktree's `.architect-team/locks/`).
DEFAULT_LOCKS_DIR = Path(".architect-team") / "locks"

# Required fields on a well-formed lock file. Any missing field => stale.
_REQUIRED_LOCK_FIELDS = ("holder", "scope_glob", "acquired_at", "ttl_seconds", "lock_id")

# Wildcard characters that mark the end of a glob's literal-prefix portion.
_WILDCARD_CHARS = set("*?[")

# Suffix for the transient file used to stage a fresh lock when reclaiming a
# stale lock at an already-existing path (EXCL-create the temp, then os.replace
# it atomically over the stale lock — no destructive unlink→write window).
_LOCK_TMP_SUFFIX = ".reclaim.tmp"

# Stabilization parameters for the intersecting-scope race resolution (REQ-R5b).
# After its EXCL write, an acquirer that observes itself as the EARLIEST
# intersecting lock must confirm that observation across `_RESCAN_CONFIRMATIONS`
# consecutive scans separated by `_RESCAN_INTERVAL_SECONDS`, so a competitor
# whose file is not yet visible at the first scan is caught before the acquirer
# commits to keeping its lock. Any scan that reveals an earlier competitor short-
# circuits to "yield" immediately. The window is intentionally small — this is an
# advisory coordination aid for cooperating Leads, not a hot path.
_RESCAN_CONFIRMATIONS = 3
_RESCAN_INTERVAL_SECONDS = 0.02


# ---- Public API --------------------------------------------------------------


def acquire_lock(
    scope_glob: str,
    ttl_seconds: int,
    run_id: str,
    locks_dir: Path | None = None,
) -> dict:
    """Acquire a lock over the file scope named by `scope_glob`.

    Behavior:
      1. Sweep `locks_dir` for stale or malformed locks; remove them.
      2. Iterate the surviving locks. If any holds a glob that intersects
         `scope_glob`, return `{"status": "blocked", "held_by": <holder>,
         "lock_id": <existing-lock-id>}`.
      3. Otherwise create the lock file atomically with
         ``os.open(path, O_CREAT|O_EXCL|O_WRONLY)`` (REQ-R5a). If the path
         already exists at this point — a same-scope acquirer that raced past the
         sweep+scan — acquisition is ``blocked`` (no silent overwrite); a *stale*
         survivor at that path is reclaimed via an atomic ``os.replace`` of a
         freshly-EXCL-created temp.
      4. RE-SCAN the lock dir (REQ-R5b). If another live lock with an
         INTERSECTING scope holds an earlier ``(acquired_at, session-id)``
         position, release own lock and return ``blocked`` naming that winner.

    Args:
        scope_glob: a fnmatch-style path glob (e.g. ``"src/auth/**"``). Two
            globs conflict if their path-space intersects — see globs_intersect.
        ttl_seconds: how long the lock is valid before being treated as stale.
            The architect-team convention is 4h (14400) for full runs.
        run_id: caller's identity (the Lead's run-slug, typically). Recorded
            as the lock's holder so a blocked acquirer can name the holder.
        locks_dir: where lock files live. Defaults to ``.architect-team/locks``
            under cwd. The directory is created on demand.

    Returns:
        Either ``{"status": "acquired", "lock_id": <hex>}`` or
        ``{"status": "blocked", "held_by": <holder>, "lock_id": <hex>}``.
    """
    locks_dir = _resolve_locks_dir(locks_dir)
    locks_dir.mkdir(parents=True, exist_ok=True)

    # Step 1: clean stale + malformed locks so they don't falsely block.
    _sweep_stale(locks_dir)

    # Step 2: check intersection against every surviving lock.
    for lock_path, lock in _iter_valid_locks(locks_dir):
        held_scope = lock.get("scope_glob")
        if not isinstance(held_scope, str):
            continue
        if globs_intersect(scope_glob, held_scope):
            return {
                "status": "blocked",
                "held_by": lock.get("holder"),
                "lock_id": lock.get("lock_id"),
            }

    # Step 3: create the lock atomically (O_CREAT|O_EXCL). The OS guarantees a
    # single creator wins the IDENTICAL-scope race — a concurrent same-scope
    # acquirer that raced past Step 1+2 hits FileExistsError here.
    lock_id = _hash_scope(scope_glob)
    payload = {
        "holder": run_id,
        "scope_glob": scope_glob,
        "acquired_at": datetime.now(timezone.utc).isoformat(),
        "ttl_seconds": int(ttl_seconds),
        "lock_id": lock_id,
    }
    lock_path = locks_dir / f"{lock_id}.json"
    if not _write_lock_excl(lock_path, payload):
        # The path already exists. Re-read it: a live holder => blocked; a stale
        # survivor (the sweep missed a just-landed expiry, or a race) => reclaim.
        existing = _read_lock(lock_path)
        if existing is not None and not _lock_is_expired(
            existing, datetime.now(timezone.utc)
        ):
            return {
                "status": "blocked",
                "held_by": existing.get("holder"),
                "lock_id": existing.get("lock_id") or lock_id,
            }
        # Stale (or unreadable) lock at this path: reclaim it atomically.
        if not _reclaim_stale_lock(lock_path, payload):
            # Lost the reclaim race to another acquirer — re-read the winner.
            winner = _read_lock(lock_path)
            return {
                "status": "blocked",
                "held_by": (winner or {}).get("holder"),
                "lock_id": (winner or {}).get("lock_id") or lock_id,
            }

    # Step 4: post-write re-scan for the INTERSECTING-scope race. Our EXCL write
    # could not see a DIFFERENT-scope acquirer (different filename); resolve by
    # the deterministic (acquired_at, session-id) tiebreak — STABILIZED so a
    # later writer cannot keep its lock merely because it re-scanned before an
    # earlier competitor's file became visible (see _resolve_intersecting_race).
    winner = _resolve_intersecting_race(locks_dir, scope_glob, payload)
    if winner is not None:
        release_lock(lock_id, locks_dir=locks_dir)
        return {
            "status": "blocked",
            "held_by": winner.get("holder"),
            "lock_id": winner.get("lock_id"),
        }

    return {"status": "acquired", "lock_id": lock_id}


def release_lock(lock_id: str, locks_dir: Path | None = None) -> None:
    """Remove the lock file for `lock_id`. Idempotent — missing is a no-op.

    Args:
        lock_id: the sha256-hex identifier returned by `acquire_lock`.
        locks_dir: see `acquire_lock`.
    """
    locks_dir = _resolve_locks_dir(locks_dir)
    lock_path = locks_dir / f"{lock_id}.json"
    try:
        lock_path.unlink()
    except FileNotFoundError:
        return
    except OSError:
        # Best-effort cleanup: a permission error or a race with another sweep
        # is not a fatal condition; the next acquire will treat the leftover as
        # stale on the next sweep.
        return


def detect_stale(locks_dir: Path | None = None) -> list[str]:
    """Return the lock IDs of every stale OR malformed lock file in `locks_dir`.

    A lock is stale when ANY of the following is true:
      - the file is not valid JSON
      - the parsed JSON is not an object
      - a required field is missing
      - `acquired_at` is not a parseable ISO 8601 timestamp
      - `acquired_at + ttl_seconds` is in the past

    For malformed files where no lock_id field is available, the file STEM (the
    portion of the filename before `.json`) is reported instead — that's the
    canonical identifier of a lock file on disk.

    Args:
        locks_dir: see `acquire_lock`. A missing directory yields ``[]``.
    """
    locks_dir = _resolve_locks_dir(locks_dir)
    if not locks_dir.is_dir():
        return []

    stale_ids: list[str] = []
    now = datetime.now(timezone.utc)
    for path in sorted(locks_dir.glob("*.json")):
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            stale_ids.append(path.stem)
            continue

        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            stale_ids.append(path.stem)
            continue

        if not isinstance(data, dict):
            stale_ids.append(path.stem)
            continue

        missing = [f for f in _REQUIRED_LOCK_FIELDS if f not in data]
        if missing:
            # If lock_id is present we use it; otherwise the filename stem.
            identifier = data.get("lock_id") or path.stem
            stale_ids.append(identifier)
            continue

        if _lock_is_expired(data, now):
            stale_ids.append(data.get("lock_id") or path.stem)

    return stale_ids


def globs_intersect(a: str, b: str) -> bool:
    """Return True iff path globs `a` and `b` could match at least one common path.

    Implementation: extract each glob's literal-prefix (the longest leading
    path-segment portion containing no wildcard characters), then construct
    candidate sample paths from each prefix (the prefix alone, and the prefix
    appended with a synthetic deeper path). Run those candidates through the
    other glob's fnmatch-translated regex; if any candidate matches, the
    globs intersect.

    A SECOND candidate class (REQ-R5c) covers the leading-wildcard-vs-prefix
    miss: when one glob is anchored by a literal PREFIX and the other by a
    literal SUFFIX, the shared path is the prefix joined to the suffix. We
    synthesize ``prefix_of_one + "/" + suffix_of_other`` (both directions) and
    test it against both regexes — so ``("src/**", "**/auth.py")`` finds the
    common path ``src/auth.py`` and returns True.

    This is heuristic — it correctly identifies the headline cases the spec
    requires (REQ-3 scenarios 3.2 and 3.3, plus REQ-R5c) while staying
    stdlib-only:

      - ``("src/auth/**", "src/auth/login/**")`` -> True (login is under auth)
      - ``("src/auth/**", "src/billing/**")``    -> False (disjoint roots)
      - ``("src/*.py",   "src/foo.py")``         -> True
      - ``("src/*.py",   "src/foo.ts")``         -> False
      - ``("src/**",     "**/auth.py")``         -> True (shared src/auth.py)
      - identical globs always intersect
    """
    if a == b:
        return True

    regex_a = re.compile(fnmatch.translate(a))
    regex_b = re.compile(fnmatch.translate(b))

    for candidate in _candidate_paths(a):
        if regex_b.match(candidate):
            return True

    for candidate in _candidate_paths(b):
        if regex_a.match(candidate):
            return True

    # Cross prefix/suffix candidate class: a prefix-anchored glob intersects a
    # suffix-anchored glob at (prefix-of-one)/(suffix-of-other). Test both
    # synthesized paths against BOTH globs so the shared path must satisfy each.
    for candidate in _cross_prefix_suffix_candidates(a, b):
        if regex_a.match(candidate) and regex_b.match(candidate):
            return True

    return False


def cdlg_overlap(
    graph: Any,
    funcs_a: Any,
    funcs_b: Any,
) -> dict:
    """Decide whether two work-items overlap by CALL-GRAPH reachability (PARA-01).

    File-path locks (``acquire_lock`` / ``globs_intersect``) catch the case where
    two work-items edit the same file. They do NOT catch the case where two items
    edit *different* files but share a hot callee — item A's function transitively
    calls a function in item B's set. This helper adds that second, call-graph
    signal (it ADDS to, and never replaces, the file-path lock logic).

    The rule (REQ-PARA-01): two work-items overlap iff their ``calls``-closures
    intersect — i.e. they share a ``func://`` node, OR one item reaches a
    function in the other's set, OR both items reach a COMMON downstream callee
    (a "shared hot callee" in neither set). The reachability concept is reused
    from ``hooks/lineage_graph.py`` (the ``REACHABILITY_EDGE_KINDS`` /
    ``calls``-edge walk); we import that module so this helper consumes the CDLG
    rather than re-deriving the edge vocabulary.

    Args:
        graph: a CDLG document (the ``lineage-graph.json`` shape — a dict with
            ``nodes`` / ``edges``). Only ``calls`` edges are walked for
            reachability. A malformed / empty graph degrades gracefully: with no
            ``calls`` edges, overlap reduces to the shared-node check.
        funcs_a: the ``func://`` ids in work-item A's set (any iterable of strings).
        funcs_b: the ``func://`` ids in work-item B's set (any iterable of strings).

    Returns:
        ``{"overlap": bool, "shared_functions": [...], "shared_subtree": [...]}``:

          - ``shared_functions`` — the ``func://`` ids present in BOTH sets
            (the direct-share signal), sorted.
          - ``shared_subtree`` — the ``func://`` ids reachable (via ``calls``
            edges) from BOTH items but not directly shared as seeds (the
            transitive shared-callee signal), sorted.
          - ``overlap`` — ``True`` iff either list is non-empty.
    """
    set_a = _as_func_set(funcs_a)
    set_b = _as_func_set(funcs_b)

    # Direct share: any func:// node present in both work-items' sets.
    shared_functions = set_a & set_b

    # Transitive share: build the calls-edge adjacency once, then intersect the
    # two items' calls-CLOSURES. Each closure INCLUDES its seed set, so overlap
    # is caught in all three shapes: (a) one item reaches a function in the
    # other's set, (b) the two sets share a func:// node directly, and crucially
    # (c) both items reach a COMMON downstream callee that is in NEITHER set —
    # the "share a hot callee" acceptance criterion (REQ-PARA-01). Reusing the
    # CDLG's calls-edge concept from hooks/lineage_graph.py.
    adjacency = _calls_adjacency(graph)
    closure_a = set_a | _reachable_funcs(set_a, adjacency)
    closure_b = set_b | _reachable_funcs(set_b, adjacency)

    # The shared subtree is every function reachable from BOTH items (a shared
    # callee / common descendant), excluding the directly-shared seeds which are
    # reported separately in shared_functions.
    shared_subtree = (closure_a & closure_b) - shared_functions

    overlap = bool(shared_functions or shared_subtree)
    return {
        "overlap": overlap,
        "shared_functions": sorted(shared_functions),
        "shared_subtree": sorted(shared_subtree),
    }


# ---- Internals ---------------------------------------------------------------


def _as_func_set(funcs: Any) -> set[str]:
    """Coerce a work-item's function list into a set of non-empty string ids.

    Defensive against None / non-iterable / non-string members — those are
    dropped rather than raising, so a malformed work-item set degrades to "no
    functions" instead of crashing the overlap check.
    """
    if not funcs or isinstance(funcs, (str, bytes)):
        # A bare string is NOT a set of ids — treat it as a single id only if
        # it is a non-empty str (a common caller convenience), else empty.
        if isinstance(funcs, str) and funcs:
            return {funcs}
        return set()
    out: set[str] = set()
    try:
        iterator = iter(funcs)
    except TypeError:
        return set()
    for item in iterator:
        if isinstance(item, str) and item:
            out.add(item)
    return out


def _calls_adjacency(graph: Any) -> dict[str, set[str]]:
    """Adjacency map (src -> set of dst) over the CDLG's ``calls`` edges.

    Reuses ``hooks/lineage_graph.py``'s edge vocabulary: we walk only ``calls``
    edges (the function→callee control-flow edges). The lineage module is
    imported lazily and best-effort — if it cannot be loaded for any reason, we
    fall back to the literal string ``"calls"`` so the overlap check still works
    (the kind name is stable, REQ-DOC-01).
    """
    if not isinstance(graph, dict):
        return {}
    calls_kind = _calls_edge_kind()
    adj: dict[str, set[str]] = {}
    for edge in graph.get("edges", []) or []:
        if not isinstance(edge, dict):
            continue
        if edge.get("kind") != calls_kind:
            continue
        src = edge.get("src")
        dst = edge.get("dst")
        if isinstance(src, str) and src and isinstance(dst, str) and dst:
            adj.setdefault(src, set()).add(dst)
    return adj


def _calls_edge_kind() -> str:
    """The CDLG edge kind that denotes a function→callee call.

    Sourced from ``hooks/lineage_graph.py`` so this module consumes the CDLG's
    canonical vocabulary rather than hard-coding it. Best-effort: falls back to
    the stable literal ``"calls"`` if the module is unreachable.
    """
    try:
        lineage = _load_lineage_graph()
        kinds = getattr(lineage, "REACHABILITY_EDGE_KINDS", None)
        # REACHABILITY_EDGE_KINDS is {"calls", "serves"}; "calls" is the
        # function→callee edge we want for work-item overlap (a work-item is a
        # set of functions, not endpoints, so the serves edge is not relevant
        # to function-set reachability).
        if kinds and "calls" in kinds:
            return "calls"
    except Exception:
        pass
    return "calls"


def _reachable_funcs(seeds: set[str], adjacency: dict[str, set[str]]) -> set[str]:
    """Every node reachable FROM ``seeds`` via ``calls`` edges, excluding the seeds.

    A plain DFS over the calls-edge adjacency. The seeds themselves are NOT
    included in the result — the result is the set of *callees* the seed set
    reaches, which is what the transitive-overlap check intersects against the
    other work-item's set. Cycle-safe via a visited set.
    """
    reached: set[str] = set()
    stack: list[str] = list(seeds)
    seen: set[str] = set(seeds)
    while stack:
        cur = stack.pop()
        for nxt in adjacency.get(cur, ()):  # callees of cur
            if nxt not in seen:
                seen.add(nxt)
                reached.add(nxt)
                stack.append(nxt)
    return reached


def _load_lineage_graph():
    """Import ``hooks/lineage_graph.py`` lazily (sibling module).

    Mirrors ``_load_worktree_paths`` — uses
    ``importlib.util.spec_from_file_location`` so the lock layer does not depend
    on a particular ``sys.path`` layout. The path is computed relative to this
    file: ``hooks/locks.py`` -> ``hooks/lineage_graph.py`` (same directory).
    """
    import importlib.util

    here = Path(__file__).resolve().parent
    target = here / "lineage_graph.py"
    spec = importlib.util.spec_from_file_location("lineage_graph", target)
    if spec is None or spec.loader is None:
        raise ImportError(f"could not load lineage_graph from {target}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _resolve_locks_dir(locks_dir: Path | None) -> Path:
    """Resolve the locks directory used by every public function.

    Behavior:
      - An explicit `locks_dir` argument is honored verbatim (test-isolation
        path used by every scenario in `tests/test_locks.py`).
      - `None` routes through `_default_locks_dir()` so the lock layer
        coordinates across git worktrees per the v1.1.0 fix.
    """
    if locks_dir is not None:
        return Path(locks_dir)
    return _default_locks_dir()


def _default_locks_dir() -> Path:
    """Return the default `.architect-team/locks/` directory.

    Routes through `scripts/setup/worktree_paths.shared_state_dir()` so two
    `/architect-team` sessions running in separate git worktrees of the same
    repo share the same lock directory (the MAIN worktree's
    `.architect-team/locks/`). In a non-worktree clone this resolves to
    `Path.cwd() / ".architect-team" / "locks"` — the same path v1.0.0 used,
    so single-session users see zero behavior change.

    The import is performed inside the function (not at module top) to avoid
    forcing the `scripts/setup/` directory onto `sys.path` for callers that
    only use the locks API. Falling back to the legacy default keeps the lock
    layer working even if `worktree_paths.py` becomes unreachable for any
    reason (deleted, syntax error, etc.).
    """
    try:
        worktree_paths = _load_worktree_paths()
        return worktree_paths.shared_state_dir() / "locks"
    except Exception:
        # Best-effort: if the worktree-aware helper can't load for any
        # reason, fall back to the v1.0.0 default. The lock layer continues
        # to work; only the cross-worktree coordination guarantee is lost in
        # this degenerate case, and the orchestrator surfaces no surprise.
        return Path.cwd() / DEFAULT_LOCKS_DIR


def _load_worktree_paths():
    """Import `scripts/setup/worktree_paths.py` lazily.

    Uses `importlib.util.spec_from_file_location` so the lock layer does not
    depend on a particular `sys.path` layout. The path is computed relative
    to this file: `hooks/locks.py` -> `<plugin-root>/scripts/setup/worktree_paths.py`.
    """
    import importlib.util

    here = Path(__file__).resolve().parent
    plugin_root = here.parent
    target = plugin_root / "scripts" / "setup" / "worktree_paths.py"
    spec = importlib.util.spec_from_file_location("worktree_paths", target)
    if spec is None or spec.loader is None:
        raise ImportError(f"could not load worktree_paths from {target}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _hash_scope(scope_glob: str) -> str:
    """SHA-256 of the scope-glob string, hex-encoded. Stable across processes."""
    return hashlib.sha256(scope_glob.encode("utf-8")).hexdigest()


def _literal_prefix(glob: str) -> str:
    """Return the leading path-segment portion of `glob` that contains no wildcard.

    Examples:
      "src/auth/**"          -> "src/auth"
      "src/auth/login/**"    -> "src/auth/login"
      "src/*.py"             -> "src"
      "README.md"            -> "README.md"
      "**"                   -> ""
      "src/[ab]/foo.py"      -> "src"
    """
    segments = glob.split("/")
    prefix_parts: list[str] = []
    for seg in segments:
        if any(c in seg for c in _WILDCARD_CHARS):
            break
        prefix_parts.append(seg)
    return "/".join(prefix_parts)


def _literal_suffix(glob: str) -> str:
    """Return the trailing path-segment portion of `glob` that contains no wildcard.

    The mirror of `_literal_prefix`, walking segments from the END. Used by the
    REQ-R5c cross prefix/suffix candidate class.

    Examples:
      "**/auth.py"           -> "auth.py"
      "src/auth/**"          -> ""           (trailing "**" is a wildcard segment)
      "**/login/*.py"        -> ""
      "README.md"            -> "README.md"
      "**"                   -> ""
      "src/auth/**/x.py"     -> "x.py"
    """
    segments = glob.split("/")
    suffix_parts: list[str] = []
    for seg in reversed(segments):
        if any(c in seg for c in _WILDCARD_CHARS):
            break
        suffix_parts.append(seg)
    suffix_parts.reverse()
    return "/".join(suffix_parts)


def _cross_prefix_suffix_candidates(a: str, b: str) -> list[str]:
    """Synthesize the prefix-of-one + suffix-of-other shared-path candidates.

    For a prefix-anchored glob (literal leading segments, then a wildcard) and a
    suffix-anchored glob (a wildcard, then literal trailing segments), the shared
    path is ``<prefix>/<suffix>``. We build both directions:

      - ``_literal_prefix(a)`` + ``_literal_suffix(b)``
      - ``_literal_prefix(b)`` + ``_literal_suffix(a)``

    Skipping any direction whose prefix or suffix is empty (an empty side gives
    no anchor — that direction cannot manufacture a meaningful shared path). The
    candidate is returned for the CALLER to verify against BOTH globs' regexes,
    so a non-shared synthesized path (e.g. ``src/billing/charge.py/auth.py``)
    is rejected by the prefix glob and never produces a false positive.
    """
    out: list[str] = []
    for prefix_glob, suffix_glob in ((a, b), (b, a)):
        prefix = _literal_prefix(prefix_glob)
        suffix = _literal_suffix(suffix_glob)
        if prefix and suffix:
            out.append(f"{prefix}/{suffix}")
    return out


def _candidate_paths(glob: str) -> list[str]:
    """Return sample candidate paths to probe against another glob's regex.

    Returns up to three forms:
      - the literal prefix as-is (handles "src/foo.py" intersection cases)
      - prefix + a synthetic file name (handles "src/auth/foo.py" cases)
      - prefix + a synthetic deep path (handles "src/auth/login/x/y/z.py" cases)
    """
    prefix = _literal_prefix(glob)
    if not prefix:
        # A leading-wildcard glob (e.g. "**") matches everything — return a
        # representative sample so the intersection-with-anything check fires.
        return ["any/file.py", "any/path/here.py", "any"]
    return [
        prefix,
        f"{prefix}/__intersect_probe__.txt",
        f"{prefix}/__a__/__b__/__c__.txt",
    ]


def _serialize_lock(payload: dict[str, Any]) -> bytes:
    """Encode a lock payload as the canonical on-disk UTF-8 bytes.

    Matches the original ``json.dumps(payload, indent=2)`` + utf-8 shape so the
    EXCL write path is byte-compatible with the prior ``write_text`` form (the
    REQ-3 scenario tests parse this exact shape).
    """
    return json.dumps(payload, indent=2).encode("utf-8")


def _write_lock_excl(lock_path: Path, payload: dict[str, Any]) -> bool:
    """Create `lock_path` atomically via ``os.open(O_CREAT|O_EXCL|O_WRONLY)``.

    Returns True iff THIS call created the file (won the create race). Returns
    False if the file already existed (``FileExistsError`` — a concurrent
    same-scope acquirer beat us, or a stale survivor sits at the path). Any other
    OSError propagates (a genuine filesystem failure should not be masked as a
    benign "already exists").

    ``O_EXCL`` is the cross-platform no-overwrite primitive — it works on Windows
    (no ``fcntl`` needed), satisfying REQ-R5a's Windows constraint.
    """
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
    try:
        fd = os.open(str(lock_path), flags, 0o644)
    except FileExistsError:
        return False
    try:
        os.write(fd, _serialize_lock(payload))
    finally:
        os.close(fd)
    return True


def _reclaim_stale_lock(lock_path: Path, payload: dict[str, Any]) -> bool:
    """Atomically replace a STALE lock at `lock_path` with a fresh `payload`.

    The fresh lock is first staged in an EXCL-created temp (so two acquirers
    racing to reclaim the same stale lock cannot both stage), then swapped over
    the stale lock with ``os.replace`` (atomic on POSIX and Windows — same
    primitive hooks/inflight_inbox.py uses). Returns True iff this call performed
    the swap; False if it lost the temp-create race to another reclaimer (its
    temp already existed) or the swap failed.
    """
    tmp_path = lock_path.with_name(lock_path.name + _LOCK_TMP_SUFFIX)
    # Stage the fresh lock in our own EXCL temp; losing this race => someone else
    # is reclaiming, so we back off and report failure (the caller re-reads the
    # winner).
    if not _write_lock_excl(tmp_path, payload):
        return False
    try:
        os.replace(str(tmp_path), str(lock_path))
    except OSError:
        _safe_unlink(tmp_path)
        return False
    return True


def _read_lock(lock_path: Path) -> dict[str, Any] | None:
    """Read+parse a single lock file. Returns None on any read/parse failure."""
    try:
        data = json.loads(lock_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    if any(f not in data for f in _REQUIRED_LOCK_FIELDS):
        return None
    return data


def _lock_position(lock: dict[str, Any]) -> tuple[str, str]:
    """The deterministic ordering key for a lock: ``(acquired_at, holder)``.

    The earlier ``acquired_at`` wins; ties (same clock-second) break on the
    holder/session-id string. ISO-8601 UTC timestamps sort correctly
    lexicographically, so a plain tuple compare gives the wall-clock order. A
    missing/non-string field sorts LAST (an ill-formed competitor never wins the
    tiebreak against a well-formed one).
    """
    acquired = lock.get("acquired_at")
    holder = lock.get("holder")
    acquired_key = acquired if isinstance(acquired, str) else "~"  # '~' > digits/'T'
    holder_key = holder if isinstance(holder, str) else "~"
    return (acquired_key, holder_key)


def _earlier_intersecting_winner(
    locks_dir: Path,
    scope_glob: str,
    own: dict[str, Any],
) -> dict[str, Any] | None:
    """SINGLE-SCAN primitive: the live intersecting lock out-ranking `own`, else None.

    After our EXCL write landed, a DIFFERENT-scope acquirer (different filename —
    invisible to our EXCL) may hold an intersecting scope. We scan every OTHER
    live lock; among those whose scope intersects ours, the one with the smallest
    ``(acquired_at, holder)`` position wins. If that winner ranks strictly EARLIER
    than `own`, we must yield to it; otherwise this scan sees no blocker.

    This is ONE observation — used by `_resolve_intersecting_race`, which repeats
    it across a confirmation window to close the race where a competitor's file
    is not yet visible at the first scan. Our own lock is excluded by lock_id; the
    strict ``<`` comparison means an exact position tie keeps our lock (no
    double-release).
    """
    own_id = own.get("lock_id")
    own_pos = _lock_position(own)
    best: dict[str, Any] | None = None
    best_pos: tuple[str, str] | None = None
    for path, lock in _iter_valid_locks(locks_dir):
        if lock.get("lock_id") == own_id:
            continue
        held_scope = lock.get("scope_glob")
        if not isinstance(held_scope, str):
            continue
        if not globs_intersect(scope_glob, held_scope):
            continue
        pos = _lock_position(lock)
        if best_pos is None or pos < best_pos:
            best, best_pos = lock, pos
    if best is not None and best_pos is not None and best_pos < own_pos:
        return best
    return None


def _resolve_intersecting_race(
    locks_dir: Path,
    scope_glob: str,
    own: dict[str, Any],
) -> dict[str, Any] | None:
    """STABILIZED resolver: the intersecting winner `own` must yield to, or None.

    The single-scan `_earlier_intersecting_winner` has a race: a LATER acquirer
    that scans BEFORE an EARLIER competitor's file is visible sees no blocker and
    keeps its lock — then the earlier competitor, scanning later, also keeps
    (it is earliest), so BOTH hold and the intersecting race is unresolved.

    The fix is to stabilize the "I see no earlier competitor" observation:

      - ANY scan that reveals an earlier competitor short-circuits to "yield"
        immediately (return that competitor). The earlier writer is never wrong
        to be yielded to.
      - Concluding "keep" (return None) requires `_RESCAN_CONFIRMATIONS`
        CONSECUTIVE clean scans separated by `_RESCAN_INTERVAL_SECONDS`. A
        competitor whose file lands during the window is caught on a later scan
        and forces the yield.

    Termination is guaranteed: the loop runs a fixed number of bounded-sleep
    iterations. Correctness across cooperating acquirers: the globally EARLIEST
    intersecting acquirer can never see an earlier competitor, so it always keeps;
    every LATER acquirer eventually observes the earliest (its file is durable
    once written) within the confirmation window and yields. The residual
    advisory boundary (a non-cooperating writer, or a competitor delayed beyond
    the whole window) is documented in the module docstring.
    """
    clean_streak = 0
    last_winner: dict[str, Any] | None = None
    for attempt in range(_RESCAN_CONFIRMATIONS):
        winner = _earlier_intersecting_winner(locks_dir, scope_glob, own)
        if winner is not None:
            return winner  # an earlier competitor exists — yield now.
        clean_streak += 1
        last_winner = None
        if clean_streak >= _RESCAN_CONFIRMATIONS:
            break
        time.sleep(_RESCAN_INTERVAL_SECONDS)
    return last_winner


def _iter_valid_locks(locks_dir: Path):
    """Yield (path, parsed-lock) pairs for every non-stale lock in locks_dir.

    Malformed and expired locks are skipped (they were swept before this is
    called from acquire_lock; here we re-check defensively in case a second
    process landed a malformed file between the sweep and the iteration).
    """
    if not locks_dir.is_dir():
        return
    now = datetime.now(timezone.utc)
    for path in sorted(locks_dir.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(data, dict):
            continue
        if any(f not in data for f in _REQUIRED_LOCK_FIELDS):
            continue
        if _lock_is_expired(data, now):
            continue
        yield path, data


def _sweep_stale(locks_dir: Path) -> None:
    """Remove every stale OR malformed lock file in `locks_dir`."""
    if not locks_dir.is_dir():
        return
    now = datetime.now(timezone.utc)
    for path in list(locks_dir.glob("*.json")):
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            _safe_unlink(path)
            continue
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            _safe_unlink(path)
            continue
        if not isinstance(data, dict):
            _safe_unlink(path)
            continue
        if any(f not in data for f in _REQUIRED_LOCK_FIELDS):
            _safe_unlink(path)
            continue
        if _lock_is_expired(data, now):
            _safe_unlink(path)


def _safe_unlink(path: Path) -> None:
    """Best-effort file removal. Race or permission error is not fatal."""
    try:
        path.unlink()
    except (FileNotFoundError, OSError):
        return


def _lock_is_expired(data: dict[str, Any], now: datetime) -> bool:
    """Return True iff `data`'s acquired_at + ttl_seconds is in the past.

    Unparseable timestamps are treated as expired (the lock is malformed and
    cannot be safely respected).
    """
    raw = data.get("acquired_at")
    if not isinstance(raw, str):
        return True
    try:
        acquired = datetime.fromisoformat(raw)
    except ValueError:
        return True
    if acquired.tzinfo is None:
        acquired = acquired.replace(tzinfo=timezone.utc)

    ttl = data.get("ttl_seconds")
    if not isinstance(ttl, (int, float)):
        return True

    age = (now - acquired).total_seconds()
    return age >= float(ttl)
