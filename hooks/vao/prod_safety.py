"""VAO prod-safe-test classification (1 tool)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

try:  # package shape: repo root on sys.path
    from hooks.vao.core import _utc_now_iso, _write_verdict
except ImportError:  # hooks/ on sys.path (vao is the package)
    try:
        from vao.core import _utc_now_iso, _write_verdict
    except ImportError:  # hooks/vao/ on sys.path (bare sibling)
        from core import _utc_now_iso, _write_verdict


# v2.17.0 — Annotation forms recognized at the top of every test file.
# Match the first 20 lines; case-insensitive substring match.
_PROD_SAFE_ANNOTATIONS: tuple[str, ...] = (
    "@prod-safe",
    "@prodSafe",
    "@PROD_SAFE",
    "@prod_safe",
)


_NOT_PROD_SAFE_ANNOTATIONS: tuple[str, ...] = (
    "@not-prod-safe",
    "@notProdSafe",
    "@NOT_PROD_SAFE",
    "@not_prod_safe",
)


# Mutation signatures. Hits in production code paths fire
# mutation-in-prod-safe-test (when the file is annotated @prod-safe).
_MUTATION_PATTERNS: tuple[tuple[str, str], ...] = (
    # HTTP POST/PUT/PATCH/DELETE
    ("page-request-post", "page.request.post("),
    ("page-request-put", "page.request.put("),
    ("page-request-patch", "page.request.patch("),
    ("page-request-delete", "page.request.delete("),
    ("axios-post", "axios.post("),
    ("axios-put", "axios.put("),
    ("axios-patch", "axios.patch("),
    ("axios-delete", "axios.delete("),
    ("fetch-method-post", 'method: "POST"'),
    ("fetch-method-put", 'method: "PUT"'),
    ("fetch-method-delete", 'method: "DELETE"'),
    ("fetch-method-patch", 'method: "PATCH"'),
    ("fetch-method-post-single", "method: 'POST'"),
    ("fetch-method-put-single", "method: 'PUT'"),
    ("fetch-method-delete-single", "method: 'DELETE'"),
    # File upload
    ("set-input-files", "page.setInputFiles"),
    ("multipart-form-data", "multipart/form-data"),
    # Form / submit button
    ("submit-button", "button[type=submit]"),
    ("submit-button-double", 'button[type="submit"]'),
    ("form-submit-call", "form.submit("),
    # DB writes
    ("prisma-create", ".create("),
    ("prisma-update", ".update("),
    ("prisma-delete", ".delete("),
    ("prisma-upsert", ".upsert("),
    ("knex-insert", ".insert("),
    ("db-insert", "INSERT INTO"),
    ("db-update-stmt", "UPDATE "),
    ("db-delete-stmt", "DELETE FROM"),
    # Cloud storage
    ("s3-putobject", "PutObject"),
    ("s3-deleteobject", "DeleteObject"),
    ("bucket-upload", "bucket.upload("),
    ("blob-upload", "BlobClient.upload"),
    ("uploader-upload", "uploader.upload("),
    # External side effects
    ("sendgrid-send", "sendgrid.send"),
    ("twilio-create", "messages.create("),
    ("stripe-charge", "charges.create"),
    ("stripe-paymentintent", "PaymentIntent.create"),
)


# Read-only signatures. These do NOT make a test prod-unsafe by themselves;
# they're tracked so a file containing ONLY read patterns can be classified
# `prod-safe` confidently.
_READ_ONLY_PATTERNS: tuple[tuple[str, str], ...] = (
    ("page-goto", "page.goto"),
    ("page-locator", "page.locator"),
    ("page-text-content", ".textContent"),
    ("page-title", ".title("),
    ("page-url", ".url("),
    ("expect-call", "expect("),
    ("to-have-text", "toHaveText"),
    ("to-be-visible", "toBeVisible"),
    ("to-contain", "toContain"),
    ("to-equal", "toEqual"),
    ("to-have-url", "toHaveURL"),
    ("axios-get", "axios.get("),
    ("fetch-method-get", 'method: "GET"'),
    ("prisma-find-unique", ".findUnique("),
    ("prisma-find-many", ".findMany("),
    ("prisma-find-first", ".findFirst("),
    ("knex-select", ".select("),
)


# Hostname/URL patterns that mark a target as PRODUCTION. Match against the
# run_target.url field. Local/dev/staging URLs are EXCLUDED so they don't
# trip the prod-deployment-runs-unsafe-test severity.
_PROD_URL_EXCLUSIONS: tuple[str, ...] = (
    "localhost",
    "127.0.0.1",
    "0.0.0.0",
    "file://",
    ".local",
    "dev.",
    "staging.",
    "stage.",
    "qa.",
    "test.",
    "preview.",
    "preprod.",
    "uat.",
    "demo.",
    "sandbox.",
)


def _scan_first_n_lines_for(content: str, needles: tuple[str, ...], n_lines: int = 20) -> tuple[str, ...]:
    """Return tuple of annotation needles found in the first `n_lines` of `content`."""
    if not isinstance(content, str) or not content:
        return ()
    lines = content.splitlines()[:n_lines]
    head = "\n".join(lines).lower()
    hits = tuple(n for n in needles if n.lower() in head)
    return hits


def _is_prod_url(url: str) -> bool:
    """A URL is a production target if it doesn't match any local/dev/staging
    exclusion AND has a non-empty host."""
    if not isinstance(url, str) or not url:
        return False
    lower = url.lower()
    return not any(p in lower for p in _PROD_URL_EXCLUSIONS)


def _classify_test_file(content: str) -> dict[str, Any]:
    """Auto-classify a test file. Returns:
      {
        annotation: "prod-safe" | "not-prod-safe" | None,
        auto_classification: "prod-safe" | "not-prod-safe" | "ambiguous",
        mutation_hits: list[str],
        readonly_hits: list[str]
      }
    """
    if not isinstance(content, str):
        content = ""
    prod_safe_hits = _scan_first_n_lines_for(content, _PROD_SAFE_ANNOTATIONS)
    not_prod_safe_hits = _scan_first_n_lines_for(content, _NOT_PROD_SAFE_ANNOTATIONS)
    annotation: str | None = None
    if not_prod_safe_hits:
        annotation = "not-prod-safe"
    elif prod_safe_hits:
        annotation = "prod-safe"

    lower = content.lower()
    mut_hits = [sig_id for sig_id, pat in _MUTATION_PATTERNS if pat.lower() in lower]
    ro_hits = [sig_id for sig_id, pat in _READ_ONLY_PATTERNS if pat.lower() in lower]

    if mut_hits:
        auto = "not-prod-safe"
    elif ro_hits:
        auto = "prod-safe"
    else:
        auto = "ambiguous"

    return {
        "annotation": annotation,
        "auto_classification": auto,
        "mutation_hits": mut_hits,
        "readonly_hits": ro_hits,
    }


def _detect_unclassified_test(
    verification_artifact: dict[str, Any],
) -> list[dict[str, Any]]:
    """Every test file MUST carry an annotation in its first 20 lines."""
    test_files = verification_artifact.get("test_files") or []
    gaps: list[dict[str, Any]] = []
    for tf in test_files:
        if not isinstance(tf, dict):
            continue
        path = tf.get("path") or ""
        content = tf.get("content") or ""
        if not isinstance(path, str) or not isinstance(content, str):
            continue
        cls = _classify_test_file(content)
        if cls["annotation"] is None:
            gaps.append({
                "severity": "unclassified-test",
                "test_path": path,
                "suggested_annotation": cls["auto_classification"],
                "mutation_hits": cls["mutation_hits"],
                "readonly_hits": cls["readonly_hits"],
                "evidence": (
                    f"test file {path!r} has no @prod-safe or @not-prod-safe "
                    f"annotation in its first 20 lines. Auto-classifier suggests "
                    f"{cls['auto_classification']!r} based on detected patterns."
                ),
                "remediation": (
                    f"v2.17.0 Prod-safe test classification discipline. Add a "
                    f"top-of-file annotation. Suggested: "
                    f"`// @{cls['auto_classification']}` (or `# @{cls['auto_classification']}` "
                    f"for Python). If the auto-classification is `ambiguous`, "
                    f"review the file manually and pick @prod-safe or @not-prod-safe."
                ),
            })
    return gaps


def _detect_prod_deployment_runs_unsafe(
    verification_artifact: dict[str, Any],
    run_target: dict[str, Any],
) -> list[dict[str, Any]]:
    """When run_target.url is a production URL, every test scheduled to
    run MUST be annotated @prod-safe AND have no mutation signatures."""
    url = run_target.get("url") or ""
    if not _is_prod_url(url):
        return []
    test_files = verification_artifact.get("test_files") or []
    gaps: list[dict[str, Any]] = []
    for tf in test_files:
        if not isinstance(tf, dict):
            continue
        path = tf.get("path") or ""
        content = tf.get("content") or ""
        cls = _classify_test_file(content)
        # Fires if: annotation says not-prod-safe, OR file is unclassified
        # AND auto-classifier sees mutations.
        is_unsafe = (
            cls["annotation"] == "not-prod-safe"
            or (cls["annotation"] is None and cls["mutation_hits"])
        )
        if is_unsafe:
            gaps.append({
                "severity": "prod-deployment-runs-unsafe-test",
                "test_path": path,
                "run_target_url": url,
                "annotation": cls["annotation"],
                "mutation_hits": cls["mutation_hits"][:5],
                "evidence": (
                    f"test {path!r} is scheduled against production URL "
                    f"{url!r} but is annotated/classified as @not-prod-safe."
                ),
                "remediation": (
                    "v2.17.0 Prod-safe test classification discipline. CRITICAL "
                    "safety violation. Either (a) re-target this test to a dev/"
                    "staging URL (URLs matching localhost / 127.0.0.1 / dev.* / "
                    "staging.* / .local / etc.), OR (b) refactor the test to "
                    "remove the mutation patterns and annotate it @prod-safe. "
                    "Running mutations against production is forbidden."
                ),
            })
    return gaps


def _detect_mutation_in_prod_safe_test(
    verification_artifact: dict[str, Any],
) -> list[dict[str, Any]]:
    """A test annotated @prod-safe MUST contain no mutation signatures."""
    test_files = verification_artifact.get("test_files") or []
    gaps: list[dict[str, Any]] = []
    for tf in test_files:
        if not isinstance(tf, dict):
            continue
        path = tf.get("path") or ""
        content = tf.get("content") or ""
        cls = _classify_test_file(content)
        if cls["annotation"] == "prod-safe" and cls["mutation_hits"]:
            gaps.append({
                "severity": "mutation-in-prod-safe-test",
                "test_path": path,
                "annotation": "prod-safe",
                "mutation_hits": cls["mutation_hits"],
                "evidence": (
                    f"test {path!r} is annotated @prod-safe but contains "
                    f"{len(cls['mutation_hits'])} mutation pattern(s): "
                    f"{cls['mutation_hits'][:5]!r}."
                ),
                "remediation": (
                    "v2.17.0 Prod-safe test classification discipline. A test "
                    "annotated @prod-safe cannot contain mutation patterns. "
                    "Either (a) remove the mutation calls (split them into a "
                    "separate @not-prod-safe test that runs only against dev/"
                    "staging), OR (b) re-classify the file as @not-prod-safe."
                ),
            })
    return gaps


def _detect_classification_mismatch(
    verification_artifact: dict[str, Any],
) -> list[dict[str, Any]]:
    """Automatic classification disagrees with the annotation."""
    test_files = verification_artifact.get("test_files") or []
    gaps: list[dict[str, Any]] = []
    for tf in test_files:
        if not isinstance(tf, dict):
            continue
        path = tf.get("path") or ""
        content = tf.get("content") or ""
        cls = _classify_test_file(content)
        if cls["annotation"] is None:
            continue  # unclassified handled by other detector
        if cls["auto_classification"] == "ambiguous":
            continue  # ambiguity isn't a mismatch
        if cls["annotation"] != cls["auto_classification"]:
            gaps.append({
                "severity": "classification-mismatch",
                "test_path": path,
                "annotation": cls["annotation"],
                "auto_classification": cls["auto_classification"],
                "mutation_hits": cls["mutation_hits"][:5],
                "readonly_hits": cls["readonly_hits"][:5],
                "evidence": (
                    f"test {path!r} carries annotation {cls['annotation']!r} but "
                    f"the auto-classifier suggests {cls['auto_classification']!r} "
                    f"based on detected patterns."
                ),
                "remediation": (
                    "v2.17.0 Prod-safe test classification discipline. The "
                    "annotation and the auto-classifier disagree. Either (a) the "
                    "annotation is wrong — update it; or (b) the test contains a "
                    "pattern the classifier mis-reads — refactor the test to "
                    "match its intended classification."
                ),
            })
    return gaps


def verify_test_prod_safety_classification(
    verification_artifact: dict[str, Any] | None = None,
    run_target: dict[str, Any] | None = None,
    out_path: Path | str | None = None,
) -> dict[str, Any]:
    """v2.17.0 Layer-3 tool — verify every test file is properly classified
    `@prod-safe` or `@not-prod-safe`, AND that no `@not-prod-safe` test is
    scheduled against a production URL.

    4 named severities:
      1. unclassified-test — file has no annotation
      2. prod-deployment-runs-unsafe-test — run_target is prod URL + test
         is @not-prod-safe (CRITICAL safety violation)
      3. mutation-in-prod-safe-test — file annotated @prod-safe contains
         mutation patterns
      4. classification-mismatch — annotation disagrees with auto-classifier

    Trivially passes when verification_artifact has no test_files AND
    run_target is empty.
    """
    artifact = verification_artifact or {}
    target = run_target or {}
    gaps: list[dict[str, Any]] = []
    gaps += _detect_unclassified_test(artifact)
    gaps += _detect_prod_deployment_runs_unsafe(artifact, target)
    gaps += _detect_mutation_in_prod_safe_test(artifact)
    gaps += _detect_classification_mismatch(artifact)

    verdict = {
        "tool": "verify-test-prod-safety-classification",
        "valid": len(gaps) == 0,
        "gaps": gaps,
        "verdict_at": _utc_now_iso(),
    }
    return _write_verdict(verdict, out_path)
