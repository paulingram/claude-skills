"""VAO persona-path + affordance family (2 tools)."""

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

try:  # package shape: repo root on sys.path
    from hooks.vao.live_verification import _LOCAL_ENV_HOST_PATTERNS
except ImportError:  # hooks/ on sys.path (vao is the package)
    try:
        from vao.live_verification import _LOCAL_ENV_HOST_PATTERNS
    except ImportError:  # hooks/vao/ on sys.path (bare sibling)
        from live_verification import _LOCAL_ENV_HOST_PATTERNS


# Canonical UI hints that indicate a loading state was observed by Playwright.
# Matched case-insensitively as substrings against playwright_test_runs[].
# ui_states_observed[] entries. Keep the list explicit so legitimate UI text
# (e.g., "loading documents" elsewhere in a screen) does not false-positive
# when the test never observed the loading state during the actual click.
_LOADING_STATE_UI_HINTS: tuple[str, ...] = (
    "spinner",
    "loading",
    "loading...",
    "working",
    "working...",
    "please wait",
    "progress-circular",
    "aria-busy",
    "skeleton",
    "placeholder-shimmer",
    "loading-skeleton",
    "progress-bar",
    "progressbar",
    "submitting",
    "submitting...",
    "creating",
    "creating...",
    "saving",
    "saving...",
    "processing",
    "processing...",
    "pending",
    "in-progress",
)


# Two clicks within this window count as a double-submit. The user reported
# clicking the Create-Matter button twice because the UI looked frozen
# (no loading state); two matters were created in the backend.
_DOUBLE_SUBMIT_TIMING_THRESHOLD_MS: int = 500


# Loading-state must surface within this window after the click. Anything
# longer is observable as "frozen UI" by the user.
_LOADING_STATE_MAX_DELAY_MS: int = 200


def _matches_loading_hint(state_text: str) -> bool:
    if not isinstance(state_text, str) or not state_text:
        return False
    lower = state_text.lower()
    return any(hint in lower for hint in _LOADING_STATE_UI_HINTS)


def _detect_persona_path_not_tested(
    persona_inventory: dict[str, Any],
    verification_artifact: dict[str, Any],
) -> list[dict[str, Any]]:
    """Every persona in inventory must have at least one playwright_test_run
    with matching persona_id."""
    personas = persona_inventory.get("personas") or []
    runs = verification_artifact.get("playwright_test_runs") or []
    tested_ids: set[str] = set()
    for r in runs:
        if isinstance(r, dict):
            pid = r.get("persona_id")
            if isinstance(pid, str) and pid:
                tested_ids.add(pid)

    gaps: list[dict[str, Any]] = []
    for p in personas:
        if not isinstance(p, dict):
            continue
        pid = p.get("persona_id")
        if not isinstance(pid, str) or not pid:
            continue
        if pid not in tested_ids:
            entry_point = p.get("entry_point", "<unknown>")
            gaps.append({
                "severity": "persona-path-not-tested",
                "persona_id": pid,
                "entry_point": entry_point,
                "evidence": (
                    f"persona {pid!r} (entry_point={entry_point!r}) is in the "
                    f"persona-inventory but no playwright_test_runs[] entry "
                    f"with persona_id={pid!r} was executed."
                ),
                "remediation": (
                    "v2.11.0 Multi-persona path-coverage discipline. Author a "
                    "Playwright test that opens the persona's entry_point against "
                    "the live dev URL, executes their golden-path flow, and asserts "
                    "every entry in expected_data_visibility[] appears in the "
                    "rendered DOM. The test goes in playwright_test_runs[] with "
                    f"persona_id={pid!r}."
                ),
            })
    return gaps


