# -*- coding: utf-8 -*-
"""Deterministic closeout assessment engine (Closeout / CO-1 … CO-3 support).

Stdlib-only, no import-time side effects. Given the set of files a session has
changed (the working-tree changes, by default), assess whether the
documentation-currency inventory appears STALE relative to those changes — the
deterministic half of the **Closeout** capability.

This engine produces advisory **signals**, NOT a verdict. It is a DOUBLE-CHECK:
the `closeout` skill / `closeout-agent` performs the actual review against the
active requirement and, if docs are lax, performs the update itself (CO-2/CO-3).
The `PreCompact` hook (`precompact-closeout.py`) calls `assess_closeout` and
surfaces the signals as a reminder before context is compacted (CO-1).

The currency-doc inventory below MIRRORS `skills/documentation-currency` (the
canonical inventory the Phase-8 doc-updater + system-architect audit enforce);
`tests/test_closeout.py` pins the key members so the two cannot silently drift.
"""
from __future__ import annotations

import subprocess
from pathlib import PurePosixPath
from typing import Any, Iterable, Optional

# --- currency-doc inventory (mirrors skills/documentation-currency) ----------- #
# Exact repo-root files whose change counts as a documentation update.
CURRENCY_DOC_FILES: tuple[str, ...] = (
    "README.md",
    "CHANGELOG.md",
    "CLAUDE.md",
    "AGENTS.md",
    "docs/CODEBASE_MAP.md",
    "docs/INTEGRATION_MAP.md",
    "phenotypes/README.md",
    "phenotypes/SCHEMA.md",
)
# Per-codebase map basenames — counted as currency docs wherever they live under
# a `docs/` directory (the *_MAP.md convention, incl. the v3.17.0 data dictionary).
CURRENCY_DOC_BASENAMES: tuple[str, ...] = (
    "CODEBASE_MAP.md",
    "INTEGRATION_MAP.md",
    "ROUTE_MAP.md",
    "DESIGN_MAP.md",
    "INTERACTION_INTUITION_MAP.md",
    "DATA_DICTIONARY_MAP.md",
)
# The version source-of-truth (a change here that the CHANGELOG doesn't reflect
# is a strong staleness signal).
VERSION_SOURCE_FILES: tuple[str, ...] = (
    ".claude-plugin/plugin.json",
    ".claude-plugin/marketplace.json",
)

# Docs that carry the inventory counts/grids a NEW surface (skill / agent /
# command) must update. A new surface that does not touch ALL of these is
# undocumented — REGARDLESS of whether some OTHER currency doc (e.g. CHANGELOG)
# was touched. This is the specificity that stops a lone CHANGELOG edit from
# silencing a genuinely-stale README/CODEBASE_MAP inventory grid.
INVENTORY_COUNT_DOCS: tuple[str, ...] = (
    "README.md",
    "CLAUDE.md",
    "docs/CODEBASE_MAP.md",
)

# Directory prefixes whose changes do NOT, by themselves, demand a doc update:
# the gitignored runtime state dir and the OpenSpec workspace (its archive is a
# doc-adjacent artifact the doc-updater reconciles, not "code").
_NON_CODE_PREFIXES: tuple[str, ...] = (
    ".architect-team/",
    "openspec/",
)
# Source roots whose changes DO demand currency. Tests are deliberately excluded
# so a test-only session does not nag (a NEW skill/agent/command is still caught
# via `new_surfaces`, which keys off added files, not the test dir).
_CODE_PREFIXES: tuple[str, ...] = (
    "skills/",
    "agents/",
    "commands/",
    "hooks/",
    "scripts/",
)


def _norm(path: str) -> str:
    """Normalize a path to forward-slash POSIX form (Windows-safe)."""
    return str(PurePosixPath(str(path).replace("\\", "/")))


def is_currency_doc(path: str) -> bool:
    """True if `path` is a documentation-currency inventory member."""
    p = _norm(path)
    if p in CURRENCY_DOC_FILES:
        return True
    parts = p.split("/")
    base = parts[-1]
    # a *_MAP.md basename living under any docs/ directory
    if base in CURRENCY_DOC_BASENAMES and "docs" in parts[:-1]:
        return True
    return False


