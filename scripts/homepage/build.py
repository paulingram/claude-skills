# -*- coding: utf-8 -*-
"""Project homepage builder -- one self-contained HTML page per project, built
from the files that already exist.

The deterministic mechanism under the `project-homepage` skill. Reads, each
best-effort with an EXPLICIT missing state (a missing source renders as
"missing", never as an empty table pretending to be a fact):

* ``.architect-team/intake-state.json`` (phase, lane, dispatch mode, run id,
  appearance mode, codebases, map_invalidated).
* every ``.architect-team-*.json`` at the project root -- KEYS and set / unset
  only. The value of a key whose name contains ``token``, ``secret``, ``key``,
  ``password``, ``api`` or ``auth`` is NEVER rendered; no other value is
  rendered either, except the publish config's ``mode`` / ``adapter`` / ``slug``.
* the git commit identity record (name only), the agent model distribution
  (from the plugin's ``agents/`` dir when resolvable), the discipline registry.
* ``.architect-team/decisions.jsonl`` (`hooks/decisions_ledger.py`).
* the maps -- CODEBASE / ROUTE / INTEGRATION / DESIGN / INTERACTION_INTUITION /
  ENDPOINT_TRACE under ``<codebase>/docs/`` plus ``lineage-graph.json`` --
  each with its ``last_*`` stamp from frontmatter and a freshness verdict from
  ``services/knowledge_server/freshness.py``, loaded LAZILY inside the one
  function that needs it (the same in-function form freshness.py itself uses
  for `hooks/lineage_graph.py`); when that import fails the verdict is
  ``unknowable`` with the reason, never a fabricated ``current``.
* ``.architect-team/test-index.json``, the newest ``test-selection-*.json``,
  and every ``suite-manifest.json`` (counts by kind / persona / trust, the
  always-run pins, the last selection's reasons).
* ``.architect-team/run-metrics/*.json`` and the timing log via
  ``scripts/homepage/timings.py``.

Output: ``<workspace>/.architect-team/homepage/index.html`` -- static, no
JavaScript, no external resources, CSS tokens on ``:root`` with light values,
redefined under ``@media (prefers-color-scheme: dark)`` guarded by
``:root:not([data-theme="light"])`` and again under ``:root[data-theme="dark"]``,
readable at 400px. Seven panels (Structure, Settings, Decisions, Maps,
Functions, Tests, Performance) plus a Runs list, a header stamp (``built_at``,
the sources read, each source's sha256) and a "stale since" banner computed
from the previous build's recorded hashes (``build-state.json``) against the
current sources' hashes and mtimes.

``source_hashes(workspace)`` and ``is_stale(workspace)`` are exposed for the
SessionStart hook: a page whose sources moved since it was built says so.

CLI::

    python scripts/homepage/build.py [build] --workspace W [--out PATH] [--json]
    python scripts/homepage/build.py stale --workspace W [--json]

Exit codes: 0 ok, 2 usage error, 3 the build itself failed (the reason on
stderr). ``stale`` always exits 0 and reports ``{"stale": true|false, ...}``.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import importlib.util
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

HOMEPAGE_RELATIVE_DIR = ".architect-team/homepage"
PAGE_NAME = "index.html"
BUILD_STATE_NAME = "build-state.json"
BUILD_STATE_SCHEMA = "homepage-build-state/v1"

STATE_DIR = ".architect-team"
INTAKE_STATE = ".architect-team/intake-state.json"
GIT_IDENTITY = ".architect-team/git-identity.json"
DISCIPLINE_REGISTRY = ".architect-team/discipline-registry.json"
DECISIONS = ".architect-team/decisions.jsonl"
TEST_INDEX = ".architect-team/test-index.json"
TEST_SELECTION_GLOB = "test-selection-*.json"
RUN_METRICS_DIR = ".architect-team/run-metrics"
TIMINGS = ".architect-team/run-history/timings.jsonl"
PUBLISH_CONFIG = ".architect-team-publish.json"
SUITE_MANIFEST = "suite-manifest.json"
LINEAGE_GRAPH = "lineage-graph.json"

MAP_NAMES = (
    "CODEBASE_MAP.md", "ROUTE_MAP.md", "INTEGRATION_MAP.md", "DESIGN_MAP.md",
    "INTERACTION_INTUITION_MAP.md", "ENDPOINT_TRACE_MAP.md",
)
#: Frontmatter keys that stamp when a map was last produced, in priority order.
STAMP_KEYS = (
    "last_mapped", "last_routed", "last_synthesized", "last_designed",
    "last_intuited", "last_traced", "last_built", "built_at", "generated_at",
)
SENSITIVE_KEY_MARKERS = ("token", "secret", "key", "password", "api", "auth")
PANELS = ("structure", "settings", "decisions", "maps", "functions", "tests", "performance")
PANEL_TITLES = {
    "structure": "Structure", "settings": "Settings", "decisions": "Decisions",
    "maps": "Maps", "functions": "Functions", "tests": "Tests",
    "performance": "Performance",
}
SKIP_DIRS = frozenset({
    "node_modules", ".git", ".architect-team", "__pycache__", ".venv", "venv",
    "dist", "build", ".next", "test-results", "playwright-report", ".pytest_cache",
    ".mypy_cache", ".ruff_cache",
})
MAX_WALK_DEPTH = 3
MAX_DECISIONS = 50
MAX_RUNS = 25
MAX_HEADINGS = 14

VERDICT_UNKNOWABLE = "unknowable"
VERDICT_STALE = "stale"
VERDICT_CURRENT = "current"

_TIMINGS_PATH = Path(__file__).resolve().parent / "timings.py"


# --------------------------------------------------------------------------- #
# small helpers
# --------------------------------------------------------------------------- #

def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _iso_from_mtime(path: Path) -> Optional[str]:
    try:
        ts = path.stat().st_mtime
    except OSError:
        return None
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _rel(path: Path, workspace: Path) -> str:
    try:
        return path.resolve().relative_to(workspace.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _sha256(path: Path) -> Optional[str]:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


def _read_json(path: Path) -> Tuple[str, Any]:
    """``("ok", data)`` / ``("missing", None)`` / ``("unreadable", reason)``."""
    if not path.is_file():
        return "missing", None
    try:
        return "ok", json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return "unreadable", f"{type(exc).__name__}: {exc}"


def _read_jsonl(path: Path) -> Tuple[str, List[Dict[str, Any]]]:
    if not path.is_file():
        return "missing", []
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return "unreadable", []
    out: List[Dict[str, Any]] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            out.append(obj)
    return "ok", out


def _plugin_root() -> Path:
    env = os.environ.get("CLAUDE_PLUGIN_ROOT", "").strip()
    if env and (Path(env) / "services").is_dir():
        return Path(env)
    return Path(__file__).resolve().parents[2]


def _load_by_path(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_timings() -> Any:
    return _load_by_path("ct6_homepage_timings", _TIMINGS_PATH)


def _load_freshness() -> Any:
    """Lazy, in-function load of ``services/knowledge_server/freshness.py``.

    Deliberately NOT a module-level import: the freshness engine lives in the
    `services/` tier and is loaded only when the Maps panel needs a verdict
    (the same lazy form freshness.py itself uses to reach
    `hooks/lineage_graph.py`). Raises ``ImportError`` when the file is not
    where the plugin layout puts it -- the caller turns that into an honest
    ``unknowable`` verdict with this reason."""
    path = _plugin_root() / "services" / "knowledge_server" / "freshness.py"
    if not path.is_file():
        raise ImportError(f"freshness engine not found at {path}")
    return _load_by_path("ct6_ks_freshness", path)


def parse_frontmatter(text: str) -> Tuple[Dict[str, str], str]:
    """Flat ``key: value`` frontmatter (block scalars folded to their first
    line) and the body. No frontmatter -> ``({}, text)``."""
    if not text.startswith("---"):
        return {}, text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, text
    fm: Dict[str, str] = {}
    for raw in parts[1].splitlines():
        if not raw or raw[0] in " \t#":
            continue
        key, sep, value = raw.partition(":")
        if not sep or not key.strip():
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        fm[key.strip()] = value
    return fm, parts[2]


def _stamp_of(fm: Dict[str, str]) -> Optional[str]:
    for key in STAMP_KEYS:
        if fm.get(key):
            return fm[key]
    for key, value in fm.items():
        if key.startswith("last_") and value:
            return value
    return None


def _headings(body: str, limit: int = MAX_HEADINGS) -> List[str]:
    out: List[str] = []
    for line in body.splitlines():
        if line.startswith("## "):
            out.append(line[3:].strip())
            if len(out) >= limit:
                break
    return out


def is_sensitive_key(key: str) -> bool:
    lowered = key.lower()
    return any(marker in lowered for marker in SENSITIVE_KEY_MARKERS)


def _is_set(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, dict)):
        return len(value) > 0
    return True


def _flatten(obj: Any, prefix: str = "") -> List[Tuple[str, Any]]:
    """Leaf (dotted-key, value) pairs; lists are leaves."""
    if not isinstance(obj, dict):
        return [(prefix or "(root)", obj)]
    out: List[Tuple[str, Any]] = []
    for key in sorted(obj.keys(), key=str):
        dotted = f"{prefix}.{key}" if prefix else str(key)
        value = obj[key]
        if isinstance(value, dict) and value:
            out.extend(_flatten(value, dotted))
        else:
            out.append((dotted, value))
    return out


def _walk_dirs(root: Path, max_depth: int = MAX_WALK_DEPTH):
    """Bounded, sorted directory walk skipping the usual noise."""
    root = root.resolve()
    for current, dirs, files in os.walk(root):
        rel_depth = len(Path(current).resolve().relative_to(root).parts)
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS and not d.startswith("."))
        if rel_depth >= max_depth:
            dirs[:] = []
        yield Path(current), sorted(files)


# --------------------------------------------------------------------------- #
# source discovery
# --------------------------------------------------------------------------- #

def _intake(workspace: Path) -> Tuple[str, Dict[str, Any]]:
    state, data = _read_json(workspace / INTAKE_STATE)
    return state, (data if isinstance(data, dict) else {})


def _codebase_roots(workspace: Path, intake: Dict[str, Any]) -> List[Tuple[str, Path]]:
    """``(name, root)`` for the workspace plus every codebase intake names.

    When intake names a codebase that IS the workspace (``path: "."``), the
    workspace entry takes that name, so ``map_invalidated`` entries and the
    page's labels use the name the run uses."""
    project = intake.get("project") if isinstance(intake.get("project"), str) else None
    roots: List[Tuple[str, Path]] = [(project or workspace.name or "workspace", workspace)]
    seen = {workspace.resolve()}
    candidates: List[Tuple[str, Any]] = []
    for value in (intake.get("codebases"), intake.get("codebase_paths")):
        if isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    candidates.append((str(item.get("name") or ""), item.get("path")))
                elif isinstance(item, str):
                    candidates.append(("", item))
    if isinstance(intake.get("codebase_path"), str):
        candidates.append(("", intake["codebase_path"]))
    for name, raw in candidates:
        if not isinstance(raw, str) or not raw.strip():
            continue
        root = Path(raw)
        if not root.is_absolute():
            root = workspace / root
        if not root.is_dir():
            continue
        resolved = root.resolve()
        if resolved in seen:
            if resolved == workspace.resolve() and name:
                roots[0] = (name, workspace)
            continue
        seen.add(resolved)
        roots.append((name or root.name, root))
    return roots