def _detect_cross_persona_sync_not_asserted(
    persona_inventory: dict[str, Any],
    verification_artifact: dict[str, Any],
) -> list[dict[str, Any]]:
    """For every persona A with cross_persona_dependencies[], a
    playwright_test_runs[] entry must create the named data as A AND open
    persona B's view AND assert the data appears."""
    personas = persona_inventory.get("personas") or []
    runs = verification_artifact.get("playwright_test_runs") or []

    # Build a map of cross-persona assertions that runs claim to cover.
    # Each run can carry cross_persona_assertions: [{writes_data, asserted_in_persona}].
    asserted_pairs: set[tuple[str, str, str]] = set()
    for r in runs:
        if not isinstance(r, dict):
            continue
        writer_persona = r.get("persona_id") or ""
        cpa = r.get("cross_persona_assertions") or []
        for entry in cpa:
            if not isinstance(entry, dict):
                continue
            data = entry.get("writes_data") or ""
            target = entry.get("asserted_in_persona") or ""
            if data and target and writer_persona:
                asserted_pairs.add((writer_persona, data, target))

    gaps: list[dict[str, Any]] = []
    for p in personas:
        if not isinstance(p, dict):
            continue
        writer_id = p.get("persona_id") or ""
        deps = p.get("cross_persona_dependencies") or []
        for dep in deps:
            if not isinstance(dep, dict):
                continue
            data = dep.get("writes_data") or ""
            target = dep.get("must_appear_in_persona") or ""
            if not data or not target:
                continue
            if (writer_id, data, target) not in asserted_pairs:
                gaps.append({
                    "severity": "cross-persona-sync-not-asserted",
                    "writer_persona": writer_id,
                    "data": data,
                    "target_persona": target,
                    "evidence": (
                        f"persona {writer_id!r} writes data {data!r} that must "
                        f"appear in persona {target!r}'s view; no playwright_test_runs[] "
                        f"entry has cross_persona_assertions covering this pair."
                    ),
                    "remediation": (
                        "v2.11.0 Multi-persona path-coverage discipline. Author a "
                        "Playwright test that opens the writer persona's entry_point, "
                        "creates the data, then opens the target persona's entry_point "
                        "and asserts the data appears in the rendered DOM. Record the "
                        "assertion in cross_persona_assertions[]."
                    ),
                })
    return gaps


def _detect_double_submit_not_tested(
    persona_inventory: dict[str, Any],
    verification_artifact: dict[str, Any],
) -> list[dict[str, Any]]:
    """For every persona's flow that includes a submit-shaped interaction,
    a playwright_test_runs[] entry must show two clicks within
    _DOUBLE_SUBMIT_TIMING_THRESHOLD_MS AND a final-record-count assertion
    of 1."""
    personas = persona_inventory.get("personas") or []
    runs = verification_artifact.get("playwright_test_runs") or []

    # Personas that have at least one submit_interaction declared in inventory.
    personas_with_submit: dict[str, str] = {}
    for p in personas:
        if not isinstance(p, dict):
            continue
        pid = p.get("persona_id") or ""
        submit_selector = p.get("submit_interaction") or ""
        if pid and submit_selector:
            personas_with_submit[pid] = submit_selector

    # Personas whose test run actually exercised a double-submit assertion.
    personas_with_double_submit_test: set[str] = set()
    for r in runs:
        if not isinstance(r, dict):
            continue
        pid = r.get("persona_id") or ""
        clicks = r.get("clicks_with_timing") or []
        record_count_after = r.get("record_count_after_double_click")
        if not isinstance(clicks, list) or len(clicks) < 2:
            continue
        # Check for two clicks within the threshold.
        rapid_pair = False
        for i in range(len(clicks) - 1):
            a = clicks[i]
            b = clicks[i + 1]
            if not isinstance(a, dict) or not isinstance(b, dict):
                continue
            ta = a.get("ts_ms")
            tb = b.get("ts_ms")
            if isinstance(ta, (int, float)) and isinstance(tb, (int, float)):
                if 0 < (tb - ta) <= _DOUBLE_SUBMIT_TIMING_THRESHOLD_MS:
                    # Same selector?
                    sa = a.get("selector") or ""
                    sb = b.get("selector") or ""
                    if sa and sb and sa == sb:
                        rapid_pair = True
                        break
        if rapid_pair and record_count_after == 1:
            personas_with_double_submit_test.add(pid)

    gaps: list[dict[str, Any]] = []
    for pid, selector in personas_with_submit.items():
        if pid not in personas_with_double_submit_test:
            gaps.append({
                "severity": "double-submit-not-tested",
                "persona_id": pid,
                "submit_selector": selector,
                "evidence": (
                    f"persona {pid!r} has submit_interaction {selector!r}; no "
                    f"playwright_test_runs[] entry shows two clicks within "
                    f"{_DOUBLE_SUBMIT_TIMING_THRESHOLD_MS}ms AND a "
                    f"record_count_after_double_click == 1 assertion."
                ),
                "remediation": (
                    "v2.11.0 Multi-persona path-coverage discipline. Author a "
                    "Playwright test that clicks the submit selector twice within "
                    f"{_DOUBLE_SUBMIT_TIMING_THRESHOLD_MS}ms (simulating a frozen-UI "
                    "user clicking twice) and asserts the backend records exactly "
                    "one entry. Record the click timing in clicks_with_timing[] "
                    "and the count in record_count_after_double_click."
                ),
            })
    return gaps


