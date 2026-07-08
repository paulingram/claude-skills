# -*- coding: utf-8 -*-
"""Deterministic Claude Design import engine (the `claude-design-mcp-import` change).

Stdlib-only, no import-time side effects. The deterministic half of the
**claude-design-import** capability: detect a Claude Design offer in prose, parse
its `?file=` selector and a trailing `Implement:` target, materialize a fetched
design project locally path-safely, and plan the graceful fallback when the
`claude_design` MCP is unavailable. It is the machine;
`skills/claude-design-import/SKILL.md` is the LLM-judgment contract + workflow.

HONEST BOUNDARY: the engine does detection, URL / `?file=` / `Implement:` parsing,
materialization, path-safety, and fallback-planning DETERMINISTICALLY and OFFLINE.
It NEVER calls the network or the MCP — the real `claude_design` MCP fetch is
invoked by the orchestrator at runtime via ToolSearch and injected here as a
`ClaudeDesignSource`; offline tests use `FakeClaudeDesignSource`. This mirrors the
`services/librarian` `Source` / `StaticSource` injected-adapter precedent. No MCP
tokens or credentials are persisted.
"""
from __future__ import annotations

import re
import urllib.parse
from pathlib import Path
from typing import Any, Optional, Union

# --------------------------------------------------------------------------- #
# detection grammar (pure, deterministic — no network)
# --------------------------------------------------------------------------- #
# A Claude Design project URL: claude.ai/design/p/<id> with an optional ?query.
# The scheme is optional so a bare `claude.ai/design/p/<id>` in prose still fires.
# The query stops at whitespace / quotes / closing brackets so a URL embedded in
# prose does not swallow following text.
# `pid` and `query` are NAMED groups so the id is read from the match itself —
# case-insensitive matching then still yields the id verbatim (a case-sensitive
# string split on "/design/p/" would miss an uppercase `CLAUDE.AI/DESIGN/P/…`).
_DESIGN_URL_RE = re.compile(
    r"(?:https?://)?claude\.ai/design/p/(?P<pid>[A-Za-z0-9_-]+)(?P<query>\?[^\s\"'<>)\]]*)?",
    re.IGNORECASE,
)
# The `claude_design` MCP mentioned by name (the second, independent trigger
# form). Word-boundary anchored so a longer identifier does NOT trip a false
# mention: `_` is a word char, so `\bclaude_design\b` matches `claude_design MCP`
# and `claude_design.` but NOT `claude_design_config`.
_MCP_MENTION_RE = re.compile(r"\bclaude_design\b", re.IGNORECASE)
# The MCP endpoint — naming it is ALSO an mcp-mention signal.
_MCP_ENDPOINT_RE = re.compile(
    r"(?:https?://)?api\.anthropic\.com/v1/design/mcp",
    re.IGNORECASE,
)
# An `Implement: <path>` directive naming the implementation focus. Matched
# ANYWHERE (not only at line start) because the real Claude Design prompt often
# glues it straight onto the URL with no separator
# (`…Finance+Dashboard.htmlImplement: …`). The path may contain spaces, so capture
# to the end of the line OR the end of the string.
_IMPLEMENT_RE = re.compile(r"Implement:[ \t]*(.+?)[ \t]*(?:\r?\n|$)", re.IGNORECASE)
# The glued-directive marker — used to strip an `Implement:` directive that got
# swept into the URL query (and therefore into the decoded file_selector).
_IMPLEMENT_MARKER_RE = re.compile(r"Implement:", re.IGNORECASE)

# A leading Windows drive letter (`C:` / `d:`) — used to reject absolute paths.
_WINDOWS_DRIVE_RE = re.compile(r"^[A-Za-z]:")

# Trailing prose punctuation to trim off a URL captured from a sentence.
_TRAILING_PUNCT = ".,;:!?)]}>\"'"


def _strip_trailing_punct(s: str) -> str:
    """Trim trailing sentence punctuation / closing quotes from a URL captured
    inside prose (`…Dashboard.html.` -> `…Dashboard.html`)."""
    return s.rstrip(_TRAILING_PUNCT)


