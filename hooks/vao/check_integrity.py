"""VAO check-falsifiability family (1 tool) — v3.47.0.

``verify-check-can-fail`` is the 21st Layer-3 tool. It answers one question a
green check cannot answer about itself: *did this check read anything, and has
this guard ever been shown able to fail?*

Two independent halves:

  * **Zero-work scan.** Every cited verification-command output is read and
    matched against a data registry of per-runner zero-work signatures — the
    output shapes a runner emits when it examined nothing (pytest
    ``collected 0 items``, Playwright ``no tests found``, jest/vitest
    ``No test files found``, and the TypeScript solution-file shape that makes
    ``tsc --noEmit`` a zero-file no-op). A cited output that does not exist, is
    not a file, or is empty clears the same bar as
    ``_detect_missing_evidence_artifact`` (``hooks/vao/live_verification.py``)
    and is itself a ``vacuous-check``.

  * **Red-run-first proof.** Every diff-added test file must cite a run in which
    it FAILED, from one of the three accepted red sources (see
    ``_ACCEPTED_RED_SOURCES``). A test file with no cited red run is
    ``new-guard-never-shown-red``; a cited red run whose output carries no
    failure signature — or whose quoted failure excerpt does not appear in that
    output — is ``red-run-not-red``.

Artifact contract::

    {
      "repo_root": "<optional; relative cited paths resolve against it>",
      "checks": [{"command": str, "output_path": str, "exit_code": int?,
                  "tsconfig_path": str?}],
      "new_test_files": ["tests/test_x.py", ...],
      "red_runs": {"tests/test_x.py": {"command": str, "output_path": str,
                                       "observed_failure_excerpt": str?,
                                       "red_source": str?}}
    }

``observed_failure_excerpt`` is optional ONLY when the cited output names the
test it is proving red. When the output identifies no test at all — a
``--tb=no`` summary behind ``make test``, say — the excerpt is REQUIRED, because
it is then the only thing tying that output to this guard.

SHARING ONE CAPTURE ACROSS GUARDS. One red run covering several new test files
is normal and fully accepted **when its output NAMES them**: correlation ties
each guard to the output independently, so nothing is taken on trust. The same
capture reused for several guards while naming NONE of them is refused
(``shared-anonymous-red``) — an anonymous summary is tied to no guard in
particular, and an excerpt does not fix that, since one string satisfies the
excerpt rule as many times as it is pasted. When a shared capture is anonymous,
either re-run with per-test reporting (drop ``--tb=no``, add ``-v``, or name the
paths) so the output identifies its tests, or split it into one captured run per
guard. Reds whose output carries path-shaped test ids are the form that makes
correlation, sharing, and the same-basename boundary below all moot.

Originating failure: the banking-app FDS fix-list release (2026-07-30) — a
typecheck gate that reported green having examined zero files, a jest run that
"passed" on *No test files found*, and new guards trusted on their first green.

STATED BOUNDARIES — what this tool deliberately does NOT decide. Each was
measured during adversarial review and is recorded here rather than left for a
reader to discover:

  * **Same-basename correlation (R4).** ``_output_references_test`` matches the
    full posix path OR the basename. When two new test files share a basename in
    different directories (``tests/unit/test_guard.py`` and
    ``tests/integration/test_guard.py``), output naming only one of them
    satisfies correlation for both. Path-shaped output ids — which pytest,
    vitest and Playwright all print by default — resolve this naturally; closing
    it in general would require per-directory output evidence the runners do not
    uniformly emit. Prefer citing a red run whose output carries full paths.

  * **Indeterminate correlation (R3).** An output that names no test at all
    cannot be tied to a guard by correlation, so the quoted excerpt becomes
    mandatory instead (severity reason ``excerpt-required-when-indeterminate``).
    That raises the floor but does not make the citation unique: one name-free
    summary WITH an excerpt can still be cited for several guards. The honest
    resolution is to capture reds that name their test.

  * **Exotic encodings (W3).** ``_decode_output_bytes`` handles every generator
    measured on the reference platform — PowerShell ``Out-File -Encoding
    Unicode`` / ``BigEndianUnicode`` / ``Set-Content -Encoding Unicode`` all emit
    a BOM, and stock ``>`` redirection emitted UTF-8-BOM — plus BOM-less UTF-16
    via the NUL-ratio rung. Three constructed remainders still evade it:
    BOM-less UTF-16LE diluted below the one-third NUL floor by wide characters,
    a truncated odd-length UTF-16 file, and BOM-less UTF-16BE. Producing any of
    them needs a hand-rolled writer, so the residual is rated low.

Stdlib-only; no import-time side effects; the only write is the verdict file.
"""

from __future__ import annotations

import codecs
import json
import re
from pathlib import Path
from typing import Any

try:  # package shape: repo root on sys.path
    from hooks.vao.core import _utc_now_iso, _write_verdict
except ImportError:  # hooks/ on sys.path (vao is the package)
    try:
        from vao.core import _utc_now_iso, _write_verdict
    except ImportError:  # hooks/vao/ on sys.path (bare sibling)
        from core import _utc_now_iso, _write_verdict


# The three acceptable ways to produce a new guard's red output (design D3).
# (a) makes red-first satisfiable for genuinely-new capabilities, (c) makes it
# reachable for tests whose pre-change state cannot build.
_ACCEPTED_RED_SOURCES: tuple[str, ...] = (
    "tdd-red",              # the failing run captured before the implementation existed
    "pre-change-checkout",  # the new test run against the baseline SHA
    "assertion-inversion",  # a deliberate inversion / mutation proving the guard bites
)


def _command_names_runner(command: Any, runner: str) -> bool:
    """True iff ``command`` names ``runner`` as a whole word.

    Word-anchored so ``pytest`` in ``python -m pytest`` matches while ``tsc``
    does not leak onto a pytest command. NOTE (adversarial B2/B3): a command
    name is a WEAK signal — real projects run their checks through `make test`
    or `npm run typecheck`, which name no runner at all. Command naming is
    therefore only ONE of the applicability signals; see
    ``_detect_runners_from_output``.
    """
    if not isinstance(command, str) or not command.strip():
        return False
    return re.search(rf"\b{re.escape(runner)}\b", command.lower()) is not None


