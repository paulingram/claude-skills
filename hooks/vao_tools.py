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
    """v2.12.0 — UNIFIED test-path detector. Recognizes the UNION of all
    test-file heuristics across the plugin (v2.0.0 fake-data audit + v2.8.0
    standing-red audit + future detectors). A file path is a TEST file if:

      - It lives under a recognized test directory: ``tests/``, ``__tests__/``,
        ``__mocks__/``, ``test/``, ``fixtures/``, ``mocks/``.
      - It has a ``.test.`` or ``.spec.`` infix in its basename.
      - Its basename starts with ``test_`` (pytest convention).
      - Its basename ends with ``_test.py`` / ``test.py`` (Go-pytest convention).
      - Its basename ends with ``_spec.rb`` (Ruby rspec convention).

    Test files may legitimately contain fake data, standing-red markers, and
    other patterns the production-code audits forbid; this function lets
    every Layer 3 tool exclude them consistently. Returns ``False`` for
    non-string input rather than raising.
    """
    if not isinstance(file_path, str) or not file_path:
        return False
    fp = file_path.lower().replace("\\", "/")
    # Path-anchored test-directory markers — startswith OR contains as `/.../`.
    test_dir_markers = ("tests/", "__tests__/", "__mocks__/", "test/", "fixtures/", "mocks/")
    if any(fp.startswith(m) or f"/{m}" in fp for m in test_dir_markers):
        return True
    # Filename-infix markers — .test. / .spec.
    if ".test." in fp or ".spec." in fp:
        return True
    # Basename-based markers.
    base = fp.rsplit("/", 1)[-1]
    if base.startswith("test_"):
        return True
    if base.endswith("_test.py") or base.endswith("test.py"):
        return True
    if base.endswith("_spec.rb"):
        return True
    return False


def _looks_like_test_path(path: str) -> bool:
    """Deprecated alias for :func:`_is_test_path` — preserved for v2.8.0 call
    sites until they migrate. v2.12.0 unified the two detectors after the
    audit found they diverged on 3 of 8 test paths (``fixtures/`` and
    ``__mocks__/`` were test paths for v2.6.0 but not v2.8.0; ``_test.py``
    suffix was a test path for v2.8.0 but not v2.6.0). New code should call
    :func:`_is_test_path` directly.
    """
    return _is_test_path(path)


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
# Tool 9 — verify-live-data-wiring (v2.6.0)
# ===========================================================================
#
# The 9th deterministic Layer 3 tool. Closes the failure mode v2.0.0's
# verify_no_fake_data missed: backend gets wired up live, but pre-existing
# mock wiring in the frontend never gets removed — UI silently renders mock
# fallbacks. Verbatim heirship-app-v3 case: backend extracted 71 facts + 13
# persons; client workspace still mock-wired for documents/facts; UI shows
# no extraction status. Two-pass verification: Playwright assess (capture
# network response, assert UI rendered value matches) THEN code-side audit
# (grep diff + touched files for mock-state residue). 5 named severities.

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


# ===========================================================================
# Tool 10 — verify-no-standing-red (v2.8.0)
# ===========================================================================

_STANDING_RED_MARKERS: tuple[tuple[str, str], ...] = (
    ("comment-standing-red", "// standing red"),
    ("comment-standing-red-block", "/* standing red"),
    ("comment-will-go-green-when", "will go green when"),
    ("comment-will-go-green-once", "will go green once"),
    ("comment-documents-the-gap", "documents the gap"),
    ("comment-known-broken", "known broken"),
    ("comment-known-bug", "known bug"),
    ("comment-not-yet-fixed", "not yet fixed"),
    ("comment-red-regression", "// red regression"),
    ("comment-standing-failure", "standing failure"),
    ("test-fixme-fn", "test.fixme("),
    ("it-fixme-fn", "it.fixme("),
    ("test-fail-fn", "test.fail("),
    ("it-fail-fn", "it.fail("),
    ("pytest-xfail", "@pytest.mark.xfail"),
    ("pytest-xfail-raw", "pytest.xfail("),
)

_CROSS_LAYER_SR_ORIGIN_KINDS: frozenset[str] = frozenset({
    "cross-layer-backend-required",
    "cross-layer-frontend-required",
})


def _detect_standing_red_committed(
    verification_artifact: dict[str, Any],
) -> list[dict[str, Any]]:
    """A newly-added test file contains a standing-red marker AND is not
    covered by a confirmed_stubs[] entry → fire."""
    diff_files = verification_artifact.get("diff_files") or []
    touched = verification_artifact.get("touched_file_contents") or {}
    confirmed_stubs = verification_artifact.get("confirmed_stubs") or []
    # Confirmed-stub entries can be strings (path) or dicts ({path, reason, user_confirmed_at}).
    confirmed_paths: set[str] = set()
    for stub in confirmed_stubs:
        if isinstance(stub, str):
            confirmed_paths.add(stub)
        elif isinstance(stub, dict):
            p = stub.get("path") or stub.get("test_path")
            if isinstance(p, str):
                confirmed_paths.add(p)

    gaps: list[dict[str, Any]] = []
    seen_pairs: set[tuple[str, str]] = set()

    def scan_text(path: str, text: str) -> None:
        if not _looks_like_test_path(path):
            return
        if path in confirmed_paths:
            return
        text_lower = text.lower()
        for marker_id, pattern in _STANDING_RED_MARKERS:
            if pattern.lower() in text_lower:
                key = (path, marker_id)
                if key in seen_pairs:
                    continue
                seen_pairs.add(key)
                gaps.append({
                    "severity": "standing-red-committed",
                    "test_path": path,
                    "marker_id": marker_id,
                    "marker": pattern,
                    "evidence": (
                        f"test file {path!r} contains standing-red marker {pattern!r} "
                        f"(marker_id={marker_id}); not covered by a confirmed_stubs[] entry"
                    ),
                    "remediation": (
                        "v2.8.0 No standing-red discipline. Replace the failing test "
                        "with a real fix that makes the test pass, OR route the unfixed "
                        "layer via a solution requirement (origin.kind: "
                        "cross-layer-backend-required / cross-layer-frontend-required), "
                        "OR mark this test as a confirmed_stub with explicit user "
                        "confirmation. A failing test committed as documentation is "
                        "the failure mode this discipline closes."
                    ),
                })

    for df in diff_files:
        if not isinstance(df, dict):
            continue
        path = df.get("path")
        if not isinstance(path, str):
            continue
        # Scan added_lines first (the change introduced the marker).
        added = df.get("added_lines") or []
        if added:
            scan_text(path, "\n".join(a for a in added if isinstance(a, str)))
        # Also scan the file's current contents if provided.
        content = touched.get(path)
        if isinstance(content, str):
            scan_text(path, content)

    # Test files in touched_file_contents that weren't in the diff (the agent
    # may have authored a test in this change without listing it in diff_files).
    for path, content in touched.items():
        if not isinstance(path, str) or not isinstance(content, str):
            continue
        scan_text(path, content)

    return gaps