def parse_design_url(url: str) -> dict[str, Optional[str]]:
    """Extract ``{base_url, project_id, file_selector}`` from a
    ``claude.ai/design/p/<id>?file=...`` URL.

    ``file_selector`` is URL-decoded (``%2F`` -> ``/``, ``+`` -> space) via
    :mod:`urllib.parse`, and a glued ``Implement:`` directive swept into the query
    is stripped back off. ``project_id`` is read from the regex's named group
    (case-preserved, so an uppercase URL still yields the id). Returns
    ``project_id=None`` for a non-matching string and NEVER raises on a plain
    string (the whole surface is pure)."""
    text = str(url if url is not None else "")
    match = _DESIGN_URL_RE.search(text)
    if not match:
        return {"base_url": None, "project_id": None, "file_selector": None}
    # id from the named group (case-insensitive match, id preserved verbatim).
    project_id = match.group("pid")
    base_url = _strip_trailing_punct(match.group(0).split("?", 1)[0])
    query = match.group("query") or ""
    query = query[1:] if query.startswith("?") else query
    file_selector: Optional[str] = None
    if query:
        # parse_qs URL-decodes: %2F -> '/', '+' -> ' ' (unquote_plus on each value).
        params = urllib.parse.parse_qs(query)
        values = params.get("file")
        if values:
            file_selector = values[0]
    if file_selector is not None:
        # A glued "…Implement: <path>" directive (no separator) gets swept into the
        # query; it is NOT part of the filename, so cut it off at the marker.
        glue = _IMPLEMENT_MARKER_RE.search(file_selector)
        if glue:
            file_selector = file_selector[:glue.start()]
        # Trim trailing sentence punctuation a prose URL may have captured.
        file_selector = _strip_trailing_punct(file_selector) or None
    return {"base_url": base_url or None, "project_id": project_id, "file_selector": file_selector}


def detect_claude_design_offer(text: str) -> dict[str, Any]:
    """Detect a Claude Design offer from prose.

    Fires on EITHER trigger form (inclusive OR): a ``claude.ai/design/p/<id>`` URL
    is present, OR the ``claude_design`` MCP is mentioned by name (naming the
    ``api.anthropic.com/v1/design/mcp`` endpoint counts as an mcp-mention too).
    Either alone is sufficient. Parses the ``?file=`` selector (URL-decoded) and a
    trailing ``Implement: <path>`` line as the focus.

    Returns::

        {
          "detected": bool,
          "trigger_forms": list[str],     # subset of {"design-url","mcp-mention"}, sorted
          "project_url": str | None,       # full claude.ai/design/p/<id>... URL if present
          "project_id": str | None,        # the <id> path segment
          "file_selector": str | None,     # URL-decoded ?file= value
          "implement_target": str | None,  # value of a trailing "Implement: <path>" line
          "mcp_endpoint": str | None,       # the MCP endpoint if named in the prose
        }
    """
    text = str(text if text is not None else "")

    url_match = _DESIGN_URL_RE.search(text)
    project_url: Optional[str] = None
    parsed: dict[str, Optional[str]] = {"base_url": None, "project_id": None, "file_selector": None}
    if url_match:
        # Parse from the RAW match (not a pre-stripped copy) so parse_design_url can
        # still see a glued `Implement:` marker in the query and strip it out.
        parsed = parse_design_url(url_match.group(0))
        project_url = _strip_trailing_punct(url_match.group(0))

    endpoint_match = _MCP_ENDPOINT_RE.search(text)
    mcp_endpoint = _strip_trailing_punct(endpoint_match.group(0)) if endpoint_match else None

    has_url = parsed["project_id"] is not None
    has_mcp_mention = bool(_MCP_MENTION_RE.search(text)) or (endpoint_match is not None)

    trigger_forms: list[str] = []
    if has_url:
        trigger_forms.append("design-url")
    if has_mcp_mention:
        trigger_forms.append("mcp-mention")
    trigger_forms.sort()

    implement_match = _IMPLEMENT_RE.search(text)
    implement_target = implement_match.group(1).strip() if implement_match else None

    return {
        "detected": bool(trigger_forms),
        "trigger_forms": trigger_forms,
        "project_url": project_url,
        "project_id": parsed["project_id"],
        "file_selector": parsed["file_selector"],
        "implement_target": implement_target,
        "mcp_endpoint": mcp_endpoint,
    }


# --------------------------------------------------------------------------- #
# the injected MCP-fetch adapter (a seam; the real fetch is the runtime MCP call)
# --------------------------------------------------------------------------- #

class ClaudeDesignSource:
    """The injected boundary for fetching a Claude Design project.

    ``fetch_project`` returns the WHOLE project's files as
    ``[{"path": str, "content": str}, ...]``. The REAL implementation is the
    runtime ``claude_design`` MCP call (done by the orchestrator via ToolSearch and
    injected here); this class is the seam. Offline tests inject
    :class:`FakeClaudeDesignSource`."""

    def fetch_project(self, project_id: str, *, file_selector: Optional[str] = None) -> list[dict[str, str]]:
        raise NotImplementedError(
            "ClaudeDesignSource is the injected seam — the real fetch is the runtime "
            "claude_design MCP call. Use FakeClaudeDesignSource for offline tests."
        )


