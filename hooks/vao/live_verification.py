"""VAO verified-live + proxy-element family (2 tools).

Owns the localhost union constant ``_LOCAL_ENV_HOST_PATTERNS`` (R1b,
v3.10.0) — the single source the former v2.2.0 list and v2.13.0
``_LOCAL_ENV_HOST_PATTERNS`` both fold into. ``persona.py`` imports it
from here; the facade re-exports it under the same name.
"""

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


# R1b (v3.10.0) — the localhost / non-deployed-URL union. The single source
# of truth that the former v2.2.0 list (verify_live_verification_claim's
# _NON_DEPLOYED_URL_MARKERS) and the v2.13.0 _LOCAL_ENV_HOST_PATTERNS
# (persona _is_local_env_url) both fold into. The facade re-exports this under
# the test-referenced name _LOCAL_ENV_HOST_PATTERNS; persona.py imports it.
_LOCAL_ENV_HOST_PATTERNS: tuple[str, ...] = (
    "localhost",
    "127.0.0.1",
    "0.0.0.0",
    "file://",
    ".local",
    "::1",
    "host.docker.internal",
    "://localhost",
    "://127.",
)


# Coordinate pairs / selectors / patterns that indicate the agent's "test"
# clicked an empty region instead of the bug-exposing element. Each pattern
# is the smoking gun for the gesture-substitution failure mode.
_EMPTY_REGION_COORD_THRESHOLD = 16  # pixels — anything <= this from (0,0) is suspect


_EMPTY_REGION_SELECTORS = (
    "body",
    "[role=\"presentation\"]",
    "[role='presentation']",
    "[data-backdrop]",
    "[data-overlay]",
    ".backdrop",
    ".overlay",
)


# Demo-matter setups that pre-populate state. When the bug requires a blank
# state to manifest, loading one of these is prefill-masking.
_DEMO_MATTER_MARKERS = (
    "carter",
    "smith-demo",
    "demo-matter",
    "pre-populated",
    "fixture-matter",
    "seeded-",
)


def _is_empty_region_click(target: dict[str, Any]) -> bool:
    """Decide whether a click_target dict refers to an empty-region click.
    A click is an empty-region click when either:
      - Its coordinate is within _EMPTY_REGION_COORD_THRESHOLD of (0, 0)
      - Its selector matches one of the known empty-region selectors AND
        the click was NOT explicitly an intended-backdrop close gesture
        (the artifact carries `intended_backdrop_close: true`)
    """
    if not isinstance(target, dict):
        return False
    coord = target.get("coord")
    if isinstance(coord, list) and len(coord) == 2 and all(isinstance(c, (int, float)) for c in coord):
        x, y = coord
        if abs(x) <= _EMPTY_REGION_COORD_THRESHOLD and abs(y) <= _EMPTY_REGION_COORD_THRESHOLD:
            return True
    selector = target.get("selector")
    if isinstance(selector, str):
        normalized = selector.strip().lower()
        for pattern in _EMPTY_REGION_SELECTORS:
            if normalized == pattern.lower():
                if not target.get("intended_backdrop_close"):
                    return True
                break
    return False


def _detect_self_verification_loop(artifact: dict[str, Any]) -> dict[str, Any] | None:
    """Detect the self-authored-unit-test failure mode.

    Returns a gap dict if the test was created within the current fix
    session AND the test's assertion contains a substring also present in
    the fix's git diff. Returns None otherwise.

    The artifact carries:
      - `test_source_created_at`: ISO 8601 string
      - `fix_session_started_at`: ISO 8601 string
      - `test_assertions[]`: list of assertion-source strings
      - `fix_diff_strings[]`: list of strings extracted from the fix's git diff
    """
    created_at = artifact.get("test_source_created_at")
    session_start = artifact.get("fix_session_started_at")
    if not isinstance(created_at, str) or not isinstance(session_start, str):
        return None
    # String comparison works correctly for ISO 8601 UTC.
    if created_at < session_start:
        return None  # test was authored before the fix session — independent
    assertions = artifact.get("test_assertions") or []
    diff_strings = artifact.get("fix_diff_strings") or []
    if not assertions or not diff_strings:
        return None
    for assertion in assertions:
        if not isinstance(assertion, str):
            continue
        for diff_str in diff_strings:
            if not isinstance(diff_str, str) or len(diff_str) < 6:
                continue
            if diff_str in assertion:
                return {
                    "severity": "self-verification-loop",
                    "evidence": f"test assertion contains fix-diff substring {diff_str!r}; "
                                f"test_source_created_at={created_at} >= fix_session_started_at={session_start}",
                    "remediation": "Use the Phase B2 bug-replicator's reproduction artifact as the test. "
                                  "Do not author a fresh test in the fix session whose assertion mirrors "
                                  "the fix's own code.",
                }
    return None


