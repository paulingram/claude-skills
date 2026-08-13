# -*- coding: utf-8 -*-
"""Deterministic suite-measurement bracket emitter + claim-backing gate.

Stdlib-only, no import-time side effects. Mirrors the established engine shape of
`scripts/docs_tooling/changelog_check.py` and `scripts/compliance/instruction_compliance.py`:
importable pure functions, an `assess`-style dict return, a `--json` CLI, and no
work performed at import.

WHY THIS EXISTS
---------------
Five suite counts were published in this repo's last four releases as
"frozen-tree, hash-bracketed" — 7284, 7305, 7360, 7375, 7386 — and **no bracket
artifact exists on disk for any of them** (`docs/proposals/WRONG_INSTRUMENT_FOLLOWUPS.md`,
OPEN item 1). The runs happened and the output was read; the evidence is prose.
Unverifiable later, by anyone, in either direction.

That is the *borrowed green* class the v3.59.x releases were built to fix, still
open in the process that shipped them. The fix is not another convention asking
someone to record a bracket. It is a script that MAKES the bracket, plus a gate
that makes its absence a red suite.

THE BRACKET
-----------
`measure_suite` digests the tree BEFORE the run, runs the suite, digests it
AFTER, and records both. A bracket that does not close means the tree moved while
it was being measured — the instrument may be correct while the tree it measured
is not the tree the claim is about. That is a **first-class failure** here: it
has its own verdict, its own violation, and its own exit code
(`EXIT_BRACKET_OPEN`), and it OUTRANKS a red suite, because a measurement of a
moving tree is not a measurement at all.

What the digest covers, and why:

* ``git rev-parse HEAD`` — the commit the working tree is anchored to.
* ``git diff HEAD`` — the FULL patch text of every tracked modification, staged
  and unstaged. Content, not just names, so an in-place edit is caught.
* ``git status --porcelain --untracked-files=all`` — the untracked path list.
  ``git diff HEAD`` is blind to a file that is not tracked yet, and "a new test
  file appeared mid-run" is exactly the churn that moves a suite count.

What it deliberately does NOT cover, named rather than left to be discovered:

* **Untracked file CONTENT — and only content.** The path list is hashed, so an
  untracked file appearing, disappearing, or being RENAMED does open the bracket
  (all three change the name set; measured, not assumed). What is invisible is an
  untracked file edited IN PLACE between the two digests. Hashing the content of
  every untracked file is unbounded in an arbitrary checkout (an untracked venv, a
  build directory) for a case that does not move a suite count, so the precise
  boundary is content-only, not "untracked files are invisible".
* **Gitignored paths.** Git cannot see them without an explicit walk, and in THIS
  repo the ignored `.architect-team/` tree holds fixtures five committed tests
  hard-require. That blind spot is precisely why `MACHINE_BOUND_CAVEAT` rides in
  every artifact instead of living in a reader's memory.
* **Anything outside the repo** — the interpreter, installed packages, the clock.

UNKNOWN IS NOT CLEAN
--------------------
Outside a git repo (or with git unavailable) the tree state is UNKNOWN, and two
unknowns must not compare equal into a passing bracket. `bracket_closes` is False
whenever either digest is `UNKNOWN_DIGEST` — the same fail-safe asymmetry as
`hooks/open_work.py`'s unknown-status-counts-as-OPEN.

THE EXIT CODE DECIDES, NOT THE SUMMARY LINE
-------------------------------------------
`suite_green` is `exit_code == 0`. The parsed `counts` are RECORDED, never used to
decide whether the run passed — this repo shipped a summary-line-parse defect and
fixed it two releases ago.

THE GATE
--------
`verify_measurement_claim(text, measurements_dir)` takes release-note text
asserting "N passing + M skipped" and requires a matching artifact with a closed
bracket. It is wired into `scripts/docs_tooling/changelog_check.py`, which already
enforces the two machine-checkable CHANGELOG invariants — one of which is *the top
entry must carry a suite-total line*. The two compose: that invariant forces a
count to be claimed, and this one forces the claim to be backed. "Just don't state
a count" is closed by the module being extended, which is why extending it is the
right home rather than standing up a new gate.

THE LABEL-TO-TREE BINDING — a release label is a claim about a TREE
--------------------------------------------------------------------
``head`` names a COMMIT. It does not name the tree that was measured: a dirty
tree at commit X is a different tree from commit X, and every count is a property
of the tree, not of the commit it descends from.

Left unbound, that gap produces the most expensive failure this tool can have.
A measurement taken mid-development and labelled ``v3.59.3`` records HEAD plus
whatever was uncommitted, then the gate reports that number as v3.59.3's and
contradicts a *correct* published count. A gate that cries wolf against correct
work teaches its reader to disbelieve it, which is strictly worse than no gate.
(This is not hypothetical: the first artifact this engine shipped was mislabelled
exactly this way and had to be retracted.)

So ``is_release_label`` recognises a version-shaped label, ``tree_digest``
reports ``dirty`` as a first-class fact, and a release-labelled measurement of a
dirty tree is marked **provisional** — recorded, because it is a true measurement
of *something*, but refused as backing for any published count, with its own
verdict and its own exit code. A non-release label ("wip", "nightly") carries no
such claim and no such obligation, so development is unaffected.

WHERE EACH CHECK CAN HOLD
-------------------------
Because a release measurement can only exist on a release tree, *demanding* one
is only meaningful when the tree is clean:

* ALWAYS — a release-labelled artifact must be usable (non-provisional, closed
  bracket), and must AGREE with the published count. A wrong number in a durable
  location is worse than the prose it replaced.
* ONLY ON A CLEAN TREE — a published count must HAVE a measurement. Mid-
  development every tree is dirty, so demanding one then demands something that
  cannot exist yet, and a gate that demands the impossible gets deleted rather
  than satisfied. On a fresh clone and in CI the tree IS clean, which is exactly
  where a published count with nothing behind it must not pass.

  **The consequence, stated rather than left implicit:** a single stray untracked
  file (``touch scratch.txt``) makes the tree dirty and silences the existence
  arm. That is deliberate — the alternative demands the impossible — but it means
  this arm is a CI-and-fresh-clone guarantee, not a local one. The two ALWAYS
  arms are what hold on a working tree.

WHY COUNT AGREEMENT IS NOT ENFORCED FROM INSIDE THE SUITE
----------------------------------------------------------
A gate test living in the suite is part of the number it validates, so the
arrangement has a dynamics. These were MEASURED — a toy suite of five ordinary
tests plus one gate test, iterated measure -> run -> measure to a fixed point —
not reasoned about:

* **Presence-only** (what ships): 5 passed/1 failed -> 6/0 -> 6/0. **Converges in
  two measurements.** Run 1 fails for lack of an artifact and writes one anyway;
  run 2 then passes and overwrites it with the true green count. Reproduced at
  full scale as 7489 -> 7490.
* **Count agreement, claim = the true green total**: 5/1 -> 5/1 -> 5/1. A **stuck
  red absorbing state** with no path out by measuring — once the artifact records
  the red count, the gate keeps failing and the next measurement records the red
  count again. Worse than oscillation, which at least moves visibly.
* **Count agreement, claim = the red count**: 5/1 -> 6/0 -> 5/1 -> … a period-2
  oscillation with no fixed point.
* **Count agreement with the gate test DESELECTED from the measured command**:
  5/0 -> 5/0. **Converges in one.**

So convergence is NOT the obstacle, and an earlier draft of this note claiming it
was is wrong. The real obstacle is what the number would then MEAN: the
self-referential test has to be excluded from the count it validates, and a count
taken with an exclusion no longer describes a plain ``python -m pytest`` run —
which is exactly the number the CHANGELOG publishes and the number a reader will
try to reproduce with one command. The alternative, publishing deselected-plus-one,
puts an arithmetic step in the release notes that nobody can verify by running
anything.

Demanding existence only on a clean tree sidesteps all of it: the artifact is
committed and therefore static, so there is no feedback loop to have dynamics.

A GATE MUST BE REACHABLE — the currency arm was not
----------------------------------------------------
The release-time currency check first compared the artifact's recorded tree
digest against the tree right now. Measured against the documented release
sequence, it was red in BOTH states — before committing the artifact and after —
because **writing the artifact changes the tree**. It could not be satisfied
anywhere, by anyone.

That is the same defect one tier down as F5, where the completion lock's own
notify state was hashed by the progress fingerprint, so every block moved the
fingerprint, the no-progress counter reset, and the budget could never exhaust.
A budget that cannot be reached is not a budget; a check that cannot pass is not
a check — it is a gate on its way to being deleted, which is worse than no gate
because deleting it also removes the checks that did work.

The fix is F5's rule verbatim — *exclude your own bookkeeping from the state you
hash* — applied in `source_digest`, with the control F5 also needed: the
exclusion is the measurements directories only, and committed content is keyed by
blob sha rather than commit sha. A source edit, a new untracked file, or an edit
to any other file under ``docs/`` all still register as stale.

WHAT THIS CANNOT FORCE — a boundary, not a footnote
---------------------------------------------------
**The artifact does not prove the run happened.** Anyone with write access can
author a consistent JSON file by hand. `validate_artifact` raises the floor —
`bracket_closes` must agree with the digests it reports, `counts` must agree with
`result_tail`, and `exit_code` must agree with the failure count, so a careless
forgery fails — but a determined author who writes all four consistently is
indistinguishable from a real run. What the artifact buys is that a published
count now has a *specific, checkable, durable* record attached to a *named tree
state*, and that its ABSENCE is loud. Proving execution would need a recorder the
authoring agent cannot write, which this harness does not have.

Public surface::

    tree_digest(root)                        -> dict   (incl. `dirty`)
    is_release_label(label)                  -> bool
    parse_counts(text)                       -> dict | None
    summary_tail(text)                       -> str
    measure_suite(root, ...)                 -> dict
    validate_artifact(artifact)              -> list[str]
    artifact_counts(artifact)                -> dict | None
    parse_suite_claims(text)                 -> list[SuiteClaim]
    load_measurements(dirs)                  -> (list[dict], list[str])
    verify_measurement_claim(text, dirs)     -> dict

CLI::

    suite_measurement.py [<root>] [--label v3.60.0] [--out-dir docs/measurements]
                         [--command "python -m pytest -q"] [--json] [--no-write]
    suite_measurement.py --verify [<root>]        # gate a CHANGELOG-shaped text
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shlex
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, NamedTuple, Optional, Union

SCHEMA = "suite-measurement/v1"

#: The command a measurement runs unless told otherwise.
DEFAULT_COMMAND = "python -m pytest -q"

#: The DURABLE home. `.architect-team/` is gitignored — an artifact written there
#: dies with the working tree, which is the exact fate that forced the audit's
#: findings into `docs/proposals/WRONG_INSTRUMENT_FOLLOWUPS.md`. Evidence meant to
#: be checkable "later, by anyone" has to be committed.
DURABLE_OUT_DIR = "docs/measurements"

#: The runtime home (gitignored), kept because the v3.59.3 demo artifact lives
#: there and a run may legitimately measure without publishing.
RUNTIME_OUT_DIR = ".architect-team/measurements"

#: Search order for the claim gate: durable first.
MEASUREMENT_SEARCH_DIRS = (DURABLE_OUT_DIR, RUNTIME_OUT_DIR)

#: This tool's OWN output. Excluded from the source digest the currency check
#: compares, because writing and committing an artifact must not make that
#: artifact look stale. Narrow on purpose: the measurements directories only,
#: never all of `docs/` or all of `.architect-team/`.
MEASUREMENT_PATH_PREFIXES = (DURABLE_OUT_DIR + "/", RUNTIME_OUT_DIR + "/")

#: Every count this repo publishes carries this precondition. It rides in the
#: artifact so the number is never read as a property of the repo.
MACHINE_BOUND_CAVEAT = (
    "Machine-bound: five committed tests hard-require gitignored .architect-team/ "
    "fixtures and one skips without the local .architect-team-deploy.json, so a "
    "fresh clone does not reproduce this count. This figure describes THIS "
    "machine's checkout, not the repository."
)

#: The digest of a tree whose state could not be determined.
UNKNOWN_DIGEST = "unknown"

DIGEST_ALGORITHM = "sha256-16"

EXIT_OK = 0
EXIT_SUITE_RED = 1
EXIT_BRACKET_OPEN = 2
EXIT_PROVISIONAL = 3

_OUTCOME_KEYS = {
    "passed": "passed",
    "failed": "failed",
    "skipped": "skipped",
    "error": "errors",
    "errors": "errors",
    "xfailed": "xfailed",
    "xpassed": "xpassed",
}

# `7386 passed`, `5 failed`, `1 error`, `7,386 passed` — a count and its outcome.
_COUNT_RE = re.compile(
    r"(?<![\w.])(\d[\d,]*)\s+(passed|failed|skipped|errors?|xfailed|xpassed)\b"
)

# A published claim: `5646 -> 5689 passing + 4 skipped`, `5362 passing + 4 skipped`.
# Deliberately WIDER than changelog_check.SUITE_TOTAL_RE, which additionally
# demands a trailing "test files" — the live v3.59.3 entry omits it, and a claim
# is a claim regardless of whether it is formatted the house way.
_CLAIM_RE = re.compile(
    r"(?:(\d[\d,]*)\s*(?:->|→)\s*)?"
    r"(\d[\d,]*)\s+passing\s*\+\s*(\d[\d,]*)\s+skipped"
)

_LABEL_SAFE_RE = re.compile(r"[^A-Za-z0-9._-]+")

# A release label: `3.59.3`, `v3.59.3`, `V3.59.3`, `v3.59.3-rc1`.
#
# CASE-INSENSITIVE, and that is load-bearing rather than tidiness. The consumer
# side (`_label_matches_version`) has always accepted either case, so a
# case-SENSITIVE definition here let `V3.60.0` be the release to one predicate
# and not-a-release to the other — which smuggled a dirty tree through as the
# release. Two predicates over the same concept must not disagree; both now
# normalise through `_strip_version_prefix`.
_RELEASE_LABEL_RE = re.compile(r"v?\d+\.\d+\.\d+(?:[-.][A-Za-z0-9.-]+)?", re.IGNORECASE)


class SuiteClaim(NamedTuple):
    """A published suite count, as asserted in release-note text."""

    passed: int
    skipped: int
    text: str


# --------------------------------------------------------------------------- #
# tree state
# --------------------------------------------------------------------------- #
def _git(args: list[str], root: Path) -> tuple[int, str]:
    """Run a git command in `root`; return (returncode, stdout). Never raises."""
    try:
        proc = subprocess.run(
            ["git", "-C", str(root), *args],
            capture_output=True,
            text=True,
            errors="replace",
        )
    except (OSError, ValueError) as exc:  # git missing, bad path
        return 127, str(exc)
    return proc.returncode, proc.stdout


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", "surrogatepass")).hexdigest()


def _is_measurement_path(path: str) -> bool:
    """Is `path` this tool's own output rather than the subject it measures?"""
    p = path.replace("\\", "/").strip().lstrip("./")
    return any(p.startswith(prefix) for prefix in MEASUREMENT_PATH_PREFIXES)