def is_version_source(path: str) -> bool:
    """True if `path` is a version source-of-truth file."""
    return _norm(path) in VERSION_SOURCE_FILES


def is_code_change(path: str) -> bool:
    """True if `path` is a source change that demands documentation currency.

    Excludes the currency docs themselves, the version sources, the gitignored
    state dir, the OpenSpec workspace, and the test tree. Tuned for this
    stdlib-Python plugin: the top-level catch-all is `.py`-only, so in an
    arbitrary repo a root-level non-Python source/config file is conservatively
    treated as non-code (new first-class surfaces are still caught via
    `new_surfaces`, which keys off skills/agents/commands paths, not extension).
    """
    p = _norm(path)
    if is_currency_doc(p) or is_version_source(p):
        return False
    if p.startswith(_NON_CODE_PREFIXES):
        return False
    if p.startswith("tests/"):
        return False
    if p.startswith(_CODE_PREFIXES):
        return True
    # a top-level Python module (e.g. conftest is under tests/, already excluded)
    if "/" not in p and p.endswith(".py"):
        return True
    return False


def new_surfaces(added_files: Iterable[str]) -> list[dict[str, str]]:
    """Identify newly ADDED first-class surfaces (skill / agent / command) whose
    inventory docs must be updated. Returns `[{kind, name, path}, ...]`."""
    out: list[dict[str, str]] = []
    for raw in added_files or []:
        p = _norm(raw)
        parts = p.split("/")
        if len(parts) == 3 and parts[0] == "skills" and parts[2] == "SKILL.md":
            out.append({"kind": "skill", "name": parts[1], "path": p})
        elif len(parts) == 2 and parts[0] == "agents" and p.endswith(".md"):
            out.append({"kind": "agent", "name": parts[1][:-3], "path": p})
        elif len(parts) == 2 and parts[0] == "commands" and p.endswith(".md"):
            out.append({"kind": "command", "name": parts[1][:-3], "path": p})
    return out


def assess_closeout(
    changed_files: Iterable[str],
    *,
    added_files: Optional[Iterable[str]] = None,
) -> dict[str, Any]:
    """Assess documentation-currency staleness from a session's changed files.

    `changed_files` — every path the session touched (modified/added/deleted).
    `added_files` — the subset that are NEW files (drives new-surface detection);
    when omitted, new-surface detection runs over `changed_files`.

    Returns a structured assessment: `docs_appear_current` (bool), the advisory
    `signals` list, the `changed` breakdown, and a one-line `recommendation`.
    """
    changed = [_norm(f) for f in (changed_files or [])]
    added = [_norm(f) for f in (added_files if added_files is not None else changed)]

    docs = [f for f in changed if is_currency_doc(f)]
    version = [f for f in changed if is_version_source(f)]
    code = [f for f in changed if is_code_change(f)]
    changelog_changed = any(f == "CHANGELOG.md" for f in changed)
    surfaces = new_surfaces(added)

    signals: list[dict[str, Any]] = []
    if code and not docs:
        signals.append({
            "signal": "code-changed-no-doc",
            "severity": "high",
            "detail": (
                f"{len(code)} source file(s) changed but no documentation-currency "
                "doc was updated"
            ),
            "files": sorted(code),
        })
    if version and not changelog_changed:
        signals.append({
            "signal": "version-bumped-no-changelog",
            "severity": "high",
            "detail": "a version source-of-truth changed but CHANGELOG.md was not updated",
            "files": sorted(version),
        })
    if code and not changelog_changed:
        signals.append({
            "signal": "source-changed-no-changelog",
            "severity": "medium",
            "detail": "source changed but CHANGELOG.md carries no entry for it",
            "files": sorted(code),
        })
    # A new surface demands the SPECIFIC inventory-count docs — not merely "some"
    # currency doc. Keying this off INVENTORY_COUNT_DOCS (rather than the generic
    # `docs` bucket) means a lone CHANGELOG touch can NOT silence a stale README /
    # CODEBASE_MAP inventory grid.
    missing_inventory = [d for d in INVENTORY_COUNT_DOCS if d not in changed]
    if surfaces and missing_inventory:
        signals.append({
            "signal": "new-surface-undocumented",
            "severity": "high",
            "detail": (
                "a new "
                + ", ".join(sorted({s["kind"] for s in surfaces}))
                + " was added but its inventory docs were not all updated "
                + "(missing: " + ", ".join(sorted(missing_inventory)) + ")"
            ),
            "surfaces": surfaces,
            "missing_inventory": sorted(missing_inventory),
        })

    docs_current = not signals
    if docs_current:
        recommendation = "Documentation appears current; no closeout update indicated."
    else:
        recommendation = (
            "Run the closeout review (the `closeout` skill / `/architect-team:closeout`) "
            "BEFORE compacting: review the changes against the requirement, confirm every "
            "affected doc in the currency inventory, and update any that are stale."
        )

    return {
        "schema": "closeout-assessment/v1",
        "docs_appear_current": docs_current,
        "signals": signals,
        "changed": {
            "code": sorted(code),
            "docs": sorted(docs),
            "version": sorted(version),
            "new_surfaces": surfaces,
        },
        "recommendation": recommendation,
    }