def _detect_cross_layer_fix_not_routed(
    verification_artifact: dict[str, Any],
) -> list[dict[str, Any]]:
    """When the agent's cross-layer diagnosis names an unfixed layer AND a
    standing-red test was committed AND no SR of cross-layer-* origin kind
    was created → fire."""
    diagnosis = verification_artifact.get("cross_layer_diagnosis") or {}
    if not isinstance(diagnosis, dict):
        return []
    unfixed_layer = diagnosis.get("unfixed_layer")
    if not isinstance(unfixed_layer, str) or not unfixed_layer:
        return []

    # Was a standing-red test committed for this diagnosis?
    standing_red_gaps = _detect_standing_red_committed(verification_artifact)
    if not standing_red_gaps:
        return []

    # Was an SR of cross-layer-* origin kind created?
    srs = verification_artifact.get("solution_requirements_created") or []
    routed = False
    for sr in srs:
        if not isinstance(sr, dict):
            continue
        origin = sr.get("origin") or {}
        kind = origin.get("kind") if isinstance(origin, dict) else None
        if isinstance(kind, str) and kind in _CROSS_LAYER_SR_ORIGIN_KINDS:
            routed = True
            break

    if routed:
        return []

    return [{
        "severity": "cross-layer-fix-not-routed",
        "unfixed_layer": unfixed_layer,
        "evidence": (
            f"cross_layer_diagnosis names {unfixed_layer!r} as the unfixed layer; "
            f"{len(standing_red_gaps)} standing-red test(s) committed for the "
            f"diagnosed bug; no SR with origin.kind in {sorted(_CROSS_LAYER_SR_ORIGIN_KINDS)!r} "
            f"was created."
        ),
        "remediation": (
            "v2.8.0 No standing-red discipline. The diagnosis correctly identified "
            "a cross-layer bug. Route the unfixed layer via a solution requirement "
            "with origin.kind=cross-layer-backend-required (or "
            "cross-layer-frontend-required) so the orchestrator dispatches the right "
            "team in the same run. The committed standing-red test is documentation "
            "of the gap, NOT a substitute for the fix."
        ),
    }]


def verify_no_standing_red(
    verification_artifact: dict[str, Any] | None = None,
    out_path: Path | str | None = None,
) -> dict[str, Any]:
    """v2.8.0 Layer-3 tool — verify the agent did NOT commit a failing test
    as documentation of a known bug.

    Checks the verification artifact against the 2 named severities:
      1. standing-red-committed — a newly-added test contains a standing-red
         marker AND is not covered by a confirmed_stubs[] entry
      2. cross-layer-fix-not-routed — cross_layer_diagnosis names an unfixed
         layer AND a standing-red test was committed AND no SR of
         cross-layer-* origin kind was created

    Args:
      verification_artifact: dict with diff_files[], touched_file_contents{},
        confirmed_stubs[], cross_layer_diagnosis{}, solution_requirements_created[].
      out_path: optional path to write the verdict JSON.

    Returns::

        {
          "tool": "verify-no-standing-red",
          "valid": bool,
          "gaps": [{"severity", "test_path"|"unfixed_layer", "evidence", "remediation"}],
          "verdict_at": "<ISO 8601 UTC>"
        }

    Trivially passes when no standing-red markers AND no cross_layer_diagnosis
    — fully backwards-compatible with pre-v2.8.0 artifacts.

    Deterministic / bit-stable output for given inputs (sorted-keys + indent=2).
    """
    artifact = verification_artifact or {}
    gaps: list[dict[str, Any]] = []

    gaps += _detect_standing_red_committed(artifact)
    gaps += _detect_cross_layer_fix_not_routed(artifact)

    verdict = {
        "tool": "verify-no-standing-red",
        "valid": len(gaps) == 0,
        "gaps": gaps,
        "verdict_at": _utc_now_iso(),
    }
    return _write_verdict(verdict, out_path)


# ===========================================================================
# Tool 11 — verify-no-end-of-run-deferral (v2.10.0)
# ===========================================================================

# Phrases that signal an end-of-run "Deferred" catalog. Each entry is matched
# case-insensitively as a substring against the agent's final_report text.
# Keep the list tight: false positives (legitimate uses of "deferred" in
# architectural decision documentation, etc.) are mitigated by requiring
# a marker AND by allowing the artifact to declare a per-item disposition
# (SR or confirmed-stub) — see _detect_wrap_up_with_known_bugs.
_DEFERRAL_CATALOG_MARKERS: tuple[tuple[str, str], ...] = (
    ("hourglass-deferred", "⏳ Deferred"),
    ("hourglass-emoji-deferred", "⏳ deferred"),
    ("deferred-em-dash", "Deferred — "),
    ("deferred-en-dash", "Deferred – "),
    ("deferred-N-bug", "deferred 7 bug"),
    ("deferred-N-bug-variant", "deferred N bug"),
    ("cluster-by-cluster", "cluster-by-cluster"),
    ("a-arrow-b-arrow-c", "A → B → C"),
    ("a-arrow-b-arrow-c-ascii", "A -> B -> C"),
    ("each-a-real-change", "each a real change"),
    ("not-a-one-liner", "not a one-liner"),
    ("i-would-take-them", "I'd take them"),
    ("defer-future-change", "Defer to a future change"),
    ("punt-to-later", "punt to later"),
    ("pick-up-next-time", "pick up next time"),
    ("out-of-scope-this-session", "out of scope for this session"),
)

# Phrases that signal an end-of-run followup-decision question. The agent
# is asking the user to decide what to do next AFTER the run claims to be
# complete — the v0.9.20 forbidden "do you want me to proceed?" gate.
_FOLLOWUP_QUESTION_MARKERS: tuple[tuple[str, str], ...] = (
    ("want-me-to-continue", "Want me to continue"),
    ("your-call", "Your call"),
    ("ideally-fresh-context", "ideally in a fresh context"),
    ("say-the-word", "say the word"),
    ("let-me-know-if", "let me know if"),
    ("shall-i-proceed", "Shall I proceed"),
    ("do-you-want-me-to", "Do you want me to"),
    ("should-i-take", "Should I take"),
    ("is-it-ok-if-i", "Is it OK if I"),
    ("if-youd-like", "If you'd like"),
)

# An item in the final report is considered "dispositioned" when it carries
# at least one of these citations to a sanctioned channel.
_ITEM_DISPOSITION_CITATIONS: tuple[str, ...] = (
    "commit-sha:",
    "SR-",  # solution requirement id (SR-101 / SR-B23-101 / etc.)
    "confirmed_stub",
    "confirmed-stub",
    "implementing_commits",
    # v2.12.0 — v2.11.0 per-persona coverage IS a sanctioned disposition channel.
    # Without these tokens, a legitimate v2.11.0 final report (per-persona
    # findings + Playwright run citations) trips v2.10.0's wrap-up gate.
    "playwright_test_runs",
    "per_persona_findings",
    "persona_id:",
    "tested green",
    "tested-green",
    "entry_point:",
)


def _scan_markers(text: str, markers: tuple[tuple[str, str], ...]) -> list[tuple[str, str]]:
    """Return the list of (marker_id, pattern) found in `text` (case-insensitive)."""
    if not isinstance(text, str) or not text:
        return []
    lower = text.lower()
    hits: list[tuple[str, str]] = []
    for marker_id, pattern in markers:
        if pattern.lower() in lower:
            hits.append((marker_id, pattern))
    return hits


def _detect_deferred_work_catalog(
    verification_artifact: dict[str, Any],
) -> list[dict[str, Any]]:
    """The final report names items as 'deferred' / clusters them under
    A→B→C→D framing / uses any of the canonical deferral-catalog markers."""
    final_report = verification_artifact.get("final_report") or ""
    if not isinstance(final_report, str) or not final_report:
        return []
    hits = _scan_markers(final_report, _DEFERRAL_CATALOG_MARKERS)
    gaps: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for marker_id, pattern in hits:
        if marker_id in seen_ids:
            continue
        seen_ids.add(marker_id)
        gaps.append({
            "severity": "deferred-work-catalog",
            "marker_id": marker_id,
            "marker": pattern,
            "evidence": (
                f"final_report contains deferral-catalog marker {pattern!r} "
                f"(marker_id={marker_id})"
            ),
            "remediation": (
                "v2.10.0 No end-of-run deferral discipline. Every in-scope item "
                "must reach one of three dispositions by run-end: (a) fixed in "
                "this change, (b) routed via a solution requirement with a "
                "canonical origin.kind, OR (c) explicit confirmed-stub with "
                "user-citation. Cataloguing items as 'Deferred' with a clustered "
                "follow-up offer is the failure mode this discipline closes."
            ),
        })
    return gaps