# B3 — output-shape detection. A wrapper command hides the runner's name, but
# never its output shape. Each entry is (runner, pattern-that-only-that-runner
# prints), used to widen signature applicability beyond command naming.
_RUNNER_OUTPUT_SHAPES: tuple[tuple[str, str], ...] = (
    ("pytest", r"(?mi)^=+\s*test session starts\s*=+"),
    ("pytest", r"(?mi)^\s*collected \d+ items?\b"),
    ("pytest", r"(?mi)^\s*rootdir:\s"),
    ("pytest", r"(?mi)^\s*\S*python\S*\s+-m\s+pytest\b"),
    ("pytest", r"(?mi)^\s*>?\s*pytest\b"),
    ("playwright", r"(?mi)^\s*Running \d+ tests? using \d+ worker"),
    ("playwright", r"(?mi)^\s*>\s*playwright test\b"),
    ("playwright", r"(?mi)^\s*\[(?:chromium|firefox|webkit)\]"),
    ("jest", r"(?mi)^\s*Test Suites:\s"),
    ("jest", r"(?mi)^\s*>\s*jest\b"),
    ("vitest", r"(?mi)^\s*Test Files\s+\d"),
    ("vitest", r"(?mi)^\s*>\s*vitest\b"),
)


# ---------------------------------------------------------------------------
# Region awareness — the SCOPE fix (adversarial round 4)
# ---------------------------------------------------------------------------
# A capture contains two kinds of text and they must never be confused:
#
#   REPORTING — what the RUNNER says about the run: session header, progress,
#     FAILURES / ERRORS sections, the short summary, the final count line.
#   RELAYED   — text the runner merely carried through: live logs, captured
#     stdout/stderr, console output, doctest expected-output blocks, echoed
#     commands, and test ids (whose parametrize labels are author-controlled).
#
# Every signature and every runner-detection probe consults REPORTING only.
# Four rounds of adversarial review showed the same guarantee breaking through
# one pattern after another; the patterns were never the defect. Relayed text is
# attacker- (or merely application-) controlled and can reproduce ANY reporting
# shape verbatim, so no pattern can survive being matched against it.

# A CI runner prefixes every line (timestamps, stream tags). Stripped before any
# structural match so a wrapped capture is still parseable (control TP10).
_LINE_PREFIX_RE = re.compile(
    r"^(?:\d{4}-\d{2}-\d{2}T[\d:.]+Z?\s+|\[\d{2}:\d{2}:\d{2}\]\s+|\d+:\d+:\d+\s+)"
)

# pytest opens a relayed sub-block with a DASHED banner; the -rA PASSES section
# is relayed wholesale (it exists to show captured output of passing tests).
_RELAYED_BLOCK_START_RE = re.compile(
    r"^-{3,}\s*(?:captured\s+(?:stdout|stderr|log)\b[^-]*|live\s+log\b[^-]*)-{3,}\s*$"
    r"|^={3,}\s*PASSES\s*={3,}\s*$",
    re.IGNORECASE,
)

# A relayed block ends ONLY at a TERMINAL reporting section. Ending it at the
# next banner of any kind would be wrong: a relayed block can quote a FAILURES
# banner verbatim (case C1), and that quote is indistinguishable from a real one
# by text alone. The terminal sections cannot be faked into the wrong position
# because the runner emits them last.
_REPORTING_RESUME_RE = re.compile(
    r"^[=\s]*(?:short test summary info|ERRORS|warnings summary)[=\s]*$", re.IGNORECASE
)

# Single-line relayed markers used by the JS runners: the marker line and the
# indented lines that follow it are the application's output, not the runner's.
_RELAYED_LINE_START_RE = re.compile(
    r"^\s*(?:stdout|stderr)\s*\|"          # vitest:    stdout | src/x.test.ts > name
    r"|^\s*console\.(?:log|error|warn|info|debug)\b"   # jest
    r"|^\s*console\.(?:log|error|warn|info|debug)\s*:",  # playwright
    re.IGNORECASE,
)

_RESULT_TOKEN_RE = re.compile(
    r"(\d+)\s+(passed|failed|errors?|skipped|xfailed|xpassed|flaky|"
    r"did not run|interrupted|total)\b",
    re.IGNORECASE,
)
_FAILING_TOKENS = ("failed", "error", "errors")


def _strip_line_prefix(line: str) -> str:
    return _LINE_PREFIX_RE.sub("", line, count=1)


def _is_summary_line(line: str) -> bool:
    """True iff the line is a runner's own result-count summary.

    Excludes anything carrying a node id (``::``): a parametrize label may
    contain a whole fake summary, and the id belongs to the test, not to the
    run's verdict (cases E1 / E2).
    """
    bare = _strip_line_prefix(line).strip().strip("=").strip()
    if not bare or "::" in bare:
        return False
    return _RESULT_TOKEN_RE.search(bare) is not None


def _is_banner_summary_line(line: str) -> bool:
    """A summary line the RUNNER framed with its own banner rule (``==== ... ====``).

    Only this form may resume reporting after a relayed block. A bare summary
    line cannot: relayed text quotes those freely — a captured vitest report
    reading ``Test Files  1 failed | 7 passed`` would otherwise re-enter the
    region and make vitest's rows applicable to a green pytest run.
    """
    bare = _strip_line_prefix(line).strip()
    if not re.match(r"^={3,}.*={3,}$", bare):
        return False
    return _is_summary_line(line)


def reporting_region(output_text: str) -> str:
    """Return only the runner's own reporting lines, with relayed text removed."""
    if not isinstance(output_text, str) or not output_text:
        return ""
    kept: list[str] = []
    in_block = False
    in_continuation = False
    for raw in output_text.splitlines():
        line = _strip_line_prefix(raw)
        if in_block:
            # A relayed block resumes ONLY at a TERMINAL section banner. It
            # deliberately does NOT resume at a summary line, even a
            # banner-framed one: relayed text quotes those verbatim, and doing
            # so let a captured report re-enter the region and supply the run's
            # verdict (round-5 seam S5f / S5g).
            if _REPORTING_RESUME_RE.match(line) and not line[:1].isspace():
                in_block = False
                kept.append(raw)
            continue
        if in_continuation:
            # A relayed LINE marker owns its indented continuation block, not
            # just its own line — the continuation is where a fake terminal
            # summary gets planted (round-5 seam S5a / S5b). A blank line ends
            # it, which is how every JS runner separates console output from
            # its own reporting.
            if not line.strip():
                in_continuation = False
                kept.append(raw)
            continue
        if _RELAYED_BLOCK_START_RE.match(line.strip()):
            in_block = True
            continue
        if _RELAYED_LINE_START_RE.match(line):
            in_continuation = True
            continue
        kept.append(raw)
    return "\n".join(kept)


# A capture holding more than one run cannot say which run proves the guard.
_RUN_START_MARKERS: tuple[str, ...] = (
    r"(?mi)^=+\s*test session starts\s*=+",
    r"(?mi)^\s*RUN\s+v\d",
    r"(?mi)^\s*Running \d+ tests? using",
)


