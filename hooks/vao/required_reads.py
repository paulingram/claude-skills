"""VAO required-reads family (1 tool) -- the referencing mandate's hall monitor.

``verify-required-reads`` is the Layer-3 tool behind proposal change 9
(``docs/proposals/CT6_MODERNIZATION_PLAN.html``, section 7, condition 3). The
referencing system moves procedure out of the always-loaded skill bodies into
``references/*.md`` chapters that a phase is told to Read before it starts.
Following a pointer is probabilistic -- an agent under pressure skips the read
-- so each phase DECLARES its required reads in an ``INDEX.md`` and this tool
checks the tool-call ledger for the Read.

WHAT IT PROVES, AND WHAT IT DOES NOT (the honest boundary)
----------------------------------------------------------
A ``required-read-skipped`` gap proves the ledger holds NO ``Read`` of the
declared file before the phase started. A satisfied requirement proves the file
was OPENED by a Read tool call. Neither proves the content was understood,
retained across a compaction, or acted on. This tool is a hall monitor for the
reading, not a comprehension test; the prose rules the chapters carry are still
enforced only where a hook or a Layer-3 tool enforces them.

STOP-ARM POSTURE
----------------
``required-read-skipped`` and ``index-path-missing`` are BLOCKING severities in
this tool's own verdict (``valid`` is false, the CLI exits 2). The Stop-hook
arm that consumes this verdict treats a skipped read as a MEASURED GAP that is
reported in the completion audit, never as a block on its own -- a Read is a
means, and blocking a finished run because a means was skipped would punish
the outcome for the process. The verdict carries the same severities either
way so the record is identical whichever consumer reads it.

INPUTS
------
* ``INDEX.md`` files under ``--plugin-root`` (default: the repo root that holds
  ``hooks/``). Every ``INDEX.md`` is parsed; the walk skips ``.git``,
  ``.architect-team``, ``.mempalace``, ``node_modules``, ``__pycache__``,
  ``tests`` and ``openspec`` so test fixtures and runtime state never count.
  Two declaration shapes are recognised:

  1. The ``## Required reads`` table::

        ## Required reads
        | Before | Read | You will know |
        |---|---|---|
        | phase-2 | `skills/common-pipeline-conventions/references/x.md` | ... |

     The ``Before`` cell names one or more phases (comma-separated) or the
     word ``always``; the ``Read`` cell names one or more backticked paths. The
     heading match is case-insensitive and accepts any heading level.

  2. ``required_before:`` lines inside the leading ``---`` frontmatter block::

        ---
        required_before: phase-2 skills/common-pipeline-conventions/references/x.md
        required_before: phase-5: references/integration.md
        required_before:
          - phase-7: references/master-review.md
        ---

  A path is resolved against the plugin root when it is repo-relative
  (``skills/...``, ``docs/...``, ``agents/...``, ``commands/...``,
  ``hooks/...``, ``scripts/...``), against the INDEX's skill directory when it
  starts with ``references/`` (the skill dir is the parent of the
  ``references/`` folder the INDEX sits in), and against the INDEX's own
  directory when it is a bare filename. A ``#fragment`` suffix is stripped for
  the existence check and recorded as ``heading``.

* The tool-call ledger at
  ``<workspace>/.architect-team/run-history/<run-id>-toolcalls.jsonl`` -- one
  JSON object per line in append order. Records carry ``tool`` (or
  ``tool_name``) and ``args`` (or ``tool_input`` / ``input``); a timestamp
  under ``ts`` / ``timestamp`` / ``at`` / ``completed_at`` is RECORDED but not
  required -- ordering is by ledger position, which is append order.

* ``<workspace>/.architect-team/intake-state.json`` and
  ``<workspace>/.architect-team/active-run.json``, read ONLY for their
  ``phase`` field (the orchestrator's observability record of the current
  phase).

THE PHASE-START RULE (precise, because the verdict hangs on it)
----------------------------------------------------------------
Phase identifiers are normalised to a canonical token before comparison:
lower-case, the Unicode minus / en dash / em dash folded to ``-``, a leading
``phase`` word and its separator dropped, and the identifier cut at the first
separator that is not part of it -- so ``Phase 2``, ``phase-2``, ``Phase 2 --
Decomposition & Team Spawn`` and ``2`` are all ``phase-2``; ``Phase -1D`` is
``phase--1d``; ``B3`` and ``phase-b3`` are ``phase-b3``; ``scope-isolation``
is ``phase-scope-isolation``.

A ledger record NAMES a phase when any of these holds:

  (a) it carries a top-level ``phase`` string;
  (b) its args carry a ``phase`` string;
  (c) it is a ``Bash`` call whose command runs ``run_continuity.py --set ...
      phase=<value>`` (the orchestrator's phase-boundary marker update) or
      ``notify.py phase_start|phase_complete|waiting_on_agents ... --phase
      <value>`` (the notifier's phase events).

A phase P is STARTED at the first tool call AFTER the earliest ledger record
that names P, or that names any LATER phase of the same lane (same letter
prefix, greater number -- a run that is in phase 3 has started phase 2, even
if phase 2's own marker was never written). ``start_index`` is therefore
``earliest_naming_index + 1``; a Read SATISFIES the requirement when its
ledger index is strictly below ``start_index``.

When no ledger record names P or a later phase of its lane, two fallbacks
apply, in order:

  * ``--phase P`` was passed: the caller asserts P is starting NOW, so P starts
    at ``len(ledger)`` -- every Read already in the ledger is "before" and only
    an ABSENT Read is a gap.
  * ``intake-state.json`` / ``active-run.json`` ``phase`` equals P or a later
    phase of its lane: P is in progress but the ledger does not say where it
    began, so the same ``len(ledger)`` rule applies (ordering inside the
    ledger is unknowable; a Read anywhere satisfies, an absent Read is a gap).

With no evidence at all, P has NOT started and its requirements are listed
with status ``not-started`` -- never a gap, because a phase that has not
begun owes nothing yet.

``always`` (the INDEX word for "before every phase") is owed at the FIRST
phase boundary of the run, whichever lane it belongs to: its start index is
the first tool call after the earliest ledger record that names ANY phase;
the ``--phase`` and marker fallbacks apply as above (any asserted or recorded
phase makes the always-reads owed, at ``len(ledger)``). ``--phase P`` keeps
the ``always`` requirements beside P's own, because they are P's too.

A Read MATCHES a requirement when the Read's ``file_path`` (or ``path`` /
``file``), with backslashes folded to ``/``, equals the requirement's resolved
repo-relative path or ends with ``/`` + that path. Only the ``Read`` tool
counts; a ``cat`` in Bash, a ``Grep`` hit, or a ``Glob`` listing is not a
read of the file.

SEVERITIES
----------
* ``required-read-skipped`` (blocking) -- the phase started and no Read of the
  file appears before (or, under the fallbacks, anywhere in) the ledger.
* ``required-read-late`` (warning, non-blocking) -- a Read exists but its
  first occurrence is at or after the phase start.
* ``index-path-missing`` (blocking) -- an INDEX names a file that does not
  exist on disk. A pointer to nothing is an index bug, not a runtime one.
* ``ledger-unreadable`` (blocking, unknown state) -- the ledger is missing or
  cannot be parsed. Unknown is not pass: the tool cannot say the reads
  happened, so it does not.

Deterministic, stdlib-only; the only write is the verdict file (default
``<workspace>/.architect-team/vao-verdicts/<run-id>-required-reads.json``).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Optional

if __name__ == "__main__":  # script shape: `python hooks/vao/required_reads.py ...`
    # Only sys.path[0] (this directory) is importable then; put the repo root
    # and hooks/ ahead of it so the dual-form imports below resolve exactly as
    # they do under the facade (hooks/vao_tools.py) or the test suite.
    _HERE = Path(__file__).resolve()
    for _entry in (str(_HERE.parents[1]), str(_HERE.parents[2])):
        if _entry not in sys.path:
            sys.path.insert(0, _entry)

try:  # package shape: repo root on sys.path
    from hooks.vao.core import _utc_now_iso, _write_verdict
except ImportError:  # hooks/ on sys.path (vao is the package)
    try:
        from vao.core import _utc_now_iso, _write_verdict
    except ImportError:  # hooks/vao/ on sys.path (bare sibling)
        from core import _utc_now_iso, _write_verdict


TOOL_NAME = "verify-required-reads"
# The INDEX word for "before every phase": owed at the run's first phase start.
ALWAYS = "always"
_ALWAYS_WORDS = frozenset({"always", "every", "every-phase", "all", "all-phases", "run-start", "*", "any"})
HONEST_BOUNDARY = (
    "A satisfied requirement proves the file was OPENED by a Read tool call "
    "before the phase started; it does not prove the content was understood, "
    "retained across compaction, or acted on."
)

SEVERITY_SKIPPED = "required-read-skipped"
SEVERITY_LATE = "required-read-late"
SEVERITY_INDEX_PATH_MISSING = "index-path-missing"
SEVERITY_LEDGER_UNREADABLE = "ledger-unreadable"

BLOCKING_SEVERITIES = frozenset({
    SEVERITY_SKIPPED,
    SEVERITY_INDEX_PATH_MISSING,
    SEVERITY_LEDGER_UNREADABLE,
})

LEDGER_RELATIVE_DIR = ".architect-team/run-history"
INTAKE_STATE_RELATIVE_PATH = ".architect-team/intake-state.json"
ACTIVE_RUN_RELATIVE_PATH = ".architect-team/active-run.json"
VERDICT_RELATIVE_DIR = ".architect-team/vao-verdicts"

# Directories the INDEX walk never descends into: runtime state, VCS internals,
# vendored trees, and the test tree (whose fixtures carry deliberately-dead
# INDEX pointers).
_SKIP_DIR_NAMES = frozenset({
    ".git", ".architect-team", ".mempalace", "node_modules", "__pycache__",
    "tests", "openspec", ".venv", "venv", ".pytest_cache",
})

# Path prefixes that mark a repo-relative pointer (resolved against the plugin
# root rather than the INDEX's own directory).
_REPO_RELATIVE_PREFIXES = ("skills/", "docs/", "agents/", "commands/", "hooks/", "scripts/")

_RE_REQUIRED_READS_HEADING = re.compile(r"^#{1,6}\s+required\s+reads\b", re.IGNORECASE)
_RE_TABLE_SEPARATOR_CELL = re.compile(r"^:?-{2,}:?$")
_RE_BACKTICKED = re.compile(r"`([^`]+)`")
_RE_REQUIRED_BEFORE = re.compile(r"^required_before:\s*(.*)$")
_RE_LIST_ITEM = re.compile(r"^\s*-\s+(.*)$")
# `<phase>: <path>` / `<phase> -> <path>` / `<phase> => <path>` -- the phase may
# carry a space ("Phase 2"), so it is matched lazily up to the separator.
_RE_PHASE_SEP_PATH = re.compile(r"^(.+?)\s*(?::|->|=>)\s*(\S+)\s*$")

# Bash-command phase markers (the two surfaces the orchestrators actually use).
_RE_SET_PHASE = re.compile(
    r"run_continuity(?:\.py)?[^\n]*?--set\b[^\n]*?\bphase=(?:\"([^\"]*)\"|'([^']*)'|(\S+))"
)
_RE_NOTIFY_PHASE = re.compile(
    r"notify(?:\.py)?[^\n]*?\b(?:phase_start|phase_complete|waiting_on_agents)\b[^\n]*?"
    r"--phase\s+(?:\"([^\"]*)\"|'([^']*)'|(\S+))"
)

# The canonical phase identifier: an optional letter prefix, an optional sign,
# a number with an optional decimal part, an optional letter suffix -- OR a
# plain word identifier (scope-isolation, light-discriminant).
_RE_PHASE_ID = re.compile(r"^([a-z]?)(-?)(\d+(?:\.\d+)?)([a-z]?)$")
_RE_PHASE_TOKEN = re.compile(r"([a-z]?\s*-?\s*\d+(?:\.\d+)?[a-z]?|[a-z][a-z0-9_-]*)")

_DASHES = {"\u2212": "-", "\u2013": "-", "\u2014": "-", "\u2012": "-", "\u2010": "-"}


# --------------------------------------------------------------------------- #
# phase identifiers
# --------------------------------------------------------------------------- #
def canonical_phase(raw: Any) -> Optional[str]:
    """Normalise a phase mention to its canonical ``phase-<id>`` token.

    Returns ``None`` when ``raw`` carries no recognisable identifier.
    """
    if isinstance(raw, bool):
        return None
    if isinstance(raw, (int, float)):
        raw = str(raw)
    if not isinstance(raw, str):
        return None
    s = raw.strip().lower()
    for src, dst in _DASHES.items():
        s = s.replace(src, dst)
    s = s.strip("`'\" ")
    if s in _ALWAYS_WORDS:
        return ALWAYS
    # Drop a leading "phase" word and EXACTLY ONE separator run: a run of
    # spaces / underscores / colons, or a single dash -- so "phase--1" keeps
    # its minus sign ("phase--1" is phase -1, not phase 1).
    s = re.sub(r"^phase(?:\s+|[_:]+\s*|-)", "", s)
    if not s or s == "phase":
        return None
    m = _RE_PHASE_TOKEN.match(s)
    if not m:
        return None
    ident = re.sub(r"\s+", "", m.group(1))
    # A word identifier followed by more words ("scope isolation") keeps only
    # its first word; a hyphenated word ("scope-isolation") is one token.
    ident = ident.strip("-") if not _RE_PHASE_ID.match(ident) else ident
    if not ident:
        return None
    return f"phase-{ident}"


def _phase_order_key(canon: str) -> Optional[tuple[str, float, str]]:
    """``(lane_prefix, number, suffix)`` for a numeric phase token, else None.

    Only numeric phases take part in later-phase inference; a word phase
    (``phase-scope-isolation``) matches by identity alone.
    """
    if not canon or not canon.startswith("phase-"):
        return None
    ident = canon[len("phase-"):]
    m = _RE_PHASE_ID.match(ident)
    if not m:
        return None
    prefix, sign, number, suffix = m.groups()
    value = float(number)
    if sign == "-":
        value = -value
    return (prefix, value, suffix)


def phase_is_at_or_after(candidate: str, target: str) -> bool:
    """True when ``candidate`` names ``target`` itself or a later phase of the
    same lane (same letter prefix, greater number; equal number and a later
    letter suffix also counts -- ``phase-3b`` is after ``phase-3``)."""
    if candidate == target:
        return True
    ck = _phase_order_key(candidate)
    tk = _phase_order_key(target)
    if ck is None or tk is None or ck[0] != tk[0]:
        return False
    if ck[1] != tk[1]:
        return ck[1] > tk[1]
    return ck[2] > tk[2]


# --------------------------------------------------------------------------- #
# INDEX.md discovery + parsing
# --------------------------------------------------------------------------- #
def default_plugin_root() -> Path:
    """The repo root that holds ``hooks/`` (this file is hooks/vao/x.py)."""
    return Path(__file__).resolve().parents[2]


def discover_indexes(plugin_root: Path | str) -> list[Path]:
    """Every ``INDEX.md`` under ``plugin_root``, skipping ``_SKIP_DIR_NAMES``."""
    root = Path(plugin_root)
    found: list[Path] = []
    if not root.is_dir():
        return found
    stack = [root]
    while stack:
        current = stack.pop()
        try:
            entries = sorted(current.iterdir(), key=lambda p: p.name)
        except OSError:
            continue
        for entry in entries:
            if entry.is_dir():
                if entry.name in _SKIP_DIR_NAMES or entry.name.startswith("."):
                    continue
                stack.append(entry)
            elif entry.name == "INDEX.md":
                found.append(entry)
    return sorted(found)


def _posix_rel(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def resolve_pointer(raw_path: str, index_path: Path, plugin_root: Path) -> tuple[Path, str, Optional[str]]:
    """Resolve a pointer as written in an INDEX to ``(absolute, repo_relative,
    heading)`` per the module docstring's three resolution rules."""
    text = raw_path.strip().strip("`").strip()
    heading: Optional[str] = None
    if "#" in text:
        text, _, frag = text.partition("#")
        heading = frag.strip() or None
        text = text.strip()
    while text.startswith("./"):
        text = text[2:]
    text = text.replace("\\", "/")
    index_dir = index_path.parent
    skill_dir = index_dir.parent if index_dir.name == "references" else index_dir
    if text.startswith(_REPO_RELATIVE_PREFIXES):
        absolute = plugin_root / text
    elif text.startswith("references/"):
        absolute = skill_dir / text
    elif "/" not in text:
        absolute = index_dir / text
    else:
        absolute = plugin_root / text
    return absolute, _posix_rel(absolute, plugin_root), heading