def source_digest(root: Union[str, Path]) -> dict[str, Any]:
    """Identify the SOURCE the measurement describes, for the currency check.

    Distinct from `tree_digest`, and deliberately so — they answer different
    questions and a single digest cannot answer both:

    * `tree_digest` asks *did anything move while the suite ran*, so it hashes
      everything and is anchored to the commit sha.
    * this asks *is the artifact still about the code in front of me*, which must
      survive the two things the release sequence itself does: writing the
      artifact, and committing it.

    Hashing the whole tree made that check UNSATISFIABLE — writing the artifact
    changes the tree, so the recorded digest could never equal the current one,
    red before the commit and red after. Same defect as F5, where the completion
    lock's own notify state was hashed by the progress fingerprint and the
    no-progress budget could never exhaust. **Exclude your own bookkeeping from
    the state you hash.**

    Two exclusions, each doing one job:

    * measurement artifacts are dropped (the bookkeeping), and
    * committed content is identified by its BLOB SHAS via ``git ls-tree`` rather
      than by the commit sha, so committing the artifact — which changes HEAD but
      no source — leaves this digest unchanged.

    Nothing else is excluded: a source edit, a new untracked file, or a change to
    any other file under ``docs/`` all move it, so the exclusion cannot become a
    hole.
    """
    root = Path(root)
    rc_tree, _ = _git(["rev-parse", "--is-inside-work-tree"], root)
    if rc_tree != 0:
        return {
            "digest": UNKNOWN_DIGEST,
            "source": "unavailable",
            "detail": f"{root} is not inside a git work tree (or git is unavailable)",
        }

    rc_head, head_out = _git(["rev-parse", "HEAD"], root)
    head = head_out.strip() if rc_head == 0 else ""

    committed: list[str] = []
    if head:
        rc_ls, ls_out = _git(["ls-tree", "-r", "HEAD"], root)
        if rc_ls != 0:
            return {
                "digest": UNKNOWN_DIGEST,
                "source": "unavailable",
                "detail": f"git ls-tree rc={rc_ls}",
            }
        for line in ls_out.splitlines():
            if not line.strip():
                continue
            path = line.split("\t", 1)[-1]
            if not _is_measurement_path(path):
                committed.append(line)
        committed.sort()

    exclusions = [f":(exclude){prefix}*" for prefix in MEASUREMENT_PATH_PREFIXES]
    rc_diff, diff_out = _git(
        (["diff", "HEAD"] if head else ["diff"]) + ["--", "."] + exclusions, root
    )
    rc_status, status_out = _git(["status", "--porcelain", "--untracked-files=all"], root)
    if rc_diff != 0 or rc_status != 0:
        return {
            "digest": UNKNOWN_DIGEST,
            "source": "unavailable",
            "detail": f"git diff rc={rc_diff}, git status rc={rc_status}",
        }

    untracked = sorted(
        line[3:]
        for line in status_out.splitlines()
        if line.startswith("?? ") and not _is_measurement_path(line[3:])
    )
    composite = (
        f"committed={_sha(chr(10).join(committed))}\n"
        f"diff={_sha(diff_out)}\n"
        f"untracked={_sha(chr(10).join(untracked))}"
    )
    return {"digest": _sha(composite)[:16], "source": "git", "detail": ""}