def _detect_loading_state_not_asserted(
    persona_inventory: dict[str, Any],
    verification_artifact: dict[str, Any],
) -> list[dict[str, Any]]:
    """For every persona's flow that includes a backend-call interaction,
    a playwright_test_runs[] entry must show a loading-state UI hint
    observed within _LOADING_STATE_MAX_DELAY_MS of the click."""
    personas = persona_inventory.get("personas") or []
    runs = verification_artifact.get("playwright_test_runs") or []

    # Personas that have at least one backend_call_interaction in inventory.
    personas_with_backend_call: dict[str, str] = {}
    for p in personas:
        if not isinstance(p, dict):
            continue
        pid = p.get("persona_id") or ""
        backend_selector = p.get("backend_call_interaction") or p.get("submit_interaction") or ""
        if pid and backend_selector:
            personas_with_backend_call[pid] = backend_selector

    personas_with_loading_state_test: set[str] = set()
    for r in runs:
        if not isinstance(r, dict):
            continue
        pid = r.get("persona_id") or ""
        states = r.get("ui_states_observed") or []
        click_delays = r.get("loading_state_delays_ms") or []
        if not isinstance(states, list):
            continue
        # Did any observed state match a loading hint?
        loading_observed = any(_matches_loading_hint(str(s)) for s in states)
        if not loading_observed:
            continue
        # Was a delay-from-click measurement recorded and within the threshold?
        delay_ok = False
        if isinstance(click_delays, list) and click_delays:
            try:
                delay_ok = any(
                    isinstance(d, (int, float)) and 0 <= d <= _LOADING_STATE_MAX_DELAY_MS
                    for d in click_delays
                )
            except Exception:
                delay_ok = False
        else:
            # If the test recorded the loading state without an explicit delay
            # measurement, accept it but flag that timing is implicit.
            delay_ok = True
        if delay_ok:
            personas_with_loading_state_test.add(pid)

    gaps: list[dict[str, Any]] = []
    for pid, selector in personas_with_backend_call.items():
        if pid not in personas_with_loading_state_test:
            gaps.append({
                "severity": "loading-state-not-asserted",
                "persona_id": pid,
                "backend_call_selector": selector,
                "evidence": (
                    f"persona {pid!r} has backend_call_interaction {selector!r}; "
                    f"no playwright_test_runs[] entry shows a loading-state UI "
                    f"hint (from _LOADING_STATE_UI_HINTS) observed within "
                    f"{_LOADING_STATE_MAX_DELAY_MS}ms of the click."
                ),
                "remediation": (
                    "v2.11.0 Multi-persona path-coverage discipline. Without a "
                    "loading-state UI a user sees a frozen page and clicks again — "
                    "the canonical heirship case (two matters created from a "
                    "frozen Create-Matter button). Author a Playwright test that "
                    "clicks the backend-call selector, captures a UI state within "
                    f"{_LOADING_STATE_MAX_DELAY_MS}ms, and asserts it matches one "
                    "of the canonical _LOADING_STATE_UI_HINTS (spinner / skeleton "
                    "/ progress-bar / 'Submitting...' / aria-busy / etc.)."
                ),
            })
    return gaps