def _detect_prefill_masking(artifact: dict[str, Any], bug: dict[str, Any]) -> dict[str, Any] | None:
    """Detect the pre-populated-state-masking failure mode.

    Returns a gap dict if:
      - The setup_actions[] load a known demo matter, AND
      - The bug requires a blank/empty state (`requires_blank_state: true`), AND
      - The trace shows a saturated state (`observed_state` includes
        `N/N answered` / `100%` / `all-complete` / similar markers).
    """
    setup = artifact.get("setup_actions") or []
    setup_text = " ".join(s.lower() if isinstance(s, str) else "" for s in setup)
    loads_demo = any(marker in setup_text for marker in _DEMO_MATTER_MARKERS)
    if not loads_demo:
        return None
    if not bug.get("requires_blank_state"):
        return None
    observed = artifact.get("observed_state") or ""
    if not isinstance(observed, str):
        observed = str(observed)
    saturation_markers = ("n/n answered", "all-complete", "all complete", "100%", "100 %", "n of n")
    observed_lower = observed.lower()
    saturated = any(m in observed_lower for m in saturation_markers)
    # Also match the explicit "X/Y" pattern where X == Y
    import re as _re
    for match in _re.finditer(r"(\d+)\s*/\s*(\d+)\s*(?:answered|complete|filled)", observed_lower):
        x, y = int(match.group(1)), int(match.group(2))
        if x == y and y > 0:
            saturated = True
            break
    if not saturated:
        return None
    matter_name = "demo matter"
    for marker in _DEMO_MATTER_MARKERS:
        if marker in setup_text:
            matter_name = marker
            break
    return {
        "severity": "prefill-masking",
        "evidence": f"setup loads {matter_name!r}; bug.requires_blank_state=true; "
                    f"observed_state shows saturation ({observed[:80]!r})",
        "remediation": "Drive the test to the bug-exposing state explicitly before asserting. "
                      "Use a blank/empty matter or navigate to a genuinely-blank step before "
                      "the bug's trigger gesture.",
    }


# The 6 canonical external-system kinds. Features whose `feature_kind` is in
# this set MUST carry an `external_state_assertion` block asserting against
# the external system's own observable downstream state.
_EXTERNAL_SYSTEM_FEATURE_KINDS: tuple[str, ...] = (
    "email",
    "payment",
    "push",
    "webhook-outbound",
    "oauth",
    "blob-storage",
)


# Per-kind list of forbidden internal-proxy assertion targets. If an
# assertion in `assertions[]` references one of these substrings AND
# `external_state_assertion` is missing, the smoking gun is named in the
# gap's `evidence` field. Substring match is case-insensitive.
_FORBIDDEN_PROXY_ASSERTION_FIELDS: dict[str, tuple[str, ...]] = {
    "email": (
        "email_dispatch_status",
        "sendgrid.statusCode",
        "sendgridResponse.statusCode",
        ".body.message_id",
        "Invite sent",  # the hardcoded UI text from the heirship case
    ),
    "payment": (
        "intent.status",
        "client_secret",
        "paymentIntent.status",
        "stripeResponse.statusCode",
    ),
    "push": (
        "message_id",
        "fcm_response.success",
        "apns_response.id",
    ),
    "webhook-outbound": (
        "trigger.statusCode",
        "we returned 200",
        "200 to the trigger",
    ),
    "oauth": (
        "access_token",
        "token_endpoint_response.statusCode",
    ),
    "blob-storage": (
        "upload_response.statusCode",
        "putObject.success",
    ),
}


