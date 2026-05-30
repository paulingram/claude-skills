#!/usr/bin/env python3
"""Layer 3 of the Verified Agent Output (VAO) framework — the five deterministic
verification tools.

Each tool produces machine-mediated PROOF of a specific agent claim. The
review-evidence schema v7 requires each tool's verdict-path citation; the
agent's prose attestation is no longer accepted as the truth-source.

The five tools — one per known failure shape (plus the heirship-amendment
verify-rendered-parity tool that closes the source-audit-vs-rendered-output
gap):

  verify_oracle_match       — Layer-1-shape: structural diff against the
                              frozen Phase 0.5 oracle spec.
  verify_baseline_clean     — v1.6.0-shape: bash-history audit for forbidden
                              git operations in the teammate's tool-call log.
  verify_no_fake_data       — v1.7.0-shape: diff sweep for design-literal
                              strings + MSW handlers + page.route fulfill
                              stubs + hardcoded JSON responses in production
                              code.
  verify_every_element      — interaction-completeness shape: for every
                              oracle-named interactive element, confirm it
                              is present, wired to a non-stub handler, and
                              driven by a Playwright test.
  verify_rendered_parity    — heirship chrome-mount-level shape: operates on
                              the RENDERED DOM + a screenshot diff, NOT the
                              source component tree. Catches the case where
                              an element exists in both candidate and oracle
                              source but mounts at different parent nodes in
                              the rendered output.

Each tool:
  - Is deterministic (bit-stable output for given inputs).
  - Writes its verdict JSON to
    <cwd>/.architect-team/vao-verdicts/<task-id>-<tool>.json by default
    (override via ``out_path=`` for testing).
  - Is callable as a Python function AND via the ``vao`` CLI subcommand.

Stdlib only for the first four tools. ``verify_rendered_parity`` reads
pre-captured DOM snapshots from a JSON input path (matching the fixture
shape) — when invoked against a LIVE URL it would shell out to playwright,
but the in-tree contract is "the DOM snapshot is the input"; the deployed
runtime would have its own playwright wrapper. This separation keeps the
plugin's own test surface stdlib-only.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Iterable


# ---------------------------------------------------------------------------
# Common output helpers
# ---------------------------------------------------------------------------


def _utc_now_iso() -> str:
    """Return current UTC time as ISO 8601 string. Lazy import keeps the
    module's hot-path stdlib-only at import time."""
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _write_verdict(verdict: dict[str, Any], out_path: Path | str | None) -> dict[str, Any]:
    """Persist the verdict JSON to disk (if ``out_path`` is given) and return it.

    Sort-keys + indent=2 makes output byte-stable for given inputs — the
    determinism contract.
    """
    if out_path is not None:
        out_path = Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(verdict, indent=2, sort_keys=True), encoding="utf-8")
    return verdict


# ===========================================================================
# Tool 1 — verify-oracle-match
# ===========================================================================


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


# ===========================================================================
# Tool 2 — verify-baseline-clean
# ===========================================================================


# The six forbidden teammate-git operations from v1.6.0's discipline. Each
# pattern matches the destructive shape WITHOUT firing on legitimate
# read/inspect operations (`git status`, `git log`, `git diff`, etc).
_FORBIDDEN_GIT_PATTERNS: tuple[tuple[str, re.Pattern], ...] = (
    ("git stash", re.compile(r"\bgit\s+stash\b(?!\s+list)", re.IGNORECASE)),
    ("git reset --hard", re.compile(r"\bgit\s+reset\s+--hard\b", re.IGNORECASE)),
    ("git rebase", re.compile(r"\bgit\s+rebase\b", re.IGNORECASE)),
    ("git commit --amend", re.compile(r"\bgit\s+commit\s+.*--amend\b", re.IGNORECASE)),
    ("git checkout other-branch", re.compile(r"\bgit\s+checkout\s+(?!--|HEAD)(?:-[bB]\s+)?[\w./-]+\b", re.IGNORECASE)),
    ("git clean -f", re.compile(r"\bgit\s+clean\s+(?:.*-f|\.\s)", re.IGNORECASE)),
)