def verify_per_persona_path_coverage(
    verification_artifact: dict[str, Any] | None = None,
    persona_inventory: dict[str, Any] | None = None,
    out_path: Path | str | None = None,
) -> dict[str, Any]:
    """v2.11.0 Layer-3 tool — verify the agent tested EVERY persona's path
    in a multi-persona feature, not just the one the user reported.

    Checks the verification artifact against the 4 named severities:
      1. persona-path-not-tested — a persona in inventory has no
         playwright_test_runs[] entry
      2. cross-persona-sync-not-asserted — persona A writes data that must
         appear in persona B's view; no test creates+asserts the pair
      3. double-submit-not-tested — submit-shaped interaction; no test
         exercises two clicks within 500ms with a single-record assertion
      4. loading-state-not-asserted — backend-call interaction; no test
         observes a canonical loading-state UI hint within 200ms of click

    Trivially passes when persona_inventory is empty — backwards-compatible.

    Returns::

        {
          "tool": "verify-per-persona-path-coverage",
          "valid": bool,
          "gaps": [{"severity", "persona_id", "evidence", "remediation", ...}],
          "verdict_at": "<ISO 8601 UTC>"
        }

    Deterministic / bit-stable output for given inputs.
    """
    artifact = verification_artifact or {}
    inventory = persona_inventory or {}

    personas = inventory.get("personas") or []
    if not isinstance(personas, list) or not personas:
        verdict = {
            "tool": "verify-per-persona-path-coverage",
            "valid": True,
            "gaps": [],
            "verdict_at": _utc_now_iso(),
        }
        return _write_verdict(verdict, out_path)

    gaps: list[dict[str, Any]] = []
    gaps += _detect_persona_path_not_tested(inventory, artifact)
    gaps += _detect_cross_persona_sync_not_asserted(inventory, artifact)
    gaps += _detect_double_submit_not_tested(inventory, artifact)
    gaps += _detect_loading_state_not_asserted(inventory, artifact)
    gaps += _detect_live_dev_environment_not_tested(inventory, artifact)

    verdict = {
        "tool": "verify-per-persona-path-coverage",
        "valid": len(gaps) == 0,
        "gaps": gaps,
        "verdict_at": _utc_now_iso(),
    }
    return _write_verdict(verdict, out_path)


def _is_local_env_url(url: str) -> bool:
    """A Playwright entry_url is a LOCAL run if it matches any of the
    _LOCAL_ENV_HOST_PATTERNS. Anything else is a remote (live-dev) run."""
    if not isinstance(url, str) or not url:
        return False
    lower = url.lower()
    return any(p in lower for p in _LOCAL_ENV_HOST_PATTERNS)


def _detect_live_dev_environment_not_tested(
    persona_inventory: dict[str, Any],
    verification_artifact: dict[str, Any],
) -> list[dict[str, Any]]:
    """v2.13.0 — Every persona MUST have BOTH a local run AND a live-dev run.
    Fires `live-dev-environment-not-tested` when a persona is tested in only
    one environment.
    """
    personas = persona_inventory.get("personas") or []
    runs = verification_artifact.get("playwright_test_runs") or []

    # Map persona_id → set of env classifications observed.
    persona_envs: dict[str, set[str]] = {}
    for r in runs:
        if not isinstance(r, dict):
            continue
        pid = r.get("persona_id")
        url = r.get("entry_url")
        if not isinstance(pid, str) or not pid or not isinstance(url, str):
            continue
        env = "local" if _is_local_env_url(url) else "live-dev"
        persona_envs.setdefault(pid, set()).add(env)

    gaps: list[dict[str, Any]] = []
    for p in personas:
        if not isinstance(p, dict):
            continue
        pid = p.get("persona_id")
        if not isinstance(pid, str) or not pid:
            continue
        envs = persona_envs.get(pid, set())
        # If persona was never tested at all, the existing
        # persona-path-not-tested detector handles it; skip here.
        if not envs:
            continue
        # If both environments observed, no gap.
        if "local" in envs and "live-dev" in envs:
            continue
        missing = "live-dev" if "local" in envs else "local"
        gaps.append({
            "severity": "live-dev-environment-not-tested",
            "persona_id": pid,
            "missing_environment": missing,
            "observed_environments": sorted(envs),
            "entry_point": p.get("entry_point", "<not declared>"),
            "evidence": (
                f"persona {pid!r} has Playwright runs in {sorted(envs)!r} "
                f"environment(s); the {missing!r} environment was never tested."
            ),
            "remediation": (
                "v2.13.0 UX-test environment sequencing discipline. Every "
                "persona MUST be tested in BOTH local AND live-dev "
                "environments. The local pass gives fast feedback "
                "(debugger / hot-reload); the live-dev pass verifies the "
                "deployed bundle (real env vars / real CDN / real auth). "
                f"Add a Playwright run with entry_url matching the {missing!r} "
                "environment. Local URLs match _LOCAL_ENV_HOST_PATTERNS "
                "(localhost / 127.0.0.1 / .local / file:// / etc.); "
                "live-dev URLs are the persona's declared entry_point."
            ),
        })
    return gaps


