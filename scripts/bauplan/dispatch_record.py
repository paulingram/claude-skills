#!/usr/bin/env python3
"""dispatch_record.py — the run-state record of what the Bauplan arming actually did.

AC3 of the bauplan-skills-dependency change binds the behavioral claim ("an armed
run dispatches at least one `bauplan-*` skill") to a durable artifact rather than
to a hook. `hooks/skill_invocation_audit.py` builds its expectations from CT6's
OWN canonical commands, so a third-party skill dispatch would never appear in its
verdict JSON; extending that hook to prove a Bauplan behavior would put an
unrelated capability's evidence needs on the Stop path of every session. The lane
already writes run state, so the record lives there instead (design.md D6).

The file is a JSON object at::

    <workspace>/.architect-team/<lane>/<slug>/bauplan-dispatches.json

carrying three independently-meaningful lists:

  * ``dispatches``          — one entry per `bauplan-*` skill actually dispatched.
  * ``missed_capabilities`` — the warn-and-degrade record: the project was
    Bauplan-shaped but the plugin was absent, so the run proceeded generically.
    Carries the remediation lines, because a degraded run that does not say what
    it degraded FROM is indistinguishable from a correctly-scoped one.
  * ``precedence_conflicts`` — where a Bauplan platform rule governed over a CT6
    default on a lakehouse operation. The augment-never-replace discipline
    requires the conflict be RECORDED, not merely resolved.

Determinism: nothing here reads the wall clock, the environment, or the network.
Every timestamp is supplied by the caller, so a test asserts exact bytes and a
resumed run records the same thing twice rather than drifting. Stdlib only, no
import-time side effects.
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any, Iterable, Optional, Union

PathLike = Union[str, "os.PathLike[str]"]

RECORD_NAME = "bauplan-dispatches.json"

#: Lanes that may record Bauplan dispatches. `data-eng` is the primary consumer;
#: `bug-fix` reaches `bauplan-debug-and-fix-pipeline` from its replicate/diagnose
#: phases. An unknown lane is rejected rather than silently creating a stray
#: directory, so a typo surfaces instead of scattering evidence the gate cannot find.
KNOWN_LANES = ("data-eng", "bug-fix")

_EMPTY: dict[str, list[Any]] = {
    "dispatches": [],
    "missed_capabilities": [],
    "precedence_conflicts": [],
}


def record_path(workspace: PathLike, slug: str, lane: str = "data-eng") -> Path:
    """Resolve the record's path for a lane + run slug. Creates nothing."""
    if lane not in KNOWN_LANES:
        raise ValueError(f"unknown lane {lane!r}: expected one of {KNOWN_LANES}")
    if not slug or "/" in slug or "\\" in slug or slug in (".", ".."):
        raise ValueError(f"invalid run slug {slug!r}")
    return Path(workspace) / ".architect-team" / lane / slug / RECORD_NAME


def read_record(workspace: PathLike, slug: str, lane: str = "data-eng") -> dict[str, list[Any]]:
    """Return the record, or the empty shape when no run has written one yet.

    A malformed or unreadable file yields the empty shape too: this is evidence
    ABOUT a run, never a gate on it, so a corrupt record must not crash the lane
    that is trying to append to it.
    """
    path = record_path(workspace, slug, lane)
    try:
        data = json.loads(path.read_bytes().decode("utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return {k: list(v) for k, v in _EMPTY.items()}
    if not isinstance(data, dict):
        return {k: list(v) for k, v in _EMPTY.items()}
    out = {k: list(v) for k, v in _EMPTY.items()}
    for key in out:
        value = data.get(key)
        if isinstance(value, list):
            out[key] = value
    return out


def _write(path: Path, payload: dict[str, Any]) -> None:
    """Atomic write (tmp in the same dir + os.replace), UTF-8, trailing newline."""
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), prefix=path.name + ".", suffix=".ct6tmp")
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(text.encode("utf-8"))
        os.replace(tmp_name, str(path))
    except BaseException:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def record_dispatch(
    workspace: PathLike,
    slug: str,
    *,
    skill: str,
    phase: str,
    teammate: str,
    ts: str,
    lane: str = "data-eng",
    detail: Optional[str] = None,
) -> dict[str, Any]:
    """Append one `bauplan-*` dispatch and return the entry written.

    `skill` must name a bauplan skill: the record exists to evidence THIS
    capability, and admitting arbitrary skill names would let an unrelated
    dispatch satisfy AC3's "at least one bauplan-* dispatch" check.
    """
    if not skill.startswith("bauplan-"):
        raise ValueError(f"not a bauplan skill: {skill!r}")
    entry: dict[str, Any] = {
        "skill": skill,
        "phase": phase,
        "teammate": teammate,
        "ts": ts,
    }
    if detail:
        entry["detail"] = detail
    record = read_record(workspace, slug, lane)
    record["dispatches"].append(entry)
    _write(record_path(workspace, slug, lane), record)
    return entry


def record_missed_capability(
    workspace: PathLike,
    slug: str,
    *,
    capability: str,
    remediation: Iterable[str],
    ts: str,
    lane: str = "data-eng",
    reason: str = "project is Bauplan-shaped but the plugin is not installed",
) -> dict[str, Any]:
    """Append the warn-and-degrade record.

    `remediation` is required and must be non-empty — naming the miss without
    naming the fix leaves the reader knowing something was lost and not how to
    recover it, which is the failure this record exists to prevent.
    """
    lines = [str(line) for line in remediation if str(line).strip()]
    if not lines:
        raise ValueError("remediation lines are required when recording a missed capability")
    entry = {
        "capability": capability,
        "reason": reason,
        "remediation": lines,
        "ts": ts,
    }
    record = read_record(workspace, slug, lane)
    record["missed_capabilities"].append(entry)
    _write(record_path(workspace, slug, lane), record)
    return entry


def record_precedence_conflict(
    workspace: PathLike,
    slug: str,
    *,
    operation: str,
    bauplan_rule: str,
    ct6_default: str,
    resolution: str,
    ts: str,
    lane: str = "data-eng",
) -> dict[str, Any]:
    """Append a conflict where the Bauplan platform rule governed.

    The augment-never-replace discipline lets the platform's own safety rules win
    on the platform's own operations — but only WITH the conflict recorded, so a
    silently-overridden CT6 default is never indistinguishable from one that
    never applied.
    """
    entry = {
        "operation": operation,
        "bauplan_rule": bauplan_rule,
        "ct6_default": ct6_default,
        "resolution": resolution,
        "ts": ts,
    }
    record = read_record(workspace, slug, lane)
    record["precedence_conflicts"].append(entry)
    _write(record_path(workspace, slug, lane), record)
    return entry


def dispatched_skills(workspace: PathLike, slug: str, lane: str = "data-eng") -> list[str]:
    """The distinct `bauplan-*` skills this run dispatched, in first-seen order."""
    seen: list[str] = []
    for entry in read_record(workspace, slug, lane)["dispatches"]:
        if isinstance(entry, dict):
            skill = entry.get("skill")
            if isinstance(skill, str) and skill not in seen:
                seen.append(skill)
    return seen


def summarize(workspace: PathLike, slug: str, lane: str = "data-eng") -> dict[str, Any]:
    """A compact summary for the run report / AC3-AC4 assertions."""
    record = read_record(workspace, slug, lane)
    return {
        "dispatch_count": len(record["dispatches"]),
        "skills": dispatched_skills(workspace, slug, lane),
        "missed_capability_count": len(record["missed_capabilities"]),
        "precedence_conflict_count": len(record["precedence_conflicts"]),
    }