def _coerce_files(spec: Any) -> list[dict[str, str]]:
    """Normalize a project file spec into ``[{"path","content"}, ...]``.

    Accepts a ``{path: content}`` mapping, a list of ``{"path","content"}`` dicts,
    or a list of ``(path, content)`` pairs."""
    out: list[dict[str, str]] = []
    if isinstance(spec, dict):
        for path, content in spec.items():
            out.append({"path": path, "content": content})
    else:
        for item in spec or []:
            if isinstance(item, dict):
                out.append({"path": item.get("path"), "content": item.get("content", "")})
            elif isinstance(item, (tuple, list)) and len(item) == 2:
                out.append({"path": item[0], "content": item[1]})
    return out


class FakeClaudeDesignSource(ClaudeDesignSource):
    """Offline test double built from a ``{path: content}`` mapping (or a file
    list) for a single project, and/or a ``{project_id: files}`` mapping for
    several projects. Returns copies so callers cannot mutate the source."""

    def __init__(
        self,
        files: Any = None,
        *,
        files_by_project: Optional[dict[str, Any]] = None,
    ) -> None:
        self._by_project: dict[str, list[dict[str, str]]] = {}
        if files_by_project:
            for project_id, spec in files_by_project.items():
                self._by_project[project_id] = _coerce_files(spec)
        self._default: Optional[list[dict[str, str]]] = _coerce_files(files) if files is not None else None

    def fetch_project(self, project_id: str, *, file_selector: Optional[str] = None) -> list[dict[str, str]]:
        if project_id in self._by_project:
            return [dict(f) for f in self._by_project[project_id]]
        if self._default is not None:
            return [dict(f) for f in self._default]
        return []


# --------------------------------------------------------------------------- #
# materialization (path-safe; never writes outside dest_dir)
# --------------------------------------------------------------------------- #

def _safe_relpath(path: str) -> str:
    """Normalize + validate a fetched file path to a safe RELATIVE path.

    Raises :class:`ValueError` on an absolute path (POSIX ``/``, a Windows drive
    ``C:``, or a UNC ``//``) or any ``..`` parent-directory traversal, so a fetched
    file can never be written outside the destination directory. Returns the
    normalized forward-slash relative path."""
    raw = str(path if path is not None else "")
    stripped = raw.strip()
    if not stripped:
        raise ValueError("empty file path")
    norm = stripped.replace("\\", "/")
    if norm.startswith("/") or norm.startswith("//") or _WINDOWS_DRIVE_RE.match(norm):
        raise ValueError(f"absolute path is not allowed: {raw!r}")
    segments = [seg for seg in norm.split("/") if seg not in ("", ".")]
    if any(seg == ".." for seg in segments):
        raise ValueError(f"parent-directory traversal is not allowed: {raw!r}")
    if not segments:
        raise ValueError(f"path does not resolve to a file: {raw!r}")
    return "/".join(segments)