def _count_runs(reporting_text: str) -> int:
    return sum(len(re.findall(p, reporting_text)) for p in _RUN_START_MARKERS)


# Sections whose framed content is the runner's own failure reporting. Used on
# the ABSTAIN path, when no terminal verdict exists at all.
_FAILURE_SECTION_RE = re.compile(r"^=+\s*(FAILURES|ERRORS)\s*=+\s*$", re.IGNORECASE)
_ANY_BANNER_RE = re.compile(r"^=+.*=+\s*$")


def _framed_failure_sections(reporting_text: str) -> str:
    """Content inside the runner's own FAILURES / ERRORS sections, plus its
    short-summary lines. The only basis trusted when the verdict is ABSENT."""
    kept: list[str] = []
    inside = False
    for raw in reporting_text.splitlines():
        line = _strip_line_prefix(raw).rstrip()
        if _FAILURE_SECTION_RE.match(line.strip()):
            inside = True
            kept.append(raw)
            continue
        if inside and _ANY_BANNER_RE.match(line.strip()) and not _FAILURE_SECTION_RE.match(line.strip()):
            inside = _REPORTING_RESUME_RE.match(line) is not None
            if inside:
                kept.append(raw)
            continue
        if inside:
            kept.append(raw)
    return "\n".join(kept)


def _terminal_verdict(reporting_text: str) -> dict[str, int] | None:
    """Parse the LAST summary line of the reporting region into counts.

    This is the runner stating its own result. When it says nothing failed, no
    amount of failure-shaped text elsewhere makes the run red.
    """
    lines = reporting_text.splitlines()
    # Walk up from the end collecting the TRAILING BLOCK of summary lines, not
    # just the last one: Playwright, vitest and jest each split their counts
    # across adjacent lines ("1 failed" / "2 passed (4.9s)"), so reading only
    # the final line would drop the failure count and call a genuine red green
    # (control TP5).
    block: list[str] = []
    seen = False
    min_indent = 10**6
    for raw in reversed(lines):
        stripped = _strip_line_prefix(raw)
        if _is_summary_line(raw):
            block.append(raw)
            seen = True
            min_indent = min(min_indent, len(stripped) - len(stripped.lstrip()))
            continue
        if not stripped.strip():
            if seen:
                break
            continue
        # Real runners interleave a DETAIL line between their count lines —
        # Playwright's list reporter prints the failing test's id between
        # "1 failed" and "2 passed (4.9s)". A detail line is indented deeper
        # than the counts it belongs to; stopping at it dropped the failure
        # count and called a genuine red green (round-5 seam S5j / S5k).
        indent = len(stripped) - len(stripped.lstrip())
        if seen and indent > min_indent:
            continue
        if seen:
            break
    if not block:
        return None
    counts: dict[str, int] = {}
    for raw in block:
        bare = _strip_line_prefix(raw).strip().strip("=").strip()
        for num, word in _RESULT_TOKEN_RE.findall(bare):
            key = "error" if word.lower().startswith("error") else word.lower()
            counts[key] = counts.get(key, 0) + int(num)
    if not counts:
        return None
    failing = sum(v for k, v in counts.items() if k in ("failed", "error"))
    return {"failing": failing, **counts}


def _detect_runners_from_output(output_text: str) -> frozenset[str]:
    """Which runners the REPORTING REGION identifies, regardless of the command.

    This is what lets a genuine red captured through `make test` or
    `npm run test:unit` be recognized (adversarial B3) — the wrapper hides the
    runner's name from the command line, never from its output.

    Region-scoped since round 4: relayed text can quote another runner's report
    verbatim, which made that runner's rows applicable and turned a green run
    into a red one (cases C2 / C3).
    """
    if not isinstance(output_text, str) or not output_text.strip():
        return frozenset()
    region = reporting_region(output_text)
    found = {runner for runner, pattern in _RUNNER_OUTPUT_SHAPES
             if re.search(pattern, region)}
    return frozenset(found)


# B2 — typecheck INTENT, not the literal token `tsc`. The originating
# banking-app incident ran as `npm run typecheck`, whose command line never
# contains "tsc".
_TYPECHECK_INTENT_RE = re.compile(r"\b(?:tsc|typecheck|type-check)\b", re.IGNORECASE)


def _command_expresses_typecheck_intent(command: Any) -> bool:
    if not isinstance(command, str) or not command.strip():
        return False
    return _TYPECHECK_INTENT_RE.search(command) is not None


def _tsc_uses_build_mode(command: Any) -> bool:
    """True iff the tsc invocation is the solution-aware build form (``-b`` /
    ``--build``) — the very command the vacuous-tsc remediation demands, so it
    is never itself flagged."""
    if not isinstance(command, str):
        return False
    return re.search(r"(?:^|\s)(?:-b|--build)(?:\s|$)", command.lower()) is not None


# Result-count tokens a test runner prints in its summary line.
_RESULT_COUNT_RE = re.compile(
    r"(\d+)\s+(passed|failed|flaky|skipped|did not run|interrupted)", re.IGNORECASE
)


def _playwright_zero_total(check: dict[str, Any], output_text: str,
                           repo_root: Path | None) -> bool:
    """Predicate — a test run whose summary counts are ALL zero.

    A predicate rather than a substring because ``0 passed`` is a substring of
    ``10 passed``: the trap that makes a naive registry entry flag every real
    ten-test run.

    B2 widened the gate: the run qualifies when the command names a known
    runner OR the OUTPUT identifies one, so a zero-total run behind
    `npm run test:e2e` no longer escapes. Requiring a recognized runner (rather
    than firing on any "0 passed" text) keeps it off non-test output.
    """
    command = check.get("command")
    known = ("playwright", "pytest", "jest", "vitest")
    if not (any(_command_names_runner(command, r) for r in known)
            or _detect_runners_from_output(output_text or "")):
        return False
    counts = _RESULT_COUNT_RE.findall(output_text or "")
    if not counts:
        return False
    return all(int(n) == 0 for n, _ in counts)


_TSCONFIG_EMPTY_FILES_RE = re.compile(r'"files"\s*:\s*\[\s*\]')
_TSCONFIG_REFERENCES_RE = re.compile(r'"references"\s*:\s*\[')


