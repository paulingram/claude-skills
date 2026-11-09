# -*- coding: utf-8 -*-
"""Deterministic test index + impact-based selector -- the machine under the
test-selection discipline (`skills/common-pipeline-conventions/references/
test-selection.md`).

The problem it closes: every gate re-ran every test. Phase 3 captured "full
test-suite output" per slice, Phase 5 ran the full integration suite and (since
v3.65.0) the ENTIRE dev Playwright project, mini-review-sweep carried the same
whole-suite rule. The ingredients of a selector already existed, unconnected:
`hooks/frontend_impact.py` maps a change set to frontend impact,
`hooks/lineage_graph.py` gives every function a `func://` identity and a
runtime-witness trust gate, `suite-manifest.json` records per Playwright test
its persona / kind / covered elements. This module adds the one missing join:
a TEST INDEX (test -> files / funcs / endpoints / elements / trust), and a
SELECTOR over it.

The index -- ``<workspace>/.architect-team/test-index.json``::

    {"schema": "test-index/v1", "built_at": iso, "workspace_root_rel": ".",
     "sources": {"static": true, "witness": path|null,
                 "lineage_graph": path|null, "suite_manifest": path|null},
     "import_graph": {"<source file>": ["<imported source file>", ...]},
     "tests": [{"id": "tests/test_x.py::test_a" | "<spec file>::<test name>",
                "file": ..., "kind": "unit"|"integration"|"e2e",
                "layer": "backend"|"frontend"|"unknown",
                "files": [...], "funcs": ["func://..."], "endpoints": [...],
                "elements": [...], "duration_s": null|float,
                "always_run": bool,
                "trust": "static"|"runtime-witnessed"|"unknown"}]}

Trust follows the lineage graph's own rule (REQ-DOC-06): a STATIC mapping is a
hypothesis; a RUNTIME-WITNESSED one is evidence; UNKNOWN (a test whose imports
resolve to no repo file) is neither, and an unknown mapping means RUN IT --
the same lesson as the completion lock, where silence is not a finding.

The selector -- ``select(workspace, changed_files, phase)``: changed files ->
the reverse transitive closure over the recorded import graph -> every test
whose ``files`` intersect; plus every ``always_run`` pin (human-owned, read
from `.architect-team-deploy.json`, never lowered by an agent); plus every
test with ``trust: unknown`` or an empty ``files`` list; plus, when the change
set carries frontend files or changed endpoints, the e2e tests whose
endpoints / elements intersect. Phase 8 -- or any phase a human lists in
``tests.full_suite_at`` -- returns EVERYTHING with reason ``full-suite-phase``;
the full suite at Phase 8 is not selectable. The selection is written as
evidence to ``<workspace>/.architect-team/test-selection-<ts>.json``.

HONEST BOUNDARIES (also stated in the reference): the static mapping is an
import graph plus the repo files a module names in a string literal (by-path
loading), so dynamic dispatch (plugins, DI containers, event buses, paths
computed at runtime) is invisible until a witness run covers it; frontend tests map
to endpoints and elements, not to functions, so a frontend-file change without
caller-supplied elements selects every e2e test (coarse, deliberately); the
endpoint scan is a string-literal heuristic over the changed files.

Stdlib-only; no import-time side effects; the cross-tier helpers
(`hooks/lineage_graph.py`, `hooks/frontend_impact.py`, `hooks/deploy_config.py`)
are loaded by file path, the `scripts/` tier's house idiom, so this engine runs
from any working directory without a package install.
"""
from __future__ import annotations

import ast
import datetime as _dt
import fnmatch
import importlib.util
import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple

INDEX_SCHEMA = "test-index/v1"
SELECTION_SCHEMA = "test-selection/v1"
WITNESS_SCHEMA = "test-witness/v1"
STATS_SCHEMA = "test-index-stats/v1"

STATE_DIR = ".architect-team"
INDEX_FILENAME = "test-index.json"
WITNESS_FILENAME = "test-witness.json"
LINEAGE_GRAPH_FILENAME = "lineage-graph.json"
SUITE_MANIFEST_FILENAME = "suite-manifest.json"
SELECTION_PREFIX = "test-selection-"

KINDS = ("unit", "integration", "e2e")
LAYERS = ("backend", "frontend", "unknown")
TRUST_LEVELS = ("static", "runtime-witnessed", "unknown")

#: The phase whose full suite is never selectable, in its normalized form.
FULL_SUITE_PHASE = "8"

REASON_FULL_SUITE = "full-suite-phase"
REASON_ALWAYS_RUN = "always_run"
REASON_UNKNOWN_MAPPING = "unknown-mapping"
REASON_FRONTEND_COARSE = "frontend-change-coarse-mapping"

#: Directory names never walked. Mirrors `hooks/discipline_registry.py`'s
#: `_SKIP_DIR_PARTS` plus the usual build / cache / vendor dirs.
SKIP_DIRS = frozenset({
    "node_modules", ".venv", "venv", "env", "__pycache__", ".git", ".hg", ".svn",
    ".architect-team", "site-packages", "dist-packages", ".tox", ".nox",
    ".mypy_cache", ".pytest_cache", ".ruff_cache", "build", "dist",
    ".mempalace", "test-results", "playwright-report",
})