def collect_changed_files(repo_root: str) -> dict[str, list[str]]:
    """Collect a session's changed files from the git working tree.

    Returns `{"changed": [...], "added": [...]}` using `git status --porcelain`
    (staged + unstaged + untracked). Best-effort: on any git error returns empty
    lists so the caller can fail open.
    """
    changed: list[str] = []
    added: list[str] = []
    try:
        proc = subprocess.run(
            ["git", "-C", str(repo_root), "status", "--porcelain", "--untracked-files=all"],
            capture_output=True, text=True, timeout=30,
        )
        if proc.returncode != 0:
            return {"changed": [], "added": []}
        for line in proc.stdout.splitlines():
            if not line.strip():
                continue
            status = line[:2]
            path = line[3:].strip()
            # rename form "old -> new": keep the new path
            if " -> " in path:
                path = path.split(" -> ", 1)[1].strip()
            # strip surrounding quotes git adds for paths with spaces/unicode
            if path.startswith('"') and path.endswith('"'):
                path = path[1:-1]
            changed.append(path)
            # a NEW path: staged-add (A/AM), copy-in (C), or rename-in (R) — the
            # new location is effectively new — or untracked (??).
            code = status.strip()
            if code == "??" or (code and code[0] in ("A", "C", "R")):
                added.append(path)
    except (OSError, subprocess.SubprocessError):
        return {"changed": [], "added": []}
    return {"changed": changed, "added": added}


def main(argv: Optional[list[str]] = None) -> int:
    """CLI: assess the current repo's working-tree closeout state.

    Usage: closeout_check.py [--repo <path>] [--json]
    Exit 0 if docs appear current, 1 if staleness signals were found (advisory —
    callers that must not gate should ignore the exit code).
    """
    import argparse
    import json

    parser = argparse.ArgumentParser(description="Assess documentation-currency closeout state.")
    parser.add_argument("--repo", default=".", help="repo root (default: cwd)")
    parser.add_argument("--json", action="store_true", help="emit the full assessment as JSON")
    args = parser.parse_args(argv)

    collected = collect_changed_files(args.repo)
    assessment = assess_closeout(collected["changed"], added_files=collected["added"])

    if args.json:
        print(json.dumps(assessment, indent=2, sort_keys=True))
    else:
        if assessment["docs_appear_current"]:
            print("closeout: documentation appears current.")
        else:
            print("closeout: documentation may be STALE —")
            for sig in assessment["signals"]:
                print(f"  [{sig['severity']}] {sig['signal']}: {sig['detail']}")
            print(assessment["recommendation"])
    return 0 if assessment["docs_appear_current"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