def _is_solution_shaped_tsconfig(path: Path) -> bool:
    """True iff the resolved tsconfig is a solution/root config — ``files: []``
    plus a ``references`` array — which compiles nothing itself.

    Real tsconfig files are JSONC (``//`` comments are legal), so a
    ``json.loads`` failure falls back to a text-shape match rather than
    silently reporting "not solution-shaped".
    """
    try:
        raw = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        return bool(_TSCONFIG_EMPTY_FILES_RE.search(raw)
                    and _TSCONFIG_REFERENCES_RE.search(raw))
    if not isinstance(data, dict):
        return False
    files = data.get("files")
    refs = data.get("references")
    return isinstance(files, list) and not files and isinstance(refs, list) and bool(refs)


def _resolve_tsconfig(check: dict[str, Any], repo_root: Path | None) -> Path | None:
    """Locate the tsconfig a typecheck check runs against, or None.

    Resolution order: the check's cited ``tsconfig_path``, then
    ``<repo_root>/tsconfig.json``. Shared by the predicate and by the
    indeterminate-note path so the two can never disagree about what was
    locatable.
    """
    cited = check.get("tsconfig_path")
    if isinstance(cited, str) and cited.strip():
        target = _resolve_cited_path(cited, repo_root)
    else:
        base = repo_root if repo_root is not None else Path.cwd()
        target = base / "tsconfig.json"
    if target is None or not target.is_file():
        return None
    return target


def _tsc_solution_shape(check: dict[str, Any], output_text: str,
                        repo_root: Path | None) -> bool:
    """Predicate — ``tsc --noEmit`` pointed at a solution-shaped tsconfig.

    This is a REPO-STATE predicate, not an output substring: the vacuous run is
    silent and exits 0, so its own output carries no tell. When the config
    cannot be located the predicate CANNOT fire — that blind spot is reported
    as an indeterminate note rather than passed off as a clean result (see
    ``_typecheck_indeterminate_note``).
    """
    command = check.get("command")
    if not _command_expresses_typecheck_intent(command) or _tsc_uses_build_mode(command):
        return False
    target = _resolve_tsconfig(check, repo_root)
    if target is None:
        return False
    return _is_solution_shaped_tsconfig(target)


def _typecheck_indeterminate_note(check: dict[str, Any],
                                  repo_root: Path | None) -> dict[str, Any] | None:
    """A typecheck ran, but no tsconfig was locatable, so nothing was verified.

    Silence here would read as "checked and fine". The verdict says instead
    that the tool could not tell — the honest third state between pass and
    fail.
    """
    command = check.get("command")
    if not _command_expresses_typecheck_intent(command) or _tsc_uses_build_mode(command):
        return None
    if _resolve_tsconfig(check, repo_root) is not None:
        return None
    return {
        "kind": "typecheck-tsconfig-indeterminate",
        "command": command,
        "evidence": (
            f"check {command!r} expresses typecheck intent, but no tsconfig "
            f"could be located (no tsconfig_path cited and no tsconfig.json at "
            f"the repo root), so the solution-shape check could NOT run. This "
            f"check is unverified, not verified-clean."
        ),
        "remediation": (
            "Cite the config this check actually resolves via `tsconfig_path` "
            "on the check entry, or pass --repo-root so <repo_root>/tsconfig.json "
            "resolves. A solution-shaped config (\"files\": [] plus "
            "\"references\") makes `tsc --noEmit` examine zero files; until the "
            "config is visible, that cannot be ruled out."
        ),
    }


# ---------------------------------------------------------------------------
# The zero-work signature registry — DATA (design D4)
# ---------------------------------------------------------------------------
# Each entry is (runner, kind, matcher, remediation):
#   runner      — the runner whose output shape the entry was written for; it is
#                 reported on the finding.
#   kind        — "regex" (matched against the cited output; every shipped
#                 pattern is LINE-ANCHORED or count-aware) or "predicate" (a
#                 callable owning its own applicability, including any command
#                 gating). A raw bare-substring kind is deliberately NOT
#                 supported: an unanchored match flags a green log that merely
#                 QUOTES the signature, which is the A11 false positive.
#   matcher     — the pattern string, or a callable (check, output_text, repo_root).
#   remediation — what to run instead.
#
# Regex entries are NOT command-gated: their text is already runner-unique, so
# a zero-work run wrapped in `make test` or a shell script is still caught.
# Adding a runner is adding an entry here — `_scan_zero_work` takes the registry
# as a parameter and never branches on the runner key.
_ZERO_WORK_SIGNATURES: tuple[tuple[str, str, Any, str], ...] = (
    ("pytest", "regex", r"(?mi)^\s*collected 0 items\b",
     "pytest collected nothing — the path/-k selector matched no tests. Re-run "
     "naming a path that exists and confirm the collected count is non-zero."),
    ("pytest", "regex", r"(?mi)^[=\s]*no tests ran\b",
     "pytest ran no tests. A green exit here proves nothing was checked; fix "
     "the selector and cite a run whose summary reports tests executed."),
    ("vitest", "regex", r"(?mi)^\s*no tests found\b",
     "vitest matched no test files — check the include globs / filter, then "
     "cite a run that reports executed tests."),
    ("playwright", "regex", r"(?mi)^\s*(?:error:\s*)?no tests found\b",
     "Playwright matched no spec files — check testDir / testMatch and the "
     "path argument, then cite a run that reports a non-zero test count."),
    ("playwright", "predicate", _playwright_zero_total,
     "The run reported zero tests in every result bucket. Cite a run whose "
     "summary counts are non-zero."),
    ("jest", "regex", r"(?mi)^\s*no test files found\b",
     "jest matched no test files — check testMatch / the path pattern, then "
     "cite a run that reports executed suites."),
    ("tsc", "predicate", _tsc_solution_shape,
     "The resolved tsconfig is a solution file (\"files\": [] plus "
     "\"references\"), so `tsc --noEmit` type-checked ZERO files and exited 0. "
     "Re-run as `tsc -b` (build mode follows the project references) and cite "
     "that output instead."),
)