def _detect_external_state_not_asserted(artifact: dict[str, Any]) -> dict[str, Any] | None:
    """Detect the v2.4.0 external-state-not-asserted failure mode.

    Returns a gap dict if:
      - `feature_kind` is in the documented external-system list, AND
      - EITHER `external_state_assertion` is missing/empty/not-a-dict, OR
        `external_state_assertion.passes` is not exactly True, OR
        any `assertions[]` entry references a known internal-proxy substring
        for this feature_kind AND `external_state_assertion` is missing.

    Returns None when the feature is not external-system OR a valid
    `external_state_assertion` block with `passes: true` is present.
    """
    feature_kind = artifact.get("feature_kind")
    if not isinstance(feature_kind, str):
        return None
    feature_kind = feature_kind.strip().lower()
    if feature_kind not in _EXTERNAL_SYSTEM_FEATURE_KINDS:
        return None

    esa = artifact.get("external_state_assertion")
    has_valid_esa = (
        isinstance(esa, dict)
        and esa.get("passes") is True
        and isinstance(esa.get("external_system"), str)
        and esa.get("external_system").strip()
    )

    # Per-kind proxy-substring check on assertions[] — name the smoking gun
    # when present even if the agent omitted external_state_assertion.
    forbidden = _FORBIDDEN_PROXY_ASSERTION_FIELDS.get(feature_kind, ())
    proxy_hits: list[str] = []
    for assertion in artifact.get("assertions", []) or []:
        if not isinstance(assertion, str):
            continue
        lower_assertion = assertion.lower()
        for proxy_field in forbidden:
            if proxy_field.lower() in lower_assertion:
                proxy_hits.append(proxy_field)

    if has_valid_esa and not proxy_hits:
        return None  # the artifact correctly cites external observable state

    if has_valid_esa and proxy_hits:
        # Even with a valid external_state_assertion, a forbidden-proxy hit
        # is informational but not a gap. Skip.
        return None

    # No valid external_state_assertion — that's the gap.
    base_evidence = (
        f"feature_kind={feature_kind!r} is an external-system kind; "
        f"verification_artifact.external_state_assertion is missing OR "
        f"passes != true"
    )
    if proxy_hits:
        base_evidence += (
            f"; assertions[] reference forbidden internal-proxy field(s) "
            f"{proxy_hits!r}"
        )
    remediation_table = {
        "email": "Query SendGrid Activity API for event=delivered, OR check the "
                 "recipient's inbox directly (Gmail / IMAP / Mailpit).",
        "payment": "Query Stripe API for Charge.paid=true + "
                   "balance_transaction.status=available, NOT intent.status.",
        "push": "Capture the device-side onMessage handler payload, NOT FCM's "
                "message_id ack.",
        "webhook-outbound": "Inspect the recipient's actually-received-payload "
                            "log, NOT the upstream trigger's 200.",
        "oauth": "Use the access_token against the resource server's GET /me "
                 "(or equivalent), NOT just the token endpoint's 200.",
        "blob-storage": "HEAD the uploaded object and verify ETag, NOT the "
                        "upload response's 200.",
    }
    return {
        "severity": "external-state-not-asserted",
        "evidence": base_evidence,
        "remediation": (
            "v2.4.0 External-state assertion discipline. "
            + remediation_table.get(feature_kind, "Assert against the external "
                                                  "system's own observable downstream state.")
        ),
    }