def _detect_followup_decision_question(
    verification_artifact: dict[str, Any],
) -> list[dict[str, Any]]:
    """The final report ends with a 'Want me to continue?' / 'Your call' /
    'ideally in a fresh context' style follow-up question that bounces the
    work decision back to the user."""
    final_report = verification_artifact.get("final_report") or ""
    if not isinstance(final_report, str) or not final_report:
        return []
    hits = _scan_markers(final_report, _FOLLOWUP_QUESTION_MARKERS)
    gaps: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for marker_id, pattern in hits:
        if marker_id in seen_ids:
            continue
        seen_ids.add(marker_id)
        gaps.append({
            "severity": "followup-decision-question",
            "marker_id": marker_id,
            "marker": pattern,
            "evidence": (
                f"final_report contains followup-question marker {pattern!r} "
                f"(marker_id={marker_id})"
            ),
            "remediation": (
                "v2.10.0 No end-of-run deferral discipline. Run-end is forward "
                "motion (per v0.9.20 default-mode-of-operation), not a checkpoint "
                "where the user picks which clusters to authorize next. Either "
                "the work was done OR the work was routed via SR — never "
                "bounced back as a 'Want me to continue?' decision question."
            ),
        })
    return gaps


def _detect_wrap_up_with_known_bugs(
    verification_artifact: dict[str, Any],
) -> list[dict[str, Any]]:
    """The final report enumerates ≥ 3 in-scope items AND none of them has
    a sanctioned per-item disposition (commit-sha / SR / confirmed-stub)."""
    final_report = verification_artifact.get("final_report") or ""
    if not isinstance(final_report, str) or not final_report:
        return []

    # Heuristic: count bullets / numbered items in the report.
    bullet_lines = 0
    for line in final_report.splitlines():
        stripped = line.lstrip()
        if not stripped:
            continue
        if (
            stripped.startswith("- ")
            or stripped.startswith("* ")
            or stripped.startswith("• ")
            or (len(stripped) >= 2 and stripped[0].isdigit() and stripped[1] in ".)")
            or (len(stripped) >= 3 and stripped[:2].isdigit() and stripped[2] in ".)")
        ):
            bullet_lines += 1

    if bullet_lines < 3:
        return []

    # Are any per-item dispositions cited?
    srs = verification_artifact.get("solution_requirements_created") or []
    confirmed_stubs = verification_artifact.get("confirmed_stubs") or []
    implementing_commits = verification_artifact.get("implementing_commits") or []
    # v2.12.0 — v2.11.0 per-persona path-coverage is a sanctioned disposition
    # channel. A run that lists per-persona test outcomes IS dispositioned
    # (the playwright_test_runs[] array is the citation).
    playwright_runs = verification_artifact.get("playwright_test_runs") or []
    per_persona_findings = verification_artifact.get("per_persona_findings") or {}
    has_dispositions = bool(
        srs or confirmed_stubs or implementing_commits
        or playwright_runs or per_persona_findings
    )

    # Also accept inline citations in the report text.
    has_inline_citation = any(
        citation in final_report for citation in _ITEM_DISPOSITION_CITATIONS
    )

    if has_dispositions or has_inline_citation:
        return []

    return [{
        "severity": "wrap-up-with-known-bugs",
        "bullet_count": bullet_lines,
        "evidence": (
            f"final_report enumerates {bullet_lines} bulleted / numbered items "
            f"with no per-item disposition citation (no solution_requirements_created, "
            f"no confirmed_stubs, no implementing_commits, no inline commit-sha/SR/"
            f"confirmed-stub references in the report text)."
        ),
        "remediation": (
            "v2.10.0 No end-of-run deferral discipline. Every enumerated in-scope "
            "item must cite ONE of: (a) the commit SHA range that fixed it, "
            "(b) the SR ID with origin.kind that routed it, OR (c) the confirmed-stub "
            "entry with user-citation. An enumerated list with no per-item disposition "
            "is the wrap-up-with-known-bugs failure mode."
        ),
    }]


def verify_no_end_of_run_deferral(
    verification_artifact: dict[str, Any] | None = None,
    out_path: Path | str | None = None,
) -> dict[str, Any]:
    """v2.10.0 Layer-3 tool — verify the agent did NOT end the run by
    cataloguing in-scope work as 'Deferred' and bouncing the unfixed items
    back to the user as a 'Want me to continue?' decision question.

    Checks the verification artifact against the 3 named severities:
      1. deferred-work-catalog — final report contains a canonical
         deferral-catalog marker (12-pattern allowlist)
      2. followup-decision-question — final report contains a canonical
         followup-question marker (10-pattern allowlist)
      3. wrap-up-with-known-bugs — final report enumerates ≥ 3 in-scope
         items AND no per-item disposition (commit-sha / SR / confirmed-stub)
         is cited

    Args:
      verification_artifact: dict with final_report (str — the agent's
        verbatim user-facing run-end report), solution_requirements_created[]
        (the SRs the run routed), confirmed_stubs[] (entries with
        user_confirmed_at), implementing_commits[] (commit SHA ranges).
      out_path: optional path to write the verdict JSON.

    Returns::

        {
          "tool": "verify-no-end-of-run-deferral",
          "valid": bool,
          "gaps": [{"severity", "marker_id"|"bullet_count", "evidence", "remediation"}],
          "verdict_at": "<ISO 8601 UTC>"
        }

    Trivially passes when final_report is empty / absent — fully
    backwards-compatible with pre-v2.10.0 artifacts.

    Deterministic / bit-stable output for given inputs (sorted-keys + indent=2).
    """
    artifact = verification_artifact or {}
    gaps: list[dict[str, Any]] = []

    gaps += _detect_deferred_work_catalog(artifact)
    gaps += _detect_followup_decision_question(artifact)
    gaps += _detect_wrap_up_with_known_bugs(artifact)

    verdict = {
        "tool": "verify-no-end-of-run-deferral",
        "valid": len(gaps) == 0,
        "gaps": gaps,
        "verdict_at": _utc_now_iso(),
    }
    return _write_verdict(verdict, out_path)


# ===========================================================================
# Tool 12 — verify-per-persona-path-coverage (v2.11.0)
# ===========================================================================

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

# v2.13.0 — Patterns that identify a LOCAL test environment URL. A Playwright
# `entry_url` matching any of these (case-insensitive substring) counts as a
# local run. Anything not matching counts as a live-dev run (the persona's
# declared `entry_point` URL is the canonical live-dev target).
_LOCAL_ENV_HOST_PATTERNS: tuple[str, ...] = (
    "localhost",
    "127.0.0.1",
    "0.0.0.0",
    "file://",
    ".local",
    "::1",
    "host.docker.internal",
)


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


# ===========================================================================
# Tool 13 — verify-affordance-coverage (v2.13.0)
# ===========================================================================

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


# ===========================================================================
# Tool 14 — verify-no-implementation-scope-cut (v2.14.0)
# ===========================================================================

# v2.14.0 — Phrases the orchestrator scans for in the user's prompt to set
# scope_mandate.full_build_required: true. Case-insensitive substring match.
_FULL_BUILD_MANDATE_PHRASES: tuple[str, ...] = (
    "implement everything in full",
    "implement everything",
    "implement it all",
    "implement all of it",
    "build everything",
    "build the whole thing",
    "do everything in full",
    "do everything",
    "ship it all",
    "ship the whole thing",
    "entire build",
    "complete build",
    "full build",
)

