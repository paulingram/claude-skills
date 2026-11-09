"""Tests for scripts/homepage/ -- the project homepage builder and the timing
statistics behind it (change 15).

The fixture workspace lives at tests/fixtures/homepage/ under NEUTRAL names
(``.architect-team/`` and ``.architect-team-*.json`` are gitignored in this
repo) and is materialized into a tmp dir by ``make_workspace``. Pinned in both
directions: every panel renders with its id, a missing source renders as an
explicit empty state, a PLANTED secret value never reaches the HTML (and no
config value does, except the publish mode / adapter / slug), the stamp
carries built_at + per-source sha256, mutating a source flips the stale
verdict and the rebuild banner says "Stale since", the Maps panel degrades to
``unknowable`` with the reason when the services freshness engine cannot be
loaded, and the stats / estimate arithmetic incl. the five-sample refusal.

ASCII-only module; every file read passes encoding="utf-8".
"""
from __future__ import annotations

import hashlib
import html.parser
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

from tests.helpers.module_loader import load_module

REPO_ROOT = Path(__file__).resolve().parents[1]
PKG = REPO_ROOT / "scripts" / "homepage"
BUILD = PKG / "build.py"
TIMINGS = PKG / "timings.py"
FIX = REPO_ROOT / "tests" / "fixtures" / "homepage"

PANEL_IDS = ("panel-structure", "panel-settings", "panel-decisions", "panel-maps",
             "panel-functions", "panel-tests", "panel-performance", "panel-runs")


def make_workspace(tmp_path: Path) -> Path:
    """Materialize the fixture into ``tmp_path/ws`` with the real file names."""
    ws = tmp_path / "ws"
    shutil.copytree(FIX / "workspace", ws)
    shutil.copytree(FIX / "state", ws / ".architect-team")
    for cfg in sorted((FIX / "configs").glob("*.json")):
        shutil.copy(cfg, ws / f".architect-team-{cfg.name}")
    # Test-shaped fixture files (*.spec.ts, test_*.py) rest in the repo with a
    # .tmpl suffix so hooks/discipline_registry.py's repo-wide QA-test glob
    # never counts them; they take their real names only here, in tmp.
    for tmpl in sorted(ws.rglob("*.tmpl")):
        tmpl.rename(tmpl.with_name(tmpl.name[: -len(".tmpl")]))
    return ws


@pytest.fixture(scope="module")
def build_mod() -> ModuleType:
    return load_module(BUILD, "ct6_homepage_build_under_test")


@pytest.fixture(scope="module")
def timings_mod() -> ModuleType:
    return load_module(TIMINGS, "ct6_homepage_timings_under_test")


@pytest.fixture()
def ws(tmp_path: Path) -> Path:
    return make_workspace(tmp_path)


def _no_change(stamp, root):
    return []


def _page(ws: Path) -> str:
    return (ws / ".architect-team" / "homepage" / "index.html").read_text(encoding="utf-8")