def _find_files(workspace: Path, filename: str) -> List[Path]:
    found: List[Path] = []
    for current, files in _walk_dirs(workspace):
        if filename in files:
            found.append(current / filename)
    state_dir = workspace / STATE_DIR
    if state_dir.is_dir():
        for current, files in _walk_dirs(state_dir, max_depth=2):
            if filename in files:
                found.append(current / filename)
    out: List[Path] = []
    seen: set = set()
    for p in found:
        key = p.resolve()
        if key not in seen:
            seen.add(key)
            out.append(p)
    return out


def discover_sources(workspace: Path) -> List[Dict[str, Any]]:
    """Every source the page reads: ``{"name", "kind", "path", "abs", "state"}``
    in a stable order. Missing expected sources are listed with
    ``state: "missing"`` so the stamp shows what was looked for."""
    workspace = Path(workspace)
    _, intake = _intake(workspace)
    sources: List[Dict[str, Any]] = []

    def add(name: str, kind: str, path: Path, expected: bool = True) -> None:
        state = "ok" if path.is_file() else "missing"
        if state == "missing" and not expected:
            return
        sources.append({"name": name, "kind": kind, "path": _rel(path, workspace),
                        "abs": path, "state": state})

    add("intake-state", "state", workspace / INTAKE_STATE)
    for cfg in sorted(workspace.glob(".architect-team-*.json")):
        if cfg.is_file():
            add(cfg.name, "config", cfg)
    add("git-identity", "state", workspace / GIT_IDENTITY)
    add("discipline-registry", "state", workspace / DISCIPLINE_REGISTRY)
    add("decisions", "ledger", workspace / DECISIONS)
    for name, root in _codebase_roots(workspace, intake):
        for map_name in MAP_NAMES:
            add(f"{name}:{map_name}", "map", root / "docs" / map_name)
    for graph in _find_files(workspace, LINEAGE_GRAPH):
        add(f"lineage-graph:{_rel(graph, workspace)}", "graph", graph)
    add("test-index", "tests", workspace / TEST_INDEX)
    selections = sorted((workspace / STATE_DIR).glob(TEST_SELECTION_GLOB)) \
        if (workspace / STATE_DIR).is_dir() else []
    if selections:
        add("test-selection", "tests", selections[-1])
    else:
        sources.append({"name": "test-selection", "kind": "tests",
                        "path": f"{STATE_DIR}/{TEST_SELECTION_GLOB}",
                        "abs": workspace / STATE_DIR / TEST_SELECTION_GLOB, "state": "missing"})
    for manifest in _find_files(workspace, SUITE_MANIFEST):
        add(f"suite-manifest:{_rel(manifest, workspace)}", "tests", manifest)
    metrics_dir = workspace / RUN_METRICS_DIR
    if metrics_dir.is_dir():
        for m in sorted(metrics_dir.glob("*.json")):
            add(f"run-metrics:{m.stem}", "metrics", m)
    else:
        sources.append({"name": "run-metrics", "kind": "metrics", "path": RUN_METRICS_DIR,
                        "abs": metrics_dir, "state": "missing"})
    add("timings", "ledger", workspace / TIMINGS)
    return sources


def source_hashes(workspace: Path) -> Dict[str, str]:
    """``{relative path: sha256}`` for every PRESENT source."""
    out: Dict[str, str] = {}
    for src in discover_sources(Path(workspace)):
        if src["state"] != "ok":
            continue
        digest = _sha256(src["abs"])
        if digest:
            out[src["path"]] = digest
    return dict(sorted(out.items()))


# --------------------------------------------------------------------------- #
# build state + staleness
# --------------------------------------------------------------------------- #

def homepage_dir(workspace: Path) -> Path:
    return Path(workspace) / HOMEPAGE_RELATIVE_DIR


def page_path(workspace: Path) -> Path:
    return homepage_dir(workspace) / PAGE_NAME


def build_state_path(workspace: Path) -> Path:
    return homepage_dir(workspace) / BUILD_STATE_NAME


def read_build_state(workspace: Path) -> Optional[Dict[str, Any]]:
    state, data = _read_json(build_state_path(workspace))
    return data if state == "ok" and isinstance(data, dict) else None