# ---------------------------------------------------------------------------
# The failure-signature registry — what a genuinely red run looks like
# ---------------------------------------------------------------------------
# (runner, regex pattern). Every row is a REGEX — anchored, count-aware, or
# glyph-exact — never a bare substring: a row satisfiable by the mere presence
# of reporting lets a GREEN run stand in as proof a guard can fail (adversarial
# B1 and W1). Case-insensitivity and multiline are set per-pattern via inline
# flags rather than globally, because some rows (`^FAILED `, `^ERROR `) must
# stay case-SENSITIVE to avoid matching ordinary prose.
#
# Applicability: a "*" row applies to every command; a named row applies when
# the command names that runner OR when `_detect_runners_from_output` finds that
# runner's shape in the output (B3 — a real red captured through `make test` or
# `npm run test:unit` must still be accepted).
#
# The failed-test glyphs are literal UTF-8, not escapes. The module never writes
# to a console — `_write_verdict` encodes UTF-8 — so no glyph can reach a
# cp1252 stdout, and none of them is ever copied into a verdict field.
_FAILURE_SIGNATURES: tuple[tuple[str, str], ...] = (
    # Count-aware AND summary-shaped. [1-9]\d* excludes "0 failed"; requiring
    # "failed" to start immediately after the digits excludes "1 xfailed"; and
    # the trailing lookahead requires a RESULT-SUMMARY boundary after the word —
    # end of line, a separator, or " in <duration>". Without that boundary the
    # row matched application log prose in a passing run's captured stdout
    # ("retry: 3 failed attempts before success"), which is the B1/W1 guarantee
    # falling through a different row (adversarial R1). Real summaries all
    # qualify: "1 failed, 45 passed in 3.02s", "Tests  1 failed | 42 passed
    # (43)", "Tests:  1 failed, 2 passed, 3 total", and a bare "  1 failed".
    ("*", r"(?i)(?<![\w.])[1-9]\d*\s+failed\b(?=\s*(?:[,|(]|$|\s+in\s))"),
    ("*", r"(?mi)^\s*Traceback \(most recent call last\)"),
    # pytest prints traceback lines as "E   AssertionError: ..." — line-anchored
    # so a test merely NAMED test_assertionerror cannot satisfy it.
    ("*", r"(?m)^\s*E\s+\w*(?:Error|Exception)\b"),
    # NOTE (adversarial R2): there is deliberately NO bare
    # `^<Name>Error: <text>` row. A PASSING test that exercises an error path
    # under -s prints exactly that line, so the row let a green run forge a red.
    # A genuine uncaught exception is preceded by "Traceback (most recent call
    # last)" and pytest prefixes its own assertion lines with "E ", both matched
    # above — so removing it costs no true positive.
    ("pytest", r"(?mi)^=+\s*FAILURES\s*=+"),
    ("pytest", r"(?m)^FAILED\s"),
    ("pytest", r"(?m)^ERROR\s"),
    # NOTE (adversarial W1): there is deliberately NO `short test summary info`
    # row. That string is a SECTION HEADER pytest prints whenever results are
    # reported at all — under -rA / -ra / -rs, and whenever skips or xfails are
    # summarized — NOT when something failed, so it let a fully green run stand
    # in as proof a guard can fail. Removing it costs no true positive: a real
    # red prints that header alongside `^FAILED ` lines, a FAILURES banner, and
    # a non-zero failed count, each of which is matched above. Every row in this
    # table must be satisfiable ONLY by failure content, never by the presence
    # of reporting.
    ("playwright", r"✘"),   # heavy ballot X - Playwright's failed-test glyph
    ("jest", r"(?m)^\s*FAIL\s"),
    ("jest", r"✕"),         # multiplication X - jest/vitest's failed-test glyph
    ("vitest", r"(?m)^\s*FAIL\s"),
    ("vitest", r"✕"),
)


# B4 — correlating a cited red output with the guard it claims to prove.
_TEST_PATH_RE = re.compile(
    r"(?i)[\w.\-/]*(?:test|spec)[\w.\-]*\.(?:py|ts|tsx|js|jsx|mjs|cjs|rb|go|java|cs)\b"
)
_TEST_NODE_ID_RE = re.compile(r"(?i)::\s*test\w+")


def _output_identifies_any_test(output_text: str) -> bool:
    """True iff the output names ANY test file or node id.

    This is the hinge between adversarial B3 and B4. An output that identifies
    some test CAN be correlated, so failing to name the guard under proof is
    real evidence of a mis-citation. An output that names no test at all — a
    `pytest --tb=no` summary behind `make test`, for instance — cannot be
    correlated either way, so correlation is INDETERMINATE and is not held
    against an otherwise genuine red. Without this split, B4's correlation
    requirement would reject exactly the honest wrapper-captured reds B3
    requires be accepted.
    """
    if not isinstance(output_text, str) or not output_text.strip():
        return False
    normalized = output_text.replace("\\", "/")
    return bool(_TEST_PATH_RE.search(normalized) or _TEST_NODE_ID_RE.search(normalized))


def _output_references_test(test_file: str, output_text: str) -> bool:
    """True iff the output names this specific test file (path or basename).

    Separator-insensitive. Basename-or-full-path only — deliberately NOT the
    stem, because a stem match would let `test_guard.py` be "proved" by output
    that only ever mentions `test_guard_2.py`.

    STATED BOUNDARY (adversarial R4): the basename arm cannot separate two new
    test files that share a basename across directories — output naming
    `tests/integration/test_guard.py` satisfies correlation for
    `tests/unit/test_guard.py` too. Dropping the basename arm is not the fix:
    it would reject the common case where a runner prints a path relative to a
    different root than the artifact used. Runners that print path-shaped ids
    resolve it naturally; see the module docstring's STATED BOUNDARIES.
    """
    if not isinstance(test_file, str) or not isinstance(output_text, str):
        return False
    normalized_out = output_text.replace("\\", "/").lower()
    normalized_tf = test_file.replace("\\", "/").lower().lstrip("./")
    if not normalized_tf:
        return False
    basename = normalized_tf.rsplit("/", 1)[-1]
    return normalized_tf in normalized_out or basename in normalized_out


def _posix_key(path: Any) -> str:
    """Normalize a test-file path for keyed lookup (adversarial B5).

    `new_test_files` and the `red_runs` keys are authored by hand and by
    different tools, so one side arrives with Windows separators and the other
    with POSIX. Matching them raw produced a spurious never-shown-red on the
    normal Windows case.
    """
    if not isinstance(path, str):
        return ""
    return path.strip().replace("\\", "/").lstrip("./").lower()


def _resolve_cited_path(path_str: Any, repo_root: Path | None) -> Path | None:
    """Resolve a cited path from either separator form, relative to repo_root.

    Backslashes are normalized before the join (the A3 path-normalization house
    pattern) so a Windows-authored artifact resolves on POSIX and vice versa.
    """
    if not isinstance(path_str, str) or not path_str.strip():
        return None
    normalized = path_str.strip().replace("\\", "/")
    candidate = Path(normalized)
    if candidate.is_absolute() or repo_root is None:
        return candidate
    return Path(repo_root) / normalized