def verify_baseline_clean(
    tool_call_log: list[dict[str, Any]] | None = None,
    baseline_sha: str | None = None,
    out_path: Path | str | None = None,
) -> dict[str, Any]:
    """Audit a teammate's tool-call log for forbidden git operations.

    Args:
      tool_call_log: a list of ledger entries; each entry should have
        ``tool``, ``args`` (with ``command`` for Bash entries), and ``ts``.
      baseline_sha: optional baseline SHA (for the verdict record; not
        used in the audit logic itself).
      out_path: optional path to write the verdict JSON.

    Returns::

        {
          "tool": "verify-baseline-clean",
          "clean": bool,
          "violations": [{"op": ..., "args": ..., "line": ..., "ts": ...}],
          "baseline_sha": str | None,
          "verdict_at": "<ISO 8601 UTC>"
        }
    """
    tool_call_log = tool_call_log or []
    violations: list[dict[str, Any]] = []
    for idx, entry in enumerate(tool_call_log):
        if entry.get("tool") != "Bash":
            continue
        args = entry.get("args", {})
        cmd = args.get("command") if isinstance(args, dict) else None
        if not isinstance(cmd, str):
            continue
        for op_name, pattern in _FORBIDDEN_GIT_PATTERNS:
            if pattern.search(cmd):
                violations.append({
                    "op": op_name,
                    "args": cmd,
                    "line": idx,
                    "ts": entry.get("ts"),
                })
                break  # one forbidden op per entry — first match wins
    verdict = {
        "tool": "verify-baseline-clean",
        "clean": len(violations) == 0,
        "violations": violations,
        "baseline_sha": baseline_sha,
        "verdict_at": _utc_now_iso(),
    }
    return _write_verdict(verdict, out_path)


# ===========================================================================
# Tool 3 — verify-no-fake-data
# ===========================================================================


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


def _is_test_path(file_path: str) -> bool:
    """Heuristic — a file path is a TEST file if it lives under a tests dir,
    has a .test. or .spec. infix, or its filename starts with test_. Test
    files may legitimately contain fake data; the fake-data audit only
    flags hits in production code.
    """
    fp = file_path.lower().replace("\\", "/")
    # Path-anchored markers — fire if the path STARTS with or CONTAINS the marker.
    test_markers = ("tests/", "__tests__/", "__mocks__/", "test/", "fixtures/", "mocks/")
    if any(fp.startswith(m) or f"/{m}" in fp for m in test_markers):
        return True
    # Filename-style markers — .test. / .spec. infixes in the basename.
    if ".test." in fp or ".spec." in fp:
        return True
    # Python-style test files: test_*.py.
    base = fp.rsplit("/", 1)[-1]
    if base.startswith("test_"):
        return True
    return False


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


# ===========================================================================
# Tool 4 — verify-every-element
# ===========================================================================


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


# ===========================================================================
# Tool 5 — verify-rendered-parity (heirship amendment)
# ===========================================================================


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


# ===========================================================================
# Tool 6 — verify-interactions-honored (v2.1.0)
# ===========================================================================


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


# ===========================================================================
# CLI
# ===========================================================================


