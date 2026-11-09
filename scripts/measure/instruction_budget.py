# -*- coding: utf-8 -*-
"""Deterministic instruction-budget measurement (proposal change 8).

Stdlib-only, no import-time side effects, ASCII-only source. Mirrors the engine
shape of ``scripts/measure/suite_measurement.py`` and
``scripts/compliance/instruction_compliance.py``: importable pure functions, a
dict-returning ``measure``, a ``--json`` CLI, and no work performed at import.

WHY THIS EXISTS
---------------
The proposal (``docs/proposals/CT6_MODERNIZATION_PLAN.html``, change 8) names
the instrument the referencing mandate is judged by: *tokens loaded per lane
start and per agent dispatch, recorded under docs/measurements/ and gated like
the suite bracket*. Before this module the only numbers were estimates read off
a transcript ("Lead, before Phase -2: 141K"). This module makes the number, so a
regression in instruction weight becomes visible the same way a regression in
the suite count does: as a recorded artifact a release can be checked against.

THE ESTIMATOR, STATED
---------------------
``tokens = ceil(utf8_bytes / 4)`` -- the ``bytes/4`` yardstick. It is NOT a
tokenizer; English prose tokenizes near 4 bytes per token, code and markdown
tables somewhat denser. Every surface is measured with the same stick, so
ratios and regressions are meaningful even where the absolute number is a
rough one. The artifact records the estimator by name so a later switch to a
real tokenizer cannot be confused with a change in the corpus.

WHAT IS MEASURED (the per-surface table)
----------------------------------------
* every ``commands/*.md``            (class ``command``)
* every ``skills/*/SKILL.md``        (class ``skill``)
* every ``skills/*/references/*.md`` (class ``chapter``; ``INDEX.md`` flagged)
* every ``agents/*.md``              (class ``agent``)

each with bytes, lines, tokens, and the tokens of its frontmatter
``description`` (the part Claude Code loads into EVERY session). Agents also
record the ``skills:`` frontmatter list when present.

THE AGGREGATES
--------------
* **lane start load** -- what the Lead holds before the first phase of a lane:
  the lane command + the lane skill's ``SKILL.md`` +
  ``skills/common-pipeline-conventions/SKILL.md``; for ``architect-team`` also
  the three skills its body invokes at start (``team-spawning-and-review-gates``,
  ``verified-agent-output``, ``intake-and-mapping``). The rule is deliberately a
  fixed, documented component list (``LANES``), not a parse of the lane prose:
  a measurement whose components move with the wording cannot be compared
  across releases. A missing component is recorded by name with 0 tokens.
* **always-loaded** -- the sum of frontmatter ``description`` tokens across
  every skill, agent and command: the text Claude Code carries into every
  session whether or not CT6 is invoked.
* **per-agent dispatch load** -- the agent file's tokens plus the ``SKILL.md``
  tokens of every skill named in its ``skills:`` frontmatter (0 extra when the
  field is absent, which is the whole corpus today).

THE BUDGETS
-----------
``BUDGETS``: a ``SKILL.md`` <= 500 lines; any single ``SKILL.md`` or reference
chapter <= 5,000 tokens; an agent <= 2,000 tokens; a lane start load <= 25,000
tokens; always-loaded <= 8,000 tokens. ``--check`` exits 1 and lists every
breach; whether a breach GATES anything is the caller's decision (the proposal
leaves gating to ``changelog_check.py``), which is why this module only
reports.

THE ARTIFACT
------------
``--write`` records ``docs/measurements/<date>-<label>-instruction-budget.json``
with schema ``instruction-budget/v1``, the repo HEAD, the tree-dirty flag
(``suite_measurement.tree_digest`` when importable, a local ``git`` fallback
otherwise), ``provenance: "measured"``, the totals, the breaches and the
per-surface table. A release-shaped label on a dirty tree is recorded
``provisional`` -- the same label-to-tree binding the suite bracket applies,
for the same reason: a count is a property of a tree, not of the commit it
descends from.
"""
from __future__ import annotations

import json
import math
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional, Union

SCHEMA = "instruction-budget/v1"
TOKEN_ESTIMATOR = "bytes/4"
DURABLE_OUT_DIR = "docs/measurements"
ARTIFACT_SUFFIX = "instruction-budget"

BUDGETS: dict[str, int] = {
    "skill_md_max_lines": 500,
    "chapter_max_tokens": 5000,
    "agent_max_tokens": 2000,
    "lane_start_max_tokens": 25000,
    "always_loaded_max_tokens": 8000,
}