#: Directory names that mark a python file as a TEST file when its basename
#: also matches ``test_*.py``.
TEST_DIR_NAMES = frozenset({"tests", "test"})

#: Extensions of changed files that are scanned for ``/api/...`` literals (a
#: changed route definition or a changed fetch call). Prose files are skipped
#: so a doc that mentions an endpoint does not select its flows.
ENDPOINT_SCAN_EXTENSIONS = frozenset({
    ".py", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".vue", ".svelte",
    ".go", ".rb", ".java", ".kt", ".cs", ".php", ".rs", ".yaml", ".yml", ".json",
})

_ENDPOINT_LITERAL_RE = re.compile(
    r"""["'`](/api/[A-Za-z0-9_\-./:{}$]*)["'`]"""
)

_REPO_ROOT = Path(__file__).resolve().parents[2]
_LOADED: Dict[str, Any] = {}


class GitError(RuntimeError):
    """A git invocation the selector depends on failed; the message carries
    the command and its stderr so the caller can show the operator."""


# --------------------------------------------------------------------------- #
# Cross-tier loading (the house idiom) + small helpers
# --------------------------------------------------------------------------- #

def _load(mod_name: str, rel_path: str) -> Any:
    """Load an in-repo stdlib leaf module by file path (cached).

    `scripts/` and `hooks/` carry no `__init__.py`, so a package import is not
    available from an arbitrary working directory; this is the same
    `spec_from_file_location` idiom `scripts/sql_mining/sql_mining.py` uses.
    """
    cached = _LOADED.get(mod_name)
    if cached is not None:
        return cached
    path = _REPO_ROOT / rel_path
    spec = importlib.util.spec_from_file_location(mod_name, path)
    if spec is None or spec.loader is None:  # pragma: no cover - defensive
        raise ImportError(f"cannot load {mod_name} from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    _LOADED[mod_name] = module
    return module


def _lineage_graph_mod() -> Any:
    return _load("ct6_test_index_lineage_graph", "hooks/lineage_graph.py")


def _frontend_impact_mod() -> Any:
    return _load("ct6_test_index_frontend_impact", "hooks/frontend_impact.py")


def _deploy_config_mod() -> Any:
    return _load("ct6_test_index_deploy_config", "hooks/deploy_config.py")


def _now_iso(now: Optional[_dt.datetime] = None) -> str:
    moment = now or _dt.datetime.now(_dt.timezone.utc)
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")


def _now_compact(now: Optional[_dt.datetime] = None) -> str:
    moment = now or _dt.datetime.now(_dt.timezone.utc)
    return moment.strftime("%Y%m%dT%H%M%SZ")


def _posix(path: Any) -> str:
    """Forward-slash, ``./``-stripped relative path text."""
    text = str(path).replace("\\", "/").strip()
    while text.startswith("./"):
        text = text[2:]
    return text.strip("/") if text not in ("", "/") else text


def _rel(workspace: Path, path: Path) -> str:
    try:
        return _posix(path.resolve().relative_to(workspace.resolve()))
    except ValueError:
        return _posix(path)


def _skipped(parts: Iterable[str]) -> bool:
    return any(part in SKIP_DIRS for part in parts)


def _read_text(path: Path) -> Optional[str]:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def _read_json(path: Optional[Path]) -> Optional[Any]:
    if path is None:
        return None
    text = _read_text(path)
    if text is None:
        return None
    try:
        return json.loads(text)
    except ValueError:
        return None


def _write_json(path: Path, payload: Any) -> None:
    """Atomic write (tmp + replace); ASCII-safe output for a cp1252 console."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n",
                   encoding="utf-8")
    os.replace(tmp, path)


def state_dir(workspace: Any) -> Path:
    return Path(workspace) / STATE_DIR


def index_path(workspace: Any) -> Path:
    return state_dir(workspace) / INDEX_FILENAME


def normalize_phase(phase: Any) -> str:
    """``"Phase 8"`` / ``"phase-8"`` / ``"8"`` -> ``"8"``; ``"B8"`` -> ``"b8"``.

    The deploy config spells phases ``phase-8``; the lanes say ``Phase 8``;
    the CLI takes ``--phase 8``. One normalized form so they compare.
    """
    text = str(phase or "").strip().lower()
    text = re.sub(r"^phase[\s_-]*", "", text)
    return re.sub(r"[\s_-]+", "", text)


# --------------------------------------------------------------------------- #
# Python discovery: test files, test functions, imports
# --------------------------------------------------------------------------- #

def _iter_workspace_files(workspace: Path) -> List[Path]:
    """Every file under the workspace outside :data:`SKIP_DIRS`, sorted."""
    out: List[Path] = []
    for root, dirs, files in os.walk(workspace):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS)
        for name in sorted(files):
            out.append(Path(root) / name)
    return out


def _iter_python_files(workspace: Path) -> List[Path]:
    return [p for p in _iter_workspace_files(workspace) if p.name.endswith(".py")]


class _PathLiterals:
    """Resolve string constants that NAME a repo file -- the by-path loading
    this repo's own tests live on (``load_module(HOOKS / "deploy_config.py")``,
    ``_load("x", "scripts/data_dictionary/data_dictionary.py")``), which no
    import graph can see.

    A constant resolves when it is an exact repo-relative path, or a bare file
    name (with an extension) that is UNIQUE in the workspace, or -- when the
    name is ambiguous -- the one candidate in the referencing file's own
    directory (``Path(__file__).parent / "engine.py"``). Anything else is left
    unresolved: a wrong edge selects the wrong tests silently, a missing edge
    is covered by the unknown-mapping rule, the pins and the Phase 8 full run.
    """

    def __init__(self, rels: Iterable[str]) -> None:
        self.rels: Set[str] = set(rels)
        self.by_basename: Dict[str, List[str]] = {}
        for rel in sorted(self.rels):
            self.by_basename.setdefault(rel.rsplit("/", 1)[-1], []).append(rel)

    def resolve(self, text: str, referrer_rel: str) -> Optional[str]:
        candidate = _posix(text)
        if not candidate or len(candidate) > 300 or candidate == referrer_rel:
            return None
        if candidate in self.rels:
            return candidate
        if "/" in candidate or "." not in candidate or candidate.startswith("."):
            return None
        options = self.by_basename.get(candidate, [])
        if len(options) == 1:
            return options[0] if options[0] != referrer_rel else None
        referrer_dir = referrer_rel.rsplit("/", 1)[0] if "/" in referrer_rel else ""
        same_dir = [o for o in options
                    if (o.rsplit("/", 1)[0] if "/" in o else "") == referrer_dir
                    and o != referrer_rel]
        return same_dir[0] if len(same_dir) == 1 else None

    def files_named_in(self, tree: ast.Module, referrer_rel: str) -> Set[str]:
        found: Set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                hit = self.resolve(node.value, referrer_rel)
                if hit:
                    found.add(hit)
        return found


def _is_test_file(rel: str) -> bool:
    parts = rel.split("/")
    name = parts[-1]
    if not (name.startswith("test_") and name.endswith(".py")):
        return False
    return any(part in TEST_DIR_NAMES for part in parts[:-1])


def _parse(path: Path) -> Optional[ast.Module]:
    text = _read_text(path)
    if text is None:
        return None
    try:
        return ast.parse(text, filename=str(path))
    except (SyntaxError, ValueError):
        return None


def _test_ids(rel: str, tree: ast.Module) -> List[str]:
    """``file::test_fn`` for module-level tests, ``file::TestClass::test_m`` for
    methods of ``Test*`` classes -- the same ids pytest assigns."""
    ids: List[str] = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name.startswith("test"):
                ids.append(f"{rel}::{node.name}")
        elif isinstance(node, ast.ClassDef) and node.name.startswith("Test"):
            for sub in node.body:
                if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)) \
                        and sub.name.startswith("test"):
                    ids.append(f"{rel}::{node.name}::{sub.name}")
    return ids


class _ModuleMap:
    """Dotted module name -> candidate (root, file) pairs over the workspace.

    Every ancestor directory of a python file is a possible ``sys.path`` root
    (``src/pkg/mod.py`` answers to ``src.pkg.mod``, ``pkg.mod`` and ``mod``),
    so one name can have several candidates. Resolution prefers the candidate
    whose root is closest to the importing file -- a bare ``import models``
    from a sibling resolves to the sibling, not to some other ``models.py``.
    """

    def __init__(self, workspace: Path, py_files: Sequence[Path]) -> None:
        self.workspace = workspace
        self.candidates: Dict[str, List[Tuple[str, str]]] = {}
        for path in py_files:
            rel = _rel(workspace, path)
            parts = rel.split("/")
            stem_parts = parts[:-1] + [parts[-1][:-3]]
            if stem_parts[-1] == "__init__":
                stem_parts = stem_parts[:-1]
            for depth in range(len(stem_parts)):
                root = "/".join(parts[:depth]) if depth else ""
                dotted = ".".join(stem_parts[depth:])
                if not dotted:
                    continue
                self.candidates.setdefault(dotted, []).append((root, rel))

    def resolve(self, dotted: str, importer_rel: str) -> Optional[str]:
        options = self.candidates.get(dotted)
        if not options:
            return None
        importer_dir = importer_rel.rsplit("/", 1)[0] if "/" in importer_rel else ""

        def score(option: Tuple[str, str]) -> Tuple[int, int, str]:
            root, rel = option
            shared = 0
            if root and (importer_dir == root or importer_dir.startswith(root + "/")):
                shared = len(root)
            return (-shared, len(root), rel)

        return sorted(options, key=score)[0][1]


def _imports_of(tree: ast.Module) -> List[Tuple[str, int, List[str]]]:
    """``(module, level, names)`` triples for every import statement, module
    scope and nested alike (a test that imports inside the function body still
    exercises that module)."""
    out: List[Tuple[str, int, List[str]]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                out.append((alias.name, 0, []))
        elif isinstance(node, ast.ImportFrom):
            out.append((node.module or "", node.level or 0,
                        [alias.name for alias in node.names]))
    return out


def _resolve_imports(modmap: _ModuleMap, importer_rel: str,
                     imports: Sequence[Tuple[str, int, List[str]]]) -> Set[str]:
    """Repo-relative files an import list reaches. Absolute names try the full
    dotted path, then each prefix (``from a.b import c`` may name a module or a
    symbol). Relative names resolve against the importer's package dir."""
    found: Set[str] = set()
    importer_dir = importer_rel.rsplit("/", 1)[0] if "/" in importer_rel else ""
    for module, level, names in imports:
        if level:
            base = importer_dir
            for _ in range(level - 1):
                base = base.rsplit("/", 1)[0] if "/" in base else ""
            base_dotted = base.replace("/", ".") if base else ""
            targets: List[str] = []
            stem = ".".join(p for p in (base_dotted, module) if p)
            for name in names:
                targets.append(".".join(p for p in (stem, name) if p))
            if stem:
                targets.append(stem)
            for dotted in targets:
                hit = modmap.resolve(dotted, importer_rel) if dotted else None
                if hit and hit != importer_rel:
                    found.add(hit)
            continue
        if not module:
            continue
        # ``from a.b import c``: c may be a submodule (resolve it) or a symbol
        # defined in a.b (then a.b itself is the dependency). Only when no name
        # resolved as a submodule does the module prefix stand in for them.
        submodules = 0
        for name in names:
            hit = modmap.resolve(f"{module}.{name}", importer_rel)
            if hit and hit != importer_rel:
                found.add(hit)
                submodules += 1
        if names and submodules == len(names):
            continue
        parts = module.split(".")
        for cut in range(len(parts), 0, -1):
            hit = modmap.resolve(".".join(parts[:cut]), importer_rel)
            if hit and hit != importer_rel:
                found.add(hit)
                break
    return found