def _detect_missing_evidence_artifact(artifact: dict[str, Any]) -> dict[str, Any] | None:
    """Detect the v2.4.0 missing-evidence-artifact failure mode.

    Returns a gap dict if:
      - `evidence_artifact_path` field is missing OR not a string OR empty, OR
      - The path does not resolve on disk, OR
      - The path is a directory (must be a file), OR
      - The file is 0 bytes.

    Returns None when a valid on-disk file > 0 bytes is cited.
    """
    path_str = artifact.get("evidence_artifact_path")
    if not isinstance(path_str, str) or not path_str.strip():
        return {
            "severity": "missing-evidence-artifact",
            "evidence": "verification_artifact.evidence_artifact_path is missing or empty",
            "remediation": "v2.4.0 Evidence-artifact citation discipline. "
                          "Every verified-live claim MUST cite a concrete on-disk artifact "
                          "(Playwright trace .zip, .har / .json network log, screenshot, "
                          "external-API response dump JSON, etc.). The agent's prose "
                          "assertions[] list is no longer accepted as evidence the assertion "
                          "was made.",
        }
    path_obj = Path(path_str)
    if not path_obj.exists():
        return {
            "severity": "missing-evidence-artifact",
            "evidence": f"evidence_artifact_path={path_str!r} does not exist on disk",
            "remediation": "Verify the artifact was actually written by your test run. "
                          "If the path is correct but the file doesn't exist, the test "
                          "did not produce the artifact (e.g., Playwright trace recording "
                          "wasn't enabled).",
        }
    if path_obj.is_dir():
        return {
            "severity": "missing-evidence-artifact",
            "evidence": f"evidence_artifact_path={path_str!r} is a directory; must be a file",
            "remediation": "Point to a single artifact file, not a directory. "
                          "If you have multiple artifacts, pick the canonical one (Playwright "
                          "trace ZIP or external-API response JSON).",
        }
    try:
        size = path_obj.stat().st_size
    except OSError:
        size = 0
    if size <= 0:
        return {
            "severity": "missing-evidence-artifact",
            "evidence": f"evidence_artifact_path={path_str!r} is empty (0 bytes)",
            "remediation": "The artifact exists but is empty — the test likely failed "
                          "before writing data. Re-run the test and confirm the artifact "
                          "is populated.",
        }
    return None