def is_stale(workspace: Path) -> Dict[str, Any]:
    """Compare the previous build's recorded hashes with the sources now.

    Returns ``{"stale", "built_at", "page_exists", "changed": [...], "since",
    "reason"}``. ``since`` is the earliest mtime among the changed sources that
    still exist (the moment the page stopped being current). Never built ->
    stale with reason ``never-built``."""
    workspace = Path(workspace)
    prev = read_build_state(workspace)
    page_exists = page_path(workspace).is_file()
    current = source_hashes(workspace)
    if prev is None or not isinstance(prev.get("hashes"), dict):
        return {"stale": True, "built_at": None, "page_exists": page_exists,
                "changed": sorted(current.keys()), "since": None,
                "reason": "never-built" if not page_exists else "no-build-state"}
    recorded: Dict[str, str] = {k: v for k, v in prev["hashes"].items() if isinstance(v, str)}
    changed = sorted(set(k for k in set(recorded) | set(current)
                         if recorded.get(k) != current.get(k)))
    since: Optional[str] = None
    for rel in changed:
        candidate = workspace / rel
        stamp = _iso_from_mtime(candidate) if candidate.is_file() else None
        if stamp and (since is None or stamp < since):
            since = stamp
    stale = bool(changed) or not page_exists
    reason = "sources-changed" if changed else ("page-missing" if not page_exists else "current")
    return {"stale": stale, "built_at": prev.get("built_at"), "page_exists": page_exists,
            "changed": changed, "since": since, "reason": reason}


# --------------------------------------------------------------------------- #
# collection
# --------------------------------------------------------------------------- #

def _collect_structure(workspace: Path, intake: Dict[str, Any],
                       roots: List[Tuple[str, Path]]) -> Dict[str, Any]:
    top: List[str] = []
    try:
        for entry in sorted(workspace.iterdir(), key=lambda p: p.name.lower()):
            if entry.name.startswith(".") or entry.name in SKIP_DIRS:
                continue
            top.append(entry.name + ("/" if entry.is_dir() else ""))
    except OSError:
        pass
    codebase_map: Dict[str, Any] = {"state": "missing", "path": _rel(workspace / "docs" / "CODEBASE_MAP.md", workspace)}
    for name, root in roots:
        candidate = root / "docs" / "CODEBASE_MAP.md"
        if candidate.is_file():
            try:
                fm, body = parse_frontmatter(candidate.read_text(encoding="utf-8"))
            except OSError:
                codebase_map = {"state": "unreadable", "path": _rel(candidate, workspace)}
                break
            codebase_map = {"state": "ok", "path": _rel(candidate, workspace),
                            "codebase": name, "last_mapped": _stamp_of(fm),
                            "headings": _headings(body)}
            break
    return {"top_level": top[:40], "codebase_map": codebase_map,
            "codebases": [{"name": n, "path": _rel(r, workspace)} for n, r in roots]}


def summarize_config(path: Path) -> Dict[str, Any]:
    """Keys + set/unset for one ``.architect-team-*.json``; publish extras."""
    state, data = _read_json(path)
    out: Dict[str, Any] = {"file": path.name, "state": state, "keys": [], "publish": None}
    if state != "ok":
        if state == "unreadable":
            out["reason"] = data
        return out
    for dotted, value in _flatten(data):
        out["keys"].append({"key": dotted, "status": "set" if _is_set(value) else "unset",
                            "sensitive": is_sensitive_key(dotted)})
    if path.name == PUBLISH_CONFIG and isinstance(data, dict):
        publish: Dict[str, Optional[str]] = {}
        for field in ("mode", "adapter", "slug"):
            value = data.get(field)
            publish[field] = value if isinstance(value, str) and value.strip() else None
        out["publish"] = publish
    return out


def _model_distribution(agents_dir: Optional[Path]) -> Dict[str, Any]:
    if agents_dir is None or not agents_dir.is_dir():
        return {"state": "unavailable", "agents_dir": str(agents_dir) if agents_dir else None,
                "distribution": {}, "agents": 0}
    counts: Dict[str, int] = {}
    total = 0
    for agent in sorted(agents_dir.glob("*.md")):
        try:
            fm, _ = parse_frontmatter(agent.read_text(encoding="utf-8"))
        except OSError:
            continue
        total += 1
        model = fm.get("model") or "(unspecified)"
        counts[model] = counts.get(model, 0) + 1
    return {"state": "ok", "agents_dir": str(agents_dir), "agents": total,
            "distribution": dict(sorted(counts.items()))}


def _collect_settings(workspace: Path, intake: Dict[str, Any],
                      agents_dir: Optional[Path]) -> Dict[str, Any]:
    configs = [summarize_config(p) for p in sorted(workspace.glob(".architect-team-*.json")) if p.is_file()]
    id_state, id_data = _read_json(workspace / GIT_IDENTITY)
    identity: Dict[str, Any] = {"state": id_state, "name": None, "source": None}
    if id_state == "ok" and isinstance(id_data, dict):
        identity["name"] = id_data.get("name") if isinstance(id_data.get("name"), str) else None
        identity["source"] = id_data.get("source") if isinstance(id_data.get("source"), str) else None
    reg_state, reg_data = _read_json(workspace / DISCIPLINE_REGISTRY)
    registry: Dict[str, Any] = {"state": reg_state, "disciplines": []}
    if reg_state == "ok" and isinstance(reg_data, dict):
        entries = reg_data.get("disciplines") if isinstance(reg_data.get("disciplines"), dict) else {}
        for name in sorted(entries.keys()):
            item = entries[name] if isinstance(entries[name], dict) else {}
            registry["disciplines"].append({
                "name": name,
                "status": str(item.get("status") or item.get("state") or "recorded"),
                "last_applied": item.get("last_applied") or item.get("applied_at"),
            })
        registry["updated_at"] = reg_data.get("updated_at")
    return {
        "configs": configs,
        "git_identity": identity,
        "models": _model_distribution(agents_dir),
        "intake_model": intake.get("model") if isinstance(intake.get("model"), str) else None,
        "dispatch_mode": intake.get("dispatch_mode"),
        "appearance_mode": intake.get("appearance_mode"),
        "phase": intake.get("phase"),
        "run_id": intake.get("run_id"),
        "lane": intake.get("lane"),
        "discipline_registry": registry,
    }


def _collect_decisions(workspace: Path) -> Dict[str, Any]:
    state, rows = _read_jsonl(workspace / DECISIONS)
    rows = [r for r in rows if isinstance(r.get("kind"), str)]
    counts: Dict[str, int] = {}
    for r in rows:
        counts[r["kind"]] = counts.get(r["kind"], 0) + 1
    return {"state": state, "path": DECISIONS, "count": len(rows),
            "by_kind": dict(sorted(counts.items())),
            "entries": list(reversed(rows))[:MAX_DECISIONS]}


def _load_graph(path: Path) -> Tuple[str, Optional[Dict[str, Any]]]:
    state, data = _read_json(path)
    if state == "ok" and not isinstance(data, dict):
        return "unreadable", None
    return state, (data if state == "ok" else None)


def _graph_summary(graph: Dict[str, Any]) -> Dict[str, Any]:
    nodes = graph.get("nodes") if isinstance(graph.get("nodes"), list) else []
    edges = graph.get("edges") if isinstance(graph.get("edges"), list) else []
    kinds: Dict[str, int] = {}
    for n in nodes:
        if isinstance(n, dict):
            k = str(n.get("kind") or "(unkinded)")
            kinds[k] = kinds.get(k, 0) + 1
    executed = sum(1 for e in edges if isinstance(e, dict) and e.get("executed") is True)
    return {"schema_version": graph.get("schema_version"), "nodes": len(nodes),
            "edges": len(edges), "node_kinds": dict(sorted(kinds.items())),
            "executed_edges": executed,
            "executed_ratio": round(executed / len(edges), 3) if edges else None}


def _freshness_for(fr: Any, graph: Optional[Dict[str, Any]], stamp: Optional[str],
                   changed: Optional[List[str]], own_path: str,
                   invalidated: List[str]) -> Dict[str, Any]:
    """One map's verdict through the freshness engine."""
    if invalidated:
        return fr.map_freshness(graph or {}, changed_paths=changed, stamp=stamp,
                                map_invalidated=invalidated)
    if not stamp:
        return fr.envelope(fr.UNKNOWABLE, ["no stamp recorded in the map's frontmatter"])
    if changed is None:
        return fr.envelope(fr.UNKNOWABLE, [
            "changed paths since the stamp could not be determined (git unavailable)",
            f"stamp: {stamp}"])
    relevant = [p for p in changed if p != own_path and not p.startswith(STATE_DIR + "/")]
    if graph is not None:
        return fr.map_freshness(graph, changed_paths=relevant, stamp=stamp)
    if relevant:
        return fr.envelope(fr.STALE, [
            f"{len(relevant)} path(s) committed since the stamp and the map was not re-derived",
            f"stamp: {stamp}"])
    return fr.envelope(fr.CURRENT, [f"no path committed since the stamp", f"stamp: {stamp}"])