def tree_digest(root: Union[str, Path]) -> dict[str, Any]:
    """Digest the working tree's state.

    Returns ``{"digest", "head", "source", "components", "detail"}``. ``source``
    is ``"git"`` when the state was determined and ``"unavailable"`` when it was
    not — in which case ``digest`` is `UNKNOWN_DIGEST` and callers must NOT treat
    two of them as a closed bracket.
    """
    root = Path(root)
    rc_tree, _ = _git(["rev-parse", "--is-inside-work-tree"], root)
    if rc_tree != 0:
        return {
            "digest": UNKNOWN_DIGEST,
            "head": None,
            "source": "unavailable",
            "dirty": None,
            "components": {},
            "detail": f"{root} is not inside a git work tree (or git is unavailable)",
        }

    rc_head, head_out = _git(["rev-parse", "HEAD"], root)
    head = head_out.strip() if rc_head == 0 else ""

    diff_args = ["diff", "HEAD"] if head else ["diff"]
    rc_diff, diff_out = _git(diff_args, root)
    rc_status, status_out = _git(["status", "--porcelain", "--untracked-files=all"], root)
    if rc_diff != 0 or rc_status != 0:
        return {
            "digest": UNKNOWN_DIGEST,
            "head": head or None,
            "source": "unavailable",
            "dirty": None,
            "components": {},
            "detail": f"git diff rc={rc_diff}, git status rc={rc_status}",
        }

    untracked = sorted(
        line[3:] for line in status_out.splitlines() if line.startswith("?? ")
    )
    # `head` names a COMMIT; it does not name the tree that was measured. A dirty
    # tree at commit X is a different tree from commit X, and conflating them is
    # how a release-labelled artifact comes to describe something that is not the
    # release. Dirtiness is therefore recorded as its own fact.
    dirty = bool(diff_out.strip()) or bool(untracked)
    components = {
        "head": head or "no-head",
        "diff_sha256": _sha(diff_out),
        "untracked_sha256": _sha("\n".join(untracked)),
        "untracked_count": len(untracked),
    }
    composite = (
        f"head={components['head']}\n"
        f"diff={components['diff_sha256']}\n"
        f"untracked={components['untracked_sha256']}"
    )
    return {
        "digest": _sha(composite)[:16],
        "head": head or None,
        "source": "git",
        "dirty": dirty,
        "components": components,
        "detail": (
            f"{len(untracked)} untracked path(s); tracked diff "
            f"{'present' if diff_out.strip() else 'empty'}"
            if dirty else ""
        ),
    }


