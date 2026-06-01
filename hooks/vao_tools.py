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
# Tool 7 — verify-live-verification-claim (v2.2.0)
# ===========================================================================


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
# Localhost / non-deployed URL patterns.
_NON_DEPLOYED_URL_MARKERS = (
    "localhost",
    "127.0.0.1",
    "0.0.0.0",
    "://localhost",
    "://127.",
    "file://",
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


# ---------------------------------------------------------------------------
# v2.4.0 — External-state assertion + Evidence-artifact citation
# ---------------------------------------------------------------------------

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
        if any(marker in url_lower for marker in _NON_DEPLOYED_URL_MARKERS):
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

    lv = sub.add_parser("verify-live-verification-claim")
    lv.add_argument("--artifact", required=True, help="Path to verification-artifact JSON.")
    lv.add_argument("--bug", required=True, help="Path to bug-description JSON.")
    lv.add_argument("--out", required=True, help="Path to write the verdict JSON.")

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
    elif args.tool == "verify-live-verification-claim":
        verdict = verify_live_verification_claim(
            verification_artifact=_load_json(args.artifact),
            bug_description=_load_json(args.bug),
            out_path=args.out,
        )
        ok = verdict["valid"]
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