def _package_inits(rel: str, py_rels: Set[str]) -> List[str]:
    """The ``__init__.py`` files of every package enclosing ``rel`` (the ones
    Python executes before the module itself), nearest first. A module depends
    on its own package inits: a change there reaches every importer."""
    out: List[str] = []
    parts = rel.split("/")
    upto = len(parts) - 1
    if parts[-1] == "__init__.py":
        upto -= 1
    for depth in range(upto, 0, -1):
        candidate = "/".join(parts[:depth] + ["__init__.py"])
        if candidate in py_rels and candidate != rel:
            out.append(candidate)
    return out


def _classify_kind(rel: str, test_name: str = "") -> str:
    low = rel.lower()
    parts = set(low.split("/"))
    if "e2e" in parts or "playwright" in low or "/e2e/" in f"/{low}":
        return "e2e"
    if "integration" in low or "integration" in test_name.lower():
        return "integration"
    return "unit"


def discover_python(workspace: Path) -> Tuple[List[Dict[str, Any]], Dict[str, List[str]]]:
    """Static discovery: ``(tests, import_graph)``.

    ``tests`` carries one entry per test function with ``files`` = the test
    file's resolved imports, plus the repo files its string constants NAME
    (:class:`_PathLiterals` -- by-path loading), plus ONE further level of
    each such module's own imports. ``import_graph`` carries every non-test source module's
    resolved imports PLUS its enclosing packages' ``__init__.py`` files (Python
    runs those before the module, so a change there reaches every importer);
    the selector walks it transitively, so the one further level here is a
    readability convenience, not the mapping's reach.
    """
    all_files = _iter_workspace_files(workspace)
    py_files = [p for p in all_files if p.name.endswith(".py")]
    modmap = _ModuleMap(workspace, py_files)
    py_rels = {_rel(workspace, p) for p in py_files}
    literals = _PathLiterals(_rel(workspace, p) for p in all_files)
    import_graph: Dict[str, List[str]] = {}
    test_files: List[Tuple[str, ast.Module]] = []
    for path in py_files:
        rel = _rel(workspace, path)
        tree = _parse(path)
        if tree is None:
            continue
        if _is_test_file(rel):
            test_files.append((rel, tree))
            continue
        deps = _resolve_imports(modmap, rel, _imports_of(tree))
        deps.update(_package_inits(rel, py_rels))
        deps.update(literals.files_named_in(tree, rel))
        import_graph[rel] = sorted(deps)

    tests: List[Dict[str, Any]] = []
    for rel, tree in test_files:
        direct = _resolve_imports(modmap, rel, _imports_of(tree))
        direct.update(literals.files_named_in(tree, rel))
        files = set(direct)
        for dep in direct:
            files.update(import_graph.get(dep, []))
        files.discard(rel)
        for test_id in _test_ids(rel, tree):
            name = test_id.rsplit("::", 1)[-1]
            kind = _classify_kind(rel, name)
            tests.append({
                "id": test_id,
                "file": rel,
                "kind": kind,
                "layer": "unknown" if kind == "e2e" else "backend",
                "files": sorted(files),
                "funcs": [],
                "endpoints": [],
                "elements": [],
                "duration_s": None,
                "always_run": False,
                "trust": "static" if files else "unknown",
            })
    return tests, import_graph