# Forbidden agent-output phrases that signal an "Honest scope statement" cut
# — the agent unilaterally cuts to a foundation subset and frames the cut
# as virtuous. Case-insensitive substring match.
_HONEST_SCOPE_STATEMENT_MARKERS: tuple[tuple[str, str], ...] = (
    ("honest-scope-statement-header", "Honest scope statement"),
    ("warning-honest-scope", "⚠️ Honest scope"),
    ("scope-statement-framing", "scope statement"),
    ("shippable-and-true-hyphen", "shippable-and-true"),
    ("shippable-and-true-spaces", "shippable and true"),
    ("i-stopped-at-the-boundary", "I stopped at the"),
    ("stopped-at-boundary-deliberately", "stopped at the boundary deliberately"),
    ("stopped-deliberately", "stopped deliberately"),
    ("rather-than-half-land", "rather than half-land"),
    ("multi-agent-build-foundation", "multi-agent build on this foundation"),
    ("land-incrementally-without-rework", "land incrementally without rework"),
    ("complete-m0-foundation", "complete M0 foundation"),
    ("foundation-deployed-and-tested", "foundation, deployed and tested"),
)

# Phrases that frame a partial build as a complete "foundation" when the
# mandate was full-build. These are scope-narrowing tells.
_FOUNDATION_ONLY_FRAMING_MARKERS: tuple[tuple[str, str], ...] = (
    ("m0-foundation", "M0 foundation"),
    ("foundation-deployed", "foundation deployed"),
    ("foundation-laid", "foundation laid"),
    ("scaffolding-shipped", "scaffolding shipped"),
    ("skeleton-shipped", "skeleton shipped"),
    ("the-foundation-so-they", "the foundation so they"),
    ("incrementally-land", "incrementally land"),
    ("incremental-landing", "incremental landing"),
)

# Patterns that suggest the agent enumerated deferred milestones. v2.14.0
# uses simple substring matching for these; v2.14.x may upgrade to regex.
_MILESTONE_DEFERRAL_PATTERNS: tuple[tuple[str, str], ...] = (
    ("milestones-m1-m7", "milestones M1"),
    ("m0-boundary", "M0 boundary"),
    ("plans-08", "plans/08"),
    ("m1-build", "M1 is"),
    ("m1-through-m7", "M1 through M7"),
    ("m1-m7-dash", "M1–M7"),
    ("m1-m7-hyphen", "M1-M7"),
)


def _detect_honest_scope_statement_emitted(
    verification_artifact: dict[str, Any],
    scope_mandate: dict[str, Any],
) -> list[dict[str, Any]]:
    """Final report contains an Honest scope statement / shippable-and-true /
    I-stopped-deliberately marker AND scope_mandate.full_build_required is true."""
    if not scope_mandate.get("full_build_required"):
        return []
    final_report = verification_artifact.get("final_report") or ""
    if not isinstance(final_report, str) or not final_report:
        return []
    hits = _scan_markers(final_report, _HONEST_SCOPE_STATEMENT_MARKERS)
    gaps: list[dict[str, Any]] = []
    seen: set[str] = set()
    for marker_id, pattern in hits:
        if marker_id in seen:
            continue
        seen.add(marker_id)
        gaps.append({
            "severity": "honest-scope-statement-emitted",
            "marker_id": marker_id,
            "marker": pattern,
            "evidence": (
                f"final_report contains Honest-scope-statement marker {pattern!r} "
                f"(marker_id={marker_id}) AND scope_mandate.full_build_required "
                f"is true (user's prompt named a full-build mandate)."
            ),
            "remediation": (
                "v2.14.0 No implementation-time scope cut discipline. The user's "
                "prompt named a full-build mandate; the agent unilaterally cut "
                "to a foundation subset and announced the cut as virtuous. The "
                "agent's run must (a) implement the full mandate, (b) route SRs "
                "with origin.kind=incomplete-implementation-scope-required for "
                "the unimplemented portions, OR (c) carry confirmed-stub entries "
                "with user_confirmed_at for them. Forbidden phrases: 'Honest "
                "scope statement', 'shippable-and-true', 'I stopped at the "
                "boundary deliberately', 'rather than half-land', 'multi-agent "
                "build on this foundation', 'land incrementally without rework'."
            ),
        })
    return gaps


def _detect_foundation_only_framing(
    verification_artifact: dict[str, Any],
    scope_mandate: dict[str, Any],
) -> list[dict[str, Any]]:
    """Final report contains foundation-only framing AND full-build mandate
    was set AND no SR/confirmed-stub covers the unimplemented portion."""
    if not scope_mandate.get("full_build_required"):
        return []
    final_report = verification_artifact.get("final_report") or ""
    if not isinstance(final_report, str) or not final_report:
        return []
    hits = _scan_markers(final_report, _FOUNDATION_ONLY_FRAMING_MARKERS)
    if not hits:
        return []
    # Check whether SRs OR confirmed-stubs cover the unimplemented portion.
    srs = verification_artifact.get("solution_requirements_created") or []
    confirmed_stubs = verification_artifact.get("confirmed_stubs") or []
    has_scope_cut_disposition = False
    for sr in srs:
        if isinstance(sr, dict):
            origin = sr.get("origin") or {}
            kind = origin.get("kind") if isinstance(origin, dict) else None
            if isinstance(kind, str) and kind == "incomplete-implementation-scope-required":
                has_scope_cut_disposition = True
                break
    for stub in confirmed_stubs:
        if isinstance(stub, dict):
            scope_cut = stub.get("scope_cut_kind") or stub.get("incomplete_scope")
            if scope_cut:
                has_scope_cut_disposition = True
                break
    if has_scope_cut_disposition:
        return []

    seen: set[str] = set()
    gaps: list[dict[str, Any]] = []
    for marker_id, pattern in hits:
        if marker_id in seen:
            continue
        seen.add(marker_id)
        gaps.append({
            "severity": "foundation-only-framing-with-full-build-mandate",
            "marker_id": marker_id,
            "marker": pattern,
            "evidence": (
                f"final_report frames partial work as a complete 'foundation' "
                f"(marker {pattern!r}, marker_id={marker_id}) AND "
                f"scope_mandate.full_build_required is true AND no SR with "
                f"origin.kind=incomplete-implementation-scope-required was "
                f"routed AND no confirmed-stub entry covers the unimplemented "
                f"portion."
            ),
            "remediation": (
                "v2.14.0 No implementation-time scope cut discipline. The "
                "foundation framing is only valid when the user explicitly "
                "asked for a foundation. Under a full-build mandate the run "
                "must route SRs for the unimplemented milestones OR carry "
                "confirmed-stubs with user_confirmed_at."
            ),
        })
    return gaps


