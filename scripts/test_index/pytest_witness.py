# -*- coding: utf-8 -*-
"""A small pytest plugin that records which repository files each test
actually executed -- the runtime witness that upgrades a test's static
mapping in the test index to ``trust: runtime-witnessed``.

Load it one of three ways (the workspace root must be on ``sys.path`` for the
dotted forms; ``python -m pytest`` from the workspace root does that)::

    python -m pytest -p scripts.test_index.pytest_witness
    # or, in the target repo's conftest.py:
    pytest_plugins = ["scripts.test_index.pytest_witness"]
    # or, when the plugin repo is elsewhere:
    PYTHONPATH=<plugin-root> python -m pytest -p scripts.test_index.pytest_witness

Output -- ``<workspace>/.architect-team/test-witness.json``::

    {"schema": "test-witness/v1", "written_at": iso, "workspace_root_rel": ".",
     "tests": {"<nodeid>": {"files": ["src/x.py", ...], "duration_s": 0.012}}}

The workspace is ``CT6_TEST_INDEX_WORKSPACE`` or ``--ct6-witness-workspace``,
else pytest's ``rootpath``; the output path is ``CT6_TEST_WITNESS_OUT`` or
``--ct6-witness-out``. An existing witness is MERGED (entries for the tests
that ran in this session are replaced, the rest kept), so a partial run never
erases the whole record; the index build drops witnessed ids whose file no
longer exists.

HOW IT WORKS, and the honest cost: ``sys.setprofile`` is installed for the
duration of each test's call phase and notes the file of every Python
``call`` event. That is a hook on every function call, so the suite runs
SLOWER under the witness -- roughly two to three times slower on call-heavy
code in informal measurements on this plugin's own suite; measure it on yours.
It is a bootstrap / refresh run, not the default way to run tests. It sees
only the main thread of the pytest process: code run in threads it did not
start, in subprocesses, or by a non-Python runtime (a Playwright browser, a
database) is NOT witnessed, and a C extension's internals are one ``call``
event at the boundary. Files under the tests directory, site-packages,
virtualenvs and this plugin itself are excluded from each test's file list.
"""
from __future__ import annotations

import datetime as _dt
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional, Set

import pytest

WITNESS_SCHEMA = "test-witness/v1"
DEFAULT_OUT = os.path.join(".architect-team", "test-witness.json")

_EXCLUDED_PARTS = frozenset({
    "site-packages", "dist-packages", ".venv", "venv", "__pycache__",
    "node_modules", ".git", ".tox", ".nox", ".architect-team",
})
_TEST_DIR_NAMES = frozenset({"tests", "test"})


def pytest_addoption(parser: Any) -> None:
    group = parser.getgroup("ct6-witness")
    group.addoption("--ct6-witness-workspace", default=None,
                    help="workspace root the witnessed paths are relative to "
                         "(default: CT6_TEST_INDEX_WORKSPACE or pytest's rootpath)")
    group.addoption("--ct6-witness-out", default=None,
                    help="where to write test-witness.json "
                         "(default: CT6_TEST_WITNESS_OUT or "
                         "<workspace>/.architect-team/test-witness.json)")


class _Witness:
    def __init__(self, workspace: Path, out: Path) -> None:
        self.workspace = workspace
        self.workspace_str = str(workspace)
        self.out = out
        self.tests: Dict[str, Dict[str, Any]] = {}
        self._current: Optional[Set[str]] = None
        self._cache: Dict[str, Optional[str]] = {}
        self._self_file = os.path.realpath(__file__)

    # -- classification -------------------------------------------------- #

    def _classify(self, filename: str) -> Optional[str]:
        if not filename or filename.startswith("<"):
            return None
        try:
            real = os.path.realpath(filename)
        except (OSError, ValueError):
            return None
        if real == self._self_file:
            return None
        if not (real == self.workspace_str
                or real.startswith(self.workspace_str + os.sep)):
            return None
        rel = os.path.relpath(real, self.workspace_str).replace(os.sep, "/")
        parts = rel.split("/")
        if any(p in _EXCLUDED_PARTS for p in parts):
            return None
        if parts[0] in _TEST_DIR_NAMES:
            return None
        return rel

    def _profile(self, frame: Any, event: str, arg: Any) -> None:
        if event != "call" or self._current is None:
            return
        filename = frame.f_code.co_filename
        hit = self._cache.get(filename, "")
        if hit == "":
            hit = self._classify(filename)
            self._cache[filename] = hit
        if hit:
            self._current.add(hit)

    # -- hooks ----------------------------------------------------------- #

    @pytest.hookimpl(hookwrapper=True)
    def pytest_runtest_call(self, item: Any):
        files: Set[str] = set()
        self._current = files
        previous = sys.getprofile()
        started = time.perf_counter()
        sys.setprofile(self._profile)
        try:
            yield
        finally:
            sys.setprofile(previous)
            duration = time.perf_counter() - started
            self._current = None
        self.tests[item.nodeid] = {
            "files": sorted(files),
            "duration_s": round(duration, 6),
        }

    def pytest_sessionfinish(self, session: Any, exitstatus: Any) -> None:
        existing: Dict[str, Any] = {}
        try:
            data = json.loads(self.out.read_text(encoding="utf-8"))
            if isinstance(data, dict) and isinstance(data.get("tests"), dict):
                existing = dict(data["tests"])
        except (OSError, ValueError):
            existing = {}
        existing.update(self.tests)
        payload = {
            "schema": WITNESS_SCHEMA,
            "written_at": _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "workspace_root_rel": ".",
            "tests": {k: existing[k] for k in sorted(existing)},
        }
        self.out.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.out.with_name(self.out.name + ".tmp")
        tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n",
                       encoding="utf-8")
        os.replace(tmp, self.out)


def _resolve_workspace(config: Any) -> Path:
    explicit = config.getoption("--ct6-witness-workspace", default=None) \
        or os.environ.get("CT6_TEST_INDEX_WORKSPACE")
    if explicit:
        return Path(explicit).resolve()
    rootpath = getattr(config, "rootpath", None)
    return Path(str(rootpath) if rootpath else os.getcwd()).resolve()


def pytest_configure(config: Any) -> None:
    workspace = _resolve_workspace(config)
    out_text = config.getoption("--ct6-witness-out", default=None) \
        or os.environ.get("CT6_TEST_WITNESS_OUT")
    out = Path(out_text) if out_text else workspace / DEFAULT_OUT
    if not out.is_absolute():
        out = workspace / out
    config.pluginmanager.register(_Witness(workspace, out), "ct6-test-witness")
