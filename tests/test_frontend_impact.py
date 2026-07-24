# -*- coding: utf-8 -*-
"""Tests for hooks/frontend_impact.py — the frontend-impact detector.

The detector decides whether a change set has "frontend impact" — the trigger
for the v3.44.0 mandatory end-to-end verification gate (a passing unit test can
never satisfy "done" when frontend impact is present). Per the owner directive
(2026-07-24), impact fires on EITHER signal (broadest):

  (a) the change set touches frontend files, OR
  (b) a changed backend endpoint/contract is consumed by a frontend route
      (evidenced in ROUTE_MAP.md / INTEGRATION_MAP.md).

Stdlib-only, pure function, no I/O — the caller supplies the changed file list,
the changed-endpoint list (derived from the backend diff), and the map texts.
"""
from __future__ import annotations

from hooks.frontend_impact import (
    FRONTEND_FILE_EXTENSIONS,
    changed_files_touch_frontend,
    detect_frontend_impact,
)


# --------------------------------------------------------------------------- #
# signal (a) — frontend files in the diff
# --------------------------------------------------------------------------- #

def test_frontend_files_trigger_impact() -> None:
    r = detect_frontend_impact(["src/App.tsx", "api/users.py"])
    assert r["impacted"] is True
    assert "src/App.tsx" in r["frontend_files"]
    assert "frontend-files" in r["signals"]


def test_extensions_cover_common_frameworks() -> None:
    for ext in (".tsx", ".jsx", ".vue", ".svelte", ".astro", ".css", ".scss", ".less"):
        assert ext in FRONTEND_FILE_EXTENSIONS


def test_changed_files_touch_frontend_helper() -> None:
    assert changed_files_touch_frontend(["a.py", "b.tsx", "c.css"]) == ["b.tsx", "c.css"]
    assert changed_files_touch_frontend(["a.py", "b.py"]) == []


def test_path_hint_directory_counts_ambiguous_ext() -> None:
    # a `.ts` file is ambiguous alone, but under a clear frontend dir it counts
    r = detect_frontend_impact(["web/src/components/Button.ts"])
    assert r["impacted"] is True
    assert "frontend-files" in r["signals"]


def test_ambiguous_ext_outside_frontend_dir_does_not_count() -> None:
    # a bare `.ts` in a server dir is NOT a frontend file on its own
    r = detect_frontend_impact(["server/lib/queue.ts"])
    assert r["impacted"] is False


# --------------------------------------------------------------------------- #
# signal (b) — backend contract consumed by a frontend route
# --------------------------------------------------------------------------- #

def test_backend_endpoint_consumed_by_frontend_route_triggers() -> None:
    route_map = "## API endpoint catalog\n- `GET /api/users` — called by src/pages/Users.tsx"
    r = detect_frontend_impact(
        ["api/users.py"],
        changed_endpoints=["/api/users"],
        route_map_text=route_map,
    )
    assert r["impacted"] is True
    assert "backend-contract-consumed-by-frontend" in r["signals"]
    assert any(h["endpoint"] == "/api/users" for h in r["backend_contract_hits"])


def test_backend_endpoint_in_integration_map_triggers() -> None:
    r = detect_frontend_impact(
        ["svc/orders.py"],
        changed_endpoints=["/orders"],
        integration_map_text="The web frontend consumes /orders for the cart view.",
    )
    assert r["impacted"] is True
    assert "backend-contract-consumed-by-frontend" in r["signals"]


def test_backend_endpoint_absent_from_maps_no_impact() -> None:
    r = detect_frontend_impact(
        ["api/internal_cron.py"],
        changed_endpoints=["/internal/cron-tick"],
        route_map_text="- `GET /api/users` — called by Users.tsx",
        integration_map_text="frontend consumes /api/users",
    )
    assert r["impacted"] is False
    assert r["signals"] == []


def test_no_endpoints_no_maps_pure_backend_no_impact() -> None:
    r = detect_frontend_impact(["api/users.py", "api/db.py"])
    assert r["impacted"] is False
    assert r["frontend_files"] == []
    assert r["signals"] == []


# --------------------------------------------------------------------------- #
# either-signal is OR, not AND
# --------------------------------------------------------------------------- #

def test_frontend_file_alone_triggers_without_endpoints_or_maps() -> None:
    assert detect_frontend_impact(["theme.css"])["impacted"] is True


def test_backend_contract_alone_triggers_without_frontend_files() -> None:
    r = detect_frontend_impact(
        ["svc/handler.py"],
        changed_endpoints=["/orders"],
        integration_map_text="/orders consumed by the web frontend",
    )
    assert r["impacted"] is True
    assert r["frontend_files"] == []


# --------------------------------------------------------------------------- #
# shape + edge cases
# --------------------------------------------------------------------------- #

def test_empty_input_is_no_impact_with_reason() -> None:
    r = detect_frontend_impact([])
    assert r["impacted"] is False
    assert isinstance(r["reason"], str) and r["reason"]


def test_result_shape_is_stable() -> None:
    r = detect_frontend_impact(["a.py"])
    assert set(r) == {"impacted", "frontend_files", "backend_contract_hits", "signals", "reason"}
    assert isinstance(r["frontend_files"], list)
    assert isinstance(r["backend_contract_hits"], list)
    assert isinstance(r["signals"], list)


def test_non_list_changed_files_is_tolerated() -> None:
    # a stray None / str must not crash the gate (fail-open to no-impact-detected
    # would be wrong for a gate, so a bad input raises TypeError deliberately)
    import pytest
    with pytest.raises(TypeError):
        detect_frontend_impact("not-a-list")  # type: ignore[arg-type]