def _detect_unilateral_implementation_scope_cut(
    verification_artifact: dict[str, Any],
    scope_mandate: dict[str, Any],
) -> list[dict[str, Any]]:
    """Final report enumerates deferred milestones (M1–M7 / plans/08 / etc.)
    AND no SR routes them AND scope_mandate.full_build_required is true."""
    if not scope_mandate.get("full_build_required"):
        return []
    final_report = verification_artifact.get("final_report") or ""
    if not isinstance(final_report, str) or not final_report:
        return []
    hits = _scan_markers(final_report, _MILESTONE_DEFERRAL_PATTERNS)
    if not hits:
        return []
    # Check whether SRs with the canonical origin.kind exist.
    srs = verification_artifact.get("solution_requirements_created") or []
    has_scope_cut_sr = False
    for sr in srs:
        if isinstance(sr, dict):
            origin = sr.get("origin") or {}
            kind = origin.get("kind") if isinstance(origin, dict) else None
            if isinstance(kind, str) and kind == "incomplete-implementation-scope-required":
                has_scope_cut_sr = True
                break
    if has_scope_cut_sr:
        return []

    return [{
        "severity": "unilateral-implementation-scope-cut",
        "deferred_milestone_markers": sorted({m for m, _ in hits}),
        "evidence": (
            f"final_report enumerates deferred milestones (markers: "
            f"{sorted({m for m, _ in hits})!r}) AND scope_mandate.full_build_required "
            f"is true AND no SR with "
            f"origin.kind=incomplete-implementation-scope-required was routed."
        ),
        "remediation": (
            "v2.14.0 No implementation-time scope cut discipline. The user "
            "asked for the full build. The agent enumerated deferred milestones "
            "but never routed an SR for them. Either implement the milestones "
            "in this change OR route SRs with "
            "origin.kind=incomplete-implementation-scope-required so the "
            "orchestrator dispatches the right team in a follow-up run OR "
            "carry confirmed-stub entries with user_confirmed_at."
        ),
    }]


def verify_no_implementation_scope_cut(
    verification_artifact: dict[str, Any] | None = None,
    scope_mandate: dict[str, Any] | None = None,
    out_path: Path | str | None = None,
) -> dict[str, Any]:
    """v2.14.0 Layer-3 tool — verify the agent did NOT unilaterally cut to a
    foundation subset and announce the cut as virtuous when the user's
    prompt named a full-build mandate.

    Three named severities:
      1. honest-scope-statement-emitted — final report contains an "Honest
         scope statement" / "shippable-and-true" / "I stopped deliberately"
         marker AND scope_mandate.full_build_required is true.
      2. foundation-only-framing-with-full-build-mandate — final report
         frames partial work as a complete "foundation" AND no SR/
         confirmed-stub covers the unimplemented portion.
      3. unilateral-implementation-scope-cut — final report enumerates
         deferred milestones AND no SR routes them.

    Trivially passes when scope_mandate is empty OR
    scope_mandate.full_build_required is false (backwards-compat with
    runs against partial mandates).
    """
    artifact = verification_artifact or {}
    mandate = scope_mandate or {}
    gaps: list[dict[str, Any]] = []
    gaps += _detect_honest_scope_statement_emitted(artifact, mandate)
    gaps += _detect_foundation_only_framing(artifact, mandate)
    gaps += _detect_unilateral_implementation_scope_cut(artifact, mandate)

    verdict = {
        "tool": "verify-no-implementation-scope-cut",
        "valid": len(gaps) == 0,
        "gaps": gaps,
        "verdict_at": _utc_now_iso(),
    }
    return _write_verdict(verdict, out_path)


# ===========================================================================
# Tool 15 — verify-test-prod-safety-classification (v2.17.0)
# ===========================================================================

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


# ===========================================================================
# v2.18.0 — verify_discipline_registry_current (16th Layer 3 tool)
# ===========================================================================


def verify_discipline_registry_current(
    workspace: str | Path,
    out_path: Path | str | None = None,
) -> dict[str, Any]:
    """v2.18.0 Layer-3 tool — verify the per-codebase discipline registry is
    current relative to the CT6 catalog. Returns standard verdict shape:

      { tool, valid, gaps, verdict_at }

    Each gap carries:
      { severity, discipline, ct6_version, auto_apply_safe,
        auto_update_command, auto_update_skill, sr_origin_kind,
        evidence, remediation }

    Severities:
      - discipline-registry-missing — registry file does not exist (and at
        least one catalog discipline is unapplied — a workspace with all
        disciplines trivially-applied does NOT trigger this severity)
      - discipline-not-applied — no registry entry AND codebase shows the
        discipline has not been applied
      - discipline-stale — registry has an entry BUT codebase shows it is
        no longer applied (surface advanced past applied_at)
    """
    # Lazy import — keeps vao_tools' stdlib-only contract clean when the
    # discipline_registry module is unused.
    from hooks.discipline_registry import (
        DISCIPLINE_CATALOG,
        REGISTRY_RELATIVE_PATH,
        freshness_check,
    )

    workspace_path = Path(workspace)
    # Check registry presence BEFORE calling freshness_check (which writes
    # the registry's last_freshness_check timestamp as a side effect).
    registry_present = (workspace_path / REGISTRY_RELATIVE_PATH).exists()
    findings = freshness_check(workspace_path, DISCIPLINE_CATALOG)
    gaps: list[dict[str, Any]] = []

    if not registry_present and findings:
        gaps.append({
            "severity": "discipline-registry-missing",
            "discipline": None,
            "ct6_version": None,
            "auto_apply_safe": True,
            "auto_update_command": None,
            "auto_update_skill": None,
            "sr_origin_kind": None,
            "evidence": (
                f"per-codebase discipline registry "
                f"{REGISTRY_RELATIVE_PATH!r} does not exist at workspace "
                f"{str(workspace_path)!r} and at least one catalog "
                f"discipline is unapplied."
            ),
            "remediation": (
                "v2.18.0 codebase discipline registry. Phase 0.1 of the "
                "next pipeline run will create the registry and apply any "
                "auto-apply-safe disciplines. Manual creation is also fine "
                "via `/architect-team:discipline-status --apply`."
            ),
        })

    for f in findings:
        gaps.append({
            "severity": f["severity"],
            "discipline": f["discipline"],
            "ct6_version": f["ct6_version"],
            "auto_apply_safe": f["auto_apply_safe"],
            "auto_update_command": f.get("auto_update_command"),
            "auto_update_skill": f.get("auto_update_skill"),
            "sr_origin_kind": f.get("sr_origin_kind"),
            "evidence": f["evidence"],
            "remediation": f["remediation"],
        })

    verdict = {
        "tool": "verify-discipline-registry-current",
        "valid": len(gaps) == 0,
        "gaps": gaps,
        "verdict_at": _utc_now_iso(),
    }
    return _write_verdict(verdict, out_path)


# ===========================================================================
# v2.19.0 — verify_inflight_clarifications_processed (17th Layer 3 tool)
# ===========================================================================


def verify_inflight_clarifications_processed(
    workspace: str | Path,
    run_id: str,
    out_path: Path | str | None = None,
) -> dict[str, Any]:
    """v2.19.0 Layer-3 tool — verify every clarification injected into the
    in-flight inbox has been processed. Fires at Phase 8 of every pipeline.

    2 severities:
      - clarification-silently-ignored — message in inbox has processed_at=null
      - unprocessed-clarification-at-phase-boundary — phase boundary was
        crossed (next phase's start_time > inbox message's injected_at) but
        the message was not yet marked processed at that point. Currently
        emitted only when the inbox carries a `phase_log` array alongside
        the JSONL — when no phase log is present, this severity does not
        fire (orchestrator-discipline self-audit is the future runtime layer).
    """
    from hooks.inflight_inbox import read_inbox, unprocessed_messages

    workspace_path = Path(workspace)
    messages = read_inbox(workspace_path, run_id)
    unprocessed = [m for m in messages if m.get("processed_at") is None]

    gaps: list[dict[str, Any]] = []
    for m in unprocessed:
        gaps.append({
            "severity": "clarification-silently-ignored",
            "message_id": m.get("message_id"),
            "text": (m.get("text") or "")[:200],
            "injected_at": m.get("injected_at"),
            "injected_via": m.get("injected_via"),
            "evidence": (
                f"in-flight inbox message {m.get('message_id')!r} "
                f"(injected at {m.get('injected_at')!r} via "
                f"{m.get('injected_via')!r}) was never processed by the "
                f"orchestrator — processed_at is null at Phase 8."
            ),
            "remediation": (
                "v2.19.0 in-flight clarification injection mechanism. Every "
                "inbox message MUST be classified at a phase boundary (see "
                "the canonical home in common-pipeline-conventions/SKILL.md "
                "## In-flight clarification injection mechanism (v2.19.0)). "
                "Read the message, classify as scope-amendment / clarification "
                "/ out-of-scope per v2.5.0, take the named action, then "
                "`hooks.inflight_inbox.mark_processed(...)`. Re-run Phase 8 "
                "once all messages are processed."
            ),
        })

    verdict = {
        "tool": "verify-inflight-clarifications-processed",
        "valid": len(gaps) == 0,
        "gaps": gaps,
        "total_messages": len(messages),
        "unprocessed_count": len(unprocessed),
        "verdict_at": _utc_now_iso(),
    }
    return _write_verdict(verdict, out_path)