def _collect_maps(workspace: Path, intake: Dict[str, Any], roots: List[Tuple[str, Path]],
                  changed_paths_fn: Optional[Callable[[Any, Any], Optional[List[str]]]]) -> Dict[str, Any]:
    engine: Dict[str, Any] = {"available": False, "reason": None}
    fr: Any = None
    try:
        fr = _load_freshness()
        engine["available"] = True
    except Exception as exc:  # noqa: BLE001 - degrade honestly, never crash the page
        engine["reason"] = f"{type(exc).__name__}: {exc}"
    invalidated_raw = intake.get("map_invalidated")
    invalidated_all = [str(x) for x in invalidated_raw] if isinstance(invalidated_raw, list) else []

    graphs: List[Dict[str, Any]] = []
    graph_data: Optional[Dict[str, Any]] = None
    for gpath in _find_files(workspace, LINEAGE_GRAPH):
        gstate, gdata = _load_graph(gpath)
        entry: Dict[str, Any] = {"path": _rel(gpath, workspace), "state": gstate}
        if gdata is not None:
            entry.update(_graph_summary(gdata))
            if graph_data is None:
                graph_data = gdata
        graphs.append(entry)

    entries: List[Dict[str, Any]] = []
    changed_cache: Dict[Tuple[str, str], Optional[List[str]]] = {}
    for name, root in roots:
        inv = [x for x in invalidated_all if x in (name, _rel(root, workspace), str(root))]
        for map_name in MAP_NAMES:
            path = root / "docs" / map_name
            rel = _rel(path, workspace)
            entry: Dict[str, Any] = {"name": map_name, "codebase": name, "path": rel,
                                     "state": "missing", "stamp": None, "confirmed": None,
                                     "freshness": {"verdict": VERDICT_UNKNOWABLE, "basis": ["map file missing"]}}
            if path.is_file():
                try:
                    fm, _ = parse_frontmatter(path.read_text(encoding="utf-8"))
                    entry["state"] = "ok"
                    entry["stamp"] = _stamp_of(fm)
                    entry["confirmed"] = fm.get("confirmed")
                except OSError as exc:
                    entry["state"] = "unreadable"
                    entry["freshness"] = {"verdict": VERDICT_UNKNOWABLE,
                                          "basis": [f"map unreadable: {type(exc).__name__}"]}
            if entry["state"] == "ok":
                if fr is None:
                    entry["freshness"] = {"verdict": VERDICT_UNKNOWABLE,
                                          "basis": [f"freshness engine unavailable: {engine['reason']}"]}
                else:
                    try:
                        key = (str(root), str(entry["stamp"]))
                        if key not in changed_cache:
                            if changed_paths_fn is not None:
                                changed_cache[key] = changed_paths_fn(entry["stamp"], root)
                            else:
                                changed_cache[key] = fr.git_changed_paths(entry["stamp"], root)
                        graph_for = graph_data if map_name == "ENDPOINT_TRACE_MAP.md" else None
                        own = rel if root.resolve() == workspace.resolve() else f"docs/{map_name}"
                        entry["freshness"] = _freshness_for(fr, graph_for, entry["stamp"],
                                                            changed_cache[key], own, inv)
                    except Exception as exc:  # noqa: BLE001
                        entry["freshness"] = {"verdict": VERDICT_UNKNOWABLE,
                                              "basis": [f"freshness computation failed: {type(exc).__name__}: {exc}"]}
            entries.append(entry)
    present = [e for e in entries if e["state"] == "ok"]
    return {"state": "ok" if present else "missing", "engine": engine, "entries": entries,
            "graphs": graphs, "verdicts": {v: sum(1 for e in present if e["freshness"].get("verdict") == v)
                                          for v in (VERDICT_CURRENT, VERDICT_STALE, VERDICT_UNKNOWABLE)}}


def _collect_functions(maps: Dict[str, Any]) -> Dict[str, Any]:
    graphs = maps.get("graphs") or []
    ok = [g for g in graphs if g.get("state") == "ok"]
    return {"state": "ok" if ok else "missing", "graphs": graphs,
            "nodes": sum(g.get("nodes", 0) for g in ok), "edges": sum(g.get("edges", 0) for g in ok),
            "executed_edges": sum(g.get("executed_edges", 0) for g in ok)}


def _tests_container(data: Any) -> List[Tuple[str, Dict[str, Any]]]:
    if isinstance(data, dict):
        inner = data.get("tests")
        if isinstance(inner, dict):
            return [(str(k), v) for k, v in inner.items() if isinstance(v, dict)]
        if isinstance(inner, list):
            return [(str(v.get("id") or v.get("test_id") or i), v) for i, v in enumerate(inner) if isinstance(v, dict)]
        return []
    if isinstance(data, list):
        return [(str(v.get("id") or v.get("test_id") or i), v) for i, v in enumerate(data) if isinstance(v, dict)]
    return []


def _collect_tests(workspace: Path) -> Dict[str, Any]:
    idx_state, idx_data = _read_json(workspace / TEST_INDEX)
    index: Dict[str, Any] = {"state": idx_state, "path": TEST_INDEX, "count": 0,
                             "by_kind": {}, "by_trust": {}, "pins": [], "built_at": None}
    if idx_state == "ok":
        tests = _tests_container(idx_data)
        index["count"] = len(tests)
        for tid, t in tests:
            kind = str(t.get("kind") or "(unkinded)")
            trust = str(t.get("trust") or "(untrusted)")
            index["by_kind"][kind] = index["by_kind"].get(kind, 0) + 1
            index["by_trust"][trust] = index["by_trust"].get(trust, 0) + 1
            if t.get("always_run") is True:
                index["pins"].append(tid)
        index["by_kind"] = dict(sorted(index["by_kind"].items()))
        index["by_trust"] = dict(sorted(index["by_trust"].items()))
        if isinstance(idx_data, dict):
            index["built_at"] = idx_data.get("built_at") or idx_data.get("at")

    selection: Dict[str, Any] = {"state": "missing", "path": None, "selected": None,
                                 "reasons": [], "baseline_sha": None, "at": None}
    state_dir = workspace / STATE_DIR
    candidates = sorted(state_dir.glob(TEST_SELECTION_GLOB)) if state_dir.is_dir() else []
    if candidates:
        sel_path = candidates[-1]
        sel_state, sel_data = _read_json(sel_path)
        selection["state"] = sel_state
        selection["path"] = _rel(sel_path, workspace)
        if sel_state == "ok" and isinstance(sel_data, dict):
            selected = sel_data.get("selected")
            selection["selected"] = len(selected) if isinstance(selected, (list, dict)) else None
            selection["baseline_sha"] = sel_data.get("baseline_sha")
            selection["at"] = sel_data.get("at") or sel_data.get("built_at") or sel_data.get("selected_at")
            reasons = sel_data.get("reasons")
            if isinstance(reasons, dict):
                selection["reasons"] = [f"{k}: {v}" for k, v in list(reasons.items())[:12]]
            elif isinstance(reasons, list):
                selection["reasons"] = [str(r) for r in reasons[:12]]

    manifests: List[Dict[str, Any]] = []
    for mpath in _find_files(workspace, SUITE_MANIFEST):
        m_state, m_data = _read_json(mpath)
        entry: Dict[str, Any] = {"path": _rel(mpath, workspace), "state": m_state, "tests": 0,
                                 "by_kind": {}, "by_persona": {}, "by_safety": {},
                                 "prod_exceptions": 0, "personas": [], "last_built": None}
        if m_state == "ok" and isinstance(m_data, dict):
            tests = m_data.get("tests") if isinstance(m_data.get("tests"), list) else []
            entry["tests"] = len(tests)
            for t in tests:
                if not isinstance(t, dict):
                    continue
                for field, bucket in (("kind", "by_kind"), ("persona", "by_persona"), ("safety", "by_safety")):
                    value = str(t.get(field) or "(unset)")
                    entry[bucket][value] = entry[bucket].get(value, 0) + 1
            for bucket in ("by_kind", "by_persona", "by_safety"):
                entry[bucket] = dict(sorted(entry[bucket].items()))
            exc = m_data.get("prod_exceptions")
            entry["prod_exceptions"] = len(exc) if isinstance(exc, list) else 0
            personas = m_data.get("personas")
            entry["personas"] = [str(p) for p in personas] if isinstance(personas, list) else []
            entry["last_built"] = m_data.get("last_built")
        manifests.append(entry)
    state = "ok" if (idx_state == "ok" or selection["state"] == "ok"
                     or any(m["state"] == "ok" for m in manifests)) else "missing"
    return {"state": state, "index": index, "selection": selection, "manifests": manifests}


