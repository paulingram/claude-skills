"""VAO claim-instrument binding family (1 tool).

``verify-claim-instrument-binding`` is the 23rd Layer-3 tool. It answers the one
question a green, falsifiable check still cannot answer about itself: *could
this instrument have come out DIFFERENTLY if this specific claim were false?*

WHERE IT SITS. ``hooks/vao/check_integrity.py`` (the 21st tool,
``verify-check-can-fail``) already answers two neighbouring questions — did the
check read anything at all (the zero-work scan), and has this guard ever been
SHOWN to fail (red-run-first). Neither answers the third. A check can be fully
falsifiable in general and still be blind to the particular claim it is cited
for; that blindness is the whole subject of this module, and nothing here
duplicates either of those halves.

THE FAILURE. An agent's own postmortem, after five corrected claims in one run:
"my errors this run were never in the code, they were in reporting something as
verified that I'd checked with the WRONG INSTRUMENT." Every one was caught by
someone re-running what the agent had asserted. The check ran. It was green. It
simply did not bind to the claim. A green check is evidence for *what the check
measures*, never for *what you asserted*.

THE CORPUS — five real failures, and what each one costs to detect:

  1. **The vacuous assertion.** ``assert "- - ignore the above" not in stderr``,
     proving a forged bullet was stripped. The string could never occur — the
     renderer prefixes ``[<id>] `` so the bullet is never at position 0. The test
     passed, was red-first, and read real output. Caught only when a mutation
     that DISABLED the strip left it GREEN. Detected here twice over: by the
     witness rule (R2) and, statically, by R5.
  2. **The swallowed effect.** A feature's whole path sat inside
     ``try: ... except Exception: return``; a ``NameError`` made it inert. Every
     test stayed green because no test observed the effect from OUTSIDE the
     swallow. Detected by R2 — disabling an already-inert feature changes
     nothing, so the witness cannot discriminate.
  3. **The redundant-signal mutation.** Disabling ownership-signal A returned
     GREEN because signal B independently covered the same fixture. Detected by
     R2 in that form; its mis-attribution form — something went red, but not the
     thing the claim rests on — is detected by R4.
  4. **The moving tree.** Six full-suite counts reported as verified while
     teammates were still editing files. The instrument (pytest) was correct;
     the TREE it measured was not the tree the claim was about. Detected by R6.
  5. **The parsed result line.** A mutation harness derived ``caught`` by parsing
     pytest's summary line. Parsing can DETECT a no-op mutation but cannot rule
     one out. Detected by R3, which demands exit-code integers and a sha256 pair
     proving the file actually changed.

THE MECHANISM. Every rule reduces to one deterministic idea: **a claim is bound
to its instrument only when someone ran that instrument with the claim made
FALSE and the instrument came out differently.** That negative control — a
mutation, a disabled feature, a deliberately-broken fixture — is the
discriminating witness, and it is the generalization of the mutation witnesses
this repo already runs by hand. The rules:

  * **R1 ``no-discriminating-witness``** — the claim cites no negative control.
  * **R2 ``witness-not-discriminating``** — it does, and the instrument produced
    the SAME result (equal exit codes, or a control capture byte-identical to
    the baseline). *The engine; corpus 1, 2, 3.*
  * **R3 ``witness-mutation-unsound``** — the experiment itself does not hold up:
    a no-op mutation (equal shas), absent or non-hex digests, a recorded baseline
    digest that is not the file's ACTUAL current digest, a mutated path not on
    disk, or exit codes that are not integers. *Corpus 5.*
  * **R4 ``witness-does-not-bind-to-claim``** — the experiment is sound but about
    the wrong thing: it mutated a file outside the claim's declared subject, or
    the tests it made fail do not include any the claim rests on. *Corpus 3.*
  * **R5 ``vacuous-negative-assertion``** — a cited absence assertion whose needle
    appears in NEITHER the baseline capture nor the control. *Corpus 1.*
  * **R6 ``measurement-input-state-unpinned``** — a whole-tree measurement claim
    with no quiescence bracket, or one whose bracket does not close. *Corpus 4.*
  * **R7 ``cited-test-absent-from-instrument-output``** — the instrument ran and
    was green over OTHER tests; it never executed the test the claim rests on.

Artifact contract::

    {
      "repo_root": "<required for any on-disk check to be decidable>",
      "claims": [{
        "id": "C1",
        "statement": "the forged bullet is stripped from the rendered stderr",
        "subject_paths": ["hooks/open_work.py"],
        "cited_tests": ["tests/test_open_work.py::test_bullet_is_stripped"],
        "instrument": {"command": str, "output_path": str, "exit_code": int?},
        "assertions": [{"polarity": "absence"|"presence", "needle": str, "text": str?}],
        "witness": {
          "kind": "mutation" | "negative-control",
          "description": str,
          "mutated_path": str,            # mutation kind only
          "baseline_sha256": str,         # mutation kind only
          "mutated_sha256": str,          # mutation kind only
          "baseline_exit_code": int,
          "mutated_exit_code": int,
          "mutated_output_path": str,
          "failing_tests_under_mutation": [str, ...]
        },
        "tree_state": {"before": str, "after": str}
      }]
    }

WHAT IS NOT DECIDED — stated rather than left for a reader to discover. Each was
weighed during design and rejected as undecidable; where the tool cannot decide
it emits a ``notes`` entry (never a gap), on the same principle as
``check_integrity``'s typecheck-indeterminate note: a blind spot is reported,
not passed off as a clean result.

  * **Whether a needle CAN occur** (corpus 1 in the abstract) is undecidable
    without running the renderer. R5 does not try. It decides the one case that
    IS decidable — the needle is absent from the control too, so the assertion
    could not have flipped under the very experiment cited for it. With no
    control capture, an absent needle is the ORDINARY shape of a passing absence
    assertion, and firing there would be a false-positive factory; the tool
    notes ``negative-control-capture-absent`` and moves on.

  * **Polarity inferred from prose.** ``_is_absence_assertion`` falls back to a
    text heuristic only when the assertion does not label itself, and ``text`` is
    contracted to be the QUOTED ASSERTION. Ordinary prose that happens to read
    "the row is not in draft state" is inferred as an absence assertion, which is
    why an explicit ``polarity`` always wins and is the preferred form. The blast
    radius is small — a mis-inferred assertion only produces a finding when its
    needle is absent from both captures, which is suspicious for a presence
    assertion too — but it is a real imprecision and is not papered over.

  * **Intra-test redundancy** (corpus 3's subtle form). R4 correlates the tests a
    mutation made fail against the tests a claim cites. It cannot see that the
    same test still passes through a second internal signal, because that
    distinction exists only inside the test's execution and never reaches an
    artifact. Building a fixture only signal A can resolve remains a human act.

  * **Whether a recorded integer is the real exit code.** Every Layer-3 tool
    reads an agent-written artifact, and this one is no different. What R3 buys
    is that the required SHAPE cannot be produced by the failure it targets: a
    summary-line parse yields no exit-code integers and no digest pair, so
    corpus 5's classification simply cannot be written down here. The one field
    checked against the world rather than taken on trust is
    ``baseline_sha256`` — it must equal the file's ACTUAL current digest.

  * **Whether the tree digests are real.** R6 requires the bracket to close
    (``before == after``) but cannot re-derive either value: by verdict time the
    tree has legitimately moved on. Presence and closure are what remain
    decidable.

  * **Which claims belong in the artifact.** The tool demands a witness for every
    claim it is handed and grants no per-claim exemption — an exemption field
    would be the escape hatch that empties the rule. Applicability is therefore a
    WIRING decision (which claims a run registers), deliberately not a judgment
    this tool makes.

  * **Relative paths with no ``repo_root``.** Unlike ``check_integrity``, a
    relative cited path is NOT resolved against the process cwd here; it is
    reported unresolvable. A verdict that changes with the directory the tool was
    invoked from is not a deterministic verdict.

Stdlib-only; no import-time side effects; the only write is the verdict file.
Path resolution, output reading, containment normalization and test-name
correlation are REUSED from ``hooks/vao/check_integrity.py`` rather than
re-implemented.
"""