# --------------------------------------------------------------------------- #
# E2E discovery from suite-manifest.json
# --------------------------------------------------------------------------- #

def find_suite_manifest(workspace: Path, e2e_dir: Optional[str] = None) -> Optional[Path]:
    if e2e_dir:
        candidate = workspace / e2e_dir / SUITE_MANIFEST_FILENAME
        return candidate if candidate.is_file() else None
    hits: List[Path] = []
    for root, dirs, files in os.walk(workspace):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS)
        if SUITE_MANIFEST_FILENAME in files:
            hits.append(Path(root) / SUITE_MANIFEST_FILENAME)
    return sorted(hits, key=lambda p: (len(p.parts), str(p)))[0] if hits else None


def endpoints_in_text(text: Optional[str]) -> List[str]:
    """Sorted, de-duplicated ``/api/...`` string literals in ``text``."""
    if not text:
        return []
    found = set()
    for match in _ENDPOINT_LITERAL_RE.finditer(text):
        ep = match.group(1).rstrip("/") or match.group(1)
        found.add(ep)
    return sorted(found)


def discover_e2e(workspace: Path, manifest_path: Path) -> List[Dict[str, Any]]:
    data = _read_json(manifest_path)
    if not isinstance(data, dict):
        return []
    tests: List[Dict[str, Any]] = []
    for entry in data.get("tests") or []:
        if not isinstance(entry, dict):
            continue
        spec_rel = entry.get("file")
        if not isinstance(spec_rel, str) or not spec_rel.strip():
            continue
        spec_rel = _posix(spec_rel)
        names = entry.get("test_names")
        if not isinstance(names, list) or not names:
            names = [spec_rel.rsplit("/", 1)[-1]]
        elements = sorted({e for e in (entry.get("covers_elements") or [])
                           if isinstance(e, str) and e.strip()})
        endpoints = endpoints_in_text(_read_text(workspace / spec_rel))
        for name in names:
            if not isinstance(name, str) or not name.strip():
                continue
            tests.append({
                "id": f"{spec_rel}::{name}",
                "file": spec_rel,
                "kind": "e2e",
                "layer": "frontend",
                "files": [spec_rel],
                "funcs": [],
                "endpoints": endpoints,
                "elements": elements,
                "duration_s": None,
                "always_run": False,
                "trust": "static",
                "persona": entry.get("persona"),
                "safety": entry.get("safety"),
                "manifest_kind": entry.get("kind"),
            })
    return tests


