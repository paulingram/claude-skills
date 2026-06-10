"""hooks.vao — the Verified Agent Output (VAO) Layer 3 verification package.

This package is the split form of the former 5,200-line ``hooks/vao_tools.py``
monolith (R2, v3.10.0). ``hooks/vao_tools.py`` remains as a thin facade that
re-exports every public function + module-level constant + helper the test
suite references and preserves the CLI byte-for-byte. The 20 ``verify_*`` tools
are grouped into per-discipline-family modules (each <= 900 lines); cross-module
helpers (``_utc_now_iso`` / ``_write_verdict`` / ``_is_test_path`` /
``_looks_like_test_path`` / ``_scan_markers``) live in ``hooks/vao/core.py`` and
are imported (dual-form) by the family modules. No behavior change.
"""
