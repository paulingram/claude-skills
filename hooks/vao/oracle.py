"""VAO oracle/parity/element/interaction family (4 tools)."""

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


def _normalize_tree(node: Any) -> Any:
    """Deterministic structural normalization for the oracle-match diff.

    Strips whitespace from leaf strings; sorts dict keys; preserves list
    ordering (lists are structurally ordered — a `<header><body>` is NOT
    the same as `<body><header>`).
    """
    if isinstance(node, str):
        return node.strip()
    if isinstance(node, dict):
        return {k: _normalize_tree(v) for k, v in sorted(node.items())}
    if isinstance(node, list):
        return [_normalize_tree(v) for v in node]
    return node


def _walk_divergences(
    expected: Any, actual: Any, path: str = ""
) -> list[dict[str, Any]]:
    """Recursive structural diff between two normalized trees. Each
    divergence is a record with ``path`` (dotted-path), ``expected``,
    ``actual``, and a ``severity`` heuristic.
    """
    divs: list[dict[str, Any]] = []
    if type(expected) is not type(actual):
        divs.append({
            "path": path or "/",
            "expected_type": type(expected).__name__,
            "actual_type": type(actual).__name__,
            "expected": expected,
            "actual": actual,
            "severity": "type-mismatch",
        })
        return divs
    if isinstance(expected, dict):
        for key in sorted(set(expected.keys()) | set(actual.keys())):
            sub_path = f"{path}.{key}" if path else key
            if key not in actual:
                divs.append({
                    "path": sub_path,
                    "expected": expected[key],
                    "actual": None,
                    "severity": "missing-in-actual",
                })
            elif key not in expected:
                divs.append({
                    "path": sub_path,
                    "expected": None,
                    "actual": actual[key],
                    "severity": "extra-in-actual",
                })
            else:
                divs.extend(_walk_divergences(expected[key], actual[key], sub_path))
        return divs
    if isinstance(expected, list):
        for i in range(max(len(expected), len(actual))):
            sub_path = f"{path}[{i}]"
            if i >= len(actual):
                divs.append({
                    "path": sub_path,
                    "expected": expected[i],
                    "actual": None,
                    "severity": "missing-in-actual",
                })
            elif i >= len(expected):
                divs.append({
                    "path": sub_path,
                    "expected": None,
                    "actual": actual[i],
                    "severity": "extra-in-actual",
                })
            else:
                divs.extend(_walk_divergences(expected[i], actual[i], sub_path))
        return divs
    if expected != actual:
        divs.append({
            "path": path or "/",
            "expected": expected,
            "actual": actual,
            "severity": "value-mismatch",
        })
    return divs


def verify_oracle_match(
    built: dict[str, Any],
    oracle_spec: dict[str, Any],
    out_path: Path | str | None = None,
) -> dict[str, Any]:
    """Compare the built tree against the frozen oracle spec.

    Args:
      built: a dict representing the built tree (component tree, route table,
        schema). Deterministic walk; key ordering canonicalized.
      oracle_spec: the frozen oracle spec dict from Phase 0.5.
      out_path: optional path to write the verdict JSON.

    Returns the verdict dict::

        {
          "tool": "verify-oracle-match",
          "matched": bool,
          "divergences": [...],
          "match_pct": float in [0.0, 1.0],
          "verdict_at": "<ISO 8601 UTC>"
        }
    """
    oracle_tree = oracle_spec.get("tree", oracle_spec)
    built_tree = built.get("tree", built)
    normalized_oracle = _normalize_tree(oracle_tree)
    normalized_built = _normalize_tree(built_tree)
    divergences = _walk_divergences(normalized_oracle, normalized_built)
    matched = len(divergences) == 0

    # Match percentage — simplistic 1 - (divergences / max(oracle leaves, 1))
    leaf_count = _count_leaves(normalized_oracle) or 1
    match_pct = max(0.0, min(1.0, 1.0 - (len(divergences) / leaf_count)))

    verdict = {
        "tool": "verify-oracle-match",
        "matched": matched,
        "divergences": divergences,
        "match_pct": round(match_pct, 4),
        "verdict_at": _utc_now_iso(),
    }
    return _write_verdict(verdict, out_path)