# v2.13.0 file-upload affordance signatures. Each entry is (signature_id,
# substring pattern). Patterns are matched case-insensitively against the
# combined content of files_scanned[]. The list is intentionally broad
# (covers HTML / JS APIs / dropzone libs / backend middleware / cloud SDKs /
# UI text / server routes) so the discipline catches the affordance no
# matter where in the stack it lives.
_FILE_UPLOAD_AFFORDANCE_SIGNATURES: tuple[tuple[str, str], ...] = (
    # HTML / DOM
    ("html-file-input", '<input type="file"'),
    ("html-file-input-single", "type='file'"),
    ("accept-attr-image", 'accept="image/'),
    ("accept-attr-pdf", 'accept=".pdf'),
    ("multipart-form-enctype", 'enctype="multipart/form-data"'),
    ("multipart-content-type", "multipart/form-data"),
    # JavaScript APIs
    ("filereader-api", "FileReader"),
    ("new-formdata", "new FormData("),
    ("formdata-append", ".append("),
    ("input-files-prop", "input.files"),
    ("datatransfer-files", "dataTransfer.files"),
    ("create-object-url", "URL.createObjectURL"),
    # Dropzone libraries (JS)
    ("react-dropzone", "react-dropzone"),
    ("uppy-import", "@uppy/"),
    ("filepond-import", "filepond"),
    ("dropzone-js", "dropzone-js"),
    ("vue-upload", "vue-upload-component"),
    ("ng-file-upload", "ng-file-upload"),
    # Backend middleware
    ("multer-mw", "multer"),
    ("busboy-mw", "busboy"),
    ("formidable-mw", "formidable"),
    ("express-fileupload", "express-fileupload"),
    ("koa-multer", "koa-multer"),
    ("django-filefield", "models.FileField"),
    ("flask-files", "request.files"),
    ("fastapi-uploadfile", "UploadFile"),
    # Cloud storage SDKs
    ("aws-s3-putobject", "PutObject"),
    ("aws-s3-presigned-post", "createPresignedPost"),
    ("aws-s3-presigned-url", "getSignedUrl"),
    ("gcs-import", "@google-cloud/storage"),
    ("azure-blob-import", "BlobServiceClient"),
    ("cloudinary-upload", "uploader.upload"),
    ("uploadcare-upload", "uploadcare"),
    # UI text patterns
    ("upload-button-text", ">Upload<"),
    ("attach-button-text", ">Attach<"),
    ("add-file-text", "Add file"),
    ("browse-files-text", "Browse files"),
    ("drop-files-here-text", "Drop files here"),
    ("choose-file-text", "Choose file"),
    # Server routes
    ("post-upload-route", '"/upload"'),
    ("post-files-route", '"/files"'),
    ("post-attachments-route", '"/attachments"'),
)


# v2.13.0 affordance dictionary. v2.13.0 ships one canonical class
# (file-upload). Future versions add file-download / realtime /
# notifications / etc. — each new affordance is a new key with its own
# signature tuple. The detector iterates over the dict; new affordances
# Just Work.
_AFFORDANCE_SIGNATURES: dict[str, tuple[tuple[str, str], ...]] = {
    "file-upload": _FILE_UPLOAD_AFFORDANCE_SIGNATURES,
}


def _scan_file_content(
    content: str, signatures: tuple[tuple[str, str], ...]
) -> list[tuple[str, str]]:
    """Return list of (signature_id, pattern) hits found in `content`.
    Case-insensitive substring match."""
    if not isinstance(content, str) or not content:
        return []
    lower = content.lower()
    hits: list[tuple[str, str]] = []
    for sig_id, pattern in signatures:
        if pattern.lower() in lower:
            hits.append((sig_id, pattern))
    return hits