def materialize_project(
    files: list[dict[str, str]],
    dest_dir: Union[str, Path],
    *,
    focus: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Write each fetched file under ``dest_dir``, path-safely (UTF-8).

    Rejects absolute paths and ``..`` traversal via :func:`_safe_relpath` (the
    entry is recorded in ``rejected`` and NEVER written outside ``dest_dir``).
    Records the ``focus`` (the ``?file=`` selector + ``Implement:`` target) so the
    downstream build knows which screen(s) drive implementation. Returns::

        {"materialized_dir": str, "files_written": list[str] (sorted),
         "rejected": list[dict], "focus": dict | None}
    """
    dest = Path(dest_dir)
    dest.mkdir(parents=True, exist_ok=True)
    dest_resolved = dest.resolve()
    files_written: list[str] = []
    rejected: list[dict[str, Any]] = []
    for entry in list(files or []):
        raw_path = entry.get("path") if isinstance(entry, dict) else None
        content = entry.get("content", "") if isinstance(entry, dict) else None
        try:
            safe = _safe_relpath(raw_path)
        except ValueError as exc:
            rejected.append({"path": raw_path, "error": str(exc)})
            continue
        target = dest / safe
        try:  # belt-and-suspenders: the resolved target must stay under dest
            target.resolve().relative_to(dest_resolved)
        except ValueError:
            rejected.append({"path": raw_path, "error": "resolves outside the destination directory"})
            continue
        try:  # an OS-illegal name can still raise on mkdir/write — reject that ONE
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content if content is not None else "", encoding="utf-8")
        except OSError as exc:  # never let one bad file abort the whole batch
            rejected.append({"path": raw_path, "error": str(exc)})
            continue
        files_written.append(safe)
    files_written.sort()
    return {
        "materialized_dir": str(dest),
        "files_written": files_written,
        "rejected": rejected,
        "focus": focus,
    }


def _safe_project_id(project_id: Any) -> str:
    """Sanitize a project id for use as a directory name (defense in depth — the id
    comes from a URL path segment)."""
    cleaned = re.sub(r"[^A-Za-z0-9._-]", "_", str(project_id if project_id is not None else ""))
    return cleaned or "design-project"


def plan_when_unavailable(offer: dict[str, Any], *, local_fallback_available: bool = True) -> dict[str, Any]:
    """Plan the graceful path when the ``claude_design`` MCP is unavailable.

    Returns ``instruct-then-fallback`` (fallback ``zip-local``) when a local
    fallback is available so a run never dead-ends, else ``instruct-then-halt``
    (fallback ``None``). The instruction names connecting the ``claude_design`` MCP
    and running ``/design-login``."""
    project_id = (offer or {}).get("project_id")
    scope = f" (project {project_id})" if project_id else ""
    instruction = (
        "The claude_design MCP is not connected, or /design-login has not been run. To import "
        f"this Claude Design project{scope} natively, connect the claude_design MCP (endpoint "
        "https://api.anthropic.com/v1/design/mcp) and run /design-login, then re-run. If you "
        "decline, the run continues down the existing zip/local design-input path."
    )
    if local_fallback_available:
        return {"action": "instruct-then-fallback", "instruction": instruction, "fallback": "zip-local"}
    return {"action": "instruct-then-halt", "instruction": instruction, "fallback": None}


def import_claude_design(
    offer: dict[str, Any],
    source: ClaudeDesignSource,
    dest_root: Union[str, Path],
    *,
    mcp_available: bool = True,
    local_fallback_available: bool = True,
) -> dict[str, Any]:
    """Orchestrate detection -> fetch -> materialize (the engine NEVER calls the MCP itself).

    When ``mcp_available`` is false, returns :func:`plan_when_unavailable` verbatim
    (no fetch). When available and ``offer.detected``, fetches the WHOLE project via
    the injected ``source`` and materializes it to ``dest_root/<project_id>/``,
    returning ``{"status": "materialized", ...}``. A not-detected offer returns a
    ``not-detected`` status without fetching."""
    offer = offer or {}
    if not mcp_available:
        return plan_when_unavailable(offer, local_fallback_available=local_fallback_available)
    if not offer.get("detected"):
        return {
            "status": "not-detected",
            "materialized_dir": None,
            "files_written": [],
            "rejected": [],
            "focus": None,
        }
    project_id = offer.get("project_id") or "design-project"
    file_selector = offer.get("file_selector")
    files = source.fetch_project(project_id, file_selector=file_selector)
    dest_dir = Path(dest_root) / _safe_project_id(project_id)
    focus = {"file_selector": file_selector, "implement_target": offer.get("implement_target")}
    result = materialize_project(files, dest_dir, focus=focus)
    result["status"] = "materialized"
    result["project_id"] = project_id
    return result


def main(argv: Optional[list[str]] = None) -> int:
    """CLI: offline detection + URL parsing (fetch/materialize need a live source).

    Usage:
      claude_design_import.py detect <text-or-@file> [--json]
      claude_design_import.py parse-url <url> [--json]
    `detect` exits 0 when an offer is detected, 1 otherwise (advisory); `parse-url`
    exits 0 when a project_id is parsed, 1 otherwise."""
    import argparse
    import json

    parser = argparse.ArgumentParser(
        description="Claude Design offer detector + URL parser (offline, deterministic)."
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    pd = sub.add_parser("detect", help="detect a Claude Design offer in prose (or @<file>)")
    pd.add_argument("text", help="the prose text, or @<path> to read the text from a file")
    pd.add_argument("--json", action="store_true")

    pp = sub.add_parser("parse-url", help="parse a claude.ai/design/p/<id> URL")
    pp.add_argument("url")
    pp.add_argument("--json", action="store_true")

    args = parser.parse_args(argv)

    if args.cmd == "detect":
        text = args.text
        if text.startswith("@"):
            text = Path(text[1:]).read_text(encoding="utf-8")
        result = detect_claude_design_offer(text)
        if args.json:
            print(json.dumps(result, indent=2, sort_keys=True))
        else:
            if result["detected"]:
                forms = ", ".join(result["trigger_forms"])
                print(f"claude-design: offer detected ({forms}).")
                if result["project_id"]:
                    print(f"  project_id: {result['project_id']}")
                if result["file_selector"]:
                    print(f"  file: {result['file_selector']}")
                if result["implement_target"]:
                    print(f"  implement: {result['implement_target']}")
            else:
                print("claude-design: no offer detected.")
        return 0 if result["detected"] else 1

    # parse-url
    result = parse_design_url(args.url)
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        if result["project_id"]:
            print(f"project_id: {result['project_id']}")
            print(f"base_url:   {result['base_url']}")
            print(f"file:       {result['file_selector']}")
        else:
            print("no claude.ai/design/p/<id> URL found.")
    return 0 if result["project_id"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