from __future__ import annotations

import hashlib
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

try:  # package shape: repo root on sys.path
    from hooks.vao.check_integrity import (
        _detect_missing_cited_output,
        _normalize_for_containment,
        _output_identifies_any_test,
        _output_references_test,
        _posix_key,
        _read_output_text,
        _resolve_cited_path,
    )
except ImportError:  # hooks/ on sys.path (vao is the package)
    try:
        from vao.check_integrity import (
            _detect_missing_cited_output,
            _normalize_for_containment,
            _output_identifies_any_test,
            _output_references_test,
            _posix_key,
            _read_output_text,
            _resolve_cited_path,
        )
    except ImportError:  # hooks/vao/ on sys.path (bare sibling)
        from check_integrity import (  # type: ignore[no-redef]
            _detect_missing_cited_output,
            _normalize_for_containment,
            _output_identifies_any_test,
            _output_references_test,
            _posix_key,
            _read_output_text,
            _resolve_cited_path,
        )


# The two ways a negative control is actually produced. `mutation` changes a
# file, so the digest evidence applies to it; `negative-control` disables the
# behavior some other way (an env flag, a swapped fixture, a stubbed dependency)
# and changes nothing on disk, so the digest rules are WAIVED for it — at the
# cost of a note saying the corpus-5 no-op class is not excluded. Any other
# value is not a negative control at all; "I reasoned it through" is the thing
# this tool exists to refuse.
_ACCEPTED_WITNESS_KINDS: tuple[str, ...] = ("mutation", "negative-control")