# --------------------------------------------------------------------------- #
# pytest output parsing (RECORDED, never used to decide green)
# --------------------------------------------------------------------------- #
def _summary_line(text: str) -> Optional[str]:
    """The LAST line carrying a pytest outcome count, or None."""
    for line in reversed((text or "").splitlines()):
        if _COUNT_RE.search(line):
            return line.strip().strip("=").strip()
    return None


def summary_tail(text: str) -> str:
    """The pytest summary line, de-padded; empty string when there is none."""
    return _summary_line(text) or ""


def parse_counts(text: str) -> Optional[dict[str, int]]:
    """Parse the pytest summary into outcome counts, or None when absent.

    Missing outcomes default to 0 for the three that always matter (passed /
    failed / skipped) so a consumer never has to distinguish "absent" from
    "zero" for them. A line with no outcome count at all ("no tests ran") yields
    None — an unparseable run records nothing rather than inventing zeros.
    """
    line = _summary_line(text)
    if line is None:
        return None
    counts = {"passed": 0, "failed": 0, "skipped": 0}
    for raw, word in _COUNT_RE.findall(line):
        key = _OUTCOME_KEYS.get(word)
        if key:
            counts[key] = int(raw.replace(",", ""))
    return counts


# --------------------------------------------------------------------------- #
# the measurement
# --------------------------------------------------------------------------- #
def default_runner(command: Union[str, list[str]], cwd: Path) -> tuple[int, str]:
    """Run `command` in `cwd`; return (exit_code, combined stdout+stderr)."""
    args = command if isinstance(command, list) else shlex.split(command)
    proc = subprocess.run(
        args, cwd=str(cwd), capture_output=True, text=True, errors="replace"
    )
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def _safe_label(label: Optional[str]) -> str:
    cleaned = _LABEL_SAFE_RE.sub("-", (label or "unlabelled").strip()).strip("-")
    return cleaned or "unlabelled"