CONVENTIONS_SKILL = "common-pipeline-conventions"

# Lane command -> the skill it drives, plus the skills the lane's body invokes
# at START (the fixed component list documented in the module docstring).
LANES: dict[str, dict[str, Any]] = {
    "architect-team": {
        "skill": "architect-team-pipeline",
        "start_skills": ("team-spawning-and-review-gates", "verified-agent-output", "intake-and-mapping"),
    },
    "bug-fix": {"skill": "bug-fix-pipeline", "start_skills": ()},
    "mini": {"skill": "mini-architect-team-pipeline", "start_skills": ()},
    "data-eng": {"skill": "data-eng-pipeline", "start_skills": ()},
    "ux-test": {"skill": "ux-test-builder", "start_skills": ()},
    "playwright-suite": {"skill": "playwright-suite-builder", "start_skills": ()},
}

EXIT_OK = 0
EXIT_BREACH = 1

_RE_RELEASE_LABEL = re.compile(r"^v?\d+\.\d+\.\d+(?:[-.][A-Za-z0-9.-]+)?$")
_RE_LABEL_SAFE = re.compile(r"[^A-Za-z0-9._-]+")


# --------------------------------------------------------------------------- #
# the estimator
# --------------------------------------------------------------------------- #
def estimate_tokens(nbytes: int) -> int:
    """``ceil(nbytes / 4)`` -- the bytes/4 estimator, stated in TOKEN_ESTIMATOR."""
    return int(math.ceil(int(nbytes) / 4.0))


def text_tokens(text: str) -> int:
    return estimate_tokens(len(text.encode("utf-8")))


# --------------------------------------------------------------------------- #
# frontmatter (tolerant, yaml-independent; matches this corpus' flat shape)
# --------------------------------------------------------------------------- #
def _frontmatter_lines(text: str) -> list[str]:
    if not text.startswith("---"):
        return []
    lines = text.splitlines()
    out: list[str] = []
    for line in lines[1:]:
        if line.strip() == "---":
            return out
        out.append(line)
    return []  # never closed -> no frontmatter


def _strip_quotes(value: str) -> str:
    v = value.strip()
    if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
        return v[1:-1]
    return v


def frontmatter_fields(text: str) -> dict[str, Any]:
    """Column-0 ``key: value`` fields; block scalars (``>`` / ``|``) and block
    lists (``- item``) are folded from their indented continuation lines, and
    an inline flow list ``[a, b]`` becomes a list."""
    lines = _frontmatter_lines(text)
    out: dict[str, Any] = {}
    i = 0
    while i < len(lines):
        raw = lines[i]
        if not raw.strip() or raw[0] in " \t#":
            i += 1
            continue
        m = re.match(r"^([A-Za-z0-9_-]+):(.*)$", raw)
        if not m:
            i += 1
            continue
        key, val = m.group(1), m.group(2).strip()
        body: list[str] = []
        j = i + 1
        while j < len(lines) and (not lines[j].strip() or lines[j][0] in " \t"):
            body.append(lines[j])
            j += 1
        if val in (">", ">-", ">+", "|", "|-", "|+"):
            out[key] = " ".join(b.strip() for b in body if b.strip())
        elif not val and any(b.strip().startswith("- ") for b in body):
            out[key] = [_strip_quotes(b.strip()[2:]) for b in body if b.strip().startswith("- ")]
        elif val.startswith("[") and val.endswith("]"):
            out[key] = [_strip_quotes(x) for x in val[1:-1].split(",") if x.strip()]
        else:
            out[key] = _strip_quotes(val)
        i = j
    return out


def _skills_list(fields: dict[str, Any]) -> list[str]:
    value = fields.get("skills")
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    if isinstance(value, str) and value.strip():
        return [v.strip() for v in value.split(",") if v.strip()]
    return []


# --------------------------------------------------------------------------- #
# surfaces
# --------------------------------------------------------------------------- #
def _surface(path: Path, root: Path, file_class: str) -> dict[str, Any]:
    data = path.read_bytes()
    text = data.decode("utf-8", errors="replace")
    fields = frontmatter_fields(text)
    description = fields.get("description")
    description = description if isinstance(description, str) else ""
    rec: dict[str, Any] = {
        "path": path.resolve().relative_to(root.resolve()).as_posix(),
        "class": file_class,
        "bytes": len(data),
        "lines": len(text.splitlines()),
        "tokens": estimate_tokens(len(data)),
        "description_tokens": text_tokens(description),
    }
    if file_class == "chapter":
        rec["is_index"] = path.name == "INDEX.md"
    if file_class == "agent":
        rec["skills"] = _skills_list(fields)
    return rec