# --------------------------------------------------------------------------- #
# Joins: lineage graph (func:// ids), witness (trust), pins (always_run)
# --------------------------------------------------------------------------- #

def _node_path(node: Dict[str, Any], lg: Any) -> Optional[str]:
    path = node.get("path")
    if isinstance(path, str) and path.strip():
        return _posix(path)
    parsed = lg.parse_func_id(node.get("id"))
    return _posix(parsed["path"]) if parsed else None


def _paths_match(node_path: str, file_rel: str) -> bool:
    if node_path == file_rel:
        return True
    return node_path.endswith("/" + file_rel) or file_rel.endswith("/" + node_path)


def join_lineage(tests: List[Dict[str, Any]], graph: Any) -> int:
    """Attach ``func://`` ids to every test whose ``files`` name a node's
    path. Returns the number of validation errors the graph carried (0 means
    a clean join; a malformed graph joins nothing and is reported, not hidden)."""
    lg = _lineage_graph_mod()
    errors = lg.validate_lineage_graph(graph)
    if errors:
        return len(errors)
    by_path: Dict[str, List[str]] = {}
    for node in graph.get("nodes", []):
        if not isinstance(node, dict) or node.get("kind") != "function":
            continue
        nid = node.get("id")
        if not isinstance(nid, str) or not nid.startswith("func://"):
            continue
        npath = _node_path(node, lg)
        if npath:
            by_path.setdefault(npath, []).append(nid)
    for test in tests:
        funcs: Set[str] = set()
        for file_rel in test.get("files", []):
            for npath, ids in by_path.items():
                if _paths_match(npath, file_rel):
                    funcs.update(ids)
        test["funcs"] = sorted(funcs)
    return 0


def _base_nodeid(nodeid: str) -> str:
    """``tests/test_x.py::test_a[param]`` -> ``tests/test_x.py::test_a``."""
    text = _posix(nodeid)
    if text.endswith("]") and "[" in text:
        text = text[:text.rindex("[")]
    return text


def merge_witness(tests: List[Dict[str, Any]], witness: Any, workspace: Path) -> int:
    """Fold a ``test-witness/v1`` document in. For every witnessed test the
    recorded file list REPLACES the static one and trust becomes
    ``runtime-witnessed``; parametrized variants aggregate onto the base id
    (union of files, summed duration). A witnessed id the static pass did not
    see (a dynamically generated test) is added when its file still exists.

    A witness that attributes NO repo file to a test (code generated by
    ``exec`` -- dataclass methods, namedtuples, some ORMs -- carries no file
    name, so a test touching only such code looks empty) leaves the static
    mapping and its trust in place and records only the duration: an empty
    observation is not evidence that the test exercises nothing.

    Returns the number of tests upgraded."""
    if not isinstance(witness, dict) or not isinstance(witness.get("tests"), dict):
        return 0
    aggregated: Dict[str, Dict[str, Any]] = {}
    for nodeid, record in witness["tests"].items():
        if not isinstance(nodeid, str) or not isinstance(record, dict):
            continue
        base = _base_nodeid(nodeid)
        slot = aggregated.setdefault(base, {"files": set(), "duration_s": None})
        for f in record.get("files") or []:
            if isinstance(f, str) and f.strip():
                slot["files"].add(_posix(f))
        dur = record.get("duration_s")
        if isinstance(dur, (int, float)) and not isinstance(dur, bool):
            slot["duration_s"] = (slot["duration_s"] or 0.0) + float(dur)
    by_id = {t["id"]: t for t in tests}
    upgraded = 0
    for base, slot in sorted(aggregated.items()):
        test = by_id.get(base)
        if test is None:
            file_rel = base.split("::", 1)[0]
            if not (workspace / file_rel).is_file():
                continue
            name = base.rsplit("::", 1)[-1]
            kind = _classify_kind(file_rel, name)
            test = {
                "id": base, "file": file_rel, "kind": kind,
                "layer": "unknown" if kind == "e2e" else "backend",
                "files": [], "funcs": [], "endpoints": [], "elements": [],
                "duration_s": None, "always_run": False, "trust": "unknown",
            }
            tests.append(test)
            by_id[base] = test
        test["duration_s"] = slot["duration_s"]
        observed = sorted(f for f in slot["files"] if f != test["file"])
        if not observed:
            continue
        test["files"] = observed
        test["trust"] = "runtime-witnessed"
        upgraded += 1
    return upgraded


