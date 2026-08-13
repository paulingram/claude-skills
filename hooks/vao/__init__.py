"""hooks.vao — the Verified Agent Output (VAO) Layer 3 verification package.

This package is the split form of the former 5,200-line ``hooks/vao_tools.py``
monolith (R2, v3.10.0). ``hooks/vao_tools.py`` remains as a thin facade that
re-exports every public function + module-level constant + helper the test
suite references and preserves the CLI byte-for-byte. The 23 ``verify_*`` tools
are grouped into per-discipline-family modules (each <= 900 lines); cross-module
helpers (``_utc_now_iso`` / ``_write_verdict`` / ``_is_test_path`` /
``_looks_like_test_path`` / ``_scan_markers`` / ``_ITEM_DISPOSITION_CITATIONS`` /
``_is_enumerated_line`` / ``_boundary_pattern`` / ``_first_token_present``) live
in ``hooks/vao/core.py`` and are imported (dual-form) by the family modules.
No behavior change.

The family modules (the list ``hooks/vao_tools.py``'s docstring points readers
here for): ``check_integrity`` (v3.47.0 — the 21st tool, check falsifiability),
``claim_binding`` (v3.59.0 — the 23rd tool: could the cited instrument have come
out differently if the claim were false?),
``core``, ``deferral`` + ``deferral_b`` (end-of-run deferral and the
claims-citation severities), ``deploy_pipeline`` + ``deploy_pipeline_b``,
``fake_data``, ``frontend_e2e`` (v3.55.0 — the 22nd tool, the frontend-E2E
loop-exit genuineness verifier), ``live_verification``, ``mention_context`` (the
shared quote/attribution machinery the claim families use), ``oracle``,
``persona``, ``prod_safety``, ``registry_inflight``, ``scope``.
"""