def _collect_runs(workspace: Path, timing_records: List[Dict[str, Any]]) -> Dict[str, Any]:
    metrics: Dict[str, Dict[str, Any]] = {}
    metrics_dir = workspace / RUN_METRICS_DIR
    metrics_state = "ok" if metrics_dir.is_dir() else "missing"
    if metrics_dir.is_dir():
        for m in sorted(metrics_dir.glob("*.json")):
            state, data = _read_json(m)
            if state == "ok" and isinstance(data, dict):
                metrics[m.stem] = data
    runs: Dict[str, Dict[str, Any]] = {}
    for rec in timing_records:
        run_id = rec.get("run_id")
        if not isinstance(run_id, str) or not run_id:
            continue
        row = runs.setdefault(run_id, {"run_id": run_id, "lane": None, "started_at": None,
                                       "ended_at": None, "duration_s": None, "outcome": None,
                                       "last_heartbeat": None, "intervals": 0})
        row["intervals"] += 1
        if rec.get("lane") and not row["lane"]:
            row["lane"] = rec["lane"]
        if rec.get("kind") == "run":
            if rec.get("outcome") == "heartbeat":
                row["last_heartbeat"] = rec.get("ended_at")
            else:
                row["started_at"] = rec.get("started_at")
                row["ended_at"] = rec.get("ended_at")
                row["duration_s"] = rec.get("duration_s")
                row["outcome"] = rec.get("outcome")
        started = rec.get("started_at")
        if isinstance(started, str) and (row["started_at"] is None or started < row["started_at"]):
            row["started_at"] = started
    for run_id, data in metrics.items():
        row = runs.setdefault(run_id, {"run_id": run_id, "lane": None, "started_at": None,
                                       "ended_at": None, "duration_s": None, "outcome": None,
                                       "last_heartbeat": None, "intervals": 0})
        row["metrics"] = {k: data.get(k) for k in ("dev_loop_iterations", "first_pass_fix",
                                                   "oscillation_count", "fix_regression_count",
                                                   "fe_api_verdict", "wrong_layer") if k in data}
    ordered = sorted(runs.values(), key=lambda r: (r.get("started_at") or "", r["run_id"]), reverse=True)
    return {"state": "ok" if ordered else "missing", "metrics_state": metrics_state,
            "metrics_files": len(metrics), "runs": ordered[:MAX_RUNS], "total": len(ordered)}


def collect(workspace: Path, *, agents_dir: Optional[Path] = None,
            changed_paths_fn: Optional[Callable[[Any, Any], Optional[List[str]]]] = None,
            now: Optional[str] = None) -> Dict[str, Any]:
    """Everything the page renders, as data. Pure given the filesystem."""
    workspace = Path(workspace)
    intake_state, intake = _intake(workspace)
    roots = _codebase_roots(workspace, intake)
    project = intake.get("project") if isinstance(intake.get("project"), str) and intake.get("project").strip() \
        else (workspace.resolve().name or "project")
    if agents_dir is None:
        candidate = _plugin_root() / "agents"
        agents_dir = candidate if candidate.is_dir() else None
    sources = discover_sources(workspace)
    for src in sources:
        src["sha256"] = _sha256(src["abs"]) if src["state"] == "ok" else None
        src["mtime"] = _iso_from_mtime(src["abs"]) if src["state"] == "ok" else None
    timings_mod = _load_timings()
    t_state, timing_records = _read_jsonl(workspace / TIMINGS)
    maps = _collect_maps(workspace, intake, roots, changed_paths_fn)
    perf_records = [r for r in timing_records if isinstance(r.get("kind"), str)]
    performance = {
        "state": t_state if perf_records or t_state != "ok" else "empty",
        "path": TIMINGS,
        "runs_by_lane": timings_mod.stats(perf_records, group_by=("lane",)),
        "phases": timings_mod.stats(perf_records, group_by=("lane", "phase")),
        "agents": timings_mod.stats(perf_records, group_by=("lane", "agent")),
    }
    model = {
        "project": project,
        "workspace": str(workspace),
        "built_at": now or _utc_now_iso(),
        "intake_state": intake_state,
        "intake": intake,
        "sources": [{k: v for k, v in s.items() if k != "abs"} for s in sources],
        "stale": is_stale(workspace),
        "structure": _collect_structure(workspace, intake, roots),
        "settings": _collect_settings(workspace, intake, agents_dir),
        "decisions": _collect_decisions(workspace),
        "maps": maps,
        "functions": _collect_functions(maps),
        "tests": _collect_tests(workspace),
        "performance": performance,
        "runs": _collect_runs(workspace, perf_records),
    }
    return model


# --------------------------------------------------------------------------- #
# rendering
# --------------------------------------------------------------------------- #

def _h(value: Any) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def _fmt_dur(seconds: Any) -> str:
    if isinstance(seconds, bool) or not isinstance(seconds, (int, float)):
        return "-"
    total = int(round(seconds))
    if total < 60:
        return f"{total}s"
    minutes, secs = divmod(total, 60)
    if minutes < 60:
        return f"{minutes}m {secs:02d}s"
    hours, minutes = divmod(minutes, 60)
    return f"{hours}h {minutes:02d}m"


def _empty(text: str) -> str:
    return f'<p class="empty">{_h(text)}</p>'


def _badge(text: str, tone: str = "neutral") -> str:
    return f'<span class="badge badge-{_h(tone)}">{_h(text)}</span>'


def _state_badge(state: str) -> str:
    tone = {"ok": "ok", "missing": "warn", "unreadable": "bad", "empty": "warn",
            "unavailable": "warn"}.get(state, "neutral")
    return _badge(state, tone)


def _verdict_badge(verdict: str) -> str:
    tone = {VERDICT_CURRENT: "ok", VERDICT_STALE: "bad", VERDICT_UNKNOWABLE: "warn"}.get(verdict, "neutral")
    return _badge(verdict, tone)


def _table(headers: List[str], rows: List[List[str]]) -> str:
    """``rows`` cells are ALREADY-escaped HTML fragments."""
    head = "".join(f"<th>{_h(h)}</th>" for h in headers)
    body = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows)
    return f'<div class="tablewrap"><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>'


def _kv(items: List[Tuple[str, str]]) -> str:
    """``items`` values are already-escaped fragments."""
    return "<dl>" + "".join(f"<dt>{_h(k)}</dt><dd>{v}</dd>" for k, v in items) + "</dl>"


def _panel(pid: str, title: str, inner: str, note: Optional[str] = None) -> str:
    note_html = f'<p class="note">{_h(note)}</p>' if note else ""
    return (f'<section class="panel" id="panel-{pid}" aria-labelledby="h-{pid}">'
            f'<h2 id="h-{pid}">{_h(title)}</h2>{note_html}{inner}</section>')