def _matches_pin(test: Dict[str, Any], pattern: str) -> bool:
    pattern = pattern.strip()
    if not pattern:
        return False
    for subject in (test["id"], test["file"]):
        if subject == pattern or fnmatch.fnmatch(subject, pattern):
            return True
    return False


def apply_pins(tests: List[Dict[str, Any]], globs: Sequence[str]) -> int:
    """Mark ``always_run`` on every test an ``always_run`` glob matches (by id
    or by file). Returns the number pinned."""
    pinned = 0
    for test in tests:
        test["always_run"] = any(_matches_pin(test, g) for g in globs if isinstance(g, str))
        pinned += 1 if test["always_run"] else 0
    return pinned


# --------------------------------------------------------------------------- #
# build / load
# --------------------------------------------------------------------------- #

def _default_path(workspace: Path, explicit: Optional[str], *candidates: Path) -> Optional[Path]:
    if explicit:
        p = Path(explicit)
        p = p if p.is_absolute() else workspace / p
        return p if p.is_file() else None
    for c in candidates:
        if c.is_file():
            return c
    return None


def build(workspace: Any, e2e_dir: Optional[str] = None,
          lineage_graph: Optional[str] = None, witness: Optional[str] = None,
          *, write: bool = True, now: Optional[_dt.datetime] = None) -> Dict[str, Any]:
    """Build the index and (by default) write it to
    ``<workspace>/.architect-team/test-index.json``.

    Sources, each optional past the static pass: the suite manifest (found
    under ``e2e_dir`` or anywhere in the tree), ``lineage-graph.json`` (the
    explicit path, else ``.architect-team/lineage-graph.json``), the witness
    (the explicit path, else ``.architect-team/test-witness.json``). Pins come
    from ``.architect-team-deploy.json``'s ``tests.always_run``.
    """
    ws = Path(workspace)
    tests, import_graph = discover_python(ws)

    manifest_path = find_suite_manifest(ws, e2e_dir)
    if manifest_path is not None:
        tests.extend(discover_e2e(ws, manifest_path))

    lg_path = _default_path(ws, lineage_graph, state_dir(ws) / LINEAGE_GRAPH_FILENAME)
    lg_errors = 0
    if lg_path is not None:
        graph = _read_json(lg_path)
        lg_errors = join_lineage(tests, graph) if graph is not None else 1

    witness_path = _default_path(ws, witness, state_dir(ws) / WITNESS_FILENAME)
    witnessed = 0
    if witness_path is not None:
        witnessed = merge_witness(tests, _read_json(witness_path), ws)

    pins = _deploy_config_mod().tests_always_run(ws)
    apply_pins(tests, pins)

    tests.sort(key=lambda t: t["id"])
    sources: Dict[str, Any] = {
        "static": True,
        "witness": _rel(ws, witness_path) if witness_path else None,
        "lineage_graph": _rel(ws, lg_path) if lg_path else None,
        "suite_manifest": _rel(ws, manifest_path) if manifest_path else None,
    }
    if lg_errors:
        sources["lineage_graph_errors"] = lg_errors
    index = {
        "schema": INDEX_SCHEMA,
        "built_at": _now_iso(now),
        "workspace_root_rel": ".",
        "sources": sources,
        "pins": {"always_run": [g for g in pins if isinstance(g, str)]},
        "witnessed_count": witnessed,
        "import_graph": {k: import_graph[k] for k in sorted(import_graph)},
        "tests": tests,
    }
    if write:
        _write_json(index_path(ws), index)
    return index


def load_index(workspace: Any) -> Optional[Dict[str, Any]]:
    data = _read_json(index_path(workspace))
    if isinstance(data, dict) and data.get("schema") == INDEX_SCHEMA \
            and isinstance(data.get("tests"), list):
        return data
    return None


# --------------------------------------------------------------------------- #
# select
# --------------------------------------------------------------------------- #