def verify_live_verification_claim(
    verification_artifact: dict[str, Any] | None = None,
    bug_description: dict[str, Any] | None = None,
    out_path: Path | str | None = None,
) -> dict[str, Any]:
    """v2.2.0 + v2.4.0 Layer-3 tool — verify that a "verified live" claim is valid.

    Checks the verification artifact against the 8 named gap severities:
      1. gesture-substitution — empty-region click instead of user gesture (v2.2.0)
      2. self-verification-loop — agent wrote the test that asserts its own fix (v2.2.0)
      3. prefill-masking — pre-populated state where the bug can't manifest (v2.2.0)
      4. missing-screenshot — no captured after-state evidence (v2.2.0)
      5. missing-deployed-url — test against localhost / no URL (v2.2.0)
      6. missing-semantic-assertion — no observable-behavior check (v2.2.0)
      7. external-state-not-asserted — assertion against internal proxy when
         feature touches an external system (v2.4.0)
      8. missing-evidence-artifact — no on-disk artifact citation (v2.4.0)

    Args:
      verification_artifact: dict carrying click_targets[], setup_actions[],
        test_source_created_at, test_assertions[], fix_diff_strings[],
        observed_state, screenshot_path, target_url, fix_session_started_at,
        assertions[].
      bug_description: dict carrying the bug summary, requires_blank_state,
        gesture_pattern, etc.
      out_path: optional path to write the verdict JSON.

    Returns::

        {
          "tool": "verify-live-verification-claim",
          "valid": bool,
          "gaps": [{"severity", "evidence", "remediation"}],
          "verdict_at": "<ISO 8601 UTC>"
        }

    Deterministic / bit-stable output for given inputs (sorted-keys + indent=2).
    """
    artifact = verification_artifact or {}
    bug = bug_description or {}
    gaps: list[dict[str, Any]] = []

    # Gesture substitution
    for target in artifact.get("click_targets", []) or []:
        if _is_empty_region_click(target):
            gaps.append({
                "severity": "gesture-substitution",
                "evidence": f"click target {target!r} is an empty-region click "
                            f"(coord near origin OR backdrop/body selector without intended_backdrop_close)",
                "remediation": "Click the bug-exposing element directly (the field, button, or control "
                              "a user would actually click), not the dropdown's own backdrop or a page "
                              "corner. The fix-session memory rule: never test by clicking nothing.",
            })
            break  # one gesture-substitution gap is enough; flag and stop

    # Self-verification loop
    loop_gap = _detect_self_verification_loop(artifact)
    if loop_gap:
        gaps.append(loop_gap)

    # Prefill masking
    masking_gap = _detect_prefill_masking(artifact, bug)
    if masking_gap:
        gaps.append(masking_gap)

    # Missing deployed URL
    target_url = artifact.get("target_url")
    if not isinstance(target_url, str) or not target_url.strip():
        gaps.append({
            "severity": "missing-deployed-url",
            "evidence": "verification_artifact.target_url is missing or empty",
            "remediation": "Run the verification against a real HTTPS URL on the live deployed "
                          "environment. Record it in target_url.",
        })
    else:
        url_lower = target_url.lower()
        if any(marker in url_lower for marker in _LOCAL_ENV_HOST_PATTERNS):
            gaps.append({
                "severity": "missing-deployed-url",
                "evidence": f"target_url={target_url!r} points to a non-deployed environment "
                            f"(localhost / 127.0.0.1 / file:// / similar)",
                "remediation": "A 'verified live' claim requires the deployed environment, not local "
                              "dev. Re-run against the live HTTPS URL.",
            })

    # Missing screenshot
    screenshot = artifact.get("screenshot_path")
    if not isinstance(screenshot, str) or not screenshot.strip():
        gaps.append({
            "severity": "missing-screenshot",
            "evidence": "verification_artifact.screenshot_path is missing or null",
            "remediation": "Capture a screenshot of the after-state and record the path in "
                          "screenshot_path.",
        })

    # Missing semantic assertion
    assertions = artifact.get("assertions") or []
    if not assertions:
        gaps.append({
            "severity": "missing-semantic-assertion",
            "evidence": "verification_artifact.assertions[] is empty — the test made no observable-"
                        "behavior check (isDisabled / role count / text content / URL change)",
            "remediation": "Add at least one assertion on the OBSERVABLE behavior. The test must "
                          "check what a user would notice, not the agent's assumed internal state.",
        })

    # v2.4.0 — External-state assertion (only fires when feature_kind is in
    # the external-system list)
    esa_gap = _detect_external_state_not_asserted(artifact)
    if esa_gap:
        gaps.append(esa_gap)

    # v2.4.0 — Evidence-artifact citation (only fires when the artifact's
    # evidence_artifact_path field is populated by the caller; pre-v2.4.0
    # callers that don't supply the field don't fire the severity, preserving
    # backwards compatibility. To make this discipline stricter — required by
    # default — flip the if-guard to always run.)
    if "evidence_artifact_path" in artifact:
        ea_gap = _detect_missing_evidence_artifact(artifact)
        if ea_gap:
            gaps.append(ea_gap)

    verdict = {
        "tool": "verify-live-verification-claim",
        "valid": len(gaps) == 0,
        "gaps": gaps,
        "verdict_at": _utc_now_iso(),
    }
    return _write_verdict(verdict, out_path)


_PROXY_SUBSTITUTION_MARKERS = (
    # Substitution language
    "measured a different element",
    "off that proxy",
    "off a proxy",
    "as a proxy",
    "used as a proxy",
    "via a proxy",
    "as the proxy",
    "the proxy element",
    # Fallback language
    "fell back to measuring",
    "the closest measurable",
    "the surrounding element",
    "the sibling element",
    "the nearest measurable",
    "approximated using",
    "used the label instead",
    "label instead of the",
    # Confession language
    "did not visually confirm",
    "wrongly reported as passing",
    "i wrongly reported",
    "passing off",
    "claimed pass on the",
)


_UNREACHABLE_STATE_MARKERS = (
    "couldn't reach",
    "could not reach",
    "unable to reach",
    "could not trigger",
    "couldn't trigger",
    "no fixture had",
    "no test data with",
    "seed data didn't include",
    "the state was never produced",
    "never observed the",
    "every X had Y",  # template marker — actual strings detected via regex below
    "every record had",
    "every day had",
    "every row had",
)


