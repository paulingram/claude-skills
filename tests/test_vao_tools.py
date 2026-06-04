"""Layer 3 of the Verified Agent Output (VAO) framework — the five
verification tools in ``hooks/vao_tools.py``.

These tests pin the deterministic-output contract: same input → byte-stable
output. Each tool has positive + negative cases, plus a synthetic-fixture
round-trip where the canonical heirship-style fixture must yield the
expected failure verdict.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest


@pytest.fixture(scope="module")
def vao_tools(plugin_root: Path):
    spec = importlib.util.spec_from_file_location(
        "vao_tools",
        plugin_root / "hooks" / "vao_tools.py",
    )
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ===========================================================================
# verify_oracle_match
# ===========================================================================


def test_oracle_match_identical_trees_pass(vao_tools):
    tree = {"tree": {"App": {"Header": {}, "Body": {"Card": "x"}}}}
    v = vao_tools.verify_oracle_match(tree, tree)
    assert v["tool"] == "verify-oracle-match"
    assert v["matched"] is True
    assert v["divergences"] == []
    assert v["match_pct"] == 1.0


def test_oracle_match_missing_subtree_fails(vao_tools):
    oracle = {"tree": {"App": {"Header": {}, "Body": {"Card": "x"}}}}
    built = {"tree": {"App": {"Header": {}}}}
    v = vao_tools.verify_oracle_match(built, oracle)
    assert v["matched"] is False
    assert any(d["severity"] == "missing-in-actual" for d in v["divergences"])
    assert v["match_pct"] < 1.0


def test_oracle_match_extra_subtree_fails(vao_tools):
    oracle = {"tree": {"App": {"Header": {}}}}
    built = {"tree": {"App": {"Header": {}, "ExtraNode": "y"}}}
    v = vao_tools.verify_oracle_match(built, oracle)
    assert v["matched"] is False
    assert any(d["severity"] == "extra-in-actual" for d in v["divergences"])


def test_oracle_match_value_mismatch_fails(vao_tools):
    oracle = {"tree": {"label": "Submit"}}
    built = {"tree": {"label": "Save"}}
    v = vao_tools.verify_oracle_match(built, oracle)
    assert v["matched"] is False
    assert any(d["severity"] == "value-mismatch" for d in v["divergences"])


def test_oracle_match_deterministic_output(vao_tools, tmp_path: Path):
    """Two invocations on the same input must produce byte-identical output
    (modulo the verdict_at timestamp). Strip the timestamp and compare."""
    oracle = {"tree": {"App": ["A", "B", {"X": "1"}]}}
    built = {"tree": {"App": ["A", "B", {"X": "1"}]}}
    v1 = vao_tools.verify_oracle_match(built, oracle, out_path=tmp_path / "v1.json")
    v2 = vao_tools.verify_oracle_match(built, oracle, out_path=tmp_path / "v2.json")
    v1.pop("verdict_at")
    v2.pop("verdict_at")
    assert v1 == v2


def test_oracle_match_writes_verdict_file(vao_tools, tmp_path: Path):
    oracle = {"tree": {"x": 1}}
    built = {"tree": {"x": 1}}
    out = tmp_path / "verdict.json"
    vao_tools.verify_oracle_match(built, oracle, out_path=out)
    assert out.exists()
    data = json.loads(out.read_text())
    assert data["tool"] == "verify-oracle-match"


# ===========================================================================
# verify_baseline_clean
# ===========================================================================


def test_baseline_clean_empty_log_passes(vao_tools):
    v = vao_tools.verify_baseline_clean(tool_call_log=[])
    assert v["tool"] == "verify-baseline-clean"
    assert v["clean"] is True
    assert v["violations"] == []


def test_baseline_clean_passes_on_legit_git_ops(vao_tools):
    log = [
        {"tool": "Bash", "args": {"command": "git status"}, "ts": "2026-05-29T10:00:00Z"},
        {"tool": "Bash", "args": {"command": "git log --oneline -5"}, "ts": "2026-05-29T10:00:30Z"},
        {"tool": "Bash", "args": {"command": "git diff HEAD~1"}, "ts": "2026-05-29T10:01:00Z"},
        {"tool": "Bash", "args": {"command": "git stash list"}, "ts": "2026-05-29T10:01:30Z"},
    ]
    v = vao_tools.verify_baseline_clean(tool_call_log=log)
    assert v["clean"] is True, v["violations"]


def test_baseline_clean_detects_git_stash(vao_tools):
    log = [{"tool": "Bash", "args": {"command": "git stash"}, "ts": "2026-05-29T10:00:00Z"}]
    v = vao_tools.verify_baseline_clean(tool_call_log=log)
    assert v["clean"] is False
    assert v["violations"][0]["op"] == "git stash"


def test_baseline_clean_detects_reset_hard(vao_tools):
    log = [{"tool": "Bash", "args": {"command": "git reset --hard HEAD~1"}, "ts": "2026-05-29T10:00:00Z"}]
    v = vao_tools.verify_baseline_clean(tool_call_log=log)
    assert v["clean"] is False
    assert v["violations"][0]["op"] == "git reset --hard"


def test_baseline_clean_detects_rebase(vao_tools):
    log = [{"tool": "Bash", "args": {"command": "git rebase main"}, "ts": "2026-05-29T10:00:00Z"}]
    v = vao_tools.verify_baseline_clean(tool_call_log=log)
    assert v["clean"] is False
    assert v["violations"][0]["op"] == "git rebase"


def test_baseline_clean_detects_amend(vao_tools):
    log = [{"tool": "Bash", "args": {"command": "git commit --amend --no-edit"}, "ts": "2026-05-29T10:00:00Z"}]
    v = vao_tools.verify_baseline_clean(tool_call_log=log)
    assert v["clean"] is False
    assert v["violations"][0]["op"] == "git commit --amend"


def test_baseline_clean_detects_clean_f(vao_tools):
    log = [{"tool": "Bash", "args": {"command": "git clean -fd"}, "ts": "2026-05-29T10:00:00Z"}]
    v = vao_tools.verify_baseline_clean(tool_call_log=log)
    assert v["clean"] is False
    assert v["violations"][0]["op"] == "git clean -f"


def test_baseline_clean_carries_baseline_sha(vao_tools):
    v = vao_tools.verify_baseline_clean(tool_call_log=[], baseline_sha="abc123")
    assert v["baseline_sha"] == "abc123"


# ===========================================================================
# verify_no_fake_data
# ===========================================================================


def test_no_fake_data_empty_diff_passes(vao_tools):
    v = vao_tools.verify_no_fake_data(diff_files=[], oracle_spec={})
    assert v["tool"] == "verify-no-fake-data"
    assert v["clean"] is True
    assert v["hits"] == []


def test_no_fake_data_detects_placeholder_name(vao_tools):
    diff = [{"path": "src/users.tsx", "added_lines": ["const userName = 'John Smith'"]}]
    v = vao_tools.verify_no_fake_data(diff_files=diff, oracle_spec={})
    assert v["clean"] is False
    assert v["hits"][0]["category"] == "placeholder-name"


def test_no_fake_data_ignores_test_files(vao_tools):
    """Fake data in test files is legal — only production code is audited."""
    diff = [{"path": "tests/users.test.tsx", "added_lines": ["const userName = 'John Smith'"]}]
    v = vao_tools.verify_no_fake_data(diff_files=diff, oracle_spec={})
    assert v["clean"] is True


def test_no_fake_data_detects_msw_handler(vao_tools):
    diff = [{"path": "src/api.ts", "added_lines": ["rest.get('/api/users', (req, res, ctx) => res(ctx.json({})))"]}]
    v = vao_tools.verify_no_fake_data(diff_files=diff, oracle_spec={})
    assert v["clean"] is False
    assert v["hits"][0]["category"] == "msw-handler"


def test_no_fake_data_detects_playwright_fulfill(vao_tools):
    diff = [{"path": "src/intercepted.ts", "added_lines": ["await page.route('/api/users', r => r.fulfill({body: '[]'}))"]}]
    v = vao_tools.verify_no_fake_data(diff_files=diff, oracle_spec={})
    assert v["clean"] is False
    assert v["hits"][0]["category"] == "playwright-route-fulfill"


def test_no_fake_data_detects_oracle_dynamic_value(vao_tools):
    """An oracle-declared dynamic value MUST NOT appear verbatim in production code."""
    diff = [{"path": "src/heir.tsx", "added_lines": ["<span>{`Park Family Trust`}</span>"]}]
    oracle = {"dynamic_values": [{"literal": "Park Family Trust"}]}
    v = vao_tools.verify_no_fake_data(diff_files=diff, oracle_spec=oracle)
    assert v["clean"] is False
    assert v["hits"][0]["category"].startswith("oracle-dynamic-value:")


def test_no_fake_data_detects_lorem_ipsum(vao_tools):
    diff = [{"path": "src/copy.tsx", "added_lines": ["<p>Lorem ipsum dolor sit amet</p>"]}]
    v = vao_tools.verify_no_fake_data(diff_files=diff, oracle_spec={})
    assert v["clean"] is False
    assert v["hits"][0]["category"] == "lorem-ipsum"


# ===========================================================================
# verify_every_element
# ===========================================================================


def test_every_element_empty_oracle_passes(vao_tools):
    v = vao_tools.verify_every_element(built_components=[], oracle_spec={"elements": []})
    assert v["tool"] == "verify-every-element"
    assert v["coverage"] == 1.0
    assert v["missing"] == []


def test_every_element_full_coverage_passes(vao_tools):
    oracle = {"elements": [{"selector": "#submit", "label": "Submit"}]}
    built = [{"path": "Form.tsx", "elements": [{"selector": "#submit", "handler": "onSubmit", "tested_by": ["test_submit"]}]}]
    v = vao_tools.verify_every_element(built_components=built, oracle_spec=oracle)
    assert v["coverage"] == 1.0
    assert v["missing"] == []
    assert v["stub"] == []
    assert v["untested"] == []


def test_every_element_missing_element_flagged(vao_tools):
    oracle = {"elements": [{"selector": "#cancel"}]}
    built = [{"path": "Form.tsx", "elements": []}]
    v = vao_tools.verify_every_element(built_components=built, oracle_spec=oracle)
    assert v["coverage"] == 0.0
    assert v["missing"][0]["selector"] == "#cancel"


def test_every_element_stub_handler_flagged(vao_tools):
    oracle = {"elements": [{"selector": "#submit"}]}
    built = [{"path": "Form.tsx", "elements": [{"selector": "#submit", "handler": "() => {}", "tested_by": ["t"]}]}]
    v = vao_tools.verify_every_element(built_components=built, oracle_spec=oracle)
    assert len(v["stub"]) == 1


def test_every_element_untested_flagged(vao_tools):
    oracle = {"elements": [{"selector": "#submit"}]}
    built = [{"path": "Form.tsx", "elements": [{"selector": "#submit", "handler": "onSubmit", "tested_by": []}]}]
    v = vao_tools.verify_every_element(built_components=built, oracle_spec=oracle)
    assert len(v["untested"]) == 1


# ===========================================================================
# verify_rendered_parity (heirship amendment — the rendered-output gate)
# ===========================================================================


def test_rendered_parity_identical_dom_passes(vao_tools):
    dom = {
        "tag": "body",
        "selector": "body",
        "children": [
            {"tag": "div", "selector": "[data-component='AppShellLayout']", "children": [
                {"tag": "header", "selector": "[data-component='TaCrumbs']", "children": []},
            ]},
        ],
    }
    spec = {"chrome_topology": [{"anchor": "[data-component='TaCrumbs']"}]}
    v = vao_tools.verify_rendered_parity(candidate_dom=dom, oracle_dom=dom, oracle_spec=spec)
    assert v["tool"] == "verify-rendered-parity"
    assert v["matched"] is True
    assert v["divergences"] == []


def test_rendered_parity_chrome_mount_level_mismatch(vao_tools):
    """The CANONICAL heirship-app-v2 case: <TaCrumbs /> exists in BOTH source
    trees but at DIFFERENT mount levels in the rendered DOM. Source-tree
    verify-oracle-match would say matched=true; verify-rendered-parity
    catches the divergence."""
    oracle_dom = {
        "tag": "body",
        "selector": "body",
        "children": [
            {"tag": "div", "selector": "[data-component='AppShellLayout']", "children": [
                {"tag": "header", "selector": "[data-component='TaCrumbs']", "children": []},
            ]},
        ],
    }
    candidate_dom = {
        "tag": "body",
        "selector": "body",
        "children": [
            {"tag": "div", "selector": "[data-component='AppShellLayout']", "children": []},
            {"tag": "div", "selector": "[data-testid='page-body']", "children": [
                {"tag": "header", "selector": "[data-component='TaCrumbs']", "children": []},
            ]},
        ],
    }
    spec = {"chrome_topology": [{"anchor": "[data-component='TaCrumbs']"}]}
    v = vao_tools.verify_rendered_parity(
        candidate_dom=candidate_dom, oracle_dom=oracle_dom, oracle_spec=spec
    )
    assert v["matched"] is False
    assert v["divergences"][0]["anchor"] == "[data-component='TaCrumbs']"
    assert v["divergences"][0]["severity"] == "architectural-mismatch"


def test_rendered_parity_missing_in_candidate(vao_tools):
    oracle_dom = {"tag": "body", "selector": "body", "children": [
        {"tag": "div", "selector": "[data-component='TaCrumbs']", "children": []},
    ]}
    candidate_dom = {"tag": "body", "selector": "body", "children": []}
    spec = {"chrome_topology": [{"anchor": "[data-component='TaCrumbs']"}]}
    v = vao_tools.verify_rendered_parity(
        candidate_dom=candidate_dom, oracle_dom=oracle_dom, oracle_spec=spec
    )
    assert v["matched"] is False
    assert v["divergences"][0]["severity"] == "missing-in-candidate"


def test_rendered_parity_pixel_diff_threshold_triggers(vao_tools):
    """A pixel diff >= 1% adds a divergence regardless of DOM parity."""
    dom = {"tag": "body", "selector": "body", "children": []}
    spec = {"chrome_topology": []}
    v = vao_tools.verify_rendered_parity(
        candidate_dom=dom, oracle_dom=dom, oracle_spec=spec, pixel_diff_pct=0.05
    )
    assert v["matched"] is False
    assert any(d["severity"] == "pixel-divergence" for d in v["divergences"])
    assert v["pixel_diff_pct"] == 0.05


def test_rendered_parity_screenshot_paths_recorded(vao_tools):
    dom = {"tag": "body", "selector": "body", "children": []}
    spec = {"chrome_topology": []}
    v = vao_tools.verify_rendered_parity(
        candidate_dom=dom,
        oracle_dom=dom,
        oracle_spec=spec,
        candidate_screenshot_path="/tmp/cand.png",
        oracle_screenshot_path="/tmp/oracle.png",
    )
    assert v["screenshot_paths"]["candidate"] == "/tmp/cand.png"
    assert v["screenshot_paths"]["oracle"] == "/tmp/oracle.png"


# ===========================================================================
# Determinism — bit-stable output for given inputs
# ===========================================================================


def test_all_tools_write_sorted_keys_for_determinism(vao_tools, tmp_path: Path):
    """The verdict JSON on disk MUST have sorted keys + indent=2, which is
    the determinism contract. Verify against each tool's output."""
    oracle = {"tree": {"x": 1}}
    out = tmp_path / "v.json"
    vao_tools.verify_oracle_match({"tree": {"x": 1}}, oracle, out_path=out)
    raw = out.read_text()
    # Sorted-keys: divergences before match_pct before matched before tool
    # before verdict_at — alphabetical order.
    assert raw.index('"divergences"') < raw.index('"match_pct"') < raw.index('"matched"') < raw.index('"tool"')