_MUTATION_KIND = "mutation"


# A claim whose subject is the WHOLE TREE rather than one behavior (corpus 4).
# Matched against the claim's own statement, so the agent does not get to decide
# whether the rule applies to it — the sentence it wrote decides.
#
# The threshold row is deliberate: a THREE-figure test count is a whole-tree
# measurement by construction, whatever the sentence calls it, while "3 tests
# pass" is a slice and must never be asked to pin a tree. Anything between is
# resolved in favour of silence — a tool that flags everything is worse than
# none — and a claim that IS tree-scoped without saying so can declare
# `tree_scoped: true`.
_TREE_SCOPE_MARKERS: tuple[str, ...] = (
    r"(?i)\b(?:full|entire|whole|complete)\s+(?:test\s+)?suite\b",
    r"(?i)\ball\s+(?:the\s+)?tests?\b",
    r"(?i)\bevery\s+test\b",
    r"(?i)\bsuite[-\s]wide\b",
    r"(?i)\brepo[-\s]wide\b",
    r"(?i)\bacross\s+the\s+(?:repo|repository|codebase|tree)\b",
    r"(?i)\bthe\s+suite\s+is\s+green\b",
    r"(?i)\bwhole\s+(?:repo|repository|codebase|tree)\b",
    r"(?i)(?<![\w.])\d{3,}\s+(?:tests?\s+)?(?:passed|passing|failed|failing)\b",
)


# Textual tells that a quoted assertion is a NEGATIVE one. Used only when the
# assertion does not label its own polarity; an explicit `polarity` always wins.
_ABSENCE_ASSERTION_MARKERS: tuple[str, ...] = (
    " not in ",
    "assertnotin",
    "assert_not_in",
    "not_in(",
    "not.tocontain",
    "not.tohave",
    "notcontain",
    "does not contain",
    "must not appear",
    "not_to_contain",
)

_ABSENCE_POLARITY_VALUES: frozenset[str] = frozenset(
    {"absence", "absent", "negative", "not-in", "not_in", "notin", "excluded"}
)


_WITNESS_REMEDIATION = (
    "Bind the claim to its instrument with a discriminating witness: run the "
    "SAME check with the claim made false — mutate the code the claim is about, "
    "or disable the behavior by a negative control — and record "
    "baseline_exit_code / mutated_exit_code as integers, the before/after "
    "sha256 of the mutated file, the control's captured output, and the tests "
    "the mutation made fail. If the instrument comes out the same, it was never "
    "measuring the claim and its green says nothing about it."
)

_MEASUREMENT_REMEDIATION = (
    "Pin the input state a whole-tree measurement was taken over: record "
    "tree_state.before immediately before the run and tree_state.after "
    "immediately after (a commit sha plus a digest of `git status --porcelain`, "
    "or a hash of the tracked-file contents). A bracket that does not close "
    "means the tree moved while it was being measured, so the number is about "
    "no particular tree."
)

_VACUITY_REMEDIATION = (
    "Assert the rendering that OCCURS rather than a string adjacent to it. This "
    "needle is absent from the green capture AND from the control in which the "
    "claim was made false, so the assertion could not have come out differently "
    "— it is satisfied by the string being unproducible, not by the behavior "
    "working. Either quote a needle the control actually contains, or invert the "
    "assertion to the positive form."
)

_CORRELATION_REMEDIATION = (
    "Cite an instrument that actually ran the test the claim rests on. This "
    "capture names other tests and never this one, so it is a green run over "
    "different code — re-run with the cited test in scope and cite THAT output."
)


# ---------------------------------------------------------------------------
# Small deterministic predicates
# ---------------------------------------------------------------------------


def _is_int(value: Any) -> bool:
    """True for a real integer. ``bool`` is excluded deliberately — ``True`` is
    an ``int`` in Python, and an exit code of ``True`` is a classification
    nobody made."""
    return isinstance(value, int) and not isinstance(value, bool)