_REACHABILITY_NOT_REACHED_VALUES = (
    "unreachable",
    "state-not-triggered",
    "fixture-did-not-produce-target-state",
    "target-element-not-found",
    "cannot-verify-without-deploy",
)


def _normalize_selector(sel: Any) -> str:
    """Normalize a selector for structural comparison: lowercase, collapse
    whitespace, sort comma-separated alternates."""
    if not isinstance(sel, str):
        return ""
    # collapse internal whitespace + lowercase + strip
    parts = [p.strip().lower() for p in sel.split(",")]
    parts = [" ".join(p.split()) for p in parts if p]
    parts.sort()
    return ",".join(parts)


def _selectors_match(target: Any, measured: Any) -> bool:
    """True iff target and measured selectors are structurally equivalent."""
    if target is None and measured is None:
        return True
    if target is None or measured is None:
        return False
    return _normalize_selector(target) == _normalize_selector(measured)


def _semantic_labels_match(target: Any, measured: Any) -> bool:
    """True iff semantic labels are structurally equivalent (case + whitespace
    + punctuation insensitive)."""
    if target is None and measured is None:
        return True
    if target is None or measured is None:
        return False
    if not isinstance(target, str) or not isinstance(measured, str):
        return False

    def norm(s: str) -> str:
        return " ".join(s.lower().replace("-", " ").replace("_", " ").split())

    return norm(target) == norm(measured)


def _detect_proxy_element_substituted(
    verification_artifact: dict[str, Any],
) -> list[dict[str, Any]]:
    target_sel = verification_artifact.get("target_element_selector")
    measured_sel = verification_artifact.get("measured_element_selector")
    verdict = (verification_artifact.get("verdict") or "").lower()
    # Only fire when verdict is positive — substitution on a non-passing
    # verdict is just notes, not fraud.
    if verdict not in ("passing", "pass", "bug-resolved", "resolved", "verified", "✅"):
        return []
    if target_sel is None and measured_sel is None:
        return []  # no claim; the discipline doesn't apply
    if _selectors_match(target_sel, measured_sel):
        return []
    return [{
        "severity": "proxy-element-substituted",
        "target_element_selector": target_sel,
        "measured_element_selector": measured_sel,
        "verdict": verdict,
        "evidence": (
            f"target_element_selector ({target_sel!r}) and "
            f"measured_element_selector ({measured_sel!r}) do not match, but "
            f"verdict is {verdict!r}. Substituting any proxy element to claim "
            f"PASS is forbidden under v2.21.0."
        ),
        "remediation": (
            "v2.21.0 no proxy-element verification discipline. Either (a) "
            "re-run the verification against the actual target element "
            "(target_element_selector), OR (b) escalate via SR with "
            "origin.kind='target-state-unreachable-needs-seed-data' so the "
            "responsible team seeds the missing state and the verification "
            "can re-run."
        ),
    }]


def _detect_unreachable_state_not_escalated(
    verification_artifact: dict[str, Any],
) -> list[dict[str, Any]]:
    reachability = (verification_artifact.get("reachability_status") or "").lower()
    verdict = (verification_artifact.get("verdict") or "").lower()
    if reachability in ("", "reached"):
        return []
    if reachability not in _REACHABILITY_NOT_REACHED_VALUES:
        return []
    if verdict not in ("passing", "pass", "bug-resolved", "resolved", "verified", "✅"):
        return []  # not passing — the discipline only catches false-pass
    return [{
        "severity": "unreachable-state-not-escalated",
        "reachability_status": reachability,
        "verdict": verdict,
        "evidence": (
            f"reachability_status={reachability!r} but verdict={verdict!r}. "
            f"The target state was not reached; the verification did not "
            f"happen; verdict CANNOT be pass under v2.21.0."
        ),
        "remediation": (
            "v2.21.0 no proxy-element verification discipline. Change verdict "
            "to 'cannot-verify' (or the pipeline-specific equivalent). "
            "Escalate via SR with origin.kind="
            "'target-state-unreachable-needs-seed-data' so the responsible "
            "team produces the missing target state."
        ),
    }]