# ─────────────────────────────────────────────────────────────────────────────
# v2.12.0 — Unified _is_test_path detector (cross-tool consistency)
# ─────────────────────────────────────────────────────────────────────────────


def test_unified_is_test_path_recognizes_v260_dir_markers(vao_tools):
    """The v2.6.0 audit recognized tests/ / __tests__/ / __mocks__/ /
    test/ / fixtures/ / mocks/ as test paths."""
    for p in ("tests/foo.py", "__tests__/foo.ts", "__mocks__/api.ts",
              "test/foo.py", "fixtures/data.json", "mocks/db.json"):
        assert vao_tools._is_test_path(p), f"path {p!r} should be a test path"


def test_unified_is_test_path_recognizes_v280_filename_suffixes(vao_tools):
    """The v2.8.0 audit recognized _test.py / test.py / _spec.rb basename
    suffixes as test paths. v2.12.0 unification preserved them."""
    for p in ("src/foo_test.py", "src/footest.py", "spec/bar_spec.rb"):
        assert vao_tools._is_test_path(p), f"path {p!r} should be a test path"


def test_unified_is_test_path_recognizes_infix_markers(vao_tools):
    """`.test.` / `.spec.` infixes in the basename signal a test file."""
    for p in ("src/foo.test.ts", "src/bar.spec.ts", "src/foo.test.tsx"):
        assert vao_tools._is_test_path(p), f"path {p!r} should be a test path"