def collect_surfaces(root: Union[str, Path]) -> list[dict[str, Any]]:
    """The per-surface table, in a stable order (class, then path)."""
    root = Path(root)
    out: list[dict[str, Any]] = []
    for p in sorted((root / "commands").glob("*.md")) if (root / "commands").is_dir() else []:
        out.append(_surface(p, root, "command"))
    if (root / "skills").is_dir():
        for d in sorted(root.glob("skills/*")):
            sk = d / "SKILL.md"
            if sk.is_file():
                out.append(_surface(sk, root, "skill"))
            refs = d / "references"
            if refs.is_dir():
                for ch in sorted(refs.glob("*.md")):
                    out.append(_surface(ch, root, "chapter"))
    for p in sorted((root / "agents").glob("*.md")) if (root / "agents").is_dir() else []:
        out.append(_surface(p, root, "agent"))
    return out


# --------------------------------------------------------------------------- #
# the measurement
# --------------------------------------------------------------------------- #
def _skill_md_rel(name: str) -> str:
    return f"skills/{name}/SKILL.md"


def measure(repo_root: Union[str, Path]) -> dict[str, Any]:
    """Measure every surface + the aggregates + the budget breaches.

    Pure: reads files only, consults neither git nor the clock (those are the
    artifact writer's). Returns::

        {"schema", "estimator", "budgets", "surfaces": [...], "lanes": {...},
         "agent_dispatch": {...}, "always_loaded": {...}, "totals": {...},
         "breaches": [...]}
    """
    root = Path(repo_root)
    surfaces = collect_surfaces(root)
    by_path = {s["path"]: s for s in surfaces}

    def tokens_of(rel: str) -> Optional[int]:
        s = by_path.get(rel)
        return int(s["tokens"]) if s else None

    breaches: list[dict[str, Any]] = []

    def breach(budget: str, surface: str, measured: int) -> None:
        limit = BUDGETS[budget]
        breaches.append({
            "budget": budget, "surface": surface, "measured": measured,
            "limit": limit, "excess": measured - limit,
        })

    # per-surface budgets
    for s in surfaces:
        if s["class"] == "skill" and s["lines"] > BUDGETS["skill_md_max_lines"]:
            breach("skill_md_max_lines", s["path"], s["lines"])
        if s["class"] in ("skill", "chapter") and s["tokens"] > BUDGETS["chapter_max_tokens"]:
            breach("chapter_max_tokens", s["path"], s["tokens"])
        if s["class"] == "agent" and s["tokens"] > BUDGETS["agent_max_tokens"]:
            breach("agent_max_tokens", s["path"], s["tokens"])

    # lane start loads
    lanes: dict[str, Any] = {}
    for lane, spec in LANES.items():
        components = [f"commands/{lane}.md", _skill_md_rel(spec["skill"]), _skill_md_rel(CONVENTIONS_SKILL)]
        components += [_skill_md_rel(x) for x in spec["start_skills"]]
        detail = []
        total = 0
        missing = []
        for rel in components:
            t = tokens_of(rel)
            if t is None:
                missing.append(rel)
                detail.append({"path": rel, "tokens": 0, "present": False})
            else:
                total += t
                detail.append({"path": rel, "tokens": t, "present": True})
        lanes[lane] = {
            "tokens": total, "limit": BUDGETS["lane_start_max_tokens"],
            "over_budget": total > BUDGETS["lane_start_max_tokens"],
            "components": detail, "missing": missing,
        }
        if total > BUDGETS["lane_start_max_tokens"]:
            breach("lane_start_max_tokens", f"lane:{lane}", total)

    # always-loaded: every frontmatter description
    desc_by_class: dict[str, int] = {"skill": 0, "agent": 0, "command": 0}
    for s in surfaces:
        if s["class"] in desc_by_class:
            desc_by_class[s["class"]] += int(s["description_tokens"])
    always_total = sum(desc_by_class.values())
    always_loaded = {
        "tokens": always_total, "by_class": desc_by_class,
        "limit": BUDGETS["always_loaded_max_tokens"],
        "over_budget": always_total > BUDGETS["always_loaded_max_tokens"],
        "basis": "sum of frontmatter description tokens across skills, agents and commands",
    }
    if always_total > BUDGETS["always_loaded_max_tokens"]:
        breach("always_loaded_max_tokens", "always-loaded", always_total)

    # per-agent dispatch load
    agent_dispatch: dict[str, Any] = {}
    for s in surfaces:
        if s["class"] != "agent":
            continue
        name = Path(s["path"]).stem
        extra = []
        extra_tokens = 0
        for skill in s.get("skills", []):
            rel = _skill_md_rel(skill)
            t = tokens_of(rel)
            extra.append({"skill": skill, "path": rel, "tokens": t or 0, "present": t is not None})
            extra_tokens += t or 0
        agent_dispatch[name] = {
            "agent_tokens": s["tokens"], "skill_tokens": extra_tokens,
            "tokens": s["tokens"] + extra_tokens, "skills": extra,
        }

    # totals
    totals: dict[str, Any] = {"surfaces": len(surfaces), "tokens": sum(s["tokens"] for s in surfaces)}
    for cls in ("command", "skill", "chapter", "agent"):
        rows = [s for s in surfaces if s["class"] == cls]
        totals[cls] = {
            "count": len(rows),
            "tokens": sum(s["tokens"] for s in rows),
            "lines": sum(s["lines"] for s in rows),
            "max_tokens": max((s["tokens"] for s in rows), default=0),
            "max_lines": max((s["lines"] for s in rows), default=0),
        }
    totals["breaches"] = len(breaches)
    totals["breaches_by_budget"] = {
        b: sum(1 for x in breaches if x["budget"] == b) for b in BUDGETS
    }

    return {
        "schema": SCHEMA,
        "estimator": TOKEN_ESTIMATOR,
        "estimator_detail": "tokens = ceil(utf8_bytes / 4); not a tokenizer, a shared yardstick",
        "budgets": dict(BUDGETS),
        "lane_rule": (
            "lane command + lane SKILL.md + common-pipeline-conventions SKILL.md"
            " (+ the fixed start_skills list for architect-team); a fixed component list,"
            " not a parse of the lane prose"
        ),
        "surfaces": surfaces,
        "lanes": lanes,
        "agent_dispatch": agent_dispatch,
        "always_loaded": always_loaded,
        "totals": totals,
        "breaches": breaches,
    }