def _render_stamp(model: Dict[str, Any]) -> str:
    sources = model["sources"]
    present = [s for s in sources if s["state"] == "ok"]
    rows = []
    for s in sources:
        digest = s.get("sha256")
        short = f'<code title="{_h(digest)}">{_h(digest[:12])}</code>' if digest else "-"
        rows.append([_h(s["name"]), f"<code>{_h(s['path'])}</code>", _state_badge(s["state"]),
                     short, _h(s.get("mtime") or "-")])
    stale = model["stale"]
    if stale.get("reason") == "never-built":
        banner_tone, banner = "neutral", "First build: no previous build state to compare against."
    elif stale.get("changed"):
        since = stale.get("since") or "an unknown time"
        banner_tone = "warn"
        banner = (f"Stale since {since}: {len(stale['changed'])} source(s) changed after the previous "
                  f"build at {stale.get('built_at') or 'unknown'} "
                  f"({', '.join(stale['changed'][:6])}{', ...' if len(stale['changed']) > 6 else ''}). "
                  f"This build supersedes it.")
    else:
        banner_tone = "ok"
        banner = f"No source changed since the previous build at {stale.get('built_at') or 'unknown'}."
    return (
        f'<header class="stamp"><h1>{_h(model["project"])} &middot; CT6 Home</h1>'
        f'<p class="meta">built_at <code>{_h(model["built_at"])}</code> &middot; '
        f'{len(present)} of {len(sources)} sources read &middot; workspace <code>{_h(model["workspace"])}</code></p>'
        f'<p class="banner banner-{banner_tone}" id="stale-banner">{_h(banner)}</p>'
        f'<p class="meta">This page is static. Check whether it is still current with '
        f'<code>python scripts/homepage/build.py stale --workspace &lt;workspace&gt; --json</code> '
        f'and rebuild with <code>/architect-team:home --rebuild</code>.</p>'
        f'<details><summary>Sources read ({len(sources)}) with sha256</summary>'
        f'{_table(["source", "path", "state", "sha256", "mtime"], rows)}</details></header>'
    )


def _render_nav() -> str:
    links = "".join(f'<a href="#panel-{p}">{_h(PANEL_TITLES[p])}</a>' for p in PANELS)
    return f'<nav class="toc" aria-label="Panels">{links}<a href="#panel-runs">Runs</a></nav>'


def _render_structure(model: Dict[str, Any]) -> str:
    s = model["structure"]
    cm = s["codebase_map"]
    parts = []
    if s["top_level"]:
        parts.append("<h3>Top level</h3><ul class=\"tree\">" + "".join(f"<li><code>{_h(x)}</code></li>" for x in s["top_level"]) + "</ul>")
    else:
        parts.append(_empty("Top level: nothing listable in the workspace."))
    parts.append("<h3>Codebases</h3>" + _table(["name", "path"], [[_h(c["name"]), f"<code>{_h(c['path'])}</code>"] for c in s["codebases"]]))
    if cm["state"] == "ok":
        heads = cm.get("headings") or []
        parts.append(f"<h3>Layers from CODEBASE_MAP.md {_state_badge('ok')}</h3>"
                     f"<p class=\"meta\">last_mapped <code>{_h(cm.get('last_mapped') or 'not stamped')}</code> &middot; <code>{_h(cm['path'])}</code></p>"
                     + ("<ol>" + "".join(f"<li>{_h(h)}</li>" for h in heads) + "</ol>" if heads else _empty("The map has no H2 sections to outline.")))
    else:
        parts.append(f"<h3>Layers from CODEBASE_MAP.md {_state_badge(cm['state'])}</h3>"
                     + _empty(f"CODEBASE_MAP.md is {cm['state']} at {cm['path']}; Phase -1 (intake-and-mapping) produces it."))
    return _panel("structure", "Structure", "".join(parts))


def _render_settings(model: Dict[str, Any]) -> str:
    st = model["settings"]
    parts = []
    run_items = [
        ("phase", _h(st.get("phase") or "-")), ("lane", _h(st.get("lane") or "-")),
        ("run_id", _h(st.get("run_id") or "-")), ("dispatch_mode", _h(st.get("dispatch_mode") or "-")),
        ("appearance_mode", _h(st.get("appearance_mode") or "-")),
    ]
    parts.append(f"<h3>Run state {_state_badge(model['intake_state'])}</h3>" + _kv(run_items))
    if st["configs"]:
        for cfg in st["configs"]:
            rows = [[f"<code>{_h(k['key'])}</code>", _badge(k["status"], "ok" if k["status"] == "set" else "neutral"),
                     _badge("value never rendered", "warn") if k["sensitive"] else ""] for k in cfg["keys"]]
            extra = ""
            if cfg.get("publish"):
                pub = cfg["publish"]
                extra = _kv([(f, _h(pub.get(f) or "unset")) for f in ("mode", "adapter", "slug")])
            parts.append(f"<h3><code>{_h(cfg['file'])}</code> {_badge('human-owned', 'neutral')} {_state_badge(cfg['state'])}</h3>"
                         + extra + (_table(["key", "status", ""], rows) if rows else _empty("No keys.")))
    else:
        parts.append("<h3>Project configs</h3>" + _empty("No .architect-team-*.json at the project root (notify / deploy / publish are opt-in)."))
    ident = st["git_identity"]
    ident_val = _h(ident.get("name") or "not recorded") + (f" ({_h(ident['source'])})" if ident.get("source") else "")
    models = st["models"]
    model_rows = [[_h(m), _h(n)] for m, n in (models.get("distribution") or {}).items()]
    parts.append("<h3>Identity and models</h3>" + _kv([
        ("commit identity (name only)", f"{ident_val} {_state_badge(ident['state'])}"),
        ("run model (intake-state)", _h(st.get("intake_model") or "-")),
        ("agent model distribution", (_table(["model", "agents"], model_rows) if model_rows
                                      else _empty(f"agents dir {models.get('state')}")) + " " + _state_badge(models["state"])),
    ]))
    reg = st["discipline_registry"]
    if reg["state"] == "ok":
        rows = [[_h(d["name"]), _h(d["status"]), _h(d.get("last_applied") or "-")] for d in reg["disciplines"]]
        parts.append(f"<h3>Discipline registry {_state_badge('ok')}</h3>"
                     + (_table(["discipline", "status", "last applied"], rows) if rows else _empty("Registry present, no disciplines recorded.")))
    else:
        parts.append(f"<h3>Discipline registry {_state_badge(reg['state'])}</h3>"
                     + _empty(f"{DISCIPLINE_REGISTRY} is {reg['state']}; /architect-team:discipline-status writes it."))
    return _panel("settings", "Settings", "".join(parts),
                  "Keys and set / unset only. A value is never rendered, and a key naming a token, secret, key, password, api or auth is flagged.")


def _render_decisions(model: Dict[str, Any]) -> str:
    d = model["decisions"]
    if d["state"] != "ok" or not d["entries"]:
        inner = _empty(f"{d['path']} is {d['state'] if d['state'] != 'ok' else 'empty'}; each deciding phase appends one line "
                       f"(python hooks/decisions_ledger.py add ...).")
        return _panel("decisions", "Decisions", f"{_state_badge(d['state'] if d['state'] != 'ok' else 'empty')}{inner}")
    rows = []
    for e in d["entries"]:
        rejected = e.get("rejected") or []
        rej_html = "<br>".join(f"<b>{_h(r.get('label'))}</b>: {_h(r.get('why') or '-')}" for r in rejected if isinstance(r, dict)) or "-"
        refs = e.get("refs") or []
        refs_html = "<br>".join(f"<code>{_h(r)}</code>" for r in refs) or "-"
        rows.append([_h(e.get("at") or "-"), _h(e.get("phase") or "-"), _badge(e.get("kind") or "other"),
                     _h(e.get("summary") or ""), _h(e.get("chosen") or "-"), rej_html, refs_html])
    counts = _kv([(k, _h(v)) for k, v in d["by_kind"].items()])
    inner = (f"<p class=\"meta\">{d['count']} decision(s) recorded; newest {len(d['entries'])} shown.</p>" + counts
             + _table(["at", "phase", "kind", "summary", "chosen", "rejected (why)", "refs"], rows))
    return _panel("decisions", "Decisions", inner)