def _detect_missing_cited_output(path_str: Any,
                                 repo_root: Path | None) -> tuple[str | None, str]:
    """The ``_detect_missing_evidence_artifact`` bar, applied to a cited output.

    Returns ``(reason, evidence)`` — reason is one of ``no-path`` /
    ``does-not-exist`` / ``is-a-directory`` / ``is-empty``, or ``None`` when a
    real non-empty file is cited.
    """
    if not isinstance(path_str, str) or not path_str.strip():
        return "no-path", "no output_path is cited"
    resolved = _resolve_cited_path(path_str, repo_root)
    if resolved is None:
        return "no-path", "no output_path is cited"
    if not resolved.exists():
        return "does-not-exist", f"cited output_path {path_str!r} does not exist on disk"
    if resolved.is_dir():
        return "is-a-directory", f"cited output_path {path_str!r} is a directory; must be a file"
    try:
        size = resolved.stat().st_size
    except OSError:
        size = 0
    if size <= 0:
        return "is-empty", f"cited output_path {path_str!r} is empty (0 bytes)"
    return None, ""


def _decode_output_bytes(raw: bytes) -> str:
    """Decode a captured console log, honoring the encodings real toolchains emit.

    Reading everything as utf-8 with ``errors='replace'`` silently defeated the
    whole scan on UTF-16 output: a UTF-16LE file interleaves NUL bytes between
    the characters, so `collected 0 items` never matched and a zero-work run
    passed (adversarial A5/A7). This is not exotic on Windows — PowerShell's
    ``Out-File -Encoding Unicode`` emits UTF-16LE, and a stock PS 5.1 ``>``
    redirection does too (on THIS machine, PS 5.1.26100.8875, ``>`` was
    measured emitting UTF-8-BOM instead; both are handled).

    Order: an explicit BOM wins; otherwise a high NUL ratio is the tell for
    BOM-less UTF-16; otherwise utf-8 with replacement, which never raises.

    STATED BOUNDARY (adversarial W3, rated low): three constructed shapes
    still evade this ladder — BOM-less UTF-16LE whose NUL ratio is diluted
    below the one-third floor by wide characters, a truncated odd-length
    UTF-16 file (both decodes raise and it falls through to utf-8), and
    BOM-less UTF-16BE (the LE attempt yields garbage that passes the
    NUL-count sanity check). The basis for rating it low is MEASURED, not
    assumed: every generator available on the reference platform emits a
    BOM — `Out-File -Encoding Unicode` / `-Encoding BigEndianUnicode` /
    `Set-Content -Encoding Unicode` — and stock `>` redirection emitted
    UTF-8-BOM there, so producing an evading file needs a hand-rolled
    writer rather than an ordinary toolchain.
    """
    if not raw:
        return ""
    if raw.startswith(codecs.BOM_UTF8):
        return raw.decode("utf-8-sig", errors="replace")
    if raw.startswith(codecs.BOM_UTF16_LE) or raw.startswith(codecs.BOM_UTF16_BE):
        return raw.decode("utf-16", errors="replace")
    # BOM-less UTF-16: ASCII text encoded as UTF-16 is ~50% NUL bytes. A third
    # is a conservative floor that plain utf-8 logs never reach.
    if raw.count(0) * 3 >= len(raw):
        for encoding in ("utf-16-le", "utf-16-be"):
            try:
                decoded = raw.decode(encoding)
            except (UnicodeDecodeError, ValueError):
                continue
            if decoded.count("\x00") * 3 < max(len(decoded), 1):
                return decoded
    return raw.decode("utf-8", errors="replace")


def _read_output_text(path_str: Any, repo_root: Path | None) -> str:
    """Read a cited output tolerantly — an undecodable byte never crashes a scan."""
    resolved = _resolve_cited_path(path_str, repo_root)
    if resolved is None:
        return ""
    try:
        return _decode_output_bytes(resolved.read_bytes())
    except OSError:
        return ""


def _scan_zero_work(
    check: dict[str, Any],
    output_text: str,
    repo_root: Path | None,
    registry: tuple[tuple[str, str, Any, str], ...],
) -> list[tuple[str, str, str]]:
    """Match one check against the registry. Returns (runner, matched, remediation).

    One generic routine over the whole table — no per-runner branching, so a new
    runner is a data edit.
    """
    # Region-scoped since round 4: the zero-work registry had the SAME defect in
    # the false-positive direction — a real 57-item run whose captured stdout
    # quoted `collected 0 items` was refused as vacuous (cases G1 / G2 / G3).
    # A banner the run RELAYED says nothing about what the run examined.
    text = reporting_region(output_text or "")
    hits: list[tuple[str, str, str]] = []
    # Two runners can legitimately share a signature (`no tests found` is both
    # Playwright's and vitest's). Both entries stay in the table — each
    # documents its own runner and remediation — but one matched TEXT is one
    # finding, reported against the first runner that claims it.
    seen_matches: set[str] = set()
    for runner, kind, matcher, remediation in registry:
        if kind == "regex":
            if not isinstance(matcher, str):
                continue
            m = re.search(matcher, text)
            if not m:
                continue
            matched = " ".join(m.group(0).split()).strip("= ")
            key = matched.lower()
            if key in seen_matches:
                continue
            seen_matches.add(key)
            hits.append((runner, matched, remediation))
        elif kind == "predicate":
            try:
                fired = bool(matcher(check, output_text, repo_root))
            except Exception:  # a predicate never breaks the scan
                fired = False
            if fired:
                hits.append((runner, f"{runner} zero-work predicate", remediation))
    return hits


def _output_shows_failure(command: Any, output_text: str,
                          registry: tuple[tuple[str, str], ...] | None = None) -> bool:
    """True iff the output carries a failure signature applicable to its runner.

    A signature applies when it is generic (``*``), when the COMMAND names its
    runner, or when the OUTPUT SHAPE identifies that runner (B3 — a real red
    captured through `make test` or `npm run test:unit` must be accepted).
    Every pattern is anchored or count-aware so that no GREEN run can satisfy
    one (B1).
    """
    table = registry if registry is not None else _FAILURE_SIGNATURES
    text = output_text or ""
    if not text.strip():
        return False
    return _assess_red_output(command, text, table)["is_red"]