def _strip_version_prefix(value: Any) -> str:
    """Drop ONE leading `v`/`V` from a version-ish string.

    A single prefix, not `lstrip("vV")` — that is a character-SET strip, so it
    would eat every leading v and read `vvv3.60.0` as `3.60.0`.
    """
    text = str(value or "").strip()
    return text[1:] if text[:1] in ("v", "V") else text


def is_release_label(label: Any) -> bool:
    """Does `label` name a RELEASE (``v3.59.3`` / ``3.59.3`` / ``v3.59.3-rc1``)?

    A release label is a claim about a tree that is identified by its version —
    the tree someone will later check out. Any other label ("wip", "nightly",
    "scratch") claims nothing of the sort, so it carries no such obligation.
    """
    return bool(_RELEASE_LABEL_RE.fullmatch(str(label or "").strip()))


def measure_suite(
    root: Union[str, Path],
    *,
    command: Union[str, list[str]] = DEFAULT_COMMAND,
    label: Optional[str] = None,
    out_dir: Union[str, Path, None] = None,
    runner: Any = None,
    now: Optional[str] = None,
    write: bool = True,
) -> dict[str, Any]:
    """Bracket a suite run and record it.

    `runner` is injected so a test never runs the real suite; it is called as
    ``runner(command, cwd) -> (exit_code, output_text)``.
    """
    root = Path(root)
    runner = runner or default_runner
    command_text = command if isinstance(command, str) else " ".join(command)
    stamp = now or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    before = tree_digest(root)
    before_source = source_digest(root)
    exit_code, output = runner(command, root)
    after = tree_digest(root)

    unavailable = UNKNOWN_DIGEST in (before["digest"], after["digest"])
    bracket_closes = (not unavailable) and before["digest"] == after["digest"]
    suite_green = exit_code == 0

    # LABEL-TO-TREE BINDING. The measurement describes the tree it RAN against,
    # which is the `before` tree. A release label asserts "this is the count for
    # version X" — false if the tree carried uncommitted work, because that tree
    # is not the one anyone will check out. Left unbound, such an artifact makes
    # the gate contradict a CORRECT published count, which is the most expensive
    # failure mode available: it teaches the reader to disbelieve the gate.
    safe_label = _safe_label(label)
    tree_dirty = before.get("dirty")
    provisional = bool(is_release_label(safe_label) and tree_dirty)

    counts = parse_counts(output)
    violations: list[str] = []
    if provisional:
        violations.append(
            f"label {safe_label!r} names a release but the tree carried "
            f"uncommitted work ({before.get('detail') or 'dirty'}): this measures "
            f"HEAD-plus-changes, not the release. Recorded as PROVISIONAL — it "
            f"backs no published count. Measure a clean checkout to label a release."
        )
    if unavailable:
        violations.append(
            "tree state is UNKNOWN "
            f"({before.get('detail') or after.get('detail')}): an unknown tree "
            "state is not a closed bracket"
        )
    elif not bracket_closes:
        violations.append(
            f"the bracket does not close ({before['digest']} -> {after['digest']}): "
            "the tree changed while the suite ran, so this count is about no "
            "particular tree state"
        )
    if not suite_green:
        violations.append(f"the suite exited {exit_code}: this measures a RED suite")

    if unavailable:
        verdict = "tree-state-unavailable"
    elif not bracket_closes:
        verdict = "bracket-open"
    elif provisional:
        verdict = "provisional-release-label"
    elif not suite_green:
        verdict = "suite-red"
    else:
        verdict = "measured-clean"

    # A mislabelled measurement is a measurement-INTEGRITY failure, like an open
    # bracket, so it outranks the subject's own red/green.
    if not bracket_closes:
        exit_status = EXIT_BRACKET_OPEN
    elif provisional:
        exit_status = EXIT_PROVISIONAL
    elif not suite_green:
        exit_status = EXIT_SUITE_RED
    else:
        exit_status = EXIT_OK

    artifact: dict[str, Any] = {
        "schema": SCHEMA,
        "label": safe_label,
        "release_label": is_release_label(safe_label),
        "tree_dirty": tree_dirty,
        "provisional": provisional,
        "timestamp": stamp,
        # Absolute, because the count is machine-bound and the artifact should
        # name the machine it describes rather than a relative cwd.
        "repo_root": str(root.resolve()),
        "command": command_text,
        "exit_code": exit_code,
        "provenance": "measured",
        "digest_algorithm": DIGEST_ALGORITHM,
        # The caveat below is about the environment, so record the part of it
        # that is cheap and that this repo is known to vary across (the suite is
        # measured under both the default codepage and PYTHONUTF8=1).
        "environment": {
            "python": sys.version.split()[0],
            "platform": sys.platform,
            "PYTHONUTF8": os.environ.get("PYTHONUTF8"),
        },
        "tree_state": {
            "before": before["digest"],
            "after": after["digest"],
            "head": before.get("head"),
            # The identity the currency check compares — see `source_digest`.
            "source_digest": before_source["digest"],
            "source": before["source"] if before["source"] == after["source"] else "mixed",
            "components_before": before.get("components", {}),
            "components_after": after.get("components", {}),
        },
        "bracket_closes": bracket_closes,
        "suite_green": suite_green,
        "counts": counts or {},
        "counts_parsed": counts is not None,
        "result_tail": summary_tail(output),
        "machine_bound": MACHINE_BOUND_CAVEAT,
        "verdict": verdict,
        "violations": violations,
    }

    artifact_path: Optional[str] = None
    if write:
        target_dir = Path(out_dir) if out_dir is not None else root / DURABLE_OUT_DIR
        target_dir.mkdir(parents=True, exist_ok=True)
        name = f"{stamp[:10]}-{artifact['label']}-suite.json"
        path = target_dir / name
        path.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        artifact_path = str(path)

    result = dict(artifact)
    result["ok"] = bracket_closes and not provisional
    result["exit_status"] = exit_status
    result["artifact_path"] = artifact_path
    return result