# ===========================================================================
# v2.20.0 — verify_deploy_mandate_satisfied (18th Layer 3 tool)
# ===========================================================================


_DEPLOY_MANDATE_VERBS = (
    "deploy",
    "launch",
    "ship",
    "publish",
    "go live",
    "going live",
    "push to prod",
    "push to dev",
    "push to production",
    "roll out",
    "rolling out",
    "release to",
    "host the",
    "host it",
    "serve from",
)

_DEPLOY_COMPLETENESS_MODIFIERS = (
    "fully",
    "100%",
    "100 percent",
    "all elements",
    "real and functional",
    "no mock",
    "no fake",
    "no mocks",
    "live data",
    "log into",
    "login",
    "hosted url",
    "deployed url",
    "anything less is failure",
    "must have",
    "1 criteria",
    "one criteria",
    "end to end",
    "end-to-end",
    "the application",
    "the product",
    "every screen",
    "every page",
    "every element",
)

_PLAN_ONLY_DELIVERABLE_MARKERS = (
    "plan ✅ delivered",
    "plan delivered",
    "plan is delivered",
    "plan_action.md",
    "_plan.md",
    "as markdown",
    "as a markdown",
    "blueprint",
    "roadmap",
    "plan is a document",
    "comprehensive plan of action",
    "produce a plan",
)

_ADJACENT_DEPENDENCY_MARKERS = (
    "auth fix",
    "fixed uam",
    "demo agents",
    "demo seed",
    "dependency live",
    "dependencies ✅ live",
    "building blocks",
    "existing platforms, not your app",
    "existing platforms not your app",
    "all on your existing platforms",
    "key dependencies",
    "supporting service",
    "attachment support",
    "demo data",
)

_PARTIAL_DEPLOY_MARKERS = (
    "thin slice",
    "thin-slice",
    "quick win",
    "phase 1 live",
    "couple of screens",
    "a few screens",
    "start with just",
    "subset deployed",
    "partial deploy",
    "mvp first",
    "smallest possible vertical slice",
)

_LOCAL_DEPLOY_URL_MARKERS = (
    "localhost",
    "127.0.0.1",
    "0.0.0.0",
    "file://",
    "::1",
    "host.docker.internal",
)


def detect_deploy_mandate_in_prompt(prompt: str) -> dict[str, Any]:
    """Classify a user prompt as carrying a deploy mandate or not.

    Returns:
        {
          "active": bool,
          "target_kind": "fullstack" | "api-only" | "spa-only" | "thin-slice" | None,
          "user_prompt_excerpt": str,    # the matched verb + modifier substring (truncated)
          "matched_verbs": list[str],
          "matched_modifiers": list[str],
        }

    A prompt activates the deploy mandate when it contains at least one deploy
    verb AND at least one completeness modifier. An explicit "thin slice"
    request narrows target_kind without disabling the mandate.
    """
    if not isinstance(prompt, str) or not prompt.strip():
        return {
            "active": False,
            "target_kind": None,
            "user_prompt_excerpt": "",
            "matched_verbs": [],
            "matched_modifiers": [],
        }
    lower = prompt.lower()
    matched_verbs = [v for v in _DEPLOY_MANDATE_VERBS if v in lower]
    matched_modifiers = [m for m in _DEPLOY_COMPLETENESS_MODIFIERS if m in lower]
    # Thin-slice phrasing is its own activation channel — the user explicitly
    # scopes the deploy mandate to a subset, but it IS still a mandate.
    has_thin_slice = any(p in lower for p in ("thin slice", "thin-slice"))
    active = bool(matched_verbs) and (bool(matched_modifiers) or has_thin_slice)

    if not active:
        return {
            "active": False,
            "target_kind": None,
            "user_prompt_excerpt": "",
            "matched_verbs": matched_verbs,
            "matched_modifiers": matched_modifiers,
        }

    # Refine target_kind from prompt content
    if any(p in lower for p in ("thin slice", "thin-slice", "mvp first", "smallest possible")):
        target_kind: str | None = "thin-slice"
    elif "api only" in lower or "api-only" in lower or "backend only" in lower:
        target_kind = "api-only"
    elif "frontend only" in lower or "spa only" in lower or "ui only" in lower:
        target_kind = "spa-only"
    else:
        target_kind = "fullstack"

    return {
        "active": True,
        "target_kind": target_kind,
        "user_prompt_excerpt": (
            (matched_verbs[0] + " ... " + matched_modifiers[0])
            if matched_verbs and matched_modifiers
            else ""
        ),
        "matched_verbs": matched_verbs,
        "matched_modifiers": matched_modifiers,
    }


def _is_localhost_or_file(url: Any) -> bool:
    if not isinstance(url, str) or not url:
        return True  # empty / non-string is NOT a real deploy
    lower = url.lower()
    return any(m in lower for m in _LOCAL_DEPLOY_URL_MARKERS)


def _detect_plan_only_deliverable(final_report: str) -> list[dict[str, Any]]:
    if not isinstance(final_report, str) or not final_report.strip():
        return []
    lower = final_report.lower()
    hits = [m for m in _PLAN_ONLY_DELIVERABLE_MARKERS if m in lower]
    if not hits:
        return []
    return [{
        "severity": "plan-only-deliverable-on-deploy-mandate",
        "matched_markers": hits[:5],
        "evidence": (
            f"final_report cites plan-only deliverable marker(s) "
            f"{hits[:3]!r} when the deploy mandate is active. A markdown plan "
            f"is not a deployment."
        ),
        "remediation": (
            "v2.20.0 deploy mandate discipline. The user mandated a deploy "
            "(verb + completeness modifier matched at intake). A markdown "
            "plan does NOT satisfy the mandate. Build the actual product "
            "backend + wire the frontend + deploy both at real URLs + "
            "verify login + assert live data on every screen. Re-run Phase "
            "8 once all 5 binding criteria are met."
        ),
    }]


def _detect_adjacent_dependencies_claimed(final_report: str) -> list[dict[str, Any]]:
    if not isinstance(final_report, str) or not final_report.strip():
        return []
    lower = final_report.lower()
    hits = [m for m in _ADJACENT_DEPENDENCY_MARKERS if m in lower]
    if not hits:
        return []
    return [{
        "severity": "adjacent-dependencies-claimed-as-deployment",
        "matched_markers": hits[:5],
        "evidence": (
            f"final_report cites adjacent-dependency marker(s) {hits[:3]!r} "
            f"as the deliverable when the deploy mandate is active. Work on "
            f"dependent services (auth fix / demo seeds / attachment support) "
            f"is not the deployment."
        ),
        "remediation": (
            "v2.20.0 deploy mandate discipline. Adjacent dependency work "
            "(auth fix / dependency live / building blocks / existing "
            "platforms) does NOT satisfy a deploy mandate. The product "
            "itself must be deployed at a real URL with the frontend wired "
            "to a real backend. Cite the product's deploy URL — not the "
            "dependency URL — in the final report."
        ),
    }]