def _assess_red_output(command: Any, output_text: str,
                       table: tuple[tuple[str, str], ...]) -> dict[str, Any]:
    """Decide whether a capture shows a failing run, and say on what basis.

    Three verdict modes, each with an explicit path — round 5 moved the load
    onto this mechanism, and an undefined mode is where the next forgery lands:

      PRESENT    the runner stated its result. It decides, full stop: nothing
                 failing means green no matter what the capture relays.
      AMBIGUOUS  the capture holds more than one run. Which one proves the
                 guard is undetermined, so it proves nothing — refused with a
                 reason code rather than resolved by first- or last-wins, both
                 of which are arbitrary.
      ABSENT     truncated capture, no summary at all. This does NOT fall back
                 to matching the whole region — that is the very behavior the
                 scope fix removed. It abstains to the runner's own FRAMED
                 failure sections and records that the basis was degraded.
    """
    text = output_text or ""
    region = reporting_region(text)
    if not region.strip():
        return {"is_red": False, "basis": "empty-region", "verdict": None}

    if _count_runs(region) > 1:
        return {"is_red": False, "basis": "ambiguous-multi-run-capture", "verdict": None}

    verdict = _terminal_verdict(region)
    if verdict is not None:
        return {
            "is_red": verdict["failing"] > 0,
            "basis": "terminal-verdict",
            "verdict": verdict,
        }

    # ABSTAIN — framed sections only, never the whole region.
    framed = _framed_failure_sections(region)
    if not framed.strip():
        return {"is_red": False, "basis": "verdict-absent-no-framed-failures", "verdict": None}
    return {
        "is_red": _match_failure_rows(command, framed, text, table),
        "basis": "verdict-absent-framed-sections-only",
        "verdict": None,
    }


def _match_failure_rows(command: Any, haystack: str, whole_output: str,
                        table: tuple[tuple[str, str], ...]) -> bool:
    region = haystack
    detected = _detect_runners_from_output(whole_output)
    for runner, pattern in table:
        if runner != "*" and runner not in detected and not _command_names_runner(command, runner):
            continue
        m = re.search(pattern, region)
        if not m:
            continue
        # The count-aware row states a RESULT, so it may only be read off a
        # result line — never off prose or a node id that happens to contain a
        # count (cases A3 / E1 / E2).
        if "failed" in pattern and "\\d" in pattern:
            line = next((ln for ln in region.splitlines()
                         if re.search(pattern, ln) and _is_summary_line(ln)), None)
            if line is None:
                continue
        return True
    return False


def _normalize_for_containment(text: str) -> str:
    """Collapse whitespace + lowercase so an excerpt survives re-wrapping."""
    return " ".join((text or "").split()).lower()


_RED_RUN_REMEDIATION = (
    "v3.47.0 check-falsifiability. A guard is not evidence until it has been "
    "shown able to fail. Capture the run in which this test FAILED — its full "
    "output, not a paraphrase — and cite that file, quoting an excerpt that "
    "appears verbatim in it. Accepted red sources: "
    + " / ".join(_ACCEPTED_RED_SOURCES) + "."
)


