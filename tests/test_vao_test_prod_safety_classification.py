"""Tests for the v2.17.0 Layer 3 tool: verify_test_prod_safety_classification.

Covers the 4 named severities (`unclassified-test`, `mutation-in-prod-safe-test`,
`classification-mismatch`, `prod-deployment-runs-unsafe-test`), helper
detection paths (annotation parsing, mutation-pattern scan, read-only signature,
prod-URL classification), fixture round-trip, and determinism (sorted-keys +
indent=2 stable output).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from hooks.vao_tools import (
    _MUTATION_PATTERNS,
    _NOT_PROD_SAFE_ANNOTATIONS,
    _PROD_SAFE_ANNOTATIONS,
    _PROD_URL_EXCLUSIONS,
    _READ_ONLY_PATTERNS,
    _classify_test_file,
    _is_prod_url,
    _scan_first_n_lines_for,
    verify_test_prod_safety_classification,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE = REPO_ROOT / "tests" / "fixtures" / "vao" / "prod-safe-test-classification-required.json"


# ---- module constants exported ----


def test_prod_safe_annotation_patterns_present() -> None:
    assert "@prod-safe" in _PROD_SAFE_ANNOTATIONS
    assert "@prodSafe" in _PROD_SAFE_ANNOTATIONS
    assert "@PROD_SAFE" in _PROD_SAFE_ANNOTATIONS
    assert "@prod_safe" in _PROD_SAFE_ANNOTATIONS


def test_not_prod_safe_annotation_patterns_present() -> None:
    assert "@not-prod-safe" in _NOT_PROD_SAFE_ANNOTATIONS
    assert "@notProdSafe" in _NOT_PROD_SAFE_ANNOTATIONS
    assert "@NOT_PROD_SAFE" in _NOT_PROD_SAFE_ANNOTATIONS
    assert "@not_prod_safe" in _NOT_PROD_SAFE_ANNOTATIONS


def test_mutation_patterns_include_http_methods() -> None:
    joined = " ".join(p for _, p in _MUTATION_PATTERNS)
    for needle in ("page.request.post", "page.request.put", "page.request.patch", "page.request.delete"):
        assert needle in joined


def test_mutation_patterns_include_db_writes() -> None:
    joined = " ".join(p for _, p in _MUTATION_PATTERNS)
    for needle in (".create(", ".update(", ".delete(", "INSERT INTO", "UPDATE ", "DELETE FROM"):
        assert needle in joined


def test_mutation_patterns_include_external_sends() -> None:
    names = " ".join(n for n, _ in _MUTATION_PATTERNS).lower()
    for needle in ("sendgrid", "stripe", "twilio", "s3"):
        assert needle in names


def test_read_only_patterns_include_safe_ops() -> None:
    joined = " ".join(p for _, p in _READ_ONLY_PATTERNS)
    for needle in ("page.goto", "page.locator", "expect(", "findUnique", "axios.get(", "method: \"GET\""):
        assert needle in joined


def test_prod_url_exclusions_include_localhost() -> None:
    joined = " ".join(_PROD_URL_EXCLUSIONS)
    for needle in ("localhost", "127.0.0.1", "dev.", "staging.", ".local"):
        assert needle in joined


# ---- helper: is_prod_url ----


@pytest.mark.parametrize(
    "url,expected",
    [
        ("https://heirship-app.example.com", True),
        ("https://app.example.com", True),
        ("http://localhost:3000", False),
        ("http://127.0.0.1:8080", False),
        ("https://dev.example.com", False),
        ("https://staging.example.com", False),
        ("http://example.local", False),
    ],
)
def test_is_prod_url(url: str, expected: bool) -> None:
    assert _is_prod_url(url) is expected


# ---- helper: scan_first_n_lines_for ----


def test_scan_first_n_lines_for_finds_annotation() -> None:
    content = "// @prod-safe\nimport { test } from 'playwright';\ntest('foo', ...);"
    hits = _scan_first_n_lines_for(content, _PROD_SAFE_ANNOTATIONS, n_lines=5)
    assert "@prod-safe" in hits


def test_scan_first_n_lines_for_misses_when_outside_window() -> None:
    body = "import a;\nimport b;\nimport c;\nimport d;\nimport e;\nimport f;\n// @prod-safe\n"
    hits = _scan_first_n_lines_for(body, _PROD_SAFE_ANNOTATIONS, n_lines=5)
    assert hits == ()


# ---- classifier ----


def test_classify_prod_safe_with_annotation() -> None:
    content = "// @prod-safe\nawait page.goto('/');\nawait expect(page).toHaveURL('/');"
    cls = _classify_test_file(content)
    assert cls["annotation"] == "prod-safe"
    assert cls["auto_classification"] == "prod-safe"


def test_classify_not_prod_safe_with_annotation() -> None:
    content = "// @not-prod-safe\nawait page.request.post('/api/x');"
    cls = _classify_test_file(content)
    assert cls["annotation"] == "not-prod-safe"
    assert cls["auto_classification"] == "not-prod-safe"


def test_classify_unclassified() -> None:
    content = "import { test } from 'playwright';\ntest('foo', async ({ page }) => { await page.goto('/'); });"
    cls = _classify_test_file(content)
    assert cls["annotation"] is None


def test_classify_mismatch_prod_safe_but_mutates() -> None:
    content = "// @prod-safe\nawait page.request.post('/api/users', { data: {x: 1} });"
    cls = _classify_test_file(content)
    assert cls["annotation"] == "prod-safe"
    assert cls["auto_classification"] == "not-prod-safe"
    assert cls["mutation_hits"]


# ---- detector: unclassified-test ----


def test_detect_unclassified_test() -> None:
    artifact = {
        "feature_kind": "test-suite-classification",
        "test_files": [
            {"path": "tests/foo.spec.ts", "content": "test('a', async ({ page }) => { await page.goto('/'); });"},
        ],
    }
    result = verify_test_prod_safety_classification(artifact, {"url": "https://example.com"})
    assert result["valid"] is False
    sevs = [g["severity"] for g in result["gaps"]]
    assert "unclassified-test" in sevs


# ---- detector: mutation-in-prod-safe-test + classification-mismatch ----


def test_detect_mutation_in_prod_safe_test() -> None:
    artifact = {
        "feature_kind": "test-suite-classification",
        "test_files": [
            {
                "path": "tests/mutate.spec.ts",
                "content": "// @prod-safe\nawait page.request.post('/api/x');",
            }
        ],
    }
    result = verify_test_prod_safety_classification(artifact, {"url": "https://example.com"})
    assert result["valid"] is False
    sevs = sorted({g["severity"] for g in result["gaps"]})
    assert "mutation-in-prod-safe-test" in sevs
    assert "classification-mismatch" in sevs


# ---- detector: prod-deployment-runs-unsafe-test ----


def test_detect_prod_deployment_runs_unsafe_test() -> None:
    artifact = {
        "feature_kind": "test-suite-classification",
        "test_files": [
            {
                "path": "tests/upload.spec.ts",
                "content": "// @not-prod-safe\nawait page.setInputFiles('input', '/tmp/x.pdf');",
            }
        ],
    }
    result = verify_test_prod_safety_classification(
        artifact, {"url": "https://app.example.com", "environment_label": "production"}
    )
    assert result["valid"] is False
    sevs = [g["severity"] for g in result["gaps"]]
    assert "prod-deployment-runs-unsafe-test" in sevs


def test_does_not_fire_prod_deployment_on_localhost() -> None:
    artifact = {
        "feature_kind": "test-suite-classification",
        "test_files": [
            {
                "path": "tests/upload.spec.ts",
                "content": "// @not-prod-safe\nawait page.setInputFiles('input', '/tmp/x.pdf');",
            }
        ],
    }
    result = verify_test_prod_safety_classification(artifact, {"url": "http://localhost:3000"})
    assert all(g["severity"] != "prod-deployment-runs-unsafe-test" for g in result["gaps"])


# ---- clean pass ----


def test_clean_prod_safe_against_prod_passes() -> None:
    artifact = {
        "feature_kind": "test-suite-classification",
        "test_files": [
            {
                "path": "tests/render.spec.ts",
                "content": "// @prod-safe\nawait page.goto('/'); await expect(page.locator('h1')).toBeVisible();",
            }
        ],
    }
    result = verify_test_prod_safety_classification(artifact, {"url": "https://app.example.com"})
    assert result["valid"] is True
    assert result["gaps"] == []


def test_clean_not_prod_safe_against_dev_passes() -> None:
    artifact = {
        "feature_kind": "test-suite-classification",
        "test_files": [
            {
                "path": "tests/mutate.spec.ts",
                "content": "// @not-prod-safe\nawait page.request.post('/api/x');",
            }
        ],
    }
    result = verify_test_prod_safety_classification(artifact, {"url": "http://localhost:3000"})
    assert result["valid"] is True
    assert result["gaps"] == []


# ---- fixture round-trip ----


def test_canonical_fixture_bad_fires_all_4_severities() -> None:
    fx = json.loads(FIXTURE.read_text(encoding="utf-8"))
    result = verify_test_prod_safety_classification(fx["verification_artifact"], fx["run_target"])
    assert result["valid"] is False
    sevs = sorted({g["severity"] for g in result["gaps"]})
    assert sevs == sorted(fx["expected_verdict_for_misverification"]["expected_unique_severities"])


def test_canonical_fixture_corrected_passes() -> None:
    fx = json.loads(FIXTURE.read_text(encoding="utf-8"))
    result = verify_test_prod_safety_classification(
        fx["_corrected_verification_artifact"], fx["_corrected_run_target"]
    )
    assert result["valid"] is True
    assert result["gaps"] == []


# ---- determinism ----


def test_output_is_deterministic_sorted_keys_indent_2() -> None:
    fx = json.loads(FIXTURE.read_text(encoding="utf-8"))
    a = verify_test_prod_safety_classification(fx["verification_artifact"], fx["run_target"])
    b = verify_test_prod_safety_classification(fx["verification_artifact"], fx["run_target"])
    assert json.dumps(a, sort_keys=True, indent=2) == json.dumps(b, sort_keys=True, indent=2)


def test_output_carries_tool_name() -> None:
    fx = json.loads(FIXTURE.read_text(encoding="utf-8"))
    result = verify_test_prod_safety_classification(fx["verification_artifact"], fx["run_target"])
    assert result["tool"] == "verify-test-prod-safety-classification"


def test_output_carries_verdict_at_iso_string() -> None:
    fx = json.loads(FIXTURE.read_text(encoding="utf-8"))
    result = verify_test_prod_safety_classification(fx["verification_artifact"], fx["run_target"])
    assert "verdict_at" in result
    assert isinstance(result["verdict_at"], str)
    assert "T" in result["verdict_at"]  # ISO 8601


# ---- gap structure ----


def test_each_gap_carries_required_fields() -> None:
    fx = json.loads(FIXTURE.read_text(encoding="utf-8"))
    result = verify_test_prod_safety_classification(fx["verification_artifact"], fx["run_target"])
    for g in result["gaps"]:
        assert "severity" in g
        assert "test_path" in g
        assert "evidence" in g
        assert "remediation" in g


# ---- empty/no-op behavior ----


def test_empty_test_files_passes() -> None:
    artifact = {"feature_kind": "test-suite-classification", "test_files": []}
    result = verify_test_prod_safety_classification(artifact, {"url": "https://example.com"})
    assert result["valid"] is True
    assert result["gaps"] == []


def test_missing_feature_kind_returns_passing_noop() -> None:
    artifact = {"test_files": [{"path": "tests/foo.spec.ts", "content": "// @prod-safe\nawait page.goto('/');"}]}
    result = verify_test_prod_safety_classification(artifact, {"url": "https://example.com"})
    assert result["valid"] is True


# ---- out_path persistence (optional sidecar) ----


def test_out_path_writes_sidecar(tmp_path: Path) -> None:
    out = tmp_path / "verdict.json"
    fx = json.loads(FIXTURE.read_text(encoding="utf-8"))
    verify_test_prod_safety_classification(
        fx["verification_artifact"], fx["run_target"], out_path=str(out)
    )
    assert out.exists()
    persisted = json.loads(out.read_text(encoding="utf-8"))
    assert persisted["tool"] == "verify-test-prod-safety-classification"