def _load_json(path: str) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Layer 3 of VAO — deterministic verification tools.",
    )
    sub = parser.add_subparsers(dest="tool", required=True)

    om = sub.add_parser("verify-oracle-match")
    om.add_argument("--built", required=True, help="Path to built-tree JSON.")
    om.add_argument("--oracle", required=True, help="Path to oracle-spec JSON.")
    om.add_argument("--out", required=True, help="Path to write the verdict JSON.")

    bc = sub.add_parser("verify-baseline-clean")
    bc.add_argument("--log", required=True, help="Path to tool-call-log JSONL or JSON-array.")
    bc.add_argument("--baseline-sha", default=None, help="Optional baseline SHA for the verdict record.")
    bc.add_argument("--out", required=True, help="Path to write the verdict JSON.")

    nfd = sub.add_parser("verify-no-fake-data")
    nfd.add_argument("--diff", required=True, help="Path to diff-files JSON.")
    nfd.add_argument("--oracle", required=True, help="Path to oracle-spec JSON.")
    nfd.add_argument("--out", required=True, help="Path to write the verdict JSON.")

    ee = sub.add_parser("verify-every-element")
    ee.add_argument("--components", required=True, help="Path to built-components JSON.")
    ee.add_argument("--oracle", required=True, help="Path to oracle-spec JSON.")
    ee.add_argument("--out", required=True, help="Path to write the verdict JSON.")

    rp = sub.add_parser("verify-rendered-parity")
    rp.add_argument("--candidate-dom", required=True, help="Path to candidate rendered-DOM JSON.")
    rp.add_argument("--oracle-dom", required=True, help="Path to oracle rendered-DOM JSON.")
    rp.add_argument("--oracle-spec", required=True, help="Path to oracle-spec JSON.")
    rp.add_argument("--candidate-screenshot", default=None, help="Optional candidate screenshot path.")
    rp.add_argument("--oracle-screenshot", default=None, help="Optional oracle screenshot path.")
    rp.add_argument("--pixel-diff", type=float, default=None, help="Pre-computed pixel-diff percentage.")
    rp.add_argument("--out", required=True, help="Path to write the verdict JSON.")

    ih = sub.add_parser("verify-interactions-honored")
    ih.add_argument("--components", required=True, help="Path to built-components JSON.")
    ih.add_argument("--oracle", required=True, help="Path to oracle-spec JSON.")
    ih.add_argument("--out", required=True, help="Path to write the verdict JSON.")

    args = parser.parse_args(argv)

    if args.tool == "verify-oracle-match":
        verdict = verify_oracle_match(_load_json(args.built), _load_json(args.oracle), out_path=args.out)
        ok = verdict["matched"]
    elif args.tool == "verify-baseline-clean":
        log = _load_log(args.log)
        verdict = verify_baseline_clean(log, args.baseline_sha, out_path=args.out)
        ok = verdict["clean"]
    elif args.tool == "verify-no-fake-data":
        verdict = verify_no_fake_data(_load_json(args.diff), _load_json(args.oracle), out_path=args.out)
        ok = verdict["clean"]
    elif args.tool == "verify-every-element":
        verdict = verify_every_element(_load_json(args.components), _load_json(args.oracle), out_path=args.out)
        ok = verdict["coverage"] >= 0.99
    elif args.tool == "verify-rendered-parity":
        verdict = verify_rendered_parity(
            candidate_dom=_load_json(args.candidate_dom),
            oracle_dom=_load_json(args.oracle_dom),
            oracle_spec=_load_json(args.oracle_spec),
            candidate_screenshot_path=args.candidate_screenshot,
            oracle_screenshot_path=args.oracle_screenshot,
            pixel_diff_pct=args.pixel_diff,
            out_path=args.out,
        )
        ok = verdict["matched"]
    elif args.tool == "verify-interactions-honored":
        verdict = verify_interactions_honored(
            built_components=_load_json(args.components),
            oracle_spec=_load_json(args.oracle),
            out_path=args.out,
        )
        ok = verdict["matched"]
    else:  # pragma: no cover
        return 2

    return 0 if ok else 2


def _load_log(path: str) -> list[dict[str, Any]]:
    """Read a tool-call log — JSONL or JSON-array."""
    text = Path(path).read_text(encoding="utf-8").strip()
    if not text:
        return []
    if text.startswith("["):
        return json.loads(text)
    entries: list[dict[str, Any]] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            entries.append(obj)
    return entries


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