def _render_maps(model: Dict[str, Any]) -> str:
    m = model["maps"]
    parts = []
    eng = m["engine"]
    if eng["available"]:
        parts.append(f"<p class=\"meta\">Freshness verdicts from services/knowledge_server/freshness.py {_badge('engine loaded', 'ok')}</p>")
    else:
        parts.append(f"<p class=\"meta\">{_badge('engine unavailable', 'warn')} every verdict is unknowable: {_h(eng.get('reason'))}</p>")
    v = m["verdicts"]
    parts.append(_kv([("current", _h(v.get(VERDICT_CURRENT, 0))), ("stale", _h(v.get(VERDICT_STALE, 0))),
                      ("unknowable", _h(v.get(VERDICT_UNKNOWABLE, 0)))]))
    rows = []
    for e in m["entries"]:
        fresh = e["freshness"]
        basis = "<br>".join(_h(b) for b in (fresh.get("basis") or [])) or "-"
        rows.append([_h(e["codebase"]), f"<a href=\"{_h(e['path'])}\"><code>{_h(e['name'])}</code></a>",
                     _state_badge(e["state"]), _h(e.get("stamp") or "-"), _h(e.get("confirmed") or "-"),
                     _verdict_badge(fresh.get("verdict") or VERDICT_UNKNOWABLE), basis])
    parts.append(_table(["codebase", "map", "state", "stamp", "confirmed", "freshness", "basis"], rows))
    if not any(e["state"] == "ok" for e in m["entries"]):
        parts.append(_empty("No map found under docs/; Phase -1 (intake-and-mapping) derives them."))
    return _panel("maps", "Maps", "".join(parts))


def _render_functions(model: Dict[str, Any]) -> str:
    f = model["functions"]
    if f["state"] != "ok":
        return _panel("functions", "Functions", _state_badge("missing") + _empty(
            "No lineage-graph.json found; endpoint-trace-mapping produces it beside ENDPOINT_TRACE_MAP.md."))
    rows = []
    for g in f["graphs"]:
        kinds = ", ".join(f"{k} {n}" for k, n in (g.get("node_kinds") or {}).items()) or "-"
        ratio = g.get("executed_ratio")
        rows.append([f"<code>{_h(g['path'])}</code>", _state_badge(g["state"]), _h(g.get("nodes", "-")),
                     _h(g.get("edges", "-")), _h(kinds),
                     _h(f"{g.get('executed_edges', 0)} ({ratio:.0%})" if isinstance(ratio, float) else g.get("executed_edges", "-"))])
    inner = (_kv([("nodes", _h(f["nodes"])), ("edges", _h(f["edges"])), ("witnessed (executed) edges", _h(f["executed_edges"]))])
             + _table(["graph", "state", "nodes", "edges", "node kinds", "witnessed edges"], rows))
    return _panel("functions", "Functions", inner, "The lineage graph in summary; stale regions are the Maps panel's ENDPOINT_TRACE_MAP verdict.")


def _render_tests(model: Dict[str, Any]) -> str:
    t = model["tests"]
    parts = []
    idx = t["index"]
    if idx["state"] == "ok":
        parts.append(f"<h3>Test index {_state_badge('ok')}</h3>" + _kv([
            ("tests", _h(idx["count"])), ("built_at", _h(idx.get("built_at") or "-")),
            ("by kind", _h(", ".join(f"{k} {n}" for k, n in idx["by_kind"].items()) or "-")),
            ("by trust", _h(", ".join(f"{k} {n}" for k, n in idx["by_trust"].items()) or "-")),
            ("always-run pins", "<br>".join(f"<code>{_h(p)}</code>" for p in idx["pins"]) or "none"),
        ]))
    else:
        parts.append(f"<h3>Test index {_state_badge(idx['state'])}</h3>"
                     + _empty(f"{idx['path']} is {idx['state']}; the test-index builder writes it. Without it every gate runs the full suite."))
    sel = t["selection"]
    if sel["state"] == "ok":
        parts.append(f"<h3>Last selection {_state_badge('ok')}</h3>" + _kv([
            ("file", f"<code>{_h(sel['path'])}</code>"), ("at", _h(sel.get("at") or "-")),
            ("selected", _h(sel.get("selected") if sel.get("selected") is not None else "-")),
            ("baseline_sha", _h(sel.get("baseline_sha") or "-")),
            ("reasons", "<br>".join(_h(r) for r in sel["reasons"]) or "-"),
        ]))
    else:
        parts.append(f"<h3>Last selection {_state_badge(sel['state'])}</h3>" + _empty("No test-selection-*.json recorded yet."))
    if t["manifests"]:
        for mf in t["manifests"]:
            parts.append(f"<h3>Suite manifest <code>{_h(mf['path'])}</code> {_state_badge(mf['state'])}</h3>" + _kv([
                ("tests", _h(mf["tests"])), ("last_built", _h(mf.get("last_built") or "-")),
                ("personas", _h(", ".join(mf["personas"]) or "-")),
                ("by kind", _h(", ".join(f"{k} {n}" for k, n in mf["by_kind"].items()) or "-")),
                ("by persona", _h(", ".join(f"{k} {n}" for k, n in mf["by_persona"].items()) or "-")),
                ("by safety (trust)", _h(", ".join(f"{k} {n}" for k, n in mf["by_safety"].items()) or "-")),
                ("prod exceptions", _h(mf["prod_exceptions"])),
            ]))
    else:
        parts.append(f"<h3>Suite manifest {_state_badge('missing')}</h3>" + _empty("No suite-manifest.json found; /architect-team:playwright-suite builds it."))
    return _panel("tests", "Tests", "".join(parts))


def _stats_rows(result: Dict[str, Any], fields: List[str]) -> List[List[str]]:
    rows = []
    for g in result.get("groups") or []:
        tr = g.get("trend") or {}
        tr_text = tr.get("direction", "-")
        if tr.get("delta_pct") is not None:
            tr_text = f"{tr_text} ({tr['delta_pct']:+.1f}%)"
        rows.append([_h(g.get("kind")), *[_h(g["key"].get(f) or "-") for f in fields], _h(g.get("n")),
                     _h(_fmt_dur(g.get("median_s"))), _h(_fmt_dur(g.get("p90_s"))), _h(_fmt_dur(g.get("mean_s"))), _h(tr_text)])
    return rows


def _render_performance(model: Dict[str, Any]) -> str:
    p = model["performance"]
    if p["state"] != "ok":
        return _panel("performance", "Performance", _state_badge(p["state"]) + _empty(
            f"{p['path']} is {p['state']}; the timing hooks and the notifier append to it as runs happen."))
    runs = p["runs_by_lane"]
    parts = [f"<p class=\"meta\">{runs['n_usable']} usable interval(s) across {runs['n_runs']} run(s). {_h(runs['note'])}</p>"]
    for title, result, fields in (("Runs by lane", p["runs_by_lane"], ["lane"]),
                                  ("Phases", p["phases"], ["lane", "phase"]),
                                  ("Agents", p["agents"], ["lane", "agent"])):
        kind = {"Runs by lane": "run", "Phases": "phase", "Agents": "agent"}[title]
        filtered = dict(result, groups=[g for g in result["groups"] if g.get("kind") == kind])
        rows = _stats_rows(filtered, fields)
        parts.append(f"<h3>{_h(title)}</h3>" + (_table(["kind", *fields, "n", "median", "p90", "mean", "trend (last 5 runs vs prior)"], rows)
                                                 if rows else _empty(f"No {kind} intervals recorded yet.")))
    return _panel("performance", "Performance", "".join(parts),
                  "Estimates come from python scripts/homepage/timings.py estimate; below five samples the answer is no basis yet.")


def _render_runs(model: Dict[str, Any]) -> str:
    r = model["runs"]
    if r["state"] != "ok":
        inner = _empty("No run recorded yet in the timing log or run-metrics/.")
        return f'<section class="panel" id="panel-runs" aria-labelledby="h-runs"><h2 id="h-runs">Runs</h2>{_state_badge("missing")}{inner}</section>'
    rows = []
    for run in r["runs"]:
        metrics = run.get("metrics") or {}
        mtext = ", ".join(f"{k}={v}" for k, v in metrics.items()) or "-"
        rows.append([f"<code>{_h(run['run_id'])}</code>", _h(run.get("lane") or "-"), _h(run.get("started_at") or "-"),
                     _h(_fmt_dur(run.get("duration_s"))), _h(run.get("outcome") or "-"),
                     _h(run.get("last_heartbeat") or "-"), _h(mtext)])
    inner = (f"<p class=\"meta\">{r['total']} run(s) known; newest {len(r['runs'])} shown; {r['metrics_files']} run-metrics file(s).</p>"
             + _table(["run", "lane", "started", "duration", "outcome", "last heartbeat", "metrics"], rows))
    return f'<section class="panel" id="panel-runs" aria-labelledby="h-runs"><h2 id="h-runs">Runs</h2>{inner}</section>'