# --------------------------------------------------------------------------- #
# artifact validation — raises the floor under forgery; does not close it
# --------------------------------------------------------------------------- #
def artifact_counts(artifact: Any) -> Optional[dict[str, int]]:
    """The artifact's counts: the `counts` block, else parsed from `result_tail`."""
    if not isinstance(artifact, dict):
        return None
    counts = artifact.get("counts")
    if isinstance(counts, dict) and counts:
        out = {"passed": 0, "failed": 0, "skipped": 0}
        for key, value in counts.items():
            if isinstance(value, bool) or not isinstance(value, int):
                return None
            out[str(key)] = value
        return out
    return parse_counts(str(artifact.get("result_tail") or ""))


def validate_artifact(artifact: Any) -> list[str]:
    """Internal-consistency findings for one artifact (empty list == consistent).

    Checks only what the record can contradict about ITSELF. A record that
    disagrees with itself was not produced by a run; a record that agrees with
    itself may still have been typed by hand, which is the named boundary.
    """
    if not isinstance(artifact, dict):
        return ["artifact is not a JSON object"]

    findings: list[str] = []

    provenance = artifact.get("provenance")
    if provenance != "measured":
        findings.append(
            f"provenance is {provenance!r}, not 'measured' — this is an artifact "
            f"shape, not a record written by a measurement run"
        )

    if artifact.get("provisional") is True:
        findings.append(
            "the measurement is PROVISIONAL: its label names a release but it ran "
            "against a dirty tree, so it describes HEAD-plus-changes rather than "
            "the release and backs no published count"
        )
    elif artifact.get("tree_dirty") is True:
        # Independent of the label. `provisional` alone left the RELEASE-TIME gate
        # weaker than the in-suite one — `find_release_artifacts` checked both, so
        # a dirty measurement the suite rejected was accepted by
        # `--require-measurements`, which is the release check. A published count
        # describes a committed tree whatever the artifact chose to call itself.
        findings.append(
            "the measurement ran against a DIRTY tree, so it describes "
            "HEAD-plus-uncommitted-changes and backs no published count, "
            "whatever its label says"
        )

    for field in ("command", "tree_state", "bracket_closes"):
        if field not in artifact:
            findings.append(f"required field {field!r} is missing")

    tree_state = artifact.get("tree_state")
    tree_state = tree_state if isinstance(tree_state, dict) else {}
    before = str(tree_state.get("before") or "").strip()
    after = str(tree_state.get("after") or "").strip()
    closes = artifact.get("bracket_closes")

    if not before or not after:
        findings.append("no tree_state bracket is recorded")
    else:
        really_closes = before == after and before != UNKNOWN_DIGEST
        if closes is not True:
            findings.append(
                f"bracket_closes is {closes!r}: the bracket does not close "
                f"({before} -> {after})"
            )
        elif not really_closes:
            findings.append(
                f"bracket_closes says true but the recorded digests contradict it "
                f"({before} -> {after})"
            )

    counts = artifact_counts(artifact)
    if counts is None:
        findings.append("no usable counts (neither a counts block nor a parseable result_tail)")
    else:
        tail_counts = parse_counts(str(artifact.get("result_tail") or ""))
        if (
            isinstance(artifact.get("counts"), dict)
            and artifact["counts"]
            and tail_counts is not None
        ):
            for key in ("passed", "failed", "skipped"):
                if counts.get(key, 0) != tail_counts.get(key, 0):
                    findings.append(
                        f"counts.{key}={counts.get(key)} contradicts result_tail "
                        f"({tail_counts.get(key)}): {artifact.get('result_tail')!r}"
                    )
        exit_code = artifact.get("exit_code")
        if isinstance(exit_code, int) and not isinstance(exit_code, bool):
            failed = counts.get("failed", 0) + counts.get("errors", 0)
            if exit_code == 0 and failed > 0:
                findings.append(
                    f"exit_code 0 contradicts {failed} recorded failure(s) — pytest "
                    f"does not exit 0 with failures"
                )
            if exit_code != 0 and failed == 0 and artifact.get("suite_green") is True:
                findings.append(
                    f"exit_code {exit_code} contradicts suite_green=true"
                )

    return findings