def _detect_partial_deploy_passed_off(final_report: str, target_kind: str | None) -> list[dict[str, Any]]:
    if target_kind == "thin-slice":
        return []  # user explicitly authorized the thin slice — no severity
    if not isinstance(final_report, str) or not final_report.strip():
        return []
    lower = final_report.lower()
    hits = [m for m in _PARTIAL_DEPLOY_MARKERS if m in lower]
    if not hits:
        return []
    return [{
        "severity": "partial-deploy-passed-off-as-deploy",
        "matched_markers": hits[:5],
        "evidence": (
            f"final_report cites partial-deploy framing {hits[:3]!r} when the "
            f"deploy mandate target_kind is {target_kind!r}, not 'thin-slice'. "
            f"Partial deploys satisfy the mandate only when the user "
            f"explicitly asks for one."
        ),
        "remediation": (
            "v2.20.0 deploy mandate discipline. A thin slice is not a full "
            "deploy. Either (a) extend the implementation to cover every "
            "screen + every endpoint, OR (b) confirm with the user that the "
            "thin-slice target_kind is acceptable (re-classify the mandate "
            "to target_kind='thin-slice') BEFORE marking the run complete."
        ),
    }]


def _detect_missing_binding_criteria(
    verification_artifact: dict[str, Any],
    target_kind: str | None,
) -> list[dict[str, Any]]:
    gaps: list[dict[str, Any]] = []

    deploy_target_url = verification_artifact.get("deploy_target_url")
    frontend_url = verification_artifact.get("frontend_url")
    login_verified = verification_artifact.get("login_verified")
    login_evidence = verification_artifact.get("login_verification_evidence_path")
    live_data_assertions = verification_artifact.get("live_data_assertions") or []
    mock_residue_count = verification_artifact.get("mock_residue_count")
    unwired_elements_count = verification_artifact.get("unwired_elements_count")

    require_backend = target_kind in (None, "fullstack", "api-only", "thin-slice")
    require_frontend = target_kind in (None, "fullstack", "spa-only", "thin-slice")

    if require_backend and (not deploy_target_url or _is_localhost_or_file(deploy_target_url)):
        gaps.append({
            "severity": "deploy-mandate-not-satisfied",
            "binding_criterion": "deploy_target_url",
            "evidence": (
                f"deploy_target_url is missing OR localhost / file:// "
                f"({deploy_target_url!r}). A deploy mandate requires a "
                f"reachable backend URL."
            ),
            "remediation": (
                "v2.20.0 deploy mandate discipline. Deploy the backend "
                "service to a real URL (ECS / Lambda / Cloud Run / Fly / "
                "Render / etc.); record the URL in the verification "
                "artifact's `deploy_target_url` field; confirm a 200 "
                "response on the health endpoint."
            ),
        })

    if require_frontend and (not frontend_url or _is_localhost_or_file(frontend_url)):
        gaps.append({
            "severity": "deploy-mandate-not-satisfied",
            "binding_criterion": "frontend_url",
            "evidence": (
                f"frontend_url is missing OR localhost / file:// "
                f"({frontend_url!r}). A deploy mandate requires a hosted "
                f"frontend the user can open in a browser."
            ),
            "remediation": (
                "v2.20.0 deploy mandate discipline. Deploy the frontend "
                "(S3+CloudFront / Vercel / Netlify / nginx on ECS / etc.) "
                "and record the URL in the verification artifact's "
                "`frontend_url` field."
            ),
        })

    if login_verified is not True:
        gaps.append({
            "severity": "deploy-mandate-not-satisfied",
            "binding_criterion": "login_verified",
            "evidence": (
                f"login_verified is not True ({login_verified!r}). A deploy "
                f"mandate requires a Playwright login run confirming the user "
                f"can access the post-login dashboard at the hosted URL."
            ),
            "remediation": (
                "v2.20.0 deploy mandate discipline. Run Playwright against "
                "the hosted frontend_url; log in with a real test user; "
                "capture a screenshot of the post-login state; set "
                "login_verified=true; cite the screenshot path in "
                "login_verification_evidence_path."
            ),
        })

    if login_verified is True and not login_evidence:
        gaps.append({
            "severity": "deploy-mandate-not-satisfied",
            "binding_criterion": "login_verification_evidence_path",
            "evidence": (
                "login_verified=true but no evidence path supplied. The "
                "claim is unverifiable without a screenshot or trace."
            ),
            "remediation": (
                "v2.20.0 deploy mandate discipline. Cite a non-empty file "
                "path in login_verification_evidence_path (.png / .zip / "
                ".har / .json)."
            ),
        })

    if not isinstance(live_data_assertions, list) or len(live_data_assertions) == 0:
        if require_frontend:
            gaps.append({
                "severity": "deploy-mandate-not-satisfied",
                "binding_criterion": "live_data_for_every_screen",
                "evidence": (
                    "live_data_assertions[] is missing or empty. Every "
                    "screen in the oracle spec MUST have a live-data "
                    "assertion proving non-mock data renders."
                ),
                "remediation": (
                    "v2.20.0 deploy mandate discipline. For each screen "
                    "named in the oracle spec, run a Playwright assertion "
                    "that reads a live (non-mock) value from the deployed "
                    "backend; record {screen, live: true, evidence} in "
                    "live_data_assertions[]."
                ),
            })
    else:
        not_live = [a for a in live_data_assertions if not (isinstance(a, dict) and a.get("live") is True)]
        if not_live:
            gaps.append({
                "severity": "deploy-mandate-not-satisfied",
                "binding_criterion": "live_data_for_every_screen",
                "screens_not_live": [a.get("screen") for a in not_live[:5] if isinstance(a, dict)],
                "evidence": (
                    f"{len(not_live)} live_data_assertions[] entries are NOT "
                    f"live (live != true). A deploy mandate requires every "
                    f"screen on live data."
                ),
                "remediation": (
                    "v2.20.0 deploy mandate discipline. Fix the unwired "
                    "screens — wire them to the deployed backend — and "
                    "re-run Playwright to flip every assertion's `live` "
                    "field to true."
                ),
            })

    if isinstance(mock_residue_count, int) and mock_residue_count > 0:
        gaps.append({
            "severity": "deploy-mandate-not-satisfied",
            "binding_criterion": "no_mock_residue",
            "mock_residue_count": mock_residue_count,
            "evidence": (
                f"mock_residue_count = {mock_residue_count} > 0. A deploy "
                f"mandate requires zero mock-state in production paths "
                f"(per v2.6.0 + v2.7.0)."
            ),
            "remediation": (
                "v2.20.0 deploy mandate discipline. Remove every mock-state "
                "signature from the production code path; sweep every "
                "consumer of every shared mock source per v2.7.0; re-run "
                "the v2.6.0 live-data wiring check."
            ),
        })

    if isinstance(unwired_elements_count, int) and unwired_elements_count > 0:
        gaps.append({
            "severity": "deploy-mandate-not-satisfied",
            "binding_criterion": "no_unwired_elements",
            "unwired_elements_count": unwired_elements_count,
            "evidence": (
                f"unwired_elements_count = {unwired_elements_count} > 0. "
                f"A deploy mandate requires every interactive element wired "
                f"to a real handler."
            ),
            "remediation": (
                "v2.20.0 deploy mandate discipline. Wire every interactive "
                "element to a real backend handler (per "
                "interaction-completeness). Unwired controls cannot ship "
                "under a deploy mandate."
            ),
        })

    return gaps