# --------------------------------------------------------------------------- #
# tree state + the durable artifact
# --------------------------------------------------------------------------- #
def _load_suite_measurement() -> Any:
    """The sibling ``suite_measurement`` module, imported by path (never on
    sys.path by default); None when it cannot be loaded."""
    try:
        import importlib.util
        sibling = Path(__file__).resolve().parent / "suite_measurement.py"
        if not sibling.is_file():
            return None
        spec = importlib.util.spec_from_file_location("ct6_suite_measurement_for_budget", sibling)
        if spec is None or spec.loader is None:
            return None
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    except Exception:  # pragma: no cover - any sibling defect degrades to the local fallback
        return None


def _git(args: list[str], root: Path) -> tuple[int, str]:
    try:
        proc = subprocess.run(
            ["git", "-C", str(root), *args],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60,
        )
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        return 127, str(exc)
    return proc.returncode, proc.stdout


def tree_state(root: Union[str, Path]) -> dict[str, Any]:
    """``{"head", "dirty", "source", "detail"}`` -- via
    ``suite_measurement.tree_digest`` when importable, else a local git read.
    ``dirty`` is None (unknown) when git is unavailable; unknown is not clean."""
    root = Path(root)
    sm = _load_suite_measurement()
    if sm is not None and hasattr(sm, "tree_digest"):
        d = sm.tree_digest(root)
        return {
            "head": d.get("head"), "dirty": d.get("dirty"), "source": d.get("source"),
            "detail": d.get("detail", ""), "digest": d.get("digest"),
            "helper": "suite_measurement.tree_digest",
        }
    rc, _ = _git(["rev-parse", "--is-inside-work-tree"], root)
    if rc != 0:
        return {"head": None, "dirty": None, "source": "unavailable",
                "detail": "not a git work tree or git unavailable", "helper": "local"}
    rc_head, head_out = _git(["rev-parse", "HEAD"], root)
    rc_status, status_out = _git(["status", "--porcelain", "--untracked-files=all"], root)
    if rc_status != 0:
        return {"head": head_out.strip() or None, "dirty": None, "source": "unavailable",
                "detail": f"git status rc={rc_status}", "helper": "local"}
    return {"head": head_out.strip() if rc_head == 0 else None,
            "dirty": bool(status_out.strip()), "source": "git", "detail": "", "helper": "local"}


def is_release_label(label: Any) -> bool:
    sm = _load_suite_measurement()
    if sm is not None and hasattr(sm, "is_release_label"):
        return bool(sm.is_release_label(label))
    return isinstance(label, str) and bool(_RE_RELEASE_LABEL.match(label.strip()))


