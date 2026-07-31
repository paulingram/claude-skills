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

Originating failure: the banking-app FDS fix-list release (2026-07-30) — a
typecheck gate that reported green having examined zero files, a jest run that
"passed" on *No test files found*, and new guards trusted on their first green.

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


def _detect_runners_from_output(output_text: str) -> frozenset[str]:
    """Which runners the OUTPUT itself identifies, regardless of the command.

    This is what lets a genuine red captured through `make test` or
    `npm run test:unit` be recognized (adversarial B3) — the wrapper hides the
    runner's name from the command line, never from its output.
    """
    if not isinstance(output_text, str) or not output_text.strip():
        return frozenset()
    found = {runner for runner, pattern in _RUNNER_OUTPUT_SHAPES
             if re.search(pattern, output_text)}
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
# (runner, substring). A "*" row applies to every command; a named row applies
# only when the red run's command names that runner. Matched case-insensitively.
# The check-mark glyphs are written as escapes so this source stays pure ASCII.
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
    text = output_text or ""
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
    detected = _detect_runners_from_output(text)
    for runner, pattern in table:
        if runner != "*" and runner not in detected and not _command_names_runner(command, runner):
            continue
        if re.search(pattern, text):
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
            if (not _output_references_test(test_file, output_text)
                    and _output_identifies_any_test(output_text)):
                reasons.append("output-does-not-reference-test")
                detail = (detail + "; " if detail else "") + (
                    f"the cited output names other tests but never {test_file!r}, "
                    f"so it is not evidence about THIS guard"
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