def _reverse_closure(import_graph: Dict[str, List[str]],
                     changed: Set[str]) -> Dict[str, str]:
    """``{affected file: the changed file it depends on}`` over the inverted
    import graph. A changed file maps to itself."""
    reverse: Dict[str, Set[str]] = {}
    for src, deps in import_graph.items():
        for dep in deps or []:
            reverse.setdefault(_posix(dep), set()).add(_posix(src))
    via: Dict[str, str] = {c: c for c in changed}
    stack = list(changed)
    while stack:
        cur = stack.pop()
        for importer in sorted(reverse.get(cur, ())):
            if importer not in via:
                via[importer] = via[cur]
                stack.append(importer)
    return via


def _scan_changed_endpoints(workspace: Path, changed: Iterable[str]) -> List[str]:
    found: Set[str] = set()
    for rel in changed:
        ext = os.path.splitext(rel)[1].lower()
        if ext not in ENDPOINT_SCAN_EXTENSIONS:
            continue
        path = workspace / rel
        if path.is_file():
            found.update(endpoints_in_text(_read_text(path)))
    return sorted(found)


def _full_suite_phases(workspace: Path) -> Set[str]:
    phases = {FULL_SUITE_PHASE}
    for p in _deploy_config_mod().tests_full_suite_at(workspace):
        norm = normalize_phase(p)
        if norm:
            phases.add(norm)
    return phases


def select(workspace: Any, changed_files: Sequence[str], phase: Any,
           index: Optional[Dict[str, Any]] = None, *,
           changed_endpoints: Optional[Sequence[str]] = None,
           changed_elements: Optional[Sequence[str]] = None,
           baseline: Optional[str] = None, write: bool = True,
           now: Optional[_dt.datetime] = None) -> Dict[str, Any]:
    """The selector. See the module docstring for the rule set.

    ``index`` defaults to the on-disk index, built fresh when absent (the
    bootstrapping case). The returned record is also written to
    ``<workspace>/.architect-team/test-selection-<ts>.json`` unless
    ``write=False``; the written path is reported as ``record_path``.
    """
    if isinstance(changed_files, (str, bytes)):
        raise TypeError("changed_files must be a sequence of paths, not a string")
    ws = Path(workspace)
    if index is None:
        index = load_index(ws) or build(ws, now=now)
    fi = _frontend_impact_mod()

    changed = sorted({_posix(f) for f in changed_files if str(f).strip()})
    changed_set = set(changed)
    via = _reverse_closure(index.get("import_graph") or {}, changed_set)
    affected = set(via)

    frontend_files = fi.changed_files_touch_frontend(changed)
    endpoints = set(_scan_changed_endpoints(ws, changed))
    for raw in changed_endpoints or []:
        text = str(raw).strip().rstrip("/")
        if text:
            endpoints.add(text if text.startswith("/") else "/" + text)
    elements = {str(e).strip() for e in (changed_elements or []) if str(e).strip()}

    phase_norm = normalize_phase(phase)
    full_suite = phase_norm in _full_suite_phases(ws)

    selected: List[Dict[str, Any]] = []
    tests = index.get("tests") or []
    for test in tests:
        reasons: List[str] = []
        if full_suite:
            reasons.append(REASON_FULL_SUITE)
        hits = sorted(set(test.get("files") or []) & affected)
        if test.get("file") in affected:
            hits = sorted(set(hits) | {test["file"]})
        for f in hits:
            root = via.get(f, f)
            reasons.append(f"touches {f}" if root == f else f"touches {f} (depends on {root})")
        if test.get("always_run"):
            reasons.append(REASON_ALWAYS_RUN)
        if test.get("trust") == "unknown" or not test.get("files"):
            reasons.append(REASON_UNKNOWN_MAPPING)
        if test.get("kind") == "e2e":
            for ep in sorted(set(test.get("endpoints") or []) & endpoints):
                reasons.append(f"endpoint {ep} changed")
            for el in sorted(set(test.get("elements") or []) & elements):
                reasons.append(f"element {el} touched")
            if frontend_files and not elements:
                reasons.append(REASON_FRONTEND_COARSE)
        if reasons:
            selected.append({
                "id": test["id"], "file": test.get("file"), "kind": test.get("kind"),
                "trust": test.get("trust"), "duration_s": test.get("duration_s"),
                "reasons": reasons,
            })

    record: Dict[str, Any] = {
        "schema": SELECTION_SCHEMA,
        "at": _now_iso(now),
        "phase": str(phase),
        "baseline": baseline,
        "changed_files": changed,
        "changed_endpoints": sorted(endpoints),
        "changed_elements": sorted(elements),
        "frontend_files": list(frontend_files),
        "affected_files": sorted(affected),
        "index_built_at": index.get("built_at"),
        "index_tests": len(tests),
        "selected": selected,
        "skipped_count": len(tests) - len(selected),
        "full_suite": full_suite,
    }
    if write:
        record["record_path"] = _rel(ws, _write_selection(ws, record, now))
    return record


def _selection_sort_key(path: Path) -> Tuple[str, int]:
    """``test-selection-<stamp>[-<n>].json`` -> ``(stamp, n)``. A plain name
    sort puts ``...Z-1.json`` BEFORE ``...Z.json`` (``-`` < ``.``), so the
    second record of a second would read as the older one."""
    stem = path.name[len(SELECTION_PREFIX):-len(".json")]
    stamp, _, counter = stem.partition("-")
    try:
        return (stamp, int(counter) if counter else 0)
    except ValueError:
        return (stamp, 0)