def verify_check_can_fail(
    verification_artifact: dict[str, Any] | None = None,
    repo_root: Path | str | None = None,
    out_path: Path | str | None = None,
    signature_registry: tuple[tuple[str, str, Any, str], ...] | None = None,
) -> dict[str, Any]:
    """v3.47.0 Layer-3 tool — verify that the run's checks could have failed.

    Args:
      verification_artifact: the check-integrity artifact (see the module
        docstring for the contract). A non-dict is treated as empty.
      repo_root: base for relative cited paths; falls back to the artifact's
        own ``repo_root`` field, then to leaving relative paths as-is.
      out_path: optional path to write the verdict JSON.
      signature_registry: override the zero-work registry (the extensibility
        seam — a new runner is a new entry, never a scan-logic edit).

    Returns::

        {
          "tool": "verify-check-can-fail",
          "valid": bool,
          "gaps": [{"severity", "evidence", "remediation", ...}],
          "notes": [{"kind", "evidence", "remediation", ...}],
          "checks_scanned": int,
          "new_test_files_count": int,
          "red_runs_cited": int,
          "verdict_at": "<ISO 8601 UTC>"
        }

    Three severities: ``vacuous-check`` (a check that examined nothing, or whose
    cited output is missing / empty / a directory), ``new-guard-never-shown-red``
    (a new test file with no cited red run, or one whose cited red source is not
    an accepted one), and ``red-run-not-red`` (a cited red run whose output
    carries no failure signature, is missing, or does not contain the quoted
    excerpt).

    ``notes`` are NOT gaps and never fail the verdict: they record what the
    tool could NOT determine — currently a typecheck whose tsconfig could not be
    located — so a blind spot is stated rather than passed off as a clean
    result.

    ``exit_code`` is RECORDED on each finding, never gating: a vacuous pytest
    run exits 5 and a vacuous ``tsc --noEmit`` exits 0 — neither exit code tells
    you whether work was done.
    """
    artifact = verification_artifact if isinstance(verification_artifact, dict) else {}
    registry = signature_registry if signature_registry is not None else _ZERO_WORK_SIGNATURES

    base = repo_root if repo_root is not None else artifact.get("repo_root")
    root = Path(base) if isinstance(base, (str, Path)) and str(base).strip() else None

    gaps: list[dict[str, Any]] = []
    # Notes are NOT gaps: they record what the tool could not determine, so a
    # blind spot never reads as a clean result.
    notes: list[dict[str, Any]] = []

    # --- half 1: every cited check examined something ----------------------
    checks = artifact.get("checks") or []
    checks = [c for c in checks if isinstance(c, dict)] if isinstance(checks, list) else []
    for check in checks:
        command = check.get("command")
        cited = check.get("output_path")
        indeterminate = _typecheck_indeterminate_note(check, root)
        if indeterminate is not None:
            notes.append(indeterminate)
        reason, evidence = _detect_missing_cited_output(cited, root)
        if reason is not None:
            gaps.append({
                "severity": "vacuous-check",
                "command": command,
                "output_path": cited,
                "exit_code": check.get("exit_code"),
                "runner": None,
                "matched_signature": None,
                "evidence": (
                    f"check {command!r} cites no readable output: {evidence}. "
                    f"A check whose output nobody can read is not evidence it ran."
                ),
                "remediation": (
                    "Re-run the check redirecting its FULL output to a file and "
                    "cite that path. The evidence bar is the same one "
                    "verify-live-verification-claim applies to artifacts: the "
                    "cited path must be an on-disk file with content."
                ),
            })
            continue
        output_text = _read_output_text(cited, root)
        for runner, matched, remediation in _scan_zero_work(check, output_text, root, registry):
            gaps.append({
                "severity": "vacuous-check",
                "command": command,
                "output_path": cited,
                "exit_code": check.get("exit_code"),
                "runner": runner,
                "matched_signature": matched,
                "evidence": (
                    f"check {command!r} cites output {cited!r} matching the "
                    f"{runner} zero-work signature {matched!r} - the check "
                    f"passed while examining nothing."
                ),
                "remediation": remediation,
            })

    # --- half 2: every new guard has been shown red ------------------------
    new_test_files = artifact.get("new_test_files") or []
    if not isinstance(new_test_files, list):
        new_test_files = []
    new_test_files = [p for p in new_test_files if isinstance(p, str) and p.strip()]

    red_runs = artifact.get("red_runs") or {}
    if not isinstance(red_runs, dict):
        red_runs = {}

    # B5 — match new_test_files against red_runs keys on a posix-normalized
    # basis so a Windows-authored artifact cannot produce a spurious
    # never-shown-red against a POSIX-authored key (or vice versa).
    red_runs_by_key: dict[str, Any] = {}
    for raw_key, block in red_runs.items():
        red_runs_by_key.setdefault(_posix_key(raw_key), block)

    for test_file in new_test_files:
        block = red_runs_by_key.get(_posix_key(test_file))
        if not isinstance(block, dict):
            gaps.append({
                "severity": "new-guard-never-shown-red",
                "test_file": test_file,
                "evidence": (
                    f"new test file {test_file!r} cites no red run - nobody has "
                    f"shown this guard can fail, so its green means nothing."
                ),
                "remediation": _RED_RUN_REMEDIATION,
            })

    # Validate every cited red run — including any for a file the artifact did
    # not list as new (the citation still has to hold up). Keyed on the
    # normalized identity (B5) so one red run is validated exactly once no
    # matter which separator form each side used.
    new_keys = {_posix_key(p) for p in new_test_files}
    ordered: list[tuple[str, dict[str, Any]]] = []
    seen_red_keys: set[str] = set()
    for path in new_test_files:
        key = _posix_key(path)
        blk = red_runs_by_key.get(key)
        if isinstance(blk, dict) and key not in seen_red_keys:
            seen_red_keys.add(key)
            ordered.append((path, blk))
    for raw_key in sorted(red_runs):
        key = _posix_key(raw_key)
        if key in new_keys or key in seen_red_keys:
            continue
        if isinstance(red_runs[raw_key], dict):
            seen_red_keys.add(key)
            ordered.append((raw_key, red_runs[raw_key]))

    # R3 closure — how many guards cite each distinct output. A cited output
    # that names no test is ANONYMOUS: nothing ties it to any particular guard,
    # so citing the same one for several guards proves none of them. Counted
    # across the whole artifact before the per-guard loop, because the defect is
    # a property of the SET of citations, not of any one of them.
    shared_output_counts: dict[str, int] = {}
    for _tf, _blk in ordered:
        key = _posix_key(_blk.get("output_path"))
        if key:
            shared_output_counts[key] = shared_output_counts.get(key, 0) + 1

    for test_file, block in ordered:
        command = block.get("command")
        cited = block.get("output_path")

        red_source = block.get("red_source")
        if red_source is not None and red_source not in _ACCEPTED_RED_SOURCES:
            gaps.append({
                "severity": "new-guard-never-shown-red",
                "test_file": test_file,
                "red_source": red_source,
                "evidence": (
                    f"red run for {test_file!r} cites red_source {red_source!r}, "
                    f"which is not one of the accepted red sources - the red "
                    f"output's provenance is unestablished."
                ),
                "remediation": _RED_RUN_REMEDIATION,
            })

        reasons: list[str] = []
        missing_reason, missing_evidence = _detect_missing_cited_output(cited, root)
        if missing_reason is not None:
            reasons.append("output-missing")
            detail = missing_evidence
        else:
            output_text = _read_output_text(cited, root)
            detail = ""
            if not _output_shows_failure(command, output_text):
                reasons.append("no-failure-signature")
                detail = "the cited output carries no failure signature for its runner"
            excerpt = block.get("observed_failure_excerpt")
            if isinstance(excerpt, str) and excerpt.strip():
                if _normalize_for_containment(excerpt) not in _normalize_for_containment(output_text):
                    reasons.append("excerpt-not-in-output")
                    detail = (detail + "; " if detail else "") + (
                        f"the quoted excerpt {excerpt!r} does not appear in the cited output"
                    )
            # B4 — the output must be about THIS guard. Checked only when the
            # output identifies some test at all; an output that names none
            # (a --tb=no summary behind a wrapper) cannot be correlated either
            # way, and penalizing it would reject the honest wrapper-captured
            # reds B3 requires be accepted.
            identifies_a_test = _output_identifies_any_test(output_text)
            if not _output_references_test(test_file, output_text) and identifies_a_test:
                reasons.append("output-does-not-reference-test")
                detail = (detail + "; " if detail else "") + (
                    f"the cited output names other tests but never {test_file!r}, "
                    f"so it is not evidence about THIS guard"
                )
            # R3 — when correlation is INDETERMINATE, the quoted excerpt is the
            # only remaining tie between the output and the guard, so it stops
            # being optional. Without it a single name-free summary proves
            # nothing in particular and can be pasted under any number of
            # guards. Scoped to the indeterminate case so B3's honest
            # wrapper-captured reds (which do quote their failure) still pass.
            elif not identifies_a_test:
                if not (isinstance(excerpt, str) and excerpt.strip()):
                    reasons.append("excerpt-required-when-indeterminate")
                    detail = (detail + "; " if detail else "") + (
                        "the cited output names no test at all, so nothing ties it to "
                        f"{test_file!r} — quote the failure you observed in "
                        "observed_failure_excerpt"
                    )
                # R3 closure. An excerpt raises the floor but does not make the
                # citation unique — one string satisfies the excerpt rule as
                # many times as it is pasted. An anonymous output cited for
                # SEVERAL guards is the one-red-proves-anything forgery, and it
                # is the SHARING that gives it away.
                if shared_output_counts.get(_posix_key(cited), 0) > 1:
                    reasons.append("shared-anonymous-red")
                    detail = (detail + "; " if detail else "") + (
                        f"the cited output names no test and is reused as the red "
                        f"proof for {shared_output_counts[_posix_key(cited)]} guards, "
                        f"so it cannot be evidence about {test_file!r} in particular"
                    )
        if reasons:
            gaps.append({
                "severity": "red-run-not-red",
                "test_file": test_file,
                "command": command,
                "output_path": cited,
                "red_source": red_source,
                "reasons": reasons,
                "evidence": (
                    f"red run for {test_file!r} cites {cited!r} but {detail}."
                ),
                "remediation": _RED_RUN_REMEDIATION,
            })

    verdict = {
        "tool": "verify-check-can-fail",
        "valid": len(gaps) == 0,
        "gaps": gaps,
        "notes": notes,
        "checks_scanned": len(checks),
        "new_test_files_count": len(new_test_files),
        "red_runs_cited": len(red_runs),
        "verdict_at": _utc_now_iso(),
    }
    return _write_verdict(verdict, out_path)