def _detect_semantic_target_mismatch(
    verification_artifact: dict[str, Any],
) -> list[dict[str, Any]]:
    target_label = verification_artifact.get("target_element_semantic_label")
    measured_label = verification_artifact.get("measured_element_semantic_label")
    verdict = (verification_artifact.get("verdict") or "").lower()
    if verdict not in ("passing", "pass", "bug-resolved", "resolved", "verified", "✅"):
        return []
    if target_label is None and measured_label is None:
        return []
    if _semantic_labels_match(target_label, measured_label):
        return []
    return [{
        "severity": "semantic-target-mismatch",
        "target_element_semantic_label": target_label,
        "measured_element_semantic_label": measured_label,
        "verdict": verdict,
        "evidence": (
            f"target_element_semantic_label={target_label!r} "
            f"≠ measured_element_semantic_label={measured_label!r}, "
            f"yet verdict={verdict!r}. Different semantic role = different "
            f"element = no PASS under v2.21.0."
        ),
        "remediation": (
            "v2.21.0 no proxy-element verification discipline. The agent "
            "measured a semantically different element than the spec named. "
            "Either re-run against the named target element or escalate via "
            "SR — never silently pass."
        ),
    }]


def _detect_proxy_substitution_markers_in_text(
    verification_artifact: dict[str, Any],
) -> list[dict[str, Any]]:
    """Heuristic backup: scan the verification_text / verification_notes /
    final_statement fields for confession language even when the structured
    fields are absent."""
    fields = (
        "verification_text",
        "verification_notes",
        "final_statement",
        "remediation_log",
    )
    chunks = [verification_artifact.get(f, "") for f in fields]
    text = "\n".join(c for c in chunks if isinstance(c, str))
    if not text.strip():
        return []
    lower = text.lower()
    hits = [m for m in _PROXY_SUBSTITUTION_MARKERS if m in lower]
    if not hits:
        return []
    return [{
        "severity": "proxy-element-substituted",
        "matched_markers": hits[:5],
        "evidence": (
            f"verification text contains confession/fallback language "
            f"{hits[:3]!r} signaling proxy substitution. Even without "
            f"structured target/measured selector fields, this confession is "
            f"sufficient to fire the v2.21.0 severity."
        ),
        "remediation": (
            "v2.21.0 no proxy-element verification discipline. Rewrite the "
            "verification to measure the actual target element OR escalate "
            "via SR. Never use 'proxy' / 'closest measurable' / 'the "
            "surrounding element' language to justify a PASS."
        ),
    }]


def verify_target_element_measured(
    verification_artifact: dict[str, Any] | None = None,
    out_path: Path | str | None = None,
) -> dict[str, Any]:
    """v2.21.0 Layer-3 tool — verify the target element was measured (not a
    proxy / sibling / nearby fallback).

    Trivially passes (`valid: True, gaps: []`) when neither
    `target_element_selector` nor `measured_element_selector` is set AND no
    proxy-substitution markers appear in verification text — backwards-
    compatible.

    3 named severities:
      - `proxy-element-substituted` — target ≠ measured selector while verdict is passing
      - `unreachable-state-not-escalated` — reachability_status != reached while verdict is passing
      - `semantic-target-mismatch` — target semantic label ≠ measured semantic label while verdict is passing
    """
    artifact = verification_artifact or {}
    gaps: list[dict[str, Any]] = []
    gaps += _detect_proxy_element_substituted(artifact)
    gaps += _detect_unreachable_state_not_escalated(artifact)
    gaps += _detect_semantic_target_mismatch(artifact)
    gaps += _detect_proxy_substitution_markers_in_text(artifact)

    verdict = {
        "tool": "verify-target-element-measured",
        "valid": len(gaps) == 0,
        "gaps": gaps,
        "verdict_at": _utc_now_iso(),
    }
    return _write_verdict(verdict, out_path)