_CSS = """
:root{--bg:#f6f6f3;--fg:#1c1c1c;--muted:#5d6166;--panel:#ffffff;--border:#d9d9d3;--accent:#1f5fbf;--ok:#1a7f37;--warn:#9a6700;--bad:#b42318;--code:#eceef1;--badge-fg:#ffffff}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){--bg:#121417;--fg:#e7e7e4;--muted:#9aa0a6;--panel:#1b1f24;--border:#2d333b;--accent:#6ea8fe;--ok:#3fb950;--warn:#d29922;--bad:#f85149;--code:#22272e;--badge-fg:#0b0d10}}
:root[data-theme="dark"]{--bg:#121417;--fg:#e7e7e4;--muted:#9aa0a6;--panel:#1b1f24;--border:#2d333b;--accent:#6ea8fe;--ok:#3fb950;--warn:#d29922;--bad:#f85149;--code:#22272e;--badge-fg:#0b0d10}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,-apple-system,Segoe UI,Roboto,sans-serif}
main{max-width:980px;margin:0 auto;padding:16px}
h1{font-size:1.5rem;margin:0 0 4px}h2{font-size:1.2rem;margin:0 0 8px}h3{font-size:1rem;margin:16px 0 6px}
a{color:var(--accent)}
code{background:var(--code);padding:1px 4px;border-radius:4px;font-size:.92em;word-break:break-all}
.stamp,.panel{background:var(--panel);border:1px solid var(--border);border-radius:8px;padding:16px;margin:0 0 16px}
.meta,.note{color:var(--muted);font-size:.9rem;margin:4px 0}
.empty{color:var(--muted);font-style:italic;border-left:3px solid var(--border);padding-left:10px;margin:8px 0}
.toc{display:flex;flex-wrap:wrap;gap:8px;margin:0 0 16px}
.toc a{padding:4px 10px;border:1px solid var(--border);border-radius:999px;text-decoration:none;background:var(--panel)}
.banner{padding:8px 12px;border-radius:6px;border:1px solid var(--border);margin:8px 0}
.banner-ok{border-color:var(--ok)}.banner-warn{border-color:var(--warn)}.banner-neutral{border-color:var(--border)}
.badge{display:inline-block;padding:0 8px;border-radius:999px;font-size:.78rem;line-height:1.6;color:var(--badge-fg);background:var(--muted);vertical-align:middle}
.badge-ok{background:var(--ok)}.badge-warn{background:var(--warn)}.badge-bad{background:var(--bad)}.badge-neutral{background:var(--muted)}
.tablewrap{overflow-x:auto;margin:6px 0}
table{border-collapse:collapse;width:100%;font-size:.9rem}
th,td{text-align:left;vertical-align:top;padding:6px 8px;border-bottom:1px solid var(--border)}
th{color:var(--muted);font-weight:600}
dl{display:grid;grid-template-columns:minmax(120px,max-content) 1fr;gap:4px 12px;margin:6px 0}
dt{color:var(--muted)}dd{margin:0;min-width:0;overflow-wrap:anywhere}
ul.tree{columns:2;column-gap:24px;margin:6px 0;padding-left:20px}
@media (max-width:480px){main{padding:12px}dl{grid-template-columns:1fr}dt{margin-top:6px}ul.tree{columns:1}}
"""


def render(model: Dict[str, Any]) -> str:
    """The complete static page for ``model`` (see :func:`collect`)."""
    body = "".join([
        _render_stamp(model), _render_nav(), _render_structure(model), _render_settings(model),
        _render_decisions(model), _render_maps(model), _render_functions(model),
        _render_tests(model), _render_performance(model), _render_runs(model),
    ])
    description = (f"CT6 project homepage for {model['project']}: structure, settings, decisions, "
                   f"map freshness, functions, tests and performance, built {model['built_at']}.")
    return ("<!doctype html>\n<html lang=\"en\">\n<head>\n<meta charset=\"utf-8\">\n"
            "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n"
            f"<title>{_h(model['project'])} &middot; CT6 Home</title>\n"
            f"<meta name=\"description\" content=\"{_h(description)}\">\n"
            f"<style>{_CSS}</style>\n</head>\n<body>\n<main>\n{body}\n"
            "<footer class=\"meta\">Built by scripts/homepage/build.py (CLAUDE TEAM SIX). "
            "Static page: no scripts, no external resources.</footer>\n</main>\n</body>\n</html>\n")


# --------------------------------------------------------------------------- #
# build
# --------------------------------------------------------------------------- #

def build(workspace: Path, out: Optional[Path] = None, *, agents_dir: Optional[Path] = None,
          changed_paths_fn: Optional[Callable[[Any, Any], Optional[List[str]]]] = None,
          now: Optional[str] = None) -> Dict[str, Any]:
    """Collect, render, write the page and the build state. Returns a summary
    ``{"out", "state_path", "built_at", "sources_read", "sources_total",
    "hashes", "stale_before", "panels"}``."""
    workspace = Path(workspace)
    model = collect(workspace, agents_dir=agents_dir, changed_paths_fn=changed_paths_fn, now=now)
    page = render(model)
    target = Path(out) if out is not None else page_path(workspace)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(target.suffix + ".tmp")
    tmp.write_text(page, encoding="utf-8")
    os.replace(tmp, target)
    hashes = {s["path"]: s["sha256"] for s in model["sources"] if s.get("sha256")}
    state = {"schema": BUILD_STATE_SCHEMA, "built_at": model["built_at"], "out": str(target),
             "project": model["project"], "hashes": dict(sorted(hashes.items())),
             "sources_total": len(model["sources"]), "sources_read": len(hashes)}
    state_target = build_state_path(workspace)
    state_target.parent.mkdir(parents=True, exist_ok=True)
    stmp = state_target.with_suffix(state_target.suffix + ".tmp")
    stmp.write_text(json.dumps(state, sort_keys=True, indent=2), encoding="utf-8")
    os.replace(stmp, state_target)
    return {"out": str(target), "state_path": str(state_target), "built_at": model["built_at"],
            "project": model["project"], "sources_read": len(hashes),
            "sources_total": len(model["sources"]), "hashes": state["hashes"],
            "stale_before": model["stale"], "panels": list(PANELS) + ["runs"],
            "map_verdicts": model["maps"]["verdicts"]}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="build.py", description="Build the CT6 project homepage.")
    sub = parser.add_subparsers(dest="command")
    b = sub.add_parser("build", help="build the page (default)")
    b.add_argument("--workspace", required=True)
    b.add_argument("--out")
    b.add_argument("--json", action="store_true")
    s = sub.add_parser("stale", help="is the built page stale?")
    s.add_argument("--workspace", required=True)
    s.add_argument("--json", action="store_true")
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] not in ("build", "stale"):
        argv = ["build"] + argv
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return 2 if exc.code not in (0, None) else 0
    if args.command == "stale":
        result = is_stale(Path(args.workspace))
        if args.json:
            print(json.dumps(result, sort_keys=True, indent=2))
        else:
            print(f"homepage {'STALE' if result['stale'] else 'current'} ({result['reason']})"
                  + (f"; since {result['since']}" if result.get("since") else "")
                  + (f"; changed: {', '.join(result['changed'])}" if result.get("changed") else ""))
        return 0
    try:
        summary = build(Path(args.workspace), Path(args.out) if args.out else None)
    except Exception as exc:  # noqa: BLE001 - the CLI reports, the caller decides
        print(f"homepage build failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 3
    if args.json:
        print(json.dumps(summary, sort_keys=True, indent=2))
    else:
        print(f"homepage built -> {summary['out']} (built_at {summary['built_at']}; "
              f"{summary['sources_read']} of {summary['sources_total']} sources read)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