def _artifact_is_green(artifact: dict[str, Any]) -> bool:
    exit_code = artifact.get("exit_code")
    counts = artifact_counts(artifact) or {}
    if isinstance(exit_code, int) and not isinstance(exit_code, bool) and exit_code != 0:
        return False
    return counts.get("failed", 0) == 0 and counts.get("errors", 0) == 0


# --------------------------------------------------------------------------- #
# the claim side
# --------------------------------------------------------------------------- #
def parse_suite_claims(text: str) -> list[SuiteClaim]:
    """Every distinct published suite count in `text`.

    The arrow form (`7024 -> 7222 passing`) claims the SECOND number; the first
    is a historical reference to a prior release and is not re-litigated here.
    """
    seen: set[tuple[int, int]] = set()
    claims: list[SuiteClaim] = []
    for match in _CLAIM_RE.finditer(text or ""):
        passed = int(match.group(2).replace(",", ""))
        skipped = int(match.group(3).replace(",", ""))
        key = (passed, skipped)
        if key in seen:
            continue
        seen.add(key)
        claims.append(SuiteClaim(passed, skipped, match.group(0)))
    return claims


def load_measurements(
    dirs: Union[str, Path, Iterable[Union[str, Path]]]
) -> tuple[list[dict[str, Any]], list[str]]:
    """Load every `*.json` under `dirs`. Returns (artifacts, read_failures).

    A file that cannot be read is a READ FAILURE reported by name, never a
    silently skipped file — an unreadable source is unknown state, not absence.
    """
    if isinstance(dirs, (str, Path)):
        dirs = [dirs]
    artifacts: list[dict[str, Any]] = []
    failures: list[str] = []
    for directory in dirs:
        d = Path(directory)
        if not d.is_dir():
            continue
        for path in sorted(d.glob("*.json")):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError, UnicodeDecodeError) as exc:
                failures.append(f"{path.name}: unreadable measurement artifact ({exc})")
                continue
            if not isinstance(data, dict):
                failures.append(f"{path.name}: measurement artifact is not a JSON object")
                continue
            data = dict(data)
            data["_path"] = str(path)
            artifacts.append(data)
    return artifacts, failures


def _label_matches_version(label: Any, version: str) -> bool:
    """Does an artifact `label` name this release version?  ("v3.60.0" ~ "3.60.0")

    Shares `_strip_version_prefix` with `is_release_label` so the two predicates
    cannot drift apart again — their disagreement was the smuggle.
    """
    text = _strip_version_prefix(label)
    target = _strip_version_prefix(version)
    return bool(target) and (text == target or text.startswith(target + "-"))


def find_release_artifacts(
    measurements_dir: Union[str, Path, Iterable[Union[str, Path]]],
    version: str,
) -> tuple[list[dict[str, Any]], list[str]]:
    """Artifacts recorded FOR `version` with a closed bracket, plus reject reasons.

    Deliberately does NOT compare counts or require a green suite — see
    `verify_measurement_claim`'s docstring for why that check cannot live inside
    the suite it measures. This is the convergent half: it answers "was a
    measurement recorded for this release at all", which is the reported defect.
    """
    artifacts, failures = load_measurements(measurements_dir)
    matching: list[dict[str, Any]] = []
    reasons: list[str] = list(failures)
    for artifact in artifacts:
        name = Path(str(artifact.get("_path", "?"))).name
        if not _label_matches_version(artifact.get("label") or artifact.get("release"), version):
            continue
        if artifact.get("provenance") != "measured":
            # Not a measurement at all — a shape. It counts toward "nothing was
            # measured", never toward "a measurement exists but is unusable";
            # conflating the two would let a local scratch file wedge the gate.
            continue
        if artifact.get("provisional") is True or artifact.get("tree_dirty") is True:
            reasons.append(
                f"{name}: PROVISIONAL — labelled for a release but measured on a "
                f"dirty tree, so it does not describe the release"
            )
            continue
        tree_state = artifact.get("tree_state")
        tree_state = tree_state if isinstance(tree_state, dict) else {}
        before = str(tree_state.get("before") or "").strip()
        after = str(tree_state.get("after") or "").strip()
        if artifact.get("bracket_closes") is not True or not before or before != after \
                or before == UNKNOWN_DIGEST:
            reasons.append(f"{name}: the bracket does not close ({before or '?'} -> {after or '?'})")
            continue
        matching.append(artifact)
    return matching, reasons