def _split_phases(cell: str) -> list[str]:
    out: list[str] = []
    for piece in re.split(r"[,;]", cell):
        piece = piece.strip().strip("`")
        if piece:
            out.append(piece)
    return out


def _split_paths(cell: str) -> list[str]:
    ticked = _RE_BACKTICKED.findall(cell)
    if ticked:
        return [t.strip() for t in ticked if t.strip()]
    cell = cell.strip()
    return [cell] if cell else []


def _frontmatter_block(lines: list[str]) -> list[tuple[int, str]]:
    """``(lineno, text)`` for every line inside the leading ``---`` block."""
    if not lines or lines[0].strip() != "---":
        return []
    out: list[tuple[int, str]] = []
    for idx in range(1, len(lines)):
        if lines[idx].strip() == "---":
            return out
        out.append((idx + 1, lines[idx]))
    return []  # never closed -> not a frontmatter block


def _parse_phase_path(text: str) -> Optional[tuple[str, str]]:
    text = text.strip()
    if not text:
        return None
    m = _RE_PHASE_SEP_PATH.match(text)
    if m:
        return m.group(1).strip(), m.group(2).strip()
    parts = text.split()
    if len(parts) >= 2:
        return " ".join(parts[:-1]), parts[-1]
    return None


def parse_index(index_path: Path | str, plugin_root: Path | str) -> list[dict[str, Any]]:
    """Collect ``(phase, path)`` requirements declared by one INDEX.md.

    Each requirement is ``{phase, raw_phase, path, resolved_path, exists,
    heading, index, line, source}``; ``source`` is ``table`` or
    ``frontmatter``. An INDEX with neither declaration shape yields ``[]``.
    """
    index_path = Path(index_path)
    plugin_root = Path(plugin_root)
    try:
        text = index_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []
    lines = text.splitlines()
    index_rel = _posix_rel(index_path, plugin_root)
    requirements: list[dict[str, Any]] = []

    def add(raw_phase: str, raw_path: str, lineno: int, source: str) -> None:
        canon = canonical_phase(raw_phase)
        if canon is None:
            return
        absolute, rel, heading = resolve_pointer(raw_path, index_path, plugin_root)
        requirements.append({
            "phase": canon,
            "raw_phase": raw_phase.strip(),
            "path": raw_path.strip().strip("`"),
            "resolved_path": rel,
            "exists": absolute.is_file(),
            "heading": heading,
            "index": index_rel,
            "line": lineno,
            "source": source,
        })

    # 1. frontmatter `required_before:` lines
    fm = _frontmatter_block(lines)
    i = 0
    while i < len(fm):
        lineno, raw = fm[i]
        m = _RE_REQUIRED_BEFORE.match(raw.strip()) if not raw.startswith((" ", "\t")) else None
        if not m:
            i += 1
            continue
        rest = m.group(1).strip()
        if rest:
            parsed = _parse_phase_path(rest)
            if parsed:
                add(parsed[0], parsed[1], lineno, "frontmatter")
            i += 1
            continue
        # block form: indented `- <phase>: <path>` items follow
        i += 1
        while i < len(fm):
            sub_lineno, sub_raw = fm[i]
            if not sub_raw.startswith((" ", "\t")):
                break
            item = _RE_LIST_ITEM.match(sub_raw)
            body = item.group(1) if item else sub_raw.strip()
            parsed = _parse_phase_path(body)
            if parsed:
                add(parsed[0], parsed[1], sub_lineno, "frontmatter")
            i += 1

    # 2. the `## Required reads` table
    in_section = False
    for lineno, raw in enumerate(lines, start=1):
        stripped = raw.strip()
        if stripped.startswith("#"):
            in_section = bool(_RE_REQUIRED_READS_HEADING.match(stripped))
            continue
        if not in_section or not stripped.startswith("|"):
            continue
        cells = [c.strip() for c in stripped.strip("|").split("|")]
        if len(cells) < 2:
            continue
        if all(_RE_TABLE_SEPARATOR_CELL.match(c) for c in cells if c):
            continue  # the |---|---| separator row
        if cells[0].lower() in ("before", "phase") and cells[1].lower() in ("read", "file", "path"):
            continue  # the header row
        for raw_phase in _split_phases(cells[0]):
            for raw_path in _split_paths(cells[1]):
                add(raw_phase, raw_path, lineno, "table")

    return requirements