def _count_leaves(node: Any) -> int:
    """Count the leaf values in a normalized tree."""
    if isinstance(node, dict):
        return sum(_count_leaves(v) for v in node.values()) or len(node)
    if isinstance(node, list):
        return sum(_count_leaves(v) for v in node) or len(node)
    return 1


def verify_every_element(
    built_components: list[dict[str, Any]] | None = None,
    oracle_spec: dict[str, Any] | None = None,
    out_path: Path | str | None = None,
) -> dict[str, Any]:
    """Coverage check: every oracle-named element MUST be present in the
    built components, wired to a non-stub handler, and driven by a
    Playwright test.

    Args:
      built_components: list of {"path": "...", "elements": [{"selector": ..., "handler": ..., "tested_by": [...]}, ...]} dicts.
      oracle_spec: oracle spec carrying ``elements: [{"selector": "..."}, ...]``.
      out_path: optional path to write the verdict JSON.

    Returns::

        {
          "tool": "verify-every-element",
          "coverage": float in [0.0, 1.0],
          "missing": [...],
          "stub": [...],
          "untested": [...],
          "verdict_at": "<ISO 8601 UTC>"
        }
    """
    built_components = built_components or []
    oracle_spec = oracle_spec or {}
    elements = oracle_spec.get("elements", []) or []

    # Index built elements by selector for O(1) lookup.
    built_index: dict[str, dict[str, Any]] = {}
    for component in built_components:
        if not isinstance(component, dict):
            continue
        for el in component.get("elements", []) or []:
            sel = el.get("selector") if isinstance(el, dict) else None
            if isinstance(sel, str):
                built_index[sel] = el

    missing: list[dict[str, Any]] = []
    stub: list[dict[str, Any]] = []
    untested: list[dict[str, Any]] = []

    for oracle_el in elements:
        if not isinstance(oracle_el, dict):
            continue
        sel = oracle_el.get("selector")
        if not isinstance(sel, str):
            continue
        built_el = built_index.get(sel)
        if built_el is None:
            missing.append({"selector": sel, "label": oracle_el.get("label")})
            continue
        handler = built_el.get("handler")
        if not handler or handler in ("() => {}", "null", "noop", "stub"):
            stub.append({"selector": sel, "handler": handler})
        tested_by = built_el.get("tested_by") or []
        if not tested_by:
            untested.append({"selector": sel})

    total = len(elements) or 1
    found = total - len(missing)
    coverage = round(found / total, 4) if total else 1.0

    verdict = {
        "tool": "verify-every-element",
        "coverage": coverage,
        "missing": missing,
        "stub": stub,
        "untested": untested,
        "verdict_at": _utc_now_iso(),
    }
    return _write_verdict(verdict, out_path)


def _parent_path(dom_tree: dict[str, Any], target_selector: str) -> str | None:
    """Walk the rendered-DOM tree and return the dotted parent-path of the
    target selector. Returns None if the selector is absent.

    The dom_tree shape::

        {
          "tag": "body",
          "selector": "body",
          "children": [
            {"tag": "div", "selector": "[data-component='AppShellLayout']",
             "children": [...]},
            ...
          ]
        }
    """
    def walk(node: dict[str, Any], parents: list[str]) -> str | None:
        if not isinstance(node, dict):
            return None
        sel = node.get("selector")
        if sel == target_selector:
            return " > ".join(parents) if parents else "<root>"
        for child in node.get("children", []) or []:
            sub_parents = parents + ([sel] if isinstance(sel, str) else [])
            found = walk(child, sub_parents)
            if found is not None:
                return found
        return None

    return walk(dom_tree, [])


