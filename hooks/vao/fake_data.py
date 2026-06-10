"""VAO fake-data + live-data-wiring family (2 tools)."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

try:  # package shape: repo root on sys.path
    from hooks.vao.core import _is_test_path, _utc_now_iso, _write_verdict
except ImportError:  # hooks/ on sys.path (vao is the package)
    try:
        from vao.core import _is_test_path, _utc_now_iso, _write_verdict
    except ImportError:  # hooks/vao/ on sys.path (bare sibling)
        from core import _is_test_path, _utc_now_iso, _write_verdict


# Common faked-data patterns that surface in heirship-app-v2-style failures.
# These are the patterns that the v1.7.0 frontend-missing-api-discipline
# forbids agents from inserting into PRODUCTION code (test fixtures are
# fine — the audit checks production-code files only).
_FAKE_DATA_PATTERNS: tuple[tuple[str, re.Pattern], ...] = (
    ("placeholder-name", re.compile(r"\bJohn\s+Smith\b|\bJane\s+Doe\b", re.IGNORECASE)),
    ("placeholder-email", re.compile(r"\b(?:john\.doe|jane\.doe|test\.user|foo\.bar)@example\.(?:com|org)\b", re.IGNORECASE)),
    ("lorem-ipsum", re.compile(r"\bLorem\s+ipsum\b", re.IGNORECASE)),
    ("placeholder-money", re.compile(r"\$1[,.]?234(?:\.00|\.56)?\b")),
    ("msw-handler", re.compile(r"\b(?:rest|http)\.(?:get|post|put|delete|patch)\s*\(", re.IGNORECASE)),
    ("playwright-route-fulfill", re.compile(r"\bpage\.route\s*\([^)]*\.fulfill", re.IGNORECASE)),
)


def verify_no_fake_data(
    diff_files: list[dict[str, Any]] | None = None,
    oracle_spec: dict[str, Any] | None = None,
    out_path: Path | str | None = None,
) -> dict[str, Any]:
    """Sweep a diff for fake-data patterns in production code.

    Args:
      diff_files: a list of {"path": "...", "added_lines": ["...", ...]} dicts.
      oracle_spec: optional oracle spec; if it carries a
        ``dynamic_values`` list, every entry's literal is added to the
        forbidden-pattern set for this audit.
      out_path: optional path to write the verdict JSON.

    Returns::

        {
          "tool": "verify-no-fake-data",
          "clean": bool,
          "hits": [{"file": ..., "line": ..., "match": ..., "category": ...}],
          "verdict_at": "<ISO 8601 UTC>"
        }
    """
    diff_files = diff_files or []
    oracle_spec = oracle_spec or {}
    dynamic_values = oracle_spec.get("dynamic_values", []) or []

    # Build the extended pattern set for this audit — oracle-declared dynamic
    # values must NOT appear verbatim in production code.
    dynamic_patterns: list[tuple[str, re.Pattern]] = []
    for dv in dynamic_values:
        if isinstance(dv, dict):
            literal = dv.get("literal") or dv.get("display") or dv.get("value")
        else:
            literal = dv if isinstance(dv, str) else None
        if isinstance(literal, str) and literal.strip():
            dynamic_patterns.append((
                f"oracle-dynamic-value:{literal[:40]}",
                re.compile(re.escape(literal)),
            ))

    all_patterns = list(_FAKE_DATA_PATTERNS) + dynamic_patterns

    hits: list[dict[str, Any]] = []
    for entry in diff_files:
        path = entry.get("path") if isinstance(entry, dict) else None
        added = entry.get("added_lines") if isinstance(entry, dict) else None
        if not isinstance(path, str) or not isinstance(added, list):
            continue
        if _is_test_path(path):
            continue
        for line_num, line in enumerate(added):
            if not isinstance(line, str):
                continue
            # Report every matching category for the line, not just the first.
            # A line can be both a placeholder-name AND inside an msw-handler;
            # both deserve to be flagged because they're different concerns.
            for category, pattern in all_patterns:
                m = pattern.search(line)
                if m:
                    hits.append({
                        "file": path,
                        "line": line_num,
                        "match": m.group(0),
                        "category": category,
                    })

    verdict = {
        "tool": "verify-no-fake-data",
        "clean": len(hits) == 0,
        "hits": hits,
        "verdict_at": _utc_now_iso(),
    }
    return _write_verdict(verdict, out_path)


# Canonical mock-state signatures. Each pattern is the smoking-gun residue
# v2.0.0's verify_no_fake_data CAN catch in ADDED lines, but v2.6.0 catches
# in ANY touched file (whether the line was added, modified, or left
# unchanged after live wiring was bolted on). Detection is substring +
# regex; AST-based traversal is v2.6.x.
_MOCK_STATE_SIGNATURES: tuple[tuple[str, str], ...] = (
    # MSW (mock service worker) — the most common React testing mock layer
    ("msw-import", "from \"msw\""),
    ("msw-import-single", "from 'msw'"),
    ("msw-setupworker", "setupWorker("),
    ("msw-setupserver", "setupServer("),
    ("msw-rest-get", "rest.get("),
    ("msw-rest-post", "rest.post("),
    ("msw-http-get", "http.get("),
    ("msw-http-post", "http.post("),
    # Mirage / Pretender — Ember/older-React testing servers
    ("miragejs-import", "from \"miragejs\""),
    ("miragejs-import-single", "from 'miragejs'"),
    ("miragejs-createserver", "createServer("),
    ("pretender-new", "new Pretender("),
    # Faker — fake-data generators
    ("faker-import", "from \"@faker-js/faker\""),
    ("faker-import-single", "from '@faker-js/faker'"),
    ("faker-dot", "faker."),
    # Mock-flag env vars and symbol names
    ("vite-use-mock", "VITE_USE_MOCK"),
    ("next-public-mock", "NEXT_PUBLIC_MOCK"),
    ("react-app-use-mock", "REACT_APP_USE_MOCK"),
    ("usemockbackend", "useMockBackend"),
    ("enablemocking", "enableMocking"),
    ("mock-api-flag", "MOCK_API"),
    ("mock-data-symbol", "MOCK_DATA"),
    ("fixture-symbol-prefix", "FIXTURE_"),
    # Fallback patterns that silently render mock when live data is null
    # (regex-style — the matcher does substring scan, so the literal must
    # appear; complex regex matching is deferred to v2.6.x)
    ("fallback-nullish-mock", "?? MOCK_"),
    ("fallback-nullish-mockdata", "?? mockData"),
    ("fallback-nullish-fixture", "?? FIXTURE_"),
    ("fallback-or-mock", "|| MOCK_"),
    ("fallback-or-mockdata", "|| mockData"),
    ("fallback-or-fixture", "|| FIXTURE_"),
    # Mock-fixture import paths
    ("mocks-dir-import", "__mocks__"),
    ("fixtures-import", "/fixtures/"),
    ("mock-data-import", "/mock-data/"),
)


# Per-async-state UI-element regex hints — the canonical state names a UI
# must render. Detection is permissive substring search.
_ASYNC_STATE_UI_HINTS: dict[str, tuple[str, ...]] = {
    "loading": ("loading", "spinner", "skeleton"),
    "pending": ("pending", "loading", "spinner"),
    "processing": ("processing", "progress"),
    "done": ("done", "complete", "ready"),
    "done-with-facts": ("done", "complete", "facts ready"),
    "success": ("success", "done", "complete"),
    "error": ("error", "failed", "retry"),
    "empty": ("empty", "no documents", "no items", "nothing"),
    "partial": ("partial", "loading more"),
}


def _detect_mock_state_residue(
    diff_files: list[dict[str, Any]],
    touched_file_contents: dict[str, str],
) -> list[dict[str, Any]]:
    """Grep diff added_lines + touched file contents for canonical mock-state
    signatures. Returns one gap per (file, signature) hit, capped per file."""
    gaps: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()  # (file, signature_id)

    # Walk diff added_lines (most direct signal of residue in agent's work)
    for entry in diff_files or []:
        path = entry.get("path") if isinstance(entry, dict) else None
        if not isinstance(path, str):
            continue
        if _is_test_path(path):
            continue
        added = entry.get("added_lines") if isinstance(entry, dict) else None
        if not isinstance(added, list):
            continue
        for line in added:
            if not isinstance(line, str):
                continue
            for sig_id, pattern in _MOCK_STATE_SIGNATURES:
                key = (path, sig_id)
                if key in seen:
                    continue
                if pattern in line:
                    gaps.append({
                        "severity": "mock-state-residue",
                        "evidence": f"file {path!r} contains mock-state signature "
                                    f"{sig_id!r} in added/modified line: {line.strip()!r}",
                        "remediation": "v2.6.0 Live-data wiring discipline. Remove the "
                                      "mock-state import / flag / fallback / handler. The "
                                      "live wiring is incomplete until the mock path is "
                                      "unreachable from production code paths.",
                    })
                    seen.add(key)

    # Walk touched_file_contents (catches residue NOT in the diff — pre-existing
    # mock state that the agent left in place when adding live wiring)
    for path, content in (touched_file_contents or {}).items():
        if not isinstance(path, str) or not isinstance(content, str):
            continue
        if _is_test_path(path):
            continue
        for sig_id, pattern in _MOCK_STATE_SIGNATURES:
            key = (path, sig_id)
            if key in seen:
                continue
            if pattern in content:
                gaps.append({
                    "severity": "mock-state-residue",
                    "evidence": f"touched file {path!r} contains pre-existing mock-state "
                                f"signature {sig_id!r}; live wiring is incomplete until "
                                f"the mock path is removed",
                    "remediation": "v2.6.0 Live-data wiring discipline. The signature was "
                                  "NOT in the agent's diff but IS in the touched file — "
                                  "the agent added live wiring without removing the prior "
                                  "mock. Remove the mock-state code path.",
                })
                seen.add(key)
    return gaps


def _detect_live_response_not_rendered(
    playwright_trace_summary: dict[str, Any],
) -> list[dict[str, Any]]:
    """Compare captured network response values against UI rendered text.
    For each captured response, if the UI doesn't contain the captured value,
    the data path is mock (UI sourced from cached fallback / hardcoded
    constant)."""
    gaps: list[dict[str, Any]] = []
    captured = playwright_trace_summary.get("captured_network_requests") or []
    ui_text = playwright_trace_summary.get("ui_text_after_render") or ""
    if not isinstance(ui_text, str):
        ui_text = str(ui_text)
    transform_hints = playwright_trace_summary.get("transform_hints") or []
    # transform_hints lists values that are KNOWN to be transformed (e.g.,
    # ISO 8601 dates rendered as "May 1, 2026"); they bypass the strict check.
    transform_set = {str(t) for t in transform_hints if t is not None}

    for req in captured:
        if not isinstance(req, dict):
            continue
        response_body = req.get("response_body")
        if not isinstance(response_body, dict):
            continue
        # Walk every string-like value in response_body; assert it appears
        # in ui_text. Only check top-level fields for v2.6.0; nested-field
        # checking is v2.6.x.
        for field_name, field_value in response_body.items():
            if not isinstance(field_value, (str, int, float)):
                continue
            field_str = str(field_value)
            if not field_str:
                continue
            if field_str in transform_set:
                continue
            if len(field_str) < 3:
                continue  # too-short values false-positive
            if field_str not in ui_text:
                gaps.append({
                    "severity": "live-response-not-rendered",
                    "evidence": f"endpoint {req.get('url', '<unknown>')!r} returned "
                                f"{field_name}={field_value!r}; the UI's rendered text does "
                                f"NOT contain this value",
                    "remediation": "v2.6.0 Live-data wiring discipline. The UI is rendering "
                                  "a stale snapshot OR a fallback OR a hardcoded constant. "
                                  "Trace the field from the network response to the rendered "
                                  "component; bind to live data not a cached mock.",
                })
                break  # one gap per request is enough; flag and continue
    return gaps


def _detect_mock_fallback_uncovered(
    diff_files: list[dict[str, Any]],
    touched_file_contents: dict[str, str],
) -> list[dict[str, Any]]:
    """Catch ?? mockValue / || MOCK_DEFAULT fallback patterns that would
    silently render mock when live data is null."""
    # Fallback-specific signatures — a subset of _MOCK_STATE_SIGNATURES
    # but reported as the more-specific severity.
    fallback_patterns = (
        ("?? MOCK_", "nullish-coalesce-to-mock"),
        ("?? mockData", "nullish-coalesce-to-mockdata"),
        ("?? FIXTURE_", "nullish-coalesce-to-fixture"),
        ("|| MOCK_", "or-fallback-to-mock"),
        ("|| mockData", "or-fallback-to-mockdata"),
        ("|| FIXTURE_", "or-fallback-to-fixture"),
        ("?? fakeData", "nullish-coalesce-to-fakedata"),
    )
    gaps: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()

    def _walk(path: str, line: str, source: str) -> None:
        if _is_test_path(path):
            return
        for pattern, hint in fallback_patterns:
            key = (path, pattern)
            if key in seen:
                continue
            if pattern in line:
                gaps.append({
                    "severity": "mock-fallback-uncovered",
                    "evidence": f"{source} {path!r} contains fallback pattern "
                                f"{pattern!r} ({hint}): {line.strip()!r}",
                    "remediation": "v2.6.0 Live-data wiring discipline. Fallback to mock "
                                  "silently renders mock data when live data is null/"
                                  "undefined — masking real failures. Replace the fallback "
                                  "with a proper loading/error/empty UI state.",
                })
                seen.add(key)

    for entry in diff_files or []:
        path = entry.get("path") if isinstance(entry, dict) else None
        if not isinstance(path, str):
            continue
        for line in (entry.get("added_lines") or []) if isinstance(entry, dict) else []:
            if isinstance(line, str):
                _walk(path, line, "diff added line in")

    for path, content in (touched_file_contents or {}).items():
        if not isinstance(path, str) or not isinstance(content, str):
            continue
        for line in content.splitlines():
            _walk(path, line, "touched file")

    return gaps


def _detect_network_not_intercepted(
    wiring_mandate: dict[str, Any],
    playwright_trace_summary: dict[str, Any],
) -> list[dict[str, Any]]:
    """For each endpoint the mandate names, assert Playwright captured a
    request to it. If not, the UI sourced data elsewhere (cached mock /
    hardcoded constant / local fixture)."""
    endpoints = wiring_mandate.get("endpoints") or []
    captured = playwright_trace_summary.get("captured_network_requests") or []
    captured_urls = []
    for req in captured:
        if isinstance(req, dict):
            url = req.get("url")
            if isinstance(url, str):
                captured_urls.append(url)

    gaps: list[dict[str, Any]] = []
    for endpoint in endpoints:
        if not isinstance(endpoint, str) or not endpoint:
            continue
        # Match the endpoint pattern against captured URLs by splitting on
        # `{placeholder}` segments. Each non-placeholder fragment must appear
        # in the URL in order. So `/api/matters/{matter_id}/documents` matches
        # `/api/matters/abc-123/documents` because `/api/matters/` and
        # `/documents` both appear in order.
        fragments = re.split(r"\{[^}]+\}", endpoint)
        fragments = [f for f in fragments if f]
        if not fragments:
            fragments = [endpoint]
        matched = False
        for url in captured_urls:
            cursor = 0
            ok = True
            for frag in fragments:
                idx = url.find(frag, cursor)
                if idx < 0:
                    ok = False
                    break
                cursor = idx + len(frag)
            if ok:
                matched = True
                break
        if not matched:
            gaps.append({
                "severity": "network-not-intercepted",
                "evidence": f"wiring_mandate.endpoints[] includes {endpoint!r}; "
                            f"Playwright captured no request matching that endpoint. "
                            f"Captured URLs: {captured_urls!r}",
                "remediation": "v2.6.0 Live-data wiring discipline. The UI never fetched "
                              "the live endpoint. Likely sources: cached mock data, "
                              "hardcoded constant, local fixture import, or the live-data "
                              "query hook was never invoked. Trace the rendering path; "
                              "ensure the live query fires.",
            })
    return gaps


def _detect_async_status_not_surfaced(
    wiring_mandate: dict[str, Any],
    playwright_trace_summary: dict[str, Any],
) -> list[dict[str, Any]]:
    """For each async state the mandate expects, assert the UI text contains
    a state-named element. Missing = the user sees silence when work is
    actually in progress (the heirship-app-v3 case verbatim)."""
    expected_states = wiring_mandate.get("async_states_expected") or []
    ui_text = playwright_trace_summary.get("ui_text_after_render") or ""
    if not isinstance(ui_text, str):
        ui_text = str(ui_text)
    ui_text_lower = ui_text.lower()

    gaps: list[dict[str, Any]] = []
    for state in expected_states:
        if not isinstance(state, str) or not state:
            continue
        # Direct state-name check + canonical UI-hint set
        hints = _ASYNC_STATE_UI_HINTS.get(state.lower(), (state.lower(),))
        if not any(hint in ui_text_lower for hint in hints):
            gaps.append({
                "severity": "async-status-not-surfaced",
                "evidence": f"wiring_mandate.async_states_expected[] includes {state!r}; "
                            f"Playwright ui_text_after_render contains none of the canonical "
                            f"UI hints {hints!r} for this state",
                "remediation": "v2.6.0 Live-data wiring discipline. The backend emits the "
                              f"{state!r} state; the UI must render a corresponding surface "
                              f"(spinner/skeleton/progress/empty-state/error-with-retry). "
                              f"Missing state UI is silent failure — the user sees nothing "
                              f"when work is actually in progress.",
            })
    return gaps


def _detect_shared_mock_source_not_swept(
    wiring_mandate: dict[str, Any],
    verification_artifact: dict[str, Any],
) -> list[dict[str, Any]]:
    """v2.7.0 — when a wiring_mandate names a shared_mock_source (e.g.,
    'WtData' / 'useWalkthroughData' / 'seedWtData') with N known consumer
    files, the diff MUST modify every consumer. If the diff modified only
    some AND any unmodified consumer still imports/calls the source,
    fires shared-mock-source-not-swept.

    Two input shapes are supported:
      (a) wiring_mandate.shared_mock_sources[] = [
            {"name": "WtData", "consumer_files": ["src/Workspace.tsx",
             "src/IntakeSteps.tsx", "src/ReviewPanel.tsx"]},
            ...
          ]
      (b) verification_artifact.codebase_scan.consumer_files = {
            "WtData": ["src/Workspace.tsx", "src/IntakeSteps.tsx", ...],
            ...
          }
    Detection uses the union of (a) and (b).
    """
    sources_from_mandate = wiring_mandate.get("shared_mock_sources") or []
    codebase_scan = verification_artifact.get("codebase_scan") or {}
    consumer_files_scan = codebase_scan.get("consumer_files") or {}
    diff_files = verification_artifact.get("diff_files") or []
    touched = verification_artifact.get("touched_file_contents") or {}

    # Files the diff modified (path strings).
    modified_paths: set[str] = set()
    for df in diff_files:
        if isinstance(df, dict) and isinstance(df.get("path"), str):
            modified_paths.add(df["path"])

    # Normalize sources_from_mandate (list of dict or list of str).
    sources: dict[str, list[str]] = {}
    for src in sources_from_mandate:
        if isinstance(src, dict):
            name = src.get("name")
            files = src.get("consumer_files") or []
            if isinstance(name, str) and name and isinstance(files, list):
                sources[name] = [f for f in files if isinstance(f, str)]
        elif isinstance(src, str) and src:
            sources.setdefault(src, [])
    for name, files in consumer_files_scan.items():
        if isinstance(name, str) and name and isinstance(files, list):
            existing = sources.get(name, [])
            merged = list(dict.fromkeys(existing + [f for f in files if isinstance(f, str)]))
            sources[name] = merged

    if not sources:
        return []

    gaps: list[dict[str, Any]] = []
    for source_name, consumer_files in sources.items():
        if not consumer_files:
            continue
        unfixed = [f for f in consumer_files if f not in modified_paths]
        # If every consumer was modified, the sweep is complete.
        if not unfixed:
            continue
        # If the diff didn't touch ANY consumer, the v2.6.0 detectors handle
        # it (mock-state-residue + network-not-intercepted). v2.7.0 fires
        # only when SOME consumers were fixed and OTHERS were left.
        fixed_count = len(consumer_files) - len(unfixed)
        if fixed_count == 0:
            continue
        # Confirm each unfixed file still references the source (either
        # via signature substring in touched contents, or — when contents
        # are not provided — by being explicitly named in codebase_scan).
        scan_unfixed = codebase_scan.get("unfixed_consumer_files") or []
        for unfixed_path in unfixed:
            content = touched.get(unfixed_path, "")
            still_uses_source = (
                (source_name in content) if isinstance(content, str) else False
            ) or (unfixed_path in scan_unfixed)
            # When the scan explicitly enumerates this consumer but we have
            # no content, treat the explicit enumeration as evidence the
            # source still survives (the scan ran codebase-wide grep).
            if not still_uses_source and not content and unfixed_path in consumer_files:
                still_uses_source = True
            if still_uses_source:
                gaps.append({
                    "severity": "shared-mock-source-not-swept",
                    "source": source_name,
                    "unfixed_consumer": unfixed_path,
                    "evidence": (
                        f"wiring_mandate.shared_mock_sources names {source_name!r} with "
                        f"{len(consumer_files)} consumer files; the diff fixed "
                        f"{fixed_count}/{len(consumer_files)} consumers but left "
                        f"{unfixed_path!r} unmodified while it still references the source."
                    ),
                    "remediation": (
                        "v2.7.0 Pattern propagation mandate. When a wiring_mandate names a "
                        "shared mock source, every consumer of that source MUST be fixed in "
                        "the same change. Sweep all consumers; do NOT offer the sweep as a "
                        "follow-up. The phrase 'say the word if you want me to sweep the rest' "
                        "is the discipline failure this severity catches."
                    ),
                })
    return gaps


def verify_live_data_wiring(
    verification_artifact: dict[str, Any] | None = None,
    wiring_mandate: dict[str, Any] | None = None,
    out_path: Path | str | None = None,
) -> dict[str, Any]:
    """v2.6.0 + v2.7.0 Layer-3 tool — verify the agent removed mock state
    when the requirement mandated live data wiring AND swept every consumer
    of any shared mock source named by the mandate.

    Checks the verification artifact against the 6 named severities:
      1. mock-state-residue — MSW / Mirage / faker / fixture / mock-flag
         signatures still present in production code paths
      2. live-response-not-rendered — UI doesn't show captured network value
      3. mock-fallback-uncovered — ?? mockValue / || MOCK_DEFAULT patterns
      4. network-not-intercepted — mandated endpoint never fetched
      5. async-status-not-surfaced — async state never rendered in UI
      6. shared-mock-source-not-swept — diff fixed some consumers of a
         named shared mock source but left others (v2.7.0)

    Args:
      verification_artifact: dict with diff_files[], touched_file_contents{},
        playwright_trace_summary{captured_network_requests[], ui_text_after_render,
        tamper_test_results, transform_hints}.
      wiring_mandate: dict with mandate_kind, endpoints[], async_states_expected[].
        Absent or empty mandate → tool trivially passes (no mandate to enforce).
      out_path: optional path to write the verdict JSON.

    Returns::

        {
          "tool": "verify-live-data-wiring",
          "valid": bool,
          "gaps": [{"severity", "evidence", "remediation"}],
          "verdict_at": "<ISO 8601 UTC>"
        }

    Deterministic / bit-stable output for given inputs (sorted-keys + indent=2).
    """
    artifact = verification_artifact or {}
    mandate = wiring_mandate or {}
    gaps: list[dict[str, Any]] = []

    # If no mandate is set, the v2.6.0 discipline doesn't apply — trivially
    # pass. This preserves backwards-compat: artifacts without wiring_mandate
    # continue to validate.
    has_mandate = bool(
        mandate.get("mandate_kind")
        or mandate.get("endpoints")
        or mandate.get("async_states_expected")
        or mandate.get("shared_mock_sources")
    )
    if not has_mandate:
        verdict = {
            "tool": "verify-live-data-wiring",
            "valid": True,
            "gaps": [],
            "verdict_at": _utc_now_iso(),
        }
        return _write_verdict(verdict, out_path)

    diff_files = artifact.get("diff_files") or []
    touched_files = artifact.get("touched_file_contents") or {}
    playwright_summary = artifact.get("playwright_trace_summary") or {}

    gaps += _detect_mock_state_residue(diff_files, touched_files)
    gaps += _detect_mock_fallback_uncovered(diff_files, touched_files)
    gaps += _detect_live_response_not_rendered(playwright_summary)
    gaps += _detect_network_not_intercepted(mandate, playwright_summary)
    gaps += _detect_async_status_not_surfaced(mandate, playwright_summary)
    gaps += _detect_shared_mock_source_not_swept(mandate, artifact)

    verdict = {
        "tool": "verify-live-data-wiring",
        "valid": len(gaps) == 0,
        "gaps": gaps,
        "verdict_at": _utc_now_iso(),
    }
    return _write_verdict(verdict, out_path)