def measurement_is_current(artifact: Any, root: Union[str, Path]) -> tuple[Optional[bool], str]:
    """Does `artifact` describe the tree at `root` RIGHT NOW?

    Returns ``(verdict, detail)`` where verdict is True / False / None (the
    current tree state could not be determined, so currency is undecidable and
    must be reported rather than assumed either way).

    A genuine measurement of a tree that has since moved is still an honest
    record — it is only misleading when cited for the tree being committed. That
    makes this a RELEASE-TIME check: mid-development the tree moves constantly
    and this would be red permanently, which is how gates get deleted.
    """
    if not isinstance(artifact, dict):
        return None, "artifact is not a JSON object"
    tree_state = artifact.get("tree_state")
    tree_state = tree_state if isinstance(tree_state, dict) else {}
    # The SOURCE digest, never the whole-tree one: comparing the whole tree makes
    # this check unsatisfiable, because writing the artifact changes the tree.
    recorded = str(tree_state.get("source_digest") or "").strip()
    if not recorded or recorded == UNKNOWN_DIGEST:
        return None, "the artifact records no source digest, so currency cannot be decided"
    current = source_digest(root)
    if current["source"] != "git":
        return None, f"the current tree state is undeterminable ({current['detail']})"
    if current["digest"] == recorded:
        return True, current["digest"]
    return False, f"measured against source {recorded}, but the source is now {current['digest']}"


def verify_measurement_claim(
    text: str,
    measurements_dir: Union[str, Path, Iterable[Union[str, Path]]],
) -> dict[str, Any]:
    """Require every suite count claimed in `text` to have a backing measurement.

    An artifact backs a claim only when it is internally consistent
    (`validate_artifact` clean, which includes a closed bracket and
    `provenance == "measured"`), records a GREEN run, and its counts equal the
    claimed ones.
    """
    artifacts, failures = load_measurements(measurements_dir)
    findings: list[str] = list(failures)
    claims_out: list[dict[str, Any]] = []

    for claim in parse_suite_claims(text):
        backed_by: Optional[str] = None
        reasons: list[str] = []
        for artifact in artifacts:
            name = Path(str(artifact.get("_path", "?"))).name
            counts = artifact_counts(artifact) or {}
            if (
                counts.get("passed") != claim.passed
                or counts.get("skipped") != claim.skipped
            ):
                reasons.append(
                    f"{name}: records {counts.get('passed')} passed / "
                    f"{counts.get('skipped')} skipped"
                )
                continue
            problems = validate_artifact(artifact)
            if problems:
                reasons.append(f"{name}: {problems[0]}")
                continue
            if not _artifact_is_green(artifact):
                reasons.append(f"{name}: measures a RED suite, so it backs no green count")
                continue
            backed_by = str(artifact.get("_path"))
            break

        claims_out.append(
            {
                "passed": claim.passed,
                "skipped": claim.skipped,
                "text": claim.text,
                "backed": backed_by is not None,
                "artifact": backed_by,
                "reasons": reasons,
            }
        )
        if backed_by is None:
            detail = "; ".join(reasons[:3]) if reasons else "no measurement artifacts found"
            findings.append(
                f"the claim '{claim.passed} passing + {claim.skipped} skipped' has no "
                f"recorded bracket artifact backing it ({detail}). Run: python "
                f"scripts/measure/suite_measurement.py --label v<version> "
                f"--out-dir {DURABLE_OUT_DIR}"
            )

    return {
        "ok": not findings,
        "findings": findings,
        "claims": claims_out,
        "artifacts_seen": len(artifacts),
    }


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def main(argv: Optional[list[str]] = None) -> int:
    """CLI: make a bracketed measurement, or verify a text's claims against them."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Make (or verify) a hash-bracketed suite measurement."
    )
    parser.add_argument("root", nargs="?", default=".", help="repo root (default: cwd)")
    parser.add_argument("--label", default=None, help="artifact label, e.g. v3.60.0")
    parser.add_argument("--command", default=DEFAULT_COMMAND, help="suite command to run")
    parser.add_argument("--out-dir", default=None, help=f"default: <root>/{DURABLE_OUT_DIR}")
    parser.add_argument("--no-write", action="store_true", help="measure without writing")
    parser.add_argument("--json", action="store_true", help="emit the full JSON result")
    parser.add_argument(
        "--verify",
        metavar="FILE",
        nargs="?",
        const="CHANGELOG.md",
        help="verify the suite claims in FILE (default CHANGELOG.md) instead of measuring",
    )
    args = parser.parse_args(argv)
    root = Path(args.root)

    if args.verify:
        text = (root / args.verify).read_text(encoding="utf-8")
        result = verify_measurement_claim(
            text, [root / d for d in MEASUREMENT_SEARCH_DIRS]
        )
        if args.json:
            print(json.dumps(result, indent=2, sort_keys=True))
        elif result["ok"]:
            print(
                f"suite-measurement: {len(result['claims'])} claim(s) backed by "
                f"{result['artifacts_seen']} artifact(s)."
            )
        else:
            print("suite-measurement: unbacked claims —")
            for finding in result["findings"]:
                print(f"  - {finding}")
        return 0 if result["ok"] else 1

    result = measure_suite(
        root,
        command=args.command,
        label=args.label,
        out_dir=args.out_dir,
        write=not args.no_write,
    )
    if args.json:
        printable = {k: v for k, v in result.items() if not k.startswith("_")}
        print(json.dumps(printable, indent=2, sort_keys=True))
    else:
        print(f"suite-measurement: {result['verdict']} — {result['result_tail'] or '(no summary)'}")
        print(
            f"  bracket {result['tree_state']['before']} -> "
            f"{result['tree_state']['after']} "
            f"({'CLOSED' if result['bracket_closes'] else 'OPEN'})"
        )
        for violation in result["violations"]:
            print(f"  - {violation}")
        if result["artifact_path"]:
            print(f"  artifact: {result['artifact_path']}")
    return int(result["exit_status"])


if __name__ == "__main__":
    raise SystemExit(main())