def _write_selection(ws: Path, record: Dict[str, Any],
                     now: Optional[_dt.datetime]) -> Path:
    stamp = _now_compact(now)
    target = state_dir(ws) / f"{SELECTION_PREFIX}{stamp}.json"
    counter = 1
    while target.exists():
        target = state_dir(ws) / f"{SELECTION_PREFIX}{stamp}-{counter}.json"
        counter += 1
    payload = {k: v for k, v in record.items() if k != "record_path"}
    _write_json(target, payload)
    return target


# --------------------------------------------------------------------------- #
# stats (for the homepage)
# --------------------------------------------------------------------------- #

def _count_by(tests: Sequence[Dict[str, Any]], key: str, domain: Sequence[str]) -> Dict[str, int]:
    counts = {d: 0 for d in domain}
    counts.setdefault("unknown", 0)
    for t in tests:
        value = t.get(key)
        counts[value if value in counts else "unknown"] += 1
    return counts


def stats(index: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    tests = (index or {}).get("tests") or []
    durations = [t["duration_s"] for t in tests
                 if isinstance(t.get("duration_s"), (int, float))]
    return {
        "schema": STATS_SCHEMA,
        "built_at": (index or {}).get("built_at"),
        "sources": (index or {}).get("sources"),
        "total": len(tests),
        "by_kind": _count_by(tests, "kind", KINDS + ("unknown",)),
        "by_layer": _count_by(tests, "layer", LAYERS),
        "by_trust": _count_by(tests, "trust", TRUST_LEVELS),
        "always_run": sum(1 for t in tests if t.get("always_run")),
        "unknown_mapping": sum(1 for t in tests
                               if t.get("trust") == "unknown" or not t.get("files")),
        "with_duration": len(durations),
        "total_duration_s": round(sum(durations), 3) if durations else None,
        "pins": (index or {}).get("pins"),
    }


def latest_selection(workspace: Any) -> Optional[Dict[str, Any]]:
    """A summary of the most recent ``test-selection-*.json``, or ``None``."""
    sd = state_dir(workspace)
    if not sd.is_dir():
        return None
    files = sorted((p for p in sd.glob(f"{SELECTION_PREFIX}*.json") if p.is_file()),
                   key=_selection_sort_key)
    if not files:
        return None
    path = files[-1]
    data = _read_json(path)
    if not isinstance(data, dict):
        return None
    return {
        "path": _rel(Path(workspace), path),
        "at": data.get("at"),
        "phase": data.get("phase"),
        "selected_count": len(data.get("selected") or []),
        "skipped_count": data.get("skipped_count"),
        "full_suite": data.get("full_suite"),
    }


# --------------------------------------------------------------------------- #
# git
# --------------------------------------------------------------------------- #

def _git(workspace: Path, *args: str) -> str:
    cmd = ["git", "-C", str(workspace), *args]
    try:
        proc = subprocess.run(cmd, capture_output=True, encoding="utf-8",
                              errors="replace", timeout=120)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise GitError(f"{' '.join(cmd)}: {exc}") from exc
    if proc.returncode != 0:
        raise GitError(f"{' '.join(cmd)} exited {proc.returncode}: "
                       f"{(proc.stderr or '').strip()}")
    return proc.stdout


def changed_files_from_git(workspace: Any, baseline_sha: str,
                           *, include_uncommitted: bool = True) -> List[str]:
    """``git diff --name-only <baseline>..HEAD`` plus the porcelain status of
    uncommitted work (modified, added, deleted, renamed -- both names -- and
    untracked files). Sorted, de-duplicated, forward-slash, repo-relative.
    Raises :class:`GitError` with the command and stderr on failure."""
    ws = Path(workspace)
    baseline = str(baseline_sha or "").strip()
    if not baseline:
        raise GitError("a baseline revision is required")
    files: Set[str] = set()
    for line in _git(ws, "diff", "--name-only", f"{baseline}..HEAD").splitlines():
        if line.strip():
            files.add(_posix(line))
    if include_uncommitted:
        entries = _git(ws, "status", "--porcelain", "--untracked-files=all", "-z").split("\0")
        i = 0
        while i < len(entries):
            entry = entries[i]
            i += 1
            if len(entry) < 4:
                continue
            code, path = entry[:2], entry[3:]
            files.add(_posix(path))
            if code[0] in "RC" and i < len(entries) and entries[i]:
                files.add(_posix(entries[i]))
                i += 1
    return sorted(files)


__all__ = [
    "INDEX_SCHEMA", "SELECTION_SCHEMA", "WITNESS_SCHEMA", "STATS_SCHEMA",
    "STATE_DIR", "INDEX_FILENAME", "WITNESS_FILENAME", "SELECTION_PREFIX",
    "KINDS", "LAYERS", "TRUST_LEVELS", "FULL_SUITE_PHASE",
    "REASON_FULL_SUITE", "REASON_ALWAYS_RUN", "REASON_UNKNOWN_MAPPING",
    "REASON_FRONTEND_COARSE", "GitError",
    "normalize_phase", "state_dir", "index_path", "endpoints_in_text",
    "discover_python", "discover_e2e", "find_suite_manifest",
    "join_lineage", "merge_witness", "apply_pins",
    "build", "load_index", "select", "stats", "latest_selection",
    "changed_files_from_git",
]