def verify_deploy_mandate_satisfied(
    verification_artifact: dict[str, Any] | None = None,
    deploy_mandate: dict[str, Any] | None = None,
    final_report: str = "",
    out_path: Path | str | None = None,
) -> dict[str, Any]:
    """v2.20.0 Layer-3 tool — verify the deploy mandate is fully satisfied.

    Trivially passes (`valid: True, gaps: []`) when
    `deploy_mandate.active != True` — fully backwards-compatible.

    4 named severities:
      - `deploy-mandate-not-satisfied` — required field missing or invalid
      - `plan-only-deliverable-on-deploy-mandate` — final_report cites a plan as the deliverable
      - `adjacent-dependencies-claimed-as-deployment` — final_report cites adjacent dep work
      - `partial-deploy-passed-off-as-deploy` — partial deploy claimed when target_kind isn't 'thin-slice'
    """
    mandate = deploy_mandate or {}
    if mandate.get("active") is not True:
        verdict = {
            "tool": "verify-deploy-mandate-satisfied",
            "valid": True,
            "gaps": [],
            "deploy_mandate_active": False,
            "verdict_at": _utc_now_iso(),
        }
        return _write_verdict(verdict, out_path)

    artifact = verification_artifact or {}
    target_kind = mandate.get("target_kind")
    report_text = final_report or ""

    gaps: list[dict[str, Any]] = []
    gaps += _detect_missing_binding_criteria(artifact, target_kind)
    gaps += _detect_plan_only_deliverable(report_text)
    gaps += _detect_adjacent_dependencies_claimed(report_text)
    gaps += _detect_partial_deploy_passed_off(report_text, target_kind)

    verdict = {
        "tool": "verify-deploy-mandate-satisfied",
        "valid": len(gaps) == 0,
        "gaps": gaps,
        "deploy_mandate_active": True,
        "target_kind": target_kind,
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

    ldw = sub.add_parser("verify-live-data-wiring")
    ldw.add_argument("--artifact", required=True, help="Path to verification-artifact JSON.")
    ldw.add_argument("--mandate", required=True, help="Path to wiring-mandate JSON.")
    ldw.add_argument("--out", required=True, help="Path to write the verdict JSON.")

    nsr = sub.add_parser("verify-no-standing-red")
    nsr.add_argument("--artifact", required=True, help="Path to verification-artifact JSON.")
    nsr.add_argument("--out", required=True, help="Path to write the verdict JSON.")

    nerd = sub.add_parser("verify-no-end-of-run-deferral")
    nerd.add_argument("--artifact", required=True, help="Path to verification-artifact JSON.")
    nerd.add_argument("--out", required=True, help="Path to write the verdict JSON.")

    pppc = sub.add_parser("verify-per-persona-path-coverage")
    pppc.add_argument("--artifact", required=True, help="Path to verification-artifact JSON.")
    pppc.add_argument("--inventory", required=True, help="Path to persona-inventory JSON.")
    pppc.add_argument("--out", required=True, help="Path to write the verdict JSON.")

    ac = sub.add_parser("verify-affordance-coverage")
    ac.add_argument("--artifact", required=True, help="Path to verification-artifact JSON with codebase_scan.")
    ac.add_argument("--inventory", required=True, help="Path to requirements-inventory JSON with addressed_affordances[].")
    ac.add_argument("--out", required=True, help="Path to write the verdict JSON.")

    nisc = sub.add_parser("verify-no-implementation-scope-cut")
    nisc.add_argument("--artifact", required=True, help="Path to verification-artifact JSON with final_report.")
    nisc.add_argument("--mandate", required=True, help="Path to scope-mandate JSON with full_build_required.")
    nisc.add_argument("--out", required=True, help="Path to write the verdict JSON.")

    tpsc = sub.add_parser("verify-test-prod-safety-classification")
    tpsc.add_argument("--artifact", required=True, help="Path to verification-artifact JSON with test_files[{path,content}].")
    tpsc.add_argument("--target", required=True, help="Path to run-target JSON with url.")
    tpsc.add_argument("--out", required=True, help="Path to write the verdict JSON.")

    drc = sub.add_parser("verify-discipline-registry-current")
    drc.add_argument("--workspace", required=True, help="Path to the target codebase workspace (the repo root).")
    drc.add_argument("--out", required=True, help="Path to write the verdict JSON.")

    icp = sub.add_parser("verify-inflight-clarifications-processed")
    icp.add_argument("--workspace", required=True, help="Path to the target codebase workspace.")
    icp.add_argument("--run-id", required=True, help="The current run-id to inspect.")
    icp.add_argument("--out", required=True, help="Path to write the verdict JSON.")

    dms = sub.add_parser("verify-deploy-mandate-satisfied")
    dms.add_argument("--artifact", required=True, help="Path to verification-artifact JSON.")
    dms.add_argument("--mandate", required=True, help="Path to deploy-mandate JSON with active/target_kind.")
    dms.add_argument("--final-report", required=False, default=None, help="Optional path to final_report text.")
    dms.add_argument("--out", required=True, help="Path to write the verdict JSON.")

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
    elif args.tool == "verify-live-data-wiring":
        verdict = verify_live_data_wiring(
            verification_artifact=_load_json(args.artifact),
            wiring_mandate=_load_json(args.mandate),
            out_path=args.out,
        )
        ok = verdict["valid"]
    elif args.tool == "verify-no-standing-red":
        verdict = verify_no_standing_red(
            verification_artifact=_load_json(args.artifact),
            out_path=args.out,
        )
        ok = verdict["valid"]
    elif args.tool == "verify-no-end-of-run-deferral":
        verdict = verify_no_end_of_run_deferral(
            verification_artifact=_load_json(args.artifact),
            out_path=args.out,
        )
        ok = verdict["valid"]
    elif args.tool == "verify-per-persona-path-coverage":
        verdict = verify_per_persona_path_coverage(
            verification_artifact=_load_json(args.artifact),
            persona_inventory=_load_json(args.inventory),
            out_path=args.out,
        )
        ok = verdict["valid"]
    elif args.tool == "verify-affordance-coverage":
        verdict = verify_affordance_coverage(
            verification_artifact=_load_json(args.artifact),
            requirements_inventory=_load_json(args.inventory),
            out_path=args.out,
        )
        ok = verdict["valid"]
    elif args.tool == "verify-no-implementation-scope-cut":
        verdict = verify_no_implementation_scope_cut(
            verification_artifact=_load_json(args.artifact),
            scope_mandate=_load_json(args.mandate),
            out_path=args.out,
        )
        ok = verdict["valid"]
    elif args.tool == "verify-test-prod-safety-classification":
        verdict = verify_test_prod_safety_classification(
            verification_artifact=_load_json(args.artifact),
            run_target=_load_json(args.target),
            out_path=args.out,
        )
        ok = verdict["valid"]
    elif args.tool == "verify-discipline-registry-current":
        verdict = verify_discipline_registry_current(
            workspace=args.workspace,
            out_path=args.out,
        )
        ok = verdict["valid"]
    elif args.tool == "verify-inflight-clarifications-processed":
        verdict = verify_inflight_clarifications_processed(
            workspace=args.workspace,
            run_id=args.run_id,
            out_path=args.out,
        )
        ok = verdict["valid"]
    elif args.tool == "verify-deploy-mandate-satisfied":
        final_report_text = ""
        if args.final_report:
            final_report_text = Path(args.final_report).read_text(encoding="utf-8")
        verdict = verify_deploy_mandate_satisfied(
            verification_artifact=_load_json(args.artifact),
            deploy_mandate=_load_json(args.mandate),
            final_report=final_report_text,
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