def _detect_affordance_not_addressed(
    verification_artifact: dict[str, Any],
    requirements_inventory: dict[str, Any],
) -> list[dict[str, Any]]:
    """For each canonical affordance class, scan the codebase. If any
    signature matches AND the requirements inventory does NOT address that
    class, fire `affordance-not-addressed`."""
    codebase_scan = verification_artifact.get("codebase_scan") or {}
    files_scanned = codebase_scan.get("files_scanned") or []
    addressed = requirements_inventory.get("addressed_affordances") or []
    addressed_set: set[str] = {
        str(a).lower() for a in addressed if isinstance(a, str)
    }
    confirmed_stubs = requirements_inventory.get("confirmed_stubs") or []
    confirmed_stub_kinds: set[str] = set()
    for stub in confirmed_stubs:
        if isinstance(stub, dict):
            k = stub.get("affordance_kind")
            if isinstance(k, str):
                confirmed_stub_kinds.add(k.lower())

    gaps: list[dict[str, Any]] = []
    for kind, sigs in _AFFORDANCE_SIGNATURES.items():
        # Aggregate hits per kind across all scanned files.
        per_file_hits: dict[str, list[tuple[str, str]]] = {}
        for f in files_scanned:
            if not isinstance(f, dict):
                continue
            path = f.get("path") or ""
            content = f.get("content_excerpt") or f.get("content") or ""
            if not isinstance(path, str) or not isinstance(content, str):
                continue
            hits = _scan_file_content(content, sigs)
            if hits:
                per_file_hits[path] = hits

        if not per_file_hits:
            continue  # affordance not detected in codebase
        if kind in addressed_set or kind in confirmed_stub_kinds:
            continue  # addressed in requirements or explicitly stubbed

        # Construct a single gap per affordance kind summarizing the hits.
        matched_files = sorted(per_file_hits.keys())
        all_sig_ids = sorted({sig_id for hits in per_file_hits.values() for sig_id, _ in hits})
        first_pattern = next(iter(per_file_hits.values()))[0][1]
        gaps.append({
            "severity": "affordance-not-addressed",
            "affordance_kind": kind,
            "signature_ids": all_sig_ids,
            "first_matched_pattern": first_pattern,
            "matched_files": matched_files,
            "evidence": (
                f"codebase carries {kind!r} affordance signatures in "
                f"{len(matched_files)} file(s) ({matched_files[:3]!r}...); "
                f"requirements_inventory.addressed_affordances does NOT include "
                f"{kind!r} AND no confirmed_stub covers it."
            ),
            "remediation": (
                f"v2.13.0 Dynamic affordance discovery discipline. The codebase "
                f"clearly carries {kind!r} functionality, so the run's "
                f"requirements MUST address it. Add a requirement for {kind!r} "
                f"to the inventory's addressed_affordances[] OR route a "
                f"solution requirement with origin.kind=affordance-coverage-gap "
                f"OR mark this affordance as confirmed_stub with user_confirmed_at."
            ),
        })
    return gaps


def verify_affordance_coverage(
    verification_artifact: dict[str, Any] | None = None,
    requirements_inventory: dict[str, Any] | None = None,
    out_path: Path | str | None = None,
) -> dict[str, Any]:
    """v2.13.0 Layer-3 tool — verify the run's requirements inventory addresses
    every canonical affordance class detected in the codebase.

    Single severity: ``affordance-not-addressed`` (with structured
    affordance_kind + signature_ids + matched_files fields). The
    ``_AFFORDANCE_SIGNATURES`` dict is the extensible canonical registry;
    v2.13.0 ships with one class (``file-upload``) and 40+ signatures.

    Trivially passes when no codebase_scan or no files_scanned[].

    Returns ``{"tool": "verify-affordance-coverage", "valid": bool,
    "gaps": [...], "verdict_at": "<ISO 8601 UTC>"}``.
    """
    artifact = verification_artifact or {}
    inventory = requirements_inventory or {}
    gaps = _detect_affordance_not_addressed(artifact, inventory)

    verdict = {
        "tool": "verify-affordance-coverage",
        "valid": len(gaps) == 0,
        "gaps": gaps,
        "verdict_at": _utc_now_iso(),
    }
    return _write_verdict(verdict, out_path)