def _safe_label(label: Optional[str]) -> str:
    text = (label or "").strip() or "unlabeled"
    return _RE_LABEL_SAFE.sub("-", text).strip("-") or "unlabeled"


def artifact_path(root: Union[str, Path], label: Optional[str], *, date: Optional[str] = None,
                  out_dir: Optional[Union[str, Path]] = None) -> Path:
    day = date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    directory = Path(out_dir) if out_dir is not None else Path(root) / DURABLE_OUT_DIR
    return directory / f"{day}-{_safe_label(label)}-{ARTIFACT_SUFFIX}.json"


def build_artifact(result: dict[str, Any], root: Union[str, Path], label: Optional[str],
                   *, timestamp: Optional[str] = None) -> dict[str, Any]:
    """The durable record: the measurement plus provenance (HEAD, dirty flag,
    label, timestamp, provisional marker)."""
    state = tree_state(root)
    release = is_release_label(label)
    dirty = state.get("dirty")
    artifact = dict(result)
    artifact.update({
        "label": label,
        "release_label": release,
        "timestamp": timestamp or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "repo_root": str(Path(root).resolve()),
        "head": state.get("head"),
        "tree_dirty": dirty,
        "tree_state": state,
        "provenance": "measured",
        # A release-shaped label on a dirty (or unknown) tree describes
        # HEAD-plus-changes, not the release: recorded, but backing nothing.
        "provisional": bool(release and dirty is not False),
    })
    return artifact


def write_artifact(result: dict[str, Any], root: Union[str, Path], label: Optional[str],
                   *, out_dir: Optional[Union[str, Path]] = None) -> Path:
    path = artifact_path(root, label, out_dir=out_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    artifact = build_artifact(result, root, label)
    path.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def format_breaches(result: dict[str, Any]) -> str:
    lines = []
    for b in result["breaches"]:
        lines.append(f"  [{b['budget']}] {b['surface']}: {b['measured']} > {b['limit']} (+{b['excess']})")
    return "\n".join(lines)


def format_summary(result: dict[str, Any]) -> str:
    t = result["totals"]
    out = [
        f"instruction-budget ({result['estimator']}): {t['surfaces']} surfaces, {t['tokens']} tokens; "
        f"{t['breaches']} breach(es).",
        f"  commands {t['command']['count']} / {t['command']['tokens']} tok; "
        f"skills {t['skill']['count']} / {t['skill']['tokens']} tok (max {t['skill']['max_lines']} lines); "
        f"chapters {t['chapter']['count']} / {t['chapter']['tokens']} tok; "
        f"agents {t['agent']['count']} / {t['agent']['tokens']} tok",
        f"  always-loaded: {result['always_loaded']['tokens']} tok (limit {result['always_loaded']['limit']})",
    ]
    for lane, info in result["lanes"].items():
        flag = " OVER" if info["over_budget"] else ""
        miss = f" missing={info['missing']}" if info["missing"] else ""
        out.append(f"  lane {lane}: {info['tokens']} tok (limit {info['limit']}){flag}{miss}")
    return "\n".join(out)


def main(argv: Optional[list[str]] = None) -> int:
    """CLI.

    Usage:
      instruction_budget.py [--root DIR] [--label vX] [--json] [--check] [--write]
    ``--check`` exits 1 when any budget is breached (listing every breach);
    ``--write`` records the artifact under ``<root>/docs/measurements/``.
    """
    import argparse

    parser = argparse.ArgumentParser(description="Instruction-budget measurement (bytes/4 estimator).")
    parser.add_argument("--root", default=".", help="repo root to measure (default: cwd)")
    parser.add_argument("--label", default=None, help="artifact label, e.g. v3.68.0 (default: unlabeled)")
    parser.add_argument("--json", action="store_true", help="emit the full JSON result")
    parser.add_argument("--check", action="store_true", help="exit 1 when any budget is breached")
    parser.add_argument("--write", action="store_true", help="record the artifact under docs/measurements/")
    parser.add_argument("--out-dir", default=None, help="override the artifact directory (with --write)")
    args = parser.parse_args(argv)

    result = measure(args.root)
    written: Optional[Path] = None
    if args.write:
        written = write_artifact(result, args.root, args.label, out_dir=args.out_dir)

    if args.json:
        payload = dict(result)
        if written is not None:
            payload["artifact_path"] = str(written)
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(format_summary(result))
        if result["breaches"]:
            print("breaches:")
            print(format_breaches(result))
        if written is not None:
            print(f"wrote {written}")

    if args.check and result["breaches"]:
        return EXIT_BREACH
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