def verify_rendered_parity(
    candidate_dom: dict[str, Any] | None = None,
    oracle_dom: dict[str, Any] | None = None,
    oracle_spec: dict[str, Any] | None = None,
    candidate_screenshot_path: str | None = None,
    oracle_screenshot_path: str | None = None,
    pixel_diff_pct: float | None = None,
    out_path: Path | str | None = None,
) -> dict[str, Any]:
    """The HEIRSHIP-AMENDMENT tool — operates on the RENDERED DOM, not the
    source component tree. Catches the canonical heirship-app-v2 case where
    `<TaCrumbs />` exists in both candidate and oracle SOURCE but at
    different mount levels in the RENDERED output.

    Args:
      candidate_dom: rendered-DOM snapshot of the candidate (the work).
      oracle_dom: rendered-DOM snapshot of the oracle (the reference).
      oracle_spec: oracle spec carrying ``chrome_topology: [{"anchor": ..., "expected_parent": ...}, ...]``.
      candidate_screenshot_path: optional path to the captured candidate screenshot.
      oracle_screenshot_path: optional path to the captured oracle screenshot.
      pixel_diff_pct: optional pre-computed pixel-diff percentage (the
        plugin's tests pass this in; a live runtime would compute it via
        playwright + pixelmatch).
      out_path: optional path to write the verdict JSON.

    Returns::

        {
          "tool": "verify-rendered-parity",
          "matched": bool,
          "divergences": [{"anchor": ..., "expected_level": ..., "actual_level": ..., "severity": ...}],
          "pixel_diff_pct": float,
          "screenshot_paths": {"oracle": ..., "candidate": ..., "diff": ...},
          "verdict_at": "<ISO 8601 UTC>"
        }
    """
    candidate_dom = candidate_dom or {}
    oracle_dom = oracle_dom or {}
    oracle_spec = oracle_spec or {}
    chrome_topology = oracle_spec.get("chrome_topology", []) or []

    divergences: list[dict[str, Any]] = []
    for entry in chrome_topology:
        if not isinstance(entry, dict):
            continue
        anchor = entry.get("anchor")
        if not isinstance(anchor, str):
            continue
        oracle_parent = _parent_path(oracle_dom, anchor)
        candidate_parent = _parent_path(candidate_dom, anchor)
        expected_level = entry.get("expected_parent", oracle_parent)
        if candidate_parent is None:
            divergences.append({
                "anchor": anchor,
                "expected_level": expected_level,
                "actual_level": None,
                "severity": "missing-in-candidate",
            })
        elif oracle_parent is None:
            divergences.append({
                "anchor": anchor,
                "expected_level": expected_level,
                "actual_level": candidate_parent,
                "severity": "missing-in-oracle",
            })
        elif candidate_parent != oracle_parent:
            divergences.append({
                "anchor": anchor,
                "expected_level": oracle_parent,
                "actual_level": candidate_parent,
                "severity": "architectural-mismatch",
            })

    # Pixel-diff threshold — anything >= 1% is a severity flag. The plugin's
    # own tests synthesize this; the live runtime would compute via pixelmatch.
    pixel_diff = pixel_diff_pct if pixel_diff_pct is not None else 0.0
    if pixel_diff >= 0.01:
        divergences.append({
            "anchor": "<screenshot>",
            "expected_level": "pixel-identical",
            "actual_level": f"{pixel_diff*100:.2f}% diff",
            "severity": "pixel-divergence",
        })

    matched = len(divergences) == 0

    verdict = {
        "tool": "verify-rendered-parity",
        "matched": matched,
        "divergences": divergences,
        "pixel_diff_pct": pixel_diff,
        "screenshot_paths": {
            "candidate": candidate_screenshot_path,
            "oracle": oracle_screenshot_path,
            "diff": None,
        },
        "verdict_at": _utc_now_iso(),
    }
    return _write_verdict(verdict, out_path)


def _resolved_target(entry: dict[str, Any]) -> tuple[str | None, str | None]:
    """For an interactions[] entry, return the target (action_kind, target)
    pair the built work must match.

    Priority:
      1. If `resolved_intent` is populated → user-confirmed canonical intent.
         Shape: a string `"<action_kind>:<target>"` (e.g., `"navigate:/sign-in"`).
      2. Else if `action_kind != "no-op"` → the observed action is the target
         (the mockup's literal behavior is binding).
      3. Else → return (None, None) — no-op elements are not verified.
    """
    resolved = entry.get("resolved_intent")
    if isinstance(resolved, str) and resolved:
        if ":" in resolved:
            kind, target = resolved.split(":", 1)
            return kind.strip(), target.strip()
        return resolved.strip(), None
    if isinstance(resolved, dict):
        return resolved.get("action_kind"), resolved.get("target")
    action_kind = entry.get("action_kind")
    if action_kind and action_kind != "no-op":
        return action_kind, entry.get("target_url_or_state")
    return None, None