def collect_requirements(plugin_root: Path | str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """``(requirements, indexes)`` across every INDEX.md under ``plugin_root``."""
    root = Path(plugin_root)
    requirements: list[dict[str, Any]] = []
    indexes: list[dict[str, Any]] = []
    for index_path in discover_indexes(root):
        reqs = parse_index(index_path, root)
        indexes.append({"path": _posix_rel(index_path, root), "requirements": len(reqs)})
        requirements.extend(reqs)
    return requirements, indexes


# --------------------------------------------------------------------------- #
# ledger reading
# --------------------------------------------------------------------------- #
def ledger_path_for(workspace: Path | str, run_id: str) -> Path:
    return Path(workspace) / LEDGER_RELATIVE_DIR / f"{run_id}-toolcalls.jsonl"


def read_ledger(path: Path | str) -> tuple[list[dict[str, Any]], str, str]:
    """``(records, state, detail)`` -- ``state`` is ``read`` / ``missing`` /
    ``unreadable``. Lines that do not parse are skipped; a non-empty file with
    ZERO parseable records is ``unreadable`` (content that is not a ledger),
    while an empty file is a legitimately empty ledger (``read``, 0 records)."""
    p = Path(path)
    if not p.exists():
        return [], "missing", f"no ledger at {p.as_posix()}"
    try:
        text = p.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return [], "unreadable", f"{p.as_posix()}: {type(exc).__name__}"
    records: list[dict[str, Any]] = []
    non_blank = 0
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        non_blank += 1
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            records.append(obj)
    if non_blank and not records:
        return [], "unreadable", f"{p.as_posix()}: {non_blank} line(s), none parse as a JSON object"
    return records, "read", ""


def _record_tool(entry: dict[str, Any]) -> str:
    tool = entry.get("tool")
    if not isinstance(tool, str) or not tool:
        tool = entry.get("tool_name")
    return tool.strip() if isinstance(tool, str) else ""


def _record_args(entry: dict[str, Any]) -> dict[str, Any]:
    for key in ("args", "tool_input", "input"):
        value = entry.get(key)
        if isinstance(value, dict):
            return value
    return {}


def _record_ts(entry: dict[str, Any]) -> Optional[str]:
    for key in ("ts", "timestamp", "at", "completed_at"):
        v = entry.get(key)
        if isinstance(v, str) and v:
            return v
    return None


def _first_group(match: "re.Match[str]") -> str:
    for g in match.groups():
        if g is not None:
            return g
    return ""


def phases_named_by(entry: dict[str, Any]) -> list[str]:
    """Canonical phase tokens this ledger record names (rules a/b/c)."""
    out: list[str] = []
    top = canonical_phase(entry.get("phase"))
    if top:
        out.append(top)
    args = _record_args(entry)
    in_args = canonical_phase(args.get("phase"))
    if in_args:
        out.append(in_args)
    if _record_tool(entry).lower() == "bash":
        command = args.get("command")
        if isinstance(command, str) and command:
            for pattern in (_RE_SET_PHASE, _RE_NOTIFY_PHASE):
                for m in pattern.finditer(command):
                    canon = canonical_phase(_first_group(m))
                    if canon:
                        out.append(canon)
    # de-dup, keep order
    seen: set[str] = set()
    uniq: list[str] = []
    for c in out:
        if c not in seen:
            seen.add(c)
            uniq.append(c)
    return uniq


def read_path_of(entry: dict[str, Any]) -> Optional[str]:
    """The file path a ``Read`` tool call opened, or None for any other call."""
    if _record_tool(entry).lower() != "read":
        return None
    args = _record_args(entry)
    for key in ("file_path", "path", "file"):
        v = args.get(key)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return None


def _norm_path(path: str) -> str:
    p = path.replace("\\", "/").strip()
    while p.startswith("./"):
        p = p[2:]
    return p


def path_matches(ledger_path: str, required_repo_relative: str) -> bool:
    """Suffix match on ``/``-normalised paths (both slash styles accepted)."""
    lp = _norm_path(ledger_path)
    req = _norm_path(required_repo_relative)
    if not lp or not req:
        return False
    return lp == req or lp.endswith("/" + req)


def _read_marker_phase(workspace: Path, rel: str) -> Optional[str]:
    p = workspace / rel
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    return canonical_phase(data.get("phase"))


def phase_start_index(
    phase: str,
    records: list[dict[str, Any]],
    *,
    cli_phase: Optional[str] = None,
    marker_phases: Optional[dict[str, Optional[str]]] = None,
) -> tuple[Optional[int], str]:
    """``(start_index, source)`` per the phase-start rule.

    ``source`` is ``ledger`` (a record named the phase or a later one),
    ``cli-phase`` (asserted starting now), ``intake-state`` / ``active-run``
    (the marker says the phase is in progress), or ``none`` (not started).
    """
    def owed_by(named: str) -> bool:
        if phase == ALWAYS:
            return True  # any phase start makes the always-reads owed
        return phase_is_at_or_after(named, phase)

    for idx, entry in enumerate(records):
        for named in phases_named_by(entry):
            if owed_by(named):
                return idx + 1, "ledger"
    if cli_phase is not None and owed_by(cli_phase):
        return len(records), "cli-phase"
    for source in ("intake-state", "active-run"):
        marker = (marker_phases or {}).get(source)
        if marker and owed_by(marker):
            return len(records), source
    return None, "none"


# --------------------------------------------------------------------------- #
# the tool
# --------------------------------------------------------------------------- #
def verify_required_reads(
    workspace: Path | str,
    run_id: str,
    phase: Optional[str] = None,
    plugin_root: Path | str | None = None,
    out_path: Path | str | None = None,
    ledger_path: Path | str | None = None,
) -> dict[str, Any]:
    """Layer-3 tool -- did each phase's declared required reads happen before
    the phase started?

    Returns ``{tool, valid, gaps[], warnings[], requirements[], indexes[],
    ledger{}, phase_filter, honest_boundary, checked_at, ...}``; ``valid`` is
    ``len(gaps) == 0`` (gaps hold only BLOCKING severities; late reads are
    warnings).
    """
    workspace = Path(workspace)
    root = Path(plugin_root) if plugin_root is not None else default_plugin_root()
    cli_phase = canonical_phase(phase) if phase is not None else None
    ledger_file = Path(ledger_path) if ledger_path is not None else ledger_path_for(workspace, run_id)

    requirements, indexes = collect_requirements(root)
    if cli_phase is not None:
        requirements = [r for r in requirements if r["phase"] in (cli_phase, ALWAYS)]

    gaps: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []

    for req in requirements:
        if not req["exists"]:
            gaps.append({
                "severity": SEVERITY_INDEX_PATH_MISSING,
                "phase": req["phase"],
                "path": req["resolved_path"],
                "index": req["index"],
                "line": req["line"],
                "evidence": (
                    f"{req['index']}:{req['line']} points at {req['resolved_path']!r}, "
                    "which does not exist on disk."
                ),
                "remediation": (
                    "Fix the pointer in the INDEX (or create the chapter it names); a "
                    "pointer to nothing cannot be read before any phase."
                ),
            })

    records, ledger_state, ledger_detail = read_ledger(ledger_file)
    ledger_info = {
        "path": ledger_file.as_posix(),
        "state": ledger_state,
        "records": len(records),
        "detail": ledger_detail,
    }

    marker_phases = {
        "intake-state": _read_marker_phase(workspace, INTAKE_STATE_RELATIVE_PATH),
        "active-run": _read_marker_phase(workspace, ACTIVE_RUN_RELATIVE_PATH),
    }

    if ledger_state != "read":
        gaps.append({
            "severity": SEVERITY_LEDGER_UNREADABLE,
            "phase": cli_phase,
            "path": ledger_file.as_posix(),
            "evidence": f"the tool-call ledger is {ledger_state}: {ledger_detail}",
            "remediation": (
                "Unknown is not pass. Confirm the run id and workspace, or that the "
                "harness is writing the toolcalls ledger; the reads cannot be "
                "verified until the ledger can be read."
            ),
        })
        for req in requirements:
            req["status"] = "unknown"
            req["phase_start_index"] = None
            req["phase_start_source"] = "none"
            req["read_index"] = None
            req["read_ts"] = None
    else:
        # First Read index per requirement (by resolved repo-relative path).
        read_entries: list[tuple[int, str, Optional[str]]] = []
        for idx, entry in enumerate(records):
            rp = read_path_of(entry)
            if rp is not None:
                read_entries.append((idx, rp, _record_ts(entry)))

        for req in requirements:
            start, source = phase_start_index(
                req["phase"], records, cli_phase=cli_phase, marker_phases=marker_phases,
            )
            req["phase_start_index"] = start
            req["phase_start_source"] = source
            first_read: Optional[tuple[int, str, Optional[str]]] = None
            for idx, rp, ts in read_entries:
                if path_matches(rp, req["resolved_path"]):
                    first_read = (idx, rp, ts)
                    break
            req["read_index"] = first_read[0] if first_read else None
            req["read_ts"] = first_read[2] if first_read else None
            if not req["exists"]:
                req["status"] = "index-path-missing"
                continue
            if start is None:
                req["status"] = "not-started"
                continue
            if first_read is None:
                req["status"] = "skipped"
                gaps.append({
                    "severity": SEVERITY_SKIPPED,
                    "phase": req["phase"],
                    "path": req["resolved_path"],
                    "index": req["index"],
                    "phase_start_index": start,
                    "phase_start_source": source,
                    "evidence": (
                        f"{req['phase']} started at ledger index {start} ({source}) and "
                        f"no Read of {req['resolved_path']!r} appears in the ledger "
                        f"({len(records)} record(s))."
                    ),
                    "remediation": (
                        f"Read {req['resolved_path']} before {req['phase']} begins, as "
                        f"{req['index']} declares. The Stop audit reports this as a "
                        "measured gap; it proves the file was never opened, not that "
                        "its rule was broken."
                    ),
                })
            elif first_read[0] >= start:
                req["status"] = "late"
                warnings.append({
                    "severity": SEVERITY_LATE,
                    "phase": req["phase"],
                    "path": req["resolved_path"],
                    "index": req["index"],
                    "phase_start_index": start,
                    "phase_start_source": source,
                    "read_index": first_read[0],
                    "evidence": (
                        f"{req['phase']} started at ledger index {start} ({source}); the "
                        f"first Read of {req['resolved_path']!r} is at index "
                        f"{first_read[0]} -- after the start."
                    ),
                    "remediation": (
                        "Read the chapter at the phase boundary, before the first tool "
                        "call of the phase; a late read may have missed the decisions "
                        "the chapter governs."
                    ),
                })
            else:
                req["status"] = "satisfied"

    verdict = {
        "tool": TOOL_NAME,
        "valid": len(gaps) == 0,
        "gaps": gaps,
        "warnings": warnings,
        "requirements": requirements,
        "indexes": indexes,
        "ledger": ledger_info,
        "marker_phases": marker_phases,
        "phase_filter": cli_phase,
        "run_id": run_id,
        "workspace": workspace.as_posix(),
        "plugin_root": root.as_posix(),
        "counts": {
            "requirements": len(requirements),
            "satisfied": sum(1 for r in requirements if r.get("status") == "satisfied"),
            "skipped": sum(1 for r in requirements if r.get("status") == "skipped"),
            "late": sum(1 for r in requirements if r.get("status") == "late"),
            "not_started": sum(1 for r in requirements if r.get("status") == "not-started"),
            "index_path_missing": sum(1 for r in requirements if r.get("status") == "index-path-missing"),
            "unknown": sum(1 for r in requirements if r.get("status") == "unknown"),
        },
        "honest_boundary": HONEST_BOUNDARY,
        "checked_at": _utc_now_iso(),
    }
    return _write_verdict(verdict, out_path)


# --------------------------------------------------------------------------- #
# CLI (also what the hooks/vao_tools.py facade wires)
# --------------------------------------------------------------------------- #
def default_out_path(workspace: Path | str, run_id: str) -> Path:
    return Path(workspace) / VERDICT_RELATIVE_DIR / f"{run_id}-required-reads.json"


def add_cli_arguments(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    """Register this tool's arguments on ``parser`` (a facade subparser or the
    standalone parser below)."""
    parser.add_argument("--workspace", required=True, help="The run's workspace root (holds .architect-team/).")
    parser.add_argument("--run-id", required=True, help="The run id naming the toolcalls ledger.")
    parser.add_argument("--phase", default=None, help="Check only this phase, asserting it is starting now.")
    parser.add_argument("--plugin-root", default=None, help="Where to find INDEX.md files (default: this repo root).")
    parser.add_argument("--ledger", default=None, help="Override the ledger path (default: <workspace>/.architect-team/run-history/<run-id>-toolcalls.jsonl).")
    parser.add_argument("--out", default=None, help="Verdict path (default: <workspace>/.architect-team/vao-verdicts/<run-id>-required-reads.json).")
    parser.add_argument("--json", action="store_true", help="Print the verdict JSON to stdout.")
    return parser


def run_from_args(args: argparse.Namespace) -> dict[str, Any]:
    """Run the tool from a parsed namespace (the facade's dispatch hook)."""
    out = args.out if args.out else default_out_path(args.workspace, args.run_id)
    return verify_required_reads(
        workspace=args.workspace,
        run_id=args.run_id,
        phase=args.phase,
        plugin_root=args.plugin_root,
        out_path=out,
        ledger_path=args.ledger,
    )


def _format_report(verdict: dict[str, Any]) -> str:
    lines = [f"{TOOL_NAME}: {'valid' if verdict['valid'] else 'GAPS'} -- "
             f"{verdict['counts']['requirements']} requirement(s), "
             f"{len(verdict['gaps'])} gap(s), {len(verdict['warnings'])} warning(s); "
             f"ledger {verdict['ledger']['state']} ({verdict['ledger']['records']} record(s))."]
    for gap in verdict["gaps"]:
        lines.append(f"  [{gap['severity']}] {gap['evidence']}")
    for warning in verdict["warnings"]:
        lines.append(f"  [{warning['severity']}] {warning['evidence']}")
    lines.append(f"  honest boundary: {HONEST_BOUNDARY}")
    return "\n".join(lines)


def main(argv: Optional[list[str]] = None) -> int:
    """Standalone CLI. Exits 0 when valid, 2 when any blocking gap exists."""
    parser = argparse.ArgumentParser(
        prog=TOOL_NAME,
        description="Layer-3 tool: were each phase's declared required reads performed before the phase started?",
    )
    add_cli_arguments(parser)
    args = parser.parse_args(argv)
    verdict = run_from_args(args)
    if args.json:
        print(json.dumps(verdict, indent=2, sort_keys=True))
    else:
        print(_format_report(verdict), file=sys.stdout if verdict["valid"] else sys.stderr)
    return 0 if verdict["valid"] else 2


__all__ = [
    "verify_required_reads",
    "ALWAYS",
    "canonical_phase",
    "phase_is_at_or_after",
    "discover_indexes",
    "parse_index",
    "collect_requirements",
    "resolve_pointer",
    "read_ledger",
    "phases_named_by",
    "read_path_of",
    "path_matches",
    "phase_start_index",
    "add_cli_arguments",
    "run_from_args",
    "main",
]


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