def _is_sha256(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    candidate = value.strip().lower()
    return len(candidate) == 64 and all(c in "0123456789abcdef" for c in candidate)


def _resolve(path_str: Any, root: Path | None) -> Path | None:
    """Resolve a cited path, or None when it cannot be resolved DETERMINISTICALLY.

    A relative path with no ``repo_root`` returns None rather than being joined
    to the process cwd: a verdict that changes with the invoking directory is
    not a verdict. Absolute paths always resolve.
    """
    if not isinstance(path_str, str) or not path_str.strip():
        return None
    if root is None and not Path(path_str.strip().replace("\\", "/")).is_absolute():
        return None
    return _resolve_cited_path(path_str, root)


def _is_absence_assertion(assertion: Any) -> bool:
    """True iff this assertion is satisfied by ABSENCE.

    An explicit ``polarity`` decides. Only when none is given is the quoted
    assertion text consulted for a negative tell (``not in`` / ``assertNotIn`` /
    ``.not.toContain``), so an agent that labels its assertions is never
    second-guessed by a text heuristic.
    """
    if not isinstance(assertion, dict):
        return False
    polarity = assertion.get("polarity")
    if isinstance(polarity, str) and polarity.strip():
        return polarity.strip().lower() in _ABSENCE_POLARITY_VALUES
    text = str(assertion.get("text") or "").lower()
    if not text:
        return False
    return any(marker in text for marker in _ABSENCE_ASSERTION_MARKERS)


def _claim_is_tree_scoped(claim: Any) -> bool:
    """True iff the claim is a WHOLE-TREE measurement (corpus 4).

    Decided from the claim's own statement, with an explicit ``tree_scoped``
    flag as an override for a measurement whose sentence does not say so.
    """
    if not isinstance(claim, dict):
        return False
    if claim.get("tree_scoped") is True:
        return True
    statement = claim.get("statement")
    if not isinstance(statement, str) or not statement.strip():
        return False
    return any(re.search(pattern, statement) for pattern in _TREE_SCOPE_MARKERS)


def _path_under_any(path: Any, roots: Any) -> bool:
    """True iff ``path`` is one of ``roots`` or lives under one of them.

    Separator- and case-insensitive via the shared ``_posix_key``, so a
    Windows-authored witness matches a POSIX-authored subject list. A declared
    DIRECTORY covers the files inside it — the common honest shape.
    """
    key = _posix_key(path)
    if not key or not isinstance(roots, (list, tuple)):
        return False
    for root in roots:
        root_key = _posix_key(root).rstrip("/")
        if not root_key:
            continue
        if key == root_key or key.startswith(root_key + "/"):
            return True
    return False


def _test_id_leaf(test_id: Any) -> str:
    """The bare test name from any id shape: ``a/b.py::Cls::test_x[param]`` ->
    ``test_x``."""
    if not isinstance(test_id, str):
        return ""
    tail = test_id.replace("\\", "/").strip().split("::")[-1]
    return tail.split("[")[0].strip().lower()


def _test_ids_intersect(cited: Any, observed: Any) -> bool:
    """True iff any cited test id names the same test as any observed one.

    Matching is deliberately GENEROUS — full id, suffix, or bare leaf name —
    because runners report ids in several shapes and a false positive here would
    reject honest work. A false negative merely asks for a clearer record.
    """
    if not isinstance(cited, (list, tuple)) or not isinstance(observed, (list, tuple)):
        return False
    for c in cited:
        c_key = _posix_key(c)
        c_leaf = _test_id_leaf(c)
        for o in observed:
            o_key = _posix_key(o)
            o_leaf = _test_id_leaf(o)
            if not c_key or not o_key:
                continue
            if c_key == o_key or c_key.endswith(o_key) or o_key.endswith(c_key):
                return True
            if c_leaf and c_leaf == o_leaf:
                return True
    return False


def _output_names_cited_test(cited: Any, output_text: str) -> bool:
    """True iff the instrument's output names this cited test.

    Reuses ``check_integrity._output_references_test`` for the file half (and
    inherits its stated same-basename boundary), and adds the node-id half so a
    ``file.py::test_name`` citation correlates on either component.
    """
    if not isinstance(cited, str) or not cited.strip():
        return False
    ident = cited.replace("\\", "/").strip()
    file_part, _, node_part = ident.partition("::")
    if file_part and _output_references_test(file_part, output_text):
        return True
    leaf = _test_id_leaf(ident)
    if leaf and leaf in (output_text or "").lower():
        return True
    return False


# ---------------------------------------------------------------------------
# Verdict record builders
# ---------------------------------------------------------------------------


def _gap(severity: str, claim: dict[str, Any], reasons: list[str],
         evidence: str, remediation: str) -> dict[str, Any]:
    return {
        "severity": severity,
        "claim_id": claim.get("id"),
        "statement": claim.get("statement"),
        "reasons": reasons,
        "evidence": evidence,
        "remediation": remediation,
    }


def _note(kind: str, claim: dict[str, Any], evidence: str,
          remediation: str) -> dict[str, Any]:
    return {
        "kind": kind,
        "claim_id": claim.get("id"),
        "evidence": evidence,
        "remediation": remediation,
    }


# ---------------------------------------------------------------------------
# The tool
# ---------------------------------------------------------------------------


def verify_claim_instrument_binding(
    verification_artifact: dict[str, Any] | None = None,
    repo_root: Path | str | None = None,
    out_path: Path | str | None = None,
) -> dict[str, Any]:
    """Layer-3 tool — verify each verified claim BINDS to the instrument cited for it.

    Args:
      verification_artifact: the claim-binding artifact (see the module
        docstring for the contract). A non-dict is treated as empty.
      repo_root: base for relative cited paths; falls back to the artifact's own
        ``repo_root`` field. Without one, no on-disk check is decidable and the
        affected checks become notes rather than gaps.
      out_path: optional path to write the verdict JSON.

    Returns::

        {
          "tool": "verify-claim-instrument-binding",
          "valid": bool,
          "gaps": [{"severity", "claim_id", "statement", "reasons", "evidence",
                    "remediation"}],
          "notes": [{"kind", "claim_id", "evidence", "remediation"}],
          "claims_scanned": int,
          "witnesses_cited": int,
          "verdict_at": "<ISO 8601 UTC>"
        }

    Seven severities — ``no-discriminating-witness``,
    ``witness-not-discriminating``, ``witness-mutation-unsound``,
    ``witness-does-not-bind-to-claim``, ``vacuous-negative-assertion``,
    ``measurement-input-state-unpinned``, ``cited-test-absent-from-instrument-output``
    — each carrying a ``reasons[]`` array, the field a consumer keys on.

    ``notes`` are NOT gaps and never fail the verdict: they record what the tool
    could not determine, so a blind spot is stated rather than passed off as a
    clean result.
    """
    artifact = verification_artifact if isinstance(verification_artifact, dict) else {}

    base = repo_root if repo_root is not None else artifact.get("repo_root")
    root = Path(base) if isinstance(base, (str, Path)) and str(base).strip() else None

    claims = artifact.get("claims") or []
    claims = [c for c in claims if isinstance(c, dict)] if isinstance(claims, list) else []

    gaps: list[dict[str, Any]] = []
    notes: list[dict[str, Any]] = []
    witnesses_cited = 0

    for claim in claims:
        # --- the instrument's own capture, read once and shared by R5 / R7 ----
        instrument = claim.get("instrument")
        instrument = instrument if isinstance(instrument, dict) else {}
        instrument_output = instrument.get("output_path")
        baseline_text = ""
        if not (isinstance(instrument_output, str) and instrument_output.strip()):
            notes.append(_note(
                "instrument-not-cited", claim,
                "the claim cites no instrument output_path, so nothing ties the "
                "claim to a check that was actually run",
                "Cite the command and the captured output of the check this claim rests on.",
            ))
        elif _resolve(instrument_output, root) is None:
            notes.append(_note(
                "instrument-output-unresolvable", claim,
                f"instrument output_path {instrument_output!r} is relative and no "
                f"repo_root was supplied, so it cannot be resolved deterministically",
                "Pass --repo-root, or cite an absolute path.",
            ))
        else:
            missing_reason, missing_evidence = _detect_missing_cited_output(instrument_output, root)
            if missing_reason is not None:
                notes.append(_note(
                    "instrument-output-unreadable", claim,
                    f"the cited instrument output cannot be read: {missing_evidence}. "
                    f"Binding to it could not be checked (a missing capture is "
                    f"verify-check-can-fail's vacuous-check, not this tool's finding)",
                    "Re-run the check redirecting its full output to a file and cite that path.",
                ))
            else:
                baseline_text = _read_output_text(instrument_output, root)

        # --- R6: a whole-tree measurement must pin the tree it measured -------
        # Placed before the witness rules because it is a property of the CLAIM,
        # not of any experiment run against it.
        if _claim_is_tree_scoped(claim):
            tree_state = claim.get("tree_state")
            tree_state = tree_state if isinstance(tree_state, dict) else {}
            before = str(tree_state.get("before") or "").strip()
            after = str(tree_state.get("after") or "").strip()
            measurement_reasons: list[str] = []
            if not before or not after:
                measurement_reasons.append("no-quiescence-bracket")
                detail = (
                    "no tree_state bracket is recorded, so the measurement is "
                    "about no particular tree state"
                )
            elif before != after:
                measurement_reasons.append("tree-moved-during-measurement")
                detail = (
                    f"the tree_state bracket does not close ({before!r} -> {after!r}): "
                    f"the tree changed while it was being measured"
                )
            if measurement_reasons:
                gaps.append(_gap(
                    "measurement-input-state-unpinned", claim, measurement_reasons,
                    f"claim {claim.get('id')!r} is a whole-tree measurement and {detail}. "
                    f"The instrument may be correct while the tree it measured is not "
                    f"the tree the claim is about.",
                    _MEASUREMENT_REMEDIATION,
                ))

        # --- R7: did the instrument even run the test the claim rests on? -----
        cited = claim.get("cited_tests")
        cited = [t for t in cited if isinstance(t, str) and t.strip()] if isinstance(cited, list) else []
        if not cited:
            notes.append(_note(
                "cited-tests-undeclared", claim,
                "the claim declares no cited_tests, so the instrument's output "
                "cannot be correlated with the guard the claim rests on",
                "List the test ids that verify this claim in cited_tests[].",
            ))
        elif baseline_text.strip():
            out_text = baseline_text
            if not _output_identifies_any_test(out_text):
                notes.append(_note(
                    "instrument-output-anonymous", claim,
                    "the instrument's output names no test at all (a --tb=no "
                    "summary behind a wrapper), so correlation is indeterminate "
                    "in both directions and is not held against this claim",
                    "Capture the run with per-test reporting (-v, or name the paths) "
                    "so the output identifies what it executed.",
                ))
            elif not any(_output_names_cited_test(t, out_text) for t in cited):
                gaps.append(_gap(
                    "cited-test-absent-from-instrument-output", claim,
                    ["instrument-output-names-other-tests-only"],
                    f"the instrument's output names other tests but none of the "
                    f"cited tests {cited!r} — it is a green run over different code, "
                    f"not evidence about this claim",
                    _CORRELATION_REMEDIATION,
                ))

        # --- R1: is there a negative control at all? --------------------------
        witness = claim.get("witness")
        if not isinstance(witness, dict) or not witness:
            gaps.append(_gap(
                "no-discriminating-witness", claim, ["witness-not-cited"],
                f"claim {claim.get('id')!r} cites no negative control. Its check may "
                f"have run and may be falsifiable in general, but nobody showed it "
                f"comes out differently when this claim is false — so its green is "
                f"evidence for what the check measures, not for the claim.",
                _WITNESS_REMEDIATION,
            ))
            continue

        witnesses_cited += 1
        kind = witness.get("kind")
        kind = kind.strip().lower() if isinstance(kind, str) else ""
        if kind not in _ACCEPTED_WITNESS_KINDS:
            gaps.append(_gap(
                "no-discriminating-witness", claim, ["unrecognized-witness-kind"],
                f"claim {claim.get('id')!r} cites a witness of kind {witness.get('kind')!r}, "
                f"which is not one of {list(_ACCEPTED_WITNESS_KINDS)}. A negative control is "
                f"something that was RUN with the claim made false, not a description of one.",
                _WITNESS_REMEDIATION,
            ))
            continue

        # --- the control capture, read once and shared by R2 / R5 -------------
        control_path = witness.get("mutated_output_path")
        control_text = ""
        control_readable = False
        if not (isinstance(control_path, str) and control_path.strip()):
            notes.append(_note(
                "negative-control-capture-absent", claim,
                "the witness records no mutated_output_path, so the control's own "
                "output could not be compared with the baseline and absence-vacuity "
                "could not be decided",
                "Redirect the control run's full output to a file and cite it as "
                "mutated_output_path.",
            ))
        elif _resolve(control_path, root) is None:
            notes.append(_note(
                "negative-control-capture-absent", claim,
                f"the witness cites mutated_output_path {control_path!r}, which is "
                f"relative with no repo_root and cannot be resolved deterministically",
                "Pass --repo-root, or cite an absolute path.",
            ))
        else:
            missing_reason, missing_evidence = _detect_missing_cited_output(control_path, root)
            if missing_reason is not None:
                notes.append(_note(
                    "negative-control-capture-absent", claim,
                    f"the witness cites a control capture that cannot be read: {missing_evidence}",
                    "Re-run the control redirecting its full output to a file.",
                ))
            else:
                control_text = _read_output_text(control_path, root)
                control_readable = True

        # --- R3: is the experiment itself sound? ------------------------------
        unsound_reasons: list[str] = []
        unsound_details: list[str] = []

        base_exit = witness.get("baseline_exit_code")
        mut_exit = witness.get("mutated_exit_code")
        exits_classified = _is_int(base_exit) and _is_int(mut_exit)
        if not exits_classified:
            unsound_reasons.append("exit-code-not-classified")
            unsound_details.append(
                f"baseline_exit_code={base_exit!r} / mutated_exit_code={mut_exit!r} "
                f"are not both integers. Deriving `caught` from a parsed summary "
                f"line can DETECT a no-op but cannot rule one out; the exit code can"
            )

        if kind == _MUTATION_KIND:
            mutated_path = witness.get("mutated_path")
            resolved_target: Path | None = None
            if not (isinstance(mutated_path, str) and mutated_path.strip()):
                unsound_reasons.append("mutated-path-not-cited")
                unsound_details.append(
                    "the witness names no mutated_path, so there is nothing to "
                    "verify a mutation was applied to"
                )
            else:
                resolved_target = _resolve(mutated_path, root)
                if resolved_target is None:
                    notes.append(_note(
                        "witness-path-unresolvable", claim,
                        f"mutated_path {mutated_path!r} is relative and no repo_root was "
                        f"supplied, so neither its existence nor its baseline digest "
                        f"could be checked against disk",
                        "Pass --repo-root so the witness's file evidence can be verified.",
                    ))
                elif not resolved_target.is_file():
                    unsound_reasons.append("mutated-path-missing-from-disk")
                    unsound_details.append(
                        f"mutated_path {mutated_path!r} does not exist on disk, so no "
                        f"mutation of it can be verified"
                    )

            base_sha = witness.get("baseline_sha256")
            mut_sha = witness.get("mutated_sha256")
            if base_sha is None or mut_sha is None:
                unsound_reasons.append("sha-missing")
                unsound_details.append(
                    "the witness records no before/after sha256 pair, so a mutation "
                    "that never changed the file cannot be ruled out"
                )
            elif not (_is_sha256(base_sha) and _is_sha256(mut_sha)):
                unsound_reasons.append("sha-not-hex")
                unsound_details.append(
                    f"baseline_sha256={base_sha!r} / mutated_sha256={mut_sha!r} are not "
                    f"both sha256 digests, so they are not evidence a file changed"
                )
            else:
                base_sha = str(base_sha).strip().lower()
                mut_sha = str(mut_sha).strip().lower()
                if base_sha == mut_sha:
                    unsound_reasons.append("no-op-mutation")
                    unsound_details.append(
                        f"the before and after digests are identical ({base_sha[:12]}...), "
                        f"so the file never changed — whatever ran afterwards was not an "
                        f"experiment"
                    )
                elif resolved_target is not None and resolved_target.is_file():
                    try:
                        disk_sha = hashlib.sha256(resolved_target.read_bytes()).hexdigest()
                    except OSError:
                        disk_sha = ""
                    if disk_sha and disk_sha != base_sha:
                        unsound_reasons.append("baseline-sha-not-current")
                        unsound_details.append(
                            f"the recorded baseline digest ({base_sha[:12]}...) is not the "
                            f"file's actual current digest ({disk_sha[:12]}...), so the "
                            f"witness was captured against a file state that no longer "
                            f"exists — the moving-tree failure at file granularity"
                        )
        else:
            notes.append(_note(
                "no-op-class-not-excluded", claim,
                "this is a negative-control witness, which changes nothing on disk, "
                "so the sha256 evidence that rules out a no-op experiment does not "
                "apply to it. The discrimination requirement still does",
                "Where the control CAN be expressed as a file mutation, prefer "
                "kind=mutation — it is the only form whose no-op class is excludable.",
            ))

        if unsound_reasons:
            gaps.append(_gap(
                "witness-mutation-unsound", claim, unsound_reasons,
                f"the negative control cited for claim {claim.get('id')!r} does not hold "
                f"up as an experiment: " + "; ".join(unsound_details) + ".",
                _WITNESS_REMEDIATION,
            ))

        # --- R2: did the instrument come out DIFFERENTLY? ---------------------
        # The engine. Evaluated even when R3 fired: a sound-looking experiment
        # that produced the same result and an unsound one are different
        # findings, and a reader needs both.
        not_discriminating: list[str] = []
        discrimination_details: list[str] = []
        if exits_classified:
            if base_exit == mut_exit:
                not_discriminating.append("same-exit-code")
                discrimination_details.append(
                    f"the instrument exited {base_exit} both with the claim true and "
                    f"with it false — it could not have come out differently, so its "
                    f"green is not about this claim"
                )
        if control_readable and baseline_text and control_text == baseline_text:
            not_discriminating.append("control-output-identical-to-baseline")
            discrimination_details.append(
                "the control's captured output is byte-identical to the baseline's, "
                "so nothing about the run changed when the claim was made false"
            )
        if not_discriminating:
            gaps.append(_gap(
                "witness-not-discriminating", claim, not_discriminating,
                f"the negative control cited for claim {claim.get('id')!r} did not "
                f"discriminate: " + "; ".join(discrimination_details) + ".",
                _WITNESS_REMEDIATION,
            ))

        # --- R4: is the experiment about THIS claim? --------------------------
        binding_reasons: list[str] = []
        binding_details: list[str] = []

        subject_paths = claim.get("subject_paths")
        subject_paths = (
            [p for p in subject_paths if isinstance(p, str) and p.strip()]
            if isinstance(subject_paths, list) else []
        )
        mutated_path = witness.get("mutated_path")
        if kind == _MUTATION_KIND and isinstance(mutated_path, str) and mutated_path.strip():
            if not subject_paths:
                notes.append(_note(
                    "subject-paths-undeclared", claim,
                    "the claim declares no subject_paths, so whether the mutation "
                    "touched the code the claim is about could not be checked",
                    "List the files the claim is about in subject_paths[].",
                ))
            else:
                if not _path_under_any(mutated_path, subject_paths):
                    binding_reasons.append("mutates-outside-claim-subject")
                    binding_details.append(
                        f"the witness mutated {mutated_path!r}, which is not under any "
                        f"declared subject path {subject_paths!r} — it is an experiment "
                        f"about a different file"
                    )

        observed_failures = witness.get("failing_tests_under_mutation")
        observed_failures = (
            [t for t in observed_failures if isinstance(t, str) and t.strip()]
            if isinstance(observed_failures, list) else []
        )
        if cited:
            if not observed_failures:
                notes.append(_note(
                    "witness-attribution-unrecorded", claim,
                    "the witness records no failing_tests_under_mutation, so whether "
                    "the control was caught by the guard this claim rests on — rather "
                    "than by an unrelated one — could not be determined",
                    "Record the test ids the control run made fail; the runner prints them.",
                ))
            elif not _test_ids_intersect(cited, observed_failures):
                binding_reasons.append("no-cited-test-failed-under-mutation")
                binding_details.append(
                    f"the control was caught by {observed_failures!r}, none of which is "
                    f"a cited test of this claim {cited!r} — something went red, but not "
                    f"the thing the claim rests on"
                )

        if binding_reasons:
            gaps.append(_gap(
                "witness-does-not-bind-to-claim", claim, binding_reasons,
                f"the negative control cited for claim {claim.get('id')!r} is a sound "
                f"experiment about the wrong thing: " + "; ".join(binding_details) + ".",
                _WITNESS_REMEDIATION,
            ))

        # --- R5: an absence assertion that could not have flipped -------------
        assertions = claim.get("assertions")
        assertions = assertions if isinstance(assertions, list) else []
        for assertion in assertions:
            if not _is_absence_assertion(assertion):
                continue
            needle = assertion.get("needle") if isinstance(assertion, dict) else None
            if not (isinstance(needle, str) and needle.strip()):
                continue
            if not control_readable:
                # Without a control, a needle absent from a green run is the
                # ORDINARY shape of a passing absence assertion. The
                # negative-control-capture-absent note above already records it.
                continue
            normalized_needle = _normalize_for_containment(needle)
            if not normalized_needle:
                continue
            in_baseline = normalized_needle in _normalize_for_containment(baseline_text)
            in_control = normalized_needle in _normalize_for_containment(control_text)
            if not in_baseline and not in_control:
                gaps.append(_gap(
                    "vacuous-negative-assertion", claim,
                    ["needle-absent-from-both-captures"],
                    f"the absence assertion on {needle!r} is satisfied in the baseline "
                    f"AND in the control in which the claim was made false — the string "
                    f"appears in neither capture, so the assertion could not have come "
                    f"out differently. It measures a string adjacent to the claim, not "
                    f"the claim.",
                    _VACUITY_REMEDIATION,
                ))

    verdict = {
        "tool": "verify-claim-instrument-binding",
        "valid": len(gaps) == 0,
        "gaps": gaps,
        "notes": notes,
        "claims_scanned": len(claims),
        "witnesses_cited": witnesses_cited,
        "verdict_at": _utc_now_iso(),
    }
    return _write_verdict(verdict, out_path)