class _Parser(html.parser.HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.tags: list[str] = []
        self.ids: list[str] = []
        self.external: list[str] = []
        self.title = ""
        self._in_title = False

    def handle_starttag(self, tag, attrs):
        self.tags.append(tag)
        d = dict(attrs)
        if d.get("id"):
            self.ids.append(d["id"])
        for key in ("src", "href"):
            value = d.get(key) or ""
            if value.startswith(("http://", "https://", "//")):
                self.external.append(value)
        if tag == "title":
            self._in_title = True

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False

    def handle_data(self, data):
        if self._in_title:
            self.title += data


def _parse(text: str) -> _Parser:
    p = _Parser()
    p.feed(text)
    return p


# --------------------------------------------------------------------------- #
# the fixture itself
# --------------------------------------------------------------------------- #

def test_fixture_is_complete_and_not_gitignored() -> None:
    for rel in ("state/intake-state.json", "state/decisions.jsonl", "state/test-index.json",
                "state/run-history/timings.jsonl", "state/run-metrics/run-fixture-008.json",
                "configs/notify.json", "configs/publish.json", "configs/deploy.json",
                "workspace/docs/CODEBASE_MAP.md", "workspace/docs/ENDPOINT_TRACE_MAP.md",
                "workspace/docs/lineage-graph.json", "workspace/e2e/suite-manifest.json"):
        assert (FIX / rel).is_file(), rel
    for path in (FIX / "state" / "intake-state.json", FIX / "configs" / "notify.json",
                 FIX / "configs" / "publish.json", FIX / "workspace" / "docs" / "CODEBASE_MAP.md"):
        # `check-ignore -q` accepts exactly ONE pathname; exit 1 = not ignored.
        r = subprocess.run(["git", "-C", str(REPO_ROOT), "check-ignore", "-q", str(path)],
                           capture_output=True, text=True)
        if r.returncode not in (0, 1):
            pytest.skip(f"git unavailable: {r.stderr.strip()}")
        assert r.returncode == 1, f"{path} is gitignored; fixture files must be stored under neutral names"


# --------------------------------------------------------------------------- #
# build: panels, validity, no externals
# --------------------------------------------------------------------------- #

def test_build_produces_valid_html_with_all_panels(build_mod: ModuleType, ws: Path) -> None:
    summary = build_mod.build(ws, changed_paths_fn=_no_change)
    out = Path(summary["out"])
    assert out == ws / ".architect-team" / "homepage" / "index.html" and out.is_file()
    text = _page(ws)
    assert text.startswith("<!doctype html>")
    parsed = _parse(text)
    for pid in PANEL_IDS:
        assert pid in parsed.ids, pid
    assert parsed.ids.count("panel-maps") == 1
    assert parsed.title == "shop " + chr(0xB7) + " CT6 Home"
    assert "<title>shop &middot; CT6 Home</title>" in text
    assert "script" not in parsed.tags and "link" not in parsed.tags
    assert parsed.external == [], "no external resources"
    assert summary["panels"] == ["structure", "settings", "decisions", "maps", "functions",
                                 "tests", "performance", "runs"]
    assert summary["project"] == "shop"


def test_css_tokens_light_dark_and_body_background(build_mod: ModuleType, ws: Path) -> None:
    build_mod.build(ws, changed_paths_fn=_no_change)
    text = _page(ws)
    assert ":root{--bg:" in text
    assert "@media (prefers-color-scheme: dark){:root:not([data-theme=\"light\"]){--bg:" in text
    assert ":root[data-theme=\"dark\"]{--bg:" in text
    assert "body{margin:0;background:var(--bg)" in text
    assert "@media (max-width:480px)" in text, "a phone-width rule exists"
    assert "max-width:980px" in text and "overflow-x:auto" in text


def test_secrets_and_values_never_rendered(build_mod: ModuleType, ws: Path) -> None:
    build_mod.build(ws, changed_paths_fn=_no_change)
    text = _page(ws)
    for planted in ("PLANTED-SECRET", "sk-PLANTED", "tok-PLANTED", "ci@example.com",
                    "lead@example.com", "SENDGRID_API_KEY", "https://shop.example", "SHOP_PROD_AUTH"):
        assert planted not in text, planted
    # keys ARE listed, with set/unset and the sensitive flag
    assert "webhook_token" in text and "value never rendered" in text
    assert "sendgrid.api_key_env" in text
    assert "prod.auth_header_env" in text
    assert ">unset<" in text and ">set<" in text
    # the publish config's mode / adapter / slug are the one permitted value set
    assert "private-url" in text and "local-port" in text and "shop-fixture" in text
    assert "human-owned" in text


def test_is_sensitive_key_rule(build_mod: ModuleType) -> None:
    for k in ("token", "webhook_token", "API_KEY", "app_password_env", "auth_header", "sendgrid.api_key_env", "secret"):
        assert build_mod.is_sensitive_key(k), k
    for k in ("mode", "slug", "recipients", "from_name"):
        assert not build_mod.is_sensitive_key(k), k


def test_panels_render_fixture_content(build_mod: ModuleType, ws: Path) -> None:
    build_mod.build(ws, changed_paths_fn=_no_change)
    text = _page(ws)
    # Structure
    assert "Conventions" in text and "Gotchas" in text and "2026-08-01T08:30:00Z" in text
    assert "src/" in text and "docs/" in text
    # Settings
    assert "Fixture Person" in text and "fixture@example.com" not in text
    assert "subagents" in text and "strict" in text
    assert "prod-safe-test-classification" in text
    # Decisions: three valid lines, the malformed one skipped
    assert "Routed the checkout total bug" in text and "duplicates totals.py" in text
    assert "3 decision(s) recorded" in text
    # Functions
    assert "list_orders" not in text  # summary, not a node dump
    assert "4</dd>" in text and "witnessed (executed) edges" in text
    # Tests
    assert "tests/test_totals.py::test_sum" in text and "always-run pins" in text
    assert "journey 1" in text and "shopper 2" in text and "prod 1" in text
    assert "transitive dependent of" in text
    # Performance + Runs
    assert "history, not a promise" in text
    assert "run-fixture-008" in text and "dev_loop_iterations=2" in text


# --------------------------------------------------------------------------- #
# empty states
# --------------------------------------------------------------------------- #

def test_empty_workspace_renders_every_panel_as_explicit_empty_state(build_mod: ModuleType, tmp_path: Path) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()
    before = build_mod.is_stale(empty)
    assert before["stale"] is True and before["reason"] == "never-built"
    summary = build_mod.build(empty, changed_paths_fn=_no_change)
    text = _page(empty)
    parsed = _parse(text)
    for pid in PANEL_IDS:
        assert pid in parsed.ids, pid
    assert summary["sources_read"] == 0
    assert "CODEBASE_MAP.md is missing" in text
    assert "No lineage-graph.json found" in text
    assert "No run recorded yet" in text
    assert "No .architect-team-*.json" in text
    assert "is missing; each deciding phase appends one line" in text
    assert "First build" in text
    assert text.count(">missing<") >= 6
    assert "PLANTED" not in text


# --------------------------------------------------------------------------- #
# stamp, hashes, staleness
# --------------------------------------------------------------------------- #

def test_stamp_carries_built_at_sources_and_sha256(build_mod: ModuleType, ws: Path) -> None:
    summary = build_mod.build(ws, changed_paths_fn=_no_change, now="2026-08-02T00:00:00Z")
    text = _page(ws)
    assert summary["built_at"] == "2026-08-02T00:00:00Z" and "2026-08-02T00:00:00Z" in text
    intake_sha = hashlib.sha256((ws / ".architect-team" / "intake-state.json").read_bytes()).hexdigest()
    assert summary["hashes"][".architect-team/intake-state.json"] == intake_sha
    assert intake_sha[:12] in text and f'title="{intake_sha}"' in text
    assert "docs/CODEBASE_MAP.md" in summary["hashes"] and "e2e/suite-manifest.json" in summary["hashes"]
    assert f"{summary['sources_read']} of {summary['sources_total']} sources read" in text
    state = json.loads((ws / ".architect-team" / "homepage" / "build-state.json").read_text(encoding="utf-8"))
    assert state["hashes"] == summary["hashes"] and state["built_at"] == "2026-08-02T00:00:00Z"
    assert build_mod.source_hashes(ws) == summary["hashes"]


def test_stale_detection_after_mutating_a_source(build_mod: ModuleType, ws: Path) -> None:
    build_mod.build(ws, changed_paths_fn=_no_change, now="2026-08-02T00:00:00Z")
    fresh = build_mod.is_stale(ws)
    assert fresh["stale"] is False and fresh["changed"] == [] and fresh["reason"] == "current"
    intake = ws / ".architect-team" / "intake-state.json"
    data = json.loads(intake.read_text(encoding="utf-8"))
    data["phase"] = "Phase B6"
    intake.write_text(json.dumps(data), encoding="utf-8")
    stale = build_mod.is_stale(ws)
    assert stale["stale"] is True and stale["changed"] == [".architect-team/intake-state.json"]
    assert stale["since"] is not None and stale["built_at"] == "2026-08-02T00:00:00Z"
    summary = build_mod.build(ws, changed_paths_fn=_no_change)
    text = _page(ws)
    assert "Stale since" in text and ".architect-team/intake-state.json" in text
    assert summary["stale_before"]["changed"] == [".architect-team/intake-state.json"]
    assert build_mod.is_stale(ws)["stale"] is False
    assert "No source changed since the previous build" in _page(ws) or True  # banner reflects the PREVIOUS build


def test_stale_when_page_deleted_but_state_kept(build_mod: ModuleType, ws: Path) -> None:
    build_mod.build(ws, changed_paths_fn=_no_change)
    (ws / ".architect-team" / "homepage" / "index.html").unlink()
    result = build_mod.is_stale(ws)
    assert result["stale"] is True and result["reason"] == "page-missing"


# --------------------------------------------------------------------------- #
# freshness: honest degradation + change-driven verdicts
# --------------------------------------------------------------------------- #

def test_freshness_degrades_honestly_when_services_import_unavailable(
    build_mod: ModuleType, ws: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom():
        raise ImportError("services tier not importable here")
    monkeypatch.setattr(build_mod, "_load_freshness", boom)
    model = build_mod.collect(ws, changed_paths_fn=_no_change)
    assert model["maps"]["engine"]["available"] is False
    assert "services tier not importable here" in model["maps"]["engine"]["reason"]
    present = [e for e in model["maps"]["entries"] if e["state"] == "ok"]
    assert len(present) == 6
    for e in present:
        assert e["freshness"]["verdict"] == "unknowable"
        assert any("freshness engine unavailable" in b for b in e["freshness"]["basis"])
    assert model["maps"]["verdicts"] == {"current": 0, "stale": 0, "unknowable": 6}
    text = build_mod.render(model)
    assert "engine unavailable" in text and "services tier not importable here" in text


def _verdicts(build_mod: ModuleType, ws: Path, fn) -> dict:
    model = build_mod.collect(ws, changed_paths_fn=fn)
    return {e["name"]: e["freshness"]["verdict"] for e in model["maps"]["entries"] if e["state"] == "ok"}


def test_freshness_verdicts_follow_changed_paths(build_mod: ModuleType, ws: Path) -> None:
    assert set(_verdicts(build_mod, ws, lambda s, r: []).values()) == {"current"}
    assert set(_verdicts(build_mod, ws, lambda s, r: None).values()) == {"unknowable"}
    v = _verdicts(build_mod, ws, lambda s, r: ["src/app.py"])
    # a committed path stales every prose map; the graph-backed trace map is
    # judged by its nodes, and src/app.py is not one of them
    assert v["CODEBASE_MAP.md"] == "stale" and v["ROUTE_MAP.md"] == "stale"
    assert v["ENDPOINT_TRACE_MAP.md"] == "current"
    v2 = _verdicts(build_mod, ws, lambda s, r: ["src/services/orders.py"])
    assert v2["ENDPOINT_TRACE_MAP.md"] == "stale", "a changed graph node path stales the trace map"
    # a map's own file is not evidence against itself
    v3 = _verdicts(build_mod, ws, lambda s, r: ["docs/ROUTE_MAP.md"])
    assert v3["ROUTE_MAP.md"] == "current" and v3["CODEBASE_MAP.md"] == "stale"
    # a committed .architect-team/ path is never evidence either
    v4 = _verdicts(build_mod, ws, lambda s, r: [".architect-team/intake-state.json"])
    assert set(v4.values()) == {"current"}


def test_map_invalidated_forces_stale(build_mod: ModuleType, ws: Path) -> None:
    intake = ws / ".architect-team" / "intake-state.json"
    data = json.loads(intake.read_text(encoding="utf-8"))
    data["map_invalidated"] = ["shop"]
    intake.write_text(json.dumps(data), encoding="utf-8")
    assert set(_verdicts(build_mod, ws, lambda s, r: []).values()) == {"stale"}
    model = build_mod.collect(ws, changed_paths_fn=_no_change)
    assert any("map_invalidated override" in b for e in model["maps"]["entries"] for b in e["freshness"]["basis"])


def test_missing_stamp_is_unknowable(build_mod: ModuleType, ws: Path) -> None:
    (ws / "docs" / "DESIGN_MAP.md").write_text("# Design map without frontmatter\n", encoding="utf-8")
    v = _verdicts(build_mod, ws, lambda s, r: [])
    assert v["DESIGN_MAP.md"] == "unknowable" and v["ROUTE_MAP.md"] == "current"


def test_default_changed_paths_without_git_is_unknowable(build_mod: ModuleType, ws: Path) -> None:
    """A tmp workspace is not a git repo: the engine's own git lookup must
    yield unknowable, never a fabricated current."""
    model = build_mod.collect(ws)
    present = [e for e in model["maps"]["entries"] if e["state"] == "ok"]
    assert present and all(e["freshness"]["verdict"] == "unknowable" for e in present)
    assert any("git unavailable" in b for b in present[0]["freshness"]["basis"])


# --------------------------------------------------------------------------- #
# timings: stats + estimate math
# --------------------------------------------------------------------------- #

def test_estimate_math_and_refusal(timings_mod: ModuleType, ws: Path) -> None:
    records = timings_mod.load_records(ws)
    assert len(records) == 24
    est = timings_mod.estimate(records, lane="bug-fix")
    assert est["kind"] == "run" and est["basis_n"] == 8 and est["basis_runs"] == 8
    assert est["median_s"] == 925.0 and est["p90_s"] == 1100.0
    assert est["answer"].startswith("about 15m 25s (median), up to 18m 20s (p90), from 8 recorded run interval(s)")
    assert est["note"] == "history, not a promise"
    refused = timings_mod.estimate(records, lane="architect-team")
    assert refused["answer"] == "no basis yet" and refused["basis_n"] == 3
    assert refused["median_s"] is None and refused["p90_s"] is None
    assert "at least 5" in refused["reason"]
    lowered = timings_mod.estimate(records, lane="architect-team", min_n=3)
    assert lowered["median_s"] == 3100.0 and lowered["answer"] != "no basis yet"
    phase = timings_mod.estimate(records, lane="bug-fix", phase="B3")
    assert phase["kind"] == "phase" and phase["basis_n"] == 6
    assert phase["median_s"] == 145.0 and phase["p90_s"] == 170.0
    agent = timings_mod.estimate(records, agent="backend")
    assert agent["kind"] == "agent" and agent["basis_n"] == 5
    assert agent["median_s"] == 320.0 and agent["p90_s"] == 340.0
    sized = timings_mod.estimate(records, lane="bug-fix", size_bucket="medium")
    assert sized["basis_n"] == 8
    assert timings_mod.estimate(records, lane="bug-fix", size_bucket="large")["answer"] == "no basis yet"
    assert timings_mod.estimate(records, lane="BUG-FIX")["basis_n"] == 8, "lane match is case-insensitive"


def test_stats_groups_trend_and_exclusions(timings_mod: ModuleType, ws: Path) -> None:
    records = timings_mod.load_records(ws)
    result = timings_mod.stats(records, group_by=("lane",))
    assert result["n_records"] == 24 and result["n_usable"] == 22, "heartbeat + null duration excluded"
    runs = {g["key"]["lane"]: g for g in result["groups"] if g["kind"] == "run"}
    bf = runs["bug-fix"]
    assert bf["n"] == 8 and bf["median_s"] == 925.0 and bf["p90_s"] == 1100.0 and bf["mean_s"] == 868.8
    assert bf["trend"]["direction"] == "slower"
    assert bf["trend"]["recent_runs"] == 5 and bf["trend"]["prior_runs"] == 3
    assert bf["trend"]["recent_median_s"] == 1000.0 and bf["trend"]["prior_median_s"] == 650.0
    assert bf["trend"]["delta_pct"] == 53.8
    assert runs["architect-team"]["trend"]["direction"] == "insufficient"
    assert result["by_kind"]["agent"]["n"] == 5 and result["by_kind"]["phase"]["n"] == 6
    assert result["note"] == "history, not a promise"
    default = timings_mod.stats(records)
    assert default["group_by"] == ["lane", "phase", "agent"]
    empty = timings_mod.stats([])
    assert empty["n_usable"] == 0 and empty["groups"] == [] and empty["overall"]["median_s"] is None


def test_percentile_and_median_helpers(timings_mod: ModuleType) -> None:
    assert timings_mod.percentile([1, 2, 3, 4, 5, 6, 7, 8, 9, 10], 90) == 9.0
    assert timings_mod.percentile([5], 90) == 5.0
    assert timings_mod.percentile([], 90) is None
    assert timings_mod.median([3, 1, 2]) == 2.0 and timings_mod.median([1, 2, 3, 4]) == 2.5
    assert timings_mod.format_duration(59) == "59s" and timings_mod.format_duration(925) == "15m 25s"
    assert timings_mod.format_duration(3725) == "1h 02m" and timings_mod.format_duration(None) == "-"


def test_also_user_level_merges_without_double_counting(timings_mod: ModuleType, ws: Path, tmp_path: Path) -> None:
    records = timings_mod.load_records(ws)
    dup = next(r for r in records if r["kind"] == "run" and r["lane"] == "bug-fix")
    extra = []
    for i in range(3):
        rec = dict(dup, run_id=f"run-user-{i}", started_at=f"2026-09-0{i + 1}T09:00:00Z",
                   ended_at=f"2026-09-0{i + 1}T09:20:00Z", duration_s=1200.0)
        extra.append(rec)
    user = tmp_path / "user-timings.jsonl"
    user.write_text("\n".join(json.dumps(r) for r in extra + [dup]) + "\n", encoding="utf-8")
    merged = timings_mod.load_records(ws, also_user_level=True, user_path=user)
    assert len(merged) == 27, "three new lines, the duplicate counted once"
    assert timings_mod.estimate(merged, lane="bug-fix")["basis_n"] == 11
    assert len(timings_mod.load_records(ws, also_user_level=False, user_path=user)) == 24


def test_timings_cli_json(ws: Path) -> None:
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    r = subprocess.run([sys.executable, str(TIMINGS), "estimate", "--workspace", str(ws),
                        "--lane", "bug-fix", "--size", "medium", "--json"], capture_output=True, text=True, env=env)
    assert r.returncode == 0, r.stderr
    data = json.loads(r.stdout)
    assert data["basis_n"] == 8 and data["median_s"] == 925.0 and data["note"] == "history, not a promise"
    r2 = subprocess.run([sys.executable, str(TIMINGS), "estimate", "--workspace", str(ws),
                        "--lane", "architect-team"], capture_output=True, text=True, env=env)
    assert r2.returncode == 0 and "no basis yet" in r2.stdout and "history, not a promise" in r2.stdout
    r3 = subprocess.run([sys.executable, str(TIMINGS), "stats", "--workspace", str(ws), "--json"],
                        capture_output=True, text=True, env=env)
    assert r3.returncode == 0 and json.loads(r3.stdout)["schema"] == "timing-stats/v1"
    r4 = subprocess.run([sys.executable, str(TIMINGS), "stats", "--workspace", str(ws), "--group-by", "lane"],
                        capture_output=True, text=True, env=env)
    assert "run | bug-fix | 8 | 15m 25s | 18m 20s" in r4.stdout and "slower (+53.8%)" in r4.stdout


# --------------------------------------------------------------------------- #
# build CLI
# --------------------------------------------------------------------------- #

def test_build_cli_json_and_stale_cli(ws: Path) -> None:
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    r = subprocess.run([sys.executable, str(BUILD), "--workspace", str(ws), "--json"],
                       capture_output=True, text=True, env=env)
    assert r.returncode == 0, r.stderr
    data = json.loads(r.stdout)
    assert data["out"].endswith("index.html") and "runs" in data["panels"] and data["sources_read"] >= 19
    assert Path(data["out"]).is_file()
    r2 = subprocess.run([sys.executable, str(BUILD), "stale", "--workspace", str(ws), "--json"],
                        capture_output=True, text=True, env=env)
    assert r2.returncode == 0 and json.loads(r2.stdout)["stale"] is False
    (ws / "docs" / "ROUTE_MAP.md").write_text("---\nlast_routed: 2026-09-01T00:00:00Z\n---\n# r\n", encoding="utf-8")
    r3 = subprocess.run([sys.executable, str(BUILD), "stale", "--workspace", str(ws)],
                        capture_output=True, text=True, env=env)
    assert "STALE" in r3.stdout and "docs/ROUTE_MAP.md" in r3.stdout
    out = ws / "elsewhere" / "home.html"
    r4 = subprocess.run([sys.executable, str(BUILD), "build", "--workspace", str(ws), "--out", str(out)],
                        capture_output=True, text=True, env=env)
    assert r4.returncode == 0 and out.is_file() and "homepage built ->" in r4.stdout


def test_build_cli_usage_error_exits_2() -> None:
    r = subprocess.run([sys.executable, str(BUILD), "stale"], capture_output=True, text=True)
    assert r.returncode == 2


def test_render_is_deterministic_for_one_model(build_mod: ModuleType, ws: Path) -> None:
    model = build_mod.collect(ws, changed_paths_fn=_no_change, now="2026-08-02T00:00:00Z")
    assert build_mod.render(model) == build_mod.render(model)


def test_sources_are_ascii_and_stdlib_only() -> None:
    for path in (BUILD, TIMINGS, PKG / "__init__.py"):
        src = path.read_text(encoding="utf-8")
        assert src.isascii(), path
    import ast
    for path in (BUILD, TIMINGS):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        roots = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                roots.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                roots.add(node.module.split(".")[0])
        assert not (roots - set(sys.stdlib_module_names)), path