def test_unified_is_test_path_recognizes_pytest_test_prefix(vao_tools):
    """`test_*.py` is the pytest convention; v2.12.0 unification preserved it."""
    assert vao_tools._is_test_path("tests/test_foo.py")
    assert vao_tools._is_test_path("src/test_unit.py")


def test_unified_is_test_path_rejects_production_paths(vao_tools):
    """Production-code paths must not be classified as test paths."""
    for p in ("src/foo.py", "src/foo.ts", "src/Button.stories.tsx",
              "src/api/client.py", "lib/util.js", "docs/foo.md"):
        assert not vao_tools._is_test_path(p), f"path {p!r} should NOT be a test path"


def test_unified_is_test_path_handles_non_string_input(vao_tools):
    """Non-string input returns False without raising (defensive)."""
    assert vao_tools._is_test_path(None) is False
    assert vao_tools._is_test_path(123) is False
    assert vao_tools._is_test_path("") is False


def test_looks_like_test_path_is_alias_of_is_test_path(vao_tools):
    """v2.12.0 — `_looks_like_test_path` is preserved as a deprecated alias
    that delegates to `_is_test_path`. Both must agree on every input."""
    paths = [
        "tests/foo.py", "src/foo.test.ts", "fixtures/data.json", "__mocks__/api.ts",
        "src/foo_test.py", "src/foo.py", "src/bar.spec.ts", "src/Button.stories.tsx",
        "test/foo.py", "mocks/db.json", "spec/bar_spec.rb", "src/api/client.py",
        "src/test_unit.py", "lib/util.js", None, "", 123,
    ]
    for p in paths:
        assert vao_tools._is_test_path(p) == vao_tools._looks_like_test_path(p), (
            f"path {p!r}: _is_test_path and _looks_like_test_path disagree"
        )