def verify_interactions_honored(
    built_components: list[dict[str, Any]] | None = None,
    oracle_spec: dict[str, Any] | None = None,
    out_path: Path | str | None = None,
) -> dict[str, Any]:
    """v2.1.0 Layer-3 tool — verify the built code honors every interactions[]
    entry in the frozen oracle spec.

    Args:
      built_components: list of {"path": ..., "handlers": [{"trigger_selector",
        "action_kind", "target_url_or_state"}, ...]} dicts.
      oracle_spec: oracle spec carrying ``interactions: [{"interaction_id",
        "trigger_selector", "semantic_label", "action_kind", "observed_effect",
        "target_url_or_state", "resolved_intent": optional}, ...]``.
      out_path: optional path to write the verdict JSON.

    Returns::

        {
          "tool": "verify-interactions-honored",
          "matched": bool,
          "gaps": [{"trigger_selector", "expected_action_kind",
                    "expected_target", "actual_action_kind", "actual_target",
                    "severity": "intent-violated" | "missing-handler" |
                    "action-kind-mismatch"}],
          "honored_count": int,
          "total_count": int,
          "verdict_at": "<ISO 8601 UTC>"
        }

    Determinism contract: sorted-keys + indent=2 output for given inputs
    (same discipline as the other 5 Layer-3 tools).
    """
    built_components = built_components or []
    oracle_spec = oracle_spec or {}
    interactions = oracle_spec.get("interactions", []) or []

    # Index built handlers by trigger_selector for O(1) lookup. A single
    # selector may have multiple handlers across components (e.g., a global
    # click delegate AND a component-local handler); collect them all into a
    # list so we can find any matching action_kind + target.
    handler_index: dict[str, list[dict[str, Any]]] = {}
    for component in built_components:
        if not isinstance(component, dict):
            continue
        for handler in component.get("handlers", []) or []:
            if not isinstance(handler, dict):
                continue
            sel = handler.get("trigger_selector")
            if isinstance(sel, str):
                handler_index.setdefault(sel, []).append(handler)

    gaps: list[dict[str, Any]] = []
    honored = 0
    total = 0

    for entry in interactions:
        if not isinstance(entry, dict):
            continue
        sel = entry.get("trigger_selector")
        if not isinstance(sel, str):
            continue
        expected_kind, expected_target = _resolved_target(entry)
        if expected_kind is None:
            # no-op element with no resolved_intent — not verified
            continue
        total += 1
        handlers = handler_index.get(sel, [])
        if not handlers:
            gaps.append({
                "trigger_selector": sel,
                "expected_action_kind": expected_kind,
                "expected_target": expected_target,
                "actual_action_kind": None,
                "actual_target": None,
                "severity": "missing-handler",
            })
            continue
        # Find a handler matching both action_kind AND target. Allow partial
        # match (action_kind matches but target differs) to surface a finer
        # severity.
        kind_matches = [h for h in handlers if h.get("action_kind") == expected_kind]
        if not kind_matches:
            # Pick any handler to report the actual action_kind
            actual = handlers[0]
            gaps.append({
                "trigger_selector": sel,
                "expected_action_kind": expected_kind,
                "expected_target": expected_target,
                "actual_action_kind": actual.get("action_kind"),
                "actual_target": actual.get("target_url_or_state"),
                "severity": "action-kind-mismatch",
            })
            continue
        # action_kind matches; check target
        target_match = next(
            (h for h in kind_matches if h.get("target_url_or_state") == expected_target),
            None,
        )
        if target_match is None:
            actual = kind_matches[0]
            gaps.append({
                "trigger_selector": sel,
                "expected_action_kind": expected_kind,
                "expected_target": expected_target,
                "actual_action_kind": actual.get("action_kind"),
                "actual_target": actual.get("target_url_or_state"),
                "severity": "intent-violated",
            })
            continue
        honored += 1

    verdict = {
        "tool": "verify-interactions-honored",
        "matched": len(gaps) == 0,
        "gaps": gaps,
        "honored_count": honored,
        "total_count": total,
        "verdict_at": _utc_now_iso(),
    }
    return _write_verdict(verdict, out_path)
